#pragma once
#include "rc_epoch_protocol.h"

template<class Regenerate>
std::string RunRcRendererSession(Renderer& renderer,const Options& options,const std::vector<std::wstring>& args,
    const std::vector<HANDLE>& inherited,ID3D12Fence* fence,ID3D12Resource* predictions,RcTransientBuffers& buffers,Regenerate regenerate) {
    constexpr UINT Epochs=6; constexpr UINT64 OutputBytes=128*96*12;
    auto readback=buffers.Buffer(OutputBytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    const UINT64 allocated=renderer.gpu.allocated;
    RcIsolatedSession session(args,inherited,options.rcProbe.c_str());
    RcFrameAdmission admission; RcFrameAdmission::Identity base{1,1,1,1,1},latest=base;
    Options requested=options; admission.RequestFrame(base);
    std::array<RcFrameAdmission::Request,Epochs> requests{};
    std::array<uint64_t,Epochs> outputHashes{}; std::array<bool,Epochs> admitted{};
    std::array<unsigned char,OutputBytes> bytes{};
    for(UINT epoch=0;epoch<Epochs;++epoch) {
        requests[epoch]=admission.Begin();
        if(epoch) { renderer.Configure(requested,true); renderer.RenderTo(1); regenerate(renderer.frame); }
        const auto noCache=renderer.ReadPixels();
        const auto command=requests[epoch].reset?RcEpochProtocol::Reset:RcEpochProtocol::Continue;
        Check(renderer.gpu.queue->Signal(fence,RcEpochProtocol::Signal(epoch,command)),"RC renderer session command");
        if(!epoch) {
            // Queue input without touching worker-owned GPU resources. Only the
            // final request is rendered after the outstanding epoch completes.
            latest.camera=2; admission.RequestFrame(latest); requested.offset[0]=options.offset[0]+.025f;
            latest.camera=3; admission.RequestFrame(latest); requested.offset[0]=options.offset[0]+.05f;
        }
        session.WaitFence(fence,RcEpochProtocol::Ack(epoch),options.rcWorkerTimeoutMs);
        admitted[epoch]=admission.Complete(requests[epoch].serial,true);
        renderer.gpu.Begin(); D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        barrier.Transition={predictions,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE};
        renderer.gpu.list->ResourceBarrier(1,&barrier); renderer.gpu.list->CopyResource(readback.Get(),predictions);
        std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter); renderer.gpu.list->ResourceBarrier(1,&barrier); renderer.gpu.Execute();
        void* mapped{}; D3D12_RANGE range{0,SIZE_T(OutputBytes)},empty{};
        Check(readback->Map(0,&range,&mapped),"RC renderer session readback"); std::memcpy(bytes.data(),mapped,bytes.size()); readback->Unmap(0,&empty);
        uint64_t hash=14695981039346656037ull; for(auto byte:bytes) { hash^=byte; hash*=1099511628211ull; } outputHashes[epoch]=hash;
        Require(renderer.ReadPixels()==noCache,"RC renderer session changed diagnostic output");
        Require(renderer.gpu.allocated==allocated,"RC renderer session allocated per-epoch GPU resources");
        if(epoch==1) admission.RequestFrame(latest);
        if(epoch==2) { latest=base; requested=options; admission.RequestFrame(latest); }
        if(epoch==3) admission.RequestFrame(latest);
        if(epoch==4) { ++latest.settings; admission.RequestFrame(latest); }
    }
    Check(renderer.gpu.queue->Signal(fence,RcEpochProtocol::Signal(Epochs,RcEpochProtocol::Stop)),"RC renderer session stop");
    session.WaitFence(fence,RcEpochProtocol::Ack(Epochs),options.rcWorkerTimeoutMs);
    const auto child=session.Finish(options.rcWorkerTimeoutMs);
    Require(child.reaped&&!child.timedOut&&!child.overflow&&!child.exitCode&&child.error.empty(),"RC renderer session child failed");
    Require(admission.coalesced==1&&admission.discarded==1&&!admission.queued&&!admission.busy,"RC renderer session queue accounting mismatch");
    std::istringstream input(child.output); std::ostringstream records;
    std::array<uint64_t,Epochs> starts{},posts{}; UINT resets=0,accepted=0;
    for(UINT epoch=0;epoch<Epochs;++epoch) {
        std::string magic; UINT ordinal=0,command=0,count=0;
        Require(bool(input>>magic>>ordinal>>command>>count>>starts[epoch]>>posts[epoch])&&magic=="RCSESSIONEPOCH1"&&ordinal==epoch&&
            command==(requests[epoch].reset?0u:1u)&&count&&count<=128*96&&posts[epoch]==outputHashes[epoch]&&starts[epoch]!=posts[epoch],"RC renderer session epoch report mismatch");
        if(requests[epoch].reset) ++resets; else Require(epoch&&starts[epoch]==posts[epoch-1],"RC renderer session lost trained state");
        if(admitted[epoch]) ++accepted;
        if(epoch) records << ',';
        records << "{\"epoch\":" << epoch << ",\"reset\":" << (requests[epoch].reset?"true":"false") << ",\"admitted\":" << (admitted[epoch]?"true":"false")
            << ",\"query_count\":" << count << ",\"start_hash\":" << starts[epoch] << ",\"post_hash\":" << posts[epoch] << '}';
    }
    std::string magic,extra; UINT completed=0,dispatches=0;
    Require(bool(input>>magic>>completed>>dispatches)&&magic=="RCSESSIONEND1"&&completed==Epochs&&dispatches==Epochs*(2+options.rcTrainingBatches)&&!(input>>extra),"RC renderer session stop report mismatch");
    Require(starts[3]==starts[0]&&posts[3]==posts[0]&&starts[5]==starts[0]&&posts[5]==posts[0]&&starts[1]!=starts[0],"RC renderer session camera/reset mismatch");
    std::ostringstream report;
    report << "{\"result\":\"rc-renderer-session-pass\",\"provider_processes\":1,\"provider_contexts\":1,\"epochs\":" << Epochs << ",\"provider_dispatches\":" << dispatches
        << ",\"reset_epochs\":" << resets << ",\"admitted_epochs\":" << accepted << ",\"coalesced_requests\":" << admission.coalesced << ",\"discarded_epochs\":" << admission.discarded
        << ",\"pending_requests\":0,\"renderer_input_submissions\":" << Epochs << ",\"per_epoch_gpu_allocations\":0,\"shared_resources\":5,\"shared_fences\":1,\"child_reaped\":true,\"stop_acknowledged\":true"
        << ",\"candidate_applied\":false,\"authoritative_output\":\"no-cache\",\"prediction_readback_bytes\":" << Epochs*OutputBytes << ",\"records\":[" << records.str() << "]}";
    return report.str();
}
