// Writable lock rectangles declare initialized regions. Copies/aliases invalidate.
void TextureReset(HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(c.Active()&&c.textureInputs&&SUCCEEDED(hr))++c.textureEpoch;}catch(...){}}
void TextureCreated(IDirect3DTexture9* texture,bool privateResource) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureInputs||!texture)return;
        auto tag=Get(texture,true);Need(bool(tag));tag->textureAdmission="private_resource";if(!privateResource)return;
        tag->textureAdmission="level_count";
        UINT levels=texture->GetLevelCount();Need(levels>0&&levels<=16);auto state=std::make_unique<TextureShadow>();state->epoch=c.textureEpoch;std::size_t total=0,maskTotal=0;
        for(UINT level=0;level<levels;++level){tag->textureAdmission="descriptor_pool_usage_extent";D3DSURFACE_DESC d{};Need(SUCCEEDED(texture->GetLevelDesc(level,&d)));
            // Dynamic DEFAULT textures are written in place through DISCARD/NOOVERWRITE locks, never
            // through UpdateTexture, so they need their own admission leg. Render/depth targets stay out.
            bool dynamicMip=c.textureUploads&&c.surfaceLocks&&d.Pool==D3DPOOL_DEFAULT&&(d.Usage&D3DUSAGE_DYNAMIC)&&!(d.Usage&(D3DUSAGE_RENDERTARGET|D3DUSAGE_DEPTHSTENCIL));
            Need(d.Pool==D3DPOOL_MANAGED||(c.textureUploads&&(d.Pool==D3DPOOL_SYSTEMMEM||d.Pool==D3DPOOL_DEFAULT))||dynamicMip);
            Need((d.Usage==0||dynamicMip)&&d.Width&&d.Height&&d.Width<=16384&&d.Height<=16384);
            if(level==0){state->pool=d.Pool;state->format=d.Format;state->dynamic=dynamicMip;}
            TextureMip m;m.width=d.Width;m.height=d.Height;
            tag->textureAdmission="format_or_alignment";if(d.Format==D3DFMT_A16B16G16R16){Need(dynamicMip);m.unit=1;m.unitBytes=8;}
            else if(d.Format!=D3DFMT_A8R8G8B8&&d.Format!=D3DFMT_X8R8G8B8){Need(c.compressedTextures&&(d.Format==D3DFMT_DXT1||d.Format==D3DFMT_DXT3||d.Format==D3DFMT_DXT5));m.unit=4;m.unitBytes=d.Format==D3DFMT_DXT1?8:16;if(level==0)Need(d.Width%4==0&&d.Height%4==0);}
            m.columns=(m.width+m.unit-1)/m.unit;m.rows=(m.height+m.unit-1)/m.unit;
            tag->textureAdmission="chain_budget";auto bytes=std::uint64_t(m.columns)*m.rows*m.unitBytes;auto budget=c.externalTextures?16*1024*1024:65536;Need(bytes<=budget&&total+bytes<=budget);total+=static_cast<std::size_t>(bytes);maskTotal+=std::size_t(m.columns)*m.rows;state->mips.push_back(std::move(m));}
        bool surfaceHistory=c.surfaceUploads&&state->pool==D3DPOOL_DEFAULT;
        tag->textureAdmission="shadow_budget";auto reservation=total+maskTotal+(surfaceHistory?128*sizeof(SurfaceTransfer):0);auto before=Retained().fetch_add(reservation);if(before+reservation>128*1024*1024){Retained().fetch_sub(reservation);return;}state->reserved=reservation;RetainedTextures().fetch_add(reservation);LiveTextures().fetch_add(1);UpdateRetainedPeak();
        if(surfaceHistory)state->surfaceTransfers.reserve(128);
        tag->textureAdmission="allocation";for(auto& m:state->mips){m.bytes.resize(std::size_t(m.columns)*m.rows*m.unitBytes);m.known.resize(std::size_t(m.columns)*m.rows);}
        Need(!tag->texture);tag->texture=std::move(state);tag->textureAdmission="tracked";
    }catch(...){}
}
void TextureInvalidate(IDirect3DResource9* resource,const char* reason) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureInputs||!resource)return;ComPtr<IDirect3DTexture9> texture;
        if(FAILED(resource->QueryInterface(IID_PPV_ARGS(&texture)))){ComPtr<IDirect3DSurface9> surface;if(FAILED(resource->QueryInterface(IID_PPV_ARGS(&surface))))return;if(FAILED(surface->GetContainer(IID_PPV_ARGS(&texture))))return;}
        auto tag=Get(texture.Get());if(tag&&tag->texture){tag->texture->Invalidate();tag->texture->lastInvalidation=reason;}
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);++c.textureEpoch;}catch(...){}}
}
void TextureLock(IDirect3DTexture9* texture,UINT level,const D3DLOCKED_RECT* locked,const RECT* rect,DWORD flags,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureInputs)return;auto tag=Get(texture);if(!tag||!tag->texture)return;auto& t=*tag->texture;t.lastLockFlags=flags;t.lockObserved=true;
        if(t.epoch!=c.textureEpoch){t.Invalidate();t.epoch=c.textureEpoch;}if(FAILED(hr)){t.Invalidate();return;}DWORD effective=c.surfaceLocks?flags&~D3DLOCK_NOSYSLOCK:flags;if(effective==D3DLOCK_READONLY)return;
        bool dynamicLock=c.surfaceLocks&&t.dynamic&&t.pool==D3DPOOL_DEFAULT&&(effective&(D3DLOCK_DISCARD|D3DLOCK_NOOVERWRITE))==effective;
        Need((t.pool!=D3DPOOL_DEFAULT||dynamicLock)&&(effective==0||dynamicLock||(c.dirtyTextures&&t.pool==D3DPOOL_SYSTEMMEM&&effective==D3DLOCK_NO_DIRTY_UPDATE))&&locked&&locked->pBits&&level<t.mips.size());auto& m=t.mips[level];Need(!m.pending);
        RECT r=rect?*rect:RECT{0,0,static_cast<LONG>(m.width),static_cast<LONG>(m.height)};
        Need(r.left>=0&&r.top>=0&&r.right>r.left&&r.bottom>r.top&&r.right<=static_cast<LONG>(m.width)&&r.bottom<=static_cast<LONG>(m.height));
        // Tiny compressed tails are admitted only as whole-mip locks. Other
        // compressed rectangles must align to complete blocks on all sides.
        bool whole=r.left==0&&r.top==0&&r.right==LONG(m.width)&&r.bottom==LONG(m.height);
        Need(whole||(r.left%m.unit==0&&r.top%m.unit==0&&r.right%m.unit==0&&r.bottom%m.unit==0));
        r={r.left/LONG(m.unit),r.top/LONG(m.unit),LONG((r.right+m.unit-1)/m.unit),LONG((r.bottom+m.unit-1)/m.unit)};
        auto width=std::size_t(r.right-r.left)*m.unitBytes;Need(locked->Pitch>0&&std::size_t(locked->Pitch)>=width);
        auto span=std::uint64_t(r.bottom-r.top-1)*locked->Pitch+width;Need(span<=16*1024*1024&&reinterpret_cast<std::uintptr_t>(locked->pBits)<=UINTPTR_MAX-span);
        m.rect=r;m.pitch=locked->Pitch;m.pointer=static_cast<const std::uint8_t*>(locked->pBits);m.pending=true;m.copied=false;m.dirtyOnUnlock=effective==0||t.dynamic;
        if(t.dynamic&&(effective&D3DLOCK_DISCARD))std::fill(m.known.begin(),m.known.end(),0);
        for(LONG y=r.top;y<r.bottom;++y)std::fill_n(m.known.begin()+std::size_t(y)*m.columns+r.left,std::size_t(r.right-r.left),0);
    }catch(...){TextureInvalidate(texture,"lock_or_unlock_contract");}
}
void TextureBeforeUnlock(IDirect3DTexture9* texture,UINT level) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureInputs)return;auto tag=Get(texture);if(!tag||!tag->texture)return;
        auto& t=*tag->texture;Need(t.epoch==c.textureEpoch&&level<t.mips.size());auto& m=t.mips[level];if(!m.pending)return;Need(m.pointer&&!m.copied);
        auto r=m.rect;for(LONG y=r.top;y<r.bottom;++y)memcpy(m.bytes.data()+(std::size_t(y)*m.columns+r.left)*m.unitBytes,m.pointer+std::size_t(y-r.top)*m.pitch,std::size_t(r.right-r.left)*m.unitBytes);
        m.pointer=nullptr;m.copied=true;
    }catch(...){TextureInvalidate(texture,"lock_or_unlock_contract");}
}
void TextureAfterUnlock(IDirect3DTexture9* texture,UINT level,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.textureInputs)return;auto tag=Get(texture);if(!tag||!tag->texture)return;
        auto& t=*tag->texture;Need(SUCCEEDED(hr)&&t.epoch==c.textureEpoch&&level<t.mips.size());auto& m=t.mips[level];if(!m.pending)return;Need(m.copied&&!m.pointer);
        auto r=m.rect;for(LONG y=r.top;y<r.bottom;++y)std::fill_n(m.known.begin()+std::size_t(y)*m.columns+r.left,std::size_t(r.right-r.left),1);
        m.pending=m.copied=false;++t.revision;
        if(m.dirtyOnUnlock&&level==0&&r.left==0&&r.top==0&&r.right==LONG(m.columns)&&r.bottom==LONG(m.rows)){t.fullDirty=true;t.dirtyProof="top_lock";}
    }catch(...){TextureInvalidate(texture,"lock_or_unlock_contract");}
}
#include "texture_upload.inc"
#include "surface_upload.inc"
void TextureDirty(IDirect3DTexture9* texture,const RECT* rect,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.dirtyTextures)return;
        auto tag=Get(texture);if(!tag||!tag->texture||tag->texture->pool!=D3DPOOL_SYSTEMMEM)return;auto& t=*tag->texture;
        Need(SUCCEEDED(hr)&&t.epoch==c.textureEpoch&&c.inFlight==1&&!c.overlap&&!c.writeGap);
        for(const auto& m:t.mips)Need(!m.pending);
        const auto& m=t.mips[0];RECT r=rect?*rect:RECT{0,0,LONG(m.width),LONG(m.height)};
        Need(r.left>=0&&r.top>=0&&r.right>r.left&&r.bottom>r.top&&r.right<=LONG(m.width)&&r.bottom<=LONG(m.height));
        if(r.left==0&&r.top==0&&r.right==LONG(m.width)&&r.bottom==LONG(m.height)){t.fullDirty=true;t.dirtyProof="notification";}
    }catch(...){TextureInvalidate(texture,"lock_or_unlock_contract");}
}

