"""Read-only validator for RRTSIG01/02 renderer diagnostic buffers (little endian)."""
import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import struct

HEADER = struct.Struct('<8s7I')
RECORD = struct.Struct('<20f')
RECORDS = {1: RECORD, 2: struct.Struct('<36f')}
MAX_BYTES = 256 * 1024 * 1024
MAX_STREAM_BYTES = 1024 * 1024 * 1024
CHUNK_PIXELS = 16384


@dataclass(frozen=True)
class Signals:
    width: int
    height: int
    samples: int
    flags: int
    mode: int
    version: int
    payload: bytes

    def pixel(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError('pixel outside signal image')
        record = RECORDS[self.version]
        return record.unpack_from(self.payload, (y * self.width + x) * record.size)

    def records(self):
        return RECORDS[self.version].iter_unpack(self.payload)


def read_header(source, limit):
    header = source.read(HEADER.size)
    if len(header) != HEADER.size:
        raise ValueError('truncated signal header')
    magic, version, width, height, stride, samples, flags, mode = HEADER.unpack(header)
    if version not in RECORDS or magic != f'RRTSIG0{version}'.encode() or stride != RECORDS[version].size:
        raise ValueError('unsupported signal format')
    size = width * height * stride
    if not width or not height or size > limit or not 1 <= samples <= 4096 or flags > (1 if version == 1 else 3) or mode > 3:
        raise ValueError('invalid signal bounds or flags')
    source.seek(0, 2)
    if source.tell() != HEADER.size + size:
        raise ValueError('signal payload size mismatch')
    source.seek(HEADER.size)
    return Signals(width, height, samples, flags, mode, version, b'')


def validated_records(image, records):
    width, height, version, flags, mode = image.width, image.height, image.version, image.flags, image.mode
    for row in records:
        if not all(math.isfinite(v) for v in row):
            raise ValueError('nonfinite signal')
        if row[3] != 1 or row[19] != 1 or row[11] not in (0, 1) or row[14] not in (0, 1):
            raise ValueError('invalid signal validity/alpha')
        if row[11] == 0:
            if any(row[4:16]):
                raise ValueError('background guide must be zero')
        elif (row[7] < 0 or abs(sum(v*v for v in row[4:7])-1) > .001
              or any(v < -.00001 or v > 1.00001 for v in row[8:11])
              or row[15] != int(row[15]) or not 1 <= row[15] <= 1024):
            raise ValueError('invalid surface guide')
        if (row[14] == 0 and any(row[12:14])) or abs(row[12]) > width or abs(row[13]) > height:
            raise ValueError('invalid motion vector')
        if version == 2:
            count, variance, accepted, reason = row[32:36]
            if row[23] < 0 or (row[11] == 0 and any(row[20:24])) or row[27] != 1 or row[31] < 0:
                raise ValueError('invalid position/sample/moment')
            if (count != int(count) or not 1 <= count <= 32 or variance < 0 or accepted not in (0, 1)
                    or reason != int(reason) or not 0 <= reason <= 7 or (reason == 0) != bool(accepted)
                    or (not accepted and count != 1) or (accepted and count < 2)):
                raise ValueError('invalid temporal statistics')
            if accepted and (not (flags & 2) or mode != 3 or not row[11] or not row[14]):
                raise ValueError('temporal reuse without valid projection/surface/mode')
        yield row


def load_signals(path):
    """Random-access convenience API, capped at 256 MiB of payload."""
    with Path(path).open('rb') as source:
        image = read_header(source, MAX_BYTES)
        size = image.width * image.height * RECORDS[image.version].size
        payload = source.read(size)
        if len(payload) != size:
            raise ValueError('truncated signal payload')
    result = Signals(image.width, image.height, image.samples, image.flags, image.mode, image.version, payload)
    for _ in validated_records(result, result.records()):
        pass
    return result


def summarize(image, records=None):
    hits = motion = 0
    maximum_motion = 0.0
    minimum_depth = math.inf
    maximum_depth = 0.0
    reasons = {str(i): 0 for i in range(8)}
    maximum_count = maximum_variance = 0
    for row in image.records() if records is None else records:
        if row[11]:
            hits += 1
            minimum_depth = min(minimum_depth, row[7])
            maximum_depth = max(maximum_depth, row[7])
        if row[14]:
            motion += 1
            maximum_motion = max(maximum_motion, math.hypot(row[12], row[13]))
        if image.version == 2:
            reasons[str(int(row[35]))] += 1
            maximum_count = max(maximum_count, row[32]); maximum_variance = max(maximum_variance, row[33])
    result = dict(format=f'RRTSIG0{image.version}', width=image.width, height=image.height, samples=image.samples, mode=image.mode,
                filter_requested=bool(image.flags & 1), hit_pixels=hits, projection_valid_pixels=motion,
                min_ray_depth=minimum_depth if hits else None, max_ray_depth=maximum_depth if hits else None,
                max_motion_pixels=maximum_motion)
    if image.version == 2:
        result.update(temporal_requested=bool(image.flags & 2), temporal_reasons=reasons,
                      max_history_samples=maximum_count, max_luminance_variance=maximum_variance)
    return result


def inspect_file(path):
    """Validate and summarize up to 1 GiB using at most 16384 records per read."""
    with Path(path).open('rb') as source:
        image = read_header(source, MAX_STREAM_BYTES)
        record = RECORDS[image.version]
        def chunks():
            remaining = image.width * image.height
            while remaining:
                count = min(CHUNK_PIXELS, remaining)
                payload = source.read(count * record.size)
                if len(payload) != count * record.size:
                    raise ValueError('truncated signal payload')
                yield from record.iter_unpack(payload)
                remaining -= count
        return summarize(image, validated_records(image, chunks()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('signals', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect_file(args.signals)))
    except (OSError, ValueError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    main()
