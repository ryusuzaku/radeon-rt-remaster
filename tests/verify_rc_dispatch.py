import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rc_dispatch_worker import EXPECTED_OUTPUT_HASH,assess,run_dispatch


def need(condition,message):
    if not condition:
        raise RuntimeError(message)


def rejected(command):
    return subprocess.run(command,capture_output=True,text=True).returncode!=0


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',required=True); parser.add_argument('--sdk-bin',required=True)
    args=parser.parse_args(); base=[args.probe,'--sdk-bin',args.sdk_bin]
    need(rejected(base+['--dispatch-test','--context-test']),'mixed modes accepted')
    need(rejected(base+['--dispatch-test','--dispatch-mode','invalid']),'invalid dispatch mode accepted')
    need(rejected(base+['--dispatch-mode','combined']),'orphan dispatch option accepted')

    inference=run_dispatch(args.probe,args.sdk_bin,mode='inference')
    combined=run_dispatch(args.probe,args.sdk_bin,mode='combined')
    repeat=run_dispatch(args.probe,args.sdk_bin,mode='combined')
    for name,report in (('inference',inference),('combined',combined),('repeat',repeat)):
        decision=report['decision']
        need(decision['status']=='dispatch-ready-with-workarounds',name+' dispatch unavailable')
        need(decision['rc_dispatch_executed'] is True and decision['rc_rendering'] is False,name+' claim mismatch')
        need(decision['raw_sdk_acceptance']=='failed' and decision['workarounds']==['pinned-sdk-provider-metadata'],name+' raw policy mismatch')
        need(decision['output_hash_fnv1a64']==EXPECTED_OUTPUT_HASH,name+' output hash mismatch')
    need(inference['decision']['output_hash_fnv1a64']==combined['decision']['output_hash_fnv1a64']==repeat['decision']['output_hash_fnv1a64'],
         'inference/training-order/repeat output mismatch')

    envelope=combined['worker']
    need(assess(envelope,mode='combined',allow_workaround=False)['status']=='unavailable','metadata workaround enabled implicitly')
    mutations={
        'dispatch_code':1,'counter_inference_after':1,'finite_output_values':36863,'output_hash_fnv1a64':1,
        'inputs_unchanged':False,'targets_unchanged':False,'mechanical_pass':False,'external_buffer_bytes':716809,
        'staging_buffer_bytes':1433617,'callback_live_bytes_after_destroy':1,'device_removed_reason':1,
    }
    for key,value in mutations.items():
        candidate=copy.deepcopy(envelope); data=json.loads(candidate['stdout']); data['dispatch_tests'][0][key]=value; candidate['stdout']=json.dumps(data)
        need(assess(candidate,mode='combined',allow_workaround=True)['status']=='unavailable','accepted mutation '+key)
    candidate=copy.deepcopy(envelope); candidate['stdout']='{"duplicate":1,"duplicate":2}'
    need(assess(candidate,mode='combined',allow_workaround=True)['status']=='unavailable','duplicate JSON accepted')
    candidate=copy.deepcopy(envelope); candidate['stdout']='{"value":NaN}'
    need(assess(candidate,mode='combined',allow_workaround=True)['status']=='unavailable','nonfinite JSON accepted')

    low=run_dispatch(args.probe,args.sdk_bin,mode='inference',budget_mib=1)
    need(low['decision']['reason']=='worker-crash' and low['worker']['child_reaped'] is True,'low-budget dispatch crash not contained')
    recovered=run_dispatch(args.probe,args.sdk_bin,mode='combined')
    need(recovered['decision']['status']=='dispatch-ready-with-workarounds','dispatch did not recover after provider crash')
    Path('rc-dispatch-test-report.json').write_text(json.dumps(dict(inference=inference,combined=combined,repeat=repeat,low_budget=low,recovered=recovered),indent=2),encoding='utf-8')
    print('Radiance Cache synthetic inference/training dispatch contract passed')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
