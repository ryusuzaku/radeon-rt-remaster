"""CPU inspection contract using a generated, proxy-inventoried program."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_shader_inventory import inspect
from disassemble_inventory import disassemble
p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--proxy',type=Path,required=True);p.add_argument('--disassembler',type=Path,required=True);a=p.parse_args()
root=Path(tempfile.mkdtemp(prefix='shader-disassembly-',dir=a.fixture.parent));out=root/'fixture';out.mkdir();ledger=root/'inventory.jsonl'
env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
env.update(RRT_FIXTURE_PROXY=str(a.proxy),RRT_SHADER_INVENTORY_FILE=str(ledger),RRT_SHADER_INVENTORY_DRAWS='1')
r=subprocess.run([str(a.fixture),'--fixture',str(out)],env=env,capture_output=True,text=True,timeout=30)
assert r.returncode==0,(r.stdout,r.stderr)
report=inspect(ledger)
for program in report['programs']:
    listing=disassemble(ledger,a.disassembler,program['sha256'],program['stage'])
    assert program['stage']+'_3_0' in listing and len(listing)<1024*1024
for bad in ('', 'xx'*8, '00'*4, '00'*16385, '0002feff00000000', '0002feffffff0000\nextra'):
    r=subprocess.run([str(a.disassembler)],input=bad+'\n',capture_output=True,text=True,timeout=15)
    assert r.returncode!=0,(bad[:32],r.stdout)
try: disassemble(ledger,a.disassembler,'0'*64)
except ValueError: pass
else: raise AssertionError('unknown hash admitted')
print(f'PASS bounded CPU disassembly and invalid input/hash rejection: {root}')
