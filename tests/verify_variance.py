"""Variance-aware presentation: CPU reference, quality, raw/history isolation and bounds."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
from functools import lru_cache
import subprocess
import tempfile

from verify_dxr import fixture, encode_scene
from verify_dxr_resolution import resized
from inspect_signals import load_signals
from material_inputs import compile_materials


def luminance(rgb):
    return sum(a*b for a, b in zip(rgb, (.2126, .7152, .0722)))


def same_surface(center, tap):
    if not tap[11] or tap[15] != center[15]:
        return False
    if sum(a*b for a, b in zip(tap[4:7], center[4:7])) < .95:
        return False
    if any(abs(a-b) > .1 for a, b in zip(tap[8:11], center[8:11])):
        return False
    delta = [a-b for a, b in zip(tap[20:23], center[20:23])]
    footprint = max(tap[23], center[23])
    return (abs(sum(a*b for a, b in zip(delta, center[4:7]))) <= max(.001, .01*footprint)
            and math.sqrt(sum(v*v for v in delta)) <= max(.002, 6*footprint))


def reference(rows, width, height, x, y, temporal, radius=3):
    center = rows[y*width+x]
    if not center[11]:
        return center[:3]
    def color(row):
        return row[28:31] if temporal else row[:3]
    def neighbors(cx, cy, support, step=1):
        current = rows[cy*width+cx]
        for dy in range(-support, support+1):
            for dx in range(-support, support+1):
                if 0 <= cx+dx*step < width and 0 <= cy+dy*step < height:
                    tap = rows[(cy+dy*step)*width+cx+dx*step]
                    if same_surface(current, tap):
                        yield dx, dy, tap
    @lru_cache(None)
    def first(cx, cy):
        current = rows[cy*width+cx]
        if temporal and current[32] >= 4:
            variance = current[33]/current[32]
        else:
            values = [luminance(color(tap)) for _, _, tap in neighbors(cx, cy, radius)]
            mean = sum(values)/len(values)
            variance = max(0, sum(v*v for v in values)/len(values)-mean*mean)
        current_l = luminance(color(current))
        total, weight_sum, variance_sum = [0., 0., 0.], 0., 0.
        for dx, dy, tap in neighbors(cx, cy, 1):
            tap_variance = tap[33]/tap[32] if temporal and tap[32] >= 4 else variance
            sigma = max(.0001, 4*math.sqrt(max(0, variance+tap_variance)))
            weight = (2-abs(dx))*(2-abs(dy))*math.exp(-abs(luminance(color(tap))-current_l)/sigma)
            for channel in range(3):
                total[channel] += color(tap)[channel]*weight
            weight_sum += weight
            variance_sum += tap_variance*weight*weight
        return [v/weight_sum for v in total]+[variance_sum/(weight_sum*weight_sum)]
    current = first(x, y)
    if radius == 1:
        return current[:3]
    total, weight_sum = [0., 0., 0.], 0.
    for dx, dy, _ in neighbors(x, y, 1, step=2):
        tap = first(x+2*dx, y+2*dy)
        sigma = max(.0001, 4*math.sqrt(max(0, current[3]+tap[3])))
        weight = (2-abs(dx))*(2-abs(dy))*math.exp(-abs(luminance(tap[:3])-luminance(current[:3]))/sigma)
        for channel in range(3):
            total[channel] += tap[channel]*weight
        weight_sum += weight
    return [v/weight_sum for v in total]


def mse(image, truth):
    return sum((a-b)**2 for a, b in zip(image, truth))/len(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dxr', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='variance-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    def run(extra):
        result = subprocess.run([str(args.dxr), *map(str, extra)], env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, f'{extra}\n{result.stdout}\n{result.stderr}'
        return json.loads(result.stdout)
    probe = run(['--probe'])
    if not probe['supported']:
        return 77
    debug = ['--debug'] if probe['debug_available'] else []
    scene = fixture(); source = folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    reports = {}
    def render(name, extra=(), path=source, export=True, mode='gi'):
        pixels, signals = folder/f'{name}.pixels', folder/f'{name}.signals'
        command = [path, '--mode', mode, '--pixels', pixels, *debug, *extra]
        if export:
            command += ['--signals', signals]
        info = run(command); reports[name] = info
        assert info['peak_requested_bytes'] <= info['requested_buffer_limit_bytes']
        assert info['timed_samples'] == info['dispatches'] and info['scene_build_submissions'] == 1
        rows = list(load_signals(signals).records()) if export else None
        return pixels.read_bytes(), rows
    def isolate(raw, filtered):
        for a, b in zip(raw, filtered):
            assert a[:16] == b[:16] and a[20:] == b[20:], 'presentation filter altered lighting/history/guides'
            if not a[11]:
                assert b[16:19] == b[:3], 'filter changed background'
    # Multiple seeds keep the improvement gate from depending on one random realization.
    truth, _ = render('reference', ['--samples', '256'], export=False)
    quality = []
    cpu_error = 0
    for seed in (1, 7, 23):
        options = ['--seed', str(seed)]
        raw, raw_rows = render(f'raw-{seed}', options)
        spatial, _ = render(f'spatial-{seed}', [*options, '--denoise'], export=False)
        filtered, rows = render(f'variance-{seed}', [*options, '--variance-filter'])
        isolate(raw_rows, rows)
        assert reports[f'variance-{seed}']['denoiser'] == 'variance'
        assert reports[f'variance-{seed}']['requested_buffer_bytes'] == reports[f'raw-{seed}']['requested_buffer_bytes']
        for x, y in ((0, 0), (5, 30), (30, 30), (45, 57), (64, 48), (80, 20), (122, 90)):
            expected = reference(rows, 128, 96, x, y, False)
            error = max(abs(a-b) for a, b in zip(expected, rows[y*128+x][16:19]))
            cpu_error = max(cpu_error, error)
            assert error < 2e-4, (seed, x, y, error)
        quality.append(dict(seed=seed, raw_mse=mse(raw, truth), spatial_mse=mse(spatial, truth), variance_mse=mse(filtered, truth)))
        if seed == 1:
            assert render('repeat', [*options, '--variance-filter'])[0] == filtered
    average = lambda key: sum(q[key] for q in quality)/len(quality)
    quality_passed = (average('variance_mse') < average('raw_mse')*.5
                      and average('variance_mse') < average('spatial_mse')*.95)
    for samples in (1, 4, 16):
        options = ['--samples', str(samples), '--temporal']
        _, raw_rows = render(f'temporal-raw-{samples}', options)
        filtered, rows = render(f'temporal-variance-{samples}', [*options, '--variance-filter'])
        isolate(raw_rows, rows)
        for x, y in ((30, 30), (45, 57), (64, 48), (80, 20)):
            expected = reference(rows, 128, 96, x, y, True)
            error = max(abs(a-b) for a, b in zip(expected, rows[y*128+x][16:19]))
            cpu_error = max(cpu_error, error)
            assert error < 2e-4, (samples, x, y, error)
        if samples == 4:
            assert render('native', [*options, '--variance-filter', '--async-test'])[0] == filtered
            assert render('history', [*options, '--variance-filter', '--history-test'])[0] == filtered
    # Strong albedo and same-draw geometry boundaries cannot share filter taps.
    checker = copy.deepcopy(scene)
    checker['draws'][0]['texture_width'] = 2
    checker['draws'][0]['texture'] = bytes([0, 0, 0, 255, 255, 255, 255, 255])
    check_path = folder/'checker.rrscene'; check_path.write_bytes(encode_scene(checker))
    _, rows = render('checker', ['--variance-filter'], path=check_path)
    assert rows[20*128+63][16:19] == (0, 0, 0), 'filter crossed an albedo edge'
    # PBR shading is filtered in radiance, not demodulated by a diffuse-only albedo.
    material = folder/'glossy.rrmat'
    material.write_bytes(compile_materials(dict(schema='rrt-materials', version=1,
        materials=[dict(target=scene['draws'][0]['material_id'], roughness=.1, metallic=1, emissive=[1, .2, 0])]), scene))
    options = ['--materials', material, '--samples', '4', '--temporal']
    _, raw_rows = render('glossy-raw', options)
    _, rows = render('glossy-filtered', [*options, '--variance-filter'])
    isolate(raw_rows, rows)
    for x, y in ((30, 30), (45, 57), (80, 20)):
        expected = reference(rows, 128, 96, x, y, True, radius=1)
        assert max(abs(a-b) for a, b in zip(expected, rows[y*128+x][16:19])) < .001
    # Filter selection is inert outside GI.
    assert render('albedo', mode='albedo')[0] == render('albedo-filter', ['--variance-filter'], mode='albedo')[0]
    hd = folder/'hd.rrscene'; hd.write_bytes(encode_scene(resized(1920, 1080)))
    hd_pixels, _ = render('hd', ['--samples', '4', '--temporal', '--variance-filter'], path=hd, export=False)
    assert render('hd-repeat', ['--samples', '4', '--temporal', '--variance-filter'], path=hd, export=False)[0] == hd_pixels
    result = dict(result='pass' if quality_passed else 'quality-gate-failed', mechanics='pass',
                  capabilities=probe, quality=quality, max_cpu_absolute_error=cpu_error,
                  cases=reports, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0 if quality_passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
