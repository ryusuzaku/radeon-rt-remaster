"""Contract: the admitted pixel-program table is one description, not three.

docs/schemas/pixel-programs.json is the source of truth; src/shader/pixel_material.inc
is what the proxy admits; src/shader/pixel_replay_fixture.inc is what the replay
fixture admits; tools/position_pixel_material.py reads the schema directly. A digest,
byte count or constant-row set in one but not the others would either capture draws
the reader then refuses, or let the reader accept draws the proxy never claimed.
Pure Python, no build needed.

The sampler-slot capture path currently binds slots 0 and 1 as 2D textures for every
admitted program; the schema's `samplers` must match that boundary until the capture
path is generalized (docs/MATERIAL_FAMILY_CONTRACTS.md, implementation step 1).
"""
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
schema = json.loads((root / 'docs/schemas/pixel-programs.json').read_text(encoding='utf-8'))
assert schema['schema'] == 'rrt-pixel-programs' and schema['version'] == 1

programs = schema['programs']
digests = [p['sha256'] for p in programs]
assert all(re.fullmatch(r'[0-9a-f]{64}', d) for d in digests), 'digests must be lowercase SHA-256'
assert len(set(digests)) == len(digests), 'digests must be unique'
for p in programs:
    assert isinstance(p['bytes'], int) and 8 <= p['bytes'] <= 2048 and p['bytes'] % 4 == 0, 'program size'
    rows = p['rows']
    assert isinstance(rows, list) and 1 <= len(rows) <= 5 and all(isinstance(r, int) and 0 <= r < 31 for r in rows), 'constant rows'
    assert len(set(rows)) == len(rows), 'constant rows must be unique'
    samplers = p['samplers']
    assert isinstance(samplers, list) and 1 <= len(samplers) <= 16, 'sampler count'
    slots = [s['slot'] for s in samplers]
    assert all(isinstance(s['slot'], int) and 0 <= s['slot'] < 16 for s in samplers), 'sampler slot'
    assert len(set(slots)) == len(slots), 'sampler slots must be unique'
    assert all(s['type'] in (3, 4) for s in samplers), 'sampler type (3=2D, 4=cube)'
    # Current capture boundary: every admitted program binds slots 0..1 as 2D.
    assert samplers == [{'slot': 0, 'type': 3}, {'slot': 1, 'type': 3}], \
        'sampler capture is not generalized yet; see MATERIAL_FAMILY_CONTRACTS.md step 1'

by_digest = {p['sha256']: p for p in programs}

# The proxy table: {bytes,"digest",{rows...},rowCount}.
inc = (root / 'src/shader/pixel_material.inc').read_text(encoding='utf-8')
proxy = re.findall(r'\{(\d+),"([0-9a-f]{64})",\{([\d,]+)\},(\d+)\}', inc)
assert proxy, 'no PixelPrograms entries found in pixel_material.inc'
assert len(proxy) == len(programs), 'proxy table size differs from schema'
for bytes_, digest, rows_csv, count in proxy:
    assert digest in by_digest, f'proxy admits unknown program {digest[:8]}'
    p = by_digest[digest]
    rows = [int(x) for x in rows_csv.split(',')][:int(count)]
    assert int(bytes_) == p['bytes'], f'{digest[:8]} byte count differs'
    assert int(count) == len(p['rows']) and rows == p['rows'], f'{digest[:8]} constant rows differ'

# The fixture mirror: {bytes,rowCount,"digest"} plus programRows[][5].
fixture = (root / 'src/shader/pixel_replay_fixture.inc').read_text(encoding='utf-8')
mirror = re.findall(r'\{(\d+),(\d+),"([0-9a-f]{64})"\}', fixture)
assert len(mirror) == len(programs), 'fixture table size differs from schema'
rows_block = re.search(r'programRows\[\]\[5\]=\{(.+?)\};', fixture, re.S)
assert rows_block, 'no programRows table in fixture'
fixture_rows = [[int(x) for x in group.split(',')][:count]
                for group, count in zip(re.findall(r'\{([\d,]+)\}', rows_block.group(1)),
                                        [int(c) for _, c, _ in mirror])]
for (bytes_, count, digest), rows in zip(mirror, fixture_rows):
    assert digest in by_digest, f'fixture admits unknown program {digest[:8]}'
    p = by_digest[digest]
    assert int(bytes_) == p['bytes'] and int(count) == len(p['rows']), f'{digest[:8]} fixture size differs'
    assert rows == p['rows'], f'{digest[:8]} fixture constant rows differ'

# The reader derives its table from the schema; confirm it agrees.
sys.path.insert(0, str(root / 'tools'))
import position_pixel_material as reader
assert set(reader.PROGRAMS) == set(digests), 'reader table differs from schema'
for digest, p in by_digest.items():
    r = reader.PROGRAMS[digest]
    assert r['bytes'] == p['bytes'] and r['rows'] == p['rows'] and r['samplers'] == p['samplers'], \
        f'{digest[:8]} reader table differs'

print(f'PASS pixel program table: {len(programs)} programs, schema/proxy/fixture/reader agree')
