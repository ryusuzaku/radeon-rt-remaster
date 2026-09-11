#include "capture.h"
#include "../trace/trace.h"
#include <wrl/client.h>
#include <algorithm>
#include <atomic>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <unordered_map>

namespace rrt::capture {
using Microsoft::WRL::ComPtr;
namespace {
// Native resource owns this object. It never owns the resource/device back.
const GUID ShadowGuid={0x9e637e67,0x89ab,0x4618,{0xa7,0x33,0x3e,0xe9,0x66,0x21,0x89,0xc3}};
std::atomic<std::size_t>& ShadowBytes() { static auto* b=new std::atomic<std::size_t>{0}; return *b; }
struct Shadow final : IUnknown {
    std::atomic<ULONG> refs{1}; std::vector<std::uint8_t> bytes;
    bool valid{},pending{},full{}; const std::uint8_t* pointer{};
    UINT offset{},length{},pitch{},rowBytes{},rows{},destinationPitch{};
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid,void** out) override {
        if(!out) return E_POINTER; *out=nullptr; if(iid!=__uuidof(IUnknown)) return E_NOINTERFACE;
        *out=static_cast<IUnknown*>(this); AddRef(); return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs; }
    ULONG STDMETHODCALLTYPE Release() override { auto n=--refs; if(!n) delete this; return n; }
    ~Shadow() { ShadowBytes().fetch_sub(bytes.size()); }
    void Resize(std::size_t n) {
        if(n==bytes.size()) return;
        if(n>scene::MaxResourceBytes) throw std::runtime_error("resource budget");
        const auto before=ShadowBytes().fetch_add(n);
        if(before+n>scene::MaxBytes) { ShadowBytes().fetch_sub(n); throw std::runtime_error("shadow budget"); }
        try { std::vector<std::uint8_t> next(n); ShadowBytes().fetch_sub(bytes.size()); bytes.swap(next); valid=false; }
        catch(...) { ShadowBytes().fetch_sub(n); throw; }
    }
};
ComPtr<Shadow> GetShadow(IDirect3DResource9* resource,bool create=false) {
    ComPtr<Shadow> shadow; if(!resource) return shadow;
    DWORD size=sizeof(Shadow*); Shadow* raw{};
    if(SUCCEEDED(resource->GetPrivateData(ShadowGuid,&raw,&size)) && raw) shadow.Attach(raw);
    else if(create) {
        shadow.Attach(new Shadow);
        if(FAILED(resource->SetPrivateData(ShadowGuid,static_cast<IUnknown*>(shadow.Get()),sizeof(IUnknown*),D3DSPD_IUNKNOWN))) shadow.Reset();
    }
    return shadow;
}
std::wstring Environment(const wchar_t* name) {
    wchar_t value[32768]{}; auto n=GetEnvironmentVariableW(name,value,32768); return n && n<32768?value:L"";
}
struct Context {
    std::recursive_mutex mutex; std::wstring path; std::uint32_t target{},frame{};
    bool done{}; IDirect3DDevice9* owner{}; scene::Scene scene; std::size_t bytes{};
    Context():path(Environment(L"RRT_SCENE_FILE")) {
        const auto value=Environment(L"RRT_SCENE_FRAME");
        if(!value.empty()) {
            wchar_t* end{}; auto n=wcstoull(value.c_str(),&end,10);
            if(*end || n>1000000) { path.clear(); return; } target=static_cast<std::uint32_t>(n);
        }
        scene.frame=target;
    }
    bool Selected() const { return !path.empty() && !done && frame==target; }
    void Reject(scene::Reason reason,std::uint32_t ordinal=UINT_MAX) {
        if(scene.rejected.size()<scene::MaxDraws) scene.rejected.push_back({ordinal,reason});
        else if(scene.rejected.size()==scene::MaxDraws) scene.rejected.push_back({UINT_MAX,scene::Reason::budget});
    }
};
Context& State() { static auto* c=new Context; return *c; }
void RejectSafe(scene::Reason reason) noexcept {
    try { auto& c=State(); std::lock_guard lock(c.mutex); if(c.Selected()) c.Reject(reason); } catch(...) {}
}
void Check(HRESULT hr) { if(FAILED(hr)) throw scene::Reason::readback; }
void Require(bool condition,scene::Reason reason) { if(!condition) throw reason; }
void Target(Context& c,IDirect3DDevice9* d) {
    if(!c.owner) c.owner=d; Require(c.owner==d,scene::Reason::multipleDevices);
    ComPtr<IDirect3DSurface9> rt,back,other;
    Check(d->GetRenderTarget(0,&rt)); Check(d->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back));
    Require(rt.Get()==back.Get(),scene::Reason::target);
    for(DWORD index=1;index<4;++index) { other.Reset(); if(SUCCEEDED(d->GetRenderTarget(index,&other))) Require(!other,scene::Reason::target); }
    D3DSURFACE_DESC desc{}; Check(rt->GetDesc(&desc));
    Require(desc.Format==D3DFMT_X8R8G8B8 && desc.MultiSampleType==D3DMULTISAMPLE_NONE && desc.Width<=4096 && desc.Height<=4096,scene::Reason::target);
    if(c.scene.width) Require(c.scene.width==desc.Width && c.scene.height==desc.Height,scene::Reason::target);
    c.scene.width=desc.Width; c.scene.height=desc.Height;
}
void InvalidateTargets(IDirect3DDevice9* d) {
    for(DWORD i=0;i<4;++i) {
        ComPtr<IDirect3DSurface9> surface; ComPtr<IDirect3DTexture9> texture;
        if(SUCCEEDED(d->GetRenderTarget(i,&surface)) && surface && SUCCEEDED(surface->GetContainer(IID_PPV_ARGS(&texture)))) Invalidate(texture.Get());
    }
}
void ReadState(IDirect3DDevice9* d,scene::Draw& out) {
    ComPtr<IDirect3DVertexShader9> vs; ComPtr<IDirect3DPixelShader9> ps;
    Check(d->GetVertexShader(&vs)); Check(d->GetPixelShader(&ps)); Require(!vs&&!ps,scene::Reason::shader);
    DWORD fvf{}; Check(d->GetFVF(&fvf)); Require(fvf==scene::Fvf,scene::Reason::topology);
    auto& s=out.state;
    Check(d->GetTransform(D3DTS_WORLD,&s.world)); Check(d->GetTransform(D3DTS_VIEW,&s.view)); Check(d->GetTransform(D3DTS_PROJECTION,&s.projection));
    Check(d->GetViewport(&s.viewport)); Check(d->GetScissorRect(&s.scissor));
    for(std::size_t i=0;i<s.render.size();++i) Check(d->GetRenderState(scene::RenderStates[i],&s.render[i]));
    for(std::size_t i=0;i<s.texture.size();++i) Check(d->GetTextureStageState(0,scene::TextureStates[i],&s.texture[i]));
    for(std::size_t i=0;i<s.sampler.size();++i) Check(d->GetSamplerState(0,scene::SamplerStates[i],&s.sampler[i]));
    for(auto state:{D3DRS_ZENABLE,D3DRS_STENCILENABLE,D3DRS_LIGHTING,D3DRS_FOGENABLE,D3DRS_SPECULARENABLE,D3DRS_VERTEXBLEND,D3DRS_CLIPPLANEENABLE}) {
        DWORD value{}; Check(d->GetRenderState(state,&value)); Require(value==0,scene::Reason::state);
    }
    DWORD wrap{}; Check(d->GetRenderState(D3DRS_WRAP0,&wrap)); Require(wrap==0,scene::Reason::state);
    DWORD fill{}; Check(d->GetRenderState(D3DRS_FILLMODE,&fill)); Require(fill==D3DFILL_SOLID,scene::Reason::state);
    DWORD value{}; Check(d->GetTextureStageState(1,D3DTSS_COLOROP,&value)); Require(value==D3DTOP_DISABLE,scene::Reason::state);
    Require(s.texture[0]==D3DTOP_MODULATE && s.texture[1]==D3DTA_TEXTURE && s.texture[2]==D3DTA_DIFFUSE &&
        s.texture[3]==D3DTOP_SELECTARG1 && s.texture[4]==D3DTA_TEXTURE && s.texture[6]==0 && s.texture[7]==D3DTTFF_DISABLE,scene::Reason::state);
    Require(s.sampler[6]==D3DTEXF_NONE && s.sampler[8]==0,scene::Reason::state);
    UINT frequency{}; Check(d->GetStreamSourceFreq(0,&frequency)); Require(frequency==1,scene::Reason::state);
    ComPtr<IDirect3DBaseTexture9> base; Check(d->GetTexture(0,&base)); Require(base!=nullptr,scene::Reason::resource);
    ComPtr<IDirect3DTexture9> texture; Require(SUCCEEDED(base.As(&texture)),scene::Reason::resource);
    D3DSURFACE_DESC desc{}; Check(texture->GetLevelDesc(0,&desc));
    Require(desc.Format==D3DFMT_A8R8G8B8 || desc.Format==D3DFMT_X8R8G8B8,scene::Reason::resource);
    auto payload=GetShadow(texture.Get()); Require(payload && payload->valid && !payload->pending,scene::Reason::resource);
    Require(desc.Width<=2048 && desc.Height<=2048 && payload->bytes.size()==std::uint64_t(desc.Width)*desc.Height*4,scene::Reason::resource);
    out.width=desc.Width; out.height=desc.Height; out.texture=payload->bytes;
    if(desc.Format==D3DFMT_X8R8G8B8) for(std::size_t i=3;i<out.texture.size();i+=4) out.texture[i]=255;
}
}
bool Enabled() noexcept { try { auto& c=State(); std::lock_guard lock(c.mutex); return !c.path.empty()&&!c.done; } catch(...) { return false; } }
void Invalidate(IDirect3DResource9* resource) noexcept {
    if(!Enabled()) return;
    try { auto& c=State(); std::lock_guard lock(c.mutex); auto shadow=GetShadow(resource); if(shadow) { shadow->valid=false; shadow->pending=false; } } catch(...) {}
}
void SurfaceWrite(IDirect3DSurface9* surface) noexcept {
    if(!Enabled() || !surface) return;
    ComPtr<IDirect3DTexture9> texture;
    if(SUCCEEDED(surface->GetContainer(IID_PPV_ARGS(&texture)))) Invalidate(texture.Get());
    // Surface-level writes are deliberately not inferred as valid texture
    // uploads. Direct writes to the primary backbuffer also break replay.
    else try {
        auto& c=State(); std::lock_guard lock(c.mutex); if(!c.Selected()) return;
        ComPtr<IDirect3DDevice9> d; ComPtr<IDirect3DSurface9> back;
        if(SUCCEEDED(surface->GetDevice(&d)) && SUCCEEDED(d->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back)) && back.Get()==surface)
            c.Reject(scene::Reason::operation);
    } catch(...) {}
}
void BufferLock(IDirect3DResource9* resource,UINT offset,UINT size,void* data,DWORD flags) noexcept {
    if(!Enabled() || (flags&D3DLOCK_READONLY)) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex); UINT total{};
        ComPtr<IDirect3DVertexBuffer9> vb; ComPtr<IDirect3DIndexBuffer9> ib;
        if(SUCCEEDED(resource->QueryInterface(IID_PPV_ARGS(&vb)))) { D3DVERTEXBUFFER_DESC desc{}; Check(vb->GetDesc(&desc)); total=desc.Size; }
        else { Check(resource->QueryInterface(IID_PPV_ARGS(&ib))); D3DINDEXBUFFER_DESC desc{}; Check(ib->GetDesc(&desc)); total=desc.Size; }
        auto s=GetShadow(resource,true); Require(s!=nullptr,scene::Reason::resource); s->Resize(total);
        if(flags&D3DLOCK_DISCARD) s->valid=false;
        Require(offset<=total,scene::Reason::resource); if(!size) size=total-offset;
        Require(size<=total-offset && data,scene::Reason::resource);
        s->offset=offset; s->length=size; s->pointer=static_cast<const std::uint8_t*>(data);
        s->rows=0; s->full=offset==0 && size==total; s->pending=true;
    } catch(...) { Invalidate(resource); }
}
void TextureLock(IDirect3DTexture9* texture,UINT level,const D3DLOCKED_RECT* locked,const RECT* rect,DWORD flags) noexcept {
    if(!Enabled() || (flags&D3DLOCK_READONLY) || level!=0) return;
    try {
        auto& c=State(); std::lock_guard guard(c.mutex); D3DSURFACE_DESC desc{}; Check(texture->GetLevelDesc(0,&desc));
        Require(locked && locked->pBits && desc.Width<=2048 && desc.Height<=2048 &&
            (desc.Format==D3DFMT_A8R8G8B8 || desc.Format==D3DFMT_X8R8G8B8),scene::Reason::resource);
        RECT box{0,0,LONG(desc.Width),LONG(desc.Height)}; if(rect) box=*rect;
        Require(box.left>=0 && box.top>=0 && box.right>box.left && box.bottom>box.top && box.right<=LONG(desc.Width) && box.bottom<=LONG(desc.Height),scene::Reason::resource);
        auto s=GetShadow(texture,true); Require(s!=nullptr,scene::Reason::resource); s->Resize(std::size_t(desc.Width)*desc.Height*4);
        if(flags&D3DLOCK_DISCARD) s->valid=false;
        s->rowBytes=(box.right-box.left)*4; Require(locked->Pitch>=INT(s->rowBytes),scene::Reason::resource);
        s->rows=box.bottom-box.top; s->pitch=locked->Pitch; s->destinationPitch=desc.Width*4;
        s->offset=(box.top*desc.Width+box.left)*4; s->pointer=static_cast<const std::uint8_t*>(locked->pBits);
        s->full=box.left==0 && box.top==0 && box.right==LONG(desc.Width) && box.bottom==LONG(desc.Height); s->pending=true;
    } catch(...) { Invalidate(texture); }
}
void BeforeUnlock(IDirect3DResource9* resource) noexcept {
    if(!Enabled()) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex); auto s=GetShadow(resource); if(!s || !s->pending) return;
        if(s->rows) for(UINT row=0;row<s->rows;++row) memcpy(s->bytes.data()+s->offset+row*s->destinationPitch,s->pointer+row*s->pitch,s->rowBytes);
        else memcpy(s->bytes.data()+s->offset,s->pointer,s->length);
        s->valid=s->valid || s->full; s->pending=false; s->pointer=nullptr;
    } catch(...) { Invalidate(resource); }
}
std::unique_ptr<scene::Draw> Draw(IDirect3DDevice9* device,D3DPRIMITIVETYPE type,UINT primitives,
    INT base,UINT start,UINT minimum,UINT count,const void* up,UINT stride,const void* upIndices,D3DFORMAT format,bool indexed) noexcept {
    if(!Enabled()) return {};
    std::unique_ptr<scene::Draw> out;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex); InvalidateTargets(device); if(!c.Selected()) return {};
        out=std::make_unique<scene::Draw>(); Target(c,device);
        Require(type==D3DPT_TRIANGLELIST && primitives>0 && primitives<=scene::MaxVertices/3,scene::Reason::topology);
        ReadState(device,*out);
        ComPtr<IDirect3DVertexBuffer9> vb; ComPtr<IDirect3DIndexBuffer9> ib; ComPtr<Shadow> vdata,idata;
        const std::uint8_t* source=static_cast<const std::uint8_t*>(up); std::uint64_t available=UINT_MAX; UINT offset=0;
        if(!up) {
            Check(device->GetStreamSource(0,&vb,&offset,&stride)); Require(vb!=nullptr,scene::Reason::resource);
            vdata=GetShadow(vb.Get()); Require(vdata && vdata->valid && !vdata->pending,scene::Reason::resource);
            Require(offset<=vdata->bytes.size(),scene::Reason::resource); source=vdata->bytes.data()+offset; available=vdata->bytes.size()-offset;
        }
        Require(stride>=sizeof(scene::Vertex) && stride<=4096,scene::Reason::topology);
        const std::uint8_t* indexSource=static_cast<const std::uint8_t*>(upIndices); std::uint64_t indexBytes=UINT_MAX;
        if(indexed && !upIndices) {
            Require(!up,scene::Reason::resource); Check(device->GetIndices(&ib)); Require(ib!=nullptr,scene::Reason::resource);
            idata=GetShadow(ib.Get()); Require(idata && idata->valid && !idata->pending,scene::Reason::resource);
            D3DINDEXBUFFER_DESC desc{}; Check(ib->GetDesc(&desc)); format=desc.Format;
            indexSource=idata->bytes.data(); indexBytes=idata->bytes.size();
        }
        Require(!indexed || format==D3DFMT_INDEX16 || format==D3DFMT_INDEX32,scene::Reason::topology);
        const UINT total=primitives*3, indexSize=format==D3DFMT_INDEX16?2:4;
        if(indexed) Require((std::uint64_t(start)+total)*indexSize<=indexBytes,scene::Reason::resource);
        std::unordered_map<std::uint32_t,std::uint32_t> remap;
        for(UINT i=0;i<total;++i) {
            std::uint32_t index{};
            if(indexed) {
                memcpy(&index,indexSource+(std::size_t(start)+i)*indexSize,indexSize);
                Require(index>=minimum && std::uint64_t(index)<std::uint64_t(minimum)+count,scene::Reason::resource);
            } else index=start+i;
            const std::int64_t adjusted=std::int64_t(index)+(indexed?base:0);
            Require(adjusted>=0 && std::uint64_t(adjusted)<=UINT_MAX && std::uint64_t(adjusted)*stride+sizeof(scene::Vertex)<=available,scene::Reason::resource);
            auto [it,added]=remap.emplace(static_cast<std::uint32_t>(adjusted),static_cast<std::uint32_t>(out->vertices.size()));
            if(added) { scene::Vertex v{}; memcpy(&v,source+std::size_t(adjusted)*stride,sizeof(v)); out->vertices.push_back(v); }
            out->indices.push_back(it->second);
        }
        scene::Identify(*out);
    } catch(scene::Reason reason) { if(out) out->failure=reason; }
    catch(...) { if(out) out->failure=scene::Reason::readback; else RejectSafe(scene::Reason::budget); }
    return out;
}
void Commit(std::unique_ptr<scene::Draw> draw,HRESULT result) noexcept {
    if(!draw || FAILED(result)) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex); if(!c.Selected()) return;
        draw->ordinal=c.scene.attempted++;
        if(draw->failure!=scene::Reason{}) { c.Reject(draw->failure,draw->ordinal); return; }
        const auto bytes=sizeof(scene::Draw)+draw->vertices.size()*sizeof(scene::Vertex)+draw->indices.size()*4+draw->texture.size();
        if(c.bytes+bytes>scene::MaxBytes/2 || c.scene.draws.size()>=scene::MaxDraws) { c.Reject(scene::Reason::budget,draw->ordinal); return; }
        c.bytes+=bytes; c.scene.draws.push_back(std::move(*draw));
    } catch(...) { RejectSafe(scene::Reason::budget); }
}
void Clear(IDirect3DDevice9* device,DWORD count,DWORD flags,D3DCOLOR color,HRESULT result) noexcept {
    if(!Enabled() || FAILED(result)) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex); InvalidateTargets(device); if(!c.Selected()) return;
        Target(c,device); D3DVIEWPORT9 vp{}; Check(device->GetViewport(&vp));
        DWORD scissor{}; Check(device->GetRenderState(D3DRS_SCISSORTESTENABLE,&scissor)); Require(!scissor,scene::Reason::clear);
        Require(count==0 && flags==D3DCLEAR_TARGET && c.scene.attempted==0 && vp.X==0 && vp.Y==0 && vp.Width==c.scene.width && vp.Height==c.scene.height,scene::Reason::clear);
        c.scene.cleared=true; c.scene.clearColor=color;
    } catch(scene::Reason r) { RejectSafe(r); }
    catch(...) { RejectSafe(scene::Reason::readback); }
}
void Unsupported(IDirect3DDevice9* device,HRESULT result) noexcept {
    if(!Enabled() || FAILED(result)) return;
    try { auto& c=State(); std::lock_guard lock(c.mutex); InvalidateTargets(device); if(c.Selected()) { Target(c,device); c.Reject(scene::Reason::operation); } }
    catch(scene::Reason r) { RejectSafe(r); } catch(...) { RejectSafe(scene::Reason::readback); }
}
void Reset(IDirect3DDevice9* device,HRESULT result) noexcept {
    if(!Enabled() || FAILED(result)) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex);
        if(c.Selected() && (c.scene.cleared || c.scene.attempted)) c.Reject(scene::Reason::operation);
        // A reset before this frame's first clear is a clean starting boundary.
        // Shadows are owned by native resources, so destroyed DEFAULT resources
        // disappear and surviving managed resources retain their valid payloads.
        if(c.Selected() && !c.scene.cleared && !c.scene.attempted) Target(c,device);
    } catch(...) { RejectSafe(scene::Reason::target); }
}
void Present(IDirect3DDevice9* device,const RECT* source,const RECT* destination,HWND window,const RGNDATA* dirty,DWORD flags,HRESULT result) noexcept {
    if(!Enabled() || result!=S_OK) return;
    try {
        auto& c=State(); std::lock_guard lock(c.mutex);
        if(c.Selected()) {
            try {
                Target(c,device);
                Require(!source && !destination && !window && !dirty && flags==0 && device->GetNumberOfSwapChains()==1,scene::Reason::target);
            } catch(scene::Reason r) { c.Reject(r); } catch(...) { c.Reject(scene::Reason::readback); }
            c.done=true; if(!c.scene.cleared) c.Reject(scene::Reason::clear);
            if(!c.scene.width) { c.scene.width=1; c.scene.height=1; }
            try { scene::Save(c.scene,c.path); Event(0,"SceneSaved",S_OK); }
            catch(...) { Event(0,"SceneSaveFailed",E_FAIL); OutputDebugStringW(L"RRT: scene save failed; existing files are never overwritten.\n"); }
            c.scene.draws.clear();
        }
        ++c.frame;
    } catch(...) {}
}
void Present(IDirect3DSwapChain9* swapchain,const RECT* source,const RECT* destination,HWND window,const RGNDATA* dirty,DWORD flags,HRESULT result) noexcept {
    if(!Enabled()) return;
    ComPtr<IDirect3DDevice9> device;
    if(SUCCEEDED(swapchain->GetDevice(&device))) Present(device.Get(),source,destination,window,dirty,flags,result);
}
}
