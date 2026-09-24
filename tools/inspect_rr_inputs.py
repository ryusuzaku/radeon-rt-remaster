"""Read bounded RRTRRI01 preparation diagnostics, not SDK-ready textures."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct

HEADER = struct.Struct('<8s8I80f')
RECORD = struct.Struct('<24f')
def file_bytes(width,height): return HEADER.size+width*height*RECORD.size+32
FILE_BYTES = file_bytes(128,96) # historical v1 compatibility constant
FILE_BYTES_V2 = file_bytes(256,192)
MAX_FILE_BYTES=max(FILE_BYTES,FILE_BYTES_V2)


def decode_inputs(data):
    if len(data)<HEADER.size+32 or len(data)>MAX_FILE_BYTES or sha256(data[:-32]).digest() != data[-32:]:
        raise ValueError('RR input length/checksum mismatch')
    fields = HEADER.unpack_from(data)
    magic, version, width, height, stride, frame_index, random_index, seed, reset = fields[:9]
    if (magic,version,width,height,stride) not in ((b'RRTRRI01',1,128,96,96),(b'RRTRRI02',2,256,192,96)) or len(data)!=file_bytes(width,height):
        raise ValueError('unsupported RR input contract')
    if reset not in (0, 1) or frame_index >= 65536 or random_index >= 4096:
        raise ValueError('invalid RR frame metadata')
    if not all(math.isfinite(x) for x in fields[9:]):
        raise ValueError('nonfinite RR matrix')
    records = list(RECORD.iter_unpack(data[HEADER.size:-32]))
    for row in records:
        if not all(math.isfinite(x) for x in row):
            raise ValueError('nonfinite RR record')
        if any(x < 0 for x in row[:3]+row[4:7]+row[12:15]):
            raise ValueError('negative RR lighting/albedo')
        hit = row[23]
        if hit != int(hit) or not 0 <= hit <= 1024 or row[7] != bool(hit) or row[15] not in (0, 1):
            raise ValueError('invalid RR hit/validity')
        if hit:
            if not 0 <= row[3] <= 100000 or not all(0 <= x <= 1 for x in row[8:10]) or not .049 <= row[10] <= 1 or row[11] != 0:
                raise ValueError('invalid RR distance/normal/material')
            if (reset or not row[15]) and any(row[16:19]):
                raise ValueError('invalid RR reset motion')
            if reset and row[15]:
                raise ValueError('valid motion on reset frame')
        elif row[:4] != (0, 0, 0, -1) or any(row[7:]):
            raise ValueError('invalid RR background')
    matrices = dict(zip(('inverse_view_projection', 'view', 'projection', 'previous_view', 'previous_view_projection'),
                        (fields[9+i*16:25+i*16] for i in range(5))))
    return dict(version=version, width=width, height=height, stride=stride, frame_index=frame_index,
                random_index=random_index, seed=seed, reset=bool(reset), matrices=matrices, records=records)


def load_inputs(path):
    path = Path(path)
    if not HEADER.size+32<=path.stat().st_size<=MAX_FILE_BYTES:
        raise ValueError('RR input file size mismatch')
    return decode_inputs(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    data = load_inputs(args.path)
    rows = data.pop('records')
    data.update(primary_hits=sum(bool(r[23]) for r in rows), motion_valid=sum(bool(r[15]) for r in rows),
                rr_rendering=False, typed_textures=False, colour_space='linear-srgb', primary_jitter=[0, 0])
    print(json.dumps(data))


if __name__ == '__main__':
    main()
