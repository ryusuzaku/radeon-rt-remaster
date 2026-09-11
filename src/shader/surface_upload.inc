// Surface aliases are resolved by COM identity, not dimensions or pointer guesses.
ComPtr<IDirect3DTexture9> SurfaceOwner(IDirect3DSurface9* surface,UINT& level){
    Need(surface);ComPtr<IDirect3DTexture9> texture;Need(SUCCEEDED(surface->GetContainer(IID_PPV_ARGS(&texture))));
    ComPtr<IUnknown> identity;Need(SUCCEEDED(surface->QueryInterface(IID_PPV_ARGS(&identity))));
    UINT levels=texture->GetLevelCount();Need(levels>0&&levels<=16);
    for(level=0;level<levels;++level){ComPtr<IDirect3DSurface9> mip;ComPtr<IUnknown> candidate;
        Need(SUCCEEDED(texture->GetSurfaceLevel(level,&mip))&&SUCCEEDED(mip.As(&candidate)));
        if(candidate.Get()==identity.Get())return texture;
    }
    Need(false);return {};
}
void KnownSurfaceRegion(const TextureMip& m,const RECT& r){
    Need(!m.pending);auto width=std::size_t(r.right-r.left);
    for(LONG y=r.top;y<r.bottom;++y){auto begin=m.known.begin()+std::size_t(y)*m.columns+r.left;
        Need(std::all_of(begin,begin+width,[](auto v){return v==1;}));}
}
std::unique_ptr<SurfaceUploadPending> BeforeSurfaceUpload(IDirect3DSurface9* source,const RECT* rect,IDirect3DSurface9* destination,const POINT* point) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceUploads)return {};
        auto p=std::make_unique<SurfaceUploadPending>();auto& e=p->transfer;
        p->destination=SurfaceOwner(destination,e.destinationLevel);auto dt=Get(p->destination.Get());Need(dt&&dt->texture);auto& d=*dt->texture;
        Need(d.pool==D3DPOOL_DEFAULT&&d.surfaceTransfers.capacity()>=128);
        if(d.epoch!=c.textureEpoch||d.uploadSource){d.Invalidate();d.epoch=c.textureEpoch;}
        Need(d.surfaceTransfers.size()<128&&c.inFlight==1&&!c.overlap&&!c.writeGap&&c.accesses.empty()&&!c.accessGap);
        p->source=SurfaceOwner(source,e.sourceLevel);auto st=Get(p->source.Get());Need(st&&st->texture&&st->id!=dt->id);auto& s=*st->texture;
        Need(s.pool==D3DPOOL_SYSTEMMEM&&s.format==d.format&&s.epoch==c.textureEpoch&&s.revision>0);
        const auto& a=s.mips.at(e.sourceLevel);auto& b=d.mips.at(e.destinationLevel);Need(!b.pending);
        e.source=st->id;e.revision=s.revision;e.sourceWidth=a.width;e.sourceHeight=a.height;
        e.rect=rect?*rect:RECT{0,0,LONG(a.width),LONG(a.height)};e.destination=point?*point:POINT{0,0};auto r=e.rect;auto q=e.destination;
        Need(r.left>=0&&r.top>=0&&r.right>r.left&&r.bottom>r.top&&r.right<=LONG(a.width)&&r.bottom<=LONG(a.height)&&q.x>=0&&q.y>=0);
        LONG w=r.right-r.left,h=r.bottom-r.top;Need(std::uint64_t(q.x)+w<=b.width&&std::uint64_t(q.y)+h<=b.height);
        bool whole=r.left==0&&r.top==0&&r.right==LONG(a.width)&&r.bottom==LONG(a.height)&&q.x==0&&q.y==0&&w==LONG(b.width)&&h==LONG(b.height);
        Need(whole||(r.left%a.unit==0&&r.top%a.unit==0&&r.right%a.unit==0&&r.bottom%a.unit==0&&q.x%a.unit==0&&q.y%a.unit==0));
        p->blocks={r.left/LONG(a.unit),r.top/LONG(a.unit),LONG((r.right+a.unit-1)/a.unit),LONG((r.bottom+a.unit-1)/a.unit)};
        p->destinationBlocks={q.x/LONG(a.unit),q.y/LONG(a.unit)};KnownSurfaceRegion(a,p->blocks);
        auto width=std::size_t(p->blocks.right-p->blocks.left)*b.unitBytes;
        for(LONG y=0;y<p->blocks.bottom-p->blocks.top;++y)std::fill_n(b.known.begin()+std::size_t(p->destinationBlocks.y+y)*b.columns+p->destinationBlocks.x,width/b.unitBytes,0);
        p->sourceRevision=s.revision;p->destinationRevision=d.revision;p->epoch=c.textureEpoch;return p;
    }catch(...){TextureInvalidate(destination);return {};}
}
void AfterSurfaceUpload(std::unique_ptr<SurfaceUploadPending> p,HRESULT hr) noexcept {
    if(!p)return;
    try{auto& c=State();std::lock_guard lock(c.mutex);Need(c.Active()&&SUCCEEDED(hr)&&c.textureEpoch==p->epoch&&c.inFlight==1&&!c.overlap&&!c.writeGap&&c.accesses.empty()&&!c.accessGap);
        auto st=Get(p->source.Get()),dt=Get(p->destination.Get());Need(st&&dt&&st->texture&&dt->texture);auto& s=*st->texture;auto& d=*dt->texture;
        Need(s.epoch==p->epoch&&d.epoch==p->epoch&&s.revision==p->sourceRevision&&d.revision==p->destinationRevision&&d.revision<UINT64_MAX&&d.surfaceTransfers.size()<128);
        auto& a=s.mips.at(p->transfer.sourceLevel);auto& b=d.mips.at(p->transfer.destinationLevel);Need(!b.pending);KnownSurfaceRegion(a,p->blocks);
        auto width=std::size_t(p->blocks.right-p->blocks.left)*b.unitBytes;
        for(LONG y=0;y<p->blocks.bottom-p->blocks.top;++y){auto offset=(std::size_t(p->destinationBlocks.y+y)*b.columns+p->destinationBlocks.x)*b.unitBytes;
            memcpy(b.bytes.data()+offset,a.bytes.data()+(std::size_t(p->blocks.top+y)*a.columns+p->blocks.left)*a.unitBytes,width);std::fill_n(b.known.begin()+offset/b.unitBytes,width/b.unitBytes,1);}
        d.surfaceTransfers.push_back(p->transfer);++d.revision;
    }catch(...){TextureInvalidate(p->destination.Get());}
}

