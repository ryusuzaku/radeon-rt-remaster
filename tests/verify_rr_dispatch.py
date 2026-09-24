"""Isolated SDK execution/texture contract; deliberately not a quality gate."""
import argparse
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_dxr import fixture, encode_scene
from material_inputs import compile_materials
from rr_dispatch import run_dispatch, assess_dispatch, decode_output, preview
from rr_worker import strict_json, assess
from inspect_rr_inputs import decode_inputs, HEADER


def need(ok, reason):
    if not ok: raise AssertionError(reason)


def main():
    parser=argparse.ArgumentParser()
    for name in ('probe','sdk-bin','dxr'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--require-zero-light',action='store_true',help='also enforce the strict zero-light quality oracle (currently fails on this SDK)')
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='rr-dispatch-',dir=args.probe.parent))
    scene=fixture(); source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    cases={}
    def render(name, scene_path=source, extra=()):
        inputs=folder/(name+'.rrinputs')
        command=[str(args.dxr),str(scene_path),'--mode','gi','--rr-inputs',str(inputs),'--debug',*map(str,extra)]
        process=subprocess.run(command,capture_output=True,text=True,timeout=45)
        need(process.returncode==0,(process.stdout,process.stderr)); return inputs
    def dispatch(name,inputs,**options):
        output=folder/(name+'.rrout')
        report=run_dispatch(args.probe,args.sdk_bin,inputs,output,**options)
        cases[name]=report; return report,output
    inputs=render('single'); raw=inputs.read_bytes(); data=decode_inputs(raw); digest=raw[-32:]
    report,output=dispatch('single',inputs)
    need(report['decision']['rr_rendering'] is True,report)
    need(report['decision']['raw_sdk_acceptance']=='failed' and report['decision']['quality_acceptance']=='not-evaluated','status overclaim')
    need(assess(report['worker'],cycles=1,allow_workaround=True)['status']=='unavailable','context-only policy accepted dispatch')
    repeat,repeated=dispatch('repeat',inputs)
    need(repeat['decision']['rr_rendering'] and output.read_bytes()==repeated.read_bytes(),'reset nondeterminism')
    preview(inputs,output,folder/'comparison.png')
    rows=decode_output(output.read_bytes(),data,digest)
    # Record first-frame displacement from raw, not an improvement claim.
    raw_mse=sum((r[c]-s[c])**2 for r,s in zip(rows,data['records']) for c in range(3))/(128*96*3)
    cases['single']['raw_difference_mse']=raw_mse
    for name,extra in [('seed',['--seed',23]),('tilt',['--yaw',7,'--pitch',-3])]:
        path=render(name,extra=extra); result,_=dispatch(name,path); need(result['decision']['rr_rendering'],result)
    perspective=copy.deepcopy(scene); perspective['draws']=perspective['draws'][:1]; perspective['attempted']=1
    perspective['draws'][0]['projection']=[1.,0,0,0,0,1.3,0,0,0,0,2/1.9,1,0,0,-.2/1.9,0]
    perspective_path=folder/'perspective.rrscene'; perspective_path.write_bytes(encode_scene(perspective))
    result,_=dispatch('perspective',render('perspective',perspective_path)); need(result['decision']['rr_rendering'],result)
    materials=folder/'materials.rrmat'
    entries=[dict(target=d['material_id'],base_color=[.7,.8,.9],roughness=.4,metallic=.2,emissive=[.1,.2,.3]) for d in scene['draws']]
    materials.write_bytes(compile_materials(dict(schema='rrt-materials',version=1,materials=entries),scene))
    result,_=dispatch('pbr',render('pbr',extra=['--materials',materials])); need(result['decision']['rr_rendering'],result)
    black=bytearray(raw)
    for pixel in range(128*96): struct.pack_into('<3f',black,HEADER.size+pixel*96,0,0,0)
    black[-32:]=sha256(black[:-32]).digest(); black_path=folder/'black.rrinputs'; black_path.write_bytes(black)
    result,black_output=dispatch('black',black_path); need(result['decision']['rr_rendering'],result)
    black_rows=decode_output(black_output.read_bytes(),decode_inputs(black),bytes(black[-32:]))
    black_values=[x for r in black_rows for x in r[:3]]
    zero_light=dict(passed=all(x==0 for x in black_values),maximum=max(black_values),mse=sum(x*x for x in black_values)/len(black_values))
    # Preserve the strict oracle, but finish containment/contract evidence first.
    # CTest covers execution only; --require-zero-light enforces this separate gate.
    # Dispatch and external-budget failure cannot be mistaken for an image.
    for name,options in [('external-budget',dict(external_mib=1)),('context-budget',dict(budget_mib=1)),('sdk-allocation',dict(fail_allocation=2))]:
        result,path=dispatch(name,inputs,**options)
        need(not result['decision']['rr_rendering'] and result['worker']['child_reaped'] and not path.exists(),result)
    result,path=dispatch('recovered',inputs)
    need(result['decision']['rr_rendering'] and path.read_bytes()==output.read_bytes(),'post-failure recovery failed')
    # Independent policy mutation checks, including packed-channel identity.
    original=strict_json(report['worker']['stdout'])
    changes=dict(dispatch_code=6,completed=False,input_sha256='0'*64,external_bytes=1,external_limit=1,
                 resources_released=7,textures=5,reset=False,frame_index=1,submissions=1,uploads_verified=False,
                 inputs_unchanged=False,distance_clamps=0,output_floats=1,staging_bytes=1,
                 packed_sha256=['0'*64]*6,formats=['R32_FLOAT']*6,changed_pixels=True)
    for key,value in changes.items():
        changed=copy.deepcopy(original); changed['dispatch_test'][key]=value
        candidate=dict(report['worker'],stdout=json.dumps(changed))
        need(assess_dispatch(candidate,data,digest)['status']=='unavailable','accepted dispatch mutation '+key)
    # Native parser rejects before creating an SDK context, even without Python.
    corrupt=[raw[:-1],raw+b'x',raw[:500]+bytes([raw[500]^1])+raw[501:]]
    for offset,fmt,value in [(8,'<I',2),(36,'<I',0),(40,'<f',math.nan),(40+16*4,'<f',2),
                             (HEADER.size+96*(48*128+64)+19*4,'<f',20000),
                             (HEADER.size+96*(48*128+64),'<f',70000)]:
        content=bytearray(raw); struct.pack_into(fmt,content,offset,value); content[-32:]=sha256(content[:-32]).digest(); corrupt.append(bytes(content))
    for index,content in enumerate(corrupt):
        path=folder/f'bad-{index}.rrinputs'; path.write_bytes(content); target=folder/f'bad-{index}.rrout'
        process=subprocess.run([str(args.probe),'--isolated-dispatch','--sdk-bin',str(args.sdk_bin.resolve()),'--debug',
                                '--input',str(path.resolve()),'--output',str(target.resolve())],capture_output=True,text=True,timeout=40)
        need(process.returncode==0,process.stderr); envelope=strict_json(process.stdout)
        need(envelope['exit_code']!=0 and envelope['child_reaped'] and 'RR context:' not in envelope['stderr'] and not target.exists(),'native input admitted')
    damaged=[]; out_raw=output.read_bytes()
    damaged.extend((out_raw[:-1],out_raw+b'x',out_raw[:60]+bytes([out_raw[60]^1])+out_raw[61:]))
    for offset,value in [(56,math.nan),(56,-1),(56+12,0)]:
        content=bytearray(out_raw); struct.pack_into('<f',content,offset,value); content[-32:]=sha256(content[:-32]).digest(); damaged.append(bytes(content))
    for content in damaged:
        try: decode_output(content,data,digest)
        except ValueError: pass
        else: raise AssertionError('damaged output accepted')
    try: run_dispatch(args.probe,args.sdk_bin,inputs,output)
    except ValueError: pass
    else: raise AssertionError('existing output overwritten')
    need(output.read_bytes()==out_raw,'existing output changed')
    nonreset=render('nonreset',extra=['--samples',2])
    try: run_dispatch(args.probe,args.sdk_bin,nonreset,folder/'nonreset.rrout')
    except ValueError: pass
    else: raise AssertionError('missing SDK history accepted')
    summary=dict(result='pass',scope='reset-dispatch-execution',quality_acceptance='not-evaluated' if zero_light['passed'] else 'failed-zero-light-oracle',zero_light=zero_light,
                 raw_sdk_acceptance='failed',cases=cases,report_mutations=len(changes),bad_inputs=len(corrupt),bad_outputs=len(damaged),artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='pass',scope=summary['scope'],artifacts=str(folder))))
    if args.require_zero_light: need(zero_light['passed'],('zero-light quality oracle failed',zero_light))


if __name__=='__main__': main()
