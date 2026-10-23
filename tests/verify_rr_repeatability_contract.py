"""CPU controls for exact RR comparisons, independent of SDK availability."""
from pathlib import Path
import copy
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from rr_repeatability import (CONTROL_KEYS, LOAD_WIDTH, LOAD_HEIGHT, GPULoad, LoadJob, compare_frames, comparison,
                              comparison_counts, gpu_load_worker, guide_digest, load_bounds, replace_json)
from rr_repeatability import run


def need(ok, reason):
    if not ok:
        raise AssertionError(reason)


def load_fixture(folder):
    if sys.stdin.readline() != 'start\n':
        return 1
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    replace_json(folder/'load-state.json', dict(stage='rendering', render_started=time.monotonic(),
                                              completed=[dict(cpu_fixture=True)], child_pid=child.pid))
    time.sleep(600)


def process_dead(pid):
    import ctypes as ct
    from ctypes import wintypes as wt
    api = ct.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    api.OpenProcess.restype = wt.HANDLE
    api.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    api.CloseHandle.argtypes = [wt.HANDLE]
    handle = api.OpenProcess(0x100000, False, pid)
    if not handle:
        return ct.get_last_error() == 87  # no such process, not access denied
    try:
        return api.WaitForSingleObject(handle, 5000) == 0
    finally:
        api.CloseHandle(handle)


