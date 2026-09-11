"""Worker-only material guide and normal/radiance setting provenance."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from verify_dxr import fixture,encode_scene
from inspect_rr_record import decode_record
from rr_recorded_dispatch import run_recording,decode_recording_output,assess_recording
from rr_guides import validate_guide,material_type
from rr_worker import strict_json


def need(ok,why):
    if not ok: raise AssertionError(why)


def main():
    parser=argparse.ArgumentParser()
    for name in ('probe','sdk-bin','dxr'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rr-guides-',dir=args.probe.parent))
    scene=fixture(); source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    recording=folder/'source.rrcapture'
    process=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--samples','2','--rr-step','.04','0','0','--rr-record',str(recording),'--debug'],capture_output=True,text=True,timeout=60)
    need(process.returncode==0,(process.stdout,process.stderr)); raw=recording.read_bytes(); data=decode_record(raw)
    cases={}
    def execute(label,guide='none',setting='none'):
        output=folder/(label+'.rrrecordout')
        report=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,query_defaults=setting!='none',
                             filter_setting=setting,coordinate_scale='unit-one',guide_preset=guide)
        need(report['decision']['rr_rendering'],report); chunks,_=decode_recording_output(output.read_bytes(),raw,filter_setting=setting,coordinate_scale='unit-one',guide_preset=guide)
        cases[label]=(report,output,chunks); return cases[label]
    baseline=execute('baseline'); normal_default=execute('normal-default',setting='normal-default')
    material=execute('material-draw',guide='material-draw'); combo=execute('material-normal-half',guide='material-draw',setting='normal-half')
    radiance=execute('max-radiance-one',setting='max-radiance-one')
    need(baseline[2]==normal_default[2],'configured normal default changed baseline frame bytes')
    base_frames=strict_json(baseline[0]['worker']['stdout'])['sequence_test']['frames']
    material_frames=strict_json(material[0]['worker']['stdout'])['sequence_test']['frames']
    for before,after in zip(base_frames,material_frames):
        need(before['packed_sha256'][:2]==after['packed_sha256'][:2] and before['packed_sha256'][3:]==after['packed_sha256'][3:]
             and before['packed_sha256'][2]!=after['packed_sha256'][2],'material preset changed wrong packed plane')
    values={material_type(row,'material-draw') for row in data['frames'][0]['records'] if row[23]}
    need(values=={0,1/3},'draw classes not encoded as AMD material fractions')
    try: decode_recording_output(material[1].read_bytes(),raw,coordinate_scale='unit-one')
    except ValueError: pass
    else: raise AssertionError('guide output accepted without expected provenance')
    root=strict_json(material[0]['worker']['stdout']); root['sequence_test'].pop('guide_preset'); envelope=copy.deepcopy(material[0]['worker']); envelope['stdout']=json.dumps(root)
    need(assess_recording(envelope,raw,coordinate_scale='unit-one',guide_preset='material-draw')['status']=='unavailable','missing guide report accepted')
    for invalid in ('draw','material',None,1):
        try: validate_guide(invalid)
        except ValueError: pass
        else: raise AssertionError('invalid guide preset accepted')
    summary=dict(result='pass',scope='guide-conditioning-contract',cases=list(cases),frames=2,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
