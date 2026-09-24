"""Fresh cross-build replay of a completed guide-conditioning grid."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rr_guide_conditioning import CANDIDATES
from rr_recorded_dispatch import run_recording


def need(ok,why):
    if not ok: raise AssertionError(why)


def main():
    parser=argparse.ArgumentParser()
    for name in ('baseline','probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); manifest=json.loads((args.baseline/'verification.json').read_text(encoding='utf-8'))
    need(manifest['result']=='measured' and manifest['candidates']==list(CANDIDATES) and manifest['seed']==7,'baseline manifest mismatch')
    shader=args.dxr.parent/'rrt_rr_inputs.dxil'; folder=Path(tempfile.mkdtemp(prefix='rr-guide-replay-',dir=args.probe.parent)); recordings=outputs=0
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None; recording=folder/(surface+'.rrcapture')
        command=[str(args.dxr),str(args.scene),'--mode','gi','--sun-radius','0','--samples','8','--seed','7',
                 '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
        if material: command+=['--materials',str(material)]
        process=subprocess.run(command,capture_output=True,text=True,timeout=90)
        need(process.returncode==0,(process.stdout,process.stderr)); need(recording.read_bytes()==(args.baseline/recording.name).read_bytes(),surface+' recording changed'); recordings+=1
        reference=args.baseline/(surface+'-reference.npz')
        need(sha256(reference.read_bytes()).hexdigest()==manifest['cases'][surface]['reference_sha256'],'baseline reference changed')
        for label,(guide,setting) in CANDIDATES.items():
            output=folder/f'{surface}-{label}.rrrecordout'
            report=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=shader,materials=material,
                                 query_defaults=setting!='none',filter_setting=setting,coordinate_scale='unit-one',guide_preset=guide)
            need(report['decision']['rr_rendering'],report); need(output.read_bytes()==(args.baseline/output.name).read_bytes(),f'{surface}/{label} output changed'); outputs+=1
    summary=dict(result='pass',scope='fresh-cross-build-guide-conditioning-replay',recordings=recordings,outputs=outputs,
                 baseline=str(args.baseline),artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
