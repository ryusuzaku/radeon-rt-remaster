"""Textured/PBR reference and matched fallback controls; no quality promotion."""
import argparse
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import struct
import tempfile
import time
from unittest.mock import patch
import numpy as np

from verify_dxr import fixture,encode_scene,decode_scene
from verify_rr_inputs import Oracle,Random,hash32,add,scale,basis
from material_inputs import compile_materials
from rr_reference import PIXELS
from rr_surface_reference import SurfaceReference,read_materials
from rr_fallback import spatial
from rr_quality import analyze
from rr_recorded_dispatch import admit_record,run_recording


def need(ok,message):
    if not ok: raise AssertionError(message)


def scalar_filter(frame,rgb,index,primary):
    # Separate scalar implementation, deliberately no vector port helpers.
    rows=frame['records']; c=rows[index]
    if not c[23]: return rgb[index]
    n=primary['normal'][index]; total=[0.,0.,0.]; weights=0
    for y in range(-2,3):
        for x in range(-2,3):
            xx=index%128+x; yy=index//128+y
            if not (0<=xx<128 and 0<=yy<96): continue
            j=yy*128+xx; tap=rows[j]
            if tap[23]!=c[23] or sum(a*b for a,b in zip(n,primary['normal'][j]))<.95: continue
            if abs(primary['distance'][j]-primary['distance'][index])>max(.005,.02*primary['distance'][index]) or any(abs(primary['color'][j,k]-primary['color'][index,k])>.1 for k in range(3)): continue
            w=math.exp(-(x*x+y*y)/2.88); weights+=w
            for k in range(3): total[k]+=rgb[j,k]/max(primary['color'][j,k],.05)*w
    return [total[k]/max(weights,1e-8)*max(primary['color'][index,k],.05) for k in range(3)]


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,default=512); args=parser.parse_args()
    started=time.monotonic(); folder=Path(tempfile.mkdtemp(prefix='rr-surfaces-',dir=args.probe.parent)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    scene=fixture()
    for i,draw in enumerate(scene['draws']):
        draw['projection']=[1.,0,0,0,0,1.3,0,0,0,0,2/1.9,1,0,0,-.2/1.9,0]
        draw['texture_width']=3; draw['texture_height']=2
        draw['texture']=bytes([35,90,220,255,180,60,30,255,80,200,120,255,100,45,200,255,210,170,65,255,15,120,230,255])
        draw['sampler']=list(draw['sampler']); draw['sampler'][0]=i+1; draw['sampler'][1]=3; draw['sampler'][4]=draw['sampler'][5]=2
        draw['vertices']=[(*v[:3],[0xffd0b0e0,0xff90f0c0,0xffe0a080,0xffc0d0f0][j],v[4]*2.17-.31,v[5]*1.79-.21) for j,v in enumerate(draw['vertices'])]
    scene=decode_scene(encode_scene(scene)); source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    authoring={0:dict(base_color=[.7,.8,.9],roughness=.5,metallic=.2,emission=[.01,.02,.01]),
               1:dict(base_color=[.9,.6,.8],roughness=.28,metallic=.65,emission=[.3,.07,.02])}
    sidecar=folder/'surface.rrmat'; sidecar.write_bytes(compile_materials(dict(schema='rrt-materials',version=1,materials=[dict(target=scene['draws'][i]['material_id'],base_color=m['base_color'],roughness=m['roughness'],metallic=m['metallic'],emissive=m['emission']) for i,m in authoring.items()]),scene))
    evidence={}; checks={}; saved={}
    def capture(name,material=None,seed=1,extra=(),count=4):
        recording=folder/(name+'.rrcapture'); output=folder/(name+'.rrrecordout')
        cmd=[str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--samples',str(count),'--seed',str(seed),'--rr-step','.04','0','0','--rr-record',str(recording),'--debug',*extra]
        if material: cmd+=['--materials',str(material)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=45); need(p.returncode==0,(p.stdout,p.stderr))
        data=admit_record(recording.read_bytes()); factors=read_materials(material,scene,data['material_sha256']); tracer=SurfaceReference(scene,data['settings'],factors)
        scalar=Oracle(scene,factors,light=data['settings']['light'],intensity=data['settings']['intensity'],ambient=data['settings']['ambient'],radius=0)
        max_gpu=max_scalar=0.; count_scalar=0
        for frame in data['frames'][:2]:
            primary=tracer.primary(frame); active=np.flatnonzero(primary['hit']); uniforms=[]
            for index in active:
                rng=Random(hash32(int(index))^hash32(frame['random_index']+0x1234567)^hash32(seed)); rng.next(); rng.next(); uniforms.append((rng.next(),rng.next()))
            values=tracer.lighting(primary,active,np.array(uniforms)); expected=np.array(frame['records'])[active,:3]
            max_gpu=max(max_gpu,float(np.max(np.abs(values-expected)))); need(max_gpu<.0005,('GPU surface mismatch',name,max_gpu))
            for j in np.linspace(0,len(active)-1,96,dtype=int):
                index=active[j]; u,v=uniforms[j]; n=primary['normal'][index]; pos=primary['position'][index]; view=primary['view'][index]
                direction=basis(n,(math.sqrt(u)*math.cos(2*math.pi*v),math.sqrt(u)*math.sin(2*math.pi*v),math.sqrt(1-u)))
                secondary=scalar.trace(add(pos,scale(n,.0001)),direction,.0001,100000)
                incoming=scalar.direct(secondary,scale(direction,-1),scalar.light) if secondary else (scalar.ambient,)*3
                throughput=primary['color'][index].copy()
                if primary['pbr'][index]:
                    h=view+direction; h=h/np.linalg.norm(h); vh=np.clip(np.dot(view,h),0,1)
                    throughput*=(1-primary['metallic'][index])*.96*(1-(1-vh)**5)
                max_scalar=max(max_scalar,float(np.max(np.abs(values[j]-throughput*incoming)))); count_scalar+=1
        need(max_scalar<1e-10,('scalar PBR mismatch',name,max_scalar))
        # Texture addressing and pre-interpolation colour decoding, including
        # negative UVs, seams and exact texel centres, against scalar sampling.
        uv=np.array([[-1.2,.13],[-.1,1.1],[0,0],[1/6,1/4],[1,1],[2.3,-.7]])
        for i in range(len(scene['draws'])):
            need(np.allclose(tracer.texture(i,uv),[scalar.texture(scene['draws'][i],tuple(p)) for p in uv],rtol=0,atol=1e-12),'texture scalar mismatch')
        worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,materials=material); need(worker['decision']['rr_rendering'],worker)
        execution=folder/(name+'-execution.json'); execution.write_text(json.dumps(worker),encoding='utf-8')
        checks[name]=dict(gpu_max_error=max_gpu,scalar_max_error=max_scalar,scalar_samples=count_scalar)
        saved[name]=(recording,output,execution,data,tracer)
        return recording,output,execution,data,tracer
    for name,material,seed in [('texture',None,1),('pbr',sidecar,23)]:
        recording,output,execution,data,tracer=capture(name,material,seed)
        print(f'{name}: CPU/GPU/scalar sample checks pass',flush=True)
        report,arrays=analyze(recording,output,source,shader,execution,samples=args.samples,surface_reference=True,materials=material,fallback=True,
                              progress=lambda i,n:print(f'{name} reference {i+1}/{n}',flush=True))
        frame=data['frames'][0]; primary=tracer.primary(frame); raw=np.array(frame['records'])[:,:3].astype(np.float16).astype(float); filtered=spatial(frame,raw,primary)
        for index in np.linspace(0,PIXELS-1,256,dtype=int): need(np.allclose(filtered[index],scalar_filter(frame,raw,index,primary),rtol=0,atol=1e-12),'fallback scalar mismatch')
        need(np.array_equal(filtered,spatial(frame,raw,primary)) and np.all(filtered[np.array(frame['records'])[:,23]==0]==0),'fallback nondeterminism/background mutation')
        need(np.array_equal(spatial(frame,np.zeros_like(raw),primary),np.zeros_like(raw)),'fallback invented black light')
        constant=np.maximum(primary['color'],.05)*.25
        need(np.allclose(spatial(frame,constant,primary),constant,rtol=0,atol=1e-15),'fallback demodulation constant control')
        # No mutation of the immutable source signal.
        need(np.array_equal(raw,np.array(frame['records'])[:,:3].astype(np.float16).astype(float)),'fallback input mutation')
        with (folder/(name+'-reference.npz')).open('xb') as stream: np.savez_compressed(stream,**arrays)
        (folder/(name+'-quality.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8'); evidence[name]=report['gates']
    _,_,_,emission,tracer=capture('emission',sidecar,1,['--ambient','0','--light-intensity','0'],count=2)
    primary=tracer.primary(emission['frames'][0]); active=np.flatnonzero(primary['hit']); primary['hit'][:]=False; primary['hit'][active[::41]]=True
    mean,_,_=tracer.estimate(primary,128,17,0); need(np.any(mean>0) and not tracer.black(),'emission incorrectly treated as analytic black')
    original_scene,original_source=scene,source; scene=copy.deepcopy(scene)
    for draw in scene['draws']:
        draw['sampler']=list(draw['sampler']); draw['sampler'][4]=draw['sampler'][5]=1
    scene=decode_scene(encode_scene(scene)); source=folder/'point.rrscene'; source.write_bytes(encode_scene(scene))
    capture('point',count=2)
    scene,source=original_scene,original_source
    # Each default-kernel rejection criterion gets an isolated impulse control.
    synthetic=np.zeros((PIXELS,24)); synthetic[:,23]=1; center=48*128+64; neighbor=center+1
    synthetic_frame=dict(records=synthetic); guides=dict(draw=np.ones(PIXELS),normal=np.tile([0.,0.,1.],(PIXELS,1)),distance=np.ones(PIXELS),color=np.full((PIXELS,3),.5))
    impulse=np.zeros((PIXELS,3)); impulse[neighbor]=1
    need(np.all(spatial(synthetic_frame,impulse,guides)[center]>0),'fallback impulse missing')
    for criterion in ('draw','normal','depth','albedo'):
        changed=copy.deepcopy(guides); rows=synthetic.copy()
        if criterion=='draw': changed['draw'][neighbor]=rows[neighbor,23]=2
        elif criterion=='normal': changed['normal'][neighbor]=[0,1,0]
        elif criterion=='depth': changed['distance'][neighbor]=1.2
        else: changed['color'][neighbor]=.9
        need(np.all(spatial(dict(records=rows),impulse,changed)[center]==0),('fallback failed guide rejection',criterion))
    rejected=0
    def rejects(fn):
        nonlocal rejected
        try: fn()
        except ValueError: rejected+=1
        else: raise AssertionError('invalid surface input accepted')
    recording,output,execution,data,tracer=saved['pbr']; digest=data['material_sha256']
    rejects(lambda:read_materials(None,scene,digest)); rejects(lambda:read_materials(sidecar,scene,'0'*64)); rejects(lambda:read_materials(source,scene,digest))
    original=sidecar.read_bytes()
    for offset,value in [(8,2),(12,17)]:
        raw=bytearray(original); struct.pack_into('<I',raw,offset,value); raw[-32:]=sha256(raw[:-32]).digest()
        path=folder/f'bad-{offset}.rrmat'; path.write_bytes(raw); rejects(lambda:read_materials(path,scene,sha256(raw).hexdigest()))
    for i,(offset,value) in enumerate([(48,float('nan')),(48,2.),(60,.01),(64,33.),(76,-.1)]):
        raw=bytearray(original); struct.pack_into('<f',raw,offset,value); raw[-32:]=sha256(raw[:-32]).digest()
        path=folder/f'factor-{i}.rrmat'; path.write_bytes(raw); rejects(lambda:read_materials(path,scene,sha256(raw).hexdigest()))
    raw=bytearray(original); raw[16:48]=bytes(32); raw[-32:]=sha256(raw[:-32]).digest()
    path=folder/'unknown.rrmat'; path.write_bytes(raw); rejects(lambda:read_materials(path,scene,sha256(raw).hexdigest()))
    rejects(lambda:analyze(recording,output,source,shader,execution,samples=64,surface_reference=True))
    rejects(lambda:analyze(recording,output,source,shader,execution,samples=64))
    with patch('rr_fallback.SHADER_SOURCE_SHA256','0'*64):
        rejects(lambda:analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,materials=sidecar,fallback=True))
    changed=copy.deepcopy(scene); changed['draws'][0]['texture_width']=17; rejects(lambda:SurfaceReference(changed,data['settings'],{}))
    changed=copy.deepcopy(scene); changed['draws'][0]['sampler']=list(changed['draws'][0]['sampler']); changed['draws'][0]['sampler'][0]=4; rejects(lambda:SurfaceReference(changed,data['settings'],{}))
    summary=dict(result='pass',scope='surface-reference-and-fallback-harness',quality_acceptance='not-qualified',samples_per_batch=args.samples,
                 cases=checks,gates=evidence,rejected_cases=rejected,fallback_guide_controls=4,elapsed_seconds=time.monotonic()-started,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
