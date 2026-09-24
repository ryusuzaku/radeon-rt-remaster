"""Bounded offline audit of one exact saved HL2 VS/PS pair; no GPU execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from inspect_shader_inventory import inspect

VS='0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2'
PS='ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11'

def audit(path,disassembler):
    with Path(path).open('rb') as f:data=f.read(16*1024*1024+1)
    if len(data)>16*1024*1024:raise ValueError('inventory budget')
    # Validate the same immutable bytes used below, not a subsequently reopened source.
    with tempfile.TemporaryDirectory(prefix='hl2-material-audit-') as temp:
        snapshot=Path(temp)/'inventory.jsonl';snapshot.write_bytes(data);summary=inspect(snapshot)
    rows=[json.loads(line) for line in data.splitlines()]
    programs={};matched=[]
    for row in rows:
        if row.get('kind')!='draw' or row.get('query')!='ok' or row['hr']<0:continue
        hashes={stage:hashlib.sha256(bytes.fromhex(row[stage])).hexdigest() if row[stage] else None for stage in ('vs','ps')}
        if hashes=={'vs':VS,'ps':PS}:
            matched.append(row['ordinal']);programs={stage:row[stage] for stage in ('vs','ps')}
    if not matched:raise ValueError('exact successful material pair absent')
    assembly={};analysis={}
    for stage,code in programs.items():
        native=subprocess.run([str(disassembler)],input=code+'\n',text=True,capture_output=True,timeout=15)
        if native.returncode or len(native.stdout)>1024*1024:raise ValueError('disassembly failed or exceeded bound')
        assembly[stage]=native.stdout
        lines=[line.strip() for line in native.stdout.splitlines() if line.strip() and not line.lstrip().startswith('//')]
        body='\n'.join(lines)
        defined={int(m.group(1)) for m in re.finditer(r'^def c(\d+),',body,re.M)}
        constants={int(x) for x in re.findall(r'\bc(\d+)\b',body)}
        analysis[stage]={'sha256':VS if stage=='vs' else PS,'bytes':len(code)//2,
            'profile':lines[0],'embedded_constants':sorted(defined),'external_constant_rows':sorted(constants-defined),
            'samplers':sorted(set(re.findall(r'\bs\d+\b',body))),
            'declared_inputs':[line for line in lines if line.startswith('dcl')],
            'texture_instructions':[line for line in lines if line.startswith('texld')],
            'instruction_lines':len(lines)-1,
            'disassembly_sha256':hashlib.sha256(native.stdout.encode()).hexdigest()}
    if analysis['ps']['external_constant_rows']!=[11,12,29,30] or analysis['vs']['external_constant_rows']!=[0,4,5,6,7,12,16,58,59,60] or len(analysis['ps']['texture_instructions'])!=5:
        raise ValueError('exact-program dependency audit changed')
    return {'schema':'rrt-hl2-material-audit','version':1,'source_sha256':hashlib.sha256(data).hexdigest(),
        'inventory_completion':summary['completion'],'inventory_draws':summary['draws'],
        'paired_successful_draws':len(matched),'paired_ordinals':matched,
        'families':[f for f in summary['families'] if f['vs']==VS and f['ps']==PS],
        'programs':analysis,'replay_ready':False,
        'scope':'exact static dependencies; no bound textures/constants/texels or draw correlation inferred'},assembly

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inventory',type=Path);p.add_argument('--disassembler',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        result,assembly=audit(a.inventory,a.disassembler)
        a.out.mkdir(parents=True,exist_ok=False)
        (a.out/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        for stage,text in assembly.items():(a.out/(stage+'.asm')).write_text(text,encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('paired_ordinals','families')},indent=2))
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as e:p.exit(2,f'material audit rejected: {e}\n')
