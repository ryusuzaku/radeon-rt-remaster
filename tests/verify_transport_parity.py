"""Phase 6 stage 2: transport parity on fixtures (docs/PHASE6_TRANSPORT_DECISION.md, test plan stage 2).

A stand-in for the proxy (`rrt_transport_host`, x86 or x64) launches the x64 renderer in `--transport-serve`
mode, hands it the scene bytes in an inherited section and drives one session over anonymous pipes. Every
frame's output digest must equal the `pixel_sha256_bgra` of the same scene and settings rendered standalone,
byte for byte; the session must be repeat-exact, end with the child reaped, and leave the host's handle count
flat after the first session. The refusal paths (bad digest, version mismatch, wrong adapter, a malformed header) must end
cleanly without a render. Needs a DXR-capable GPU; exits 77 otherwise.

The proxy itself is not involved: this stage proves the transport and the renderer's serve mode, not capture.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests'))
from verify_dxr import fixture, encode_scene  # noqa: E402

SETTINGS = (
    ('gi-1spp', ['--mode', 'gi', '--samples', '1', '--seed', '7']),
    ('gi-4spp-denoise', ['--mode', 'gi', '--samples', '4', '--seed', '3', '--denoise']),
    ('albedo', ['--mode', 'albedo']),
)


def need(value, message):
    if not value: raise AssertionError(message)


def busy_scene(triangles=300):
    random.seed(5); scene = fixture(); draw = copy.deepcopy(scene['draws'][1]); verts = []; idx = []
    for i in range(triangles):
        cx, cy, cz = random.uniform(-.9, .9), random.uniform(-.9, .9), random.uniform(.1, .7)
        for _ in range(3): verts.append([cx + random.uniform(-.08, .08), cy + random.uniform(-.08, .08), cz, 0xffffffff, random.random(), random.random()])
        idx += [3 * i, 3 * i + 1, 3 * i + 2]
    draw['ordinal'] = 2; draw['vertices'] = verts; draw['indices'] = idx; scene['draws'].append(draw); scene['attempted'] = len(scene['draws'])
    return scene


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--host', type=Path, required=True); parser.add_argument('--dxr', type=Path, required=True)
    parser.add_argument('--out', type=Path, help='directory that receives parity.json'); args = parser.parse_args()
    for path in (args.host, args.dxr):
        if not path.is_file(): print('SKIP: missing', path); return 77
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    probe = json.loads(subprocess.run([str(args.dxr), '--probe'], capture_output=True, text=True, env=env, timeout=60).stdout)
    if not probe['supported']: print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable'); return 77
    folder = Path(tempfile.mkdtemp(prefix='transport-parity-', dir=args.dxr.parent)); scenes = {}
    for name, scene in (('fixture', fixture()), ('busy', busy_scene())):
        path = folder / f'{name}.rrscene'; path.write_bytes(encode_scene(scene)); scenes[name] = path

    def standalone(scene, extra):
        process = subprocess.run([str(args.dxr), str(scene), *extra], capture_output=True, text=True, env=env, timeout=120)
        need(process.returncode == 0, (process.stdout, process.stderr)); return json.loads(process.stdout)['pixel_sha256_bgra']

    def host(scene, extra=(), host_args=(), expect_code=0):
        command = [str(args.host), '--renderer', str(args.dxr.resolve()), '--scene', str(scene), '--timeout-ms', '20000', *host_args, '--', *extra]
        process = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
        need(process.returncode == expect_code, (process.returncode, process.stdout, process.stderr)); return json.loads(process.stdout)

    def stable(report):  # everything that is not a timing or a per-run count of live handles
        return {k: ([{kk: vv for kk, vv in f.items() if kk != 'wall_ms'} for f in v] if k == 'frames' else v) for k, v in report.items()
                if k not in ('host_handles_before', 'host_handles_after', 'host_handles_each', 'host_handles_baseline')}

    results = {}
    for scene_name, scene in scenes.items():
        trailer = scene.read_bytes()[-32:].hex()
        for setting_name, extra in SETTINGS:
            want = standalone(scene, extra); report = host(scene, extra, ['--frames', '2'])
            label = f'{scene_name}/{setting_name}'
            need(report['result'] == 'transport-host-pass' and report['ack_status'] == 0 and report['scene_status'] == 0, f'{label}: session did not pass: {report}')
            need(report['host_pointer_bytes'] in (4, 8) and report['protocol_version'] == 1, f'{label}: host identity')
            frames = report['frames']; need(len(frames) == 2 and all(f['status'] == 0 for f in frames), f'{label}: frames')
            need(all(f['output_sha256'] == want for f in frames), f'{label}: transport frames {[f["output_sha256"] for f in frames]} != standalone {want}')
            need(report['stopped'] and report['stop_completed'] == 2 and report['stop_discarded'] == 0 and report['session_completed'] == 2, f'{label}: stop accounting')
            need(report['child_reaped'] is True and report['renderer_exit_code'] == 0 and report['renderer_stderr'] == '', f'{label}: child not clean: {report["renderer_stderr"]}')
            inner = json.loads(report['renderer_stdout'])
            need(inner['result'] == 'transport-serve-done' and inner['frames'] == 2 and inner['completed'] == 2 and inner['scene_sha256'] == trailer, f'{label}: renderer report {inner}')
            need(inner['last_output_sha256'] == frames[1]['output_sha256'] and inner['width'] == report['scene_width'] and inner['height'] == report['scene_height'], f'{label}: renderer report differs from the host view')
            repeat = host(scene, extra, ['--frames', '2'])
            need(stable(repeat) == stable(report), f'{label}: repeated session differs')
            results[label] = dict(standalone=want, transport=frames[0]['output_sha256'], second_frame=frames[1]['output_sha256'], wall_ms=[f['wall_ms'] for f in frames])

    fixture_scene = scenes['fixture']; gi = SETTINGS[0][1]
    refused = host(fixture_scene, gi, ['--corrupt-digest'])
    need(refused['result'] == 'transport-host-scene-refused' and refused['scene_status'] == 1 and refused['frames'] == [] and refused['stopped'] is True, f'bad digest was not refused: {refused}')
    need(refused['child_reaped'] is True and refused['renderer_exit_code'] == 0, 'bad digest left the renderer unclean')
    version = host(fixture_scene, gi, ['--min-version', '2', '--max-version', '3'])
    need(version['result'] == 'transport-host-refused' and version['ack_status'] == 1 and version['child_reaped'] is True and version['renderer_exit_code'] == 0, f'version mismatch: {version}')
    need(json.loads(version['renderer_stdout'])['result'] == 'transport-serve-refused', 'renderer did not report the refusal')
    luid = host(fixture_scene, gi, ['--wrong-luid'])
    need(luid['result'] == 'transport-host-refused' and luid['ack_status'] == 2 and luid['child_reaped'] is True and luid['renderer_exit_code'] == 0, f'adapter mismatch: {luid}')
    garbage = host(fixture_scene, gi, ['--inject-garbage'])
    need(garbage['result'] == 'transport-host-injected' and garbage['child_reaped'] is True and garbage['renderer_exit_code'] == 3, f'malformed header: {garbage}')
    need(json.loads(garbage['renderer_stdout'])['error'] == 'bad_magic', 'renderer did not name the violation')
    cycles = host(fixture_scene, gi, ['--repeat', '6'])
    each = cycles['host_handles_each']
    need(cycles['result'] == 'transport-host-pass' and len(each) == 6, f'repeated sessions: {cycles}')
    need(all(h == each[1] for h in each[1:]) and each[1] <= cycles['host_handles_baseline'] + 8, f'host handle count grows per session: baseline {cycles["host_handles_baseline"]}, then {each}')
    results['handles'] = dict(baseline=cycles['host_handles_baseline'], after_each_session=each)
    results['refusals'] = dict(bad_digest=refused['scene_status'], version_mismatch=version['ack_status'], adapter_mismatch=luid['ack_status'], malformed_exit_code=garbage['renderer_exit_code'])
    if args.out: args.out.mkdir(parents=True, exist_ok=True); (args.out / 'parity.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(result='pass', host_pointer_bytes=report['host_pointer_bytes'], cases=len(results) - 1, artifacts=str(folder))))
    return 0


if __name__ == '__main__': sys.exit(main())
