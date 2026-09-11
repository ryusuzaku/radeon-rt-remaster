// Only proven whole-chain SYSTEMMEM -> DEFAULT UpdateTexture transfers.
std::unique_ptr<TextureUploadPending> BeforeTextureUpload(IDirect3DBaseTexture9* source,IDirect3DBaseTexture9* destination) noexcept {
    TextureShadow* diagnostic=nullptr;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureUploads||!source)return {};
        if(destination){auto tag=Get(destination);if(tag&&tag->texture){diagnostic=tag->texture.get();diagnostic->lastUpload="source_tracking";}}
        ComPtr<IDirect3DTexture9> src;Need(SUCCEEDED(source->QueryInterface(IID_PPV_ARGS(&src))));
        auto sourceTag=Get(src.Get());Need(sourceTag&&sourceTag->texture);auto& s=*sourceTag->texture;
        if(diagnostic){diagnostic->uploadSourceLockFlags=s.lastLockFlags;diagnostic->uploadSourceLockObserved=s.lockObserved;diagnostic->uploadSourceInvalidation=s.lastInvalidation;}
        bool full=s.fullDirty;auto proof=s.dirtyProof;s.fullDirty=false;s.dirtyProof=nullptr; // Consume even on failed/unsupported attempts.
        if(diagnostic)diagnostic->lastUpload="source_not_fully_dirty";Need(destination&&full);
        if(diagnostic)diagnostic->lastUpload="source_dirty_proof_missing";Need(proof);
        if(diagnostic)diagnostic->lastUpload="source_pool";Need(s.pool==D3DPOOL_SYSTEMMEM);
        if(diagnostic)diagnostic->lastUpload="source_epoch";Need(s.epoch==c.textureEpoch);
        if(diagnostic)diagnostic->lastUpload="source_revision";Need(s.revision>0);
        auto p=std::make_unique<TextureUploadPending>();p->source=src;p->dirtyProof=proof;
        Need(SUCCEEDED(destination->QueryInterface(IID_PPV_ARGS(&p->destination))));
        auto destinationTag=Get(p->destination.Get());Need(destinationTag&&destinationTag->texture&&destinationTag->id!=sourceTag->id);
        if(diagnostic)diagnostic->lastUpload="destination_contract_or_order";
        auto& d=*destinationTag->texture;
        Need(d.pool==D3DPOOL_DEFAULT&&d.format==s.format&&d.mips.size()==s.mips.size()&&c.inFlight==1&&!c.overlap&&!c.writeGap);
        if(diagnostic)diagnostic->lastUpload="source_coverage_or_chain";
        for(std::size_t i=0;i<s.mips.size();++i){const auto& a=s.mips[i];const auto& b=d.mips[i];
            Need(a.width==b.width&&a.height==b.height&&a.bytes.size()==b.bytes.size()&&!a.pending&&!b.pending&&std::all_of(a.known.begin(),a.known.end(),[](auto v){return v==1;}));}
        d.lastUpload="pending_native_result";d.epoch=c.textureEpoch;p->epoch=c.textureEpoch;p->sourceId=sourceTag->id;p->sourceRevision=s.revision;p->destinationRevision=d.revision;return p;
    }catch(...){return {};}
}
void AfterTextureUpload(std::unique_ptr<TextureUploadPending> p,HRESULT hr) noexcept {
    if(!p)return;
    try{auto& c=State();std::lock_guard lock(c.mutex);
        Need(c.Active()&&SUCCEEDED(hr)&&p->epoch==c.textureEpoch&&c.inFlight==1&&!c.overlap&&!c.writeGap);
        auto sourceTag=Get(p->source.Get()),destinationTag=Get(p->destination.Get());Need(sourceTag&&destinationTag&&sourceTag->texture&&destinationTag->texture);
        auto& s=*sourceTag->texture;auto& d=*destinationTag->texture;
        Need(s.epoch==p->epoch&&d.epoch==p->epoch&&s.revision==p->sourceRevision&&d.revision==p->destinationRevision&&d.revision<UINT64_MAX);
        for(const auto& m:s.mips)Need(!m.pending&&std::all_of(m.known.begin(),m.known.end(),[](auto v){return v==1;}));
        for(const auto& m:d.mips)Need(!m.pending);
        for(std::size_t i=0;i<s.mips.size();++i){auto& m=d.mips[i];memcpy(m.bytes.data(),s.mips[i].bytes.data(),m.bytes.size());std::fill(m.known.begin(),m.known.end(),1);}
        d.lastUpload="complete";++d.revision;d.uploadSource=p->sourceId;d.uploadRevision=p->sourceRevision;d.uploadDirtyProof=p->dirtyProof;
    }catch(...){TextureInvalidate(p->destination.Get());}
}
