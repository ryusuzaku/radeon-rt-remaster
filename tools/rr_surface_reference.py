"""Bounded textured/PBR extension of the independent matched CPU reference."""
import copy
from hashlib import sha256
from pathlib import Path
import struct
import numpy as np
from rr_reference import Reference,require,normalize,linear_rgb


def read_materials(path,scene,expected):
    if expected=='0'*64:
        require(path is None,'recording has no material sidecar'); return {}
    require(path is not None,'original material sidecar required')
    with Path(path).open('rb') as stream: raw=stream.read(48+16*64+1)
    require(48<=len(raw)<=48+16*64 and sha256(raw).hexdigest()==expected,'material identity/size mismatch')
    require(raw[:8]==b'RRTMAT1\0' and sha256(raw[:-32]).digest()==raw[-32:],'material magic/checksum mismatch')
    version,count=struct.unpack_from('<2I',raw,8); require(version==1 and count<=16 and len(raw)==48+count*64,'material version/count')
    known={d['material_id'] for d in scene['draws']}; records={}; previous=''
    for i in range(count):
        offset=16+i*64; target=raw[offset:offset+32].hex(); values=struct.unpack_from('<8f',raw,offset+32)
        require(target in known and target>previous,'unmatched/duplicate/unsorted material'); previous=target
        require(all(np.isfinite(values)) and all(0<=v<=1 for v in values[:3]) and .05<=values[3]<=1 and all(0<=v<=32 for v in values[4:7]) and 0<=values[7]<=1,'material factor range')
        records[target]=dict(base_color=values[:3],roughness=values[3],emission=values[4:7],metallic=values[7])
    return {i:records[d['material_id']] for i,d in enumerate(scene['draws']) if d['material_id'] in records}


