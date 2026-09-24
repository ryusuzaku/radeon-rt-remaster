// Standalone display ownership. Included after Renderer in main.cpp's private namespace.
// One ordered queue preserves renderer history dependencies; CPU reuse is fence-gated.
enum class FrameWake { Ready, Messages, Timeout };
FrameWake WaitFrame(HANDLE handle,DWORD milliseconds) {
    const DWORD result=MsgWaitForMultipleObjectsEx(1,&handle,milliseconds,QS_ALLINPUT,MWMO_INPUTAVAILABLE);
    if(result==WAIT_OBJECT_0) return FrameWake::Ready;
    if(result==WAIT_OBJECT_0+1) return FrameWake::Messages;
    if(result==WAIT_TIMEOUT) return FrameWake::Timeout;
    if(result==WAIT_FAILED) Check(HRESULT_FROM_WIN32(GetLastError()),"frame admission wait");
    throw std::runtime_error("unexpected frame admission wait result");
}
// Own the DXGI handle across ResizeBuffers; close it once at swapchain teardown.
struct FrameHandle {
    HANDLE value{};
    ~FrameHandle() { if(value) CloseHandle(value); }
    FrameHandle()=default;
    FrameHandle(const FrameHandle&)=delete;
    FrameHandle& operator=(const FrameHandle&)=delete;
};
UINT VerifyFrameWait(HWND window) {
    FrameHandle event; event.value=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event.value!=nullptr,"pacing test event");
    MSG message{};
    Require(PostMessageW(window,WM_APP,0,0)!=0,"pacing test message");
    // Seen-but-unconsumed input must still wake MWMO_INPUTAVAILABLE.
    Require(PeekMessageW(&message,window,WM_APP,WM_APP,PM_NOREMOVE)!=0,"pacing test peek");
    Require(WaitFrame(event.value,0)==FrameWake::Messages,"pacing message wake failed");
    UINT mask=2;
    for(UINT attempt=0;attempt<100;++attempt) {
        while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
        if(WaitFrame(event.value,0)==FrameWake::Timeout) { mask|=4; break; }
    }
    Require(SetEvent(event.value)!=0,"pacing test signal");
    Require(WaitFrame(event.value,0)==FrameWake::Ready,"pacing ready wake failed");
    return mask|1;
}
struct NativeDisplay {
    Renderer& renderer;
    Device& gpu;
    HWND window;
    bool validate{},occluded{};
    bool paced{},admitted{};
    FrameHandle latency;
    UINT width{},height{},rtvStride{};
    UINT64 validationBytes{};
    UINT64 backFences[2]{};
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    ComPtr<IDXGISwapChain3> swap;
    ComPtr<ID3D12Resource> buffers[2],validation;
    ComPtr<ID3D12DescriptorHeap> rtvs;
    ComPtr<ID3D12RootSignature> root;
    ComPtr<ID3D12PipelineState> pipeline;

