"""Reference/metric validity plus actual RR measurements; not a quality promotion."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import numpy as np

from verify_dxr import fixture,encode_scene
from verify_rr_inputs import Oracle,Random,hash32,scale,basis,add,transform,norm,sub,dot
from rr_reference import Reference,PIXELS
from rr_recorded_dispatch import run_recording,admit_record,decode_recording_output
from rr_quality import analyze,measure,errors


def need(ok,message):
    if not ok: raise AssertionError(message)


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,default=512)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rr-quality-',dir=args.probe.parent)); start=time.monotonic()
    scene=fixture()
    for draw in scene['draws']: draw['projection']=[1.,0,0,0,0,1.3,0,0,0,0,2/1.9,1,0,0,-.2/1.9,0]
    source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    def capture(name,extra=(),count=4):
        path=folder/(name+'.rrcapture')
        p=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--samples',str(count),'--rr-step','.04','0','0','--rr-record',str(path),'--debug',*extra],capture_output=True,text=True,timeout=45)
        need(p.returncode==0,(p.stdout,p.stderr)); raw=path.read_bytes(); data=admit_record(raw)
        out=folder/(name+'.rrrecordout'); evidence=run_recording(args.probe,args.sdk_bin,path,out,scene=source,shader=shader)
        need(evidence['decision']['rr_rendering'],evidence)
        execution=folder/(name+'-execution.json'); execution.write_text(json.dumps(evidence),encoding='utf-8')
        return path,out,execution,data,decode_recording_output(out.read_bytes(),raw)[1]
    recording,output,execution,data,rows=capture('moving')
    tracer=Reference(scene,data['settings']); primary=tracer.primary(data['frames'][0]); active=np.flatnonzero(primary['hit'])
    # Reproduce only the validation sample directions with the legacy RNG;
    # high-sample reference estimation always uses different PCG64 streams.
    uniforms=[]
    for pixel in active:
        rng=Random(hash32(int(pixel))^hash32(0x1234567)^hash32(data['settings']['seed']))
        rng.next(); rng.next(); uniforms.append((rng.next(),rng.next()))
    values=tracer.lighting(primary,active,np.array(uniforms)); gpu=np.array(data['frames'][0]['records'])[active,:3]
    error=float(np.max(np.abs(values-gpu))); need(error<.0005,('CPU/GPU sample disagreement',error))
    settings=data['settings']; scalar=Oracle(scene,light=settings['light'],intensity=settings['intensity'],ambient=settings['ambient'],radius=0); scalar_error=0
    for j in np.linspace(0,len(active)-1,64,dtype=int):
        index=int(active[j]); n=primary['normal'][index]; pos=primary['position'][index]; u,v=uniforms[j]
        direction=basis(n,(np.sqrt(u)*np.cos(2*np.pi*v),np.sqrt(u)*np.sin(2*np.pi*v),np.sqrt(1-u)))
        hit=scalar.trace(add(pos,scale(n,.0001)),direction,.0001,100000)
        incoming=scalar.direct(hit,scale(direction,-1),scalar.light) if hit else (scalar.ambient,)*3
        expected=np.array(incoming)*primary['color'][index]; scalar_error=max(scalar_error,float(np.max(np.abs(values[j]-expected))))
    need(scalar_error<1e-10,('vector/scalar mismatch',scalar_error))
    print('Matched CPU/GPU and scalar reference checks pass',flush=True)
    report,arrays=analyze(recording,output,source,shader,execution,samples=args.samples,progress=lambda i,n:print(f'CPU reference {i+1}/{n}',flush=True))
    need(report['quality_acceptance']=='not-qualified' and report['raw_sdk_acceptance']=='failed','acceptance overclaim')
    need(sum(f['groups']['disoccluded']['pixels'] for f in report['frames'])>20,'no geometric disocclusion coverage')
    for frame in report['frames'][1:]:
        need(sum(group['pixels'] for group in frame['groups'].values())==frame['all']['pixels'],'visibility masks do not partition active pixels')
    # Serialize numeric-only evidence and verify exact array roundtrip.
    reference=folder/'reference.npz'
    with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
    with np.load(reference,allow_pickle=False) as saved:
        need(set(saved.files)==set(arrays) and all(np.array_equal(saved[k],v) for k,v in arrays.items()),'reference roundtrip mismatch')
    report['reference_file_sha256']=sha256(reference.read_bytes()).hexdigest()
    (folder/'quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    # Determinism, independent streams, and convergence on a fixed sparse set.
    sparse=copy.deepcopy(primary); sparse['hit']=np.zeros(PIXELS,dtype=bool); sparse['hit'][active[::127]]=True
    a=tracer.estimate(sparse,256,17,0); b=tracer.estimate(sparse,256,17,0); c=tracer.estimate(sparse,256,18,0)
    need(all(np.array_equal(x,y) for x,y in zip(a,b)),'reference nondeterministic')
    need(not np.array_equal(a[0],c[0]) and np.any(a[2]),'reference streams not independent')
    low=tracer.estimate(sparse,64,17,0)
    need(a[1].mean()<low[1].mean()*.6,'reference variance did not shrink with sample count')
    # An isolated plane has no hemisphere-facing secondary geometry: the
    # ambient bounce is analytically constant for every sampling direction.
    plane=copy.deepcopy(scene); plane['draws']=plane['draws'][:1]; plane['attempted']=1
    analytic=Reference(plane,data['settings']); pixels=np.array([[20.5,20.5],[100.5,70.5]])
    origin,direction,maximum=analytic.rays(data['frames'][0]['matrices']['inverse_view_projection'],pixels)
    p=analytic.trace(origin,direction,maximum=maximum,pixels=pixels)
    # Embed two known surface points into the bounded full-frame array layout.
    analytic_primary={k:np.repeat(v[:1],PIXELS,axis=0) for k,v in p.items()}; analytic_primary['hit'][2:]=False
    for k,v in p.items(): analytic_primary[k][:2]=v
    expected=analytic_primary['color'][:2]*data['settings']['ambient']; analytic_mean,analytic_variance,_=analytic.estimate(analytic_primary,64,1,0)
    need(np.allclose(analytic_mean[:2],expected,rtol=0,atol=1e-15) and np.max(analytic_variance)<1e-15,'analytic plane reference failed')
    # Metric controls: identity must give zero, and a constructed history trail
    # at independently identified disocclusions must be detected.
    mask=primary['hit']; target=arrays['mean'][0]; variance=np.zeros_like(target)
    need(errors(target,target,target,variance,mask)['rr_mse']==0,'identity metric nonzero')
    dis=arrays['visibility_masks'][1,1]; biased=arrays['mean'][1].copy(); biased[dis]+=.25
    need(abs(errors(arrays['mean'][1],biased,arrays['mean'][1],variance,dis)['rr_mse']-.0625)<1e-12,'ghost injection not detected')
    # A foreground visibility oracle control: a current point revealed by a
    # translated perspective camera must be blocked along the exact old ray.
    visibility,mapping=tracer.visibility(tracer.primary(data['frames'][1]),primary,data['frames'][1],data['frames'][0])
    need(np.array_equal(visibility['disoccluded'],dis),'visibility nondeterminism')
    current=tracer.primary(data['frames'][1]); previous_matrix=data['frames'][0]['matrices']['inverse_view_projection']
    for z in (.05,3.):
        outside=copy.deepcopy(current); index=int(np.flatnonzero(current['hit'])[0]); outside['position'][index]=[0,0,z]
        outside_masks,_=tracer.visibility(outside,primary,data['frames'][1],data['frames'][0])
        need(outside_masks['offscreen'][index] and not outside_masks['disoccluded'][index],'near/far clip misclassified as occlusion')
    scalar_visibility=0
    for label in ('stable','disoccluded'):
        selected=np.flatnonzero(visibility[label])[::31]
        for index in selected:
            pos=current['position'][index]; clip=transform((*pos,1),data['frames'][1]['matrices']['previous_view_projection'])
            ndc=(clip[0]/clip[3],clip[1]/clip[3]); near=transform((*ndc,0,1),previous_matrix); far=transform((*ndc,1,1),previous_matrix)
            origin=scale(near[:3],1/near[3]); end=scale(far[:3],1/far[3]); direction=norm(sub(end,origin))
            hit=scalar.trace(origin,direction,0,np.sqrt(dot(sub(end,origin),sub(end,origin))),((ndc[0]+1)*64,(1-ndc[1])*48))
            visible=hit is not None and hit['index']+1==current['draw'][index] and np.linalg.norm(np.array(hit['position'])-pos)<5e-5
            need(visible==(label=='stable'),'scalar visibility disagrees'); scalar_visibility+=1
    invalid=0
    def rejects(fn):
        nonlocal invalid
        try: fn()
        except (ValueError,KeyError): invalid+=1
        else: raise AssertionError('unsupported/corrupt quality input accepted')
    changed=copy.deepcopy(data); changed['material_sha256']='f'*64; rejects(lambda:measure(scene,changed,rows,samples=64))
    changed=copy.deepcopy(data['settings']); changed['radius']=.1; rejects(lambda:Reference(scene,changed))
    changed=copy.deepcopy(scene); changed['draws'][0]['texture_width']=2; rejects(lambda:Reference(changed,data['settings']))
    changed=copy.deepcopy(scene); changed['draws'][0]['vertices']=list(changed['draws'][0]['vertices']); vertex=list(changed['draws'][0]['vertices'][0]); vertex[3]=0xff000000; changed['draws'][0]['vertices'][0]=vertex
    rejects(lambda:Reference(changed,data['settings']))
    changed=copy.deepcopy(data['frames'][0]); changed['records']=list(changed['records']); row=list(changed['records'][active[0]]); row[23]=0; changed['records'][active[0]]=row
    rejects(lambda:tracer.primary(changed))
    rejects(lambda:tracer.estimate(sparse,63,1,0)); rejects(lambda:tracer.estimate(sparse,64,-1,0))
    rejects(lambda:measure(scene,data,rows[:-1],samples=64)); rejects(lambda:analyze(recording,output,source,source,execution,samples=64))
    oversized=folder/'oversized.rrscene'; oversized.write_bytes(bytes(65537)); rejects(lambda:analyze(recording,output,oversized,shader,execution,samples=64))
    changed=copy.deepcopy(scene); changed['draws'][0]['vertices']=list(changed['draws'][0]['vertices'])*20; rejects(lambda:Reference(changed,data['settings']))
    damaged=folder/'bad-execution.json'; evidence=json.loads(execution.read_text()); evidence['input_sha256']='0'*64; damaged.write_text(json.dumps(evidence))
    rejects(lambda:analyze(recording,output,source,shader,damaged,samples=64))
    # Analytic black oracle, including actual SDK output, with no bias clamp.
    black,black_out,black_execution,black_data,black_rows=capture('black',['--ambient','0','--light-intensity','0'],count=2)
    black_report,black_arrays=analyze(black,black_out,source,shader,black_execution,samples=64)
    need(not np.any(black_arrays['mean']) and not np.any(black_arrays['mean_variance']),'black reference not exactly zero')
    maximum=float(np.max(np.array(black_rows)[:,:,:3])); need(maximum>0 and not black_report['gates']['spatial_non_regression'],'known zero-light failure was hidden')
    (folder/'black-quality.json').write_text(json.dumps(black_report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    cli_report=folder/'black-cli.json'; cli_reference=folder/'black-cli.npz'
    cli=[sys.executable,str(Path(__file__).resolve().parents[1]/'tools/rr_quality.py'),'--recording',str(black),'--output',str(black_out),
         '--scene',str(source),'--shader',str(shader),'--execution',str(black_execution),'--samples','64','--report',str(cli_report),
         '--reference',str(cli_reference),'--require-gates']
    process=subprocess.run(cli,capture_output=True,text=True,timeout=60)
    need(process.returncode==2 and cli_report.is_file() and cli_reference.is_file(),('quality gate CLI did not retain failure evidence',process.stdout,process.stderr))
    original=cli_report.read_bytes(),cli_reference.read_bytes()
    process=subprocess.run(cli,capture_output=True,text=True,timeout=60)
    need(process.returncode==1 and original==(cli_report.read_bytes(),cli_reference.read_bytes()),'CLI overwrote evidence')
    summary=dict(result='pass',scope='quality-harness-validation',quality_acceptance='not-qualified',gates=report['gates'],
                 cpu_gpu_max_error=error,scalar_max_error=scalar_error,rejected_cases=invalid,zero_light_maximum=maximum,
                 scalar_visibility_checks=scalar_visibility,
                 frustum_checks=2,
                 elapsed_seconds=time.monotonic()-start,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
