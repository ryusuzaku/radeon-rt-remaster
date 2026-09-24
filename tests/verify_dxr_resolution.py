"""Resolution independence: 1440p and 4K must render, with bounded export chunks.

The working set is a fixed cost per pixel, so a flat budget cap becomes a
resolution ceiling. This asserts the opposite: the same scene renders correctly
at 1080p, 1440p and 4K, and the guard still refuses a scene that genuinely does
not fit.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from verify_dxr import fixture, encode_scene, ROOT
from inspect_signals import load_signals, inspect_file, summarize, HEADER, CHUNK_PIXELS


def resized(width, height):
    scene = fixture()
    scene.update(width=width, height=height)
    for draw in scene['draws']:
        draw['viewport'] = [0, 0, width, height, 0., 1.]
        draw['scissor'] = [0, 0, width, height]
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dxr', type=Path, required=True)
    parser.add_argument('--full-hd-export', action='store_true', help='Also retain and stream-validate a 285 MiB diagnostic file')
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='resolution-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}

    def run(command, ok=True):
        result = subprocess.run([str(x) for x in command], env=env, text=True, capture_output=True, timeout=120)
        assert (result.returncode == 0) == ok, f'{command}\n{result.stdout}\n{result.stderr}'
        return result

    probe = json.loads(run([args.dxr, '--probe']).stdout)
    if not probe['supported']:
        print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable'); return 77
    debug = ['--debug'] if probe['debug_available'] else []
    paths = {}
    # 4096x4096 is the largest extent the scene format can express and needs
    # 3.75 GiB, past both the 1 GiB per-allocation and 2 GiB total limits, so it
    # keeps the guard exercised rather than merely bypassed.
    for name, width, height in (('hd', 1920, 1080), ('chunks', 257, 129),
                                ('qhd', 2560, 1440), ('uhd', 3840, 2160),
                                ('over-budget', 4096, 4096)):
        paths[name] = folder / (name + '.rrscene')
        paths[name].write_bytes(encode_scene(resized(width, height)))

    def render(name, source='hd', extra=()):
        pixels = folder / (name + '.pixels')
        report = json.loads(run([args.dxr, paths[source], '--pixels', pixels, *debug, *extra]).stdout)
        assert report['scene_build_submissions'] == 1
        assert report['working_stride'] == 88 and report['temporal_stride'] == 64 and report['signal_stride'] == 144
        # A fixed ceiling, not an adapter share: DXGI's dedicated-memory figure is
        # clamped in a 32-bit process (3.00 GiB vs 15.81 GiB for the same GPU), so
        # a share of it made x86 refuse 4K while x64 accepted it. Asserting the
        # exact value is what would catch that regression returning.
        assert report['requested_buffer_limit_bytes'] == 8 * 1024 ** 3, report['requested_buffer_limit_bytes']
        assert report['requested_buffer_bytes'] <= report['requested_buffer_limit_bytes']
        assert all(report[k] >= 0 for k in ('gpu_trace_ms', 'gpu_temporal_ms', 'gpu_filter_ms', 'gpu_export_ms', 'signal_export_ms'))
        data = pixels.read_bytes()
        assert len(data) == report['width'] * report['height'] * 3
        return data, report

    albedo, albedo_info = render('albedo', extra=['--mode', 'albedo'])
    def pixel(data, x, y, width=1920): return data[(y*width+x)*3:(y*width+x+1)*3]
    assert pixel(albedo, 960, 540) == bytes([32, 128, 240])
    assert pixel(albedo, 450, 338) == bytes([176]*3)
    assert pixel(albedo, 0, 0) == bytes([80, 40, 20])
    # Resolution independence: the identical scene must produce identical colours
    # at 1440p and 4K, not merely allocate. The fixture is a full-viewport grey
    # quad, a centred blue occluder triangle over the middle 40% and a clear
    # colour outside, so the same three fractional sample points hold at any size.
    budgets = {'hd': albedo_info['requested_buffer_bytes']}
    limit = albedo_info['requested_buffer_limit_bytes']
    for name, width, height in (('qhd', 2560, 1440), ('uhd', 3840, 2160)):
        data, info = render(name, name, extra=['--mode', 'albedo'])
        assert (info['width'], info['height']) == (width, height)
        assert pixel(data, width//2, height//2, width) == bytes([32, 128, 240]), name
        assert pixel(data, int(.2344*width), int(.3130*height), width) == bytes([176]*3), name
        assert pixel(data, 0, 0, width) == bytes([80, 40, 20]), name
        budgets[name] = info['requested_buffer_bytes']
    # Cost must scale with pixels and stay under the limit at every step.
    assert budgets['hd'] < budgets['qhd'] < budgets['uhd'] < limit, budgets
    assert albedo_info['export_submissions'] == 0 and albedo_info['gpu_export_ms'] == 0
    gi_args = ['--mode', 'gi', '--temporal', '--denoise', '--samples', '4']
    gi, gi_info = render('gi', extra=gi_args)
    repeated, repeat_info = render('repeat', extra=gi_args)
    assert gi == repeated and gi != albedo
    assert gi_info['samples'] == gi_info['dispatches'] == 4 and gi_info['history_resets'] == 0
    assert albedo_info['requested_buffer_bytes'] == gi_info['requested_buffer_bytes'] == repeat_info['requested_buffer_bytes']

    signal_path = folder / 'chunks.signals'
    chunk_pixels, chunk_info = render('chunks', 'chunks', [*gi_args, '--signals', signal_path])
    without_export, plain_info = render('chunks-plain', 'chunks', gi_args)
    assert chunk_pixels == without_export, 'diagnostic export changed presentation'
    assert chunk_info['export_chunk_pixels'] == CHUNK_PIXELS
    assert chunk_info['export_submissions'] == (257*129 + CHUNK_PIXELS-1)//CHUNK_PIXELS == 3
    assert chunk_info['requested_buffer_bytes'] - plain_info['requested_buffer_bytes'] == 2*CHUNK_PIXELS*144-256
    signals = load_signals(signal_path)
    assert signals.samples == 4 and signals.flags == 3
    assert signal_path.stat().st_size == HEADER.size + 257*129*144
    summary = summarize(signals)
    assert inspect_file(signal_path) == summary
    assert json.loads(run([sys.executable, ROOT/'tools/inspect_signals.py', signal_path]).stdout) == summary
    assert summary['max_history_samples'] == 4 and summary['temporal_reasons']['0'] > 0
    for i, row in enumerate(signals.records()):
        expected = [round(max(0., min(1., value))*255) for value in row[16:19]][::-1]
        assert all(abs(a-b) <= 1 for a, b in zip(expected, chunk_pixels[3*i:3*i+3])), (i, row)
    # Late corruption must be detected after crossing multiple streaming chunks.
    invalid = bytearray(signal_path.read_bytes())
    struct.pack_into('<f', invalid, HEADER.size+(257*129-1)*144+32*4, 33.)
    bad = folder/'bad-tail.signals'; bad.write_bytes(invalid)
    for reader in (load_signals, inspect_file):
        try: reader(bad)
        except ValueError: pass
        else: raise AssertionError('accepted invalid statistics in last chunk')
    invalid[-1:] = b''; bad.write_bytes(invalid)
    run([sys.executable, ROOT/'tools/inspect_signals.py', bad], ok=False)

    # 4096x4096 is the largest extent the scene format can express. It must either
    # fit within the adapter's limit, or be refused with our own diagnosable error
    # rather than a driver failure -- both are correct, and which one happens
    # depends on the card. What must never happen is a silent partial success.
    refused_pixels = folder/'refused.pixels'; refused_signals = folder/'refused.signals'
    attempt = subprocess.run([str(args.dxr), str(paths['over-budget']), '--pixels', str(refused_pixels),
                              '--signals', str(refused_signals), *[str(x) for x in debug]],
                             env=env, text=True, capture_output=True, timeout=300)
    if attempt.returncode == 0:
        report = json.loads(attempt.stdout)
        assert (report['width'], report['height']) == (4096, 4096)
        assert report['requested_buffer_bytes'] <= report['requested_buffer_limit_bytes']
        format_max = dict(outcome='rendered', requested=report['requested_buffer_bytes'], limit=report['requested_buffer_limit_bytes'])
    else:
        assert 'budget' in attempt.stderr.lower(), attempt.stderr
        assert not refused_pixels.exists() and not refused_signals.exists(), 'refused render left output behind'
        format_max = dict(outcome='refused', error=attempt.stderr.strip(), limit=limit)

    # No valid scene can reach the limit now, so exercise the guard directly: an
    # over-limit request must be refused with our error and must charge nothing.
    guard = json.loads(run([args.dxr, '--budget-test', *debug]).stdout)
    assert guard['budget_test'] == 'refused', guard
    assert guard['refused_request_bytes'] > guard['requested_buffer_limit_bytes'], guard
    assert guard['allocated_bytes'] == guard['allocated_before_bytes'], guard
    hd_export = None
    if args.full_hd_export:
        hd_signals = folder/'hd.signals'
        exported, info = render('hd-export', extra=[*gi_args, '--signals', hd_signals])
        assert exported == gi
        assert info['requested_buffer_bytes']-gi_info['requested_buffer_bytes'] == 2*CHUNK_PIXELS*144-256
        assert info['export_submissions'] == 127
        assert hd_signals.stat().st_size == HEADER.size+1920*1080*144
        try: load_signals(hd_signals)
        except ValueError: pass  # Random-access API intentionally retains its 256 MiB bound.
        else: raise AssertionError('random-access allocation bound was increased')
        inspection = json.loads(run([sys.executable, ROOT/'tools/inspect_signals.py', hd_signals]).stdout)
        assert inspection['max_history_samples'] == 4 and inspection['width'] == 1920 and inspection['height'] == 1080
        hd_export = dict(render=info, inspection=inspection, bytes=hd_signals.stat().st_size)
    result = dict(result='pass', capabilities=probe, full_hd=gi_info, chunks=chunk_info, chunk_inspection=summary,
                  resolution_budgets=budgets, budget_limit=limit, format_maximum=format_max,
                  budget_guard=guard, full_hd_export=hd_export, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result)); return 0


if __name__ == '__main__': sys.exit(main())
