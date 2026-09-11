"""Strict v8 observed-call history and deliberately conservative coverage reports."""

OPERATIONS = set('DrawPrimitive DrawIndexedPrimitive DrawPrimitiveUP DrawIndexedPrimitiveUP DrawRectPatch DrawTriPatch Clear UpdateSurface UpdateTexture StretchRect ColorFill ComposeRects GetRenderTargetData GetFrontBufferData Reset ResetEx SetRenderTarget SetDepthStencilSurface Present PresentEx LockRect UnlockRect LockBox UnlockBox GetDC ReleaseDC GenerateMipSubLevels AddDirtyRect AddDirtyBox Apply'.split())


def validate(row, previous, captures):
    def need(ok, message):
        if not ok: raise ValueError('write evidence: '+message)
    def uint(value): return type(value) is int and 0 <= value < 2**64
    w=row.get('write_evidence')
    need(type(w) is dict and set(w)=={'scope','unobserved','observer_gap','overlap','dropped_through','through','events'}, 'shape')
    need(w['scope']=='process_observed_calls' and w['unobserved'] is True, 'scope cannot claim unobserved coverage')
    need(type(w['observer_gap']) is bool and type(w['overlap']) is bool, 'gap flags')
    need(uint(w['through']) and uint(w['dropped_through']) and w['through']>0 and w['dropped_through']==max(0,w['through']-64), 'window bounds')
    events=w['events']
    need(type(events) is list and len(events)==min(64,w['through']), 'event bound')
    current=row.get('status')=='captured'
    if current: captures[row['ordinal']]=(row['device'],row['timing']['reset_epoch'],w['through'])
    for serial,e in enumerate(events,w['dropped_through']+1):
        need(type(e) is dict and set(e)=={'serial','operation','device','target_id','depth_id','reset_epoch','clear_serial','hr','captured_ordinal'}, 'event shape')
        need(all(uint(e[k]) for k in ('serial','device','target_id','depth_id','reset_epoch','clear_serial')) and e['serial']==serial, 'event order/identity')
        need(type(e['operation']) is str and e['operation'] in OPERATIONS, 'operation')
        need(type(e['hr']) is int and -(2**31)<=e['hr']<2**31, 'native outcome')
        ordinal=e['captured_ordinal']
        need(type(ordinal) is int and -1<=ordinal<4096, 'capture reference')
        if ordinal>=0:
            need(e['operation']=='DrawIndexedPrimitive' and e['hr']>=0 and captures.get(ordinal)==(e['device'],e['reset_epoch'],serial), 'unproven captured draw')
        if serial in previous: need(previous[serial]==e, 'history changed')
        previous[serial]=e
    if current:
        e=events[-1];s=row.get('render_state')
        need(type(s) is dict, 'current draw composition')
        need(e['captured_ordinal']==row['ordinal'] and e['target_id']==s.get('target_id') and e['depth_id']==s.get('depth_id') and e['clear_serial']==s.get('clear_serial') and e['hr']==row['hr'], 'current draw endpoint')


def assess_writes(row):
    w=row.get('write_evidence')
    result={'observed_segment':'unavailable','complete_surface_write_coverage':False,'reasons':[]}
    if w is None:
        result['reasons'].append('ordered_write_evidence_unavailable');return result
    reasons=result['reasons']
    reasons.append('unobserved_external_alias_or_mrt_writes')
    if w['observer_gap']: reasons.append('observer_failure_gap')
    if w['overlap']: reasons.append('overlapping_calls_order_unknown')
    if w['dropped_through']: reasons.append('history_prefix_overflow')
    clear=row['render_state']['last_clear']
    anchors=[e for e in w['events'] if clear is not None and e['operation']=='Clear' and e['hr']>=0 and
             (e['device'],e['reset_epoch'],e['clear_serial'],e['target_id'],e['depth_id'])==
             (row['device'],clear['reset_epoch'],clear['serial'],clear['target_id'],clear['depth_id'])]
    if not anchors:
        reasons.append('clear_anchor_not_in_history');return result
    anchor=anchors[-1]
    intervening=[e for e in w['events'] if anchor['serial']<e['serial']<w['through'] and e['hr']>=0]
    blockers=[e for e in intervening if e['captured_ordinal']<0]
    result['observed_segment']='gapped' if blockers or w['observer_gap'] or w['overlap'] else 'captured_draws_only'
    result['clear_event_serial']=anchor['serial']
    result['intervening_captured_ordinals']=[e['captured_ordinal'] for e in intervening if e['captured_ordinal']>=0]
    result['unsupported_event_serials']=[e['serial'] for e in blockers]
    if blockers: reasons.append('unsupported_or_uncaptured_intervening_calls')
    return result
