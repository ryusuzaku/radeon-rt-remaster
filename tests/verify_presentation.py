"""Native swapchain pixel/lifetime acceptance in hidden windows, not scanout qualification."""
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
    folder = Path(tempfile.mkdtemp(prefix='presentation-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    def run(command, ok=True):
        result = subprocess.run([str(x) for x in command], env=env, text=True, capture_output=True, timeout=90)
        assert (result.returncode == 0) == ok, f'{command}\n{result.stdout}\n{result.stderr}'
        return result
    probe = json.loads(run([args.dxr, '--probe']).stdout)
    if not probe['supported']: return 77
    debug = ['--debug'] if probe['debug_available'] else []
    reports = {}
    for width, height in ((128, 96), (257, 129), (1920, 1080)):
        source = folder/f'{width}.rrscene'; source.write_bytes(encode_scene(resized(width, height)))
        modes = ('albedo', 'gi') if width != 1920 else ('gi',)
        for mode in modes:
            label = f'{width}-{mode}'
            base = [args.dxr, source, '--mode', mode, '--samples', '4', '--denoise', '--temporal', *debug]
            reference_path = folder/f'{label}-headless.pixels'
            reference = json.loads(run([*base, '--pixels', reference_path]).stdout)
            expected = reference_path.read_bytes()
            assert reference['display_submissions'] == 0 and reference['presentation'] == 'headless'
            native_path = folder/f'{label}-native.pixels'
            native = json.loads(run([*base, '--presentation-test', '--pixels', native_path]).stdout)
            assert native_path.read_bytes() == expected, 'window events changed renderer output'
            assert native['presentation'] == 'd3d12-swapchain'
            assert native['display_submissions'] == native['display_verified'] > 0
            assert native['display_presented']+native['display_occluded'] == native['display_submissions']
            assert native['display_buffer_mask'] == 3, 'both swapchain buffers must be exercised'
            assert native['display_resizes'] == 3 and native['display_suspended_ticks'] >= 1
            assert native['display_rejected_resizes'] == 1
            assert native['history_resets'] == 4 and native['samples'] == 4 and native['dispatches'] == 17
            assert native['scene_build_submissions'] == 1
            assert native['requested_buffer_bytes'] == reference['requested_buffer_bytes'], 'display resources leaked into final accounting'
            assert native['requested_buffer_bytes'] < native['peak_requested_bytes'] <= native['requested_buffer_limit_bytes']
            if width == 128:
                gdi_path = folder/f'{label}-gdi.pixels'
                gdi = json.loads(run([*base, '--window-test', '--gdi', '--pixels', gdi_path]).stdout)
                assert gdi_path.read_bytes() == expected and gdi['presentation'] == 'gdi'
                assert gdi['display_submissions'] == 0 and gdi['display_verified'] == 0
            if width == 257 and mode == 'gi':
                repeat_path = folder/f'{label}-repeat.pixels'
                repeated = json.loads(run([*base, '--presentation-test', '--pixels', repeat_path]).stdout)
                assert repeated['peak_requested_bytes'] == native['peak_requested_bytes'] and repeat_path.read_bytes() == expected
            reports[label] = native
    for extra in (['--gdi'], ['--presentation-test', '--gdi'], ['--presentation-test', '--history-test']):
        run([args.dxr, source, *extra], ok=False)
    result = dict(result='pass', capabilities=probe, cases=reports,
                  qualification='Hidden-window back-buffer readback; controlled minimize/restore and occlusion-status branches, not real desktop scanout.', artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result)); return 0


if __name__ == '__main__': sys.exit(main())
