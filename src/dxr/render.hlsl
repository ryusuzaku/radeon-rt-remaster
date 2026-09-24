struct Vertex { float3 position; uint color; float2 uv; };
struct Draw { uint vertexOffset; uint indexOffset; uint textureOffset; uint width;
    uint height; uint filter; uint addressU; uint addressV; uint4 scissor;
    float3 baseColor; float roughness; float3 emission; float metallic; uint usePbr; };
RaytracingAccelerationStructure scene : register(t0);
StructuredBuffer<Vertex> vertices : register(t1);
StructuredBuffer<uint> indices : register(t2);
StructuredBuffer<Draw> draws : register(t3);
StructuredBuffer<uint> texels : register(t4);
RWStructuredBuffer<uint> output : register(u0);
RWStructuredBuffer<float4> history : register(u1);
struct Signal { float4 radiance; float4 normalDepth; float4 albedoHit; float4 motion; float4 filtered;
    float4 position; float4 sample; float4 temporal; float4 statistics; };
// Runtime records retain only consumed float32 values. Diagnostic records are
// reconstructed on demand, without precision-reducing packing of lighting.
struct Working { float4 normalDepth; float4 albedoId; float4 position; float4 sample; float4 temporal; float2 motion; };
struct TemporalRecord { float4 normalId; float4 albedoCount; float4 position; float4 temporal; };
RWStructuredBuffer<Working> signals : register(u2);
StructuredBuffer<TemporalRecord> previousSignals : register(t5);
RWStructuredBuffer<TemporalRecord> nextSignals : register(u3);
RWStructuredBuffer<Signal> diagnosticOutput : register(u4);
// Aliases previousSignals only after temporalResolve has finished reading it.
RWStructuredBuffer<TemporalRecord> filterScratch : register(u5);
cbuffer Frame : register(b0) {
    row_major float4x4 inverseViewProjection;
    uint2 size; uint mode; uint shadows;
    float3 background; float ambient;
    float3 lightDirection; float intensity;
    uint sampleIndex; uint seed; float sunRadius; uint flags;
    row_major float4x4 previousViewProjection;
    uint randomIndex; uint exportStart; uint exportCount; uint padding;
    float3 lightColor; uint colorPadding;
};
float luminance(float3 color) { return dot(color,float3(.2126,.7152,.0722)); }
Signal currentSignal(uint index) {
    Working w=signals[index]; Signal s=(Signal)0;
    s.radiance=history[index]; s.normalDepth=w.normalDepth;
    s.albedoHit=float4(w.albedoId.rgb,w.albedoId.w!=0?1:0);
    s.motion.w=w.albedoId.w; s.position=w.position; s.sample=float4(w.sample.rgb,1); s.temporal=w.temporal;
    uint state=asuint(w.sample.w),reason=(state>>6)&7; float l=luminance(w.temporal.rgb);
    s.statistics=float4(state&63,max(0,w.temporal.w-l*l),reason==0?1:0,reason);
    s.motion.xyz=float3(w.motion,(state>>9)&1);
    return s;
}
Signal previousSignal(uint index) {
    TemporalRecord h=previousSignals[index]; Signal s=(Signal)0;
    s.normalDepth=float4(h.normalId.xyz,0); s.motion.w=h.normalId.w;
    s.albedoHit=float4(h.albedoCount.xyz,h.normalId.w!=0?1:0);
    s.statistics.x=h.albedoCount.w; s.position=h.position; s.temporal=h.temporal; return s;
}
float3 rgb(uint value) {
    float3 c=float3((value>>16)&255,(value>>8)&255,value&255)/255.0;
#ifdef RRT_RR_INPUTS
    // Decode individual texels/vertices before filtering/interpolation, only in
    // the separate RR preparation shader. Material factors remain linear.
    c=select(c<=.04045,c/12.92,pow((c+.055)/1.055,2.4));
#endif
    return c;
}
int address(int x,int extent,uint kind) {
    if(kind==3) return clamp(x,0,extent-1);
    int period=kind==2?extent*2:extent;
    x=((x%period)+period)%period;
    return kind==2 && x>=extent?period-1-x:x;
}
float3 texel(Draw d,int2 p) {
    p=int2(address(p.x,d.width,d.addressU),address(p.y,d.height,d.addressV));
    return rgb(texels[d.textureOffset+p.y*d.width+p.x]);
}
float3 textureColor(Draw d,float2 uv) {
    float2 p=uv*float2(d.width,d.height);
    if(d.filter==1) return texel(d,int2(floor(p)));
    p-=0.5; int2 a=int2(floor(p)); float2 f=frac(p);
    return lerp(lerp(texel(d,a),texel(d,a+int2(1,0)),f.x),
                lerp(texel(d,a+int2(0,1)),texel(d,a+int2(1,1)),f.x),f.y);
}
uint hash(uint x) {
    x ^= x>>16; x *= 0x7feb352d; x ^= x>>15; x *= 0x846ca68b; return x^(x>>16);
}
float random(inout uint state) { state=hash(state+0x9e3779b9); return (state>>8)*(1.0/16777216.0); }
float3 basisDirection(float3 normal,float3 local) {
    float3 tangent=normalize(cross(abs(normal.z)<.999?float3(0,0,1):float3(0,1,0),normal));
    return tangent*local.x+cross(normal,tangent)*local.y+normal*local.z;
}
float3 sun(inout uint rng) {
    float radius=sunRadius*sqrt(random(rng)),angle=6.28318530718*random(rng);
    return normalize(basisDirection(lightDirection,float3(radius*cos(angle),radius*sin(angle),1)));
}
struct Surface { float3 color; float3 normal; float3 emission; float roughness; float metallic; uint usePbr; };
Surface surface(uint instance,uint primitive,float2 bary,float3 direction) {
    Draw d=draws[instance]; uint index=d.indexOffset+primitive*3;
    Vertex a=vertices[d.vertexOffset+indices[index]],b=vertices[d.vertexOffset+indices[index+1]],c=vertices[d.vertexOffset+indices[index+2]];
    float3 weights=float3(1-bary.x-bary.y,bary);
    Surface s; s.color=textureColor(d,a.uv*weights.x+b.uv*weights.y+c.uv*weights.z)*(rgb(a.color)*weights.x+rgb(b.color)*weights.y+rgb(c.color)*weights.z);
    s.normal=normalize(cross(b.position-a.position,c.position-a.position));
    if(dot(s.normal,direction)>0) s.normal=-s.normal;
    s.usePbr=d.usePbr; s.roughness=d.roughness; s.metallic=d.metallic; s.emission=d.emission;
    if(s.usePbr) s.color*=d.baseColor;
    return s;
}
float direct(float3 hit,float3 normal,float3 light) {
    float cosine=saturate(dot(normal,light));
    if(shadows && cosine>0) {
        RayDesc ray; ray.Origin=hit+normal*.0001; ray.Direction=light; ray.TMin=.0001; ray.TMax=100000;
        RayQuery<RAY_FLAG_FORCE_OPAQUE|RAY_FLAG_ACCEPT_FIRST_HIT_AND_END_SEARCH> query;
        query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray); while(query.Proceed()) {}
        if(query.CommittedStatus()==COMMITTED_TRIANGLE_HIT) return 0;
    }
    return intensity*cosine;
}
// GGX / correlated Smith / Schlick. Roughness is bounded to [.05,1] by both readers.
// Factors use the current literal-RGB working space, not automatic sRGB decoding.
float fresnelPower(float cosine) { float x=1-saturate(cosine); float x2=x*x; return x2*x2*x; }
float3 pbrBrdf(Surface s,float3 view,float3 light) {
    float nv=saturate(dot(s.normal,view)),nl=saturate(dot(s.normal,light));
    if(nv<=0 || nl<=0) return 0;
    float3 halfDirection=normalize(view+light);
    float nh=saturate(dot(s.normal,halfDirection)),vh=saturate(dot(view,halfDirection));
    float alpha=s.roughness*s.roughness,a2=alpha*alpha;
    float denominator=(1-nh*nh)+nh*nh*a2;
    float distribution=a2/(3.14159265359*denominator*denominator);
    float visibility=.5/(nl*sqrt(nv*nv*(1-a2)+a2)+nv*sqrt(nl*nl*(1-a2)+a2));
    float power=fresnelPower(vh);
    float3 f0=lerp(.04.xxx,s.color,s.metallic),f=f0+(1-f0)*power;
    float3 diffuse=s.color*((1-s.metallic)*.96*(1-power)/3.14159265359);
    return diffuse+distribution*visibility*f;
}
float3 pbrDirect(Surface s,float3 hit,float3 view,float3 light) {
    return pbrBrdf(s,view,light)*direct(hit,s.normal,light)*lightColor;
}
float3 secondaryLight(Surface s,float3 hit,float3 view,float3 light) {
    if(s.usePbr) return s.emission+pbrDirect(s,hit,view,light);
    float3 value=s.color*direct(hit,s.normal,light);
    if(flags&16) value*=lightColor;
    return value;
}
float3 indirect(float3 hit,float3 normal,inout uint rng) {
    // Cosine-weighted sampling cancels the Lambert BRDF cosine/pdf terms.
    float u=random(rng),angle=6.28318530718*random(rng);
    RayDesc ray; ray.Origin=hit+normal*.0001;
    ray.Direction=basisDirection(normal,float3(sqrt(u)*cos(angle),sqrt(u)*sin(angle),sqrt(1-u)));
    ray.TMin=.0001; ray.TMax=100000;
    RayQuery<RAY_FLAG_FORCE_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray); while(query.Proceed()) {}
    if(query.CommittedStatus()!=COMMITTED_TRIANGLE_HIT) return ambient.xxx;
    Surface s=surface(query.CommittedInstanceID(),query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
    return secondaryLight(s,ray.Origin+ray.Direction*query.CommittedRayT(),-ray.Direction,sun(rng));
}
float3 pbrIndirect(Surface primary,float3 hit,float3 view,inout uint rng) {
    // Sample only the diffuse lobe. Specular indirect transport is deliberately absent.
    float u=random(rng),angle=6.28318530718*random(rng);
    RayDesc ray; ray.Origin=hit+primary.normal*.0001;
    ray.Direction=basisDirection(primary.normal,float3(sqrt(u)*cos(angle),sqrt(u)*sin(angle),sqrt(1-u)));
    ray.TMin=.0001; ray.TMax=100000;
    RayQuery<RAY_FLAG_FORCE_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray); while(query.Proceed()) {}
    float3 incoming=ambient.xxx;
    if(query.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
        Surface s=surface(query.CommittedInstanceID(),query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
        incoming=secondaryLight(s,ray.Origin+ray.Direction*query.CommittedRayT(),-ray.Direction,sun(rng));
    }
    float vh=saturate(dot(view,normalize(view+ray.Direction)));
    return primary.color*((1-primary.metallic)*.96*(1-fresnelPower(vh)))*incoming;
}
RayDesc cameraRay(float2 pixel) {
    float2 ndc=float2(pixel.x*2.0/size.x-1,1-pixel.y*2.0/size.y);
    float4 nearH=mul(float4(ndc,0,1),inverseViewProjection),farH=mul(float4(ndc,1,1),inverseViewProjection);
    float3 nearP=nearH.xyz/nearH.w,farP=farH.xyz/farH.w;
    RayDesc ray; ray.Origin=nearP; ray.Direction=normalize(farP-nearP); ray.TMin=0; ray.TMax=length(farP-nearP); return ray;
}
Signal guide(uint2 pixel) {
    Signal result=(Signal)0;
    RayDesc ray=cameraRay(float2(pixel));
    RayQuery<RAY_FLAG_FORCE_NON_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray);
    while(query.Proceed()) {
        if(query.CandidateType()==CANDIDATE_NON_OPAQUE_TRIANGLE) {
            Draw d=draws[query.CandidateInstanceID()];
            if(all(pixel>=d.scissor.xy) && all(pixel<d.scissor.zw)) query.CommitNonOpaqueTriangleHit();
        }
    }
    if(query.CommittedStatus()!=COMMITTED_TRIANGLE_HIT) return result;
    Surface s=surface(query.CommittedInstanceID(),query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
    result.normalDepth=float4(s.normal,query.CommittedRayT());
    result.albedoHit=float4(s.color,1);
    result.motion.w=query.CommittedInstanceID()+1; // Draw identity, zero reserved for background.
    float3 hit=ray.Origin+ray.Direction*query.CommittedRayT();
    RayDesc adjacent=cameraRay(float2(pixel)+float2(1,0));
    result.position=float4(hit,length(adjacent.Origin+adjacent.Direction*query.CommittedRayT()-hit));
    // Retain the original projection result: recomputing from stored position
    // can round differently at frustum edges and change temporal acceptance.
    if(flags&2) {
        float4 clip=mul(float4(hit,1),previousViewProjection);
        if(clip.w>1e-8) {
            float3 ndc=clip.xyz/clip.w;
            float2 previousPixel=float2((ndc.x+1)*size.x*.5,(1-ndc.y)*size.y*.5);
            if(all(isfinite(ndc)) && ndc.z>=0 && ndc.z<=1 && all(previousPixel>=0) && all(previousPixel<float2(size)))
                result.motion.xyz=float3(previousPixel-float2(pixel),1);
        }
    }
    return result;
}
[numthreads(8,8,1)]
void main(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    // D3D9 pixel centers are at integer coordinates; retain that convention
    // for comparisons to the legacy raster oracle.
    uint rng=hash(thread.y*size.x+thread.x)^hash(randomIndex+0x1234567)^hash(seed);
    float2 pixel=float2(thread.xy);
    if(mode==3) { pixel.x+=random(rng)-.5; pixel.y+=random(rng)-.5; }
    RayDesc ray=cameraRay(pixel);
    RayQuery<RAY_FLAG_FORCE_NON_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray);
    while(query.Proceed()) {
        if(query.CandidateType()==CANDIDATE_NON_OPAQUE_TRIANGLE) {
            Draw d=draws[query.CandidateInstanceID()];
            if(all(thread.xy>=d.scissor.xy) && all(thread.xy<d.scissor.zw)) query.CommitNonOpaqueTriangleHit();
        }
    }
    float3 color=background;
    if(query.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
        Surface s=surface(query.CommittedInstanceID(),query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
        color=s.color; float3 normal=s.normal;
        float3 hit=ray.Origin+ray.Direction*query.CommittedRayT();
        if(mode==1) color=normal*0.5+0.5;
        else if(mode==2) {
            if(s.usePbr) color=s.emission+s.color*((1-s.metallic)*.96*ambient)+pbrDirect(s,hit,-ray.Direction,lightDirection);
            else if(flags&16) color*=ambient+direct(hit,normal,lightDirection)*lightColor;
            else color*=ambient+direct(hit,normal,lightDirection);
        }
        else if(mode==3) {
            if(s.usePbr) { float3 lighting=pbrDirect(s,hit,-ray.Direction,sun(rng)); color=s.emission+lighting+pbrIndirect(s,hit,-ray.Direction,rng); }
            else { float lighting=direct(hit,normal,sun(rng));
                if(flags&16) color*=lighting*lightColor+indirect(hit,normal,rng);
                else color*=lighting+indirect(hit,normal,rng);
            }
        }
    }
    uint index=thread.y*size.x+thread.x;
    float3 fresh=color;
    // Sample zero overwrites without reading undefined or stale history.
    if(sampleIndex>0) color=lerp(history[index].rgb,color,1.0/(sampleIndex+1));
    history[index]=float4(color,1);
    Signal data=guide(thread.xy); Working w;
    w.normalDepth=data.normalDepth; w.albedoId=float4(data.albedoHit.rgb,data.motion.w);
    w.position=data.position; w.sample=float4(fresh,asfloat(1u|(1u<<6)|(uint(data.motion.z)<<9)));
    w.temporal=0; w.motion=data.motion.xy; signals[index]=w;
}

