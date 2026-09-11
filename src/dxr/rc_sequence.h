#pragma once

struct RcSequenceStep {
    const char* name="none"; uint32_t dispatchCode=UINT32_MAX,counters[2]{},finite{},nonnegative{},changed{};
    uint64_t outputHash{}; double minimum{},maximum{},mean{},targetMse{};
    bool submitted{},fenceCompleted{},inputsUnchanged{},targetsUnchanged{},deviceHealthy{},pass{};
    std::string Json() const {
        std::ostringstream out; out << "{\"name\":" << Quote(name) << ",\"dispatch_code\":" << dispatchCode
            << ",\"submitted\":" << (submitted?"true":"false") << ",\"fence_completed\":" << (fenceCompleted?"true":"false")
            << ",\"counter_inference_after\":" << counters[0] << ",\"counter_training_after\":" << counters[1]
            << ",\"finite_output_values\":" << finite << ",\"nonnegative_output_values\":" << nonnegative << ",\"changed_output_values\":" << changed
            << ",\"output_hash_fnv1a64\":" << outputHash << ",\"output_minimum\":" << minimum << ",\"output_maximum\":" << maximum
            << ",\"output_mean\":" << mean << ",\"target_mse\":" << targetMse
            << ",\"inputs_unchanged\":" << (inputsUnchanged?"true":"false") << ",\"targets_unchanged\":" << (targetsUnchanged?"true":"false")
            << ",\"device_healthy\":" << (deviceHealthy?"true":"false") << ",\"pass\":" << (pass?"true":"false") << '}'; return out.str();
    }
};

struct RcSequenceResult {
    const char* result="not-created"; const char* backend="none";
    uint32_t batches{},wmmaCode=UINT32_MAX,fallbackCode=UINT32_MAX,providerCode=UINT32_MAX,destroyCode=UINT32_MAX;
    uint64_t requestedProvider{},provider{},budget{},peak{},live{},attempts{},allocations{},releases{},denials{},errors{};
    uint32_t postChangedValues{},resetChangedValues{}; double postMse{},postMaxAbs{},resetMse{},resetMaxAbs{};
    uint32_t populatedInference{},populatedTraining{}; double baselineCompositeMse{},postCompositeMse{}; std::string artifactSha256;
    bool rendererFixture{},compositeImproved{};
    bool wmmaAttempted{},fallbackAttempted{},created{},destroyed{},retainedStateObserved{},targetImproved{},resetExact{},mechanicalPass{},rawPass{};
    std::vector<RcSequenceStep> steps;
    std::string Json() const {
        std::ostringstream out; out << "{\"result\":" << Quote(result) << ",\"validation\":true,\"hard_budget_enforced\":true,\"mode\":\"sequence\""
            << ",\"training_batches\":" << batches << ",\"max_inference_samples\":" << InferenceSamples << ",\"max_training_samples\":" << TrainingSamples
            << ",\"renderer_fixture\":" << (rendererFixture?"true":"false") << ",\"populated_inference_samples\":" << populatedInference
            << ",\"populated_training_samples\":" << populatedTraining << ",\"artifact_sha256\":" << QuoteBytes(artifactSha256)
            << ",\"external_buffer_bytes\":716808,\"staging_buffer_bytes\":1433616,\"budget_bytes\":" << budget
            << ",\"wmma_attempted\":" << (wmmaAttempted?"true":"false") << ",\"wmma_create_code\":" << wmmaCode
            << ",\"fallback_attempted\":" << (fallbackAttempted?"true":"false") << ",\"fallback_create_code\":" << fallbackCode
            << ",\"selected_backend\":" << Quote(backend) << ",\"created\":" << (created?"true":"false") << ",\"steps\":[";
        for(size_t i=0;i<steps.size();++i) { if(i) out << ','; out << steps[i].Json(); }
        out << "],\"post_changed_values\":" << postChangedValues << ",\"post_vs_baseline_mse\":" << postMse << ",\"post_vs_baseline_max_abs\":" << postMaxAbs
            << ",\"reset_changed_values\":" << resetChangedValues << ",\"reset_vs_baseline_mse\":" << resetMse << ",\"reset_vs_baseline_max_abs\":" << resetMaxAbs
            << ",\"retained_state_observed\":" << (retainedStateObserved?"true":"false") << ",\"target_mse_improved\":" << (targetImproved?"true":"false")
            << ",\"reset_exact\":" << (resetExact?"true":"false") << ",\"mechanical_pass\":" << (mechanicalPass?"true":"false")
            << ",\"baseline_composite_mse\":" << baselineCompositeMse << ",\"post_composite_mse\":" << postCompositeMse
            << ",\"composite_mse_improved\":" << (compositeImproved?"true":"false")
            << ",\"requested_provider_id\":" << requestedProvider << ",\"provider_query_code\":" << providerCode << ",\"provider_id\":" << provider
            << ",\"destroy_code\":" << destroyCode << ",\"destroyed\":" << (destroyed?"true":"false")
            << ",\"callback_peak_bytes\":" << peak << ",\"callback_live_bytes_after_destroy\":" << live
            << ",\"allocation_attempts\":" << attempts << ",\"allocations\":" << allocations << ",\"releases\":" << releases
            << ",\"allocation_denials\":" << denials << ",\"callback_errors\":" << errors << '}'; return out.str();
    }
};

