#pragma once
#include "rc_epoch_protocol.h"

// Stage 2 enforcement of docs/RC_STALENESS_POLICY.md, opt-in RC mode only.
// The admission queue already asks for a reset on any identity change; this gate
// re-derives the decision at the command boundary and fails closed: a Continue is
// never signalled across a scene, lighting, material, settings or camera change.
// `forceContinue` exists only for the negative control that proves the fixture can
// show stale lighting. It is never a shipped mode.
struct RcStalenessGate {
    struct Decision { RcEpochProtocol::Command command{}; UINT changedGenerations{}; bool refused{},forced{}; };
    using Identity=RcFrameAdmission::Identity;
    static UINT ChangedGenerations(const Identity& a,const Identity& b) {
        return UINT(a.scene!=b.scene)+UINT(a.lighting!=b.lighting)+UINT(a.material!=b.material)+UINT(a.settings!=b.settings);
    }
    // Call after RcFrameAdmission::Begin and before the epoch is completed.
    static Decision Enforce(const RcFrameAdmission& admission,const RcFrameAdmission::Request& request,bool forceContinue=false) {
        Decision d;
        const bool policyReset=RcFrameAdmission::MustReset(admission.haveCompleted,admission.completedIdentity,request.identity);
        d.changedGenerations=admission.haveCompleted?ChangedGenerations(admission.completedIdentity,request.identity):0;
        d.refused=policyReset&&!request.reset;
        d.command=(request.reset||policyReset)?RcEpochProtocol::Reset:RcEpochProtocol::Continue;
        if(forceContinue&&d.command==RcEpochProtocol::Reset&&admission.haveCompleted) { d.command=RcEpochProtocol::Continue; d.forced=true; }
        return d;
    }
};

void VerifyRcStalenessGate() {
    RcFrameAdmission queue; RcFrameAdmission::Identity base{1,1,1,1,1};
    auto begin=[&](RcFrameAdmission::Identity identity) { queue.RequestFrame(identity); return queue.Begin(); };
    auto first=begin(base); auto d=RcStalenessGate::Enforce(queue,first);
    Require(d.command==RcEpochProtocol::Reset&&!d.refused&&!d.forced,"RC staleness gate did not reset the first epoch");
    queue.Complete(first.serial,true);
    auto same=begin(base); d=RcStalenessGate::Enforce(queue,same);
    Require(d.command==RcEpochProtocol::Continue&&d.changedGenerations==0,"RC staleness gate reset an unchanged identity");
    queue.Complete(same.serial,true);
    auto changed=base; ++changed.camera; auto camera=begin(changed); d=RcStalenessGate::Enforce(queue,camera);
    Require(d.command==RcEpochProtocol::Reset&&d.changedGenerations==0,"RC staleness gate continued across a camera change");
    queue.Complete(camera.serial,true);
    for(UINT field=0;field<4;++field) {
        if(field==0) ++changed.scene; else if(field==1) ++changed.lighting; else if(field==2) ++changed.material; else ++changed.settings;
        auto next=begin(changed); d=RcStalenessGate::Enforce(queue,next);
        Require(d.command==RcEpochProtocol::Reset&&d.changedGenerations==1&&!d.forced,"RC staleness gate continued across a generation change");
        const auto forced=RcStalenessGate::Enforce(queue,next,true);
        Require(forced.command==RcEpochProtocol::Continue&&forced.forced&&forced.changedGenerations==1,"RC staleness negative control did not force continue");
        queue.Complete(next.serial,true);
    }
    // Fail closed even if an admission reported Continue for a changed identity.
    auto next=changed; ++next.lighting; queue.RequestFrame(next); auto tampered=queue.Begin(); tampered.reset=false;
    d=RcStalenessGate::Enforce(queue,tampered);
    Require(d.command==RcEpochProtocol::Reset&&d.refused,"RC staleness gate accepted a continue across a generation change");
}