bool sameSurface(Signal a,Signal b) {
    return b.albedoHit.w!=0 && a.motion.w==b.motion.w && dot(a.normalDepth.xyz,b.normalDepth.xyz)>=.95
        && all(abs(a.albedoHit.rgb-b.albedoHit.rgb)<=.1);
}

[numthreads(8,8,1)]
void temporalResolve(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    uint index=thread.y*size.x+thread.x; Signal current=currentSignal(index);
    float3 mean=current.sample.rgb; float moment=luminance(mean); moment*=moment;
    float count=1; uint reason=0;
    if(!(flags&4) || mode!=3) reason=1;
    else if(!(flags&8)) reason=2;
    else if(!current.albedoHit.w) reason=3;
    else if(!current.motion.z) reason=4;
    int2 p=int2(floor(float2(thread.xy)+current.motion.xy+.5));
    if(reason==0 && (any(p<0) || any(p>=int2(size)))) reason=4;
    Signal old=(Signal)0;
    if(reason==0) {
        old=previousSignal(p.y*size.x+p.x);
        if(!old.albedoHit.w) reason=5;
        else if(!sameSurface(current,old)) reason=6;
        else {
            float3 delta=current.position.xyz-old.position.xyz;
            float planeError=abs(dot(delta,old.normalDepth.xyz));
            // Compare actual world-space surfaces, not ray lengths from different cameras.
            if(planeError>max(.001,.001*current.normalDepth.w)
               || length(delta)>max(.002,1.5*max(current.position.w,old.position.w))) reason=7;
        }
    }
    if(reason==0) {
        // Moving-camera history is clipped to a local, matching-surface range.
        // Stationary histories keep their moments untouched for convergence tests.
        float3 historyColor=old.temporal.rgb;
        float historyMoment=old.temporal.w;
        if(any(abs(current.motion.xy)>.001)) {
            float3 lo=current.sample.rgb,hi=lo;
            for(int y=-1;y<=1;++y) for(int x=-1;x<=1;++x) {
                int2 q=int2(thread.xy)+int2(x,y);
                if(any(q<0) || any(q>=int2(size))) continue;
                Signal tap=currentSignal(q.y*size.x+q.x);
                if(!sameSurface(current,tap) || abs(dot(tap.position.xyz-current.position.xyz,current.normalDepth.xyz))>.001) continue;
                lo=min(lo,tap.sample.rgb); hi=max(hi,tap.sample.rgb);
            }
            historyColor=clamp(historyColor,lo,hi);
            float oldL=luminance(old.temporal.rgb),newL=luminance(historyColor);
            historyMoment=max(0,historyMoment-oldL*oldL)+newL*newL;
        }
        count=min(old.statistics.x+1,32.0);
        mean=lerp(historyColor,mean,1.0/count);
        moment=lerp(historyMoment,moment,1.0/count);
    }
    signals[index].temporal=float4(mean,moment);
    signals[index].sample.w=asfloat(uint(count)|(reason<<6)|(uint(current.motion.z)<<9));
}

