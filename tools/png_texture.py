"""Bounded PNG texture decoding: non-interlaced 8-bit RGB/RGBA, all five filters.

Pixel values are imported literally; colour profiles/gamma are not transformed.
Unknown critical chunks, palette/transparency extensions and animation fail closed.
"""
import struct
import zlib
from scene_io import require


def decode_png(data):
    require(len(data) <= 20*1024*1024 and data[:8] == b'\x89PNG\r\n\x1a\n', 'invalid PNG signature or file size')
    cursor, header, ended, idat_closed = 8, None, False, False
    compressed = bytearray()
    seen_idat = False
    while cursor < len(data):
        require(cursor + 12 <= len(data), 'truncated PNG chunk')
        size, kind = struct.unpack_from('>I4s', data, cursor)
        require(size <= len(data)-cursor-12, 'PNG chunk length exceeds file')
        chunk = data[cursor+8:cursor+8+size]
        checksum = struct.unpack_from('>I', data, cursor+8+size)[0]
        require(zlib.crc32(kind+chunk) == checksum, 'PNG CRC mismatch')
        require(all(65 <= c <= 90 or 97 <= c <= 122 for c in kind) and 65 <= kind[2] <= 90, 'invalid PNG chunk type')
        cursor += size+12
        require(header is not None or kind == b'IHDR', 'PNG must begin with IHDR')
        if kind == b'IHDR':
            require(header is None and size == 13, 'invalid or duplicate PNG header')
            header = struct.unpack('>2I5B', chunk)
            width, height, depth, color, compression, filtering, interlace = header
            require(0 < width <= 2048 and 0 < height <= 2048, 'PNG dimensions exceed texture budget')
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    'PNG requires non-interlaced 8-bit RGB or RGBA')
        elif kind == b'IDAT':
            require(not idat_closed, 'PNG IDAT chunks must be consecutive')
            seen_idat = True
            compressed.extend(chunk)
        elif kind == b'IEND':
            require(size == 0 and seen_idat and cursor == len(data), 'invalid PNG end or trailing data')
            ended = True
            break
        else:
            require(kind not in (b'tRNS', b'acTL', b'fcTL', b'fdAT') and kind[0] & 32, 'unsupported PNG chunk')
            if seen_idat:
                idat_closed = True
    require(ended, 'missing PNG end')
    width, height, _, color, *_ = header
    channels = 4 if color == 6 else 3
    stride = width*channels
    expected = (stride+1)*height
    stream = zlib.decompressobj()
    raw = stream.decompress(compressed, expected+1)
    require(len(raw) == expected and stream.eof and not stream.unused_data and not stream.unconsumed_tail,
            'PNG decompressed size or stream mismatch')
    previous = bytearray(stride)
    bgra = bytearray(width*height*4)
    for y in range(height):
        at = y*(stride+1)
        filter_type = raw[at]
        require(filter_type <= 4, 'invalid PNG filter')
        row = bytearray(raw[at+1:at+1+stride])
        for x in range(stride):
            left = row[x-channels] if x >= channels else 0
            above = previous[x]
            upper_left = previous[x-channels] if x >= channels else 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left+above)//2
            elif filter_type == 4:
                p = left+above-upper_left
                distances = (abs(p-left), abs(p-above), abs(p-upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
            else:
                predictor = 0
            row[x] = (row[x]+predictor) & 255
        for x in range(width):
            p = x*channels
            bgra[(y*width+x)*4:(y*width+x+1)*4] = bytes((row[p+2], row[p+1], row[p], row[p+3] if channels == 4 else 255))
        previous = row
    return width, height, bytes(bgra)
