"""Offline stable-ID mods: extract assets, create manifests, validate and apply.

Only data files are loaded. Mods cannot execute scripts, fetch URLs or alter the
source capture. Resolution always uses original IDs, never replacement IDs.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zlib
from scene_io import decode_scene, encode_scene, require, SceneError, MAX_BYTES
from png_texture import decode_png
from export_gltf import png

HASH = re.compile(r'[0-9a-f]{64}\Z')
MOD_ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,63}\Z')
MAX_ENTRIES = 256
MAX_ASSET = 20*1024*1024


def read_bounded(path, limit):
    with Path(path).open('rb') as source:
        data = source.read(limit+1)
    require(len(data) <= limit, 'file exceeds budget: ' + str(path))
    return data


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise SceneError('nonfinite JSON number: ' + value)
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError, UnicodeError) as error:
        raise SceneError('invalid JSON: ' + str(error)) from error


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
            'missing or unknown fields; expected ' + ', '.join(required))


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'integer outside supported range')
    return value


def asset_path(root, name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name and '\0' not in name,
            'asset path must be a relative portable path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and '.' not in name.split('/'), 'asset path escapes mod directory')
    resolved = (root / path).resolve(strict=True)
    require(resolved.is_relative_to(root.resolve()) and resolved.is_file(), 'asset path escapes mod directory or is not a file')
    return resolved


def payload(kind, data):
    if kind == 'texture':
        return decode_png(data)
    value = strict_json(data)
    if kind == 'mesh':
        fields(value, ('version', 'vertices', 'indices'))
        require(type(value['version']) is int and value['version'] == 1, 'unsupported mesh version')
        vertices, indices = value['vertices'], value['indices']
        require(isinstance(vertices, list) and 0 < len(vertices) <= 500000 and
                isinstance(indices, list) and 0 < len(indices) <= 1500000 and len(indices)%3 == 0, 'invalid mesh counts')
        for vertex in vertices:
            require(isinstance(vertex, list) and len(vertex) == 6, 'vertex must be [x,y,z,argb,u,v]')
            integer(vertex[3], 0, 0xffffffff)
            for i in (0, 1, 2, 4, 5):
                require(type(vertex[i]) in (int, float) and math.isfinite(vertex[i]) and abs(vertex[i]) <= 3.402823466e38,
                        'invalid float32 vertex')
        for index in indices:
            integer(index, 0, len(vertices)-1)
        return value
    require(kind == 'material', 'unknown replacement kind')
    fields(value, ('version',), ('alpha_mode', 'alpha_cutoff', 'double_sided', 'min_filter', 'mag_filter', 'address_u', 'address_v'))
    require(type(value['version']) is int and value['version'] == 1 and len(value) > 1, 'invalid material version or empty patch')
    for key, options in (('alpha_mode', ('opaque', 'blend', 'mask')), ('min_filter', ('point', 'linear')),
                         ('mag_filter', ('point', 'linear')), ('address_u', ('wrap', 'mirror', 'clamp')),
                         ('address_v', ('wrap', 'mirror', 'clamp'))):
        if key in value:
            require(value[key] in options, 'invalid material ' + key)
    if 'double_sided' in value:
        require(type(value['double_sided']) is bool, 'double_sided must be boolean')
    if 'alpha_cutoff' in value:
        integer(value['alpha_cutoff'], 0, 255)
        require(value.get('alpha_mode') == 'mask', 'alpha_cutoff requires alpha_mode mask')
    return value


def load_mod(path):
    path = Path(path).resolve(strict=True)
    raw = read_bounded(path, 1024*1024)
    mod = strict_json(raw)
    fields(mod, ('schema', 'version', 'id', 'priority', 'replacements'))
    require(mod['schema'] == 'rrt-mod' and type(mod['version']) is int and mod['version'] == 1, 'unsupported mod schema/version')
    require(isinstance(mod['id'], str) and MOD_ID.fullmatch(mod['id']), 'invalid mod id')
    integer(mod['priority'], -1000000, 1000000)
    require(isinstance(mod['replacements'], list) and len(mod['replacements']) <= MAX_ENTRIES, 'too many replacements')
    seen = set()
    used_bytes = len(raw)
    entries = []
    for entry in mod['replacements']:
        fields(entry, ('kind', 'target', 'asset', 'sha256'))
        kind, target, digest = entry['kind'], entry['target'], entry['sha256']
        require(kind in ('texture', 'mesh', 'material') and isinstance(target, str) and HASH.fullmatch(target), 'invalid replacement target')
        require(isinstance(digest, str) and HASH.fullmatch(digest), 'invalid dependency hash')
        require((kind, target) not in seen, 'duplicate target in mod')
        seen.add((kind, target))
        data = read_bounded(asset_path(path.parent, entry['asset']), MAX_ASSET)
        used_bytes += len(data)
        require(used_bytes <= MAX_BYTES, 'mod dependency budget exceeded')
        require(sha256(data).hexdigest() == digest, 'asset checksum mismatch: ' + entry['asset'])
        decoded = payload(kind, data)
        # Compressed PNG file sizes alone do not bound retained decoded texels.
        if kind == 'texture':
            used_bytes += len(decoded[2])
        elif kind == 'mesh':
            used_bytes += len(decoded['vertices'])*24 + len(decoded['indices'])*4
        require(used_bytes <= MAX_BYTES, 'mod decoded-payload budget exceeded')
        entries.append({**entry, 'payload': decoded})
    return {**mod, 'replacements': entries, 'manifest_sha256': sha256(raw).hexdigest(), 'bytes': used_bytes}


def patch_material(draw, value):
    render, sampler = list(draw['render']), list(draw['sampler'])
    if 'double_sided' in value:
        render[7] = 1 if value['double_sided'] else 3  # NONE or CCW cull, explicit D3D9 convention.
    if 'alpha_mode' in value:
        mode = value['alpha_mode']
        render[4], render[12] = int(mode == 'mask'), int(mode == 'blend')
        if mode == 'mask':
            render[9], render[10] = value.get('alpha_cutoff', 128), 7  # GREATER_EQUAL
        if mode == 'blend':
            render[5], render[6], render[22], render[30] = 5, 6, 1, 0  # SRCALPHA, INVSRCALPHA, ADD
    for key, slot in (('min_filter', 5), ('mag_filter', 4)):
        if key in value:
            sampler[slot] = {'point': 1, 'linear': 2}[value[key]]
    for key, slot in (('address_u', 0), ('address_v', 1)):
        if key in value:
            sampler[slot] = {'wrap': 1, 'mirror': 2, 'clamp': 3}[value[key]]
    draw['render'], draw['sampler'] = render, sampler


def resolve(scene, mods, allow_unmatched=False, allow_partial=False):
    require(scene['complete'] or allow_partial, 'incomplete input scene; use --allow-partial for diagnostics')
    require(len(mods) <= 32 and len({m['id'] for m in mods}) == len(mods), 'too many mods or duplicate mod IDs')
    require(sum(m['bytes'] for m in mods) <= MAX_BYTES, 'combined mod dependency budget exceeded')
    candidates = {}
    occupied = set()
    for mod in sorted(mods, key=lambda m: (m['priority'], m['id'])):
        for entry in mod['replacements']:
            key = (entry['kind'], entry['target'])
            rank_key = (*key, mod['priority'])
            require(rank_key not in occupied, 'equal-priority replacement conflict: ' + '/'.join(key))
            occupied.add(rank_key)
            candidates.setdefault(key, []).append((mod, entry))
    known = {(kind, d[kind+'_id']) for d in scene['draws'] for kind in ('texture', 'mesh', 'material')}
    unmatched = sorted(set(candidates)-known)
    require(not unmatched or allow_unmatched, 'unmatched replacement target(s): ' + str(unmatched))
    winners = {key: values[-1] for key, values in candidates.items()}
    output = {**scene, 'draws': []}
    changed = []
    for original in scene['draws']:
        draw = dict(original)
        applied = []
        for kind in ('mesh', 'texture', 'material'):
            found = winners.get((kind, original[kind+'_id']))
            if not found:
                continue
            mod, entry = found
            value = entry['payload']
            if kind == 'texture':
                draw['texture_width'], draw['texture_height'], draw['texture'] = value
            elif kind == 'mesh':
                draw['vertices'], draw['indices'] = value['vertices'], value['indices']
            else:
                patch_material(draw, value)
            applied.append(dict(kind=kind, mod=mod['id'], target=entry['target'], dependency_sha256=entry['sha256']))
        output['draws'].append(draw)
        if applied:
            changed.append(dict(ordinal=draw['ordinal'], replacements=applied))
    encoded = encode_scene(output)
    updated = decode_scene(encoded)
    by_ordinal = {d['ordinal']: d for d in updated['draws']}
    for change in changed:
        change['result_ids'] = {k: by_ordinal[change['ordinal']][k+'_id'] for k in ('texture', 'mesh', 'material')}
    report = dict(schema='rrt-mod-report', version=1, complete=updated['complete'],
        mods=[dict(id=m['id'], priority=m['priority'], manifest_sha256=m['manifest_sha256']) for m in sorted(mods, key=lambda m: m['id'])],
        matched_draws=changed, unmatched=[dict(kind=k, target=t) for k, t in unmatched],
        shadowed=[dict(kind=k[0], target=k[1], mod=m['id'], winner=values[-1][0]['id'])
                  for k, values in sorted(candidates.items()) for m, _ in values[:-1]],
        output_sha256=sha256(encoded).hexdigest())
    return encoded, report


def extract(scene, directory):
    """Create an entirely new editing directory; no existing files are replaced."""
    root = Path(directory)
    require(scene['complete'], 'cannot create starter assets from an incomplete scene')
    files, inventory = {}, []
    for kind in ('mesh', 'texture'):
        seen = set()
        for draw in scene['draws']:
            identifier = draw[kind+'_id']
            if identifier in seen:
                continue
            seen.add(identifier)
            if kind == 'texture':
                name = 'textures/'+identifier+'.png'
                data = png(draw['texture_width'], draw['texture_height'], draw['texture'])
            else:
                name = 'meshes/'+identifier+'.json'
                data = json.dumps(dict(version=1, vertices=draw['vertices'], indices=draw['indices']), allow_nan=False).encode()
            require(len(data) <= MAX_ASSET, 'extracted asset exceeds replacement file budget')
            require(sum(len(v) for v in files.values()) + len(data) <= MAX_BYTES, 'extraction budget exceeded')
            files[name] = data
            inventory.append(dict(kind=kind, target=identifier, asset=name, sha256=sha256(data).hexdigest(),
                                  draws=[d['ordinal'] for d in scene['draws'] if d[kind+'_id'] == identifier]))
    # An identity texture replacement is a runnable starting point.
    starter = next((a for a in inventory if a['kind'] == 'texture'), None)
    manifest = dict(schema='rrt-mod', version=1, id='starter', priority=0,
                    replacements=[{k: starter[k] for k in ('kind', 'target', 'asset', 'sha256')}] if starter else [])
    catalog = dict(schema='rrt-asset-catalog', version=1, assets=inventory,
                   materials=[dict(target=d['material_id'], draw=d['ordinal'], render=d['render'], sampler=d['sampler']) for d in scene['draws']])
    files['mod.json'] = json.dumps(manifest, indent=2).encode()
    files['catalog.json'] = json.dumps(catalog, indent=2).encode()
    require(sum(len(v) for v in files.values()) <= MAX_BYTES, 'extraction budget exceeded')
    root.mkdir()  # exist_ok=False intentionally, parent must already exist.
    (root/'textures').mkdir(); (root/'meshes').mkdir()
    for name, data in files.items():
        with (root/name).open('xb') as out:
            out.write(data)
    return dict(directory=str(root), assets=len(inventory), manifest=str(root/'mod.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    catalog = commands.add_parser('extract', help='export editable mesh JSON/PNG plus catalog and identity starter mod')
    catalog.add_argument('scene', type=Path); catalog.add_argument('directory', type=Path)
    make = commands.add_parser('make', help='validate an edited asset and write a new one-entry manifest with its checksum')
    make.add_argument('--kind', required=True, choices=('mesh', 'texture', 'material'))
    make.add_argument('--target', required=True); make.add_argument('--asset', required=True)
    make.add_argument('--id', required=True); make.add_argument('--priority', type=int, default=0)
    make.add_argument('--output', required=True, type=Path)
    for name in ('check', 'apply'):
        cmd = commands.add_parser(name)
        cmd.add_argument('scene', type=Path); cmd.add_argument('--mod', action='append', required=True, type=Path)
        cmd.add_argument('--allow-unmatched', action='store_true'); cmd.add_argument('--allow-partial', action='store_true')
        if name == 'apply':
            cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'make':
            require(MOD_ID.fullmatch(args.id) and HASH.fullmatch(args.target), 'invalid mod or target ID')
            integer(args.priority, -1000000, 1000000)
            data = read_bounded(asset_path(args.output.parent, args.asset), MAX_ASSET)
            payload(args.kind, data)
            manifest = dict(schema='rrt-mod', version=1, id=args.id, priority=args.priority,
                replacements=[dict(kind=args.kind, target=args.target, asset=args.asset, sha256=sha256(data).hexdigest())])
            with args.output.open('x', encoding='utf-8') as out:
                json.dump(manifest, out, indent=2); out.write('\n')
            report = dict(manifest=str(args.output), dependency_sha256=sha256(data).hexdigest())
        else:
            raw = read_bounded(args.scene, MAX_BYTES)
            scene = decode_scene(raw)
            if args.command == 'extract':
                report = extract(scene, args.directory)
            else:
                require(len(args.mod) <= 32, 'too many mods')
                mods = []
                for path in args.mod:
                    mods.append(load_mod(path))
                    require(sum(m['bytes'] for m in mods) <= MAX_BYTES, 'combined mod dependency budget exceeded')
                result, report = resolve(scene, mods, args.allow_unmatched, args.allow_partial)
                report['source_sha256'] = sha256(raw).hexdigest()
                if args.command == 'apply':
                    with args.output.open('xb') as out:
                        out.write(result)
        print(json.dumps(report, indent=2, allow_nan=False))
    except (OSError, ValueError, OverflowError, struct.error, zlib.error, RecursionError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
