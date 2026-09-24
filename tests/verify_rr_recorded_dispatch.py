"""Recorded RR motion, reset isolation and fail-closed boundaries; not image quality."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

from verify_dxr import fixture,encode_scene
from inspect_rr_record import decode_record,PREFIX,STRIDE,METADATA
from inspect_rr_inputs import FILE_BYTES
from material_inputs import compile_materials
from rr_recorded_dispatch import admit_record,run_recording,assess_recording,decode_recording_output
from rr_sequence import run_sequence,encode_sequence,decode_sequence_output
from rr_dispatch import run_dispatch
from rr_worker import strict_json


def need(ok,why):
    if not ok: raise AssertionError(why)


def seal(raw):
    raw=bytearray(raw); raw[-32:]=sha256(raw[:-32]).digest(); return bytes(raw)


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rr-recorded-dispatch-',dir=args.probe.parent))
    source=folder/'source.rrscene'; scene=fixture(); source.write_bytes(encode_scene(scene)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'; cases={}
    def record(name,extra=(),count=4):
        path=folder/(name+'.rrcapture')
        p=subprocess.run([str(args.dxr),str(source),'--mode','gi','--samples',str(count),'--rr-record',str(path),'--debug',*map(str,extra)],capture_output=True,text=True,timeout=45)
        need(p.returncode==0,(p.stdout,p.stderr)); admit_record(path.read_bytes()); return path
    def execute(name,path,**options):
        output=folder/(name+'.rrrecordout'); report=run_recording(args.probe,args.sdk_bin,path,output,scene=source,shader=shader,**options); cases[name]=report
        if any(k in options for k in ('budget_mib','external_mib','fail_allocation')):
            need(not report['decision']['rr_rendering'] and report['worker']['child_reaped'] and not output.exists(),report); return report,None,None
        need(report['decision']['rr_rendering'],report)
        need(report['decision']['raw_sdk_acceptance']=='failed' and report['decision']['quality_acceptance']=='not-evaluated','acceptance overclaim')
        chunks,rows=decode_recording_output(output.read_bytes(),path.read_bytes()); return report,chunks,rows
    stationary=record('stationary',['--sun-radius',0]); _,stationary_chunks,_=execute('stationary',stationary)
    old=folder/'stationary.rrseq'; old_raw=encode_sequence(decode_record(stationary.read_bytes())['parts']); old.write_bytes(old_raw)
    old_out=folder/'stationary.rrseqout'; old_report=run_sequence(args.probe,args.sdk_bin,old,old_out)
    need(old_report['decision']['rr_rendering'] and decode_sequence_output(old_out.read_bytes(),old_raw)[0]==stationary_chunks,'stationary compatibility failed')
    moving=record('moving',['--rr-step',.05,.02,0]); report,chunks,rows=execute('moving',moving)
    _,repeat,_=execute('repeat',moving); need(chunks==repeat,'moving output nondeterministic')
    rotated=record('rotated',['--yaw',7,'--pitch',-3,'--rr-step',.02,.01,.01],count=3); execute('rotated',rotated)
    reset=record('reset',['--rr-step',.03,0,0,'--rr-reset-frame',2]); _,reset_chunks,reset_rows=execute('reset',reset)
    reset_data=decode_record(reset.read_bytes()); single=folder/'reset.rrinputs'; single.write_bytes(reset_data['parts'][2]); single_out=folder/'reset.rrout'
    single_report=run_dispatch(args.probe,args.sdk_bin,single,single_out)
    need(single_report['decision']['rr_rendering'] and single_out.read_bytes()==reset_chunks[2],'reset differs from fresh single context')
    fresh=record('fresh',['--camera-offset',.06,0,0,'--rr-step',.03,0,0],count=2); _,_,fresh_rows=execute('fresh',fresh)
    need(fresh_rows==reset_rows[2:],'history leaked across explicit reset')
    cut=record('cut',['--rr-step',1.1,0,0],count=8); _,cut_chunks,_=execute('cut',cut)
    for i,part in enumerate(decode_record(cut.read_bytes())['parts']):
        inp=folder/f'cut-{i}.rrinputs'; inp.write_bytes(part); out=folder/f'cut-{i}.rrout'
        result=run_dispatch(args.probe,args.sdk_bin,inp,out)
        need(result['decision']['rr_rendering'] and out.read_bytes()==cut_chunks[i],'cut retained history')
    eight=record('eight',['--rr-step',.02,0,0],count=8); execute('eight',eight)
    materials=folder/'material.rrmat'; materials.write_bytes(compile_materials(dict(schema='rrt-materials',version=1,
        materials=[dict(target=d['material_id'],base_color=[.7,.8,.9],roughness=.4,metallic=.2,emissive=[.1,.2,.3]) for d in scene['draws']]),scene))
    material=record('material',['--materials',materials,'--rr-step',.02,0,0],count=2); execute('material',material,materials=materials)
    # Nearest-neighbour prior draw-ID mismatch/out-of-bounds is a coverage
    # diagnostic, not a complete geometric disocclusion or quality oracle.
    data=decode_record(moving.read_bytes()); visibility=[]
    for previous,frame in zip(data['frames'],data['frames'][1:]):
        changed=0
        for pixel,row in enumerate(frame['records']):
            if not row[23]: continue
            u=(pixel%128+.5)/128+row[16]; v=(pixel//128+.5)/96+row[17]
            changed+=not (0<=u<1 and 0<=v<1) or previous['records'][int(v*96)*128+int(u*128)][23]!=row[23]
        visibility.append(changed)
    need(any(visibility),'moving fixture lacks visibility-change coverage')
    for name,options in [('external-budget',dict(external_mib=1)),('context-budget',dict(budget_mib=1)),('sdk-failure',dict(fail_allocation=2))]:
        execute(name,moving,**options)
    _,recovered,_=execute('recovered',moving); need(chunks==recovered,'fresh worker recovery changed output')
    # External source mismatches must reject before even launching the host.
    source_failures=[dict(scene=shader),dict(shader=source),dict(materials=materials)]
    for i,change in enumerate(source_failures+[{},dict(materials=shader)]):
        opts=dict(scene=source,shader=shader); opts.update(change); path=moving if i<3 else material
        with patch('rr_recorded_dispatch.subprocess.run',side_effect=AssertionError('host launched before source check')):
            try: run_recording(args.probe,args.sdk_bin,path,folder/f'wrong-source-{i}.out',**opts)
            except ValueError: pass
            else: raise AssertionError('wrong/missing source accepted')
    raw=moving.read_bytes(); root=strict_json(report['worker']['stdout']); mutations=[]
    for key,value in [('frame_index',0),('camera_delta',[.05,.02,0]),('camera_delta',[False,0,0]),('camera_delta',[float('nan'),0,0]),('submissions',2),('resources_released',8),('input_sha256','0'*64),('inputs_unchanged',False)]:
        bad=copy.deepcopy(root); bad['sequence_test']['frames'][1][key]=value; mutations.append(bad)
    for key in ('scene_sha256','material_sha256','shader_sha256','settings_sha256'):
        bad=copy.deepcopy(root); bad['sequence_test']['recording'][key]='f'*64; mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['frames'].pop(); mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['input_sha256']='0'*64; mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['reset_policy']='flag-only'; mutations.append(bad)
    bad=copy.deepcopy(root); bad['dispatch_test']['resources_released']=0; mutations.append(bad)
    bad=copy.deepcopy(root); bad['dispatch_test']['resources_released']=8.0; mutations.append(bad)
    bad=copy.deepcopy(root); bad['sequence_test']['frames'][1]['changed_pixels']=-1; mutations.append(bad)
    for bad in mutations:
        env=copy.deepcopy(report['worker']); env['stdout']=json.dumps(bad)
        need(assess_recording(env,raw)['status']=='unavailable','malformed report accepted')
    invalid=[raw[:-1],raw+b'!',b'BADMAGIC'+raw[8:]]
    for offset,value in [(12,9),(16,1),(20,80),(PREFIX+STRIDE,0),(PREFIX+STRIDE+4,7),(PREFIX+STRIDE+8,2),(PREFIX+STRIDE+12,1)]:
        bad=bytearray(raw); struct.pack_into('<I',bad,offset,value); invalid.append(seal(bad))
    for offset in (24,88):
        bad=bytearray(raw); bad[offset:offset+32]=bytes(32); invalid.append(seal(bad))
    bad=bytearray(raw); bad[120]^=1; invalid.append(seal(bad))
    # Self-consistent requested poses/settings, but a different actual camera:
    # metadata checks alone must not be enough for worker admission.
    bad=bytearray(raw); step=struct.unpack('<f',struct.pack('<f',.04))[0]; struct.pack_into('<f',bad,192,step)
    for i in range(data['count']): struct.pack_into('<f',bad,PREFIX+i*STRIDE+16,i*step)
    bad[204:236]=sha256(bad[120:204]).digest(); invalid.append(seal(bad))
    for offset,value in [(136,float('nan')),(168,2.0)]:
        bad=bytearray(raw); struct.pack_into('<f',bad,offset,value); bad[204:236]=sha256(bad[120:204]).digest(); invalid.append(seal(bad))
    active=next(i for i,r in enumerate(data['frames'][1]['records']) if r[23])
    for offset,fmt,value in [(24,'<I',7),(28,'<I',0),(36,'<I',1),(40+48*4,'<f',.25),(360+active*96+16*4,'<f',.2),(360+active*96+15*4,'<f',0),(360+active*96,'<f',100000)]:
        bad=bytearray(raw); start=PREFIX+STRIDE+METADATA.size; struct.pack_into(fmt,bad,start+offset,value)
        bad[start:start+FILE_BYTES]=seal(bad[start:start+FILE_BYTES]); invalid.append(seal(bad))
    for i,bad in enumerate(invalid):
        try: admit_record(bad)
        except ValueError: pass
        else: raise AssertionError(('managed malformed recording accepted',i))
        path=folder/f'bad-{i}.rrcapture'; path.write_bytes(bad); out=folder/f'bad-{i}.rrrecordout'
        p=subprocess.run([str(args.probe),'--isolated-recording','--sdk-bin',str(args.sdk_bin.resolve()),'--input',str(path.resolve()),'--output',str(out.resolve()),'--debug'],capture_output=True,text=True,timeout=45)
        need(p.returncode==0,p.stderr); env=strict_json(p.stdout)
        need(env['child_reaped'] and env['exit_code']!=0 and 'RR context:' not in env['stderr'] and not env['stdout'] and not out.exists(),env)
    output=(folder/'moving.rrrecordout').read_bytes(); damaged=[output[:-1],output+b'!',b'RRTRRT01'+output[8:]]
    bad=bytearray(output); bad[24]^=1; damaged.append(seal(bad))
    bad=bytearray(output); bad[56:56+len(chunks[0])]=chunks[1]; damaged.append(seal(bad))
    for bad in damaged:
        try: decode_recording_output(bad,raw)
        except ValueError: pass
        else: raise AssertionError('damaged recording output accepted')
    try: run_recording(args.probe,args.sdk_bin,moving,folder/'moving.rrrecordout',scene=source,shader=shader)
    except ValueError: pass
    else: raise AssertionError('overwrite accepted')
    need((folder/'moving.rrrecordout').read_bytes()==output,'existing output changed')
    summary=dict(result='pass',scope='recorded-motion-execution',quality_acceptance='not-evaluated',cases=cases,
                 visibility_changes=visibility,report_mutations=len(mutations),bad_inputs=len(invalid),bad_outputs=len(damaged),source_failures=5,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('result','scope','quality_acceptance','visibility_changes','artifacts')}))


if __name__=='__main__': main()
