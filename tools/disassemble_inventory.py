"""Validate inventory and disassemble one exact hash in a bounded CPU subprocess."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from inspect_shader_inventory import inspect

def disassemble(inventory, executable, digest, stage='vs'):
    report=inspect(inventory)
    if stage not in ('vs','ps') or not any(p['sha256']==digest and p['stage']==stage for p in report['programs']):
        raise ValueError('program hash/stage not present in validated inventory')
    with Path(inventory).open(encoding='utf-8') as stream:
        total=0
        for _ in range(4098):
            line=stream.readline(70001)
            if not line: break
            total+=len(line)
            if len(line)>70000 or not line.endswith('\n') or total>16*1024*1024:
                raise ValueError('inventory changed or exceeded bounds after validation')
            record=json.loads(line);code=record.get(stage)
            if record.get('kind')!='draw' or record.get('query')!='ok' or code is None:
                continue
            if not isinstance(code,str) or len(code)>32768:
                raise ValueError('shader changed or exceeded bounds after validation')
            if hashlib.sha256(bytes.fromhex(code)).hexdigest()!=digest:
                continue
            result=subprocess.run([str(executable)],input=code+'\n',capture_output=True,text=True,timeout=15)
            if result.returncode:
                raise ValueError(f'disassembler rejected program: {result.stderr[:1000]}')
            return result.stdout
    raise ValueError('program disappeared after validation')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inventory',type=Path);p.add_argument('--disassembler',type=Path,required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--stage',choices=('vs','ps'),default='vs')
    a=p.parse_args()
    try: print(disassemble(a.inventory,a.disassembler,a.sha256,a.stage),end='')
    except (OSError,ValueError,subprocess.TimeoutExpired) as error: p.exit(2,f'{error}\n')
