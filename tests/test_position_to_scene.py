"""Synthetic-ledger checks for tools/position_to_scene.py. Pure Python, no GPU, no game content.

The synthetic records follow the position ledger's layout (hex indices, per-index corner positions, per-index
evaluated clip/model positions, the 128 bytes of vertex-program constants). The expectations are computed here with
independent arithmetic and deliberately asymmetric matrices, so a transposed convention, a mis-composed camera or a
dropped model matrix fails.
"""
import math
from pathlib import Path
import struct
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import position_to_scene as p
from scene_io import decode_scene

C0 = (0.0, 1.0, 2.0, 0.5)


def rotation_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def model_matrix(angle, shift):
    m = rotation_z(angle); m[0][3], m[1][3], m[2][3] = shift
    m[0][0] *= 1.5  # non-uniform scale: a missing or transposed model matrix cannot hide
    return m


VIEW_PROJECTION = [[0.9, 0.1, 0.0, -3.0], [0.0, 1.6, 0.2, 5.0], [0.05, 0.0, 1.002, -2.0], [0.0, 0.0, 1.0, 40.0]]


def apply(matrix, point):
    v = list(point) + [1.0]
    return [sum(matrix[i][k] * v[k] for k in range(4)) for i in range(4)]


def row(ordinal, positions, indices, model, view_projection=VIEW_PROJECTION, viewport=(0, 0, 5120, 1440, 0.0, 1.0), interval=7, c0=C0, evaluated_view_projection=None):
    clip_matrix = p.matmul(view_projection, model)
    constants = struct.pack('<32f', *c0, *[x for r in clip_matrix for x in r], *[x for r in model[:3] for x in r])
    corners = [positions[i] for i in indices]
    camera = p.matmul(evaluated_view_projection or view_projection, model)
    evaluated = b''.join(struct.pack('<4f', *apply(camera, c)) + struct.pack('<3f', *apply(model, c)[:3]) + struct.pack('<f', 1.0) for c in corners)
    return dict(ordinal=ordinal, primitives=len(indices) // 3, indices=struct.pack('<%dH' % len(indices), *indices).hex(),
                positions=b''.join(struct.pack('<3f', *c) for c in corners).hex(), evaluated=evaluated.hex(), constants=constants.hex(),
                viewport=struct.pack('<4I2f', *viewport).hex(), target=[viewport[2], viewport[3], 21, 0], device=2,
                timing=dict(reset_epoch=0, present_interval=interval, indexed_draw=ordinal), render_state=None)


QUAD = [(-40.0, -30.0, 120.0), (40.0, -30.0, 120.0), (40.0, 30.0, 150.0), (-40.0, 30.0, 150.0)]
INDICES = [0, 1, 2, 0, 2, 3]
MODEL = model_matrix(0.4, (100.0, -50.0, 20.0))


def raises(function, text):
    try: function()
    except p.ConversionError as error:
        assert text in str(error), f'expected "{text}" in "{error}"'
    else: raise AssertionError(f'expected a ConversionError mentioning "{text}"')


def test_round_trip_and_gate():
    rows = [row(297, QUAD, INDICES, MODEL), row(299, QUAD, [2, 1, 0], model_matrix(-0.7, (-300.0, 10.0, 5.0)))]
    scene, provenance = p.build_scene(rows)
    p.check_admissible(scene)
    assert provenance['max_relative_clip_error'] < 1e-5 and provenance['max_relative_model_error'] < 1e-5, provenance
    data = p.encode_scene(scene); decoded = decode_scene(data)
    assert len(decoded['draws']) == 2 and sum(len(d['indices']) for d in decoded['draws']) == 9
    first = scene['draws'][0]
    assert all(d['view'] == first['view'] and d['projection'] == first['projection'] for d in scene['draws']), 'camera must be bit-identical'
    # An independent projection through the stored row-vector matrices lands on the captured clip position.
    for r, d in zip(rows, scene['draws']):
        for corner, expected in zip(d['indices'], struct.iter_unpack('<8f', bytes.fromhex(r['evaluated']))):
            clip = p.row_vector_project(d, d['vertices'][corner][:3])
            assert max(abs(a - b) for a, b in zip(clip, expected[:4])) <= 1e-4 * max(1.0, max(abs(x) for x in expected[:4])), (clip, expected[:4])
    assert provenance['draw_ordinals'] == [297, 299] and [d['ordinal'] for d in scene['draws']] == [0, 1] and scene['attempted'] == 2


