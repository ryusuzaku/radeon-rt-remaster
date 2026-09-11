"""Fresh-render/fresh-worker replication of a completed six-recording grid."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

from rr_setting_surfaces import SEEDS,PRESETS,require
from rr_recorded_dispatch import run_recording,admit_record
from inspect_rr_record import MAX_BYTES


def bounded(path,limit):
    with path.open('rb') as stream: value=stream.read(limit+1)
    require(len(value)<=limit,'oversized replay input'); return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); started=time.monotonic()
    baseline=json.loads(bounded(args.baseline/'verification.json',1024*1024))
    labels={f'{surface}-seed-{seed}' for surface in ('texture','pbr') for seed in SEEDS}
    require(baseline['result']=='measured' and set(baseline['cases'])==labels,'incomplete baseline grid')
    folder=Path(tempfile.mkdtemp(prefix='rr-surface-replay-',dir=args.probe.resolve().parent)); cases={}
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'
    for surface in ('texture','pbr'):
        for seed in SEEDS:
            label=f'{surface}-seed-{seed}'; print(label+': replay',flush=True)
            material=args.materials if surface=='pbr' else None
            recording=folder/(label+'.rrcapture')
            command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','4','--seed',str(seed),
                     '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
            if material: command+=['--materials',str(material)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=45)
            require(process.returncode==0,('replay capture failed',label,process.stdout,process.stderr))
            raw=bounded(recording,MAX_BYTES); admit_record(raw)
            require(raw==bounded(args.baseline/(label+'.rrcapture'),MAX_BYTES),'recording bytes changed')
            require(raw[-32:].hex()==baseline['cases'][label]['recording_sha256'],'baseline recording digest changed')
            outputs={}
            for preset in PRESETS:
                output=folder/f'{label}-{preset}.rrrecordout'
                worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                     query_defaults=True,filter_setting=preset)
                (folder/f'{label}-{preset}-execution.json').write_text(json.dumps(worker),encoding='utf-8')
                require(worker['decision']['rr_rendering'],'replication worker failed; evidence retained')
                value=bounded(output,2*1024*1024)
                require(value==bounded(args.baseline/output.name,2*1024*1024),('SDK output bytes changed',label,preset))
                outputs[preset]=sha256(value).hexdigest()
            cases[label]=outputs
    report=dict(result='pass',recordings=6,exact_output_bundles=18,quality_acceptance='not-qualified',
                baseline=str(args.baseline.resolve()),cases=cases,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report))


if __name__=='__main__': main()
