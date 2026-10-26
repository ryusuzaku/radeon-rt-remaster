"""Contract: scene metadata is declared, not guessed, and v1 keeps its meaning.

The .rrscene v2 header adds units, scale, up-axis and handedness. The position
ledger's v20 header carries the same four values. This test exercises both
readers directly:

  * a v2 scene round-trips the metadata and rejects impossible values;
  * a v1 scene is still readable and yields the documented defaults without
    changing its draws;
  * the glTF exporter follows the declared handedness/up-axis instead of assuming;
  * a v1 or v19 ledger reports the same defaults, while v20 must declare the
    object and may not carry it on an older version.
"""
import json
from hashlib import sha256
from pathlib import Path
import struct
import sys

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

from scene_io import DEFAULT_METADATA, SceneError, decode_scene, encode_scene, require_metadata
from export_gltf import export
from inspect_position_capture import inspect_bytes


def scene_with_one_draw():
    state = bytearray(452)
    struct.pack_into('<4I2f', state, 192, 0, 0, 16, 16, 0.0, 1.0)
    struct.pack_into('<I', state, 232 + 4, 3)  # fill mode = D3DFILL_SOLID
    struct.pack_into('<8I', state, 368, 4, 2, 0, 2, 2, 0, 0, 0)
    vertices = [(-1.0, -1.0, 0.0, 0xffffffff, 0.0, 0.0),
                (1.0, -1.0, 0.0, 0xffffffff, 1.0, 0.0),
                (0.0, 1.0, 0.0, 0xffffffff, 0.5, 1.0)]
    identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    draw = dict(ordinal=0, texture_width=4, texture_height=4,
                world=identity, view=identity, projection=identity,
                viewport=[0, 0, 16, 16, 0.0, 1.0], scissor=[0, 0, 16, 16],
                render=[0] * 34, texture_states=[0] * 8, sampler=[0] * 13,
                vertices=vertices, indices=[0, 1, 2], texture=bytes(4 * 4 * 4))
    draw['render'][1] = 3
    draw['texture_states'] = [4, 2, 0, 2, 2, 0, 0, 0]
    return dict(frame=0, width=16, height=16, clear_color=0xff000000,
                attempted=1, cleared=True, complete=True, rejected=[], draws=[draw])


def ledger(version, **extra):
    header = {'kind': 'header', 'schema': 'rrt-position-capture', 'version': version}
    if version >= 3:
        header.update(session='0' * 32,
                      sampling='bounded-per-present-interval' if version >= 5 else 'one-per-present-interval')
    if version >= 5:
        header['limits'] = {'per_interval': 4, 'total': 16}
    if version >= 4:
        header['selection'] = {'any_target': True, 'min_primitives': 1}
    header.update(extra)
    return (json.dumps(header, separators=(',', ':')) + '\n').encode()


def must_reject(action, message):
    try:
        action()
    except (SceneError, ValueError):
        return
    raise AssertionError(message)


def main():
    # --- the binary scene header -------------------------------------------------
    base = scene_with_one_draw()
    v2 = encode_scene(base)
    decoded = decode_scene(v2)
    assert decoded['version'] == 2, decoded['version']
    assert decoded['metadata'] == DEFAULT_METADATA, decoded['metadata']
    assert len(decoded['draws']) == 1 and decoded['draws'][0]['indices'] == [0, 1, 2]

    # Convert the same bytes to a v1 header by dropping the 16-byte metadata block
    # and restoring the old version number. The draw payload must decode identically.
    body = bytearray(v2[:-32])
    body[8:12] = struct.pack('<I', 1)
    del body[44:60]
    v1 = bytes(body) + sha256(body).digest()
    legacy = decode_scene(v1)
    assert legacy['version'] == 1 and legacy['metadata'] == DEFAULT_METADATA
    assert legacy['draws'] == decoded['draws'], 'v1 loading changed the draw payload'

    custom = dict(units='centimetre', scale=0.01, up_axis='+Z', handedness='right')
    round_trip = decode_scene(encode_scene(dict(base, metadata=custom)))
    assert round_trip['metadata']['units'] == 'centimetre'
    assert round_trip['metadata']['up_axis'] == '+Z'
    assert round_trip['metadata']['handedness'] == 'right'
    assert abs(round_trip['metadata']['scale'] - 0.01) < 1e-9

    for bad in (dict(units='unitless', scale=2.0, up_axis='+Y', handedness='left'),
                dict(units='furlong', scale=1.0, up_axis='+Y', handedness='left'),
                dict(units='metre', scale=0.0, up_axis='+Y', handedness='left'),
                dict(units='metre', scale=1.0, up_axis='sideways', handedness='left'),
                dict(units='metre', scale=1.0, up_axis='+Y', handedness='ambidextrous')):
        must_reject(lambda bad=bad: require_metadata(bad), 'impossible scene metadata accepted')
        must_reject(lambda bad=bad: encode_scene(dict(base, metadata=bad)),
                    'scene writer accepted impossible metadata')

    body = bytearray(v2[:-32])
    body[8:12] = struct.pack('<I', 3)
    must_reject(lambda: decode_scene(bytes(body) + sha256(body).digest()),
                'future scene version accepted')

    # --- the exporter reads the declaration ---------------------------------------
    document = export(decoded)
    assert document['extras']['metadata'] == DEFAULT_METADATA
    assert 'reflect Z' in document['extras']['coordinate_conversion']
    right = decode_scene(encode_scene(dict(base, metadata=dict(
        units='metre', scale=2.0, up_axis='+Y', handedness='right'))))
    right_document = export(right)
    assert right_document['extras']['metadata']['handedness'] == 'right'
    assert 'no handedness conversion' in right_document['extras']['coordinate_conversion']
    assert right_document['nodes'][0]['matrix'][0] == 2.0, 'scene scale not applied'
    must_reject(lambda: export(dict(decoded, metadata=dict(
        units='metre', scale=1.0, up_axis='+Z', handedness='left'))),
        'exporter accepted an unsupported up-axis')

    # --- the position ledger header ----------------------------------------------
    for version in (1, 19):
        result = inspect_bytes(ledger(version))
        assert result['version'] == version
        assert result['scene'] == DEFAULT_METADATA, (version, result['scene'])
        assert result['scene_declared'] is False

    declared = dict(units='metre', scale=0.01, up_axis='+Y', handedness='right')
    result = inspect_bytes(ledger(20, scene=declared))
    assert result['version'] == 20
    assert result['scene'] == declared and result['scene_declared'] is True

    must_reject(lambda: inspect_bytes(ledger(20)), 'v20 ledger without scene metadata accepted')
    must_reject(lambda: inspect_bytes(ledger(19, scene=declared)),
                'v19 ledger claiming scene metadata accepted')
    must_reject(lambda: inspect_bytes(ledger(20, scene=dict(declared, extra=1))),
                'v20 ledger with an unknown scene field accepted')
    must_reject(lambda: inspect_bytes(ledger(20, scene=dict(declared, units='unitless', scale=2.0))),
                'v20 ledger with an impossible unit scale accepted')
    must_reject(lambda: inspect_bytes(ledger(20, scene=dict(declared, up_axis='sideways'))),
                'v20 ledger with an unknown up-axis accepted')

    print('PASS scene metadata: v1/v2 scene headers and v1/v19/v20 ledger headers agree')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
