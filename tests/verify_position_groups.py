"""Saved multi-draw composition plus controlled ordering and admission checks."""
import argparse
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from replay_position_groups import groups, payload, replay

p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);a=p.parse_args()
digest,session,batches=groups(a.capture)
assert len(batches)==4 and all(len(rows)==4 for _,rows in batches)
result=replay(a.capture,a.fixture)
assert all(g['status']=='matched' and g['max_normalized_error']==0 for g in result['groups'])
assert [g['covered'] for g in result['groups']]==[2593,2588,2555,2565]
env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
def invoke(text):
    return subprocess.run([str(a.fixture),'--position-group'],input=text,text=True,capture_output=True,env=env,timeout=30)
def draw(rows):
    r=invoke(payload(rows));assert r.returncode==0,(r.stdout,r.stderr)
    return json.loads(r.stdout)

# Synthetic controls: independent model rows, shared identity clip transform.
base=copy.deepcopy(batches[0][1][0]);c=[0.,1.,2.,.5]+[1.,0.,0.,0., 0.,1.,0.,0., 0.,0.,1.,0., 0.,0.,0.,1.]+[1.,0.,0.,0., 0.,1.,0.,0., 0.,0.,1.,0.]
base['constants']=struct.pack('<32f',*c).hex()
left=dict(base,positions=struct.pack('<9f',-.9,-.8,.3,-.2,-.8,.3,-.55,.8,.3).hex())
right=dict(base,positions=struct.pack('<9f',.2,-.8,.3,.9,-.8,.3,.55,.8,.3).hex())
l,r=draw([left]),draw([right]);combined=draw([left,right])
assert l['covered']>0 and r['covered']>0 and combined['covered']==l['covered']+r['covered']
assert draw([right,left])['fingerprint_fnv1a64']==combined['fingerprint_fnv1a64']
changed=list(c);changed[23]=5.0 # model-output x translation; clip stays unchanged
overlay=dict(left,constants=struct.pack('<32f',*changed).hex())
assert draw([left,overlay])['fingerprint_fnv1a64']==draw([overlay])['fingerprint_fnv1a64']
assert draw([overlay,left])['fingerprint_fnv1a64']==l['fingerprint_fnv1a64']
assert draw([overlay])['fingerprint_fnv1a64']!=l['fingerprint_fnv1a64']
assert draw([left]*16)['covered']==l['covered']

valid=payload([left,right])
bad_constants=list(c);bad_constants[0]=float('nan')
mixed=list(c);mixed[7]=.1
invalid=[valid[:-1],valid+'x',valid.replace('\n2\n','\n0\n',1),valid.replace('\n2\n','\n17\n',1),
         payload([dict(left,constants=struct.pack('<32f',*bad_constants).hex())]),
         payload([left,dict(right,constants=struct.pack('<32f',*mixed).hex())]),
         payload([dict(left,positions='00')]),
         payload([dict(left,positions='00'*(4096*3*12+12))])]
for text in invalid:
    r=invoke(text);assert r.returncode!=0,(r.stdout,r.stderr)

# Grouping is deterministic, separates incompatible descriptors and never invents frames.
with tempfile.TemporaryDirectory(prefix='position-groups-') as temp:
    target=Path(temp)/'ledger.jsonl';rows=[json.loads(x) for x in a.capture.read_text().splitlines()]
    target.write_text(''.join(json.dumps(r)+'\n' for r in [rows[0],*reversed(rows[1:-1]),rows[-1]]))
    assert [[r['ordinal'] for r in b] for _,b in groups(target)[2]]==[[r['ordinal'] for r in b] for _,b in batches]
    changed=copy.deepcopy(rows);accepted=[r for r in changed if r.get('status')=='captured'];accepted[0]['target'][2]+=1
    target.write_text(''.join(json.dumps(r)+'\n' for r in changed))
    assert len(groups(target)[2])==5
    target.write_text(json.dumps({'kind':'header','schema':'rrt-position-capture','version':1})+'\n')
    try:groups(target)
    except ValueError:pass
    else:raise AssertionError('legacy/partial group input admitted')
print('PASS real four-group replay, disjoint union, independent model constants, overwrite order,16-draw bound, malformed input and grouping isolation')
