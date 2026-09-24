"""Validate bounded position evidence and independently recompute its outputs."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import struct
from position_write_evidence import validate as validate_writes
from position_surface_scope import validate as validate_scope
from position_color_replay import validate as validate_color
from position_material_inputs import validate as validate_material
from position_pixel_material import validate as validate_pixel_material
from position_texture_inputs import validate as validate_texture_inputs
from texture_assets import TextureAssets
from position_texture_diagnostic import validate as validate_texture_diagnostic

DIGEST='0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2'
COMPOSITION_STATES=set('z_enable z_write z_func alpha_test alpha_ref alpha_func blend_enable src_blend dst_blend blend_op separate_alpha src_blend_alpha dst_blend_alpha blend_op_alpha blend_factor color_write cull fill scissor_enable stencil_enable srgb_write depth_bias slope_depth_bias'.split())
def need(ok,message):
    if not ok: raise ValueError(message)
def inspect(path,include_records=False):
    with Path(path).open('rb') as stream:
        data=stream.read(16*1024*1024+1)
    return inspect_bytes(data,include_records,TextureAssets(path))

def inspect_bytes(data,include_records=False,assets=None):
    """Validate one immutable bounded snapshot (also used for digest-bound imports)."""
    need(type(data) is bytes and len(data)<=16*1024*1024,'file budget')
    policy=None;shader_policy=None;failure_stages=Counter()
    header=False;version=0;session=None;selection=None;footer=None;seen=set();captured=[];reasons=Counter();records=[];intervals=Counter();draw_keys=set();total_limit=4;interval_limit=1
    observed_targets=Counter();texture_diagnostics=Counter()
    write_events={};write_captures={};write_through=0;write_gaps={'observer_gap':False,'overlap':False}
    scope_origins={};scope_caps={};scope_access_gap=False
    def blob(record,key,size):
        value=record.get(key);need(isinstance(value,str) and len(value)==size*2,'blob length: '+key)
        data=bytes.fromhex(value);need(len(data)==size,'blob bytes: '+key);return data
    with io.BytesIO(data) as stream:
        for _ in range(4099):
            line=stream.readline(1200001)
            if not line: break
            need(len(line)<=1200000 and line.endswith(b'\n'),'record bound/truncation')
            row=json.loads(line);need(isinstance(row,dict) and footer is None,'record ordering')
            if not header:
                version=row.get('version');need(type(version) is int and version in (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19),'header version')
                expected={'kind':'header','schema':'rrt-position-capture','version':version}
                if version>=3:
                    session=row.get('session');need(isinstance(session,str) and len(session)==32 and all(c in '0123456789abcdef' for c in session),'session identity')
                    expected.update(session=session,sampling='bounded-per-present-interval' if version>=5 else 'one-per-present-interval')
                if version>=5:
                    limits=row.get('limits');need(type(limits) is dict and set(limits)=={'per_interval','total'} and type(limits['per_interval']) is int and type(limits['total']) is int and limits=={'per_interval':4,'total':16},'sampling limits')
                    expected['limits']=limits;total_limit=16;interval_limit=4
                if version>=4:
                    selection=row.get('selection')
                    need(isinstance(selection,dict),'selection policy')
                    if set(selection)=={'any_target','min_primitives'}:
                        need(selection['any_target'] is True and type(selection['min_primitives']) is int and 1<=selection['min_primitives']<=4096,'selection bounds')
                    else:
                        need(set(selection)=={'target_width','target_height','min_primitives'},'selection policy')
                        need(all(type(v) is int and 1<=v<=(4096 if k=='min_primitives' else 16384) for k,v in selection.items()),'selection bounds')
                    expected['selection']=selection
                if 'selection_rejections' in row:
                    policy=row['selection_rejections']
                    need(version in (18,19) and policy=='first4-per-target-reason-up-to64-keys-plus-every64th-attempt','selection rejection sampling')
                    expected['selection_rejections']=policy
                if 'shader_rejections' in row:
                    shader_policy=row['shader_rejections']
                    need(version in (18,19) and shader_policy=='first4-per-target-reason-up-to64-keys-plus-every64th-attempt','shader rejection sampling')
                    expected['shader_rejections']=shader_policy
                need(row==expected,'header');header=True;continue
            if row.get('kind')=='end':
                need(row.get('reason') in (('capture_limit','attempt_limit','byte_limit','io_error','present_limit') if version>=3 else ('capture_limit','attempt_limit','byte_limit','io_error')),'footer reason')
                need(type(row.get('attempts')) is int and len(seen)<=row['attempts']<=4096,'attempt count')
                need(row.get('captured')==len(captured),'capture count')
                if row['reason']=='capture_limit':need(len(captured)==total_limit,'early capture stop')
                if row['reason']=='attempt_limit':need(row['attempts']==4096,'early attempt stop')
                if version>=3:
                    need(type(row.get('presents')) is int and 0<=row['presents']<=120,'present count')
                    if row['reason']=='present_limit':need(row['presents']==120,'early present stop')
                # Optional shadow-budget attribution: the shared ceiling split by resource kind.
                attributed=('retained','retained_buffers','retained_textures','live_textures',
                            'retained_peak','peak_buffers','peak_textures')
                for name in attributed:
                    if name in row:need(type(row[name]) is int and 0<=row[name]<2**40,'footer budget attribution')
                if 'retained' in row:
                    need(type(row.get('retained_buffers')) is int and type(row.get('retained_textures')) is int,'footer budget split')
                    need(row['retained']==row['retained_buffers']+row['retained_textures'],'footer budget attribution total')
                if 'retained_peak' in row:
                    need(type(row.get('peak_buffers')) is int and type(row.get('peak_textures')) is int,'footer peak split')
                    need(row['retained_peak']==row['peak_buffers']+row['peak_textures'],'footer peak total')
                    need(row['retained_peak']>=row.get('retained',0),'footer peak below stop value')
                footer=row;continue
            ordinal=row.get('ordinal');hr=row.get('hr')
            need(row.get('kind')=='draw' and type(ordinal) is int and 0<=ordinal<4096 and ordinal not in seen,'draw ordinal');seen.add(ordinal)
            need(type(hr) is int and -(2**31)<=hr<2**31,'HRESULT')
            timing=row.get('timing')
            if version>=3:
                need(type(row.get('device')) is int and 0<row['device']<2**64,'device identity')
                need(isinstance(timing,dict) and set(timing)=={'reset_epoch','present_interval','indexed_draw'} and all(type(v) is int and 0<=v<2**64 for v in timing.values()),'draw timing')
            else:need('timing' not in row,'legacy capture cannot claim timing')
            if version>=8:
                validate_writes(row,write_events,write_captures)
                need(row['write_evidence']['through']>write_through,'write history snapshot order')
                write_through=row['write_evidence']['through']
                for key,was_set in write_gaps.items():
                    need(not was_set or row['write_evidence'][key],'write gap cannot disappear')
                    write_gaps[key]=row['write_evidence'][key]
            else:need('write_evidence' not in row,'legacy capture cannot claim ordered writes')
            if version<9:need('surface_scope' not in row,'legacy capture cannot claim surface scope')
            if version<10:need('color_replay' not in row,'legacy capture cannot claim color replay')
            if version<11:need('material_inputs' not in row,'legacy capture cannot claim material inputs')
            if version<12:need('pixel_material' not in row,'legacy capture cannot claim pixel material')
            if version<13:need('texture_inputs' not in row,'legacy capture cannot claim texture inputs')
            if 'evidence_failure' in row:
                failure=row['evidence_failure']
                need(version in (18,19) and row.get('status')=='rejected' and hr>=0 and type(failure) is dict and set(failure)=={'stage','detail'},'evidence failure shape')
                need(failure['stage'] in ('topology','device_state','selection','buffer_binding','buffer_tracking','position_material','composition','surface_scope','color_evidence','pixel_material','texture_inputs'),'evidence failure stage')
                detail=failure['detail'];need(type(detail) is str and 0<len(detail)<=96 and all('a'<=c<='z' or c in '_ ' for c in detail),'evidence failure detail')
                failure_stages[(failure['stage'],detail)]+=1
            if 'texture_diagnostic' in row:
                validate_texture_diagnostic(row,version)
                texture_diagnostics[json.dumps(row['texture_diagnostic'],sort_keys=True)]+=1
            if 'selection_observed' in row:
                observed=row['selection_observed']
                need(version>=4 and row.get('status')=='rejected' and type(observed) is dict and set(observed)=={'target','primitives'},'selection observation shape')
                t=observed['target'];n=observed['primitives']
                need(type(t) is list and len(t)==4 and all(type(v) is int and 0<=v<2**32 for v in t) and t[0]>0 and t[1]>0,'selection observation target')
                need(type(n) is int and 0<=n<2**32,'selection observation primitives')
                if row.get('reason')=='selection_target_mismatch':need('any_target' not in selection and t[:2]!=[selection['target_width'],selection['target_height']],'selection mismatch observation')
                if row.get('reason')=='selection_primitive_minimum':need(n<selection['min_primitives'] and ('any_target' in selection or t[:2]==[selection['target_width'],selection['target_height']]),'selection minimum observation')
                observed_targets[tuple(t)]+=1
            if row.get('status')=='rejected':
                reason=row.get('reason');need(isinstance(reason,str) and 0<len(reason)<=128,'rejection reason');reasons[reason]+=1;continue
            need(row.get('status')=='captured' and hr>=0 and row.get('reason')=='' and len(captured)<total_limit,'capture status')
            composition=row.get('render_state')
            if version>=6:
                composition_keys={'target_id','depth_id','depth_desc','clear_serial','binding_serial','states','scissor'}
                if version>=7:composition_keys.add('last_clear')
                need(isinstance(composition,dict) and set(composition)==composition_keys,'composition metadata')
                need(all(type(composition[k]) is int and 0<=composition[k]<2**64 for k in ('target_id','depth_id','clear_serial','binding_serial')) and composition['target_id']>0,'surface identity/serial')
                desc=composition['depth_desc']
                need((composition['depth_id']==0 and desc is None) or (composition['depth_id']>0 and isinstance(desc,list) and len(desc)==4 and all(type(v) is int and 0<=v<2**32 for v in desc)),'depth descriptor')
                need(composition['depth_id']!=composition['target_id'],'surface identity collision')
                states=composition['states'];need(isinstance(states,dict) and set(states)==COMPOSITION_STATES and all(type(v) is int and 0<=v<2**32 for v in states.values()),'render states')
                rect=composition['scissor'];need(isinstance(rect,list) and len(rect)==4 and all(type(v) is int and -(2**31)<=v<2**31 for v in rect),'scissor rectangle')
                if version>=7 and composition['last_clear'] is not None:
                    clear=composition['last_clear'];keys={'serial','reset_epoch','target_id','depth_id','target_desc','viewport','scissor_enable','flags','color','depth_bits','stencil','rects'}
                    need(isinstance(clear,dict) and set(clear)==keys,'clear metadata')
                    need(all(type(clear[k]) is int and 0<=clear[k]<2**64 for k in ('serial','reset_epoch','target_id','depth_id')) and clear['serial']>0 and clear['target_id']>0,'clear identity')
                    need(clear['serial']==composition['clear_serial'],'clear serial mismatch')
                    need(clear['reset_epoch']<=timing['reset_epoch'],'future clear epoch')
                    need(all(type(clear[k]) is int and 0<=clear[k]<2**32 for k in ('scissor_enable','flags','color','depth_bits','stencil')),'clear arguments')
                    desc=clear['target_desc'];need(isinstance(desc,list) and len(desc)==4 and all(type(v) is int and 0<=v<2**32 for v in desc),'clear target descriptor')
                    vp=struct.unpack('<4I2f',blob(clear,'viewport',24));need(all(map(math.isfinite,vp[4:])),'clear viewport')
                    rects=clear['rects'];need(isinstance(rects,list) and len(rects)<=16 and all(isinstance(r,list) and len(r)==4 and all(type(v) is int and -(2**31)<=v<2**31 for v in r) for r in rects),'clear rectangles')
            else:need('render_state' not in row,'legacy capture cannot claim composition metadata')
            if version>=9:
                validate_scope(row)
                for snapshot in row['surface_scope'].values():
                    if snapshot is None:continue
                    identity=snapshot['attachments'][0];origin=snapshot['origin']
                    need(identity not in scope_origins or scope_origins[identity]==origin,'surface creation origin changed')
                    scope_origins[identity]=origin
                    need(row['device'] not in scope_caps or scope_caps[row['device']]==len(snapshot['attachments']),'surface MRT capability changed')
                    scope_caps[row['device']]=len(snapshot['attachments'])
                gap=row['surface_scope']['draw']['access_gap']
                need(not scope_access_gap or gap,'surface access gap cannot disappear');scope_access_gap=gap
            if version>=10:validate_color(row)
            provenance=row.get('provenance')
            if version==1:need('provenance' not in row,'v1 cannot claim resource provenance')
            if version>=2:
                keys={'vb_id','vb_revision','ib_id','ib_revision','reset_epoch','knowledge_revision'}
                need(type(row.get('device')) is int and 0<row['device']<2**64,'device identity')
                need(isinstance(provenance,dict) and set(provenance)==keys and all(type(v) is int and 0<=v<2**64 for v in provenance.values()),'provenance')
                need(all(provenance[k]>0 for k in ('vb_id','ib_id','vb_revision','ib_revision')) and provenance['vb_id']!=provenance['ib_id'],'resource identity/revision')
            if version>=3:
                need(timing['reset_epoch']==provenance['reset_epoch'],'timing/provenance epoch mismatch')
                interval=(row['device'],timing['reset_epoch'],timing['present_interval'])
                need(intervals[interval]<interval_limit,'accepted interval quota exceeded');intervals[interval]+=1
                draw_key=(*interval,timing['indexed_draw']);need(draw_key not in draw_keys,'duplicate accepted draw timing');draw_keys.add(draw_key)
            need(hashlib.sha256(blob(row,'shader',612)).hexdigest()==DIGEST,'program identity')
            for key in ('offset','stride','minimum','vertices','start','primitives','vb_size','ib_size'):
                need(type(row.get(key)) is int and 0<=row[key]<2**32,'integer: '+key)
            need(type(row.get('base')) is int and -(2**31)<=row['base']<2**31,'base')
            need(1<=row['primitives']<=4096 and 1<=row['vertices']<=65536 and 12<=row['stride']<=256,'draw budget')
            need(row['vb_size']<=16*1024*1024 and row['ib_size']<=16*1024*1024,'buffer budget')
            declaration=row.get('declaration');need(isinstance(declaration,str) and 16<=len(declaration)<=1040 and len(declaration)%16==0,'declaration')
            elements=list(struct.iter_unpack('<HHBBBB',bytes.fromhex(declaration)))
            need(elements[-1]==(255,0,17,0,0,0),'declaration terminator')
            need([e for e in elements[:-1] if e[4:]==(0,0)]==[(0,0,2,0,0,0)],'position declaration')
            constants=struct.unpack('<32f',blob(row,'constants',128));need(all(map(math.isfinite,constants)),'nonfinite constants')
            viewport=struct.unpack('<4I2f',blob(row,'viewport',24));need(all(map(math.isfinite,viewport[4:])),'nonfinite viewport')
            target=row.get('target');need(isinstance(target,list) and len(target)==4 and all(type(v) is int and 0<=v<2**32 for v in target),'target metadata')
            if selection is not None:
                need('any_target' in selection or target[:2]==[selection['target_width'],selection['target_height']],'capture violates selection')
                need(row['primitives']>=selection['min_primitives'],'capture violates selection')
            corners=row['primitives']*3
            need(row['start']*2+corners*2<=row['ib_size'],'index buffer range')
            indices=struct.unpack('<'+'H'*corners,blob(row,'indices',corners*2))
            positions=list(struct.iter_unpack('<3f',blob(row,'positions',corners*12)))
            outputs=list(struct.iter_unpack('<8f',blob(row,'evaluated',corners*32)))
            for index,p,result in zip(indices,positions,outputs):
                need(row['minimum']<=index<row['minimum']+row['vertices'],'declared index range')
                vertex=index+row['base'];need(vertex>=0 and row['offset']+vertex*row['stride']+12<=row['vb_size'],'vertex buffer range')
                need(all(map(math.isfinite,(*p,*result))),'nonfinite vertex/output')
                a,b=constants[:2];q=[p[0]*b+a,p[1]*b+a,p[2]*b+a,p[0]*a+b]
                calculated=[sum(q[j]*constants[i*4+j] for j in range(4)) for i in range(1,8)]+[1.0]
                need(all(abs(x-y)/(1+abs(y))<=2e-4 for x,y in zip(result,calculated)),'position calculation mismatch')
            if version>=11:validate_material(row)
            if version>=12:validate_pixel_material(row)
            if version>=13:validate_texture_inputs(row,assets,version>=14,version>=15,version>=16,version>=17,version>=18)
            captured.append({'ordinal':ordinal,'corners':corners,'unique_indices':len(set(indices)),'stride':row['stride'],'vb_size':row['vb_size'],'ib_size':row['ib_size']})
            if include_records:records.append(row)
        else:raise ValueError('record count')
    need(header,'missing header')
    result={'completion':footer['reason'] if footer else 'partial','version':version,'resource_provenance':version>=2,'session':session,'selection':selection,'limits':{'per_interval':interval_limit if version>=3 else None,'total':total_limit},'frame_sampling':version>=3,'attempts_recorded':len(seen),'captures':captured,'rejections':dict(reasons)}
    if footer and 'retained' in footer:
        result['retained']={name:footer[name] for name in ('retained','retained_buffers','retained_textures','live_textures')}
        if 'retained_peak' in footer:
            result['retained'].update({name:footer[name] for name in ('retained_peak','peak_buffers','peak_textures')})
    need(policy is None or version in (18,19),'selection sampling version')
    result['texture_diagnostics']=[dict(json.loads(t),recorded_rejections=n) for t,n in sorted(texture_diagnostics.items())]
    result['shader_rejection_sampling']=shader_policy
    result['evidence_failures']=[{'stage':stage,'detail':detail,'recorded_rejections':n} for (stage,detail),n in sorted(failure_stages.items())]
    result['selection_rejection_sampling']=policy
    result['attempts_total']=footer['attempts'] if footer else None
    result['observed_rejection_targets']=[{'target':list(t),'recorded_rejections':n} for t,n in sorted(observed_targets.items())]
    if include_records:result['records']=records
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);a=p.parse_args()
    try:print(json.dumps(inspect(a.capture),indent=2))
    except (OSError,ValueError,TypeError,KeyError) as e:p.exit(2,f'position capture rejected: {e}\n')
