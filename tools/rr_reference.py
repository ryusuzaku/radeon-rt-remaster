"""Independent, bounded NumPy/float64 reference for constant-colour diffuse RR fixtures.

No SDK or renderer implementation is imported. Two PCG64 Monte Carlo streams
are independent of the renderer's hash RNG. This is one-bounce diffuse lighting,
not a physically complete path tracer or an exact ground truth.
"""
import numpy as np

WIDTH,HEIGHT=128,96
PIXELS=WIDTH*HEIGHT


def require(ok,message):
    if not ok: raise ValueError(message)


def normalize(v):
    length=np.linalg.norm(v,axis=-1,keepdims=True)
    require(np.all(length>1e-12),'degenerate vector')
    return v/length


def linear_rgb(value):
    c=np.array([(value>>k)&255 for k in (16,8,0)],dtype=np.float64)/255
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)


class Reference:
    def __init__(self,scene,settings):
        require(scene['complete'] and (scene['width'],scene['height']) in ((WIDTH,HEIGHT),(256,192)),'reference scene extent/completeness')
        self.width,self.height=scene['width'],scene['height']; self.pixels=self.width*self.height
        require(settings['radius']==0,'reference requires zero sun radius')
        self.light=normalize(np.array(settings['light'],dtype=np.float64))
        self.light_color=np.array(settings['color'],dtype=np.float64)
        self.intensity=settings['intensity']; self.ambient=settings['ambient']; self.shadows=settings['shadows']
        self.triangles=[]; self.colors=[]; self.draw_ids=[]; self.scissors=[]
        require(1<=len(scene['draws'])<=16,'reference draw bound')
        for index,draw in enumerate(scene['draws']):
            require(draw['texture_width']==draw['texture_height']==1,'reference requires constant textures')
            require(all(x in (1,2,3) for x in draw['sampler'][:2]),'reference does not support border sampling')
            vertices=draw['vertices']; require(3<=len(vertices)<=48,'reference vertex bound')
            require(len({v[3] for v in vertices})==1,'reference requires constant vertex colour')
            world=np.array(draw['world']).reshape(4,4)
            require(np.array_equal(world[:,3],[0,0,0,1]),'reference requires affine world transform')
            points=np.array([(*v[:3],1) for v in vertices])@world
            colour=linear_rgb(vertices[0][3])*linear_rgb(int.from_bytes(draw['texture'],'little'))
            indices=draw['indices']; require(3<=len(indices)<=48 and len(indices)%3==0,'triangle index count')
            for start in range(0,len(indices),3):
                self.triangles.append(points[list(indices[start:start+3]),:3]); self.colors.append(colour); self.draw_ids.append(index+1)
                self.scissors.append(draw['scissor'] if draw['render'][23] else (0,0,self.width,self.height))
        require(1<=len(self.triangles)<=16,'reference triangle bound')
        self.triangles=np.array(self.triangles); self.colors=np.array(self.colors); self.draw_ids=np.array(self.draw_ids)
        self.e1=self.triangles[:,1]-self.triangles[:,0]; self.e2=self.triangles[:,2]-self.triangles[:,0]
        self.normals=normalize(np.cross(self.e1,self.e2))

    def trace(self,origin,direction,minimum=0.,maximum=100000.,pixels=None):
        origin=np.asarray(origin,dtype=np.float64); direction=np.broadcast_to(direction,origin.shape)
        distances=np.broadcast_to(maximum,(len(origin),)).copy(); ids=np.full(len(origin),-1,dtype=np.int32)
        barycentric=np.zeros((len(origin),2))
        for k,a in enumerate(self.triangles[:,0]):
            p=np.cross(direction,self.e2[k]); det=np.einsum('ij,j->i',p,self.e1[k]); good=np.abs(det)>1e-10
            inv=np.divide(1.,det,out=np.zeros_like(det),where=good)
            t=origin-a; u=np.einsum('ij,ij->i',t,p)*inv; q=np.cross(t,self.e1[k])
            v=np.einsum('ij,ij->i',direction,q)*inv; distance=np.einsum('ij,j->i',q,self.e2[k])*inv
            good &= (u>=0)&(v>=0)&(u+v<=1)&(distance>=minimum)&(distance<=distances)
            if pixels is not None:
                l,top,r,b=self.scissors[k]; good &= (pixels[:,0]>=l)&(pixels[:,0]<r)&(pixels[:,1]>=top)&(pixels[:,1]<b)
            distances[good]=distance[good]; ids[good]=k
            barycentric[good]=np.column_stack((u[good],v[good]))
        normal=self.normals[np.maximum(ids,0)].copy()
        normal[np.einsum('ij,ij->i',normal,direction)>0]*=-1
        position=origin+direction*distances[:,None]
        return dict(triangle=ids,hit=ids>=0,position=position,normal=normal,distance=distances,barycentric=barycentric,
                    color=self.colors[np.maximum(ids,0)],draw=np.where(ids>=0,self.draw_ids[np.maximum(ids,0)],0))

    def rays(self,inverse,pixels):
        xy=np.asarray(pixels); ndc=xy*np.array([2/self.width,-2/self.height])+[-1,1]
        n=np.column_stack((ndc,np.zeros(len(xy)),np.ones(len(xy))))@np.array(inverse).reshape(4,4)
        f=np.column_stack((ndc,np.ones(len(xy)),np.ones(len(xy))))@np.array(inverse).reshape(4,4)
        require(np.all(np.abs(n[:,3])>1e-8) and np.all(np.abs(f[:,3])>1e-8),'reference homogeneous camera')
        origin=n[:,:3]/n[:,3:]; end=f[:,:3]/f[:,3:]; delta=end-origin
        return origin,normalize(delta),np.linalg.norm(delta,axis=1)

    def primary(self,frame):
        pixels=np.column_stack((np.arange(self.pixels)%self.width+.5,np.arange(self.pixels)//self.width+.5))
        origin,direction,maximum=self.rays(frame['matrices']['inverse_view_projection'],pixels)
        primary=self.trace(origin,direction,maximum=maximum,pixels=pixels)
        records=np.array(frame['records']); hit=primary['hit']
        require(np.array_equal(primary['draw'],records[:,23]),'CPU/GPU primary identity mismatch')
        require(np.allclose(primary['position'][hit],records[hit,20:23],rtol=0,atol=5e-5),'CPU/GPU primary position mismatch')
        require(np.allclose(self.diffuse_albedo(primary)[hit],records[hit,12:15],rtol=0,atol=5e-5),'CPU/GPU albedo mismatch')
        n=primary['normal'][hit]; octa=n[:,:2]/np.abs(n).sum(axis=1)[:,None]
        folded=(1-np.abs(octa[:,::-1]))*np.where(octa>=0,1,-1)
        octa=np.where((n[:,2]<0)[:,None],folded,octa)*.5+.5
        require(np.allclose(octa,records[hit,8:10],rtol=0,atol=5e-5),'CPU/GPU normal mismatch')
        primary['view']=-direction
        return primary

    def diffuse_albedo(self,primary): return primary['color']

    def black(self): return self.intensity==self.ambient==0

    def lighting(self,primary,indices,uniforms):
        """One independently sampled bounce per supplied primary index."""
        normal=primary['normal'][indices]; pos=primary['position'][indices]
        up=np.zeros_like(normal); up[:,2]=1; up[np.abs(normal[:,2])>=.999]=[0,1,0]
        tangent=normalize(np.cross(up,normal)); bitangent=np.cross(normal,tangent)
        u=uniforms[:,0]; angle=2*np.pi*uniforms[:,1]
        direction=tangent*(np.sqrt(u)*np.cos(angle))[:,None]+bitangent*(np.sqrt(u)*np.sin(angle))[:,None]+normal*np.sqrt(1-u)[:,None]
        secondary=self.trace(pos+normal*.0001,direction,.0001)
        incoming=np.full((len(indices),3),self.ambient); hit=secondary['hit']; active=np.flatnonzero(hit)
        if len(active):
            n=secondary['normal'][active]; cosine=np.maximum(0,np.einsum('ij,j->i',n,self.light))
            if self.shadows:
                shadow=self.trace(secondary['position'][active]+n*.0001,np.broadcast_to(self.light,n.shape),.0001)
                cosine[shadow['hit']]=0
            incoming[active]=secondary['color'][active]*(self.intensity*cosine)[:,None]*self.light_color
        return primary['color'][indices]*incoming

    def estimate(self,primary,samples,seed,frame_index):
        require(type(samples) is int and samples in (64,128,256,512,1024),'samples per batch must be 64,128,256,512,1024')
        require(type(seed) is int and 0<=seed<2**32,'reference seed out of range')
        active=np.flatnonzero(primary['hit']); means=[]; variances=[]
        # Exactly black lighting is analytic; no stochastic noise is introduced.
        if self.black():
            zero=np.zeros((self.pixels,3)); return zero,zero.copy(),zero.copy()
        for replicate in range(2):
            mean=np.zeros((self.pixels,3)); variance=np.zeros_like(mean)
            for start in range(0,len(active),256):
                ids=active[start:start+256]; total=np.zeros((len(ids),3)); squared=np.zeros_like(total)
                rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([0x52525452,seed,frame_index,replicate,start])))
                for _ in range(samples//64):
                    repeated=np.repeat(ids,64); values=self.lighting(primary,repeated,rng.random((len(repeated),2))).reshape(len(ids),64,3)
                    total+=values.sum(axis=1); squared+=(values*values).sum(axis=1)
                mean[ids]=total/samples
                variance[ids]=np.maximum(0,(squared-total*total/samples)/(samples-1))/samples
            means.append(mean); variances.append(variance)
        return (means[0]+means[1])*.5,(variances[0]+variances[1])*.25,means[0]-means[1]

    def visibility(self,current,previous,frame,previous_frame):
        """Geometric visibility at the exact projected point, plus sample compatibility."""
        active=np.flatnonzero(current['hit']); masks={key:np.zeros(self.pixels,dtype=bool) for key in ('stable','disoccluded','offscreen','unmatched')}
        mapping=np.zeros(self.pixels,dtype=np.int32)
        if frame['reset']: return masks,mapping
        position=current['position'][active]; clip=np.column_stack((position,np.ones(len(active))))@np.array(frame['matrices']['previous_view_projection']).reshape(4,4)
        valid=clip[:,3]>1e-8; xy=np.zeros((len(active),2)); xy[valid]=(clip[valid,:2]/clip[valid,3:])*[self.width*.5,-self.height*.5]+[self.width*.5,self.height*.5]
        valid &= (clip[:,2]>=0)&(clip[:,2]<=clip[:,3]) # D3D near/far clip planes
        valid &= (xy[:,0]>=0)&(xy[:,0]<self.width)&(xy[:,1]>=0)&(xy[:,1]<self.height)
        masks['offscreen'][active[~valid]]=True; ids=active[valid]; xy=xy[valid]
        origin,direction,maximum=self.rays(previous_frame['matrices']['inverse_view_projection'],xy)
        traced=self.trace(origin,direction,maximum=maximum,pixels=xy)
        visible=traced['hit']&(traced['draw']==current['draw'][ids])&(np.linalg.norm(traced['position']-current['position'][ids],axis=1)<5e-5)
        masks['disoccluded'][ids[~visible]]=True
        nearest=xy[:,1].astype(int)*self.width+xy[:,0].astype(int); mapping[ids]=nearest
        compatible=visible&(previous['draw'][nearest]==current['draw'][ids])
        compatible &= np.abs(np.einsum('ij,ij->i',previous['position'][nearest]-current['position'][ids],current['normal'][ids]))<5e-5
        compatible &= np.einsum('ij,ij->i',previous['normal'][nearest],current['normal'][ids])>.999
        masks['stable'][ids[compatible]]=True; masks['unmatched'][ids[visible&~compatible]]=True
        return masks,mapping
