"""Phase 6 stage 2, slice B: the opt-in transport client inside the real proxy (docs/TRANSPORT_PROTOCOL.md).

The D3D9 smoke fixture runs through the proxy (`d3d9.dll`, x86) with scene capture on and
RRT_TRANSPORT_RENDERER pointing at the x64 `rrt_dxr.exe`. The proxy hands the captured frame's scene to a worker that
launches the renderer, drives a transport session and writes the RRT_TRANSPORT_RESULT file. Asserted:

  * raster baseline: the game's pixels equal the `--runtime system` baseline exactly, with the transport on, and
    equal it when the transport fails (missing renderer, a renderer that rejects its arguments, a renderer killed
    mid-session) -- the client never changes what the game draws and never hangs it;
  * parity: the digest the renderer returns for the captured scene equals a standalone `rrt_dxr` render of the very
    scene file the proxy wrote, for every captured frame and extent;
  * containment: the renderer is reaped and its process is gone when the game exits; without the opt-in, or with
    RRT_PROXY_DISABLE=1, nothing is started and no result file appears.

Needs an interactive desktop (the fixture presents a window) and a DXR-capable GPU; exits 77 without DXR.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SETTINGS = '--mode gi --samples 1 --seed 7'
FRAMES = (0, 1, 6, 7)


def need(value, message):
    if not value: raise AssertionError(message)


def alive(pid):
    out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=30).stdout
    return f'"{pid}"' in out


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sample', type=Path, required=True); parser.add_argument('--dxr', type=Path, required=True)
    parser.add_argument('--ex', action='store_true'); args = parser.parse_args()
    sample, dxr = args.sample.resolve(), args.dxr.resolve()
    for path in (sample, dxr):
        if not path.is_file(): print('SKIP: missing', path); return 77
    base_env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    probe = json.loads(subprocess.run([str(dxr), '--probe'], capture_output=True, text=True, env=base_env, timeout=60).stdout)
    if not probe['supported']: print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable'); return 77
    folder = Path(tempfile.mkdtemp(prefix='transport-proxy-ex-' if args.ex else 'transport-proxy-', dir=sample.parent))

    def game(name, frame, system=False, env=None):
        scene, pixels, result = folder / f'{name}.rrscene', folder / f'{name}.pixels', folder / f'{name}.result.json'
        variables = dict(base_env); variables.update(RRT_SCENE_FILE=str(scene), RRT_SCENE_FRAME=str(frame), RRT_TRANSPORT_RESULT=str(result)); variables.update(env or {})
        command = [str(sample), '--runtime', 'system' if system else 'proxy', '--read-frame', str(frame), '--pixels', str(pixels), '--scene-fixture'] + (['--ex'] if args.ex else [])
        process = subprocess.run(command, env=variables, capture_output=True, text=True, timeout=180)
        need(process.returncode == 0, f'{name}: game failed ({process.returncode}): {process.stdout}\n{process.stderr}')
        return scene, pixels.read_bytes(), (json.loads(result.read_text(encoding='utf-8')) if result.exists() else None)

    on = dict(RRT_TRANSPORT_RENDERER=str(dxr), RRT_TRANSPORT_ARGS=SETTINGS, RRT_TRANSPORT_TIMEOUT_MS='20000')
    report = {}
    for frame in FRAMES:
        _, baseline, none = game(f'native-{frame}', frame, system=True); need(none is None, 'the system runtime produced a transport result')
        scene, pixels, result = game(f'transport-{frame}', frame, env=on)
        need(pixels == baseline, f'frame {frame}: the transport changed the game pixels')
        need(result is not None and result['result'] == 'transport-session-pass' and result['error'] == '', f'frame {frame}: session did not pass: {result}')
        need(result['host_pointer_bytes'] == 4 and result['ack_status'] == 0 and result['scene_status'] == 0, f'frame {frame}: session identity {result}')
        need(len(result['frames']) == 1 and result['frames'][0]['status'] == 0 and result['stopped'] and result['stop_completed'] == 1, f'frame {frame}: frame accounting')
        need(result['child_reaped'] is True and result['renderer_exit_code'] == 0 and result['renderer_stderr'] == '' and not alive(result['renderer_pid']), f'frame {frame}: renderer not cleanly gone')
        standalone = subprocess.run([str(dxr), str(scene), *SETTINGS.split()], capture_output=True, text=True, env=base_env, timeout=120)
        need(standalone.returncode == 0, standalone.stderr)
        want = json.loads(standalone.stdout)['pixel_sha256_bgra']
        need(result['frames'][0]['output_sha256'] == want, f'frame {frame}: transported digest {result["frames"][0]["output_sha256"]} != standalone render of the captured scene {want}')
        report[f'frame-{frame}'] = dict(extent=[result['scene_width'], result['scene_height']], digest=want, wall_ms=result['frames'][0]['wall_ms'])

    _, baseline, _ = game('native-fault', 0, system=True)
    faults = {
        'missing-renderer': (dict(on, RRT_TRANSPORT_RENDERER=str(folder / 'missing' / 'rrt_dxr.exe')), 'RRT_TRANSPORT_RENDERER'),
        'bad-renderer-option': (dict(on, RRT_TRANSPORT_ARGS='--no-such-option'), 'renderer closed the transport'),
        'renderer-killed': (dict(on, RRT_TRANSPORT_TEST_KILL='1'), ''),
    }
    for name, (env, text) in faults.items():
        _, pixels, result = game(f'fault-{name}', 0, env=env)
        need(pixels == baseline, f'{name}: a transport failure changed the game pixels')
        need(result is not None and result['result'] == 'transport-session-error' and text in result['error'] and result['error'], f'{name}: failure not reported: {result}')
        if 'renderer_pid' in result and result['renderer_pid']:
            need(result['child_reaped'] is True and not alive(result['renderer_pid']), f'{name}: renderer left running')
        report[f'fault-{name}'] = result['error']
    for name, env in (('no-opt-in', dict()), ('proxy-disabled', dict(on, RRT_PROXY_DISABLE='1'))):
        scene, pixels, result = game(f'control-{name}', 0, env=env)
        need(pixels == baseline and result is None, f'{name}: pixels differ or a transport result appeared')
        report[f'control-{name}'] = 'no result file'
    (folder / 'transport-proxy.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(result='pass', ex=args.ex, frames=len(FRAMES), faults=len(faults), artifacts=str(folder))))
    return 0


if __name__ == '__main__': sys.exit(main())
