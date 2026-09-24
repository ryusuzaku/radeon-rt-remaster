#pragma once
#include <bcrypt.h>
#include <DirectXPackedVector.h>
#include <DirectXMath.h>
#include <fstream>
#include <cmath>
#include <cstring>

struct RrScalePreset { const char* name; float value; };
constexpr RrScalePreset RrScalePresets[]={
    {"none",1.f},{"unit-tenth",.1f},{"unit-one",1.f},{"unit-ten",10.f}
};
struct RrGuidePreset { const char* name; };
constexpr RrGuidePreset RrGuidePresets[]={{"none"},{"material-draw"}};

std::array<unsigned char,32> RrDigest(const void* data,size_t size) {
    std::array<unsigned char,32> result{};
    Require(size<=UINT32_MAX,"RR hash input too large");
    Require(BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,
            const_cast<PUCHAR>(static_cast<const unsigned char*>(data)),ULONG(size),result.data(),ULONG(result.size()))>=0,"RR SHA256 failed");
    return result;
}
std::string RrHex(const std::array<unsigned char,32>& digest) {
    std::string result; const char hex[]="0123456789abcdef";
    for(auto c:digest) { result+=hex[c>>4]; result+=hex[c&15]; } return result;
}
struct RrInputFile {
    static constexpr UINT Pixels=128*96,FileBytes=360+Pixels*96+32,NativePixels=256*192,NativeFileBytes=360+NativePixels*96+32;
    UINT header[8]{}; float matrices[80]{};
    UINT width{},height{},pixelCount{},fileBytes{};
    std::vector<std::array<float,24>> rows;
    std::array<unsigned char,32> digest{};
    static std::vector<unsigned char> Read(const std::filesystem::path& path) {
        const auto size=std::filesystem::file_size(path);
        Require(path.is_absolute()&&(size==FileBytes||size==NativeFileBytes),"RR input path/size invalid");
        std::ifstream file(path,std::ios::binary); std::vector<unsigned char> bytes(static_cast<size_t>(size));
        Require(bool(file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()))&&file.peek()==EOF,"RR input read failed");
        return bytes;
    }
    explicit RrInputFile(const std::filesystem::path& path):RrInputFile(Read(path),false) {}
    explicit RrInputFile(const std::vector<unsigned char>& bytes,bool stationary,bool moving=false) {
        Require(bytes.size()==FileBytes||bytes.size()==NativeFileBytes,"RR input size invalid");
        digest=RrDigest(bytes.data(),bytes.size()-32);
        Require(!memcmp(bytes.data()+bytes.size()-32,digest.data(),32),"RR input checksum mismatch");
        memcpy(header,bytes.data()+8,sizeof(header)); memcpy(matrices,bytes.data()+40,sizeof(matrices));
        const bool legacy=!memcmp(bytes.data(),"RRTRRI01",8)&&header[0]==1&&header[1]==128&&header[2]==96&&bytes.size()==FileBytes;
        const bool nativeV2=!memcmp(bytes.data(),"RRTRRI02",8)&&header[0]==2&&header[1]==256&&header[2]==192&&bytes.size()==NativeFileBytes;
        Require((legacy||nativeV2)&&header[3]==96,"RR input header mismatch");
        width=header[1]; height=header[2]; pixelCount=width*height; fileBytes=UINT(bytes.size());
        Require(header[4]<65536&&header[5]<4096&&header[7]<=1&&(stationary||header[7]==1),"RR dispatch requires a reset input frame");
        for(float value:matrices) Require(std::isfinite(value)&&std::abs(value)<=1e6,"RR matrix exceeds finite range");
        using namespace DirectX;
        XMFLOAT4X4 v{},p{},ivp{}; memcpy(&ivp,matrices,64); memcpy(&v,matrices+16,64); memcpy(&p,matrices+32,64);
        XMFLOAT4X4 identity{}; XMStoreFloat4x4(&identity,XMLoadFloat4x4(&v)*XMLoadFloat4x4(&p)*XMLoadFloat4x4(&ivp));
        for(UINT i=0;i<4;++i) for(UINT j=0;j<4;++j) Require(std::isfinite(identity.m[i][j])&&std::abs(identity.m[i][j]-(i==j?1.f:0.f))<.0005f,"RR camera matrices inconsistent");
        Require(std::abs(v._14)<.0005f&&std::abs(v._24)<.0005f&&std::abs(v._34)<.0005f&&std::abs(v._44-1)<.0005f,"RR view must be affine");
        for(UINT i=0;i<3;++i) for(UINT j=0;j<3;++j) {
            float value=0; for(UINT k=0;k<3;++k) value+=v.m[i][k]*v.m[j][k];
            Require(std::abs(value-(i==j?1.f:0.f))<.0005f,"RR view must be orthonormal");
        }
        rows.resize(pixelCount); memcpy(rows.data(),bytes.data()+360,size_t(pixelCount)*96);
        for(const auto& r:rows) {
            for(float value:r) Require(std::isfinite(value)&&std::abs(value)<=1e6,"RR record exceeds finite range");
            Require(r[23]>=0&&r[23]<=1024&&r[23]==std::floor(r[23])&&r[7]==(r[23]>0?1.f:0.f),"RR primary validity invalid");
            if(header[7]) Require(r[15]==0&&r[16]==0&&r[17]==0&&r[18]==0,"RR reset frame has motion");
            else Require(r[15]==r[7]&&std::abs(r[16])<=(moving?65504.f:1e-5f)&&std::abs(r[17])<=(moving?65504.f:1e-5f)&&std::abs(r[18])<=(moving?65504.f:1e-5f),"RR motion invalid or unsupported");
            for(UINT base:{0u,4u,12u}) for(UINT c=0;c<3;++c) Require(r[base+c]>=0&&r[base+c]<=65504,"RR radiance/albedo out of half range");
            if(r[23]>0) {
                Require(r[3]>=0&&r[3]<=100000&&r[8]>=0&&r[8]<=1&&r[9]>=0&&r[9]<=1&&r[10]>=.049f&&r[10]<=1&&r[11]==0,"RR distance/normal invalid");
                Require(std::abs(r[19])>=.001f&&std::abs(r[19])<=10000,"RR active depth out of bounds");
                const float viewZ=r[20]*v._13+r[21]*v._23+r[22]*v._33+v._43;
                Require(std::abs(viewZ-r[19])<.0005f*std::max(1.f,std::abs(viewZ)),"RR depth/position mismatch");
            } else {
                Require(r[0]==0&&r[1]==0&&r[2]==0&&r[3]==-1,"RR background signal invalid");
                for(UINT i=7;i<24;++i) Require(r[i]==0,"RR background guide invalid");
            }
        }
    }
};

