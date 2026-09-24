"""Verify the optional SDK probe without pretending a query is an RR dispatch."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--sdk-bin', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='rr-probe-', dir=args.probe.parent))
    def run(extra):
        return subprocess.run([str(args.probe), *map(str, extra)], text=True, capture_output=True, timeout=45)
    assert run(['--help']).returncode == 0
    for extra in ([], ['--sdk-bin', 'relative'], ['--sdk-bin', folder],
                  ['--sdk-bin', args.sdk_bin, '--adapter', '-1'], ['--unknown'],
                  ['--sdk-bin', args.sdk_bin, '--cycles', '2'],
                  ['--sdk-bin', args.sdk_bin, '--context-test', '--cycles', '4'],
                  ['--sdk-bin', args.sdk_bin, '--context-test', '--budget-mib', '65'],
                  ['--sdk-bin', args.sdk_bin, '--sdk-allocator-control'],
                  ['--sdk-bin', args.sdk_bin, '--context-test', '--sdk-allocator-control', '--fail-allocation', '2']):
        result = run(extra)
        assert result.returncode == 1 and not result.stdout, (extra, result)
    result = run(['--sdk-bin', args.sdk_bin, '--debug', '--allocator-test'])
    (folder/'stderr.txt').write_text(result.stderr, encoding='utf-8')
    assert result.returncode in (0, 77), result.stderr
    data = json.loads(result.stdout)
    assert data['contexts_created'] == data['dispatches'] == 0
    assert data['allocator_contract'] == 'pass'
    assert data['sdk_api'] == '1.2.0'
    assert bool(data['providers']) == (result.returncode == 0)
    for provider in data['providers']:
        assert len(provider['memory']) == 3
        for size in provider['memory']:
            assert size['query_code'] == 0
            assert size['total_bytes'] > 0
            assert 0 <= size['aliasable_bytes'] <= size['total_bytes']
            assert size['persistent_bytes'] == size['total_bytes'] - size['aliasable_bytes']
    data['contract_test'] = 'pass'
    (folder/'verification.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(artifacts=str(folder), **data)))


if __name__ == '__main__':
    main()
