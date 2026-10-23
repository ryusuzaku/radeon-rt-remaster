import struct
from pathlib import Path
import sys
import unittest
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from png_texture import decode_png
from scene_io import SceneError

SIGNATURE=b'\x89PNG\r\n\x1a\n'

def chunk(kind,payload):
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))

def header(width,height,depth=8,color=2,compression=0,filtering=0,interlace=0):
    return chunk(b'IHDR',struct.pack('>2I5B',width,height,depth,color,compression,filtering,interlace))

def filters_row(row,previous,channels,kind):
    out=bytearray(len(row))
    for x in range(len(row)):
        left=row[x-channels] if x>=channels else 0
        above=previous[x]
        upper_left=previous[x-channels] if x>=channels else 0
        if kind==1: predictor=left
        elif kind==2: predictor=above
        elif kind==3: predictor=(left+above)//2
        elif kind==4:
            p=left+above-upper_left
            distances=(abs(p-left),abs(p-above),abs(p-upper_left))
            predictor=(left,above,upper_left)[distances.index(min(distances))]
        else: predictor=0
        out[x]=(row[x]-predictor)&255
    return bytes(out)

def png(width,height,pixels,color=2,kinds=None,idat=None):
    channels=4 if color==6 else 3
    kinds=kinds or [0]*height
    raw,previous=bytearray(),bytes(width*channels)
    for y in range(height):
        row=b''.join(bytes(p) for p in pixels[y*width:(y+1)*width])
        raw+=bytes((kinds[y],))+filters_row(row,previous,channels,kinds[y])
        previous=row
    body=idat if idat is not None else zlib.compress(bytes(raw))
    return SIGNATURE+header(width,height,color=color)+chunk(b'IDAT',body)+chunk(b'IEND',b'')

def bgra(*pixels):
    return b''.join(bytes((p[2],p[1],p[0],p[3] if len(p)==4 else 255)) for p in pixels)

