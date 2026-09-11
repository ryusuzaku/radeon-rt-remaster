"""CPU-only coordinate-scale aggregation contract."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rr_coordinate_scales import summarize,SCALES,SETTINGS,TRAJECTORIES


def frame(i,value):
    return dict(all=dict(rr_mse=value),temporal=dict(rr_residual_mse=None if i in (0,4) else value),
                groups=dict(disoccluded=dict(rr_mse=None if i in (0,4) else value)))


def main():
    cases={}
    for surface in ('texture','pbr'):
        for trajectory in TRAJECTORIES:
            reports={}
            for si,scale in enumerate(SCALES):
                reports[scale]={}
                for fi,setting in enumerate(SETTINGS): reports[scale][setting]=dict(frames=[frame(i,10+si+fi) for i in range(8)])
            cases[f'{surface}-{trajectory}']=dict(trajectory=trajectory,reports=reports)
    result=summarize(cases)
    if result['scale_vs_unit_one']['none']['unit-tenth']['spatial']['improved']!=32: raise AssertionError(result)
    if result['scale_vs_unit_one']['none']['unit-ten']['late_temporal']['worsened']!=12: raise AssertionError(result)
    if result['zero_vs_default']['unit-one']['spatial']['worsened']!=32: raise AssertionError(result)
    changed=dict(cases); key=next(iter(changed)); changed[key]=dict(changed[key]); changed[key]['reports']=dict(changed[key]['reports']); changed[key]['reports']['unit-ten']={}
    try: summarize(changed)
    except (ValueError,KeyError): pass
    else: raise AssertionError('incomplete scale grid accepted')
    print('RR coordinate-scale aggregation contract passes')


if __name__=='__main__': main()
