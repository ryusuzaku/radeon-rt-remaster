"""Native v16 whole-chain uploads, provenance and dirty-region rejection."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from capture_position_scene import Capture
from inspect_position_capture import inspect, inspect_bytes
from texture_assets import TextureAssets
from replay_pixel_material import replay
from qualify_compressed_pixel import blocks


def qualify(fixture, proxy, root, clean, asset_env, code, pixel_code):
    flags = dict(asset_env, RRT_POSITION_COMPRESSED_TEXTURES='1', RRT_POSITION_TEXTURE_UPLOADS='1')
    summary = {'version': 16, 'accepted': [], 'rejected': [], 'legacy': []}

    def run(case, suffix='', env_flags=None, proxied=True):
        source = root / ('upload-' + case + suffix + '.jsonl')
        env = dict(clean, RRT_MATERIAL_FIXTURE_CASE='valid' if case == 'managed' else 'upload-' + case)
        if proxied:
            env.update(flags if env_flags is None else env_flags)
            env.update(RRT_FIXTURE_PROXY=str(proxy), RRT_POSITION_CAPTURE_FILE=str(source))
        native = subprocess.run([str(fixture), '--pixel-material'], input=code + '\n' + pixel_code + '\n',
                                env=env, capture_output=True, text=True, timeout=60)
        assert native.returncode == 0, (case, native.stdout, native.stderr)
        return source, json.loads(native.stdout)

    for name in ('rgba', 'dxt1', 'dxt3', 'dxt5'):
        for action in ('full', 'partialinit', 'refresh', 'recover', 'sourcechanged',
                       'partial', 'consumed', 'failed', 'sourcealias', 'unknown', 'destalias', 'mismatch', 'incomplete', 'lowermip'):
            case = name + '-' + action
            source, native = run(case)
            _, baseline = run(case, '-baseline', proxied=False)
            assert native == baseline, (case, native, baseline)
            capture = inspect(source, include_records=True)
            assert capture['version'] == 16
            if action not in ('full', 'partialinit', 'refresh', 'recover', 'sourcechanged'):
                assert not capture['records'] and capture['rejections'], (case, capture)
                summary['rejected'].append(case)
                continue
            rows = capture['records']
            assert len(rows) == 16 and capture['completion'] == 'capture_limit', (case, capture)
            ids = [t['id'] for t in rows[0]['texture_inputs']]
            generation = 1 if action in ('refresh', 'recover') else 0
            for row in rows:
                for texture, sampler in zip(row['texture_inputs'], row['pixel_material']['samplers']):
                    slot = ids.index(texture['id'])
                    assert texture['origin'] == 'observed_private_default_update'
                    transfer = texture['transfer']
                    assert transfer['operation'] == 'UpdateTexture' and transfer['scope'] == 'whole_chain'
                    assert transfer['source'] > 0 and transfer['source'] != texture['id'] and transfer['revision'] > 0
                    for level, (mip, desc) in enumerate(zip(texture['mips'], sampler['texture']['descriptors'])):
                        assert desc[3:] == [0, 0, 0, 0]
                        if name == 'rgba':
                            data = b''.join(struct.pack('<I', 0xff000000 | ((32+x*13+(level+generation)*7)<<16) |
                                                       ((40+y*17+slot*31)<<8) | (60+(level+generation)*19))
                                            for y in range(desc[1]) for x in range(desc[0]))
                        else:
                            data = blocks(name.upper(), *desc[:2], level + generation, slot)
                        assert mip == {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
                        assert (Path(str(source)+'.assets') / (mip['sha256']+'.bin')).read_bytes() == data
            assert Capture(source).report()['candidates'][0]['texture_inputs'] == rows[0]['texture_inputs']
            result = replay(source, fixture, None if action == 'full' else 0)
            assert all(r['status'] == 'matched' for r in result['draws']), (case, result)
            summary['accepted'].append(dict(case=case, native_sha256=native['native_sha256'], replay=result))
            if action != 'full':
                continue
            original = [json.loads(line) for line in source.read_bytes().splitlines()]
            for mutation in ('legacy', 'missing', 'origin', 'source', 'revision', 'operation', 'scope', 'systemmem', 'crosssource', 'shared'):
                changed = copy.deepcopy(original)
                row = next(r for r in changed if r.get('status') == 'captured')
                t = row['texture_inputs'][0]
                if mutation == 'legacy':
                    changed[0]['version'] = 15
                elif mutation == 'missing':
                    del t['transfer']
                elif mutation == 'origin':
                    t['origin'] = 'observed_private_managed'
                elif mutation == 'source':
                    t['transfer']['source'] = t['id']
                elif mutation == 'revision':
                    t['transfer']['revision'] = False
                elif mutation in ('operation', 'scope'):
                    t['transfer'][mutation] = 'inferred'
                elif mutation == 'crosssource':
                    t['transfer']['source'] = row['texture_inputs'][1]['id']
                elif mutation == 'shared':
                    row['texture_inputs'][1]['transfer'] = copy.deepcopy(t['transfer'])
                else:
                    for d in row['pixel_material']['samplers'][0]['texture']['descriptors']:
                        d[4] = 2
                try:
                    inspect_bytes((''.join(json.dumps(r)+'\n' for r in changed)).encode(), assets=TextureAssets(source))
                except ValueError:
                    pass
                else:
                    raise AssertionError((case, mutation))
                summary['rejected'].append(case + ':' + mutation)
            legacy_flags = dict(flags)
            legacy_flags.pop('RRT_POSITION_TEXTURE_UPLOADS')
            old, old_native = run(case, '-legacy', legacy_flags)
            assert inspect(old)['version'] == 15 and not inspect(old)['captures'] and old_native == native
            summary['legacy'].append(case)
    source, _ = run('managed')
    managed = inspect(source, include_records=True)
    assert managed['version'] == 16 and len(managed['records']) == 16
    assert all(t['origin'] == 'observed_private_managed' and 'transfer' not in t for t in managed['records'][0]['texture_inputs'])
    assert replay(source, fixture, 0)['draws'][0]['status'] == 'matched'
    for i, invalid in enumerate(({'RRT_POSITION_TEXTURE_UPLOADS':'1'}, dict(flags, RRT_POSITION_TEXTURE_UPLOADS='2'),
                                 dict(asset_env, RRT_POSITION_TEXTURE_UPLOADS='1'))):
        source, _ = run('rgba-full', '-invalid' + str(i), invalid)
        assert not source.exists() and not Path(str(source)+'.assets').exists()
    (root / 'texture-upload-comparison.json').write_text(json.dumps(summary, indent=2))


if __name__ == '__main__':
    import argparse
    import os
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--proxy', type=Path, required=True)
    args = parser.parse_args()
    row = inspect(args.capture, include_records=True)['records'][0]
    clean = {k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
    suffixes = ('FRAME_SAMPLING', 'MULTI_DRAW', 'RENDER_STATE', 'CLEAR_EVIDENCE',
                'WRITE_EVIDENCE', 'SURFACE_SCOPE', 'COLOR_REPLAY', 'MATERIAL_INPUTS',
                'PIXEL_MATERIAL', 'TEXTURE_INPUTS', 'TEXTURE_ASSETS')
    flags = {'RRT_POSITION_' + s:'1' for s in suffixes}
    flags['RRT_POSITION_SELECTION'] = '128x96:1'
    root = Path(tempfile.mkdtemp(prefix='texture-uploads-', dir=args.fixture.resolve().parent))
    qualify(args.fixture.resolve(), args.proxy.resolve(), root, clean, flags,
            row['shader'], row['color_replay']['pixel_shader'])
    print('PASS texture uploads: ' + str(root))
