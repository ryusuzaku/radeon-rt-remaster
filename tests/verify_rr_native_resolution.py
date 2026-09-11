"""Exact 256x192 RR recording/SDK execution and extent-aware CPU guides."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_dxr import fixture,encode_scene
from inspect_rr_inputs import decode_inputs,FILE_BYTES_V2
from inspect_rr_record import decode_record
from rr_recorded_dispatch import run_recording,decode_recording_output
from rr_dispatch import run_dispatch
from rr_reference import Reference
from rr_fallback import spatial


def need(ok,why):
    if not ok: raise AssertionError(why)


def resized_fixture(width=256,height=192):
    scene=copy.deepcopy(fixture()); scene['width']=width; scene['height']=height
    for draw in scene['draws']:
        draw['viewport']=[0,0,width,height,0.0,1.0]
        draw['scissor']=[0,0,width,height]
    return scene


def main():
    parser=argparse.ArgumentParser()
    for name in ('probe','sdk-bin','dxr'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rr-native-resolution-',dir=args.probe.parent))
    scene=resized_fixture(); source=folder/'source-256x192.rrscene'; source.write_bytes(encode_scene(scene))
    recording=folder/'native-256x192.rrcapture'
    command=[args.dxr,source,'--mode','gi','--samples','2','--sun-radius','0','--rr-record',recording,'--debug']
    process=subprocess.run([str(x) for x in command],capture_output=True,text=True,timeout=60)
    need(process.returncode==0,(process.stdout,process.stderr)); render_report=json.loads(process.stdout)
    data=decode_record(recording.read_bytes())
    need((data['version'],data['width'],data['height'],data['count'])==(2,256,192,2),'native-v2 recording identity mismatch')
    need(all(len(part)==FILE_BYTES_V2 and part[:8]==b'RRTRRI02' for part in data['parts']),'native-v2 frame ABI mismatch')
    need(render_report['rr_recorded_frames']==2 and render_report['rr_input_stride']==96,'renderer report mismatch')

    reference=Reference(scene,data['settings']); primary=reference.primary(data['frames'][0])
    radiance=np.asarray([row[:3] for row in data['frames'][0]['records']],dtype=np.float64)
    filtered=spatial(data['frames'][0],radiance,primary)
    need(filtered.shape==(256*192,3) and np.all(np.isfinite(filtered)),'extent-aware fallback failed')

    malformed=bytearray(data['parts'][0]); malformed[:8]=b'RRTRRI01'; malformed[-32:]=sha256(malformed[:-32]).digest()
    try: decode_inputs(malformed)
    except ValueError: pass
    else: raise AssertionError('cross-version native-v2 frame accepted')

    output=folder/'native-256x192.rrrecordout'; shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    report=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,coordinate_scale='unit-one')
    need(report['decision']['rr_rendering'],report)
    chunks,rows=decode_recording_output(output.read_bytes(),recording.read_bytes(),coordinate_scale='unit-one')
    need(len(chunks)==len(rows)==2 and all(len(row)==256*192 for row in rows),'native-v2 SDK output mismatch')
    need(output.read_bytes()[:8]==b'RRTRRD05','native-v2 output version mismatch')
    single=folder/'native-v2-reset.rrinputs'; single.write_bytes(data['parts'][0]); single_output=folder/'native-v2-reset.rrout'
    single_report=run_dispatch(args.probe,args.sdk_bin,single,single_output)
    need(single_report['decision']['rr_rendering'] and single_report['decision']['context']['width']==256
         and len(single_output.read_bytes())==len(chunks[0]),'native-v2 single dispatch mismatch')
    summary=dict(result='pass',extent=[256,192],frames=2,reference_hits=int(np.count_nonzero(primary['hit'])),
                 fallback_finite=True,decision=report['decision'],artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('result','extent','frames','reference_hits','artifacts')}))


if __name__=='__main__': main()
