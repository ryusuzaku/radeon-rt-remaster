"""Validate renderer-owned RR recordings; no SDK admission or quality claim."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct

from inspect_rr_inputs import decode_inputs,FILE_BYTES,FILE_BYTES_V2,MAX_FILE_BYTES

PREFIX=236
METADATA=struct.Struct('<4I5f')
STRIDE=METADATA.size+FILE_BYTES
MAX_BYTES=PREFIX+8*(METADATA.size+MAX_FILE_BYTES)+32


def f32(x): return struct.unpack('<f',struct.pack('<f',x))[0]
def transform(v,m): return tuple(sum(v[k]*m[k*4+j] for k in range(4)) for j in range(4))
def multiply(a,b): return tuple(sum(a[r*4+k]*b[k*4+c] for k in range(4)) for r in range(4) for c in range(4))
def close(a,b): return all(abs(x-y)<=.0005*max(1,abs(x),abs(y)) for x,y in zip(a,b))


def decode_record(raw):
    if not PREFIX+2*(METADATA.size+min(FILE_BYTES,FILE_BYTES_V2))+32<=len(raw)<=MAX_BYTES: raise ValueError('recording size invalid')
    magic,version,count,stride,settings_size=struct.unpack_from('<8s4I',raw)
    expected={(b'RRTRRC01',1):FILE_BYTES,(b'RRTRRC02',2):FILE_BYTES_V2}.get((magic,version))
    if expected is None or stride!=expected or settings_size!=84 or not 2<=count<=8:
        raise ValueError('recording header invalid')
    frame_stride=METADATA.size+stride
    if len(raw)!=PREFIX+count*frame_stride+32 or sha256(raw[:-32]).digest()!=raw[-32:]:
        raise ValueError('recording checksum/length mismatch')
    if sha256(raw[120:204]).digest()!=raw[204:236]: raise ValueError('settings checksum mismatch')
    mode,seed,shadows,reset_frame,*values=struct.unpack_from('<4I17f',raw,120)
    if mode!=3 or shadows not in (0,1) or reset_frame!=0xffffffff and not 1<=reset_frame<count:
        raise ValueError('recording settings invalid')
    if not all(math.isfinite(v) for v in values): raise ValueError('nonfinite settings')
    light=values[:3]; color=values[3:6]; intensity,ambient,radius=values[6:9]; pose=values[9:14]; step=values[14:17]
    if any(abs(v)>=1000 for v in light) or sum(v*v for v in light)<=1e-12 or any(not 0<=v<=32 for v in color+[intensity,ambient]) or not 0<=radius<=1:
        raise ValueError('lighting settings invalid')
    if any(abs(v)>=1e5 for v in pose[:3]) or abs(pose[3])>360 or abs(pose[4])>89 or any(abs(v)>2 for v in step):
        raise ValueError('trajectory settings invalid')
    if raw[24:56]==bytes(32) or raw[88:120]==bytes(32): raise ValueError('missing scene/shader identity')
    parts=[]; frames=[]; metadata=[]; segment=0; previous_pose=pose
    for i in range(count):
        start=PREFIX+i*frame_stride; ordinal,index,reason,reserved,*actual_pose=METADATA.unpack_from(raw,start)
        expected_pose=[f32(pose[k]+f32(i*step[k])) for k in range(3)]+pose[3:]
        if actual_pose!=expected_pose: raise ValueError('frame pose mismatch')
        distance=0
        for a,b in zip(actual_pose[:3],previous_pose[:3]): distance=f32(distance+f32(f32(a-b)**2))
        expected_reason=(1 if i==0 else 0)|(2 if i==reset_frame else 0)|(4 if i and distance>1 else 0)
        if reason: segment=0
        if (ordinal,index,reason,reserved)!=(i,segment,expected_reason,0) or actual_pose!=expected_pose:
            raise ValueError('frame trajectory/reset metadata mismatch')
        part=raw[start+METADATA.size:start+frame_stride]; frame=decode_inputs(part); m=frame['matrices']
        if (frame['frame_index'],frame['random_index'],frame['seed'],frame['reset'])!=(i,segment,seed,bool(reason)):
            raise ValueError('frame identity/index/reset mismatch')
        vp=multiply(m['view'],m['projection'])
        if not close(multiply(vp,m['inverse_view_projection']),[float(r==c) for r in range(4) for c in range(4)]):
            raise ValueError('camera inverse mismatch')
        if i and m['projection']!=frames[0]['matrices']['projection']: raise ValueError('projection changed')
        previous=m if reason else frames[i-1]['matrices']
        if not close(m['previous_view'],previous['view']) or not close(m['previous_view_projection'],multiply(previous['view'],previous['projection'])):
            raise ValueError('previous camera continuity mismatch')
        for pixel,row in enumerate(frame['records']):
            if not row[23]: continue
            position=(*row[20:23],1)
            if not close([transform(position,m['view'])[2]],[row[19]]): raise ValueError('view depth mismatch')
            clip=transform(position,m['previous_view_projection'])
            valid=not reason and clip[3]>1e-8
            if bool(row[15])!=valid: raise ValueError('motion validity mismatch')
            if valid:
                width,height=frame['width'],frame['height']
                motion=(clip[0]/clip[3]*.5+.5-(pixel%width+.5)/width,.5-clip[1]/clip[3]*.5-(pixel//width+.5)/height,
                        transform(position,m['previous_view'])[2]-row[19])
                if not close(row[16:19],motion): raise ValueError('motion reprojection mismatch')
        parts.append(part); frames.append(frame); metadata.append(dict(ordinal=i,segment_index=segment,reset_reason=reason,pose=actual_pose))
        segment+=1; previous_pose=actual_pose
    return dict(version=version,count=count,width=frames[0]['width'],height=frames[0]['height'],scene_sha256=raw[24:56].hex(),material_sha256=raw[56:88].hex(),shader_sha256=raw[88:120].hex(),
                settings_sha256=raw[204:236].hex(),frames=frames,parts=parts,metadata=metadata,settings=dict(seed=seed,shadows=bool(shadows),
                reset_frame=reset_frame,light=light,color=color,intensity=intensity,ambient=ambient,radius=radius,pose=pose,step=step))


def load_record(path):
    with Path(path).open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    return decode_record(raw)


def verify_source(path,expected,*,trailer=False):
    path=Path(path); size=path.stat().st_size
    if not 32<=size<=512*1024*1024: raise ValueError('source size invalid')
    remaining=size-(32 if trailer else 0); digest=sha256()
    with path.open('rb') as stream:
        while remaining:
            block=stream.read(min(remaining,1024*1024))
            if not block: raise ValueError('source truncated')
            digest.update(block); remaining-=len(block)
        if trailer and stream.read(32)!=digest.digest(): raise ValueError('source scene checksum mismatch')
        if stream.read(1): raise ValueError('source length changed')
    if digest.hexdigest()!=expected: raise ValueError('source identity mismatch')


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('path',type=Path)
    for key in ('scene','materials','shader'): parser.add_argument('--'+key,type=Path)
    args=parser.parse_args()
    try:
        data=load_record(args.path); verified=[]
        for key,digest in [('scene','scene_sha256'),('materials','material_sha256'),('shader','shader_sha256')]:
            if getattr(args,key): verify_source(getattr(args,key),data[digest],trailer=key=='scene'); verified.append(key)
        data.pop('frames'); data.pop('parts'); data.update(rr_rendering=False,worker_admitted=False,verified_sources=verified)
        print(json.dumps(data)); return 0
    except (OSError,ValueError,OverflowError) as error:
        print(json.dumps(dict(result='invalid',reason=str(error)))); return 1


if __name__=='__main__': raise SystemExit(main())
