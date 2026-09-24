"""Supervise the isolated FidelityFX Radiance Cache context research worker."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

DLL_HASHES={
    'amd_fidelityfx_loader_dx12.dll':'e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa',
    'amd_fidelityfx_radiancecache_dx12.dll':'256db18d924c8cd38923d04e3ecd210695d3f0f796b240eab9663ad4d54e31a0',
}


def strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON constant: '+value)
    return json.loads(text,object_pairs_hook=pairs,parse_constant=invalid)


def verify_sdk(directory):
    directory=Path(directory); hashes={}
    for name,expected in DLL_HASHES.items():
        path=directory/name
        if not path.is_file() or not 0<path.stat().st_size<=32*1024*1024:
            raise ValueError('SDK DLL missing or oversized: '+name)
        state=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                state.update(chunk)
        digest=state.hexdigest()
        if digest!=expected:
            raise ValueError('SDK DLL does not match reviewed 2.3.0 build: '+name)
        hashes[name]=digest
    return hashes


def assess(envelope,*,cycles=1,budget_mib=32,adapter=0,allow_workaround=False):
    unavailable=dict(status='unavailable',reason='invalid-worker-report',rc_rendering=False,workarounds=[])
    def need(condition):
        if not condition:
            raise ValueError('worker contract mismatch')
    try:
        need(type(cycles) is int and 1<=cycles<=3 and type(budget_mib) is int and 1<=budget_mib<=256)
        need(type(adapter) is int and 0<=adapter<=31)
        need(envelope['protocol']=='rc-isolation-1' and envelope['job_assigned_before_resume'] is True and envelope['child_reaped'] is True)
        need(envelope['output_limit_bytes']==65536)
        for stream in ('stdout','stderr'):
            need(type(envelope[stream]) is str and len(envelope[stream].encode('utf-8'))<=65536)
        if envelope['timed_out'] is True:
            return dict(unavailable,reason='worker-timeout')
        if envelope['output_limit_exceeded'] is True:
            return dict(unavailable,reason='worker-output-limit')
        need(envelope['timed_out'] is False and envelope['output_limit_exceeded'] is False)
        code=envelope['exit_code']; need(type(code) is int and 0<=code<=0xffffffff)
        if code not in (0,1,77):
            return dict(unavailable,reason='worker-crash',worker_exit_code=code)
        if code==77:
            return dict(unavailable,reason='no-provider')
        data=strict_json(envelope['stdout'])
        need(data['adapter']==adapter and data['sdk_api']=='0.9.0' and data['shader_model_6_6'] is True)
        need(type(data['wave_lane_min']) is int and type(data['wave_lane_max']) is int and data['wave_lane_min']<=32<=data['wave_lane_max'])
        need(data['wave32_reference'] is True and data['dispatches']==0)
        providers=data['providers']; need(type(providers) is list and len(providers)==1)
        provider=providers[0]; need(type(provider['id']) is int and 0<provider['id']<=0xffffffffffffffff and provider['name']=='0.9.0')
        rows=data['context_tests']; need(type(rows) is list and rows)
        for row in rows:
            for key in ('max_inference_samples','max_training_samples','budget_bytes','wmma_create_code','fallback_create_code',
                        'requested_provider_id','provider_query_code','provider_id','destroy_code','callback_peak_bytes',
                        'callback_live_bytes_after_destroy','allocation_attempts','allocations','releases','allocation_denials','callback_errors'):
                need(type(row[key]) is int and 0<=row[key]<=0xffffffffffffffff)
            need(row['validation'] is True and row['hard_budget_enforced'] is True)
            need(row['max_inference_samples']==12288 and row['max_training_samples']==512 and row['budget_bytes']==budget_mib*1024*1024)
            need(row['requested_provider_id']==provider['id'])
        if code==1 and len(rows)==1 and rows[0]['result']=='allocation-rejected':
            row=rows[0]
            need(row['created'] is False and row['destroyed'] is False and row['allocation_denials']==1)
            need(row['allocations']==row['releases'] and row['callback_live_bytes_after_destroy']==row['callback_errors']==0)
            need(data['contexts_created']==data['contexts_destroyed']==0 and data['result']=='validation-failed')
            return dict(unavailable,reason='allocation-rejected')
        need(len(rows)==cycles and data['contexts_created']==data['contexts_destroyed']==cycles)
        peaks=[]; workarounds=set()
        for row in rows:
            need(row['result']=='context-validation-failed' and row['wmma_attempted'] is True and row['wmma_create_code']==0)
            need(row['fallback_attempted'] is False and row['fallback_create_code']==0xffffffff and row['selected_backend']=='wmma')
            need(row['created'] is True and row['destroyed'] is True and row['destroy_code']==0)
            peak=row['callback_peak_bytes']; need(0<peak<=row['budget_bytes'])
            need(row['allocation_attempts']==row['allocations']==row['releases'] and row['allocations']>0)
            need(row['callback_live_bytes_after_destroy']==row['allocation_denials']==row['callback_errors']==0)
            if row['provider_query_code']==0 and row['provider_id']==provider['id']:
                pass
            else:
                need(allow_workaround and row['provider_query_code']==4 and row['provider_id']==0)
                workarounds.add('pinned-sdk-provider-metadata')
            peaks.append(peak)
        need(code==1 and data['result']=='validation-failed' if workarounds else code==0 and data['result']=='context-tests-pass')
        return dict(status='context-ready-with-workarounds' if workarounds else 'context-ready',reason=None,rc_rendering=False,
                    workarounds=sorted(workarounds),raw_sdk_acceptance='failed' if workarounds else 'passed',
                    accounting='hard-callback-ceiling-no-preflight-query',peak_callback_bytes=max(peaks),contexts_verified=cycles,
                    requested_provider_id=provider['id'],provider_name=provider['name'],selected_backend=rows[0]['selected_backend'],
                    max_inference_samples=12288,max_training_samples=512)
    except (KeyError,IndexError,TypeError,ValueError,OverflowError,RecursionError):
        return unavailable


def run_context(probe,sdk_bin,*,cycles=1,budget_mib=32,adapter=0,fail_allocation=None,timeout_ms=60000):
    probe=Path(probe).resolve(strict=True); sdk_bin=Path(sdk_bin).resolve(strict=True)
    if not probe.is_file() or not sdk_bin.is_dir():
        raise ValueError('probe must be a file and SDK path a directory')
    if not 1<=cycles<=3 or not 1<=budget_mib<=256 or not 0<=adapter<=31 or not 1<=timeout_ms<=60000:
        raise ValueError('invalid worker limits')
    if fail_allocation is not None and not 1<=fail_allocation<=255:
        raise ValueError('invalid failure ordinal')
    hashes=verify_sdk(sdk_bin)
    command=[str(probe),'--isolated-context','--sdk-bin',str(sdk_bin),'--debug','--cycles',str(cycles),
             '--budget-mib',str(budget_mib),'--adapter',str(adapter),'--worker-timeout-ms',str(timeout_ms)]
    if fail_allocation is not None:
        command+=['--fail-allocation',str(fail_allocation)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=timeout_ms/1000+10,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1024*1024:
        raise RuntimeError('RC isolation host failed')
    envelope=strict_json(process.stdout); decision=assess(envelope,cycles=cycles,budget_mib=budget_mib,adapter=adapter,allow_workaround=True)
    if fail_allocation is not None and decision['status'].startswith('context-ready'):
        decision=dict(status='unavailable',reason='failure-injection-not-observed',rc_rendering=False,workarounds=[])
    return dict(decision=decision,sdk_sha256=hashes,worker=envelope)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',required=True,type=Path); parser.add_argument('--sdk-bin',required=True,type=Path)
    parser.add_argument('--cycles',type=int,default=1); parser.add_argument('--budget-mib',type=int,default=32)
    parser.add_argument('--fail-allocation',type=int); parser.add_argument('--timeout-ms',type=int,default=60000)
    args=parser.parse_args()
    try:
        report=run_context(args.probe,args.sdk_bin,cycles=args.cycles,budget_mib=args.budget_mib,
                           fail_allocation=args.fail_allocation,timeout_ms=args.timeout_ms)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(decision=dict(status='unavailable',reason=str(error),rc_rendering=False))))
        return 1
    print(json.dumps(report))
    return 0 if report['decision']['status'].startswith('context-ready') else 1


if __name__=='__main__':
    raise SystemExit(main())
