"""Replay real captured position inputs on a fresh native device per draw."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from inspect_position_capture import inspect,need
from reconstruct_positions import bounded_hash

def verify(capture,fixture):
    digest=bounded_hash(capture);source=inspect(capture,include_records=True)
    need(digest==bounded_hash(capture),'capture changed')
    need(source['completion'] in ('capture_limit','attempt_limit','byte_limit','present_limit') and source['records'],'completed captures required')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
    draws=[]
    for row in source['records']:
        payload='\n'.join(row[k] for k in ('shader','constants','positions'))+'\n'
        result=subprocess.run([str(fixture),'--recorded-position'],input=payload,env=env,capture_output=True,text=True,timeout=60)
        if result.returncode:
            draws.append({'ordinal':row['ordinal'],'status':'failed','error':result.stderr[:1000]});continue
        evidence=json.loads(result.stdout)
        need(evidence.get('status') in ('matched','empty'),'unexpected fixture status')
        draws.append({'ordinal':row['ordinal'],'triangles':row['primitives'],'source_target':row['target'],**evidence})
    return {'schema':'rrt-recorded-position-verification','version':1,'source_sha256':digest,'draws':draws,
            'scope':'position-only raster comparison at diagnostic resolution; empty draws are not visible validation'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args()
    try:
        report=verify(a.capture,a.fixture)
        if a.out:
            with a.out.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
        print(json.dumps(report,indent=2))
        if any(d['status']=='failed' for d in report['draws']):raise SystemExit(1)
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as e:p.exit(2,f'verification rejected: {e}\n')
