"""Eight-frame textured/PBR stability histories; no setting promotion."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import time
import numpy as np

from inspect_rr_record import MAX_BYTES
from rr_recorded_dispatch import admit_record,run_recording
from rr_quality import analyze_comparison
from rr_setting_surfaces import SEEDS,PRESETS,require,seed_fingerprints

TRAJECTORIES={
    'stationary':(),
    'moving':('--rr-step','.04','0','0'),
    'reset':('--rr-step','.04','0','0','--rr-reset-frame','4'),
}


def counts(values):
    require(values,'missing paired measurements')
    return dict(comparisons=len(values),improved=sum(v<0 for v in values),equal=sum(v==0 for v in values),worsened=sum(v>0 for v in values),
                mean_delta=float(np.mean(values)),median_delta=float(np.median(values)),minimum_delta=float(np.min(values)),maximum_delta=float(np.max(values)))


def deltas(selected,preset,indices,name):
    values=[]
    for case in selected:
        a=case['reports']['none']['frames']; b=case['reports'][preset]['frames']; require(len(a)==len(b)==8,'history frame count changed')
        for index in indices:
            if name=='spatial': before,after=a[index]['all']['rr_mse'],b[index]['all']['rr_mse']
            elif name=='temporal': before,after=a[index]['temporal']['rr_residual_mse'],b[index]['temporal']['rr_residual_mse']
            else: before,after=a[index]['groups']['disoccluded']['rr_mse'],b[index]['groups']['disoccluded']['rr_mse']
            require((before is None)==(after is None),'paired metric availability changed')
            if before is not None: values.append(after-before)
    return values


def history_summary(cases):
    result={}
    for preset in PRESETS[1:]:
        result[preset]={}
        for trajectory in TRAJECTORIES:
            selected=[case for case in cases.values() if case['trajectory']==trajectory]
            require(len(selected)==6,'trajectory case count changed')
            late=range(5,8) if trajectory=='reset' else range(4,8)
            result[preset][trajectory]={
                'all_spatial':counts(deltas(selected,preset,range(8),'spatial')),
                'all_temporal':counts(deltas(selected,preset,range(8),'temporal')),
                'late_spatial':counts(deltas(selected,preset,late,'spatial')),
                'late_temporal':counts(deltas(selected,preset,late,'temporal')),
            }
            if trajectory!='stationary':
                result[preset][trajectory]['all_disoccluded']=counts(deltas(selected,preset,range(8),'disoccluded'))
                result[preset][trajectory]['late_disoccluded']=counts(deltas(selected,preset,late,'disoccluded'))
        reset=[case for case in cases.values() if case['trajectory']=='reset']
        result[preset]['reset_frame_spatial']=counts(deltas(reset,preset,[4],'spatial'))
    return result


def audit(cases):
    for surface in ('texture','pbr'):
        for trajectory in TRAJECTORIES:
            selected=[cases[f'{surface}-{trajectory}-seed-{seed}'] for seed in SEEDS]
            require(len({case['recording_sha256'] for case in selected})==3,'seed did not change recording')
            require(len({case['signal_sha256'] for case in selected})==3,'seed did not change stochastic signal')
            require(len({case['guide_camera_sha256'] for case in selected})==1,'seed changed guides/camera')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512),default=512)
    args=parser.parse_args(); started=time.monotonic(); require(8*args.samples<=4096,'reference work budget')
    for path in (args.probe,args.dxr,args.scene,args.materials): require(path.is_file(),f'missing input: {path}')
    require(args.sdk_bin.is_dir(),'missing SDK bin directory')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; require(shader.is_file(),'missing RR input shader')
    folder=Path(tempfile.mkdtemp(prefix='rr-setting-histories-',dir=args.probe.resolve().parent)); cases={}
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None
        for trajectory,options in TRAJECTORIES.items():
            for input_seed in SEEDS:
                label=f'{surface}-{trajectory}-seed-{input_seed}'; print(label+': capture',flush=True)
                recording=folder/(label+'.rrcapture')
                command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','8','--seed',str(input_seed),
                         '--rr-record',str(recording),'--debug',*options]
                if material: command+=['--materials',str(material)]
                process=subprocess.run(command,capture_output=True,text=True,timeout=60)
                require(process.returncode==0,('capture failed',label,process.stdout,process.stderr))
                with recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
                data=admit_record(raw); expected=[0,4] if trajectory=='reset' else [0]
                require(data['count']==8 and data['settings']['seed']==input_seed and [i for i,f in enumerate(data['frames']) if f['reset']]==expected,
                        'capture history/reset contract changed')
                require(data['material_sha256']!=('0'*64) if material else data['material_sha256']==('0'*64),'material provenance changed')
                signal_hash,guide_hash=seed_fingerprints(data); candidates={}
                for preset in PRESETS:
                    print(f'{label}: {preset} dispatch',flush=True)
                    output=folder/f'{label}-{preset}.rrrecordout'; execution=folder/f'{label}-{preset}-execution.json'
                    worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                         query_defaults=True,filter_setting=preset)
                    execution.write_text(json.dumps(worker),encoding='utf-8')
                    require(worker['input_sha256']==raw[-32:].hex() and worker['decision']['rr_rendering'],'history execution failed; evidence retained')
                    candidates[preset]=(output,execution)
                reports,arrays=analyze_comparison(recording,candidates,args.scene,shader,samples=args.samples,surface_reference=True,materials=material,
                                                  progress=lambda i,n,label=label:print(f'{label} reference {i+1}/{n}',flush=True))
                reference=folder/(label+'-reference.npz')
                with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
                reference_hash=sha256(reference.read_bytes()).hexdigest()
                for preset,report in reports.items():
                    report['reference_file_sha256']=reference_hash
                    (folder/f'{label}-{preset}-quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                cases[label]=dict(surface=surface,trajectory=trajectory,input_seed=input_seed,recording_sha256=raw[-32:].hex(),
                                  signal_sha256=signal_hash,guide_camera_sha256=guide_hash,reference_sha256=reference_hash,reports=reports)
    audit(cases)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='eight-frame-surface-stability-histories',seeds=list(SEEDS),
                 trajectories=list(TRAJECTORIES),samples_per_batch=args.samples,cases=cases,paired_summary=history_summary(cases),
                 artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='measured',quality_acceptance='not-qualified',paired_summary=summary['paired_summary'],artifacts=str(folder))))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
