"""v19 observed texture-mip surface LockRect/UnlockRect tracking.

The source's mip bytes are rewritten without a dirty declaration first, so the
only thing that can supply a whole-chain upload proof is the surface alias lock
itself. A whole level-0 alias lock must be admitted; partial, lower-mip and
failed alias locks must not, the DEFAULT destination alias must stay untracked,
the same case without the option must keep the pre-v19 rejection, and invalid
option chains must fail closed.

Pre-existing transfer controls live in the 'upload' and 'surface' kinds.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from capture_position_scene import Capture
from inspect_position_capture import inspect
from replay_pixel_material import replay
from qualify_compressed_pixel import blocks

FORMATS = ('rgba', 'dxt5')


def rgba(w, h, level, slot):
    return b''.join(struct.pack('<I', 0xff000000 | ((32 + x * 13 + level * 7) << 16) |
                                ((40 + y * 17 + slot * 31) << 8) | (60 + level * 19))
                    for y in range(h) for x in range(w))


def mip_bytes(name, level, slot, desc):
    return rgba(desc[0], desc[1], level, slot) if name == 'rgba' else blocks(name.upper(), *desc[:2], level, slot)


def qualify(fixture, proxy, root, clean, asset_env, code, pixel_code):
    v18 = dict(asset_env, RRT_POSITION_COMPRESSED_TEXTURES='1', RRT_POSITION_TEXTURE_UPLOADS='1',
               RRT_POSITION_DIRTY_TEXTURES='1', RRT_POSITION_SURFACE_UPLOADS='1')
    v19 = dict(v18, RRT_POSITION_SURFACE_LOCKS='1')
    summary = {'version': 19, 'accepted': [], 'rejected': [], 'legacy': []}

    def run(case, suffix='', flags=None, proxied=True):
        path = root / ('locks-' + case + suffix + '.jsonl')
        env = dict(clean, RRT_MATERIAL_FIXTURE_CASE='upload-' + case)
        if proxied:
            env.update(v19 if flags is None else flags)
            env.update(RRT_FIXTURE_PROXY=str(proxy), RRT_POSITION_CAPTURE_FILE=str(path))
        result = subprocess.run([str(fixture), '--pixel-material'], input=code + '\n' + pixel_code + '\n',
                                env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, (case, result.returncode, result.stdout, result.stderr)
        return path, json.loads(result.stdout)

    def rejected(case, flags=None, version=19, suffix=''):
        """The case must reject without capturing, and must not perturb native output."""
        path, native = run(case, suffix, flags)
        _, baseline = run(case, suffix + '-baseline', proxied=False)
        assert native == baseline, (case + suffix, native, baseline)
        report = inspect(path, include_records=True)
        assert report['version'] == version, (case + suffix, report['version'])
        assert not report['records'] and report['rejections'], (case + suffix, report)
        summary['rejected'].append(case + suffix)

    for name in FORMATS:
        case = name + '-aliasfull'

        # v19 admits a whole level-0 surface alias lock as the whole-chain proof.
        path, native = run(case)
        _, baseline = run(case, '-baseline', proxied=False)
        assert native == baseline, (case, native, baseline)
        report = inspect(path, include_records=True)
        assert report['version'] == 19, (case, report['version'])
        rows = report['records']
        assert len(rows) == 16 and report['completion'] == 'capture_limit', (case, report)
        ids = [t['id'] for t in rows[0]['texture_inputs']]
        for row in rows:
            for texture, sampler in zip(row['texture_inputs'], row['pixel_material']['samplers']):
                assert texture['origin'] == 'observed_private_default_update', (case, texture['origin'])
                transfer = texture['transfer']
                assert transfer['operation'] == 'UpdateTexture', (case, transfer)
                assert transfer['scope'] == 'whole_chain', (case, transfer)
                assert transfer['dirty_proof'] == 'top_lock', (case, transfer)
                assert transfer['source'] > 0 and transfer['source'] != texture['id'], (case, transfer)
                assert transfer['revision'] > 0, (case, transfer)
                slot = ids.index(texture['id'])
                # The fixture binds textures[(sampler+variant)%2], so the sampler index is not the
                # fixture texture index; recover it from the bound level-0 extent (16 or 32 wide).
                index = 0 if sampler['texture']['descriptors'][0][0] == 16 else 1
                for level, (mip, desc) in enumerate(zip(texture['mips'], sampler['texture']['descriptors'])):
                    data = mip_bytes(name, level + 1, index, desc)
                    assert mip == {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}, (case, slot, level, mip)
                    assert (Path(str(path) + '.assets') / (mip['sha256'] + '.bin')).read_bytes() == data, (case, slot, level)
        assert Capture(path).report()['candidates'][0]['texture_inputs'] == rows[0]['texture_inputs'], case
        result = replay(path, fixture, 0)
        assert all(d['status'] == 'matched' for d in result['draws']), (case, result)
        summary['accepted'].append(dict(case=case, native_sha256=native['native_sha256'], replay=result))

        # The proof is exactly a whole-mip level-0 lock from the source's own mip surface.
        for action in ('aliaspartial', 'aliasmip', 'aliasreadonly', 'destalias'):
            rejected(name + '-' + action)

        # Regression: the identical case without the option keeps the pre-v19 rejection.
        rejected(case, v18, version=18, suffix='-v18')
        summary['legacy'].append(case + '-v18')

    # An invalid value, or locks enabled without their surface-upload dependency, must fail closed.
    for index, flags in enumerate((dict(v19, RRT_POSITION_SURFACE_LOCKS='2'),
                                   dict(v19, RRT_POSITION_SURFACE_UPLOADS='2'),
                                   dict(v19, RRT_POSITION_DIRTY_TEXTURES='2'))):
        path, _ = run('rgba-aliasfull', '-invalid' + str(index), flags)
        assert not path.exists(), (index, flags)
    (root / 'surface-lock-comparison.json').write_text(json.dumps(summary, indent=2))
