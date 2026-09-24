"""V12 paired material state; texture contents and write provenance stay unknown."""
import hashlib
import math
import struct
DIGEST='ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11'

def validate(row):
    def need(ok,message):
        if not ok:raise ValueError('pixel material: '+message)
    def uint(v):return type(v) is int and 0<=v<2**32
    m=row.get('pixel_material')
    need(row['write_evidence']['overlap'] is False,'observed overlap')
    need(type(m) is dict and set(m)=={'constants','samplers'},'shape')
    code=bytes.fromhex(row['color_replay']['pixel_shader'])
    need(len(code)==1792 and hashlib.sha256(code).hexdigest()==DIGEST,'program')
    c=m['constants'];need(type(c) is str and len(c)==128 and all(x in '0123456789abcdef' for x in c),'constant blob')
    need(all(map(math.isfinite,struct.unpack('<16f',bytes.fromhex(c)))),'nonfinite constants')
    samplers=m['samplers'];need(type(samplers) is list and len(samplers)==2,'samplers')
    identities={}
    for s in samplers:
        need(type(s) is dict and set(s)=={'states','texture'},'sampler shape')
        states=s['states'];need(type(states) is list and len(states)==13 and all(map(uint,states)),'states')
        t=s['texture'];need(type(t) is dict and set(t)=={'id','type','levels','lod','autogen_filter','contents','descriptors'},'texture shape')
        need(type(t['id']) is int and 0<t['id']<2**64,'identity')
        need(type(t['type']) is int and t['type']==3 and t['contents']=='unknown','texture type/contents')
        need(type(t['levels']) is int and 1<=t['levels']<=16 and uint(t['lod']) and uint(t['autogen_filter']),'texture parameters')
        ds=t['descriptors'];need(type(ds) is list and len(ds)==t['levels'],'levels')
        for i,d in enumerate(ds):
            need(type(d) is list and len(d)==7 and all(map(uint,d)) and 1<=d[0]<=16384 and 1<=d[1]<=16384,'descriptor')
            if i:need(d[:2]==[max(1,ds[0][0]>>i),max(1,ds[0][1]>>i)] and d[2:]==ds[0][2:],'mip descriptor')
        if t['id'] in identities:need(t==identities[t['id']],'inconsistent shared binding')
        identities[t['id']]=t
