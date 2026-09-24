#pragma once

void RcSharedWait(ID3D12Fence* fence,uint64_t value) {
    if(fence->GetCompletedValue()>=value) return;
    RcHandle event; event.value=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event.value!=nullptr,"RC shared fence event failed");
    Require(SUCCEEDED(fence->SetEventOnCompletion(value,event.value)),"RC shared fence completion failed");
    Require(WaitForSingleObject(event.value,30000)==WAIT_OBJECT_0,"RC shared fence timeout");
}
ComPtr<ID3D12CommandQueue> RcSharedQueue(ID3D12Device* device) {
    D3D12_COMMAND_QUEUE_DESC desc{}; desc.Type=D3D12_COMMAND_LIST_TYPE_DIRECT; ComPtr<ID3D12CommandQueue> queue;
    Require(SUCCEEDED(device->CreateCommandQueue(&desc,IID_PPV_ARGS(&queue))),"RC shared queue creation failed"); return queue;
}
RcExternalBuffer RcCreateSharedExternalBuffer(ID3D12Device* device,uint64_t bytes,uint32_t stride) {
    Require(bytes&&stride&&bytes%stride==0,"invalid RC shared external layout"); RcExternalBuffer value; value.bytes=bytes; value.stride=stride;
    D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=bytes; desc.Height=1; desc.DepthOrArraySize=1;
    desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    D3D12_HEAP_PROPERTIES heap{}; heap.Type=D3D12_HEAP_TYPE_DEFAULT;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_SHARED,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&value.gpu))),"RC shared external creation failed");
    desc.Flags=D3D12_RESOURCE_FLAG_NONE; heap.Type=D3D12_HEAP_TYPE_UPLOAD;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_GENERIC_READ,nullptr,IID_PPV_ARGS(&value.upload))),"RC shared upload creation failed");
    heap.Type=D3D12_HEAP_TYPE_READBACK;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&value.readback))),"RC shared readback creation failed"); return value;
}