def load_contract():
    for seconds, samples in ((float('nan'), 1), (float('inf'), 1), (4, 1), (601, 1), (5, 0), (5, 4097)):
        try:
            load_bounds(seconds, samples)
        except ValueError:
            pass
        else:
            raise AssertionError('unbounded GPU load accepted')
    load_bounds(5, 1)
    load_bounds(600, 4096)
    need(comparison_counts({'a': dict(rgba_byte_equal=True), 'b': dict(rgba_byte_equal=False)}) ==
         dict(total=2, match=1, differ=1), 'exact comparison counts lost a failure')
    need(comparison_counts({}) == dict(total=0, match=0, differ=0), 'empty counts invented results')
    with tempfile.TemporaryDirectory(prefix='rr-load-contract-') as temporary:
        folder = Path(temporary)
        with patch('rr_repeatability.run_matrix', return_value=dict(result='observed-exact-sample')), \
                patch('rr_repeatability.GPULoad') as load_type:
            result = run(None, None, None, folder/'unloaded', 0)
            need(result['gpu_load'] == dict(enabled=False), 'unloaded run labelled as loaded')
            need(not load_type.called, 'GPU load is not opt-in')
        # Exercise the actual worker loop without a GPU: successful GPU-shaped
        # report followed by a synthetic execution failure, both retained.
        native = dict(samples=1, dispatches=1, width=LOAD_WIDTH, height=LOAD_HEIGHT, gpu_trace_ms=1)
        completed = subprocess.CompletedProcess([], 0, json.dumps(native), '')
        import io
        with patch('rr_repeatability.sys.stdin', io.StringIO('start\n')), \
                patch('rr_repeatability.subprocess.run', side_effect=[completed, RuntimeError('fixture')]):
            need(gpu_load_worker(Path('unused'), Path('unused'), folder, 5, 1) == 1, 'worker failure passed')
        state = json.loads((folder/'load-state.json').read_text())
        need(state['stage'] == 'failed' and len(state['completed']) == 1, 'worker checkpoint lost completed work')
        if sys.platform != 'win32':
            print('Windows job lifecycle controls unavailable on this platform; comparison/worker controls passed')
            return
        from verify_dxr import fixture
        from scene_io import encode_scene
        inputs = folder/'inputs'
        inputs.mkdir()
        (inputs/'source.rrscene').write_bytes(encode_scene(fixture()))
        popen = subprocess.Popen

        def start_fixture(command, **kwargs):
            # Replace only the load helper, keeping the real job, stdin gate,
            # watchdog, status reader and descendant cleanup paths.
            output = command[command.index('--out')+1]
            return popen([sys.executable, str(Path(__file__).resolve()), '--load-fixture', output], **kwargs)

        for mode in ('normal', 'exception', 'deadline', 'early-exit', 'assignment-failure'):
            output = folder/mode
            output.mkdir()
            with patch('rr_repeatability.subprocess.Popen', side_effect=start_fixture):
                load = GPULoad(Path(sys.executable), inputs, output, 5, 1)
                try:
                    with patch.object(LoadJob, 'assign', side_effect=RuntimeError('fixture')) if mode == 'assignment-failure' else patch.dict(os.environ, {}):
                        with load:
                            load.check()
                            if mode == 'exception':
                                raise ValueError('fixture')
                            if mode == 'deadline':
                                load.process.wait(timeout=8)
                                load.check()
                            if mode == 'early-exit':
                                load.process.kill()
                                load.process.wait(timeout=5)
                                load.check()
                except (ValueError, RuntimeError):
                    need(mode != 'normal', 'normal lifecycle failed')
                else:
                    need(mode == 'normal', 'load failure was admitted')
            report = json.loads((output/'gpu-load.json').read_text())
            need(report['helper_reaped'] and report['job_active_processes_after_stop'] == 0,
                 'load process escaped cleanup')
            need(report['watchdog_expired'] == (mode == 'deadline'), 'watchdog status misreported')
            if report['state']:
                need(process_dead(report['state']['child_pid']), 'load descendant escaped cleanup')
        # Abrupt parent exit must close the sole job handle and kill its child.
        marker = folder/'abrupt.json'
        process = popen([sys.executable, str(Path(__file__).resolve()), '--abrupt-parent', str(marker)],
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        need(process.wait(timeout=10) == 55, 'abrupt parent fixture failed')
        need(process_dead(json.loads(marker.read_text())['pid']), 'child survived abrupt parent exit')


def main():
    zero = bytes(196696)
    changed = bytearray(zero)
    struct.pack_into('<f', changed, 56, .25)
    delta = compare_frames([zero], [bytes(changed)])
    need(not delta['rgba_byte_equal'] and delta['frames'][0]['pixels_different'] == 1 and
         delta['frames'][0]['components_different'] == 1 and delta['frames'][0]['maximum_rgb_difference'] == .25 and
         delta['frames'][0]['rgb_mse'] == .0625/(128*96*3), 'injected difference missed')
    # Equal RGB with a sign-bit change must still fail exact RGBA equality.
    signed = bytearray(zero)
    struct.pack_into('<I', signed, 56+12, 0x80000000)
    delta = compare_frames([zero], [bytes(signed)])
    need(not delta['rgba_byte_equal'] and delta['frames'][0]['components_different'] == 1 and
         delta['frames'][0]['rgb_mse'] == 0, 'bitwise alpha control missed')
    header = bytearray(zero)
    header[24] = 1
    need(compare_frames([zero], [bytes(header)])['rgba_byte_equal'], 'input identity treated as pixel difference')
    controls = [{key: key for key in CONTROL_KEYS}]
    equal = comparison([zero], [zero], ['a'], ['a'], controls, controls)
    need(all(equal[k] for k in ('rgba_byte_equal', 'input_records_and_matrices_equal', 'dispatch_controls_equal')), 'equal control failed')
    for key in CONTROL_KEYS:
        mutated = [dict(controls[0], **{key: 'changed'})]
        need(not comparison([zero], [zero], ['a'], ['a'], controls, mutated)['dispatch_controls_equal'], 'metadata mutation accepted')
    need(not comparison([zero], [zero], ['a'], ['b'], controls, controls)['input_records_and_matrices_equal'], 'input mismatch accepted')
    frame = dict(frame_index=0, random_index=0, seed=1, reset=True,
                 records=[(0.,)*24], matrices={key: (0.,)*16 for key in
                     ('inverse_view_projection', 'view', 'projection', 'previous_view', 'previous_view_projection')})
    changed = dict(frame, frame_index=4)
    need(guide_digest(frame) == guide_digest(changed), 'global ordinal was not omitted')
    for key, value in (('random_index', 1), ('seed', 2), ('reset', False)):
        need(guide_digest(frame) != guide_digest(dict(frame, **{key: value})), 'sample metadata was omitted')
    changed = copy.deepcopy(frame)
    changed['matrices']['previous_view_projection'] = (1.,)+(0.,)*15
    need(guide_digest(frame) != guide_digest(changed), 'previous matrix was omitted')
    changed = copy.deepcopy(frame)
    changed['records'] = [(-0.,)+(0.,)*23]
    need(guide_digest(frame) != guide_digest(changed), 'input float bits were lost')
    for a, b in (([], []), ([zero], []), ([b'bad'], [zero])):
        try:
            compare_frames(a, b)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid comparison accepted')
    try:
        comparison([zero], [zero], [], [], controls, controls)
    except ValueError:
        pass
    else:
        raise AssertionError('missing metadata accepted')
    load_contract()
    print('RR exact comparison and bounded GPU-load lifecycle controls passed; no SDK/quality acceptance')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--load-fixture':
        raise SystemExit(load_fixture(Path(sys.argv[2])))
    if len(sys.argv) == 3 and sys.argv[1] == '--abrupt-parent':
        job = LoadJob()
        child = subprocess.Popen([sys.executable, '-c', 'import sys,time; sys.stdin.readline(); time.sleep(600)'],
                                 stdin=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        job.assign(child)
        Path(sys.argv[2]).write_text(json.dumps(dict(pid=child.pid)))
        child.stdin.write(b'start\n')
        child.stdin.flush()
        os._exit(55)
    main()
