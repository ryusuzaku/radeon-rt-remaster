"""Isolated original-versus-reconstructed pixel comparison, not frame replay."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from inspect_position_capture import inspect_bytes,need
from position_color_replay import FIXED,EXTRA
from texture_assets import TextureAssets
import copy

MAX_PIXELS=8_000_000

def diagnostic_scope(row):
    width,height=row['target'][:2]
    x,y,w,h,lo,hi=struct.unpack('<4I2f',bytes.fromhex(row['viewport']))
    need(0<width<=8192 and 0<height<=8192 and width*height<=MAX_PIXELS,'pixel target budget')
    need(w>0 and h>0 and x+w<=width and y+h<=height and math.isfinite(lo) and math.isfinite(hi) and 0<=lo<=hi<=1,'pixel viewport bounds')
    return {'mode':'normalized_material','captured_target':row['target'],
            'comparison_target':[width,height,116,0],'viewport':[x,y,w,h,lo,hi],
            'captured_render_state':row['render_state'],
            'captured_extra_states':row['color_replay']['extra_states'],
            'captured_npatch_mode':row['color_replay']['npatch_mode'],
            'comparison_states':dict(FIXED,blend_enable=0),'comparison_extra_states':EXTRA,
            'comparison_npatch_mode':0,'depth_attachment':False,'clear_color':0,
            'composition_preserved':False,'texture_sampler_state_preserved':True}

def payload(row,normalized=False):
    if not normalized:need(row['target']==[128,96,116,0] and struct.unpack('<4I2f',bytes.fromhex(row['viewport']))==(0,0,128,96,0,1),'pixel replay extent')
    state=row['render_state']['states'];color=row['color_replay']
    if not normalized:need(all(state[k]==v for k,v in FIXED.items()) and state['blend_enable']==0 and color['extra_states']==EXTRA and color['npatch_mode']==0,'pixel replay raster subset')
    material=row['material_inputs']
    positions=bytes.fromhex(row['positions']);colors=bytes.fromhex(material['color']);uvs=bytes.fromhex(material['uv'])
    vertices=b''.join(positions[i*12:i*12+12]+b'\0'*12+colors[i*4:i*4+4]+uvs[i*16:i*16+16]+b'\0'*4 for i in range(row['primitives']*3))
    header=['RRT_PIXEL_REPLAY1']
    if normalized:
        diagnostic_scope(row)
        header=['RRT_PIXEL_REPLAY2',*map(str,row['target'][:2]),*map(str,struct.unpack('<6I',bytes.fromhex(row['viewport'])))]
    lines=[*header,row['shader'],color['pixel_shader'],row['constants'],material['constants'],row['pixel_material']['constants'],vertices.hex()]
    for sampler,snapshot in zip(row['pixel_material']['samplers'],row['texture_inputs']):
        t=sampler['texture'];s=sampler['states'];bias=struct.unpack('<f',struct.pack('<I',s[7]))[0]
        need(t['lod']<t['levels'] and all(1<=v<=4 for v in s[:3]) and s[4] in (1,2) and s[5] in (1,2) and s[6] in (0,1,2) and math.isfinite(bias) and abs(bias)<=4 and s[8]<t['levels'] and s[9]==1 and s[10] in (0,1) and s[11:]==[0,0],'pixel replay sampler subset')
        lines.extend(map(str,[*t['descriptors'][0][:3],t['levels'],t['lod'],*s]))
        lines.extend(m['bytes'] for m in snapshot['mips'])
    return '\n'.join(lines)+'\n'

def probe(row,fixture,control=None,normalized=False):
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
    if control is not None:
        need(control in ('fog','alpha','address','srgb','lod','filter','texel','one_sample'),'pixel replay control')
        env['RRT_PIXEL_REPLAY_CONTROL']=control
    result=subprocess.run([str(fixture),'--pixel-replay'],input=payload(row,normalized),text=True,capture_output=True,env=env,timeout=60)
    need(result.returncode==0,'native pixel comparison exit '+str(result.returncode)+': '+result.stderr[:1000])
    output=json.loads(result.stdout)
    need(output.get('status') in ('matched','different') and math.isfinite(output['max_normalized_error']),'pixel comparison result')
    if normalized:output['diagnostic_scope']=diagnostic_scope(row)
    return output

def replay(path,fixture,ordinal=None,normalized=False):
    with Path(path).open('rb') as stream:data=stream.read(16*1024*1024+1)
    assets=TextureAssets(path);capture=inspect_bytes(data,include_records=True,assets=assets)
    need(capture['version'] in (13,14,15,16,17,18,19) and capture['completion'] in ('capture_limit','attempt_limit','byte_limit','present_limit'),'completed v13-v19 capture required')
    rows=[r for r in capture['records'] if ordinal is None or r['ordinal']==ordinal];need(rows,'no selected material draw')
    draws=[]
    for row in rows:
        if capture['version']>=14:
            row=copy.deepcopy(row)
            for texture in row['texture_inputs']:
                for mip in texture['mips']:mip['bytes']=assets.read(mip['sha256'],mip['size']).hex()
        try:result=probe(row,fixture,normalized=normalized)
        except ValueError as e:result={'status':'unqualified','reason':str(e)}
        draws.append(dict(result,ordinal=row['ordinal']))
    return {'schema':'rrt-pixel-material-comparison','version':1,'source_sha256':hashlib.sha256(data).hexdigest(),'scope':'isolated_draw','ready_for_frame_replay':False,'draws':draws}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--ordinal',type=int);p.add_argument('--normalized-material',action='store_true',help='preserve extent/viewport, compare with explicitly normalized raster state');a=p.parse_args()
    try:
        result=replay(a.capture,a.fixture,a.ordinal,a.normalized_material);print(json.dumps(result,indent=2))
        return 0 if all(d['status']=='matched' for d in result['draws']) else 1
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:print(str(e));return 1
if __name__=='__main__':raise SystemExit(main())
