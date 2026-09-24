"""Fixed single-key presets; none is the only unconfigured path."""
import struct

PRESETS={
    'none':(0,0,0.,0.),
    'stability-default':(1,2,1.,1.),
    'stability-half':(2,2,.5,1.),
    'stability-zero':(3,2,0.,1.),
    'gaussian-default':(4,5,0.,0.),
    'gaussian-quarter':(5,5,.25,0.),
    'gaussian-half':(6,5,.5,0.),
    'gaussian-one':(7,5,1.,0.),
    'normal-default':(8,1,1.,1.),
    'normal-half':(9,1,.5,1.),
    'max-radiance-default':(10,3,65504.,65504.),
    'max-radiance-one':(11,3,1.,65504.)}


def validate_setting(name):
    if type(name) is not str or name not in PRESETS:
        raise ValueError('unknown filter setting preset')
    return PRESETS[name]


def bits(value):
    return struct.unpack('<I',struct.pack('<f',value))[0]


def check_settings(contexts,sequence,name,inspection):
    ident,key,value,default=validate_setting(name)
    if not ident:
        if 'filter_setting' in sequence or any('filter_setting' in c for c in contexts):
            raise ValueError('configured report requires explicit expected preset')
        return
    if sequence.get('filter_setting')!=name or inspection['status']!='defaults-ready':
        raise ValueError('missing setting identity or stable defaults')
    expected=dict(preset=name,key=key,format='float32',count=1,value_bits=bits(value),default_query_code=0,
                  default_bits=bits(default),guard_before=0xa59c3e71,guard_after=0xa59c3e71,
                  configure_attempted=True,configure_code=0)
    for context in contexts:
        row=context.get('filter_setting')
        if type(row) is not dict or set(row)!=set(expected) or any(type(row[k]) is not type(v) or row[k]!=v for k,v in expected.items()):
            raise ValueError('setting request/default/configure evidence mismatch')
        for snapshot in context['default_queries']:
            if snapshot['queries'][key-1]['bits']!=bits(default):
                raise ValueError('preset default admission mismatch')
