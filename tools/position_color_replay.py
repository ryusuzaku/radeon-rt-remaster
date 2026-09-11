"""Exact constant-RGBA color replay admission, separate from position diagnostics."""
import struct
import math
from position_surface_scope import assess_scope
from position_write_evidence import assess_writes

PROGRAM=struct.pack('<5I',0xffff0200,0x02000001,0x800f0800,0xa0e40000,0xffff).hex()
EXTRA=[0,1,0,0,0xffffffff,0] # fog, clipping, clip planes, dither, sample mask, line AA
FIXED={'z_enable':0,'z_write':0,'alpha_test':0,'separate_alpha':0,'stencil_enable':0,
       'srgb_write':0,'depth_bias':0,'slope_depth_bias':0,'fill':3,'cull':1,
       'scissor_enable':0,'color_write':15}

def validate(row):
    def need(ok,message):
        if not ok:raise ValueError('color replay: '+message)
    c=row.get('color_replay');need(type(c) is dict and set(c)=={'pixel_shader','rgba','extra_states','npatch_mode'},'shape')
    need(type(c['npatch_mode']) is int and 0<=c['npatch_mode']<2**32,'npatch mode')
    for key,low,high in [('pixel_shader',16,8192),('rgba',32,32)]:
        value=c[key];need(type(value) is str and low<=len(value)<=high and len(value)%8==0 and all(x in '0123456789abcdef' for x in value),'blob '+key)
    states=c['extra_states'];need(type(states) is list and len(states)==6 and all(type(x) is int and 0<=x<2**32 for x in states),'extra states')

def assess_color(row):
    result={'supported_draw':False,'ready_for_stateful_replay':False,'reasons':[]}
    reasons=result['reasons'];c=row.get('color_replay')
    if c is None:reasons.append('color_evidence_unavailable');return result
    if not assess_scope(row)['qualified']:reasons.append('color_scope_unqualified')
    if c['pixel_shader']!=PROGRAM:reasons.append('pixel_shader_unsupported')
    rgba=struct.unpack('<4f',bytes.fromhex(c['rgba']))
    if not all(math.isfinite(v) and 0<=v<=1 for v in rgba):reasons.append('color_constant_unsupported')
    s=row['render_state']['states']
    if any(s[k]!=v for k,v in FIXED.items()) or c['extra_states']!=EXTRA or c['npatch_mode']!=0:reasons.append('raster_state_unsupported')
    if s['blend_enable'] not in (0,1) or (s['blend_enable'] and (s['blend_op']!=1 or s['src_blend'] not in (1,2,5,6) or s['dst_blend'] not in (1,2,5,6))):reasons.append('blend_state_unsupported')
    if row['target']!=[128,96,116,0] or struct.unpack('<4I2f',bytes.fromhex(row['viewport']))!=(0,0,128,96,0,1):reasons.append('extent_or_viewport_unsupported')
    result['supported_draw']=not reasons
    if not reasons:reasons.append('complete_prefix_required')
    return result

def prefix(rows, endpoint):
    """Resolve every required previous draw, never silently replay a sampled suffix."""
    by_ordinal={r['ordinal']:r for r in rows}
    expected=assess_writes(endpoint).get('intervening_captured_ordinals',[])+[endpoint['ordinal']]
    if len(expected)>16 or any(o not in by_ordinal for o in expected):raise ValueError('color replay prefix missing')
    selected=[by_ordinal[o] for o in expected]
    for index,row in enumerate(selected):
        if not assess_color(row)['supported_draw']:raise ValueError('unsupported color draw in prefix')
        if assess_writes(row).get('intervening_captured_ordinals',[])!=expected[:index]:raise ValueError('inconsistent color prefix')
        if (row['device'],row['timing']['reset_epoch'],row['render_state']['last_clear'])!=(endpoint['device'],endpoint['timing']['reset_epoch'],endpoint['render_state']['last_clear']):raise ValueError('mixed color segment')
    return selected

def payload(rows):
    selected=prefix(rows,rows[-1])
    if selected!=rows:raise ValueError('color prefix order')
    lines=['RRT_POSITION_COLOR1',str(len(rows)),rows[0]['shader'],str(rows[0]['render_state']['last_clear']['color'])]
    for r in rows:
        s=r['render_state']['states'];c=r['color_replay']
        lines.extend([r['constants'],r['positions'],c['rgba'],str(s['blend_enable']),str(s['src_blend'] if s['blend_enable'] else 2),str(s['dst_blend'] if s['blend_enable'] else 1)])
    return '\n'.join(lines)+'\n'