// Resolve the actual texture mip through canonical COM identity, never size alone.
bool SurfaceTextureTracked(IDirect3DResource9* resource) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceLocks||!resource)return false;
        ComPtr<IDirect3DSurface9> surface;if(FAILED(resource->QueryInterface(IID_PPV_ARGS(&surface))))return false;
        UINT level{};auto texture=SurfaceOwner(surface.Get(),level);auto tag=Get(texture.Get());
        return tag&&tag->texture&&(tag->texture->pool==D3DPOOL_MANAGED||tag->texture->pool==D3DPOOL_SYSTEMMEM||tag->texture->dynamic);
    }catch(...){return false;}
}
void SurfaceTextureLock(IDirect3DSurface9* surface,const D3DLOCKED_RECT* locked,const RECT* rect,DWORD flags,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceLocks||!SurfaceTextureTracked(surface))return;
        Need(c.inFlight==1&&!c.overlap&&!c.writeGap);UINT level{};auto texture=SurfaceOwner(surface,level);TextureLock(texture.Get(),level,locked,rect,flags,hr);
    }catch(...){TextureInvalidate(surface,"surface_lock_contract");}
}
void SurfaceTextureBeforeUnlock(IDirect3DSurface9* surface) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceLocks||!SurfaceTextureTracked(surface))return;
        Need(c.inFlight==1&&!c.overlap&&!c.writeGap);UINT level{};auto texture=SurfaceOwner(surface,level);TextureBeforeUnlock(texture.Get(),level);
    }catch(...){TextureInvalidate(surface,"surface_unlock_contract");}
}
void SurfaceTextureAfterUnlock(IDirect3DSurface9* surface,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceLocks||!SurfaceTextureTracked(surface))return;
        Need(c.inFlight==1&&!c.overlap&&!c.writeGap);UINT level{};auto texture=SurfaceOwner(surface,level);TextureAfterUnlock(texture.Get(),level,hr);
    }catch(...){TextureInvalidate(surface,"surface_unlock_contract");}
}
