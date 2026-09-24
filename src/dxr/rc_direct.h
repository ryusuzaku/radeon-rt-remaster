#pragma once

struct RcBufferPool {
    struct Entry {
        ComPtr<ID3D12Resource> resource; UINT64 bytes{}; D3D12_HEAP_TYPE heap{};
        D3D12_RESOURCE_STATES initial{},final{}; D3D12_RESOURCE_FLAGS flags{}; bool shared{},used{};
    };
    Device& gpu; std::array<Entry,32> entries{};
    UINT64 charged{},allocations{},reuses{},restoreSubmissions{},restoredBuffers{}; bool active{},includeDefault{};
    explicit RcBufferPool(Device& device,bool allBuffers=false):gpu(device),includeDefault(allBuffers) {}
    RcBufferPool(const RcBufferPool&)=delete; RcBufferPool& operator=(const RcBufferPool&)=delete;
    ~RcBufferPool() { ReleaseEntries(); }
    void Clear() { Require(!active,"RC staging pool still leased"); ReleaseEntries(); }
    void Begin() { Require(!active,"RC staging pool already leased"); active=true; }
    void End(bool reusable) { if(!reusable) ReleaseEntries(); for(auto& entry:entries) entry.used=false; active=false; }
    ComPtr<ID3D12Resource> Acquire(UINT64 bytes,D3D12_HEAP_TYPE heap,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS flags=D3D12_RESOURCE_FLAG_NONE,bool shared=false) {
        Require(active,"RC buffer pool has no lease"); if(!shared) bytes=std::max(bytes,UINT64(256));
        Require((heap==D3D12_HEAP_TYPE_UPLOAD&&state==D3D12_RESOURCE_STATE_GENERIC_READ)||
            (heap==D3D12_HEAP_TYPE_READBACK&&state==D3D12_RESOURCE_STATE_COPY_DEST)||
            (includeDefault&&heap==D3D12_HEAP_TYPE_DEFAULT),"RC pool heap/state invalid");
        Require(!shared||(heap==D3D12_HEAP_TYPE_DEFAULT&&state==D3D12_RESOURCE_STATE_UNORDERED_ACCESS&&flags==D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS),"RC shared pool descriptor invalid");
        for(auto& entry:entries) if(entry.resource&&!entry.used&&entry.bytes==bytes&&entry.heap==heap&&entry.initial==state&&entry.flags==flags&&entry.shared==shared) {
            entry.used=true; ++reuses; return entry.resource;
        }
        Require(charged+bytes<=(includeDefault?8ull:1ull)*1024*1024,"RC buffer pool byte limit exceeded");
        for(UINT index=0;index<(includeDefault?32u:16u);++index) { auto& entry=entries[index]; if(!entry.resource) {
            entry.resource=shared?gpu.SharedBuffer(bytes):gpu.Buffer(bytes,heap,state,flags);
            entry.bytes=bytes; entry.heap=heap; entry.initial=entry.final=state; entry.flags=flags; entry.shared=shared; entry.used=true;
            charged+=bytes; ++allocations; return entry.resource;
        } }
        throw std::runtime_error("RC buffer pool entry limit exceeded");
    }
    void FinalState(ID3D12Resource* resource,D3D12_RESOURCE_STATES state) {
        Require(active,"RC pool state update without lease");
        for(auto& entry:entries) if(entry.used&&entry.resource.Get()==resource) { entry.final=state; return; }
        throw std::runtime_error("RC pool state update for unknown resource");
    }
    void Restore() {
        Require(active,"RC pool restore without lease");
        std::array<D3D12_RESOURCE_BARRIER,32> barriers{}; UINT count=0;
        for(auto& entry:entries) if(entry.used&&entry.initial!=entry.final) {
            auto& barrier=barriers[count++]; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            barrier.Transition={entry.resource.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,entry.final,entry.initial};
        }
        if(count) { gpu.Begin(); gpu.list->ResourceBarrier(count,barriers.data()); gpu.Execute(); ++restoreSubmissions; restoredBuffers+=count; }
        for(auto& entry:entries) if(entry.used) entry.final=entry.initial;
    }
private:
    void ReleaseEntries() { for(auto& entry:entries) entry=Entry{}; gpu.allocated-=charged; charged=0; }
};

