template<class Fill>
void SurfaceFixtureUploads(IDirect3DDevice9* d,IDirect3DTexture9* source,IDirect3DTexture9* destination,const std::wstring& action,Fill fill){
    auto alias=[&]{ComPtr<IDirect3DSurface9> surface;Check(source->GetSurfaceLevel(0,&surface));D3DLOCKED_RECT lock{};Check(surface->LockRect(&lock,nullptr,0));Check(surface->UnlockRect());};
    auto copy=[&](bool partial,bool staged=false){
        if(staged)alias();
        for(UINT level=0;level<destination->GetLevelCount();++level){ComPtr<IDirect3DSurface9> src,dst;
            Check(source->GetSurfaceLevel(level+(action==L"surfacemip"?1:0),&src));Check(destination->GetSurfaceLevel(level,&dst));
            D3DSURFACE_DESC desc{};Check(src->GetDesc(&desc));UINT nx=partial&&desc.Width>=8?2:1,ny=partial&&desc.Height>=8?2:1;
            for(UINT py=0;py<ny;++py)for(UINT px=0;px<nx;++px){
                RECT r{LONG(desc.Width*px/nx),LONG(desc.Height*py/ny),LONG(desc.Width*(px+1)/nx),LONG(desc.Height*(py+1)/ny)};POINT q{r.left,r.top};
                bool whole=nx==1&&ny==1;
                if(staged){D3DLOCKED_RECT lock{};Check(source->LockRect(level,&lock,whole?nullptr:&r,D3DLOCK_NO_DIRTY_UPDATE));Check(source->UnlockRect(level));}
                Check(d->UpdateSurface(src.Get(),whole?nullptr:&r,dst.Get(),whole?nullptr:&q));
            }
        }
    };
    auto invalid=[&]{ComPtr<IDirect3DSurface9> src,dst;Check(source->GetSurfaceLevel(0,&src));Check(destination->GetSurfaceLevel(0,&dst));
        D3DSURFACE_DESC desc{};Check(dst->GetDesc(&desc));RECT r{0,0,4,4};POINT q{LONG(desc.Width),0};
        Need(FAILED(d->UpdateSurface(src.Get(),&r,dst.Get(),&q)),"out-of-bounds surface copy succeeded");};
    if(action==L"surfaceincomplete"||action==L"surfaceunknown"){
        Check(d->UpdateTexture(source,destination));
        if(action==L"surfaceunknown"){alias();copy(false);}
        else{ComPtr<IDirect3DSurface9> src,dst;Check(source->GetSurfaceLevel(0,&src));Check(destination->GetSurfaceLevel(0,&dst));RECT r{0,0,4,4};POINT q{0,0};Check(d->UpdateSurface(src.Get(),&r,dst.Get(),&q));}
        return;
    }
    copy(action==L"surfacepartial"||action==L"surfacestaged",action==L"surfacestaged");
    if(action==L"surfacerefresh"){fill(1);copy(true);}
    if(action==L"surfacerecover"){invalid();fill(1);copy(false);}
    if(action==L"surfacefailed")invalid();
    if(action==L"surfaceafter"){fill(1);Check(d->UpdateTexture(source,destination));}
    if(action==L"surfaceoffset"){fill(1);ComPtr<IDirect3DSurface9> src,dst;Check(source->GetSurfaceLevel(0,&src));Check(destination->GetSurfaceLevel(0,&dst));
        RECT r{4,4,8,8};POINT q{0,0};Check(d->UpdateSurface(src.Get(),&r,dst.Get(),&q));}
    if(action==L"surfacehistory"){ComPtr<IDirect3DSurface9> src,dst;Check(source->GetSurfaceLevel(0,&src));Check(destination->GetSurfaceLevel(0,&dst));
        for(UINT i=0;i<129;++i)Check(d->UpdateSurface(src.Get(),nullptr,dst.Get(),nullptr));}
    if(action==L"surfaceunaligned"){ComPtr<IDirect3DSurface9> src,dst;Check(source->GetSurfaceLevel(0,&src));Check(destination->GetSurfaceLevel(0,&dst));
        RECT r{1,0,5,4};POINT q{0,0};d->UpdateSurface(src.Get(),&r,dst.Get(),&q);}
}

