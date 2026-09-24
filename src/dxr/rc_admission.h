#pragma once

// Owned by one scheduler thread. Identities are caller-issued revisions, not hashes of
// padded option structs. Any scene/camera/lighting/material/settings change
// requires a fresh epoch; unchanged input can continue the existing cache.
struct RcFrameAdmission {
    struct Identity {
        uint64_t scene{},camera{},lighting{},material{},settings{};
        bool operator==(const Identity& other) const {
            return scene==other.scene&&camera==other.camera&&lighting==other.lighting&&
                material==other.material&&settings==other.settings;
        }
    };
    struct Request { Identity identity; uint64_t serial{}; bool reset{}; };
    Identity latest{},completedIdentity{};
    Request active{},pending{};
    uint64_t serial{},coalesced{},discarded{};
    bool busy{},queued{},closed{},haveCompleted{};

    void RequestFrame(Identity identity) {
        Require(!closed,"RC admission closed");
        latest=identity;
        // Repeated notifications for the same active/pending request add no work.
        if((queued&&pending.identity==identity)||(!queued&&busy&&active.identity==identity)) return;
        if(queued) ++coalesced;
        pending={identity,++serial,false}; queued=true;
    }
    Request Begin() {
        Require(!closed&&!busy&&queued,"RC admission cannot start epoch");
        active=pending; active.reset=!haveCompleted||!(active.identity==completedIdentity);
        queued=false; busy=true; return active;
    }
    bool Complete(uint64_t token,bool successful) {
        Require(busy&&active.serial==token,"RC admission completion token mismatch");
        busy=false;
        haveCompleted=successful;
        if(successful) completedIdentity=active.identity;
        const bool publish=successful&&!closed&&active.identity==latest;
        if(!publish) ++discarded;
        return publish;
    }
    void Close() { closed=true; queued=false; }
};

void VerifyRcFrameAdmission() {
    RcFrameAdmission queue; RcFrameAdmission::Identity base{1,1,1,1,1};
    queue.RequestFrame(base); auto first=queue.Begin(); Require(first.reset,"RC initial epoch did not reset");
    bool rejected=false;
    try { queue.Begin(); } catch(const std::runtime_error&) { rejected=true; }
    Require(rejected&&queue.busy,"RC overlapping epoch admitted");
    rejected=false;
    try { queue.Complete(first.serial+1,true); } catch(const std::runtime_error&) { rejected=true; }
    Require(rejected&&queue.busy,"RC foreign completion accepted");
    queue.RequestFrame(base); Require(!queue.queued,"RC duplicate queued work");
    auto changed=base; ++changed.camera; queue.RequestFrame(changed); ++changed.camera; queue.RequestFrame(changed);
    Require(queue.coalesced==1&&!queue.Complete(first.serial,true),"RC stale camera epoch published");
    auto next=queue.Begin(); Require(next.reset&&next.identity==changed,"RC latest camera request lost");
    Require(queue.Complete(next.serial,true),"RC current camera epoch rejected");
    queue.RequestFrame(changed); next=queue.Begin(); Require(!next.reset,"RC stable identity reset");
    queue.Complete(next.serial,true);
    for(UINT field=0;field<4;++field) {
        if(field==0) ++changed.scene; else if(field==1) ++changed.lighting;
        else if(field==2) ++changed.material; else ++changed.settings;
        queue.RequestFrame(changed); next=queue.Begin(); Require(next.reset,"RC changed identity reused cache");
        queue.Complete(next.serial,true);
    }
    queue.RequestFrame(changed); next=queue.Begin();
    Require(!queue.Complete(next.serial,false),"RC failed epoch published");
    queue.RequestFrame(changed); next=queue.Begin(); Require(next.reset,"RC failure retained cache identity");
    queue.Close(); Require(!queue.Complete(next.serial,true)&&!queue.queued,"RC closed epoch published");
    rejected=false;
    try { queue.RequestFrame(base); } catch(const std::runtime_error&) { rejected=true; }
    Require(rejected&&!queue.queued,"RC closed queue accepted work");
}
