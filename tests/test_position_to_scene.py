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


def test_grouping_by_derived_camera():
    # Draws with different model matrices have different raw clip rows but the same captured view: one scene, per-draw worlds.
    models = [model_matrix(0.4, (100.0, -50.0, 20.0)), model_matrix(-0.7, (-300.0, 10.0, 5.0)), model_matrix(1.9, (0.0, 0.0, -80.0))]
    rows = [row(10 + i, QUAD, INDICES, m) for i, m in enumerate(models)]
    assert len({r['constants'][32:288] for r in rows}) == 3, 'the raw clip rows differ, so the old grouping would split these'
    groups = p.groups_of(rows)
    assert [len(g) for g in groups] == [3]
    scene, provenance = p.build_scene(groups[0])
    p.check_admissible(scene)
    assert len({tuple(d['world']) for d in scene['draws']}) == 3 and len({tuple(d['projection']) for d in scene['draws']}) == 1
    assert provenance['shared_camera_spread'] < 1e-3 and provenance['max_relative_clip_error'] < 1e-5, provenance
    # A different view in the same interval stays apart, and so does a draw the derivation cannot handle.
    other = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 1.0, 10.0]]
    mixed = rows + [row(20, QUAD, INDICES, models[0], view_projection=other), row(21, QUAD, INDICES, models[0], c0=(0.0, 2.0, 2.0, 0.5))]
    sizes = [len(g) for g in p.groups_of(mixed)]
    assert sizes == [3, 1, 1], sizes
    assert [g[0]['ordinal'] for g in p.groups_of(mixed)] == [10, 20, 21], 'groups keep first-appearance order'
    # Near-identical cameras (float32 noise) are one group; a visibly different camera is not.
    noisy = [[v * (1 + 1e-7) for v in r] for r in VIEW_PROJECTION]
    assert len(p.groups_of([row(1, QUAD, INDICES, MODEL), row(2, QUAD, INDICES, MODEL, view_projection=noisy)])) == 1
    shifted = [r[:] for r in VIEW_PROJECTION]; shifted[0][3] += 5.0
    assert len(p.groups_of([row(1, QUAD, INDICES, MODEL), row(2, QUAD, INDICES, MODEL, view_projection=shifted)])) == 2


def flex_row(ordinal, positions, indices, model, flex, scale=0.75, view_projection=VIEW_PROJECTION, c0=(0.0, 1.0, 0.0, 0.0), recorded_flex=None):
    """A record of the second program: nine rows (c0, c3, c8-c11, c58-c60) and one flex value per corner (stride 0: the same
    one each time). The evaluated outputs fold the flex offset in, as the program does; `recorded_flex` lets a test record a
    different value than the one evaluated."""
    constants = struct.pack('<36f', *c0, scale, 0.0, 0.0, 0.0, *[x for r in view_projection for x in r], *[x for r in model[:3] for x in r])
    corners = [positions[i] for i in indices]
    drawn = [[c[j] + flex[j] * scale for j in range(3)] for c in corners]
    camera = p.matmul(view_projection, model)
    evaluated = b''.join(struct.pack('<4f', *apply(camera, d)) + struct.pack('<3f', *apply(model, d)[:3]) + struct.pack('<f', 1.0) for d in drawn)
    record = recorded_flex or flex
    return dict(ordinal=ordinal, primitives=len(indices) // 3, indices=struct.pack('<%dH' % len(indices), *indices).hex(),
                positions=b''.join(struct.pack('<3f', *c) for c in corners).hex(), evaluated=evaluated.hex(), constants=constants.hex(),
                constant_rows=list(p.FLEX_ROWS), flex=dict(offset=0, stride=0, vb_size=28, values=struct.pack('<4f', *record, 1.0).hex() * len(corners)),
                viewport=struct.pack('<4I2f', 0, 0, 5120, 1440, 0.0, 1.0).hex(), target=[5120, 1440, 21, 0], device=2,
                timing=dict(reset_epoch=0, present_interval=7, indexed_draw=ordinal), render_state=None)


