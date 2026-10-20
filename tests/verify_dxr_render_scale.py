"""Internal render resolution: decoupled from the captured extent and the window.

The renderer used to allocate and dispatch every per-pixel buffer from the
captured target extent, so a 4K capture always cost 4K of working set. This
asserts the opposite: the frame can be rendered on a smaller internal grid and
upscaled at presentation, while the captured scissors still clip in target
space and the default (100%) output stays byte-identical.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from verify_dxr import fixture, encode_scene
from inspect_signals import load_signals

HEADER = struct.Struct('<8s7I')


def scene_with_scissor(scissor):
    scene = fixture()
    scene['draws'][1]['scissor'] = scissor
    # The renderer only honours a captured scissor when the state enables it.
    render = list(scene['draws'][1]['render'])
    render[23] = 1
    scene['draws'][1]['render'] = render
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dxr', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='render-scale-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}

    def run(command, ok=True):
        result = subprocess.run([str(x) for x in command], env=env, text=True,
                                capture_output=True, timeout=180)
        assert (result.returncode == 0) == ok, f'{command}\n{result.stdout}\n{result.stderr}'
        return result

    probe = json.loads(run([args.dxr, '--probe']).stdout)
    if not probe['supported']:
        print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable')
        return 77
    debug = ['--debug'] if probe['debug_available'] else []

    source = folder / 'source.rrscene'
    source.write_bytes(encode_scene(fixture()))
    clipped = folder / 'clipped.rrscene'
    clipped.write_bytes(encode_scene(scene_with_scissor([64, 0, 128, 96])))

    def render(name, scene=source, extra=()):
        pixels = folder / (name + '.pixels')
        report = json.loads(run([args.dxr, scene, '--pixels', pixels, *debug, *extra]).stdout)
        return report, pixels.read_bytes()

    def colours(data):
        return {data[i:i + 3] for i in range(0, len(data), 3)}

    full, full_pixels = render('full')
    assert full['render_scale'] == 100
    assert (full['width'], full['height']) == (128, 96)
    assert (full['scene_width'], full['scene_height']) == (128, 96)
    assert len(full_pixels) == 128 * 96 * 3

    half, half_pixels = render('half', extra=['--render-scale', '50'])
    assert half['render_scale'] == 50
    assert (half['width'], half['height']) == (64, 48), (half['width'], half['height'])
    assert (half['scene_width'], half['scene_height']) == (128, 96)
    assert len(half_pixels) == 64 * 48 * 3

    # Every per-pixel buffer must shrink with the grid. A ratio near 1.0 means the
    # allocation still follows the captured extent; near zero means nothing was
    # allocated for the frame at all.
    ratio = half['requested_buffer_bytes'] / full['requested_buffer_bytes']
    assert 0.15 < ratio < 0.4, ratio
    assert half['requested_buffer_bytes'] < full['requested_buffer_bytes']
    assert half['requested_buffer_bytes'] <= half['requested_buffer_limit_bytes']

    # A nearest-pixel reduction may only sample fewer of the same colours; it must
    # not blend new ones. This is what distinguishes a reduction from a resample.
    assert colours(half_pixels) <= colours(full_pixels), colours(half_pixels) - colours(full_pixels)
    centre = half_pixels[(24 * 64 + 32) * 3:(24 * 64 + 32) * 3 + 3]
    assert centre == bytes([32, 128, 240]), centre  # occluder blue, as at 128x96

    # Captured scissors are target pixels. The occluder draw is restricted to the
    # right half of the target, so no occluder colour may appear on the left at
    # either grid size; a shader that compared render coordinates directly would
    # shift the boundary to the middle of the smaller grid and leak it.
    occluder = bytes([32, 128, 240])
    for scale, width, height in ((100, 128, 96), (50, 64, 48)):
        name = f'clip-{scale}'
        extra = [] if scale == 100 else ['--render-scale', str(scale)]
        _, pixels = render(name, scene=clipped, extra=extra)
        left = sum(pixels[(y * width + x) * 3:(y * width + x) * 3 + 3] == occluder
                   for y in range(height) for x in range(width // 2))
        right = sum(pixels[(y * width + x) * 3:(y * width + x) * 3 + 3] == occluder
                    for y in range(height) for x in range(width // 2, width))
        assert left == 0, (scale, left)
        assert right > 0, (scale, right)

    # Diagnostic signals follow the payload grid, not the captured extent.
    signals = folder / 'half.signals'
    report = json.loads(run([args.dxr, source, '--render-scale', '50',
                             '--signals', signals, *debug]).stdout)
    magic, version, width, height, stride, samples, flags, mode = HEADER.unpack(
        signals.read_bytes()[:HEADER.size])
    assert magic == b'RRTSIG02' and version == 2
    assert (width, height) == (64, 48), (width, height)
    assert stride == 144 and samples >= 1
    assert signals.stat().st_size == HEADER.size + width * height * stride

    # Presentation upscales the render grid into a window sized to the capture.
    presented = json.loads(run([args.dxr, source, '--render-scale', '50',
                                '--presentation-test', *debug]).stdout)
    assert presented['display_verified'] > 0
    assert presented['display_presented'] + presented['display_occluded'] > 0
    assert (presented['width'], presented['height']) == (64, 48)

    # Motion vectors are in render pixels. Pixel (15,15) of the 64x48 grid is the
    # identical camera ray to pixel (30,30) of the 128x96 grid, because the ray
    # generator uses pixel*2/size with no half-pixel bias -- so the same camera
    # translation must report exactly half the displacement.
    full_motion_path = folder / 'motion-full.signals'
    render('motion-full', extra=['--motion-test', '--signals', full_motion_path])
    full_motion = load_signals(full_motion_path).pixel(30, 30)
    half_motion_path = folder / 'motion-half.signals'
    render('motion-half', extra=['--motion-test', '--render-scale', '50',
                                 '--signals', half_motion_path])
    half_motion = load_signals(half_motion_path).pixel(15, 15)
    assert full_motion[14] == half_motion[14] == 1, (full_motion[14], half_motion[14])
    assert abs(full_motion[12] - 6.4) < 1e-4 and abs(full_motion[13] + 4.8) < 1e-4
    assert abs(half_motion[12] - full_motion[12] / 2) < 1e-4, half_motion[12]
    assert abs(half_motion[13] - full_motion[13] / 2) < 1e-4, half_motion[13]

    # Temporal reuse must still converge and stay deterministic on the smaller
    # grid: history is keyed on the render grid, so a mismatch would either reset
    # every frame or accept history from the wrong pixel.
    temporal = []
    for run_index in (1, 2):
        path = folder / f'temporal-half-{run_index}.signals'
        report = json.loads(run([args.dxr, source, '--mode', 'gi', '--temporal',
                                 '--samples', '8', '--render-scale', '50',
                                 '--signals', path, *debug]).stdout)
        assert report['temporal_resets'] == 0, report['temporal_resets']
        temporal.append((report['pixel_sha256_bgra'], load_signals(path)))
    assert temporal[0][0] == temporal[1][0], 'reduced-grid temporal output is not deterministic'
    ground = temporal[0][1].pixel(15, 15)
    assert ground[34] == 1, ground[32:36]          # accepted
    assert ground[32] >= 4, ground[32]             # converged count

    # Out-of-range values fail closed instead of silently clamping.
    for bad in ('0', '101', '-50', 'abc'):
        result = run([args.dxr, source, '--render-scale', bad], ok=False)
        assert 'render scale' in result.stderr, (bad, result.stderr)
    # RR evidence paths are fixed-extent and must refuse a reduced grid, not fail
    # earlier for an unrelated option mismatch.
    result = run([args.dxr, source, '--mode', 'gi', '--render-scale', '50',
                  '--rr-inputs', folder / 'rr.bin'], ok=False)
    assert 'render scale is unsupported' in result.stderr, result.stderr

    print(f'PASS: 100%={full["requested_buffer_bytes"]}B 50%={half["requested_buffer_bytes"]}B '
          f'ratio={ratio:.3f} signals={width}x{height}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
