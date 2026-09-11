#pragma once
#include "snapshot.h"
#include <memory>
#include <string>
#include <wrl/client.h>
namespace rrt::shader::hook {
void Lock(IDirect3DResource9*,UINT,UINT,void*,DWORD) noexcept;
void BeforeUnlock(IDirect3DResource9*) noexcept;
void AfterUnlock(IDirect3DResource9*,HRESULT) noexcept;
void Invalidate(IDirect3DResource9*) noexcept;
void Constants(std::uint64_t,UINT,UINT,HRESULT) noexcept;
void PixelConstants(std::uint64_t,UINT,UINT,HRESULT) noexcept;
void TextureCreated(IDirect3DTexture9*,bool) noexcept;
void TextureReset(HRESULT) noexcept;
void TextureInvalidate(IDirect3DResource9*,const char* reason="unknown") noexcept;
void TextureLock(IDirect3DTexture9*,UINT,const D3DLOCKED_RECT*,const RECT*,DWORD,HRESULT) noexcept;
void TextureBeforeUnlock(IDirect3DTexture9*,UINT) noexcept;
void TextureAfterUnlock(IDirect3DTexture9*,UINT,HRESULT) noexcept;
bool SurfaceTextureTracked(IDirect3DResource9*) noexcept;
void SurfaceTextureLock(IDirect3DSurface9*,const D3DLOCKED_RECT*,const RECT*,DWORD,HRESULT) noexcept;
void SurfaceTextureBeforeUnlock(IDirect3DSurface9*) noexcept;
void SurfaceTextureAfterUnlock(IDirect3DSurface9*,HRESULT) noexcept;
void TextureDirty(IDirect3DTexture9*,const RECT*,HRESULT) noexcept;
struct TextureUploadPending {
    Microsoft::WRL::ComPtr<IDirect3DTexture9> source,destination;
    std::uint64_t sourceId{},sourceRevision{},destinationRevision{},epoch{};
    const char* dirtyProof{};
};
std::unique_ptr<TextureUploadPending> BeforeTextureUpload(IDirect3DBaseTexture9*,IDirect3DBaseTexture9*) noexcept;
void AfterTextureUpload(std::unique_ptr<TextureUploadPending>,HRESULT) noexcept;
struct SurfaceTransfer {
    std::uint64_t source{},revision{};UINT sourceLevel{},destinationLevel{},sourceWidth{},sourceHeight{};
    RECT rect{};POINT destination{};
};
struct SurfaceUploadPending : TextureUploadPending {SurfaceTransfer transfer;RECT blocks{};POINT destinationBlocks{};};
std::unique_ptr<SurfaceUploadPending> BeforeSurfaceUpload(IDirect3DSurface9*,const RECT*,IDirect3DSurface9*,const POINT*) noexcept;
void AfterSurfaceUpload(std::unique_ptr<SurfaceUploadPending>,HRESULT) noexcept;
void Boundary(std::uint64_t,int,HRESULT) noexcept; // 0 reset, 1 begin, 2 end
void Applied(HRESULT) noexcept;
void Retire(std::uint64_t) noexcept;
void CompositionBoundary(std::uint64_t,bool,HRESULT) noexcept;
void CreatedTarget(std::uint64_t,IDirect3DResource9*,bool,bool) noexcept;
struct WriterPending {bool active{};std::uint64_t device{},target{},depth{},epoch{},resource{};const char* operation{};int access{};};
WriterPending BeforeWriter(std::uint64_t,IDirect3DDevice9*,IDirect3DResource9*,const char*,int=0) noexcept;
void AfterWriter(WriterPending,HRESULT) noexcept;
bool BeforeColorState() noexcept;
void AfterColorState(bool) noexcept;
struct ClearPending {std::string record,scope="null";std::uint64_t serial{};};
std::unique_ptr<ClearPending> BeforeClear(std::uint64_t,IDirect3DDevice9*,DWORD,const D3DRECT*,DWORD,D3DCOLOR,float,DWORD) noexcept;
void AfterClear(std::uint64_t,std::unique_ptr<ClearPending>,HRESULT) noexcept;
bool FrameSampling() noexcept;
void Presented(std::uint64_t,HRESULT) noexcept;
struct Pending { std::vector<std::uint8_t> bytes; const char* failure{}; bool position{},sampled{},composition{};std::uint64_t device{},epoch{},interval{},clearSerial{},bindingSerial{},writeSerial{},ordinal{};std::string record,reason,selectionObserved,stage,failureStage,detail,textureDiagnostic; };
std::unique_ptr<Pending> BeforeDraw(std::uint64_t,IDirect3DDevice9*,D3DPRIMITIVETYPE,Draw) noexcept;
void Commit(std::unique_ptr<Pending>,HRESULT) noexcept;
}
