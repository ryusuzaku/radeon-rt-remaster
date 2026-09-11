// Same-adapter cross-process D3D12 shared-buffer/fence integrity contract.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
namespace {
constexpr uint64_t SharedBytes=1573120;
void Require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
std::string QuoteBytes(const std::string& value) { std::ostringstream out; out << '"'; for(unsigned char c:value) { if(c=='"'||c=='\\') out << '\\' << c; else if(c=='\r') out << "\\r"; else if(c=='\n') out << "\\n"; else if(c>=32) out << c; } out << '"'; return out.str(); }
std::string Quote(const char* value) { return QuoteBytes(value?value:""); }
#include "rc_isolation.h"

uint64_t Parse64(const wchar_t* text) { wchar_t* end{}; const auto value=wcstoull(text,&end,10); Require(text&&*text&&end&&!*end,"invalid shared handle value"); return value; }
uint64_t Hash(const void* data,size_t size) { uint64_t hash=14695981039346656037ull; const auto* bytes=static_cast<const unsigned char*>(data); for(size_t i=0;i<size;++i) { hash^=bytes[i]; hash*=1099511628211ull; } return hash; }
std::vector<unsigned char> Payload() { std::vector<unsigned char> bytes(SharedBytes); for(size_t i=0;i<bytes.size();++i) bytes[i]=unsigned char((i*131u+(i>>8)*17u+0x5au)&255); return bytes; }

struct Gpu {
    ComPtr<IDXGIFactory6> factory; ComPtr<IDXGIAdapter1> adapter; ComPtr<ID3D12Device> device; LUID luid{};
    explicit Gpu(UINT index) { Require(SUCCEEDED(CreateDXGIFactory2(0,IID_PPV_ARGS(&factory))),"shared factory failed"); Require(SUCCEEDED(factory->EnumAdapters1(index,&adapter)),"shared adapter unavailable");
        DXGI_ADAPTER_DESC1 desc{}; Require(SUCCEEDED(adapter->GetDesc1(&desc))&&!(desc.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"shared adapter invalid"); luid=desc.AdapterLuid;
        Require(SUCCEEDED(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device))),"shared device failed"); }
};
ComPtr<ID3D12CommandQueue> Queue(ID3D12Device* device) { D3D12_COMMAND_QUEUE_DESC desc{}; desc.Type=D3D12_COMMAND_LIST_TYPE_DIRECT; ComPtr<ID3D12CommandQueue> queue;
    Require(SUCCEEDED(device->CreateCommandQueue(&desc,IID_PPV_ARGS(&queue))),"shared queue failed"); return queue; }
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device,D3D12_HEAP_TYPE type,D3D12_HEAP_FLAGS flags,D3D12_RESOURCE_STATES state) {
    D3D12_HEAP_PROPERTIES heap{}; heap.Type=type; D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER; desc.Width=SharedBytes; desc.Height=1; desc.DepthOrArraySize=1;
    desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; ComPtr<ID3D12Resource> resource;
    Require(SUCCEEDED(device->CreateCommittedResource(&heap,flags,&desc,state,nullptr,IID_PPV_ARGS(&resource))),"shared buffer creation failed"); return resource;
}
ComPtr<ID3D12Resource> BufferSized(ID3D12Device* device,uint64_t bytes,D3D12_HEAP_TYPE type,D3D12_HEAP_FLAGS heapFlags,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS resourceFlags=D3D12_RESOURCE_FLAG_NONE) {
    Require(bytes&&bytes<=UINT32_MAX,"shared sized buffer extent invalid"); D3D12_HEAP_PROPERTIES heap{}; heap.Type=type; D3D12_RESOURCE_DESC desc{}; desc.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width=bytes; desc.Height=1; desc.DepthOrArraySize=1; desc.MipLevels=1; desc.SampleDesc.Count=1; desc.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR; desc.Flags=resourceFlags;
    ComPtr<ID3D12Resource> resource; Require(SUCCEEDED(device->CreateCommittedResource(&heap,heapFlags,&desc,state,nullptr,IID_PPV_ARGS(&resource))),"shared sized buffer creation failed"); return resource;
}
void Transition(ID3D12GraphicsCommandList* list,ID3D12Resource* resource,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after) { D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition={resource,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,before,after}; list->ResourceBarrier(1,&barrier); }
void Wait(ID3D12Fence* fence,uint64_t value) { if(fence->GetCompletedValue()>=value) return; RcHandle event; event.value=CreateEventW(nullptr,FALSE,FALSE,nullptr); Require(event.value&&SUCCEEDED(fence->SetEventOnCompletion(value,event.value)),"shared fence event failed"); Require(WaitForSingleObject(event.value,30000)==WAIT_OBJECT_0,"shared fence timeout"); }

