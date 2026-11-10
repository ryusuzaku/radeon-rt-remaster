"""Local-evidence oracle for the third admitted vertex program, the skinned one (docs/HL2_SKINNED_POSITION_CONTRACT.md).

Requires the user's own HL2 shader inventory, which holds the program's bytes; nothing from the title is committed.

  1. The native fixture runs the unmodified program on the GPU with the title's exact declaration and a full 53-bone palette, and
     compares it with the CPU evaluator (24 variants: three bones per vertex, stride-0 and per-vertex flex, light branches on and
     off, a near plane through the triangle), plus evaluator and standalone-capture negatives. A changed byte must be refused.
  2. The same fixture runs under the real proxy with position capture on, which needs constant tracking past c60: the ledger must
     hold captured skinned draws with bone, blend and stream-2 evidence for both stride layouts, and the reader must accept them.
  3. The reader must refuse a ledger whose weights, bone rows, bone list, index bytes or blend layout were altered.
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
from inspect_position_capture import SKIN_BYTES, SKIN_DIGEST, SKIN_ROWS, inspect, inspect_bytes  # noqa: E402

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
        if isinstance(candidate, str) and len(candidate) == SKIN_BYTES * 2 and hashlib.sha256(bytes.fromhex(candidate)).hexdigest() == SKIN_DIGEST:
            code = candidate; break
assert code is not None, 'the inventory does not hold the skinned program'

clean = {k: v for k, v in os.environ.items() if not k.upper().startswith('RRT_')}
result = subprocess.run([str(args.fixture), '--hl2-skin-position'], input=code + '\n', env=clean, capture_output=True, text=True, timeout=120)
assert result.returncode == 0, (result.stdout, result.stderr)
assert 'PASS exact HL2 skinned VS hardware raster oracle: variants=24' in result.stdout, result.stdout
print(result.stdout, end='')
bad = ('0' if code[0] != '0' else '1') + code[1:]
result = subprocess.run([str(args.fixture), '--hl2-skin-position'], input=bad + '\n', env=clean, capture_output=True, text=True, timeout=30)
assert result.returncode != 0 and 'position program not admitted' in result.stderr, (result.stdout, result.stderr)

root = Path(tempfile.mkdtemp(prefix='skin-position-', dir=args.fixture.parent))
ledger = root / 'capture.jsonl'
env = dict(clean, RRT_FIXTURE_PROXY=str(args.proxy.resolve()), RRT_POSITION_CAPTURE_FILE=str(ledger))
result = subprocess.run([str(args.fixture), '--hl2-skin-position'], input=code + '\n', env=env, capture_output=True, text=True, timeout=180)
assert result.returncode == 0, (result.stdout, result.stderr, root)
report = inspect(ledger, include_records=True)
records = report['records']
assert report['completion'] == 'capture_limit' and len(records) == 4, report
assert all(c['program'] == 'skin' for c in report['captures']), report['captures']
strides = sorted(r['flex']['stride'] for r in records)
assert 0 in strides and 28 in strides, strides
for record in records:
    assert record['constant_rows'] == SKIN_ROWS and record['bones']['offsets'] == [6, 15, 21, 33, 51, 78, 126, 144, 156], record['bones']['offsets']
    assert record['blend']['weights_offset'] == 12 and record['blend']['indices_offset'] == 16

lines = ledger.read_bytes().splitlines(keepends=True)
first = next(i for i, l in enumerate(lines) if b'"status":"captured"' in l)


def mutated(change):
    row = json.loads(lines[first]); change(row)
    return b''.join(lines[:first] + [(json.dumps(row, separators=(',', ':')) + '\n').encode()] + lines[first + 1:])


def refused(blob, reason):
    try:
        inspect_bytes(blob)
    except ValueError as error:
        assert reason in str(error), (reason, str(error)); return
    raise AssertionError(f'reader accepted a ledger it should refuse ({reason})')


def edit_blend(row, corner, weights=None, color=None):
    values = bytearray(bytes.fromhex(row['blend']['values'])); w0, w1, c = struct.unpack_from('<2hI', values, corner * 8)
    struct.pack_into('<2hI', values, corner * 8, *(weights or (w0, w1)), c if color is None else color); row['blend']['values'] = values.hex()


def edit_bone_row(row):
    values = bytearray(bytes.fromhex(row['bones']['rows'])); x = struct.unpack_from('<f', values, 0)[0]
    struct.pack_into('<f', values, 0, x + 0.25); row['bones']['rows'] = values.hex()


refused(mutated(lambda row: edit_blend(row, 0, weights=(1000, -1000))), 'position calculation mismatch')
refused(mutated(edit_bone_row), 'position calculation mismatch')
refused(mutated(lambda row: edit_blend(row, 0, color=0x00000101)), 'recorded bones differ')  # a vertex reading bones nobody recorded
refused(mutated(lambda row: row['bones'].update(offsets=row['bones']['offsets'][1:], rows=row['bones']['rows'][96:])), 'recorded bones differ')
refused(mutated(lambda row: row['blend'].update(weights_offset=8)), 'blend weight declaration')
refused(mutated(lambda row: row.__setitem__('constant_rows', SKIN_ROWS[:-1])), 'skinned constant rows')
refused(mutated(lambda row: row.pop('bones')), 'bone metadata')
print(json.dumps({'result': 'pass', 'captured': len(records), 'flex_strides': strides, 'ledger': str(ledger)}))
