void TextureNeed(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
void TextureAsset(Context& c,const std::string& digest,const std::vector<std::uint8_t>& bytes){
    auto found=c.assetFiles.find(digest);if(found!=c.assetFiles.end()){Need(found->second==bytes.size());return;}
    Need(c.assetFileCount<512&&bytes.size()<=16*1024*1024&&c.assetBytes+bytes.size()<=256*1024*1024);
    auto attributes=GetFileAttributesW((c.path+L".assets").c_str());Need(attributes!=INVALID_FILE_ATTRIBUTES&&(attributes&FILE_ATTRIBUTE_DIRECTORY)&&!(attributes&FILE_ATTRIBUTE_REPARSE_POINT));
    auto path=c.path+L".assets\\"+std::wstring(digest.begin(),digest.end())+L".bin";
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);Need(file!=INVALID_HANDLE_VALUE);
    // Charge the reservation even if the write fails; never retry over an
    // existing partial file and never exceed the session's on-disk budget.
    ++c.assetFileCount;c.assetBytes+=bytes.size();DWORD written{};bool ok=WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr)&&written==bytes.size();CloseHandle(file);Need(ok);
    c.assetFiles.emplace(digest,bytes.size());
}
// Read-only failure context: no payload readback, new resource admission or recovery.
std::string TextureDiagnostic(IDirect3DDevice9* d,UINT slot) noexcept {
    try{ComPtr<IDirect3DBaseTexture9> base;if(FAILED(d->GetTexture(slot,&base))||!base)return {};
        ComPtr<IDirect3DTexture9> texture;if(FAILED(base.As(&texture)))return {};D3DSURFACE_DESC desc{};
        if(FAILED(texture->GetLevelDesc(0,&desc)))return {};auto tag=Get(base.Get());auto t=tag?tag->texture.get():nullptr;
        std::uint64_t known=0,total=0,coverage=0;unsigned pending=0;if(t)for(const auto& mip:t->mips){total+=mip.bytes.size();coverage+=mip.known.size();known+=std::count(mip.known.begin(),mip.known.end(),std::uint8_t(1))*mip.unitBytes;pending+=mip.pending?1:0;}
        std::string result="{\"slot\":"+std::to_string(slot)+",\"id\":"+std::to_string(tag?tag->id:0)+",\"descriptor\":[";
        bool first=true;for(auto value:{DWORD(desc.Width),DWORD(desc.Height),DWORD(desc.Format),DWORD(desc.Usage),DWORD(desc.Pool),DWORD(desc.MultiSampleType),DWORD(desc.MultiSampleQuality)}){if(!first)result+=",";first=false;result+=std::to_string(value);}
        return result+"],\"levels\":"+std::to_string(texture->GetLevelCount())+",\"tracked\":"+(t?"true":"false")+",\"admission\":\""+(tag?tag->textureAdmission:"unobserved")+"\",\"revision\":"+std::to_string(t?t->revision:0)+",\"known_bytes\":"+std::to_string(known)+",\"total_bytes\":"+std::to_string(total)+",\"pending_mips\":"+std::to_string(pending)+",\"upload_source\":"+std::to_string(t?t->uploadSource:0)+",\"upload_revision\":"+std::to_string(t?t->uploadRevision:0)+",\"surface_transfers\":"+std::to_string(t?t->surfaceTransfers.size():0)+",\"coverage_bytes\":"+std::to_string(coverage)+",\"upload_source_lock_flags\":"+(t&&t->uploadSourceLockObserved?std::to_string(t->uploadSourceLockFlags):"null")+",\"upload_source_invalidation\":\""+(t?t->uploadSourceInvalidation:"unavailable")+"\""+",\"last_invalidation\":\""+(t?t->lastInvalidation:"none")+"\",\"last_upload\":\""+(t?t->lastUpload:"none")+"\"}";
    }catch(...){return {};}
}
std::string TextureInputs(Context& c,IDirect3DDevice9* d,Pending* diagnostic){
    auto hex=[](const void* data,std::size_t size){std::string s;const char* h="0123456789abcdef";auto b=static_cast<const unsigned char*>(data);for(std::size_t i=0;i<size;++i){s+=h[b[i]>>4];s+=h[b[i]&15];}return s;};
    std::string s=",\"texture_inputs\":[";
    for(UINT slot=0;slot<2;++slot){try{ComPtr<IDirect3DBaseTexture9> texture;TextureNeed(SUCCEEDED(d->GetTexture(slot,&texture))&&texture,"texture_binding_query");auto tag=Get(texture.Get());TextureNeed(tag&&tag->texture,"texture_tracking_missing");
        const auto& t=*tag->texture;TextureNeed(t.epoch==c.textureEpoch&&t.revision>0,"texture_revision_or_epoch");if(slot)s+=",";
        bool uploaded=t.pool==D3DPOOL_DEFAULT;bool surface=c.surfaceUploads&&uploaded&&!t.surfaceTransfers.empty();
        // Dynamic textures are written in place through observed locks, never uploaded: a fully
        // observed revision carries its own proof and needs no UpdateTexture chain.
        bool dynamicInPlace=c.surfaceLocks&&c.textureUploads&&uploaded&&t.dynamic&&t.revision>0;
        TextureNeed(t.pool==D3DPOOL_MANAGED||surface||(c.textureUploads&&uploaded&&t.uploadSource&&t.uploadRevision)||dynamicInPlace,"texture_upload_proof_missing");
        s+="{\"id\":"+std::to_string(tag->id)+",\"revision\":"+std::to_string(t.revision)+",\"origin\":\""+(surface?std::string("observed_private_default_surface"):dynamicInPlace?std::string("observed_private_default_dynamic"):uploaded?std::string("observed_private_default_update"):std::string("observed_private_managed"))+"\"";
        if(uploaded&&!surface&&!dynamicInPlace){s+=",\"transfer\":{\"operation\":\"UpdateTexture\",\"scope\":\"whole_chain\",\"source\":"+std::to_string(t.uploadSource)+",\"revision\":"+std::to_string(t.uploadRevision);
            if(c.dirtyTextures){Need(t.uploadDirtyProof);s+=",\"dirty_proof\":\""+std::string(t.uploadDirtyProof)+"\"";}s+="}";}
        if(dynamicInPlace&&!surface&&c.dirtyTextures){Need(t.dirtyProof);s+=",\"dynamic_proof\":\""+std::string(t.dirtyProof)+"\"";}
        if(surface){s+=",\"surface_transfers\":[";bool first=true;for(const auto& e:t.surfaceTransfers){if(!first)s+=",";first=false;
            s+="{\"source\":"+std::to_string(e.source)+",\"revision\":"+std::to_string(e.revision)+",\"source_level\":"+std::to_string(e.sourceLevel)+",\"destination_level\":"+std::to_string(e.destinationLevel)+",\"source_extent\":["+std::to_string(e.sourceWidth)+","+std::to_string(e.sourceHeight)+"],\"source_rect\":["+std::to_string(e.rect.left)+","+std::to_string(e.rect.top)+","+std::to_string(e.rect.right)+","+std::to_string(e.rect.bottom)+"],\"destination\":["+std::to_string(e.destination.x)+","+std::to_string(e.destination.y)+"]}";}s+="]";}
        s+=",\"mips\":[";
        for(std::size_t level=0;level<t.mips.size();++level){const auto& m=t.mips[level];TextureNeed(!m.pending,"texture_mip_pending");TextureNeed(std::all_of(m.known.begin(),m.known.end(),[](auto b){return b==1;}),"texture_mip_uninitialized");
            auto digest=scene::Digest(m.bytes.data(),m.bytes.size());if(level)s+=",";
            auto key=hex(digest.data(),digest.size());
            if(c.externalTextures){TextureAsset(c,key,m.bytes);s+="{\"sha256\":\""+key+"\",\"size\":"+std::to_string(m.bytes.size())+"}";}
            else s+="{\"sha256\":\""+key+"\",\"bytes\":\""+hex(m.bytes.data(),m.bytes.size())+"\"}";}
        s+="]}";
        }catch(...){if(c.surfaceUploads)diagnostic->textureDiagnostic=TextureDiagnostic(d,slot);throw;}
    }
    return s+"]";
}
