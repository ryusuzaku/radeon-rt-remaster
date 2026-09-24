"""Asynchronous slot reuse, sparse readback, teardown and exact-render parity."""
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
    folder = Path(tempfile.mkdtemp(prefix='async-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    def run(command, ok=True):
        result = subprocess.run([str(x) for x in command], env=env, text=True, capture_output=True, timeout=90)
        assert (result.returncode == 0) == ok, f'{command}\n{result.stdout}\n{result.stderr}'
        return result
    probe = json.loads(run([args.dxr, '--probe']).stdout)
    if not probe['supported']: return 77
    debug = ['--debug'] if probe['debug_available'] else []
    reports = {}
    for width, height, samples in ((128, 96, 32), (257, 129, 16), (1920, 1080, 4)):
        source = folder/f'{width}.rrscene'; source.write_bytes(encode_scene(resized(width, height)))
        def render(label, extra, export=True):
            pixels = folder/f'{width}-{label}.pixels'; signals = folder/f'{width}-{label}.signals'
            command = [args.dxr, source, '--mode', 'gi', '--temporal', '--denoise', '--pixels', pixels, *debug, *extra]
            if export: command += ['--signals', signals]
            report = json.loads(run(command).stdout)
            assert report['frame_slots'] == 4 and report['frame_slot_mask'] == 15
            assert 0 <= report['max_inflight_submissions'] <= 4
            assert report['timed_samples'] == report['dispatches'] and report['scene_build_submissions'] == 1
            assert report['mode'] == 3 and report['denoised'] and report['temporal'], 'unrendered controls changed output provenance'
            assert report['peak_requested_bytes'] <= report['requested_buffer_limit_bytes']
            return pixels.read_bytes(), signals.read_bytes() if export else None, report
        # Avoid retaining several 285 MiB HD dumps in every default test run.
        export = width != 1920
        raw, raw_signals, synchronous = render('headless', ['--samples', str(samples)], export)
        moved, moved_signals, asynchronous = render('controls', ['--samples', str(samples), '--async-test'], export)
        assert moved == raw and moved_signals == raw_signals, 'asynchronous controls changed final renderer values'
        assert asynchronous['dispatches'] == 4*samples+1 and asynchronous['history_resets'] == 4
        assert asynchronous['render_readbacks'] == asynchronous['readback_submissions'] == 6
        assert asynchronous['async_submissions'] >= asynchronous['dispatches']
        assert 5 <= asynchronous['display_verified'] < asynchronous['display_submissions']
        assert asynchronous['display_buffer_mask'] == 3 and asynchronous['display_resizes'] == 3
        assert asynchronous['display_suspended_ticks'] >= 1 and asynchronous['display_rejected_resizes'] == 1
        assert asynchronous['requested_buffer_bytes'] == synchronous['requested_buffer_bytes']
        assert synchronous['render_readbacks'] == samples and synchronous['async_submissions'] == 0
        # Close on a non-final sample with no per-sample CPU references or display validation.
        seven, seven_signals, _ = render('seven', ['--samples', '7'], export)
        early, early_signals, closed = render('early-close', ['--samples', '64', '--async-close-test'], export)
        assert early == seven and early_signals == seven_signals, 'pending GPU work was lost on window teardown'
        assert closed['samples'] == closed['dispatches'] == closed['timed_samples'] == 7
        assert closed['render_readbacks'] == closed['readback_submissions'] == 1
        assert closed['display_verified'] == 0 and closed['async_submissions'] > 7
        assert closed['display_buffer_mask'] == 3
        assert closed['maximum_frame_latency'] == 1 and closed['pacing_ready'] == closed['display_submissions']
        assert asynchronous['maximum_frame_latency'] == asynchronous['pacing_waits'] == 0
        if width == 257:
            repeated, repeated_signals, info = render('repeat', ['--samples', str(samples), '--async-test'], export)
            assert repeated == moved and repeated_signals == moved_signals
            assert info['requested_buffer_bytes'] == asynchronous['requested_buffer_bytes']
        reports[str(width)] = dict(controls=asynchronous, early_close=closed)
    for extra in (['--async-test'], ['--async-test', '--gdi', '--samples', '8'], ['--async-close-test'],
                  ['--async-close-test', '--presentation-test', '--samples', '8']):
        run([args.dxr, source, *extra], ok=False)
    result = dict(result='pass', capabilities=probe, cases=reports, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result)); return 0


if __name__ == '__main__': sys.exit(main())
