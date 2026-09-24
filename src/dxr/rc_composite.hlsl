struct RcPathRow { float4 secondaryPositionValid,secondaryNormalRoughness,secondaryViewInstance,secondaryDiffuseAlbedo,targetRadiance,throughput,noCacheIndirectDistance,directBackgroundPrimaryValid; };
StructuredBuffer<RcPathRow> rows : register(t0);
StructuredBuffer<float3> predictions : register(t1);
StructuredBuffer<uint> pixelMapping : register(t2);
cbuffer CompositeConstants : register(b0) { uint populatedCount; uint3 compositePadding; }
RWStructuredBuffer<float4> candidateError : register(u0);
[numthreads(1,1,1)]
void compositeRcPaths(uint3 thread : SV_DispatchThreadID) {
    for(uint pixel=0;pixel<128*96;++pixel) candidateError[pixel]=0;
    const uint count=min(populatedCount,128*96);
    for(uint i=0;i<count;++i) {
        const uint pixel=pixelMapping[i]; RcPathRow row=rows[pixel];
        const float3 candidate=row.directBackgroundPrimaryValid.xyz+row.throughput.xyz*predictions[i];
        const float3 source=row.directBackgroundPrimaryValid.xyz+row.noCacheIndirectDistance.xyz;
        const float3 delta=candidate-source;
        candidateError[pixel]=float4(candidate,dot(delta,delta));
    }
}
