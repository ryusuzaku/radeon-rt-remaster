"""V12 paired material state; texture contents and write provenance stay unknown.

The payload declares which constant rows the bound program reads, because there is
more than one admitted program now. `rows` is present in captures written after
2026-10-20; older captures predate it and are still valid, so a missing `rows` means
"the original four-row program" rather than an error.

The program table is duplicated in `src/shader/pixel_material.inc`. Adding an entry
to one without the other makes a capture unreadable, which is the failure this
validator exists to make loud.
"""
import hashlib
import math
import struct

PROGRAMS = {
    # 1792-byte program: fog from the interpolated factor in t4.w.
    'ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11':
        {'bytes': 1792, 'rows': [11, 12, 29, 30]},
    # 1912-byte program: fog from length(t4.xyz - c10.xyz).
    'dbca89ccb0e1d72bae02fb44cef4b80a6088cec6d163f0d4fe3dbf8661b199b0':
        {'bytes': 1912, 'rows': [10, 11, 12, 29, 30]},
}
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
    need(type(samplers) is list and len(samplers) == 2, 'samplers')
    identities = {}
    for s in samplers:
        need(type(s) is dict and set(s) == {'states', 'texture'}, 'sampler shape')
        states = s['states']
        need(type(states) is list and len(states) == 13 and all(map(uint, states)), 'states')
        t = s['texture']
        need(type(t) is dict and set(t) == {'id', 'type', 'levels', 'lod', 'autogen_filter',
                                           'contents', 'descriptors'}, 'texture shape')
        need(type(t['id']) is int and 0 < t['id'] < 2 ** 64, 'identity')
        need(type(t['type']) is int and t['type'] == 3 and t['contents'] == 'unknown',
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
