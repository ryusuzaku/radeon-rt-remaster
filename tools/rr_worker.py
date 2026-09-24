"""Supervise the isolated RR context research worker, never the game process.

This policy works around two exact reporting defects in the pinned SDK. It does
not alter raw SDK diagnostics, render an RR frame, or repair the SDK binary.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROVIDER = 4311875584
DLL_HASHES = {
    'amd_fidelityfx_denoiser_dx12.dll': '48f1e5888ba6a0a3d59a98b9751e37c392b0f7b8c223d0082d5c1f40642879d3',
    'amd_fidelityfx_loader_dx12.dll': 'e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa',
}
INVALID_SDK_TOTAL = 18446744073689694208
INVALID_SDK_TOTAL_256 = 18446744073688121344


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('nonfinite JSON constant: '+value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)


def verify_sdk(directory):
    hashes = {}
    for name, expected in DLL_HASHES.items():
        path = directory/name
        if not path.is_file() or not 0 < path.stat().st_size <= 32*1024*1024:
            raise ValueError('SDK DLL missing or oversized: '+name)
        with path.open('rb') as stream:
            state = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                state.update(chunk)
            digest = state.hexdigest()
        if digest != expected:
            raise ValueError('SDK DLL does not match the reviewed 2.3.0 build: '+name)
        hashes[name] = digest
    return hashes


def assess(envelope, *, cycles=1, budget_mib=64, adapter=0, allow_workaround=False, expected_dispatches=0, recorded_segments=False,width=128,height=96):
    """Fail closed on protocol, lifecycle, budgets and unexpected SDK failures."""
    result = dict(status='unavailable', reason='invalid-worker-report', rr_rendering=False, workarounds=[])
    def need(condition):
        if not condition:
            raise ValueError('worker contract mismatch')
    try:
        need(type(recorded_segments) is bool)
        need(type(expected_dispatches) is int and 0 <= expected_dispatches <= 8)
        need(type(cycles) is int and 1 <= cycles <= (expected_dispatches if recorded_segments else 3))
        need(type(budget_mib) is int and 1 <= budget_mib <= 64)
        need(type(adapter) is int and 0 <= adapter <= 31)
        need(type(expected_dispatches) is int and 0 <= expected_dispatches <= 8)
        need(envelope['protocol'] == 'rr-isolation-1')
        need(envelope['job_assigned_before_resume'] is True and envelope['child_reaped'] is True)
        need(envelope['output_limit_bytes'] == 65536)
        for stream in ('stdout', 'stderr'):
            need(isinstance(envelope[stream], str) and len(envelope[stream].encode('utf-8')) <= 65536)
        if envelope['timed_out'] is True:
            return dict(result, reason='worker-timeout')
        if envelope['output_limit_exceeded'] is True:
            return dict(result, reason='worker-output-limit')
        need(envelope['timed_out'] is False and envelope['output_limit_exceeded'] is False)
        code = envelope['exit_code']
        need(type(code) is int and 0 <= code <= 0xffffffff)
        if code not in (0, 1, 77):
            return dict(result, reason='worker-crash', worker_exit_code=code)
        if code == 77:
            return dict(result, reason='no-provider')
        data = strict_json(envelope['stdout'])
        for key in ('adapter', 'dispatches', 'contexts_created', 'contexts_destroyed'):
            need(type(data[key]) is int)
        need(data['adapter'] == adapter and data['sdk_api'] == '1.2.0')
        need(data['shader_model_6_6'] is True and data['dispatches'] == expected_dispatches)
        provider = data['providers'][0]
        need(provider['id'] == PROVIDER and provider['name'] == 'FSR Ray Regeneration - 1.2.0')
        rows = data['context_tests']
        need(type(rows) is list)
        for row in rows:
            for key in ('width', 'height', 'preflight_code', 'create_code', 'destroy_code', 'requested_provider_id',
                        'predicted_bytes', 'budget_bytes', 'callback_peak_bytes', 'allocations', 'releases', 'allocation_attempts',
                        'callback_live_bytes_after_destroy', 'callback_errors', 'allocation_denials', 'actual_query_code',
                        'actual_bytes', 'actual_aliasable_bytes', 'provider_query_code', 'provider_id'):
                need(type(row[key]) is int and 0 <= row[key] <= 0xffffffffffffffff)
        if code == 1 and len(rows) == 1 and rows[0]['result'] == 'preflight-budget-rejected':
            row = rows[0]
            need(row['create_attempted'] is False and row['allocations'] == 0)
            need(row['budget_bytes'] == budget_mib*1024*1024 and row['predicted_bytes'] > row['budget_bytes'])
            need(data['contexts_created'] == data['contexts_destroyed'] == 0)
            return dict(result, reason='budget-rejected')
        need(len(rows) == cycles and data['contexts_created'] == data['contexts_destroyed'] == cycles)
        workarounds = set()
        peaks = []
        for row in rows:
            need(row['width']==width and row['height']==height and (width,height) in ((128,96),(256,192)))
            need(row['validation'] is True and row['hard_budget_enforced'] is True)
            need(row['create_attempted'] is True and row['created'] is True and row['destroyed'] is True)
            need(row['preflight_code'] == row['create_code'] == row['destroy_code'] == 0)
            need(row['requested_provider_id'] == PROVIDER)
            budget = row['budget_bytes']
            need(type(budget) is int and budget == budget_mib*1024*1024)
            need(0 < row['predicted_bytes'] <= budget)
            peak = row['callback_peak_bytes']
            need(type(peak) is int and 0 < peak <= budget)
            need(row['allocations'] == row['releases'] == row['allocation_attempts'] == 6)
            need(row['callback_live_bytes_after_destroy'] == row['callback_errors'] == row['allocation_denials'] == 0)
            memory_valid = (row['actual_query_code'] == 0 and row['sdk_memory_valid'] is True
                            and 0 < row['actual_bytes'] <= budget and 0 <= row['actual_aliasable_bytes'] <= row['actual_bytes'])
            if not memory_valid:
                need(allow_workaround and row['actual_query_code'] == 0 and row['sdk_memory_valid'] is False)
                expected_invalid=INVALID_SDK_TOTAL if (width,height)==(128,96) else INVALID_SDK_TOTAL_256
                need(row['actual_bytes'] == expected_invalid and row['actual_aliasable_bytes'] == 65536)
                if (width,height)==(128,96): need(peak == 20971520 and row['predicted_bytes'] == 19988480)
                else: need(peak == 22544384 and row['predicted_bytes'] == 21561344)
                workarounds.add('pinned-sdk-post-context-memory-report')
            if not (row['provider_query_code'] == 0 and row['provider_id'] == PROVIDER):
                need(allow_workaround and row['provider_query_code'] == 6 and row['provider_id'] == 0)
                workarounds.add('pinned-sdk-provider-metadata')
            need(row['result'] in ('context-lifecycle-pass', 'context-validation-failed'))
            peaks.append(peak)
        need((code == 1 and data['result'] == 'validation-failed') if workarounds else (code == 0 and data['result'] == 'context-tests-pass'))
        ready=dict(status='context-ready-with-workarounds' if workarounds else 'context-ready', reason=None,
                   rr_rendering=False, workarounds=sorted(workarounds), accounting='bounded-resource-and-heap-callbacks',
                   peak_callback_bytes=max(peaks), contexts_verified=cycles, requested_provider_id=PROVIDER,
                   raw_sdk_acceptance='failed' if workarounds else 'passed')
        if (width,height)!=(128,96): ready.update(width=width,height=height)
        return ready
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, RecursionError):
        return result


def run_context(probe, sdk_bin, *, cycles=1, budget_mib=64, adapter=0, fail_allocation=None, timeout_ms=30000):
    probe, sdk_bin = Path(probe).resolve(strict=True), Path(sdk_bin).resolve(strict=True)
    if not probe.is_file() or not sdk_bin.is_dir():
        raise ValueError('probe must be a file and SDK path a directory')
    if not 1 <= cycles <= 3 or not 1 <= budget_mib <= 64 or not 0 <= adapter <= 31 or not 1 <= timeout_ms <= 60000:
        raise ValueError('invalid worker limits')
    if fail_allocation is not None and not 1 <= fail_allocation <= 31:
        raise ValueError('invalid failure ordinal')
    hashes = verify_sdk(sdk_bin)
    command = [str(probe), '--isolated-context', '--sdk-bin', str(sdk_bin), '--debug', '--cycles', str(cycles),
               '--budget-mib', str(budget_mib), '--adapter', str(adapter), '--worker-timeout-ms', str(timeout_ms)]
    if fail_allocation is not None:
        command += ['--fail-allocation', str(fail_allocation)]
    process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                             timeout=timeout_ms/1000+10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode != 0 or len(process.stdout) > 1024*1024:
        raise RuntimeError('isolation host failed')
    envelope = strict_json(process.stdout)
    decision = assess(envelope, cycles=cycles, budget_mib=budget_mib, adapter=adapter, allow_workaround=True)
    if fail_allocation is not None and decision['status'].startswith('context-ready'):
        decision = dict(status='unavailable', reason='failure-injection-not-observed', rr_rendering=False, workarounds=[])
    return dict(decision=decision, sdk_sha256=hashes, worker=envelope)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--sdk-bin', required=True, type=Path)
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--budget-mib', type=int, default=64)
    parser.add_argument('--fail-allocation', type=int)
    parser.add_argument('--timeout-ms', type=int, default=30000)
    args = parser.parse_args()
    try:
        report = run_context(args.probe, args.sdk_bin, cycles=args.cycles, budget_mib=args.budget_mib,
                             fail_allocation=args.fail_allocation, timeout_ms=args.timeout_ms)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(decision=dict(status='unavailable', reason=str(error), rr_rendering=False))))
        return 1
    print(json.dumps(report))
    return 0 if report['decision']['status'].startswith('context-ready') else 1


if __name__ == '__main__':
    raise SystemExit(main())
