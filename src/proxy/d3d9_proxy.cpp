#include <windows.h>
#include <d3d9.h>
#include <mutex>
#include "observers.h"
#include "../trace/trace.h"

namespace {
HMODULE NativeRuntime() noexcept {
    static std::once_flag once;
    static HMODULE module{};
    try { std::call_once(once, [] {
        wchar_t path[MAX_PATH]{};
        const UINT length=GetSystemDirectoryW(path,MAX_PATH);
        if(!length || length+10>=MAX_PATH) return;
        wcscat_s(path,L"\\d3d9.dll");
        module=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(!module) OutputDebugStringA("RRT: system D3D9 load failed\n");
        // Process lifetime: native resource references can outlive factories.
    }); } catch(...) {}
    return module;
}
template<class T> T Resolve(const char* name) noexcept {
    const auto module=NativeRuntime();
    return module?reinterpret_cast<T>(GetProcAddress(module,name)):nullptr;
}
bool Disabled() noexcept {
    wchar_t value[8]{};
    return GetEnvironmentVariableW(L"RRT_PROXY_DISABLE",value,8)==1 && value[0]==L'1';
}
}
extern "C" IDirect3D9* WINAPI Direct3DCreate9(UINT version) {
    const auto fn=Resolve<decltype(&Direct3DCreate9)>("Direct3DCreate9");
    if(!fn) return nullptr;
    auto* result=fn(version);
    if(!result || Disabled()) return result;
    if(FAILED(rrt::WrapReturned(__uuidof(IDirect3D9),reinterpret_cast<void**>(&result)))) return nullptr;
    rrt::Event(rrt::ObjectId(result),"Direct3DCreate9",S_OK);
    return result;
}
extern "C" HRESULT WINAPI Direct3DCreate9Ex(UINT version, IDirect3D9Ex** output) {
    const auto fn=Resolve<decltype(&Direct3DCreate9Ex)>("Direct3DCreate9Ex");
    if(!fn) { if(output) *output=nullptr; return D3DERR_NOTAVAILABLE; }
    HRESULT result=fn(version,output);
    if(SUCCEEDED(result) && !Disabled()) {
        result=rrt::WrapReturned(__uuidof(IDirect3D9Ex),reinterpret_cast<void**>(output));
        if(SUCCEEDED(result)) rrt::Event(output?rrt::ObjectId(*output):0,"Direct3DCreate9Ex",result);
    }
    return result;
}
extern "C" void WINAPI RRTFinishTrace() { if(!Disabled()) rrt::FinishTrace(); }
extern "C" UINT WINAPI RRTProxyVersion() { return 1; }
extern "C" int WINAPI D3DPERF_BeginEvent(D3DCOLOR color,LPCWSTR name) {
    auto fn=Resolve<decltype(&D3DPERF_BeginEvent)>("D3DPERF_BeginEvent"); return fn?fn(color,name):-1;
}
extern "C" int WINAPI D3DPERF_EndEvent() {
    auto fn=Resolve<decltype(&D3DPERF_EndEvent)>("D3DPERF_EndEvent"); return fn?fn():-1;
}
extern "C" void WINAPI D3DPERF_SetMarker(D3DCOLOR color,LPCWSTR name) {
    auto fn=Resolve<decltype(&D3DPERF_SetMarker)>("D3DPERF_SetMarker"); if(fn) fn(color,name);
}
extern "C" void WINAPI D3DPERF_SetRegion(D3DCOLOR color,LPCWSTR name) {
    auto fn=Resolve<decltype(&D3DPERF_SetRegion)>("D3DPERF_SetRegion"); if(fn) fn(color,name);
}
extern "C" BOOL WINAPI D3DPERF_QueryRepeatFrame() {
    auto fn=Resolve<decltype(&D3DPERF_QueryRepeatFrame)>("D3DPERF_QueryRepeatFrame"); return fn?fn():FALSE;
}
extern "C" void WINAPI D3DPERF_SetOptions(DWORD options) {
    auto fn=Resolve<decltype(&D3DPERF_SetOptions)>("D3DPERF_SetOptions"); if(fn) fn(options);
}
extern "C" DWORD WINAPI D3DPERF_GetStatus() {
    auto fn=Resolve<decltype(&D3DPERF_GetStatus)>("D3DPERF_GetStatus"); return fn?fn():0;
}
// No locks, allocation, logging, file I/O or library loads under the loader lock.
BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
