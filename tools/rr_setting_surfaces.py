"""Bounded multi-seed textured/PBR stability comparison; no default promotion."""
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

SEEDS=(1,7,23)
PRESETS=('none','stability-half','stability-zero')


def require(ok,message):
    if not ok: raise ValueError(message)


def seed_fingerprints(data):
    records=np.asarray([frame['records'] for frame in data['frames']],dtype='<f4')
    matrices=np.asarray([[value for matrix in frame['matrices'].values() for value in matrix] for frame in data['frames']],dtype='<f4')
    # indirectDistance is one stochastic float4: RGB AND sampled bounce T.
    # Components 4..23 and camera matrices are deterministic at zero sun radius.
    return (sha256(records[:,:,:4].tobytes()).hexdigest(),
            sha256(records[:,:,4:].tobytes()+matrices.tobytes()).hexdigest())


def audit_seeds(cases):
    for surface in ('texture','pbr'):
        selected=[cases[f'{surface}-seed-{seed}'] for seed in SEEDS]
        require(len({c['recording_sha256'] for c in selected})==len(SEEDS),'renderer seed did not change recording identity')
        require(len({c['signal_sha256'] for c in selected})==len(SEEDS),'renderer seed did not change noisy signal')
        require(len({c['guide_camera_sha256'] for c in selected})==1,'renderer seed changed guides/camera')


def paired_summary(cases):
    result={}
    for preset in PRESETS[1:]:
        groups={name:[] for name in ('spatial','temporal','disoccluded')}
        for case in cases.values():
            base=case['reports']['none']['frames']; candidate=case['reports'][preset]['frames']
            require(len(base)==len(candidate),'paired frame count changed')
            for a,b in zip(base,candidate):
                require(a['index']==b['index'],'paired frame index changed')
                for name,key in (('spatial','rr_mse'),('temporal','rr_residual_mse')):
                    before=a['all'][key] if name=='spatial' else a['temporal'][key]
                    after=b['all'][key] if name=='spatial' else b['temporal'][key]
                    if before is not None and after is not None: groups[name].append(after-before)
                before=a['groups']['disoccluded']['rr_mse']; after=b['groups']['disoccluded']['rr_mse']
                if before is not None and after is not None: groups['disoccluded'].append(after-before)
        result[preset]={}
        for name,values in groups.items():
            require(values,'missing paired '+name+' measurements')
            result[preset][name]=dict(comparisons=len(values),improved=sum(v<0 for v in values),equal=sum(v==0 for v in values),
                                      worsened=sum(v>0 for v in values),mean_delta=float(np.mean(values)),median_delta=float(np.median(values)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512,1024),default=1024)
    args=parser.parse_args(); started=time.monotonic()
    require(4*args.samples<=4096,'reference work budget')
    for path in (args.probe,args.dxr,args.scene,args.materials): require(path.is_file(),f'missing input: {path}')
    require(args.sdk_bin.is_dir(),'missing SDK bin directory')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; require(shader.is_file(),'missing RR input shader')
    folder=Path(tempfile.mkdtemp(prefix='rr-setting-surfaces-',dir=args.probe.resolve().parent))
    cases={}
    for surface in ('texture','pbr'):
        for input_seed in SEEDS:
            label=f'{surface}-seed-{input_seed}'; print(label+': capture',flush=True)
            recording=folder/(label+'.rrcapture')
            command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','4','--seed',str(input_seed),
                     '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
            material=args.materials if surface=='pbr' else None
            if material: command+=['--materials',str(material)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=45)
            require(process.returncode==0,('capture failed',label,process.stdout,process.stderr))
            with recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
            data=admit_record(raw); require(data['count']==4 and data['settings']['seed']==input_seed,'capture contract changed')
            require(data['material_sha256']!=('0'*64) if material else data['material_sha256']==('0'*64),'material provenance changed')
            signal_hash,guide_hash=seed_fingerprints(data)
            candidates={}
            for preset in PRESETS:
                print(f'{label}: {preset} dispatch',flush=True)
                output=folder/f'{label}-{preset}.rrrecordout'; execution=folder/f'{label}-{preset}-execution.json'
                worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                     query_defaults=True,filter_setting=preset)
                execution.write_text(json.dumps(worker),encoding='utf-8')
                require(worker['input_sha256']==raw[-32:].hex(),'recording changed during comparison')
                require(worker['decision']['rr_rendering'],'recording execution failed; worker evidence retained')
                candidates[preset]=(output,execution)
            print(label+': shared independent reference',flush=True)
            reports,arrays=analyze_comparison(recording,candidates,args.scene,shader,samples=args.samples,surface_reference=True,materials=material,
                                              progress=lambda i,n:print(f'{label} reference {i+1}/{n}',flush=True))
            reference=folder/(label+'-reference.npz')
            with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
            reference_hash=sha256(reference.read_bytes()).hexdigest()
            for preset,report in reports.items():
                report['reference_file_sha256']=reference_hash
                (folder/f'{label}-{preset}-quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            cases[label]=dict(surface=surface,input_seed=input_seed,recording_sha256=raw[-32:].hex(),signal_sha256=signal_hash,
                              guide_camera_sha256=guide_hash,reference_sha256=reference_hash,reports=reports)
    audit_seeds(cases)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='six-recording-three-preset-surface-comparison',
                 seeds=list(SEEDS),samples_per_batch=args.samples,cases=cases,paired_summary=paired_summary(cases),
                 artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='measured',quality_acceptance='not-qualified',paired_summary=summary['paired_summary'],artifacts=str(folder))))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
