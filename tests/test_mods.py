"""Offline replacement validation, ordering and bounded-decoder tests."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from scene_io import decode_scene, encode_scene, SceneError
from mod_scene import load_mod, resolve, extract, payload, strict_json, asset_path
from png_texture import decode_png
from export_gltf import png


def scene_fixture():
    identity = [1.0 if i%5 == 0 else 0.0 for i in range(16)]
    render = [0]*34; render[1] = 3; render[7] = 1; render[21] = 15
    draw = dict(ordinal=0, texture_width=2, texture_height=2,
        world=identity, view=identity, projection=identity, viewport=[0,0,64,64,0.0,1.0],
        scissor=[0,0,64,64], render=render, texture_states=[4,2,0,2,2,0,0,0],
        sampler=[1,1,1,0,1,1,0,0,0,1,0,0,0],
        vertices=[[-.8,-.7,.5,0xffffffff,0,1],[0,.8,.5,0xffffffff,.5,0],[.8,-.7,.5,0xffffffff,1,1]],
        indices=[0,1,2], texture=b'\xff\xff\xff\xff'*4)
    other = copy.deepcopy(draw); other['ordinal'] = 1; other['texture'] = b'\x00\x00\xff\xff'*4
    return decode_scene(encode_scene(dict(frame=0, width=64, height=64, clear_color=0xff142850,
        attempted=2, cleared=True, complete=True, rejected=[], draws=[draw, other])))


class Mods(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scene = scene_fixture()
        self.counter = 0

    def mod(self, kind='texture', target=None, priority=0, identifier=None, asset=None):
        self.counter += 1
        name = identifier or f'mod-{self.counter}'
        if asset is None:
            asset = png(2,2,b'\xff\x00\xff\xff'*4)
        (self.root/(name+'.asset')).write_bytes(asset)
        entry = dict(kind=kind, target=target or self.scene['draws'][0][kind+'_id'], asset=name+'.asset', sha256=sha256(asset).hexdigest())
        manifest = dict(schema='rrt-mod', version=1, id=name, priority=priority, replacements=[entry])
        path = self.root/(name+'.json'); path.write_text(json.dumps(manifest))
        return path

    def test_roundtrip_and_extraction(self):
        raw = encode_scene(self.scene)
        self.assertEqual(raw, encode_scene(decode_scene(raw)))
        folder = self.root/'edit'
        extract(self.scene, folder)
        noop, _ = resolve(self.scene, [load_mod(folder/'mod.json')])
        self.assertEqual(noop, raw)
        with self.assertRaises(FileExistsError):
            extract(self.scene, folder)
        for image in (folder/'textures').glob('*.png'):
            self.assertEqual(decode_png(image.read_bytes())[:2], (2,2))

    def test_isolation_and_original_id_composition(self):
        before = encode_scene(self.scene)
        texture = load_mod(self.mod())
        material = load_mod(self.mod('material', asset=json.dumps(dict(version=1, min_filter='linear', alpha_mode='blend')).encode()))
        result, report = resolve(self.scene, [texture, material])
        output = decode_scene(result)
        self.assertEqual(output['draws'][1], self.scene['draws'][1])
        self.assertNotEqual(output['draws'][0]['texture_id'], self.scene['draws'][0]['texture_id'])
        self.assertEqual(output['draws'][0]['sampler'][5], 2)
        self.assertEqual(output['draws'][0]['render'][12], 1)
        self.assertEqual(len(report['matched_draws'][0]['replacements']), 2)
        self.assertEqual(encode_scene(self.scene), before)

    def test_priority_and_conflicts(self):
        low = load_mod(self.mod(priority=-1))
        high = load_mod(self.mod(priority=1, asset=png(1,1,b'\x00\xff\x00\xff')))
        a, ra = resolve(self.scene, [low, high])
        b, rb = resolve(self.scene, [high, low])
        self.assertEqual((a,ra), (b,rb))
        self.assertEqual(len(ra['shadowed']), 1)
        same = load_mod(self.mod(priority=1))
        with self.assertRaisesRegex(SceneError, 'equal-priority'):
            resolve(self.scene, [low, high, same])
        with self.assertRaisesRegex(SceneError, 'duplicate mod IDs'):
            resolve(self.scene, [high, high])

    def test_unmatched_and_partial(self):
        mod = load_mod(self.mod(target='0'*64))
        with self.assertRaisesRegex(SceneError, 'unmatched'):
            resolve(self.scene, [mod])
        raw, report = resolve(self.scene, [mod], allow_unmatched=True)
        self.assertEqual(raw, encode_scene(self.scene)); self.assertEqual(len(report['unmatched']), 1)
        scene = copy.deepcopy(self.scene); scene['complete'] = False
        scene['rejected'] = [dict(ordinal=0xffffffff, reason='unsupported_frame_operation')]
        with self.assertRaisesRegex(SceneError, 'incomplete'):
            resolve(scene, [])
        raw, _ = resolve(scene, [], allow_partial=True)
        self.assertFalse(decode_scene(raw)['complete'])

    def test_manifest_rejections(self):
        path = self.mod()
        original = json.loads(path.read_text())
        cases = []
        for key, value in [('version', True), ('schema', 'wrong'), ('priority', True), ('id', '../bad'), ('extra', 1)]:
            bad = copy.deepcopy(original); bad[key] = value; cases.append(bad)
        for key, value in [('target', 'x'*64), ('kind', 'script'), ('sha256', '0'*64),
                           ('asset', '../escape.png'), ('asset', 'C:/secrets'), ('asset', 'https://x/a.png'),
                           ('asset', '/absolute'), ('asset', 'dir\\file.png'), ('asset', 'missing.png')]:
            bad = copy.deepcopy(original); bad['replacements'][0][key] = value; cases.append(bad)
        bad = copy.deepcopy(original); bad['replacements'] *= 2; cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad):
                path.write_text(json.dumps(bad))
                with self.assertRaises((SceneError, OSError)):
                    load_mod(path)
        for data in (b'{"version":1,"version":2}', b'{"n":NaN}', b'['*2000, b'\xff'):
            with self.assertRaises(SceneError):
                strict_json(data)

    def test_symlink_escape(self):
        outside = self.root/'outside'; outside.mkdir(); (outside/'asset').write_bytes(b'x')
        inside = self.root/'mod'; inside.mkdir()
        try:
            (inside/'link').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit creating test symlinks')
        with self.assertRaises(SceneError):
            asset_path(inside, 'link/asset')

    def test_mesh_material_validation(self):
        mesh = dict(version=1, vertices=self.scene['draws'][0]['vertices'], indices=[0,1,2])
        mod = load_mod(self.mod('mesh', asset=json.dumps(mesh).encode()))
        self.assertEqual(resolve(self.scene, [mod])[0], encode_scene(self.scene))
        for indices in ([0,1,3], [0,1], [True,1,2], []):
            bad = {**mesh, 'indices': indices}
            with self.assertRaises(SceneError):
                payload('mesh', json.dumps(bad).encode())
        for material in (dict(version=True), dict(version=1), dict(version=1, roughness=.5),
                         dict(version=1, double_sided=1), dict(version=1, alpha_cutoff=10),
                         dict(version=1, min_filter='magic')):
            with self.assertRaises(SceneError):
                payload('material', json.dumps(material).encode())

    def test_decoded_budget_and_invalid_loser(self):
        path = self.mod(asset=png(16,16,b'\xff\x00\xff\xff'*256))
        with patch('mod_scene.MAX_BYTES', 1024):
            with self.assertRaisesRegex(SceneError, 'decoded-payload budget'):
                load_mod(path)
        # A lower-priority entry is still a validated dependency, not ignored.
        loser = self.mod(priority=-10)
        data = json.loads(loser.read_text())
        (self.root/data['replacements'][0]['asset']).write_bytes(b'invalid')
        with self.assertRaisesRegex(SceneError, 'checksum'):
            load_mod(loser)

    def test_png_filters_and_bounds(self):
        def chunk(kind, data):
            return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
        for channels, color in ((3,2), (4,6)):
            rows = [bytes((10,20,30,40,50,60,70,80)[:channels*2]), bytes((90,80,70,60,50,40,30,20)[:channels*2])]
            expected = b''.join(bytes((row[x+2],row[x+1],row[x],row[x+3] if channels==4 else 255)) for row in rows for x in range(0,len(row),channels))
            for filter_type in range(5):
                raw = bytearray(); previous = bytes(channels*2)
                for row in rows:
                    raw.append(filter_type)
                    for x,v in enumerate(row):
                        a = row[x-channels] if x>=channels else 0; b = previous[x]; c = previous[x-channels] if x>=channels else 0
                        p = a+b-c; distances = (abs(p-a),abs(p-b),abs(p-c))
                        predictor = (0,a,b,(a+b)//2,(a,b,c)[distances.index(min(distances))])[filter_type]
                        raw.append((v-predictor)&255)
                    previous = row
                data = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',2,2,8,color,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
                self.assertEqual(decode_png(data), (2,2,expected))
        valid = png(1,1,b'\x00\xff\x00\xff')
        broken = [valid[:-1], valid+b'x', valid[:30]+b'x'+valid[31:], png(2049,1,b'\x00'*8196)]
        header = chunk(b'IHDR',struct.pack('>2I5B',1,1,8,6,0,0,0))
        for raw in (b'\0'*100000, b'\0'*4, b'\5'+b'\0'*4):
            broken.append(valid[:8]+header+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
        for data in broken:
            with self.assertRaises((SceneError,zlib.error)):
                decode_png(data)


if __name__ == '__main__':
    unittest.main()
