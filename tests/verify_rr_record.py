"""Renderer-owned RR input recording, identity, motion and baseline equivalence."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_dxr import fixture,encode_scene
from verify_rr_inputs import Oracle
from material_inputs import compile_materials
from inspect_rr_record import decode_record,load_record,verify_source,PREFIX,STRIDE,METADATA
from inspect_rr_inputs import HEADER,FILE_BYTES
from rr_sequence import decode_sequence


def need(ok,why):
    if not ok: raise AssertionError(why)


def seal(raw):
    raw=bytearray(raw); raw[-32:]=sha256(raw[:-32]).digest(); return bytes(raw)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--dxr',required=True,type=Path); args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='rr-record-',dir=args.dxr.parent)); scene=fixture(); source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    results={}
    def command(argv,ok=True):
        p=subprocess.run([str(args.dxr),*map(str,argv)],capture_output=True,text=True,timeout=60)
        need((p.returncode==0)==ok,(argv,p.stdout,p.stderr)); return json.loads(p.stdout) if ok else None
    def record(name,extra=(),scene_path=source,count=4):
        path=folder/(name+'.rrcapture'); pixels=folder/(name+'.pixels')
        report=command([scene_path,'--mode','gi','--samples',count,'--rr-record',path,'--pixels',pixels,'--debug',*extra]); raw=path.read_bytes(); data=decode_record(raw)
        need(report['rr_recorded_frames']==count and report['rr_input_preparations']==count and report['rr_input_stride']==96 and report['rr_dispatches']==0,'recording report mismatch')
        need(report['scene_build_submissions']==1 and report['dispatches']==count,'unexpected scene/frame submissions')
        verify_source(scene_path,data['scene_sha256'],trailer=True); verify_source(args.dxr.parent/'rrt_rr_inputs.dxil',data['shader_sha256'])
        results[name]=dict(report=report,metadata=data['metadata'],settings_sha256=data['settings_sha256'],scene_sha256=data['scene_sha256'],material_sha256=data['material_sha256'])
        return raw,data,pixels.read_bytes()
    raw,base,pixels=record('stationary')
    again,_,_=record('repeat'); need(raw==again,'recording not deterministic')
    for i,part in enumerate(base['parts']):
        path=folder/f'prefix-{i}.rrinputs'; out=folder/f'prefix-{i}.pixels'
        report=command([source,'--mode','gi','--samples',i+1,'--rr-inputs',path,'--pixels',out,'--debug'])
        need(path.read_bytes()==part,'stationary preparation differs from legacy prefix')
        if i==3: need(pixels==out.read_bytes(),'stationary final renderer pixels changed')
    eight,eight_data,_=record('eight',count=8)
    need(results['eight']['report']['peak_requested_bytes']==results['stationary']['report']['peak_requested_bytes'],'recording allocations grow with count')
    need(results['eight']['report']['requested_buffer_bytes']==results['stationary']['report']['requested_buffer_bytes'],'temporary allocation charge leaked')
    moving,motion,_=record('move',['--rr-step',.05,.02,0])
    for frame in motion['frames']: Oracle(scene).check(frame)
    need(any(abs(row[16])+abs(row[17])>0 for row in motion['frames'][1]['records']),'no camera motion captured')
    _,rotated,_=record('rotated-depth-move',['--yaw',7,'--pitch',-3,'--rr-step',.02,.01,.01],count=3)
    for frame in rotated['frames']: Oracle(scene).check(frame)
    need(any(abs(row[18])>.001 for row in rotated['frames'][1]['records']),'no view-Z motion captured')
    reset,reset_data,_=record('reset',['--rr-step',.03,0,0,'--rr-reset-frame',2])
    need([x['random_index'] for x in reset_data['frames']]==[0,1,0,1] and [m['reset_reason'] for m in reset_data['metadata']]==[1,0,2,0],'explicit reset sequence invalid')
    for frame in reset_data['frames']: Oracle(scene).check(frame)
    _,cut,_=record('cut',['--rr-step',1.1,0,0],count=3)
    need([m['reset_reason'] for m in cut['metadata']]==[1,4,4],'automatic cuts missing')
    # A changed off-camera texture/geometry still changes source identity, even
    # if a particular view happens to present the same visible surfaces.
    changed=copy.deepcopy(scene); hidden=copy.deepcopy(changed['draws'][0]); hidden['ordinal']=2
    hidden['vertices']=[(v[0]+100,*v[1:]) for v in hidden['vertices']]
    changed['draws'].append(hidden); changed['attempted']=3
    altered=folder/'altered.rrscene'; altered.write_bytes(encode_scene(changed))
    _,altered_data,_=record('source-identity',scene_path=altered,count=2)
    need(base['scene_sha256']!=altered_data['scene_sha256'],'source identity missing')
    need(base['frames'][0]['records']==altered_data['frames'][0]['records'],'hidden identity fixture changed visible inputs')
    try: verify_source(altered,base['scene_sha256'],trailer=True)
    except ValueError: pass
    else: raise AssertionError('wrong scene accepted')
    materials=folder/'material.rrmat'
    entries=[dict(target=d['material_id'],base_color=[.7,.8,.9],roughness=.4,metallic=.2,emissive=[.1,.2,.3]) for d in scene['draws']]
    materials.write_bytes(compile_materials(dict(schema='rrt-materials',version=1,materials=entries),scene))
    _,material_data,_=record('material-identity',['--materials',materials],count=2)
    verify_source(materials,material_data['material_sha256']); need(material_data['material_sha256']!=base['material_sha256'],'material identity missing')
    _,light_data,_=record('settings-identity',['--ambient',.2],count=2)
    need(light_data['settings_sha256']!=base['settings_sha256'],'lighting settings identity missing')
    # Version separation: even stationary recordings are not silently admitted
    # as older manually assembled worker bundles.
    try: decode_sequence(raw)
    except ValueError: pass
    else: raise AssertionError('stationary worker accepted recording format')
    corrupt=[raw[:-1],raw+b'!',b'BADMAGIC'+raw[8:]]
    for offset,value in [(12,9),(16,1),(20,80),(PREFIX+STRIDE,0),(PREFIX+STRIDE+4,7),(PREFIX+STRIDE+8,2),(PREFIX+STRIDE+12,1)]:
        bad=bytearray(raw); struct.pack_into('<I',bad,offset,value); corrupt.append(seal(bad))
    bad=bytearray(raw); bad[120]^=1; corrupt.append(seal(bad))
    bad=bytearray(raw); struct.pack_into('<f',bad,PREFIX+STRIDE+16,1e38); corrupt.append(seal(bad))
    for offset,value in [(136,float('nan')),(168,2.0)]:
        bad=bytearray(raw); struct.pack_into('<f',bad,offset,value); bad[204:236]=sha256(bad[120:204]).digest(); corrupt.append(seal(bad))
    for offset in (24,88):
        bad=bytearray(raw); bad[offset:offset+32]=bytes(32); corrupt.append(seal(bad))
    for offset,value in [(36,1),(24,7),(28,7),(40+48*4,.25),(HEADER.size+1000*96+16*4,.2)]:
        bad=bytearray(moving); start=PREFIX+STRIDE+METADATA.size
        struct.pack_into('<I' if offset in (24,28,36) else '<f',bad,start+offset,value)
        bad[start:start+FILE_BYTES]=seal(bad[start:start+FILE_BYTES]); corrupt.append(seal(bad))
    for bad in corrupt:
        try: decode_record(bad)
        except ValueError: pass
        else: raise AssertionError('corrupt recording accepted')
    invalid=[['--samples',1],['--samples',9],['--temporal'],['--denoise'],['--rr-reset-frame',4],['--rr-step','nan',0,0],['--rr-step',3,0,0],['--rr-inputs',folder/'collision.rrinputs']]
    for i,extra in enumerate(invalid):
        out=folder/f'invalid-{i}.rrcapture'
        command([source,'--mode','gi','--samples',4,'--rr-record',out,*extra],False); need(not out.exists(),'invalid mode wrote output')
    command([source,'--mode','gi','--rr-step',.1,0,0],False)
    collision=folder/'case-collision.rrcapture'
    command([source,'--mode','gi','--samples',4,'--rr-record',collision,'--pixels',str(collision).upper()],False)
    need(not collision.exists(),'case-insensitive output collision wrote a file')
    original=(folder/'stationary.rrcapture').read_bytes()
    command([source,'--mode','gi','--samples',4,'--rr-record',folder/'stationary.rrcapture'],False)
    need((folder/'stationary.rrcapture').read_bytes()==original,'existing recording overwritten')
    summary=dict(result='pass',scope='input-recording-only',rr_rendering=False,cases=results,malformed_files=len(corrupt),invalid_modes=len(invalid)+2,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(result='pass',cases=len(results),artifacts=str(folder))))


if __name__=='__main__': main()