int RcSharedProviderChild(ffxFunctions& api,ID3D12Device* device,uint64_t provider,bool wave32,const std::array<uint64_t,8>& values,LUID actualLuid) {
    const LUID expected{DWORD(values[6]),LONG(uint32_t(values[7]))}; Require(actualLuid.LowPart==expected.LowPart&&actualLuid.HighPart==expected.HighPart,"RC shared provider adapter LUID mismatch");
    constexpr uint64_t sizes[5]={sizeof(RcCacheInput)*InferenceSamples,sizeof(RcCacheOutput)*InferenceSamples,sizeof(RcCacheInput)*TrainingSamples,sizeof(RcCacheOutput)*TrainingSamples,sizeof(uint32_t)*2};
    constexpr uint32_t strides[5]={sizeof(RcCacheInput),sizeof(RcCacheOutput),sizeof(RcCacheInput),sizeof(RcCacheOutput),sizeof(uint32_t)};
    std::array<RcExternalBuffer,5> buffers;
    for(UINT i=0;i<5;++i) { Require(SUCCEEDED(device->OpenSharedHandle(HANDLE(uintptr_t(values[i])),IID_PPV_ARGS(&buffers[i].gpu))),"RC shared provider resource open failed");
        buffers[i].bytes=sizes[i]; buffers[i].stride=strides[i]; const auto desc=buffers[i].gpu->GetDesc();
        Require(desc.Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&desc.Width==sizes[i]&&(desc.Flags&D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS),"RC shared provider resource mismatch"); }
    ComPtr<ID3D12Fence> fence; Require(SUCCEEDED(device->OpenSharedHandle(HANDLE(uintptr_t(values[5])),IID_PPV_ARGS(&fence))),"RC shared provider fence open failed");
    ffxOverrideVersion version{}; version.header.type=FFX_API_DESC_TYPE_OVERRIDE_VERSION; version.versionId=provider; RcGpuBudget tracked(device,32ull*1024*1024,0);
    ffxCreateBackendDX12AllocationCallbacksDesc callbacks{}; callbacks.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12_ALLOCATION_CALLBACKS;
    callbacks.pfnFfxResourceAllocator=RcGpuBudget::Resource; callbacks.pfnFfxResourceDeallocator=RcGpuBudget::FreeResource; callbacks.pfnFfxHeapAllocator=RcGpuBudget::Heap; callbacks.pfnFfxHeapDeallocator=RcGpuBudget::FreeHeap; callbacks.header.pNext=&version.header;
    ffxCreateBackendDX12Desc backend{}; backend.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_DX12; backend.device=device; backend.header.pNext=&callbacks.header;
    auto create=[&](uint32_t flags,ffxContext& context) { ffxCreateContextDescRadianceCache desc{}; desc.header.type=FFX_API_CREATE_CONTEXT_DESC_TYPE_RADIANCECACHE; desc.header.pNext=&backend.header;
        desc.flags=flags; desc.version=FFX_RADIANCECACHE_VERSION; desc.maxInferenceSampleCount=InferenceSamples; desc.maxTrainingSampleCount=TrainingSamples; return api.CreateContext(&context,&desc.header,nullptr); };
    ffxContext context{}; auto createCode=create(FFX_RADIANCE_CACHE_CONTEXT_TRY_FORCE_WMMA,context);
    if(createCode==FFX_API_RETURN_ERROR_PARAMETER&&wave32&&!tracked.live) createCode=create(0,context);
    Require(createCode==FFX_API_RETURN_OK&&context,"RC shared provider context creation failed"); auto queue=RcSharedQueue(device); Require(SUCCEEDED(queue->Wait(fence.Get(),20)),"RC shared provider queue wait failed");
    ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
    Require(SUCCEEDED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"RC shared provider command list failed");
    ffxDispatchDescRadianceCache dispatch{}; dispatch.header.type=FFX_API_DISPATCH_DESC_TYPE_RADIANCECACHE; dispatch.commandList=list.Get();
    dispatch.predictionInputs=RcWrap(buffers[0]); dispatch.predictionOutputs=RcWrap(buffers[1]); dispatch.trainInputs=RcWrap(buffers[2]); dispatch.trainTargets=RcWrap(buffers[3]); dispatch.sampleCounters=RcWrap(buffers[4]);
    dispatch.flags=FFX_RADIANCE_CACHE_RESET|FFX_RADIANCE_CACHE_DISPATCH_INFERENCE|FFX_RADIANCE_CACHE_CLEAR_ALL_COUNTERS;
    Require(api.Dispatch(&context,&dispatch.header)==FFX_API_RETURN_OK,"RC shared provider dispatch failed"); Require(SUCCEEDED(list->Close()),"RC shared provider close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists);
    Require(SUCCEEDED(queue->Signal(fence.Get(),21)),"RC shared provider signal failed"); RcSharedWait(fence.Get(),21); const auto removed=device->GetDeviceRemovedReason(); Require(removed==S_OK,"RC shared provider device removed");
    Require(api.DestroyContext(&context,nullptr)==FFX_API_RETURN_OK,"RC shared provider destroy failed"); context=nullptr;
    Require(tracked.peak>0&&tracked.peak<=32ull*1024*1024&&!tracked.live&&!tracked.denials&&!tracked.errors&&tracked.allocations==tracked.releases,"RC shared provider allocation accounting failed");
    std::cout << "{\"shared_provider_child\":true,\"dispatch_code\":0,\"fence_value\":21,\"destroyed\":true}"; return 0;
}

std::string RcSharedProviderParent(ID3D12Device* device,UINT adapterIndex,LUID luid,const std::filesystem::path& directory) {
    std::vector<RcCacheInput> predictions(InferenceSamples),training(TrainingSamples); std::vector<RcCacheOutput> outputs(InferenceSamples),targets(TrainingSamples);
    for(UINT i=0;i<InferenceSamples;++i) { const float x=float(i%128)/127.0f,y=float(i/128)/95.0f; predictions[i]={{x,y,0.25f+0.5f*y},{0.0f,0.5f},{0.0f,0.5f},{0.15f+0.7f*x,0.1f+0.6f*y,0.2f+0.3f*x*y},0.2f+0.6f*y}; for(float& value:outputs[i].radiance) value=std::numeric_limits<float>::quiet_NaN(); }
    for(UINT i=0;i<TrainingSamples;++i) { training[i]=predictions[size_t(i)*InferenceSamples/TrainingSamples]; const float x=training[i].position[0],y=training[i].position[1]; targets[i]={{0.05f+0.45f*x,0.1f+0.35f*y,0.025f+0.25f*x*y}}; }
    const auto originalPredictions=predictions; const auto originalTraining=training; const auto originalTargets=targets; std::array<uint32_t,2> counters={InferenceSamples,0};
    std::array<RcExternalBuffer,5> buffers={RcCreateSharedExternalBuffer(device,sizeof(RcCacheInput)*InferenceSamples,sizeof(RcCacheInput)),RcCreateSharedExternalBuffer(device,sizeof(RcCacheOutput)*InferenceSamples,sizeof(RcCacheOutput)),
        RcCreateSharedExternalBuffer(device,sizeof(RcCacheInput)*TrainingSamples,sizeof(RcCacheInput)),RcCreateSharedExternalBuffer(device,sizeof(RcCacheOutput)*TrainingSamples,sizeof(RcCacheOutput)),RcCreateSharedExternalBuffer(device,sizeof(counters),sizeof(uint32_t))};
    RcUpload(buffers[0],predictions.data()); RcUpload(buffers[1],outputs.data()); RcUpload(buffers[2],training.data()); RcUpload(buffers[3],targets.data()); RcUpload(buffers[4],counters.data());
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE}; std::array<RcHandle,5> resourceHandles; std::vector<HANDLE> inherited;
    for(UINT i=0;i<5;++i) { Require(SUCCEEDED(device->CreateSharedHandle(buffers[i].gpu.Get(),&security,GENERIC_ALL,nullptr,&resourceHandles[i].value)),"RC shared provider handle failed"); inherited.push_back(resourceHandles[i].value); }
    ComPtr<ID3D12Fence> fence; RcHandle fenceHandle; Require(SUCCEEDED(device->CreateFence(0,D3D12_FENCE_FLAG_SHARED,IID_PPV_ARGS(&fence)))&&SUCCEEDED(device->CreateSharedHandle(fence.Get(),&security,GENERIC_ALL,nullptr,&fenceHandle.value)),"RC shared provider fence creation failed"); inherited.push_back(fenceHandle.value);
    auto queue=RcSharedQueue(device); ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
    Require(SUCCEEDED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"RC shared provider upload list failed");
    for(auto& buffer:buffers) { list->CopyResource(buffer.gpu.Get(),buffer.upload.Get()); RcTransition(list.Get(),buffer.gpu.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE); }
    Require(SUCCEEDED(list->Close()),"RC shared provider upload close failed"); ID3D12CommandList* uploadLists[]={list.Get()}; queue->ExecuteCommandLists(1,uploadLists); Require(SUCCEEDED(queue->Signal(fence.Get(),20)),"RC shared provider parent signal failed");
    std::vector<std::wstring> args={L"--sdk-bin",directory.wstring(),L"--adapter",std::to_wstring(adapterIndex),L"--shared-worker-child"}; for(auto& handle:resourceHandles) args.push_back(std::to_wstring(uintptr_t(handle.value)));
    args.push_back(std::to_wstring(uintptr_t(fenceHandle.value))); args.push_back(std::to_wstring(luid.LowPart)); args.push_back(std::to_wstring(uint32_t(luid.HighPart)));
    const auto child=RcRunIsolated(args,30000,false,nullptr,&inherited);
    if(!(child.reaped&&!child.timedOut&&!child.overflow&&child.exitCode==0&&child.error.empty()&&child.output=="{\"shared_provider_child\":true,\"dispatch_code\":0,\"fence_value\":21,\"destroyed\":true}"))
        throw std::runtime_error("RC shared provider child validation failed: stdout="+child.output+" stderr="+child.error+" exit="+std::to_string(child.exitCode));
    RcSharedWait(fence.Get(),21);
    allocator.Reset(); list.Reset(); Require(SUCCEEDED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"RC shared provider readback list failed");
    for(auto& buffer:buffers) { RcTransition(list.Get(),buffer.gpu.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE); list->CopyResource(buffer.readback.Get(),buffer.gpu.Get()); }
    Require(SUCCEEDED(list->Close()),"RC shared provider readback close failed"); ID3D12CommandList* readLists[]={list.Get()}; queue->ExecuteCommandLists(1,readLists); Require(SUCCEEDED(queue->Signal(fence.Get(),22)),"RC shared provider readback signal failed"); RcSharedWait(fence.Get(),22);
    RcReadback(buffers[0],predictions.data()); RcReadback(buffers[1],outputs.data()); RcReadback(buffers[2],training.data()); RcReadback(buffers[3],targets.data()); RcReadback(buffers[4],counters.data());
    Require(std::memcmp(predictions.data(),originalPredictions.data(),predictions.size()*sizeof(predictions[0]))==0
        &&std::memcmp(training.data(),originalTraining.data(),training.size()*sizeof(training[0]))==0
        &&std::memcmp(targets.data(),originalTargets.data(),targets.size()*sizeof(targets[0]))==0,"RC shared provider immutable input changed"); Require(counters[0]==0&&counters[1]==0,"RC shared provider counters not cleared");
    uint32_t finite=0,nonnegative=0,changed=0; for(const auto& output:outputs) for(float value:output.radiance) { if(std::isfinite(value)) ++finite; if(std::isfinite(value)&&value>=0) ++nonnegative; if(!std::isnan(value)) ++changed; }
    Require(finite==InferenceSamples*3&&nonnegative==InferenceSamples*3&&changed==InferenceSamples*3,"RC shared provider output invalid"); const auto hash=RcHash(outputs.data(),outputs.size()*sizeof(outputs[0]));
    std::ostringstream out; out << "{\"result\":\"shared-provider-dispatch-pass\",\"external_buffer_bytes\":716808,\"output_hash_fnv1a64\":" << hash
        << ",\"finite_output_values\":" << finite << ",\"counters_cleared\":true,\"inputs_unchanged\":true,\"shared_resources\":5,\"shared_fences\":1,\"allowlisted_handles\":6,\"fence_values\":[20,21,22],\"child_reaped\":true,\"child_exit_code\":0,\"cpu_payload_transfer_bytes\":0}"; return out.str();
}
