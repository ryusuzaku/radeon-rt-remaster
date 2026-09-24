"""Fixed-resolution coherent scene-unit RR comparison; no default promotion."""
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
from rr_quality import analyze_scale_comparison
from rr_setting_histories import counts
from rr_setting_surfaces import require

SCALES=('unit-tenth','unit-one','unit-ten')
SETTINGS=('none','stability-zero')
TRAJECTORIES={
    'moving':('--rr-step','.04','0','0'),
    'reset':('--rr-step','.04','0','0','--rr-reset-frame','4'),
}


def metric(frame,name):
    if name=='spatial': return frame['all']['rr_mse']
    if name=='temporal': return frame['temporal']['rr_residual_mse']
    return frame['groups']['disoccluded']['rr_mse']


def paired(cases,left,right,name,late=False):
    values=[]
    for case in cases.values():
        a=case['reports'][left[0]][left[1]]['frames']; b=case['reports'][right[0]][right[1]]['frames']
        require(len(a)==len(b)==8,'scale frame count changed')
        indices=range(5,8) if late and case['trajectory']=='reset' else range(4,8) if late else range(8)
        for i in indices:
            before,after=metric(a[i],name),metric(b[i],name)
            require((before is None)==(after is None),'scale metric availability changed')
            if before is not None: values.append(after-before)
    return counts(values)


def summarize(cases):
    result={'scale_vs_unit_one':{},'zero_vs_default':{}}
    for setting in SETTINGS:
        result['scale_vs_unit_one'][setting]={}
        for scale in ('unit-tenth','unit-ten'):
            result['scale_vs_unit_one'][setting][scale]={}
            for name in ('spatial','temporal','disoccluded'):
                result['scale_vs_unit_one'][setting][scale][name]=paired(cases,('unit-one',setting),(scale,setting),name)
                result['scale_vs_unit_one'][setting][scale]['late_'+name]=paired(cases,('unit-one',setting),(scale,setting),name,True)
    for scale in SCALES:
        result['zero_vs_default'][scale]={name:paired(cases,(scale,'none'),(scale,'stability-zero'),name)
                                          for name in ('spatial','temporal','disoccluded')}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512),default=512)
    parser.add_argument('--seed',type=int,choices=(1,7,23),default=7)
    args=parser.parse_args(); started=time.monotonic(); require(8*args.samples<=4096,'reference work budget')
    for path in (args.probe,args.dxr,args.scene,args.materials): require(path.is_file(),f'missing input: {path}')
    require(args.sdk_bin.is_dir(),'missing SDK bin directory')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; require(shader.is_file(),'missing RR input shader')
    folder=Path(tempfile.mkdtemp(prefix='rr-coordinate-scales-',dir=args.probe.resolve().parent)); cases={}
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None
        for trajectory,options in TRAJECTORIES.items():
            label=f'{surface}-{trajectory}-seed-{args.seed}'; print(label+': capture',flush=True)
            recording=folder/(label+'.rrcapture')
            command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','8','--seed',str(args.seed),
                     '--rr-record',str(recording),'--debug',*options]
            if material: command+=['--materials',str(material)]
            p=subprocess.run(command,capture_output=True,text=True,timeout=60); require(p.returncode==0,('capture failed',p.stdout,p.stderr))
            with recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
            data=admit_record(raw); expected=[0,4] if trajectory=='reset' else [0]
            require(data['count']==8 and [i for i,f in enumerate(data['frames']) if f['reset']]==expected,'capture/reset contract changed')
            candidates={}
            for scale in SCALES:
                for setting in SETTINGS:
                    stem=f'{label}-{scale}-{setting}'; print(stem+': dispatch',flush=True)
                    output=folder/(stem+'.rrrecordout'); execution=folder/(stem+'-execution.json')
                    worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                         query_defaults=setting!='none',filter_setting=setting,coordinate_scale=scale)
                    execution.write_text(json.dumps(worker),encoding='utf-8')
                    require(worker['decision']['rr_rendering'] and worker['input_sha256']==raw[-32:].hex(),'scale execution failed; evidence retained')
                    candidates[(scale,setting)]=(output,execution)
            # Explicit unit-one must preserve the historical unconfigured inner frame bytes.
            control=folder/f'{label}-unconfigured.rrrecordout'; control_execution=folder/f'{label}-unconfigured-execution.json'
            worker=run_recording(args.probe,args.sdk_bin,recording,control,scene=args.scene,shader=shader,materials=material)
            control_execution.write_text(json.dumps(worker),encoding='utf-8'); tagged=candidates[('unit-one','none')][0].read_bytes(); plain=control.read_bytes()
            frame_bytes=196696
            require(all(tagged[56+i*frame_bytes:56+(i+1)*frame_bytes]==plain[56+i*frame_bytes:56+(i+1)*frame_bytes] for i in range(8)),
                    'unit-one changed historical SDK frame bytes')
            reports,arrays=analyze_scale_comparison(recording,candidates,args.scene,shader,samples=args.samples,surface_reference=True,materials=material,
                                                     progress=lambda i,n,label=label:print(f'{label} reference {i+1}/{n}',flush=True))
            reference=folder/(label+'-reference.npz')
            with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
            reference_hash=sha256(reference.read_bytes()).hexdigest()
            for scale in SCALES:
                for setting in SETTINGS:
                    report=reports[scale][setting]; report['reference_file_sha256']=reference_hash
                    (folder/f'{label}-{scale}-{setting}-quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            cases[label]=dict(surface=surface,trajectory=trajectory,input_seed=args.seed,recording_sha256=raw[-32:].hex(),
                              unit_one_inner_frames_exact=True,reference_sha256=reference_hash,reports=reports)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='four-case-coherent-coordinate-scale-comparison',
                 resolution=[128,96],seed=args.seed,samples_per_batch=args.samples,cases=cases,paired_summary=summarize(cases),
                 artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('result','quality_acceptance','paired_summary','artifacts','elapsed_seconds')}))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
