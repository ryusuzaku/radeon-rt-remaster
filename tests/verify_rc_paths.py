"""Renderer-owned Radiance Cache path export contract; no provider dispatch."""
import argparse
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
sys.path.insert(0, str(ROOT / 'tests'))
from inspect_rc_paths import load_paths, decode_paths, HEADER
from verify_dxr import fixture, encode_scene


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dxr', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='rc-paths-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}

    def run(command, ok=True):
        process = subprocess.run([str(args.dxr), *map(str, command)], text=True, capture_output=True,
                                 env=env, timeout=60)
        need((process.returncode == 0) == ok, (command, process.stdout, process.stderr))
        return json.loads(process.stdout) if ok else None

    probe = run(['--probe'])
    if not probe['supported']:
        return 77
    debug = ['--debug'] if probe['debug_available'] else []
    scene = folder / 'fixture.rrscene'
    scene.write_bytes(encode_scene(fixture()))
    baseline_pixels, baseline_signals = folder / 'baseline.pixels', folder / 'baseline.signals'
    run([scene, '--mode', 'gi', '--samples', 1, '--pixels', baseline_pixels,
         '--signals', baseline_signals, *debug])

    pixels, signals, paths = folder / 'paths.pixels', folder / 'paths.signals', folder / 'paths.rcpaths'
    report = run([scene, '--mode', 'gi', '--samples', 1, '--pixels', pixels, '--signals', signals,
                  '--rc-paths', paths, *debug])
    data = load_paths(paths)
    need(pixels.read_bytes() == baseline_pixels.read_bytes(), 'path export changed ordinary pixels')
    need(signals.read_bytes() == baseline_signals.read_bytes(), 'path export changed ordinary signals')
    need(report['rc_path_exports'] == 1 and report['rc_path_stride'] == 128, 'false path export report')
    need(report['rc_path_queries'] == len(data['queries']) and
         report['rc_path_training'] == len(data['training']) == min(len(data['queries']), 512), 'path count mismatch')
    need(len(data['queries']) > 0 and data['primary_hits'] > 1000, 'insufficient renderer path coverage')
    need(report['scene_build_submissions'] == 1 and report['readback_submissions'] >= 1, 'path submission accounting')

    repeat = folder / 'repeat.rcpaths'
    repeat_report = run([scene, '--mode', 'gi', '--samples', 1, '--rc-paths', repeat, *debug])
    need(paths.read_bytes() == repeat.read_bytes(), 'path export nondeterminism')
    need(repeat_report['rc_path_queries'] == report['rc_path_queries'], 'repeat query count mismatch')
    streamed = subprocess.run([str(args.dxr), str(scene), '--mode', 'gi', '--samples', '1', '--rc-stream', *debug],
                              capture_output=True, env=env, timeout=60)
    need(streamed.returncode == 0 and streamed.stderr == b'' and streamed.stdout == paths.read_bytes(), 'RC stream differs from file artifact')

    encoded = paths.read_bytes()
    malformed = [encoded[:-1], encoded + b'x']
    changed = bytearray(encoded); struct.pack_into('<I', changed, 8, 2); malformed.append(changed)
    changed = bytearray(encoded); struct.pack_into('<I', changed, 32, 0); changed[-32:] = sha256(changed[:-32]).digest(); malformed.append(changed)
    changed = bytearray(encoded); struct.pack_into('<f', changed, HEADER.size, float('nan')); changed[-32:] = sha256(changed[:-32]).digest(); malformed.append(changed)
    changed = bytearray(encoded); struct.pack_into('<f', changed, HEADER.size + 3 * 4, .5); changed[-32:] = sha256(changed[:-32]).digest(); malformed.append(changed)
    for candidate in malformed:
        try:
            decode_paths(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted malformed RC path artifact')

    before = paths.read_bytes()
    run([scene, '--mode', 'gi', '--samples', 1, '--rc-paths', paths], ok=False)
    need(paths.read_bytes() == before, 'existing path artifact was overwritten')
    for index, invalid in enumerate((['--mode', 'albedo'], ['--samples', 2], ['--interactive'],
                                     ['--denoise'], ['--temporal'])):
        run([scene, *invalid, '--rc-paths', folder / f'invalid-{index}.rcpaths'], ok=False)

    collision = folder / 'collision.out'
    run([scene, '--mode', 'gi', '--samples', 1, '--rc-paths', collision, '--pixels', collision], ok=False)
    for invalid in (['--rc-stream', '--rc-paths', folder/'mixed.rcpaths'], ['--rc-stream', '--pixels', folder/'mixed.pixels'],
                    ['--rc-stream', '--samples', 2], ['--rc-stream', '--interactive']):
        process=subprocess.run([str(args.dxr),str(scene),*map(str,invalid)],capture_output=True,env=env,timeout=60)
        need(process.returncode != 0 and process.stdout == b'', 'invalid RC stream mode accepted')
    summary = dict(result='pass', query_count=len(data['queries']), training_count=len(data['training']),
                   primary_hits=data['primary_hits'], artifact_sha256=data['artifact_sha256'],
                   source_rgb_sha256=data['source_rgb_sha256'], maximum_factor_error=data['maximum_factor_error'],
                   debug_layer_tested=bool(debug), artifacts=str(folder))
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    sys.exit(main())
