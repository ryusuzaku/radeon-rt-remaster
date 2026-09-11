#include "observers.h"
#include "../trace/trace.h"
#include "../capture/capture.h"
#include "../shader/intercept.h"
#include "../shader/inventory.h"
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>

namespace rrt {
namespace {
struct Entry;
struct Registry {
    std::recursive_mutex mutex;
    std::unordered_map<IUnknown*, Entry*> native;
    std::unordered_map<IUnknown*, Entry*> wrapped;
    std::uint64_t nextId{1};
};
Registry& Objects() { static auto* registry=new Registry; return *registry; }
struct Entry {
    IUnknown* native{};
    IUnknown* wrapper{};
    IUnknown* identity{};
    ULONG references{1};
    std::uint64_t id{};
    const char* type{};
    virtual ~Entry() { native->Release(); }
    virtual bool Supports(REFIID iid) const noexcept=0;
    ULONG Retain() noexcept { auto& r=Objects(); std::lock_guard lock(r.mutex); return ++references; }
    ULONG Drop() noexcept {
        ULONG remaining;
        { auto& r=Objects(); std::lock_guard lock(r.mutex); remaining=--references;
          if(!remaining) { r.native.erase(identity); r.wrapped.erase(wrapper); }
        }
        if(!remaining) { shader::hook::Retire(id); Event(id,"ObjectDestroyed",S_OK); delete this; }
        return remaining;
    }
};
template<class T> struct Observer : T, Entry {
    T* inner_;
    Observer(T* inner, const char* name) : inner_(inner) { native=inner; wrapper=static_cast<T*>(this); type=name; }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** output) override {
        if(!output) return E_POINTER;
        *output=nullptr;
        if(!Supports(iid)) { Event(id,"UnsupportedQueryInterface",E_NOINTERFACE); return E_NOINTERFACE; }
        *output=static_cast<T*>(this); Retain(); return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return Retain(); }
    ULONG STDMETHODCALLTYPE Release() override { return Drop(); }
};

void SwapPresented(IDirect3DSwapChain9* chain,HRESULT hr) noexcept {
    if(hr!=S_OK||!shader::hook::FrameSampling())return;
    IDirect3DDevice9* device{};if(FAILED(chain->GetDevice(&device)))return;
    IUnknown* identity{};auto status=device->QueryInterface(__uuidof(IUnknown),reinterpret_cast<void**>(&identity));device->Release();
    if(FAILED(status))return;
    std::uint64_t id{};
    {auto& r=Objects();std::lock_guard lock(r.mutex);auto it=r.native.find(identity);if(it!=r.native.end())id=it->second->id;}
    identity->Release();if(id)shader::hook::Presented(id,hr);
}

// Checked-in mechanically generated forwards; no vtable memory patches.
#include "generated_observers.inc"

template<class Interface, class Wrapper> Entry* TryMake(IUnknown* original) {
    Interface* typed{};
    if(FAILED(original->QueryInterface(__uuidof(Interface),reinterpret_cast<void**>(&typed)))) return nullptr;
    try { return new Wrapper(typed); } catch(...) { typed->Release(); throw; }
}
Entry* Make(IUnknown* original) {
#include "generated_factory.inc"
    return nullptr;
}
}
HRESULT WrapReturned(REFIID iid, void** output) noexcept {
    if(!output || !*output) return S_OK;
    auto* raw=static_cast<IUnknown*>(*output);
    try {
        IUnknown* identity{};
        HRESULT result=raw->QueryInterface(__uuidof(IUnknown),reinterpret_cast<void**>(&identity));
        if(FAILED(result)) { raw->Release(); *output=nullptr; return result; }
        identity->Release();
        auto& registry=Objects(); std::lock_guard lock(registry.mutex);
        if(auto it=registry.native.find(identity); it!=registry.native.end()) {
            Entry* e=it->second;
            if(!e->Supports(iid)) { raw->Release(); *output=nullptr; return E_NOINTERFACE; }
            e->Retain(); raw->Release(); *output=e->wrapper; return S_OK;
        }
        std::unique_ptr<Entry> entry(Make(raw));
        if(!entry || !entry->Supports(iid)) { raw->Release(); *output=nullptr; return E_NOINTERFACE; }
        entry->identity=identity; entry->id=registry.nextId++;
        registry.native.emplace(identity,entry.get());
        try { registry.wrapped.emplace(entry->wrapper,entry.get()); }
        catch(...) { registry.native.erase(identity); throw; }
        *output=entry->wrapper;
        try { Event(entry->id,"ObjectCreated",S_OK,std::string("\"interface\":\"")+entry->type+"\""); }
        catch(...) { /* Diagnostics allocation must not invalidate a registered wrapper. */ }
        entry.release(); raw->Release(); return S_OK;
    } catch(...) { raw->Release(); *output=nullptr; return E_OUTOFMEMORY; }
}
IUnknown* UnwrapUnknown(IUnknown* object) noexcept {
    if(!object) return nullptr;
    auto& r=Objects(); std::lock_guard lock(r.mutex);
    auto it=r.wrapped.find(object); return it==r.wrapped.end()?object:it->second->native;
}
std::uint64_t ObjectId(IUnknown* object) noexcept {
    if(!object) return 0;
    auto& r=Objects(); std::lock_guard lock(r.mutex);
    auto it=r.wrapped.find(object); return it==r.wrapped.end()?0:it->second->id;
}
}
