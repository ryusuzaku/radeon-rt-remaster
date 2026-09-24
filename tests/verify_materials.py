"""GPU material-ID binding, numerical direct BRDF, diffuse emission transport and isolation."""
import argparse
import copy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_dxr import fixture, encode_scene
from verify_dxr_resolution import resized
from material_inputs import compile_materials
from inspect_signals import load_signals, validated_records


def reference_brdf(base, roughness, metallic, light, view=(0, 0, -1)):
    # Independent double-precision reference for the flat fixture: N=(0,0,-1).
    length = math.sqrt(sum(x*x for x in light))
    direction = [x/length for x in light]
    nl = max(0, -direction[2])
    nv = max(0, -view[2])
    if nl == 0 or nv == 0:
        return [0, 0, 0]
    half_vector = [a+b for a, b in zip(direction, view)]
    half_length = math.sqrt(sum(x*x for x in half_vector))
    nh = -half_vector[2]/half_length
    a2 = roughness**4
    distribution = a2/(math.pi*(1-nh*nh+nh*nh*a2)**2)
    visibility = .5/(nl*math.sqrt(nv*nv*(1-a2)+a2)+nv*math.sqrt(nl*nl*(1-a2)+a2))
    vh = sum(a*b for a, b in zip(view, half_vector))/half_length
    power = (1-vh)**5
    return [(b*(1-metallic)*.96*(1-power)/math.pi + distribution*visibility*
             ((.04*(1-metallic)+b*metallic)*(1-power)+power))*nl for b in base]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dxr', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='materials-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    def run(command, ok=True):
        result = subprocess.run([str(args.dxr), *map(str, command)], text=True, capture_output=True, env=env, timeout=60)
        assert (result.returncode == 0) == ok, f'{command}\n{result.stdout}\n{result.stderr}'
        return json.loads(result.stdout) if ok else None
    probe = run(['--probe'])
    if not probe['supported']:
        return 77
    debug = ['--debug'] if probe['debug_available'] else []
    scene = fixture(); source = folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    ground, foreground = (d['material_id'] for d in scene['draws'])
    def sidecar(name, entries):
        path = folder/f'{name}.rrmat'
        path.write_bytes(compile_materials(dict(schema='rrt-materials', version=1, materials=entries), scene))
        return path
    reports = {}
    def render(name, extra=(), mode='relit', material=None, scene_path=source):
        pixels, signals = folder/f'{name}.pixels', folder/f'{name}.signals'
        command = [scene_path, '--mode', mode, '--pixels', pixels, '--signals', signals, *debug, *extra]
        if material is not None:
            command += ['--materials', material]
        report = run(command)
        image = load_signals(signals)
        rows = list(validated_records(image, image.records()))
        assert report['requested_buffer_bytes'] <= report['requested_buffer_limit_bytes']
        assert report['timed_samples'] == report['dispatches'] and report['scene_build_submissions'] == 1
        reports[name] = report
        return pixels.read_bytes(), rows, signals.read_bytes()
    baseline = render('legacy', mode='albedo')
    empty = sidecar('empty', [])
    assert render('empty', mode='albedo', material=empty) == baseline
    tint = sidecar('tint', [dict(target=foreground, base_color=[.5, .75, .25])])
    tinted = render('tint', mode='albedo', material=tint)
    center, floor = 48*128+64, 30*128+30
    assert tinted[1][floor] == baseline[1][floor]
    for value, expected in zip(tinted[1][center][8:11], [240/255*.5, 128/255*.75, 32/255*.25]):
        assert abs(value-expected) < 1e-6
    assert reports['tint']['pbr_draws'] == reports['tint']['material_records'] == 1
    assert reports['tint']['material_sha256'] == sha256(tint.read_bytes()).hexdigest()
    assert render('normals-base', mode='normals')[0] == render('normals-pbr', mode='normals', material=tint)[0]
    max_error = 0
    for roughness in (.05, .3, 1):
        for metallic in (0, .5, 1):
            material = sidecar(f'brdf-{roughness}-{metallic}', [dict(target=ground, roughness=roughness, metallic=metallic)])
            for label, light in (('normal', [0, 0, -1]), ('angled', [.6, .3, -1]), ('tangent', [1, 0, 0])):
                name = f'brdf-{roughness}-{metallic}-{label}'
                _, rows, _ = render(name, ['--no-shadows', '--ambient', '0', '--light-intensity', '1', '--light', *light], material=material)
                expected = reference_brdf([176/255]*3, roughness, metallic, light)
                for actual, target in zip(rows[floor][:3], expected):
                    error = abs(actual-target)/max(1, abs(target)); max_error = max(max_error, error)
                    assert error < 3e-4, (name, actual, target, error)
    tilted = sidecar('tilted', [dict(target=ground, roughness=.3, metallic=.5)])
    _, rows, _ = render('tilted-view', ['--yaw', '20', '--no-shadows', '--ambient', '0', '--light-intensity', '1', '--light', '0', '0', '-1'], material=tilted)
    view = (-math.sin(math.radians(20)), 0, -math.cos(math.radians(20)))
    assert rows[floor][15] == 1
    for actual, target in zip(rows[floor][:3], reference_brdf([176/255]*3, .3, .5, [0, 0, -1], view)):
        assert abs(actual-target)/max(1, abs(target)) < 3e-4
    emitted = sidecar('emitted', [dict(target=foreground, base_color=[0, 0, 0], emissive=[4, .5, 0])])
    _, rows, _ = render('emission', ['--ambient', '0', '--light-intensity', '0'], material=emitted)
    assert rows[center][:3] == (4, .5, 0) and rows[floor][:3] == (0, 0, 0)
    # Emissive secondary hits contribute through the existing diffuse bounce.
    _, bounced, _ = render('emission-bounce', ['--ambient', '0', '--light-intensity', '0', '--samples', '64'], mode='gi', material=emitted)
    # Unjittered guide IDs do not describe every jittered sample at silhouettes.
    # Restrict this transport oracle to a ground interior away from both silhouettes.
    interior = [y*128+x for y in range(20, 76) for x in range(20, 45)]
    dark = sidecar('dark', [dict(target=foreground, base_color=[0, 0, 0])])
    _, dark_rows, _ = render('dark-bounce', ['--ambient', '0', '--light-intensity', '0', '--samples', '64'], mode='gi', material=dark)
    received = sum(bounced[i][0]-dark_rows[i][0] for i in interior)
    assert received > 1, 'emission did not reach diffuse ground'
    metal = sidecar('metal-ground', [dict(target=foreground, base_color=[0, 0, 0], emissive=[4, .5, 0]), dict(target=ground, metallic=1)])
    _, metallic_rows, _ = render('no-specular-bounce', ['--ambient', '0', '--light-intensity', '0', '--samples', '16'], mode='gi', material=metal)
    assert all(metallic_rows[i][:3] == (0, 0, 0) for i in interior), 'diffuse bounce leaked through a metal'
    colored = ['--light-color', '.2', '.3', '.4', '--light-intensity', '2', '--ambient', '.1', '--temporal', '--samples', '4']
    expected = render('colored', colored, mode='gi', material=tint)
    assert render('lighting-history', [*colored, '--lighting-test'], mode='gi', material=tint) == expected
    assert reports['lighting-history']['history_resets'] == 9
    assert render('native', [*colored, '--async-test'], mode='gi', material=tint) == expected
    assert reports['native']['history_resets'] == 4
    # A PBR material must retain the visibility test, not just the BRDF colour.
    shadowed = render('pbr-shadow', ['--light', '.6', '.3', '-1'], material=tilted)[1]
    unshadowed = render('pbr-unshadowed', ['--no-shadows', '--light', '.6', '.3', '-1'], material=tilted)[1]
    assert sum(a[:3] != b[:3] for a, b in zip(shadowed, unshadowed)) > 50
    assert all(x <= y+1e-6 for a, b in zip(shadowed, unshadowed) for x, y in zip(a[:3], b[:3]))
    # An override applies to every matching ID, not to a frame-specific ordinal.
    shared = copy.deepcopy(scene); shared['draws'][1]['texture'] = shared['draws'][0]['texture']
    shared_path = folder/'shared.rrscene'; shared_path.write_bytes(encode_scene(shared))
    only_ground = sidecar('shared', [dict(target=ground, metallic=.5)])
    render('shared-id', material=only_ground, scene_path=shared_path)
    assert reports['shared-id']['pbr_draws'] == 2 and reports['shared-id']['material_records'] == 1
    # Full-HD PBR runs omit the large diagnostic dump, retaining pixels and budget evidence.
    hd_source = folder/'hd.rrscene'; hd_source.write_bytes(encode_scene(resized(1920, 1080)))
    hd_material = sidecar('hd', [dict(target=ground, roughness=.3, metallic=.5),
                                dict(target=foreground, emissive=[2, .1, .2])])
    hd_reference = None
    for name in ('hd', 'hd-repeat'):
        out = folder/f'{name}.pixels'
        info = run([hd_source, '--materials', hd_material, '--mode', 'gi', '--samples', '4',
                    '--temporal', '--denoise', '--pixels', out, *debug])
        assert info['pbr_draws'] == 2 and info['samples'] == info['timed_samples'] == 4
        assert info['peak_requested_bytes'] <= info['requested_buffer_limit_bytes']
        pixels = out.read_bytes()
        assert len(pixels) == 1920*1080*3
        if hd_reference is None:
            hd_reference = pixels
        else:
            assert pixels == hd_reference
        reports[name] = info
    raw = bytearray(tint.read_bytes())
    malformed = {'truncated': bytes(raw[:-1]), 'checksum': bytes(raw[:-1]+bytes([raw[-1]^1]))}
    for label, offset, payload in (
        ('magic', 0, b'BADMAT1\0'), ('version', 8, struct.pack('<I', 2)), ('count', 12, struct.pack('<I', 4097)),
        ('unknown-id', 16, bytes(32)), ('nan', 48, struct.pack('<f', float('nan'))),
        ('base-high', 48, struct.pack('<f', 2)), ('rough-zero', 60, struct.pack('<f', 0)),
        ('rough-high', 60, struct.pack('<f', 2)), ('emission-negative', 64, struct.pack('<f', -1)),
        ('emission-high', 64, struct.pack('<f', 33)), ('metallic-high', 76, struct.pack('<f', 2))):
        changed = bytearray(raw[:-32]); changed[offset:offset+len(payload)] = payload
        malformed[label] = bytes(changed)+sha256(changed).digest()
    duplicate = raw[:16]+raw[16:-32]*2; struct.pack_into('<I', duplicate, 12, 2)
    malformed['duplicate'] = bytes(duplicate)+sha256(duplicate).digest()
    unsorted = bytearray(metal.read_bytes()[:-32]); unsorted[16:80], unsorted[80:144] = unsorted[80:144], unsorted[16:80]
    malformed['unsorted'] = bytes(unsorted)+sha256(unsorted).digest()
    trailing = raw[:-32]+b'x'; malformed['trailing'] = bytes(trailing)+sha256(trailing).digest()
    for label, data in malformed.items():
        bad, out = folder/f'bad-{label}.rrmat', folder/f'bad-{label}.pixels'; bad.write_bytes(data)
        run([source, '--materials', bad, '--pixels', out], ok=False)
        assert not out.exists()
    for extra in (['--light-color', 'nan', '0', '0'], ['--light-color', '2', '0', '0'],
                  ['--light-intensity', '-1'], ['--ambient', '33'], ['--lighting-test']):
        run([source, *extra], ok=False)
    result = dict(result='pass', capabilities=probe, cases=reports, max_brdf_relative_error=max_error,
                  diffuse_received_red_sum=received, rejected_binary_cases=len(malformed), artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
