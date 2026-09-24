"""CPU-only longer-history aggregation contract."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rr_setting_histories import history_summary,TRAJECTORIES
from rr_setting_surfaces import PRESETS,SEEDS


def frame(index,spatial,temporal,disoccluded):
    return dict(index=index,all=dict(rr_mse=spatial),temporal=dict(rr_residual_mse=temporal),groups=dict(disoccluded=dict(rr_mse=disoccluded)))


def main():
    cases={}
    for surface in ('texture','pbr'):
        for trajectory in TRAJECTORIES:
            for seed in SEEDS:
                reports={}
                for preset in PRESETS:
                    delta={'none':0,'stability-half':-1,'stability-zero':1}[preset]
                    rows=[]
                    for i in range(8):
                        reset=i==0 or trajectory=='reset' and i==4
                        rows.append(frame(i,10 if reset else 10+delta,None if reset else 10-delta,
                                          None if trajectory=='stationary' or reset else 10+delta))
                    reports[preset]=dict(frames=rows)
                cases[f'{surface}-{trajectory}-seed-{seed}']=dict(trajectory=trajectory,reports=reports)
    result=history_summary(cases)
    half=result['stability-half']; zero=result['stability-zero']
    if half['stationary']['all_spatial']['improved']!=42 or half['stationary']['all_spatial']['equal']!=6: raise AssertionError(result)
    if half['moving']['all_temporal']['worsened']!=42 or half['reset']['all_temporal']['worsened']!=36: raise AssertionError(result)
    if half['reset_frame_spatial']['equal']!=6 or half['reset']['late_spatial']['improved']!=18: raise AssertionError(result)
    if zero['moving']['all_spatial']['worsened']!=42 or zero['moving']['all_disoccluded']['worsened']!=42: raise AssertionError(result)
    changed=dict(cases); key='texture-moving-seed-1'; changed[key]=dict(changed[key]); changed[key]['reports']=dict(changed[key]['reports']); changed[key]['reports']['stability-zero']=dict(frames=[])
    try: history_summary(changed)
    except ValueError: pass
    else: raise AssertionError('mismatched history accepted')
    print('RR longer-history aggregation contract passes')


if __name__=='__main__': main()
