"""Native proxy inventory contract and CPU reader admission checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_shader_inventory import inspect
p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--proxy',type=Path,required=True);a=p.parse_args()
root=Path(tempfile.mkdtemp(prefix='shader-inventory-',dir=a.fixture.parent))
clean={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
def run(name,variables):
    out=root/name;out.mkdir()
    env=dict(clean,RRT_FIXTURE_PROXY=str(a.proxy),**{k:str(v) for k,v in variables.items()})
    r=subprocess.run([str(a.fixture),'--fixture',str(out)],env=env,capture_output=True,text=True,timeout=30)
    assert r.returncode==0,(r.stdout,r.stderr,root)
    if name!='oracle':
        for i in range(3):
            assert (out/f'variant-{i}.bgr').read_bytes()==(root/'oracle'/f'variant-{i}.bgr').read_bytes()
    return out
run('oracle',{'RRT_PROXY_DISABLE':'1'})
for limit in (1,3,4,512):
    file=root/f'{limit}.jsonl'
    run(f'limit-{limit}',{'RRT_SHADER_INVENTORY_FILE':file,'RRT_SHADER_INVENTORY_DRAWS':limit})
    report=inspect(file)
    assert report['draws']==min(limit,4) and report['failed_draws']==report['unavailable_queries']==0,report
    assert report['completion']==('partial' if limit>4 else 'draw_limit'),report
    assert len(report['programs'])==2 and len(report['families'])==(1 if limit==1 else 2),report
file=root/'failed.jsonl'
unknown=root/'unknown.jsonl'
snapshot=root/'unknown.rrshader'
run('unknown',{'RRT_SHADER_INVENTORY_FILE':unknown,'RRT_SHADER_INVENTORY_DRAWS':1,'RRT_SHADER_FIXTURE_CASE':'inventory-unknown','RRT_SHADER_SNAPSHOT_FILE':snapshot})
assert not snapshot.exists() and Path(str(snapshot)+'.rejected').exists()
known=inspect(root/'1.jsonl');opaque=inspect(unknown)
assert opaque['unavailable_queries']==0 and opaque['families'][0]['ps']!=known['families'][0]['ps']
budget=root/'budget.jsonl'
run('budget',{'RRT_SHADER_INVENTORY_FILE':budget,'RRT_SHADER_INVENTORY_DRAWS':4096,'RRT_SHADER_FIXTURE_CASE':'inventory-budget'})
assert inspect(budget)['completion']=='byte_limit' and budget.stat().st_size<=16*1024*1024
run('failed',{'RRT_SHADER_INVENTORY_FILE':file,'RRT_SHADER_INVENTORY_DRAWS':1,'RRT_SHADER_FIXTURE_CASE':'failed-draw'})
assert inspect(file)['failed_draws']==1 and not inspect(file)['families']
marker=root/'trigger';file=root/'triggered.jsonl'
run('waiting',{'RRT_SHADER_INVENTORY_FILE':file,'RRT_SHADER_INVENTORY_TRIGGER_FILE':marker})
assert not file.exists()
marker.mkdir()
run('directory-marker',{'RRT_SHADER_INVENTORY_FILE':file,'RRT_SHADER_INVENTORY_TRIGGER_FILE':marker})
assert not file.exists()
marker=root/'regular.trigger';marker.write_text('go')
run('triggered',{'RRT_SHADER_INVENTORY_FILE':file,'RRT_SHADER_INVENTORY_TRIGGER_FILE':marker,'RRT_SHADER_INVENTORY_DRAWS':1})
assert inspect(file)['completion']=='draw_limit'
for name,extra in [('disabled',{'RRT_PROXY_DISABLE':'1'}),('invalid-limit',{'RRT_SHADER_INVENTORY_DRAWS':4097})]:
    file=root/f'{name}.jsonl';run(name,dict(RRT_SHADER_INVENTORY_FILE=file,**extra));assert not file.exists()
file=root/'collision.jsonl';file.write_bytes(b'preserve')
run('collision',{'RRT_SHADER_INVENTORY_FILE':file});assert file.read_bytes()==b'preserve'
run('missing-parent',{'RRT_SHADER_INVENTORY_FILE':root/'absent'/'out.jsonl'})
records=[json.loads(s) for s in (root/'1.jsonl').read_text().splitlines()]
cases=[records+[records[1]], [records[0],records[1],records[1]], [records[0],dict(records[1],vs='00')],
       [records[0],dict(records[1],streams=[])], [records[0],dict(records[2],committed=9)],
       [dict(records[0],draw_limit=0)], [records[0],dict(records[1],declaration='00'*8)]]
for i,rows in enumerate(cases):
    file=root/f'bad-{i}.jsonl';file.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    try: inspect(file)
    except ValueError: pass
    else: raise AssertionError(('reader admitted invalid evidence',i))
print(f'PASS bounded inventory, unchanged pixels, native failure, trigger, collision, reader rejection: {root}')
