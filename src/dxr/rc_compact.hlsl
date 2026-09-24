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
struct RcCacheInput {
    float3 position;
    float2 normal;
    float2 viewDirection;
    float3 diffuseAlbedo;
    float roughness;
};
StructuredBuffer<RcPathRow> rows : register(t0);
cbuffer CompactConstants : register(b0) { float3 lower; uint rowCount; float3 extent; uint trainingCapacity; }
RWStructuredBuffer<RcCacheInput> predictionInputs : register(u0);
RWStructuredBuffer<float3> predictionOutputs : register(u1);
RWStructuredBuffer<RcCacheInput> trainingInputs : register(u2);
RWStructuredBuffer<float3> trainingTargets : register(u3);
RWStructuredBuffer<uint> sampleCounters : register(u4);
RWStructuredBuffer<uint> pixelMapping : register(u5);

float2 spherical(float3 value) {
    float theta=acos(clamp(value.z,-1.0,1.0))/(3.14159265358979323846*.5);
    theta=theta<1?sqrt(theta):2-sqrt(2-theta);
    return float2(theta*.5,atan2(value.y,value.x)/(2*3.14159265358979323846)+.5);
}
[numthreads(1,1,1)]
void compactRcPaths(uint3 thread : SV_DispatchThreadID) {
    uint count=0;
    const float nanValue=asfloat(0x7fc00000);
    for(uint pixel=0;pixel<rowCount;++pixel) {
        RcPathRow row=rows[pixel];
        if(row.secondaryPositionValid.w==0) continue;
        RcCacheInput input;
        input.position=(((row.secondaryPositionValid.xyz-lower)/extent-.5)/1.05)+.5;
        input.normal=spherical(row.secondaryNormalRoughness.xyz);
        input.viewDirection=spherical(row.secondaryViewInstance.xyz);
        input.diffuseAlbedo=row.secondaryDiffuseAlbedo.xyz;
        input.roughness=row.secondaryNormalRoughness.w;
        predictionInputs[count]=input;
        pixelMapping[count]=pixel;
        predictionOutputs[count]=nanValue.xxx;
        if(count<trainingCapacity) { trainingInputs[count]=input; trainingTargets[count]=row.targetRadiance.xyz; }
        ++count;
    }
    for(uint i=count;i<rowCount;++i) { predictionInputs[i]=(RcCacheInput)0; predictionOutputs[i]=nanValue.xxx; }
    for(uint i=min(count,trainingCapacity);i<trainingCapacity;++i) { trainingInputs[i]=(RcCacheInput)0; trainingTargets[i]=0; }
    sampleCounters[0]=count;
    sampleCounters[1]=min(count,trainingCapacity);
}
