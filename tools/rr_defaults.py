"""Validate read-only live-context default queries, separately from RR quality."""
import math
import struct

KEYS=('cross_bilateral_normal_strength','stability_bias','max_radiance',
      'radiance_clip_std_k','gaussian_kernel_relaxation','disocclusion_threshold')
PHASES=('before-1','before-2','after-1','after-2')
GUARD=0xa59c3e71
SENTINEL=0x7fc0a55a


def inspect_defaults(contexts, *, required=False):
    if type(required) is not bool:
        raise ValueError('query-defaults must be boolean')
    present=['default_queries' in context for context in contexts]
    if not any(present) and not required:
        return dict(status='not-requested')
    if not contexts or not all(present):
        raise ValueError('missing default-query evidence')
    baseline=None; stable=True; failed=0; queries=0
    for context in contexts:
        snapshots=context['default_queries']
        if type(snapshots) is not list or len(snapshots)!=len(PHASES):
            raise ValueError('invalid default-query snapshot count')
        for phase,snapshot in zip(PHASES,snapshots):
            if (type(snapshot) is not dict or set(snapshot)!={'phase','format','count','queries'}
                    or snapshot['phase']!=phase or snapshot['format']!='float32'
                    or type(snapshot['count']) is not int or snapshot['count']!=1
                    or type(snapshot['queries']) is not list or len(snapshot['queries'])!=len(KEYS)):
                raise ValueError('invalid default-query descriptor')
            for key,row in enumerate(snapshot['queries'],1):
                if type(row) is not dict or set(row)!={'key','code','bits','guard_before','guard_after','value'}:
                    raise ValueError('invalid default-query row')
                if any(type(row[k]) is not int or not 0<=row[k]<=0xffffffff for k in ('key','code','bits','guard_before','guard_after')) or row['key']!=key:
                    raise ValueError('invalid default-query integer/key')
                # A damaged canary is a memory-safety failure, not a default.
                if row['guard_before']!=GUARD or row['guard_after']!=GUARD:
                    raise ValueError('default-query guard overwritten')
                packed=struct.pack('<I',row['bits']); value=struct.unpack('<f',packed)[0]
                valid=row['code']==0 and row['bits']!=SENTINEL and math.isfinite(value)
                if valid:
                    if type(row['value']) not in (int,float) or not math.isfinite(row['value']) or struct.pack('<f',row['value'])!=packed:
                        raise ValueError('default-query value/bytes mismatch')
                elif row['value'] is not None:
                    raise ValueError('failed default query invented a value')
                failed+=not valid; queries+=1
            rows=snapshot['queries']
            if baseline is None: baseline=rows
            else: stable=stable and rows==baseline
    ready=not failed and stable
    return dict(status='defaults-ready' if ready else 'default-query-failed' if failed else 'default-query-unstable',
                query_count=queries,failed_queries=failed,stable=stable,contexts=len(contexts),
                values={name:row['value'] for name,row in zip(KEYS,baseline)} if ready else None)
