#define RRT_RR_INPUTS 1
#include "render.hlsl"

struct RrInput { float4 indirectDistance; float4 directEmission; float4 normalRoughness;
    float4 diffuseAlbedo; float4 motionDepth; float4 positionId; };
RWStructuredBuffer<RrInput> rrOutput : register(u6);
cbuffer RrCamera : register(b1) {
    row_major float4x4 rrView;
    row_major float4x4 rrPreviousView;
    uint rrReset;
};
float2 rrOct(float3 n) {
    float2 p=n.xy/(abs(n.x)+abs(n.y)+abs(n.z));
    // A nonzero sign is essential at the negative-Z pole and fold axes.
    if(n.z<0) p=(1-abs(p.yx))*select(p>=0,1.0.xx,-1.0.xx);
    return p*.5+.5;
}
float4 rrBounce(Surface primary,float3 hit,float3 view,inout uint rng) {
    float u=random(rng),angle=6.28318530718*random(rng);
    RayDesc ray; ray.Origin=hit+primary.normal*.0001;
    ray.Direction=basisDirection(primary.normal,float3(sqrt(u)*cos(angle),sqrt(u)*sin(angle),sqrt(1-u)));
    ray.TMin=.0001; ray.TMax=100000;
    RayQuery<RAY_FLAG_FORCE_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray); while(query.Proceed()) {}
    float distance=ray.TMax; float3 incoming=ambient.xxx;
    if(query.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
        distance=query.CommittedRayT();
        Surface secondary=surface(query.CommittedInstanceID(),query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
        incoming=secondaryLight(secondary,ray.Origin+ray.Direction*distance,-ray.Direction,sun(rng));
    }
    float3 throughput=primary.color;
    if(primary.usePbr) throughput*=((1-primary.metallic)*.96*(1-fresnelPower(dot(view,normalize(view+ray.Direction)))));
    return float4(throughput*incoming,distance);
}
[numthreads(8,8,1)]
void prepareRr(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    // RR uses texel centres, unlike the legacy D3D9 integer-centre oracle.
    float2 pixel=float2(thread.xy)+.5;
    RayDesc ray=cameraRay(pixel);
    RayQuery<RAY_FLAG_FORCE_NON_OPAQUE> query;
    query.TraceRayInline(scene,RAY_FLAG_NONE,255,ray);
    while(query.Proceed()) if(query.CandidateType()==CANDIDATE_NON_OPAQUE_TRIANGLE) {
        Draw d=draws[query.CandidateInstanceID()];
        if(all(thread.xy>=d.scissor.xy) && all(thread.xy<d.scissor.zw)) query.CommitNonOpaqueTriangleHit();
    }
    RrInput result=(RrInput)0;
    result.indirectDistance.w=-1; // No primary surface: inactive signal, depth zero.
    result.directEmission=float4(rgb((uint(round(background.r*255))<<16)|(uint(round(background.g*255))<<8)|uint(round(background.b*255))),0);
    if(query.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
        uint instance=query.CommittedInstanceID();
        Surface s=surface(instance,query.CommittedPrimitiveIndex(),query.CommittedTriangleBarycentrics(),ray.Direction);
        float3 hit=ray.Origin+ray.Direction*query.CommittedRayT();
        uint rng=hash(thread.y*size.x+thread.x)^hash(randomIndex+0x1234567)^hash(seed);
        float3 light=sun(rng);
        float3 directColor=s.usePbr?s.emission+pbrDirect(s,hit,-ray.Direction,light):s.color*direct(hit,s.normal,light)*lightColor;
        result.directEmission=float4(directColor,1);
        result.indirectDistance=rrBounce(s,hit,-ray.Direction,rng);
        result.normalRoughness=float4(rrOct(s.normal),s.usePbr?s.roughness:1,0);
        result.diffuseAlbedo=float4(s.color*(1-(s.usePbr?s.metallic:0)),1);
        float z=mul(float4(hit,1),rrView).z;
        result.motionDepth.w=z;
        if(!rrReset) {
            float4 clip=mul(float4(hit,1),previousViewProjection);
            if(clip.w>1e-8 && all(isfinite(clip))) {
                float2 uv=float2(clip.x/clip.w*.5+.5,.5-clip.y/clip.w*.5);
                // Keep offscreen motion: the denoiser must reject out-of-bounds history.
                result.motionDepth.xyz=float3(uv-pixel/float2(size),mul(float4(hit,1),rrPreviousView).z-z);
            } else result.diffuseAlbedo.w=0; // Diagnostic motion-valid bit.
        } else result.diffuseAlbedo.w=0;
        result.positionId=float4(hit,instance+1);
    }
    rrOutput[thread.y*size.x+thread.x]=result;
}
