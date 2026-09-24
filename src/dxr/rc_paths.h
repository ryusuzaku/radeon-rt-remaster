#pragma once

struct RcPathRow {
    XMFLOAT4 secondaryPositionValid,secondaryNormalRoughness,secondaryViewInstance,secondaryDiffuseAlbedo;
    XMFLOAT4 targetRadiance,throughput,noCacheIndirectDistance,directBackgroundPrimaryValid;
};
static_assert(sizeof(RcPathRow)==128);
struct RcPathExport { std::vector<std::uint8_t> bytes; UINT queries{},training{}; };

RcPathExport PrepareRcPaths(Renderer& renderer,const rrt::scene::Hash& sceneDigest) {
    renderer.Drain(); Require(renderer.scene.width==128&&renderer.scene.height==96&&renderer.samples>0&&renderer.pbrDraws==0,"RC path export requires rendered 128x96 legacy-diffuse GI");
    XMFLOAT3 lower{FLT_MAX,FLT_MAX,FLT_MAX},upper{-FLT_MAX,-FLT_MAX,-FLT_MAX};
    for(const auto& draw:renderer.scene.draws) {
        const auto world=Matrix(draw.state.world);
        for(const auto& vertex:draw.vertices) {
            XMFLOAT3 point; XMStoreFloat3(&point,XMVector3TransformCoord(XMVectorSet(vertex.x,vertex.y,vertex.z,1),world));
            lower.x=std::min(lower.x,point.x); lower.y=std::min(lower.y,point.y); lower.z=std::min(lower.z,point.z);
            upper.x=std::max(upper.x,point.x); upper.y=std::max(upper.y,point.y); upper.z=std::max(upper.z,point.z);
        }
    }
    Require(upper.x-lower.x>=1e-4f&&upper.y-lower.y>=1e-4f&&upper.z-lower.z>=1e-4f,"RC path scene bounds must be nondegenerate on all axes");
    const UINT pixelCount=128*96,payloadBytes=pixelCount*sizeof(RcPathRow); const auto allocation=renderer.gpu.allocated;
    auto output=renderer.gpu.Buffer(payloadBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto readback=renderer.gpu.Buffer(payloadBytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    Frame frame=renderer.frame; auto constants=renderer.gpu.Upload(&frame,sizeof(frame));
    D3D12_ROOT_PARAMETER parameters[7]{};
    for(UINT i=0;i<5;++i) { parameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; parameters[i].Descriptor.ShaderRegister=i; }
    parameters[5].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; parameters[5].Descriptor.ShaderRegister=0;
    parameters[6].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[6].Descriptor.ShaderRegister=6;
    D3D12_ROOT_SIGNATURE_DESC desc{}; desc.NumParameters=7; desc.pParameters=parameters;
    ComPtr<ID3DBlob> serialized,error; Check(D3D12SerializeRootSignature(&desc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"RC path root serialization");
    ComPtr<ID3D12RootSignature> root; Check(renderer.gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&root)),"RC path root");
    wchar_t module[32768]{}; Require(GetModuleFileNameW(nullptr,module,32768)!=0,"RC path shader module path");
    Options shaderOptions; shaderOptions.shader=std::filesystem::path(module).parent_path()/L"rrt_rc_paths.dxil";
    const auto code=Shader(shaderOptions); const auto shaderDigest=rrt::scene::Digest(code.data(),code.size());
    D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline{}; pipeline.pRootSignature=root.Get(); pipeline.CS={code.data(),code.size()};
    ComPtr<ID3D12PipelineState> pso; Check(renderer.gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&pso)),"RC path pipeline");
    renderer.gpu.Begin(); renderer.gpu.list->SetComputeRootSignature(root.Get()); renderer.gpu.list->SetPipelineState(pso.Get());
    ID3D12Resource* srvs[]={renderer.top.result.Get(),renderer.vb.Get(),renderer.ib.Get(),renderer.materials.Get(),renderer.textures.Get()};
    for(UINT i=0;i<5;++i) renderer.gpu.list->SetComputeRootShaderResourceView(i,srvs[i]->GetGPUVirtualAddress());
    renderer.gpu.list->SetComputeRootConstantBufferView(5,constants->GetGPUVirtualAddress()); renderer.gpu.list->SetComputeRootUnorderedAccessView(6,output->GetGPUVirtualAddress());
    renderer.gpu.list->Dispatch(16,12,1);
    D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition={output.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE};
    renderer.gpu.list->ResourceBarrier(1,&barrier); renderer.gpu.list->CopyResource(readback.Get(),output.Get()); renderer.gpu.Execute(); ++renderer.rcPathSubmissions; ++renderer.readbackSubmissions;
    std::vector<RcPathRow> rows(pixelCount); void* mapped{}; D3D12_RANGE range{0,payloadBytes}; Check(readback->Map(0,&range,&mapped),"RC path readback");
    std::memcpy(rows.data(),mapped,payloadBytes); D3D12_RANGE noWrite{0,0}; readback->Unmap(0,&noWrite);
    UINT queries=0;
    auto finite4=[](const XMFLOAT4& value) { return std::isfinite(value.x)&&std::isfinite(value.y)&&std::isfinite(value.z)&&std::isfinite(value.w); };
    for(const auto& row:rows) {
        Require(finite4(row.secondaryPositionValid)&&finite4(row.secondaryNormalRoughness)&&finite4(row.secondaryViewInstance)&&finite4(row.secondaryDiffuseAlbedo)
            &&finite4(row.targetRadiance)&&finite4(row.throughput)&&finite4(row.noCacheIndirectDistance)&&finite4(row.directBackgroundPrimaryValid),"nonfinite RC path row");
        Require((row.secondaryPositionValid.w==0||row.secondaryPositionValid.w==1)&&(row.directBackgroundPrimaryValid.w==0||row.directBackgroundPrimaryValid.w==1),"invalid RC path validity");
        Require(row.secondaryPositionValid.w<=row.directBackgroundPrimaryValid.w,"secondary hit without primary hit");
        if(row.secondaryPositionValid.w) {
            ++queries; Require(row.secondaryPositionValid.x>=lower.x-1e-4f&&row.secondaryPositionValid.x<=upper.x+1e-4f
                &&row.secondaryPositionValid.y>=lower.y-1e-4f&&row.secondaryPositionValid.y<=upper.y+1e-4f&&row.secondaryPositionValid.z>=lower.z-1e-4f&&row.secondaryPositionValid.z<=upper.z+1e-4f,"RC path hit outside scene bounds");
            const float nl=row.secondaryNormalRoughness.x*row.secondaryNormalRoughness.x+row.secondaryNormalRoughness.y*row.secondaryNormalRoughness.y+row.secondaryNormalRoughness.z*row.secondaryNormalRoughness.z;
            const float vl=row.secondaryViewInstance.x*row.secondaryViewInstance.x+row.secondaryViewInstance.y*row.secondaryViewInstance.y+row.secondaryViewInstance.z*row.secondaryViewInstance.z;
            Require(std::abs(nl-1)<1e-3f&&std::abs(vl-1)<1e-3f&&row.secondaryNormalRoughness.w==1&&row.secondaryViewInstance.w>=1&&row.noCacheIndirectDistance.w>0,"invalid RC path surface tuple");
            for(UINT c=0;c<3;++c) { const float albedo=(&row.secondaryDiffuseAlbedo.x)[c],target=(&row.targetRadiance.x)[c],weight=(&row.throughput.x)[c],indirect=(&row.noCacheIndirectDistance.x)[c];
                Require(albedo>=0&&albedo<=1&&target>=0&&weight>=0&&weight<=1&&std::abs(indirect-weight*target)<=2e-5f,"invalid RC path factorization"); }
        }
    }
    Require(queries>0,"RC path fixture contains no secondary surface queries"); const UINT training=std::min(queries,512u);
    struct Settings { UINT seed,shadows,flags,reserved; float light[3],intensity,lightColor[3],ambient,sunRadius,padding[3]; } settings{};
    static_assert(sizeof(Settings)==64); settings.seed=frame.seed; settings.shadows=frame.shadows; settings.flags=frame.flags; std::memcpy(settings.light,frame.light,12);
    settings.intensity=frame.intensity; std::memcpy(settings.lightColor,frame.lightColor,12); settings.ambient=frame.ambient; settings.sunRadius=frame.sunRadius;
    const auto settingsDigest=rrt::scene::Digest(&settings,sizeof(settings)); const float bounds[]={lower.x,lower.y,lower.z,upper.x,upper.y,upper.z};
    const UINT header[]={1,128,96,128,pixelCount,queries,training,frame.randomIndex}; RcPathExport result; result.queries=queries; result.training=training;
    auto append=[&](const void* data,size_t size) { const auto* p=static_cast<const std::uint8_t*>(data); result.bytes.insert(result.bytes.end(),p,p+size); };
    result.bytes.reserve(224+payloadBytes+32); append("RCRPATH1",8); append(header,sizeof(header)); append(sceneDigest.data(),32); append(shaderDigest.data(),32);
    append(settingsDigest.data(),32); append(bounds,sizeof(bounds)); append(&settings,sizeof(settings)); append(rows.data(),payloadBytes);
    Require(result.bytes.size()==224+payloadBytes,"RC path prefix/payload size mismatch"); const auto digest=rrt::scene::Digest(result.bytes.data(),result.bytes.size()); append(digest.data(),digest.size());
    renderer.gpu.allocated=allocation; return result;
}

void SaveRcPaths(Renderer& renderer,const Options& options,const rrt::scene::Hash& sceneDigest) {
    if(options.rcPaths.empty()) return; auto result=PrepareRcPaths(renderer,sceneDigest); renderer.rcPathQueries=result.queries; renderer.rcPathTraining=result.training; WriteRrFile(options.rcPaths,result.bytes);
}
