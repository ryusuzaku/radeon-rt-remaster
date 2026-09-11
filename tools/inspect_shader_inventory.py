"""Bounded, CPU-only inspection of opaque shader/layout evidence; never executes it."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

def need(ok, message):
    if not ok:
        raise ValueError(message)

def inspect(path):
    path = Path(path)
    need(path.stat().st_size <= 16*1024*1024, 'inventory exceeds byte budget')
    programs = {}; families = Counter(); layouts = {}; ordinals = set()
    header = None; footer = None; failed = 0; unavailable = 0
    def blob(value, maximum, alignment):
        need(isinstance(value, str) and len(value) <= maximum*2, 'invalid hex length')
        data = bytes.fromhex(value)
        need(data and len(data) <= maximum and len(data) % alignment == 0, 'invalid blob size')
        return data
    def program(value, stage):
        if value is None:
            return None
        data = blob(value, 16384, 4); digest = hashlib.sha256(data).hexdigest()
        programs[stage+':'+digest] = {'stage': stage, 'sha256': digest, 'bytes': len(data),
                                    'version_token': f'{struct.unpack_from("<I", data)[0]:08x}'}
        return digest
    with path.open('rb') as stream:
        for number in range(4099):
            line = stream.readline(70001)
            if not line:
                break
            need(len(line) <= 70000 and line.endswith(b'\n'), 'oversized or truncated record')
            record = json.loads(line)
            need(isinstance(record, dict), 'record must be an object')
            need(footer is None, 'records after footer')
            if header is None:
                need(record.get('kind') == 'header' and record.get('schema') == 'rrt-shader-inventory' and record.get('version') == 1, 'invalid header')
                need(type(record.get('draw_limit')) is int and 1 <= record['draw_limit'] <= 4096, 'invalid draw limit')
                header = record; continue
            if record.get('kind') == 'end':
                need(record.get('reason') in ('draw_limit','byte_limit','io_error','internal_error'), 'invalid termination')
                need(record.get('committed') == len(ordinals), 'footer count mismatch')
                if record['reason'] == 'draw_limit':
                    need(len(ordinals) == header['draw_limit'], 'early draw-limit footer')
                footer = record; continue
            need(record.get('kind') == 'draw', 'unknown record')
            ordinal = record.get('ordinal'); hr = record.get('hr')
            need(type(ordinal) is int and 0 <= ordinal < header['draw_limit'] and ordinal not in ordinals, 'invalid/duplicate ordinal')
            need(type(hr) is int and -(2**31) <= hr < 2**31, 'invalid HRESULT')
            need(record.get('query') in ('ok', 'unavailable'), 'invalid query status')
            ordinals.add(ordinal)
            if hr < 0:
                failed += 1
            if record['query'] != 'ok':
                unavailable += 1; continue
            need('vs' in record and 'ps' in record, 'missing shader bindings')
            vs = program(record['vs'], 'vs'); ps = program(record['ps'], 'ps')
            decl = blob(record.get('declaration'), 520, 8)
            elements = list(struct.iter_unpack('<HHBBBB', decl))
            need(elements[-1] == (255,0,17,0,0,0), 'missing declaration terminator')
            need(all(e[0] < 16 for e in elements[:-1]), 'invalid declaration stream')
            streams = record.get('streams'); need(isinstance(streams, list) and len(streams) <= 16, 'invalid streams')
            seen = set()
            for s in streams:
                need(isinstance(s,list) and len(s)==5 and all(type(n) is int and 0<=n<2**32 for n in s), 'invalid stream tuple')
                need(s[0]<16 and s[0] not in seen and s[4] in (0,1), 'invalid stream identity')
                seen.add(s[0])
            need(seen == {e[0] for e in elements[:-1]}, 'declaration/stream mismatch')
            need(type(record.get('topology')) is int and type(record.get('index_format')) is int, 'invalid draw metadata')
            # Offset is per-draw placement, not a vertex-layout family discriminator.
            layout = {'vs':vs,'ps':ps,'elements':elements,
                      'streams':sorted([s[0],s[2],s[3],s[4]] for s in streams),
                      'topology':record['topology'],'index_format':record['index_format']}
            key = hashlib.sha256(json.dumps(layout,sort_keys=True).encode()).hexdigest()
            if hr >= 0:
                families[key] += 1; layouts[key] = layout
        else:
            raise ValueError('too many records')
    need(header is not None, 'missing header')
    return {'schema':'rrt-shader-inventory-summary','version':1,
            'completion':footer['reason'] if footer else 'partial',
            'draws':len(ordinals),'failed_draws':failed,'unavailable_queries':unavailable,
            'programs':list(programs.values()),
            'families':[dict(sha256=k,draws=n,**layouts[k]) for k,n in families.most_common()]}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('inventory',type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.inventory),indent=2))
    except (OSError,ValueError,TypeError,KeyError) as error:
        parser.exit(2, f'inventory rejected: {error}\n')
