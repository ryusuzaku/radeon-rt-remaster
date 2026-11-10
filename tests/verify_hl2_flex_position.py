"""Local-evidence oracle for the second admitted vertex program (docs/HL2_FLEX_POSITION_CONTRACT.md).

Requires the user's own HL2 shader inventory, which holds the program's bytes; nothing from the title is committed.

  1. The native fixture runs the unmodified program on the GPU with the title's exact declaration and compares it with the
     CPU evaluator (24 variants: stride-0 and per-vertex flex, a near plane through the triangle), plus evaluator and
     standalone-capture negatives. A changed byte must be refused.
  2. The same fixture runs under the real proxy with position capture on. The ledger must hold captured draws of this program
     with stream-2 evidence for both stride layouts, and the reader must accept them.
  3. The reader must refuse a ledger whose flex value, constant-row list or program bytes were altered.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_position_capture import FLEX_BYTES, FLEX_DIGEST, FLEX_ROWS, inspect, inspect_bytes  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--fixture', type=Path, required=True)
parser.add_argument('--proxy', type=Path, required=True)
parser.add_argument('--inventory', type=Path, required=True)
args = parser.parse_args()

code = None
with args.inventory.open(encoding='utf-8') as stream:
    for _ in range(4098):
        line = stream.readline(70001)
        if not line: break
        assert len(line) <= 70000 and line.endswith('\n')
        candidate = json.loads(line).get('vs')
        if isinstance(candidate, str) and len(candidate) == FLEX_BYTES * 2 and hashlib.sha256(bytes.fromhex(candidate)).hexdigest() == FLEX_DIGEST:
            code = candidate; break
assert code is not None, 'the inventory does not hold the second program'

clean = {k: v for k, v in os.environ.items() if not k.upper().startswith('RRT_')}
result = subprocess.run([str(args.fixture), '--hl2-flex-position'], input=code + '\n', env=clean, capture_output=True, text=True, timeout=120)
assert result.returncode == 0, (result.stdout, result.stderr)
assert 'PASS exact HL2 flex VS hardware raster oracle: variants=24' in result.stdout, result.stdout
print(result.stdout, end='')
bad = ('0' if code[0] != '0' else '1') + code[1:]
result = subprocess.run([str(args.fixture), '--hl2-flex-position'], input=bad + '\n', env=clean, capture_output=True, text=True, timeout=30)
assert result.returncode != 0 and 'position program not admitted' in result.stderr, (result.stdout, result.stderr)

root = Path(tempfile.mkdtemp(prefix='flex-position-', dir=args.fixture.parent))
ledger = root / 'capture.jsonl'
env = dict(clean, RRT_FIXTURE_PROXY=str(args.proxy.resolve()), RRT_POSITION_CAPTURE_FILE=str(ledger))
result = subprocess.run([str(args.fixture), '--hl2-flex-position'], input=code + '\n', env=env, capture_output=True, text=True, timeout=180)
assert result.returncode == 0, (result.stdout, result.stderr, root)
report = inspect(ledger, include_records=True)
records = report['records']
assert report['completion'] == 'capture_limit' and len(records) == 4, report
assert all(c['program'] == 'flex' for c in report['captures']), report['captures']
strides = sorted(r['flex']['stride'] for r in records)
assert 0 in strides and 28 in strides, strides  # the title's stride-0 binding and a per-vertex stream both went through the proxy
for record in records:
    assert record['constant_rows'] == FLEX_ROWS and len(record['shader']) == FLEX_BYTES * 2
    assert record['flex']['vb_size'] > 0 and record['provenance']['vb_id'] > 0

data = ledger.read_bytes()
lines = data.splitlines(keepends=True)
# Mutate the captured draw with the largest flex scale (c3.x is the second constant row): variant 0 has c3.x == 0, where a
# shifted flex value changes nothing and the reader would rightly accept it.
captured = [i for i, l in enumerate(lines) if b'"status":"captured"' in l]
scale = lambda i: abs(struct.unpack_from('<f', bytes.fromhex(json.loads(lines[i])['constants']), 16)[0])
first = max(captured, key=scale)
assert scale(first) > 0.01, 'no captured draw applies its flex value'


def mutated(change):
    row = json.loads(lines[first]); change(row)
    return b''.join(lines[:first] + [(json.dumps(row, separators=(',', ':')) + '\n').encode()] + lines[first + 1:])


def refused(blob, reason):
    try:
        inspect_bytes(blob)
    except ValueError as error:
        assert reason in str(error), (reason, str(error)); return
    raise AssertionError(f'reader accepted a ledger it should refuse ({reason})')


def shift_flex(row):
    values = bytearray(bytes.fromhex(row['flex']['values'])); x = struct.unpack_from('<f', values, 0)[0]
    struct.pack_into('<f', values, 0, x + 0.25); row['flex']['values'] = values.hex()


refused(mutated(shift_flex), 'position calculation mismatch')
refused(mutated(lambda row: row.__setitem__('constant_rows', FLEX_ROWS[:-1])), 'flex constant rows')
refused(mutated(lambda row: row.__setitem__('shader', ('1' if row['shader'][0] == '0' else '0') + row['shader'][1:])), 'program identity')
refused(mutated(lambda row: row.pop('flex')), 'flex metadata')
print(json.dumps({'result': 'pass', 'captured': len(records), 'flex_strides': strides, 'ledger': str(ledger)}))
