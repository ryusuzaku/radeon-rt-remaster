"""Fresh Debug replication of a completed Release longer-history grid."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

from inspect_rr_record import MAX_BYTES
from rr_recorded_dispatch import admit_record,run_recording
from rr_setting_surfaces import SEEDS,PRESETS,require
from rr_setting_histories import TRAJECTORIES


def read(path,limit):
    with path.open('rb') as stream: value=stream.read(limit+1)
    require(len(value)<=limit,'replay artifact oversized'); return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); started=time.monotonic(); baseline=json.loads(read(args.baseline/'verification.json',4*1024*1024))
    labels={f'{surface}-{trajectory}-seed-{seed}' for surface in ('texture','pbr') for trajectory in TRAJECTORIES for seed in SEEDS}
    require(baseline['result']=='measured' and set(baseline['cases'])==labels,'incomplete history baseline')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; folder=Path(tempfile.mkdtemp(prefix='rr-history-replay-',dir=args.probe.resolve().parent)); cases={}
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None
        for trajectory,options in TRAJECTORIES.items():
            for seed in SEEDS:
                label=f'{surface}-{trajectory}-seed-{seed}'; print(label+': replay',flush=True); recording=folder/(label+'.rrcapture')
                command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','8','--seed',str(seed),
                         '--rr-record',str(recording),'--debug',*options]
                if material: command+=['--materials',str(material)]
                process=subprocess.run(command,capture_output=True,text=True,timeout=60); require(process.returncode==0,(label,process.stdout,process.stderr))
                raw=read(recording,MAX_BYTES); admit_record(raw); require(raw==read(args.baseline/recording.name,MAX_BYTES),'recording bytes changed')
                require(raw[-32:].hex()==baseline['cases'][label]['recording_sha256'],'recording digest changed')
                outputs={}
                for preset in PRESETS:
                    output=folder/f'{label}-{preset}.rrrecordout'; worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,
                                                                                       materials=material,query_defaults=True,filter_setting=preset)
                    (folder/f'{label}-{preset}-execution.json').write_text(json.dumps(worker),encoding='utf-8')
                    require(worker['decision']['rr_rendering'],'replay worker failed; evidence retained')
                    value=read(output,3*1024*1024); require(value==read(args.baseline/output.name,3*1024*1024),('output changed',label,preset))
                    outputs[preset]=sha256(value).hexdigest()
                cases[label]=outputs
    report=dict(result='pass',recordings=18,exact_output_bundles=54,quality_acceptance='not-qualified',baseline=str(args.baseline.resolve()),
                cases=cases,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report))


if __name__=='__main__': main()
