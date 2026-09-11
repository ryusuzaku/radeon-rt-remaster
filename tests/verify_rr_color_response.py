"""Actual SDK colour isolation with an analytic, noise-free ambient plane."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import time
import numpy as np

from verify_dxr import fixture,encode_scene,decode_scene
from rr_reference import PIXELS
from rr_surface_reference import SurfaceReference
from rr_color_response import response
from rr_recorded_dispatch import admit_record,decode_recording_output,run_recording
from rr_quality import analyze


def need(ok,message):
    if not ok: raise AssertionError(message)


def cases():
    source=fixture(); source['draws']=source['draws'][:1]; source['attempted']=1
    draw=source['draws'][0]
    draw['projection']=[1.,0,0,0,0,1.3,0,0,0,0,2/1.9,1,0,0,-.2/1.9,0]
    draw['texture']=bytes([255]*4)
    result={}
    for name,texel in [('white',[255]*3),('grey',[128]*3),('dark',[32]*3),('colour',[35,90,220])]:
        scene=copy.deepcopy(source); scene['draws'][0]['texture']=bytes([*texel,255]); result[name]=scene
    vertex=copy.deepcopy(source)
    vertex['draws'][0]['vertices']=[(*v[:3],[0xffd0b0e0,0xff90f0c0,0xffe0a080,0xffc0d0f0][j],*v[4:]) for j,v in enumerate(draw['vertices'])]
    result['vertex']=vertex
    textured=copy.deepcopy(source); d=textured['draws'][0]
    d['texture_width']=3; d['texture_height']=2
    d['texture']=bytes([35,90,220,255,180,60,30,255,80,200,120,255,100,45,200,255,210,170,65,255,15,120,230,255])
    d['sampler']=list(d['sampler']); d['sampler'][0]=1; d['sampler'][1]=3; d['sampler'][4]=d['sampler'][5]=2
    result['linear']=textured
    point=copy.deepcopy(textured); point['draws'][0]['sampler'][4]=point['draws'][0]['sampler'][5]=1; result['point']=point
    result['black']=copy.deepcopy(source)
    equivalent=copy.deepcopy(source)
    equivalent['draws'][0]['vertices']=[(*v[:3],0xffdc5a23,*v[4:]) for v in draw['vertices']]
    result['colour_vertex']=equivalent
    result['linear_seed']=copy.deepcopy(textured)
    result['linear_history']=copy.deepcopy(textured)
    return {name:decode_scene(encode_scene(scene)) for name,scene in result.items()}


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); started=time.monotonic()
    folder=Path(tempfile.mkdtemp(prefix='rr-colour-',dir=args.probe.parent)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    evidence={}; identities={}; geometry=None; bundles={}; packed_inputs={}
    for name,scene in cases().items():
        print(name+': recording analytic plane',flush=True)
        source=folder/(name+'.rrscene'); source.write_bytes(encode_scene(scene))
        recording=folder/(name+'.rrcapture'); output=folder/(name+'.rrrecordout'); execution=folder/(name+'-execution.json')
        count=8 if name=='linear_history' else 2; seed=23 if name=='linear_seed' else 1
        command=[str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--light-intensity','0','--ambient','0' if name=='black' else '.25',
                 '--samples',str(count),'--seed',str(seed),'--rr-record',str(recording),'--debug']
        process=subprocess.run(command,capture_output=True,text=True,timeout=45)
        need(process.returncode==0,(process.stdout,process.stderr))
        raw=recording.read_bytes(); data=admit_record(raw); tracer=SurfaceReference(scene,data['settings'],{})
        worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader)
        need(worker['decision']['rr_rendering'],worker); execution.write_text(json.dumps(worker),encoding='utf-8')
        rows=np.array(decode_recording_output(output.read_bytes(),raw)[1])
        bundles[name]=rows.copy()
        packed_inputs[name]=[f['packed_sha256'][:5] for f in worker['decision']['sequence']['frames']]
        report,arrays=analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,fallback=True)
        diagnostics=[]; analytic=[]
        for i,frame in enumerate(data['frames']):
            primary=tracer.primary(frame); mask=primary['hit']; inputs=np.array(frame['records'])
            need(mask.all(),'analytic plane must fill the viewport')
            need(np.all(inputs[:,3]==100000),'analytic plane has secondary hits')
            invariant=inputs[:,[7,8,9,10,11,19,20,21,22,23]]
            if geometry is None: geometry=invariant.copy()
            need(np.array_equal(invariant,geometry),'colour experiment changed geometry/guides')
            expected=primary['color']*data['settings']['ambient']; analytic.append(expected)
            gpu_error=float(np.max(np.abs(inputs[:,:3]-expected)))
            need(gpu_error<5e-7,('analytic CPU/GPU disagreement',name,gpu_error))
            # E[x^2]-E[x]^2 can retain cancellation roundoff even for a
            # constant integrand. Bound that in float64 units, not RR error.
            variance_roundoff=128*np.finfo(np.float64).eps*max(1.,float(np.max(expected**2)))/(63*64)
            need(np.allclose(arrays['mean'][i],expected,rtol=0,atol=1e-14) and np.max(arrays['mean_variance'][i])<=variance_roundoff,'Monte Carlo/reference violates analytic control')
            diagnostics.append(dict(frame=i,cpu_gpu_max_error=gpu_error,
                                    rr=response(expected,rows[i,:,:3],mask),raw=response(expected,inputs[:,:3].astype(np.float16).astype(float),mask),
                                    fallback=response(expected,arrays['fallback'][i],mask)))
        arrays['analytic']=np.array(analytic)
        reference=folder/(name+'-reference.npz')
        with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
        report['reference_file_sha256']=sha256(reference.read_bytes()).hexdigest()
        report['colour_response']=diagnostics
        report['implementation_sha256']['rr_color_response.py']=sha256(Path(__file__).resolve().parents[1].joinpath('tools/rr_color_response.py').read_bytes()).hexdigest()
        report['analytic_contract']='single non-PBR plane; every secondary misses; expected linear base colour * recorded ambient'
        (folder/(name+'-quality.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        evidence[name]=[dict(frame=d['frame'],mse=d['rr']['mse'],max_error=d['rr']['max_absolute_error'],bias=d['rr']['bias'],centered_gain=d['rr']['centered_gain']) for d in diagnostics]
        identities[name]=dict(recording=raw[-32:].hex(),reference=report['reference_file_sha256'])
        print(json.dumps(dict(case=name,frames=evidence[name])),flush=True)
    for a,b in [('colour','colour_vertex'),('linear','linear_seed'),('linear','linear_history')]:
        need(packed_inputs[a]==packed_inputs[b][:2],('equivalent source changed packed inputs',a,b))
        need(np.array_equal(bundles[a],bundles[b][:2]),('identical packed prefix changed SDK output',a,b))
    # Pure diagnostic controls: identity, fixed offset, channel swap, constant
    # zero and malformed inputs. None modifies an SDK output or quality gate.
    ramp=np.zeros((96,128,3)); ramp[:,:,0]=np.arange(128)[None,:]/128; ramp[:,:,1]=np.arange(96)[:,None]/96
    ramp=ramp.reshape(PIXELS,3); mask=np.ones(PIXELS,dtype=bool); original=ramp.copy()
    need(response(ramp,ramp,mask)['mse']==0,'response identity')
    swapped=response(ramp,ramp[:,::-1],mask); need(swapped['mse']>0 and swapped['red_blue_swap_mse']==0,'response channel-swap control')
    moved=np.roll(ramp.reshape(96,128,3),1,axis=1).reshape(PIXELS,3)
    shifted=response(ramp,moved,mask); best=min(shifted['fixed_offset_scan'],key=lambda v:v['mse'])
    need(best['dx']==1 and best['dy']==0 and best['mse']==0,'response offset control')
    need(np.array_equal(ramp,original),'response mutated input')
    zero=response(np.zeros_like(ramp),np.zeros_like(ramp),mask); need(zero['mse']==0 and zero['correlation']==[None]*3,'response zero')
    rejected=0
    for a,b,m in [(ramp[:-1],ramp,mask),(ramp,ramp,mask&False),(ramp,ramp+np.nan,mask)]:
        try: response(a,b,m)
        except ValueError: rejected+=1
        else: raise AssertionError('response invalid input admitted')
    summary=dict(result='pass',quality_acceptance='not-qualified',scope='analytic-colour-response-harness',cases=evidence,
                 identities=identities,rejected_cases=rejected,equivalent_pairs=3,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
