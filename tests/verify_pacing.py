"""Waitable DXGI admission and responsive lifecycle; not scanout latency measurement."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from verify_dxr_resolution import resized, encode_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dxr', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='pacing-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}

    def run(extra, ok=True):
        result = subprocess.run([str(args.dxr), *map(str, extra)], env=env, text=True,
                                capture_output=True, timeout=30)
        assert (result.returncode == 0) == ok, f'{extra}\n{result.stdout}\n{result.stderr}'
        return json.loads(result.stdout) if ok else None

    probe = run(['--probe'])
    if not probe['supported']:
        return 77
    debug = ['--debug'] if probe['debug_available'] else []
    reports = {}
    for width, height in ((128, 96), (257, 129), (1920, 1080)):
        source = folder/f'{width}.rrscene'
        source.write_bytes(encode_scene(resized(width, height)))
        reference = None
        allocation = None
        for label, extra in (
            ('headless', ['--samples', '7']),
            ('unpaced', ['--samples', '64', '--async-close-test', '--no-frame-pacing']),
            ('paced', ['--samples', '64', '--async-close-test']),
            ('lifecycle', ['--samples', '64', '--pacing-test']),
            ('repeat', ['--samples', '64', '--pacing-test']),
        ):
            pixels, signals = folder/f'{width}-{label}.pixels', folder/f'{width}-{label}.signals'
            command = [source, '--mode', 'gi', '--temporal', '--denoise', '--pixels', pixels, *debug, *extra]
            if width != 1920:
                command += ['--signals', signals]
            report = run(command)
            payload = (pixels.read_bytes(), signals.read_bytes() if width != 1920 else None)
            if reference is None:
                reference, allocation = payload, report['requested_buffer_bytes']
            assert payload == reference, f'{width} {label}: admission changed output'
            assert report['samples'] == report['dispatches'] == report['timed_samples'] == 7
            assert report['history_resets'] == 0 and report['scene_build_submissions'] == 1
            assert report['mode'] == 3 and report['denoised'] and report['temporal']
            assert report['requested_buffer_bytes'] == allocation
            assert report['peak_requested_bytes'] <= report['requested_buffer_limit_bytes']
            assert report['max_inflight_submissions'] <= 4
            if label in ('headless', 'unpaced'):
                assert report['maximum_frame_latency'] == report['pacing_waits'] == report['pacing_ready'] == 0
            else:
                assert report['maximum_frame_latency'] == 1
                assert report['pacing_ready'] == report['display_submissions'] >= 7
                assert report['pacing_waits'] == sum(report[k] for k in ('pacing_ready', 'pacing_messages', 'pacing_timeouts'))
                assert report['pacing_wait_ms'] >= 0
            if label != 'headless':
                assert report['render_readbacks'] == report['readback_submissions'] == 1
                assert report['display_verified'] == 0 and report['display_buffer_mask'] == 3
            if label in ('lifecycle', 'repeat'):
                assert report['pacing_test_mask'] == 7  # Actual event, message and timeout wait branches.
                assert report['display_resizes'] == 1 and report['display_suspended_ticks'] >= 1
            reports[f'{width}-{label}'] = report
    for extra in (['--no-frame-pacing'], ['--interactive', '--gdi', '--no-frame-pacing'],
                  ['--pacing-test'], ['--pacing-test', '--samples', '64', '--no-frame-pacing'],
                  ['--pacing-test', '--samples', '64', '--window-test']):
        run([source, *extra], ok=False)
    result = dict(result='pass', capabilities=probe, cases=reports, artifacts=str(folder),
                  qualification='Hidden-window DXGI admission and controlled lifecycle; synthetic wait outcomes are separate from real DXGI readiness. No input-to-scanout latency claim.')
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
