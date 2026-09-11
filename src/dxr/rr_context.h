// Bounded RR context ownership; optional work callbacks must fence before returning.
#pragma once
#include <dx12/ffx_api_dx12.h>
#include <array>
#include <mutex>
#include <limits>
#include <functional>
#include "rr_defaults.h"
#include "rr_settings.h"

struct RrGpuBudget {
    struct Allocation { IUnknown* object{}; uint64_t bytes{}; bool heap{}; };
    static constexpr uint64_t MaximumBytes=64ull*1024*1024;
    static inline RrGpuBudget* active{}; // One context at a time in this standalone process.
    ID3D12Device* device;
    uint64_t limit,live{},peak{},attempts{},allocations{},releases{},denials{},errors{},failAt;
    std::array<Allocation,1024> records{};
    std::mutex mutex;
    RrGpuBudget(ID3D12Device* gpu,uint64_t bytes,uint64_t failure):device(gpu),limit(bytes),failAt(failure) {
        Require(!active&&bytes>0&&bytes<=MaximumBytes,"invalid or overlapping RR budget scope"); active=this;
    }
    ~RrGpuBudget() { active=nullptr; }
    RrGpuBudget(const RrGpuBudget&)=delete;
    RrGpuBudget& operator=(const RrGpuBudget&)=delete;
    Allocation* Admit(uint64_t bytes) {
        ++attempts;
        if((failAt&&attempts==failAt)||!bytes||bytes>limit-live) { ++denials; return nullptr; }
        for(auto& record:records) if(!record.object) return &record;
        ++denials; return nullptr;
    }
    void Commit(Allocation& record,IUnknown* object,uint64_t bytes,bool heap) {
        record={object,bytes,heap}; live+=bytes; peak=std::max(peak,live); ++allocations;
    }
    ffxReturnCode_t Release(IUnknown* object,bool heap,uint64_t offset=0,uint64_t size=0) {
        if(!object) return FFX_API_RETURN_OK;
        for(auto& record:records) if(record.object==object) {
            if(record.heap!=heap||offset||(heap&&size!=record.bytes)) { ++errors; return FFX_API_RETURN_ERROR_PARAMETER; }
            live-=record.bytes; record={}; ++releases; object->Release(); return FFX_API_RETURN_OK;
        }
        ++errors; return FFX_API_RETURN_ERROR_PARAMETER;
    }
    static ffxReturnCode_t Resource(uint32_t effect,D3D12_RESOURCE_STATES state,const D3D12_HEAP_PROPERTIES* props,
                                   const D3D12_RESOURCE_DESC* desc,const FfxApiResourceDescription*,const D3D12_CLEAR_VALUE* clear,ID3D12Resource** output) noexcept {
        if(output) *output=nullptr;
        if(!active||!output||!props||!desc) return FFX_API_RETURN_ERROR_PARAMETER;
        try {
            auto& b=*active; std::lock_guard lock(b.mutex);
            (void)effect;
            const auto info=b.device->GetResourceAllocationInfo(0,1,desc);
            auto* record=b.Admit(info.SizeInBytes); if(!record) return FFX_API_RETURN_ERROR_MEMORY;
            const auto hr=b.device->CreateCommittedResource(props,D3D12_HEAP_FLAG_NONE,desc,state,clear,IID_PPV_ARGS(output));
            if(FAILED(hr)) { ++b.errors; return FFX_API_RETURN_ERROR_RUNTIME_ERROR; }
            b.Commit(*record,*output,info.SizeInBytes,false); return FFX_API_RETURN_OK;
        } catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t FreeResource(uint32_t,ID3D12Resource* object) noexcept {
        if(!active) return FFX_API_RETURN_ERROR_PARAMETER;
        try { auto& b=*active; std::lock_guard lock(b.mutex); return b.Release(object,false); }
        catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t Heap(uint32_t effect,const D3D12_HEAP_DESC* desc,bool,ID3D12Heap** output,uint64_t* offset) noexcept {
        if(output) *output=nullptr; if(offset) *offset=0;
        if(!active||!output||!offset||!desc) return FFX_API_RETURN_ERROR_PARAMETER;
        try {
            auto& b=*active; std::lock_guard lock(b.mutex);
            (void)effect;
            auto* record=b.Admit(desc->SizeInBytes); if(!record) return FFX_API_RETURN_ERROR_MEMORY;
            const auto hr=b.device->CreateHeap(desc,IID_PPV_ARGS(output));
            if(FAILED(hr)) { ++b.errors; return FFX_API_RETURN_ERROR_RUNTIME_ERROR; }
            b.Commit(*record,*output,desc->SizeInBytes,true); return FFX_API_RETURN_OK;
        } catch(...) { return FFX_API_RETURN_ERROR; }
    }
    static ffxReturnCode_t FreeHeap(uint32_t,ID3D12Heap* object,uint64_t offset,uint64_t size) noexcept {
        if(!active) return FFX_API_RETURN_ERROR_PARAMETER;
        try { auto& b=*active; std::lock_guard lock(b.mutex); return b.Release(object,true,offset,size); }
        catch(...) { return FFX_API_RETURN_ERROR; }
    }
};

struct RrContextOwner {
    ffxFunctions& api; ffxContext context{};
    ~RrContextOwner() { if(context) Destroy(); }
    // Callers must complete submitted GPU work before context destruction.
    ffxReturnCode_t Destroy() {
        if(!context) return FFX_API_RETURN_OK;
        const auto code=api.DestroyContext(&context,nullptr);
        std::cerr << "RR context: destroy returned " << code << '\n';
        // Ownership ends after successful destruction, whether or not a provider
        // clears the caller's handle. Never destroy an already-freed context twice.
        if(code==FFX_API_RETURN_OK) context=nullptr;
        return code;
    }
};

struct RrContextResult {
    const char* result="not-created";
    std::string defaultQueries;
    RrSettingResult setting;
    bool sdkAllocator{};
    uint32_t preflightCode=UINT32_MAX,createCode=UINT32_MAX,actualCode=UINT32_MAX,providerCode=UINT32_MAX,destroyCode=UINT32_MAX;
    uint64_t predicted{},actual{},aliasable{},provider{},requestedProvider{},budget{},peak{},live{},attempts{},allocations{},releases{},denials{},errors{};
    bool attempted{},created{},destroyed{},passed{};
    uint32_t width=128,height=96;
    std::string Json() const {
        std::ostringstream out;
        out << "{\"result\":" << Quote(result) << ",\"width\":" << width << ",\"height\":" << height << ",\"validation\":true"
            << ",\"hard_budget_enforced\":" << (sdkAllocator?"false":"true")
            << ",\"preflight_code\":" << preflightCode << ",\"predicted_bytes\":" << predicted << ",\"budget_bytes\":" << budget
            << ",\"create_attempted\":" << (attempted?"true":"false") << ",\"created\":" << (created?"true":"false")
            << ",\"destroyed\":" << (destroyed?"true":"false") << ",\"create_code\":" << createCode
            << ",\"actual_query_code\":" << actualCode << ",\"actual_bytes\":" << actual << ",\"actual_aliasable_bytes\":" << aliasable
            << ",\"sdk_memory_valid\":" << (created&&actualCode==0&&actual>0&&actual<=budget&&aliasable<=actual?"true":"false")
            << ",\"provider_query_code\":" << providerCode << ",\"provider_id\":" << provider << ",\"destroy_code\":" << destroyCode
            << ",\"requested_provider_id\":" << requestedProvider
            << ",\"callback_peak_bytes\":" << peak << ",\"callback_live_bytes_after_destroy\":" << live
            << ",\"allocation_attempts\":" << attempts << ",\"allocations\":" << allocations << ",\"releases\":" << releases
            << ",\"allocation_denials\":" << denials << ",\"callback_errors\":" << errors;
        if(!defaultQueries.empty()) out << ",\"default_queries\":[" << defaultQueries << ']';
        if(!setting.json.empty()) out << ",\"filter_setting\":" << setting.json;
        out << '}';
        return out.str();
    }
};

RrContextResult TestRrContext(ffxFunctions& api,ID3D12Device* device,uint64_t provider,uint64_t budget,uint64_t failAt,bool sdkAllocator=false,
                            const std::function<void(ffxContext*)>& work={},bool queryDefaults=false,UINT settingId=0,UINT width=128,UINT height=96) {
    RrContextResult result; result.budget=budget; result.sdkAllocator=sdkAllocator; result.requestedProvider=provider; result.width=width; result.height=height;
    Require((width==128&&height==96)||(width==256&&height==192),"RR context extent invalid");
    ffxOverrideVersion version{}; version.header.type=FFX_API_DESC_TYPE_OVERRIDE_VERSION; version.versionId=provider;
    FfxApiEffectMemoryUsage predicted{};
    ffxQueryDescDenoiserGetGPUMemoryUsage query{};
    query.header.type=FFX_API_QUERY_DESC_TYPE_DENOISER_GPU_MEMORY_USAGE; query.header.pNext=&version.header;
    query.device=device; query.maxRenderSize={width,height}; query.signalFlags=FFX_DENOISER_SIGNAL_INDIRECT_DIFFUSE;
    query.flags=FFX_DENOISER_ENABLE_VALIDATION; query.gpuMemoryUsage=&predicted;
    result.preflightCode=api.Query(nullptr,&query.header); result.predicted=predicted.totalUsageInBytes;
    if(result.preflightCode!=FFX_API_RETURN_OK) { result.result="preflight-query-failed"; return result; }
    if(!result.predicted||result.predicted>budget) { result.result="preflight-budget-rejected"; return result; }
    Require(api.CreateContext&&api.DestroyContext,"SDK context exports missing");
    RrGpuBudget tracked(device,budget,failAt);
    ffxCreateBackendDX12AllocationCallbacksDesc callbacks{};
    callbacks.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12_ALLOCATION_CALLBACKS;
    callbacks.pfnFfxResourceAllocator=RrGpuBudget::Resource; callbacks.pfnFfxResourceDeallocator=RrGpuBudget::FreeResource;
    callbacks.pfnFfxHeapAllocator=RrGpuBudget::Heap; callbacks.pfnFfxHeapDeallocator=RrGpuBudget::FreeHeap;
    callbacks.header.pNext=&version.header;
    ffxCreateBackendDX12Desc backend{}; backend.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12;
    backend.device=device; backend.header.pNext=&callbacks.header;
    // Diagnostic control only: fixed small resolution, preflight admission, no
    // custom allocator ceiling. Never confuse this with the bounded path.
    if(sdkAllocator) backend.header.pNext=&version.header;
    ffxCreateContextDescDenoiser description{}; description.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_DENOISER;
    description.header.pNext=&backend.header; description.version=FFX_DENOISER_VERSION;
    description.maxRenderSize=query.maxRenderSize; description.signalFlags=query.signalFlags; description.flags=query.flags;
    RrContextOwner owner{api}; result.attempted=true;
    std::cerr << "RR context: creating " << width << 'x' << height << ", budget=" << budget << ", estimate=" << result.predicted << '\n';
    result.createCode=api.CreateContext(&owner.context,&description.header,nullptr);
    std::cerr << "RR context: create returned " << result.createCode << ", allocations=" << tracked.allocations << '\n';
    result.created=result.createCode==FFX_API_RETURN_OK&&owner.context;
    if(result.created) {
        if(queryDefaults) {
            result.defaultQueries=RrQueryDefaults(api,&owner.context,"before-1");
            result.defaultQueries+=','+RrQueryDefaults(api,&owner.context,"before-2");
        }
        if(settingId) result.setting=RrConfigureSetting(api,&owner.context,settingId);
        if(work&&result.setting.ready) work(&owner.context); // The callback must complete/fence GPU work before returning or throwing.
        if(queryDefaults) {
            result.defaultQueries+=','+RrQueryDefaults(api,&owner.context,"after-1");
            result.defaultQueries+=','+RrQueryDefaults(api,&owner.context,"after-2");
        }
        std::cerr << "RR context: querying actual memory\n";
        FfxApiEffectMemoryUsage actual{}; query.header.pNext=nullptr; query.gpuMemoryUsage=&actual;
        result.actualCode=api.Query(&owner.context,&query.header);
        std::cerr << "RR context: actual memory returned " << result.actualCode << '\n';
        result.actual=actual.totalUsageInBytes; result.aliasable=actual.aliasableUsageInBytes;
        ffxQueryGetProviderVersion selected{}; selected.header.type=FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
        result.providerCode=api.Query(&owner.context,&selected.header); result.provider=selected.versionId;
        std::cerr << "RR context: provider query returned " << result.providerCode << '\n';
    }
    std::cerr << "RR context: destroying\n";
    result.destroyCode=owner.Destroy(); result.destroyed=result.created&&!owner.context&&result.destroyCode==FFX_API_RETURN_OK;
    result.peak=tracked.peak; result.live=tracked.live; result.attempts=tracked.attempts;
    result.allocations=tracked.allocations; result.releases=tracked.releases; result.denials=tracked.denials; result.errors=tracked.errors;
    result.passed=result.created&&result.destroyed&&result.actualCode==0&&result.providerCode==0&&result.provider==provider
        &&result.actual>0&&result.aliasable<=result.actual&&result.actual<=budget&&result.peak>0&&result.peak<=budget
        &&!result.live&&!result.denials&&!result.errors&&result.allocations==result.releases;
    result.result=result.passed?"context-lifecycle-pass":result.created?"context-validation-failed":"context-create-failed";
    if(sdkAllocator) {
        result.passed=result.created&&result.destroyed&&result.actualCode==0&&result.actual>0&&result.actual<=budget&&result.aliasable<=result.actual;
        result.result=result.passed?"sdk-allocator-control-pass":"sdk-allocator-control-failed";
    }
    return result;
}

void TestRrAllocator(ID3D12Device* device) {
    D3D12_HEAP_PROPERTIES props{}; props.Type=D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=256;
    desc.Height=1; desc.DepthOrArraySize=1; desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    const auto size=device->GetResourceAllocationInfo(0,1,&desc).SizeInBytes;
    Require(size>0&&size<=RrGpuBudget::MaximumBytes/2,"unexpected test-buffer allocation size");
    {
        RrGpuBudget budget(device,size*2,0);
        ComPtr<ID3D12Resource> first,second; ID3D12Resource* denied=nullptr;
        Require(RrGpuBudget::Resource(22,D3D12_RESOURCE_STATE_COMMON,&props,&desc,nullptr,nullptr,&first)==0,"first budget test allocation failed");
        Require(RrGpuBudget::Resource(22,D3D12_RESOURCE_STATE_COMMON,&props,&desc,nullptr,nullptr,&second)==0,"second budget test allocation failed");
        Require(RrGpuBudget::Resource(22,D3D12_RESOURCE_STATE_COMMON,&props,&desc,nullptr,nullptr,&denied)==FFX_API_RETURN_ERROR_MEMORY&&!denied,"budget overflow was not rejected");
        Require(budget.live==size*2&&budget.peak==size*2&&budget.denials==1,"allocation charge mismatch");
        Require(RrGpuBudget::FreeResource(22,first.Detach())==0&&RrGpuBudget::FreeResource(22,second.Detach())==0,"budget resource release failed");
        Require(!budget.live&&budget.allocations==budget.releases&&!budget.errors,"resource budget leaked");
    }
    {
        RrGpuBudget budget(device,size*2,2);
        ComPtr<ID3D12Resource> first; ID3D12Resource* denied=nullptr;
        Require(RrGpuBudget::Resource(22,D3D12_RESOURCE_STATE_COMMON,&props,&desc,nullptr,nullptr,&first)==0,"failure test first allocation failed");
        Require(RrGpuBudget::Resource(22,D3D12_RESOURCE_STATE_COMMON,&props,&desc,nullptr,nullptr,&denied)==FFX_API_RETURN_ERROR_MEMORY&&!denied,"injected failure not enforced");
        Require(RrGpuBudget::FreeResource(22,first.Detach())==0&&!budget.live&&budget.denials==1,"injected failure cleanup failed");
    }
    {
        RrGpuBudget budget(device,size,0);
        D3D12_HEAP_DESC heap{}; heap.SizeInBytes=size; heap.Properties=props; heap.Flags=D3D12_HEAP_FLAG_ALLOW_ONLY_BUFFERS;
        ComPtr<ID3D12Heap> object; uint64_t offset=UINT64_MAX;
        Require(RrGpuBudget::Heap(22,&heap,false,&object,&offset)==0&&offset==0,"heap test allocation failed");
        Require(RrGpuBudget::FreeHeap(22,object.Get(),1,size)==FFX_API_RETURN_ERROR_PARAMETER&&budget.live==size,"invalid heap offset accepted");
        Require(RrGpuBudget::FreeHeap(22,object.Get(),0,size+1)==FFX_API_RETURN_ERROR_PARAMETER&&budget.live==size,"invalid heap size accepted");
        Require(RrGpuBudget::FreeHeap(22,object.Detach(),0,size)==0&&!budget.live&&budget.errors==2,"heap test release failed");
    }
}
