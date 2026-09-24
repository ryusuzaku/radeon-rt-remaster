"""Fixed material/normal/radiance RR conditioning comparison; no promotion."""
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
from rr_quality import analyze_guide_comparison
from rr_setting_surfaces import require

CANDIDATES={
    'baseline':('none','none'),
    'material-draw':('material-draw','none'),
    'normal-half':('none','normal-half'),
    'material-normal-half':('material-draw','normal-half'),
    'max-radiance-one':('none','max-radiance-one')}


def metric(frame,name):
    if name=='spatial': return frame['all']['rr_mse']
    if name=='temporal': return frame['temporal']['rr_residual_mse']
    return frame['groups']['disoccluded']['rr_mse']


def compare(report,baseline,name):
    values=[]
    for after,before in zip(report['frames'],baseline['frames']):
        a,b=metric(after,name),metric(before,name)
        require((a is None)==(b is None),'guide metric availability changed')
        if a is not None and not after['reset']: values.append(a-b)
    return dict(lower=sum(x<0 for x in values),equal=sum(x==0 for x in values),higher=sum(x>0 for x in values),mean_delta=sum(values)/len(values))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512),default=512)
    parser.add_argument('--seed',type=int,choices=(1,7,23),default=7)
    args=parser.parse_args(); started=time.monotonic(); require(8*args.samples<=4096,'reference work budget')
    for path in (args.probe,args.dxr,args.scene,args.materials): require(path.is_file(),f'missing input: {path}')
    require(args.sdk_bin.is_dir(),'missing SDK bin directory')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; require(shader.is_file(),'missing RR input shader')
    folder=Path(tempfile.mkdtemp(prefix='rr-guide-conditioning-',dir=args.probe.resolve().parent)); cases={}
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None; print(surface+': capture',flush=True)
        recording=folder/(surface+'.rrcapture')
        command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','8','--seed',str(args.seed),
                 '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
        if material: command+=['--materials',str(material)]
        process=subprocess.run(command,capture_output=True,text=True,timeout=90)
        require(process.returncode==0,('capture failed',process.stdout,process.stderr))
        with recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
        data=admit_record(raw); require(data['count']==8 and (data['width'],data['height'])==(128,96),'guide recording contract changed')
        candidates={}
        for label,(guide,setting) in CANDIDATES.items():
            print(f'{surface}-{label}: dispatch',flush=True); output=folder/f'{surface}-{label}.rrrecordout'; execution=folder/f'{surface}-{label}-execution.json'
            worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                 query_defaults=setting!='none',filter_setting=setting,coordinate_scale='unit-one',guide_preset=guide)
            execution.write_text(json.dumps(worker),encoding='utf-8'); require(worker['decision']['rr_rendering'],'guide execution failed; evidence retained')
            candidates[label]=(output,execution)
        reports,arrays=analyze_guide_comparison(recording,candidates,args.scene,shader,samples=args.samples,materials=material,
                                                 progress=lambda i,n,surface=surface:print(f'{surface} reference {i+1}/{n}',flush=True))
        reference=folder/(surface+'-reference.npz')
        with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
        reference_hash=sha256(reference.read_bytes()).hexdigest()
        for label,report in reports.items():
            report['reference_file_sha256']=reference_hash
            (folder/f'{surface}-{label}-quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        baseline=reports['baseline']; paired={label:{name:compare(report,baseline,name) for name in ('spatial','temporal','disoccluded')}
                                            for label,report in reports.items() if label!='baseline'}
        cases[surface]=dict(recording_sha256=raw[-32:].hex(),reference_sha256=reference_hash,reports=reports,paired=paired)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='material-normal-radiance-guide-conditioning',seed=args.seed,
                 samples_per_batch=args.samples,candidates=list(CANDIDATES),cases=cases,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('result','quality_acceptance','candidates','artifacts','elapsed_seconds')}))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
