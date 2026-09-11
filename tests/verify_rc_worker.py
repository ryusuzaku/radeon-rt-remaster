"""Containment and exact managed admission for Radiance Cache context research."""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rc_worker import assess,run_context,strict_json,verify_sdk


def need(ok,reason):
    if not ok:
        raise AssertionError(reason)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',type=Path,required=True); parser.add_argument('--sdk-bin',type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rc-worker-',dir=args.probe.parent)); results={}
    for scenario in ('success','failure','malformed','nul','crash','timeout','overflow'):
        process=subprocess.run([str(args.probe),'--isolation-test',scenario],capture_output=True,text=True,timeout=40)
        need(process.returncode==0,process.stderr); data=strict_json(process.stdout); results[scenario]=data
        need(data['job_assigned_before_resume'] and data['child_reaped'],scenario+' not contained')
        need(len(data['stdout'].encode())<=65536 and len(data['stderr'].encode())<=65536,'output unbounded')
        if scenario=='success': need(data['exit_code']==0 and strict_json(data['stdout'])=={'fixture':True},'success transport failed')
        elif scenario=='timeout': need(data['timed_out'],'deadline not enforced')
        elif scenario=='overflow': need(data['output_limit_exceeded'],'output limit not enforced')
        elif scenario=='crash': need(data['exit_code']==0xe0005243,'crash code lost')
        elif scenario=='nul': need(data['stdout']=='{}\0extra','embedded NUL truncated')
        need(assess(data)['status']=='unavailable','fixture accepted as context')
    exited=subprocess.run([str(args.probe),'--isolation-test','parent-exit'],capture_output=True,text=True,timeout=10)
    for scenario in ('success','crash','timeout','overflow'):
        process=subprocess.run([str(args.probe),'--live-isolation-test',scenario],capture_output=True,text=True,timeout=15)
        need(process.returncode==0,process.stderr)
        live=strict_json(process.stdout); data=live['worker']; results['live_'+scenario]=live
        need(data['child_reaped'] and data['job_assigned_before_resume'],'live child not contained')
        expected={'success':'exited before fence','crash':'exited before fence','timeout':'fence timeout','overflow':'output limit exceeded'}[scenario]
        need(expected in live['wait_error'],'live fence failure misclassified: '+str(live))
        need(data['timed_out']==(scenario=='timeout'),'live timeout classification wrong')
        need(data['output_limit_exceeded']==(scenario=='overflow'),'live output classification wrong')
        need(len(data['stdout'])<=65536 and len(data['stderr'])<=65536,'live output unbounded')
        if scenario=='crash': need(data['exit_code']==0xe0005243,'live crash code lost')
    need(exited.returncode==55,'parent exit fixture failed'); pid=strict_json(exited.stdout)['child_pid']
    kernel=ctypes.WinDLL('kernel32',use_last_error=True); kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]; kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]; kernel.WaitForSingleObject.restype=ctypes.c_uint32; kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x100000,False,pid)
    if handle:
        try: need(kernel.WaitForSingleObject(handle,2000)==0,'worker survived parent exit')
        finally: kernel.CloseHandle(handle)
    else: need(ctypes.get_last_error()==87,'child termination unknown')
    results['parent_exit']=dict(parent_exit_code=55,child_pid=pid,child_terminated=True)
    try: verify_sdk(folder)
    except ValueError: pass
    else: raise AssertionError('missing SDK accepted')
    for name in ('amd_fidelityfx_loader_dx12.dll','amd_fidelityfx_radiancecache_dx12.dll'):
        (folder/name).write_bytes(b'untrusted-test-fixture-not-a-DLL')
    try: verify_sdk(folder)
    except ValueError: pass
    else: raise AssertionError('unreviewed SDK hash accepted')
    healthy=run_context(args.probe,args.sdk_bin,budget_mib=32); results['healthy']=healthy
    need(healthy['decision']['status']=='context-ready-with-workarounds','managed context unavailable')
    need(healthy['decision']['raw_sdk_acceptance']=='failed' and not healthy['decision']['rc_rendering'],'raw failure hidden')
    need(healthy['decision']['selected_backend']=='wmma' and healthy['decision']['peak_callback_bytes']==20643840,'measured contract changed')
    need(assess(healthy['worker'],budget_mib=32)['status']=='unavailable','workaround enabled implicitly')
    envelope=healthy['worker']; root=strict_json(envelope['stdout']); mutations={
        'hard_budget_enforced':False,'max_inference_samples':1,'max_training_samples':1,'budget_bytes':1,
        'wmma_create_code':6,'fallback_attempted':True,'selected_backend':'reference','created':False,'destroyed':False,
        'requested_provider_id':0,'provider_query_code':5,'provider_id':1,'destroy_code':1,'callback_peak_bytes':2**30,
        'callback_live_bytes_after_destroy':1,'allocation_attempts':12,'allocations':10,'releases':10,
        'allocation_denials':1,'callback_errors':1,'validation':False}
    for key,value in mutations.items():
        changed=copy.deepcopy(root); changed['context_tests'][0][key]=value; candidate=dict(envelope,stdout=json.dumps(changed))
        need(assess(candidate,budget_mib=32,allow_workaround=True)['status']=='unavailable','accepted mutation '+key)
    for text in ('{"adapter":0,"adapter":0}','{"x":NaN}','{}\0extra','['*2000+']'*2000):
        need(assess(dict(envelope,stdout=text),budget_mib=32,allow_workaround=True)['status']=='unavailable','malformed JSON accepted')
    low=run_context(args.probe,args.sdk_bin,budget_mib=1); results['low_budget']=low
    need(low['decision']['reason']=='worker-crash' and low['worker']['child_reaped'],'low-budget crash not contained')
    failed=run_context(args.probe,args.sdk_bin,budget_mib=32,fail_allocation=2); results['injected_failure']=failed
    need(failed['decision']['reason']=='worker-crash' and failed['worker']['child_reaped'],'injected crash not contained')
    recovered=run_context(args.probe,args.sdk_bin,budget_mib=32); results['recovered']=recovered
    need(recovered['decision']['status']=='context-ready-with-workarounds','fresh recovery failed')
    report=dict(result='pass',scope='radiance-cache-context-containment',raw_sdk_acceptance='failed',rc_rendering=False,
                rejected_mutations=len(mutations)+4,cases=results,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('result','scope','raw_sdk_acceptance','rc_rendering','artifacts')}))


if __name__=='__main__':
    main()
