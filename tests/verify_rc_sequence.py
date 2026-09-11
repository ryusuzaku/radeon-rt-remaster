import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rc_sequence_worker import BASELINE_HASH,POST_TRAINING_HASH,assess,run_sequence


def need(condition,message):
    if not condition: raise RuntimeError(message)


def rejected(command):
    return subprocess.run(command,capture_output=True,text=True).returncode!=0


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',required=True); parser.add_argument('--sdk-bin',required=True); args=parser.parse_args()
    base=[args.probe,'--sdk-bin',args.sdk_bin]
    need(rejected(base+['--sequence-test','--dispatch-test']),'mixed sequence/dispatch modes accepted')
    need(rejected(base+['--sequence-test','--training-batches','0']),'zero batches accepted')
    need(rejected(base+['--sequence-test','--training-batches','9']),'excess batches accepted')
    need(rejected(base+['--training-batches','2']),'orphan batch option accepted')
    need(rejected(base+['--sequence-test','--dispatch-mode','combined']),'single-dispatch option accepted by sequence')
    need(rejected(base+['--dispatch-test','--training-batches','1']),'sequence option accepted by single dispatch')

    first=run_sequence(args.probe,args.sdk_bin); repeat=run_sequence(args.probe,args.sdk_bin)
    for name,report in (('first',first),('repeat',repeat)):
        decision=report['decision']; need(decision['status']=='training-observed-with-workarounds',name+' sequence unavailable')
        need(decision['rc_training_observed'] is True and decision['rc_rendering'] is False,name+' claims mismatch')
        need(decision['baseline_hash_fnv1a64']==BASELINE_HASH and decision['post_training_hash_fnv1a64']==POST_TRAINING_HASH,name+' hashes mismatch')
        need(decision['post_changed_values']==36864 and decision['target_mse_after']<decision['target_mse_before'] and decision['reset_exact'] is True,name+' learning/reset evidence mismatch')
    need(first['decision']==repeat['decision'],'fresh sequence decision is not exact')

    envelope=first['worker']; need(assess(envelope,allow_workaround=False)['status']=='unavailable','metadata workaround enabled implicitly')
    row_mutations={'training_batches':2,'post_changed_values':36863,'reset_changed_values':1,'retained_state_observed':False,
                   'target_mse_improved':False,'reset_exact':False,'mechanical_pass':False,'callback_live_bytes_after_destroy':1}
    for key,value in row_mutations.items():
        candidate=copy.deepcopy(envelope); data=json.loads(candidate['stdout']); data['sequence_tests'][0][key]=value; candidate['stdout']=json.dumps(data)
        need(assess(candidate,allow_workaround=True)['status']=='unavailable','accepted row mutation '+key)
    step_mutations=[(0,'output_hash_fnv1a64',1),(1,'changed_output_values',1),(2,'target_mse',1.0),(3,'output_hash_fnv1a64',1),
                    (2,'inputs_unchanged',False),(3,'counter_training_after',1)]
    for index,key,value in step_mutations:
        candidate=copy.deepcopy(envelope); data=json.loads(candidate['stdout']); data['sequence_tests'][0]['steps'][index][key]=value; candidate['stdout']=json.dumps(data)
        need(assess(candidate,allow_workaround=True)['status']=='unavailable',f'accepted step mutation {index}:{key}')
    candidate=copy.deepcopy(envelope); candidate['stdout']='{"x":1,"x":2}'
    need(assess(candidate,allow_workaround=True)['status']=='unavailable','duplicate JSON accepted')
    candidate=copy.deepcopy(envelope); candidate['stdout']='{"x":Infinity}'
    need(assess(candidate,allow_workaround=True)['status']=='unavailable','nonfinite JSON accepted')

    low=run_sequence(args.probe,args.sdk_bin,budget_mib=1)
    need(low['decision']['reason']=='worker-crash' and low['worker']['child_reaped'] is True,'low-budget sequence crash not contained')
    recovered=run_sequence(args.probe,args.sdk_bin)
    need(recovered['decision']['status']=='training-observed-with-workarounds','sequence did not recover after provider crash')
    Path('rc-sequence-test-report.json').write_text(json.dumps(dict(first=first,repeat=repeat,low_budget=low,recovered=recovered),indent=2),encoding='utf-8')
    print('Radiance Cache persistent training/reset sequence contract passed'); return 0


if __name__=='__main__': raise SystemExit(main())