def test_gate_catches_a_wrong_convention():
    wrong = [list(col) for col in zip(*VIEW_PROJECTION)]  # the ledger says "transposed camera": the scene cannot reproduce it
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, MODEL, evaluated_view_projection=wrong)]), 'projected clip positions differ')


def test_dedup_and_consistency():
    scene, _ = p.build_scene([row(1, QUAD, [0, 1, 2, 0, 2, 3], MODEL)])
    assert len(scene['draws'][0]['vertices']) == 4 and scene['draws'][0]['indices'] == [0, 1, 2, 0, 2, 3]
    bad = row(1, QUAD, INDICES, MODEL)
    corners = bytearray(bytes.fromhex(bad['positions'])); corners[3 * 12:3 * 12 + 4] = struct.pack('<f', 999.0)  # corner 3 reuses index 0 with new bytes
    bad['positions'] = corners.hex()
    raises(lambda: p.build_scene([bad]), 'repeated with different positions')


def test_rejections():
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, MODEL, c0=(0.0, 2.0, 2.0, 0.5))]), 'affine')
    singular = model_matrix(0.1, (0, 0, 0)); singular[0][0] = 0.0; singular[1][1] = 0.0; singular[0][1] = 0.0; singular[1][0] = 0.0
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, singular)]), 'singular')
    raises(lambda: p.build_scene([]), 'no draws')
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, MODEL, viewport=(10, 0, 5120, 1440, 0.0, 1.0))]), 'full-frame')
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, MODEL, viewport=(0, 0, 5120, 1440, 0.0, 0.5))]), 'full-frame')
    raises(lambda: p.build_scene([row(1, QUAD, INDICES, MODEL)], max_extent=5000), 'max extent')
    short = row(1, QUAD, INDICES, MODEL); short['evaluated'] = short['evaluated'][:-64]
    raises(lambda: p.build_scene([short]), 'one entry per index')


def test_grouping_and_extent():
    other = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 1.0, 10.0]]
    rows = [row(1, QUAD, INDICES, MODEL), row(2, QUAD, INDICES, MODEL, interval=8, view_projection=other), row(3, QUAD, INDICES, MODEL)]
    groups = p.groups_of(rows)
    assert [len(g) for g in groups] == [2, 1], 'draws with equal clip rows, interval and target share a group'
    scene, provenance = p.build_scene(groups[0])
    assert (scene['width'], scene['height']) == (1280, 360) and provenance['extent_scale'] == 0.25
    assert all(d['viewport'] == [0, 0, 1280, 360, 0.0, 1.0] and d['scissor'] == [0, 0, 1280, 360] for d in scene['draws'])
    small, meta = p.build_scene(groups[0], max_extent=100)
    assert (small['width'], small['height']) == (100, 28) and meta['source_viewport'] == [0, 0, 5120, 1440]
    native, _ = p.build_scene([row(1, QUAD, INDICES, MODEL, viewport=(0, 0, 640, 480, 0.0, 1.0))])
    assert (native['width'], native['height']) == (640, 480), 'a small capture is not enlarged'


def test_outputs_are_exclusive_and_checked():
    scene, provenance = p.build_scene([row(1, QUAD, INDICES, MODEL)])
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / 'scene'
        data = p.write_outputs(scene, provenance, out)
        assert (out / 'scene.rrscene').read_bytes() == data and b'RRTSCN1' in data[:8]
        meta = __import__('json').loads((out / 'provenance.json').read_text(encoding='utf-8'))
        assert meta['scene_bytes'] == len(data) and len(meta['scene_sha256']) == 64 and 'unverified' in meta['coordinate_status']
        try: p.write_outputs(scene, provenance, out)
        except FileExistsError: pass
        else: raise AssertionError('existing output was overwritten')
    broken = {**scene, 'draws': [dict(scene['draws'][0], render=[1] * 34)]}
    raises(lambda: p.check_admissible(broken), 'opaque double-sided')
    shifted = {**scene, 'draws': [dict(scene['draws'][0]), dict(scene['draws'][0], projection=[x + 1 for x in scene['draws'][0]['projection']])]}
    raises(lambda: p.check_admissible(shifted), 'shared camera')


if __name__ == '__main__':
    tests = [value for name, value in sorted(globals().items()) if name.startswith('test_')]
    for test in tests: test()
    print(f'PASS position_to_scene: {len(tests)} synthetic-ledger checks (round trip and gate, wrong convention, dedup, rejections, grouping and extent, outputs)')
