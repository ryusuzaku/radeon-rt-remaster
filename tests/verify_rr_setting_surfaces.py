"""CPU-only aggregation and comparison admission checks."""
import argparse
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

from rr_setting_surfaces import paired_summary,PRESETS,seed_fingerprints
from rr_quality import analyze_comparison,analyze,_analyze


def frame(index,spatial,temporal,disoccluded):
    return dict(index=index,all=dict(rr_mse=spatial),temporal=dict(rr_residual_mse=temporal),groups=dict(disoccluded=dict(rr_mse=disoccluded)))


def rejects(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('invalid comparison input accepted')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-prefix',type=Path)
    for key in ('scene','shader','materials'): parser.add_argument('--'+key,type=Path)
    args=parser.parse_args()
    cases={}
    for case in ('texture-seed-1','pbr-seed-1'):
        cases[case]=dict(reports={
            'none':dict(frames=[frame(0,4,None,None),frame(1,4,4,4)]),
            'stability-half':dict(frames=[frame(0,4,None,None),frame(1,2,5,3)]),
            'stability-zero':dict(frames=[frame(0,4,None,None),frame(1,5,2,4)])})
    summary=paired_summary(cases)
    if summary['stability-half']['spatial']!=dict(comparisons=4,improved=2,equal=2,worsened=0,mean_delta=-1.,median_delta=-1.): raise AssertionError(summary)
    if summary['stability-half']['temporal']['worsened']!=2 or summary['stability-half']['disoccluded']['improved']!=2: raise AssertionError(summary)
    if summary['stability-zero']['spatial']['worsened']!=2 or summary['stability-zero']['disoccluded']['equal']!=2: raise AssertionError(summary)
    changed={k:dict(v) for k,v in cases.items()}; changed['pbr-seed-1']=dict(changed['pbr-seed-1']); changed['pbr-seed-1']['reports']=dict(changed['pbr-seed-1']['reports'])
    changed['pbr-seed-1']['reports']['stability-zero']=dict(frames=[])
    rejects(lambda:paired_summary(changed))
    rejects(lambda:analyze_comparison('missing',{'none':()},'missing','missing'))
    rejects(lambda:analyze_comparison('missing',{p:() for p in PRESETS},'missing','missing'))
    data=dict(frames=[dict(records=[list(range(24))],matrices=dict(view=list(range(16))))])
    signal,guides=seed_fingerprints(data)
    changed=copy.deepcopy(data); changed['frames'][0]['records'][0][3]+=1
    if seed_fingerprints(changed)[0]==signal or seed_fingerprints(changed)[1]!=guides: raise AssertionError('sampled distance classified as fixed guide')
    changed=copy.deepcopy(data); changed['frames'][0]['records'][0][8]+=1
    if seed_fingerprints(changed)[1]==guides: raise AssertionError('normal change not detected')
    changed=copy.deepcopy(data); changed['frames'][0]['matrices']['view'][0]+=1
    if seed_fingerprints(changed)[1]==guides: raise AssertionError('camera change not detected')
    print('RR surface-setting comparison contract passes')
    if args.case_prefix:
        if args.scene is None or args.shader is None: raise ValueError('integration check requires scene and shader')
        prefix=str(args.case_prefix); recording=Path(prefix+'.rrcapture')
        candidates={p:(Path(prefix+'-'+p+'.rrrecordout'),Path(prefix+'-'+p+'-execution.json')) for p in PRESETS}
        from rr_surface_reference import SurfaceReference
        original=SurfaceReference.estimate; calls=[]
        def counted(self,*values):
            calls.append(values[-1]); return original(self,*values)
        with patch.object(SurfaceReference,'estimate',counted):
            reports,arrays=analyze_comparison(recording,candidates,args.scene,args.shader,samples=64,surface_reference=True,materials=args.materials)
        expected=list(range(len(reports['none']['frames'])))
        if calls!=expected: raise AssertionError(('cached estimate count',calls))
        calls=[]
        with patch.object(SurfaceReference,'estimate',counted):
            for preset,(output,execution) in candidates.items():
                report,reference=analyze(recording,output,args.scene,args.shader,execution,samples=64,surface_reference=True,
                                         materials=args.materials,fallback=True,filter_setting=preset)
                if report!=reports[preset] or set(reference)!=set(arrays) or any(not np.array_equal(reference[k],arrays[k]) for k in arrays):
                    raise AssertionError(('cached/uncached mismatch',preset))
        if calls!=expected*3: raise AssertionError(('independent estimate count',calls))
        output,execution=candidates['none']
        rejects(lambda:_analyze(recording,output,args.scene,args.shader,execution,samples=64,surface_reference=True,
                                 materials=args.materials,fallback=True,_estimates={'identity':('changed',)}))
        changed=dict(candidates); changed['stability-half']=candidates['stability-zero']
        rejects(lambda:analyze_comparison(recording,changed,args.scene,args.shader,samples=64,surface_reference=True,materials=args.materials))
        result=dict(result='pass',case_prefix=prefix,cached_reference_calls=len(expected),independent_reference_calls=len(expected)*3,
                    exact_report_array_pairs=3,rejected_cache_or_preset_mismatches=2)
        destination=Path(prefix+'-comparison-validation.json')
        with destination.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
        print(json.dumps(result))


if __name__=='__main__': main()
