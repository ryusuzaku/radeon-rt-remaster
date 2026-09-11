"""Run one independent native texture qualification matrix from pinned inventory."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_shader_inventory import inspect
from inspect_position_capture import DIGEST
from position_pixel_material import DIGEST as PIXEL_DIGEST

p=argparse.ArgumentParser(description=__doc__)
for name in ('fixture','proxy','inventory'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--kind',choices=('compressed','upload','dirty','surface','locks','scope','selection'),required=True)
a=p.parse_args();inspect(a.inventory);code=pixel=None
with a.inventory.open(encoding='utf-8') as stream:
    for line in stream:
        row=json.loads(line);vs=row.get('vs');ps=row.get('ps')
        if (isinstance(vs,str) and isinstance(ps,str) and hashlib.sha256(bytes.fromhex(vs)).hexdigest()==DIGEST
                and hashlib.sha256(bytes.fromhex(ps)).hexdigest()==PIXEL_DIGEST):
            code,pixel=vs,ps;break
assert code and pixel,'paired pinned shaders missing'
root=Path(tempfile.mkdtemp(prefix='texture-'+a.kind+'-',dir=a.fixture.resolve().parent))
clean={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
suffixes=('FRAME_SAMPLING','MULTI_DRAW','RENDER_STATE','CLEAR_EVIDENCE','WRITE_EVIDENCE','SURFACE_SCOPE',
          'COLOR_REPLAY','MATERIAL_INPUTS','PIXEL_MATERIAL','TEXTURE_INPUTS','TEXTURE_ASSETS')
flags={'RRT_POSITION_'+s:'1' for s in suffixes};flags['RRT_POSITION_SELECTION']='128x96:1'
module={'compressed':'qualify_compressed_capture','upload':'qualify_texture_upload',
        'dirty':'qualify_dirty_texture','surface':'qualify_surface_upload','locks':'qualify_surface_locks','scope':'qualify_pixel_scope','selection':'qualify_selection_capture'}[a.kind]
importlib.import_module(module).qualify(a.fixture.resolve(),a.proxy.resolve(),root,clean,flags,code,pixel)
print('PASS '+a.kind+': '+str(root))

