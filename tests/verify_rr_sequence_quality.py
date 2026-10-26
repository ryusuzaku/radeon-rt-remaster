"""Eight-frame RR motion/reveal measurements; passing validates the harness only."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import time
import numpy as np

from verify_dxr import fixture,encode_scene,decode_scene
from rr_recorded_dispatch import admit_record,run_recording,decode_recording_output
from rr_quality import analyze
from rr_sequence_quality import measure_history,history_metrics


def need(ok,message):
    if not ok: raise AssertionError(message)


def save(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False); stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); started=time.monotonic()
    folder=Path(tempfile.mkdtemp(prefix='rr-sequence-quality-',dir=args.probe.parent))
    scene=fixture()
    for draw in scene['draws']:
        draw['projection']=[1.,0,0,0,0,1.3,0,0,0,0,2/1.9,1,0,0,-.2/1.9,0]
        # Keep the extended trajectory off exact half-pixel triangle edges:
        # the strict float64/float32 primary-ID oracle remains unchanged.
        draw['vertices']=[(vertex[0]+.00123,*vertex[1:]) for vertex in draw['vertices']]
    scene_bytes=encode_scene(scene)
    scene=decode_scene(scene_bytes)
    source=folder/'source.rrscene'; source.write_bytes(scene_bytes)
    shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    def capture(label,options,count=8):
        path=folder/(label+'.rrcapture')
        process=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0',
                                '--samples',str(count),'--rr-record',str(path),'--debug',*options],
                               capture_output=True,text=True,timeout=60)
        need(process.returncode==0,(process.stdout,process.stderr))
        renderer=json.loads(process.stdout); save(folder/(label+'-renderer.json'),renderer)
        raw=path.read_bytes(); data=admit_record(raw)
        need(data['count']==count and renderer['rr_dispatches']==0,'recording contract changed')
        return path,raw,data
    def dispatch(label,path,raw):
        output=folder/(label+'.rrrecordout')
        evidence=run_recording(args.probe,args.sdk_bin,path,output,scene=source,shader=shader)
        execution=folder/(label+'-execution.json'); save(execution,evidence)
        need(evidence['decision']['rr_rendering'] and evidence['decision']['raw_sdk_acceptance']=='failed',evidence)
        need(evidence['decision']['quality_acceptance']=='not-evaluated','execution claimed quality')
        context=evidence['decision']['context']
        need(context['peak_callback_bytes']==20971520,'SDK callback allocation changed')
        need(all(frame['external_bytes']==1900544 for frame in evidence['decision']['sequence']['frames']),
             'sequence external allocation changed')
        return output,execution,decode_recording_output(output.read_bytes(),raw)[1]
    definitions={
        'lateral': ['--seed','1','--rr-step','.03125','0','0'],
        'depth-rotated': ['--seed','2','--yaw','7','--pitch','-3','--rr-step','.03125','.015625','.0078125'],
        'reset': ['--seed','1','--rr-step','.03125','0','0','--rr-reset-frame','4'],
    }
    cases={}; captures={}; candidate_rows={}; buffer_peaks=[]
    for label,options in definitions.items():
        print(label+': capture and dispatch',flush=True)
        recording,raw,data=capture(label,options); captures[label]=(recording,raw,data)
        output,execution,rows=dispatch(label,recording,raw); candidate_rows[label]=rows
        expected=[0,4] if label=='reset' else [0]
        need([i for i,frame in enumerate(data['frames']) if frame['reset']]==expected,'unexpected reset/cut')
        report,arrays=analyze(recording,output,source,shader,execution,samples=512,
                              progress=lambda i,n:print(f'{label}: reference {i+1}/{n}',flush=True))
        history,ages=measure_history(scene,data,rows,arrays)
        arrays['reveal_age']=ages
        reference=folder/(label+'-reference.npz')
        with reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
        report['reference_file_sha256']=sha256(reference.read_bytes()).hexdigest()
        history.update(recording_sha256=report['recording_sha256'],output_sha256=report['output_sha256'],
                       reference_file_sha256=report['reference_file_sha256'],
                       implementation_sha256=sha256(Path(__file__).resolve().parents[1].joinpath('tools/rr_sequence_quality.py').read_bytes()).hexdigest())
        # Save measurements before enforcing coverage. Failed quality gates are
        # evidence, while broken coverage or controls fail this harness test.
        save(folder/(label+'-quality.json'),report); save(folder/(label+'-history.json'),history)
        need(report['quality_acceptance']==history['quality_acceptance']=='not-qualified','quality overclaim')
        need(report['total_samples_per_hit']==1024 and data['count']*report['samples_per_batch']==4096,'reference budget changed')
        for i,frame in enumerate(report['frames']):
            if frame['reset']:
                need(not arrays['visibility_masks'][i].any() and np.all(ages[i]==-1),'reset borrowed temporal coverage')
            else:
                need(sum(group['pixels'] for group in frame['groups'].values())==frame['all']['pixels'],'visibility partition failed')
                need(frame['groups']['disoccluded']['pixels']>20 and frame['temporal']['pixels']>100,'missing geometric coverage')
        tracked=ages>=1
        need(np.count_nonzero(tracked)>20 and np.any(ages>=(2 if label=='reset' else 3)),
             'no persistent reveal cohort')
        # A known trail must remain detectable beyond the first reveal frame.
        selected=next(i for i in range(8) if np.any(ages[i]>=1))
        target=arrays['mean'][selected]; trail=target.copy(); trail[ages[selected]>=1]+=.25
        control=history_metrics(target,trail,target,np.zeros_like(target),ages[selected])
        need(all(abs(entry['rr_mse']-.0625)<1e-12 for entry in control if entry['age']>=1 and entry['pixels']),
             'persistent injected trail escaped the metric')
        save(folder/(label+'-trail-control.json'),control)
        buffer_peaks.append(json.loads((folder/(label+'-renderer.json')).read_text())['peak_requested_bytes'])
        cases[label]=dict(recording_sha256=report['recording_sha256'],quality_gates=report['gates'],history_gates=history['gates'],
                          disoccluded_pixels=[f['groups']['disoccluded']['pixels'] for f in report['frames']],
                          offscreen_pixels=[f['groups']['offscreen']['pixels'] for f in report['frames']],
                          tracked_pixels_by_age=[int(np.count_nonzero(ages==age)) for age in range(8)])
    need(sum(cases['lateral']['offscreen_pixels'])>0,'offscreen coverage absent')
    # Same source/output bytes must survive a fresh worker; reset history must
    # equal an independently captured four-frame segment at the reset pose.
    path,raw,_=captures['lateral']; repeat_output,_,_=dispatch('repeat',path,raw)
    repeat_equal=repeat_output.read_bytes()==(folder/'lateral.rrrecordout').read_bytes()
    save(folder/'repeat-equivalence.json',dict(output_bundle_byte_equal=repeat_equal,
         first_sha256=sha256((folder/'lateral.rrrecordout').read_bytes()).hexdigest(),
         repeat_sha256=sha256(repeat_output.read_bytes()).hexdigest()))
    fresh,fresh_raw,fresh_data=capture('fresh-reset',['--seed','1','--camera-offset','.125','0','0','--rr-step','.03125','0','0'],count=4)
    _,_,fresh_rows=dispatch('fresh-reset',fresh,fresh_raw)
    # Global frame ordinals differ, but actual fresh samples and guides agree.
    reset_frames=captures['reset'][2]['frames'][4:]
    inputs_equal=all(np.asarray(a['records'],dtype='<f4').tobytes()==np.asarray(b['records'],dtype='<f4').tobytes()
                     and all(np.asarray(a['matrices'][key],dtype='<f4').tobytes()==np.asarray(b['matrices'][key],dtype='<f4').tobytes()
                             for key in a['matrices']) for a,b in zip(fresh_data['frames'],reset_frames))
    reset_execution=json.loads((folder/'reset-execution.json').read_text())['decision']['sequence']['frames'][4:]
    fresh_execution=json.loads((folder/'fresh-reset-execution.json').read_text())['decision']['sequence']['frames']
    dispatch_equal=all(all(a[key]==b[key] for key in ('frame_index','reset','camera_delta','dispatch_flags','packed_sha256','formats'))
                       for a,b in zip(reset_execution,fresh_execution))
    differences=[]
    for i,(a,b) in enumerate(zip(candidate_rows['reset'][4:],fresh_rows)):
        a=np.asarray(a,dtype='<f4'); b=np.asarray(b,dtype='<f4')
        changed=a.view('<u4')!=b.view('<u4'); delta=a.astype(np.float64)-b
        differences.append(dict(segment_index=i,pixels_not_bit_equal=int(np.count_nonzero(changed.any(axis=1))),
                                channels_not_bit_equal=int(np.count_nonzero(changed)),
                                maximum_absolute_rgb_difference=float(np.max(np.abs(delta[:,:3]))),
                                rgb_difference_mse=float(np.mean(delta[:,:3]**2))))
    reset_equal=all(row['channels_not_bit_equal']==0 for row in differences)
    save(folder/'reset-equivalence.json',dict(input_records_and_matrices_byte_equal=inputs_equal,
         dispatch_indices_flags_camera_delta_and_packing_equal=dispatch_equal,output_pixels_byte_equal=reset_equal,
         frames=differences,interpretation='exact output equivalence control; does not identify an SDK-internal cause'))
    need(len(set(buffer_peaks))==1,'motion increased renderer buffer peak')
    summary=dict(result='pass' if repeat_equal and inputs_equal and dispatch_equal and reset_equal else 'failed-exact-controls',
                 scope='bounded-sequence-quality-harness',quality_acceptance='not-qualified',
                 raw_sdk_acceptance='failed',samples_per_batch=512,total_samples_per_hit=1024,
                 cases=cases,repeat_byte_equal=repeat_equal,reset_fresh_byte_equal=reset_equal,
                 reset_inputs_byte_equal=inputs_equal,reset_dispatch_metadata_equal=dispatch_equal,reset_differences=differences,
                 renderer_requested_buffer_peak_bytes=buffer_peaks[0],
                 sdk_callback_peak_bytes=20971520,external_bytes=1900544,
                 test_implementation_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                 elapsed_seconds=time.monotonic()-started)
    save(folder/'verification.json',summary)
    print(json.dumps(dict(summary,artifacts=folder.name)))
    need(repeat_equal,'eight-frame motion replay changed; evidence retained; exact gate unchanged')
    need(inputs_equal and dispatch_equal,'fresh segment inputs/dispatch differ; evidence retained')
    need(reset_equal,'post-reset output differs from a fresh segment; evidence retained; exact gate unchanged')


if __name__=='__main__': main()
