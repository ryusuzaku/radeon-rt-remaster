"""Real SDK lifecycle acceptance. Leaves a report and fails on SDK anomalies.

Not registered as passing CTest acceptance while the pinned SDK fails this gate.
Allocation-failure injection is opt-in because it currently crashes the child.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--sdk-bin', type=Path, required=True)
    parser.add_argument('--exercise-allocation-failure', action='store_true')
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='rr-context-', dir=args.probe.parent))
    cases = {}
    def run(name, extra):
        command = [str(args.probe), '--sdk-bin', str(args.sdk_bin), '--debug', '--context-test', *extra]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (folder/f'{name}.stdout.txt').write_text(result.stdout, encoding='utf-8')
        (folder/f'{name}.stderr.txt').write_text(result.stderr, encoding='utf-8')
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = None
        cases[name] = dict(exit_code=result.returncode, report=data)
        return result, data
    result, rejected = run('preflight-rejection', ['--budget-mib', '1'])
    assert result.returncode == 1 and rejected
    rejection = rejected['context_tests'][0]
    assert rejection['result'] == 'preflight-budget-rejected'
    assert not rejection['create_attempted'] and rejection['allocations'] == 0
    result, normal = run('bounded', ['--cycles', '3'])
    mechanics = bool(normal and normal['contexts_created'] == normal['contexts_destroyed'] == 3)
    if mechanics:
        for cycle in normal['context_tests']:
            mechanics &= (cycle['created'] and cycle['destroyed'] and cycle['hard_budget_enforced']
                          and 0 < cycle['callback_peak_bytes'] <= cycle['budget_bytes']
                          and cycle['allocations'] == cycle['releases'] > 0
                          and cycle['callback_live_bytes_after_destroy'] == cycle['callback_errors'] == cycle['allocation_denials'] == 0)
    accepted = result.returncode == 0 and mechanics
    control, _ = run('sdk-allocator-control', ['--cycles', '1', '--sdk-allocator-control'])
    accepted &= control.returncode == 0
    if args.exercise_allocation_failure:
        failure, data = run('injected-failure', ['--cycles', '1', '--fail-allocation', '2'])
        clean_failure = bool(failure.returncode == 1 and data and data['contexts_created'] == 0
                             and data['context_tests'][0]['callback_live_bytes_after_destroy'] == 0)
        recovery, recovered = run('post-failure-recovery', ['--cycles', '1'])
        cases['injected-failure']['graceful'] = clean_failure
        cases['post-failure-recovery']['lifetime_recovered'] = bool(recovered and recovered['contexts_created'] == recovered['contexts_destroyed'] == 1)
        accepted &= clean_failure and recovery.returncode == 0
    report = dict(result='pass' if accepted else 'acceptance-failed', lifecycle_mechanics='pass' if mechanics else 'failed',
                  allocation_failure_exercised=args.exercise_allocation_failure, cases=cases, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(result=report['result'], lifecycle_mechanics=report['lifecycle_mechanics'], artifacts=str(folder))))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
