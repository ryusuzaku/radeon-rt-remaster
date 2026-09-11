"""Compile opt-in stable-material-ID PBR factors without altering a capture."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct

from mod_scene import fields, strict_json, read_bounded, HASH
from scene_io import require, load_scene, MAX_DRAWS


def number(value, low, high):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f'material number must be finite in {low}..{high}')
    return float(value)


def vector(value, high):
    require(isinstance(value, list) and len(value) == 3, 'colour must have three numbers')
    return [number(x, 0, high) for x in value]


def compile_materials(value, scene):
    fields(value, ('schema', 'version', 'materials'))
    require(value['schema'] == 'rrt-materials' and type(value['version']) is int and value['version'] == 1,
            'unsupported material schema/version')
    require(scene['complete'], 'material inputs require a complete scene')
    require(isinstance(value['materials'], list) and len(value['materials']) <= MAX_DRAWS,
            'too many material records')
    known = {d['material_id'] for d in scene['draws']}
    records = {}
    for entry in value['materials']:
        fields(entry, ('target',), ('base_color', 'roughness', 'metallic', 'emissive'))
        target = entry['target']
        require(isinstance(target, str) and HASH.fullmatch(target), 'invalid material target ID')
        require(target in known, 'unmatched material target')
        require(target not in records, 'duplicate material target')
        base = vector(entry.get('base_color', [1, 1, 1]), 1)
        roughness = number(entry.get('roughness', 1), .05, 1)
        emission = vector(entry.get('emissive', [0, 0, 0]), 32)
        metallic = number(entry.get('metallic', 0), 0, 1)
        records[target] = bytes.fromhex(target) + struct.pack('<8f', *base, roughness, *emission, metallic)
    raw = b'RRTMAT1\0' + struct.pack('<2I', 1, len(records)) + b''.join(records[k] for k in sorted(records))
    return raw + sha256(raw).digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    template = commands.add_parser('template', help='write a NEW authoring JSON containing each material ID')
    compile_cmd = commands.add_parser('compile', help='validate JSON against a scene and write a NEW .rrmat')
    for command in (template, compile_cmd):
        command.add_argument('scene', type=Path)
        command.add_argument('--output', required=True, type=Path)
    compile_cmd.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    try:
        scene = load_scene(args.scene)
        require(scene['complete'], 'material inputs require a complete scene')
        if args.command == 'template':
            value = dict(schema='rrt-materials', version=1, materials=[dict(target=target,
                         base_color=[1, 1, 1], roughness=1, metallic=0, emissive=[0, 0, 0])
                         for target in sorted({d['material_id'] for d in scene['draws']})])
            raw = (json.dumps(value, indent=2)+'\n').encode('utf-8')
        else:
            value = strict_json(read_bounded(args.input, 2*1024*1024))
            raw = compile_materials(value, scene)
        with args.output.open('xb') as output:
            output.write(raw)
        print(json.dumps(dict(output=str(args.output), records=len(value['materials']), sha256=sha256(raw).hexdigest())))
    except (OSError, ValueError, OverflowError, struct.error, RecursionError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
