"""Ledger checks for draws captured through the vs_2_0 interpreter (docs/VS_INTERPRETER.md).

A record holds the program, its declaration, the raw bytes of every input its position slice reads, the float registers it read
(static, relative and camera) and one clip position per corner. This module re-derives all of it with the independent Python
interpreter in vs_interpreter.py: the program must be on the admitted list, its inputs must be exactly the slice's, each input must
sit inside its recorded buffer, the recorded registers must be exactly the ones the vertices read plus the camera, and every clip
component must match within the float32 allowance.
"""
import hashlib
import json
import math
import struct
from pathlib import Path

import vs_interpreter as vi

LIST = Path(__file__).resolve().parents[1] / 'docs' / 'schemas' / 'interpreted-vertex-programs.json'
ADMITTED = {p['sha256'] for p in json.loads(LIST.read_text(encoding='utf-8'))['programs']}


def need(ok, message):
    if not ok: raise ValueError(message)


def blob(record, key, size):
    value = record.get(key); need(isinstance(value, str) and len(value) == size * 2, 'blob length: ' + key)
    return bytes.fromhex(value)


def validate(row, version, selection, indices):
    """Validate one interpreted record whose index list has already been decoded; returns the number of corners."""
    need(version < 11, 'interpreted programs have no material contract')
    for key in ('positions', 'evaluated', 'flex', 'bones', 'blend', 'constant_rows'):
        need(key not in row, 'interpreted records carry clip positions only')
    shader = row.get('shader'); need(isinstance(shader, str) and 16 <= len(shader) <= 32768 and len(shader) % 8 == 0, 'program identity')
    code = bytes.fromhex(shader); need(hashlib.sha256(code).hexdigest() in ADMITTED, 'program identity')
    try:
        program = vi.analyse(list(struct.unpack('<%dI' % (len(code) // 4), code)))
    except vi.Refused as error:
        raise ValueError(f'admitted program refused by the reader: {error}')
    declaration = row.get('declaration'); need(isinstance(declaration, str) and 16 <= len(declaration) <= 1040 and len(declaration) % 16 == 0, 'declaration')
    elements = list(struct.iter_unpack('<HHBBBB', bytes.fromhex(declaration))); need(elements[-1] == (255, 0, 17, 0, 0, 0), 'declaration terminator')
    interpreted = row.get('interpreted'); need(isinstance(interpreted, dict) and set(interpreted) == {'constants', 'camera', 'inputs'}, 'interpreted metadata')
    recorded = interpreted['inputs']; need(isinstance(recorded, list) and len(recorded) == len(program['inputs']), 'interpreted inputs differ from the position slice')
    corners = len(indices)
    inputs = []
    for want, got in zip(program['inputs'], recorded):
        keys = {'register', 'usage', 'usage_index', 'stream', 'element_offset', 'type', 'stream_offset', 'stride', 'vb_size', 'values'}
        need(isinstance(got, dict) and set(got) == keys, 'interpreted input metadata')
        need((got['register'], got['usage'], got['usage_index']) == (want['reg'], want['usage'], want['usage_index']), 'interpreted inputs differ from the position slice')
        matching = [e for e in elements[:-1] if e[4:] == (want['usage'], want['usage_index'])]
        need(len(matching) == 1 and matching[0][:3] == (got['stream'], got['element_offset'], got['type']) and matching[0][3] == 0, 'interpreted input declaration')
        need(got['type'] in vi.INPUT_SIZE, 'unsupported input type')
        size = vi.INPUT_SIZE[got['type']]
        need(all(type(got[k]) is int and 0 <= got[k] < 2 ** 32 for k in ('stream_offset', 'stride', 'vb_size')) and got['stride'] <= 256 and got['vb_size'] <= 16 * 1024 * 1024, 'interpreted stream layout')
        need(got['stride'] == 0 or got['element_offset'] + size <= got['stride'], 'interpreted stream layout')
        inputs.append((got, size, blob(got, 'values', corners * size)))
    constants = interpreted['constants']; need(isinstance(constants, dict) and set(constants) == {'registers', 'values'}, 'interpreted constants')
    registers = constants['registers']; need(isinstance(registers, list) and all(type(r) is int and 0 <= r < 256 for r in registers) and registers == sorted(set(registers)), 'interpreted constant registers')
    values = struct.unpack('<%df' % (4 * len(registers)), blob(constants, 'values', 16 * len(registers)))
    table = {r: values[i * 4:i * 4 + 4] for i, r in enumerate(registers)}
    need(all(map(math.isfinite, values)), 'nonfinite constants')
    camera = interpreted['camera']; expected_camera = set()
    if camera is not None:
        named = program['camera']
        if 'view_projection' in camera:
            need(camera == {'view_projection': named.get('view_projection')}, 'camera differs from the program constant table'); expected_camera = set(range(camera['view_projection'], camera['view_projection'] + 4))
        else:
            need(camera == {'model_view_projection': named.get('model_view_projection'), 'model': named.get('model')} and 'view_projection' not in named, 'camera differs from the program constant table')
            expected_camera = set(range(camera['model_view_projection'], camera['model_view_projection'] + 4)) | set(range(camera['model'], camera['model'] + 3))
    clips = list(struct.iter_unpack('<4f', blob(row, 'clip', corners * 16)))
    read = set(program['constants']) | expected_camera
    for corner, (index, clip) in enumerate(zip(indices, clips)):
        vertex = index + row['base']; need(vertex >= 0, 'negative vertex')
        state = {}
        for got, size, raw in inputs:
            need(got['stream_offset'] + vertex * got['stride'] + got['element_offset'] + size <= got['vb_size'], 'interpreted input buffer range')
            state[got['register']] = vi.convert(got['type'], raw[corner * size:(corner + 1) * size])
        need(all(math.isfinite(v) for v, _ in [(x, 0) for got, _, _ in inputs for x in state[got['register']][0]]), 'nonfinite input')
        try:
            position, magnitude, reads = vi.evaluate(program, state, lambda r: table.get(r))
        except vi.Refused as error:
            raise ValueError(f'interpreted vertex refused: {error}')
        need(all(map(math.isfinite, clip)), 'nonfinite clip position')
        need(vi.matches(clip, position, magnitude), 'position calculation mismatch')
        read.update(reads)
    need(set(registers) == read, 'recorded constants differ from the registers the vertices read')
    return corners
