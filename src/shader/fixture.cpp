#include "snapshot.h"
#include "position.h"
#include "position_capture.h"
#include "color_contract.h"
#include <d3dcompiler.h>
#include <cmath>
#include "../scene/scene.h"
#include <windows.h>
#include <wrl/client.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <stdexcept>
#include <limits>
#include <algorithm>
using Microsoft::WRL::ComPtr;
using namespace rrt::shader;
namespace {
void Need(bool x,const char* why) { if(!x) throw std::runtime_error(why); }
void Check(HRESULT hr) { if(FAILED(hr)) throw std::runtime_error("fixture D3D failure hr="+std::to_string(static_cast<std::int32_t>(hr))); }
template<class F> void Reject(F f) { bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Need(rejected,"invalid snapshot accepted"); }
struct Device {
    HWND window{}; HMODULE runtime{};ComPtr<IDirect3D9> factory;ComPtr<IDirect3DDevice9> device;
    Device(bool hardware=false) {
        window=CreateWindowExW(0,L"STATIC",L"Shader snapshot fixture",WS_OVERLAPPEDWINDOW,0,0,256,192,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);Need(window!=nullptr,"window");
        wchar_t path[32768]{};Need(GetSystemDirectoryW(path,32768)!=0,"system directory");wcscat_s(path,L"\\d3d9.dll");runtime=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);Need(runtime!=nullptr,"system D3D9");
        wchar_t proxy[32768]{};auto proxyLength=GetEnvironmentVariableW(L"RRT_FIXTURE_PROXY",proxy,32768);
        if(proxyLength){Need(proxyLength<32768,"proxy path bound");FreeLibrary(runtime);runtime=LoadLibraryExW(proxy,nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);Need(runtime && GetProcAddress(runtime,"RRTProxyVersion"),"fixture proxy load");}
        auto create=reinterpret_cast<IDirect3D9*(WINAPI*)(UINT)>(GetProcAddress(runtime,"Direct3DCreate9"));Need(create!=nullptr,"factory export");factory.Attach(create(D3D_SDK_VERSION));Need(factory!=nullptr,"factory");
        D3DPRESENT_PARAMETERS pp{};pp.Windowed=TRUE;pp.SwapEffect=D3DSWAPEFFECT_DISCARD;pp.hDeviceWindow=window;pp.BackBufferWidth=128;pp.BackBufferHeight=96;pp.BackBufferFormat=D3DFMT_X8R8G8B8;
        Check(factory->CreateDevice(0,D3DDEVTYPE_HAL,window,hardware?D3DCREATE_HARDWARE_VERTEXPROCESSING:D3DCREATE_SOFTWARE_VERTEXPROCESSING,&pp,&device));
    }
    ~Device(){device.Reset();factory.Reset();if(runtime)FreeLibrary(runtime);if(window)DestroyWindow(window);}
};
void Write(const std::filesystem::path& path,std::span<const std::uint8_t> bytes) {
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);Need(file!=INVALID_HANDLE_VALUE,"exclusive artifact create");
    DWORD count{};bool ok=WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&count,nullptr)!=FALSE;CloseHandle(file);Need(ok && count==bytes.size(),"artifact write");
}
std::vector<std::uint8_t> Read(const std::filesystem::path& path) {
    auto size=std::filesystem::file_size(path);Need(size<=MaxFile,"input file bound");std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));std::ifstream in(path,std::ios::binary);in.read(reinterpret_cast<char*>(bytes.data()),bytes.size());Need(bool(in),"input read");return bytes;
}
std::vector<std::uint8_t> Pixels(IDirect3DDevice9* d) {
    ComPtr<IDirect3DSurface9> rt,read;Check(d->GetRenderTarget(0,&rt));Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_X8R8G8B8,D3DPOOL_SYSTEMMEM,&read,nullptr));Check(d->GetRenderTargetData(rt.Get(),read.Get()));
    D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));std::vector<std::uint8_t> bytes;
    for(UINT y=0;y<96;++y) for(UINT x=0;x<128;++x) for(UINT c=0;c<3;++c) bytes.push_back(static_cast<const std::uint8_t*>(lock.pBits)[y*lock.Pitch+x*4+c]);Check(read->UnlockRect());return bytes;
}
void Clear(IDirect3DDevice9* d) { Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0xff142850,1,0)); }
#include "position_fixture.inc"
void Fixture(const std::filesystem::path& out) {
    Device source;auto* d=source.device.Get();
    ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;ComPtr<IDirect3DVertexShader9> vs;ComPtr<IDirect3DPixelShader9> ps;ComPtr<IDirect3DVertexDeclaration9> decl;
    Check(d->CreateVertexBuffer(256,D3DUSAGE_DYNAMIC|D3DUSAGE_WRITEONLY,0,D3DPOOL_DEFAULT,&vb,nullptr));Check(d->CreateIndexBuffer(16,0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));
    auto vcode=Program(false),pcode=Program(true);Check(d->CreateVertexShader(vcode.data(),&vs));Check(d->CreatePixelShader(pcode.data(),&ps));
    D3DVERTEXELEMENT9 layout[]={{0,0,D3DDECLTYPE_FLOAT3,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_POSITION,0},D3DDECL_END()};Check(d->CreateVertexDeclaration(layout,&decl));
    std::vector<std::uint8_t> vertices(256),indices(16),vmask(256),imask(16);
    const std::uint16_t triangle[]={0,1,2};
    for(int variant=0;variant<3;++variant) {
        const UINT offset=variant==2?8:16,stride=variant==2?24:16,startIndex=variant==2?3:1;
        const INT base=variant==2?2:1;const UINT firstVertex=offset+base*stride;
        std::fill(vmask.begin(),vmask.end(),0);std::fill(imask.begin(),imask.end(),0);
        memcpy(indices.data()+startIndex*2,triangle,6);std::fill(imask.begin()+startIndex*2,imask.begin()+startIndex*2+6,1);
        const float positions[3][3]={{-.7f,-.6f,.4f},{0,.7f,.4f},{.7f,-.6f,.4f}};
        for(int i=0;i<3;++i) { auto at=firstVertex+i*stride;memcpy(vertices.data()+at,positions[i],12);std::fill(vmask.begin()+at,vmask.begin()+at+12,1); }
        if(variant==2) {float x=.4f;memcpy(vertices.data()+firstVertex+2*stride,&x,4);}
        void* pointer{};Check(vb->Lock(0,0,&pointer,D3DLOCK_DISCARD));memcpy(pointer,vertices.data(),vertices.size());Check(vb->Unlock());Check(ib->Lock(0,0,&pointer,0));memcpy(pointer,indices.data(),indices.size());Check(ib->Unlock());
        std::array<float,20> constants={1,0,0,variant==1?.2f:0, 0,1,0,0, 0,0,1,0, 0,0,0,1, .8f,variant==1?.8f:.2f,.1f,1};
        Configure(d);Check(d->SetVertexShader(vs.Get()));Check(d->SetPixelShader(ps.Get()));Check(d->SetVertexDeclaration(decl.Get()));Check(d->SetVertexShaderConstantF(0,constants.data(),5));
        Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));D3DVIEWPORT9 viewport{0,0,128,96,0,1};Check(d->SetViewport(&viewport));
        wchar_t mode[64]{};GetEnvironmentVariableW(L"RRT_SHADER_FIXTURE_CASE",mode,64);
        if(variant==0 && (std::wstring(mode)==L"reset-missing" || std::wstring(mode)==L"reset-refresh")) {
            Check(d->SetStreamSource(0,nullptr,0,0));Check(d->SetIndices(nullptr));vb.Reset();
            D3DPRESENT_PARAMETERS reset{};reset.Windowed=TRUE;reset.SwapEffect=D3DSWAPEFFECT_DISCARD;reset.hDeviceWindow=source.window;reset.BackBufferWidth=128;reset.BackBufferHeight=96;reset.BackBufferFormat=D3DFMT_X8R8G8B8;
            Check(d->Reset(&reset));Check(d->CreateVertexBuffer(256,D3DUSAGE_DYNAMIC|D3DUSAGE_WRITEONLY,0,D3DPOOL_DEFAULT,&vb,nullptr));
            Check(vb->Lock(0,0,&pointer,D3DLOCK_DISCARD));memcpy(pointer,vertices.data(),vertices.size());Check(vb->Unlock());
            Configure(d);Check(d->SetVertexShader(vs.Get()));Check(d->SetPixelShader(ps.Get()));Check(d->SetVertexDeclaration(decl.Get()));Check(d->SetViewport(&viewport));
            Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));
            if(std::wstring(mode)==L"reset-refresh")Check(d->SetVertexShaderConstantF(0,constants.data(),5));
        }
        Evidence ve{vb.Get(),vertices,vmask},ie{ib.Get(),indices,imask};Draw draw{base,0,3,startIndex,1};
        if(variant==0 && (std::wstring(mode)==L"retire-missing" || std::wstring(mode)==L"retire-refresh")) {
            source.device.Reset();Check(vb->GetDevice(source.device.ReleaseAndGetAddressOf()));d=source.device.Get();
            if(std::wstring(mode)==L"retire-refresh")Check(d->SetVertexShaderConstantF(0,constants.data(),5));
        }
        Clear(d);Check(d->BeginScene());auto snapshot=Capture(d,draw,ve,ie,{true,true,true,true,true});
        // An opaque, non-allowlisted but equivalent program for the inventory probe.
        // Snapshot Capture above still sees only the accepted program.
        if(std::wstring(mode)==L"inventory-unknown" || std::wstring(mode)==L"inventory-budget") {
            auto code=Program(true);const UINT words=std::wstring(mode)==L"inventory-budget"?4000:1;
            std::vector<DWORD> comment(words+1,0x12345678u);comment[0]=DWORD(D3DSIO_COMMENT)|(words<<16);
            code.insert(code.begin()+1,comment.begin(),comment.end());
            ComPtr<IDirect3DPixelShader9> opaque;Check(d->CreatePixelShader(code.data(),&opaque));Check(d->SetPixelShader(opaque.Get()));
        }
        if(variant==0 && (std::wstring(mode)==L"stateblock" || std::wstring(mode)==L"stateblock-refresh")) {
            ComPtr<IDirect3DStateBlock9> block;Check(d->CreateStateBlock(D3DSBT_ALL,&block));Check(block->Apply());
            if(std::wstring(mode)==L"stateblock-refresh")Check(d->SetVertexShaderConstantF(0,constants.data(),5));
        }
        if(variant==0 && std::wstring(mode)==L"recording") {
            ComPtr<IDirect3DStateBlock9> block;Check(d->BeginStateBlock());Check(d->SetVertexShaderConstantF(0,constants.data(),5));Check(d->EndStateBlock(&block));
        }
        if(variant==0 && std::wstring(mode)==L"discard") {
            Check(vb->Lock(0,4,&pointer,D3DLOCK_DISCARD));memset(pointer,0,4);Check(vb->Unlock());
        }
        if(variant==0 && std::wstring(mode)==L"failed-draw") {
            Need(FAILED(d->DrawIndexedPrimitive(static_cast<D3DPRIMITIVETYPE>(0),draw.base,draw.minimum,draw.vertices,draw.start,draw.primitives)),"invalid draw succeeded");
        }
        Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,draw.base,draw.minimum,draw.vertices,draw.start,draw.primitives));
        if(variant==0 && std::wstring(mode)==L"inventory-budget")
            for(int repeat=0;repeat<600;++repeat)Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,draw.base,draw.minimum,draw.vertices,draw.start,draw.primitives));
        Check(d->EndScene());
        auto encoded=Encode(snapshot);Need(Encode(Decode(encoded))==encoded,"roundtrip mismatch");
        Write(out/("variant-"+std::to_string(variant)+".rrshader"),encoded);Write(out/("variant-"+std::to_string(variant)+".bgr"),Pixels(d));
        Reject([&]{Capture(d,draw,ve,ie,{true,true,false,true,true});});
        vmask[firstVertex]=0;Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});vmask[firstVertex]=1;
        imask[startIndex*2]=0;Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});imask[startIndex*2]=1;
        auto foreign=ve;foreign.resource=nullptr;Reject([&]{Capture(d,draw,foreign,ie,{true,true,true,true,true});});
        ComPtr<IDirect3DVertexBuffer9> replacement;Check(d->CreateVertexBuffer(256,0,0,D3DPOOL_MANAGED,&replacement,nullptr));
        Check(d->SetStreamSource(0,replacement.Get(),offset,stride));Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});Check(d->SetStreamSource(0,vb.Get(),offset,stride));
        Check(d->SetPixelShader(nullptr));Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});Check(d->SetPixelShader(ps.Get()));
        Check(d->SetStreamSourceFreq(0,D3DSTREAMSOURCE_INDEXEDDATA|2));Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});Check(d->SetStreamSourceFreq(0,1));
        auto bad=snapshot;bad.vs[0]=0;Reject([&]{Validate(bad);});bad=snapshot;bad.declaration[0].Type=D3DDECLTYPE_FLOAT4;Reject([&]{Validate(bad);});
        bad=snapshot;bad.draw.start=UINT_MAX;Reject([&]{Validate(bad);});bad=snapshot;bad.draw.base=-99;Reject([&]{Validate(bad);});
        bad=snapshot;bad.constants[0]=std::numeric_limits<float>::infinity();Reject([&]{Validate(bad);});
        auto corrupt=encoded;corrupt[50]^=1;Reject([&]{Decode(corrupt);});corrupt=encoded;corrupt.pop_back();Reject([&]{Decode(corrupt);});corrupt=encoded;corrupt.push_back(0);Reject([&]{Decode(corrupt);});
        corrupt=encoded;const UINT huge=UINT_MAX;memcpy(corrupt.data()+164,&huge,4);
        auto hash=rrt::scene::Digest(corrupt.data(),corrupt.size()-32);memcpy(corrupt.data()+corrupt.size()-32,hash.data(),32);Reject([&]{Decode(corrupt);});
        // DISCARD invalidates earlier initialization, even if the driver happens
        // to return the same memory. Only the explicitly written byte is known.
        Check(vb->Lock(0,0,&pointer,D3DLOCK_DISCARD));static_cast<std::uint8_t*>(pointer)[0]=0;Check(vb->Unlock());
        std::fill(vmask.begin(),vmask.end(),0);vmask[0]=1;Reject([&]{Capture(d,draw,ve,ie,{true,true,true,true,true});});
    }
    // Release default-pool bindings before Reset; retained file snapshots must
    // not depend on any pre-reset device resource or state.
    Check(d->SetStreamSource(0,nullptr,0,0));Check(d->SetIndices(nullptr));vb.Reset();ib.Reset();
    D3DPRESENT_PARAMETERS pp{};pp.Windowed=TRUE;pp.SwapEffect=D3DSWAPEFFECT_DISCARD;pp.hDeviceWindow=source.window;pp.BackBufferWidth=128;pp.BackBufferHeight=96;pp.BackBufferFormat=D3DFMT_X8R8G8B8;
    Check(d->Reset(&pp));auto retained=Decode(Read(out/"variant-0.rrshader"));Clear(d);Check(d->BeginScene());Replay(d,retained);Check(d->EndScene());Write(out/"reset-replay.bgr",Pixels(d));
    std::cout<<"shader fixture and admission negatives passed\n";
}
}
namespace {
#include "position_group_fixture.inc"
#include "material_fixture.inc"
#include "pixel_replay_fixture.inc"
}
int wmain(int argc,wchar_t** argv) {
    try {
        if(argc==2 && std::wstring(argv[1])==L"--hl2-position") PositionFixture();
        else if(argc==2 && std::wstring(argv[1])==L"--recorded-position") PositionFixture(true);
        else if(argc==2 && std::wstring(argv[1])==L"--position-group") PositionGroupFixture();
        else if(argc==2 && std::wstring(argv[1])==L"--material-inputs") MaterialFixture();
        else if(argc==2 && std::wstring(argv[1])==L"--pixel-material") MaterialFixture(true);
        else if(argc==2 && std::wstring(argv[1])==L"--pixel-replay") PixelReplayFixture();
        else if(argc==3 && std::wstring(argv[1])==L"--fixture") Fixture(argv[2]);
        else if(argc==4 && std::wstring(argv[1])==L"--replay") {
            auto snapshot=Decode(Read(argv[2]));Device replay;Clear(replay.device.Get());Check(replay.device->BeginScene());Replay(replay.device.Get(),snapshot);Check(replay.device->EndScene());Write(argv[3],Pixels(replay.device.Get()));
        } else throw std::runtime_error("--fixture EXISTING_DIRECTORY | --replay SNAPSHOT PIXELS");
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