bool filterSurface(Signal center,Signal tap) {
    if(!sameSurface(center,tap)) return false;
    float3 delta=tap.position.xyz-center.position.xyz;
    float footprint=max(center.position.w,tap.position.w);
    return abs(dot(delta,center.normalDepth.xyz))<=max(.001,.01*footprint)
        && length(delta)<=max(.002,6*footprint);
}
float3 filterInput(Signal s,bool temporalActive) { return temporalActive?s.temporal.rgb:s.radiance.rgb; }
float4 varianceFirst(uint2 pixel,Signal center,bool temporalActive) {
    float3 original=filterInput(center,temporalActive);
    // The guide ID identifies an immutable draw. Glossy PBR gets conservative support.
    Draw material=draws[uint(center.motion.w)-1];
    int radius=material.usePbr && material.roughness<.35?1:3;
    bool mature=temporalActive && center.statistics.x>=4;
    float mean=0,secondMoment=0,count=0;
    // A 3x3 bootstrap can report zero variance for a chance constant-noise patch,
    // causing the luminance edge stop to preserve that noise. Estimate across
    // the full supported footprint until temporal moments are available.
    if(!mature) for(int y=-radius;y<=radius;++y) for(int x=-radius;x<=radius;++x) {
        int2 p=int2(pixel)+int2(x,y); if(any(p<0) || any(p>=int2(size))) continue;
        Signal tap=currentSignal(p.y*size.x+p.x); if(!filterSurface(center,tap)) continue;
        float value=luminance(filterInput(tap,temporalActive)); mean+=value; secondMoment+=value*value; count+=1;
    }
    mean/=max(count,1); float localVariance=max(0,secondMoment/max(count,1)-mean*mean);
    float variance=mature?center.statistics.y/center.statistics.x:localVariance;
    float centerL=luminance(original),weightSum=0,varianceSum=0; float3 total=0;
    for(int y=-1;y<=1;++y) for(int x=-1;x<=1;++x) {
        int2 p=int2(pixel)+int2(x,y); if(any(p<0) || any(p>=int2(size))) continue;
        Signal tap=currentSignal(p.y*size.x+p.x); if(!filterSurface(center,tap)) continue;
        float3 value=filterInput(tap,temporalActive);
        float tapVariance=temporalActive && tap.statistics.x>=4?tap.statistics.y/tap.statistics.x:variance;
        float sigma=max(.0001,4*sqrt(max(0,variance+tapVariance)));
        float weight=float((2-abs(x))*(2-abs(y)))*exp(-abs(luminance(value)-centerL)/sigma);
        total+=value*weight; weightSum+=weight; varianceSum+=tapVariance*weight*weight;
    }
    return weightSum>0?float4(total/weightSum,varianceSum/(weightSum*weightSum)):float4(original,variance);
}
[numthreads(8,8,1)]
void variancePrepare(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    uint index=thread.y*size.x+thread.x; Signal center=currentSignal(index);
    filterScratch[index].temporal=center.albedoHit.w!=0?varianceFirst(thread.xy,center,(flags&4)!=0):float4(center.radiance.rgb,0);
}
float3 varianceFiltered(uint2 pixel,Signal center) {
    float4 original=filterScratch[pixel.y*size.x+pixel.x].temporal;
    Draw material=draws[uint(center.motion.w)-1];
    if(material.usePbr && material.roughness<.35) return original.rgb;
    float centerL=luminance(original.rgb),weightSum=0; float3 total=0;
    for(int y=-1;y<=1;++y) for(int x=-1;x<=1;++x) {
        int2 p=int2(pixel)+2*int2(x,y); if(any(p<0) || any(p>=int2(size))) continue;
        uint index=p.y*size.x+p.x; Signal tap=currentSignal(index); if(!filterSurface(center,tap)) continue;
        float4 value=filterScratch[index].temporal;
        float sigma=max(.0001,4*sqrt(max(0,original.w+value.w)));
        float weight=float((2-abs(x))*(2-abs(y)))*exp(-abs(luminance(value.rgb)-centerL)/sigma);
        total+=value.rgb*weight; weightSum+=weight;
    }
    return weightSum>0?total/weightSum:original.rgb;
}
float3 presentationColor(uint2 pixel) {
    uint index=pixel.y*size.x+pixel.x;
    Signal center=currentSignal(index); bool temporalActive=(flags&4) && mode==3;
    float3 color=temporalActive && center.albedoHit.w!=0?center.temporal.rgb:center.radiance.rgb;
    if((flags&1) && mode==3 && center.albedoHit.w!=0) {
        if(flags&32) return varianceFiltered(pixel,center);
        float3 total=0; float weightSum=0;
        for(int y=-2;y<=2;++y) for(int x=-2;x<=2;++x) {
            int2 p=int2(pixel)+int2(x,y);
            if(any(p<0) || any(p>=int2(size))) continue;
            Signal tap=currentSignal(p.y*size.x+p.x);
            if(tap.albedoHit.w==0 || tap.motion.w!=center.motion.w) continue;
            if(dot(tap.normalDepth.xyz,center.normalDepth.xyz)<.95) continue;
            if(abs(tap.normalDepth.w-center.normalDepth.w)>max(.005,.02*center.normalDepth.w)) continue;
            if(any(abs(tap.albedoHit.rgb-center.albedoHit.rgb)>.1)) continue;
            float weight=exp(-float(x*x+y*y)/2.88);
            total+=(temporalActive?tap.temporal.rgb:tap.radiance.rgb)/max(tap.albedoHit.rgb,.05)*weight; weightSum+=weight;
        }
        color=total/max(weightSum,1e-8)*max(center.albedoHit.rgb,.05);
    }
    return color;
}
[numthreads(8,8,1)]
void present(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    uint index=thread.y*size.x+thread.x; float3 color=presentationColor(thread.xy);
    Signal s=currentSignal(index); TemporalRecord h;
    h.normalId=float4(s.normalDepth.xyz,s.motion.w); h.albedoCount=float4(s.albedoHit.xyz,s.statistics.x);
    h.position=s.position; h.temporal=s.temporal; nextSignals[index]=h;
    uint3 value=(uint3)round(saturate(color)*255);
    output[index]=0xff000000|(value.r<<16)|(value.g<<8)|value.b;
}
[numthreads(64,1,1)]
void exportSignals(uint3 thread : SV_DispatchThreadID) {
    if(thread.x>=exportCount) return;
    uint index=exportStart+thread.x; Signal s=currentSignal(index);
    s.filtered=float4(presentationColor(uint2(index%size.x,index/size.x)),1);
    diagnosticOutput[thread.x]=s;
}
