"""Local-evidence checks for the vs_2_0 position interpreter (docs/VS_INTERPRETER.md).

Requires the user's own HL2 shader inventory, which holds the programs' bytes and declarations; nothing from the title is committed.

  1. Self-test: on the three hand-admitted programs the interpreter equals the hand-written evaluators bit for bit (12,000
     random comparisons), and refuses an unknown constant, a changed slice opcode, a truncated program and vs_3_0.
  2. Synthetic GPU oracle: two token-assembled programs exercise mova rounding of fractional and negative values, the negate
     modifier, min, max, abs, dp3 and partial write masks on the hardware.
  3. For every admitted program the inventory holds: the GPU point oracle (instrumented bytecode, one-pixel points, all four clip
     components) passes; the C++ and Python analyses agree on the slice length; and the fixture drawn under the real proxy yields
     four captured draws that the reader's independent interpreter accepts.
  4. The reader refuses a ledger whose input bytes, constant list, camera or program bytes were altered.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vs_interpreter as vi  # noqa: E402
from inspect_position_capture import DIGEST, FLEX_DIGEST, SKIN_DIGEST, inspect, inspect_bytes  # noqa: E402
from position_interpreted import ADMITTED  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--fixture', type=Path, required=True)
parser.add_argument('--proxy', type=Path, required=True)
parser.add_argument('--inventory', type=Path, required=True)
args = parser.parse_args()
fixture = str(args.fixture.resolve())
clean = {k: v for k, v in os.environ.items() if not k.upper().startswith('RRT_')}

programs = {}
with args.inventory.open(encoding='utf-8') as stream:
    for _ in range(4098):
        line = stream.readline(70001)
        if not line: break
        assert len(line) <= 70000 and line.endswith('\n')
        row = json.loads(line)
        if row.get('kind') != 'draw' or not isinstance(row.get('vs'), str): continue
        digest = hashlib.sha256(bytes.fromhex(row['vs'])).hexdigest()
        programs.setdefault(digest, (row['vs'], row['declaration']))
for name, digest in (('first', DIGEST), ('flex', FLEX_DIGEST), ('skinned', SKIN_DIGEST)):
    assert digest in programs, f'the inventory does not hold the {name} hand-admitted program'


def run(mode, text, env=clean, timeout=180):
    return subprocess.run([fixture, mode], input=text, env=env, capture_output=True, text=True, timeout=timeout)


result = run('--interpret-selftest', '\n'.join(programs[d][0] for d in (DIGEST, FLEX_DIGEST, SKIN_DIGEST)) + '\n')
assert result.returncode == 0 and 'bit for bit: comparisons=12000' in result.stdout, (result.stdout, result.stderr)
print(result.stdout, end='')
result = run('--interpret-synthetic', '')
assert result.returncode == 0 and 'PASS interpreter synthetic GPU oracle: programs=2 vertices=4096' in result.stdout, (result.stdout, result.stderr)
print(result.stdout, end='')

covered = sorted(d for d in ADMITTED if d in programs)
assert covered, 'the inventory holds none of the admitted interpreted programs'
root = Path(tempfile.mkdtemp(prefix='vs-interpreter-', dir=args.fixture.parent))
ledgers = {}
for digest in covered + [DIGEST, FLEX_DIGEST, SKIN_DIGEST]:
    code, declaration = programs[digest]
    result = run('--interpret-oracle', code + '\n' + declaration + '\n')
    assert result.returncode == 0 and 'max_normalized_error=' in result.stdout, (digest, result.stdout, result.stderr)
    slice_length = int(re.search(r'slice=(\d+)', result.stdout).group(1))
    python = vi.analyse(list(struct.unpack('<%dI' % (len(code) // 8), bytes.fromhex(code))))
    assert sum(i['slice'] for i in python['code']) == slice_length, (digest, 'the C++ and Python slices differ')
    if digest not in ADMITTED: continue
    ledger = root / f'{digest[:8]}.jsonl'
    env = dict(clean, RRT_FIXTURE_PROXY=str(args.proxy.resolve()), RRT_POSITION_CAPTURE_FILE=str(ledger))
    result = run('--interpret-capture', code + '\n' + declaration + '\n', env=env)
    assert result.returncode == 0, (digest, result.stdout, result.stderr)
    report = inspect(ledger, include_records=True)
    assert report['completion'] == 'capture_limit' and [c['program'] for c in report['captures']] == ['interpreted'] * 4, (digest, report)
    ledgers[digest] = ledger
print(f'PASS interpreted programs: {len(covered)} of {len(ADMITTED)} admitted programs in the inventory; GPU point oracle, C++/Python slice agreement and proxy capture each')

# Reader negatives on a program with a view-projection camera, when the inventory holds one.
first_record = lambda d: json.loads(ledgers[d].read_text().splitlines()[1])
target = next((d for d in covered if first_record(d)['interpreted']['camera'] == {'view_projection': 8}), covered[0])
lines = ledgers[target].read_bytes().splitlines(keepends=True)
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


def shift_position(row):
    entry = next(e for e in row['interpreted']['inputs'] if e['usage'] == 0 and e['usage_index'] == 0)
    raw = bytearray(bytes.fromhex(entry['values'])); x = struct.unpack_from('<f', raw, 0)[0]; struct.pack_into('<f', raw, 0, x + 7.5); entry['values'] = raw.hex()


def drop_register(row):
    table = row['interpreted']['constants']; table['registers'] = table['registers'][1:]; table['values'] = table['values'][32:]


refused(mutated(shift_position), 'position calculation mismatch')
refused(mutated(drop_register), 'interpreted')
refused(mutated(lambda row: row['interpreted'].__setitem__('camera', {'view_projection': 4})), 'camera differs')
flip_last_digit = lambda text: text[:-1] + ('1' if text[-1] == '0' else '0')
refused(mutated(lambda row: row.__setitem__('shader', flip_last_digit(row['shader']))), 'program identity')
refused(mutated(lambda row: row['interpreted']['inputs'].pop()), 'interpreted inputs differ from the position slice')
print(json.dumps({'result': 'pass', 'interpreted_programs': len(covered), 'negatives_on': target[:8], 'artifacts': str(root)}))