int Child(UINT adapterIndex,HANDLE inputHandle,HANDLE outputHandle,HANDLE fenceHandle,LUID expected) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX); Gpu gpu(adapterIndex);
    Require(gpu.luid.LowPart==expected.LowPart&&gpu.luid.HighPart==expected.HighPart,"shared child adapter LUID mismatch");
    ComPtr<ID3D12Resource> input,output; ComPtr<ID3D12Fence> fence;
    Require(SUCCEEDED(gpu.device->OpenSharedHandle(inputHandle,IID_PPV_ARGS(&input)))&&SUCCEEDED(gpu.device->OpenSharedHandle(outputHandle,IID_PPV_ARGS(&output)))
        &&SUCCEEDED(gpu.device->OpenSharedHandle(fenceHandle,IID_PPV_ARGS(&fence))),"shared child open failed");
    Require(input->GetDesc().Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&input->GetDesc().Width==SharedBytes&&output->GetDesc().Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&output->GetDesc().Width==SharedBytes,"shared child resource description mismatch");
    auto queue=Queue(gpu.device.Get()); Require(SUCCEEDED(queue->Wait(fence.Get(),1)),"shared child queue wait failed"); ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
    Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"shared child command list failed");
    list->CopyResource(output.Get(),input.Get()); Require(SUCCEEDED(list->Close()),"shared child close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists);
    Require(SUCCEEDED(queue->Signal(fence.Get(),2)),"shared child signal failed"); Wait(fence.Get(),2);
    std::cout << "{\"shared_child\":true,\"bytes\":" << SharedBytes << ",\"fence_value\":2}"; return 0;
}

constexpr uint64_t CacheSizes[5]={540672,147456,22528,6144,8};
constexpr uint32_t CacheStrides[5]={44,12,44,12,4};
std::vector<unsigned char> CachePattern(UINT slot,bool childWrite=false) {
    std::vector<unsigned char> bytes(static_cast<size_t>(CacheSizes[slot]));
    for(size_t i=0;i<bytes.size();++i) bytes[i]=static_cast<unsigned char>(((i+1)*(slot*29u+17u)+(i>>5)*11u+(childWrite?0xa7u:0x31u))&255);
    if(childWrite&&slot==4) std::fill(bytes.begin(),bytes.end(),0); return bytes;
}
int CacheChild(UINT adapterIndex,const std::array<HANDLE,5>& resourceHandles,HANDLE fenceHandle,LUID expected) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX); Gpu gpu(adapterIndex);
    Require(gpu.luid.LowPart==expected.LowPart&&gpu.luid.HighPart==expected.HighPart,"cache shared child adapter LUID mismatch");
    std::array<ComPtr<ID3D12Resource>,5> resources; ComPtr<ID3D12Fence> fence;
    for(UINT i=0;i<5;++i) { Require(SUCCEEDED(gpu.device->OpenSharedHandle(resourceHandles[i],IID_PPV_ARGS(&resources[i]))),"cache shared resource open failed"); const auto desc=resources[i]->GetDesc();
        Require(desc.Dimension==D3D12_RESOURCE_DIMENSION_BUFFER&&desc.Width==CacheSizes[i]&&(desc.Flags&D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS),"cache shared resource description mismatch"); }
    Require(SUCCEEDED(gpu.device->OpenSharedHandle(fenceHandle,IID_PPV_ARGS(&fence))),"cache shared fence open failed"); auto queue=Queue(gpu.device.Get()); Require(SUCCEEDED(queue->Wait(fence.Get(),10)),"cache shared child wait failed");
    const auto outputBytes=CachePattern(1,true),counterBytes=CachePattern(4,true); auto outputUpload=BufferSized(gpu.device.Get(),CacheSizes[1],D3D12_HEAP_TYPE_UPLOAD,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_GENERIC_READ);
    auto counterUpload=BufferSized(gpu.device.Get(),CacheSizes[4],D3D12_HEAP_TYPE_UPLOAD,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_GENERIC_READ); void* mapped{}; D3D12_RANGE empty{};
    Require(SUCCEEDED(outputUpload->Map(0,&empty,&mapped))&&mapped,"cache output upload map failed"); std::memcpy(mapped,outputBytes.data(),outputBytes.size()); outputUpload->Unmap(0,nullptr);
    Require(SUCCEEDED(counterUpload->Map(0,&empty,&mapped))&&mapped,"cache counter upload map failed"); std::memcpy(mapped,counterBytes.data(),counterBytes.size()); counterUpload->Unmap(0,nullptr);
    ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list; Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))
        &&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"cache shared child command list failed");
    list->CopyResource(resources[1].Get(),outputUpload.Get()); list->CopyResource(resources[4].Get(),counterUpload.Get()); Require(SUCCEEDED(list->Close()),"cache shared child close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists);
    Require(SUCCEEDED(queue->Signal(fence.Get(),11)),"cache shared child signal failed"); Wait(fence.Get(),11); std::cout << "{\"cache_shared_child\":true,\"external_bytes\":716808,\"fence_value\":11}"; return 0;
}