    NativeDisplay(Renderer& r,HWND hwnd,const Options& options,bool forceValidate=false,bool forcePaced=false):renderer(r),gpu(r.gpu),window(hwnd),validate(options.windowTest||forceValidate),paced(forcePaced||(!options.windowTest && !options.noFramePacing)) {
        D3D12_ROOT_PARAMETER parameters[2]{};
        parameters[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; parameters[0].ShaderVisibility=D3D12_SHADER_VISIBILITY_PIXEL;
        parameters[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS; parameters[1].Constants.Num32BitValues=4; parameters[1].ShaderVisibility=D3D12_SHADER_VISIBILITY_PIXEL;
        D3D12_ROOT_SIGNATURE_DESC desc{}; desc.NumParameters=2; desc.pParameters=parameters;
        ComPtr<ID3DBlob> serialized,error;
        Check(D3D12SerializeRootSignature(&desc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"display root serialization");
        Check(gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&root)),"display root signature");
        auto vs=Shader(options,4),ps=Shader(options,5);
        D3D12_GRAPHICS_PIPELINE_STATE_DESC pso{}; pso.pRootSignature=root.Get();
        pso.VS={vs.data(),vs.size()}; pso.PS={ps.data(),ps.size()};
        pso.RasterizerState.FillMode=D3D12_FILL_MODE_SOLID; pso.RasterizerState.CullMode=D3D12_CULL_MODE_NONE; pso.RasterizerState.DepthClipEnable=TRUE;
        auto& blend=pso.BlendState.RenderTarget[0]; blend.SrcBlend=D3D12_BLEND_ONE; blend.DestBlend=D3D12_BLEND_ZERO; blend.BlendOp=D3D12_BLEND_OP_ADD;
        blend.SrcBlendAlpha=D3D12_BLEND_ONE; blend.DestBlendAlpha=D3D12_BLEND_ZERO; blend.BlendOpAlpha=D3D12_BLEND_OP_ADD;
        blend.LogicOp=D3D12_LOGIC_OP_NOOP; blend.RenderTargetWriteMask=D3D12_COLOR_WRITE_ENABLE_ALL;
        pso.SampleMask=UINT_MAX; pso.PrimitiveTopologyType=D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
        pso.NumRenderTargets=1; pso.RTVFormats[0]=DXGI_FORMAT_B8G8R8A8_UNORM; pso.SampleDesc.Count=1;
        Check(gpu.device->CreateGraphicsPipelineState(&pso,IID_PPV_ARGS(&pipeline)),"display pipeline");
        D3D12_DESCRIPTOR_HEAP_DESC heap{}; heap.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV; heap.NumDescriptors=2;
        Check(gpu.device->CreateDescriptorHeap(&heap,IID_PPV_ARGS(&rtvs)),"display RTV heap");
        rtvStride=gpu.device->GetDescriptorHandleIncrementSize(heap.Type);
        RECT client{}; Require(GetClientRect(window,&client)!=0,"display client bounds");
        try { Resize(UINT(client.right),UINT(client.bottom)); }
        catch(...) { Release(); throw; }
    }
    ~NativeDisplay() {
        try { renderer.Drain(); gpu.ClearReferences(); }
        catch(const std::exception& error) { std::fprintf(stderr,"display teardown: %s\n",error.what()); }
        Release();
    }
    void Release() {
        // Caller drains before releasing resources referenced by queued work.
        for(auto& buffer:buffers) buffer.Reset();
        validation.Reset(); gpu.allocated-=validationBytes; validationBytes=0; gpu.displayBytes=0;
    }
    void Resize(UINT w,UINT h) {
        if(!w || !h || (w==width && h==height)) return;
        Require(w<=4096 && h<=4096,"display dimensions exceed 4096");
        D3D12_RESOURCE_DESC texture{}; texture.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;
        texture.Width=w; texture.Height=h; texture.DepthOrArraySize=1; texture.MipLevels=1;
        texture.Format=DXGI_FORMAT_B8G8R8A8_UNORM; texture.SampleDesc.Count=1; texture.Flags=D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
        const auto allocation=gpu.device->GetResourceAllocationInfo(0,1,&texture);
        UINT64 copyBytes{}; D3D12_PLACED_SUBRESOURCE_FOOTPRINT nextFootprint{};
        gpu.device->GetCopyableFootprints(&texture,0,1,0,&nextFootprint,nullptr,nullptr,&copyBytes);
        const UINT64 nextValidation=validate?std::max(copyBytes,UINT64(256)):0;
        Require(allocation.SizeInBytes<=MaxGpuAllocationBytes && nextValidation<=MaxGpuAllocationBytes
            && gpu.allocated-validationBytes+allocation.SizeInBytes*2+nextValidation<=gpu.requestedLimit,"display allocation budget exceeded");
        // Reset recorded references as well as releasing our resource pointers.
        renderer.Drain(); gpu.ClearReferences(); Release();
        backFences[0]=backFences[1]=0;
        if(swap) {
            Check(swap->ResizeBuffers(2,w,h,DXGI_FORMAT_B8G8R8A8_UNORM,paced?DXGI_SWAP_CHAIN_FLAG_FRAME_LATENCY_WAITABLE_OBJECT:0),"swapchain resize"); ++renderer.displayResizes;
        } else {
            DXGI_SWAP_CHAIN_DESC1 desc{}; desc.Width=w; desc.Height=h; desc.Format=texture.Format;
            desc.SampleDesc.Count=1; desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.BufferCount=2;
            desc.Scaling=DXGI_SCALING_STRETCH; desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD; desc.AlphaMode=DXGI_ALPHA_MODE_IGNORE;
            desc.Flags=paced?DXGI_SWAP_CHAIN_FLAG_FRAME_LATENCY_WAITABLE_OBJECT:0;
            ComPtr<IDXGISwapChain1> created;
            Check(gpu.factory->CreateSwapChainForHwnd(gpu.queue.Get(),window,&desc,nullptr,nullptr,&created),"native swapchain");
            Check(created.As(&swap),"swapchain3 interface");
            if(paced) {
                Check(swap->SetMaximumFrameLatency(1),"swapchain frame latency");
                latency.value=swap->GetFrameLatencyWaitableObject(); Require(latency.value!=nullptr,"swapchain latency handle");
                Check(swap->GetMaximumFrameLatency(&renderer.frameLatency),"query swapchain frame latency");
                Require(renderer.frameLatency==1,"unexpected swapchain frame latency");
            }
            Check(gpu.factory->MakeWindowAssociation(window,DXGI_MWA_NO_ALT_ENTER),"disable exclusive-fullscreen toggle");
        }
        gpu.displayBytes=allocation.SizeInBytes*2;
        gpu.peakRequested=std::max(gpu.peakRequested,gpu.allocated+gpu.displayBytes);
        for(UINT i=0;i<2;++i) {
            Check(swap->GetBuffer(i,IID_PPV_ARGS(&buffers[i])),"swapchain back buffer");
            auto rtv=rtvs->GetCPUDescriptorHandleForHeapStart(); rtv.ptr+=SIZE_T(i)*rtvStride;
            gpu.device->CreateRenderTargetView(buffers[i].Get(),nullptr,rtv);
        }
        if(validate) { validation=gpu.Buffer(nextValidation,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST); validationBytes=nextValidation; }
        footprint=nextFootprint; width=w; height=h; occluded=false;
    }
    void Status(HRESULT status) {
        Check(status,"display status");
        Require(status==S_OK || status==DXGI_STATUS_OCCLUDED,"unexpected display status");
        occluded=status==DXGI_STATUS_OCCLUDED;
    }
    bool Available() {
        if(occluded) Status(swap->Present(0,DXGI_PRESENT_TEST));
        return !occluded;
    }
    bool Ready() {
        if(!paced || admitted) return true;
        Check(gpu.device->GetDeviceRemovedReason(),"frame admission device status");
        const auto start=std::chrono::steady_clock::now();
        const auto wake=WaitFrame(latency.value,100);
        renderer.pacingWaitMs+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
        ++renderer.pacingWaits;
        if(wake==FrameWake::Ready) { admitted=true; ++renderer.pacingReady; }
        else if(wake==FrameWake::Messages) ++renderer.pacingMessages;
        else ++renderer.pacingTimeouts;
        // Re-pump even after admission; retain the permit across intervening messages.
        return false;
    }
    void Transition(ID3D12Resource* resource,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after) {
        D3D12_RESOURCE_BARRIER b{}; b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        b.Transition={resource,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,before,after}; gpu.list->ResourceBarrier(1,&b);
    }
    void Draw(const std::vector<UINT>& reference,bool verify=true) {
        Require(!paced || admitted,"display submitted without frame admission");
        const bool check=validate && verify;
        const UINT index=swap->GetCurrentBackBufferIndex(); Require(index<2,"invalid back buffer index");
        renderer.displayMask|=1u<<index;
        gpu.Wait(backFences[index]);
        gpu.Begin(); Transition(renderer.output.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        Transition(buffers[index].Get(),D3D12_RESOURCE_STATE_PRESENT,D3D12_RESOURCE_STATE_RENDER_TARGET);
        gpu.list->SetGraphicsRootSignature(root.Get()); gpu.list->SetPipelineState(pipeline.Get());
        gpu.list->SetGraphicsRootShaderResourceView(0,renderer.output->GetGPUVirtualAddress());
        const UINT dimensions[]={renderer.scene.width,renderer.scene.height,width,height};
        gpu.list->SetGraphicsRoot32BitConstants(1,4,dimensions,0);
        D3D12_VIEWPORT viewport{0,0,float(width),float(height),0,1}; D3D12_RECT scissor{0,0,LONG(width),LONG(height)};
        gpu.list->RSSetViewports(1,&viewport); gpu.list->RSSetScissorRects(1,&scissor);
        auto rtv=rtvs->GetCPUDescriptorHandleForHeapStart(); rtv.ptr+=SIZE_T(index)*rtvStride;
        gpu.list->OMSetRenderTargets(1,&rtv,FALSE,nullptr); gpu.list->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        gpu.list->DrawInstanced(3,1,0,0);
        if(check) {
            Transition(buffers[index].Get(),D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_COPY_SOURCE);
            D3D12_TEXTURE_COPY_LOCATION source{}; source.pResource=buffers[index].Get(); source.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            D3D12_TEXTURE_COPY_LOCATION target{}; target.pResource=validation.Get(); target.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; target.PlacedFootprint=footprint;
            gpu.list->CopyTextureRegion(&target,0,0,0,&source,nullptr);
        }
        Transition(buffers[index].Get(),check?D3D12_RESOURCE_STATE_COPY_SOURCE:D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_PRESENT);
        Transition(renderer.output.Get(),D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE);
        const auto status=gpu.Execute(swap.Get(),check); backFences[index]=gpu.sequence; ++renderer.displaySubmissions; Status(status);
        admitted=false;
        if(occluded) ++renderer.displayOccluded; else ++renderer.displayPresented;
        if(check) {
            void* data{}; D3D12_RANGE range{0,SIZE_T(validationBytes)}; Check(validation->Map(0,&range,&data),"back buffer verification map");
            bool equal=reference.size()==std::size_t(renderer.scene.width)*renderer.scene.height;
            for(UINT y=0;y<height && equal;++y) {
                const auto* row=reinterpret_cast<const UINT*>(static_cast<const char*>(data)+footprint.Offset+SIZE_T(y)*footprint.Footprint.RowPitch);
                for(UINT x=0;x<width;++x) if(row[x]!=reference[std::size_t(y*renderer.scene.height/height)*renderer.scene.width+x*renderer.scene.width/width]) { equal=false; break; }
            }
            D3D12_RANGE noWrite{0,0}; validation->Unmap(0,&noWrite);
            Require(equal,"native back buffer differs from headless pixels"); ++renderer.displayVerified;
        }
    }
};
