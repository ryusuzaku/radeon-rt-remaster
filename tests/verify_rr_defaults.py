"""Bounded live default inspection, unchanged rendering and honest failed queries."""
import argparse
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from verify_rr_color_response import cases,need
from verify_dxr import encode_scene
from rr_recorded_dispatch import run_recording,admit_record,assess_recording
from rr_defaults import inspect_defaults,KEYS,GUARD,SENTINEL
from rr_quality import analyze


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args(); started=time.monotonic()
    folder=Path(tempfile.mkdtemp(prefix='rr-defaults-',dir=args.probe.parent)); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    results={}; saved={}; baseline_matches=0; expected=None
    for name,count,extra in [('linear',2,[]),('black',2,[]),('linear_history',8,[]),
                             ('linear_reset',4,['--rr-step','.03','0','0','--rr-reset-frame','2']),
                             ('maximum_cuts',8,['--rr-step','1.1','0','0'])]:
        print(name+': query-off/on in both encodings',flush=True)
        source=folder/(name+'.rrscene'); source.write_bytes(encode_scene(cases()['black' if name=='black' else 'linear']))
        recording=folder/(name+'.rrcapture')
        p=subprocess.run([str(args.dxr),str(source),'--mode','gi','--sun-radius','0','--light-intensity','0',
                          '--ambient','0' if name=='black' else '.25','--samples',str(count),'--seed','1','--rr-record',str(recording),'--debug',*extra],
                         capture_output=True,text=True,timeout=45)
        need(p.returncode==0,(p.stdout,p.stderr)); raw=recording.read_bytes(); data=admit_record(raw)
        for encoding in ('linear','sqrt'):
            pair={}
            for enabled in (False,True):
                tag=name+'-'+encoding+('-on' if enabled else '-off'); output=folder/(tag+'.rrrecordout')
                worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=source,shader=shader,
                                     albedo_encoding=encoding,query_defaults=enabled)
                (folder/(tag+'-execution.json')).write_text(json.dumps(worker),encoding='utf-8')
                need(worker['decision']['rr_rendering'] and worker['decision']['raw_sdk_acceptance']=='failed',worker)
                inspection=worker['decision']['default_inspection']; root=json.loads(worker['worker']['stdout'])
                if enabled:
                    need(inspection['status']=='defaults-ready' and inspection['stable'],inspection)
                    need(inspection['query_count']==24*sum(f['reset'] for f in data['frames']),'query count')
                    if expected is None: expected=inspection['values']
                    need(inspection['values']==expected,'defaults changed across recordings/encodings/contexts')
                    need(len(worker['worker']['stdout'].encode('utf-8'))<=65536,'query report exceeds isolation cap')
                    for context in root['context_tests']: del context['default_queries']
                else:
                    need(inspection['status']=='not-requested' and all('default_queries' not in c for c in root['context_tests']),'implicit default queries')
                pair[enabled]=(output.read_bytes(),root,worker)
            need(pair[False][:2]==pair[True][:2],'queries changed output, dispatch, SDK accounting or raw validation evidence')
            need(recording.read_bytes()==raw,'query modified recording')
            results[name+'-'+encoding]=dict(inspection=pair[True][2]['decision']['default_inspection'],
                                           stdout_bytes=len(pair[True][2]['worker']['stdout'].encode('utf-8')),
                                           unchanged_output=True,unchanged_nonquery_report=True)
            saved[name,encoding]=(recording,source,raw,pair)
            if args.baseline and name!='maximum_cuts':
                need((args.baseline/(name+'.rrcapture')).read_bytes()==raw,'historical recording mismatch')
                need((args.baseline/(name+'-'+encoding+'.rrrecordout')).read_bytes()==pair[False][0],'historical output changed')
                baseline_matches+=1
    recording,source,raw,pair=saved['linear','linear']; worker=pair[True][2]; root=json.loads(worker['worker']['stdout'])
    rejected=0
    def rejects(fn):
        nonlocal rejected
        try: fn()
        except (ValueError,KeyError): rejected+=1
        else: raise AssertionError('invalid default-query evidence accepted')
    # Native query evidence must fail closed even when the caller did not
    # explicitly require inspection (e.g. historical quality readers).
    for mutation in ('missing_all','missing_snapshot','phase','format','count','bool_count','short_keys','key','bool_key',
                     'bool_code','negative_code','large_bits','bool_bits','guard_before','guard_after','value','bool_value','null_value','extra'):
        changed=copy.deepcopy(root); c=changed['context_tests'][0]; s=c['default_queries'][0]; r=s['queries'][0]
        if mutation=='missing_all': del c['default_queries']
        elif mutation=='missing_snapshot': c['default_queries'].pop()
        elif mutation=='phase': s['phase']='after-1'
        elif mutation=='format': s['format']='float64'
        elif mutation=='count': s['count']=2
        elif mutation=='bool_count': s['count']=True
        elif mutation=='short_keys': s['queries'].pop()
        elif mutation=='key': r['key']=2
        elif mutation=='bool_key': r['key']=True
        elif mutation=='bool_code': r['code']=False
        elif mutation=='negative_code': r['code']=-1
        elif mutation=='large_bits': r['bits']=2**32
        elif mutation=='bool_bits': r['bits']=False
        elif mutation in ('guard_before','guard_after'): r[mutation]=0
        elif mutation=='value': r['value']=3
        elif mutation=='bool_value': r['value']=True
        elif mutation=='null_value': r['value']=None
        else: r['invented_default']=0
        envelope=copy.deepcopy(worker['worker']); envelope['stdout']=json.dumps(changed)
        need(assess_recording(envelope,raw,query_defaults=True)['status']=='unavailable',mutation); rejected+=1
        if mutation!='missing_all': need(assess_recording(envelope,raw)['status']=='unavailable','optional inspection ignored '+mutation)
    # Honest nonzero codes, untouched sentinels and nonfinite successful writes
    # are retained as failed inspection, never filled with made-up zero values.
    failure_cases=0
    for code,bits in [(6,SENTINEL),(0,SENTINEL),(0,0x7f800000),(0,0x7fc00000),(6,0)]:
        contexts=copy.deepcopy(root['context_tests'])
        for snapshot in contexts[0]['default_queries']:
            snapshot['queries'][0].update(code=code,bits=bits,value=None)
        verdict=inspect_defaults(contexts,required=True)
        need(verdict['status']=='default-query-failed' and verdict['values'] is None and verdict['failed_queries']==4,verdict)
        altered=copy.deepcopy(root); altered['context_tests']=contexts
        envelope=copy.deepcopy(worker['worker']); envelope['stdout']=json.dumps(altered)
        decision=assess_recording(envelope,raw,query_defaults=True)
        need(decision['status']=='recording-report-ready' and decision['default_inspection']==verdict,'honest query failure was hidden or promoted')
        contexts[0]['default_queries'][0]['queries'][0]['value']=0
        rejects(lambda:inspect_defaults(contexts,required=True)); failure_cases+=1
    for slot in ('same-context','different-context'):
        contexts=copy.deepcopy(root['context_tests'])
        if slot=='different-context': contexts.append(copy.deepcopy(contexts[0]))
        contexts[-1]['default_queries'][-1]['queries'][0].update(bits=0x40000000,value=2)
        verdict=inspect_defaults(contexts,required=True)
        need(verdict['status']=='default-query-unstable' and not verdict['stable'] and verdict['values'] is None,verdict)
    contexts=copy.deepcopy(root['context_tests'])
    for snapshot in contexts[0]['default_queries']:
        snapshot['queries'][0].update(bits=0x80000000,value=-0.0)
    need(inspect_defaults(contexts,required=True)['status']=='defaults-ready','finite negative-zero default rejected')
    contexts[0]['default_queries'][0]['queries'][0]['value']=0
    rejects(lambda:inspect_defaults(contexts,required=True))
    contexts=copy.deepcopy(root['context_tests']); contexts.append({})
    rejects(lambda:inspect_defaults(contexts))
    need(assess_recording(pair[False][2]['worker'],raw)['status']=='recording-report-ready','query-off historical compatibility')
    need(assess_recording(pair[False][2]['worker'],raw,query_defaults=True)['status']=='unavailable','required queries absent'); rejected+=1
    with patch('rr_recorded_dispatch.subprocess.run',side_effect=AssertionError('invalid option launched process')):
        for value in (1,'true',None,[]):
            rejects(lambda:run_recording(args.probe,args.sdk_bin,recording,folder/'invalid.rrrecordout',scene=source,shader=shader,query_defaults=value))
    for options in (['--query-defaults'],['--isolated-context','--query-defaults'],['--isolated-recording','--query-defaults','--query-defaults']):
        p=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),*options],capture_output=True,text=True,timeout=10)
        need(p.returncode!=0,'native invalid query option accepted'); rejected+=1
    # Quality analysis revalidates queries instead of trusting saved decisions.
    execution=folder/'linear-linear-on-execution.json'; output=folder/'linear-linear-on.rrrecordout'
    report,_=analyze(recording,output,source,shader,execution,samples=64,surface_reference=True,fallback=True)
    need(report['default_inspection']['status']=='defaults-ready','quality lost default inspection')
    (folder/'linear-query-quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    changed=copy.deepcopy(worker); changed['worker']=pair[False][2]['worker']
    missing=folder/'missing-query-execution.json'; missing.write_text(json.dumps(changed),encoding='utf-8')
    rejects(lambda:analyze(recording,output,source,shader,missing,samples=64,surface_reference=True))
    cli_output=folder/'cli.rrrecordout'
    p=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/rr_recorded_dispatch.py'),
                      '--probe',str(args.probe),'--sdk-bin',str(args.sdk_bin),'--input',str(recording),'--output',str(cli_output),
                      '--scene',str(source),'--shader',str(shader),'--query-defaults'],capture_output=True,text=True,timeout=45)
    need(p.returncode==0 and json.loads(p.stdout)['decision']['default_inspection']['status']=='defaults-ready',(p.stdout,p.stderr))
    need(cli_output.read_bytes()==pair[False][0],'CLI queries changed output')
    failed_output=folder/'injected.rrrecordout'
    failed=run_recording(args.probe,args.sdk_bin,recording,failed_output,scene=source,shader=shader,query_defaults=True,fail_allocation=2)
    (folder/'injected-execution.json').write_text(json.dumps(failed),encoding='utf-8')
    need(not failed['decision']['rr_rendering'] and failed['worker']['child_reaped'] and not failed_output.exists(),'query worker failure containment')
    recovered=folder/'recovered.rrrecordout'
    recovery=run_recording(args.probe,args.sdk_bin,recording,recovered,scene=source,shader=shader,query_defaults=True)
    need(recovered.read_bytes()==pair[True][0] and recovery['decision']['default_inspection']['values']==expected,'query recovery mismatch')
    summary=dict(result='pass',quality_acceptance='not-qualified',values=expected,cases=results,rejected_cases=rejected,
                 honest_failure_cases=failure_cases,unstable_cases=2,baseline_matches=baseline_matches,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__': main()