int CacheParent(UINT adapterIndex) {
    Gpu gpu(adapterIndex); std::array<ComPtr<ID3D12Resource>,5> resources,uploads,readbacks; std::array<RcHandle,5> resourceHandles;
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE}; std::array<std::vector<unsigned char>,5> initial;
    for(UINT i=0;i<5;++i) { resources[i]=BufferSized(gpu.device.Get(),CacheSizes[i],D3D12_HEAP_TYPE_DEFAULT,D3D12_HEAP_FLAG_SHARED,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
        uploads[i]=BufferSized(gpu.device.Get(),CacheSizes[i],D3D12_HEAP_TYPE_UPLOAD,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_GENERIC_READ); readbacks[i]=BufferSized(gpu.device.Get(),CacheSizes[i],D3D12_HEAP_TYPE_READBACK,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_COPY_DEST);
        Require(SUCCEEDED(gpu.device->CreateSharedHandle(resources[i].Get(),&security,GENERIC_ALL,nullptr,&resourceHandles[i].value)),"cache shared handle creation failed"); initial[i]=CachePattern(i); void* mapped{}; D3D12_RANGE empty{};
        Require(SUCCEEDED(uploads[i]->Map(0,&empty,&mapped))&&mapped,"cache shared parent upload map failed"); std::memcpy(mapped,initial[i].data(),initial[i].size()); uploads[i]->Unmap(0,nullptr); }
    ComPtr<ID3D12Fence> fence; Require(SUCCEEDED(gpu.device->CreateFence(0,D3D12_FENCE_FLAG_SHARED,IID_PPV_ARGS(&fence))),"cache shared fence creation failed"); RcHandle fenceHandle;
    Require(SUCCEEDED(gpu.device->CreateSharedHandle(fence.Get(),&security,GENERIC_ALL,nullptr,&fenceHandle.value)),"cache shared fence handle failed"); auto queue=Queue(gpu.device.Get());
    ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list; Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))
        &&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"cache shared parent upload list failed");
    for(UINT i=0;i<5;++i) { list->CopyResource(resources[i].Get(),uploads[i].Get()); if(i==0||i==2||i==3) Transition(list.Get(),resources[i].Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE); }
    Require(SUCCEEDED(list->Close()),"cache shared parent upload close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists); Require(SUCCEEDED(queue->Signal(fence.Get(),10)),"cache shared parent signal failed");
    std::vector<HANDLE> handles; std::vector<std::wstring> args={L"--cache-child",std::to_wstring(adapterIndex)}; for(auto& handle:resourceHandles) { handles.push_back(handle.value); args.push_back(std::to_wstring(uintptr_t(handle.value))); }
    handles.push_back(fenceHandle.value); args.push_back(std::to_wstring(uintptr_t(fenceHandle.value))); args.push_back(std::to_wstring(gpu.luid.LowPart)); args.push_back(std::to_wstring(uint32_t(gpu.luid.HighPart)));
    const auto child=RcRunIsolated(args,30000,false,nullptr,&handles); Require(child.reaped&&!child.timedOut&&!child.overflow&&child.exitCode==0&&child.error.empty()
        &&child.output=="{\"cache_shared_child\":true,\"external_bytes\":716808,\"fence_value\":11}","cache shared child validation failed"); Wait(fence.Get(),11);
    allocator.Reset(); list.Reset(); Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))
        &&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"cache shared parent readback list failed");
    for(UINT i=0;i<5;++i) { Transition(list.Get(),resources[i].Get(),i==0||i==2||i==3?D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE:D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE); list->CopyResource(readbacks[i].Get(),resources[i].Get()); }
    Require(SUCCEEDED(list->Close()),"cache shared parent readback close failed"); ID3D12CommandList* reads[]={list.Get()}; queue->ExecuteCommandLists(1,reads); Require(SUCCEEDED(queue->Signal(fence.Get(),12)),"cache shared parent readback signal failed"); Wait(fence.Get(),12);
    uint64_t hashes[5]{}; for(UINT i=0;i<5;++i) { std::vector<unsigned char> actual(static_cast<size_t>(CacheSizes[i])); void* mapped{}; D3D12_RANGE range{0,SIZE_T(CacheSizes[i])}; Require(SUCCEEDED(readbacks[i]->Map(0,&range,&mapped))&&mapped,"cache shared readback map failed");
        std::memcpy(actual.data(),mapped,actual.size()); D3D12_RANGE empty{}; readbacks[i]->Unmap(0,&empty); const auto expected=(i==1||i==4)?CachePattern(i,true):initial[i]; Require(actual==expected,"cache shared buffer mutation mismatch"); hashes[i]=Hash(actual.data(),actual.size()); }
    std::cout << "{\"result\":\"cache-shared-layout-pass\",\"external_buffer_bytes\":716808,\"sizes\":[540672,147456,22528,6144,8],\"strides\":[44,12,44,12,4],\"hashes_fnv1a64\":[";
    for(UINT i=0;i<5;++i) { if(i) std::cout << ','; std::cout << hashes[i]; } std::cout << "],\"immutable_buffers\":[0,2,3],\"writable_buffers\":[1,4],\"counters_cleared\":true,\"shared_resources\":5,\"shared_fences\":1,\"allowlisted_handles\":6,\"fence_values\":[10,11,12],\"child_reaped\":true,\"cpu_payload_transfer_bytes\":0}" << '\n'; return 0;
}