// All returned references stay local to RunRcDirect. Holding a second reference
// here makes budget ownership explicit and keeps inputs alive through worker
// teardown, including exception paths. GPU submissions are fenced by the caller.
struct RcTransientBuffers {
    Device& gpu;
    RcBufferPool* pool{}; bool reusable{};
    UINT64 charged{};
    std::vector<ComPtr<ID3D12Resource>> resources;
    explicit RcTransientBuffers(Device& device,RcBufferPool* staging=nullptr):gpu(device),pool(staging) {
        if(pool) { Require(&pool->gpu==&gpu,"RC staging pool belongs to another device"); pool->Begin(); }
    }
    RcTransientBuffers(const RcTransientBuffers&)=delete;
    RcTransientBuffers& operator=(const RcTransientBuffers&)=delete;
    ~RcTransientBuffers() { resources.clear(); gpu.allocated-=charged; if(pool) pool->End(reusable); }
    ComPtr<ID3D12Resource> Keep(ComPtr<ID3D12Resource> resource,UINT64 bytes) {
        try { resources.push_back(resource); }
        catch(...) { resource.Reset(); gpu.allocated-=bytes; throw; }
        charged+=bytes; return resource;
    }
    ComPtr<ID3D12Resource> Buffer(UINT64 bytes,D3D12_HEAP_TYPE heap,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS flags=D3D12_RESOURCE_FLAG_NONE) {
        if(pool&&(pool->includeDefault||(flags==D3D12_RESOURCE_FLAG_NONE&&(heap==D3D12_HEAP_TYPE_UPLOAD||heap==D3D12_HEAP_TYPE_READBACK)))) return pool->Acquire(bytes,heap,state,flags);
        return Keep(gpu.Buffer(bytes,heap,state,flags),std::max(bytes,UINT64(256)));
    }
    ComPtr<ID3D12Resource> SharedBuffer(UINT64 bytes) {
        if(pool&&pool->includeDefault) return pool->Acquire(bytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS,true);
        return Keep(gpu.SharedBuffer(bytes),bytes);
    }
    void FinalState(ID3D12Resource* resource,D3D12_RESOURCE_STATES state) { if(pool&&pool->includeDefault) pool->FinalState(resource,state); }
    void Recycle() { if(pool) pool->Restore(); reusable=true; }
    ComPtr<ID3D12Resource> Upload(const void* data,size_t bytes) {
        auto resource=Buffer(bytes,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
        void* mapped{}; D3D12_RANGE empty{};
        Check(resource->Map(0,&empty,&mapped),"RC scoped upload map");
        if(bytes) std::memcpy(mapped,data,bytes);
        resource->Unmap(0,nullptr); return resource;
    }
};

#include "rc_renderer_session.h"
std::vector<std::uint8_t> RcDirectShader(const wchar_t* name) {
    wchar_t module[32768]{}; Require(GetModuleFileNameW(nullptr,module,32768)!=0,"RC direct executable path unavailable"); const auto path=std::filesystem::path(module).parent_path()/name;
    std::ifstream file(path,std::ios::binary|std::ios::ate); Require(file.good(),"RC direct shader missing"); const auto length=file.tellg(); Require(length>0&&length<16*1024*1024,"RC direct shader size invalid"); std::vector<std::uint8_t> bytes(static_cast<size_t>(length)); file.seekg(0); file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()); Require(file.good(),"RC direct shader read failed"); return bytes;
}
std::string RunRcDirect(Renderer& renderer,const Options& options,const rrt::scene::Hash& sceneDigest,RcBufferPool* staging=nullptr) {
    RcTransientBuffers transient(renderer.gpu,staging);
    try {
        const auto directStart=std::chrono::steady_clock::now();
        renderer.Drain(); Require(renderer.scene.width==128&&renderer.scene.height==96&&renderer.samples>0&&renderer.pbrDraws==0,"RC direct requires rendered legacy-diffuse fixture");
        XMFLOAT3 lower{FLT_MAX,FLT_MAX,FLT_MAX},upper{-FLT_MAX,-FLT_MAX,-FLT_MAX}; for(const auto& draw:renderer.scene.draws) { const auto world=Matrix(draw.state.world); for(const auto& vertex:draw.vertices) { XMFLOAT3 point; XMStoreFloat3(&point,XMVector3TransformCoord(XMVectorSet(vertex.x,vertex.y,vertex.z,1),world)); lower.x=std::min(lower.x,point.x); lower.y=std::min(lower.y,point.y); lower.z=std::min(lower.z,point.z); upper.x=std::max(upper.x,point.x); upper.y=std::max(upper.y,point.y); upper.z=std::max(upper.z,point.z); } }
        const XMFLOAT3 extent{upper.x-lower.x,upper.y-lower.y,upper.z-lower.z}; Require(extent.x>=1e-4f&&extent.y>=1e-4f&&extent.z>=1e-4f,"RC direct scene bounds invalid"); constexpr UINT Rows=128*96; constexpr uint64_t sizes[5]={540672,147456,22528,6144,8};
        auto raw=transient.Buffer(uint64_t(Rows)*128,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS); auto pixelMapping=transient.Buffer(uint64_t(Rows)*sizeof(UINT),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS); std::array<ComPtr<ID3D12Resource>,5> shared; for(UINT i=0;i<5;++i) shared[i]=transient.SharedBuffer(sizes[i]);
        Frame frame=renderer.frame; auto frameConstants=transient.Upload(&frame,sizeof(frame)); struct CompactConstants { XMFLOAT3 lower; UINT rows; XMFLOAT3 extent; UINT training; } compactConstants{lower,Rows,extent,512}; auto compactUpload=transient.Upload(&compactConstants,sizeof(compactConstants));
        const auto rawCode=RcDirectShader(L"rrt_rc_paths.dxil"),compactCode=RcDirectShader(L"rrt_rc_compact.dxil"); D3D12_ROOT_PARAMETER rawParameters[7]{}; for(UINT i=0;i<5;++i) { rawParameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; rawParameters[i].Descriptor.ShaderRegister=i; } rawParameters[5].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; rawParameters[5].Descriptor.ShaderRegister=0; rawParameters[6].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; rawParameters[6].Descriptor.ShaderRegister=6;
        D3D12_ROOT_SIGNATURE_DESC rawDesc{}; rawDesc.NumParameters=7; rawDesc.pParameters=rawParameters; ComPtr<ID3DBlob> serialized,error; Check(D3D12SerializeRootSignature(&rawDesc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RC direct raw root serialization"); ComPtr<ID3D12RootSignature> rawRoot; Check(renderer.gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&rawRoot)),"RC direct raw root"); D3D12_COMPUTE_PIPELINE_STATE_DESC rawPipeline{}; rawPipeline.pRootSignature=rawRoot.Get(); rawPipeline.CS={rawCode.data(),rawCode.size()}; ComPtr<ID3D12PipelineState> rawPso; Check(renderer.gpu.device->CreateComputePipelineState(&rawPipeline,IID_PPV_ARGS(&rawPso)),"RC direct raw pipeline");
        D3D12_ROOT_PARAMETER compactParameters[8]{}; compactParameters[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; compactParameters[0].Descriptor.ShaderRegister=0; compactParameters[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; compactParameters[1].Descriptor.ShaderRegister=0; for(UINT i=0;i<6;++i) { compactParameters[2+i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; compactParameters[2+i].Descriptor.ShaderRegister=i; } D3D12_ROOT_SIGNATURE_DESC compactDesc{}; compactDesc.NumParameters=8; compactDesc.pParameters=compactParameters; serialized.Reset(); error.Reset(); Check(D3D12SerializeRootSignature(&compactDesc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RC direct compact root serialization"); ComPtr<ID3D12RootSignature> compactRoot; Check(renderer.gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&compactRoot)),"RC direct compact root"); D3D12_COMPUTE_PIPELINE_STATE_DESC compactPipeline{}; compactPipeline.pRootSignature=compactRoot.Get(); compactPipeline.CS={compactCode.data(),compactCode.size()}; ComPtr<ID3D12PipelineState> compactPso; Check(renderer.gpu.device->CreateComputePipelineState(&compactPipeline,IID_PPV_ARGS(&compactPso)),"RC direct compact pipeline");
        renderer.gpu.Begin(); renderer.gpu.list->SetComputeRootSignature(rawRoot.Get()); renderer.gpu.list->SetPipelineState(rawPso.Get()); ID3D12Resource* srvs[]={renderer.top.result.Get(),renderer.vb.Get(),renderer.ib.Get(),renderer.materials.Get(),renderer.textures.Get()}; for(UINT i=0;i<5;++i) renderer.gpu.list->SetComputeRootShaderResourceView(i,srvs[i]->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(5,frameConstants->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(6,raw->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(16,12,1);
        D3D12_RESOURCE_BARRIER rawBarrier{}; rawBarrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; rawBarrier.Transition={raw.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; renderer.gpu.list->ResourceBarrier(1,&rawBarrier); renderer.gpu.list->SetComputeRootSignature(compactRoot.Get()); renderer.gpu.list->SetPipelineState(compactPso.Get()); renderer.gpu.list->SetComputeRootShaderResourceView(0,raw->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(1,compactUpload->GetGPUVirtualAddress()); for(UINT i=0;i<5;++i) renderer.gpu.list->SetComputeRootUnorderedAccessView(2+i,shared[i]->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(7,pixelMapping->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(1,1,1);
        std::array<D3D12_RESOURCE_BARRIER,6> barriers{}; for(UINT i=0;i<5;++i) { barriers[i].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; barriers[i].Transition={shared[i].Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; } barriers[5].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; barriers[5].Transition={pixelMapping.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; renderer.gpu.list->ResourceBarrier(UINT(barriers.size()),barriers.data()); renderer.gpu.Execute(); ++renderer.rcPathSubmissions;
        auto regenerate=[&](const Frame& nextFrame) {
            auto nextConstants=frameConstants; void* mappedConstants{}; D3D12_RANGE noRead{};
            Check(nextConstants->Map(0,&noRead,&mappedConstants),"RC reused frame constants map"); std::memcpy(mappedConstants,&nextFrame,sizeof(nextFrame)); nextConstants->Unmap(0,nullptr);
            renderer.gpu.Begin(); std::array<D3D12_RESOURCE_BARRIER,7> toUav{};
            toUav[0].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; toUav[0].Transition={raw.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS};
            for(UINT i=0;i<5;++i) { toUav[1+i].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; toUav[1+i].Transition={shared[i].Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS}; }
            toUav[6].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; toUav[6].Transition={pixelMapping.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS}; renderer.gpu.list->ResourceBarrier(UINT(toUav.size()),toUav.data());
            renderer.gpu.list->SetComputeRootSignature(rawRoot.Get()); renderer.gpu.list->SetPipelineState(rawPso.Get()); ID3D12Resource* nextSrvs[]={renderer.top.result.Get(),renderer.vb.Get(),renderer.ib.Get(),renderer.materials.Get(),renderer.textures.Get()}; for(UINT i=0;i<5;++i) renderer.gpu.list->SetComputeRootShaderResourceView(i,nextSrvs[i]->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(5,nextConstants->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(6,raw->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(16,12,1);
            D3D12_RESOURCE_BARRIER nextRaw{}; nextRaw.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; nextRaw.Transition={raw.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; renderer.gpu.list->ResourceBarrier(1,&nextRaw); renderer.gpu.list->SetComputeRootSignature(compactRoot.Get()); renderer.gpu.list->SetPipelineState(compactPso.Get()); renderer.gpu.list->SetComputeRootShaderResourceView(0,raw->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(1,compactUpload->GetGPUVirtualAddress()); for(UINT i=0;i<5;++i) renderer.gpu.list->SetComputeRootUnorderedAccessView(2+i,shared[i]->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(7,pixelMapping->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(1,1,1);
            std::array<D3D12_RESOURCE_BARRIER,6> toSrv{}; for(UINT i=0;i<5;++i) { toSrv[i].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; toSrv[i].Transition={shared[i].Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; } toSrv[5].Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; toSrv[5].Transition={pixelMapping.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; renderer.gpu.list->ResourceBarrier(UINT(toSrv.size()),toSrv.data()); renderer.gpu.Execute(); ++renderer.rcPathSubmissions;
        };
        SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE}; std::array<RcHandle,5> handles; std::vector<HANDLE> inherited; for(UINT i=0;i<5;++i) { Check(renderer.gpu.device->CreateSharedHandle(shared[i].Get(),&security,GENERIC_ALL,nullptr,&handles[i].value),"RC direct shared handle"); inherited.push_back(handles[i].value); } ComPtr<ID3D12Fence> fence; RcHandle fenceHandle; Check(renderer.gpu.device->CreateFence(0,D3D12_FENCE_FLAG_SHARED,IID_PPV_ARGS(&fence)),"RC direct shared fence"); Check(renderer.gpu.device->CreateSharedHandle(fence.Get(),&security,GENERIC_ALL,nullptr,&fenceHandle.value),"RC direct fence handle"); inherited.push_back(fenceHandle.value); Check(renderer.gpu.queue->Signal(fence.Get(),30),"RC direct initial signal");
        const UINT workerEpochs=options.rcRendererSessionTest?4:options.rcLiveSessionTest?3:options.rcPersistentEpochs; std::vector<std::wstring> args={L"--sdk-bin",options.rcSdkBin.wstring(),L"--adapter",std::to_wstring(options.adapter),L"--shared-path-worker-child"}; for(auto& handle:handles) args.push_back(std::to_wstring(uintptr_t(handle.value))); args.push_back(std::to_wstring(uintptr_t(fenceHandle.value))); args.push_back(std::to_wstring(renderer.gpu.desc.AdapterLuid.LowPart)); args.push_back(std::to_wstring(uint32_t(renderer.gpu.desc.AdapterLuid.HighPart))); args.push_back(L"0"); args.push_back(L"0"); args.push_back(std::to_wstring(options.rcTrainingBatches)); args.push_back(std::to_wstring(options.rcBudgetMiB)); args.push_back(std::to_wstring(workerEpochs)); RcProcessResult child; Frame finalFrame=frame;
        if(options.rcRendererSessionTest) return RunRcRendererSession(renderer,options,args,inherited,fence.Get(),shared[1].Get(),transient,regenerate);
        if(options.rcLiveSessionTest) {
            RcIsolatedSession session(args,inherited,options.rcProbe.c_str()); session.WaitFence(fence.Get(),31,options.rcWorkerTimeoutMs); Check(renderer.gpu.queue->Signal(fence.Get(),32),"RC live stable submit signal"); session.WaitFence(fence.Get(),33,options.rcWorkerTimeoutMs);
            auto moved=options; moved.offset[0]+=.05f; renderer.Configure(moved); renderer.RenderTo(1); finalFrame=renderer.frame; regenerate(finalFrame); Check(renderer.gpu.queue->Signal(fence.Get(),34),"RC live changed submit signal"); session.WaitFence(fence.Get(),35,options.rcWorkerTimeoutMs); child=session.Finish(options.rcWorkerTimeoutMs);
        } else child=RcRunIsolated(args,options.rcWorkerTimeoutMs,false,nullptr,&inherited,options.rcProbe.c_str());
        Require(child.reaped&&!child.timedOut&&!child.overflow&&child.exitCode==0&&child.error.empty(),"RC direct provider child unavailable"); std::istringstream parsed(child.output); std::string magic,extra; uint64_t baseline=0,firstPost=0,epochStart=0,stablePost=0,changedBaseline=0,post=0,reset=0; UINT changed=0,epochChanged=0,changedFrameValues=0,finalPopulated=0,resetChanged=0; bool fields=false;
        if(workerEpochs==1) { fields=bool(parsed>>magic>>baseline>>post>>reset>>changed>>resetChanged); firstPost=epochStart=stablePost=post; }
        else if(workerEpochs==2) { fields=bool(parsed>>magic>>baseline>>firstPost>>epochStart>>post>>reset>>changed>>epochChanged>>resetChanged); stablePost=post; }
        else fields=bool(parsed>>magic>>baseline>>firstPost>>epochStart>>stablePost>>changedBaseline>>post>>reset>>changed>>epochChanged>>changedFrameValues>>finalPopulated>>resetChanged);
        const bool noExtra=!(parsed>>extra); const auto expectedMagic=workerEpochs==1?"RCSHAREDSEQ1":workerEpochs==2?"RCSHAREDEPOCH2":"RCSHAREDLIVE3"; const uint64_t resetReference=workerEpochs==3?changedBaseline:baseline;
        if(workerEpochs<3) finalPopulated=changed/3; Require(fields&&noExtra&&magic==expectedMagic&&baseline&&firstPost!=baseline&&epochStart==firstPost&&reset==resetReference&&changed&&changed%3==0&&finalPopulated&&finalPopulated<=Rows&&!resetChanged&&(workerEpochs==1?(post==firstPost&&!epochChanged):(stablePost!=firstPost&&epochChanged==changed))&&(workerEpochs<3||(changedBaseline!=baseline&&post!=changedBaseline&&changedFrameValues==finalPopulated*3)),"RC direct provider report invalid"); const UINT populated=finalPopulated;
        auto candidate=transient.Buffer(uint64_t(Rows)*sizeof(XMFLOAT4),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS); auto candidateReadback=transient.Buffer(uint64_t(Rows)*sizeof(XMFLOAT4),D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST); UINT compositeConstants[4]{populated,0,0,0}; auto compositeUpload=transient.Upload(compositeConstants,sizeof(compositeConstants)); const auto compositeCode=RcDirectShader(L"rrt_rc_composite.dxil"); D3D12_ROOT_PARAMETER compositeParameters[5]{}; for(UINT i=0;i<3;++i) { compositeParameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; compositeParameters[i].Descriptor.ShaderRegister=i; } compositeParameters[3].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; compositeParameters[3].Descriptor.ShaderRegister=0; compositeParameters[4].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; compositeParameters[4].Descriptor.ShaderRegister=0; D3D12_ROOT_SIGNATURE_DESC compositeDesc{}; compositeDesc.NumParameters=5; compositeDesc.pParameters=compositeParameters; serialized.Reset(); error.Reset(); Check(D3D12SerializeRootSignature(&compositeDesc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RC direct composite root serialization"); ComPtr<ID3D12RootSignature> compositeRoot; Check(renderer.gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&compositeRoot)),"RC direct composite root"); D3D12_COMPUTE_PIPELINE_STATE_DESC compositePipeline{}; compositePipeline.pRootSignature=compositeRoot.Get(); compositePipeline.CS={compositeCode.data(),compositeCode.size()}; ComPtr<ID3D12PipelineState> compositePso; Check(renderer.gpu.device->CreateComputePipelineState(&compositePipeline,IID_PPV_ARGS(&compositePso)),"RC direct composite pipeline"); renderer.gpu.Begin(); renderer.gpu.list->SetComputeRootSignature(compositeRoot.Get()); renderer.gpu.list->SetPipelineState(compositePso.Get()); renderer.gpu.list->SetComputeRootShaderResourceView(0,raw->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootShaderResourceView(1,shared[1]->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootShaderResourceView(2,pixelMapping->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(3,compositeUpload->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(4,candidate->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(1,1,1); D3D12_RESOURCE_BARRIER candidateBarrier{}; candidateBarrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; candidateBarrier.Transition={candidate.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE}; renderer.gpu.list->ResourceBarrier(1,&candidateBarrier); renderer.gpu.list->CopyResource(candidateReadback.Get(),candidate.Get()); renderer.gpu.Execute();
        std::vector<XMFLOAT4> composite(Rows); void* compositeMapped{}; D3D12_RANGE compositeRange{0,SIZE_T(composite.size()*sizeof(XMFLOAT4))}; Check(candidateReadback->Map(0,&compositeRange,&compositeMapped),"RC direct composite readback map"); std::memcpy(composite.data(),compositeMapped,composite.size()*sizeof(XMFLOAT4)); D3D12_RANGE noWrite{}; candidateReadback->Unmap(0,&noWrite); double errorSum=0; UINT admitted=0; for(const auto& value:composite) { Require(std::isfinite(value.x)&&std::isfinite(value.y)&&std::isfinite(value.z)&&std::isfinite(value.w)&&value.w>=0,"RC direct composite nonfinite"); if(value.w>0) { errorSum+=value.w; ++admitted; } } Require(admitted>0&&admitted<=populated,"RC direct composite coverage invalid"); const double compositeMse=errorSum/(double(populated)*3); Require(std::isfinite(compositeMse)&&compositeMse>0&&compositeMse<.01,"RC direct composite quality outside guard");
        UINT appliedCount=0,changedPixels=0; UINT64 applyAuditReadbackBytes=0; std::string noCacheOutputSha,presentationOutputSha;
        if(options.rcPresentCandidate) {
            const auto noCachePixels=renderer.ReadPixels();
            noCacheOutputSha=rrt::scene::Hex(rrt::scene::Digest(noCachePixels.data(),noCachePixels.size()*sizeof(noCachePixels[0])));
            auto backup=transient.Buffer(renderer.bytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST);
            auto audit=transient.Buffer(uint64_t(Rows)*sizeof(UINT),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
            transient.FinalState(audit.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE);
            auto auditReadback=transient.Buffer(uint64_t(Rows)*sizeof(UINT),D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
            const auto applyCode=RcDirectShader(L"rrt_rc_apply.dxil"); D3D12_ROOT_PARAMETER applyParameters[5]{};
            for(UINT i=0;i<2;++i) { applyParameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; applyParameters[i].Descriptor.ShaderRegister=i; }
            applyParameters[2].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; applyParameters[2].Descriptor.ShaderRegister=0;
            for(UINT i=0;i<2;++i) { applyParameters[3+i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; applyParameters[3+i].Descriptor.ShaderRegister=i; }
            D3D12_ROOT_SIGNATURE_DESC applyDesc{}; applyDesc.NumParameters=5; applyDesc.pParameters=applyParameters; serialized.Reset(); error.Reset();
            Check(D3D12SerializeRootSignature(&applyDesc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RC direct apply root serialization"); ComPtr<ID3D12RootSignature> applyRoot;
            Check(renderer.gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&applyRoot)),"RC direct apply root");
            D3D12_COMPUTE_PIPELINE_STATE_DESC applyPipeline{}; applyPipeline.pRootSignature=applyRoot.Get(); applyPipeline.CS={applyCode.data(),applyCode.size()}; ComPtr<ID3D12PipelineState> applyPso;
            Check(renderer.gpu.device->CreateComputePipelineState(&applyPipeline,IID_PPV_ARGS(&applyPso)),"RC direct apply pipeline");
            renderer.gpu.Begin(); renderer.gpu.list->CopyResource(backup.Get(),renderer.output.Get());
            D3D12_RESOURCE_BARRIER applyBarriers[2]{}; for(auto& value:applyBarriers) value.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            applyBarriers[0].Transition={renderer.output.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS};
            applyBarriers[1].Transition={candidate.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE}; renderer.gpu.list->ResourceBarrier(2,applyBarriers);
            renderer.gpu.list->SetComputeRootSignature(applyRoot.Get()); renderer.gpu.list->SetPipelineState(applyPso.Get()); renderer.gpu.list->SetComputeRootShaderResourceView(0,candidate->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootShaderResourceView(1,pixelMapping->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootConstantBufferView(2,compositeUpload->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(3,renderer.output->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(4,audit->GetGPUVirtualAddress()); renderer.gpu.list->Dispatch(1,1,1);
            D3D12_RESOURCE_BARRIER resultBarriers[2]{}; for(auto& value:resultBarriers) value.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            resultBarriers[0].Transition={renderer.output.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE}; resultBarriers[1].Transition={audit.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE}; renderer.gpu.list->ResourceBarrier(2,resultBarriers);
            renderer.gpu.list->CopyResource(renderer.readback.Get(),renderer.output.Get()); renderer.gpu.list->CopyResource(auditReadback.Get(),audit.Get()); renderer.gpu.Execute();
            try {
                const auto appliedOutput=renderer.ReadPixels(); std::vector<UINT> mask(Rows); void* auditMapped{}; D3D12_RANGE auditRange{0,SIZE_T(mask.size()*sizeof(mask[0]))}; Check(auditReadback->Map(0,&auditRange,&auditMapped),"RC direct apply audit map"); std::memcpy(mask.data(),auditMapped,mask.size()*sizeof(mask[0])); auditReadback->Unmap(0,&noWrite);
                for(UINT pixel=0;pixel<Rows;++pixel) {
                    Require(mask[pixel]<=1,"RC direct apply audit invalid");
                    if(mask[pixel]) { ++appliedCount; const auto& color=composite[pixel]; const UINT r=UINT(std::round(std::clamp(color.x,0.f,1.f)*255)),g=UINT(std::round(std::clamp(color.y,0.f,1.f)*255)),b=UINT(std::round(std::clamp(color.z,0.f,1.f)*255)); Require(appliedOutput[pixel]==(0xff000000|(r<<16)|(g<<8)|b),"RC direct applied pixel mismatch"); if(appliedOutput[pixel]!=noCachePixels[pixel]) ++changedPixels; }
                    else Require(appliedOutput[pixel]==noCachePixels[pixel],"RC direct apply changed unmapped pixel");
                }
                Require(appliedCount==populated&&changedPixels>0&&changedPixels<=appliedCount,"RC direct applied coverage invalid"); presentationOutputSha=rrt::scene::Hex(rrt::scene::Digest(appliedOutput.data(),appliedOutput.size()*sizeof(appliedOutput[0]))); Require(presentationOutputSha!=noCacheOutputSha,"RC direct applied output unchanged"); applyAuditReadbackBytes=uint64_t(Rows)*sizeof(UINT);
            } catch(...) {
                renderer.gpu.Begin(); D3D12_RESOURCE_BARRIER restore[2]{}; for(auto& value:restore) value.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; restore[0].Transition={backup.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE}; restore[1].Transition={renderer.output.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_COPY_DEST}; renderer.gpu.list->ResourceBarrier(2,restore); renderer.gpu.list->CopyResource(renderer.output.Get(),backup.Get()); restore[1].Transition.StateBefore=D3D12_RESOURCE_STATE_COPY_DEST; restore[1].Transition.StateAfter=D3D12_RESOURCE_STATE_COPY_SOURCE; renderer.gpu.list->ResourceBarrier(1,&restore[1]); renderer.gpu.list->CopyResource(renderer.readback.Get(),renderer.output.Get()); renderer.gpu.Execute(); throw;
            }
        }
        transient.FinalState(raw.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        transient.FinalState(pixelMapping.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        for(auto& buffer:shared) transient.FinalState(buffer.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        transient.FinalState(candidate.Get(),options.rcPresentCandidate?D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE:D3D12_RESOURCE_STATE_COPY_SOURCE);
        transient.Recycle();
        const auto directEnd=std::chrono::steady_clock::now();
        std::ostringstream out; out << "{\"result\":\"rc-direct-shared-pass\",\"renderer_gpu_compaction\":true,\"renderer_path_readback_bytes\":0,\"provider_cpu_payload_transfer_bytes\":0,\"candidate_readback_bytes\":196608,\"pixel_mapping_bytes\":49152,\"pixel_mapping_order\":\"ascending-valid-pixels\",\"renderer_frame_input_submissions\":" << (options.rcLiveSessionTest?2:1) << ",\"populated_inference_samples\":" << populated << ",\"populated_training_samples\":" << std::min(populated,512u) << ",\"training_batches\":" << options.rcTrainingBatches << ",\"persistent_epochs\":" << options.rcPersistentEpochs << ",\"live_session\":" << (options.rcLiveSessionTest?"true":"false") << ",\"submitted_frame_epochs\":" << workerEpochs << ",\"camera_reset_epochs\":" << (options.rcLiveSessionTest?1:0) << ",\"provider_processes\":1,\"provider_process_id\":" << child.processId << ",\"provider_contexts\":1,\"provider_dispatches\":" << (workerEpochs==3?7+3*options.rcTrainingBatches:workerEpochs==1?3+options.rcTrainingBatches:5+2*options.rcTrainingBatches) << ",\"baseline_hash_fnv1a64\":" << baseline << ",\"first_epoch_post_hash_fnv1a64\":" << firstPost << ",\"second_epoch_start_hash_fnv1a64\":" << epochStart << ",\"stable_epoch_post_hash_fnv1a64\":" << stablePost << ",\"second_epoch_changed_values\":" << epochChanged << ",\"changed_frame_baseline_hash_fnv1a64\":" << changedBaseline << ",\"changed_frame_changed_values\":" << changedFrameValues << ",\"post_training_hash_fnv1a64\":" << post << ",\"reset_hash_fnv1a64\":" << reset << ",\"reset_exact\":true,\"post_composite_mse\":" << compositeMse << ",\"composite_admitted_pixels\":" << admitted << ",\"candidate_sha256\":" << QuoteBytes(rrt::scene::Hex(rrt::scene::Digest(composite.data(),composite.size()*sizeof(composite[0])))) << ",\"direct_wall_ms\":" << std::chrono::duration<double,std::milli>(directEnd-directStart).count() << ",\"shared_resources\":5,\"shared_fences\":1,\"allowlisted_handles\":6,\"fence_values\":\"" << (options.rcLiveSessionTest?"30/31/32/33/34/35":"30/31") << "\",\"child_reaped\":true,\"candidate_applied\":" << (options.rcPresentCandidate?"true":"false") << ",\"authoritative_output\":\"" << (options.rcPresentCandidate?"radiance-cache-candidate":"no-cache") << "\",\"apply_audit_readback_bytes\":" << applyAuditReadbackBytes << ",\"applied_pixels\":" << appliedCount << ",\"changed_pixels\":" << changedPixels << ",\"no_cache_output_sha256\":" << QuoteBytes(noCacheOutputSha) << ",\"presentation_output_sha256\":" << QuoteBytes(presentationOutputSha) << ",\"scene_sha256\":" << QuoteBytes(rrt::scene::Hex(sceneDigest)) << ",\"initial_frame_sha256\":" << QuoteBytes(rrt::scene::Hex(rrt::scene::Digest(&frame,sizeof(frame)))) << ",\"frame_sha256\":" << QuoteBytes(rrt::scene::Hex(rrt::scene::Digest(&finalFrame,sizeof(finalFrame)))) << '}'; return out.str();
    } catch(const std::exception& error) { std::ostringstream out; out << "{\"result\":\"rc-direct-shared-fallback\",\"reason\":" << QuoteBytes(error.what()) << ",\"candidate_applied\":false,\"authoritative_output\":\"no-cache\"}"; return out.str(); }
}
