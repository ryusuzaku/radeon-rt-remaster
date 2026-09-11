"""Export the captured unlit triangle subset as a self-contained glTF 2.0.

Raster replay remains the accuracy oracle: glTF cannot represent every D3D9
blend/scissor/projection state. Original state is retained in extras.
"""
import argparse
import base64
import json
from pathlib import Path
import struct
import zlib
from scene_io import load_scene, SceneError


def data_uri(kind, data):
    return 'data:' + kind + ';base64,' + base64.b64encode(data).decode('ascii')


def png(width, height, bgra):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            b, g, r, a = bgra[(y * width + x) * 4:(y * width + x + 1) * 4]
            rows.extend((r, g, b, a))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


def export(scene):
    binary = bytearray()
    gltf = dict(asset=dict(version='2.0', generator='RRT scene exporter v1'), scene=0,
        scenes=[dict(nodes=[])], nodes=[], meshes=[], materials=[], textures=[], images=[],
        samplers=[], buffers=[], bufferViews=[], accessors=[], extensionsUsed=['KHR_materials_unlit'],
        extras=dict(source_frame=scene['frame'], complete=scene['complete'], rejected=scene['rejected'],
                    coordinate_conversion='D3D left-handed to glTF right-handed: reflect Z and reverse winding',
                    fidelity='Geometry/texture interchange, not exact D3D9 raster equivalence. View/projection/scissor retained in node extras.'))
    textures, materials, meshes = {}, {}, {}

    def accessor(values, fmt, kind, component, target, bounds=False):
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack('<' + fmt, *value))
        view = len(gltf['bufferViews'])
        gltf['bufferViews'].append(dict(buffer=0, byteOffset=offset, byteLength=len(binary)-offset, target=target))
        acc = dict(bufferView=view, componentType=component, count=len(values), type=kind)
        if bounds:
            acc['min'] = [min(v[i] for v in values) for i in range(len(values[0]))]
            acc['max'] = [max(v[i] for v in values) for i in range(len(values[0]))]
        gltf['accessors'].append(acc)
        return len(gltf['accessors']) - 1

    for draw in scene['draws']:
        tex_key = (draw['texture_id'], tuple(draw['sampler']))
        if tex_key not in textures:
            image = len(gltf['images'])
            gltf['images'].append(dict(name=draw['texture_id'], uri=data_uri('image/png', png(draw['texture_width'], draw['texture_height'], draw['texture']))))
            sampler = draw['sampler']
            wrap = {1: 10497, 2: 33648, 3: 33071}
            si = len(gltf['samplers'])
            gltf['samplers'].append(dict(magFilter=9728 if sampler[4] == 1 else 9729,
                minFilter=9728 if sampler[5] == 1 else 9729, wrapS=wrap.get(sampler[0], 33071), wrapT=wrap.get(sampler[1], 33071)))
            textures[tex_key] = len(gltf['textures'])
            gltf['textures'].append(dict(source=image, sampler=si))
        if draw['material_id'] not in materials:
            rs = draw['render']
            material = dict(name=draw['material_id'], pbrMetallicRoughness=dict(baseColorTexture=dict(index=textures[tex_key]),
                metallicFactor=0, roughnessFactor=1), extensions={'KHR_materials_unlit': {}},
                doubleSided=rs[7] == 1, alphaMode='BLEND' if rs[12] else ('MASK' if rs[4] else 'OPAQUE'),
                extras=dict(d3d9_render_states=list(rs), d3d9_texture_states=list(draw['texture_states']), d3d9_sampler_states=list(draw['sampler'])))
            if rs[4]:
                material['alphaCutoff'] = rs[9] / 255
            materials[draw['material_id']] = len(gltf['materials'])
            gltf['materials'].append(material)
        key = (draw['mesh_id'], draw['material_id'])
        if key not in meshes:
            positions = [(v[0], v[1], -v[2]) for v in draw['vertices']]
            colors = [(((v[3] >> 16) & 255)/255, ((v[3] >> 8) & 255)/255, (v[3] & 255)/255, (v[3] >> 24)/255) for v in draw['vertices']]
            uv = [(v[4], v[5]) for v in draw['vertices']]
            indices = draw['indices']
            reflected = [(indices[i+k],) for i in range(0, len(indices), 3) for k in (0, 2, 1)]
            attrs = dict(POSITION=accessor(positions, '3f', 'VEC3', 5126, 34962, True),
                         COLOR_0=accessor(colors, '4f', 'VEC4', 5126, 34962),
                         TEXCOORD_0=accessor(uv, '2f', 'VEC2', 5126, 34962))
            primitive = dict(attributes=attrs, indices=accessor(reflected, 'I', 'SCALAR', 5125, 34963),
                             material=materials[draw['material_id']], mode=4)
            meshes[key] = len(gltf['meshes'])
            gltf['meshes'].append(dict(name=draw['mesh_id'], primitives=[primitive]))
        # Row-major D3D row-vector matrix becomes a column-major glTF matrix
        # with the same flattened order. Apply S*M*S for the Z reflection.
        sign = (1, 1, -1, 1)
        matrix = [v * sign[i//4] * sign[i%4] for i, v in enumerate(draw['world'])]
        node = dict(name=f"draw_{draw['ordinal']}", mesh=meshes[key], matrix=matrix,
                    extras=dict(source_draw=draw['ordinal'], d3d9_view=list(draw['view']),
                                d3d9_projection=list(draw['projection']), viewport=list(draw['viewport']), scissor=list(draw['scissor'])))
        gltf['scenes'][0]['nodes'].append(len(gltf['nodes']))
        gltf['nodes'].append(node)
    if binary:
        gltf['buffers'].append(dict(byteLength=len(binary), uri=data_uri('application/octet-stream', binary)))
    # glTF disallows empty top-level arrays.
    return {k: v for k, v in gltf.items() if not isinstance(v, list) or v}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    try:
        scene = load_scene(args.scene)
        if not scene['complete'] and not args.allow_partial:
            raise SceneError('incomplete scene; inspect rejections or explicitly use --allow-partial')
        content = json.dumps(export(scene), indent=2, allow_nan=False)
        with args.output.open('x', encoding='utf-8') as destination:
            destination.write(content + '\n')
        print(json.dumps(dict(output=str(args.output), draws=len(scene['draws']), complete=scene['complete'])))
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
