"""Stationary persistent-context execution and reset isolation; not quality acceptance."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_dxr import fixture,encode_scene
from inspect_rr_inputs import HEADER as INPUT_HEADER, FILE_BYTES, decode_inputs
from rr_sequence import encode_sequence,decode_sequence,run_sequence,decode_sequence_output,assess_sequence,HEADER
from rr_dispatch import run_dispatch
from rr_worker import strict_json,assess


def need(ok,why):
    if not ok: raise AssertionError(why)


def seal(raw):
    raw=bytearray(raw); raw[-32:]=sha256(raw[:-32]).digest(); return bytes(raw)


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--require-zero-light',action='store_true',help='also enforce the exact-zero quality oracle (currently fails)')
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='rr-sequence-',dir=args.probe.parent)); source=folder/'source.rrscene'
    source.write_bytes(encode_scene(fixture())); frames=[]; cases={}
    for i in range(4):
        path=folder/f'frame-{i}.rrinputs'
        process=subprocess.run([str(args.dxr),str(source),'--mode','gi','--samples',str(i+1),'--sun-radius','0','--rr-inputs',str(path),'--debug'],capture_output=True,text=True,timeout=45)
        need(process.returncode==0,(process.stdout,process.stderr)); frames.append(path.read_bytes())
    def execute(name,parts,**options):
        raw=encode_sequence(parts); path=folder/(name+'.rrseq'); path.write_bytes(raw); out=folder/(name+'.rrseqout')
        result=run_sequence(args.probe,args.sdk_bin,path,out,**options); cases[name]=result
        if options:
            need(not result['decision']['rr_rendering'] and result['worker']['child_reaped'] and not out.exists(),result)
            return result,None,None
        need(result['decision']['rr_rendering'],result)
        chunks,rows=decode_sequence_output(out.read_bytes(),raw)
        need(result['decision']['raw_sdk_acceptance']=='failed' and result['decision']['quality_acceptance']=='not-evaluated','status overclaim')
        return result,chunks,rows
    sequence=frames+frames
    report,chunks,rows=execute('history-reset',sequence)
    need(chunks[:4]==chunks[4:],'reset failed to isolate history')
    _,repeat,_=execute('repeat',sequence)
    need(chunks==repeat,'sequence nondeterminism')
    single_path=folder/'single.rrout'
    single=run_dispatch(args.probe,args.sdk_bin,folder/'frame-0.rrinputs',single_path)
    need(single['decision']['rr_rendering'] and single_path.read_bytes()==chunks[0],'single/reset compatibility')
    # Same final noisy sample/guides but explicitly discarded history, solely
    # as an ablation control. Original exporter samples are kept intact.
    control=bytearray(frames[3]); struct.pack_into('<I',control,36,1)
    for pixel in range(128*96):
        struct.pack_into('<f',control,INPUT_HEADER.size+pixel*96+15*4,0)
        struct.pack_into('<3f',control,INPUT_HEADER.size+pixel*96+16*4,0,0,0)
    control=seal(control); control_path=folder/'reset-control.rrinputs'; control_path.write_bytes(control)
    control_out=folder/'reset-control.rrout'; result=run_dispatch(args.probe,args.sdk_bin,control_path,control_out)
    need(result['decision']['rr_rendering'],result)
    temporal_changed=sum(a!=b for a,b in zip(chunks[3][56:-32],control_out.read_bytes()[56:-32]))
    need(temporal_changed>0,'history has no observable influence')
    black=[]
    for frame in frames[:2]:
        data=bytearray(frame)
        for pixel in range(128*96): struct.pack_into('<3f',data,INPUT_HEADER.size+pixel*96,0,0,0)
        black.append(seal(data))
    _,dark_chunks,dark_rows=execute('zero-light',black)
    _,transition,_=execute('lit-to-dark-reset',frames[:2]+black)
    need(transition[2:]==dark_chunks,'reset leaked lit history into dark segment')
    zero_light=[dict(maximum=max(x for row in frame for x in row[:3]),mse=sum(x*x for row in frame for x in row[:3])/(128*96*3)) for frame in dark_rows]
    for name,opts in [('external-budget',dict(external_mib=1)),('context-budget',dict(budget_mib=1)),('sdk-allocation',dict(fail_allocation=2))]:
        execute(name,frames[:2],**opts)
    _,recovered,_=execute('recovered',sequence); need(recovered==chunks,'fresh worker recovery changed output')
    need(assess(report['worker'],cycles=1,allow_workaround=True)['status']=='unavailable','context-only accepted sequence')
    root=strict_json(report['worker']['stdout']); mutations=[]
    for key,value in [('dispatches',7),('contexts_created',8),('contexts_destroyed',0)]:
        bad=copy.deepcopy(root); bad[key]=value; mutations.append(bad)
    for key,value in [('reset',True),('frame_index',0),('submissions',2),('resources_released',8),('input_sha256','0'*64),('external_bytes',0),('inputs_unchanged',False)]:
        bad=copy.deepcopy(root); bad['sequence_test']['frames'][1][key]=value; mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['frames'].pop(); mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['input_sha256']='0'*64; mutations.append(bad)
    bad=copy.deepcopy(root); bad['dispatch_test']['resources_released']=0; mutations.append(bad)
    raw=encode_sequence(sequence)
    for bad in mutations:
        env=copy.deepcopy(report['worker']); env['stdout']=json.dumps(bad)
        decision=assess_sequence(env,raw)
        need(not decision['rr_rendering'] and decision['status']=='unavailable','mutated report accepted')
    invalid=[raw[:-1],raw+b'!',b'BADMAGIC'+raw[8:]]
    def frame_mutation(index,offset,fmt,value):
        parts=list(frames[:2]); changed=bytearray(parts[index]); struct.pack_into(fmt,changed,offset,value); parts[index]=seal(changed)
        data=HEADER.pack(b'RRTRRS01',1,2,FILE_BYTES,0)+b''.join(parts)
        return data+sha256(data).digest()
    invalid += [frame_mutation(0,36,'<I',0),frame_mutation(1,24,'<I',4),frame_mutation(1,28,'<I',0),frame_mutation(1,32,'<I',99),
                frame_mutation(1,40+48*4,'<f',.25),frame_mutation(1,40,'<f',.5),
                frame_mutation(1,INPUT_HEADER.size+1000*96+16*4,'<f',.1)]
    active=next(i for i,r in enumerate(decode_inputs(frames[1])['records']) if r[23])
    invalid += [frame_mutation(1,INPUT_HEADER.size+active*96+4*4,'<f',.123),
                frame_mutation(1,INPUT_HEADER.size+active*96+12*4,'<f',.123),
                frame_mutation(1,INPUT_HEADER.size+active*96+15*4,'<f',0),
                frame_mutation(0,24,'<I',1)]
    # Exact count/reserved bounds with a valid outer checksum.
    for offset,value in [(12,9),(20,1),(16,FILE_BYTES-1)]:
        data=bytearray(raw); struct.pack_into('<I',data,offset,value); invalid.append(seal(data))
    for i,bad in enumerate(invalid):
        try: decode_sequence(bad)
        except ValueError: pass
        else: raise AssertionError(('Python accepted malformed sequence',i))
        path=folder/f'bad-{i}.rrseq'; out=folder/f'bad-{i}.rrseqout'; path.write_bytes(bad)
        process=subprocess.run([str(args.probe),'--isolated-sequence','--sdk-bin',str(args.sdk_bin.resolve()),'--input',str(path.resolve()),'--output',str(out.resolve()),'--debug'],capture_output=True,text=True,timeout=45)
        need(process.returncode==0,process.stderr); env=strict_json(process.stdout)
        need(env['child_reaped'] and env['exit_code']!=0 and 'RR context:' not in env['stderr'] and not out.exists(),env)
    output=(folder/'history-reset.rrseqout').read_bytes()
    damaged=[output[:-1],output+b'!',b'BADMAGIC'+output[8:]]
    bad=bytearray(output); bad[24]^=1; damaged.append(seal(bad))
    bad=bytearray(output); bad[56:56+196696]=output[56+196696:56+2*196696]; damaged.append(seal(bad))
    for bad in damaged:
        try: decode_sequence_output(bad,raw)
        except ValueError: pass
        else: raise AssertionError('damaged output accepted')
    try: run_sequence(args.probe,args.sdk_bin,folder/'history-reset.rrseq',folder/'history-reset.rrseqout')
    except ValueError: pass
    else: raise AssertionError('overwrite accepted')
    need((folder/'history-reset.rrseqout').read_bytes()==output,'existing output changed')
    summary=dict(result='pass',scope='stationary-history-execution',quality_acceptance='failed-zero-light-oracle' if any(x['maximum'] for x in zero_light) else 'not-evaluated',
                 zero_light=zero_light,temporal_changed_bytes=temporal_changed,cases=cases,report_mutations=len(mutations),bad_inputs=len(invalid),bad_outputs=len(damaged),artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='pass',scope=summary['scope'],quality_acceptance=summary['quality_acceptance'],artifacts=str(folder))))
    if args.require_zero_light: need(not any(x['maximum'] for x in zero_light),('zero-light quality oracle failed',zero_light))


if __name__=='__main__': main()
