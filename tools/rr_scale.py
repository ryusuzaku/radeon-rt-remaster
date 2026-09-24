"""Fixed coherent scene-unit presets for recorded RR research."""
import math
import struct

PRESETS=('none','unit-tenth','unit-one','unit-ten')
_VALUES=(1.0,0.1,1.0,10.0)


def validate_scale(name):
    if type(name) is not str or name not in PRESETS:
        raise ValueError('unknown coordinate scale preset')
    index=PRESETS.index(name)
    return index,_VALUES[index]


def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def scaled(value,scale):
    return f32(f32(value)*f32(scale))


def scaled_distance(value,scale):
    if value<0: return value
    # Exact ray TMax means no committed secondary hit. Keep the unbounded
    # sentinel at FP16 max instead of turning it into a finite scene length.
    return 65504.0 if value>=100000 else min(scaled(value,scale),65504.0)


def scaled_matrices(matrices,scale):
    if type(matrices) is not dict or set(('view','projection'))-set(matrices):
        raise ValueError('missing camera matrices')
    view=list(matrices['view']); projection=list(matrices['projection'])
    if len(view)!=16 or len(projection)!=16 or not all(math.isfinite(x) for x in view+projection):
        raise ValueError('invalid camera matrices')
    # Row-vector homogeneous unit transform:
    # V' = S^-1 V S; P' = S^-1 (sP), S=diag(s,s,s,1).
    view=[scaled(x,(scale if c<3 else 1)/(scale if r<3 else 1)) for r in range(4) for c,x in enumerate(view[r*4:r*4+4])]
    projection=[scaled(x,scale if r==3 else 1) for r in range(4) for x in projection[r*4:r*4+4]]
    return view,projection