struct RrDispatchGpu {
    ID3D12Device* device; const RrInputFile* current;
    const bool sqrtAlbedo;
    const UINT scaleId;
    const UINT guideId;
    const float coordinateScale;
    UINT dispatchFlags{};
    UINT width{},height{},pixels{};
    struct Texture { ComPtr<ID3D12Resource> resource; D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
        UINT rowBytes{}; std::vector<unsigned char> packed; D3D12_RESOURCE_STATES state=D3D12_RESOURCE_STATE_COPY_DEST; } textures[6];
    ComPtr<ID3D12Resource> upload,readback;
    ComPtr<ID3D12CommandQueue> queue; ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
    ComPtr<ID3D12Fence> fence; RrHandle event;
    UINT64 allocated{},limit{},stagingBytes{},sequence{};
    UINT distanceClamps{},changedPixels{},releases{},dispatchCode=UINT32_MAX;
    UINT sdkFrameIndex{}; float cameraDelta[3]{};
    float scaledView[16]{},scaledProjection[16]{},depthBounds[2]{};
    bool uploaded{},inputsIntact{},completed{};
    std::vector<float> output;
    ComPtr<ID3D12Resource> Resource(const D3D12_RESOURCE_DESC& desc,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state) {
        const auto info=device->GetResourceAllocationInfo(0,1,&desc);
        Require(info.SizeInBytes>0&&info.SizeInBytes<=limit-allocated,"RR external allocation budget exceeded");
        D3D12_HEAP_PROPERTIES heap{}; heap.Type=type; ComPtr<ID3D12Resource> resource;
        Require(SUCCEEDED(device->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&desc,state,nullptr,IID_PPV_ARGS(&resource))),"RR external allocation failed");
        allocated+=info.SizeInBytes; return resource;
    }
    void Barrier(Texture& t,D3D12_RESOURCE_STATES state) {
        if(t.state==state) return;
        D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        barrier.Transition={t.resource.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,t.state,state}; list->ResourceBarrier(1,&barrier); t.state=state;
    }
    void Submit() {
        Require(SUCCEEDED(list->Close()),"RR command close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists);
        // Once work is submitted, never unwind resources underneath an unknown
        // GPU lifetime. The job-owned child exits on a failed fence/device wait.
        if(FAILED(queue->Signal(fence.Get(),++sequence))||FAILED(fence->SetEventOnCompletion(sequence,event.value))||
           WaitForSingleObject(event.value,10000)!=WAIT_OBJECT_0||FAILED(device->GetDeviceRemovedReason())) {
            std::cerr << "RR GPU completion failed; terminating isolated child\n"; ExitProcess(0xe0005253);
        }
    }
    void Begin() { Require(SUCCEEDED(allocator->Reset())&&SUCCEEDED(list->Reset(allocator.Get(),nullptr)),"RR command reset failed"); }
    void CopyBack(UINT count) {
        for(UINT i=0;i<count;++i) {
            auto& t=textures[i]; const auto old=t.state; Barrier(t,D3D12_RESOURCE_STATE_COPY_SOURCE);
            D3D12_TEXTURE_COPY_LOCATION from{},to{}; from.pResource=t.resource.Get(); from.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            to.pResource=readback.Get(); to.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; to.PlacedFootprint=t.footprint;
            list->CopyTextureRegion(&to,0,0,0,&from,nullptr); Barrier(t,old);
        }
    }
    void CheckPacked(UINT count) {
        void* mapped{}; D3D12_RANGE range{0,SIZE_T(stagingBytes)};
        Require(SUCCEEDED(readback->Map(0,&range,&mapped)),"RR packed readback map failed"); bool equal=true;
        for(UINT i=0;i<count;++i) for(UINT y=0;y<height;++y) {
            const auto& t=textures[i];
            equal=equal&&!memcmp(static_cast<char*>(mapped)+t.footprint.Offset+y*t.footprint.Footprint.RowPitch,t.packed.data()+y*t.rowBytes,t.rowBytes);
        }
        D3D12_RANGE none{0,0}; readback->Unmap(0,&none); Require(equal,"RR GPU input bytes changed");
    }
    void Pack(const RrInputFile& input) {
        Require(input.width == width && input.height == height, "RR input extent changed within recording");
        current=&input; distanceClamps=changedPixels=0; completed=uploaded=inputsIntact=false; dispatchCode=UINT32_MAX; output.clear();
        for(UINT i=0;i<6;++i) {
            auto& t=textures[i];
            for(UINT pixel=0;pixel<pixels;++pixel) {
                const auto& r=input.rows[pixel];
                if(i==0) { const float value=r[19]*coordinateScale; memcpy(t.packed.data()+pixel*4,&value,4); }
                else {
                    float values[4]{};
                    if(i==1) { memcpy(values,r.data()+16,12); values[2]*=coordinateScale; }
                    if(i==2) {
                        memcpy(values,r.data()+8,16);
                        if(guideId==1&&r[23]>0) values[3]=float((UINT(r[23])-1)%4)/3.f;
                    }
                    if(i==3) {
                        memcpy(values,r.data()+12,12);
                        if(sqrtAlbedo) for(UINT c=0;c<3;++c) values[c]=float(std::sqrt(double(values[c])));
                    }
                    if(i==4) { memcpy(values,r.data(),16); if(values[3]>=100000) { values[3]=65504; ++distanceClamps; }
                        else if(values[3]>=0) { values[3]*=coordinateScale; if(values[3]>65504) { values[3]=65504; ++distanceClamps; } } }
                    if(i==5) { values[0]=values[1]=values[2]=-1234; values[3]=r[3]>=100000?65504.f:r[3]>=0?std::min(r[3]*coordinateScale,65504.f):r[3]; }
                    for(UINT c=0;c<4;++c) { const auto half=DirectX::PackedVector::XMConvertFloatToHalf(values[c]); memcpy(t.packed.data()+pixel*8+c*2,&half,2); }
                }
            }
        }
    }
    void Upload(const RrInputFile& input) {
        Pack(input);
        void* mapped{}; D3D12_RANGE none{0,0}; Require(SUCCEEDED(upload->Map(0,&none,&mapped)),"RR upload map failed");
        memset(mapped,0,SIZE_T(stagingBytes));
        for(auto& t:textures) for(UINT y=0;y<height;++y) memcpy(static_cast<char*>(mapped)+t.footprint.Offset+y*t.footprint.Footprint.RowPitch,t.packed.data()+y*t.rowBytes,t.rowBytes);
        upload->Unmap(0,nullptr);
        if(sequence) Begin();
        for(UINT i=0;i<6;++i) {
            auto& t=textures[i]; Barrier(t,D3D12_RESOURCE_STATE_COPY_DEST); D3D12_TEXTURE_COPY_LOCATION from{},to{};
            from.pResource=upload.Get(); from.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; from.PlacedFootprint=t.footprint;
            to.pResource=t.resource.Get(); to.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            list->CopyTextureRegion(&to,0,0,0,&from,nullptr);
            Barrier(t,i==5?D3D12_RESOURCE_STATE_UNORDERED_ACCESS:D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        }
        CopyBack(6); Submit(); CheckPacked(6); uploaded=true;
    }
    explicit RrDispatchGpu(ID3D12Device* gpu,const RrInputFile& data,UINT64 budget,bool encodedAlbedo=false,UINT units=0,UINT guides=0):device(gpu),current(&data),sqrtAlbedo(encodedAlbedo),scaleId(units),guideId(guides),coordinateScale(units<std::size(RrScalePresets)?RrScalePresets[units].value:1.f),width(data.width),height(data.height),pixels(data.pixelCount),limit(budget) {
        Require(scaleId<std::size(RrScalePresets),"invalid coordinate scale preset");
        Require(guideId<std::size(RrGuidePresets),"invalid guide preset");
        Require(limit>0&&limit<=8ull*1024*1024,"RR external budget invalid");
        for(UINT i=0;i<6;++i) {
            auto& t=textures[i]; const bool depth=i==0;
            D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D; desc.Width=width; desc.Height=height;
            desc.DepthOrArraySize=1; desc.MipLevels=1; desc.SampleDesc.Count=1;
            desc.Format=depth?DXGI_FORMAT_R32_FLOAT:DXGI_FORMAT_R16G16B16A16_FLOAT;
            if(i==5) desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
            D3D12_FEATURE_DATA_FORMAT_SUPPORT support{desc.Format};
            Require(SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_FORMAT_SUPPORT,&support,sizeof(support)))&&
                    (support.Support1&D3D12_FORMAT_SUPPORT1_TEXTURE2D)&&
                    (i==5?(support.Support2&D3D12_FORMAT_SUPPORT2_UAV_TYPED_STORE):(support.Support1&D3D12_FORMAT_SUPPORT1_SHADER_LOAD)),"RR texture format unsupported");
            t.resource=Resource(desc,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST);
            UINT64 size{}; device->GetCopyableFootprints(&desc,0,1,stagingBytes,&t.footprint,nullptr,nullptr,&size);
            stagingBytes=t.footprint.Offset+UINT64(t.footprint.Footprint.RowPitch)*height;
            t.rowBytes=width*(depth?4:8); t.packed.resize(t.rowBytes*height);
        }
        D3D12_RESOURCE_DESC buffer{}; buffer.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; buffer.Width=stagingBytes; buffer.Height=1;
        buffer.DepthOrArraySize=1; buffer.MipLevels=1; buffer.SampleDesc.Count=1; buffer.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        upload=Resource(buffer,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
        readback=Resource(buffer,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
        D3D12_COMMAND_QUEUE_DESC q{}; q.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
        Require(SUCCEEDED(device->CreateCommandQueue(&q,IID_PPV_ARGS(&queue)))&&SUCCEEDED(device->CreateCommandAllocator(q.Type,IID_PPV_ARGS(&allocator)))&&
                SUCCEEDED(device->CreateCommandList(0,q.Type,allocator.Get(),nullptr,IID_PPV_ARGS(&list)))&&SUCCEEDED(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence))),"RR GPU command objects failed");
        event.value=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event.value!=nullptr,"RR GPU event failed");
        Upload(data);
    }
    void Dispatch(ffxFunctions& api,ffxContext* context,UINT frameIndex=UINT32_MAX,const float* delta=nullptr) {
        const auto& input=*current;
        Require(api.Dispatch,"RR dispatch export missing"); Begin();
        ffxDispatchDescDenoiserIndirectDiffuse diffuse{}; diffuse.header.type=FFX_API_DISPATCH_DESC_TYPE_DENOISER_INDIRECT_DIFFUSE;
        diffuse.signal.input=ffxApiGetResourceDX12(textures[4].resource.Get());
        diffuse.signal.output=ffxApiGetResourceDX12(textures[5].resource.Get(),FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
        ffxDispatchDescDenoiser desc{}; desc.header.type=FFX_API_DISPATCH_DESC_TYPE_DENOISER; desc.header.pNext=&diffuse.header;
        desc.commandList=list.Get(); desc.linearDepth=ffxApiGetResourceDX12(textures[0].resource.Get());
        desc.motionVectors=ffxApiGetResourceDX12(textures[1].resource.Get()); desc.normals=ffxApiGetResourceDX12(textures[2].resource.Get());
        desc.diffuseAlbedo=ffxApiGetResourceDX12(textures[3].resource.Get()); desc.motionVectorScale={1,1,1};
        for(UINT r=0;r<4;++r) for(UINT c=0;c<4;++c) {
            const float factor=(c<3?coordinateScale:1.f)/(r<3?coordinateScale:1.f);
            scaledView[r*4+c]=input.matrices[16+r*4+c]*factor;
            scaledProjection[r*4+c]=input.matrices[32+r*4+c]*(r==3?coordinateScale:1.f);
        }
        memcpy(&desc.view,scaledView,64); memcpy(&desc.projection,scaledProjection,64);
        sdkFrameIndex=frameIndex==UINT32_MAX?(input.header[7]?0:input.header[4]):frameIndex;
        for(UINT k=0;k<3;++k) cameraDelta[k]=delta?delta[k]:0;
        for(float& value:cameraDelta) value*=coordinateScale;
        desc.cameraPositionDelta={cameraDelta[0],cameraDelta[1],cameraDelta[2]};
        depthBounds[0]=.001f*coordinateScale; depthBounds[1]=10000.f*coordinateScale;
        desc.linearDepthBounds={depthBounds[0],depthBounds[1]}; desc.renderSize={width,height}; desc.frameIndex=sdkFrameIndex;
        desc.flags=(input.header[7]?FFX_DENOISER_DISPATCH_RESET:0)|(sqrtAlbedo?0:FFX_DENOISER_DISPATCH_NON_GAMMA_ALBEDO);
        dispatchFlags=desc.flags;
        std::cerr << "RR dispatch: frame=" << desc.frameIndex << ", reset=" << input.header[7] << '\n';
        dispatchCode=api.Dispatch(context,&desc.header);
        std::cerr << "RR dispatch: returned " << dispatchCode << '\n';
        Require(dispatchCode==0,"RR dispatch failed");
        CopyBack(6); Submit(); CheckPacked(5); inputsIntact=true;
        output.resize(size_t(pixels)*4); bool valid=true; UINT badValues=0;
        void* mapped{}; D3D12_RANGE range{0,SIZE_T(stagingBytes)}; Require(SUCCEEDED(readback->Map(0,&range,&mapped)),"RR output map failed");
        for(UINT i=0;i<pixels;++i) {
            bool changed=false; const auto& t=textures[5];
            for(UINT c=0;c<4;++c) {
                uint16_t half{},original{}; memcpy(&half,static_cast<char*>(mapped)+t.footprint.Offset+(i/width)*t.footprint.Footprint.RowPitch+(i%width)*8+c*2,2);
                const float value=DirectX::PackedVector::XMConvertHalfToFloat(half); output[i*4+c]=value;
                memcpy(&original,textures[4].packed.data()+i*8+c*2,2);
                const bool accepted=std::isfinite(value)&&(c==3?half==original:value>=0);
                if(!accepted&&badValues++<8) std::cerr << "RR output invalid: pixel=" << i << ", channel=" << c << ", hit=" << input.rows[i][23]
                    << ", value=" << value << ", input=" << DirectX::PackedVector::XMConvertHalfToFloat(original) << '\n';
                valid=valid&&accepted;
                if(c<3&&half!=original) changed=true;
            }
            if(changed&&input.rows[i][23]>0) ++changedPixels;
        }
        D3D12_RANGE none{0,0}; readback->Unmap(0,&none); Require(valid,"RR output incomplete/nonfinite/invalid alpha"); completed=true;
    }
    void Release() {
        // All submits synchronously fenced before this method can be reached.
        list.Reset(); allocator.Reset(); queue.Reset(); fence.Reset(); event.Close();
        for(auto& t:textures) if(t.resource) { t.resource.Reset(); ++releases; }
        if(upload) { upload.Reset(); ++releases; } if(readback) { readback.Reset(); ++releases; }
    }
    std::string Json() const {
        const auto& input=*current;
        std::ostringstream out; out.precision(9); out << "{\"dispatch_code\":" << dispatchCode << ",\"completed\":" << (completed?"true":"false")
            << ",\"albedo_encoding\":" << Quote(sqrtAlbedo?"sqrt":"linear") << ",\"dispatch_flags\":" << dispatchFlags
            << ",\"input_sha256\":" << Quote(RrHex(input.digest).c_str()) << ",\"external_bytes\":" << allocated << ",\"external_limit\":" << limit
            << ",\"resources_released\":" << releases << ",\"textures\":6";
        if(width!=128) out << ",\"width\":" << width << ",\"height\":" << height;
        out << ",\"reset\":" << (input.header[7]?"true":"false") << ",\"frame_index\":" << sdkFrameIndex << ",\"submissions\":" << sequence
            << ",\"camera_delta\":[" << cameraDelta[0] << ',' << cameraDelta[1] << ',' << cameraDelta[2] << ']'
            << (scaleId?",\"coordinate_scale\":" : "") << (scaleId?Quote(RrScalePresets[scaleId].name):"")
            << (scaleId?",\"scaled_view_sha256\":" : "") << (scaleId?Quote(RrHex(RrDigest(scaledView,sizeof(scaledView))).c_str()):"")
            << (scaleId?",\"scaled_projection_sha256\":" : "") << (scaleId?Quote(RrHex(RrDigest(scaledProjection,sizeof(scaledProjection))).c_str()):"");
        if(guideId) out << ",\"guide_preset\":" << Quote(RrGuidePresets[guideId].name);
        if(scaleId) out << ",\"linear_depth_bounds\":[" << depthBounds[0] << ',' << depthBounds[1] << ']';
        out
            << ",\"uploads_verified\":" << (uploaded?"true":"false") << ",\"inputs_unchanged\":" << (inputsIntact?"true":"false")
            << ",\"distance_clamps\":" << distanceClamps << ",\"changed_pixels\":" << changedPixels << ",\"output_floats\":" << output.size()
            << ",\"staging_bytes\":" << stagingBytes << ",\"packed_sha256\":[";
        for(UINT i=0;i<6;++i) { if(i) out << ','; out << Quote(RrHex(RrDigest(textures[i].packed.data(),textures[i].packed.size())).c_str()); }
        out << "],\"formats\":[\"R32_FLOAT\",\"RGBA16_FLOAT\",\"RGBA16_FLOAT\",\"RGBA16_FLOAT\",\"RGBA16_FLOAT\",\"RGBA16_FLOAT\"]}"; return out.str();
    }
    std::vector<unsigned char> OutputBytes() const {
        const auto& input=*current;
        Require(completed,"RR output has not completed");
        std::vector<unsigned char> bytes(56+output.size()*4); memcpy(bytes.data(),width==128?"RRTRRO01":"RRTRRO02",8);
        const UINT header[]={width==128?1u:2u,width,height,16}; memcpy(bytes.data()+8,header,16); memcpy(bytes.data()+24,input.digest.data(),32); memcpy(bytes.data()+56,output.data(),output.size()*4);
        const auto hash=RrDigest(bytes.data(),bytes.size()); bytes.insert(bytes.end(),hash.begin(),hash.end());
        return bytes;
    }
    void Save(const std::filesystem::path& path) const {
        Require(releases==8,"RR output resources not released"); const auto bytes=OutputBytes();
        RrHandle file; file.value=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        Require(file.value!=INVALID_HANDLE_VALUE,"RR output exists or unavailable"); DWORD written{};
        Require(WriteFile(file.value,bytes.data(),DWORD(bytes.size()),&written,nullptr)&&written==bytes.size(),"RR output write failed");
    }
};
