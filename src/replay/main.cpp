#include "../scene/scene.h"
#include <wrl/client.h>
#include <cstdio>
#include <cstring>
#include <stdexcept>

using Microsoft::WRL::ComPtr;
namespace {
void Check(HRESULT hr,const char* what) { if(FAILED(hr)) { char text[200]; sprintf_s(text,"%s: 0x%08lx",what,static_cast<unsigned long>(hr)); throw std::runtime_error(text); } }
LRESULT CALLBACK Procedure(HWND w,UINT m,WPARAM a,LPARAM b) {
    if(m==WM_DESTROY) { PostQuitMessage(0); return 0; } return DefWindowProcW(w,m,a,b);
}
struct Window {
    HWND handle{};
    Window(UINT width,UINT height,bool show) {
        WNDCLASSW c{}; c.lpfnWndProc=Procedure; c.hInstance=GetModuleHandleW(nullptr); c.lpszClassName=L"RRTReplay";
        if(!RegisterClassW(&c) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) throw std::runtime_error("window class");
        RECT rect{0,0,LONG(width),LONG(height)}; AdjustWindowRect(&rect,WS_OVERLAPPEDWINDOW,FALSE);
        handle=CreateWindowW(c.lpszClassName,L"Radeon RT Remaster - captured scene replay",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,rect.right-rect.left,rect.bottom-rect.top,nullptr,nullptr,c.hInstance,nullptr);
        if(!handle) throw std::runtime_error("window creation"); if(show) ShowWindow(handle,SW_SHOW);
    }
    ~Window() { if(IsWindow(handle)) DestroyWindow(handle); }
};
void Report(const rrt::scene::Scene& s) {
    std::printf("{\"version\":1,\"frame\":%u,\"width\":%u,\"height\":%u,\"attempted\":%u,\"complete\":%s,\"draws\":[",s.frame,s.width,s.height,s.attempted,s.rejected.empty()?"true":"false");
    bool comma=false;
    for(auto& d:s.draws) {
        std::printf("%s{\"ordinal\":%u,\"vertices\":%zu,\"triangles\":%zu,\"mesh_id\":\"%s\",\"texture_id\":\"%s\",\"material_id\":\"%s\"}",comma?",":"",d.ordinal,d.vertices.size(),d.indices.size()/3,rrt::scene::Hex(d.meshId).c_str(),rrt::scene::Hex(d.textureId).c_str(),rrt::scene::Hex(d.materialId).c_str()); comma=true;
    }
    std::printf("],\"rejected\":["); comma=false;
    for(auto& r:s.rejected) { std::printf("%s{\"ordinal\":%u,\"reason\":\"%s\"}",comma?",":"",r.ordinal,rrt::scene::ReasonName(r.reason)); comma=true; }
    std::printf("]}\n");
}
void Pixels(IDirect3DDevice9* d,const std::filesystem::path& path) {
    ComPtr<IDirect3DSurface9> rt,readback; Check(d->GetRenderTarget(0,&rt),"target"); D3DSURFACE_DESC desc{}; Check(rt->GetDesc(&desc),"description");
    Check(d->CreateOffscreenPlainSurface(desc.Width,desc.Height,desc.Format,D3DPOOL_SYSTEMMEM,&readback,nullptr),"readback surface");
    Check(d->GetRenderTargetData(rt.Get(),readback.Get()),"readback"); D3DLOCKED_RECT lock{}; Check(readback->LockRect(&lock,nullptr,D3DLOCK_READONLY),"readback lock");
    std::vector<std::uint8_t> bytes(std::size_t(desc.Width)*desc.Height*3);
    for(UINT y=0;y<desc.Height;++y) for(UINT x=0;x<desc.Width;++x) memcpy(bytes.data()+(std::size_t(y)*desc.Width+x)*3,static_cast<const std::uint8_t*>(lock.pBits)+std::size_t(y)*lock.Pitch+x*4,3);
    Check(readback->UnlockRect(),"readback unlock");
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE) throw std::runtime_error("pixel output exists or path unavailable");
    DWORD written{}; bool ok=WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr) && written==bytes.size(); CloseHandle(file);
    if(!ok) throw std::runtime_error("pixel output failed");
}
void Render(const rrt::scene::Scene& scene,const std::filesystem::path& pixels,bool show,unsigned limit) {
    wchar_t path[32768]{}; if(!GetSystemDirectoryW(path,32768)) throw std::runtime_error("system directory"); wcscat_s(path,L"\\d3d9.dll");
    // Never resolve the capture proxy through executable-directory DLL search.
    HMODULE module=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32); if(!module || GetProcAddress(module,"RRTProxyVersion")) throw std::runtime_error("system D3D9 load failed");
    auto create=reinterpret_cast<IDirect3D9*(WINAPI*)(UINT)>(GetProcAddress(module,"Direct3DCreate9")); if(!create) throw std::runtime_error("D3D9 export missing");
    ComPtr<IDirect3D9> factory; factory.Attach(create(D3D_SDK_VERSION)); if(!factory) throw std::runtime_error("D3D9 creation failed");
    Window window(scene.width,scene.height,show);
    D3DPRESENT_PARAMETERS pp{}; pp.Windowed=TRUE; pp.SwapEffect=D3DSWAPEFFECT_COPY; pp.BackBufferFormat=D3DFMT_X8R8G8B8;
    pp.BackBufferWidth=scene.width; pp.BackBufferHeight=scene.height; pp.hDeviceWindow=window.handle; pp.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE;
    ComPtr<IDirect3DDevice9> device; Check(factory->CreateDevice(0,D3DDEVTYPE_HAL,window.handle,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&pp,&device),"device");
    Check(device->Clear(0,nullptr,D3DCLEAR_TARGET,scene.clearColor,1,0),"clear"); Check(device->BeginScene(),"begin");
    Check(device->SetFVF(rrt::scene::Fvf),"FVF"); Check(device->SetTextureStageState(1,D3DTSS_COLOROP,D3DTOP_DISABLE),"disable stage one");
    unsigned count=0;
    for(auto& draw:scene.draws) {
        if(count++>=limit) break;
        ComPtr<IDirect3DTexture9> texture;
        Check(device->CreateTexture(draw.width,draw.height,1,0,D3DFMT_A8R8G8B8,D3DPOOL_MANAGED,&texture,nullptr),"texture");
        D3DLOCKED_RECT lock{}; Check(texture->LockRect(0,&lock,nullptr,0),"texture lock");
        for(UINT y=0;y<draw.height;++y) memcpy(static_cast<std::uint8_t*>(lock.pBits)+std::size_t(y)*lock.Pitch,draw.texture.data()+std::size_t(y)*draw.width*4,draw.width*4);
        Check(texture->UnlockRect(0),"texture unlock"); Check(device->SetTexture(0,texture.Get()),"bind texture");
        auto& s=draw.state;
        Check(device->SetTransform(D3DTS_WORLD,&s.world),"world"); Check(device->SetTransform(D3DTS_VIEW,&s.view),"view"); Check(device->SetTransform(D3DTS_PROJECTION,&s.projection),"projection");
        Check(device->SetViewport(&s.viewport),"viewport"); Check(device->SetScissorRect(&s.scissor),"scissor");
        for(std::size_t i=0;i<s.render.size();++i) Check(device->SetRenderState(rrt::scene::RenderStates[i],s.render[i]),"render state");
        for(std::size_t i=0;i<s.texture.size();++i) Check(device->SetTextureStageState(0,rrt::scene::TextureStates[i],s.texture[i]),"texture state");
        for(std::size_t i=0;i<s.sampler.size();++i) Check(device->SetSamplerState(0,rrt::scene::SamplerStates[i],s.sampler[i]),"sampler state");
        Check(device->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST,0,static_cast<UINT>(draw.vertices.size()),static_cast<UINT>(draw.indices.size()/3),draw.indices.data(),D3DFMT_INDEX32,draw.vertices.data(),sizeof(rrt::scene::Vertex)),"replay draw");
    }
    Check(device->EndScene(),"end"); if(!pixels.empty()) Pixels(device.Get(),pixels);
    Check(device->Present(nullptr,nullptr,nullptr,nullptr),"present");
    if(show) { MSG msg{}; while(GetMessageW(&msg,nullptr,0,0)>0) { TranslateMessage(&msg); DispatchMessageW(&msg); if(IsWindow(window.handle)) device->Present(nullptr,nullptr,nullptr,nullptr); } }
}
}
int wmain(int argc,wchar_t** argv) {
    try {
        std::filesystem::path input,pixels; bool show=false,partial=false,inspect=false; unsigned limit=UINT_MAX;
        for(int i=1;i<argc;++i) {
            std::wstring arg=argv[i];
            if(arg==L"--help") { std::puts("rrt_replay SCENE --inspect | [--pixels NEW_FILE] [--show] [--allow-partial] [--draw-count N]"); return 0; }
            if(arg==L"--pixels" && i+1<argc) pixels=argv[++i];
            else if(arg==L"--show") show=true;
            else if(arg==L"--allow-partial") partial=true;
            else if(arg==L"--inspect") inspect=true;
            else if(arg==L"--draw-count" && i+1<argc) { wchar_t* end{}; auto n=wcstoul(argv[++i],&end,10); if(*end || n>rrt::scene::MaxDraws) throw std::runtime_error("invalid draw count"); limit=n; }
            else if(input.empty() && !arg.starts_with(L"--")) input=arg;
            else throw std::runtime_error("invalid arguments");
        }
        if(input.empty()) throw std::runtime_error("scene path required; use --help");
        auto scene=rrt::scene::Load(input); Report(scene);
        if(!inspect) {
            if(!scene.rejected.empty() && !partial) throw std::runtime_error("incomplete scene; inspect rejection reasons or explicitly use --allow-partial");
            Render(scene,pixels,show,limit);
        }
        return 0;
    } catch(const std::exception& e) { std::fprintf(stderr,"%s\n",e.what()); return 2; }
}
