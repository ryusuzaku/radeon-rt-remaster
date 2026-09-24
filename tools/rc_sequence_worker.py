"""Supervise one persistent FidelityFX Radiance Cache training sequence."""
import argparse
import math
from pathlib import Path
import subprocess

from rc_worker import strict_json,verify_sdk

BASELINE_HASH=8439070038676242095
TRAIN_SENTINEL_HASH=3911126094895948581
POST_TRAINING_HASH=11036946020368386469
PATH_BASELINE_HASH=4380958906282038366
PATH_POST_TRAINING_HASH=17423046786485749504
PATH_POST_TWO_BATCH_HASH=13270289865275143940


def assess(envelope,*,budget_mib=32,adapter=0,allow_workaround=False,artifact_sha256=None,training_batches=1,populated_counts=None,dynamic_fixture=False):
    unavailable=dict(status='unavailable',reason='invalid-worker-report',rc_rendering=False,rc_training_observed=False,workarounds=[])
    def need(condition):
        if not condition:
            raise ValueError('sequence worker contract mismatch')
    try:
        need(type(budget_mib) is int and 1<=budget_mib<=256 and type(adapter) is int and 0<=adapter<=31)
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
        need(data['wave_lane_min']<=32<=data['wave_lane_max'] and data['wave32_reference'] is True)
        need(data['context_tests']==[] and data['dispatch_tests']==[] and data['dispatches']==training_batches+3)
        providers=data['providers']; need(type(providers) is list and len(providers)==1)
        provider=providers[0]; need(type(provider['id']) is int and 0<provider['id']<=0xffffffffffffffff and provider['name']=='0.9.0')
        rows=data['sequence_tests']; need(type(rows) is list and len(rows)==1); row=rows[0]
        integer_fields=('training_batches','max_inference_samples','max_training_samples','populated_inference_samples','populated_training_samples','external_buffer_bytes','staging_buffer_bytes','budget_bytes',
                        'wmma_create_code','fallback_create_code','post_changed_values','reset_changed_values','requested_provider_id',
                        'provider_query_code','provider_id','destroy_code','callback_peak_bytes','callback_live_bytes_after_destroy',
                        'allocation_attempts','allocations','releases','allocation_denials','callback_errors')
        for key in integer_fields: need(type(row[key]) is int and 0<=row[key]<=0xffffffffffffffff)
        need(type(training_batches) is int and 1<=training_batches<=2)
        need(row['validation'] is True and row['hard_budget_enforced'] is True and row['mode']=='sequence' and row['training_batches']==training_batches)
        need(row['max_inference_samples']==12288 and row['max_training_samples']==512 and row['external_buffer_bytes']==716808)
        renderer_fixture=artifact_sha256 is not None
        need(row['renderer_fixture'] is renderer_fixture and row['artifact_sha256']==('' if artifact_sha256 is None else artifact_sha256))
        expected_counts=populated_counts if populated_counts is not None else ((172,172) if renderer_fixture else (12288,512))
        need(type(expected_counts) is tuple and len(expected_counts)==2 and (row['populated_inference_samples'],row['populated_training_samples'])==expected_counts)
        need(row['staging_buffer_bytes']==1433616 and row['budget_bytes']==budget_mib*1024*1024)
        need(row['wmma_attempted'] is True and row['wmma_create_code']==0 and row['fallback_attempted'] is False)
        need(row['fallback_create_code']==0xffffffff and row['selected_backend']=='wmma' and row['created'] is True)
        steps=row['steps']; need(type(steps) is list and len(steps)==training_batches+3)
        names=['baseline-reset-inference',*(['training']*training_batches),'post-training-inference','reset-inference']
        baseline_hash=PATH_BASELINE_HASH if renderer_fixture else BASELINE_HASH
        need(renderer_fixture or training_batches==1); need(not dynamic_fixture or renderer_fixture)
        post_hash=(PATH_POST_TWO_BATCH_HASH if training_batches==2 else PATH_POST_TRAINING_HASH) if renderer_fixture else POST_TRAINING_HASH
        hashes=[baseline_hash,*([TRAIN_SENTINEL_HASH]*training_batches),post_hash,baseline_hash]
        for index,step in enumerate(steps):
            need(step['name']==names[index] and step['dispatch_code']==0 and step['submitted'] is True and step['fence_completed'] is True)
            need(step['counter_inference_after']==step['counter_training_after']==0 and step['inputs_unchanged'] is True and step['targets_unchanged'] is True)
            need(step['device_healthy'] is True and step['pass'] is True)
            if not dynamic_fixture or step['name']=='training': need(step['output_hash_fnv1a64']==hashes[index])
            numeric=[step['output_minimum'],step['output_mean'],step['output_maximum'],step['target_mse']]
            need(all(type(value) in (int,float) and math.isfinite(value) for value in numeric))
            if step['name']=='training':
                need(step['finite_output_values']==step['nonnegative_output_values']==step['changed_output_values']==0)
                need(numeric==[0,0,0,0])
            else:
                need(step['finite_output_values']==step['nonnegative_output_values']==step['changed_output_values']==36864)
                need(0<=step['output_minimum']<=step['output_mean']<=step['output_maximum']<=65504 and step['target_mse']>0)
        floats=['post_vs_baseline_mse','post_vs_baseline_max_abs','reset_vs_baseline_mse','reset_vs_baseline_max_abs']
        need(all(type(row[key]) in (int,float) and math.isfinite(row[key]) and row[key]>=0 for key in floats))
        need(row['post_changed_values']==expected_counts[0]*3 and row['post_vs_baseline_mse']>0 and row['post_vs_baseline_max_abs']>0)
        need(row['reset_changed_values']==0 and row['reset_vs_baseline_mse']==row['reset_vs_baseline_max_abs']==0)
        need(row['retained_state_observed'] is True and row['target_mse_improved'] is True and row['reset_exact'] is True and row['mechanical_pass'] is True)
        post_step=steps[-2]; need(post_step['target_mse']<steps[0]['target_mse'])
        if dynamic_fixture:
            need(steps[0]['output_hash_fnv1a64']>0 and post_step['output_hash_fnv1a64']!=steps[0]['output_hash_fnv1a64'])
            need(steps[-1]['output_hash_fnv1a64']==steps[0]['output_hash_fnv1a64'])
        composite=[row['baseline_composite_mse'],row['post_composite_mse']]
        need(all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in composite))
        if renderer_fixture: need(row['composite_mse_improved'] is True and 0<row['post_composite_mse']<row['baseline_composite_mse'])
        else: need(row['composite_mse_improved'] is False and composite==[0,0])
        need(row['requested_provider_id']==provider['id'] and row['destroyed'] is True and row['destroy_code']==0)
        need(0<row['callback_peak_bytes']<=row['budget_bytes'])
        need(row['allocation_attempts']==row['allocations']==row['releases'] and row['allocations']>0)
        need(row['callback_live_bytes_after_destroy']==row['allocation_denials']==row['callback_errors']==0)
        workarounds=[]
        if row['provider_query_code']==0 and row['provider_id']==provider['id']:
            need(code==0 and row['result']=='sequence-pass' and data['result']=='sequence-tests-pass')
        else:
            need(allow_workaround and code==1 and row['provider_query_code']==4 and row['provider_id']==0)
            need(row['result']=='sequence-pass-provider-metadata-failed' and data['result']=='validation-failed')
            workarounds=['pinned-sdk-provider-metadata']
        need(data['contexts_created']==data['contexts_destroyed']==1)
        return dict(status='training-observed-with-workarounds' if workarounds else 'training-observed',reason=None,
                    rc_rendering=False,rc_training_observed=True,workarounds=workarounds,
                    raw_sdk_acceptance='failed' if workarounds else 'passed',training_batches=training_batches,
                    renderer_fixture=renderer_fixture,artifact_sha256=artifact_sha256,offline_composite_validated=renderer_fixture,
                    baseline_hash_fnv1a64=steps[0]['output_hash_fnv1a64'],post_training_hash_fnv1a64=post_step['output_hash_fnv1a64'],
                    post_changed_values=row['post_changed_values'],post_vs_baseline_mse=row['post_vs_baseline_mse'],
                    target_mse_before=steps[0]['target_mse'],target_mse_after=post_step['target_mse'],
                    composite_mse_before=row['baseline_composite_mse'],composite_mse_after=row['post_composite_mse'],reset_exact=True,
                    peak_callback_bytes=row['callback_peak_bytes'],requested_provider_id=provider['id'],provider_name=provider['name'])
    except (KeyError,IndexError,TypeError,ValueError,OverflowError,RecursionError):
        return unavailable


