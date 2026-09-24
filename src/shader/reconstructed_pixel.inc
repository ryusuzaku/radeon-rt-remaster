// Independent cubic B-spline expression of the audited pinned pixel program.
// Fixed 1024x512 reference scale belongs to its bytecode, not texture dimensions.
constexpr const char* ReconstructedPixel=R"HLSL(
sampler2D baseTexture:register(s0);
sampler2D lightmap:register(s1);
float4 fogParams:register(c11);
float4 tint:register(c12);
float4 fogColor:register(c29);
float4 lightScale:register(c30);
float4 main(float2 uv:TEXCOORD0,float2 lightUV:TEXCOORD2,
            float4 model:TEXCOORD4,float4 color:COLOR0):COLOR {
    float2 q=lightUV*float2(1024,512)+0.5;
    float2 f=frac(q), cell=q-f;
    float2 f2=f*f, f3=f2*f;
    float2 w0=(1-f)*(1-f)*(1-f)/6;
    float2 w1=(3*f3-6*f2+4)/6;
    float2 w2=(-3*f3+3*f2+3*f+1)/6;
    float2 w3=f3/6;
    float2 plus=w2+w3, minus=w0+w1;
    float2 p=(cell+w3/plus+0.5)/float2(1024,512);
    float2 m=(cell+w1/minus-1.5)/float2(1024,512);
    float3 upper=tex2D(lightmap,p).rgb*plus.x+tex2D(lightmap,float2(m.x,p.y)).rgb*minus.x;
    float3 lower=tex2D(lightmap,float2(p.x,m.y)).rgb*plus.x+tex2D(lightmap,m).rgb*minus.x;
    float3 illumination=upper*plus.y+lower*minus.y;
#ifdef RRT_ONE_SAMPLE
    illumination=tex2D(lightmap,lightUV).rgb;
#endif
    float4 base=tex2D(baseTexture,uv);
    float3 lit=illumination*tint.rgb*base.rgb*color.rgb*lightScale.x;
    float fog=saturate(min(model.w*fogParams.w-fogParams.x,fogParams.z));
    return float4(lit+fog*fog*(fogColor.rgb-lit),color.a*tint.a*base.a);
}
)HLSL";
