#pragma once
#include <windows.h>
#include <d3d9.h>

namespace rrt {
// Consumes the native reference in *object, replacing it with an identity-preserving
// wrapper reference. Unknown private extension interfaces are explicitly rejected.
HRESULT WrapReturned(REFIID iid, void** object) noexcept;
IUnknown* UnwrapUnknown(IUnknown* object) noexcept;
template<class T> T* Unwrap(T* object) noexcept {
    return reinterpret_cast<T*>(UnwrapUnknown(object));
}
}
