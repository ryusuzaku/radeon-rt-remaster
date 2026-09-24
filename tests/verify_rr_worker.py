"""Acceptance of the containment/workaround boundary, not raw SDK denoising."""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from rr_worker import assess, run_context, strict_json, verify_sdk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--sdk-bin', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='rr-worker-', dir=args.probe.parent))
    results = {}
    def check(condition, message):
        if not condition:
            raise AssertionError(message)
    for scenario in ('success', 'failure', 'malformed', 'nul', 'crash', 'timeout', 'overflow'):
        process = subprocess.run([str(args.probe), '--isolation-test', scenario], capture_output=True, text=True, timeout=40)
        check(process.returncode == 0, process.stderr)
        data = strict_json(process.stdout)
        results[scenario] = data
        check(data['job_assigned_before_resume'] and data['child_reaped'], scenario+' not contained')
        check(len(data['stdout']) <= 65536 and len(data['stderr']) <= 65536, 'unbounded output')
        if scenario == 'success':
            check(data['exit_code'] == 0 and strict_json(data['stdout']) == {'fixture': True}, 'success transport failed')
        elif scenario == 'timeout':
            check(data['timed_out'], 'deadline not enforced')
        elif scenario == 'overflow':
            check(data['output_limit_exceeded'], 'output limit not enforced')
        elif scenario == 'crash':
            check(data['exit_code'] == 0xe0005252, 'crash code lost')
        elif scenario == 'nul':
            check(data['stdout'] == '{}\0extra', 'embedded NUL was truncated')
        check(assess(data)['status'] == 'unavailable', 'fixture accepted as RR context')
    exited = subprocess.run([str(args.probe), '--isolation-test', 'parent-exit'], capture_output=True, text=True, timeout=10)
    check(exited.returncode == 55, 'parent-death fixture failed')
    pid = strict_json(exited.stdout)['child_pid']
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if handle:
        try:
            check(kernel.WaitForSingleObject(handle, 2000) == 0, 'worker survived parent exit')
        finally:
            kernel.CloseHandle(handle)
    else:
        check(ctypes.get_last_error() == 87, 'could not establish child termination')
    results['parent_exit'] = dict(parent_exit_code=55, child_pid=pid, child_terminated=True)
    try:
        verify_sdk(folder)
    except ValueError:
        pass
    else:
        raise AssertionError('untrusted SDK accepted')
    for name in ('amd_fidelityfx_loader_dx12.dll', 'amd_fidelityfx_denoiser_dx12.dll'):
        (folder/name).write_bytes(b'untrusted-test-fixture-not-a-DLL')
    try:
        verify_sdk(folder)
    except ValueError:
        pass
    else:
        raise AssertionError('unreviewed DLL hashes accepted')
    healthy = run_context(args.probe, args.sdk_bin, cycles=3)
    results['healthy'] = healthy
    check(healthy['decision']['status'] == 'context-ready-with-workarounds', 'pinned workaround did not pass')
    check(healthy['decision']['raw_sdk_acceptance'] == 'failed' and not healthy['decision']['rr_rendering'], 'raw SDK status concealed')
    check(assess(healthy['worker'], cycles=3)['status'] == 'unavailable', 'workaround enabled without policy')
    envelope = healthy['worker']
    original = strict_json(envelope['stdout'])
    mutations = dict(width=1920, height=1080, hard_budget_enforced=False, callback_peak_bytes=2**30,
                     callback_live_bytes_after_destroy=1, releases=5, allocation_attempts=7, callback_errors=1,
                     create_code=6, destroy_code=1, actual_query_code=6, actual_bytes=42, actual_aliasable_bytes=0,
                     provider_query_code=5, requested_provider_id=0, allocations=True, validation=False, predicted_bytes=1)
    for key, value in mutations.items():
        changed = copy.deepcopy(original)
        changed['context_tests'][0][key] = value
        candidate = dict(envelope, stdout=json.dumps(changed))
        check(assess(candidate, cycles=3, allow_workaround=True)['status'] == 'unavailable', 'accepted mutation '+key)
    malformed = ('{"adapter":0,"adapter":0}', '{"x":NaN}', '{}\0extra', '['*2000+']'*2000)
    for text in malformed:
        candidate = dict(envelope, stdout=text)
        check(assess(candidate, cycles=3, allow_workaround=True)['status'] == 'unavailable', 'malformed JSON accepted')
    rejected = run_context(args.probe, args.sdk_bin, budget_mib=1)
    check(rejected['decision']['reason'] == 'budget-rejected', 'preflight rejection lost')
    results['budget_rejected'] = rejected
    failed = run_context(args.probe, args.sdk_bin, fail_allocation=2)
    check(failed['decision']['reason'] == 'worker-crash' and failed['worker']['child_reaped'], 'SDK crash not contained')
    results['sdk_allocation_failure'] = failed
    recovered = run_context(args.probe, args.sdk_bin)
    check(recovered['decision']['status'] == 'context-ready-with-workarounds', 'recovery failed')
    results['recovered'] = recovered
    report = dict(result='pass', scope='context-containment-and-pinned-reporting-workarounds',
                  raw_sdk_acceptance='failed', rr_rendering=False, rejected_mutations=len(mutations)+len(malformed),
                  cases=results, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('result', 'scope', 'raw_sdk_acceptance', 'rr_rendering', 'artifacts')}))


if __name__ == '__main__':
    main()
