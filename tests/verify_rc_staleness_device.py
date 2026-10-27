"""Device contract: Stage 2 staleness enforcement on the stale-lighting scenario.

Runs `rrt_dxr --rc-staleness-test` on the canonical scene in one provider
process and context: train at the default light (L0), change only the lighting
generation (L1), then repeat L1 under new camera revisions. The policy run must
reset at every identity change and match a fresh L1 session exactly. The
negative control (`--rc-staleness-force-continue`) forces a Continue across the
lighting change, which the gate would otherwise refuse, and proves the metric
and the forcing work.

The provider output on this fixture does not depend on the lighting change, so
the negative control cannot yet show lighting-specific stale values
(`stale_fraction` stays zero). The contract records that as a measured fact and
does not claim stale lighting is demonstrated; see docs/RC_STALENESS_POLICY.md.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT/'tests'))
from rc_staleness import decide,ACTION_RESET,ACTION_CONTINUE
from verify_dxr import fixture,encode_scene


def need(value,message):
    if not value: raise AssertionError(message)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',type=Path,required=True); parser.add_argument('--sdk-bin',type=Path,required=True); parser.add_argument('--dxr',type=Path,required=True)
    parser.add_argument('--out',type=Path,help='directory that receives staleness.json'); args=parser.parse_args()
    for path in (args.probe,args.dxr):
        if not path.is_file(): print('SKIP: missing',path); return 77
    folder=Path(tempfile.mkdtemp(prefix='rc-staleness-',dir=args.probe.parent)); env={k:v for k,v in os.environ.items() if not k.startswith('RRT_')}
    scene=folder/'fixture.rrscene'; scene.write_bytes(encode_scene(fixture()))
    def run(*extra):
        command=[str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-shared-probe',str(args.probe),'--rc-sdk-bin',str(args.sdk_bin),'--rc-staleness-test','--debug',*extra]
        process=subprocess.run(command,capture_output=True,text=True,env=env,timeout=70); need(process.returncode==0,(process.stdout,process.stderr)); return json.loads(process.stdout)
    policy=run(); policy_repeat=run(); control=run('--rc-staleness-force-continue'); control_repeat=run('--rc-staleness-force-continue')
    need(policy_repeat==policy and control_repeat==control,'staleness report is not repeat-exact')
    (folder/'staleness.json').write_text(json.dumps(dict(policy=policy,negative_control=control),indent=2)+'\n',encoding='utf-8')
    if args.out: args.out.mkdir(parents=True,exist_ok=True); (args.out/'staleness.json').write_text(json.dumps(dict(policy=policy,negative_control=control),indent=2)+'\n',encoding='utf-8')
    for row,mode in ((policy,'policy'),(control,'negative-control')):
        need(row['result']=='rc-staleness-session-pass' and row['mode']==mode,'staleness session did not pass')
        need(row['provider_processes']==row['provider_contexts']==1 and row['epochs']==4 and row['provider_dispatches']==12,'staleness session lifecycle mismatch')
        need(row['shared_resources']==5 and row['shared_fences']==1 and row['child_reaped'] is True and row['stop_acknowledged'] is True,'staleness containment mismatch')
        need(row['per_epoch_gpu_allocations']==0,'staleness session allocated per-epoch resources')
        need(row['candidate_applied'] is False and row['authoritative_output']=='no-cache','staleness session changed the claim boundary')
        need(row['reset_exact'] is True and row['compared_values']==516,'staleness reset or comparison mismatch')
        records=row['records']; need([r['query_count'] for r in records]==[172]*4,'staleness scenario changed the query count')
        need(all(r['admitted'] for r in records),'staleness epoch was not admitted')
        g=row['generations']; need(g['lighting_old']!=g['lighting_new'],'lighting generation did not change')
        for index in (0,2,3): need(records[index]['start_hash']==records[0]['start_hash'],'staleness reset baseline moved')
    # The decision table (Python reference model) agrees with the epochs the device chose.
    base=dict(scene=g['scene'],lighting=g['lighting_old'],material=g['material'],settings=g['settings'],camera=1)
    l1=dict(base,lighting=g['lighting_new']); camera2=dict(l1,camera=2); camera3=dict(l1,camera=3)
    expected=[decide(base,l1,[]).action,decide(l1,camera2,[]).action,decide(camera2,camera3,[]).action]
    need(expected==[ACTION_RESET]*3,'reference model no longer resets across the scenario')
    # Policy gate: reset at every identity change, exact match with the fresh session.
    need([r['reset'] for r in policy['records']]==[True]*4 and not any(r['forced_continue'] for r in policy['records']),'policy did not reset at every change')
    need(policy['records'][1]['changed_generations']==1 and policy['enforced_resets']==1 and policy['generation_violations']==0,'policy lighting enforcement mismatch')
    need(policy['stale_mse']==0 and policy['stale_max_abs']==0 and policy['stale_fraction']==0 and policy['stale_values']==0,'policy produced stale values')
    need(policy['records'][1]['post_hash']==policy['records'][2]['post_hash']==policy['records'][3]['post_hash'],'policy epoch differs from a fresh session')
    # Negative control: the forced continue is the only difference, and the metric sees it.
    need([r['reset'] for r in control['records']]==[True,False,True,True] and [r['forced_continue'] for r in control['records']]==[False,True,False,False],'negative control did not force continue exactly once')
    need(control['records'][1]['changed_generations']==1 and control['generation_violations']==1 and control['enforced_resets']==0,'negative control violation accounting mismatch')
    need(control['records'][1]['start_hash']==control['records'][0]['post_hash'],'negative control did not continue from the trained state')
    need(control['records'][1]['post_hash']!=policy['records'][1]['post_hash'] and control['stale_mse']>0 and control['stale_max_abs']>0,'negative control did not differ from the policy run')
    need(control['records'][2]['post_hash']==policy['records'][2]['post_hash'],'fresh session differs between modes')
    print(json.dumps(dict(result='pass',stale_fraction_policy=policy['stale_fraction'],stale_mse_control=control['stale_mse'],stale_max_abs_control=control['stale_max_abs'],
        stale_fraction_control=control['stale_fraction'],provider_output_lighting_independent=control['provider_output_lighting_independent'],
        fixture_discriminates_lighting=control['stale_fraction']>0,artifacts=str(folder))))
    return 0


if __name__=='__main__': sys.exit(main())
