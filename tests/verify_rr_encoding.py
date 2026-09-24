"""Paired SDK albedo encodings, provenance rejection and unchanged inputs."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import numpy as np

from verify_rr_color_response import cases,need
from verify_dxr import encode_scene
from rr_recorded_dispatch import run_recording,admit_record,decode_recording_output,assess_recording
from rr_quality import analyze
from rr_color_response import response
from rr_dispatch import packed_hashes


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args(); started=time.monotonic()
    folder=Path(tempfile.mkdtemp(prefix='rr-encoding-',dir=args.probe.parent)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    measurements={}; saved={}; baseline_matches=0
    for name in ('white','grey','linear','point','black','linear_history','linear_reset'):
        print(name+': canonical recording and paired dispatch',flush=True)
        scene=cases()['linear' if name=='linear_reset' else name]; source=folder/(name+'.rrscene'); source.write_bytes(encode_scene(scene))
        recording=folder/(name+'.rrcapture'); count=8 if name=='linear_history' else 4 if name=='linear_reset' else 2
        extra=['--rr-step','.03','0','0','--rr-reset-frame','2'] if name=='linear_reset' else []
        process=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--light-intensity','0',
                                '--ambient','0' if name=='black' else '.25','--samples',str(count),'--seed','1','--rr-record',str(recording),'--debug',*extra],capture_output=True,text=True,timeout=45)
        need(process.returncode==0,(process.stdout,process.stderr)); original=recording.read_bytes(); data=admit_record(original)
        reports={}; outputs={}; frames={}; arrays={}; workers={}
        for encoding in ('linear','sqrt'):
            output=folder/(name+'-'+encoding+'.rrrecordout'); execution=folder/(name+'-'+encoding+'-execution.json')
            worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,albedo_encoding=encoding)
            need(worker['decision']['rr_rendering'] and worker['decision']['raw_sdk_acceptance']=='failed',worker)
            execution.write_text(json.dumps(worker),encoding='utf-8'); workers[encoding]=worker
            outputs[encoding]=output.read_bytes(); frames[encoding]=np.array(decode_recording_output(outputs[encoding],original,albedo_encoding=encoding)[1])
            report,reference=analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,fallback=True,albedo_encoding=encoding)
            # Analytic reference for the single non-PBR plane; independent
            # means were validated against this estimator in rr_colour_response.
            need(all(all(r[3]==100000 and r[23]==1 for r in f['records']) for f in data['frames']),'analytic fixture contract')
            report['response']=[response(reference['mean'][i],pixels[:,:3],np.ones(128*96,dtype=bool)) for i,pixels in enumerate(frames[encoding])]
            reports[encoding]=report; arrays[encoding]=reference
            need(recording.read_bytes()==original,'canonical input mutated')
        need(all(np.array_equal(arrays['linear'][k],arrays['sqrt'][k]) for k in arrays['linear']),'encoding changed reference/fallback')
        for i,frame in enumerate(data['frames']):
            a=workers['linear']['decision']['sequence']['frames'][i]; b=workers['sqrt']['decision']['sequence']['frames'][i]
            need(all(a['packed_sha256'][k]==b['packed_sha256'][k] for k in (0,1,2,4,5)),'encoding changed non-albedo resource')
            need(a['dispatch_flags']==int(frame['reset'])+2 and b['dispatch_flags']==int(frame['reset']),'encoding flag mismatch')
            if name in ('grey','linear','point','linear_history','linear_reset'): need(a['packed_sha256'][3]!=b['packed_sha256'][3],'encoded texture did not change')
        reference_path=folder/(name+'-reference.npz')
        with reference_path.open('xb') as stream: np.savez_compressed(stream,**arrays['linear'])
        for encoding,report in reports.items():
            report['reference_file_sha256']=sha256(reference_path.read_bytes()).hexdigest()
            (folder/(name+'-'+encoding+'-quality.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        measurements[name]=dict(linear=[dict(mse=f['mse'],gain=f['centered_gain'],max_error=f['max_absolute_error']) for f in reports['linear']['response']],
                                sqrt=[dict(mse=f['mse'],gain=f['centered_gain'],max_error=f['max_absolute_error']) for f in reports['sqrt']['response']],
                                output_max_difference=float(np.max(np.abs(frames['linear'][:,:,:3]-frames['sqrt'][:,:,:3]))))
        print(json.dumps(dict(case=name,measurement=measurements[name])),flush=True)
        saved[name]=(recording,source,original,data,workers,outputs,frames)
        if args.baseline and name!='linear_reset':
            need((args.baseline/(name+'.rrcapture')).read_bytes()==original,'historical recording mismatch')
            need((args.baseline/(name+'.rrrecordout')).read_bytes()==outputs['linear'],'default output changed from historical binary')
            baseline_matches+=1
    recording,source,raw,data,workers,outputs,frames=saved['linear']; rejected=0
    def rejects(fn):
        nonlocal rejected
        try: fn()
        except (ValueError,KeyError): rejected+=1
        else: raise AssertionError('invalid encoding provenance accepted')
    rejects(lambda:decode_recording_output(outputs['sqrt'],raw))
    rejects(lambda:decode_recording_output(outputs['linear'],raw,albedo_encoding='sqrt'))
    rejects(lambda:decode_recording_output(outputs['sqrt'],raw,albedo_encoding='unknown'))
    for offset,value in [(8,1),(20,0),(20,2)]:
        changed=bytearray(outputs['sqrt']); struct.pack_into('<I',changed,offset,value); changed[-32:]=sha256(changed[:-32]).digest()
        rejects(lambda:decode_recording_output(changed,raw,albedo_encoding='sqrt'))
    for mutation in ('root','frame','flags','bool_flags','missing_encoding','missing_flags','missing_both','packing'):
        envelope=copy.deepcopy(workers['sqrt']['worker']); root=json.loads(envelope['stdout']); frame=root['sequence_test']['frames'][0]
        if mutation=='root': root['sequence_test']['albedo_encoding']='linear'
        elif mutation=='frame': frame['albedo_encoding']='linear'
        elif mutation=='flags': frame['dispatch_flags']=3
        elif mutation=='bool_flags': frame['dispatch_flags']=True
        elif mutation=='missing_encoding': del frame['albedo_encoding']
        elif mutation=='missing_flags': del frame['dispatch_flags']
        elif mutation=='missing_both': del frame['albedo_encoding']; del frame['dispatch_flags']
        else: frame['packed_sha256']=packed_hashes(data['frames'][0])
        envelope['stdout']=json.dumps(root)
        need(assess_recording(envelope,raw,albedo_encoding='sqrt')['status']=='unavailable',mutation); rejected+=1
    need(assess_recording(workers['sqrt']['worker'],raw)['status']=='unavailable','sqrt report implicitly accepted as linear'); rejected+=1
    sqrt_output=folder/'linear-sqrt.rrrecordout'; sqrt_execution=folder/'linear-sqrt-execution.json'
    rejects(lambda:analyze(recording,sqrt_output,source,shader,sqrt_execution,samples=64,surface_reference=True))
    for value in ('linear',None):
        altered=copy.deepcopy(workers['sqrt'])
        if value is None: del altered['albedo_encoding']
        else: altered['albedo_encoding']=value
        bad_execution=folder/('wrong-encoding-'+str(value)+'.json'); bad_execution.write_text(json.dumps(altered),encoding='utf-8')
        rejects(lambda:analyze(recording,sqrt_output,source,shader,bad_execution,samples=64,surface_reference=True,albedo_encoding='sqrt'))
    cli_report=folder/'sqrt-cli-quality.json'; cli_reference=folder/'sqrt-cli-reference.npz'
    cli=[sys.executable,str(Path(__file__).resolve().parents[1]/'tools/rr_quality.py'),'--recording',str(recording),'--output',str(sqrt_output),
         '--scene',str(source),'--shader',str(shader),'--execution',str(sqrt_execution),'--surface-reference','--fallback',
         '--albedo-encoding','sqrt','--samples','64','--report',str(cli_report),'--reference',str(cli_reference),'--require-gates']
    p=subprocess.run(cli,capture_output=True,text=True,timeout=60)
    need(p.returncode==2 and cli_report.is_file() and cli_reference.is_file(),('sqrt CLI must retain failed gate evidence',p.stdout,p.stderr))
    need(json.loads(cli_report.read_text())['albedo_encoding']=='sqrt','quality CLI lost encoding provenance')
    # Historical reports without either field remain linear-only; a partial
    # field pair must not use that compatibility allowance.
    envelope=copy.deepcopy(workers['linear']['worker']); root=json.loads(envelope['stdout']); del root['sequence_test']['albedo_encoding']
    for frame in [*root['sequence_test']['frames'],root['dispatch_test']]: del frame['albedo_encoding']; del frame['dispatch_flags']
    envelope['stdout']=json.dumps(root); need(assess_recording(envelope,raw)['status']=='recording-report-ready','legacy linear report rejected')
    root['sequence_test']['frames'][0]['dispatch_flags']=3; envelope['stdout']=json.dumps(root)
    need(assess_recording(envelope,raw)['status']=='unavailable','partial linear metadata accepted'); rejected+=1
    with patch('rr_recorded_dispatch.subprocess.run',side_effect=AssertionError('invalid mode launched a process')):
        for mode in ('',True,None,[], 'gamma'):
            rejects(lambda:run_recording(args.probe,args.sdk_bin,recording,folder/'invalid.rrrecordout',scene=source,shader=shader,albedo_encoding=mode))
    for options in (['--albedo-encoding','sqrt'],['--isolated-context','--albedo-encoding','sqrt'],['--isolated-recording','--albedo-encoding','bad'],['--isolated-recording','--albedo-encoding','linear','--albedo-encoding','sqrt']):
        p=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),*options],capture_output=True,text=True,timeout=10)
        need(p.returncode!=0,'native invalid option accepted'); rejected+=1
    # An omitted native option must be identical to explicit linear mode.
    default_out=folder/'native-default.rrrecordout'
    p=subprocess.run([str(args.probe),'--isolated-recording','--sdk-bin',str(args.sdk_bin),'--input',str(recording),'--output',str(default_out),'--debug'],capture_output=True,text=True,timeout=45)
    need(p.returncode==0 and assess_recording(json.loads(p.stdout),raw)['status']=='recording-report-ready','native default dispatch failed')
    need(default_out.read_bytes()==outputs['linear'],'native omitted mode changed default output')
    failed=run_recording(args.probe,args.sdk_bin,recording,folder/'injected.rrrecordout',scene=source,shader=shader,albedo_encoding='sqrt',fail_allocation=2)
    need(not failed['decision']['rr_rendering'] and failed['worker']['child_reaped'] and not (folder/'injected.rrrecordout').exists(),'encoded failure containment')
    recovered=folder/'recovered.rrrecordout'; run_recording(args.probe,args.sdk_bin,recording,recovered,scene=source,shader=shader,albedo_encoding='sqrt')
    need(recovered.read_bytes()==outputs['sqrt'],'encoded recovery changed output')
    summary=dict(result='pass',quality_acceptance='not-qualified',measurements=measurements,rejected_cases=rejected,
                 baseline_matches=baseline_matches,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
