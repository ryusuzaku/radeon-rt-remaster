"""v9 closed standalone RT0 color-call qualification; no stateful replay claim."""
from position_write_evidence import assess_writes
import struct


def validate(row):
    def need(ok, message):
        if not ok: raise ValueError('surface scope: '+message)
    def uint(x): return type(x) is int and 0<=x<2**64
    scope=row.get('surface_scope')
    need(type(scope) is dict and set(scope)=={'draw','clear'},'shape')
    for name in ('draw','clear'):
        s=scope[name]
        if name=='clear' and s is None:
            need(row['render_state']['last_clear'] is None,'missing clear scope');continue
        need(type(s) is dict and set(s)=={'attachments','depth_id','open_accesses','access_gap','origin'},'snapshot')
        a=s['attachments'];need(type(a) is list and 1<=len(a)<=4 and all(uint(x) for x in a) and a[0]>0,'MRT slots')
        need(uint(s['depth_id']) and type(s['open_accesses']) is int and 0<=s['open_accesses']<=64 and type(s['access_gap']) is bool,'access bounds')
        o=s['origin'];need(type(o) is dict and set(o)=={'observed','private','lockable','device','reset_epoch'},'origin')
        need(all(type(o[k]) is bool for k in ('observed','private','lockable')) and uint(o['device']) and uint(o['reset_epoch']),'origin types')
        need((o['observed'] and o['device']>0) or (not o['observed'] and not o['private'] and not o['lockable'] and o['device']==o['reset_epoch']==0),'origin consistency')
        target=row['render_state'] if name=='draw' else row['render_state']['last_clear']
        need(type(target) is dict and a[0]==target['target_id'] and s['depth_id']==target['depth_id'],'attachment identity')


def assess_scope(row):
    result={'scope':'private_standalone_rt0_color_calls','qualified':False,
            'complete_color_write_call_coverage':False,'ready_for_stateful_replay':False,'reasons':[]}
    reasons=result['reasons'];scope=row.get('surface_scope')
    if scope is None: reasons.append('surface_scope_unavailable');return result
    for name in ('draw','clear'):
        s=scope[name]
        if s is None: reasons.append(name+'_scope_unavailable');continue
        o=s['origin']
        if not o['observed'] or not o['private'] or o['lockable']:reasons.append(name+'_private_nonlockable_standalone_origin_unproven')
        if (o['device'],o['reset_epoch'])!=(row['device'],row['timing']['reset_epoch']):reasons.append(name+'_origin_device_or_epoch_mismatch')
        if any(s['attachments'][1:]) or s['depth_id']:reasons.append(name+'_depth_or_mrt_bound')
        if s['open_accesses'] or s['access_gap']:reasons.append(name+'_outstanding_or_unknown_access')
    clear=row['render_state']['last_clear']
    if clear is None:reasons.append('clear_unavailable')
    else:
        viewport=struct.unpack('<4I2f',bytes.fromhex(clear['viewport']))
        if (clear['target_id']!=row['render_state']['target_id'] or clear['target_desc']!=row['target'] or
            clear['reset_epoch']!=row['timing']['reset_epoch'] or clear['flags']!=1 or clear['rects'] or
            viewport[:4]!=(0,0,*row['target'][:2]) or clear['scissor_enable']):reasons.append('full_current_color_clear_unproven')
    if row['target'][3]!=0:reasons.append('multisample_scope_unsupported')
    writes=assess_writes(row)
    if writes['observed_segment']!='captured_draws_only':reasons.append('ordered_color_call_segment_incomplete')
    # A retained clear supersedes only the dropped prefix. It does not supersede
    # sticky access/query/overlap gaps or unknown resource origin.
    result['qualified']=result['complete_color_write_call_coverage']=not reasons
    return result