int Parent(UINT adapterIndex) {
    Gpu gpu(adapterIndex); auto input=Buffer(gpu.device.Get(),D3D12_HEAP_TYPE_DEFAULT,D3D12_HEAP_FLAG_SHARED,D3D12_RESOURCE_STATE_COPY_DEST);
    auto output=Buffer(gpu.device.Get(),D3D12_HEAP_TYPE_DEFAULT,D3D12_HEAP_FLAG_SHARED,D3D12_RESOURCE_STATE_COPY_DEST);
    auto upload=Buffer(gpu.device.Get(),D3D12_HEAP_TYPE_UPLOAD,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_GENERIC_READ); auto readback=Buffer(gpu.device.Get(),D3D12_HEAP_TYPE_READBACK,D3D12_HEAP_FLAG_NONE,D3D12_RESOURCE_STATE_COPY_DEST);
    ComPtr<ID3D12Fence> fence; Require(SUCCEEDED(gpu.device->CreateFence(0,D3D12_FENCE_FLAG_SHARED,IID_PPV_ARGS(&fence))),"shared fence creation failed");
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE}; RcHandle inputHandle,outputHandle,fenceHandle;
    Require(SUCCEEDED(gpu.device->CreateSharedHandle(input.Get(),&security,GENERIC_ALL,nullptr,&inputHandle.value))&&SUCCEEDED(gpu.device->CreateSharedHandle(output.Get(),&security,GENERIC_ALL,nullptr,&outputHandle.value))
        &&SUCCEEDED(gpu.device->CreateSharedHandle(fence.Get(),&security,GENERIC_ALL,nullptr,&fenceHandle.value)),"shared handle creation failed");
    const auto expected=Payload(); void* mapped{}; D3D12_RANGE empty{}; Require(SUCCEEDED(upload->Map(0,&empty,&mapped))&&mapped,"shared upload map failed"); std::memcpy(mapped,expected.data(),expected.size()); upload->Unmap(0,nullptr);
    auto queue=Queue(gpu.device.Get()); ComPtr<ID3D12CommandAllocator> allocator; ComPtr<ID3D12GraphicsCommandList> list;
    Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"shared parent command list failed");
    list->CopyResource(input.Get(),upload.Get()); Transition(list.Get(),input.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE); Require(SUCCEEDED(list->Close()),"shared parent upload close failed"); ID3D12CommandList* lists[]={list.Get()}; queue->ExecuteCommandLists(1,lists); Require(SUCCEEDED(queue->Signal(fence.Get(),1)),"shared parent signal failed");
    std::vector<HANDLE> handles={inputHandle.value,outputHandle.value,fenceHandle.value}; LUID luid=gpu.luid;
    const auto child=RcRunIsolated({L"--shared-child",std::to_wstring(adapterIndex),std::to_wstring(uintptr_t(inputHandle.value)),std::to_wstring(uintptr_t(outputHandle.value)),std::to_wstring(uintptr_t(fenceHandle.value)),
                                    std::to_wstring(luid.LowPart),std::to_wstring(uint32_t(luid.HighPart))},30000,false,nullptr,&handles);
    Require(child.reaped&&!child.timedOut&&!child.overflow&&child.exitCode==0&&child.error.empty()&&child.output=="{\"shared_child\":true,\"bytes\":1573120,\"fence_value\":2}","shared child validation failed");
    Wait(fence.Get(),2); allocator.Reset(); list.Reset(); Require(SUCCEEDED(gpu.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&allocator)))&&SUCCEEDED(gpu.device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator.Get(),nullptr,IID_PPV_ARGS(&list))),"shared parent readback list failed");
    Transition(list.Get(),output.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE); list->CopyResource(readback.Get(),output.Get()); Require(SUCCEEDED(list->Close()),"shared parent readback close failed"); ID3D12CommandList* readLists[]={list.Get()}; queue->ExecuteCommandLists(1,readLists); Require(SUCCEEDED(queue->Signal(fence.Get(),3)),"shared parent readback signal failed"); Wait(fence.Get(),3);
    std::vector<unsigned char> actual(SharedBytes); D3D12_RANGE range{0,SharedBytes}; Require(SUCCEEDED(readback->Map(0,&range,&mapped))&&mapped,"shared readback map failed"); std::memcpy(actual.data(),mapped,actual.size()); D3D12_RANGE noWrite{}; readback->Unmap(0,&noWrite);
    Require(actual==expected,"shared payload mismatch"); const auto hash=Hash(actual.data(),actual.size());
    std::cout << "{\"result\":\"shared-roundtrip-pass\",\"adapter_luid_low\":" << luid.LowPart << ",\"adapter_luid_high\":" << luid.HighPart
              << ",\"bytes\":" << SharedBytes << ",\"payload_hash_fnv1a64\":" << hash << ",\"shared_resources\":2,\"shared_fences\":1,\"allowlisted_handles\":3"
              << ",\"fence_values\":[1,2,3],\"child_reaped\":true,\"child_exit_code\":0,\"cpu_payload_transfer_bytes\":0}" << '\n'; return 0;
}
}

