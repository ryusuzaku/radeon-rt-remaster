"""Run one no-file DXR renderer-to-isolated-Radiance-Cache transaction."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from inspect_rc_paths import decode_paths,FILE_BYTES
from rc_sequence_worker import assess
from rc_worker import strict_json,verify_sdk


def run_live(dxr,scene,probe,sdk_bin,*,budget_mib=32,adapter=0,timeout_ms=60000,training_batches=1,camera_offset=(0,0,0)):
    dxr=Path(dxr).resolve(strict=True); scene=Path(scene).resolve(strict=True); probe=Path(probe).resolve(strict=True); sdk_bin=Path(sdk_bin).resolve(strict=True)
    if not dxr.is_file() or not scene.is_file() or not probe.is_file() or not sdk_bin.is_dir(): raise ValueError('live transaction paths have wrong types')
    if not 1<=budget_mib<=256 or not 0<=adapter<=31 or not 1<=timeout_ms<=60000 or training_batches not in (1,2): raise ValueError('invalid live transaction limits')
    if type(camera_offset) not in (tuple,list) or len(camera_offset)!=3 or any(type(x) not in (int,float) or not -2<=x<=2 for x in camera_offset): raise ValueError('invalid live camera offset')
    env={key:value for key,value in os.environ.items() if not key.startswith('RRT_')}
    total_start=time.perf_counter(); renderer_start=total_start
    render_command=[str(dxr),str(scene),'--mode','gi','--samples','1','--rc-stream']
    if any(camera_offset): render_command += ['--camera-offset',*map(str,camera_offset)]
    renderer=subprocess.run(render_command,capture_output=True,env=env,timeout=60,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if renderer.returncode or renderer.stderr or len(renderer.stdout)!=FILE_BYTES: raise RuntimeError('renderer RC stream failed')
    renderer_ms=(time.perf_counter()-renderer_start)*1000
    source=decode_paths(renderer.stdout); digest=source['artifact_sha256']
    hashes=verify_sdk(sdk_bin)
    command=[str(probe),'--isolated-stream-sequence','--training-batches',str(training_batches),'--sdk-bin',str(sdk_bin),'--debug',
             '--budget-mib',str(budget_mib),'--adapter',str(adapter),'--worker-timeout-ms',str(timeout_ms)]
    provider_start=time.perf_counter(); process=subprocess.run(command,input=renderer.stdout,capture_output=True,timeout=timeout_ms/1000+10,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    provider_ms=(time.perf_counter()-provider_start)*1000
    if process.returncode or process.stderr or len(process.stdout)>1024*1024:
        raise RuntimeError(f'RC live isolation host failed (exit={process.returncode}, stdout={len(process.stdout)}, stderr={process.stderr[:512]!r})')
    envelope=strict_json(process.stdout.decode('utf-8'))
    counts=(len(source['queries']),len(source['training']))
    decision=assess(envelope,budget_mib=budget_mib,adapter=adapter,allow_workaround=True,artifact_sha256=digest,training_batches=training_batches,
                    populated_counts=counts,dynamic_fixture=bool(any(camera_offset)))
    decision['transport']='bounded-stdin-pipe'; decision['persistent_file_bytes']=0; decision['authoritative_output']='no-cache'
    decision['candidate_applied']=False; decision['fallback_available']=True
    return dict(decision=decision,sdk_sha256=hashes,renderer=dict(artifact_sha256=digest,bytes=len(renderer.stdout),queries=len(source['queries']),training=len(source['training']),wall_ms=renderer_ms),
                provider_wall_ms=provider_ms,total_wall_ms=(time.perf_counter()-total_start)*1000,worker=envelope)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--dxr',type=Path,required=True); parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True); parser.add_argument('--sdk-bin',type=Path,required=True); parser.add_argument('--budget-mib',type=int,default=32); parser.add_argument('--timeout-ms',type=int,default=60000)
    parser.add_argument('--training-batches',type=int,choices=(1,2),default=1)
    args=parser.parse_args()
    try: report=run_live(args.dxr,args.scene,args.probe,args.sdk_bin,budget_mib=args.budget_mib,timeout_ms=args.timeout_ms,training_batches=args.training_batches)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(decision=dict(status='unavailable',reason=str(error),rc_rendering=False,rc_training_observed=False)))); return 1
    print(json.dumps(report)); return 0 if report['decision']['status'].startswith('training-observed') else 1


if __name__=='__main__': raise SystemExit(main())
