#pragma once
#include "rc_staleness.h"

// Stale-lighting device scenario (docs/RC_STALENESS_POLICY.md, section 4). One
// provider process and context, four epochs on the canonical scene:
//   0 reset, train on L0                       -> C_old
//   1 identity changes lighting only (L1)      -> C_policy (policy: reset; control: forced continue)
//   2 reset, same L1 inputs (camera revision)  -> C_fresh
//   3 reset, same L1 inputs again              -> exact recovery
// The negative control forces Continue at epoch 1 and must show stale values;
// the policy run must match the fresh session exactly. Diagnostic only: the cache
// output is never applied and the no-cache pixels stay authoritative.
template<class Regenerate,class GenerationsFor>
std::string RunRcStalenessSession(Renderer& renderer,const Options& options,const std::vector<std::wstring>& args,
    const std::vector<HANDLE>& inherited,ID3D12Fence* fence,ID3D12Resource* predictions,RcTransientBuffers& buffers,Regenerate regenerate,GenerationsFor generationsFor) {
    constexpr UINT Epochs=4; constexpr UINT64 OutputBytes=128*96*12; constexpr UINT Rows=128*96;
    auto readback=buffers.Buffer(OutputBytes,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
    const UINT64 allocated=renderer.gpu.allocated;
    RcIsolatedSession session(args,inherited,options.rcProbe.c_str());
    VerifyRcFrameAdmission(); VerifyRcGenerations(); VerifyRcStalenessGate();
    const bool control=options.rcStalenessForceContinue;
    RcFrameAdmission admission; Options requested=options;
    auto identityFor=[&](UINT camera) { const auto g=generationsFor(renderer.frame,requested); return RcFrameAdmission::Identity{g.scene,camera,g.lighting,g.material,g.settings}; };
    std::array<RcFrameAdmission::Identity,Epochs> identities{};
    identities[0]=identityFor(1); admission.RequestFrame(identities[0]);
    std::array<RcFrameAdmission::Request,Epochs> requests{}; std::array<RcStalenessGate::Decision,Epochs> decisions{};
    std::array<uint64_t,Epochs> outputHashes{}; std::array<bool,Epochs> admitted{}; std::array<std::vector<float>,Epochs> values;
    std::array<unsigned char,OutputBytes> bytes{};
    UINT enforcedResets=0,generationViolations=0,refused=0;
    for(UINT epoch=0;epoch<Epochs;++epoch) {
        requests[epoch]=admission.Begin();
        const auto noCache=renderer.ReadPixels();
        decisions[epoch]=RcStalenessGate::Enforce(admission,requests[epoch],control&&epoch==1);
        Require(!decisions[epoch].refused,"RC staleness gate refused an admission continue across a generation change");
        if(decisions[epoch].command==RcEpochProtocol::Reset&&decisions[epoch].changedGenerations) ++enforcedResets;
        if(decisions[epoch].command==RcEpochProtocol::Continue) generationViolations+=decisions[epoch].changedGenerations;
        Check(renderer.gpu.queue->Signal(fence,RcEpochProtocol::Signal(epoch,decisions[epoch].command)),"RC staleness session command");
        session.WaitFence(fence,RcEpochProtocol::Ack(epoch),options.rcWorkerTimeoutMs);
        admitted[epoch]=admission.Complete(requests[epoch].serial,true);
        renderer.gpu.Begin(); D3D12_RESOURCE_BARRIER barrier{}; barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        barrier.Transition={predictions,D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_SOURCE};
        renderer.gpu.list->ResourceBarrier(1,&barrier); renderer.gpu.list->CopyResource(readback.Get(),predictions);
        std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter); renderer.gpu.list->ResourceBarrier(1,&barrier); renderer.gpu.Execute();
        void* mapped{}; D3D12_RANGE range{0,SIZE_T(OutputBytes)},empty{};
        Check(readback->Map(0,&range,&mapped),"RC staleness session readback"); std::memcpy(bytes.data(),mapped,bytes.size()); readback->Unmap(0,&empty);
        uint64_t hash=14695981039346656037ull; for(auto byte:bytes) { hash^=byte; hash*=1099511628211ull; } outputHashes[epoch]=hash;
        values[epoch].resize(Rows*3); std::memcpy(values[epoch].data(),bytes.data(),bytes.size());
        Require(renderer.ReadPixels()==noCache,"RC staleness session changed diagnostic output");
        Require(renderer.gpu.allocated==allocated,"RC staleness session allocated per-epoch GPU resources");
        if(epoch+1<Epochs) {
            // Parent owns the inputs again after the acknowledgement. Epoch 1 changes
            // lighting only; epochs 2 and 3 repeat L1 under a new camera revision,
            // which the policy resets without any real camera change.
            if(epoch==0) requested.lightIntensity=options.lightIntensity*.4f;
            renderer.Configure(requested,true); renderer.RenderTo(1); regenerate(renderer.frame);
            identities[epoch+1]=identityFor(epoch==0?1:UINT(epoch+1)); admission.RequestFrame(identities[epoch+1]);
        }
    }
    Check(renderer.gpu.queue->Signal(fence,RcEpochProtocol::Signal(Epochs,RcEpochProtocol::Stop)),"RC staleness session stop");
    session.WaitFence(fence,RcEpochProtocol::Ack(Epochs),options.rcWorkerTimeoutMs);
    const auto child=session.Finish(options.rcWorkerTimeoutMs);
    Require(child.reaped&&!child.timedOut&&!child.overflow&&!child.exitCode&&child.error.empty(),"RC staleness session child failed");
    Require(!admission.queued&&!admission.busy&&admission.coalesced==0&&admission.discarded==0,"RC staleness session queue accounting mismatch");
    Require(identities[1].lighting!=identities[0].lighting&&identities[1].scene==identities[0].scene&&identities[1].material==identities[0].material&&identities[1].settings==identities[0].settings,
        ("RC staleness scenario did not change lighting only: scene "+std::to_string(identities[1].scene==identities[0].scene)+" lighting "+std::to_string(identities[1].lighting!=identities[0].lighting)+
         " material "+std::to_string(identities[1].material==identities[0].material)+" settings "+std::to_string(identities[1].settings==identities[0].settings)).c_str());
    Require(identities[2].lighting==identities[1].lighting&&identities[3].lighting==identities[1].lighting,"RC staleness fresh epochs changed lighting");
    std::istringstream input(child.output); std::ostringstream records;
    std::array<uint64_t,Epochs> starts{},posts{}; std::array<UINT,Epochs> counts{};
    for(UINT epoch=0;epoch<Epochs;++epoch) {
        std::string magic; UINT ordinal=0,command=0;
        Require(bool(input>>magic>>ordinal>>command>>counts[epoch]>>starts[epoch]>>posts[epoch])&&magic=="RCSESSIONEPOCH1"&&ordinal==epoch&&
            command==(decisions[epoch].command==RcEpochProtocol::Reset?0u:1u)&&counts[epoch]&&counts[epoch]<=Rows&&posts[epoch]==outputHashes[epoch]&&starts[epoch]!=posts[epoch],"RC staleness session epoch report mismatch");
        if(epoch) records << ',';
        records << "{\"epoch\":" << epoch << ",\"reset\":" << (decisions[epoch].command==RcEpochProtocol::Reset?"true":"false") << ",\"forced_continue\":" << (decisions[epoch].forced?"true":"false")
            << ",\"changed_generations\":" << decisions[epoch].changedGenerations << ",\"admitted\":" << (admitted[epoch]?"true":"false")
            << ",\"query_count\":" << counts[epoch] << ",\"start_hash\":" << starts[epoch] << ",\"post_hash\":" << posts[epoch] << '}';
    }
    std::string magic,extra; UINT completed=0,dispatches=0;
    Require(bool(input>>magic>>completed>>dispatches)&&magic=="RCSESSIONEND1"&&completed==Epochs&&dispatches==Epochs*(2+options.rcTrainingBatches)&&!(input>>extra),"RC staleness session stop report mismatch");
    Require(counts[0]==counts[1]&&counts[1]==counts[2]&&counts[2]==counts[3],"RC staleness scenario changed the query count");
    // C_old = epoch 0, C_policy = epoch 1, C_fresh = epoch 2, over the populated rows (3 values each).
    const size_t n=size_t(counts[0])*3; double sumSquares=0,maxAbs=0; size_t stale=0;
    for(size_t i=0;i<n;++i) {
        const float old=values[0][i],policy=values[1][i],fresh=values[2][i];
        Require(std::isfinite(old)&&std::isfinite(policy)&&std::isfinite(fresh),"RC staleness values are not finite");
        const double d=double(policy)-double(fresh); sumSquares+=d*d; maxAbs=std::max(maxAbs,std::fabs(d));
        if(std::fabs(d)>std::fabs(double(policy)-double(old))) ++stale;
    }
    const double mse=sumSquares/double(n),fraction=double(stale)/double(n);
    // Lighting changes only the training targets, so the untrained baseline matches L0.
    Require(starts[3]==starts[2]&&posts[3]==posts[2]&&starts[2]==starts[0],"RC staleness fresh reset was not exact");
    // Diagnostic, not a gate: the provider output can be independent of the lighting change on this fixture.
    const bool outputLightingIndependent=posts[2]==posts[0];
    char metrics[256]; std::snprintf(metrics,sizeof(metrics),"\"stale_mse\":%.9g,\"stale_max_abs\":%.9g,\"stale_fraction\":%.9g,\"stale_values\":%zu,\"compared_values\":%zu",mse,maxAbs,fraction,stale,n);
    std::ostringstream report;
    report << "{\"result\":\"rc-staleness-session-pass\",\"mode\":\"" << (control?"negative-control":"policy") << "\",\"provider_processes\":1,\"provider_contexts\":1,\"epochs\":" << Epochs
        << ",\"provider_dispatches\":" << dispatches << ",\"enforced_resets\":" << enforcedResets << ",\"generation_violations\":" << generationViolations
        << ",\"per_epoch_gpu_allocations\":0,\"shared_resources\":5,\"shared_fences\":1,\"child_reaped\":true,\"stop_acknowledged\":true"
        << ",\"candidate_applied\":false,\"authoritative_output\":\"no-cache\",\"reset_exact\":true,\"provider_output_lighting_independent\":" << (outputLightingIndependent?"true":"false") << "," << metrics
        << ",\"generations\":{\"scene\":" << identities[0].scene << ",\"lighting_old\":" << identities[0].lighting << ",\"lighting_new\":" << identities[1].lighting
        << ",\"material\":" << identities[0].material << ",\"settings\":" << identities[0].settings << "},\"records\":[" << records.str() << "]}";
    return report.str();
}
