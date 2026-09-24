"""Replay admitted constant-RGBA prefixes; never a general game-frame renderer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from inspect_position_capture import inspect_bytes,need
from position_color_replay import prefix,payload
from texture_assets import TextureAssets

def replay(path,fixture):
    with Path(path).open('rb') as f:data=f.read(16*1024*1024+1)
    report=inspect_bytes(data,include_records=True,assets=TextureAssets(path))
    need(report['version']>=10 and report['records'] and report['completion'] in ('capture_limit','attempt_limit','byte_limit','present_limit'),'completed v10+ capture required')
    endpoints={}
    for row in report['records']:
        key=(row['device'],row['timing']['reset_epoch'],row['render_state']['target_id'],row['render_state']['clear_serial'])
        endpoints[key]=row
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
    segments=[]
    for endpoint in endpoints.values():
        item={'endpoint_ordinal':endpoint['ordinal'],'through_write_serial':endpoint['write_evidence']['through'],'ready_for_stateful_replay':False}
        try:selected=prefix(report['records'],endpoint)
        except ValueError as e:item.update(status='unqualified',reason=str(e));segments.append(item);continue
        item.update(ready_for_stateful_replay=True,ordinals=[r['ordinal'] for r in selected],clear_color=endpoint['render_state']['last_clear']['color'])
        native=subprocess.run([str(fixture),'--position-group'],input=payload(selected),text=True,capture_output=True,env=env,timeout=60)
        if native.returncode:item.update(status='failed',error=native.stderr[:1000])
        else:
            result=json.loads(native.stdout)
            need(result.get('mode')=='constant_rgba_color' and result.get('status') in ('matched','empty') and result.get('draws')==len(selected),'invalid color replay result')
            item.update(result)
            # Nonzero clear alpha is not geometric coverage. A successful full
            # pixel comparison remains a match even if every output alpha is zero.
            item['nonzero_alpha_pixels']=item.pop('covered');item['status']='matched'
        segments.append(item)
    return {'schema':'rrt-position-color-replay','version':1,'source_sha256':hashlib.sha256(data).hexdigest(),
            'contract':'private_rt0_constant_rgba_128x96_v1','segments':segments,
            'scope':'captured clear through explicit endpoint; native-vs-CPU vertex path comparison; no game materials or full frame claim'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args()
    try:
        if a.out:need(not a.out.exists(),'output exists')
        result=replay(a.capture,a.fixture)
        if a.out:
            with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps(result,indent=2))
        if any(s['status'] in ('failed','unqualified') for s in result['segments']):raise SystemExit(1)
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as e:p.exit(2,f'color replay rejected: {e}\n')
