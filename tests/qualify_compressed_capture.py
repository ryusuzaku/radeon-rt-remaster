"""V15 native compressed capture, exact blocks and conservative write evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from inspect_position_capture import inspect, inspect_bytes
from texture_assets import TextureAssets
from replay_pixel_material import replay
from qualify_compressed_pixel import blocks


def qualify(fixture, proxy, root, clean, asset_env, code, pixel_code):
    evidence = {'version': 15, 'accepted': [], 'rejected': [], 'legacy': []}
    flags = dict(asset_env, RRT_POSITION_COMPRESSED_TEXTURES='1')

    def run(case, suffix='', environment=None, proxied=True):
        source = root / ('compressed-' + case + suffix + '.jsonl')
        env = dict(clean, RRT_MATERIAL_FIXTURE_CASE=case)
        if proxied:
            env.update(flags if environment is None else environment)
            env.update(RRT_FIXTURE_PROXY=str(proxy), RRT_POSITION_CAPTURE_FILE=str(source))
        native = subprocess.run([str(fixture), '--pixel-material'], input=code + '\n' + pixel_code + '\n',
                                env=env, capture_output=True, text=True, timeout=60)
        assert native.returncode == 0, (case, native.stdout, native.stderr)
        return source, json.loads(native.stdout)

    for name in ('DXT1', 'DXT3', 'DXT5'):
        for action in ('full', 'partial', 'readonly', 'refresh', 'failed', 'alias', 'dirty', 'incomplete', 'flags', 'unaligned'):
            case = name.lower() + '-' + action
            source, native = run(case)
            # Compare all 24 native float images, not just the tolerance/coverage
            # aggregates from the independently evaluated vertex path.
            _, baseline = run(case, '-baseline', proxied=False)
            assert native == baseline, (case, native, baseline)
            report = inspect(source, include_records=True)
            assert report['version'] == 15, report
            rows = report['records']
            if action not in ('full', 'partial', 'readonly', 'refresh'):
                assert not rows and report['rejections'], (case, report)
                evidence['rejected'].append(case)
                continue
            assert len(rows) == 16 and report['completion'] == 'capture_limit', (case, report)
            ids = [t['id'] for t in rows[0]['texture_inputs']]
            for row in rows:
                for value, sampler in zip(row['texture_inputs'], row['pixel_material']['samplers']):
                    slot = ids.index(value['id'])
                    for level, (mip, desc) in enumerate(zip(value['mips'], sampler['texture']['descriptors'])):
                        expected = blocks(name, *desc[:2], level, slot)
                        assert mip == {'sha256': hashlib.sha256(expected).hexdigest(), 'size': len(expected)}
                        assert (Path(str(source) + '.assets') / (mip['sha256'] + '.bin')).read_bytes() == expected
            from capture_position_scene import Capture
            assert Capture(source).report()['candidates'][0]['texture_inputs'] == rows[0]['texture_inputs']
            result = replay(source, fixture, None if action == 'full' else 0)
            assert all(r['status'] == 'matched' for r in result['draws']), (case, result)
            evidence['accepted'].append(dict(case=case, native_sha256=native['native_sha256'], replay=result))
            if action != 'full':
                continue
            # Version downgrade cannot retroactively admit compressed textures.
            original = [json.loads(line) for line in source.read_bytes().splitlines()]
            for mutation in ('v14', 'v13', 'size', 'dxt2', 'dxt4', 'pool', 'alignment', 'tail'):
                changed = copy.deepcopy(original)
                row = next(r for r in changed if r.get('status') == 'captured')
                t = row['pixel_material']['samplers'][0]['texture']
                if mutation.startswith('v'):
                    changed[0]['version'] = int(mutation[1:])
                elif mutation == 'size':
                    row['texture_inputs'][0]['mips'][0]['size'] += 1
                elif mutation in ('dxt2', 'dxt4', 'pool'):
                    for d in t['descriptors']:
                        if mutation == 'pool':
                            d[4] = 0
                        else:
                            d[2] = int.from_bytes(mutation.upper().encode(), 'little')
                elif mutation == 'alignment':
                    for i, d in enumerate(t['descriptors']):
                        d[0] = max(1, 15 >> i)
                else:
                    row['texture_inputs'][0]['mips'][-1]['size'] = 1
                try:
                    inspect_bytes((''.join(json.dumps(r) + '\n' for r in changed)).encode(), assets=TextureAssets(source))
                except ValueError:
                    pass
                else:
                    raise AssertionError((case, 'malformed compressed evidence admitted', mutation))
                evidence['rejected'].append(case + ':' + mutation)
            for version in (13, 14):
                legacy = dict(asset_env)
                if version == 13:
                    legacy.pop('RRT_POSITION_TEXTURE_ASSETS')
                old_source, old_native = run(case, '-v' + str(version), legacy)
                old_report = inspect(old_source, include_records=True)
                assert old_report['version'] == version and not old_report['records'] and old_native == native
                evidence['legacy'].append(case + ':v' + str(version))
    for name in ('dxt2', 'dxt4'):
        source, _ = run(name + '-full')
        assert not inspect(source)['captures'], name
    source, _ = run('valid')
    assert inspect(source)['version'] == 15 and len(inspect(source)['captures']) == 16
    assert replay(source, fixture, 0)['draws'][0]['status'] == 'matched'
    for invalid in ({'RRT_POSITION_COMPRESSED_TEXTURES': '1'},
                    dict(asset_env, RRT_POSITION_COMPRESSED_TEXTURES='2')):
        source, _ = run('dxt1-full', '-invalid-' + str(len(invalid)), invalid)
        assert not source.exists() and not Path(str(source) + '.assets').exists()
    (root / 'compressed-capture-comparison.json').write_text(json.dumps(evidence, indent=2))
