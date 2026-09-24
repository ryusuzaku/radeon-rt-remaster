"""Float64 CPU port of presentationColor's default 5x5 spatial algorithm.

Applied to matched RR indirect RGB/guides, not the legacy renderer image. No
temporal/variance filter; no claim of GPU bit equivalence or runtime timing.
"""
import numpy as np
from rr_reference import require

SHADER_SOURCE_SHA256='95cf0738709b136f9b4676ea04b3a6ee44441f7370c30e29f341760ca4535a36'


def spatial(frame,radiance,primary):
    rows=np.asarray(frame['records']); value=np.asarray(radiance,dtype=np.float64)
    width,height=frame['width'],frame['height']; pixels=width*height
    require((width,height) in ((128,96),(256,192)) and rows.shape==(pixels,24) and value.shape==(pixels,3) and np.all(np.isfinite(value)),'fallback input invalid')
    # Legacy guide depth is primary ray T, not RR view Z; its albedo is base
    # surface colour, not RR colour*(1-metallic). Obtain both at matched hits.
    normal=primary['normal']; depth=primary['distance']; albedo=primary['color']
    require(np.array_equal(primary['draw'],rows[:,23]),'fallback primary identity mismatch')
    require(normal.shape==albedo.shape==(pixels,3) and depth.shape==(pixels,) and all(np.all(np.isfinite(v)) for v in (normal,depth,albedo)),'fallback guides invalid')
    total=np.zeros_like(value); weight_sum=np.zeros(pixels); image=np.arange(pixels).reshape(height,width)
    for y in range(-2,3):
        for x in range(-2,3):
            c=image[max(0,-y):min(height,height-y),max(0,-x):min(width,width-x)].ravel()
            tap=c+y*width+x
            valid=(rows[c,23]>0)&(rows[tap,23]==rows[c,23])
            valid &= np.einsum('ij,ij->i',normal[c],normal[tap])>=.95
            valid &= np.abs(depth[tap]-depth[c])<=np.maximum(.005,.02*depth[c])
            valid &= np.all(np.abs(albedo[tap]-albedo[c])<=.1,axis=1)
            c=c[valid]; tap=tap[valid]; weight=np.exp(-(x*x+y*y)/2.88)
            total[c]+=value[tap]/np.maximum(albedo[tap],.05)*weight; weight_sum[c]+=weight
    result=value.copy(); hit=rows[:,23]>0
    result[hit]=total[hit]/np.maximum(weight_sum[hit,None],1e-8)*np.maximum(albedo[hit],.05)
    return result
