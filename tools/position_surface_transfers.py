"""Independent coverage checks for v18 texture-mip UpdateSurface history."""
def validate(value,descriptors,bound_ids):
    def need(ok,message):
        if not ok:raise ValueError('surface transfers: '+message)
    events=value['surface_transfers']
    need(type(events) is list and 1<=len(events)<=128,'history bound')
    unit=1 if descriptors[0][2] in (21,22) else 4
    coverage=[bytearray(((d[0]+unit-1)//unit)*((d[1]+unit-1)//unit)) for d in descriptors]
    sources={}
    for e in events:
        need(type(e) is dict and set(e)=={'source','revision','source_level','destination_level','source_extent','source_rect','destination'},'shape')
        need(type(e['source']) is int and 0<e['source']<2**64 and e['source'] not in bound_ids,'source identity')
        need(type(e['revision']) is int and 0<e['revision']<2**64,'source revision')
        need(type(e['source_level']) is int and 0<=e['source_level']<16,'source level')
        level=e['destination_level'];need(type(level) is int and 0<=level<len(descriptors),'destination level')
        for key,n in (('source_extent',2),('source_rect',4),('destination',2)):
            need(type(e[key]) is list and len(e[key])==n and all(type(v) is int for v in e[key]),key)
        sw,sh=e['source_extent'];l,t,r,b=e['source_rect'];x,y=e['destination'];dw,dh=descriptors[level][:2]
        need(1<=sw<=16384 and 1<=sh<=16384 and 0<=l<r<=sw and 0<=t<b<=sh,'source bounds')
        w,h=r-l,b-t;need(x>=0 and y>=0 and x+w<=dw and y+h<=dh,'destination bounds')
        whole=(l,t,r,b,x,y,w,h)==(0,0,sw,sh,0,0,dw,dh)
        need(whole or all(v%unit==0 for v in (l,t,r,b,x,y)),'block alignment')
        key=(e['source'],e['revision'],e['source_level'])
        if key in sources:need(sources[key]==(sw,sh),'source extent disagreement')
        sources[key]=(sw,sh)
        columns=(dw+unit-1)//unit;left=x//unit;top=y//unit
        width=(r+unit-1)//unit-l//unit;height=(b+unit-1)//unit-t//unit
        for row in range(top,top+height):
            start=row*columns+left;coverage[level][start:start+width]=b'\1'*width
    need(all(all(mask) for mask in coverage),'incomplete mip coverage')

