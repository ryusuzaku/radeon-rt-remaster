#pragma once

// Bounded offline input preparation, never a denoiser dispatch or live bridge.
void AdmitRrCamera(const rrt::scene::Scene& scene) {
    XMFLOAT4X4 view; XMStoreFloat4x4(&view,Matrix(scene.draws[0].state.view));
    Require(view._14==0 && view._24==0 && view._34==0 && view._44==1,"RR inputs require an affine camera view");
    for(UINT i=0;i<3;++i) for(UINT j=0;j<3;++j) {
        float product=0; for(UINT k=0;k<3;++k) product+=view.m[i][k]*view.m[j][k];
        Require(std::isfinite(product) && std::abs(product-(i==j?1.f:0.f))<.0001f,"RR inputs require an orthonormal camera view");
    }
}
std::vector<std::uint8_t> PrepareRrInputs(Renderer& renderer,UINT randomIndex=UINT32_MAX,rrt::scene::Hash* shaderDigest=nullptr) {
    auto& gpu=renderer.gpu; renderer.Drain();
    const UINT width=renderer.scene.width,height=renderer.scene.height;
    Require(((width==128&&height==96)||(width==256&&height==192))&&renderer.samples>0,"RR input extent/state invalid");
    struct Camera { XMFLOAT4X4 view,previousView; UINT reset; } camera{};
    static_assert(sizeof(Camera)==132);
    const auto projection=Matrix(renderer.scene.draws[0].state.projection);
    const auto inverseProjection=XMMatrixInverse(nullptr,projection);
    const auto view=XMMatrixInverse(nullptr,XMLoadFloat4x4(&renderer.frame.inverse))*inverseProjection;
    const auto previousVp=renderer.rrFrameReset?view*projection:XMLoadFloat4x4(&renderer.frame.previousViewProjection);
    XMStoreFloat4x4(&camera.view,view);
    XMStoreFloat4x4(&camera.previousView,previousVp*inverseProjection); camera.reset=renderer.rrFrameReset?1u:0u;
    XMFLOAT4X4 matrices[5]={renderer.frame.inverse,camera.view,{},camera.previousView,{}};
    XMStoreFloat4x4(&matrices[2],projection); XMStoreFloat4x4(&matrices[4],previousVp);
    for(const auto& matrix:matrices) for(const auto& row:matrix.m) for(float value:row) Require(std::isfinite(value),"nonfinite RR camera");
    Frame frame=renderer.frame; frame.previousViewProjection=matrices[4];
    if(randomIndex!=UINT32_MAX) frame.randomIndex=randomIndex;
    const UINT payloadBytes=width*height*96;
    auto output=gpu.Buffer(payloadBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto readback=gpu.Buffer(payloadBytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    auto constants=gpu.Upload(&frame,sizeof(frame)); auto cameras=gpu.Upload(&camera,sizeof(camera));
    D3D12_ROOT_PARAMETER parameters[8]{};
    for(UINT i=0;i<5;++i) { parameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; parameters[i].Descriptor.ShaderRegister=i; }
    parameters[5].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; parameters[5].Descriptor.ShaderRegister=0;
    parameters[6].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; parameters[6].Descriptor.ShaderRegister=1;
    parameters[7].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[7].Descriptor.ShaderRegister=6;
    D3D12_ROOT_SIGNATURE_DESC desc{}; desc.NumParameters=8; desc.pParameters=parameters;
    ComPtr<ID3DBlob> serialized,error; Check(D3D12SerializeRootSignature(&desc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RR input root serialization");
    ComPtr<ID3D12RootSignature> root; Check(gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&root)),"RR input root");
    wchar_t module[32768]{}; Require(GetModuleFileNameW(nullptr,module,32768)!=0,"RR shader module path");
    Options shaderOptions; shaderOptions.shader=std::filesystem::path(module).parent_path()/L"rrt_rr_inputs.dxil";
    const auto code=Shader(shaderOptions); D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline{};
    if(shaderDigest) *shaderDigest=rrt::scene::Digest(code.data(),code.size());
    pipeline.pRootSignature=root.Get(); pipeline.CS={code.data(),code.size()};
    ComPtr<ID3D12PipelineState> pso; Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&pso)),"RR input pipeline");
    gpu.Begin(); gpu.list->SetComputeRootSignature(root.Get()); gpu.list->SetPipelineState(pso.Get());
    ID3D12Resource* srvs[]={renderer.top.result.Get(),renderer.vb.Get(),renderer.ib.Get(),renderer.materials.Get(),renderer.textures.Get()};
    for(UINT i=0;i<5;++i) gpu.list->SetComputeRootShaderResourceView(i,srvs[i]->GetGPUVirtualAddress());
    gpu.list->SetComputeRootConstantBufferView(5,constants->GetGPUVirtualAddress());
    gpu.list->SetComputeRootConstantBufferView(6,cameras->GetGPUVirtualAddress());
    gpu.list->SetComputeRootUnorderedAccessView(7,output->GetGPUVirtualAddress());
    gpu.list->Dispatch((width+7)/8,(height+7)/8,1);
    D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition={output.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE};
    gpu.list->ResourceBarrier(1,&barrier); gpu.list->CopyResource(readback.Get(),output.Get()); gpu.Execute();
    ++renderer.rrInputSubmissions; ++renderer.readbackSubmissions;
    // Explicit byte serialization: magic, eight uint32 fields, five row-major
    // matrices, six float4 fields per pixel, SHA-256 over all preceding bytes.
    const UINT version=width==128?1u:2u;
    const UINT header[]={version,width,height,96,renderer.dispatches-1,frame.randomIndex,frame.seed,camera.reset};
    std::vector<std::uint8_t> bytes;
    auto append=[&](const void* data,size_t size) { auto p=static_cast<const std::uint8_t*>(data); bytes.insert(bytes.end(),p,p+size); };
    append(version==1?"RRTRRI01":"RRTRRI02",8); append(header,sizeof(header)); append(matrices,sizeof(matrices));
    bytes.reserve(bytes.size()+payloadBytes+32);
    void* data{}; D3D12_RANGE range{0,payloadBytes}; Check(readback->Map(0,&range,&data),"RR input readback");
    // Reserve before mapping so allocation failure cannot leave the map active.
    try { append(data,payloadBytes); } catch(...) { D3D12_RANGE noWrite{0,0}; readback->Unmap(0,&noWrite); throw; }
    D3D12_RANGE noWrite{0,0}; readback->Unmap(0,&noWrite);
    const auto digest=rrt::scene::Digest(bytes.data(),bytes.size()); append(digest.data(),digest.size());
    return bytes;
}
void WriteRrFile(const std::filesystem::path& path,const std::vector<std::uint8_t>& bytes) {
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    Require(file!=INVALID_HANDLE_VALUE,"RR input output exists or unavailable");
    DWORD written{}; const bool ok=WriteFile(file,bytes.data(),DWORD(bytes.size()),&written,nullptr) && written==bytes.size();
    CloseHandle(file); Require(ok,"RR input export failed");
}
void SaveRrInputs(Renderer& renderer,const Options& options) {
    if(!options.rrInputs.empty()) WriteRrFile(options.rrInputs,PrepareRrInputs(renderer));
}
