"""Bounded exact-repeat diagnostics through the existing pinned RR workers.

This measures execution variability, never image-quality acceptance. A quiet
host interval is not a measurement of GPU idle, clocks or exclusive GPU use.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import threading

from inspect_rr_inputs import decode_inputs
from rr_dispatch import decode_output, run_dispatch
from rr_recorded_dispatch import admit_record, decode_recording_output, run_recording
from rr_sequence import decode_sequence, decode_sequence_output, encode_sequence, run_sequence

CONTROL_KEYS = ('frame_index', 'reset', 'camera_delta', 'dispatch_flags', 'packed_sha256', 'formats')
LOAD_WIDTH, LOAD_HEIGHT = 2048, 1536


def comparison_counts(comparisons):
    return dict(total=len(comparisons), match=sum(c['rgba_byte_equal'] for c in comparisons.values()),
                differ=sum(not c['rgba_byte_equal'] for c in comparisons.values()))


def load_bounds(seconds, samples):
    if not 5 <= seconds <= 600 or not 1 <= samples <= 4096:
        raise ValueError('GPU load requires finite 5..600 seconds and 1..4096 samples')


def replace_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


class LoadJob:
    """Windows kill-on-close job: gate the helper until it belongs to the job.

    The non-inherited job handle belongs only to the diagnostic. Abrupt parent
    exit kills the helper and its current renderer too. No arbitrary command
    line is accepted by the public diagnostic.
    """
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError('contained GPU load currently requires Windows')
        import ctypes as ct
        from ctypes import wintypes as wt
        class Basic(ct.Structure):
            _fields_ = [('user', ct.c_int64), ('job_user', ct.c_int64), ('flags', wt.DWORD),
                        ('min_ws', ct.c_size_t), ('max_ws', ct.c_size_t), ('active_limit', wt.DWORD),
                        ('affinity', ct.c_size_t), ('priority', wt.DWORD), ('scheduling', wt.DWORD)]
        class Limits(ct.Structure):
            _fields_ = [('basic', Basic), ('io', ct.c_uint64*6), ('process_memory', ct.c_size_t),
                        ('job_memory', ct.c_size_t), ('peak_process', ct.c_size_t), ('peak_job', ct.c_size_t)]
        self.ct = ct
        self.api = ct.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ct.c_void_p, wt.LPCWSTR]
        self.api.CreateJobObjectW.restype = wt.HANDLE
        self.api.SetInformationJobObject.argtypes = [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        self.api.TerminateJobObject.argtypes = [wt.HANDLE, wt.UINT]
        self.api.QueryInformationJobObject.argtypes = [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.c_void_p]
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ct.WinError(ct.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000 | 0x8  # KILL_ON_JOB_CLOSE | ACTIVE_PROCESS
        limits.basic.active_limit = 2     # helper and one headless renderer
        if not self.api.SetInformationJobObject(self.handle, 9, ct.byref(limits), ct.sizeof(limits)):
            self.close()
            raise ct.WinError(ct.get_last_error())

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise self.ct.WinError(self.ct.get_last_error())

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            raise self.ct.WinError(self.ct.get_last_error())

    def active(self):
        # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION: four LARGE_INTEGERs,
        # then page faults, total processes, active processes, terminated.
        values = self.ct.create_string_buffer(48)
        if not self.api.QueryInformationJobObject(self.handle, 1, values, 48, None):
            raise self.ct.WinError(self.ct.get_last_error())
        return struct.unpack_from('<I', values.raw, 40)[0]

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def gpu_load_worker(dxr, scene, folder, seconds, samples):
    load_bounds(seconds, samples)
    if sys.stdin.readline() != 'start\n':
        return 1
    started = time.monotonic()
    deadline = started + seconds
    state = dict(started=started, deadline=deadline, completed=[], stage='starting')
    command = [str(dxr), str(scene), '--adapter', '0', '--mode', 'gi', '--samples', str(samples), '--debug']
    while time.monotonic() < deadline:
        before = time.monotonic()
        state.update(stage='rendering', render_started=before)
        replace_json(folder/'load-state.json', state)
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    timeout=min(60, deadline-before),
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            native = json.loads(result.stdout) if result.returncode == 0 else None
            if (result.returncode or native['samples'] != samples or native['dispatches'] != samples or
                    native['width'] != LOAD_WIDTH or native['height'] != LOAD_HEIGHT or native['gpu_trace_ms'] <= 0):
                raise ValueError('load renderer did not complete the requested GPU work')
            state['completed'].append(dict(started=before, ended=time.monotonic(), report=native,
                                           stdout_sha256=digest(result.stdout.encode()),
                                           stderr_sha256=digest(result.stderr.encode())))
        except Exception as error:
            state.update(stage='failed', error_type=type(error).__name__, ended=time.monotonic())
            replace_json(folder/'load-state.json', state)
            return 1
    state.update(stage='deadline', ended=time.monotonic())
    replace_json(folder/'load-state.json', state)
    return 1  # An expired load budget cannot label an ongoing matrix as loaded.


class GPULoad:
    def __init__(self, dxr, inputs, folder, seconds=300, samples=1024):
        load_bounds(seconds, samples)
        self.folder, self.process, self.timer, self.job = folder, None, None, None
        self.report = dict(enabled=True, workload='repeated-headless-rrt_dxr', adapter=0,
                           width=LOAD_WIDTH, height=LOAD_HEIGHT, samples=samples, mode='gi', debug_layer=True,
                           maximum_seconds=seconds, renderer_sha256=digest(dxr.read_bytes()),
                           renderer_shader_sha256={p.name: digest(p.read_bytes()) for p in sorted(dxr.parent.glob('*.dxil'))},
                           render_timeout_seconds=60, watchdog_expired=False,
                           kill_on_job_close=True, active_process_limit=2)
        self.dxr, self.inputs, self.seconds, self.samples = dxr, inputs, seconds, samples

    def __enter__(self):
        from scene_io import decode_scene, encode_scene
        scene = decode_scene((self.inputs/'source.rrscene').read_bytes())
        scene['width'], scene['height'] = LOAD_WIDTH, LOAD_HEIGHT
        for draw in scene['draws']:
            draw['viewport'] = [0, 0, LOAD_WIDTH, LOAD_HEIGHT, *draw['viewport'][4:]]
            draw['scissor'] = [0, 0, LOAD_WIDTH, LOAD_HEIGHT]
        path = self.folder/'load.rrscene'
        path.write_bytes(encode_scene(scene))
        self.report['scene_sha256'] = digest(path.read_bytes())
        save(self.folder/'load-settings.json', self.report)
        try:
            self.job = LoadJob()
            command = [sys.executable, str(Path(__file__).resolve()), '_gpu-load-worker',
                       '--dxr', str(self.dxr.resolve()), '--scene', str(path.resolve()),
                       '--out', str(self.folder.resolve()), '--seconds', str(self.seconds), '--samples', str(self.samples)]
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, text=True,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.job.assign(self.process)
            self.report['assigned_before_workload_start'] = True
            def expire():
                self.report['watchdog_expired'] = True
                self.job.terminate()
            self.timer = threading.Timer(self.seconds, expire)
            self.timer.daemon = True
            self.timer.start()
            self.process.stdin.write('start\n')
            self.process.stdin.close()
            deadline = time.monotonic() + min(65, self.seconds)
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('GPU load exited during warmup')
                state = self.state()
                if state and state['completed'] and state['stage'] == 'rendering':
                    self.report['ready'] = time.monotonic()
                    return self
                time.sleep(.05)
            raise RuntimeError('GPU load warmup exceeded its budget')
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def state(self):
        path = self.folder/'load-state.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def check(self):
        state = self.state()
        if self.process.poll() is not None or not state or state['stage'] != 'rendering':
            raise RuntimeError('GPU load ended before the matrix completed')
        return dict(checked=time.monotonic(), render_started=state['render_started'],
                    completed_renders=len(state['completed']))

    def __exit__(self, *exc):
        if self.timer:
            self.timer.cancel()
            self.timer.join()
        try:
            if self.job:
                self.job.terminate()
            if self.process:
                # Also cover assignment failure: that helper is still gated
                # on stdin and has never been allowed to launch a renderer.
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=5)
            deadline = time.monotonic()+5
            while self.job and self.job.active() and time.monotonic() < deadline:
                time.sleep(.01)
            self.report.update(ended=time.monotonic(), helper_reaped=self.process is not None and self.process.poll() is not None,
                               job_active_processes_after_stop=self.job.active() if self.job else None,
                               state=self.state(), failed=exc[0] is not None)
        finally:
            if self.job:
                self.job.close()
            save(self.folder/'gpu-load.json', self.report)
        if self.job and self.report['job_active_processes_after_stop'] != 0:
            raise RuntimeError('GPU load cleanup could not verify an empty job')


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


def run_matrix(probe, sdk_bin, inputs, folder, quiet_seconds, load=None):
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
            load_before = load.check() if load else None
            worker_started = time.monotonic()
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
            worker_ended = time.monotonic()
            load_after = load.check() if load else None
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
                                worker_started=worker_started, worker_ended=worker_ended,
                                load_before=load_before, load_after=load_after,
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
    summary = dict(schema='rr-repeatability-2', result='observed-exact-sample' if exact and controls else 'failed-exact-controls',
                   quality_acceptance='not-qualified', raw_sdk_acceptance='failed',
                   all_comparison_inputs_and_controls_equal=controls, all_rgba_byte_equal=exact,
                   probe_sha256=digest(probe.read_bytes()), sdk_sha256=report['sdk_sha256'],
                   cases=cases, comparisons=comparisons, exact_comparisons=comparison_counts(comparisons),
                   limitations=['No allocation addresses or placement measured; only existing resource reuse/lifecycles controlled.',
                                'Host pause is not verified GPU idle; clocks and other GPU clients unmeasured.',
                                'Build configuration comparison retains the D3D12 debug layer in both.',
                                'Three launches per mode on one GPU do not prove general repeatability.',
                                'A live load process and completed GPU timings do not measure continuous utilization or scheduler overlap.'])
    return summary


def run(probe, sdk_bin, inputs, folder, quiet_seconds, *, load_dxr=None, load_seconds=300, load_samples=1024):
    folder.mkdir(parents=True, exist_ok=False)
    try:
        if load_dxr:
            with GPULoad(load_dxr, inputs, folder, load_seconds, load_samples) as load:
                summary = run_matrix(probe, sdk_bin, inputs, folder, quiet_seconds, load)
                load.check()
            summary['gpu_load'] = load.report
        else:
            summary = run_matrix(probe, sdk_bin, inputs, folder, quiet_seconds)
            summary['gpu_load'] = dict(enabled=False)
        save(folder/'verification.json', summary)
        return summary
    except BaseException as error:
        save(folder/'failure.json', dict(result='failed-execution', error_type=type(error).__name__,
                                       gpu_load_requested=load_dxr is not None,
                                       completed_checkpoints=len(list(folder.glob('*-checkpoint.json')))))
        raise


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
    execute.add_argument('--with-gpu-load', action='store_true', help='opt in to a contained second-process headless GPU workload')
    execute.add_argument('--load-dxr', type=Path, help='required with --with-gpu-load; rrt_dxr executable')
    execute.add_argument('--load-seconds', type=float, default=300, help='hard load lifetime, 5..600 seconds (default 300)')
    execute.add_argument('--load-samples', type=int, default=1024, help='samples per 2048x1536 headless GI render, 1..4096')
    worker = sub.add_parser('_gpu-load-worker', help=argparse.SUPPRESS)
    for key in ('dxr', 'scene', 'out'):
        worker.add_argument('--'+key, type=Path, required=True)
    worker.add_argument('--seconds', type=float, required=True)
    worker.add_argument('--samples', type=int, required=True)
    args = parser.parse_args()
    if args.command == '_gpu-load-worker':
        return gpu_load_worker(args.dxr, args.scene, args.out, args.seconds, args.samples)
    if args.command == 'prepare':
        prepare(args.dxr.resolve(strict=True), args.out)
        return 0
    if not 0 <= args.quiet_seconds <= 5:
        parser.error('quiet interval must be finite and within 0..5 seconds')
    if args.with_gpu_load != (args.load_dxr is not None):
        parser.error('--with-gpu-load and --load-dxr must be supplied together')
    try:
        load_bounds(args.load_seconds, args.load_samples)
    except ValueError as error:
        parser.error(str(error))
    folder = args.out or Path(tempfile.mkdtemp(prefix='rr-repeatability-', dir=args.probe.parent))/'results'
    summary = run(args.probe, args.sdk_bin, args.inputs, folder, args.quiet_seconds,
                  load_dxr=args.load_dxr, load_seconds=args.load_seconds, load_samples=args.load_samples)
    print(json.dumps(dict(result=summary['result'], exact_comparisons=summary['exact_comparisons'],
                         quality_acceptance=summary['quality_acceptance'], artifacts=str(folder))))
    return 0 if summary['result'] == 'observed-exact-sample' else 1


if __name__ == '__main__':
    raise SystemExit(main())
