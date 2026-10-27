"""Compiled transport check: layout in this architecture, and the C++ session against the golden scenarios.

Runs the built `rrt_transport_check` (x86 or x64): its sizeof/offsetof output must equal
docs/schemas/transport-v1.json, and every message of every scenario in tests/transport_vectors.py must get the
outcome the hand-written expectation names. Needs no GPU. The pure-Python half is verify_transport_contract.py.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests'))
import transport_io as t  # noqa: E402
from transport_vectors import scenarios  # noqa: E402


def need(condition, message):
    if not condition: raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', type=Path, required=True); args = parser.parse_args()
    layout = json.loads(subprocess.run([str(args.check), '--layout'], capture_output=True, text=True, check=True, timeout=30).stdout)
    need(layout['little_endian'] is True, 'host is not little-endian; the wire format is')
    need(layout['pointer_bytes'] in (4, 8), 'unexpected pointer size')
    schema = t.SCHEMA
    need(layout['magic'] == schema['magic'] and layout['max_message_bytes'] == schema['max_message_bytes'] and layout['max_in_flight'] == schema['max_in_flight'], 'compiled constants differ from the schema')
    need(layout['sizes']['Header'] == schema['header']['size'], 'Header size')
    need(layout['offsets']['Header'] == {f['name']: f['offset'] for f in schema['header']['fields']}, 'Header offsets')
    for message in schema['messages']:
        if not message['payload_size']:
            continue
        need(layout['sizes'][message['name']] == message['payload_size'], f'{message["name"]} size')
        need(layout['offsets'][message['name']] == {f['name']: f['offset'] for f in message['fields']}, f'{message["name"]} offsets')
    lines = []
    expected = []
    for steps in scenarios().values():
        lines.append('reset')
        for direction, data, code in steps:
            lines.append(f'{direction} {data.hex()}'); expected.append(code)
    result = subprocess.run([str(args.check)], input='\n'.join(lines) + '\n', capture_output=True, text=True, timeout=30)
    need(result.returncode == 0, (result.stdout, result.stderr))
    got = [t.ERRORS[int(x)] for x in result.stdout.split()]
    need(len(got) == len(expected), f'{len(got)} outcomes for {len(expected)} messages')
    for index, (g, e) in enumerate(zip(got, expected)):
        need(g == e, f'message {index}: C++ says {g}, expected {e}')
    print(json.dumps(dict(result='pass', pointer_bytes=layout['pointer_bytes'], messages=len(expected))))
    return 0


if __name__ == '__main__': sys.exit(main())
