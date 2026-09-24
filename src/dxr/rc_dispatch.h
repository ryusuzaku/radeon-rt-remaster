#pragma once

struct RcCacheInput {
    float position[3];
    float normal[2];
    float viewDirection[2];
    float diffuseAlbedo[3];
    float roughness;
};
struct RcCacheOutput { float radiance[3]; };
static_assert(sizeof(RcCacheInput)==44 && sizeof(RcCacheOutput)==12,"Radiance Cache sample layout changed");

struct RcExternalBuffer {
    ComPtr<ID3D12Resource> gpu,upload,readback;
    uint64_t bytes{}; uint32_t stride{};
};

RcExternalBuffer RcCreateExternalBuffer(ID3D12Device* device,uint64_t bytes,uint32_t stride) {
    Require(bytes&&bytes<=UINT32_MAX&&stride&&bytes%stride==0,"invalid RC external buffer layout");
    RcExternalBuffer value; value.bytes=bytes; value.stride=stride;
    D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=bytes; desc.Height=1; desc.DepthOrArraySize=1;
    desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    D3D12_HEAP_PROPERTIES heap{}; heap.Type=D3D12_HEAP_TYPE_DEFAULT;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&value.gpu))),"RC external GPU buffer creation failed");
    desc.Flags=D3D12_RESOURCE_FLAG_NONE; heap.Type=D3D12_HEAP_TYPE_UPLOAD;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&value.upload))),"RC upload buffer creation failed");
    heap.Type=D3D12_HEAP_TYPE_READBACK;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&value.readback))),"RC readback buffer creation failed");
    return value;
}

void RcUpload(RcExternalBuffer& buffer,const void* source) {
    void* mapped{}; D3D12_RANGE empty{};
    Require(SUCCEEDED(buffer.upload->Map(0,&empty,&mapped))&&mapped,"RC upload map failed");
    std::memcpy(mapped,source,size_t(buffer.bytes)); buffer.upload->Unmap(0,nullptr);
}
void RcReadback(RcExternalBuffer& buffer,void* destination) {
    void* mapped{}; const D3D12_RANGE range{0,SIZE_T(buffer.bytes)};
    Require(SUCCEEDED(buffer.readback->Map(0,&range,&mapped))&&mapped,"RC readback map failed");
    std::memcpy(destination,mapped,size_t(buffer.bytes)); const D3D12_RANGE empty{}; buffer.readback->Unmap(0,&empty);
}
FfxApiResource RcWrap(RcExternalBuffer& buffer) {
    auto resource=ffxApiGetResourceDX12(buffer.gpu.Get(),FFX_API_RESOURCE_STATE_COMPUTE_READ,0);
    resource.description.stride=buffer.stride; return resource;
}
void RcTransition(ID3D12GraphicsCommandList* list,ID3D12Resource* resource,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after) {
    D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; barrier.Transition.pResource=resource;
    barrier.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES; barrier.Transition.StateBefore=before; barrier.Transition.StateAfter=after;
    list->ResourceBarrier(1,&barrier);
}
uint64_t RcHash(const void* data,size_t size) {
    uint64_t hash=14695981039346656037ull; const auto* bytes=static_cast<const unsigned char*>(data);
    for(size_t i=0;i<size;++i) { hash^=bytes[i]; hash*=1099511628211ull; } return hash;
}

struct RcDispatchResult {
    const char* result="not-created"; const char* backend="none"; const char* mode="none";
    uint32_t wmmaCode=UINT32_MAX,fallbackCode=UINT32_MAX,dispatchCode=UINT32_MAX,providerCode=UINT32_MAX,destroyCode=UINT32_MAX;
    uint32_t countersAfter[2]{}; uint32_t finiteValues{},nonnegativeValues{},changedValues{};
    uint64_t requestedProvider{},provider{},budget{},peak{},live{},attempts{},allocations{},releases{},denials{},errors{},outputHash{};
    double outputMinimum{},outputMaximum{},outputMean{}; long deviceRemovedReason{};
    bool wmmaAttempted{},fallbackAttempted{},created{},submitted{},fenceCompleted{},inputsUnchanged{},targetsUnchanged{},destroyed{},mechanicalPass{},rawPass{};
    std::string Json() const {
        std::ostringstream out;
        out << "{\"result\":" << Quote(result) << ",\"validation\":true,\"hard_budget_enforced\":true,\"mode\":" << Quote(mode)
            << ",\"max_inference_samples\":" << InferenceSamples << ",\"max_training_samples\":" << TrainingSamples
            << ",\"populated_inference_samples\":" << InferenceSamples << ",\"populated_training_samples\":" << (std::string(mode)=="combined"?TrainingSamples:0)
            << ",\"external_buffer_bytes\":716808,\"staging_buffer_bytes\":1433616,\"budget_bytes\":" << budget
            << ",\"wmma_attempted\":" << (wmmaAttempted?"true":"false") << ",\"wmma_create_code\":" << wmmaCode
            << ",\"fallback_attempted\":" << (fallbackAttempted?"true":"false") << ",\"fallback_create_code\":" << fallbackCode
            << ",\"selected_backend\":" << Quote(backend) << ",\"created\":" << (created?"true":"false")
            << ",\"dispatch_code\":" << dispatchCode << ",\"submitted\":" << (submitted?"true":"false") << ",\"fence_completed\":" << (fenceCompleted?"true":"false")
            << ",\"counter_inference_after\":" << countersAfter[0] << ",\"counter_training_after\":" << countersAfter[1]
            << ",\"finite_output_values\":" << finiteValues << ",\"nonnegative_output_values\":" << nonnegativeValues
            << ",\"changed_output_values\":" << changedValues << ",\"output_hash_fnv1a64\":" << outputHash
            << ",\"output_minimum\":" << outputMinimum << ",\"output_maximum\":" << outputMaximum << ",\"output_mean\":" << outputMean
            << ",\"inputs_unchanged\":" << (inputsUnchanged?"true":"false") << ",\"targets_unchanged\":" << (targetsUnchanged?"true":"false")
            << ",\"device_removed_reason\":" << deviceRemovedReason << ",\"mechanical_pass\":" << (mechanicalPass?"true":"false")
            << ",\"requested_provider_id\":" << requestedProvider << ",\"provider_query_code\":" << providerCode << ",\"provider_id\":" << provider
            << ",\"destroy_code\":" << destroyCode << ",\"destroyed\":" << (destroyed?"true":"false")
            << ",\"callback_peak_bytes\":" << peak << ",\"callback_live_bytes_after_destroy\":" << live
            << ",\"allocation_attempts\":" << attempts << ",\"allocations\":" << allocations << ",\"releases\":" << releases
            << ",\"allocation_denials\":" << denials << ",\"callback_errors\":" << errors << '}'; return out.str();
    }
};

