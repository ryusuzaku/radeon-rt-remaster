"""V12 paired material state; texture contents and write provenance stay unknown.

The payload declares which constant rows the bound program reads, because there is
more than one admitted program now. `rows` is present in captures written after
2026-10-20; older captures predate it and are still valid, so a missing `rows` means
"the original four-row program" rather than an error.

The program table is the single source of truth in docs/schemas/pixel-programs.json,
mirrored by src/shader/pixel_material.inc and the replay fixture;
tests/verify_pixel_program_table.py keeps the descriptions identical. Adding an entry
to one without the others makes a capture unreadable, which is the failure this
validator exists to make loud.

Each sampler may carry an explicit `slot` (captures written after the sampler table
landed). A missing `slot` means the legacy implicit order — sampler i binds slot i —
so older captures still validate.
"""
import hashlib
import json
import math
import struct
from pathlib import Path

_SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'docs' / 'schemas' / 'pixel-programs.json').read_text(encoding='utf-8'))
PROGRAMS = {p['sha256']: {'bytes': p['bytes'], 'rows': p['rows'], 'samplers': p['samplers']}
            for p in _SCHEMA['programs']}
DIGEST = 'ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11'


def validate(row):
    def need(ok, message):
        if not ok:
            raise ValueError('pixel material: ' + message)

    def uint(v):
        return type(v) is int and 0 <= v < 2 ** 32

    m = row.get('pixel_material')
    need(row['write_evidence']['overlap'] is False, 'observed overlap')
    need(type(m) is dict and set(m) in ({'constants', 'samplers'},
                                        {'constants', 'samplers', 'rows'}), 'shape')
    code = bytes.fromhex(row['color_replay']['pixel_shader'])
    digest = hashlib.sha256(code).hexdigest()
    need(digest in PROGRAMS, 'program')
    program = PROGRAMS[digest]
    need(len(code) == program['bytes'], 'program size')
    if 'rows' in m:
        need(m['rows'] == program['rows'], 'declared constant rows')
    rows = program['rows']
    c = m['constants']
    width = 8 * 4 * len(rows)
    need(type(c) is str and len(c) == width and all(x in '0123456789abcdef' for x in c),
         'constant blob')
    need(all(map(math.isfinite, struct.unpack('<%df' % (4 * len(rows)), bytes.fromhex(c)))),
         'nonfinite constants')
    samplers = m['samplers']
    declared = program['samplers']
    need(type(samplers) is list and len(samplers) == len(declared), 'samplers')
    identities = {}
    for i, s in enumerate(samplers):
        need(type(s) is dict and set(s) in ({'states', 'texture'}, {'states', 'texture', 'slot'}),
             'sampler shape')
        if 'slot' in s:
            need(uint(s['slot']) and s['slot'] == declared[i]['slot'], 'declared sampler slot')
        states = s['states']
        need(type(states) is list and len(states) == 13 and all(map(uint, states)), 'states')
        t = s['texture']
        need(type(t) is dict and set(t) == {'id', 'type', 'levels', 'lod', 'autogen_filter',
                                           'contents', 'descriptors'}, 'texture shape')
        need(type(t['id']) is int and 0 < t['id'] < 2 ** 64, 'identity')
        need(type(t['type']) is int and t['type'] == declared[i]['type'] and t['contents'] == 'unknown',
             'texture type/contents')
        need(type(t['levels']) is int and 1 <= t['levels'] <= 16 and uint(t['lod'])
             and uint(t['autogen_filter']), 'texture parameters')
        ds = t['descriptors']
        need(type(ds) is list and len(ds) == t['levels'], 'levels')
        for i, d in enumerate(ds):
            need(type(d) is list and len(d) == 7 and all(map(uint, d))
                 and 1 <= d[0] <= 16384 and 1 <= d[1] <= 16384, 'descriptor')
            if i:
                need(d[:2] == [max(1, ds[0][0] >> i), max(1, ds[0][1] >> i)]
                     and d[2:] == ds[0][2:], 'mip descriptor')
        if t['id'] in identities:
            need(t == identities[t['id']], 'inconsistent shared binding')
        identities[t['id']] = t