class SurfaceReference(Reference):
    def __init__(self,scene,settings,materials):
        canonical=copy.deepcopy(scene); self.draws=scene['draws']; self.materials=materials
        require(set(materials).issubset(range(len(self.draws))),'unknown material draw')
        for draw in canonical['draws']:
            require(1<=draw['texture_width']<=16 and 1<=draw['texture_height']<=16,'reference texture bound')
            require(draw['sampler'][4] in (1,2) and draw['sampler'][4]==draw['sampler'][5] and not draw['sampler'][10],'reference requires matched point/linear sampling')
            draw['texture_width']=draw['texture_height']=1; draw['texture']=bytes([255]*4)
            draw['vertices']=[(*v[:3],0xffffffff,*v[4:]) for v in draw['vertices']]
        super().__init__(canonical,settings)
        self.uv=[]; self.vertex_colours=[]; self.parameters=[]
        self.texels=[]
        for i,draw in enumerate(self.draws):
            texture=np.frombuffer(draw['texture'],dtype='<u4')
            self.texels.append(np.array([linear_rgb(int(v)) for v in texture]).reshape(draw['texture_height'],draw['texture_width'],3))
            m=materials.get(i); factors=([*m['base_color'],m['roughness'],*m['emission'],m['metallic'],1] if m else [1,1,1,1,0,0,0,0,0])
            for start in range(0,len(draw['indices']),3):
                vertices=[draw['vertices'][j] for j in draw['indices'][start:start+3]]
                self.uv.append([v[4:6] for v in vertices]); self.vertex_colours.append([linear_rgb(v[3]) for v in vertices]); self.parameters.append(factors)
        self.uv=np.array(self.uv); self.vertex_colours=np.array(self.vertex_colours); self.parameters=np.array(self.parameters)

    def texture(self,draw_index,uv):
        d=self.draws[draw_index]; w,h=d['texture_width'],d['texture_height']; texels=self.texels[draw_index]
        def address(x,extent,mode):
            if mode==3: return np.clip(x,0,extent-1)
            x=x%(extent*2 if mode==2 else extent)
            return np.where(x>=extent,extent*2-1-x,x)
        def texel(x,y): return texels[address(y,h,d['sampler'][1]),address(x,w,d['sampler'][0])]
        p=uv*[w,h]
        if d['sampler'][4]==1: return texel(np.floor(p[:,0]).astype(int),np.floor(p[:,1]).astype(int))
        p-=.5; integer=np.floor(p).astype(int); f=p-integer; result=np.zeros((len(uv),3))
        for x in (0,1):
            for y in (0,1): result+=texel(integer[:,0]+x,integer[:,1]+y)*((f[:,0] if x else 1-f[:,0])*(f[:,1] if y else 1-f[:,1]))[:,None]
        return result

    def trace(self,*args,**kwargs):
        result=super().trace(*args,**kwargs); tri=np.maximum(result['triangle'],0); uv=result['barycentric']
        weights=np.column_stack((1-uv.sum(axis=1),uv)); texcoord=np.einsum('ij,ijk->ik',weights,self.uv[tri])
        colour=np.einsum('ij,ijk->ik',weights,self.vertex_colours[tri]); parameters=self.parameters[tri]
        for i in range(len(self.draws)):
            selected=result['draw']==i+1
            if selected.any(): colour[selected]*=self.texture(i,texcoord[selected])
        result['color']=colour*parameters[:,:3]; result['pbr']=parameters[:,8]!=0
        result['roughness']=parameters[:,3]; result['emission']=parameters[:,4:7]; result['metallic']=parameters[:,7]
        return result

    def diffuse_albedo(self,primary): return primary['color']*(1-primary['metallic'])[:,None]
    def black(self): return super().black() and not np.any(self.parameters[:,4:7])

    def primary(self,frame):
        p=super().primary(frame); hit=p['hit']
        require(np.allclose(p['roughness'][hit],np.array(frame['records'])[hit,10],rtol=0,atol=5e-5),'CPU/GPU roughness mismatch')
        return p

    def lighting(self,primary,indices,uniforms):
        normal=primary['normal'][indices]; pos=primary['position'][indices]; view=primary['view'][indices]
        up=np.zeros_like(normal); up[:,2]=1; up[np.abs(normal[:,2])>=.999]=[0,1,0]
        tangent=normalize(np.cross(up,normal)); bitangent=np.cross(normal,tangent)
        u=uniforms[:,0]; angle=2*np.pi*uniforms[:,1]
        direction=tangent*(np.sqrt(u)*np.cos(angle))[:,None]+bitangent*(np.sqrt(u)*np.sin(angle))[:,None]+normal*np.sqrt(1-u)[:,None]
        secondary=self.trace(pos+normal*.0001,direction,.0001); active=np.flatnonzero(secondary['hit'])
        incoming=np.full((len(indices),3),self.ambient)
        if len(active):
            n=secondary['normal'][active]; secondary_view=-direction[active]
            nl=np.maximum(0,np.einsum('ij,j->i',n,self.light)); nv=np.maximum(0,np.einsum('ij,ij->i',n,secondary_view))
            if self.shadows:
                shadow=super().trace(secondary['position'][active]+n*.0001,np.broadcast_to(self.light,n.shape),.0001)
                nl[shadow['hit']]=0
            colour=secondary['color'][active]; value=colour*(self.intensity*nl)[:,None]*self.light_color
            pbr=secondary['pbr'][active]; ids=np.flatnonzero(pbr & (nl>0)&(nv>0))
            value[pbr]=secondary['emission'][active[pbr]]
            if len(ids):
                h=normalize(secondary_view[ids]+self.light); nh=np.maximum(0,np.einsum('ij,ij->i',n[ids],h)); vh=np.clip(np.einsum('ij,ij->i',secondary_view[ids],h),0,1)
                power=(1-vh)**5; a2=secondary['roughness'][active[ids]]**4; metal=secondary['metallic'][active[ids]]
                distribution=a2/(np.pi*(1-nh*nh+nh*nh*a2)**2)
                visibility=.5/(nl[ids]*np.sqrt(nv[ids]**2*(1-a2)+a2)+nv[ids]*np.sqrt(nl[ids]**2*(1-a2)+a2))
                f0=.04*(1-metal)[:,None]+colour[ids]*metal[:,None]
                brdf=colour[ids]*((1-metal)*.96*(1-power)/np.pi)[:,None]+(distribution*visibility)[:,None]*(f0*(1-power)[:,None]+power[:,None])
                value[ids]+=brdf*(self.intensity*nl[ids])[:,None]*self.light_color
            incoming[active]=value
        throughput=primary['color'][indices].copy(); pbr=primary['pbr'][indices]
        if pbr.any():
            h=normalize(view[pbr]+direction[pbr]); vh=np.clip(np.einsum('ij,ij->i',view[pbr],h),0,1)
            throughput[pbr]*=((1-primary['metallic'][indices[pbr]])*.96*(1-(1-vh)**5))[:,None]
        return throughput*incoming
