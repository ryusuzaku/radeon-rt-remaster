"""Diagnostic composition of compatible captured draws, not game-frame replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from inspect_position_capture import inspect_bytes, need
from position_initial_contents import assess


def groups(path):
    with Path(path).open('rb') as f:
        data = f.read(16*1024*1024+1)
    from texture_assets import TextureAssets
    report = inspect_bytes(data, include_records=True, assets=TextureAssets(path))
    need(report['version'] >= 3, 'group replay requires captured interval evidence')
    need(report['completion'] in ('capture_limit', 'attempt_limit', 'byte_limit', 'present_limit')
         and report['records'], 'completed accepted evidence required')
    grouped = {}
    for row in report['records']:
        t = row['timing']
        # Same dimensions alone do not prove the same physical render target/pass.
        key = (row['device'], t['reset_epoch'], t['present_interval'],
               tuple(row['target']), row['viewport'], row['constants'][32:160],
               json.dumps(row.get('render_state'),sort_keys=True))
        grouped.setdefault(key, []).append(row)
    result = []
    for key, rows in sorted(grouped.items()):
        rows.sort(key=lambda r: r['timing']['indexed_draw'])
        result.append((key, rows))
    return hashlib.sha256(data).hexdigest(), report['session'], result


def payload(rows):
    need(1 <= len(rows) <= 16, 'group draw budget')
    need(len({r['shader'] for r in rows}) == 1, 'mixed group programs')
    return '\n'.join(['RRT_POSITION_GROUP1', str(len(rows)), rows[0]['shader']] +
                     [value for r in rows for value in (r['constants'], r['positions'])]) + '\n'


def replay(path, fixture):
    digest, session, batches = groups(path)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('RRT_')}
    results = []
    for key, rows in batches:
        run = subprocess.run([str(fixture), '--position-group'], input=payload(rows),
                             text=True, capture_output=True, env=env, timeout=60)
        if run.returncode:
            result = {'status': 'failed', 'error': run.stderr[:1000]}
        else:
            result = json.loads(run.stdout)
            need(result.get('status') in ('matched', 'empty') and result.get('draws') == len(rows), 'invalid group response')
        results.append({'device': key[0], 'reset_epoch': key[1], 'present_interval': key[2],
                        'source_target': key[3], 'source_viewport': key[4],
                        'captured_render_state': json.loads(key[6]),
                        'initial_content_admission': assess(rows[0]),
                        'per_draw_admission': [assess(row) for row in rows],
                        'ordinals': [r['ordinal'] for r in rows],
                        'triangles': sum(r['primitives'] for r in rows), **result})
    return {'schema': 'rrt-position-group-replay', 'version': 1,
            'source_sha256': digest, 'session': session, 'groups': results,
            'policy': 'one clear per compatible group; indexed-draw order; depth/blending off; last covering draw wins',
            'scope': '128x96 position-output diagnostic; matching target descriptors do not prove pass identity; no materials or real game-frame equivalence'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--fixture', type=Path, required=True)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    try:
        if a.out: need(not a.out.exists(), 'output already exists')
        result = replay(a.capture, a.fixture)
        if a.out:
            with a.out.open('x', encoding='utf-8') as f: json.dump(result, f, indent=2)
        print(json.dumps(result, indent=2))
        if any(g['status'] == 'failed' for g in result['groups']): raise SystemExit(1)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as e:
        p.exit(2, f'group replay rejected: {e}\n')
