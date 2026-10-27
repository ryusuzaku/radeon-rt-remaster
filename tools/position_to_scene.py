"""Convert one render group of an HL2 position-capture ledger into a renderable .rrscene.

The position ledgers carry, per accepted draw, the indexed corner positions, the vertex program's constants (c0, the
clip rows c4-c7, the model rows c58-c60) and the clip/model positions the program produced. This tool turns one
group of draws that share a camera into a v2 scene the DXR renderer admits, so a real title's geometry can go through
the transport. What it does and does not claim:

  * geometry only: no UVs, vertex colours, textures or materials were captured. Every draw gets a 1x1 grey texture,
    white vertex colours and zero UVs, so the result is relit grey geometry, not the game's look;
  * world space is whatever the vertex program's model rows produce (docs/HL2_POSITION_CONTRACT.md calls it unverified), so
    the scene carries default metadata and the provenance sidecar says so;
  * correctness is checked, not assumed: every vertex is projected through the scene's own D3D matrices and must land
    on the clip position the ledger recorded, and the model-output position must match too. A transposed or
    mis-composed matrix fails here, with no GPU involved.

Pure Python, standard library only. Output is exclusive-create: an existing file is never overwritten.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_io import encode_scene, decode_scene, SceneError  # noqa: E402

TEXTURE = bytes([176, 176, 176, 255])
CLEAR_COLOR = 0xff142850
WHITE = 0xffffffff
MAX_EXTENT = 4096
# The fixed-function state the DXR renderer admits (opaque, double-sided, Gouraud RGB, matched point/linear sampling).
# It mirrors the fixture in tests/verify_dxr.py, whose draws rrt_dxr renders.
RENDER = [0] * 34
for _index, _value in {1: 3, 2: 2, 7: 1, 10: 8, 16: 1, 18: 1, 21: 15, 22: 1, 25: 1, 26: 0xffffffff, 27: 0xffffffff, 31: 2, 32: 1, 33: 1}.items():
    RENDER[_index] = _value
TEXTURE_STATES = [4, 2, 0, 2, 2, 0, 0, 0]
SAMPLER = [1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0]
IDENTITY = [float(i % 5 == 0) for i in range(16)]


class ConversionError(ValueError):
    pass


def need(condition, message):
    if not condition: raise ConversionError(message)


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def inverse(matrix):
    work = [list(row) + [float(i == j) for j in range(4)] for i, row in enumerate(matrix)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda i: abs(work[i][column]))
        if abs(work[pivot][column]) < 1e-10: return None
        work[pivot], work[column] = work[column], work[pivot]
        scale = work[column][column]; work[column] = [x / scale for x in work[column]]
        for i in range(4):
            if i != column:
                scale = work[i][column]; work[i] = [x - scale * y for x, y in zip(work[i], work[column])]
    return [row[4:] for row in work]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transpose_flat(matrix):
    return [matrix[j][i] for i in range(4) for j in range(4)]


def row_vector_project(draw, point):
    """Transform (x, y, z, 1) as Direct3D does: a row vector times world, view and projection (row-major lists)."""
    v = [point[0], point[1], point[2], 1.0]
    for key in ('world', 'view', 'projection'):
        m = draw[key]; v = [sum(v[i] * m[i * 4 + j] for i in range(4)) for j in range(4)]
    return v


def constants_of(row):
    values = list(struct.iter_unpack('<4f', bytes.fromhex(row['constants'])))
    need(len(values) == 8, 'a draw needs the eight captured constant registers')
    return values


GROUP_TOLERANCE = 1e-4


def derived_view_projection(row):
    """clip rows x inverse(model) as a 4x4, or None when the draw is not affine-prepared or its model is singular."""
    c = constants_of(row)
    if not (c[0][0] == 0 and c[0][1] == 1): return None
    inv = inverse([list(r) for r in c[5:8]] + [[0.0, 0.0, 0.0, 1.0]])
    return None if inv is None else matmul([list(r) for r in c[1:5]], inv)


def same_camera(a, b, tolerance=GROUP_TOLERANCE):
    if a is None or b is None: return False
    scale = max(1.0, max(abs(x) for r in a for x in r))
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4)) <= tolerance * scale


def groups_of(rows, tolerance=GROUP_TOLERANCE):
    """Ledger records grouped into scenes: same device, reset epoch, present interval, target, viewport and render state, and the
    same camera. The camera is the derived view-projection (clip rows x inverse model), so draws with different model matrices share
    a scene when they share the view that was captured; a draw the derivation cannot handle is grouped by its raw clip rows and
    refused later with a reason. Groups come back in the order their first draw appears."""
    buckets = {}
    for position, row in enumerate(rows):
        timing = row.get('timing') or {}
        key = json.dumps([row.get('device'), timing.get('reset_epoch'), timing.get('present_interval'), row.get('target'), row['viewport'], row.get('render_state')],
                         sort_keys=True, separators=(',', ':'))
        buckets.setdefault(key, []).append((position, row))
    groups = []
    for members in buckets.values():
        clusters = []  # [camera or raw clip rows, first position, rows]
        for position, row in members:
            camera = derived_view_projection(row); raw = [list(r) for r in constants_of(row)[1:5]]
            for cluster in clusters:
                if (camera is not None and cluster[3] is not None and same_camera(cluster[0], camera, tolerance)) or (camera is None and cluster[3] is None and cluster[0] == raw):
                    cluster[2].append(row); break
            else:
                clusters.append([camera if camera is not None else raw, position, [row], camera])
        groups.extend((first, rows_) for _, first, rows_, _ in clusters)
    return [rows_ for _, rows_ in sorted(groups, key=lambda g: g[0])]


def corners(row):
    n = row['primitives'] * 3
    indices = struct.unpack('<' + 'H' * n, bytes.fromhex(row['indices']))
    positions = list(struct.iter_unpack('<3f', bytes.fromhex(row['positions'])))
    evaluated = list(struct.iter_unpack('<8f', bytes.fromhex(row['evaluated'])))
    need(len(positions) == n and len(evaluated) == n, 'position and evaluated records must have one entry per index')
    return indices, positions, evaluated


def build_scene(rows, max_extent=1280):
    """One group of ledger records (same camera) to (scene dict, provenance dict). Raises ConversionError."""
    need(rows, 'no draws to convert')
    need(1 <= max_extent <= MAX_EXTENT, f'max extent must be 1..{MAX_EXTENT}')
    viewport = struct.unpack('<4I2f', bytes.fromhex(rows[0]['viewport']))
    need(viewport[0] == 0 and viewport[1] == 0 and viewport[2] > 0 and viewport[3] > 0 and viewport[4] == 0 and viewport[5] == 1, 'only full-frame 0..1 viewports are supported')
    for row in rows: need(row['viewport'] == rows[0]['viewport'], 'draws in one scene must share a viewport')
    scale = min(1.0, max_extent / max(viewport[2], viewport[3]))
    width, height = max(1, round(viewport[2] * scale)), max(1, round(viewport[3] * scale))
    need(width <= MAX_EXTENT and height <= MAX_EXTENT, 'scene extent exceeds the format limit')

    prepared = []; reference = None; spread = 0.0
    for row in rows:
        c = constants_of(row)
        need(c[0][0] == 0 and c[0][1] == 1, f'draw {row["ordinal"]}: c0 is not the affine (0, 1) preparation, so q.w is not one')
        model = [list(r) for r in c[5:8]] + [[0.0, 0.0, 0.0, 1.0]]
        inv = inverse(model); need(inv is not None, f'draw {row["ordinal"]}: singular model matrix')
        clip = [list(r) for r in c[1:5]]
        view_projection = matmul(clip, inv)  # clip = view_projection * world, column-vector convention
        if reference is None: reference = view_projection
        spread = max(spread, max(abs(view_projection[i][j] - reference[i][j]) for i in range(4) for j in range(4)))
        prepared.append((row, model))
    shared = [[f32(x) for x in r] for r in reference]  # one bit-identical camera for every draw, as the renderer requires

    draws = []; clip_error = model_error = 0.0; triangles = 0
    for scene_ordinal, (row, model) in enumerate(prepared):
        indices, positions, evaluated = corners(row)
        unique = {}; vertices = []; faces = []
        for index, position, result in zip(indices, positions, evaluated):
            if index in unique:
                need(vertices[unique[index]][:3] == list(position), f'draw {row["ordinal"]}: vertex {index} repeated with different positions')
            else:
                unique[index] = len(vertices); vertices.append([position[0], position[1], position[2], WHITE, 0.0, 0.0])
            faces.append(unique[index])
        draw = dict(ordinal=scene_ordinal, texture_width=1, texture_height=1, world=[f32(x) for x in transpose_flat(model)], view=list(IDENTITY),
                    projection=[f32(x) for x in transpose_flat(shared)], viewport=[0, 0, width, height, 0.0, 1.0], scissor=[0, 0, width, height],
                    render=list(RENDER), texture_states=list(TEXTURE_STATES), sampler=list(SAMPLER), vertices=vertices, indices=faces, texture=TEXTURE)
        for corner, result in zip(faces, evaluated):  # the gate: through the scene's own matrices, in Direct3D's convention
            clip = row_vector_project(draw, vertices[corner][:3])
            scale_clip = max(1.0, max(abs(x) for x in result[:4])); clip_error = max(clip_error, max(abs(a - b) for a, b in zip(clip, result[:4])) / scale_clip)
            world = [sum(model[i][k] * (list(vertices[corner][:3]) + [1.0])[k] for k in range(4)) for i in range(3)]
            scale_model = max(1.0, max(abs(x) for x in result[4:7])); model_error = max(model_error, max(abs(a - b) for a, b in zip(world, result[4:7])) / scale_model)
        triangles += len(faces) // 3; draws.append(draw)
    need(clip_error <= 2e-4, f'projected clip positions differ from the ledger by {clip_error:.3g} (relative)')
    need(model_error <= 2e-4, f'model-output positions differ from the ledger by {model_error:.3g} (relative)')
    timing = rows[0].get('timing') or {}
    # Scene ordinals are the draws' positions (the format wants them increasing and below `attempted`); the ledger's own
    # ordinals are kept in the provenance.
    scene = dict(frame=int(timing.get('present_interval') or 0), width=width, height=height, clear_color=CLEAR_COLOR, attempted=len(draws), cleared=True,
                 complete=True, rejected=[], draws=draws)
    provenance = dict(
        draw_ordinals=[row['ordinal'] for row, _ in prepared], triangles=triangles, vertices=sum(len(d['vertices']) for d in draws), source_viewport=list(viewport[:4]),
        scene_extent=[width, height], extent_scale=scale, shared_camera_spread=spread, max_relative_clip_error=clip_error, max_relative_model_error=model_error,
        target=rows[0].get('target'), present_interval=timing.get('present_interval'), reset_epoch=timing.get('reset_epoch'),
        material='uniform 1x1 grey texture, white vertex colours, zero UVs: geometry only, nothing about the game\'s materials was captured',
        coordinate_status='model-output space of the captured vertex program; world-space meaning, units and handedness are unverified')
    return scene, provenance


def check_admissible(scene):
    """The rules rrt_dxr's Admit enforces, so a bad conversion fails here and not on the GPU."""
    need(scene['draws'] and len(scene['draws']) <= 1024 and not scene['rejected'], 'the renderer needs a complete scene of 1..1024 draws')
    first = scene['draws'][0]
    for d in scene['draws']:
        need(d['view'] == first['view'] and d['projection'] == first['projection'], 'the renderer needs one shared camera')
        need(d['viewport'] == [0, 0, scene['width'], scene['height'], 0.0, 1.0], 'the renderer needs a full-frame viewport')
        w = d['world']; need((w[3], w[7], w[11], w[15]) == (0.0, 0.0, 0.0, 1.0), 'the renderer needs affine world transforms')
        r = d['render']; need(not r[4] and not r[12] and r[7] == 1 and r[2] == 2 and r[21] == 15 and not r[28], 'the renderer needs opaque double-sided Gouraud RGB state')


