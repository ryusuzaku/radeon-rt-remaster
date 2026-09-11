"""Predeclared one-setting RR grids, default equivalence and provenance rejection."""
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
from rr_recorded_dispatch import run_recording,admit_record,assess_recording,decode_recording_output
from rr_settings import PRESETS
from rr_quality import analyze
from rr_color_response import response


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args(); started=time.monotonic()
    folder=Path(tempfile.mkdtemp(prefix='rr-settings-',dir=args.probe.parent)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    measurements={}; saved={}; historical=0; controls=0
    for name,count,extra in [('linear',2,[]),('linear_history',8,[]),('linear_reset',4,['--rr-step','.03','0','0','--rr-reset-frame','2']),('black',2,[])]:
        source=folder/(name+'.rrscene'); source.write_bytes(encode_scene(cases()['black' if name=='black' else 'linear']))
        recording=folder/(name+'.rrcapture')
        p=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--light-intensity','0',
                          '--ambient','0' if name=='black' else '.25','--samples',str(count),'--seed','1','--rr-record',str(recording),'--debug',*extra],capture_output=True,text=True,timeout=45)
        need(p.returncode==0,(p.stdout,p.stderr)); raw=recording.read_bytes(); data=admit_record(raw)
        need(all(all(r[23]==1 and r[3]==100000 for r in frame['records']) for frame in data['frames']),'analytic fixture no longer fully covered')
        for encoding in (('linear','sqrt') if name=='linear' else ('linear',)):
            label=name+'-'+encoding; print(label+': one-key grid',flush=True)
            base=None; results={}; stored={}
            for preset in PRESETS:
                output=folder/(label+'-'+preset+'.rrrecordout'); execution=folder/(label+'-'+preset+'-execution.json')
                worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,
                                     albedo_encoding=encoding,query_defaults=True,filter_setting=preset)
                execution.write_text(json.dumps(worker),encoding='utf-8')
                need(worker['decision']['rr_rendering'] and worker['decision']['raw_sdk_acceptance']=='failed',worker)
                chunks,rows=decode_recording_output(output.read_bytes(),raw,albedo_encoding=encoding,filter_setting=preset)
                root=json.loads(worker['worker']['stdout']); pixels=np.asarray(rows)[:,:,:3]
                if preset=='none':
                    base=(chunks,root); report,reference=analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,fallback=True,albedo_encoding=encoding)
                    (folder/(label+'-baseline-quality.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
                    with (folder/(label+'-reference.npz')).open('xb') as stream: np.savez_compressed(stream,**reference)
                    if args.baseline:
                        need((args.baseline/(name+'.rrcapture')).read_bytes()==raw,'historical canonical recording changed')
                        need((args.baseline/(label+'-off.rrrecordout')).read_bytes()==output.read_bytes(),'unconfigured historical output changed'); historical+=1
                else:
                    for c,b in zip(root['context_tests'],base[1]['context_tests']):
                        changed=dict(c); del changed['filter_setting']; need(changed==b,'setting changed defaults/accounting/raw SDK validation')
                    need(all(a['packed_sha256']==b['packed_sha256'] and a['dispatch_flags']==b['dispatch_flags']
                             for a,b in zip(root['sequence_test']['frames'],base[1]['sequence_test']['frames'])),'setting changed input packing/flags')
                    if preset.endswith('-default'):
                        need(chunks==base[0],'configuring queried default changed inner output'); controls+=1
                metric=[]
                for i,rr in enumerate(pixels):
                    ref=reference['mean'][i]; item=response(ref,rr,np.ones(128*96,dtype=bool))
                    raw_rgb=np.asarray(data['frames'][i]['records'])[:,:3].astype(np.float16).astype(float)
                    metric.append(dict(mse=item['mse'],gain=item['centered_gain'],max_error=item['max_absolute_error'],
                                       raw_mse=float(np.mean((raw_rgb-ref)**2)),fallback_mse=float(np.mean((reference['fallback'][i]-ref)**2))))
                results[preset]=metric; stored[preset]=(worker,output,execution,chunks)
                need(recording.read_bytes()==raw,'recording modified')
            measurements[label]=results; saved[label]=(recording,source,raw,stored)
            print(json.dumps(dict(case=label,last_frame_mse={k:v[-1]['mse'] for k,v in results.items()})),flush=True)
    recording,source,raw,stored=saved['linear-linear']; worker,output,execution,chunks=stored['gaussian-one']; rejected=0
    def rejects(fn):
        nonlocal rejected
        try: fn()
        except (ValueError,KeyError): rejected+=1
        else: raise AssertionError('configured output/provenance implicitly accepted')
    rejects(lambda:decode_recording_output(output.read_bytes(),raw))
    rejects(lambda:decode_recording_output(output.read_bytes(),raw,filter_setting='stability-half'))
    rejects(lambda:decode_recording_output(output.read_bytes(),raw,albedo_encoding='sqrt',filter_setting='gaussian-one'))
    rejects(lambda:decode_recording_output(stored['none'][1].read_bytes(),raw,filter_setting='gaussian-one'))
    for offset,value in ((8,1),(20,0),(20,15),(20,16)):
        bad=bytearray(output.read_bytes()); struct.pack_into('<I',bad,offset,value); bad[-32:]=sha256(bad[:-32]).digest()
        rejects(lambda:decode_recording_output(bad,raw,filter_setting='gaussian-one'))
    root=json.loads(worker['worker']['stdout'])
    for mutation in ('sequence','missing_sequence','missing_context','preset','key','value_bits','default_bits','default_query_code',
                     'configure_code','configure_attempted','bool_code','bool_bits','format','count','guard_before','guard_after','extra','missing_queries','default_snapshot'):
        changed=copy.deepcopy(root); context=changed['context_tests'][0]; row=context['filter_setting']
        if mutation=='sequence': changed['sequence_test']['filter_setting']='stability-zero'
        elif mutation=='missing_sequence': del changed['sequence_test']['filter_setting']
        elif mutation=='missing_context': del context['filter_setting']
        elif mutation=='preset': row['preset']='stability-zero'
        elif mutation=='key': row['key']=2
        elif mutation in ('value_bits','default_bits'): row[mutation]=0x3f000000
        elif mutation in ('default_query_code','configure_code'): row[mutation]=6
        elif mutation=='configure_attempted': row[mutation]=False
        elif mutation=='bool_code': row['configure_code']=False
        elif mutation=='bool_bits': row['default_bits']=False
        elif mutation=='format': row[mutation]='float64'
        elif mutation=='count': row[mutation]=True
        elif mutation in ('guard_before','guard_after'): row[mutation]=0
        elif mutation=='extra': row['assumed_success']=True
        elif mutation=='missing_queries': del context['default_queries']
        else: context['default_queries'][0]['queries'][4].update(bits=0x3f800000,value=1)
        envelope=copy.deepcopy(worker['worker']); envelope['stdout']=json.dumps(changed)
        need(assess_recording(envelope,raw,filter_setting='gaussian-one')['status']=='unavailable',mutation); rejected+=1
    need(assess_recording(worker['worker'],raw)['status']=='unavailable','implicit configured report accepted'); rejected+=1
    need(assess_recording(stored['none'][0]['worker'],raw,filter_setting='gaussian-one')['status']=='unavailable','missing expected setting accepted'); rejected+=1
    rejects(lambda:analyze(recording,output,source,shader,execution,samples=64,surface_reference=True))
    report,_=analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,fallback=True,filter_setting='gaussian-one')
    need(report['filter_setting']=='gaussian-one','quality lost setting provenance')
    (folder/'configured-quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    hist_record,hist_source,_,hist_stored=saved['linear_history-linear']
    _,hist_output,hist_execution,_=hist_stored['stability-zero']
    hist_report,_=analyze(hist_record,hist_output,hist_source,shader,hist_execution,samples=64,surface_reference=True,fallback=True,filter_setting='stability-zero')
    (folder/'stability-zero-history-quality.json').write_text(json.dumps(hist_report,indent=2),encoding='utf-8')
    for value in (None,'none',True):
        bad=copy.deepcopy(worker)
        if value is None: del bad['filter_setting']
        else: bad['filter_setting']=value
        path=folder/('wrong-setting-'+str(value)+'.json'); path.write_text(json.dumps(bad),encoding='utf-8')
        rejects(lambda:analyze(recording,output,source,shader,path,samples=64,surface_reference=True,filter_setting='gaussian-one'))
    with patch('rr_recorded_dispatch.subprocess.run',side_effect=AssertionError('invalid preset launched worker')):
        for preset in (None,True,[],1,'nan','gaussian:2'):
            rejects(lambda:run_recording(args.probe,args.sdk_bin,recording,folder/'invalid.rrrecordout',scene=source,shader=shader,filter_setting=preset))
    for opts in (['--filter-setting','stability-half'],['--isolated-context','--filter-setting','gaussian-one'],
                 ['--isolated-recording','--filter-setting','nan'],['--isolated-recording','--filter-setting','none','--filter-setting','gaussian-one']):
        p=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),*opts],capture_output=True,text=True,timeout=10)
        need(p.returncode!=0,'native invalid setting accepted'); rejected+=1
    # Native option alone must imply all default-query snapshots.
    native=folder/'native-implied-query.rrrecordout'
    p=subprocess.run([str(args.probe),'--isolated-recording','--sdk-bin',str(args.sdk_bin),'--input',str(recording),'--output',str(native),
                      '--debug','--filter-setting','gaussian-one'],capture_output=True,text=True,timeout=45)
    need(p.returncode==0 and assess_recording(json.loads(p.stdout),raw,filter_setting='gaussian-one')['status']=='recording-report-ready',(p.stdout,p.stderr))
    need(native.read_bytes()==output.read_bytes(),'native setting forwarding mismatch')
    cli_report=folder/'configured-cli-quality.json'; cli_ref=folder/'configured-cli-reference.npz'
    p=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/rr_quality.py'),'--recording',str(recording),'--output',str(output),
                      '--scene',str(source),'--shader',str(shader),'--execution',str(execution),'--surface-reference','--fallback','--samples','64',
                      '--filter-setting','gaussian-one','--report',str(cli_report),'--reference',str(cli_ref),'--require-gates'],capture_output=True,text=True,timeout=60)
    need(p.returncode==2 and cli_report.is_file() and cli_ref.is_file(),('configured quality must retain failed gates',p.stdout,p.stderr))
    failed_output=folder/'injected.rrrecordout'
    failed=run_recording(args.probe,args.sdk_bin,recording,failed_output,scene=source,shader=shader,filter_setting='gaussian-one',fail_allocation=2)
    (folder/'injected-execution.json').write_text(json.dumps(failed),encoding='utf-8')
    need(not failed['decision']['rr_rendering'] and failed['worker']['child_reaped'] and not failed_output.exists(),'configured allocation-failure containment')
    recovered=folder/'recovered.rrrecordout'; run_recording(args.probe,args.sdk_bin,recording,recovered,scene=source,shader=shader,filter_setting='gaussian-one')
    need(recovered.read_bytes()==output.read_bytes(),'configured recovery changed output')
    # Maximum reset/context count with a real override and sqrt packing.
    maximum=folder/'maximum-cuts.rrcapture'; maximum_output=folder/'maximum-cuts.rrrecordout'
    p=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--light-intensity','0','--ambient','.25',
                      '--samples','8','--seed','1','--rr-step','1.1','0','0','--rr-record',str(maximum),'--debug'],capture_output=True,text=True,timeout=45)
    need(p.returncode==0,(p.stdout,p.stderr))
    maximum_worker=run_recording(args.probe,args.sdk_bin,maximum,maximum_output,scene=source,shader=shader,albedo_encoding='sqrt',filter_setting='gaussian-one')
    (folder/'maximum-cuts-execution.json').write_text(json.dumps(maximum_worker),encoding='utf-8')
    need(maximum_worker['decision']['rr_rendering'] and maximum_worker['decision']['default_inspection']['contexts']==8,'maximum setting/reset admission')
    maximum_stdout=len(maximum_worker['worker']['stdout'].encode('utf-8')); need(maximum_stdout<=65536,'configured report exceeded worker cap')
    summary=dict(result='pass',quality_acceptance='not-qualified',measurements=measurements,default_equivalence_controls=controls,
                 rejected_cases=rejected,historical_matches=historical,maximum_contexts=8,maximum_stdout_bytes=maximum_stdout,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in summary.items() if key!='measurements'}))


if __name__=='__main__': main()
