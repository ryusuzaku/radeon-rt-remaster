"""Real-GPU capture/replay gate. Artifacts deliberately remain in the build tree."""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scene_io import load_scene, SceneError
from export_gltf import png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--ex', action='store_true')
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='scene-ex-' if args.ex else 'scene-classic-', dir=args.sample.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}

    def run(command, extra=None, success=True):
        process = subprocess.run([str(x) for x in command], env={**env, **(extra or {})}, capture_output=True, text=True, timeout=30)
        if success:
            assert process.returncode == 0, f'{command}\n{process.stdout}\n{process.stderr}'
        else:
            assert process.returncode != 0, f'unexpected success: {command}'
        return process

    def sample(name, frame, system=False, fixture=True, extra=None):
        scene = folder / (name + '.rrscene')
        pixels = folder / (name + '.pixels')
        command = [args.sample, '--runtime', 'system' if system else 'proxy', '--read-frame', frame, '--pixels', pixels]
        if args.ex:
            command += ['--ex']
        if fixture:
            command += ['--scene-fixture']
        run(command, dict(RRT_SCENE_FILE=str(scene), RRT_SCENE_FRAME=str(frame), **(extra or {})))
        return scene, pixels.read_bytes()

    captured = {}
    comparisons = []
    for frame in (0, 1, 6, 7):
        _, baseline = sample(f'native-{frame}', frame, system=True)
        path, observed = sample(f'capture-{frame}', frame)
        assert observed == baseline, 'capture changed game pixels'
        scene = load_scene(path)
        assert scene['complete'] and scene['attempted'] == 4 and len(scene['draws']) == 4, scene['rejected']
        assert scene['frame'] == frame and scene['width'] == (256 if frame < 6 else 320)
        assert len({d['mesh_id'] for d in scene['draws']}) == 2
        assert len({d['texture_id'] for d in scene['draws']}) == 2
        replay_pixels = folder / f'replay-{frame}.pixels'
        report = json.loads(run([args.replay, path, '--pixels', replay_pixels]).stdout)
        actual = replay_pixels.read_bytes()
        assert actual == baseline, f'frame {frame}: {sum(a != b for a, b in zip(actual, baseline))} different channels'
        comparisons.append(dict(frame=frame, bytes=len(actual), differing_channels=0, max_channel_error=0,
                                reference_sha256=sha256(baseline).hexdigest(), replay_sha256=sha256(actual).hexdigest()))
        assert report['complete'] and len(report['draws']) == 4
        # All four quadrants must contain rendered pixels, not just clear color.
        width, height = scene['width'], scene['height']
        if frame == 0:
            for name, bgr in (('reference', baseline), ('replay', actual)):
                bgra = bytearray(width*height*4)
                for i in range(width*height):
                    bgra[i*4:i*4+3] = bgr[i*3:i*3+3]; bgra[i*4+3] = 255
                (folder / (name + '.png')).write_bytes(png(width, height, bgra))
        for qx, qy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            colored = sum(actual[(y*width+x)*3:(y*width+x+1)*3] != b'\x50\x28\x14'
                          for y in range(qy*height//2, (qy+1)*height//2)
                          for x in range(qx*width//2, (qx+1)*width//2))
            assert colored > 100
        captured[frame] = path

    (folder / 'image-diff.json').write_text(json.dumps(comparisons, indent=2) + '\n')

    repeated, _ = sample('repeat', 0)
    assert repeated.read_bytes() == captured[0].read_bytes(), 'scene not byte-stable across sessions'
    assert load_scene(captured[0])['draws'][0]['texture_id'] != load_scene(captured[1])['draws'][0]['texture_id'], 'stale texture shadow'
    prefix = folder / 'draw-prefix.pixels'
    run([args.replay, captured[0], '--pixels', prefix, '--draw-count', 1])
    assert prefix.read_bytes() != (folder / 'replay-0.pixels').read_bytes(), 'draw prefix ignored'

    partial, _ = sample('shader', 0, fixture=False)
    parsed = load_scene(partial)
    assert not parsed['complete'] and len(parsed['draws']) == 2
    assert parsed['rejected'] == [dict(ordinal=1, reason='programmable_shader')]
    assert 'incomplete scene' in run([args.replay, partial], success=False).stderr
    run([args.replay, partial, '--allow-partial', '--pixels', folder / 'partial.pixels'])

    for case, reason, accepted in (
        ('surface-write', 'missing_or_invalid_resource_payload', 0),
        ('partial-discard', 'missing_or_invalid_resource_payload', 2),
        ('wireframe', 'unsupported_fixed_function_state', 0),
        ('no-clear', 'unsupported_or_missing_clear', 4),
        ('draw-budget', 'capture_budget_exceeded', 4096),
    ):
        path = folder / (case + '.rrscene')
        run([args.sample, '--scene-case', case] + (['--ex'] if args.ex else []), {'RRT_SCENE_FILE': str(path)})
        negative = load_scene(path)
        assert not negative['complete'] and len(negative['draws']) == accepted, (case, negative['rejected'])
        assert {r['reason'] for r in negative['rejected']} == {reason}
        run([args.replay, path], success=False)
        assert path.stat().st_size < 64*1024*1024

    # Existing output and unavailable paths must never change rendering.
    before = captured[0].read_bytes()
    run([args.sample, '--scene-fixture', '--read-frame', 0, '--pixels', folder / 'collision.pixels'] + (['--ex'] if args.ex else []),
        {'RRT_SCENE_FILE': str(captured[0])})
    assert captured[0].read_bytes() == before
    assert (folder / 'collision.pixels').read_bytes() == (folder / 'capture-0.pixels').read_bytes()
    run([args.sample, '--scene-fixture'], {'RRT_SCENE_FILE': str(folder / 'missing' / 'scene.rrscene')})
    disabled, disabled_pixels = sample('disabled', 0, extra={'RRT_PROXY_DISABLE': '1'})
    assert not disabled.exists() and disabled_pixels == (folder / 'capture-0.pixels').read_bytes()

    # Both independent readers reject corruption, even when its outer checksum
    # was recomputed. No malformed file reaches D3D device creation.
    original = captured[0].read_bytes()
    mutations = {'truncated': original[:-1], 'checksum': original[:-1] + bytes([original[-1] ^ 1])}
    def changed(name, offset, payload):
        data = bytearray(original[:-32]); data[offset:offset+len(payload)] = payload
        mutations[name] = bytes(data) + sha256(data).digest()
    changed('version', 8, struct.pack('<I', 2))
    changed('dimensions', 16, struct.pack('<I', 0xffffffff))
    changed('counts', 36, struct.pack('<I', 0xffffffff))
    changed('missing_draw', 28, struct.pack('<I', 5))
    changed('vertex_count', 44+12, struct.pack('<I', 0xffffffff))
    changed('asset_hash', 44+20, bytes(32))
    changed('nan_transform', 44+116, struct.pack('<f', float('nan')))
    data = original[:-32] + b'extra'
    mutations['trailing'] = data + sha256(data).digest()
    for name, data in mutations.items():
        path = folder / (name + '.rrscene'); path.write_bytes(data)
        run([args.replay, path, '--inspect'], success=False)
        try:
            load_scene(path)
        except SceneError:
            pass
        else:
            raise AssertionError('Python reader accepted ' + name)

    gltf = folder / 'capture.gltf'
    run([sys.executable, ROOT / 'tools/export_gltf.py', captured[0], gltf])
    document = json.loads(gltf.read_text())
    assert document['asset']['version'] == '2.0' and len(document['nodes']) == 4
    blob = base64.b64decode(document['buffers'][0]['uri'].split(',')[1])
    assert len(blob) == document['buffers'][0]['byteLength']
    for view in document['bufferViews']:
        assert view['byteOffset'] % 4 == 0 and view['byteOffset'] + view['byteLength'] <= len(blob)
    for image in document['images']:
        image_bytes = base64.b64decode(image['uri'].split(',')[1]); assert image_bytes.startswith(b'\x89PNG\r\n\x1a\n')
        assert struct.unpack_from('>2I', image_bytes, 16) == (2, 2)
    prior = gltf.read_bytes()
    run([sys.executable, ROOT / 'tools/export_gltf.py', captured[0], gltf], success=False)
    assert gltf.read_bytes() == prior
    run([sys.executable, ROOT / 'tools/export_gltf.py', partial, folder / 'partial.gltf'], success=False)
    print(json.dumps(dict(result='pass', mode='ex' if args.ex else 'classic', frames=[0,1,6,7], exact_pixels=True,
                         malformed_files=len(mutations), artifacts=str(folder))))


if __name__ == '__main__':
    main()