class DecodeTests(unittest.TestCase):
    def test_rgb_all_filters(self):
        pixels=[(10+7*i,20+11*i,30+13*i) for i in range(18)]
        width,height,result=decode_png(png(3,6,pixels,kinds=[0,1,2,3,4,0]))
        self.assertEqual((width,height),(3,6))
        self.assertEqual(result,bgra(*pixels))
    def test_rgba_alpha_kept(self):
        pixels=[(1,2,3,4),(5,6,7,8),(9,10,11,12),(13,14,15,16)]
        width,height,result=decode_png(png(2,2,pixels,color=6,kinds=[4,4]))
        self.assertEqual((width,height),(2,2))
        self.assertEqual(result,bgra(*pixels))
        self.assertEqual(result[3::4],bytes((4,8,12,16)))
    def test_single_pixel_and_split_idat(self):
        body=zlib.compress(b'\x00\x11\x22\x33')
        data=(SIGNATURE+header(1,1)+chunk(b'IDAT',body[:2])+chunk(b'IDAT',body[2:])+chunk(b'IEND',b''))
        self.assertEqual(decode_png(data),(1,1,bytes((0x33,0x22,0x11,255))))
    def test_ancillary_chunks_allowed(self):
        pixels=[(1,2,3),(4,5,6)]
        data=(SIGNATURE+header(2,1)+chunk(b'tEXt',b'k\x00v')+chunk(b'IDAT',zlib.compress(b'\x00'+bytes((1,2,3,4,5,6))))
              +chunk(b'tIME',b'\x00'*7)+chunk(b'IEND',b''))
        self.assertEqual(decode_png(data)[2],bgra(*pixels))
    def test_bad_signature(self):
        for data in (b'',b'\x89PNG',b'GIF89a'+png(1,1,[(0,0,0)])[6:],png(1,1,[(0,0,0)]).replace(b'\x89PNG\r\n\x1a\n',b'\x89PNG\r\n\x1a\x0b')):
            with self.subTest(data=data[:8]):
                with self.assertRaises(SceneError): decode_png(data)
    def test_truncated_chunk(self):
        good=png(1,1,[(1,2,3)])
        for cut in (9,12,20,33,len(good)-13,len(good)-1):
            with self.subTest(cut=cut):
                with self.assertRaises(SceneError): decode_png(good[:cut])
        with self.assertRaises(SceneError): decode_png(good+b'\x00'*4)
    def test_chunk_length_exceeds_file(self):
        data=bytearray(png(1,1,[(1,2,3)]))
        struct.pack_into('>I',data,8,0x7fffffff)
        with self.assertRaises(SceneError): decode_png(bytes(data))
    def test_bad_crc(self):
        good=bytearray(png(1,1,[(1,2,3)]))
        good[-1]^=0xff
        with self.assertRaises(SceneError): decode_png(bytes(good))
        body=bytearray(png(1,1,[(1,2,3)]))
        body[30]^=0x01  # inside the IHDR CRC, dimensions stay valid
        with self.assertRaises(SceneError): decode_png(bytes(body))
    def test_oversize_and_empty_dimensions(self):
        for width,height in ((2049,1),(1,2049),(0,1),(1,0),(0xffffffff,1)):
            with self.subTest(width=width,height=height):
                data=(SIGNATURE+header(width,height)+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00'))
                      +chunk(b'IEND',b''))
                with self.assertRaises(SceneError): decode_png(data)
    def test_unsupported_header_fields(self):
        for fields in (dict(depth=16),dict(depth=4),dict(color=0),dict(color=4),dict(color=3),
                       dict(compression=1),dict(filtering=1),dict(interlace=1)):
            with self.subTest(**fields):
                data=(SIGNATURE+header(1,1,**fields)+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00'))
                      +chunk(b'IEND',b''))
                with self.assertRaises(SceneError): decode_png(data)
    def test_unsupported_and_misplaced_chunks(self):
        base=header(1,1)
        for kind in (b'tRNS',b'acTL',b'fcTL',b'fdAT',b'ZZZZ',b'zZzZ'):
            with self.subTest(kind=kind):
                data=(SIGNATURE+base+chunk(kind,b'')+chunk(b'IDAT',zlib.compress(b'\x00\x01\x02\x03'))
                      +chunk(b'IEND',b''))
                with self.assertRaises(SceneError): decode_png(data)
        split=(SIGNATURE+base+chunk(b'IDAT',zlib.compress(b'\x00\x01\x02\x03')[:1])+chunk(b'tEXt',b'')
               +chunk(b'IDAT',zlib.compress(b'\x00\x01\x02\x03')[1:])+chunk(b'IEND',b''))
        with self.assertRaises(SceneError): decode_png(split)
    def test_missing_or_invalid_end(self):
        body=zlib.compress(b'\x00\x01\x02\x03')
        for data in (SIGNATURE+header(1,1)+chunk(b'IDAT',body),
                     SIGNATURE+header(1,1)+chunk(b'IEND',b''),
                     SIGNATURE+header(1,1)+chunk(b'IDAT',body)+chunk(b'IEND',b'x'),
                     SIGNATURE+header(1,1)+chunk(b'IDAT',body)+chunk(b'IEND',b'')+b'\x00'):
            with self.subTest(length=len(data)):
                with self.assertRaises(SceneError): decode_png(data)
        with self.assertRaises(SceneError): decode_png(SIGNATURE+chunk(b'IEND',b''))
    def test_stream_and_filter_mismatch(self):
        def build(body):
            return SIGNATURE+header(1,1)+chunk(b'IDAT',body)+chunk(b'IEND',b'')
        cases=(b'',zlib.compress(b'\x00\x01\x02'),zlib.compress(b'\x00\x01\x02\x03\x04'),
               zlib.compress(b'\x05\x01\x02\x03'),zlib.compress(b'\x00\x01\x02\x03')+b'junk',
               zlib.compress(b'\x00\x01\x02\x03')[:-2])
        for body in cases:
            with self.subTest(body=body[:4]):
                with self.assertRaises(SceneError): decode_png(build(body))
        for body in (b'\x00\x01\x02\x03',b'not a zlib stream'):
            with self.subTest(body=body[:4]):
                with self.assertRaises(zlib.error): decode_png(build(body))

if __name__ == '__main__': unittest.main()
