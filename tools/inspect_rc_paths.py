"""Strictly inspect the bounded renderer-owned RCRPATH1 diagnostic artifact."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct


WIDTH, HEIGHT, STRIDE = 128, 96, 128
PIXELS = WIDTH * HEIGHT
HEADER = struct.Struct('<8s8I32s32s32s6f4I12f')
ROW = struct.Struct('<32f')
FILE_BYTES = HEADER.size + PIXELS * ROW.size + 32


def _unit_spherical(value):
    """Match the NRC sample's normalized spherical direction encoding."""
    x, y, z = value
    z = min(1.0, max(-1.0, z))
    theta = math.acos(z) / (math.pi / 2.0)
    theta = math.sqrt(theta) if theta < 1.0 else 2.0 - math.sqrt(2.0 - theta)
    return theta * 0.5, math.atan2(y, x) / (2.0 * math.pi) + 0.5


def _cache_input(row, lower, upper):
    position = tuple((((row[i] - lower[i]) / (upper[i] - lower[i])) - 0.5) / 1.05 + 0.5 for i in range(3))
    normal = _unit_spherical(row[4:7])
    view = _unit_spherical(row[8:11])
    return (*position, *normal, *view, *row[12:15], row[7])


def decode_paths(data):
    if len(data) != FILE_BYTES or sha256(data[:-32]).digest() != data[-32:]:
        raise ValueError('RC path length/checksum mismatch')
    fields = HEADER.unpack_from(data)
    (magic, version, width, height, stride, pixels, declared_queries,
     declared_training, random_index) = fields[:9]
    if (magic, version, width, height, stride, pixels) != (b'RCRPATH1', 1, WIDTH, HEIGHT, STRIDE, PIXELS):
        raise ValueError('unsupported RC path contract')
    if not 0 < declared_queries <= PIXELS or declared_training != min(declared_queries, 512) or random_index >= 4096:
        raise ValueError('invalid RC path counts/frame metadata')
    scene_digest, shader_digest, settings_digest = fields[9:12]
    if not all(any(digest) for digest in (scene_digest, shader_digest, settings_digest)):
        raise ValueError('zero RC path provenance digest')
    bounds = fields[12:18]
    settings = fields[18:34]
    if not all(math.isfinite(x) for x in (*bounds, *settings[4:])):
        raise ValueError('nonfinite RC path header')
    lower, upper = bounds[:3], bounds[3:]
    if any(upper[i] - lower[i] < 1e-4 for i in range(3)):
        raise ValueError('degenerate RC path bounds')
    settings_bytes = data[HEADER.size - 64:HEADER.size]
    if sha256(settings_bytes).digest() != settings_digest:
        raise ValueError('RC path settings digest mismatch')
    seed, shadows, flags, reserved = settings[:4]
    if shadows not in (0, 1) or reserved != 0:
        raise ValueError('invalid RC path settings')

    rows = list(ROW.iter_unpack(data[HEADER.size:-32]))
    queries = []
    source_rgb = bytearray()
    maximum_factor_error = 0.0
    primary_hits = 0
    for pixel, row in enumerate(rows):
        if not all(math.isfinite(x) for x in row):
            raise ValueError('nonfinite RC path row')
        secondary, primary = row[3], row[31]
        if secondary not in (0.0, 1.0) or primary not in (0.0, 1.0) or secondary > primary:
            raise ValueError('invalid RC path validity')
        if any(x < 0 for x in (*row[12:15], *row[16:19], *row[20:23], *row[24:27], *row[28:31])):
            raise ValueError('negative RC path radiance/material')
        if any(x > 1 for x in (*row[12:15], *row[20:23])):
            raise ValueError('invalid RC path albedo/throughput')
        if primary:
            primary_hits += 1
            expected = tuple(row[20+i] * row[16+i] for i in range(3))
            error = max(abs(row[24+i] - expected[i]) for i in range(3))
            maximum_factor_error = max(maximum_factor_error, error)
            if error > 2e-5:
                raise ValueError('invalid RC path factorization')
            output = tuple(row[28+i] + row[24+i] for i in range(3))
        else:
            if secondary or any(row[:27]) or row[27] != -1:
                raise ValueError('invalid RC path background row')
            output = row[28:31]
        source_rgb.extend(struct.pack('<3f', *output))
        if not secondary:
            continue
        if not all(lower[i] - 1e-4 <= row[i] <= upper[i] + 1e-4 for i in range(3)):
            raise ValueError('RC path query outside bounds')
        nl = sum(x*x for x in row[4:7]); vl = sum(x*x for x in row[8:11])
        if abs(nl-1) >= 1e-3 or abs(vl-1) >= 1e-3 or row[7] != 1 or row[11] < 1 or row[27] <= 0:
            raise ValueError('invalid RC path surface tuple')
        cache_input = _cache_input(row, lower, upper)
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in cache_input):
            raise ValueError('invalid normalized RC cache input')
        queries.append(dict(pixel=pixel, input=cache_input, target=row[16:19], throughput=row[20:23],
                            direct=row[28:31], source_indirect=row[24:27]))
    if len(queries) != declared_queries:
        raise ValueError('RC path query count mismatch')
    return dict(version=version, width=width, height=height, stride=stride, pixels=pixels,
                queries=queries, training=queries[:declared_training], random_index=random_index,
                seed=seed, shadows=bool(shadows), flags=flags, bounds=dict(lower=lower, upper=upper),
                scene_sha256=scene_digest.hex(), shader_sha256=shader_digest.hex(),
                settings_sha256=settings_digest.hex(), artifact_sha256=data[-32:].hex(),
                source_rgb_sha256=sha256(source_rgb).hexdigest(), primary_hits=primary_hits,
                maximum_factor_error=maximum_factor_error)


def load_paths(path):
    path = Path(path)
    if path.stat().st_size != FILE_BYTES:
        raise ValueError('RC path file size mismatch')
    return decode_paths(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    result = load_paths(parser.parse_args().path)
    result['query_count'] = len(result.pop('queries'))
    result['training_count'] = len(result.pop('training'))
    result['rc_dispatches'] = 0
    result['rc_rendering'] = False
    print(json.dumps(result))


if __name__ == '__main__':
    main()
