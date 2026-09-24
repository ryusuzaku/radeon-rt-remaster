"""Bounded exact-zero RR floor localization; never compensates output pixels."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from inspect_rr_inputs import HEADER as INPUT_HEADER, RECORD, decode_inputs
from inspect_rr_record import MAX_BYTES
from rr_dispatch import decode_output, output_bytes, read_exact, run_dispatch
from rr_recorded_dispatch import admit_record, decode_recording_output, run_recording


VARIANTS=('active','zero-albedo','zero-distance','background')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def seal(raw):
    raw=bytearray(raw)
    raw[-32:]=sha256(raw[:-32]).digest()
    return bytes(raw)


def mutate_input(raw, variant):
    if variant not in VARIANTS:
        raise ValueError('unknown black-floor input variant')
    source=decode_inputs(raw)
    require(source['reset'],'black-floor single controls require a reset frame')
    require(all(not any(row[:3]) for row in source['records']),'black-floor source radiance is not exact zero')
    if variant=='active':
        return bytes(raw)
    result=bytearray(raw)
    for pixel,row in enumerate(source['records']):
        offset=INPUT_HEADER.size+pixel*RECORD.size
        if variant=='background':
            RECORD.pack_into(result,offset,0,0,0,-1,*([0]*20))
        elif row[23] and variant=='zero-albedo':
            struct.pack_into('<3f',result,offset+12*4,0,0,0)
        elif row[23] and variant=='zero-distance':
            struct.pack_into('<f',result,offset+3*4,0)
    result=seal(result)
    decoded=decode_inputs(result)
    require(all(not any(row[:3]) for row in decoded['records']),'variant invented radiance')
    return result


def distribution(rows, source):
    active=[]; background=[]
    for output,input_row in zip(rows,source['records']):
        (active if input_row[23] else background).extend(output[:3])
    def summarize(values):
        positive=sorted(x for x in values if x>0)
        count=len(values)
        return dict(values=count,nonzero=len(positive),minimum_positive=positive[0] if positive else 0,
                    maximum=max(values,default=0),mean=sum(values)/count if count else 0,
                    mse=sum(x*x for x in values)/count if count else 0,
                    unique_positive=len(set(positive)))
    all_values=[x for row in rows for x in row[:3]]
    return dict(all=summarize(all_values),active=summarize(active),background=summarize(background),
                channel_maxima=[max((row[c] for row in rows),default=0) for c in range(3)],
                channel_means=[sum(row[c] for row in rows)/len(rows) for c in range(3)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--materials',type=Path)
    parser.add_argument('--seed',type=int,default=1)
    args=parser.parse_args(); started=time.monotonic()
    require(0<=args.seed<4096,'seed out of range')
    probe=args.probe.resolve(strict=True); sdk=args.sdk_bin.resolve(strict=True)
    dxr=args.dxr.resolve(strict=True); scene=args.scene.resolve(strict=True)
    materials=args.materials.resolve(strict=True) if args.materials else None
    shader=(dxr.parent/'rrt_rr_inputs.dxil').resolve(strict=True)
    folder=Path(tempfile.mkdtemp(prefix='rr-black-floor-',dir=probe.parent))
    recording=folder/'black.rrcapture'
    command=[str(dxr),str(scene),'--mode','gi','--sun-radius','0','--light-intensity','0','--ambient','0',
             '--samples','8','--seed',str(args.seed),'--rr-record',str(recording),'--debug']
    if materials:
        command += ['--materials',str(materials)]
    process=subprocess.run(command,capture_output=True,text=True,timeout=90)
    require(process.returncode==0,('black capture failed',process.stdout,process.stderr))
    raw=read_exact(recording,recording.stat().st_size); data=admit_record(raw)
    require(data['count']==8 and all(not any(row[:3]) for frame in data['frames'] for row in frame['records']),
            'capture is not eight exact-zero frames')

    history_output=folder/'history.rrrecordout'; history_execution=folder/'history-execution.json'
    history=run_recording(probe,sdk,recording,history_output,scene=scene,shader=shader,materials=materials)
    require(history['decision']['rr_rendering'],'black history did not execute')
    history_execution.write_text(json.dumps(history,indent=2)+'\n',encoding='utf-8')
    history_chunks,history_rows=decode_recording_output(history_output.read_bytes(),raw)
    history_stats=[distribution(rows,frame) for rows,frame in zip(history_rows,data['frames'])]

    variants={}; variant_rows={}
    for name in VARIANTS:
        input_path=folder/(name+'.rrinputs'); input_raw=mutate_input(data['parts'][0],name)
        input_path.write_bytes(input_raw); source=decode_inputs(input_raw)
        output_path=folder/(name+'.rrout'); execution_path=folder/(name+'-execution.json')
        execution=run_dispatch(probe,sdk,input_path,output_path)
        require(execution['decision']['rr_rendering'],name+' control did not execute')
        execution_path.write_text(json.dumps(execution,indent=2)+'\n',encoding='utf-8')
        rows=decode_output(read_exact(output_path,output_bytes(source)),source,input_raw[-32:])
        variant_rows[name]=rows
        variants[name]=dict(input_sha256=input_raw[-32:].hex(),output_sha256=sha256(output_path.read_bytes()).hexdigest(),
                            active_pixels=sum(bool(row[23]) for row in source['records']),statistics=distribution(rows,source),
                            execution=str(execution_path),output=str(output_path))

    require(variants['background']['statistics']['all']['nonzero']==0,'all-background control changed')
    for name in VARIANTS:
        variants[name]['rgb_matches_active']=all(a[:3]==b[:3] for a,b in zip(variant_rows['active'],variant_rows[name]))
    manifest=dict(result='pass',scope='exact-zero-floor-localization',quality_acceptance='failed-zero-light-oracle',
                  raw_sdk_acceptance='failed',seed=args.seed,recording_sha256=raw[-32:].hex(),
                  history_output_sha256=sha256(history_output.read_bytes()).hexdigest(),history=history_stats,
                  variants=variants,history_first_matches_active=history_chunks[0]==(folder/'active.rrout').read_bytes(),
                  source=dict(scene=str(scene),materials=str(materials) if materials else None,shader=str(shader)),
                  elapsed_seconds=time.monotonic()-started,artifacts=str(folder))
    require(any(frame['all']['nonzero'] for frame in history_stats),'known zero floor disappeared; inspect before accepting')
    (folder/'verification.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='pass',scope=manifest['scope'],artifacts=str(folder),
                          history_maxima=[x['all']['maximum'] for x in history_stats],
                          variant_maxima={k:v['statistics']['all']['maximum'] for k,v in variants.items()})))


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError,OverflowError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error))))
        raise SystemExit(1)
