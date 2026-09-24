#define RRT_RR_INPUTS 1
#include "render.hlsl"

struct RcPathRow {
    float4 secondaryPositionValid;
    float4 secondaryNormalRoughness;
    float4 secondaryViewInstance;
    float4 secondaryDiffuseAlbedo;
    float4 targetRadiance;
    float4 throughput;
    float4 noCacheIndirectDistance;
    float4 directBackgroundPrimaryValid;
};
RWStructuredBuffer<RcPathRow> rcPathOutput : register(u6);

[numthreads(8,8,1)]
void prepareRcPaths(uint3 thread : SV_DispatchThreadID) {
    if(any(thread.xy>=size)) return;
    const uint index=thread.y*size.x+thread.x;
    const float2 pixel=float2(thread.xy)+.5;
    RayDesc camera=cameraRay(pixel);
    RayQuery<RAY_FLAG_FORCE_NON_OPAQUE> primaryQuery;
    primaryQuery.TraceRayInline(scene,RAY_FLAG_NONE,255,camera);
    while(primaryQuery.Proceed()) if(primaryQuery.CandidateType()==CANDIDATE_NON_OPAQUE_TRIANGLE) {
        Draw d=draws[primaryQuery.CandidateInstanceID()];
        if(all(thread.xy>=d.scissor.xy) && all(thread.xy<d.scissor.zw)) primaryQuery.CommitNonOpaqueTriangleHit();
    }
    RcPathRow result=(RcPathRow)0;
    result.noCacheIndirectDistance.w=-1;
    result.directBackgroundPrimaryValid=float4(background,0);
    if(primaryQuery.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
        const uint primaryInstance=primaryQuery.CommittedInstanceID();
        Surface primary=surface(primaryInstance,primaryQuery.CommittedPrimitiveIndex(),primaryQuery.CommittedTriangleBarycentrics(),camera.Direction);
        const float3 primaryHit=camera.Origin+camera.Direction*primaryQuery.CommittedRayT();
        uint rng=hash(index)^hash(randomIndex+0x1234567)^hash(seed);
        const float3 primaryLight=sun(rng);
        result.directBackgroundPrimaryValid=float4(primary.color*direct(primaryHit,primary.normal,primaryLight)*lightColor,1);

        const float u=random(rng),angle=6.28318530718*random(rng);
        RayDesc bounce; bounce.Origin=primaryHit+primary.normal*.0001;
        bounce.Direction=basisDirection(primary.normal,float3(sqrt(u)*cos(angle),sqrt(u)*sin(angle),sqrt(1-u)));
        bounce.TMin=.0001; bounce.TMax=100000;
        RayQuery<RAY_FLAG_FORCE_OPAQUE> secondaryQuery;
        secondaryQuery.TraceRayInline(scene,RAY_FLAG_NONE,255,bounce); while(secondaryQuery.Proceed()) {}
        float3 target=ambient.xxx,weight=primary.color;
        if(secondaryQuery.CommittedStatus()==COMMITTED_TRIANGLE_HIT) {
            const uint instance=secondaryQuery.CommittedInstanceID();
            const float distance=secondaryQuery.CommittedRayT();
            Surface secondary=surface(instance,secondaryQuery.CommittedPrimitiveIndex(),secondaryQuery.CommittedTriangleBarycentrics(),bounce.Direction);
            const float3 hit=bounce.Origin+bounce.Direction*distance;
            // Legacy diffuse only: factor the secondary albedo into the renderer-owned throughput.
            target=direct(hit,secondary.normal,sun(rng))*lightColor;
            weight*=secondary.color;
            result.secondaryPositionValid=float4(hit,1);
            result.secondaryNormalRoughness=float4(secondary.normal,1);
            result.secondaryViewInstance=float4(-bounce.Direction,instance+1);
            result.secondaryDiffuseAlbedo=float4(secondary.color,1);
            result.targetRadiance=float4(target,1);
            result.noCacheIndirectDistance.w=distance;
        } else result.targetRadiance=float4(target,0);
        result.throughput=float4(weight,1);
        result.noCacheIndirectDistance.xyz=weight*target;
    }
    rcPathOutput[index]=result;
}