RcDispatchResult TestRcDispatch(ffxFunctions& api,ID3D12Device* device,uint64_t provider,uint64_t budget,bool wave32,bool combined) {
    RcDispatchResult result; result.mode=combined?"combined":"inference"; result.budget=budget; result.requestedProvider=provider;
    std::vector<RcCacheInput> predictions(InferenceSamples),training(TrainingSamples);
    std::vector<RcCacheOutput> outputs(InferenceSamples),targets(TrainingSamples);
    for(UINT i=0;i<InferenceSamples;++i) {
        const float x=float(i%128)/127.0f,y=float(i/128)/95.0f;
        predictions[i]={{x,y,0.25f+0.5f*y},{0.0f,0.5f},{0.0f,0.5f},{0.15f+0.7f*x,0.1f+0.6f*y,0.2f+0.3f*x*y},0.2f+0.6f*y};
        for(float& value:outputs[i].radiance) value=std::numeric_limits<float>::quiet_NaN();
    }
    for(UINT i=0;i<TrainingSamples;++i) {
        training[i]=predictions[size_t(i)*InferenceSamples/TrainingSamples]; const float x=training[i].position[0],y=training[i].position[1];
        targets[i]={{0.05f+0.45f*x,0.1f+0.35f*y,0.025f+0.25f*x*y}};
    }
    const auto predictionsOriginal=predictions;
    const auto trainingOriginal=training;
    const auto targetsOriginal=targets;
    std::array<uint32_t,2> counters={InferenceSamples,combined?TrainingSamples:0u};
    ffxOverrideVersion version{}; version.header.type=FFX_API_DESC_TYPE_OVERRIDE_VERSION; version.versionId=provider;
    RcGpuBudget tracked(device,budget,0);
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
        auto predIn=RcCreateExternalBuffer(device,sizeof(RcCacheInput)*InferenceSamples,sizeof(RcCacheInput));
        auto predOut=RcCreateExternalBuffer(device,sizeof(RcCacheOutput)*InferenceSamples,sizeof(RcCacheOutput));
        auto trainIn=RcCreateExternalBuffer(device,sizeof(RcCacheInput)*TrainingSamples,sizeof(RcCacheInput));
        auto trainOut=RcCreateExternalBuffer(device,sizeof(RcCacheOutput)*TrainingSamples,sizeof(RcCacheOutput));
        auto counter=RcCreateExternalBuffer(device,sizeof(counters),sizeof(uint32_t));
        RcUpload(predIn,predictions.data()); RcUpload(predOut,outputs.data()); RcUpload(trainIn,training.data()); RcUpload(trainOut,targets.data()); RcUpload(counter,counters.data());
        ComPtr<ID3D12CommandQueue> queue; D3D12_COMMAND_QUEUE_DESC queueDesc{}; queueDesc.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
        Require(SUCCEEDED(device->CreateCommandQueue(&queueDesc,IID_PPV_ARGS(&queue))),"RC queue creation failed");
        ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
        Require(SUCCEEDED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator))),"RC allocator creation failed");
        Require(SUCCEEDED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"RC command list creation failed");
        std::array<RcExternalBuffer*,5> buffers={&predIn,&predOut,&trainIn,&trainOut,&counter};
        for(auto* buffer:buffers) { list->CopyBufferRegion(buffer->gpu.Get(),0,buffer->upload.Get(),0,buffer->bytes); RcTransition(list.Get(),buffer->gpu.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE); }
        ffxDispatchDescRadianceCache dispatch{}; dispatch.header.type=FFX_API_DISPATCH_DESC_TYPE_RADIANCECACHE; dispatch.commandList=list.Get();
        dispatch.predictionInputs=RcWrap(predIn); dispatch.predictionOutputs=RcWrap(predOut); dispatch.trainInputs=RcWrap(trainIn);
        dispatch.trainTargets=RcWrap(trainOut); dispatch.sampleCounters=RcWrap(counter);
        dispatch.flags=FFX_RADIANCE_CACHE_RESET|FFX_RADIANCE_CACHE_DISPATCH_INFERENCE|FFX_RADIANCE_CACHE_CLEAR_ALL_COUNTERS;
        if(combined) dispatch.flags|=FFX_RADIANCE_CACHE_DISPATCH_TRAINING;
        result.dispatchCode=api.Dispatch(&context,&dispatch.header);
        if(result.dispatchCode==FFX_API_RETURN_OK) {
            for(auto* buffer:buffers) { RcTransition(list.Get(),buffer->gpu.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE); list->CopyBufferRegion(buffer->readback.Get(),0,buffer->gpu.Get(),0,buffer->bytes); }
            Require(SUCCEEDED(list->Close()),"RC command list close failed"); ID3D12CommandList* submitted[]={list.Get()}; queue->ExecuteCommandLists(1,submitted); result.submitted=true;
            ComPtr<ID3D12Fence> fence; Require(SUCCEEDED(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence))),"RC fence creation failed");
            HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event!=nullptr,"RC fence event creation failed");
            Require(SUCCEEDED(queue->Signal(fence.Get(),1))&&SUCCEEDED(fence->SetEventOnCompletion(1,event)),"RC fence signal failed");
            const DWORD wait=WaitForSingleObject(event,30000); CloseHandle(event); result.fenceCompleted=wait==WAIT_OBJECT_0;
            if(result.fenceCompleted) {
                RcReadback(predIn,predictions.data()); RcReadback(predOut,outputs.data()); RcReadback(trainIn,training.data()); RcReadback(trainOut,targets.data()); RcReadback(counter,result.countersAfter);
                result.inputsUnchanged=std::memcmp(predictions.data(),predictionsOriginal.data(),predictions.size()*sizeof(predictions[0]))==0
                    &&std::memcmp(training.data(),trainingOriginal.data(),training.size()*sizeof(training[0]))==0;
                result.targetsUnchanged=std::memcmp(targets.data(),targetsOriginal.data(),targets.size()*sizeof(targets[0]))==0;
                double sum=0; result.outputMinimum=std::numeric_limits<double>::infinity(); result.outputMaximum=-std::numeric_limits<double>::infinity();
                for(const auto& output:outputs) for(float value:output.radiance) {
                    if(std::isfinite(value)) { ++result.finiteValues; result.outputMinimum=std::min(result.outputMinimum,double(value)); result.outputMaximum=std::max(result.outputMaximum,double(value)); sum+=value; }
                    if(std::isfinite(value)&&value>=0) ++result.nonnegativeValues; if(!std::isnan(value)) ++result.changedValues;
                }
                result.outputMean=result.finiteValues?sum/result.finiteValues:0; result.outputHash=RcHash(outputs.data(),outputs.size()*sizeof(outputs[0]));
            }
        }
        result.deviceRemovedReason=device->GetDeviceRemovedReason();
        ffxQueryGetProviderVersion selected{}; selected.header.type=FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
        result.providerCode=api.Query(&context,&selected.header); result.provider=selected.versionId;
        result.destroyCode=api.DestroyContext(&context,nullptr); if(result.destroyCode==FFX_API_RETURN_OK) context=nullptr; result.destroyed=!context&&result.destroyCode==FFX_API_RETURN_OK;
    }
    result.peak=tracked.peak; result.live=tracked.live; result.attempts=tracked.attempts; result.allocations=tracked.allocations;
    result.releases=tracked.releases; result.denials=tracked.denials; result.errors=tracked.errors;
    const uint32_t outputValues=InferenceSamples*3;
    result.mechanicalPass=result.created&&result.dispatchCode==FFX_API_RETURN_OK&&result.submitted&&result.fenceCompleted
        &&result.countersAfter[0]==0&&result.countersAfter[1]==0&&result.finiteValues==outputValues&&result.nonnegativeValues==outputValues
        &&result.changedValues==outputValues&&result.inputsUnchanged&&result.targetsUnchanged&&result.deviceRemovedReason==S_OK&&result.destroyed
        &&result.peak>0&&result.peak<=budget&&!result.live&&!result.denials&&!result.errors&&result.allocations==result.releases;
    result.rawPass=result.mechanicalPass&&result.providerCode==FFX_API_RETURN_OK&&result.provider==provider;
    result.result=result.rawPass?"dispatch-pass":result.mechanicalPass?"dispatch-pass-provider-metadata-failed":result.created?"dispatch-validation-failed":"context-create-failed";
    return result;
}
