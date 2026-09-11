"""Read-only texture failure context; never admissible texture contents."""
def validate(row,version):
    def need(value,message):
        if not value:raise ValueError('texture diagnostic: '+message)
    t=row['texture_diagnostic']
    keys={'slot','id','descriptor','levels','tracked','admission','revision','known_bytes','total_bytes','pending_mips','upload_source','upload_revision','surface_transfers','last_invalidation','last_upload'}
    need(version in (18,19) and row.get('status')=='rejected' and row.get('hr',-1)>=0 and row.get('evidence_failure',{}).get('stage')=='texture_inputs','failure scope')
    need(type(t) is dict and (set(t)==keys or set(t)==keys|{'coverage_bytes','upload_source_lock_flags','upload_source_invalidation'}),'shape')
    for key in keys-{'descriptor','tracked','admission','last_invalidation','last_upload'}:
        need(type(t[key]) is int and 0<=t[key]<2**64,'integer '+key)
    if 'coverage_bytes' in t:
        need(type(t['coverage_bytes']) is int and 0<=t['coverage_bytes']<=t['total_bytes'],'coverage bytes')
        flags=t['upload_source_lock_flags'];need(flags is None or (type(flags) is int and 0<=flags<2**32),'source lock flags')
        s=t['upload_source_invalidation'];need(type(s) is str and 0<len(s)<=64 and all(c.isascii() and (c.isalpha() or c=='_') for c in s),'source invalidation')
        if not t['tracked']:need(t['coverage_bytes']==0 and flags is None and s=='unavailable','untracked source')
    need(t['slot']<2 and 0<t['levels']<2**32 and type(t['tracked']) is bool,'binding')
    desc=t['descriptor'];need(type(desc) is list and len(desc)==7 and all(type(v) is int and 0<=v<2**32 for v in desc) and desc[0]>0 and desc[1]>0,'descriptor')
    need(t['admission'] in ('unobserved','private_resource','level_count','descriptor_pool_usage_extent','format_or_alignment','chain_budget','shadow_budget','allocation','tracked'),'admission')
    for key in ('last_invalidation','last_upload'):
        s=t[key];need(type(s) is str and 0<len(s)<=64 and all(c.isascii() and (c.isalpha() or c=='_') for c in s),key)
    need(t['known_bytes']<=t['total_bytes']<=16*1024*1024 and t['pending_mips']<=min(16,t['levels']) and t['surface_transfers']<=128,'shadow bounds')
    if t['tracked']:
        need(t['admission']=='tracked' and t['id']>0,'tracked identity')
        if 'coverage_bytes' in t:
            unit_bytes={21:4,22:4,827611204:8,861165636:16,894720068:16}.get(desc[2])
            need(unit_bytes is not None and t['coverage_bytes']*unit_bytes==t['total_bytes'] and t['known_bytes']%unit_bytes==0,'coverage unit consistency')
    else:need(t['admission']!='tracked' and all(t[k]==0 for k in ('revision','known_bytes','total_bytes','pending_mips','upload_source','upload_revision','surface_transfers')),'untracked cannot claim shadow')
