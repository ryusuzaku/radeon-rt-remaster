#pragma once
#include "../scene/scene.h"
#include <memory>

namespace rrt::capture {
// All interception boundaries are noexcept; capture failure never changes D3D results.
bool Enabled() noexcept;
void BufferLock(IDirect3DResource9* resource,UINT offset,UINT size,void* data,DWORD flags) noexcept;
void TextureLock(IDirect3DTexture9* texture,UINT level,const D3DLOCKED_RECT* lock,const RECT* rect,DWORD flags) noexcept;
void BeforeUnlock(IDirect3DResource9* resource) noexcept;
void Invalidate(IDirect3DResource9* resource) noexcept;
void SurfaceWrite(IDirect3DSurface9* surface) noexcept;
std::unique_ptr<scene::Draw> Draw(IDirect3DDevice9* device,D3DPRIMITIVETYPE type,UINT primitives,
    INT base,UINT start,UINT minimum,UINT count,const void* vertices,UINT stride,const void* indices,D3DFORMAT format,bool indexed) noexcept;
void Commit(std::unique_ptr<scene::Draw> draw,HRESULT result) noexcept;
void Clear(IDirect3DDevice9* device,DWORD count,DWORD flags,D3DCOLOR color,HRESULT result) noexcept;
void Unsupported(IDirect3DDevice9* device,HRESULT result) noexcept;
void Reset(IDirect3DDevice9* device,HRESULT result) noexcept;
void Present(IDirect3DDevice9* device,const RECT* source,const RECT* destination,HWND window,const RGNDATA* dirty,DWORD flags,HRESULT result) noexcept;
void Present(IDirect3DSwapChain9* swapchain,const RECT* source,const RECT* destination,HWND window,const RGNDATA* dirty,DWORD flags,HRESULT result) noexcept;
}
