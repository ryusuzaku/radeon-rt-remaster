"""CPU-only strict authoring and stable-target tests."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from verify_dxr import fixture, encode_scene, ROOT
from material_inputs import compile_materials
from mod_scene import strict_json


class MaterialInputsTests(unittest.TestCase):
    def setUp(self):
        self.scene = fixture()
        self.entry = dict(target=self.scene['draws'][0]['material_id'])
        self.value = dict(schema='rrt-materials', version=1, materials=[self.entry])

    def test_canonical_binary(self):
        self.value['materials'].append(dict(target=self.scene['draws'][1]['material_id']))
        raw = compile_materials(self.value, self.scene)
        self.value['materials'].reverse()
        self.assertEqual(raw, compile_materials(self.value, self.scene))
        self.assertEqual(len(raw), 176)
        self.assertEqual(raw[:8], b'RRTMAT1\0')
        self.assertEqual(raw[-32:], sha256(raw[:-32]).digest())

    def test_rejected_json(self):
        for raw in ('{"version":1,"version":1}', '{"x":NaN}', '{"x":Infinity}', '{'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_rejected_values(self):
        entries = [dict(self.entry, roughness=x) for x in (0, .049, 1.01, True, '1', float('nan'))]
        entries += [dict(self.entry, metallic=x) for x in (-1, 2, False, float('inf'))]
        entries += [dict(self.entry, base_color=x) for x in ([1, 1], [1, -1, 1], [1, 2, 1], [True, 1, 1], 'rgb')]
        entries += [dict(self.entry, emissive=x) for x in ([33, 0, 0], [-1, 0, 0], [0, float('nan'), 0])]
        entries += [dict(self.entry, unknown=1), dict(target='0'*64), dict(target=True)]
        for entry in entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                compile_materials(dict(self.value, materials=[entry]), self.scene)
        for value in (dict(self.value, version=True), dict(self.value, version=2),
                      dict(self.value, extra=0), dict(self.value, materials={}),
                      dict(self.value, materials=[self.entry]*2), dict(self.value, materials=[self.entry]*4097)):
            with self.subTest(value=str(value)[:100]), self.assertRaises(ValueError):
                compile_materials(value, self.scene)
        partial = copy.deepcopy(self.scene); partial['complete'] = False
        with self.assertRaises(ValueError):
            compile_materials(self.value, partial)

    def test_limits_and_empty(self):
        for roughness in (.05, 1):
            compile_materials(dict(self.value, materials=[dict(self.entry, roughness=roughness,
                              metallic=1, emissive=[32, 0, 32], base_color=[0, 1, 0])]), self.scene)
        self.assertEqual(len(compile_materials(dict(self.value, materials=[]), self.scene)), 48)

    def test_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='rrt-materials-') as directory:
            folder = Path(directory)
            scene, authoring, binary = folder/'scene.rrscene', folder/'materials.json', folder/'materials.rrmat'
            scene.write_bytes(encode_scene(self.scene))
            def run(*args):
                return subprocess.run([sys.executable, str(ROOT/'tools/material_inputs.py'), *map(str, args)], capture_output=True, timeout=10)
            self.assertEqual(run('template', scene, '--output', authoring).returncode, 0)
            value = json.loads(authoring.read_text())
            self.assertEqual(len(value['materials']), 2)
            self.assertEqual(run('compile', scene, '--input', authoring, '--output', binary).returncode, 0)
            expected = binary.read_bytes()
            self.assertEqual(expected, compile_materials(value, self.scene))
            self.assertNotEqual(run('compile', scene, '--input', authoring, '--output', binary).returncode, 0)
            self.assertEqual(binary.read_bytes(), expected)
            self.assertNotEqual(run('template', scene, '--output', scene).returncode, 0)
            self.assertEqual(scene.read_bytes(), encode_scene(self.scene))


if __name__ == '__main__':
    unittest.main()