int wmain(int argc,wchar_t** argv) {
    try {
        if(argc==8&&std::wstring(argv[1])==L"--shared-child") { LUID luid{DWORD(Parse64(argv[6])),LONG(uint32_t(Parse64(argv[7])))}; return Child(UINT(Parse64(argv[2])),HANDLE(uintptr_t(Parse64(argv[3]))),HANDLE(uintptr_t(Parse64(argv[4]))),HANDLE(uintptr_t(Parse64(argv[5]))),luid); }
        if(argc==11&&std::wstring(argv[1])==L"--cache-child") { std::array<HANDLE,5> handles{}; for(UINT i=0;i<5;++i) handles[i]=HANDLE(uintptr_t(Parse64(argv[3+i]))); LUID luid{DWORD(Parse64(argv[9])),LONG(uint32_t(Parse64(argv[10])))};
            return CacheChild(UINT(Parse64(argv[2])),handles,HANDLE(uintptr_t(Parse64(argv[8]))),luid); }
        UINT adapter=0; bool cache=false; for(int i=1;i<argc;++i) { const std::wstring arg=argv[i]; if(arg==L"--cache-layout"&&!cache) cache=true; else if(arg==L"--adapter"&&i+1<argc) adapter=UINT(Parse64(argv[++i])); else throw std::runtime_error("usage: rrt_rc_shared [--adapter 0] [--cache-layout]"); }
        Require(adapter<32,"shared adapter out of range"); return cache?CacheParent(adapter):Parent(adapter);
    } catch(const std::exception& error) { std::cerr << "rrt_rc_shared: " << error.what() << '\n'; return 1; }
}