def test_flex_program():
    flex = (6.0, -4.0, 9.0)
    rows = [row(30, QUAD, INDICES, MODEL), flex_row(31, QUAD, INDICES, model_matrix(-0.7, (-300.0, 10.0, 5.0)), flex)]
    groups = p.groups_of(rows)
    assert [len(g) for g in groups] == [2], 'a flex draw under the same view joins the first program\'s scene'
    scene, provenance = p.build_scene(groups[0])
    p.check_admissible(scene)
    assert provenance['programs'] == dict(pinned=1, flex=1, skin=0) and provenance['max_relative_clip_error'] < 1e-5, provenance
    stored = scene['draws'][1]['vertices'][0][:3]
    assert all(abs(a - (b + f * 0.75)) < 1e-4 for a, b, f in zip(stored, QUAD[0], flex)), ('the flex offset is folded into the vertex', stored)
    # The fold is necessary: recording a zero flex value while the program used a real one must fail the gate.
    raises(lambda: p.build_scene([flex_row(32, QUAD, INDICES, MODEL, flex, recorded_flex=(0.0, 0.0, 0.0))]), 'projected clip positions differ')
    # A zero scale makes the flex value irrelevant, so the same mismatch is then harmless.
    p.build_scene([flex_row(33, QUAD, INDICES, MODEL, flex, scale=0.0, recorded_flex=(0.0, 0.0, 0.0))])
    raises(lambda: p.build_scene([flex_row(34, QUAD, INDICES, MODEL, flex, c0=(0.0, 0.5, 0.0, 0.0))]), 'c0.y is not one')


def skin_row(ordinal, models, indices, view_projection=VIEW_PROJECTION, c0=(0.0, 1.0, 2.0, 0.5), clip_offset=0.0):
    """A record of the skinned program as the converter sees it: six rows (c0, c3, c8-c11) and per-corner evaluated outputs. The
    blend itself is the reader's to check; here every corner simply has its own model position, as skinned vertices do."""
    constants = struct.pack('<24f', *c0, 0.5, 0.0, 0.0, 0.0, *[x for r in view_projection for x in r])
    corners = [models[i] for i in indices]
    evaluated = b''.join(struct.pack('<4f', *[v + clip_offset for v in apply(view_projection, m)]) + struct.pack('<3f', *m) + struct.pack('<f', 1.0) for m in corners)
    return dict(ordinal=ordinal, primitives=len(indices) // 3, indices=struct.pack('<%dH' % len(indices), *indices).hex(),
                positions=b''.join(struct.pack('<3f', 0.0, 0.0, 0.0) for _ in corners).hex(), evaluated=evaluated.hex(), constants=constants.hex(),
                constant_rows=list(p.SKIN_ROWS), viewport=struct.pack('<4I2f', 0, 0, 5120, 1440, 0.0, 1.0).hex(), target=[5120, 1440, 21, 0], device=2,
                timing=dict(reset_epoch=0, present_interval=7, indexed_draw=ordinal), render_state=None)


def test_skinned_program():
    skinned = [(10.0, -20.0, 130.0), (60.0, -25.0, 140.0), (35.0, 40.0, 160.0)]
    rows = [row(40, QUAD, INDICES, MODEL), skin_row(41, skinned, [0, 1, 2])]
    groups = p.groups_of(rows)
    assert [len(g) for g in groups] == [2], 'a skinned draw under the same view joins the scene'
    scene, provenance = p.build_scene(groups[0])
    p.check_admissible(scene)
    assert provenance['programs'] == dict(pinned=1, flex=0, skin=1) and provenance['max_relative_clip_error'] < 1e-5, provenance
    draw = scene['draws'][1]
    assert draw['world'] == [float(i % 5 == 0) for i in range(16)] and [v[:3] for v in draw['vertices']] == [list(m) for m in skinned], draw['vertices']
    # The gate still decides: a recorded clip position the model position cannot produce under the camera is refused.
    raises(lambda: p.build_scene([skin_row(42, skinned, [0, 1, 2], clip_offset=0.5)]), 'projected clip positions differ')
    raises(lambda: p.build_scene([skin_row(43, skinned, [0, 1, 2], c0=(0.0, 0.5, 2.0, 0.5))]), 'c0.y is not one')


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
    print(f'PASS position_to_scene: {len(tests)} synthetic-ledger checks (round trip and gate, wrong convention, dedup, rejections, grouping and extent, second and skinned programs, outputs)')
