// Standalone FidelityFX Radiance Cache context research; never a renderer hook.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <array>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <fstream>
#include <bcrypt.h>
#include <ffx_api_loader.h>
#include <dx12/ffx_api_dx12.h>
#include <ffx_radiancecache.h>

static_assert(FFX_RADIANCECACHE_VERSION_MAJOR==0 && FFX_RADIANCECACHE_VERSION_MINOR==9 && FFX_RADIANCECACHE_VERSION_PATCH==0,
              "Review the RC probe contract before changing the SDK version");
using Microsoft::WRL::ComPtr;
namespace {
constexpr UINT InferenceSamples=128*96;
constexpr UINT TrainingSamples=512;
void Require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
std::string QuoteBytes(const std::string& value) {
    std::ostringstream out; out << '"';
    for(const unsigned char c:value) {
        if(c=='"'||c=='\\') out << '\\' << c;
        else if(c<32) { const char hex[]="0123456789abcdef"; out << "\\u00" << hex[c>>4] << hex[c&15]; }
        else out << c;
    }
    out << '"'; return out.str();
}
std::string Quote(const char* value) { return QuoteBytes(value?std::string(value):std::string()); }
struct Module {
    HMODULE handle{};
    explicit Module(const std::filesystem::path& path) {
        Require(path.is_absolute()&&std::filesystem::is_regular_file(path),"RC SDK DLL missing or path is not absolute");
        handle=LoadLibraryExW(path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        Require(handle!=nullptr,"RC SDK DLL load failed (architecture, dependency or signature policy)");
    }
    ~Module() { if(handle) FreeLibrary(handle); }
    Module(const Module&)=delete; Module& operator=(const Module&)=delete;
};
UINT BoundedUnsigned(const wchar_t* text,UINT maximum) {
    Require(*text!=0,"unsigned value missing"); UINT result=0;
    for(const wchar_t* p=text;*p;++p) { Require(*p>=L'0'&&*p<=L'9',"expected unsigned decimal value"); result=result*10+UINT(*p-L'0'); Require(result<=maximum,"unsigned value out of range"); }
    return result;
}
struct RcGpuBudget {
    struct Allocation { IUnknown* object{}; uint64_t bytes{}; bool heap{}; };
    static constexpr uint64_t MaximumBytes=256ull*1024*1024;
    static inline RcGpuBudget* active{};
    ID3D12Device* device; uint64_t limit,live{},peak{},attempts{},allocations{},releases{},denials{},errors{},failAt;
    std::array<Allocation,1024> records{}; std::mutex mutex;
    RcGpuBudget(ID3D12Device* gpu,uint64_t bytes,uint64_t failure):device(gpu),limit(bytes),failAt(failure) {
        Require(!active&&bytes>0&&bytes<=MaximumBytes,"invalid or overlapping RC budget scope"); active=this;
    }
    ~RcGpuBudget() { active=nullptr; }
    Allocation* Admit(uint64_t bytes) {
        ++attempts; if((failAt&&attempts==failAt)||!bytes||bytes>limit-live) { ++denials; return nullptr; }
        for(auto& record:records) if(!record.object) return &record; ++denials; return nullptr;
    }
    void Commit(Allocation& record,IUnknown* object,uint64_t bytes,bool heap) { record={object,bytes,heap}; live+=bytes; peak=std::max(peak,live); ++allocations; }
    ffxReturnCode_t Release(IUnknown* object,bool heap,uint64_t offset=0,uint64_t size=0) {
        if(!object) return FFX_API_RETURN_OK;
        for(auto& record:records) if(record.object==object) {
            if(record.heap!=heap||offset||(heap&&size!=record.bytes)) { ++errors; return FFX_API_RETURN_ERROR_PARAMETER; }
            live-=record.bytes; record={}; ++releases; object->Release(); return FFX_API_RETURN_OK;
        }
        ++errors; return FFX_API_RETURN_ERROR_PARAMETER;
    }
    static ffxReturnCode_t Resource(uint32_t,D3D12_RESOURCE_STATES state,const D3D12_HEAP_PROPERTIES* props,const D3D12_RESOURCE_DESC* desc,
                                   const FfxApiResourceDescription*,const D3D12_CLEAR_VALUE* clear,ID3D12Resource** output) noexcept {
        if(output) *output=nullptr; if(!active||!output||!props||!desc) return FFX_API_RETURN_ERROR_PARAMETER;
        try { auto& b=*active; std::lock_guard lock(b.mutex); const auto info=b.device->GetResourceAllocationInfo(0,1,desc); auto* record=b.Admit(info.SizeInBytes);
            if(!record) return FFX_API_RETURN_ERROR_MEMORY; const auto hr=b.device->CreateCommittedResource(props,D3D12_HEAP_FLAG_NONE,desc,state,clear,IID_PPV_ARGS(output));
            if(FAILED(hr)) { ++b.errors; return FFX_API_RETURN_ERROR_RUNTIME_ERROR; } b.Commit(*record,*output,info.SizeInBytes,false); return FFX_API_RETURN_OK;
        } catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t FreeResource(uint32_t,ID3D12Resource* object) noexcept {
        if(!active) return FFX_API_RETURN_ERROR_PARAMETER; try { auto& b=*active; std::lock_guard lock(b.mutex); return b.Release(object,false); } catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t Heap(uint32_t,const D3D12_HEAP_DESC* desc,bool,ID3D12Heap** output,uint64_t* offset) noexcept {
        if(output) *output=nullptr; if(offset) *offset=0; if(!active||!output||!offset||!desc) return FFX_API_RETURN_ERROR_PARAMETER;
        try { auto& b=*active; std::lock_guard lock(b.mutex); auto* record=b.Admit(desc->SizeInBytes); if(!record) return FFX_API_RETURN_ERROR_MEMORY;
            const auto hr=b.device->CreateHeap(desc,IID_PPV_ARGS(output)); if(FAILED(hr)) { ++b.errors; return FFX_API_RETURN_ERROR_RUNTIME_ERROR; }
            b.Commit(*record,*output,desc->SizeInBytes,true); return FFX_API_RETURN_OK;
        } catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t FreeHeap(uint32_t,ID3D12Heap* object,uint64_t offset,uint64_t size) noexcept {
        if(!active) return FFX_API_RETURN_ERROR_PARAMETER; try { auto& b=*active; std::lock_guard lock(b.mutex); return b.Release(object,true,offset,size); } catch(...) { return FFX_API_RETURN_ERROR; }
    }
};
struct RcContextResult {
    const char* result="not-created"; const char* backend="none";
    uint32_t wmmaCode=UINT32_MAX,fallbackCode=UINT32_MAX,providerCode=UINT32_MAX,destroyCode=UINT32_MAX;
    uint64_t requestedProvider{},provider{},budget{},peak{},live{},attempts{},allocations{},releases{},denials{},errors{};
    bool wmmaAttempted{},fallbackAttempted{},created{},destroyed{},passed{};
    std::string Json() const {
        std::ostringstream out;
        out << "{\"result\":" << Quote(result) << ",\"validation\":true,\"hard_budget_enforced\":true"
            << ",\"max_inference_samples\":" << InferenceSamples << ",\"max_training_samples\":" << TrainingSamples
            << ",\"budget_bytes\":" << budget << ",\"wmma_attempted\":" << (wmmaAttempted?"true":"false") << ",\"wmma_create_code\":" << wmmaCode
            << ",\"fallback_attempted\":" << (fallbackAttempted?"true":"false") << ",\"fallback_create_code\":" << fallbackCode
            << ",\"selected_backend\":" << Quote(backend) << ",\"created\":" << (created?"true":"false") << ",\"destroyed\":" << (destroyed?"true":"false")
            << ",\"requested_provider_id\":" << requestedProvider << ",\"provider_query_code\":" << providerCode << ",\"provider_id\":" << provider
            << ",\"destroy_code\":" << destroyCode << ",\"callback_peak_bytes\":" << peak << ",\"callback_live_bytes_after_destroy\":" << live
            << ",\"allocation_attempts\":" << attempts << ",\"allocations\":" << allocations << ",\"releases\":" << releases
            << ",\"allocation_denials\":" << denials << ",\"callback_errors\":" << errors << '}'; return out.str();
    }
};
#include "rc_dispatch.h"
#include "rc_path_sequence.h"
#include "rc_sequence.h"
std::vector<unsigned char> RcReadPathStdin() {
    const HANDLE input=GetStdHandle(STD_INPUT_HANDLE); Require(input&&input!=INVALID_HANDLE_VALUE,"RC stream stdin unavailable");
    std::vector<unsigned char> bytes(RcPathSequenceBytes); size_t offset=0;
    while(offset<bytes.size()) { DWORD count=0; const DWORD request=DWORD(std::min<size_t>(65536,bytes.size()-offset));
        Require(ReadFile(input,bytes.data()+offset,request,&count,nullptr)&&count,"truncated RC stream stdin"); offset+=count; }
    unsigned char extra{}; DWORD count=0; const BOOL eof=ReadFile(input,&extra,1,&count,nullptr);
    Require((eof&&count==0)||(!eof&&GetLastError()==ERROR_BROKEN_PIPE),"oversized RC stream stdin"); return bytes;
}
RcContextResult TestRcContext(ffxFunctions& api,ID3D12Device* device,uint64_t provider,uint64_t budget,uint64_t failAt,bool wave32) {
    RcContextResult result; result.budget=budget; result.requestedProvider=provider;
    ffxOverrideVersion version{}; version.header.type=FFX_API_DESC_TYPE_OVERRIDE_VERSION; version.versionId=provider;
    RcGpuBudget tracked(device,budget,failAt);
    ffxCreateBackendDX12AllocationCallbacksDesc callbacks{}; callbacks.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12_ALLOCATION_CALLBACKS;
    callbacks.pfnFfxResourceAllocator=RcGpuBudget::Resource; callbacks.pfnFfxResourceDeallocator=RcGpuBudget::FreeResource;
    callbacks.pfnFfxHeapAllocator=RcGpuBudget::Heap; callbacks.pfnFfxHeapDeallocator=RcGpuBudget::FreeHeap; callbacks.header.pNext=&version.header;
    ffxCreateBackendDX12Desc backend{}; backend.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12; backend.device=device; backend.header.pNext=&callbacks.header;
    auto create=[&](uint32_t flags,ffxContext& context) {
        ffxCreateContextDescRadianceCache desc{}; desc.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_RADIANCECACHE; desc.header.pNext=&backend.header;
        desc.flags=flags; desc.version=FFX_RADIANCECACHE_VERSION; desc.maxInferenceSampleCount=InferenceSamples; desc.maxTrainingSampleCount=TrainingSamples;
        return api.CreateContext(&context,&desc.header,nullptr);
    };
    ffxContext context{}; result.wmmaAttempted=true; result.wmmaCode=create(FFX_RADIANCE_CACHE_CONTEXT_TRY_FORCE_WMMA,context);
    if(result.wmmaCode==FFX_API_RETURN_OK&&context) result.backend="wmma";
    else if(result.wmmaCode==FFX_API_RETURN_ERROR_PARAMETER&&wave32&&!tracked.live) {
        result.fallbackAttempted=true; result.fallbackCode=create(0,context); if(result.fallbackCode==FFX_API_RETURN_OK&&context) result.backend="reference";
    }
    result.created=context!=nullptr&&((result.wmmaCode==FFX_API_RETURN_OK)||result.fallbackCode==FFX_API_RETURN_OK);
    if(result.created) {
        ffxQueryGetProviderVersion selected{}; selected.header.type=FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
        result.providerCode=api.Query(&context,&selected.header); result.provider=selected.versionId;
        result.destroyCode=api.DestroyContext(&context,nullptr); if(result.destroyCode==FFX_API_RETURN_OK) context=nullptr;
        result.destroyed=!context&&result.destroyCode==FFX_API_RETURN_OK;
    }
    result.peak=tracked.peak; result.live=tracked.live; result.attempts=tracked.attempts; result.allocations=tracked.allocations;
    result.releases=tracked.releases; result.denials=tracked.denials; result.errors=tracked.errors;
    result.passed=result.created&&result.destroyed&&result.providerCode==FFX_API_RETURN_OK&&result.provider==provider&&result.peak>0&&result.peak<=budget
        &&!result.live&&!result.denials&&!result.errors&&result.allocations==result.releases;
    result.result=result.passed?"context-lifecycle-pass":result.created?"context-validation-failed":result.denials?"allocation-rejected":"context-create-failed";
    return result;
}
}
#include "rc_isolation.h"
#include "rc_shared_dispatch.h"
#include "rc_shared_path.h"

int wmain(int argc,wchar_t** argv) {
    try {
        if(argc==3&&std::wstring(argv[1])==L"--isolation-child") return RcIsolationChild(argv[2]);
        if(argc==3&&std::wstring(argv[1])==L"--live-isolation-test") {
            wchar_t executable[32768]{}; const DWORD length=GetModuleFileNameW(nullptr,executable,32768);
            Require(length&&length<32768,"live fixture executable unavailable");
            ComPtr<ID3D12Device> device; ComPtr<ID3D12Fence> fence;
            Require(SUCCEEDED(D3D12CreateDevice(nullptr,D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device))),"live fixture device unavailable");
            Require(SUCCEEDED(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence))),"live fixture fence unavailable");
            RcIsolatedSession session({L"--isolation-child",argv[2]}, {}, executable);
            std::string failure;
            try { session.WaitFence(fence.Get(),1,std::wstring(argv[2])==L"timeout"?100u:5000u); }
            catch(const std::exception& e) { failure=e.what(); }
            const auto result=session.Finish(5000);
            std::cout << "{\"wait_error\":" << QuoteBytes(failure) << ",\"worker\":" << result.Json() << "}\n"; return 0;
        }
        if(argc==3&&std::wstring(argv[1])==L"--isolation-test") {
            if(std::wstring(argv[2])==L"parent-exit") { RcRunIsolated({L"--isolation-child",L"timeout"},30000,true); return 1; }
            const auto result=RcRunIsolated({L"--isolation-child",argv[2]},std::wstring(argv[2])==L"timeout"?100u:30000u);
            std::cout << result.Json() << '\n'; return 0;
        }
        std::filesystem::path directory,pathSequence,sharedPathSequence; UINT adapterIndex=0,cycles=1,budgetMiB=32,failAt=0,trainingBatches=1,timeoutMs=30000;
        bool debug=false,contextTest=false,dispatchTest=false,sequenceTest=false,sharedTest=false,sharedChild=false,sharedPathTest=false,sharedPathChild=false,sharedStreamOption=false,combinedDispatch=true,isolated=false,child=false,contextOption=false,dispatchModeOption=false,trainingOption=false,pathOption=false,streamOption=false;
        std::array<uint64_t,8> sharedValues{};
        std::array<uint64_t,13> sharedPathValues{};
        std::wstring sessionCommands;
        for(int i=1;i<argc;++i) {
            const std::wstring arg=argv[i];
            if(arg==L"--help") { std::cout << "rrt_rc_probe --sdk-bin ABSOLUTE_DIRECTORY [--adapter 0] [--debug] [--context-test|--isolated-context|--dispatch-test|--isolated-dispatch|--sequence-test|--isolated-sequence|--isolated-stream-sequence|--shared-dispatch|--shared-path-sequence ABSOLUTE_RCRPATH1|--shared-stream-sequence] [--path-sequence ABSOLUTE_RCRPATH1] [--dispatch-mode inference|combined] [--training-batches 1..8] [--cycles 1..3] [--budget-mib 1..256] [--fail-allocation 1..255] [--worker-timeout-ms 1..60000]]\nDefault: enumerate Radiance Cache 0.9 providers. Shared path/stream modes retain one contained provider context across renderer-fixture training while the five external buffers cross by same-adapter handles.\n"; return 0; }
            if(arg==L"--sdk-bin"&&i+1<argc&&directory.empty()) directory=argv[++i];
            else if(arg==L"--adapter"&&i+1<argc) adapterIndex=BoundedUnsigned(argv[++i],31);
            else if(arg==L"--debug") debug=true;
            else if(arg==L"--context-test") contextTest=true;
            else if(arg==L"--isolated-context") { isolated=true; contextTest=true; }
            else if(arg==L"--dispatch-test") dispatchTest=true;
            else if(arg==L"--isolated-dispatch") { isolated=true; dispatchTest=true; }
            else if(arg==L"--sequence-test") sequenceTest=true;
            else if(arg==L"--shared-dispatch") sharedTest=true;
            else if(arg==L"--shared-worker-child"&&i+8<argc) { sharedChild=true; for(UINT n=0;n<8;++n) sharedValues[n]=wcstoull(argv[++i],nullptr,10); }
            else if(arg==L"--shared-path-sequence"&&i+1<argc&&sharedPathSequence.empty()) { sharedPathTest=true; sharedPathSequence=argv[++i]; Require(sharedPathSequence.is_absolute(),"shared path sequence must be absolute"); }
            else if(arg==L"--session-commands"&&i+1<argc&&sessionCommands.empty()) {
                sessionCommands=argv[++i]; Require(!sessionCommands.empty()&&sessionCommands.size()<=16&&sessionCommands[0]==L'R'&&sessionCommands.find_first_not_of(L"RC")==std::wstring::npos,"session commands must be 1..16 R/C characters beginning with R");
            }
            else if(arg==L"--shared-stream-sequence"&&!sharedStreamOption) { sharedPathTest=true; sharedStreamOption=true; contextOption=true; }
            else if(arg==L"--shared-path-worker-child"&&i+13<argc) { sharedPathChild=true; for(UINT n=0;n<13;++n) sharedPathValues[n]=wcstoull(argv[++i],nullptr,10); }
            else if(arg==L"--isolated-sequence") { isolated=true; sequenceTest=true; }
            else if(arg==L"--isolated-stream-sequence") { isolated=true; sequenceTest=true; streamOption=true; contextOption=true; }
            else if(arg==L"--stream-sequence") { sequenceTest=true; streamOption=true; contextOption=true; }
            else if(arg==L"--dispatch-mode"&&i+1<argc) {
                const std::wstring mode=argv[++i]; Require(mode==L"inference"||mode==L"combined","dispatch mode must be inference or combined");
                combinedDispatch=mode==L"combined"; contextOption=true; dispatchModeOption=true;
            }
            else if(arg==L"--training-batches"&&i+1<argc) { trainingBatches=BoundedUnsigned(argv[++i],8); Require(trainingBatches>0,"training batches must be 1..8"); contextOption=true; trainingOption=true; }
            else if(arg==L"--path-sequence"&&i+1<argc&&pathSequence.empty()) { pathSequence=argv[++i]; Require(pathSequence.is_absolute(),"path sequence must be absolute"); pathOption=true; contextOption=true; }
            else if(arg==L"--worker-child") child=true;
            else if(arg==L"--worker-timeout-ms"&&i+1<argc) { timeoutMs=BoundedUnsigned(argv[++i],60000); Require(timeoutMs>0,"worker timeout must be positive"); }
            else if((arg==L"--cycles"||arg==L"--budget-mib"||arg==L"--fail-allocation")&&i+1<argc) {
                const UINT n=BoundedUnsigned(argv[++i],arg==L"--budget-mib"?256u:255u); Require(n>0,"context option must be positive");
                if(arg==L"--cycles") { Require(n<=3,"cycles must be 1..3"); cycles=n; }
                else if(arg==L"--budget-mib") budgetMiB=n; else failAt=n; contextOption=true;
            } else throw std::runtime_error("unknown, duplicate or incomplete option");
        }
        Require(directory.is_absolute(),"--sdk-bin requires an explicit absolute directory");
        Require(UINT(contextTest)+UINT(dispatchTest)+UINT(sequenceTest)+UINT(sharedTest)+UINT(sharedChild)+UINT(sharedPathTest)+UINT(sharedPathChild)<=1,"RC work modes are mutually exclusive");
        Require(!contextOption||contextTest||dispatchTest||sequenceTest||sharedPathTest,"worker options require a work mode");
        Require(!child||(!isolated&&(contextTest||dispatchTest||sequenceTest)),"invalid RC worker child mode");
        Require(!failAt||contextTest,"allocation failure injection is context-only");
        Require(cycles==1||contextTest,"multiple cycles are context-only");
        Require(!dispatchModeOption||dispatchTest,"dispatch mode option is single-dispatch-only");
        Require(!trainingOption||sequenceTest||sharedPathTest,"training batch count is sequence-only");
        Require(sessionCommands.empty()||sharedPathTest,"session commands require shared path/stream mode");
        Require(!pathOption||sequenceTest,"path sequence is sequence-only");
        Require(!(pathOption&&streamOption),"path and stream sequences are mutually exclusive");
        Require(!(sharedStreamOption&&!sharedPathSequence.empty()),"shared path and stream sequences are mutually exclusive");
        std::vector<unsigned char> streamPayload; if(streamOption||sharedStreamOption) streamPayload=RcReadPathStdin();
        if(isolated) {
            std::vector<std::wstring> args={L"--worker-child",streamOption?L"--stream-sequence":sequenceTest?L"--sequence-test":dispatchTest?L"--dispatch-test":L"--context-test",L"--sdk-bin",directory.wstring(),L"--adapter",std::to_wstring(adapterIndex),
                                            L"--cycles",std::to_wstring(cycles),L"--budget-mib",std::to_wstring(budgetMiB)};
            if(dispatchTest) args.insert(args.end(),{L"--dispatch-mode",combinedDispatch?L"combined":L"inference"});
            if(sequenceTest) args.insert(args.end(),{L"--training-batches",std::to_wstring(trainingBatches)});
            if(pathOption) args.insert(args.end(),{L"--path-sequence",pathSequence.wstring()});
            if(debug) args.push_back(L"--debug"); if(failAt) args.insert(args.end(),{L"--fail-allocation",std::to_wstring(failAt)});
            const auto result=RcRunIsolated(args,timeoutMs,false,streamOption?&streamPayload:nullptr); std::cout << result.Json() << '\n'; return 0;
        }
        if(child||sharedChild||sharedPathChild) SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
        ComPtr<ID3D12Debug> layer; if(debug) { Require(SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&layer))),"D3D12 debug layer unavailable"); layer->EnableDebugLayer(); }
        ComPtr<IDXGIFactory6> factory; ComPtr<IDXGIAdapter1> adapter; ComPtr<ID3D12Device> device;
        Require(SUCCEEDED(CreateDXGIFactory2(0,IID_PPV_ARGS(&factory))),"DXGI factory failed");
        Require(SUCCEEDED(factory->EnumAdapters1(adapterIndex,&adapter)),"adapter unavailable");
        DXGI_ADAPTER_DESC1 desc{}; Require(SUCCEEDED(adapter->GetDesc1(&desc)),"adapter description failed");
        Require(!(desc.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"software adapter is not a Radiance Cache candidate");
        Require(SUCCEEDED(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device))),"D3D12 device unavailable");
        D3D12_FEATURE_DATA_SHADER_MODEL sm{D3D_SHADER_MODEL_6_6};
        const bool sm66=SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL,&sm,sizeof(sm)))&&sm.HighestShaderModel>=D3D_SHADER_MODEL_6_6;
        D3D12_FEATURE_DATA_D3D12_OPTIONS1 options{}; const bool optionsOk=SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS1,&options,sizeof(options)));
        const bool wave32=optionsOk&&options.WaveLaneCountMin<=32&&options.WaveLaneCountMax>=32;
        Module effect(directory/L"amd_fidelityfx_radiancecache_dx12.dll"); Module loader(directory/L"amd_fidelityfx_loader_dx12.dll");
        ffxFunctions api{}; ffxLoadFunctions(&api,loader.handle); Require(api.Query&&api.Configure&&api.CreateContext&&api.DestroyContext,"RC SDK exports missing");
        ffxConfigureDescGlobalDebug logging{}; logging.header.type=FFX_API_CONFIGURE_DESC_TYPE_GLOBALDEBUG; logging.effectId=FFX_API_EFFECT_ID_RADIANCECACHE;
        logging.debugLevel=FFX_API_CONFIGURE_GLOBALDEBUG_LEVEL_WARNINGS; logging.fpMessage=[](uint32_t,const wchar_t* message) { std::wcerr << L"RC: " << (message?message:L"") << L'\n'; };
        if(!sharedChild&&!sharedPathChild) Require(api.Configure(nullptr,&logging.header)==FFX_API_RETURN_OK,"RC logging configuration failed");
        uint64_t count=0; ffxQueryDescGetVersions versions{}; versions.header.type=FFX_API_QUERY_DESC_TYPE_GET_VERSIONS;
        versions.createDescType=FFX_API_CREATE_CONTEXT_DESC_TYPE_RADIANCECACHE; versions.device=device.Get(); versions.outputCount=&count;
        Require(api.Query(nullptr,&versions.header)==FFX_API_RETURN_OK,"RC provider enumeration failed"); Require(count<=16,"excessive RC provider count");
        std::vector<uint64_t> ids(static_cast<size_t>(count)); std::vector<const char*> names(static_cast<size_t>(count));
        if(count) { const auto capacity=count; versions.versionIds=ids.data(); versions.versionNames=names.data(); Require(api.Query(nullptr,&versions.header)==FFX_API_RETURN_OK&&count<=capacity,"RC provider enumeration changed"); }
        std::vector<std::string> copiedNames; for(size_t i=0;i<count;++i) copiedNames.emplace_back(names[i]?names[i]:"");
        if(sharedChild) { Require(sm66&&api.Dispatch&&count,"RC shared provider child unavailable"); return RcSharedProviderChild(api,device.Get(),ids[0],wave32,sharedValues,desc.AdapterLuid); }
        if(sharedPathChild) { Require(sm66&&api.Dispatch&&count,"RC shared path child unavailable"); return RcSharedPathChild(api,device.Get(),ids[0],wave32,sharedPathValues,desc.AdapterLuid); }
        if(sharedTest) { Require(sm66&&api.Dispatch&&count,"RC shared provider dispatch unavailable"); std::cout << RcSharedProviderParent(device.Get(),adapterIndex,desc.AdapterLuid,directory) << '\n'; return 0; }
        if(sharedPathTest) { Require(sm66&&api.Dispatch&&count,"RC shared path sequence unavailable"); const auto fixture=sharedStreamOption?DecodeRcPathSequence(streamPayload):LoadRcPathSequence(sharedPathSequence); std::cout << RcSharedPathParent(device.Get(),adapterIndex,desc.AdapterLuid,directory,fixture,trainingBatches,budgetMiB,timeoutMs,sessionCommands) << '\n'; return 0; }
        char name[1024]{}; WideCharToMultiByte(CP_UTF8,0,desc.Description,-1,name,sizeof(name),nullptr,nullptr);
        std::ostringstream out; out << "{\"adapter\":" << adapterIndex << ",\"name\":" << Quote(name)
            << ",\"shader_model_6_6\":" << (sm66?"true":"false") << ",\"wave_lane_min\":" << (optionsOk?options.WaveLaneCountMin:0)
            << ",\"wave_lane_max\":" << (optionsOk?options.WaveLaneCountMax:0) << ",\"wave32_reference\":" << (wave32?"true":"false")
            << ",\"sdk_api\":\"0.9.0\",\"providers\":[";
        for(size_t i=0;i<count;++i) { if(i) out << ','; out << "{\"id\":" << ids[i] << ",\"name\":" << QuoteBytes(copiedNames[i]) << '}'; } out << ']';
        UINT created=0,destroyed=0,dispatches=0; bool passed=true; out << ",\"context_tests\":[";
        if(contextTest) {
            Require(sm66,"RC context requires shader model 6.6");
            if(count) for(UINT cycle=0;cycle<cycles;++cycle) {
                const auto result=TestRcContext(api,device.Get(),ids[0],uint64_t(budgetMiB)*1024*1024,failAt,wave32);
                if(cycle) out << ','; out << result.Json(); created+=result.created; destroyed+=result.destroyed; if(!result.passed) { passed=false; break; }
            }
        }
        out << "],\"dispatch_tests\":[";
        if(dispatchTest) {
            Require(sm66,"RC dispatch requires shader model 6.6"); Require(api.Dispatch,"RC SDK dispatch export missing"); Require(count,"RC dispatch provider unavailable");
            const auto result=TestRcDispatch(api,device.Get(),ids[0],uint64_t(budgetMiB)*1024*1024,wave32,combinedDispatch);
            out << result.Json(); created+=result.created; destroyed+=result.destroyed; dispatches=result.submitted?1u:0u; passed=result.rawPass;
        }
        out << "],\"sequence_tests\":[";
        if(sequenceTest) {
            Require(sm66,"RC sequence requires shader model 6.6"); Require(api.Dispatch,"RC SDK dispatch export missing"); Require(count,"RC sequence provider unavailable");
            RcPathSequenceFixture fixture; if(pathOption) fixture=LoadRcPathSequence(pathSequence); else if(streamOption) fixture=DecodeRcPathSequence(streamPayload);
            const auto result=TestRcSequence(api,device.Get(),ids[0],uint64_t(budgetMiB)*1024*1024,wave32,trainingBatches,(pathOption||streamOption)?&fixture:nullptr);
            out << result.Json(); created+=result.created; destroyed+=result.destroyed; dispatches=UINT(result.steps.size()); passed=result.rawPass;
        }
        out << "]";
        ComPtr<ID3D12InfoQueue> info; if(debug&&SUCCEEDED(device.As(&info))) for(UINT64 i=0;i<info->GetNumStoredMessagesAllowedByRetrievalFilter();++i) {
            SIZE_T length=0; info->GetMessage(i,nullptr,&length); std::vector<unsigned char> bytes(length); auto* message=reinterpret_cast<D3D12_MESSAGE*>(bytes.data());
            Require(SUCCEEDED(info->GetMessage(i,message,&length)),"RC debug message retrieval failed"); Require(message->Severity>D3D12_MESSAGE_SEVERITY_ERROR,"D3D12 debug layer reported RC error");
        }
        out << ",\"dispatches\":" << dispatches << ",\"contexts_created\":" << created << ",\"contexts_destroyed\":" << destroyed
            << ",\"result\":" << Quote(!count?"no-provider":sequenceTest?(passed?"sequence-tests-pass":"validation-failed"):dispatchTest?(passed?"dispatch-tests-pass":"validation-failed"):contextTest?(passed?"context-tests-pass":"validation-failed"):"queried") << '}';
        std::cout << out.str() << '\n'; return !count?77:passed?0:1;
    } catch(const std::exception& error) { std::cerr << "rrt_rc_probe: " << error.what() << '\n'; return 1; }
}
