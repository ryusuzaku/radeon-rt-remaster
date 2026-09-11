"""Supervise one isolated FidelityFX Radiance Cache synthetic dispatch."""
import argparse
import math
from pathlib import Path
import subprocess

from rc_worker import strict_json,verify_sdk

EXPECTED_OUTPUT_HASH=8439070038676242095


def assess(envelope,*,mode='combined',budget_mib=32,adapter=0,allow_workaround=False):
    unavailable=dict(status='unavailable',reason='invalid-worker-report',rc_rendering=False,rc_dispatch_executed=False,workarounds=[])
    def need(condition):
        if not condition:
            raise ValueError('dispatch worker contract mismatch')
    try:
        need(mode in ('inference','combined') and type(budget_mib) is int and 1<=budget_mib<=256)
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
        need(data['wave32_reference'] is True and data['context_tests']==[] and data['dispatches']==1)
        providers=data['providers']; need(type(providers) is list and len(providers)==1)
        provider=providers[0]; need(type(provider['id']) is int and 0<provider['id']<=0xffffffffffffffff and provider['name']=='0.9.0')
        rows=data['dispatch_tests']; need(type(rows) is list and len(rows)==1)
        row=rows[0]
        integer_fields=('max_inference_samples','max_training_samples','populated_inference_samples','populated_training_samples',
                        'external_buffer_bytes','staging_buffer_bytes','budget_bytes','wmma_create_code','fallback_create_code',
                        'dispatch_code','counter_inference_after','counter_training_after','finite_output_values','nonnegative_output_values',
                        'changed_output_values','output_hash_fnv1a64','device_removed_reason','requested_provider_id','provider_query_code',
                        'provider_id','destroy_code','callback_peak_bytes','callback_live_bytes_after_destroy','allocation_attempts',
                        'allocations','releases','allocation_denials','callback_errors')
        for key in integer_fields:
            need(type(row[key]) is int and 0<=row[key]<=0xffffffffffffffff)
        need(row['validation'] is True and row['hard_budget_enforced'] is True and row['mode']==mode)
        need(row['max_inference_samples']==row['populated_inference_samples']==12288 and row['max_training_samples']==512)
        need(row['populated_training_samples']==(512 if mode=='combined' else 0))
        need(row['external_buffer_bytes']==716808 and row['staging_buffer_bytes']==1433616 and row['budget_bytes']==budget_mib*1024*1024)
        need(row['wmma_attempted'] is True and row['wmma_create_code']==0 and row['fallback_attempted'] is False)
        need(row['fallback_create_code']==0xffffffff and row['selected_backend']=='wmma' and row['created'] is True)
        need(row['dispatch_code']==0 and row['submitted'] is True and row['fence_completed'] is True)
        need(row['counter_inference_after']==row['counter_training_after']==0)
        need(row['finite_output_values']==row['nonnegative_output_values']==row['changed_output_values']==36864)
        need(row['output_hash_fnv1a64']==EXPECTED_OUTPUT_HASH)
        values=[row['output_minimum'],row['output_mean'],row['output_maximum']]
        need(all(type(value) in (int,float) and math.isfinite(value) for value in values))
        need(0<=values[0]<=values[1]<=values[2]<=65504 and row['inputs_unchanged'] is True and row['targets_unchanged'] is True)
        need(row['device_removed_reason']==0 and row['mechanical_pass'] is True and row['destroyed'] is True and row['destroy_code']==0)
        need(row['requested_provider_id']==provider['id'])
        need(0<row['callback_peak_bytes']<=row['budget_bytes'])
        need(row['allocation_attempts']==row['allocations']==row['releases'] and row['allocations']>0)
        need(row['callback_live_bytes_after_destroy']==row['allocation_denials']==row['callback_errors']==0)
        workarounds=[]
        if row['provider_query_code']==0 and row['provider_id']==provider['id']:
            need(code==0 and row['result']=='dispatch-pass' and data['result']=='dispatch-tests-pass')
        else:
            need(allow_workaround and code==1 and row['provider_query_code']==4 and row['provider_id']==0)
            need(row['result']=='dispatch-pass-provider-metadata-failed' and data['result']=='validation-failed')
            workarounds=['pinned-sdk-provider-metadata']
        need(data['contexts_created']==data['contexts_destroyed']==1)
        return dict(status='dispatch-ready-with-workarounds' if workarounds else 'dispatch-ready',reason=None,
                    rc_rendering=False,rc_dispatch_executed=True,workarounds=workarounds,
                    raw_sdk_acceptance='failed' if workarounds else 'passed',mode=mode,output_hash_fnv1a64=row['output_hash_fnv1a64'],
                    output_minimum=row['output_minimum'],output_mean=row['output_mean'],output_maximum=row['output_maximum'],
                    peak_callback_bytes=row['callback_peak_bytes'],external_buffer_bytes=row['external_buffer_bytes'],
                    requested_provider_id=provider['id'],provider_name=provider['name'],selected_backend=row['selected_backend'])
    except (KeyError,IndexError,TypeError,ValueError,OverflowError,RecursionError):
        return unavailable


def run_dispatch(probe,sdk_bin,*,mode='combined',budget_mib=32,adapter=0,timeout_ms=60000):
    probe=Path(probe).resolve(strict=True); sdk_bin=Path(sdk_bin).resolve(strict=True)
    if not probe.is_file() or not sdk_bin.is_dir():
        raise ValueError('probe must be a file and SDK path a directory')
    if mode not in ('inference','combined') or not 1<=budget_mib<=256 or not 0<=adapter<=31 or not 1<=timeout_ms<=60000:
        raise ValueError('invalid dispatch worker limits')
    hashes=verify_sdk(sdk_bin)
    command=[str(probe),'--isolated-dispatch','--dispatch-mode',mode,'--sdk-bin',str(sdk_bin),'--debug',
             '--budget-mib',str(budget_mib),'--adapter',str(adapter),'--worker-timeout-ms',str(timeout_ms)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=timeout_ms/1000+10,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1024*1024:
        raise RuntimeError('RC dispatch isolation host failed')
    envelope=strict_json(process.stdout)
    return dict(decision=assess(envelope,mode=mode,budget_mib=budget_mib,adapter=adapter,allow_workaround=True),sdk_sha256=hashes,worker=envelope)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',required=True,type=Path); parser.add_argument('--sdk-bin',required=True,type=Path)
    parser.add_argument('--mode',choices=('inference','combined'),default='combined')
    parser.add_argument('--budget-mib',type=int,default=32); parser.add_argument('--timeout-ms',type=int,default=60000)
    args=parser.parse_args()
    try:
        report=run_dispatch(args.probe,args.sdk_bin,mode=args.mode,budget_mib=args.budget_mib,timeout_ms=args.timeout_ms)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        import json
        print(json.dumps(dict(decision=dict(status='unavailable',reason=str(error),rc_rendering=False,rc_dispatch_executed=False))))
        return 1
    import json
    print(json.dumps(report))
    return 0 if report['decision']['status'].startswith('dispatch-ready') else 1


if __name__=='__main__':
    raise SystemExit(main())
