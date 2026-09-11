"""Independent v11 UV/color/fog calculation for the exact pinned vertex program."""
import math
import struct

def validate(row):
    def need(ok,message):
        if not ok:raise ValueError('material inputs: '+message)
    material=row.get('material_inputs')
    need(type(material) is dict and set(material)=={'constants','uv','color','evaluated'},'shape')
    need(row['stride']==48 and row['primitives']<=1024,'layout/budget')
    elements=list(struct.iter_unpack('<HHBBBB',bytes.fromhex(row['declaration'])))
    for element in [(0,24,4,0,10,0),(0,28,1,0,5,0),(0,36,1,0,5,1)]:
        need([e for e in elements[:-1] if e[4:]==element[4:]]==[element],'semantic declaration')
    corners=row['primitives']*3
    def blob(key,size):
        value=material[key];need(type(value) is str and len(value)==size*2 and all(c in '0123456789abcdef' for c in value),'blob '+key);return bytes.fromhex(value)
    extra=struct.unpack('<8f',blob('constants',32));need(all(map(math.isfinite,extra)),'constants')
    uvs=list(struct.iter_unpack('<4f',blob('uv',corners*16)))
    colors=struct.unpack('<'+'I'*corners,blob('color',corners*4))
    outputs=list(struct.iter_unpack('<10f',blob('evaluated',corners*40)))
    constants=struct.unpack('<32f',bytes.fromhex(row['constants']));a,b=constants[:2]
    positions=list(struct.iter_unpack('<3f',bytes.fromhex(row['positions'])))
    indices=struct.unpack('<'+'H'*corners,bytes.fromhex(row['indices']))
    for p,uv,color,out,index in zip(positions,uvs,colors,outputs,indices):
        need(row['offset']+(row['base']+index)*48+44<=row['vb_size'],'material buffer range')
        need(all(map(math.isfinite,(*uv,*out))),'nonfinite data')
        q=[p[0]*b+a,p[1]*b+a,p[2]*b+a,p[0]*a+b]
        distance=sum(x*y for x,y in zip(q,extra[:4]));fog=max(extra[4]-distance*extra[7],extra[6])
        expected=[uv[0],uv[1],uv[2]*b,uv[3]*b,*[((color>>shift)&255)/255 for shift in (16,8,0,24)],distance,fog]
        need(all(math.isfinite(y) and abs(x-y)/(1+abs(y))<=2e-4 for x,y in zip(out,expected)),'evaluation mismatch')
