#include <windows.h>
#include <d3d9.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <array>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
namespace {
void Check(HRESULT hr, const char* operation) {
    if(FAILED(hr)) { char text[256]; sprintf_s(text,"%s: 0x%08lx",operation,static_cast<unsigned long>(hr)); throw std::runtime_error(text); }
}
void Require(bool value,const char* message) { if(!value) throw std::runtime_error(message); }
LRESULT CALLBACK Procedure(HWND w,UINT m,WPARAM a,LPARAM b) { return DefWindowProcW(w,m,a,b); }
struct Window {
    HWND value{};
    Window() {
        WNDCLASSW c{}; c.lpfnWndProc=Procedure; c.hInstance=GetModuleHandleW(nullptr); c.lpszClassName=L"RRTTest";
        if(!RegisterClassW(&c) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) throw std::runtime_error("RegisterClass");
        value=CreateWindowExW(0,c.lpszClassName,L"RRT harness",WS_OVERLAPPEDWINDOW,0,0,640,480,nullptr,nullptr,c.hInstance,nullptr);
        Require(value!=nullptr,"CreateWindow");
        // Successful-present/selected-frame tests require a visible surface.
        // Hidden windows can return S_PRESENT_OCCLUDED on current drivers.
        Require(SetWindowPos(value,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW)!=FALSE,"show harness window");
        UpdateWindow(value);
        MSG message{}; while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
    }
    ~Window() { if(value) DestroyWindow(value); }
};
void Identity(IUnknown* a,IUnknown* b) {
    ComPtr<IUnknown> x,y;
    Check(a->QueryInterface(IID_PPV_ARGS(&x)),"identity A");
    Check(b->QueryInterface(IID_PPV_ARGS(&y)),"identity B");
    Require(x.Get()==y.Get(),"COM identity mismatch");
}
struct Vertex { float x,y,z; DWORD color; float u,v; };
const std::array<Vertex,3> vertices={{{-.8f,-.7f,.5f,0xffffffff,0,1},{0,.8f,.5f,0xffffffff,.5f,0},{.8f,-.7f,.5f,0xffffffff,1,1}}};
const WORD indices[]={0,1,2};
constexpr DWORD fvf=D3DFVF_XYZ|D3DFVF_DIFFUSE|D3DFVF_TEX1;
struct Scene {
    ComPtr<IDirect3DVertexBuffer9> vb;
    ComPtr<IDirect3DIndexBuffer9> ib;
    ComPtr<IDirect3DTexture9> texture;
    ComPtr<IDirect3DStateBlock9> block;
    ComPtr<IDirect3DVertexShader9> vs;
    ComPtr<IDirect3DPixelShader9> ps;
};
Scene CreateScene(IDirect3DDevice9* device,bool fixture=false) {
    Scene s;
    Check(device->CreateVertexBuffer(sizeof(vertices),D3DUSAGE_DYNAMIC|D3DUSAGE_WRITEONLY,fvf,D3DPOOL_DEFAULT,&s.vb,nullptr),"vertex buffer");
    const DWORD wideIndices[]={99,99,2,3,4};
    Check(device->CreateIndexBuffer(fixture?sizeof(wideIndices):sizeof(indices),D3DUSAGE_DYNAMIC|D3DUSAGE_WRITEONLY,fixture?D3DFMT_INDEX32:D3DFMT_INDEX16,D3DPOOL_DEFAULT,&s.ib,nullptr),"index buffer");
    void* data{};
    Check(s.vb->Lock(0,0,&data,D3DLOCK_DISCARD),"vertex lock"); memcpy(data,vertices.data(),sizeof(vertices)); Check(s.vb->Unlock(),"vertex unlock");
    Check(s.ib->Lock(0,0,&data,D3DLOCK_DISCARD),"index lock");
    if(fixture) memcpy(data,wideIndices,sizeof(wideIndices)); else memcpy(data,indices,sizeof(indices));
    Check(s.ib->Unlock(),"index unlock");
    Check(device->CreateTexture(2,2,1,D3DUSAGE_DYNAMIC,D3DFMT_A8R8G8B8,D3DPOOL_DEFAULT,&s.texture,nullptr),"texture");
    ComPtr<IDirect3DDevice9Ex> extended;
    if(SUCCEEDED(device->QueryInterface(IID_PPV_ARGS(&extended)))) {
        IDirect3DResource9* resources[]={s.vb.Get(),s.texture.Get()};
        Check(extended->CheckResourceResidency(resources,2),"resource array unwrapping");
    }
    D3DLOCKED_RECT locked{};
    Check(s.texture->LockRect(0,&locked,nullptr,D3DLOCK_DISCARD),"texture lock");
    const DWORD colors[4]={0xffff4040,0xff40ff40,0xff4040ff,0xffffffff};
    memcpy(locked.pBits,colors,8); memcpy(static_cast<char*>(locked.pBits)+locked.Pitch,colors+2,8);
    Check(s.texture->UnlockRect(0),"texture unlock");

    ComPtr<IDirect3DDevice9> owner; Check(s.vb->GetDevice(&owner),"buffer owner"); Identity(device,owner.Get());
    ComPtr<IDirect3DResource9> resource; Check(s.texture.As(&resource),"resource QI");
    Identity(s.texture.Get(),resource.Get());
    ComPtr<IDirect3DSurface9> level; Check(s.texture->GetSurfaceLevel(0,&level),"texture level");
    ComPtr<IDirect3DTexture9> container; Check(level->GetContainer(IID_PPV_ARGS(&container)),"surface container");
    Identity(s.texture.Get(),container.Get());
    D3DMATRIX identity{}; identity._11=identity._22=identity._33=identity._44=1;
    Check(device->SetTransform(D3DTS_WORLD,&identity),"world");
    Check(device->SetTransform(D3DTS_VIEW,&identity),"view");
    Check(device->SetTransform(D3DTS_PROJECTION,&identity),"projection");
    Check(device->SetFVF(fvf),"FVF");
    Check(device->SetRenderState(D3DRS_LIGHTING,FALSE),"lighting");
    Check(device->SetRenderState(D3DRS_ZENABLE,FALSE),"z");
    Check(device->SetRenderState(D3DRS_CULLMODE,D3DCULL_NONE),"cull");
    Check(device->SetTextureStageState(0,D3DTSS_COLOROP,D3DTOP_MODULATE),"color op");
    Check(device->SetTextureStageState(0,D3DTSS_COLORARG1,D3DTA_TEXTURE),"color arg");
    Check(device->SetTextureStageState(0,D3DTSS_COLORARG2,D3DTA_DIFFUSE),"color arg2");
    Check(device->SetSamplerState(0,D3DSAMP_MINFILTER,D3DTEXF_POINT),"min filter");
    Check(device->SetSamplerState(0,D3DSAMP_MAGFILTER,D3DTEXF_POINT),"mag filter");
    Check(device->SetTexture(0,s.texture.Get()),"texture bind");
    Check(device->SetStreamSource(0,s.vb.Get(),0,sizeof(Vertex)),"stream");
    Check(device->SetIndices(s.ib.Get()),"indices");
    ComPtr<IDirect3DBaseTexture9> bound; Check(device->GetTexture(0,&bound),"get texture"); Identity(bound.Get(),s.texture.Get());
    Check(device->CreateStateBlock(D3DSBT_ALL,&s.block),"state block");
    Check(device->SetRenderState(D3DRS_CULLMODE,D3DCULL_CW),"modify state");
    Check(s.block->Apply(),"state restore");
    DWORD cull{}; Check(device->GetRenderState(D3DRS_CULLMODE,&cull),"get state"); Require(cull==D3DCULL_NONE,"state block did not restore");
    const char* shader=R"(
        sampler tex : register(s0);
        struct V { float4 p:POSITION; float4 c:COLOR0; float2 uv:TEXCOORD0; };
        V vsMain(float4 p:POSITION,float4 c:COLOR0,float2 uv:TEXCOORD0) { V o; o.p=p; o.c=c; o.uv=uv; return o; }
        float4 psMain(V input):COLOR0 { return tex2D(tex,input.uv)*input.c; }
    )";
    ComPtr<ID3DBlob> vsCode,psCode,errors;
    Check(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"vsMain","vs_3_0",0,0,&vsCode,&errors),"compile VS");
    Check(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"psMain","ps_3_0",0,0,&psCode,&errors),"compile PS");
    Check(device->CreateVertexShader(static_cast<DWORD*>(vsCode->GetBufferPointer()),&s.vs),"VS");
    Check(device->CreatePixelShader(static_cast<DWORD*>(psCode->GetBufferPointer()),&s.ps),"PS");
    return s;
}
std::uint64_t Pixels(IDirect3DDevice9* device,std::vector<unsigned char>& pixels) {
    ComPtr<IDirect3DSurface9> target,readback;
    Check(device->GetRenderTarget(0,&target),"render target");
    D3DSURFACE_DESC desc{}; Check(target->GetDesc(&desc),"surface description");
    Check(device->CreateOffscreenPlainSurface(desc.Width,desc.Height,desc.Format,D3DPOOL_SYSTEMMEM,&readback,nullptr),"readback surface");
    Check(device->GetRenderTargetData(target.Get(),readback.Get()),"readback");
    D3DLOCKED_RECT locked{}; Check(readback->LockRect(&locked,nullptr,D3DLOCK_READONLY),"readback lock");
    std::uint64_t hash=14695981039346656037ull;
    for(UINT y=0;y<desc.Height;++y) {
        const auto* row=static_cast<const unsigned char*>(locked.pBits)+y*locked.Pitch;
        for(UINT x=0;x<desc.Width;++x) for(int channel=0;channel<3;++channel) {
            const auto b=row[4*x+channel]; hash=(hash^b)*1099511628211ull; pixels.push_back(b);
        }
    }
    Check(readback->UnlockRect(),"readback unlock");
    return hash;
}
void ClearBindings(IDirect3DDevice9* d) {
    Check(d->SetTexture(0,nullptr),"unbind texture"); Check(d->SetStreamSource(0,nullptr,0,0),"unbind stream");
    Check(d->SetIndices(nullptr),"unbind index"); Check(d->SetVertexShader(nullptr),"unbind VS");
    Check(d->SetPixelShader(nullptr),"unbind PS");
}
void Run(HMODULE module,bool ex,unsigned frames,const std::filesystem::path& pixelPath,bool fixture,unsigned readFrame,const std::wstring& sceneCase) {
    Window window;
    ComPtr<IDirect3D9> factory;
    ComPtr<IDirect3D9Ex> factoryEx;
    if(ex) {
        const auto create=reinterpret_cast<HRESULT(WINAPI*)(UINT,IDirect3D9Ex**)>(GetProcAddress(module,"Direct3DCreate9Ex"));
        Require(create!=nullptr,"Ex export missing"); Check(create(D3D_SDK_VERSION,&factoryEx),"create9Ex"); Check(factoryEx.As(&factory),"base factory");
    } else {
        const auto create=reinterpret_cast<IDirect3D9*(WINAPI*)(UINT)>(GetProcAddress(module,"Direct3DCreate9"));
        Require(create!=nullptr,"factory export missing"); factory.Attach(create(D3D_SDK_VERSION)); Require(factory!=nullptr,"create9");
    }
    D3DPRESENT_PARAMETERS pp{};
    pp.Windowed=TRUE; pp.SwapEffect=D3DSWAPEFFECT_DISCARD; pp.BackBufferFormat=D3DFMT_X8R8G8B8;
    pp.BackBufferWidth=256; pp.BackBufferHeight=192; pp.hDeviceWindow=window.value; pp.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE;
    ComPtr<IDirect3DDevice9> device;
    ComPtr<IDirect3DDevice9Ex> deviceEx;
    if(ex) {
        Check(factoryEx->CreateDeviceEx(0,D3DDEVTYPE_HAL,window.value,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&pp,nullptr,&deviceEx),"create device Ex");
        Check(deviceEx.As(&device),"base device");
    } else Check(factory->CreateDevice(0,D3DDEVTYPE_HAL,window.value,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&pp,&device),"create device");
    {
        ComPtr<IDirect3D9> returned; Check(device->GetDirect3D(&returned),"get factory"); Identity(factory.Get(),returned.Get());
        ComPtr<IDirect3DSurface9> invalid;
        Require(FAILED(device->GetBackBuffer(99,0,D3DBACKBUFFER_TYPE_MONO,&invalid)),"invalid get-backbuffer succeeded");
        GUID unknown={0x12532fa9,0x1337,0x4321,{0,1,2,3,4,5,6,7}};
        void* output=reinterpret_cast<void*>(1); Require(device->QueryInterface(unknown,&output)==E_NOINTERFACE && !output,"QI failure contract");
    }
    std::vector<unsigned char> pixels;
    std::vector<std::uint64_t> hashes;
    auto scene=CreateScene(device.Get(),fixture);
    ComPtr<IDirect3DSwapChain9> swapchain; Check(device->GetSwapChain(0,&swapchain),"swap chain");
    {
        ComPtr<IDirect3DDevice9> returned; Check(swapchain->GetDevice(&returned),"swap owner"); Identity(device.Get(),returned.Get());
    }
    for(unsigned frame=0;frame<frames;++frame) {
        MSG msg{}; while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
        if(frame==frames/2) {
            ClearBindings(device.Get()); scene=Scene{}; swapchain.Reset();
            pp.BackBufferWidth=320; pp.BackBufferHeight=240;
            auto invalid=pp; invalid.SwapEffect=static_cast<D3DSWAPEFFECT>(0);
            const HRESULT badReset=ex?deviceEx->ResetEx(&invalid,nullptr):device->Reset(&invalid);
            Require(badReset==D3DERR_INVALIDCALL,"invalid reset did not fail as expected");
            if(ex) Check(deviceEx->ResetEx(&pp,nullptr),"ResetEx");
            else Check(device->Reset(&pp),"Reset");
            scene=CreateScene(device.Get(),fixture); Check(device->GetSwapChain(0,&swapchain),"swap after reset");
        }
        if(fixture) {
            // Partial buffer updates retain the untouched bytes from the initial
            // full lock. Change content every frame to detect stale snapshots.
            void* data{}; const DWORD color=0xff80ffffu|(frame*11u<<16);
            Check(scene.vb->Lock(offsetof(Vertex,color),sizeof(color),&data,0),"partial vertex lock");
            memcpy(data,&color,sizeof(color)); Check(scene.vb->Unlock(),"partial vertex unlock");
            Check(device->SetRenderState(D3DRS_SCISSORTESTENABLE,FALSE),"disable scissor");
            if(sceneCase==L"partial-discard") {
                // Deliberately initialize only one vertex after DISCARD. The
                // capture must reject the undefined remainder, never reuse it.
                Check(scene.vb->Lock(0,sizeof(Vertex),&data,D3DLOCK_DISCARD),"partial discard");
                memcpy(data,vertices.data(),sizeof(Vertex)); Check(scene.vb->Unlock(),"partial discard unlock");
            }
            if(sceneCase==L"wireframe") Check(device->SetRenderState(D3DRS_FILLMODE,D3DFILL_WIREFRAME),"wireframe negative case");
        }
        if(sceneCase!=L"no-clear") Check(device->Clear(0,nullptr,D3DCLEAR_TARGET,0xff142850,1,0),"clear");
        Check(device->BeginScene(),"begin");
        Check(device->SetStreamSource(0,scene.vb.Get(),0,sizeof(Vertex)),"stream per frame");
        Check(device->SetIndices(scene.ib.Get()),"indices per frame");
        if(fixture) {
            auto world=[&](float x,float y) { D3DMATRIX m{}; m._11=m._22=.45f; m._33=m._44=1; m._41=x; m._42=y; Check(device->SetTransform(D3DTS_WORLD,&m),"fixture world"); };
            auto texel=[&](DWORD color) {
                RECT box{0,0,1,1}; D3DLOCKED_RECT locked{}; Check(scene.texture->LockRect(0,&locked,&box,0),"partial texel lock");
                memcpy(locked.pBits,&color,4); Check(scene.texture->UnlockRect(0),"partial texel unlock");
            };
            texel(0xff2020ffu+frame*0x00100000u);
            if(sceneCase==L"surface-write") {
                ComPtr<IDirect3DSurface9> alias; Check(scene.texture->GetSurfaceLevel(0,&alias),"write alias");
                D3DLOCKED_RECT locked{}; Check(alias->LockRect(&locked,nullptr,0),"surface write lock");
                const DWORD color=0xff008080; memcpy(locked.pBits,&color,4); Check(alias->UnlockRect(),"surface write unlock");
            }
            world(-.5f,-.5f); Check(device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,-2,2,3,2,1),"fixture indexed32 negative base");
            texel(0xffffff20u-frame*0x00100000u);
            world(-.5f,.5f); Check(device->DrawPrimitive(D3DPT_TRIANGLELIST,0,1),"fixture nonindexed");
            world(.5f,.5f); Check(device->DrawPrimitiveUP(D3DPT_TRIANGLELIST,1,vertices.data(),sizeof(Vertex)),"fixture UP");
            world(.5f,-.5f);
            RECT scissor{LONG(pp.BackBufferWidth/2),LONG(pp.BackBufferHeight/2),LONG(pp.BackBufferWidth*7/8),LONG(pp.BackBufferHeight)};
            Check(device->SetScissorRect(&scissor),"fixture scissor"); Check(device->SetRenderState(D3DRS_SCISSORTESTENABLE,TRUE),"fixture enable scissor");
            Check(device->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST,0,3,1,indices,D3DFMT_INDEX16,vertices.data(),sizeof(Vertex)),"fixture indexed UP16");
            if(sceneCase==L"draw-budget" && frame==0) for(UINT i=0;i<4097;++i)
                Check(device->DrawPrimitiveUP(D3DPT_TRIANGLELIST,1,vertices.data(),sizeof(Vertex)),"draw budget probe");
        } else {
        Check(device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,0,3,0,1),"fixed draw");
        Check(device->SetVertexShader(scene.vs.Get()),"bind VS"); Check(device->SetPixelShader(scene.ps.Get()),"bind PS");
        Check(device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,0,3,0,1),"shader draw");
        Check(device->SetVertexShader(nullptr),"clear VS"); Check(device->SetPixelShader(nullptr),"clear PS");
        Check(device->DrawPrimitiveUP(D3DPT_TRIANGLELIST,1,vertices.data(),sizeof(Vertex)),"UP draw");
        }
        Check(device->EndScene(),"end");
        if((readFrame==UINT_MAX && (frame==0 || frame==frames/2)) || frame==readFrame) hashes.push_back(Pixels(device.Get(),pixels));
        HRESULT presented=S_PRESENT_OCCLUDED;
        const auto deadline=GetTickCount64()+3000;
        do {
            if(frame%2) presented=swapchain->Present(nullptr,nullptr,nullptr,nullptr,0);
            else if(ex) presented=deviceEx->PresentEx(nullptr,nullptr,nullptr,nullptr,0);
            else presented=device->Present(nullptr,nullptr,nullptr,nullptr);
            Check(presented,"present");
            if(presented!=S_PRESENT_OCCLUDED) break;
            // Allow the compositor to notice the newly shown/reset window.
            // Retry presentation only; do not submit duplicate fixture draws.
            MsgWaitForMultipleObjects(0,nullptr,FALSE,16,QS_ALLINPUT);
            MSG pending{}; while(PeekMessageW(&pending,nullptr,0,0,PM_REMOVE)) { TranslateMessage(&pending); DispatchMessageW(&pending); }
        } while(GetTickCount64()<deadline);
        Require(presented==S_OK,"harness presentation unavailable (occluded or non-S_OK)");
    }
    // Resource-held native references must survive loss/recreation of the public
    // device wrapper. GetDevice must re-enter observation without a raw escape.
    swapchain.Reset(); deviceEx.Reset(); device.Reset();
    Check(scene.vb->GetDevice(&device),"recover device from live resource");
    ClearBindings(device.Get()); scene=Scene{};
    if(!pixelPath.empty()) {
        std::ofstream out(pixelPath,std::ios::binary); out.write(reinterpret_cast<const char*>(pixels.data()),pixels.size()); Require(out.good(),"pixel output");
    }
    std::printf("{\"frames\":%u,\"resets\":1,\"mode\":\"%s\",\"hashes\":[",frames,ex?"ex":"classic");
    for(std::size_t i=0;i<hashes.size();++i) std::printf("%s\"%016llx\"",i?",":"",hashes[i]);
    std::puts("]}");
}
}
int wmain(int argc,wchar_t** argv) {
    std::wstring runtime=L"proxy",sceneCase; bool ex=false,fixture=false; unsigned frames=12,readFrame=UINT_MAX; std::filesystem::path output;
    for(int i=1;i<argc;++i) {
        const std::wstring arg=argv[i];
        if(arg==L"--help") { std::puts("--runtime system|PATH_TO_PROXY --ex --frames N --pixels PATH --scene-fixture --read-frame N --scene-case surface-write|partial-discard|wireframe|no-clear|draw-budget"); return 0; }
        if(arg==L"--runtime" && i+1<argc) runtime=argv[++i];
        else if(arg==L"--ex") ex=true;
        else if(arg==L"--scene-fixture") fixture=true;
        else if(arg==L"--scene-case" && i+1<argc) { sceneCase=argv[++i]; fixture=true; }
        else if(arg==L"--read-frame" && i+1<argc) readFrame=wcstoul(argv[++i],nullptr,10);
        else if(arg==L"--frames" && i+1<argc) frames=wcstoul(argv[++i],nullptr,10);
        else if(arg==L"--pixels" && i+1<argc) output=argv[++i];
        else { std::fputs("Invalid arguments\n",stderr); return 2; }
    }
    if(frames<2 || frames>10000 || (readFrame!=UINT_MAX && readFrame>=frames)) return 2;
    if(!sceneCase.empty() && sceneCase!=L"surface-write" && sceneCase!=L"partial-discard" && sceneCase!=L"wireframe" && sceneCase!=L"no-clear" && sceneCase!=L"draw-budget") return 2;
    HMODULE module{};
    try {
        wchar_t path[32768]{};
        if(runtime==L"system") {
            Require(GetSystemDirectoryW(path,32768)!=0,"system directory"); wcscat_s(path,L"\\d3d9.dll");
        } else if(runtime==L"proxy") {
            Require(GetModuleFileNameW(nullptr,path,32768)!=0,"module path");
            wcscpy_s(path,(std::filesystem::path(path).parent_path()/L"d3d9.dll").c_str());
        } else wcscpy_s(path,std::filesystem::absolute(runtime).c_str());
        module=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        Require(module!=nullptr,"runtime load");
        const bool marker=GetProcAddress(module,"RRTProxyVersion")!=nullptr;
        Require(marker==(runtime!=L"system"),"loaded unexpected D3D9 provider");
        Run(module,ex,frames,output,fixture,readFrame,sceneCase);
        if(auto finish=reinterpret_cast<void(WINAPI*)()>(GetProcAddress(module,"RRTFinishTrace"))) finish();
        // Retain module to process exit after every COM reference has been released.
        return 0;
    } catch(const std::exception& e) { std::fprintf(stderr,"%s\n",e.what()); return 1; }
}