def digest_of(path):
    data = Path(path).read_bytes()
    need(len(data) <= 16 * 1024 * 1024, 'ledger exceeds the 16 MiB read budget')
    return hashlib.sha256(data).hexdigest()


def write_outputs(scene, provenance, out):
    """Exclusive-create `scene.rrscene` and `provenance.json` in a new directory; returns the scene bytes."""
    check_admissible(scene)
    data = encode_scene(scene); decode_scene(data)
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    with (out / 'scene.rrscene').open('xb') as stream: stream.write(data)
    provenance = dict(provenance, scene_sha256=hashlib.sha256(data).hexdigest(), scene_bytes=len(data))
    with (out / 'provenance.json').open('x', encoding='utf-8') as stream: stream.write(json.dumps(provenance, indent=2, allow_nan=False) + '\n')
    return data


def convert_ledger(ledger, out, group=None, max_extent=1280):
    from inspect_position_capture import inspect
    ledger = Path(ledger).resolve(); digest = digest_of(ledger)
    report = inspect(ledger, include_records=True)
    need(digest == digest_of(ledger), 'ledger changed while it was being read')
    need(report.get('records'), 'the ledger has no accepted draws')
    groups = groups_of(report['records'])
    if group is None: group = max(range(len(groups)), key=lambda i: (len(groups[i]), -i))
    need(0 <= group < len(groups), f'group {group} does not exist; the ledger has {len(groups)}')
    scene, provenance = build_scene(groups[group], max_extent)
    provenance.update(ledger=str(ledger), ledger_sha256=digest, group=group, groups=[len(g) for g in groups])
    write_outputs(scene, provenance, out)
    return provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ledger', type=Path); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--group', type=int, help='render group index (default: the group with the most draws)')
    parser.add_argument('--max-extent', type=int, default=1280, help='longest scene side in pixels (default 1280)')
    args = parser.parse_args()
    try:
        result = convert_ledger(args.ledger, args.out, args.group, args.max_extent)
        print(json.dumps(dict(out=str(args.out.resolve()), group=result['group'], groups=result['groups'], draws=len(result['draw_ordinals']), triangles=result['triangles'],
                              extent=result['scene_extent'], max_relative_clip_error=result['max_relative_clip_error'], shared_camera_spread=result['shared_camera_spread'])))
    except (OSError, ValueError, KeyError, SceneError) as error:
        parser.exit(2, f'conversion rejected: {error}\n')
