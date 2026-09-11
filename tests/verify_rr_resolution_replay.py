"""Fresh cross-build replay of a completed native-resolution grid."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from scene_io import decode_scene,encode_scene
from rr_recorded_dispatch import run_recording
from rr_resolutions import EXTENTS,SETTINGS,resized


def need(ok,why):
    if not ok: raise AssertionError(why)


def main():
    parser=argparse.ArgumentParser()
    for name in ('baseline','probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); manifest=json.loads((args.baseline/'verification.json').read_text(encoding='utf-8'))
    need(manifest['result']=='measured' and manifest['extents']==[list(x) for x in EXTENTS] and manifest['seed']==7,'baseline manifest mismatch')
    original=decode_scene(args.scene.read_bytes()); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    folder=Path(tempfile.mkdtemp(prefix='rr-resolution-replay-',dir=args.probe.parent)); recordings=outputs=0
    for width,height in EXTENTS:
        scene_path=folder/f'source-{width}x{height}.rrscene'; scene_path.write_bytes(encode_scene(resized(original,width,height)))
        need(scene_path.read_bytes()==(args.baseline/scene_path.name).read_bytes(),'resized source changed')
        for surface in ('texture','pbr'):
            material=args.materials if surface=='pbr' else None; label=f'{surface}-{width}x{height}'
            recording=folder/(label+'.rrcapture')
            command=[str(args.dxr),str(scene_path),'--mode','gi','--sun-radius','0','--samples','8','--seed','7',
                     '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
            if material: command+=['--materials',str(material)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=120)
            need(process.returncode==0,(process.stdout,process.stderr))
            baseline_recording=args.baseline/recording.name
            need(recording.read_bytes()==baseline_recording.read_bytes(),f'{label} recording changed'); recordings+=1
            case=manifest['cases'][label]
            reference=args.baseline/(label+'-reference.npz')
            need(sha256(reference.read_bytes()).hexdigest()==case['reference_sha256'],'baseline reference changed')
            for setting in SETTINGS:
                output=folder/f'{label}-{setting}.rrrecordout'
                report=run_recording(args.probe,args.sdk_bin,recording,output,scene=scene_path,shader=shader,materials=material,
                                     query_defaults=setting!='none',filter_setting=setting,coordinate_scale='unit-one')
                need(report['decision']['rr_rendering'],report)
                baseline_output=args.baseline/output.name
                need(output.read_bytes()==baseline_output.read_bytes(),f'{label}/{setting} output changed'); outputs+=1
    summary=dict(result='pass',scope='fresh-cross-build-native-resolution-replay',recordings=recordings,outputs=outputs,
                 baseline=str(args.baseline),artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
