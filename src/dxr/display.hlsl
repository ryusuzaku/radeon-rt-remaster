// Literal-colour, nearest-pixel display of the packed renderer output.
// Render resolution/history remain independent of the window dimensions.
StructuredBuffer<uint> pixels : register(t0);
cbuffer Display : register(b0) { uint2 sourceSize; uint2 targetSize; };
float4 vertex(uint id : SV_VertexID) : SV_Position {
    return float4(id==2?3:-1,id==1?3:-1,0,1);
}
float4 pixel(float4 position : SV_Position) : SV_Target {
    uint2 p=min(uint2(position.xy)*sourceSize/targetSize,sourceSize-1);
    uint value=pixels[p.y*sourceSize.x+p.x];
    return float4((value>>16)&255,(value>>8)&255,value&255,255)/255.0;
}
