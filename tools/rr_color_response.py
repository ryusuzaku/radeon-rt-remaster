"""Read-only spatial response diagnostics; fitted models are not corrections."""
import numpy as np
from rr_reference import require,WIDTH,HEIGHT,PIXELS


def response(reference,candidate,mask):
    reference=np.asarray(reference,dtype=np.float64); candidate=np.asarray(candidate,dtype=np.float64)
    mask=np.asarray(mask,dtype=bool)
    require(reference.shape==candidate.shape==(PIXELS,3) and mask.shape==(PIXELS,) and mask.any(),'response shape/coverage')
    require(np.all(np.isfinite(reference)) and np.all(np.isfinite(candidate)),'response nonfinite')
    a=reference[mask]; b=candidate[mask]; error=b-a
    centered_a=a-a.mean(axis=0); centered_b=b-b.mean(axis=0)
    energy_a=np.sum(centered_a**2,axis=0); energy_b=np.sum(centered_b**2,axis=0)
    def ratio(numerator,denominator):
        return [float(n/d) if d>1e-20 else None for n,d in zip(numerator,denominator)]
    # Fixed, predeclared hypotheses; output never overwrites candidate data.
    mse=float(np.mean(error**2)); scale=ratio(np.sum(a*b,axis=0),np.sum(b*b,axis=0))
    fits=[]; image=np.arange(PIXELS).reshape(HEIGHT,WIDTH)
    for dy in range(-2,3):
        for dx in range(-2,3):
            center=image[2:HEIGHT-2,2:WIDTH-2].ravel(); tap=center+dy*WIDTH+dx
            good=mask[center]&mask[tap]; center=center[good]; tap=tap[good]
            fits.append(dict(dx=dx,dy=dy,pixels=len(center),mse=float(np.mean((reference[center]-candidate[tap])**2)) if len(center) else None))
    return dict(pixels=int(mask.sum()),mse=mse,max_absolute_error=float(np.max(np.abs(error))),
                reference_mean=a.mean(axis=0).tolist(),candidate_mean=b.mean(axis=0).tolist(),bias=error.mean(axis=0).tolist(),
                centered_gain=ratio(np.sum(centered_a*centered_b,axis=0),energy_a),
                correlation=ratio(np.sum(centered_a*centered_b,axis=0),np.sqrt(energy_a*energy_b)),
                diagnostic_candidate_scale=scale,red_blue_swap_mse=float(np.mean((b[:,::-1]-a)**2)),
                fixed_offset_scan=fits,interpretation='diagnostic only; no candidate transformation or quality promotion')