RcSequenceResult TestRcSequence(ffxFunctions& api,ID3D12Device* device,uint64_t provider,uint64_t budget,bool wave32,uint32_t batches,const RcPathSequenceFixture* fixture=nullptr) {
    RcSequenceResult result; result.batches=batches; result.budget=budget; result.requestedProvider=provider;
    std::vector<RcCacheInput> predictions(InferenceSamples),training(TrainingSamples);
    std::vector<RcCacheOutput> outputs(InferenceSamples),targets(TrainingSamples),expectedTargets(InferenceSamples);
    uint32_t inferenceCount=InferenceSamples,trainingCount=TrainingSamples;
    if(fixture) {
        inferenceCount=UINT(fixture->predictions.size()); trainingCount=UINT(fixture->training.size()); result.rendererFixture=true;
        result.artifactSha256=fixture->artifactSha256; std::copy(fixture->predictions.begin(),fixture->predictions.end(),predictions.begin());
        std::copy(fixture->training.begin(),fixture->training.end(),training.begin()); std::copy(fixture->targets.begin(),fixture->targets.end(),expectedTargets.begin());
        std::copy(fixture->targets.begin(),fixture->targets.begin()+trainingCount,targets.begin());
    } else {
        for(UINT i=0;i<InferenceSamples;++i) { const float x=float(i%128)/127.0f,y=float(i/128)/95.0f;
            predictions[i]={{x,y,0.25f+0.5f*y},{0.0f,0.5f},{0.0f,0.5f},{0.15f+0.7f*x,0.1f+0.6f*y,0.2f+0.3f*x*y},0.2f+0.6f*y};
            expectedTargets[i]={{0.05f+0.45f*x,0.1f+0.35f*y,0.025f+0.25f*x*y}}; }
        for(UINT i=0;i<TrainingSamples;++i) { const size_t source=size_t(i)*InferenceSamples/TrainingSamples; training[i]=predictions[source]; targets[i]=expectedTargets[source]; }
    }
    result.populatedInference=inferenceCount; result.populatedTraining=trainingCount;
    const auto predictionsOriginal=predictions;
    const auto trainingOriginal=training;
    const auto targetsOriginal=targets;
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
    std::vector<RcCacheOutput> baseline,post,reset;
    if(result.created) {
        auto predIn=RcCreateExternalBuffer(device,sizeof(RcCacheInput)*InferenceSamples,sizeof(RcCacheInput));
        auto predOut=RcCreateExternalBuffer(device,sizeof(RcCacheOutput)*InferenceSamples,sizeof(RcCacheOutput));
        auto trainIn=RcCreateExternalBuffer(device,sizeof(RcCacheInput)*TrainingSamples,sizeof(RcCacheInput));
        auto trainOut=RcCreateExternalBuffer(device,sizeof(RcCacheOutput)*TrainingSamples,sizeof(RcCacheOutput));
        std::array<uint32_t,2> occupancy{}; auto counter=RcCreateExternalBuffer(device,sizeof(occupancy),sizeof(uint32_t));
        std::array<RcExternalBuffer*,5> buffers={&predIn,&predOut,&trainIn,&trainOut,&counter};
        ComPtr<ID3D12CommandQueue> queue; D3D12_COMMAND_QUEUE_DESC queueDesc{}; queueDesc.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
        Require(SUCCEEDED(device->CreateCommandQueue(&queueDesc,IID_PPV_ARGS(&queue))),"RC sequence queue creation failed");
        ComPtr<ID3D12Fence> fence; Require(SUCCEEDED(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence))),"RC sequence fence creation failed");
        HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event!=nullptr,"RC sequence event creation failed");
        uint64_t fenceValue=0; bool first=true;
        auto runStep=[&](const char* name,uint32_t flags,uint32_t inferenceCount,uint32_t trainingCount,bool expectInference,std::vector<RcCacheOutput>* captured) {
            RcSequenceStep step; step.name=name; occupancy={inferenceCount,trainingCount};
            for(auto& output:outputs) for(float& value:output.radiance) value=std::numeric_limits<float>::quiet_NaN();
            RcUpload(predIn,predictionsOriginal.data()); RcUpload(predOut,outputs.data()); RcUpload(trainIn,trainingOriginal.data()); RcUpload(trainOut,targetsOriginal.data()); RcUpload(counter,occupancy.data());
            ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
            Require(SUCCEEDED(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator))),"RC sequence allocator creation failed");
            Require(SUCCEEDED(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"RC sequence command list creation failed");
            for(auto* buffer:buffers) {
                if(!first) RcTransition(list.Get(),buffer->gpu.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_COPY_DEST);
                list->CopyBufferRegion(buffer->gpu.Get(),0,buffer->upload.Get(),0,buffer->bytes);
                RcTransition(list.Get(),buffer->gpu.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            }
            first=false;
            ffxDispatchDescRadianceCache dispatch{}; dispatch.header.type=FFX_API_DISPATCH_DESC_TYPE_RADIANCECACHE; dispatch.commandList=list.Get();
            dispatch.predictionInputs=RcWrap(predIn); dispatch.predictionOutputs=RcWrap(predOut); dispatch.trainInputs=RcWrap(trainIn);
            dispatch.trainTargets=RcWrap(trainOut); dispatch.sampleCounters=RcWrap(counter); dispatch.flags=flags|FFX_RADIANCE_CACHE_CLEAR_ALL_COUNTERS;
            step.dispatchCode=api.Dispatch(&context,&dispatch.header);
            if(step.dispatchCode==FFX_API_RETURN_OK) {
                for(auto* buffer:buffers) { RcTransition(list.Get(),buffer->gpu.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE); list->CopyBufferRegion(buffer->readback.Get(),0,buffer->gpu.Get(),0,buffer->bytes); }
                Require(SUCCEEDED(list->Close()),"RC sequence command list close failed"); ID3D12CommandList* submitted[]={list.Get()}; queue->ExecuteCommandLists(1,submitted); step.submitted=true;
                ++fenceValue; Require(SUCCEEDED(queue->Signal(fence.Get(),fenceValue))&&SUCCEEDED(fence->SetEventOnCompletion(fenceValue,event)),"RC sequence fence signal failed");
                step.fenceCompleted=WaitForSingleObject(event,30000)==WAIT_OBJECT_0;
                if(step.fenceCompleted) {
                    RcReadback(predIn,predictions.data()); RcReadback(predOut,outputs.data()); RcReadback(trainIn,training.data()); RcReadback(trainOut,targets.data()); RcReadback(counter,step.counters);
                    step.inputsUnchanged=std::memcmp(predictions.data(),predictionsOriginal.data(),predictions.size()*sizeof(predictions[0]))==0
                        &&std::memcmp(training.data(),trainingOriginal.data(),training.size()*sizeof(training[0]))==0;
                    step.targetsUnchanged=std::memcmp(targets.data(),targetsOriginal.data(),targets.size()*sizeof(targets[0]))==0;
                    double sum=0,error=0; step.minimum=std::numeric_limits<double>::infinity(); step.maximum=-std::numeric_limits<double>::infinity();
                    for(size_t i=0;i<outputs.size();++i) for(size_t channel=0;channel<3;++channel) {
                        const float value=outputs[i].radiance[channel];
                        if(std::isfinite(value)) { ++step.finite; step.minimum=std::min(step.minimum,double(value)); step.maximum=std::max(step.maximum,double(value)); sum+=value; }
                        if(std::isfinite(value)&&value>=0) ++step.nonnegative; if(!std::isnan(value)) ++step.changed;
                        if(expectInference&&i<inferenceCount&&std::isfinite(value)) {
                            const float expected=expectedTargets[i].radiance[channel];
                            const double difference=double(value)-expected; error+=difference*difference;
                        }
                    }
                    if(!step.finite) step.minimum=step.maximum=0;
                    step.mean=step.finite?sum/step.finite:0; step.targetMse=expectInference?error/(inferenceCount*3):0;
                    step.outputHash=RcHash(outputs.data(),outputs.size()*sizeof(outputs[0])); if(captured) *captured=outputs;
                }
            }
            // The preview WMMA provider writes the full fixed-capacity prediction output even when the occupancy counter is smaller.
            // Only populated entries participate in target/composite metrics; the complete write remains finite/nonnegative guarded.
            step.deviceHealthy=device->GetDeviceRemovedReason()==S_OK; const uint32_t values=InferenceSamples*3;
            step.pass=step.dispatchCode==FFX_API_RETURN_OK&&step.submitted&&step.fenceCompleted&&step.counters[0]==0&&step.counters[1]==0
                &&step.inputsUnchanged&&step.targetsUnchanged&&step.deviceHealthy
                &&(expectInference?(step.finite==values&&step.nonnegative==values&&step.changed==values):(step.finite==0&&step.changed==0));
            result.steps.push_back(step); return step.pass;
        };
        bool sequenceOk=runStep("baseline-reset-inference",FFX_RADIANCE_CACHE_RESET|FFX_RADIANCE_CACHE_DISPATCH_INFERENCE,inferenceCount,0,true,&baseline);
        for(uint32_t i=0;i<batches&&sequenceOk;++i) sequenceOk=runStep("training",FFX_RADIANCE_CACHE_DISPATCH_TRAINING,0,trainingCount,false,nullptr);
        if(sequenceOk) sequenceOk=runStep("post-training-inference",FFX_RADIANCE_CACHE_DISPATCH_INFERENCE,inferenceCount,0,true,&post);
        if(sequenceOk) sequenceOk=runStep("reset-inference",FFX_RADIANCE_CACHE_RESET|FFX_RADIANCE_CACHE_DISPATCH_INFERENCE,inferenceCount,0,true,&reset);
        CloseHandle(event);
        auto compare=[&](const std::vector<RcCacheOutput>& left,const std::vector<RcCacheOutput>& right,uint32_t& changed,double& mse,double& maximum) {
            double sum=0; for(size_t i=0;i<inferenceCount;++i) for(size_t c=0;c<3;++c) { const double delta=double(right[i].radiance[c])-left[i].radiance[c];
                if(std::memcmp(&right[i].radiance[c],&left[i].radiance[c],sizeof(float))!=0) ++changed; sum+=delta*delta; maximum=std::max(maximum,std::abs(delta)); }
            mse=sum/(inferenceCount*3);
        };
        if(baseline.size()==InferenceSamples&&post.size()==InferenceSamples&&reset.size()==InferenceSamples) {
            compare(baseline,post,result.postChangedValues,result.postMse,result.postMaxAbs);
            compare(baseline,reset,result.resetChangedValues,result.resetMse,result.resetMaxAbs);
            result.retainedStateObserved=result.postChangedValues>0; result.resetExact=result.resetChangedValues==0;
            result.targetImproved=result.steps[result.steps.size()-2].targetMse<result.steps.front().targetMse;
            if(fixture) {
                auto compositeMse=[&](const std::vector<RcCacheOutput>& predictions) { double sum=0;
                    for(size_t i=0;i<inferenceCount;++i) for(size_t c=0;c<3;++c) { const double candidate=fixture->direct[i][c]+fixture->throughput[i][c]*predictions[i].radiance[c];
                        const double source=fixture->direct[i][c]+fixture->sourceIndirect[i][c]; const double delta=candidate-source; sum+=delta*delta; }
                    return sum/(inferenceCount*3); };
                result.baselineCompositeMse=compositeMse(baseline); result.postCompositeMse=compositeMse(post); result.compositeImproved=result.postCompositeMse<result.baselineCompositeMse;
            }
        }
        ffxQueryGetProviderVersion selected{}; selected.header.type=FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
        result.providerCode=api.Query(&context,&selected.header); result.provider=selected.versionId;
        result.destroyCode=api.DestroyContext(&context,nullptr); if(result.destroyCode==FFX_API_RETURN_OK) context=nullptr; result.destroyed=!context&&result.destroyCode==FFX_API_RETURN_OK;
        result.mechanicalPass=sequenceOk&&result.retainedStateObserved&&result.resetExact&&result.destroyed;
    }
    result.peak=tracked.peak; result.live=tracked.live; result.attempts=tracked.attempts; result.allocations=tracked.allocations; result.releases=tracked.releases;
    result.denials=tracked.denials; result.errors=tracked.errors;
    result.mechanicalPass=result.mechanicalPass&&result.peak>0&&result.peak<=budget&&!result.live&&!result.denials&&!result.errors&&result.allocations==result.releases;
    result.rawPass=result.mechanicalPass&&result.providerCode==FFX_API_RETURN_OK&&result.provider==provider;
    result.result=result.rawPass?"sequence-pass":result.mechanicalPass?"sequence-pass-provider-metadata-failed":result.created?"sequence-validation-failed":"context-create-failed";
    return result;
}
