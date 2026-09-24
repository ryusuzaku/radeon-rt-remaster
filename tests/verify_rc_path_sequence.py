"""End-to-end renderer RCRPATH1 to isolated FidelityFX cache sequence contract."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT/'tests'))
from inspect_rc_paths import load_paths
from rc_sequence_worker import PATH_BASELINE_HASH,PATH_POST_TRAINING_HASH,PATH_POST_TWO_BATCH_HASH,assess,run_sequence
from rc_live_worker import run_live
from verify_dxr import fixture,encode_scene


def need(value,message):
    if not value: raise AssertionError(message)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',type=Path,required=True); parser.add_argument('--sdk-bin',type=Path,required=True); parser.add_argument('--dxr',type=Path,required=True); args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='rc-path-sequence-',dir=args.probe.parent)); env={k:v for k,v in os.environ.items() if not k.startswith('RRT_')}
    scene=folder/'fixture.rrscene'; paths=folder/'fixture.rcpaths'; scene.write_bytes(encode_scene(fixture()))
    render=subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-paths',str(paths)],capture_output=True,text=True,env=env,timeout=60)
    need(render.returncode==0,(render.stdout,render.stderr)); source=load_paths(paths); need(len(source['queries'])==172,'unexpected source query count')
    def direct(*extra):
        command=[str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-shared-probe',str(args.probe),'--rc-sdk-bin',str(args.sdk_bin),*map(str,extra)]
        process=subprocess.run(command,capture_output=True,text=True,env=env,timeout=70); need(process.returncode==0,(process.stdout,process.stderr)); return json.loads(process.stdout)
    def deterministic(row): return {key:value for key,value in row.items() if key not in ('direct_wall_ms','provider_process_id')}
    direct_one=direct('--rc-training-batches',1); direct_repeat=direct('--rc-training-batches',1); direct_two=direct('--rc-training-batches',2)
    for row,batches,post_hash,candidate_hash in ((direct_one,1,6891511169378437159,'f46fd7afb78ece4edcfb6d70582073f6d545849a30bd8242eb7584462a81b3b8'),(direct_repeat,1,6891511169378437159,'f46fd7afb78ece4edcfb6d70582073f6d545849a30bd8242eb7584462a81b3b8'),(direct_two,2,12625136704411306072,'079c9ae7a4cd98a3e8cfb986e22d46a86cab868e58e8ea8da502584af58acd48')):
        need(row['result']=='rc-direct-shared-pass' and row['renderer_gpu_compaction'] is True,'GPU-direct path unavailable')
        need(row['renderer_path_readback_bytes']==row['provider_cpu_payload_transfer_bytes']==0,'GPU-direct transport copied path payload')
        need(row['pixel_mapping_bytes']==49152 and row['pixel_mapping_order']=='ascending-valid-pixels','GPU-direct pixel mapping mismatch')
        need(row['candidate_readback_bytes']==196608 and row['composite_admitted_pixels']==172 and 0<row['post_composite_mse']<.001,'GPU-direct composite guard mismatch')
        need(row['candidate_sha256']==candidate_hash and 0<row['direct_wall_ms']<60000,'GPU-direct composite identity/timing mismatch')
        need(row['populated_inference_samples']==row['populated_training_samples']==172 and row['training_batches']==batches,'GPU-direct counts mismatch')
        need(row['persistent_epochs']==row['provider_processes']==row['provider_contexts']==1 and row['provider_dispatches']==3+batches,'default GPU-direct context accounting mismatch')
        need(row['live_session'] is False and row['submitted_frame_epochs']==row['persistent_epochs'] and row['camera_reset_epochs']==0 and row['renderer_frame_input_submissions']==1 and row['provider_process_id']>0 and row['fence_values']=='30/31','default GPU-direct live-session isolation mismatch')
        need(row['first_epoch_post_hash_fnv1a64']==row['second_epoch_start_hash_fnv1a64']==post_hash and row['second_epoch_changed_values']==0,'default GPU-direct epoch isolation mismatch')
        need(row['baseline_hash_fnv1a64']==row['reset_hash_fnv1a64']==566204800999108543 and row['post_training_hash_fnv1a64']==post_hash and row['reset_exact'] is True,'GPU-direct sequence hash mismatch')
        need(row['shared_resources']==5 and row['shared_fences']==1 and row['allowlisted_handles']==6 and row['child_reaped'] is True,'GPU-direct containment mismatch')
        need(row['candidate_applied'] is False and row['authoritative_output']=='no-cache' and len(row['scene_sha256'])==len(row['frame_sha256'])==64,'GPU-direct claim boundary mismatch')
        need(row['apply_audit_readback_bytes']==row['applied_pixels']==row['changed_pixels']==0 and row['no_cache_output_sha256']==row['presentation_output_sha256']=='','default GPU-direct path mutated presentation')
    need(deterministic(direct_repeat)==deterministic(direct_one),'GPU-direct repeat changed')
    need(direct_two['post_composite_mse']<direct_one['post_composite_mse'],'second GPU-direct training batch did not improve composite')
    persistent=direct('--rc-persistent-epochs',2); persistent_repeat=direct('--rc-persistent-epochs',2)
    for row in (persistent,persistent_repeat):
        need(row['persistent_epochs']==2 and row['provider_processes']==row['provider_contexts']==1 and row['provider_dispatches']==7,'persistent GPU-direct context accounting mismatch')
        need(row['first_epoch_post_hash_fnv1a64']==row['second_epoch_start_hash_fnv1a64']==direct_one['post_training_hash_fnv1a64'] and row['second_epoch_changed_values']==516,'persistent GPU-direct epoch continuity mismatch')
        need(row['post_training_hash_fnv1a64']==direct_two['post_training_hash_fnv1a64'] and row['candidate_sha256']==direct_two['candidate_sha256'] and row['post_composite_mse']==direct_two['post_composite_mse'],'persistent GPU-direct final candidate mismatch')
        need(row['reset_exact'] is True and row['reset_hash_fnv1a64']==row['baseline_hash_fnv1a64'],'persistent GPU-direct reset mismatch')
    need(deterministic(persistent_repeat)==deterministic(persistent),'persistent GPU-direct repeat changed')
    need(persistent['direct_wall_ms']<direct_one['direct_wall_ms']+direct_repeat['direct_wall_ms'],'persistent GPU-direct transaction did not amortize two launches')
    direct_applied=direct('--rc-present-candidate'); direct_applied_repeat=direct('--rc-present-candidate')
    for row in (direct_applied,direct_applied_repeat):
        need(row['result']=='rc-direct-shared-pass' and row['candidate_applied'] is True and row['authoritative_output']=='radiance-cache-candidate','GPU-direct presentation was not admitted')
        need(row['apply_audit_readback_bytes']==49152 and row['applied_pixels']==row['changed_pixels']==172,'GPU-direct presentation coverage mismatch')
        need(row['no_cache_output_sha256']=='f6dabb47da97f149b859a9645c10af922c097057995da7cac9a661136f46c641','no-cache presentation identity mismatch')
        need(row['presentation_output_sha256']=='719b289967ea103fb13d98ad5661c9c3e31f8b417d17de98deb3dbdf6a4c1659','applied presentation identity mismatch')
    need(deterministic(direct_applied_repeat)==deterministic(direct_applied),'applied GPU-direct presentation changed')
    scheduled=direct('--rc-presentation-test')
    for scenario in ('camera','close','close-admission'):
        held=direct('--rc-scheduler-test',scenario)
        need(held['native_presentation'] is False and held['native_display_submissions']==0,'stale or closed RC output presented')
        need(held['scheduler_closed']==(scenario!='camera') and held['scheduler_pending']==(1 if scenario=='camera' else 0),'RC queue close/pending mismatch')
        need(held['scheduler_coalesced']==(2 if scenario=='camera' else 0) and held['scheduler_discarded']==1,'RC back-pressure mismatch')
        need(held['provider_wait_messages']>=2,'RC queue messages were not pumped')
    need(scheduled['candidate_applied'] is True and scheduled['authoritative_output']=='radiance-cache-candidate' and scheduled['candidate_sha256']==direct_applied['candidate_sha256'] and scheduled['presentation_output_sha256']==direct_applied['presentation_output_sha256'],'scheduled presentation candidate identity mismatch')
    need(scheduled['native_presentation'] is True and scheduled['native_display_submissions']==scheduled['native_display_verified']==1,'native RC presentation submission mismatch')
    need(scheduled['native_display_presented']+scheduled['native_display_occluded']==1 and scheduled['native_display_buffer_mask'] in (1,2),'native RC presentation status mismatch')
    need(scheduled['native_frame_latency']==1 and scheduled['frame_wait_mask']==7 and scheduled['frame_admission_attempts']<100,'native RC frame admission mismatch')
    need(scheduled['provider_wait_messages']>0 and scheduled['provider_wait_pumps']>0 and 0<scheduled['provider_wait_ms']<60000,'provider wait blocked native message scheduling')
    direct_low=direct('--rc-budget-mib',1); direct_timeout=direct('--rc-worker-timeout-ms',1)
    for row in (direct_low,direct_timeout): need(row['result']=='rc-direct-shared-fallback' and row['candidate_applied'] is False and row['authoritative_output']=='no-cache','GPU-direct fallback failed')
    applied_low=direct('--rc-present-candidate','--rc-budget-mib',1); applied_timeout=direct('--rc-present-candidate','--rc-worker-timeout-ms',1)
    for row in (applied_low,applied_timeout): need(row['result']=='rc-direct-shared-fallback' and row['candidate_applied'] is False and row['authoritative_output']=='no-cache','applied GPU-direct fallback mutated authority')
    persistent_low=direct('--rc-persistent-epochs',2,'--rc-budget-mib',1)
    need(persistent_low['result']=='rc-direct-shared-fallback' and persistent_low['candidate_applied'] is False and persistent_low['authoritative_output']=='no-cache','persistent GPU-direct fallback mutated authority')
    recovered_direct=direct('--rc-training-batches',1)
    need(deterministic(recovered_direct)==deterministic(direct_one),'GPU-direct path did not recover exactly')
    direct_moved=direct('--camera-offset',.05,0,0)
    need(direct_moved['result']=='rc-direct-shared-pass' and direct_moved['frame_sha256']!=direct_one['frame_sha256'] and direct_moved['scene_sha256']==direct_one['scene_sha256'],'GPU-direct camera identity mismatch')
    need(direct_moved['reset_exact'] is True and direct_moved['candidate_applied'] is False,'GPU-direct camera reset/authority mismatch')
    live_session=direct('--rc-live-session-test'); live_repeat=direct('--rc-live-session-test')
    renderer_session=direct('--rc-renderer-session-test','--debug')
    need(direct('--rc-renderer-session-test','--debug')==renderer_session,'renderer-commanded session repeat changed')
    (folder/'renderer-session.json').write_text(json.dumps(renderer_session,indent=2)+'\n',encoding='utf-8')
    need(renderer_session['result']=='rc-renderer-session-pass' and renderer_session['provider_processes']==renderer_session['provider_contexts']==1,'renderer session did not retain provider')
    need(renderer_session['epochs']==6 and renderer_session['provider_dispatches']==18 and renderer_session['reset_epochs']==4,'renderer session epoch accounting mismatch')
    need(renderer_session['admitted_epochs']==5 and renderer_session['discarded_epochs']==renderer_session['coalesced_requests']==1 and renderer_session['pending_requests']==0,'renderer session failed to consume latest queued input')
    need(renderer_session['renderer_input_submissions']==6 and renderer_session['per_epoch_gpu_allocations']==0 and renderer_session['prediction_readback_bytes']==884736,'renderer session resources/readback mismatch')
    need(renderer_session['child_reaped'] and renderer_session['stop_acknowledged'] and renderer_session['candidate_applied'] is False and renderer_session['authoritative_output']=='no-cache','renderer session lifecycle/authority mismatch')
    rows=renderer_session['records']; need([row['query_count'] for row in rows]==[172,178,178,172,172,172],'renderer session did not refresh counts')
    for index in (0,3,5): need(rows[index]['start_hash']==direct_one['baseline_hash_fnv1a64'] and rows[index]['post_hash']==direct_one['post_training_hash_fnv1a64'],'renderer session did not reset base exactly')
    need(rows[1]['start_hash']==live_session['changed_frame_baseline_hash_fnv1a64'] and rows[1]['post_hash']==live_session['post_training_hash_fnv1a64'],'renderer session camera reset mismatch')
    need(rows[2]['start_hash']==rows[1]['post_hash'] and rows[2]['post_hash']==8100200300773600753 and rows[4]['post_hash']==direct_two['post_training_hash_fnv1a64'],'renderer session training continuation mismatch')
    for extra in (('--rc-budget-mib',1),('--rc-worker-timeout-ms',1)):
        failed=direct('--rc-renderer-session-test',*extra)
        need(failed['result']=='rc-direct-shared-fallback' and failed['authoritative_output']=='no-cache' and failed['candidate_applied'] is False,'renderer session failure changed authority')
    need(direct('--rc-renderer-session-test','--debug')==renderer_session,'renderer session recovery changed')
    lifetime=direct('--rc-resource-test')
    pooled=direct('--rc-pool-test')
    gpu_pooled=direct('--rc-gpu-pool-test','--debug')
    (folder/'gpu-pool.json').write_text(json.dumps(gpu_pooled,indent=2)+'\n',encoding='utf-8')
    need(gpu_pooled['gpu_pool_enabled'] is True and gpu_pooled['iterations']==8 and len(gpu_pooled['transactions'])==8 and gpu_pooled['pool_restore_submissions']==7 and gpu_pooled['pool_restored_buffers']==61,'RC GPU pool state restoration missing')
    for diagnostic in gpu_pooled['transactions'][6:]:
        need(diagnostic['candidate_applied'] is False and diagnostic['authoritative_output']=='no-cache' and diagnostic['candidate_sha256']==direct_one['candidate_sha256'],'GPU pool diagnostic authority/identity changed')
    need(0<gpu_pooled['buffer_pool_retained_bytes']<=8*1024*1024 and gpu_pooled['baseline_live_bytes']==gpu_pooled['final_live_bytes'],'RC GPU pool leaked/exceeded budget')
    need(gpu_pooled['buffer_pool_reuses']>pooled['staging_pool_reuses'],'RC GPU buffers were not reused')
    for expected,actual in zip(lifetime['transactions'],gpu_pooled['transactions']):
        need(deterministic(expected)==deterministic(actual),'GPU-pooled RC transaction changed result')
    (folder/'staging-pool.json').write_text(json.dumps(pooled,indent=2)+'\n',encoding='utf-8')
    need(pooled['staging_pool_enabled'] is True and pooled['staging_pool_allocations']>0 and pooled['staging_pool_reuses']>0,'RC staging pool did not reuse allocations')
    need(0<pooled['staging_pool_retained_bytes']<=1024*1024 and pooled['baseline_live_bytes']==pooled['final_live_bytes'],'RC staging pool exceeded/leaked budget')
    for expected,actual in zip(lifetime['transactions'],pooled['transactions']):
        need(deterministic(expected)==deterministic(actual),'pooled RC transaction changed result')
    (folder/'resource-lifetime.json').write_text(json.dumps(lifetime,indent=2)+'\n',encoding='utf-8')
    need(lifetime['result']=='rc-resource-lifetime-pass' and lifetime['iterations']==6,'RC lifetime fixture failed')
    need(0<lifetime['baseline_live_bytes']==lifetime['final_live_bytes']<lifetime['peak_requested_bytes'],'RC buffer budget was not returned')
    runs=lifetime['transactions']; need(len(runs)==6,'RC lifetime transactions missing')
    for index in (0,1,3):
        need(runs[index]['candidate_sha256']==direct_applied['candidate_sha256'] and runs[index]['presentation_output_sha256']==direct_applied['presentation_output_sha256'],'same-renderer recovery candidate changed')
    need(runs[2]['result']=='rc-direct-shared-fallback' and runs[2]['authoritative_output']=='no-cache','RC lifecycle failure not contained')
    need(runs[4]['candidate_sha256']==runs[5]['candidate_sha256']==live_session['candidate_sha256'],'RC lifecycle moved/live candidate changed')
    for row in (live_session,live_repeat):
        need(row['live_session'] is True and row['submitted_frame_epochs']==3 and row['camera_reset_epochs']==1 and row['renderer_frame_input_submissions']==2,'live RC frame submission accounting mismatch')
        need(row['populated_inference_samples']==row['populated_training_samples']==178 and row['composite_admitted_pixels']==178,'live RC changed-frame population mismatch')
        need(row['provider_processes']==row['provider_contexts']==1 and row['provider_process_id']>0 and row['provider_dispatches']==10 and row['fence_values']=='30/31/32/33/34/35','live RC process/fence accounting mismatch')
        need(row['first_epoch_post_hash_fnv1a64']==row['second_epoch_start_hash_fnv1a64']==direct_one['post_training_hash_fnv1a64'] and row['stable_epoch_post_hash_fnv1a64']==direct_two['post_training_hash_fnv1a64'] and row['second_epoch_changed_values']==516,'live RC stable continuity mismatch')
        need(row['changed_frame_baseline_hash_fnv1a64']==9990495896441858603 and row['post_training_hash_fnv1a64']==587237281996004111 and row['reset_hash_fnv1a64']==row['changed_frame_baseline_hash_fnv1a64'] and row['changed_frame_changed_values']==534 and row['reset_exact'] is True,'live RC changed-frame reset mismatch')
        need(row['initial_frame_sha256']==direct_one['frame_sha256'] and row['frame_sha256']!=row['initial_frame_sha256'] and row['scene_sha256']==direct_one['scene_sha256'],'live RC frame identity mismatch')
        need(row['candidate_sha256']==direct_moved['candidate_sha256']=='31f8700b024782226c43284f4849cb0a5539a47a4eb45cd7e0aa5985adde7761' and row['post_composite_mse']==direct_moved['post_composite_mse'],'live RC changed-frame composite mismatch')
    need(deterministic(live_repeat)==deterministic(live_session),'live RC session repeat changed')
    live_low=direct('--rc-live-session-test','--rc-budget-mib',1); live_timeout=direct('--rc-live-session-test','--rc-worker-timeout-ms',1)
    for row in (live_low,live_timeout): need(row['result']=='rc-direct-shared-fallback' and row['candidate_applied'] is False and row['authoritative_output']=='no-cache','live RC session fallback mutated authority')
    need(deterministic(direct('--rc-live-session-test'))==deterministic(live_session),'live RC session did not recover exactly')
    def shared(batches):
        process=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-path-sequence',str(paths),'--training-batches',str(batches)],capture_output=True,text=True,env=env,timeout=70)
        need(process.returncode==0,(process.stdout,process.stderr)); return json.loads(process.stdout)
    shared_one=shared(1); shared_repeat=shared(1); shared_two=shared(2)
    def session(commands,*extra,ok=True):
        process=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-path-sequence',str(paths),'--session-commands',commands,*map(str,extra)],capture_output=True,text=True,env=env,timeout=30)
        need((process.returncode==0)==ok,(process.stdout,process.stderr))
        return json.loads(process.stdout) if ok else None
    commanded=session('RCRCC'); need(session('RCRCC')==commanded,'commanded session repeat changed')
    (folder/'commanded-session.json').write_text(json.dumps(commanded,indent=2)+'\n',encoding='utf-8')
    need(commanded['result']=='shared-session-pass' and commanded['provider_processes']==commanded['provider_contexts']==1 and commanded['epochs']==5 and commanded['provider_dispatches']==15,'commanded session lifecycle mismatch')
    need(commanded['shared_resources']==5 and commanded['shared_fences']==1 and commanded['allowlisted_handles']==6 and commanded['stop_acknowledged'] and commanded['child_reaped'],'commanded session containment mismatch')
    records=commanded['records']; need(len(records)==5,'commanded session records missing')
    for index in (0,2): need(records[index]['reset'] and records[index]['start_hash']==PATH_BASELINE_HASH and records[index]['post_hash']==PATH_POST_TRAINING_HASH,'commanded reset not exact')
    for index in (1,3): need(not records[index]['reset'] and records[index]['start_hash']==PATH_POST_TRAINING_HASH and records[index]['post_hash']==PATH_POST_TWO_BATCH_HASH,'commanded continuation not exact')
    need(records[4]['start_hash']==PATH_POST_TWO_BATCH_HASH and records[4]['post_hash']==commanded['final_output_hash']==1061084142929051959,'commanded third training/shared output mismatch')
    need(session('R')['final_output_hash']==PATH_POST_TRAINING_HASH,'single epoch stop failed')
    need(session('R'*16)['epochs']==16,'maximum parent command sequence failed')
    for invalid in ('','C','RX','R'*17): session(invalid,ok=False)
    session('RCRCC','--budget-mib',1,ok=False); session('RCRCC','--worker-timeout-ms',1,ok=False)
    need(session('RCRCC')==commanded,'commanded session did not recover after failure')
    shared_common={'result':'shared-path-sequence-pass','artifact_sha256':source['artifact_sha256'],'populated_inference_samples':172,'populated_training_samples':172,'budget_bytes':33554432,
                   'baseline_hash_fnv1a64':PATH_BASELINE_HASH,'reset_hash_fnv1a64':PATH_BASELINE_HASH,'post_changed_values':516,'reset_changed_values':0,'reset_exact':True,
                   'external_buffer_bytes':716808,'shared_resources':5,'shared_fences':1,'allowlisted_handles':6,'fence_values':[30,31,32],
                   'child_reaped':True,'child_exit_code':0,'cpu_payload_transfer_bytes':0}
    need(shared_one==dict(shared_common,training_batches=1,post_training_hash_fnv1a64=PATH_POST_TRAINING_HASH),'one-batch shared path mismatch')
    need(shared_repeat==shared_one,'shared path repeat changed')
    need(shared_two==dict(shared_common,training_batches=2,post_training_hash_fnv1a64=PATH_POST_TWO_BATCH_HASH),'two-batch shared path mismatch')
    shared_stream_process=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-stream-sequence','--training-batches','1','--budget-mib','32','--worker-timeout-ms','60000'],input=paths.read_bytes(),capture_output=True,env=env,timeout=70)
    need(shared_stream_process.returncode==0,(shared_stream_process.stdout,shared_stream_process.stderr)); need(json.loads(shared_stream_process.stdout)==shared_one,'shared stream and file results differ')
    shared_low=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-path-sequence',str(paths),'--budget-mib','1'],capture_output=True,env=env,timeout=70)
    shared_timeout=subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-path-sequence',str(paths),'--worker-timeout-ms','1'],capture_output=True,env=env,timeout=15)
    need(shared_low.returncode!=0 and shared_timeout.returncode!=0,'shared path failure containment did not reject')
    need(shared(1)==shared_one,'shared path did not recover exactly after failure')
    first=run_sequence(args.probe,args.sdk_bin,path_sequence=paths); repeat=run_sequence(args.probe,args.sdk_bin,path_sequence=paths)
    live=run_live(args.dxr,scene,args.probe,args.sdk_bin)
    persistent=run_live(args.dxr,scene,args.probe,args.sdk_bin,training_batches=2)
    for label,report in (('first',first),('repeat',repeat)):
        decision=report['decision']; need(decision['status']=='training-observed-with-workarounds',label+' renderer sequence unavailable')
        need(decision['renderer_fixture'] is True and decision['offline_composite_validated'] is True and decision['rc_rendering'] is False,'claim boundary mismatch')
        need(decision['artifact_sha256']==source['artifact_sha256'],'artifact identity mismatch')
        need(decision['baseline_hash_fnv1a64']==PATH_BASELINE_HASH and decision['post_training_hash_fnv1a64']==PATH_POST_TRAINING_HASH,'fixture output hash mismatch')
        need(decision['post_changed_values']==516 and decision['target_mse_after']<decision['target_mse_before'] and decision['reset_exact'] is True,'fixture training/reset mismatch')
    need(first['decision']==repeat['decision'],'fresh renderer sequence decision changed')
    comparable={key:value for key,value in live['decision'].items() if key not in ('transport','persistent_file_bytes','authoritative_output','candidate_applied','fallback_available')}
    need(comparable==first['decision'],'stream and file sequence decisions differ')
    need(live['decision']['transport']=='bounded-stdin-pipe' and live['decision']['persistent_file_bytes']==0,'live transport claim mismatch')
    need(live['decision']['authoritative_output']=='no-cache' and live['decision']['candidate_applied'] is False and live['decision']['fallback_available'] is True,'live fallback contract mismatch')
    need(all(live['renderer'][key]==value for key,value in dict(artifact_sha256=source['artifact_sha256'],bytes=len(paths.read_bytes()),queries=172,training=172).items()),'live renderer evidence mismatch')
    need(0<live['renderer']['wall_ms']<60000 and 0<live['provider_wall_ms']<70000 and 0<live['total_wall_ms']<130000,'live timing bounds mismatch')
    need(persistent['decision']['training_batches']==2 and persistent['decision']['post_training_hash_fnv1a64']==PATH_POST_TWO_BATCH_HASH,'two-frame persistent hash mismatch')
    need(persistent['decision']['target_mse_after']<live['decision']['target_mse_after'] and persistent['decision']['composite_mse_after']<live['decision']['composite_mse_after'],'second persistent frame did not improve')
    need(persistent['decision']['reset_exact'] is True and persistent['decision']['persistent_file_bytes']==0,'persistent reset/transport mismatch')
    low=run_live(args.dxr,scene,args.probe,args.sdk_bin,budget_mib=1)
    need(low['decision']['reason']=='worker-crash' and low['worker']['child_reaped'] is True and low['decision']['authoritative_output']=='no-cache','live low-budget fallback failed')
    timed=run_live(args.dxr,scene,args.probe,args.sdk_bin,timeout_ms=1)
    need(timed['decision']['reason']=='worker-timeout' and timed['worker']['child_reaped'] is True and timed['decision']['candidate_applied'] is False,'live timeout fallback failed')
    recovered=run_live(args.dxr,scene,args.probe,args.sdk_bin)
    need(recovered['decision']==live['decision'],'live transaction did not recover exactly')
    moved=run_live(args.dxr,scene,args.probe,args.sdk_bin,camera_offset=(.05,0,0))
    need(moved['renderer']['artifact_sha256']!=live['renderer']['artifact_sha256'] and moved['worker']['child_pid']!=live['worker']['child_pid'],'camera identity did not restart isolated state')
    need(moved['decision']['status']=='training-observed-with-workarounds' and moved['decision']['reset_exact'] is True,'camera-change reset transaction failed')
    need(moved['decision']['target_mse_after']<moved['decision']['target_mse_before'] and moved['decision']['composite_mse_after']<moved['decision']['composite_mse_before'],'camera-change candidate did not improve')
    envelope=first['worker']; need(assess(envelope,allow_workaround=True)['status']=='unavailable','fixture admitted without artifact identity')
    digest=source['artifact_sha256']
    for key,value in {'artifact_sha256':'0'*64,'populated_inference_samples':173,'populated_training_samples':173,'renderer_fixture':False,
                      'composite_mse_improved':False,'post_composite_mse':1.0}.items():
        candidate=copy.deepcopy(envelope); data=json.loads(candidate['stdout']); data['sequence_tests'][0][key]=value; candidate['stdout']=json.dumps(data)
        need(assess(candidate,allow_workaround=True,artifact_sha256=digest)['status']=='unavailable','accepted fixture mutation '+key)
    bad=bytearray(paths.read_bytes()); bad[224]^=1; corrupt=folder/'corrupt.rcpaths'; corrupt.write_bytes(bad)
    need(subprocess.run([str(args.probe),'--sdk-bin',str(args.sdk_bin),'--shared-path-sequence',str(corrupt)],capture_output=True).returncode!=0,'shared path accepted corrupt artifact')
    try: run_sequence(args.probe,args.sdk_bin,path_sequence=corrupt)
    except ValueError: pass
    else: raise AssertionError('managed worker accepted corrupt artifact')
    base=[str(args.probe),'--sdk-bin',str(args.sdk_bin)]
    stream_command=base+['--isolated-stream-sequence','--training-batches','1','--worker-timeout-ms','60000']
    truncated=subprocess.run(stream_command,input=paths.read_bytes()[:-1],capture_output=True)
    oversized=subprocess.run(stream_command,input=paths.read_bytes()+b'x',capture_output=True)
    need(truncated.returncode!=0 and oversized.returncode!=0 and not truncated.stdout and not oversized.stdout,'stream length boundary accepted')
    shared_stream_command=base+['--shared-stream-sequence']
    shared_truncated=subprocess.run(shared_stream_command,input=paths.read_bytes()[:-1],capture_output=True)
    shared_oversized=subprocess.run(shared_stream_command,input=paths.read_bytes()+b'x',capture_output=True)
    need(shared_truncated.returncode!=0 and shared_oversized.returncode!=0 and not shared_truncated.stdout and not shared_oversized.stdout,'shared stream length boundary accepted')
    corrupt_stream=subprocess.run(stream_command,input=bytes(bad),capture_output=True)
    corrupt_envelope=json.loads(corrupt_stream.stdout)
    need(corrupt_stream.returncode==0 and corrupt_envelope['child_reaped'] is True and corrupt_envelope['exit_code']==1,'corrupt stream not contained')
    need(subprocess.run(base+['--dispatch-test','--path-sequence',str(paths)],capture_output=True).returncode!=0,'path accepted outside sequence mode')
    need(subprocess.run(base+['--sequence-test','--path-sequence','relative.rcpaths'],capture_output=True).returncode!=0,'relative path accepted')
    need(subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-present-candidate'],capture_output=True).returncode!=0,'candidate presentation accepted outside RC direct mode')
    need(subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-presentation-test'],capture_output=True).returncode!=0,'native candidate presentation accepted outside RC direct mode')
    for epochs in (0,3): need(subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-shared-probe',str(args.probe),'--rc-sdk-bin',str(args.sdk_bin),'--rc-persistent-epochs',str(epochs)],capture_output=True).returncode!=0,'invalid persistent epoch count accepted')
    need(subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','1','--rc-shared-probe',str(args.probe),'--rc-sdk-bin',str(args.sdk_bin),'--rc-live-session-test','--rc-persistent-epochs','2'],capture_output=True).returncode!=0,'live session accepted conflicting persistent epochs')
    print(json.dumps(dict(result='pass',artifact_sha256=digest,query_count=172,baseline_hash=PATH_BASELINE_HASH,post_hash=PATH_POST_TRAINING_HASH,transport=live['decision']['transport'],two_batch_hash=PATH_POST_TWO_BATCH_HASH,
                          target_mse_before=first['decision']['target_mse_before'],target_mse_after=first['decision']['target_mse_after'],artifacts=str(folder))))
    return 0


if __name__=='__main__': raise SystemExit(main())