def run_sequence(probe,sdk_bin,*,budget_mib=32,adapter=0,timeout_ms=60000,path_sequence=None):
    probe=Path(probe).resolve(strict=True); sdk_bin=Path(sdk_bin).resolve(strict=True)
    if not probe.is_file() or not sdk_bin.is_dir(): raise ValueError('probe must be a file and SDK path a directory')
    if not 1<=budget_mib<=256 or not 0<=adapter<=31 or not 1<=timeout_ms<=60000: raise ValueError('invalid sequence worker limits')
    hashes=verify_sdk(sdk_bin)
    artifact_sha256=None
    if path_sequence is not None:
        from inspect_rc_paths import load_paths
        path_sequence=Path(path_sequence).resolve(strict=True); artifact_sha256=load_paths(path_sequence)['artifact_sha256']
    command=[str(probe),'--isolated-sequence','--training-batches','1','--sdk-bin',str(sdk_bin),'--debug',
             '--budget-mib',str(budget_mib),'--adapter',str(adapter),'--worker-timeout-ms',str(timeout_ms)]
    if path_sequence is not None: command += ['--path-sequence',str(path_sequence)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=timeout_ms/1000+10,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1024*1024: raise RuntimeError('RC sequence isolation host failed')
    envelope=strict_json(process.stdout)
    return dict(decision=assess(envelope,budget_mib=budget_mib,adapter=adapter,allow_workaround=True,artifact_sha256=artifact_sha256),sdk_sha256=hashes,worker=envelope)


def main():
    import json
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--probe',required=True,type=Path); parser.add_argument('--sdk-bin',required=True,type=Path)
    parser.add_argument('--path-sequence',type=Path)
    parser.add_argument('--budget-mib',type=int,default=32); parser.add_argument('--timeout-ms',type=int,default=60000); args=parser.parse_args()
    try: report=run_sequence(args.probe,args.sdk_bin,budget_mib=args.budget_mib,timeout_ms=args.timeout_ms,path_sequence=args.path_sequence)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(decision=dict(status='unavailable',reason=str(error),rc_rendering=False,rc_training_observed=False)))); return 1
    print(json.dumps(report)); return 0 if report['decision']['status'].startswith('training-observed') else 1


if __name__=='__main__': raise SystemExit(main())
