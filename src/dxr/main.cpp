#include "../scene/scene.h"
#include <d3d12.h>
#include <dxgi1_6.h>
#include <DirectXMath.h>
#include <wrl/client.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cfloat>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <future>
#include <fcntl.h>
#include <io.h>
#include <iostream>
#include <memory>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

using Microsoft::WRL::ComPtr;
using namespace DirectX;
namespace {
void Require(bool ok,const char* text) { if(!ok) throw std::runtime_error(text); }
std::string QuoteBytes(const std::string& value) { std::ostringstream out; out << '"'; for(unsigned char c:value) { if(c=='"'||c=='\\') out << '\\' << c; else if(c=='\r') out << "\\r"; else if(c=='\n') out << "\\n"; else if(c>=32) out << c; } out << '"'; return out.str(); }
#include "rc_isolation.h"
void Check(HRESULT hr,const char* what) { if(FAILED(hr)) { char text[256]; sprintf_s(text,"%s: 0x%08lx",what,static_cast<unsigned long>(hr)); throw std::runtime_error(text); } }
std::string JsonName(const wchar_t* input) {
    char text[1024]{}; WideCharToMultiByte(CP_UTF8,0,input,-1,text,1024,nullptr,nullptr);
    std::string escaped; for(unsigned char c:std::string(text)) { if(c=='"'||c=='\\') escaped+='\\'; if(c>=32) escaped+=c; } return escaped;
}
#include "material_inputs.h"
// Requested-GPU-memory policy. The renderer charges every allocation it requests
// against a running total and refuses to exceed these limits. The guard exists to
// catch unbounded growth; it must not be a resolution ceiling, because the product
// has to run at whatever resolution a user's display or window happens to be.
//
// The working set is a fixed cost per pixel: 240 bytes (output 4, readback 4,
// history 16, signals 88, previous/next 64+64). Two consequences:
//   - Both limits have to move together. The per-allocation limit must clear the
//     largest single buffer, which is `signals`: 696 MiB at 4K and 1.375 GiB at
//     the 4096x4096 the scene format allows. Raising only the total would still
//     refuse the resolution on the per-allocation check -- and the two checks
//     share one error string, so that failure is easy to misattribute.
//   - A fixed total becomes a resolution ceiling as soon as it is smaller than
//     the largest supported resolution. The ceiling is therefore set above the
//     whole expressible range -- 4096x4096 costs 3.88 GiB including display
//     buffers -- so there is room for future per-pixel buffers instead of
//     sitting at 95% of today's need.
//
// The ceiling is a fixed constant rather than a share of the adapter, because
// DXGI's dedicated-memory figure is not trustworthy in this process: the same RX
// 9070 XT reports 15.81 GiB to the x64 renderer and 3.00 GiB to the 32-bit one,
// which is clamped by the 32-bit address space rather than by the hardware.
// Deriving the limit from it made the x86 build refuse 4K while x64 accepted it.
// A flat ceiling is bounded, predictable, identical on both architectures and
// therefore testable. If a machine-aware cap is wanted later, the correct input
// is IDXGIAdapter3::QueryVideoMemoryInfo, whose Budget is valid in 32-bit;
// DedicatedVideoMemory is not it.
constexpr std::uint64_t MaxGpuAllocationBytes=2ull<<30; // 2 GiB, largest single buffer
constexpr std::uint64_t MaxGpuRequestedBytes=8ull<<30;  // 8 GiB whole working set
struct Options {
    std::filesystem::path scene,pixels,shader,signals; bool probe{},debug{},show{},interactive{},historyTest{},windowTest{},motionTest{},denoise{},shadows{true},budgetTest{};
    UINT adapter{},mode{},samples{1},seed{1},cutSerial{}; bool temporal{},gdi{},presentationTest{},asyncTest{},asyncCloseTest{},noFramePacing{},pacingTest{}; std::wstring temporalTest;
    float light[3]{-.4f,.6f,-1.f};
    std::filesystem::path materialPath,rrInputs,rcPaths,rcProbe,rcSdkBin; bool lightingTest{},varianceFilter{},rcStream{},rcPresentCandidate{},rcPresentationTest{},rcLiveSessionTest{};
    UINT rcTrainingBatches{1},rcBudgetMiB{32},rcWorkerTimeoutMs{60000},rcPersistentEpochs{1}; std::wstring rcSchedulerTest; bool rcResourceTest{},rcPoolTest{},rcGpuPoolTest{},rcRendererSessionTest{};
    std::filesystem::path rrRecord; float rrStep[3]{}; UINT rrResetFrame{UINT32_MAX}; bool rrStepSet{};
    float lightColor[3]{1,1,1},lightIntensity{.85f},ambient{.15f};
    float offset[3]{},yaw{},pitch{},sunRadius{.04f};
};
struct Device {
    ComPtr<IDXGIFactory6> factory; ComPtr<IDXGIAdapter1> adapter; ComPtr<ID3D12Device5> device;
    static constexpr UINT SlotCount=4;
    struct Slot { ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList4> list; UINT64 fence{}; } slots[SlotCount];
    ComPtr<ID3D12CommandQueue> queue; ComPtr<ID3D12GraphicsCommandList4> list;
    UINT slot{},slotMask{},asyncSubmissions{},fenceWaits{},maxInflight{};
    ComPtr<ID3D12Fence> fence; ComPtr<ID3D12InfoQueue> info;
    HANDLE event{}; UINT64 sequence{},allocated{},displayBytes{},peakRequested{},requestedLimit{}; DXGI_ADAPTER_DESC1 desc{};
    D3D12_RAYTRACING_TIER tier{}; D3D_SHADER_MODEL model{}; bool debugAvailable{};
    double buildMs{},traceMs{},temporalMs{},filterMs{},copyMs{},exportMs{};
    explicit Device(const Options& options) {
        ComPtr<ID3D12Debug> debug;
        debugAvailable=SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug)));
        if(options.debug) { Require(debugAvailable,"D3D12 debug layer unavailable; install Windows Graphics Tools or omit --debug"); debug->EnableDebugLayer(); }
        Check(CreateDXGIFactory2(0,IID_PPV_ARGS(&factory)),"DXGI factory");
        Check(factory->EnumAdapters1(options.adapter,&adapter),"adapter index"); Check(adapter->GetDesc1(&desc),"adapter description");
        // Set before any early return so --probe reports the real limit. Kept as a
        // member so the policy has one home and is reported rather than implied.
        requestedLimit=MaxGpuRequestedBytes;
        const auto created=D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device));
        if(FAILED(created) && options.probe) return;
        Check(created,"D3D12 device");
        D3D12_FEATURE_DATA_D3D12_OPTIONS5 rt{};
        if(SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS5,&rt,sizeof(rt)))) tier=rt.RaytracingTier;
        D3D12_FEATURE_DATA_SHADER_MODEL sm{D3D_SHADER_MODEL_6_5};
        if(SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL,&sm,sizeof(sm)))) model=sm.HighestShaderModel;
        device.As(&info);
        if(options.probe) return;
        Require(Supported(),"selected adapter lacks hardware DXR 1.1 / shader model 6.5; use rrt_replay for D3D9 raster fallback");
        D3D12_COMMAND_QUEUE_DESC q{}; q.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
        Check(device->CreateCommandQueue(&q,IID_PPV_ARGS(&queue)),"command queue");
        for(UINT i=0;i<SlotCount;++i) {
            Check(device->CreateCommandAllocator(q.Type,IID_PPV_ARGS(&slots[i].allocator)),"allocator");
            Check(device->CreateCommandList(0,q.Type,slots[i].allocator.Get(),nullptr,IID_PPV_ARGS(&slots[i].list)),"command list");
            if(i) Check(slots[i].list->Close(),"initial command list close");
        }
        list=slots[0].list;
        Check(device->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)),"fence");
        event=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event!=nullptr,"fence event");
    }
    ~Device() { if(event) CloseHandle(event); }
    bool Supported() const { return !(desc.Flags&DXGI_ADAPTER_FLAG_SOFTWARE) && tier>=D3D12_RAYTRACING_TIER_1_1 && model>=D3D_SHADER_MODEL_6_5; }
    void Probe(UINT index) {
        std::printf("{\"adapter\":%u,\"name\":\"%s\",\"vendor_id\":%u,\"dxgi_reported_dedicated_bytes\":%llu,\"requested_buffer_limit_bytes\":%llu,\"process_bits\":%zu,\"d3d12_available\":%s,\"dxr_tier\":%u,\"shader_model_tested\":%u,\"supported\":%s,\"debug_available\":%s}\n",
            index,JsonName(desc.Description).c_str(),desc.VendorId,static_cast<unsigned long long>(desc.DedicatedVideoMemory),static_cast<unsigned long long>(requestedLimit),sizeof(void*)*8,device?"true":"false",UINT(tier),UINT(model),Supported()?"true":"false",debugAvailable?"true":"false");
    }
    ComPtr<ID3D12Resource> Buffer(UINT64 bytes,D3D12_HEAP_TYPE heap,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS flags=D3D12_RESOURCE_FLAG_NONE) {
        bytes=(std::max)(bytes,UINT64(256)); Require(bytes<=MaxGpuAllocationBytes && allocated+bytes+displayBytes<=requestedLimit,"GPU allocation budget exceeded");
        D3D12_HEAP_PROPERTIES properties{}; properties.Type=heap;
        D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=bytes; desc.Height=1; desc.DepthOrArraySize=1; desc.MipLevels=1;
        desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; desc.Flags=flags;
        ComPtr<ID3D12Resource> result;
        Check(device->CreateCommittedResource(&properties,D3D12_HEAP_FLAG_NONE,&desc,state,nullptr,IID_PPV_ARGS(&result)),"buffer allocation"); allocated+=bytes; peakRequested=std::max(peakRequested,allocated+displayBytes); return result;
    }
    ComPtr<ID3D12Resource> SharedBuffer(UINT64 bytes) {
        Require(bytes&&bytes<=MaxGpuAllocationBytes&&allocated+bytes+displayBytes<=requestedLimit,"shared GPU allocation budget exceeded"); D3D12_HEAP_PROPERTIES properties{}; properties.Type=D3D12_HEAP_TYPE_DEFAULT;
        D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=bytes; desc.Height=1; desc.DepthOrArraySize=1; desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; desc.Flags=D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
        ComPtr<ID3D12Resource> result; Check(device->CreateCommittedResource(&properties,D3D12_HEAP_FLAG_SHARED,&desc,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,nullptr,IID_PPV_ARGS(&result)),"shared buffer allocation"); allocated+=bytes; peakRequested=std::max(peakRequested,allocated+displayBytes); return result;
    }
    ComPtr<ID3D12Resource> Upload(const void* data,std::size_t size) {
        auto result=Buffer(size,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ); void* mapped{}; D3D12_RANGE range{0,0};
        Check(result->Map(0,&range,&mapped),"upload map"); if(size) memcpy(mapped,data,size); result->Unmap(0,nullptr); return result;
    }
    void Uav(ID3D12Resource* resource) {
        D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_UAV; barrier.UAV.pResource=resource; list->ResourceBarrier(1,&barrier);
    }
    void Wait(UINT64 value) {
        Check(device->GetDeviceRemovedReason(),"GPU device status");
        if(fence->GetCompletedValue()<value) {
            ++fenceWaits; Check(fence->SetEventOnCompletion(value,event),"fence event");
            Require(WaitForSingleObject(event,30000)==WAIT_OBJECT_0,"GPU fence timed out");
        }
        Check(device->GetDeviceRemovedReason(),"GPU device status");
    }
    void DebugCheck() {
        if(info) {
            for(UINT64 i=0;i<info->GetNumStoredMessagesAllowedByRetrievalFilter();++i) {
                SIZE_T size{}; info->GetMessage(i,nullptr,&size); std::vector<std::uint8_t> bytes(size);
                auto* message=reinterpret_cast<D3D12_MESSAGE*>(bytes.data()); Check(info->GetMessage(i,message,&size),"debug message");
                if(message->Severity<=D3D12_MESSAGE_SEVERITY_ERROR) throw std::runtime_error(message->pDescription);
            }
            info->ClearStoredMessages();
        }
    }
    void Drain() { Wait(sequence); DebugCheck(); }
    void Begin() {
        slot=(slot+1)%SlotCount; Wait(slots[slot].fence); DebugCheck(); list=slots[slot].list;
        Check(slots[slot].allocator->Reset(),"reset allocator"); Check(list->Reset(slots[slot].allocator.Get(),nullptr),"reset command list");
    }
    void ClearReferences() {
        Drain();
        for(auto& item:slots) { Check(item.allocator->Reset(),"clear allocator"); Check(item.list->Reset(item.allocator.Get(),nullptr),"clear command references"); Check(item.list->Close(),"close cleared list"); }
    }
    HRESULT Execute(IDXGISwapChain3* swap=nullptr,bool wait=true) {
        Check(list->Close(),"close command list"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists);
        const HRESULT present=swap?swap->Present(1,0):S_OK;
        Check(queue->Signal(fence.Get(),++sequence),"queue signal"); slots[slot].fence=sequence; slotMask|=1u<<slot;
        const UINT64 completed=fence->GetCompletedValue(); UINT pending=0;
        for(const auto& item:slots) if(item.fence>completed) ++pending;
        maxInflight=std::max(maxInflight,pending);
        if(wait) Drain(); else ++asyncSubmissions;
        Check(present,"swapchain present"); return present;
    }
};
struct GpuDraw { UINT vertexOffset,indexOffset,textureOffset,width,height,filter,addressU,addressV,scissor[4]; PbrMaterial pbr{}; UINT usePbr{}; };
static_assert(sizeof(GpuDraw)==84);
struct Frame { XMFLOAT4X4 inverse; UINT width,height,mode,shadows; float background[3],ambient; float light[3],intensity;
    UINT sampleIndex,seed; float sunRadius; UINT flags;
    XMFLOAT4X4 previousViewProjection;
    UINT randomIndex,exportStart,exportCount,padding;
    float lightColor[3]; UINT colorPadding;
};
static_assert(sizeof(Frame)==224 && offsetof(Frame,previousViewProjection)==128);
struct Signal { XMFLOAT4 radiance,normalDepth,albedoHit,motion,filtered,position,sample,temporal,statistics; };
static_assert(sizeof(Signal)==144);
struct WorkingSignal { XMFLOAT4 normalDepth,albedoId,position,sample,temporal; XMFLOAT2 motion; };
struct TemporalRecord { XMFLOAT4 normalId,albedoCount,position,temporal; };
static_assert(sizeof(WorkingSignal)==88 && sizeof(TemporalRecord)==64);
constexpr UINT ExportChunkPixels=16384;
XMMATRIX Matrix(const D3DMATRIX& matrix) { XMFLOAT4X4 value; memcpy(&value,&matrix,sizeof(value)); return XMLoadFloat4x4(&value); }
void Admit(const rrt::scene::Scene& scene) {
    Require(scene.rejected.empty() && !scene.draws.empty(),"DXR requires a complete nonempty scene");
    Require(scene.draws.size()<=1024,"DXR draw budget exceeded (1024)");
    const auto& first=scene.draws.front().state;
    for(const auto& draw:scene.draws) {
        const auto& s=draw.state;
        Require(memcmp(&s.view,&first.view,sizeof(s.view))==0 && memcmp(&s.projection,&first.projection,sizeof(s.projection))==0,"DXR requires one shared camera");
        Require(s.viewport.X==0 && s.viewport.Y==0 && s.viewport.Width==scene.width && s.viewport.Height==scene.height && s.viewport.MinZ==0 && s.viewport.MaxZ==1,"DXR requires a full-frame viewport with depth range 0..1");
        Require(s.world._14==0 && s.world._24==0 && s.world._34==0 && s.world._44==1,"DXR requires affine world transforms");
        Require(!s.render[4] && !s.render[12] && s.render[7]==D3DCULL_NONE && s.render[2]==D3DSHADE_GOURAUD && s.render[21]==15 && !s.render[28],"DXR supports opaque, double-sided, Gouraud RGB output without sRGB conversion");
        Require((s.sampler[4]==1 || s.sampler[4]==2) && s.sampler[4]==s.sampler[5] && s.sampler[0]>=1 && s.sampler[0]<=3 && s.sampler[1]>=1 && s.sampler[1]<=3 && !s.sampler[10],"DXR supports matched point/linear filters, wrap/mirror/clamp and literal colour space");
        if(s.render[23]) Require(s.scissor.left>=0 && s.scissor.top>=0 && s.scissor.right<=LONG(scene.width) && s.scissor.bottom<=LONG(scene.height) && s.scissor.right>s.scissor.left && s.scissor.bottom>s.scissor.top,"invalid scissor");
    }
}
std::vector<std::uint8_t> Shader(const Options& options,UINT pass=0) {
    auto path=pass?std::filesystem::path{}:options.shader;
    if(path.empty()) { wchar_t module[32768]{}; Require(GetModuleFileNameW(nullptr,module,32768)!=0,"executable path"); path=std::filesystem::path(module).parent_path()/(pass==6?L"rrt_variance.dxil":pass==5?L"rrt_display_pixel.dxil":pass==4?L"rrt_display_vertex.dxil":pass==3?L"rrt_export.dxil":pass==2?L"rrt_temporal.dxil":pass==1?L"rrt_present.dxil":L"rrt_rayquery.dxil"); }
    std::ifstream file(path,std::ios::binary|std::ios::ate); Require(file.good(),"missing renderer DXIL; build rrt_dxr and deploy its matching shaders");
    auto size=file.tellg(); Require(size>0 && size<16*1024*1024,"invalid shader size"); std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    file.seekg(0); file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()); Require(file.good(),"shader read"); return bytes;
}
struct Acceleration { ComPtr<ID3D12Resource> result,scratch; };
Acceleration Build(Device& gpu,const D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS& inputs) {
    D3D12_RAYTRACING_ACCELERATION_STRUCTURE_PREBUILD_INFO info{}; gpu.device->GetRaytracingAccelerationStructurePrebuildInfo(&inputs,&info);
    Require(info.ResultDataMaxSizeInBytes && info.ScratchDataSizeInBytes,"invalid acceleration structure prebuild");
    Acceleration as{gpu.Buffer(info.ResultDataMaxSizeInBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_RAYTRACING_ACCELERATION_STRUCTURE,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS),
                    gpu.Buffer(info.ScratchDataSizeInBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS)};
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_DESC build{}; build.Inputs=inputs; build.DestAccelerationStructureData=as.result->GetGPUVirtualAddress(); build.ScratchAccelerationStructureData=as.scratch->GetGPUVirtualAddress();
    gpu.list->BuildRaytracingAccelerationStructure(&build,0,nullptr); gpu.Uav(as.result.Get()); return as;
}
struct Renderer {
    Device& gpu; const rrt::scene::Scene& scene;
    ComPtr<ID3D12Resource> vb,ib,materials,textures,instanceBuffer,output,readback,history,timingReadback,constants,signals,previousSignals,nextSignals,diagnosticOutput,signalReadback;
    std::vector<Acceleration> bottom; Acceleration top;
    ComPtr<ID3D12QueryHeap> timing; ComPtr<ID3D12RootSignature> root; ComPtr<ID3D12PipelineState> pso,presentPso,temporalPso,exportPso,variancePso;
    ComPtr<ID3D12Resource> filterScratch; UINT varianceDispatches{};
    Frame frame{}; UINT samples{},resets{},dispatches{}; bool configured{},copied{};
    XMFLOAT4X4 lastViewProjection{};
    Options activeOptions,lastRenderedOptions; bool temporalValid{}; UINT randomSequence{},temporalResets{};
    UINT exportSubmissions{},displaySubmissions{},displayResizes{},displayVerified{},displayPresented{},displayOccluded{},displayMask{},displaySuspended{},displayRejected{},readbackSubmissions{},renderReadbacks{},timedSamples{}; double exportWallMs{};
    UINT frameLatency{},pacingWaits{},pacingReady{},pacingMessages{},pacingTimeouts{},pacingTestMask{}; double pacingWaitMs{};
    UINT64 pendingTiming[Device::SlotCount]{};
    MaterialInputs materialInputs; UINT pbrDraws{};
    bool rrResetPending{true},rrFrameReset{true}; UINT rrInputSubmissions{},rcPathSubmissions{},rcPathQueries{},rcPathTraining{};
    const UINT64 bytes;
    Renderer(Device& device,const rrt::scene::Scene& inputScene,const Options& options):gpu(device),scene(inputScene),bytes(UINT64(scene.width)*scene.height*4) {
    Admit(scene);
    materialInputs=LoadMaterials(options.materialPath,scene);
    std::vector<rrt::scene::Vertex> vertices; std::vector<UINT> indices,texels; std::vector<GpuDraw> draws;
    std::uint64_t total=0;
    for(const auto& source:scene.draws) {
        total+=source.vertices.size()*24+source.indices.size()*4+source.texture.size(); Require(total<=rrt::scene::MaxBytes,"DXR upload budget exceeded");
        const auto& s=source.state;
        GpuDraw draw{UINT(vertices.size()),UINT(indices.size()),UINT(texels.size()),source.width,source.height,s.sampler[4],s.sampler[0],s.sampler[1],{0,0,scene.width,scene.height}};
        if(auto found=materialInputs.records.find(source.materialId);found!=materialInputs.records.end()) { draw.pbr=found->second; draw.usePbr=1; ++pbrDraws; }
        if(s.render[23]) { draw.scissor[0]=s.scissor.left; draw.scissor[1]=s.scissor.top; draw.scissor[2]=s.scissor.right; draw.scissor[3]=s.scissor.bottom; }
        const auto world=Matrix(s.world);
        for(auto v:source.vertices) { auto p=XMVector3TransformCoord(XMVectorSet(v.x,v.y,v.z,1),world); XMFLOAT3 xyz; XMStoreFloat3(&xyz,p);
            Require(std::isfinite(xyz.x)&&std::isfinite(xyz.y)&&std::isfinite(xyz.z) && std::abs(xyz.x)<=1e6f && std::abs(xyz.y)<=1e6f && std::abs(xyz.z)<=1e6f && std::abs(v.u)<=1e6f && std::abs(v.v)<=1e6f,"transformed position or UV exceeds finite renderer range (+/-1e6)"); v.x=xyz.x; v.y=xyz.y; v.z=xyz.z; vertices.push_back(v); }
        indices.insert(indices.end(),source.indices.begin(),source.indices.end());
        auto offset=texels.size(); texels.resize(offset+source.texture.size()/4); memcpy(texels.data()+offset,source.texture.data(),source.texture.size()); draws.push_back(draw);
    }
    vb=gpu.Upload(vertices.data(),vertices.size()*24); ib=gpu.Upload(indices.data(),indices.size()*4);
    materials=gpu.Upload(draws.data(),draws.size()*sizeof(GpuDraw)); textures=gpu.Upload(texels.data(),texels.size()*4);
    D3D12_QUERY_HEAP_DESC queryDesc{}; queryDesc.Type=D3D12_QUERY_HEAP_TYPE_TIMESTAMP; queryDesc.Count=5*Device::SlotCount;
    Check(gpu.device->CreateQueryHeap(&queryDesc,IID_PPV_ARGS(&timing)),"timestamp heap");
    timingReadback=gpu.Buffer(40*Device::SlotCount,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0);
    std::vector<D3D12_RAYTRACING_INSTANCE_DESC> instances;
    for(std::size_t i=0;i<draws.size();++i) {
        D3D12_RAYTRACING_GEOMETRY_DESC geometry{}; geometry.Type=D3D12_RAYTRACING_GEOMETRY_TYPE_TRIANGLES;
        geometry.Triangles.VertexBuffer={vb->GetGPUVirtualAddress()+draws[i].vertexOffset*24,24}; geometry.Triangles.VertexCount=UINT(scene.draws[i].vertices.size()); geometry.Triangles.VertexFormat=DXGI_FORMAT_R32G32B32_FLOAT;
        geometry.Triangles.IndexBuffer=ib->GetGPUVirtualAddress()+draws[i].indexOffset*4; geometry.Triangles.IndexCount=UINT(scene.draws[i].indices.size()); geometry.Triangles.IndexFormat=DXGI_FORMAT_R32_UINT;
        D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS input{}; input.Type=D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL; input.DescsLayout=D3D12_ELEMENTS_LAYOUT_ARRAY; input.NumDescs=1; input.pGeometryDescs=&geometry; input.Flags=D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_PREFER_FAST_TRACE;
        bottom.push_back(Build(gpu,input)); D3D12_RAYTRACING_INSTANCE_DESC instance{};
        instance.Transform[0][0]=instance.Transform[1][1]=instance.Transform[2][2]=1; instance.InstanceID=UINT(i); instance.InstanceMask=255; instance.AccelerationStructure=bottom.back().result->GetGPUVirtualAddress(); instances.push_back(instance);
    }
    instanceBuffer=gpu.Upload(instances.data(),instances.size()*sizeof(instances[0]));
    D3D12_BUILD_RAYTRACING_ACCELERATION_STRUCTURE_INPUTS input{}; input.Type=D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL; input.DescsLayout=D3D12_ELEMENTS_LAYOUT_ARRAY; input.NumDescs=UINT(instances.size()); input.InstanceDescs=instanceBuffer->GetGPUVirtualAddress();
    top=Build(gpu,input);
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,1);
    output=gpu.Buffer(bytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    readback=gpu.Buffer(bytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    history=gpu.Buffer(bytes*4,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    signals=gpu.Buffer(bytes/4*sizeof(WorkingSignal),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    previousSignals=gpu.Buffer(bytes/4*sizeof(TemporalRecord),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    nextSignals=gpu.Buffer(bytes/4*sizeof(TemporalRecord),D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    const UINT64 stagingBytes=options.signals.empty()?256:ExportChunkPixels*sizeof(Signal);
    diagnosticOutput=gpu.Buffer(stagingBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    if(!options.signals.empty()) signalReadback=gpu.Buffer(stagingBytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    constants=gpu.Buffer(256*Device::SlotCount,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
    D3D12_ROOT_PARAMETER parameters[13]{};
    for(UINT i=0;i<5;++i) { parameters[i].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; parameters[i].Descriptor.ShaderRegister=i; }
    parameters[5].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[5].Descriptor.ShaderRegister=0;
    parameters[6].ParameterType=D3D12_ROOT_PARAMETER_TYPE_CBV; parameters[6].Descriptor.ShaderRegister=0;
    parameters[7].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[7].Descriptor.ShaderRegister=1;
    parameters[8].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[8].Descriptor.ShaderRegister=2;
    parameters[9].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV; parameters[9].Descriptor.ShaderRegister=5;
    parameters[10].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[10].Descriptor.ShaderRegister=3;
    parameters[11].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[11].Descriptor.ShaderRegister=4;
    parameters[12].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV; parameters[12].Descriptor.ShaderRegister=5;
    D3D12_ROOT_SIGNATURE_DESC rootDesc{}; rootDesc.NumParameters=13; rootDesc.pParameters=parameters;
    ComPtr<ID3DBlob> serialized,error; Check(D3D12SerializeRootSignature(&rootDesc,D3D_ROOT_SIGNATURE_VERSION_1,&serialized,&error),"root signature serialization");
    Check(gpu.device->CreateRootSignature(0,serialized->GetBufferPointer(),serialized->GetBufferSize(),IID_PPV_ARGS(&root)),"root signature");
    const auto shader=Shader(options); D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline{}; pipeline.pRootSignature=root.Get(); pipeline.CS={shader.data(),shader.size()};
    Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&pso)),"ray-query compute pipeline");
    const auto presentShader=Shader(options,true); pipeline.CS={presentShader.data(),presentShader.size()};
    Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&presentPso)),"presentation compute pipeline");
    const auto temporalShader=Shader(options,2); pipeline.CS={temporalShader.data(),temporalShader.size()};
    Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&temporalPso)),"temporal compute pipeline");
    const auto exportShader=Shader(options,3); pipeline.CS={exportShader.data(),exportShader.size()};
    Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&exportPso)),"diagnostic export pipeline");
    if(options.varianceFilter) {
        const auto varianceShader=Shader(options,6); pipeline.CS={varianceShader.data(),varianceShader.size()};
        Check(gpu.device->CreateComputePipelineState(&pipeline,IID_PPV_ARGS(&variancePso)),"experimental variance filter pipeline");
    }
    gpu.list->ResolveQueryData(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0,2,timingReadback.Get(),0); gpu.Execute();
    gpu.buildMs=ReadTiming(2)[1];
    Configure(options);
    }
    ~Renderer() { try { gpu.Drain(); } catch(const std::exception& error) { std::fprintf(stderr,"renderer teardown: %s\n",error.what()); } }
    std::vector<double> ReadTiming(UINT count,UINT first=0) {
        UINT64 frequency{}; Check(gpu.queue->GetTimestampFrequency(&frequency),"timestamp frequency"); Require(frequency!=0,"invalid timestamp frequency");
        void* data{}; D3D12_RANGE range{first*8,(first+count)*8}; Check(timingReadback->Map(0,&range,&data),"timestamp readback");
        UINT64 ticks[5]{}; memcpy(ticks,static_cast<const char*>(data)+first*8,count*8); D3D12_RANGE noWrite{0,0}; timingReadback->Unmap(0,&noWrite);
        std::vector<double> result(count);
        for(UINT i=1;i<count;++i) { Require(ticks[i]>=ticks[i-1],"nonmonotonic GPU timestamps"); result[i]=(ticks[i]-ticks[0])*1000.0/frequency; }
        return result;
    }
    void CollectTiming(UINT slot) {
        if(!pendingTiming[slot]) return;
        gpu.Wait(pendingTiming[slot]); const auto times=ReadTiming(5,slot*5);
        gpu.traceMs+=times[1]; gpu.temporalMs+=times[2]-times[1]; gpu.filterMs+=times[3]-times[2]; gpu.copyMs+=times[4]-times[3];
        pendingTiming[slot]=0; ++timedSamples;
    }
    void Drain() { gpu.Drain(); for(UINT i=0;i<Device::SlotCount;++i) CollectTiming(i); }
    void Configure(const Options& options,bool forceReset=false) {
    Require(!configured || options.materialPath==activeOptions.materialPath,"material sidecars are immutable; recreate the renderer to change them");
    Frame next{}; next.width=scene.width; next.height=scene.height; next.mode=options.mode; next.shadows=options.shadows;
    next.background[0]=float((scene.clearColor>>16)&255)/255; next.background[1]=float((scene.clearColor>>8)&255)/255; next.background[2]=float(scene.clearColor&255)/255;
    next.ambient=options.ambient; next.intensity=options.lightIntensity; next.seed=options.seed; next.sunRadius=options.sunRadius; next.flags=(options.denoise?1:0)|(options.temporal?4:0);
    memcpy(next.lightColor,options.lightColor,12);
    if(options.lightColor[0]!=1 || options.lightColor[1]!=1 || options.lightColor[2]!=1) next.flags|=16;
    if(options.varianceFilter) next.flags|=32;
    XMVECTOR determinant{}; auto inverse=XMMatrixInverse(&determinant,Matrix(scene.draws[0].state.view)*Matrix(scene.draws[0].state.projection));
    Require(std::isfinite(XMVectorGetX(determinant)) && std::abs(XMVectorGetX(determinant))>1e-12f,"singular camera matrix");
    if(options.yaw!=0 || options.pitch!=0 || options.offset[0]!=0 || options.offset[1]!=0 || options.offset[2]!=0) {
        const auto camera=XMMatrixInverse(nullptr,Matrix(scene.draws[0].state.view));
        const auto rotation=XMMatrixRotationRollPitchYaw(XMConvertToRadians(options.pitch),XMConvertToRadians(options.yaw),0);
        inverse=XMMatrixInverse(nullptr,Matrix(scene.draws[0].state.projection))*rotation*camera*XMMatrixTranslation(options.offset[0],options.offset[1],options.offset[2]);
    }
    XMStoreFloat4x4(&next.inverse,inverse);
    float cameraWSign=0;
    const float jitter=options.mode==3?.5f:0.f;
    for(float y:{-jitter,float(scene.height-1)+jitter}) for(float x:{-jitter,float(scene.width-1)+jitter}) for(float z:{0.f,1.f}) {
        auto point=XMVector4Transform(XMVectorSet(x*2/scene.width-1,1-y*2/scene.height,z,1),inverse);
        const float w=XMVectorGetW(point);
        Require(std::isfinite(w) && std::abs(w)>1e-8f,"camera near/far plane at infinity unsupported");
        if(cameraWSign==0) cameraWSign=w>0?1.f:-1.f;
        Require(w*cameraWSign>0,"camera crosses a homogeneous horizon");
        XMFLOAT3 p; XMStoreFloat3(&p,XMVectorScale(point,1/w));
        Require(std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z) && std::abs(p.x)<=1e6f && std::abs(p.y)<=1e6f && std::abs(p.z)<=1e6f,"camera bounds exceed renderer range");
    }
    XMFLOAT3 light; XMStoreFloat3(&light,XMVector3Normalize(XMVectorSet(options.light[0],options.light[1],options.light[2],0))); memcpy(next.light,&light,12);
    // sampleIndex is dispatch state, not part of the history identity.
    auto previous=frame; previous.sampleIndex=0; previous.flags&=53;
    float distanceSquared=0; for(UINT i=0;i<3;++i) { const float delta=options.offset[i]-lastRenderedOptions.offset[i]; distanceSquared+=delta*delta; }
    const bool cut=copied && (distanceSquared>1 || std::abs(std::remainder(options.yaw-lastRenderedOptions.yaw,360.f))>=30 || std::abs(options.pitch-lastRenderedOptions.pitch)>=30);
    const bool explicitReset=forceReset || (configured && options.cutSerial!=activeOptions.cutSerial);
    const bool appearanceChanged=memcmp(reinterpret_cast<const char*>(&previous)+64,reinterpret_cast<const char*>(&next)+64,64)!=0 || memcmp(previous.lightColor,next.lightColor,12)!=0;
    if(!configured || explicitReset || appearanceChanged || memcmp(&previous,&next,offsetof(Frame,previousViewProjection))!=0) {
        if(!configured || explicitReset || cut || appearanceChanged) {
            rrResetPending=true;
            if(temporalValid) ++temporalResets;
            temporalValid=false; randomSequence=0;
        }
        if(configured) ++resets; samples=0; frame=next; configured=true;
    }
    activeOptions=options;
    }
    void Bind(ID3D12PipelineState* pipeline) {
        void* constantData{}; D3D12_RANGE empty{0,0}; Check(constants->Map(0,&empty,&constantData),"frame constants map");
        const UINT offset=gpu.slot*256;
        memcpy(static_cast<char*>(constantData)+offset,&frame,sizeof(frame)); D3D12_RANGE written{offset,offset+sizeof(frame)}; constants->Unmap(0,&written);
        gpu.list->SetComputeRootSignature(root.Get()); gpu.list->SetPipelineState(pipeline);
        ID3D12Resource* srvs[]={top.result.Get(),vb.Get(),ib.Get(),materials.Get(),textures.Get()};
        for(UINT i=0;i<5;++i) gpu.list->SetComputeRootShaderResourceView(i,srvs[i]->GetGPUVirtualAddress());
        gpu.list->SetComputeRootUnorderedAccessView(5,output->GetGPUVirtualAddress()); gpu.list->SetComputeRootConstantBufferView(6,constants->GetGPUVirtualAddress()+offset);
        gpu.list->SetComputeRootUnorderedAccessView(7,history->GetGPUVirtualAddress());
        gpu.list->SetComputeRootUnorderedAccessView(8,signals->GetGPUVirtualAddress());
        gpu.list->SetComputeRootShaderResourceView(9,previousSignals->GetGPUVirtualAddress());
        gpu.list->SetComputeRootUnorderedAccessView(10,nextSignals->GetGPUVirtualAddress());
        gpu.list->SetComputeRootUnorderedAccessView(11,diagnosticOutput->GetGPUVirtualAddress());
        gpu.list->SetComputeRootUnorderedAccessView(12,filterScratch->GetGPUVirtualAddress());
    }
    std::vector<std::uint32_t> Sample(bool readPixels=true) {
    Require(samples<4096,"sample budget exceeded (4096)");
    gpu.Begin(); CollectTiming(gpu.slot); const UINT query=gpu.slot*5;
    if(copied) {
        D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; barrier.Transition.pResource=output.Get(); barrier.Transition.StateBefore=D3D12_RESOURCE_STATE_COPY_SOURCE; barrier.Transition.StateAfter=D3D12_RESOURCE_STATE_UNORDERED_ACCESS; barrier.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES; gpu.list->ResourceBarrier(1,&barrier);
        gpu.Uav(history.Get());
        gpu.Uav(signals.Get());
    }
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query);
    frame.sampleIndex=samples;
    rrFrameReset=rrResetPending || !copied; rrResetPending=false;
    frame.flags=(frame.flags&53)|(copied?2:0)|(temporalValid?8:0); frame.previousViewProjection=lastViewProjection;
    frame.randomIndex=(frame.flags&4) && frame.mode==3?randomSequence:samples;
    filterScratch=previousSignals;
    Bind(pso.Get());
    gpu.list->Dispatch((scene.width+7)/8,(scene.height+7)/8,1);
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query+1);
    gpu.Uav(history.Get()); gpu.Uav(signals.Get()); gpu.list->SetPipelineState(temporalPso.Get());
    gpu.list->Dispatch((scene.width+7)/8,(scene.height+7)/8,1);
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query+2);
    gpu.Uav(signals.Get());
    const bool varianceActive=(frame.flags&33)==33 && frame.mode==3;
    if(varianceActive) {
        // Temporal reads are complete. The retired history buffer becomes scratch,
        // then stays UAV when it rotates into nextSignals for the following sample.
        D3D12_RESOURCE_BARRIER scratchBarrier{}; scratchBarrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        scratchBarrier.Transition={filterScratch.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS};
        gpu.list->ResourceBarrier(1,&scratchBarrier); gpu.list->SetPipelineState(variancePso.Get());
        gpu.list->Dispatch((scene.width+7)/8,(scene.height+7)/8,1); gpu.Uav(filterScratch.Get()); ++varianceDispatches;
    }
    gpu.list->SetPipelineState(presentPso.Get());
    gpu.list->Dispatch((scene.width+7)/8,(scene.height+7)/8,1);
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query+3);
    D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; barrier.Transition.pResource=output.Get(); barrier.Transition.StateBefore=D3D12_RESOURCE_STATE_UNORDERED_ACCESS; barrier.Transition.StateAfter=D3D12_RESOURCE_STATE_COPY_SOURCE; barrier.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES; gpu.list->ResourceBarrier(1,&barrier);
    if(readPixels) gpu.list->CopyResource(readback.Get(),output.Get());
    barrier.Transition.pResource=nextSignals.Get(); barrier.Transition.StateBefore=D3D12_RESOURCE_STATE_UNORDERED_ACCESS; barrier.Transition.StateAfter=D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE; gpu.list->ResourceBarrier(1,&barrier);
    if(!varianceActive) { barrier.Transition.pResource=previousSignals.Get(); std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter); gpu.list->ResourceBarrier(1,&barrier); }
    gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query+4);
    gpu.list->ResolveQueryData(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,query,5,timingReadback.Get(),query*8); gpu.Execute(nullptr,readPixels);
    pendingTiming[gpu.slot]=gpu.sequence;
    std::swap(nextSignals,previousSignals);
    temporalValid=(frame.flags&4) && frame.mode==3; ++randomSequence; lastRenderedOptions=activeOptions;
    XMStoreFloat4x4(&lastViewProjection,XMMatrixInverse(nullptr,XMLoadFloat4x4(&frame.inverse)));
    ++samples; ++dispatches; copied=true;
    if(!readPixels) return {};
    CollectTiming(gpu.slot); return ReadPixels();
    }
    std::vector<std::uint32_t> ReadPixels() {
    ++renderReadbacks;
    void* mapped{}; D3D12_RANGE range{0,SIZE_T(bytes)}; Check(readback->Map(0,&range,&mapped),"readback map"); std::vector<std::uint32_t> pixels(std::size_t(scene.width)*scene.height); memcpy(pixels.data(),mapped,bytes); D3D12_RANGE noWrite{0,0}; readback->Unmap(0,&noWrite); return pixels;
    }
    std::vector<std::uint32_t> Snapshot() {
        Require(copied && samples>0,"snapshot requires a rendered frame");
        Drain(); gpu.Begin(); gpu.list->CopyResource(readback.Get(),output.Get()); gpu.Execute(); ++readbackSubmissions; return ReadPixels();
    }
    std::vector<std::uint32_t> RenderTo(UINT target,bool readPixels=true) {
        Require(target>samples && target<=4096,"invalid target sample count");
        std::vector<std::uint32_t> pixels; while(samples<target) pixels=Sample(readPixels); return pixels;
    }
    void SaveSignals(const std::filesystem::path& path) {
        if(path.empty()) return;
        Require(signalReadback && samples>0,"signals have not been rendered");
        Drain();
        const auto start=std::chrono::steady_clock::now();
        HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        Require(file!=INVALID_HANDLE_VALUE,"signal output exists or path unavailable");
        try {
        const char magic[8]={'R','R','T','S','I','G','0','2'};
        const UINT header[]={2,scene.width,scene.height,sizeof(Signal),samples,(frame.flags&1)|((frame.flags&4)>>1),frame.mode}; DWORD written{};
        bool ok=WriteFile(file,magic,8,&written,nullptr) && written==8;
        ok=ok && WriteFile(file,header,sizeof(header),&written,nullptr) && written==sizeof(header);
        Require(ok,"signal header output failed");
        for(UINT first=0;first<scene.width*scene.height;first+=ExportChunkPixels) {
            frame.exportStart=first; frame.exportCount=std::min(ExportChunkPixels,scene.width*scene.height-first);
            gpu.Begin(); Bind(exportPso.Get()); gpu.Uav(history.Get()); gpu.Uav(signals.Get());
            gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0);
            gpu.list->Dispatch((frame.exportCount+63)/64,1,1);
            D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            barrier.Transition={diagnosticOutput.Get(),D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE};
            gpu.list->ResourceBarrier(1,&barrier);
            const SIZE_T signalBytes=SIZE_T(frame.exportCount)*sizeof(Signal);
            gpu.list->CopyBufferRegion(signalReadback.Get(),0,diagnosticOutput.Get(),0,signalBytes);
            std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter); gpu.list->ResourceBarrier(1,&barrier);
            gpu.list->EndQuery(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,1);
            gpu.list->ResolveQueryData(timing.Get(),D3D12_QUERY_TYPE_TIMESTAMP,0,2,timingReadback.Get(),0); gpu.Execute();
            ++exportSubmissions; gpu.exportMs+=ReadTiming(2)[1];
            void* data{}; D3D12_RANGE range{0,signalBytes}; Check(signalReadback->Map(0,&range,&data),"signal readback map");
            ok=WriteFile(file,data,DWORD(signalBytes),&written,nullptr) && written==signalBytes;
            D3D12_RANGE noWrite{0,0}; signalReadback->Unmap(0,&noWrite); Require(ok,"signal output failed");
        }
        } catch(...) { CloseHandle(file); throw; }
        CloseHandle(file);
        exportWallMs+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    }
};
#include "rr_inputs.h"
#include "rr_record.h"
#include "rc_paths.h"
#include "rc_admission.h"
#include "rc_direct.h"

