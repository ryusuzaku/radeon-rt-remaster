"""Bounded exact-repeat diagnostics through the existing pinned RR workers.

This measures execution variability, never image-quality acceptance. A quiet
host interval is not a measurement of GPU idle, clocks or exclusive GPU use.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time

from inspect_rr_inputs import decode_inputs
from rr_dispatch import decode_output, run_dispatch
from rr_recorded_dispatch import admit_record, decode_recording_output, run_recording
from rr_sequence import decode_sequence, decode_sequence_output, encode_sequence, run_sequence

CONTROL_KEYS = ('frame_index', 'reset', 'camera_delta', 'dispatch_flags', 'packed_sha256', 'formats')


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def digest(raw):
    return sha256(raw).hexdigest()


def guide_digest(frame):
    # Recording-global indices intentionally differ across reset segments.
    # Preserve exact float32 bits of every record and all five camera matrices,
    # plus seed/sample/reset metadata; only the global frame ordinal is omitted.
    values = [x for row in frame['records'] for x in row]
    for key in sorted(frame['matrices']):
        values.extend(frame['matrices'][key])
    return digest(struct.pack('<3I', frame['random_index'], frame['seed'], frame['reset']) +
                  struct.pack('<' + 'f' * len(values), *values))


def compare_frames(left, right):
    if len(left) != len(right) or not left:
        raise ValueError('comparison requires matching nonempty frame counts')
    differences = []
    for a, b in zip(left, right):
        # Native validated RRTRRO01 payload; exclude input identity and checksum.
        if len(a) != 196696 or len(b) != 196696:
            raise ValueError('unexpected diagnostic frame size')
        x, y = a[56:-32], b[56:-32]
        bits_a = list(struct.iter_unpack('<4I', x))
        bits_b = list(struct.iter_unpack('<4I', y))
        rows_a = list(struct.iter_unpack('<4f', x))
        rows_b = list(struct.iter_unpack('<4f', y))
        delta = [abs(u[c] - v[c]) for u, v in zip(rows_a, rows_b) for c in range(3)]
        differences.append(dict(
            left_rgba_sha256=digest(x), right_rgba_sha256=digest(y),
            rgba_byte_equal=x == y,
            pixels_different=sum(u != v for u, v in zip(bits_a, bits_b)),
            components_different=sum(u[c] != v[c] for u, v in zip(bits_a, bits_b) for c in range(4)),
            maximum_rgb_difference=max(delta), rgb_mse=sum(d*d for d in delta)/len(delta)))
    return dict(rgba_byte_equal=all(d['rgba_byte_equal'] for d in differences), frames=differences)


def comparison(left, right, left_guides, right_guides, left_controls, right_controls):
    count = len(left)
    if any(len(v) != count for v in (right, left_guides, right_guides, left_controls, right_controls)):
        raise ValueError('comparison metadata count mismatch')
    result = compare_frames(left, right)
    result['input_records_and_matrices_equal'] = left_guides == right_guides
    result['dispatch_controls_equal'] = all(
        all(a[k] == b[k] for k in CONTROL_KEYS) for a, b in zip(left_controls, right_controls))
    return result


def prepare(dxr, folder):
    # Use the existing legal constant-colour fixture, with deterministic sunlight.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
    from verify_dxr import encode_scene, fixture
    folder.mkdir(parents=True, exist_ok=False)
    source = folder/'source.rrscene'
    source.write_bytes(encode_scene(fixture()))
    shader = folder/'rrt_rr_inputs.dxil'
    shader.write_bytes((dxr.parent/shader.name).read_bytes())
    definitions = {
        'stationary': ['--rr-reset-frame', '4'],
        'moving': ['--rr-step', '.03125', '0', '0', '--rr-reset-frame', '4'],
        'fresh': ['--camera-offset', '.125', '0', '0', '--rr-step', '.03125', '0', '0'],
    }
    identities = {}
    for name, options in definitions.items():
        path = folder/(name+'.rrcapture')
        process = subprocess.run([str(dxr), str(source), '--mode', 'gi', '--sun-radius', '0',
                                  '--samples', '4' if name == 'fresh' else '8',
                                  '--rr-record', str(path), '--debug', *options],
                                 capture_output=True, text=True, timeout=60,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        save(folder/(name+'-renderer.json'), dict(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr))
        if process.returncode:
            raise RuntimeError('headless fixture recording failed; see renderer report')
        raw = path.read_bytes()
        data = admit_record(raw)
        identities[name] = dict(file_sha256=digest(raw), input_sha256=raw[-32:].hex(),
                                guides=[guide_digest(f) for f in data['frames']])
    stationary = admit_record((folder/'stationary.rrcapture').read_bytes())
    parts = stationary['parts'][:4]
    (folder/'single.rrinputs').write_bytes(parts[0])
    (folder/'sequence.rrseq').write_bytes(encode_sequence(parts+parts))
    save(folder/'inputs.json', dict(recordings=identities, renderer_sha256=digest(dxr.read_bytes()),
                                   shader_sha256=digest(shader.read_bytes()), scene_sha256=digest(source.read_bytes())))


def run(probe, sdk_bin, inputs, folder, quiet_seconds):
    folder.mkdir(parents=True, exist_ok=False)
    cases = {}
    comparisons = {}
    retained = {}
    for name in ('single', 'sequence', 'stationary', 'moving', 'fresh'):
        for attempt in ('initial', 'consecutive', 'after-quiet'):
            # Apply the same pause before EACH final-round case, not only the
            # first case. Previous worker completion includes its fenced work.
            started = time.monotonic()
            if attempt == 'after-quiet':
                time.sleep(quiet_seconds)
            elapsed = time.monotonic()-started
            label = name+'-'+attempt
            path = inputs/(name+('.rrinputs' if name == 'single' else '.rrseq' if name == 'sequence' else '.rrcapture'))
            raw = path.read_bytes()
            output = folder/(label+'.rrout')
            if name == 'single':
                data = [decode_inputs(raw)]
                report = run_dispatch(probe, sdk_bin, path, output)
            elif name == 'sequence':
                _, data = decode_sequence(raw)
                report = run_sequence(probe, sdk_bin, path, output)
            else:
                data = admit_record(raw)['frames']
                report = run_recording(probe, sdk_bin, path, output,
                                       scene=inputs/'source.rrscene', shader=inputs/'rrt_rr_inputs.dxil')
            save(folder/(label+'-execution.json'), report)
            if not report['decision']['rr_rendering']:
                raise RuntimeError('worker admission failed: '+label)
            if report['decision']['raw_sdk_acceptance'] != 'failed' or report['decision']['quality_acceptance'] != 'not-evaluated':
                raise ValueError('unexpected execution acceptance')
            out = output.read_bytes()
            if name == 'single':
                decode_output(out, data[0], raw[-32:])
                chunks = [out]
                controls = [report['decision']['dispatch']]
            elif name == 'sequence':
                chunks, _ = decode_sequence_output(out, raw)
                controls = report['decision']['sequence']['frames']
            else:
                chunks, _ = decode_recording_output(out, raw)
                controls = report['decision']['sequence']['frames']
            guides = [guide_digest(f) for f in data]
            cases[label] = dict(input_file_sha256=digest(raw), output_file_sha256=digest(out),
                                guides=guides, controls=controls,
                                host_pause_seconds=elapsed, requested_pause_seconds=quiet_seconds if attempt == 'after-quiet' else 0,
                                frame_rgba_sha256=[digest(c[56:-32]) for c in chunks])
            retained[label] = (chunks, guides, controls)
            def compare(label, a, b):
                comparisons[label] = comparison(a[0], b[0], a[1], b[1], a[2], b[2])
            current = retained[label]
            if attempt != 'initial':
                compare(label+'-vs-initial', retained[name+'-initial'], current)
            if name in ('sequence', 'stationary'):
                compare(label+'-reset-segments', tuple(v[:4] for v in current), tuple(v[4:] for v in current))
            if name == 'sequence':
                compare(label+'-vs-single', retained['single-'+attempt], tuple(v[:1] for v in current))
            if name == 'stationary':
                compare(label+'-vs-sequence', retained['sequence-'+attempt], current)
            if name == 'fresh':
                compare('moving-reset-vs-fresh-'+attempt,
                        tuple(v[4:] for v in retained['moving-'+attempt]), current)
            save(folder/(label+'-checkpoint.json'), dict(case=cases[label], comparisons=comparisons))
            print(label+': retained', flush=True)
    exact = all(c['rgba_byte_equal'] for c in comparisons.values())
    controls = all(c['input_records_and_matrices_equal'] and c['dispatch_controls_equal'] for c in comparisons.values())
    summary = dict(schema='rr-repeatability-1', result='observed-exact-sample' if exact and controls else 'failed-exact-controls',
                   quality_acceptance='not-qualified', raw_sdk_acceptance='failed',
                   all_comparison_inputs_and_controls_equal=controls, all_rgba_byte_equal=exact,
                   probe_sha256=digest(probe.read_bytes()), sdk_sha256=report['sdk_sha256'],
                   cases=cases, comparisons=comparisons,
                   limitations=['No allocation addresses or placement measured; only existing resource reuse/lifecycles controlled.',
                                'Host pause is not verified GPU idle; clocks and other GPU clients unmeasured.',
                                'Build configuration comparison retains the D3D12 debug layer in both.',
                                'Three launches per mode on one GPU do not prove general repeatability.'])
    save(folder/'verification.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--dxr', type=Path, required=True)
    prep.add_argument('--out', type=Path, required=True)
    execute = sub.add_parser('run')
    for key in ('probe', 'sdk-bin', 'inputs'):
        execute.add_argument('--'+key, type=Path, required=True)
    execute.add_argument('--out', type=Path)
    execute.add_argument('--quiet-seconds', type=float, default=2)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.dxr.resolve(strict=True), args.out)
        return 0
    if not 0 <= args.quiet_seconds <= 5:
        parser.error('quiet interval must be finite and within 0..5 seconds')
    folder = args.out or Path(tempfile.mkdtemp(prefix='rr-repeatability-', dir=args.probe.parent))/'results'
    summary = run(args.probe, args.sdk_bin, args.inputs, folder, args.quiet_seconds)
    print(json.dumps(dict(result=summary['result'], quality_acceptance=summary['quality_acceptance'], artifacts=str(folder))))
    return 0 if summary['result'] == 'observed-exact-sample' else 1


if __name__ == '__main__':
    raise SystemExit(main())
