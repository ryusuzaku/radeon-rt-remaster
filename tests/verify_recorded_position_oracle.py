"""Real capture oracle regression and bounded native-input rejection."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_recorded_positions import verify
from inspect_position_capture import inspect
p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);a=p.parse_args()
report=verify(a.capture,a.fixture)
assert report['draws'] and all(d['status'] in ('matched','empty') for d in report['draws']),report
assert any(d['status']=='matched' and d['covered']>0 for d in report['draws']),'all-empty result is not a visible verification'
rows=inspect(a.capture,include_records=True)['records'];row=rows[0]
env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
shader=row['shader'];constants=row['constants'];positions=row['positions']
for data in [shader+'\n',shader+'\n00\n'+positions+'\n',shader+'\n'+constants+'\n00\n',
             shader+'\n'+constants+'\n'+positions+'\nextra',
             shader+'\n0000807f'+constants[8:]+'\n'+positions+'\n',
             shader+'\n'+constants+'\n'+('00'*(4096*3*12+1))+'\n']:
    result=subprocess.run([str(a.fixture),'--recorded-position'],input=data,env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode!=0,'invalid native fixture input admitted'
print(json.dumps(report))
