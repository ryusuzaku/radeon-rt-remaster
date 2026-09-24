"""Paired 128x96/256x192 native RR sensitivity measurement; no promotion."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import time
import numpy as np

from inspect_rr_record import MAX_BYTES
from scene_io import decode_scene,encode_scene
from rr_recorded_dispatch import admit_record,run_recording
from rr_quality import analyze_setting_pair
from rr_setting_surfaces import require

EXTENTS=((128,96),(256,192))
SETTINGS=('none','stability-zero')


def resized(scene,width,height):
    result=dict(scene); result['draws']=[dict(draw) for draw in scene['draws']]
    result.update(width=width,height=height)
    for draw in result['draws']:
        draw['viewport']=[0,0,width,height,0.,1.]; draw['scissor']=[0,0,width,height]
    return result


def aggregate(report,name):
    items=[]
    for frame in report['frames']:
        if frame['reset']: continue
        item=frame['all'] if name in ('spatial','raw','fallback') else frame['temporal'] if name=='temporal' else frame['groups']['disoccluded']
        key={'spatial':'rr_mse','raw':'raw_mse','fallback':'fallback_mse','temporal':'rr_residual_mse','disoccluded':'rr_mse'}[name]
        if item['pixels'] and item[key] is not None: items.append((item['pixels'],item[key]))
    require(items,f'missing {name} resolution metric')
    return sum(n*v for n,v in items)/sum(n for n,_ in items)


def summarize(cases):
    values={}
    for surface in ('texture','pbr'):
        values[surface]={}
        for setting in SETTINGS:
            values[surface][setting]={}
            for extent in EXTENTS:
                report=cases[f'{surface}-{extent[0]}x{extent[1]}']['reports'][setting]
                values[surface][setting][f'{extent[0]}x{extent[1]}']={name:aggregate(report,name) for name in ('raw','spatial','temporal','disoccluded','fallback')}
            low=values[surface][setting]['128x96']; high=values[surface][setting]['256x192']
            values[surface][setting]['high_over_low']={name:high[name]/low[name] if low[name] else None for name in low}
        values[surface]['zero_minus_default']={}
        for extent in ('128x96','256x192'):
            default=values[surface]['none'][extent]; zero=values[surface]['stability-zero'][extent]
            values[surface]['zero_minus_default'][extent]={name:zero[name]-default[name] for name in default}
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr','scene','materials'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512),default=256)
    parser.add_argument('--seed',type=int,choices=(1,7,23),default=7)
    args=parser.parse_args(); started=time.monotonic(); require(8*args.samples<=4096,'reference work budget')
    for path in (args.probe,args.dxr,args.scene,args.materials): require(path.is_file(),f'missing input: {path}')
    require(args.sdk_bin.is_dir(),'missing SDK bin directory')
    shader=args.dxr.resolve().parent/'rrt_rr_inputs.dxil'; require(shader.is_file(),'missing RR input shader')
    original=decode_scene(args.scene.read_bytes()); require(original['complete'],'incomplete source scene')
    folder=Path(tempfile.mkdtemp(prefix='rr-resolutions-',dir=args.probe.resolve().parent)); cases={}
    for width,height in EXTENTS:
        scene_path=folder/f'source-{width}x{height}.rrscene'; scene_path.write_bytes(encode_scene(resized(original,width,height)))
        for surface in ('texture','pbr'):
            material=args.materials if surface=='pbr' else None; label=f'{surface}-{width}x{height}'
            print(label+': capture',flush=True); recording=folder/(label+'.rrcapture')
            command=[str(args.dxr),str(scene_path),'--mode','gi','--sun-radius','0','--samples','8','--seed',str(args.seed),
                     '--rr-step','.04','0','0','--rr-record',str(recording),'--debug']
            if material: command+=['--materials',str(material)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=120)
            require(process.returncode==0,('capture failed',process.stdout,process.stderr))
            with recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
            data=admit_record(raw); require((data['width'],data['height'],data['count'])==(width,height,8),'native recording extent changed')
            candidates={}
            for setting in SETTINGS:
                stem=f'{label}-{setting}'; print(stem+': dispatch',flush=True)
                output=folder/(stem+'.rrrecordout'); execution=folder/(stem+'-execution.json')
                worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=scene_path,shader=shader,materials=material,
                                     query_defaults=setting!='none',filter_setting=setting,coordinate_scale='unit-one')
                execution.write_text(json.dumps(worker),encoding='utf-8')
                require(worker['decision']['rr_rendering'],'resolution execution failed; evidence retained')
                candidates[setting]=(output,execution)
            reports,arrays=analyze_setting_pair(recording,candidates,scene_path,shader,samples=args.samples,
                                                 surface_reference=True,materials=material,coordinate_scale='unit-one',
                                                 progress=lambda i,n,label=label:print(f'{label} reference {i+1}/{n}',flush=True))
            reference=folder/(label+'-reference.npz')
            with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
            reference_hash=sha256(reference.read_bytes()).hexdigest()
            for setting,report in reports.items():
                report.update(reference_file_sha256=reference_hash,native_extent=[width,height])
                (folder/f'{label}-{setting}-quality.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            cases[label]=dict(surface=surface,extent=[width,height],recording_sha256=raw[-32:].hex(),reference_sha256=reference_hash,reports=reports)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='paired-native-resolution-sensitivity',extents=[list(x) for x in EXTENTS],
                 seed=args.seed,samples_per_batch=args.samples,cases=cases,paired_summary=summarize(cases),artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('result','quality_acceptance','paired_summary','artifacts','elapsed_seconds')}))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
