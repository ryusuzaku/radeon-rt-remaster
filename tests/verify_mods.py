"""GPU acceptance for offline texture/mesh/material replacements and isolation."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from scene_io import load_scene
from export_gltf import png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--ex', action='store_true')
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='mods-ex-' if args.ex else 'mods-classic-', dir=args.sample.parent))
    env = {k:v for k,v in os.environ.items() if not k.startswith('RRT_')}
    cli = [sys.executable, ROOT/'tools/mod_scene.py']

    def run(command, extra=None, success=True):
        result = subprocess.run([str(x) for x in command], env={**env, **(extra or {})}, text=True, capture_output=True, timeout=30)
        assert (result.returncode == 0) == success, f'{command}\n{result.stdout}\n{result.stderr}'
        return result

    def capture(name, frame):
        path = folder/(name+'.rrscene')
        run([args.sample, '--scene-fixture', '--read-frame', frame, '--pixels', folder/(name+'.pixels')] + (['--ex'] if args.ex else []),
            {'RRT_SCENE_FILE':str(path), 'RRT_SCENE_FRAME':str(frame)})
        return path

    source = capture('original', 0)
    repeat = capture('repeat', 0)
    after_reset = capture('after-reset', 6)
    before = source.read_bytes()
    scene = load_scene(source)
    baseline = (folder/'original.pixels').read_bytes()
    run([*cli, 'extract', source, folder/'edit'])
    noop = folder/'noop.rrscene'
    run([*cli, 'apply', source, '--mod', folder/'edit/mod.json', '--output', noop])
    assert noop.read_bytes() == before
    run([args.replay, noop, '--pixels', folder/'noop.pixels'])
    assert (folder/'noop.pixels').read_bytes() == baseline

    def make(kind, target, asset, name):
        manifest = folder/(name+'.json')
        report = json.loads(run([*cli, 'make', '--kind', kind, '--target', target,
            '--asset', asset.name, '--id', name, '--output', manifest]).stdout)
        assert report['dependency_sha256'] == sha256(asset.read_bytes()).hexdigest()
        return manifest

    texture = folder/'magenta.png'; texture.write_bytes(png(4,4,b'\xff\x00\xff\xff'*16))
    texture_mod = make('texture', scene['draws'][0]['texture_id'], texture, 'texture')
    geometry = dict(version=1, vertices=[[-.35,-.35,.5,0xffffffff,0,1],[0,.35,.5,0xffffffff,.5,0],[.35,-.35,.5,0xffffffff,1,1]], indices=[0,1,2])
    mesh = folder/'small-triangle.json'; mesh.write_text(json.dumps(geometry))
    mesh_mod = make('mesh', scene['draws'][2]['mesh_id'], mesh, 'mesh')
    material = folder/'linear.json'; material.write_text(json.dumps(dict(version=1, min_filter='linear', mag_filter='linear')))
    material_mod = make('material', scene['draws'][1]['material_id'], material, 'material')

    reports = []
    def apply(name, path, manifests, intended_draws, intended_quadrants):
        output = folder/(name+'.rrscene')
        command = [*cli, 'apply', path, '--output', output]
        for manifest in manifests:
            command += ['--mod', manifest]
        report = json.loads(run(command).stdout)
        assert {d['ordinal'] for d in report['matched_draws']} == intended_draws
        original_scene, updated = load_scene(path), load_scene(output)
        for original_draw, modified_draw in zip(original_scene['draws'], updated['draws']):
            if original_draw['ordinal'] not in intended_draws:
                assert original_draw == modified_draw, 'unmatched draw changed'
            else:
                for field in ('world','view','projection','viewport','scissor','ordinal'):
                    assert original_draw[field] == modified_draw[field], 'replacement changed instance context'
        pixels = folder/(name+'.pixels')
        run([args.replay, output, '--pixels', pixels])
        actual = pixels.read_bytes()
        reference = path.with_suffix('.pixels').read_bytes()
        w,h = updated['width'],updated['height']
        changes = {}
        for qx,qy in ((0,0),(1,0),(0,1),(1,1)):
            changes[(qx,qy)] = sum(actual[(y*w+x)*3:(y*w+x+1)*3] != reference[(y*w+x)*3:(y*w+x+1)*3]
                for y in range(qy*h//2,(qy+1)*h//2) for x in range(qx*w//2,(qx+1)*w//2))
            assert (changes[(qx,qy)] > 100) if (qx,qy) in intended_quadrants else changes[(qx,qy)] == 0, (name,changes)
        bgra = bytearray(w*h*4)
        for i in range(w*h):
            bgra[4*i:4*i+3] = actual[3*i:3*i+3]; bgra[4*i+3] = 255
        (folder/(name+'.png')).write_bytes(png(w,h,bgra))
        reports.append(dict(case=name, matched_draws=sorted(intended_draws), changed_pixels_by_quadrant={str(k):v for k,v in changes.items()},
                            output_sha256=report['output_sha256']))
        return output

    apply('texture-result', source, [texture_mod], {0}, {(0,1)})
    apply('mesh-result', source, [mesh_mod], {2,3}, {(1,0),(1,1)})
    apply('material-result', source, [material_mod], {1,2}, {(0,0),(1,0)})
    combined = apply('combined', source, [texture_mod,mesh_mod,material_mod], {0,1,2,3}, {(0,0),(1,0),(0,1),(1,1)})
    repeated = apply('combined-repeat', repeat, [material_mod,texture_mod,mesh_mod], {0,1,2,3}, {(0,0),(1,0),(0,1),(1,1)})
    assert combined.read_bytes() == repeated.read_bytes(), 'mod result depends on session or CLI order'
    apply('mesh-after-reset', after_reset, [mesh_mod], {2,3}, {(1,0),(1,1)})
    check = json.loads(run([*cli,'check',source,'--mod',texture_mod]).stdout)
    assert len(check['matched_draws']) == 1
    run([*cli,'apply',source,'--mod',texture_mod,'--output',source], success=False)
    assert source.read_bytes() == before
    # Reusing an asset-ID mod on a newly updated texture must not guess a match.
    run([*cli,'apply',after_reset,'--mod',texture_mod,'--output',folder/'unmatched.rrscene'], success=False)
    assert not (folder/'unmatched.rrscene').exists()
    damaged_manifest = json.loads(texture_mod.read_text())
    damaged_manifest['replacements'][0]['asset'] = 'damaged.png'
    (folder/'damaged.png').write_bytes(b'damaged dependency')
    damaged_mod = folder/'damaged-mod.json'; damaged_mod.write_text(json.dumps(damaged_manifest))
    run([*cli,'apply',source,'--mod',damaged_mod,'--output',folder/'invalid.rrscene'], success=False)
    assert not (folder/'invalid.rrscene').exists()
    run([sys.executable,ROOT/'tools/export_gltf.py',combined,folder/'combined.gltf'])
    assert source.read_bytes() == before
    (folder/'isolation-report.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps(dict(result='pass', mode='ex' if args.ex else 'classic', artifacts=str(folder),
                         cases=len(reports), unaffected_quadrants='byte-identical')))


if __name__ == '__main__':
    main()
