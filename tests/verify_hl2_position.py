"""Local-evidence GPU oracle; requires the user's bounded HL2 inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_shader_inventory import inspect

p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args()
digest='0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2'
report=inspect(a.inventory)
assert any(s['stage']=='vs' and s['sha256']==digest for s in report['programs']), 'required shader absent'
code=None
with a.inventory.open(encoding='utf-8') as stream:
    for _ in range(4098):
        line=stream.readline(70001)
        if not line: break
        assert len(line)<=70000 and line.endswith('\n')
        row=json.loads(line);candidate=row.get('vs')
        if isinstance(candidate,str) and len(candidate)==1224 and hashlib.sha256(bytes.fromhex(candidate)).hexdigest()==digest:
            code=candidate;break
assert code is not None
env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
result=subprocess.run([str(a.fixture),'--hl2-position'],input=code+'\n',env=env,capture_output=True,text=True,timeout=60)
assert result.returncode==0,(result.stdout,result.stderr)
assert 'variants=24' in result.stdout and 'PASS exact HL2 VS hardware raster oracle' in result.stdout
print(result.stdout,end='')
bad=('0' if code[0]!='0' else '1')+code[1:]
result=subprocess.run([str(a.fixture),'--hl2-position'],input=bad+'\n',env=env,capture_output=True,text=True,timeout=15)
assert result.returncode!=0 and 'position program not admitted' in result.stderr
