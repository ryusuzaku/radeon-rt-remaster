"""Bounded reader for the little-endian RRTSCN1 scene format (no GPU needed)."""
from hashlib import sha256
from pathlib import Path
import math
import struct

MAX_BYTES = 64 * 1024 * 1024
MAX_DRAWS = 4096
STATE_BYTES = 452
REASONS = ('invalid', 'programmable_shader', 'unsupported_topology_or_fvf',
           'unsupported_fixed_function_state', 'missing_or_invalid_resource_payload',
           'unsupported_render_target', 'capture_budget_exceeded',
           'state_query_or_capture_failure', 'unsupported_or_missing_clear',
           'unsupported_frame_operation', 'multiple_devices')


class SceneError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SceneError(message)


def load_scene(path):
    with Path(path).open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    return decode_scene(data)


def decode_scene(data):
    require(76 <= len(data) <= MAX_BYTES, 'invalid scene file size')
    require(sha256(data[:-32]).digest() == data[-32:], 'scene checksum mismatch')
    data = memoryview(data)[:-32]
    cursor = 0

    def take(size):
        nonlocal cursor
        require(0 <= size <= len(data) - cursor, 'truncated scene')
        result = data[cursor:cursor + size]
        cursor += size
        return result

    def unpack(fmt):
        return struct.unpack('<' + fmt, take(struct.calcsize('<' + fmt)))

    require(bytes(take(8)) == b'RRTSCN1\0', 'invalid scene magic')
    version, frame, width, height, clear, attempted, cleared, draws, rejects = unpack('9I')
    require(version == 1, 'unsupported scene version')
    require(0 < width <= 4096 and 0 < height <= 4096, 'invalid scene dimensions')
    require(cleared in (0, 1) and (cleared or rejects), 'invalid clear flag or missing clear')
    require(draws <= MAX_DRAWS and rejects <= MAX_DRAWS + 1, 'too many scene records')
    require(rejects or attempted == draws, 'complete scene omits draws')
    result = dict(version=version, frame=frame, width=width, height=height,
                  clear_color=clear, attempted=attempted, cleared=bool(cleared),
                  complete=rejects == 0, draws=[], rejected=[])
    for _ in range(rejects):
        ordinal, reason = unpack('2I')
        require(0 < reason < len(REASONS), 'invalid rejection reason')
        result['rejected'].append(dict(ordinal=ordinal, reason=REASONS[reason]))
    previous = -1
    for _ in range(draws):
        ordinal, tw, th, nv, ni = unpack('5I')
        require(previous < ordinal < attempted, 'invalid draw ordinal')
        previous = ordinal
        require(0 < nv <= 500000 and 0 < ni <= 1500000 and ni % 3 == 0, 'invalid geometry counts')
        require(0 < tw <= 2048 and 0 < th <= 2048, 'invalid texture dimensions')
        mesh_id, texture_id, material_id = (bytes(take(32)) for _ in range(3))
        state = bytes(take(STATE_BYTES))
        matrices = struct.unpack_from('<48f', state)
        require(all(math.isfinite(x) for x in matrices), 'nonfinite transform')
        viewport = struct.unpack_from('<4I2f', state, 192)
        x, y, w, h, zmin, zmax = viewport
        require(w > 0 and h > 0 and x + w <= width and y + h <= height and
                math.isfinite(zmin) and math.isfinite(zmax) and 0 <= zmin <= zmax <= 1,
                'invalid viewport')
        vertex_bytes, index_bytes, texture = bytes(take(nv * 24)), bytes(take(ni * 4)), bytes(take(tw * th * 4))
        vertices = list(struct.iter_unpack('<3fI2f', vertex_bytes))
        indices = list(struct.unpack('<' + str(ni) + 'I', index_bytes))
        require(all(math.isfinite(v[k]) for v in vertices for k in (0, 1, 2, 4, 5)), 'nonfinite vertex')
        require(all(i < nv for i in indices), 'index outside vertex array')
        require(sha256(struct.pack('<2I', nv, ni) + vertex_bytes + index_bytes).digest() == mesh_id,
                'mesh hash mismatch')
        require(sha256(struct.pack('<2I', tw, th) + texture).digest() == texture_id, 'texture hash mismatch')
        require(sha256(texture_id + state[232:]).digest() == material_id, 'material hash mismatch')
        render = struct.unpack_from('<34I', state, 232)
        texture_states = struct.unpack_from('<8I', state, 368)
        sampler = struct.unpack_from('<13I', state, 400)
        require(all(render[i] == 0 for i in (0, 13, 14, 15, 17, 19, 20)) and render[1] == 3,
                'scene uses unsupported render state')
        require(texture_states[:5] == (4, 2, 0, 2, 2) and texture_states[6:] == (0, 0) and sampler[6] == sampler[8] == 0,
                'scene uses unsupported texture state')
        result['draws'].append(dict(ordinal=ordinal, texture_width=tw, texture_height=th,
            mesh_id=mesh_id.hex(), texture_id=texture_id.hex(), material_id=material_id.hex(),
            world=matrices[:16], view=matrices[16:32], projection=matrices[32:], viewport=viewport,
            scissor=struct.unpack_from('<4i', state, 216), render=render,
            texture_states=texture_states, sampler=sampler,
            vertices=vertices, indices=indices, texture=texture))
    require(cursor == len(data), 'trailing scene data')
    return result


def encode_scene(scene):
    """Re-identify and validate before publishing bytes; never mutate the input."""
    data = bytearray(b'RRTSCN1\0')
    data.extend(struct.pack('<9I', 1, scene['frame'], scene['width'], scene['height'],
        scene['clear_color'], scene['attempted'], int(scene['cleared']), len(scene['draws']), len(scene['rejected'])))
    for rejection in scene['rejected']:
        data.extend(struct.pack('<2I', rejection['ordinal'], REASONS.index(rejection['reason'])))
    for draw in scene['draws']:
        nv, ni = len(draw['vertices']), len(draw['indices'])
        require(0 < nv <= 500000 and 0 < ni <= 1500000 and ni % 3 == 0, 'invalid geometry counts')
        require(len(data) + 568 + nv*24 + ni*4 + len(draw['texture']) + 32 <= MAX_BYTES, 'scene byte budget exceeded')
        vertices = b''.join(struct.pack('<3fI2f', *v) for v in draw['vertices'])
        indices = struct.pack('<' + str(ni) + 'I', *draw['indices'])
        texture = draw['texture']
        state = (struct.pack('<48f', *draw['world'], *draw['view'], *draw['projection']) +
                 struct.pack('<4I2f', *draw['viewport']) + struct.pack('<4i', *draw['scissor']) +
                 struct.pack('<34I8I13I', *draw['render'], *draw['texture_states'], *draw['sampler']))
        mesh_id = sha256(struct.pack('<2I', nv, ni) + vertices + indices).digest()
        texture_id = sha256(struct.pack('<2I', draw['texture_width'], draw['texture_height']) + texture).digest()
        material_id = sha256(texture_id + state[232:]).digest()
        data.extend(struct.pack('<5I', draw['ordinal'], draw['texture_width'], draw['texture_height'], nv, ni))
        data.extend(mesh_id + texture_id + material_id + state + vertices + indices + texture)
    require(len(data) + 32 <= MAX_BYTES, 'scene byte budget exceeded')
    data.extend(sha256(data).digest())
    decode_scene(data)  # Same semantic checks as the reader, including finite float32 values.
    return bytes(data)
