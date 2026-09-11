StructuredBuffer<float4> candidate : register(t0);
StructuredBuffer<uint> pixelMapping : register(t1);
cbuffer ApplyConstants : register(b0) { uint populated; uint3 padding; }
RWStructuredBuffer<uint> output : register(u0);
RWStructuredBuffer<uint> appliedMask : register(u1);

[numthreads(1,1,1)]
void applyRcCandidate(uint3 thread : SV_DispatchThreadID) {
    for(uint pixel=0;pixel<128*96;++pixel) appliedMask[pixel]=0;
    for(uint i=0;i<populated;++i) {
        const uint pixel=pixelMapping[i];
        const uint3 value=(uint3)round(saturate(candidate[pixel].rgb)*255);
        output[pixel]=0xff000000|(value.r<<16)|(value.g<<8)|value.b;
        appliedMask[pixel]=1;
    }
}
