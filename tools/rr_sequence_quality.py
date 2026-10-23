"""Bounded post-disocclusion age diagnostics on matched RR reference arrays.

A cohort starts at geometric disocclusion and survives only through compatible
nearest-pixel correspondences. Resets clear it. This is a spatial error measure
over approximate tracks, not proof of ghost-free reconstruction.
"""
import numpy as np

from rr_quality import errors
from rr_reference import Reference, PIXELS, require


def advance_ages(previous, masks, mapping, reset):
    previous=np.asarray(previous); masks=np.asarray(masks); mapping=np.asarray(mapping)
    require(previous.shape==(PIXELS,) and previous.dtype.kind=='i' and
            np.all((previous>=-1)&(previous<=7)), 'invalid reveal ages')
    require(masks.shape==(4,PIXELS) and masks.dtype==np.bool_ and
            np.all(masks.sum(axis=0)<=1), 'invalid visibility partition')
    require(mapping.shape==(PIXELS,) and mapping.dtype.kind in 'iu' and
            np.all((mapping>=0)&(mapping<PIXELS)), 'invalid previous-pixel mapping')
    require(type(reset) is bool, 'invalid reset flag')
    result=np.full(PIXELS,-1,dtype=np.int8)
    if reset:
        require(not masks.any(), 'reset has temporal visibility')
        return result
    result[masks[1]]=0
    stable=np.flatnonzero(masks[0]); ages=previous[mapping[stable]]
    tracked=ages>=0
    require(np.all(ages[tracked]<7), 'reveal history exceeds eight frames')
    result[stable[tracked]]=ages[tracked]+1
    return result


def history_metrics(raw, candidate, mean, variance, ages):
    return [dict(age=age,**errors(raw,candidate,mean,variance,ages==age))
            for age in range(8)]


def history_gates(frames):
    # Missing cohorts stay unevaluated; they cannot produce a vacuous pass.
    tracked=[entry for frame in frames for entry in frame['ages']
             if entry['age']>0 and entry['pixels']]
    return dict(post_reveal_non_regression=all(e['rr_mse']<=e['raw_mse'] for e in tracked) if tracked else None,
                post_reveal_reference_noise_small=all(e['reference_noise_small'] for e in tracked) if tracked else None)


def measure_history(scene, data, rows, arrays):
    count=data['count']
    require(count==len(data['frames'])==len(rows)==8, 'history requires eight frames')
    for name in ('mean','mean_variance','batch_difference'):
        value=np.asarray(arrays[name])
        require(value.shape==(count,PIXELS,3) and np.isfinite(value).all(), 'invalid reference arrays')
    require(np.all(arrays['mean_variance']>=0), 'negative reference variance')
    visibility=np.asarray(arrays['visibility_masks'])
    require(visibility.shape==(count,4,PIXELS) and visibility.dtype==np.bool_, 'invalid visibility arrays')
    tracer=Reference(scene,data['settings']); primary=[tracer.primary(frame) for frame in data['frames']]
    previous=np.full(PIXELS,-1,dtype=np.int8); age_rows=[]; frames=[]
    for i,(frame,hit,pixels) in enumerate(zip(data['frames'],primary,rows)):
        masks,mapping=tracer.visibility(hit,primary[i-1] if i else hit,frame,data['frames'][i-1] if i else frame)
        observed=np.stack([masks[key] for key in ('stable','disoccluded','offscreen','unmatched')])
        require(np.array_equal(observed,visibility[i]), 'reference visibility changed')
        previous=advance_ages(previous,observed,mapping,frame['reset'])
        raw=np.asarray(frame['records'])[:,:3].astype(np.float16).astype(np.float64)
        rr=np.asarray(pixels)[:,:3]
        require(rr.shape==raw.shape and np.isfinite(rr).all(), 'invalid history candidate')
        frames.append(dict(index=i,reset=frame['reset'],ages=history_metrics(
            raw,rr,arrays['mean'][i],arrays['mean_variance'][i],previous)))
        age_rows.append(previous)
    report=dict(schema='rr-sequence-quality-1',quality_acceptance='not-qualified',frames=frames,
                gates=history_gates(frames),
                method='geometric reveal cohorts propagated only through stable nearest-pixel correspondences; reset clears cohorts',
                limitation='approximate tracks may duplicate or lose points; eight frames do not establish absence of longer-lived ghosting')
    return report,np.stack(age_rows)