std::string VerifyRcResourceLifetime(Renderer& renderer,const Options& options,const rrt::scene::Hash& sceneDigest) {
    const UINT64 baseline=renderer.gpu.allocated;
    RcBufferPool pool(renderer.gpu,options.rcGpuPoolTest); UINT64 stableAllocations=0,stablePeak=0,diagnosticAllocations=0; std::ostringstream reports;
    const UINT iterations=options.rcGpuPoolTest?8:6;
    for(UINT epoch=0;epoch<iterations;++epoch) {
        auto request=options; request.rcPresentCandidate=true;
        if(epoch>=6) request.rcPresentCandidate=false;
        if(epoch==2) request.rcBudgetMiB=1;
        if(epoch==4) request.offset[0]+=.05f;
        if(epoch==5) request.rcLiveSessionTest=true;
        renderer.Configure(request,true); renderer.RenderTo(1);
        const auto noCache=renderer.ReadPixels();
        auto report=RunRcDirect(renderer,request,sceneDigest,options.rcPoolTest?&pool:nullptr);
        Require(renderer.gpu.allocated==baseline+pool.charged,"RC transaction retained unowned buffer budget");
        if(epoch==0) stableAllocations=pool.allocations;
        if(options.rcPoolTest&&epoch==1) Require(pool.allocations==stableAllocations&&pool.reuses>0,"RC staging buffers were not reused");
        if(options.rcPoolTest&&epoch==2) Require(pool.charged==0,"RC failed transaction retained staging pool");
        if(options.rcPoolTest&&epoch==3) Require(pool.allocations>stableAllocations,"RC failure recovery did not rebuild pool");
        if(epoch==6) diagnosticAllocations=pool.allocations;
        if(epoch==7) Require(pool.allocations==diagnosticAllocations,"RC diagnostic repeat allocated buffers");
        Require(report.find(epoch==2?"\"result\":\"rc-direct-shared-fallback\"":"\"result\":\"rc-direct-shared-pass\"")!=std::string::npos,"RC resource lifecycle transaction unexpected result");
        if(epoch==0) stablePeak=renderer.gpu.peakRequested;
        if(epoch==1||epoch==3) Require(renderer.gpu.peakRequested==stablePeak,"RC repeated transaction increased peak budget");
        if(epoch==2||epoch>=6) Require(renderer.ReadPixels()==noCache,"RC failed/diagnostic transaction changed no-cache output");
        if(epoch) reports << ','; reports << report;
    }
    const UINT64 retained=pool.charged; pool.Clear();
    Require(renderer.gpu.allocated==baseline,"RC pool teardown retained buffer budget");
    std::ostringstream out;
    out << "{\"result\":\"rc-resource-lifetime-pass\",\"iterations\":" << iterations << ",\"baseline_live_bytes\":" << baseline
        << ",\"final_live_bytes\":" << renderer.gpu.allocated << ",\"peak_requested_bytes\":" << renderer.gpu.peakRequested
        << ",\"staging_pool_enabled\":" << (options.rcPoolTest?"true":"false") << ",\"staging_pool_allocations\":" << pool.allocations
        << ",\"staging_pool_reuses\":" << pool.reuses << ",\"staging_pool_retained_bytes\":" << retained
        << ",\"gpu_pool_enabled\":" << (options.rcGpuPoolTest?"true":"false") << ",\"buffer_pool_allocations\":" << pool.allocations << ",\"buffer_pool_reuses\":" << pool.reuses << ",\"buffer_pool_retained_bytes\":" << retained
        << ",\"pool_restore_submissions\":" << pool.restoreSubmissions << ",\"pool_restored_buffers\":" << pool.restoredBuffers
        << ",\"transactions\":[" << reports.str() << "]}";
    return out.str();
}
#include "presentation.h"
void Save(const std::filesystem::path& path,const std::vector<UINT>& pixels) {
    if(path.empty()) return; std::vector<std::uint8_t> bytes; bytes.reserve(pixels.size()*3);
    for(auto value:pixels) { bytes.push_back(value&255); bytes.push_back((value>>8)&255); bytes.push_back((value>>16)&255); }
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr); Require(file!=INVALID_HANDLE_VALUE,"pixel output exists or path unavailable");
    DWORD written{}; bool ok=WriteFile(file,bytes.data(),DWORD(bytes.size()),&written,nullptr) && written==bytes.size(); CloseHandle(file); Require(ok,"pixel output failed");
}
bool Control(Options& options,UINT key,const rrt::scene::Scene& scene) {
    if(key>=L'1' && key<=L'4') { options.mode=key-L'1'; return true; }
    if(key==VK_HOME) { std::fill(std::begin(options.offset),std::end(options.offset),0.f); options.yaw=options.pitch=0; ++options.cutSerial; return true; }
    if(key==VK_LEFT || key==VK_RIGHT) { options.yaw+=key==VK_LEFT?-3.f:3.f; options.yaw=std::remainder(options.yaw,360.f); return true; }
    if(key==VK_UP || key==VK_DOWN) { options.pitch=std::clamp(options.pitch+(key==VK_UP?-3.f:3.f),-89.f,89.f); return true; }
    if(key==L'L') { const auto x=options.light[0]; options.light[0]=-options.light[2]; options.light[2]=x; return true; }
    if(key==L'H') { options.shadows=!options.shadows; return true; }
    if(key==L'F') { options.denoise=!options.denoise; return true; }
    if(key==L'T') { options.temporal=!options.temporal; return true; }
    if(key==L'R') { ++options.cutSerial; return true; }
    float x=0,y=0,z=0;
    if(key==L'A') x=-.05f; else if(key==L'D') x=.05f;
    else if(key==L'Q') y=-.05f; else if(key==L'E') y=.05f;
    else if(key==L'W') z=.05f; else if(key==L'S') z=-.05f; else return false;
    // Navigation follows the captured camera basis, including current rotation.
    const auto camera=XMMatrixInverse(nullptr,Matrix(scene.draws[0].state.view));
    const auto rotation=XMMatrixRotationRollPitchYaw(XMConvertToRadians(options.pitch),XMConvertToRadians(options.yaw),0);
    XMFLOAT3 delta; XMStoreFloat3(&delta,XMVector3TransformNormal(XMVectorSet(x,y,z,0),rotation*camera));
    options.offset[0]+=delta.x; options.offset[1]+=delta.y; options.offset[2]+=delta.z; return true;
}
struct Preview { const std::vector<UINT>* pixels; UINT width,height; Options* options{}; bool dirty{},paused{},native{},repaint{true},suspended{}; };
LRESULT CALLBACK Procedure(HWND window,UINT message,WPARAM a,LPARAM b) {
    if(message==WM_NCCREATE) SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(reinterpret_cast<CREATESTRUCTW*>(b)->lpCreateParams));
    if(message==WM_DESTROY) { PostQuitMessage(0); return 0; }
    auto* preview=reinterpret_cast<Preview*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(message==WM_SIZE && preview) { preview->suspended=a==SIZE_MINIMIZED || !LOWORD(b) || !HIWORD(b); preview->repaint=true; return 0; }
    if(message==WM_PAINT) {
        PAINTSTRUCT paint; HDC dc=BeginPaint(window,&paint);
        if(preview && preview->native) preview->repaint=true;
        if(preview && !preview->native) { BITMAPINFO bitmap{}; bitmap.bmiHeader.biSize=sizeof(BITMAPINFOHEADER); bitmap.bmiHeader.biWidth=preview->width; bitmap.bmiHeader.biHeight=-LONG(preview->height); bitmap.bmiHeader.biPlanes=1; bitmap.bmiHeader.biBitCount=32; bitmap.bmiHeader.biCompression=BI_RGB; RECT client; GetClientRect(window,&client);
            StretchDIBits(dc,0,0,client.right,client.bottom,0,0,preview->width,preview->height,preview->pixels->data(),&bitmap,DIB_RGB_COLORS,SRCCOPY); }
        EndPaint(window,&paint); return 0;
    }
    return DefWindowProcW(window,message,a,b);
}
void Show(std::vector<UINT>& pixels,Renderer& renderer,Options& options) {
    const auto width=renderer.scene.width,height=renderer.scene.height;
    WNDCLASSW c{}; c.lpfnWndProc=Procedure; c.hInstance=GetModuleHandleW(nullptr); c.lpszClassName=L"RRTRayQuery"; Check(RegisterClassW(&c)?S_OK:E_FAIL,"preview class");
    Preview preview{&pixels,width,height,options.interactive?&options:nullptr}; RECT rect{0,0,LONG(width),LONG(height)}; AdjustWindowRect(&rect,WS_OVERLAPPEDWINDOW,FALSE);
    preview.native=!options.gdi;
    HWND window=CreateWindowW(c.lpszClassName,L"RRT - DXR hardware-ray-query result",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,rect.right-rect.left,rect.bottom-rect.top,nullptr,nullptr,c.hInstance,&preview); Require(window!=nullptr,"preview window");
    if(!options.windowTest && !options.asyncCloseTest) ShowWindow(window,SW_SHOW);
    try {
        std::unique_ptr<NativeDisplay> display;
        if(preview.native) display=std::make_unique<NativeDisplay>(renderer,window,options);
        const bool readPixels=options.gdi || (options.windowTest && !options.asyncTest);
        const auto checkpoint=[&]() { if(options.asyncTest) { pixels=renderer.Snapshot(); display->Draw(pixels); } };
        bool running=true; MSG msg{}; UINT testStep=0; std::vector<UINT> reference;
        UINT suspendedSubmission=0,pacingStep=0;
        if(options.pacingTest) renderer.pacingTestMask=VerifyFrameWait(window);
        const auto initial=options;
        const auto key=[&](UINT value) { Require(PostMessageW(window,WM_KEYDOWN,value,0)!=0,"post test key"); };
        const auto resize=[&](UINT w,UINT h) { RECT bounds{0,0,LONG(w),LONG(h)}; AdjustWindowRect(&bounds,WS_OVERLAPPEDWINDOW,FALSE);
            Require(SetWindowPos(window,nullptr,0,0,bounds.right-bounds.left,bounds.bottom-bounds.top,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE)!=0,"test resize"); };
        while(running) {
            while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)) {
                if(msg.message==WM_QUIT) { running=false; break; }
                // Handle only keys addressed to our window; no global hooks.
                if(preview.options && msg.hwnd==window && msg.message==WM_KEYDOWN) {
                    if(msg.wParam==VK_ESCAPE) { DestroyWindow(window); continue; }
                    if(msg.wParam==VK_SPACE) preview.paused=!preview.paused;
                    else preview.dirty=Control(options,UINT(msg.wParam),renderer.scene) || preview.dirty;
                }
                TranslateMessage(&msg); DispatchMessageW(&msg);
            }
            if(!running) break;
            const bool recovering=display && display->occluded;
            const bool available=!preview.suspended && (!display || display->Available());
            if(recovering && available) preview.repaint=true;
            if(preview.suspended) ++renderer.displaySuspended;
            const bool wantsRender=options.interactive && (preview.dirty || renderer.samples==0 || (!preview.paused && renderer.samples<options.samples));
            if(display && available && (wantsRender || preview.repaint)) {
                RECT client{}; Require(GetClientRect(window,&client)!=0,"window client bounds");
                display->Resize(UINT(client.right),UINT(client.bottom));
                // A newly acquired permit returns through the message pump before sampling input.
                if(!display->Ready()) continue;
            }
            if(preview.dirty && available) { renderer.Configure(options); preview.dirty=false; }
            const bool render=available && options.interactive && (renderer.samples==0 || (!preview.paused && renderer.samples<options.samples));
            if(render) { pixels=renderer.Sample(readPixels); if(running) InvalidateRect(window,nullptr,FALSE); }
            if(display && available && (render || preview.repaint)) {
                RECT client{}; Require(GetClientRect(window,&client)!=0,"window client bounds");
                display->Resize(UINT(client.right),UINT(client.bottom)); display->Draw(pixels,!options.asyncTest || (!render && !pixels.empty())); preview.repaint=false;
            }
            wchar_t title[256]; swprintf_s(title,L"RRT DXR | mode %u | %u/%u samples%s | spatial %s temporal %s | WASD/QE, arrows, Home, 1-4, L/H/F/T/R, Space",options.mode,renderer.samples,options.samples,preview.paused?L" (paused)":L"",options.denoise && options.mode==3?L"on":L"off",options.temporal && options.mode==3?L"on":L"off");
            SetWindowTextW(window,title);
            bool queued=false;
            if(options.pacingTest) {
                if(pacingStep==0 && renderer.samples==3) { resize(width+37,height+19); key(VK_SPACE); ++pacingStep; queued=true; }
                else if(pacingStep==1 && preview.paused) {
                    Require(renderer.samples==3 && display->width==width+37,"paced pause/resize failed");
                    suspendedSubmission=renderer.displaySubmissions;
                    SendMessageW(window,WM_SIZE,SIZE_MINIMIZED,0); ++pacingStep; queued=true;
                } else if(pacingStep==2 && preview.suspended) {
                    Require(renderer.displaySubmissions==suspendedSubmission,"paced suspend submitted work");
                    SendMessageW(window,WM_SIZE,SIZE_RESTORED,MAKELPARAM(width+37,height+19));
                    key(VK_SPACE); ++pacingStep; queued=true;
                }
            }
            if(options.asyncCloseTest && renderer.samples==7) {
                // A queued control that never renders must not relabel the final image.
                key(L'1'+(options.mode+1)%4);
                Require(PostMessageW(window,WM_CLOSE,0,0)!=0,"post async early close"); queued=true;
            }
            if(options.windowTest) {
                if(testStep==0 && renderer.samples==options.samples) {
                    checkpoint();
                    reference=pixels; key(VK_SPACE); key(L'D'); ++testStep; queued=true;
                } else if(testStep==1 && preview.paused) {
                    checkpoint();
                    Require(renderer.samples==1 && renderer.resets==1,"paused navigation must display one fresh sample");
                    key(VK_HOME); key(VK_SPACE); ++testStep; queued=true;
                } else if(testStep==2 && renderer.samples==options.samples) {
                    checkpoint();
                    Require(pixels==reference && renderer.resets==2,"Home/resume did not restore the captured camera image");
                    key(L'1'+(initial.mode+1)%4); key(L'L'); key(L'H'); key(L'F'); ++testStep; queued=true;
                } else if(testStep==3 && renderer.samples==options.samples) {
                    checkpoint();
                    Require(options.mode==(initial.mode+1)%4 && options.shadows!=initial.shadows && options.denoise!=initial.denoise && renderer.resets==3,"mode/light/shadow/filter controls failed");
                    key(L'1'+initial.mode); key(L'L'); key(L'L'); key(L'L'); key(L'H'); key(L'F'); ++testStep; queued=true;
                } else if(testStep==4 && renderer.samples==options.samples) {
                    checkpoint();
                    Require(pixels==reference && renderer.resets==4,"window controls left stale accumulation");
                    if(options.presentationTest) resize(width+37,height+19);
                    else Require(PostMessageW(window,WM_CLOSE,0,0)!=0,"post test close");
                    ++testStep; queued=true;
                } else if(options.presentationTest && testStep==5) {
                    Require(display->width==width+37 && display->height==height+19,"first display resize failed");
                    resize(width+61,height+27); ++testStep; queued=true;
                } else if(options.presentationTest && testStep==6) {
                    Require(display->width==width+61 && display->height==height+27,"second display resize failed");
                    suspendedSubmission=renderer.displaySubmissions;
                    SendMessageW(window,WM_SIZE,SIZE_MINIMIZED,0); ++testStep; queued=true;
                } else if(options.presentationTest && testStep==7) {
                    Require(preview.suspended && renderer.displaySubmissions==suspendedSubmission,"minimized window submitted GPU display work");
                    SendMessageW(window,WM_SIZE,SIZE_RESTORED,MAKELPARAM(width+61,height+27)); ++testStep; queued=true;
                } else if(options.presentationTest && testStep==8) {
                    Require(!preview.suspended && renderer.displaySubmissions>suspendedSubmission,"restored window did not repaint");
                    // Deterministic status-path check, not a claim of actual desktop occlusion.
                    display->Status(DXGI_STATUS_OCCLUDED); Require(display->occluded,"occlusion state not retained"); display->Status(S_OK);
                    resize(width,height); ++testStep; queued=true;
                } else if(options.presentationTest && testStep==9) {
                    Require(display->width==width && display->height==height && pixels==reference && renderer.resets==4,"display resize changed render history");
                    // Deliberate out-of-range resize: it must be refused and must
                    // leave the live display and its resources intact. Only the
                    // dimension cap is reachable now. At the current 8 GiB limit a
                    // legal 4096x4096 display costs about 134 MiB, so no in-range
                    // resize can trip the display allocation budget, and the guard
                    // is exercised directly by --budget-test instead. Picking the
                    // refusal reason from the fixture size would only test whichever
                    // limit happens to be tightest.
                    bool rejected=false;
                    try { display->Resize(4097,4096); }
                    catch(const std::runtime_error& error) { rejected=std::string(error.what()).starts_with("display dimensions"); }
                    Require(rejected && display->width==width && display->height==height,"display bounds failure damaged live resources");
                    ++renderer.displayRejected; display->Draw(pixels,!options.asyncTest);
                    Require(PostMessageW(window,WM_CLOSE,0,0)!=0,"post presentation close"); ++testStep; queued=true;
                }
            }
            if(!render && !queued) {
                if(display && display->occluded) MsgWaitForMultipleObjects(0,nullptr,FALSE,100,QS_ALLINPUT);
                else WaitMessage();
            }
        }
        if(options.windowTest) Require(testStep==(options.presentationTest?10u:5u),"window test closed prematurely");
        if(options.asyncCloseTest) Require(renderer.samples==7,"async early close missed target");
        if(options.pacingTest) Require(pacingStep==3 && renderer.pacingTestMask==7,"pacing lifecycle incomplete");
        renderer.Drain();
        Require(renderer.samples>0,"viewer closed before the first rendered sample; no output saved");
        options=renderer.lastRenderedOptions;
    } catch(...) { if(IsWindow(window)) DestroyWindow(window); throw; }
}
#include "rc_admission.h"
std::string RunRcScheduledPresentation(Renderer& renderer,const Options& options,const rrt::scene::Hash& sceneDigest) {
    VerifyRcFrameAdmission();
    RcFrameAdmission admission; RcFrameAdmission::Identity identity{1,1,1,1,1};
    admission.RequestFrame(identity); const auto active=admission.Begin();
    const auto width=renderer.scene.width,height=renderer.scene.height;
    WNDCLASSW c{}; c.lpfnWndProc=Procedure; c.hInstance=GetModuleHandleW(nullptr); c.lpszClassName=L"RRTRcScheduledPresentation"; Check(RegisterClassW(&c)?S_OK:E_FAIL,"RC presentation class");
    std::vector<UINT> pendingPixels; Preview preview{&pendingPixels,width,height,nullptr}; preview.native=true;
    RECT rect{0,0,LONG(width),LONG(height)}; AdjustWindowRect(&rect,WS_OVERLAPPEDWINDOW,FALSE);
    HWND window=CreateWindowW(c.lpszClassName,L"RRT - scheduled Radiance Cache candidate",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,rect.right-rect.left,rect.bottom-rect.top,nullptr,nullptr,c.hInstance,&preview); Require(window!=nullptr,"RC presentation window");
    try {
        const auto waitStart=std::chrono::steady_clock::now();
        auto transaction=std::async(std::launch::async,[&]() { return RunRcDirect(renderer,options,sceneDigest); });
        Require(PostMessageW(window,WM_APP,0,0)!=0,"RC presentation provider-wait message");
        if(options.rcSchedulerTest==L"close") Require(PostMessageW(window,WM_CLOSE,0,0)!=0,"RC scheduler close message");
        if(options.rcSchedulerTest==L"camera") for(UINT i=0;i<3;++i) Require(PostMessageW(window,WM_APP+1,0,0)!=0,"RC scheduler camera message");
        UINT providerMessages=0,providerPumps=0; MSG message{};
        const auto pump=[&]() {
            while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) {
                ++providerMessages;
                if(message.message==WM_QUIT || (message.hwnd==window&&message.message==WM_CLOSE)) admission.Close();
                if(!admission.closed&&message.hwnd==window&&message.message==WM_APP+1) { ++identity.camera; admission.RequestFrame(identity); }
                TranslateMessage(&message); DispatchMessageW(&message);
            }
        };
        for(;;) {
            pump();
            if(transaction.wait_for(std::chrono::milliseconds(0))==std::future_status::ready) break;
            ++providerPumps; MsgWaitForMultipleObjects(0,nullptr,FALSE,10,QS_ALLINPUT);
        }
        auto report=transaction.get(); const double providerWaitMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-waitStart).count();
        Require(providerMessages>0&&providerPumps>0,"RC presentation provider wait did not pump messages");
        const auto current=[&]() { if(!IsWindow(window)) admission.Close(); return !admission.closed&&active.identity==admission.latest; };
        const auto suppress=[&]() {
            Require(!admission.Complete(active.serial,true),"RC suppression of current epoch");
            if(IsWindow(window)) DestroyWindow(window);
            Require(!report.empty()&&report.back()=='}',"RC presentation report malformed"); report.pop_back();
            std::ostringstream suffix;
            suffix << ",\"native_presentation\":false,\"native_display_submissions\":0,\"scheduler_closed\":" << (admission.closed?"true":"false")
                << ",\"scheduler_pending\":" << (admission.queued?1:0) << ",\"scheduler_coalesced\":" << admission.coalesced
                << ",\"scheduler_discarded\":" << admission.discarded << ",\"provider_wait_messages\":" << providerMessages << '}';
            return report+suffix.str();
        };
        if(!current()) return suppress();
        pendingPixels=renderer.ReadPixels();
        const UINT frameWaitMask=VerifyFrameWait(window); UINT admissionAttempts=0;
        if(!current()) return suppress();
        {
            NativeDisplay display(renderer,window,options,true,true);
            if(options.rcSchedulerTest==L"close-admission") Require(PostMessageW(window,WM_CLOSE,0,0)!=0,"RC scheduler admission close message");
            for(;admissionAttempts<100;++admissionAttempts) {
                pump();
                if(!current()||display.Ready()) break;
            }
            if(current()) {
                Require(display.admitted,"RC presentation frame admission timed out");
                Require(admission.Complete(active.serial,true),"RC current epoch rejected");
                display.Draw(pendingPixels,true);
                Require(renderer.frameLatency==1&&renderer.displaySubmissions==1&&renderer.displayVerified==1&&renderer.displayMask!=0&&renderer.displayPresented+renderer.displayOccluded==1,"RC native presentation evidence invalid");
            }
        }
        if(!current()) return suppress();
        if(IsWindow(window)) DestroyWindow(window);
        Require(!report.empty()&&report.back()=='}',"RC presentation report malformed"); report.pop_back(); std::ostringstream suffix;
        suffix << ",\"native_presentation\":true,\"native_display_submissions\":" << renderer.displaySubmissions << ",\"native_display_verified\":" << renderer.displayVerified << ",\"native_display_presented\":" << renderer.displayPresented << ",\"native_display_occluded\":" << renderer.displayOccluded << ",\"native_display_buffer_mask\":" << renderer.displayMask << ",\"native_frame_latency\":" << renderer.frameLatency << ",\"frame_wait_mask\":" << frameWaitMask << ",\"frame_admission_attempts\":" << admissionAttempts << ",\"provider_wait_messages\":" << providerMessages << ",\"provider_wait_pumps\":" << providerPumps << ",\"provider_wait_ms\":" << providerWaitMs << '}'; report+=suffix.str(); return report;
    } catch(...) { if(IsWindow(window)) DestroyWindow(window); throw; }
}
void VerifyHistory(Renderer& renderer,const Options& options,const std::vector<UINT>& reference) {
    const auto allocation=renderer.gpu.allocated;
    renderer.Configure(options); Require(renderer.samples==options.samples,"unchanged options discarded history");
    for(UINT test=0;test<9;++test) {
        auto changed=options;
        const UINT keys[]={L'D',VK_RIGHT,UINT(options.pitch>=86?VK_UP:VK_DOWN),L'L',L'H',L'1'+(options.mode+1)%4};
        if(test<6) Control(changed,keys[test],renderer.scene);
        else if(test==6) ++changed.seed;
        else if(test==7) changed.sunRadius=changed.sunRadius==0?.04f:0;
        else changed.denoise=!changed.denoise;
        if(test==3 && options.light[0]==0 && options.light[2]==0) changed.light[0]=.3f;
        renderer.Configure(changed,true); Require(renderer.samples==0,"changed input failed to reset history");
        renderer.RenderTo(options.samples);
        renderer.Configure(options,true); Require(renderer.samples==0,"restored input failed to reset history");
        Require(renderer.RenderTo(options.samples)==reference,"stale history after restoring input");
        Require(renderer.gpu.allocated==allocation,"sample/configuration allocated new GPU scene resources");
    }
}
void VerifyLighting(Renderer& renderer,const Options& options,const std::vector<UINT>& reference) {
    const auto allocation=renderer.gpu.allocated;
    for(UINT test=0;test<4;++test) {
        auto changed=options;
        if(test==0) changed.ambient=options.ambient==0?.2f:0;
        else if(test==1) changed.lightIntensity=options.lightIntensity==0?1.f:0;
        else { changed.lightColor[0]=options.lightColor[0]<.5f?.8f:.2f; changed.lightColor[1]=.3f; changed.lightColor[2]=.4f; }
        // No forced reset: exercise the actual scalar/extended-constant history key.
        renderer.Configure(changed); Require(renderer.samples==0 && !renderer.temporalValid,"lighting change reused stale history");
        renderer.RenderTo(options.samples);
        renderer.Configure(changed); Require(renderer.samples==options.samples,"unchanged lighting discarded history");
        if(test==2) {
            auto recolored=changed; recolored.lightColor[0]=.7f;
            renderer.Configure(recolored); Require(renderer.samples==0 && !renderer.temporalValid,"same-flag colour change reused history");
            renderer.RenderTo(options.samples);
        }
        renderer.Configure(options); Require(renderer.samples==0 && !renderer.temporalValid,"restored lighting reused stale history");
        Require(renderer.RenderTo(options.samples)==reference,"lighting restoration changed output");
        Require(renderer.gpu.allocated==allocation,"lighting changes allocated GPU resources");
    }
}
}
int wmain(int argc,wchar_t** argv) {
    try {
        Options options;
        for(int i=1;i<argc;++i) {
            std::wstring arg=argv[i];
            if(arg==L"--help") std::puts("Optional: --rr-inputs NEW_FILE (128x96 or 256x192 headless GI only; fresh linear input diagnostics, not RR rendering)");
            if(arg==L"--help") std::puts("Recording: --rr-record NEW_FILE --samples 2..8 [--rr-step X Y Z] [--rr-reset-frame 1..7]; unfiltered headless GI, no SDK dispatch");
            if(arg==L"--help") std::puts("Radiance Cache paths: --rc-paths NEW_FILE (128x96 headless legacy-diffuse GI; offline secondary-hit fixture, no cache dispatch)");
            if(arg==L"--help") std::puts("Radiance Cache stream: --rc-stream (writes exactly one binary RCRPATH1 artifact to stdout; no JSON or files)");
            if(arg==L"--help") std::puts("Radiance Cache direct: --rc-shared-probe ABSOLUTE_RRT_RC_PROBE --rc-sdk-bin ABSOLUTE_SIGNEDBIN [--rc-present-candidate|--rc-presentation-test|--rc-live-session-test] [--rc-training-batches 1|2] [--rc-persistent-epochs 1|2] [--rc-budget-mib 1..256] [--rc-worker-timeout-ms 1..60000]");
            if(arg==L"--help") { std::puts("rrt_dxr [SCENE] [--probe] [--adapter N] [--mode albedo|normals|relit|gi] [--samples 1..4096] [--seed N] [--sun-radius 0..1] [--no-shadows] [--denoise] [--temporal] [--materials FILE.rrmat] [--light X Y Z] [--light-color R G B] [--light-intensity 0..32] [--ambient 0..32] [--camera-offset X Y Z] [--yaw DEG] [--pitch DEG] [--pixels NEW_FILE] [--signals NEW_FILE] [--show|--interactive] [--gdi|--no-frame-pacing] [--budget-test] [--history-test|--lighting-test|--window-test|--presentation-test|--async-test|--async-close-test|--pacing-test|--motion-test|--temporal-test move|light|cut|reset] [--debug]"); return 0; }
            if(arg==L"--probe") options.probe=true;
            else if(arg==L"--debug") options.debug=true;
            else if(arg==L"--show") options.show=true;
            else if(arg==L"--gdi") options.gdi=true;
            else if(arg==L"--presentation-test") { options.presentationTest=true; options.windowTest=true; options.interactive=true; }
            else if(arg==L"--async-test") { options.asyncTest=true; options.presentationTest=true; options.windowTest=true; options.interactive=true; }
            else if(arg==L"--async-close-test") { options.asyncCloseTest=true; options.interactive=true; }
            else if(arg==L"--no-frame-pacing") options.noFramePacing=true;
            else if(arg==L"--pacing-test") { options.pacingTest=true; options.asyncCloseTest=true; options.interactive=true; }
            else if(arg==L"--interactive") options.interactive=true;
            else if(arg==L"--history-test") options.historyTest=true;
            else if(arg==L"--budget-test") options.budgetTest=true;
            else if(arg==L"--lighting-test") options.lightingTest=true;
            else if(arg==L"--motion-test") options.motionTest=true;
            else if(arg==L"--denoise") options.denoise=true;
            else if(arg==L"--variance-filter") { options.varianceFilter=true; options.denoise=true; }
            else if(arg==L"--temporal") options.temporal=true;
            else if(arg==L"--temporal-test" && i+1<argc) { options.temporalTest=argv[++i]; Require(options.temporalTest==L"move" || options.temporalTest==L"light" || options.temporalTest==L"cut" || options.temporalTest==L"reset","invalid temporal diagnostic"); }
            else if(arg==L"--window-test") { options.windowTest=true; options.interactive=true; }
            else if(arg==L"--no-shadows") options.shadows=false;
            else if(arg==L"--pixels" && i+1<argc) { options.pixels=argv[++i]; Require(!options.pixels.empty(),"empty pixel output path"); }
            else if(arg==L"--signals" && i+1<argc) { options.signals=argv[++i]; Require(!options.signals.empty(),"empty signal output path"); }
            else if(arg==L"--rr-inputs" && i+1<argc) { options.rrInputs=argv[++i]; Require(!options.rrInputs.empty(),"empty RR input output path"); }
            else if(arg==L"--rc-paths" && i+1<argc) { options.rcPaths=argv[++i]; Require(!options.rcPaths.empty(),"empty RC path output path"); }
            else if(arg==L"--rc-stream") options.rcStream=true;
            else if(arg==L"--rc-present-candidate") options.rcPresentCandidate=true;
            else if(arg==L"--rc-presentation-test") { options.rcPresentationTest=true; options.rcPresentCandidate=true; }
            else if(arg==L"--rc-live-session-test") options.rcLiveSessionTest=true;
            else if(arg==L"--rc-renderer-session-test") options.rcRendererSessionTest=true;
            else if(arg==L"--rc-resource-test") options.rcResourceTest=true;
            else if(arg==L"--rc-pool-test") { options.rcResourceTest=true; options.rcPoolTest=true; }
            else if(arg==L"--rc-gpu-pool-test") { options.rcResourceTest=true; options.rcPoolTest=true; options.rcGpuPoolTest=true; }
            else if(arg==L"--rc-scheduler-test"&&i+1<argc) {
                options.rcSchedulerTest=argv[++i]; Require(options.rcSchedulerTest==L"close"||options.rcSchedulerTest==L"close-admission"||options.rcSchedulerTest==L"camera","RC scheduler test must be close, close-admission or camera");
                options.rcPresentationTest=true; options.rcPresentCandidate=true;
            }
            else if(arg==L"--rc-shared-probe"&&i+1<argc&&options.rcProbe.empty()) options.rcProbe=argv[++i];
            else if(arg==L"--rc-sdk-bin"&&i+1<argc&&options.rcSdkBin.empty()) options.rcSdkBin=argv[++i];
            else if((arg==L"--rc-training-batches"||arg==L"--rc-persistent-epochs"||arg==L"--rc-budget-mib"||arg==L"--rc-worker-timeout-ms")&&i+1<argc) { const wchar_t* value=argv[++i]; wchar_t* end{}; const auto n=wcstoul(value,&end,10); Require(end!=value&&!*end,"invalid RC direct unsigned option");
                if(arg==L"--rc-training-batches") { Require(n>=1&&n<=2,"RC direct training batches must be 1 or 2"); options.rcTrainingBatches=n; }
                else if(arg==L"--rc-persistent-epochs") { Require(n>=1&&n<=2,"RC direct persistent epochs must be 1 or 2"); options.rcPersistentEpochs=n; }
                else if(arg==L"--rc-budget-mib") { Require(n>=1&&n<=256,"RC direct budget must be 1..256 MiB"); options.rcBudgetMiB=n; }
                else { Require(n>=1&&n<=60000,"RC direct worker timeout must be 1..60000 ms"); options.rcWorkerTimeoutMs=n; } }
            else if(arg==L"--rr-record" && i+1<argc && options.rrRecord.empty()) { options.rrRecord=argv[++i]; Require(!options.rrRecord.empty(),"empty RR recording path"); }
            else if(arg==L"--rr-step" && i+3<argc && !options.rrStepSet) {
                options.rrStepSet=true;
                for(float& value:options.rrStep) { const wchar_t* p=argv[++i]; wchar_t* end{}; value=wcstof(p,&end); Require(end!=p&&!*end&&std::isfinite(value)&&std::abs(value)<=2,"RR step must be finite in -2..2"); }
            }
            else if(arg==L"--rr-reset-frame" && i+1<argc && options.rrResetFrame==UINT32_MAX) {
                const std::wstring value=argv[++i]; Require(value.size()==1&&value[0]>=L'1'&&value[0]<=L'7',"RR reset frame must be 1..7"); options.rrResetFrame=UINT(value[0]-L'0');
            }
            else if(arg==L"--shader" && i+1<argc) options.shader=argv[++i];
            else if(arg==L"--materials" && i+1<argc) { options.materialPath=argv[++i]; Require(!options.materialPath.empty(),"empty material path"); }
            else if((arg==L"--light-intensity" || arg==L"--ambient") && i+1<argc) {
                const wchar_t* value=argv[++i]; wchar_t* end{}; const float f=wcstof(value,&end);
                Require(end!=value && *end==0 && std::isfinite(f) && f>=0 && f<=32,"lighting scalar must be finite in 0..32");
                if(arg==L"--ambient") options.ambient=f; else options.lightIntensity=f;
            }
            else if(arg==L"--light-color" && i+3<argc) { for(auto& f:options.lightColor) { const wchar_t* value=argv[++i]; wchar_t* end{}; f=wcstof(value,&end); Require(end!=value && *end==0 && std::isfinite(f) && f>=0 && f<=1,"light colour must be finite in 0..1"); } }
            else if((arg==L"--samples" || arg==L"--seed") && i+1<argc) {
                const std::wstring value=argv[++i]; wchar_t* end{}; const auto n=wcstoull(value.c_str(),&end,10);
                Require(!value.empty() && value[0]!=L'-' && *end==0 && n<=0xffffffffull,"invalid unsigned count");
                if(arg==L"--samples") { Require(n>0 && n<=4096,"samples must be 1..4096"); options.samples=UINT(n); } else options.seed=UINT(n);
            }
            else if((arg==L"--yaw" || arg==L"--pitch" || arg==L"--sun-radius") && i+1<argc) {
                const wchar_t* value=argv[++i]; wchar_t* end{}; const float f=wcstof(value,&end);
                Require(end!=value && *end==0 && std::isfinite(f),"invalid float argument");
                if(arg==L"--sun-radius") { Require(f>=0 && f<=1,"sun radius must be 0..1"); options.sunRadius=f; }
                else if(arg==L"--yaw") { Require(std::abs(f)<=360,"yaw must be -360..360"); options.yaw=f; }
                else { Require(std::abs(f)<=89,"pitch must be -89..89"); options.pitch=f; }
            }
            else if(arg==L"--camera-offset" && i+3<argc) { for(auto& f:options.offset) { const wchar_t* value=argv[++i]; wchar_t* end{}; f=wcstof(value,&end); Require(end!=value && *end==0 && std::isfinite(f) && std::abs(f)<1e5,"invalid camera offset"); } }
            else if(arg==L"--adapter" && i+1<argc) { const wchar_t* value=argv[++i]; wchar_t* end{}; auto n=wcstoul(value,&end,10); Require(end!=value && *end==0 && n<32,"invalid adapter index"); options.adapter=n; }
            else if(arg==L"--light" && i+3<argc) { for(auto& f:options.light) { const wchar_t* value=argv[++i]; wchar_t* end{}; f=wcstof(value,&end); Require(end!=value && *end==0 && std::isfinite(f) && std::abs(f)<1000,"invalid light direction"); } }
            else if(arg==L"--mode" && i+1<argc) { std::wstring mode=argv[++i]; Require(mode==L"albedo"||mode==L"normals"||mode==L"relit"||mode==L"gi","invalid mode"); options.mode=mode==L"albedo"?0:mode==L"normals"?1:mode==L"relit"?2:3; }
            else if(options.scene.empty() && !arg.starts_with(L"--")) options.scene=arg;
            else throw std::runtime_error("invalid arguments; use --help");
        }
        Require(options.light[0]*options.light[0]+options.light[1]*options.light[1]+options.light[2]*options.light[2]>1e-12f,"zero light direction");
        if(options.probe) { Device gpu(options); gpu.Probe(options.adapter); return 0; }
        // Deterministic negative control for the memory guard. Now that the limit
        // covers the whole expressible resolution range, no valid scene can reach
        // it, so this proves the guard is still armed rather than bypassed -- and
        // that a refused allocation charges nothing against the running total.
        if(options.budgetTest) {
            Device gpu(options); const auto before=gpu.allocated; bool refused=false;
            try { gpu.Buffer(gpu.requestedLimit+1,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS); }
            catch(const std::exception& error) { refused=std::string(error.what())=="GPU allocation budget exceeded"; }
            Require(refused,"budget test did not refuse an over-limit allocation");
            Require(gpu.allocated==before,"budget test charged a refused allocation");
            std::printf("{\"budget_test\":\"refused\",\"requested_buffer_limit_bytes\":%llu,\"refused_request_bytes\":%llu,\"allocated_before_bytes\":%llu,\"allocated_bytes\":%llu}\n",
                static_cast<unsigned long long>(gpu.requestedLimit),static_cast<unsigned long long>(gpu.requestedLimit+1),
                static_cast<unsigned long long>(before),static_cast<unsigned long long>(gpu.allocated));
            return 0;
        }
        Require(!options.scene.empty(),"scene path required"); rrt::scene::Hash sceneDigest{}; auto scene=rrt::scene::Load(options.scene,&sceneDigest); Admit(scene);
        Require(!options.rrRecord.empty() || (!options.rrStepSet&&options.rrResetFrame==UINT32_MAX),"RR trajectory options require --rr-record");
        if(!options.rrRecord.empty()) {
            Require(((scene.width==128&&scene.height==96)||(scene.width==256&&scene.height==192))&&options.mode==3&&options.samples>=2&&options.samples<=8&&options.rrInputs.empty()&&options.shader.empty()&&!options.temporal&&!options.denoise&&!options.interactive&&!options.show&&!options.historyTest&&!options.lightingTest&&!options.motionTest&&options.temporalTest.empty(),"RR recording requires 128x96 or 256x192 headless unfiltered GI, 2..8 frames and no other diagnostics");
            Require(options.rrResetFrame==UINT32_MAX||options.rrResetFrame<options.samples,"RR reset index outside recording");
            AdmitRrCamera(scene);
            for(const auto& path:{options.pixels,options.signals}) if(!path.empty()) Require(_wcsicmp(std::filesystem::absolute(path).lexically_normal().c_str(),std::filesystem::absolute(options.rrRecord).lexically_normal().c_str())!=0,"RR recording output collision");
            Require(!std::filesystem::exists(options.rrRecord),"RR recording output exists");
        }
        Require(!options.historyTest || (!options.interactive && !options.show),"history-test is headless only");
        Require(!options.lightingTest || (options.mode==3 && options.temporal && options.samples>=2 && !options.historyTest && !options.interactive && !options.show && !options.motionTest && options.temporalTest.empty()),"lighting-test requires temporal GI, at least two samples and no other diagnostics/window");
        Require(!options.gdi || options.interactive || options.show,"--gdi requires a window");
        Require(!options.presentationTest || !options.gdi,"presentation-test requires native D3D12 display");
        Require(!options.asyncTest || options.samples>=4,"async-test requires at least four target samples");
        Require(!options.noFramePacing || ((options.interactive || options.show) && !options.gdi),"no-frame-pacing requires native display");
        Require(!options.pacingTest || !options.noFramePacing,"pacing-test requires frame pacing");
        Require(!options.asyncCloseTest || (options.samples>=8 && !options.gdi && !options.windowTest && !options.historyTest && !options.show),"async-close-test requires at least eight target samples and no other window/diagnostic options");
        Require(!options.windowTest || (options.yaw==0 && options.pitch==0 && options.offset[0]==0 && options.offset[1]==0 && options.offset[2]==0),"window-test requires the original captured camera");
        Require(!options.motionTest || (!options.signals.empty() && options.samples==1 && !options.interactive && !options.show && !options.historyTest),"motion-test requires --signals, one sample and no other diagnostics/window");
        Require(options.temporalTest.empty() || (options.temporal && options.mode==3 && !options.signals.empty() && !options.interactive && !options.show && !options.historyTest && !options.motionTest),"temporal-test requires --temporal, GI, --signals and no other diagnostics/window");
        Require(options.rrInputs.empty() || (((scene.width==128&&scene.height==96)||(scene.width==256&&scene.height==192)) && options.mode==3 && !options.interactive && !options.show && !options.historyTest && !options.lightingTest && options.shader.empty()),"RR input preparation requires 128x96 or 256x192 headless GI and matching built-in shaders; no history/lighting diagnostics");
        const bool rcDirect=!options.rcProbe.empty()||!options.rcSdkBin.empty(); const bool rcRequested=!options.rcPaths.empty()||options.rcStream||rcDirect;
        Require(!options.rcPresentCandidate||rcDirect,"RC candidate presentation requires RC direct mode");
        Require(!options.rcPresentationTest||rcDirect,"RC native presentation test requires RC direct mode");
        Require(!options.rcRendererSessionTest||(rcDirect&&!options.rcPresentationTest&&!options.rcLiveSessionTest&&!options.rcResourceTest&&!options.rcPresentCandidate&&options.rcPersistentEpochs==1),"RC renderer session test requires direct diagnostic mode and default epochs, without other RC tests");
        Require(!options.rcResourceTest||(rcDirect&&!options.rcPresentationTest&&!options.rcLiveSessionTest&&options.rcPersistentEpochs==1&&options.rcBudgetMiB==32),"RC resource test requires direct mode with default epochs and budget, without presentation/live tests");
        Require(!options.rcLiveSessionTest||(rcDirect&&options.rcPersistentEpochs==1),"RC live session test requires RC direct mode and default persistent epochs");
        Require(!rcDirect||(sizeof(void*)==8&&options.rcProbe.is_absolute()&&std::filesystem::is_regular_file(options.rcProbe)&&options.rcSdkBin.is_absolute()&&std::filesystem::is_directory(options.rcSdkBin)),"RC direct requires absolute x64 probe and SDK directories");
        Require(!rcRequested || (scene.width==128&&scene.height==96&&options.mode==3&&options.samples==1&&!options.interactive&&!options.show&&!options.historyTest&&!options.lightingTest&&!options.motionTest&&options.temporalTest.empty()&&!options.temporal&&!options.denoise&&options.shader.empty()&&options.materialPath.empty()),"RC path export requires one-sample 128x96 headless unfiltered legacy-diffuse GI and built-in shaders");
        Require(!options.rcStream || (options.rcPaths.empty()&&options.pixels.empty()&&options.signals.empty()&&options.rrInputs.empty()&&options.rrRecord.empty()),"RC stream is exclusive with file outputs and recordings");
        Require(!rcDirect||(options.rcPaths.empty()&&!options.rcStream&&options.pixels.empty()&&options.signals.empty()&&options.rrInputs.empty()&&options.rrRecord.empty()),"RC direct is exclusive with file outputs and recordings");
        if(!options.rrInputs.empty()) AdmitRrCamera(scene);
        for(const auto& path:{options.pixels,options.signals,options.rrInputs,options.rcPaths}) if(!path.empty()) Require(!std::filesystem::exists(path),"output already exists");
        if(!options.rrInputs.empty()) for(const auto& path:{options.pixels,options.signals}) if(!path.empty()) Require(_wcsicmp(std::filesystem::absolute(path).lexically_normal().c_str(),std::filesystem::absolute(options.rrInputs).lexically_normal().c_str())!=0,"RR input output must differ from other outputs");
        if(!options.pixels.empty() && !options.signals.empty()) Require(_wcsicmp(std::filesystem::absolute(options.pixels).lexically_normal().c_str(),std::filesystem::absolute(options.signals).lexically_normal().c_str())!=0,"pixel and signal outputs must differ");
        if(!options.rcPaths.empty()) for(const auto& path:{options.pixels,options.signals,options.rrInputs}) if(!path.empty()) Require(_wcsicmp(std::filesystem::absolute(path).lexically_normal().c_str(),std::filesystem::absolute(options.rcPaths).lexically_normal().c_str())!=0,"RC path output must differ from other outputs");
        Device gpu(options); auto start=std::chrono::steady_clock::now(); Renderer renderer(gpu,scene,options);
        const bool readPixels=!(options.interactive||options.show) || options.gdi || (options.windowTest&&!options.asyncTest);
        // Native interactive work starts only after display admission, including sample one.
        const UINT initialSamples=options.interactive?(!options.gdi && !options.windowTest?0u:1u):options.samples;
        std::vector<std::uint8_t> recording;
        auto pixels=!options.rrRecord.empty()?RecordRr(renderer,options,sceneDigest,recording):initialSamples?renderer.RenderTo(initialSamples,readPixels):std::vector<UINT>{};
        if(options.historyTest) VerifyHistory(renderer,options,pixels);
        if(options.lightingTest) VerifyLighting(renderer,options,pixels);
        if(options.motionTest) { options.offset[0]+=.1f; options.offset[1]+=.1f; renderer.Configure(options); pixels=renderer.RenderTo(1); }
        if(!options.temporalTest.empty()) {
            if(options.temporalTest==L"move") { options.offset[0]+=.1f; options.offset[1]+=.1f; }
            else if(options.temporalTest==L"light") { options.light[0]=.7f; options.light[1]=.2f; options.light[2]=-.5f; }
            else if(options.temporalTest==L"cut") options.offset[0]+=1.1f;
            else ++options.cutSerial;
            renderer.Configure(options,options.temporalTest==L"light"); pixels=renderer.RenderTo(1);
        }
        if(options.interactive || options.show) Show(pixels,renderer,options);
        renderer.Drain();
        if(!readPixels) pixels=renderer.Snapshot();
        auto end=std::chrono::steady_clock::now(); Save(options.pixels,pixels); renderer.SaveSignals(options.signals);
        if(options.rcStream) {
            auto result=PrepareRcPaths(renderer,sceneDigest); Require(_setmode(_fileno(stdout),_O_BINARY)!=-1,"RC stream binary mode failed");
            Require(std::fwrite(result.bytes.data(),1,result.bytes.size(),stdout)==result.bytes.size()&&std::fflush(stdout)==0,"RC stream write failed"); return 0;
        }
        if(rcDirect) { std::cout << (options.rcResourceTest?VerifyRcResourceLifetime(renderer,options,sceneDigest):options.rcPresentationTest?RunRcScheduledPresentation(renderer,options,sceneDigest):RunRcDirect(renderer,options,sceneDigest)) << '\n'; return 0; }
        SaveRrInputs(renderer,options);
        SaveRcPaths(renderer,options,sceneDigest);
        if(!options.rrRecord.empty()) WriteRrFile(options.rrRecord,recording);
        std::printf("{\"frame_slots\":%u,\"frame_slot_mask\":%u,\"async_submissions\":%u,\"max_inflight_submissions\":%u,\"fence_waits\":%u,\"render_readbacks\":%u,\"readback_submissions\":%u,\"timed_samples\":%u,",Device::SlotCount,gpu.slotMask,gpu.asyncSubmissions,gpu.maxInflight,gpu.fenceWaits,renderer.renderReadbacks,renderer.readbackSubmissions,renderer.timedSamples);
        std::printf("\"pbr_draws\":%u,\"material_records\":%zu,\"material_sha256\":\"%s\",\"light_color\":[%.9g,%.9g,%.9g],\"light_intensity\":%.9g,\"ambient\":%.9g,",renderer.pbrDraws,renderer.materialInputs.records.size(),renderer.materialInputs.digest.c_str(),options.lightColor[0],options.lightColor[1],options.lightColor[2],options.lightIntensity,options.ambient);
        std::printf("\"denoiser\":\"%s\",\"variance_dispatches\":%u,",options.denoise && options.mode==3?(options.varianceFilter?"variance":"spatial"):"none",renderer.varianceDispatches);
        std::printf("\"rr_input_preparations\":%u,\"rr_dispatches\":0,\"rr_input_stride\":%u,",renderer.rrInputSubmissions,options.rrInputs.empty()&&options.rrRecord.empty()?0u:96u);
        std::printf("\"rr_recorded_frames\":%u,",options.rrRecord.empty()?0u:options.samples);
        std::printf("\"rc_path_exports\":%u,\"rc_path_stride\":%u,\"rc_path_queries\":%u,\"rc_path_training\":%u,",renderer.rcPathSubmissions,options.rcPaths.empty()?0u:128u,renderer.rcPathQueries,renderer.rcPathTraining);
        std::printf("\"maximum_frame_latency\":%u,\"pacing_waits\":%u,\"pacing_ready\":%u,\"pacing_messages\":%u,\"pacing_timeouts\":%u,\"pacing_test_mask\":%u,\"pacing_wait_ms\":%.3f,",renderer.frameLatency,renderer.pacingWaits,renderer.pacingReady,renderer.pacingMessages,renderer.pacingTimeouts,renderer.pacingTestMask,renderer.pacingWaitMs);
        std::printf("\"presentation\":\"%s\",\"display_submissions\":%u,\"display_resizes\":%u,\"display_verified\":%u,\"display_presented\":%u,\"display_occluded\":%u,\"display_buffer_mask\":%u,\"display_suspended_ticks\":%u,\"display_rejected_resizes\":%u,\"peak_requested_bytes\":%llu,",
            options.interactive||options.show?(options.gdi?"gdi":"d3d12-swapchain"):"headless",renderer.displaySubmissions,renderer.displayResizes,renderer.displayVerified,renderer.displayPresented,renderer.displayOccluded,renderer.displayMask,renderer.displaySuspended,renderer.displayRejected,gpu.peakRequested);
        std::printf("\"renderer\":\"dxr-inline-1.1\",\"adapter\":\"%s\",\"mode\":%u,\"draws\":%zu,\"width\":%u,\"height\":%u,\"samples\":%u,\"dispatches\":%u,\"history_resets\":%u,\"scene_build_submissions\":%llu,\"history_test\":%s,\"denoised\":%s,\"temporal\":%s,\"temporal_resets\":%u,\"signal_stride\":%zu,\"working_stride\":%zu,\"temporal_stride\":%zu,\"export_chunk_pixels\":%u,\"export_submissions\":%u,\"requested_buffer_bytes\":%llu,\"requested_buffer_limit_bytes\":%llu,\"build_render_readback_ms\":%.3f,\"gpu_build_ms\":%.6f,\"gpu_trace_ms\":%.6f,\"gpu_temporal_ms\":%.6f,\"gpu_filter_ms\":%.6f,\"gpu_copy_ms\":%.6f,\"gpu_export_ms\":%.6f,\"signal_export_ms\":%.3f,\"pixel_sha256_bgra\":\"%s\"}\n",
            JsonName(gpu.desc.Description).c_str(),options.mode,scene.draws.size(),scene.width,scene.height,renderer.samples,renderer.dispatches,renderer.resets,gpu.sequence-renderer.dispatches-renderer.exportSubmissions-renderer.displaySubmissions-renderer.readbackSubmissions,options.historyTest?"true":"false",options.denoise && options.mode==3?"true":"false",options.temporal && options.mode==3?"true":"false",renderer.temporalResets,sizeof(Signal),sizeof(WorkingSignal),sizeof(TemporalRecord),ExportChunkPixels,renderer.exportSubmissions,gpu.allocated,gpu.requestedLimit,std::chrono::duration<double,std::milli>(end-start).count(),gpu.buildMs,gpu.traceMs,gpu.temporalMs,gpu.filterMs,gpu.copyMs,gpu.exportMs,renderer.exportWallMs,rrt::scene::Hex(rrt::scene::Digest(pixels.data(),pixels.size()*4)).c_str());
        return 0;
    } catch(const std::exception& error) { std::fprintf(stderr,"%s\n",error.what()); return 2; }
}
