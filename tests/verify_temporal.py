"""Hardware temporal reuse: fresh samples, disocclusion, resets and moments."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from verify_dxr import fixture, ROOT
from scene_io import encode_scene
from inspect_signals import load_signals, summarize, HEADER, RECORD
from export_gltf import png


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dxr',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,help='Optional previous temporal-* artifacts for byte-exact comparison on the same GPU/driver')
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='temporal-',dir=args.dxr.parent))
    env={k:v for k,v in os.environ.items() if not k.startswith('RRT_')}
    def run(command,ok=True):
        result=subprocess.run([str(v) for v in command],env=env,capture_output=True,text=True,timeout=60)
        assert (result.returncode==0)==ok,(command,result.stdout,result.stderr)
        return result
    probe=json.loads(run([args.dxr,'--probe']).stdout)
    if not probe['supported']: return 77
    debug=['--debug'] if probe['debug_available'] else []
    scene=fixture(); source=folder/'source.rrscene'; source.write_bytes(encode_scene(scene))
    def render(name,extra=(),scene_path=source):
        signals=folder/(name+'.signals'); pixels=folder/(name+'.pixels')
        report=json.loads(run([args.dxr,scene_path,'--mode','gi','--signals',signals,'--pixels',pixels,*debug,*extra]).stdout)
        data=load_signals(signals); image=pixels.read_bytes()
        bgra=bytearray()
        for i in range(0,len(image),3): bgra.extend(image[i:i+3]+b'\xff')
        (folder/(name+'.png')).write_bytes(png(data.width,data.height,bgra))
        assert report['scene_build_submissions']==1 and report['gpu_temporal_ms']>=0
        assert data.version==2 and report['signal_stride']==144
        return data,image,report
    def mse(a,b): return sum((x-y)**2 for x,y in zip(a,b))/len(a)
    stationary,stationary_pixels,stationary_info=render('stationary',['--temporal','--samples','8'])
    raw,raw_pixels,_=render('raw-eight',['--samples','8'])
    assert stationary_pixels==raw_pixels,'stationary temporal mean differs from raw progressive mean'
    assert all(a[:16]==b[:16] for a,b in zip(stationary.records(),raw.records()))
    assert stationary.pixel(30,30)[32:33]==(8,)
    assert stationary.pixel(30,30)[34:36]==(1,0)
    assert stationary_info['temporal_resets']==0
    # Independently recompute luminance moments from the actual fresh samples.
    fresh=[]
    for n in range(1,9):
        prefix,_,_=render(f'prefix-{n}',['--temporal','--samples',str(n)])
        fresh.append(prefix.pixel(45,57)[24:27])
        if n==1: assert all(r[34]==0 and r[35]==2 for r in prefix.records())
    means=[sum(v[c] for v in fresh)/len(fresh) for c in range(3)]
    values=[sum(c*w for c,w in zip(v,(.2126,.7152,.0722))) for v in fresh]
    moment=sum(v*v for v in values)/len(values); variance=moment-(sum(values)/len(values))**2
    row=stationary.pixel(45,57)
    assert max(abs(a-b) for a,b in zip(means,row[28:31]))<1e-6
    assert abs(row[31]-moment)<1e-6 and abs(row[33]-variance)<1e-6,(row,moment,variance)
    capped,_,_=render('capped',['--temporal','--samples','64'])
    assert max(r[32] for r in capped.records())==32 and capped.pixel(30,30)[32]==32
    for name,extra in [('reset',[]),('light',['--light','.7','.2','-.5']),('cut',['--camera-offset','1.1','0','0'])]:
        reset,image,info=render(name,['--temporal','--samples','8','--temporal-test',name])
        fresh_reset,fresh_image,_=render(name+'-fresh',['--temporal',*extra])
        assert image==fresh_image and all(a[24:]==b[24:] for a,b in zip(reset.records(),fresh_reset.records()))
        assert info['temporal_resets']==1 and info['history_resets']==1 and info['dispatches']==9
        assert all(r[32]==1 and r[34]==0 and r[35]==2 for r in reset.records())
    reset_history,history_pixels,history_info=render('history',['--temporal','--samples','8','--history-test'])
    assert history_pixels==stationary_pixels and history_info['history_resets']==18 and history_info['temporal_resets']==17
    _,window_pixels,_=render('window',['--temporal','--samples','8','--window-test'])
    assert window_pixels==stationary_pixels
    # Same draw, material and normal on two depths: rejection must use actual
    # surface position/depth, not merely draw ID or colour.
    perspective=copy.deepcopy(scene); ground=perspective['draws'][0]; front=perspective['draws'][1]
    ground['vertices']=[list(v) for v in ground['vertices']]+[list(v) for v in front['vertices']]
    ground['indices']=list(ground['indices'])+[i+4 for i in front['indices']]
    ground['projection']=[1.,0,0,0, 0,1.3,0,0, 0,0,2/1.9,1, 0,0,-.2/1.9,0]
    perspective['draws']=[ground]; perspective['attempted']=1
    perspective_path=folder/'perspective.rrscene'; perspective_path.write_bytes(encode_scene(perspective))
    moved,moved_pixels,moved_info=render('moved',['--temporal','--samples','32','--temporal-test','move'],perspective_path)
    before,_,before_info=render('before',['--temporal','--samples','32'],perspective_path)
    moved_again,repeated,_=render('moved-repeat',['--temporal','--samples','32','--temporal-test','move'],perspective_path)
    reference,reference_pixels,_=render('reference',['--samples','256','--camera-offset','.1','.1','0'],perspective_path)
    assert moved_pixels==repeated and moved.payload==moved_again.payload
    reasons=summarize(moved)['temporal_reasons']
    assert reasons['0']>1000 and reasons['7']>10,reasons
    assert moved_info['temporal_resets']==0 and moved_info['history_resets']==1 and moved_info['dispatches']==33
    assert moved_info['requested_buffer_bytes']==before_info['requested_buffer_bytes']
    revealed=0
    for y in range(moved.height):
        for x in range(moved.width):
            row=moved.pixel(x,y)
            if not row[14]: continue
            px=math.floor(x+row[12]+.5); py=math.floor(y+row[13]+.5)
            if not (0<=px<before.width and 0<=py<before.height): continue
            prior=before.pixel(px,py)
            if row[22]>.7 and prior[11] and prior[22]<.4:
                assert row[35]==7 and row[34]==0,'newly revealed ground reused the old foreground'
                revealed+=1
    assert revealed>10,revealed
    accepted_raw=[]; accepted_temporal=[]; accepted_reference=[]
    for r,ref in zip(moved.records(),reference.records()):
        if r[34]:
            assert r[32]>1
            accepted_raw.extend(r[24:27]); accepted_temporal.extend(r[28:31]); accepted_reference.extend(ref[:3])
        else:
            assert r[32]==1 and r[28:31]==r[24:27],'rejected history contaminated the new sample'
    raw_error=mse(accepted_raw,accepted_reference); temporal_error=mse(accepted_temporal,accepted_reference)
    assert temporal_error<raw_error*.8,(raw_error,temporal_error)
    material_scene=copy.deepcopy(scene)
    for draw in material_scene['draws']: draw['projection']=ground['projection']
    material_path=folder/'material.rrscene'; material_path.write_bytes(encode_scene(material_scene))
    material,_,_=render('material-move',['--temporal','--samples','8','--temporal-test','move'],material_path)
    assert summarize(material)['temporal_reasons']['6']>10,'draw/material history mismatch not rejected'
    # v1 compatibility remains explicit rather than silently reinterpreting stride.
    v1=folder/'legacy.signals'
    v1.write_bytes(HEADER.pack(b'RRTSIG01',1,raw.width,raw.height,80,raw.samples,0,raw.mode)
                   +b''.join(RECORD.pack(*r[:20]) for r in raw.records()))
    assert load_signals(v1).version==1
    invalid=bytearray((folder/'stationary.signals').read_bytes())
    struct.pack_into('<f',invalid,HEADER.size+32*4,33)
    invalid_path=folder/'bad-count.signals'; invalid_path.write_bytes(invalid)
    try: load_signals(invalid_path)
    except ValueError: pass
    else: raise AssertionError('accepted excessive temporal history')
    for extra in (['--temporal-test','move'],['--temporal-test','unknown'],['--temporal','--temporal-test','reset']):
        run([args.dxr,source,*extra],ok=False)
    baseline=None
    if args.baseline:
        files=sorted(p for p in folder.iterdir() if p.suffix in ('.rrscene','.pixels','.signals'))
        for path in files:
            assert path.read_bytes()==(args.baseline/path.name).read_bytes(),f'baseline mismatch: {path.name}'
        baseline=dict(path=str(args.baseline),files_compared=len(files),byte_identical=True)
    summary=dict(result='pass',capabilities=probe,baseline=baseline,stationary=summarize(stationary),moving=summarize(moved),newly_revealed_pixels=revealed,
                 accepted_raw_mse=raw_error,accepted_temporal_mse=temporal_error,moving_render=moved_info,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary)); return 0


if __name__=='__main__': sys.exit(main())
