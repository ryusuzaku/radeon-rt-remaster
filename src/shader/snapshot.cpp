#include "snapshot.h"
#include "../scene/scene.h"
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
namespace rrt::shader {
static_assert(sizeof(D3DVIEWPORT9)==24 && sizeof(D3DVERTEXELEMENT9)==8 && sizeof(float)==4 && sizeof(DWORD)==4);
using Microsoft::WRL::ComPtr;
namespace {
void Need(bool ok,const char* what) { if(!ok) throw std::runtime_error(what); }
void Check(HRESULT hr) { Need(SUCCEEDED(hr),"D3D snapshot operation failed"); }
const std::array<D3DVERTEXELEMENT9,2> Layout={{{0,0,D3DDECLTYPE_FLOAT3,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_POSITION,0},D3DDECL_END()}};
const std::pair<D3DRENDERSTATETYPE,DWORD> States[]={
    {D3DRS_ZENABLE,FALSE},{D3DRS_ZWRITEENABLE,FALSE},{D3DRS_ALPHATESTENABLE,FALSE},
    {D3DRS_ALPHABLENDENABLE,FALSE},{D3DRS_SEPARATEALPHABLENDENABLE,FALSE},
    {D3DRS_CULLMODE,D3DCULL_NONE},{D3DRS_STENCILENABLE,FALSE},{D3DRS_FOGENABLE,FALSE},
    {D3DRS_SCISSORTESTENABLE,FALSE},{D3DRS_SRGBWRITEENABLE,FALSE},{D3DRS_COLORWRITEENABLE,15},
    {D3DRS_FILLMODE,D3DFILL_SOLID},{D3DRS_CLIPPLANEENABLE,0},{D3DRS_CLIPPING,TRUE}};
template<class Shader> std::vector<DWORD> ReadProgram(Shader* shader,bool pixel) {
    Need(shader!=nullptr,"missing shader"); UINT size{}; Check(shader->GetFunction(nullptr,&size));
    Need(size>=8 && size<=4096 && size%4==0,"shader byte bound");
    std::vector<DWORD> code(size/4); Check(shader->GetFunction(code.data(),&size));
    Need(size==code.size()*4 && code==Program(pixel),"unsupported shader program"); return code;
}
void Identity(IDirect3DResource9* resource,IDirect3DDevice9* device) {
    ComPtr<IDirect3DDevice9> owner; Check(resource->GetDevice(&owner)); Need(owner.Get()==device,"foreign device resource");
}
template<class F> void Ranges(const Snapshot& s,F visit) {
    Need(s.draw.primitives>0 && s.draw.primitives<=4096 && s.draw.vertices>0 && s.draw.vertices<=4096,"draw budget");
    Need(s.stride>=12 && s.stride<=256 && s.offset<=MaxBuffer,"stream range");
    const std::uint64_t first=std::uint64_t(s.draw.start)*2, count=std::uint64_t(s.draw.primitives)*3;
    Need(first+count*2<=s.index.size(),"index range");
    for(std::uint64_t i=0;i<count;++i) {
        const auto at=static_cast<std::size_t>(first+i*2); std::uint16_t index{}; memcpy(&index,s.index.data()+at,2);
        Need(index>=s.draw.minimum && std::uint64_t(index)<std::uint64_t(s.draw.minimum)+s.draw.vertices,"declared vertex range");
        const auto vertex=std::int64_t(s.draw.base)+index; Need(vertex>=0,"negative base vertex");
        const auto byte=std::uint64_t(s.offset)+std::uint64_t(vertex)*s.stride;
        Need(byte+12<=s.vertex.size(),"vertex range"); visit(at,static_cast<std::size_t>(byte));
    }
}
}
std::vector<DWORD> Program(bool pixel) {
    // Exact compiled programs are an admission allowlist, not a shader interpreter.
    static const char source[]=R"(
float4 m0:register(c0); float4 m1:register(c1); float4 m2:register(c2); float4 m3:register(c3); float4 tint:register(c4);
struct O { float4 position:POSITION; float4 color:COLOR0; };
O vsMain(float3 p:POSITION) { O o; float4 q=float4(p,1); o.position=float4(dot(q,m0),dot(q,m1),dot(q,m2),dot(q,m3)); o.color=tint; return o; }
float4 psMain(float4 color:COLOR0):COLOR0 { return color; }
)";
    auto compile=[&](bool ps) { ComPtr<ID3DBlob> blob,error;
        Check(D3DCompile(source,sizeof(source)-1,nullptr,nullptr,nullptr,ps?"psMain":"vsMain",ps?"ps_3_0":"vs_3_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));
        std::vector<DWORD> result(blob->GetBufferSize()/4); memcpy(result.data(),blob->GetBufferPointer(),blob->GetBufferSize()); return result; };
    static const auto vs=compile(false),ps=compile(true); return pixel?ps:vs;
}
void Configure(IDirect3DDevice9* d) { for(auto [state,value]:States) Check(d->SetRenderState(state,value)); }
void Validate(const Snapshot& s) {
    Need(s.width && s.height && s.width<=512 && s.height<=512,"target budget");
    Need(s.viewport.Width && s.viewport.Height && std::uint64_t(s.viewport.X)+s.viewport.Width<=s.width && std::uint64_t(s.viewport.Y)+s.viewport.Height<=s.height,"viewport range");
    Need(s.viewport.MinZ==0 && s.viewport.MaxZ==1,"viewport depth");
    Need(s.vertex.size()<=MaxBuffer && s.index.size()<=MaxBuffer && s.index.size()%2==0,"buffer budget");
    Need(memcmp(s.declaration.data(),Layout.data(),sizeof(Layout))==0,"unsupported declaration");
    Need(s.vs==Program(false) && s.ps==Program(true),"unsupported shader bytecode");
    for(float value:s.constants) Need(std::isfinite(value),"non-finite constants");
    Ranges(s,[&](std::size_t,std::size_t vertex) { float position[3]; memcpy(position,s.vertex.data()+vertex,12); for(float x:position) Need(std::isfinite(x),"non-finite vertex"); });
}
Snapshot Capture(IDirect3DDevice9* d,Draw draw,const Evidence& vb,const Evidence& ib,std::array<bool,5> known) {
    for(bool initialized:known) Need(initialized,"unknown constant state");
    Snapshot s; s.draw=draw;
    ComPtr<IDirect3DVertexShader9> vs; ComPtr<IDirect3DPixelShader9> ps; ComPtr<IDirect3DVertexDeclaration9> declaration;
    Check(d->GetVertexShader(&vs)); Check(d->GetPixelShader(&ps)); s.vs=ReadProgram(vs.Get(),false); s.ps=ReadProgram(ps.Get(),true);
    Check(d->GetVertexDeclaration(&declaration)); Need(declaration!=nullptr,"missing declaration");
    UINT elements{}; Check(declaration->GetDeclaration(nullptr,&elements)); Need(elements==2,"declaration bound");
    Check(declaration->GetDeclaration(s.declaration.data(),&elements)); Need(elements==2,"declaration changed");
    Check(d->GetVertexShaderConstantF(0,s.constants.data(),5)); Check(d->GetViewport(&s.viewport));
    for(auto [state,expected]:States) { DWORD value{}; Check(d->GetRenderState(state,&value)); Need(value==expected,"unsupported raster state"); }
    ComPtr<IDirect3DSurface9> target,back,extra; Check(d->GetRenderTarget(0,&target)); Check(d->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back));
    Need(target.Get()==back.Get(),"offscreen target unsupported");
    for(DWORD i=1;i<4;++i) { extra.Reset(); if(SUCCEEDED(d->GetRenderTarget(i,&extra))) Need(!extra,"MRT unsupported"); }
    D3DSURFACE_DESC targetDesc{}; Check(target->GetDesc(&targetDesc));
    Need(targetDesc.Format==D3DFMT_X8R8G8B8 && targetDesc.MultiSampleType==D3DMULTISAMPLE_NONE,"target format"); s.width=targetDesc.Width; s.height=targetDesc.Height;
    ComPtr<IDirect3DVertexBuffer9> vertices; ComPtr<IDirect3DIndexBuffer9> indices;
    Check(d->GetStreamSource(0,&vertices,&s.offset,&s.stride)); Check(d->GetIndices(&indices));
    Need(vertices && indices && vertices.Get()==vb.resource && indices.Get()==ib.resource,"stale resource evidence");
    Identity(vertices.Get(),d); Identity(indices.Get(),d);
    for(UINT stream=0;stream<16;++stream) { UINT frequency{}; Check(d->GetStreamSourceFreq(stream,&frequency)); Need(frequency==1,"instancing unsupported");
        if(stream) { ComPtr<IDirect3DVertexBuffer9> other; UINT offset{},stride{}; Check(d->GetStreamSource(stream,&other,&offset,&stride)); Need(!other,"multiple streams unsupported"); } }
    D3DVERTEXBUFFER_DESC vd{}; D3DINDEXBUFFER_DESC id{}; Check(vertices->GetDesc(&vd)); Check(indices->GetDesc(&id));
    Need(vd.Size<=MaxBuffer && id.Size<=MaxBuffer && id.Format==D3DFMT_INDEX16,"resource format/budget");
    Need(vb.bytes.size()==vd.Size && vb.initialized.size()==vd.Size && ib.bytes.size()==id.Size && ib.initialized.size()==id.Size,"shadow size mismatch");
    s.vertex.resize(vd.Size); s.index.resize(id.Size);
    const std::uint64_t first=std::uint64_t(draw.start)*2,length=std::uint64_t(draw.primitives)*6;
    Need(draw.primitives && draw.primitives<=4096 && first+length<=id.Size,"index range");
    for(auto i=first;i<first+length;++i) { Need(ib.initialized[i]==1,"undefined index bytes"); s.index[i]=ib.bytes[i]; }
    Ranges(s,[&](std::size_t,std::size_t vertex) { for(std::size_t i=vertex;i<vertex+12;++i) { Need(vb.initialized[i]==1,"undefined vertex bytes"); s.vertex[i]=vb.bytes[i]; } });
    Validate(s); return s;
}
std::vector<std::uint8_t> Encode(const Snapshot& s) {
    Validate(s); std::vector<std::uint8_t> out;
    auto put=[&](const void* p,std::size_t n) { Need(out.size()+n<=MaxFile-32,"snapshot byte budget"); auto b=static_cast<const std::uint8_t*>(p); out.insert(out.end(),b,b+n); };
    auto word=[&](std::uint32_t n){put(&n,4);};
    put("RRTSHD01",8); word(s.width);word(s.height);word(s.offset);word(s.stride);
    word(static_cast<std::uint32_t>(s.draw.base));word(s.draw.minimum);word(s.draw.vertices);word(s.draw.start);word(s.draw.primitives);
    put(&s.viewport,sizeof(s.viewport));put(s.constants.data(),sizeof(s.constants));put(s.declaration.data(),sizeof(s.declaration));
    word(static_cast<UINT>(s.vs.size()));word(static_cast<UINT>(s.ps.size()));word(static_cast<UINT>(s.vertex.size()));word(static_cast<UINT>(s.index.size()));
    put(s.vs.data(),s.vs.size()*4);put(s.ps.data(),s.ps.size()*4);put(s.vertex.data(),s.vertex.size());put(s.index.data(),s.index.size());
    auto hash=scene::Digest(out.data(),out.size()); out.insert(out.end(),hash.begin(),hash.end()); return out;
}
Snapshot Decode(std::span<const std::uint8_t> bytes) {
    Need(bytes.size()>=64 && bytes.size()<=MaxFile,"snapshot size");
    auto hash=scene::Digest(bytes.data(),bytes.size()-32); Need(memcmp(hash.data(),bytes.data()+bytes.size()-32,32)==0,"snapshot digest");
    std::size_t at{}; auto get=[&](void* p,std::size_t n){Need(n<=bytes.size()-32-at,"snapshot truncated");memcpy(p,bytes.data()+at,n);at+=n;};
    auto word=[&](){std::uint32_t n{};get(&n,4);return n;}; char magic[8];get(magic,8);Need(memcmp(magic,"RRTSHD01",8)==0,"snapshot magic");
    Snapshot s; s.width=word();s.height=word();s.offset=word();s.stride=word();s.draw.base=static_cast<INT>(word());s.draw.minimum=word();s.draw.vertices=word();s.draw.start=word();s.draw.primitives=word();
    get(&s.viewport,sizeof(s.viewport));get(s.constants.data(),sizeof(s.constants));get(s.declaration.data(),sizeof(s.declaration));
    auto nv=word(),np=word(),vb=word(),ib=word(); Need(nv<=1024 && np<=1024 && vb<=MaxBuffer && ib<=MaxBuffer,"snapshot allocation bound");
    s.vs.resize(nv);s.ps.resize(np);s.vertex.resize(vb);s.index.resize(ib);
    get(s.vs.data(),nv*4);get(s.ps.data(),np*4);get(s.vertex.data(),vb);get(s.index.data(),ib);Need(at==bytes.size()-32,"snapshot trailing data");Validate(s);return s;
}
void Replay(IDirect3DDevice9* d,const Snapshot& s) {
    Validate(s); ComPtr<IDirect3DSurface9> target; Check(d->GetRenderTarget(0,&target)); D3DSURFACE_DESC desc{};Check(target->GetDesc(&desc));
    Need(desc.Width==s.width && desc.Height==s.height && desc.Format==D3DFMT_X8R8G8B8 && desc.MultiSampleType==D3DMULTISAMPLE_NONE,"replay target mismatch");
    ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;ComPtr<IDirect3DVertexShader9> vs;ComPtr<IDirect3DPixelShader9> ps;ComPtr<IDirect3DVertexDeclaration9> decl;
    Check(d->CreateVertexBuffer(static_cast<UINT>(s.vertex.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));Check(d->CreateIndexBuffer(static_cast<UINT>(s.index.size()),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));
    void* data{};Check(vb->Lock(0,0,&data,0));memcpy(data,s.vertex.data(),s.vertex.size());Check(vb->Unlock());Check(ib->Lock(0,0,&data,0));memcpy(data,s.index.data(),s.index.size());Check(ib->Unlock());
    Check(d->CreateVertexShader(s.vs.data(),&vs));Check(d->CreatePixelShader(s.ps.data(),&ps));Check(d->CreateVertexDeclaration(s.declaration.data(),&decl));
    Configure(d);Check(d->SetViewport(&s.viewport));Check(d->SetVertexShader(vs.Get()));Check(d->SetPixelShader(ps.Get()));Check(d->SetVertexDeclaration(decl.Get()));Check(d->SetVertexShaderConstantF(0,s.constants.data(),5));
    for(UINT i=0;i<16;++i) { Check(d->SetStreamSourceFreq(i,1));if(i) Check(d->SetStreamSource(i,nullptr,0,0)); }
    Check(d->SetStreamSource(0,vb.Get(),s.offset,s.stride));Check(d->SetIndices(ib.Get()));
    Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,s.draw.base,s.draw.minimum,s.draw.vertices,s.draw.start,s.draw.primitives));
}
}
