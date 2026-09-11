#include "scene.h"
#include <bcrypt.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace rrt::scene {
namespace {
void Require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
struct Bytes {
    std::vector<std::uint8_t> data;
    void Put(const void* p,std::size_t n) {
        Require(n<=MaxBytes && data.size()<=MaxBytes-n,"scene byte budget exceeded");
        if(n) { auto* b=static_cast<const std::uint8_t*>(p); data.insert(data.end(),b,b+n); }
    }
    template<class T> void Pod(const T& v) { static_assert(std::is_trivially_copyable_v<T>); Put(&v,sizeof(v)); }
};
struct Reader {
    const std::vector<std::uint8_t>& data; std::size_t cursor{};
    void Get(void* p,std::size_t n) { Require(n<=data.size()-cursor,"truncated scene"); if(n) memcpy(p,data.data()+cursor,n); cursor+=n; }
    template<class T> T Pod() { T v{}; Get(&v,sizeof(v)); return v; }
    template<class T> std::vector<T> Vector(std::uint32_t n,std::uint32_t cap) {
        Require(n<=cap && std::uint64_t(n)*sizeof(T)<=data.size()-cursor,"invalid scene array size");
        std::vector<T> result(n); Get(result.data(),result.size()*sizeof(T)); return result;
    }
};
}
Hash Digest(const void* data,std::size_t size) {
    Require(size<=MaxBytes,"hash input too large"); Hash hash{};
    Require(BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,
        const_cast<PUCHAR>(static_cast<const UCHAR*>(data)),static_cast<ULONG>(size),hash.data(),32)>=0,"SHA256 failed");
    return hash;
}
std::string Hex(const Hash& hash) { std::string s; for(auto b:hash) { s+="0123456789abcdef"[b>>4]; s+="0123456789abcdef"[b&15]; } return s; }
void Identify(Draw& d) {
    Bytes mesh; mesh.Pod(static_cast<std::uint32_t>(d.vertices.size())); mesh.Pod(static_cast<std::uint32_t>(d.indices.size()));
    mesh.Put(d.vertices.data(),d.vertices.size()*sizeof(Vertex)); mesh.Put(d.indices.data(),d.indices.size()*4);
    d.meshId=Digest(mesh.data.data(),mesh.data.size());
    Bytes texture; texture.Pod(d.width); texture.Pod(d.height); texture.Put(d.texture.data(),d.texture.size());
    d.textureId=Digest(texture.data.data(),texture.data.size());
    Bytes material; material.Pod(d.textureId); material.Pod(d.state.render); material.Pod(d.state.texture); material.Pod(d.state.sampler);
    d.materialId=Digest(material.data.data(),material.data.size());
}
const char* ReasonName(Reason r) {
    switch(r) {
    case Reason::shader:return "programmable_shader"; case Reason::topology:return "unsupported_topology_or_fvf";
    case Reason::state:return "unsupported_fixed_function_state"; case Reason::resource:return "missing_or_invalid_resource_payload";
    case Reason::target:return "unsupported_render_target"; case Reason::budget:return "capture_budget_exceeded";
    case Reason::readback:return "state_query_or_capture_failure"; case Reason::clear:return "unsupported_or_missing_clear";
    case Reason::operation:return "unsupported_frame_operation"; case Reason::multipleDevices:return "multiple_devices";
    default:return "invalid_reason";
    }
}
void Validate(const Scene& s) {
    Require(s.width>0 && s.height>0 && s.width<=4096 && s.height<=4096,"invalid scene dimensions");
    Require(s.draws.size()<=MaxDraws && s.rejected.size()<=MaxDraws+1,"too many records");
    Require(s.cleared || !s.rejected.empty(),"scene has no initial clear");
    Require(!s.rejected.empty() || s.attempted==s.draws.size(),"complete scene omits draws");
    std::uint32_t previous=0; bool first=true;
    for(auto& d:s.draws) {
        Require(d.ordinal<s.attempted && (first || d.ordinal>previous),"invalid draw ordinal"); first=false; previous=d.ordinal;
        Require(!d.vertices.empty() && d.vertices.size()<=MaxVertices && !d.indices.empty() && d.indices.size()%3==0 && d.indices.size()<=MaxVertices*3,"invalid geometry counts");
        for(auto& v:d.vertices) Require(std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z)&&std::isfinite(v.u)&&std::isfinite(v.v),"nonfinite vertex");
        for(auto i:d.indices) Require(i<d.vertices.size(),"index outside vertex array");
        Require(d.width>0 && d.height>0 && d.width<=2048 && d.height<=2048 && std::uint64_t(d.width)*d.height*4==d.texture.size(),"invalid texture dimensions");
        auto& vp=d.state.viewport;
        Require(vp.Width>0 && vp.Height>0 && std::uint64_t(vp.X)+vp.Width<=s.width && std::uint64_t(vp.Y)+vp.Height<=s.height &&
            std::isfinite(vp.MinZ)&&std::isfinite(vp.MaxZ)&&vp.MinZ>=0&&vp.MaxZ<=1&&vp.MinZ<=vp.MaxZ,"invalid viewport");
        for(auto* matrix:{&d.state.world,&d.state.view,&d.state.projection})
            for(auto& row:matrix->m) for(float value:row) Require(std::isfinite(value),"nonfinite transform");
        const auto& rs=d.state.render;
        for(auto slot:{0,13,14,15,17,19,20}) Require(rs[slot]==0,"scene uses unsupported render state");
        Require(rs[1]==D3DFILL_SOLID,"scene uses unsupported fill mode");
        auto& ts=d.state.texture; auto& sampler=d.state.sampler;
        Require(ts[0]==D3DTOP_MODULATE && ts[1]==D3DTA_TEXTURE && ts[2]==D3DTA_DIFFUSE && ts[3]==D3DTOP_SELECTARG1 &&
            ts[4]==D3DTA_TEXTURE && ts[6]==0 && ts[7]==0 && sampler[6]==D3DTEXF_NONE && sampler[8]==0,"scene uses unsupported texture state");
    }
    for(auto& r:s.rejected) Require(static_cast<unsigned>(r.reason)>=1 && static_cast<unsigned>(r.reason)<=10,"invalid rejection reason");
}
void Save(const Scene& s,const std::filesystem::path& path) {
    Validate(s); Bytes b; b.Put("RRTSCN1\0",8); b.Pod(Version); b.Pod(s.frame); b.Pod(s.width); b.Pod(s.height); b.Pod(s.clearColor);
    b.Pod(s.attempted); b.Pod(std::uint32_t(s.cleared)); b.Pod(std::uint32_t(s.draws.size())); b.Pod(std::uint32_t(s.rejected.size()));
    for(auto& r:s.rejected) { b.Pod(r.ordinal); b.Pod(r.reason); }
    for(auto& d:s.draws) {
        b.Pod(d.ordinal); b.Pod(d.width); b.Pod(d.height); b.Pod(std::uint32_t(d.vertices.size())); b.Pod(std::uint32_t(d.indices.size()));
        b.Pod(d.meshId); b.Pod(d.textureId); b.Pod(d.materialId); b.Pod(d.state);
        b.Put(d.vertices.data(),d.vertices.size()*sizeof(Vertex)); b.Put(d.indices.data(),d.indices.size()*4); b.Put(d.texture.data(),d.texture.size());
    }
    const auto checksum=Digest(b.data.data(),b.data.size()); b.Pod(checksum);
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    Require(file!=INVALID_HANDLE_VALUE,"cannot create scene (existing file or unavailable path)");
    DWORD written{}; const bool ok=WriteFile(file,b.data.data(),static_cast<DWORD>(b.data.size()),&written,nullptr) && written==b.data.size();
    CloseHandle(file); Require(ok,"scene write failed (incomplete file retained)");
}
Scene Load(const std::filesystem::path& path,Hash* sourceDigest) {
    std::ifstream f(path,std::ios::binary|std::ios::ate); Require(f.good(),"cannot open scene");
    auto length=f.tellg(); Require(length>=76 && length<=MaxBytes,"invalid scene file size");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(length)); f.seekg(0); f.read(reinterpret_cast<char*>(bytes.data()),bytes.size()); Require(f.good(),"scene read failed");
    Hash checksum{}; memcpy(checksum.data(),bytes.data()+bytes.size()-32,32);
    Require(checksum==Digest(bytes.data(),bytes.size()-32),"scene checksum mismatch"); bytes.resize(bytes.size()-32);
    Reader r{bytes}; char magic[8]; r.Get(magic,8); Require(memcmp(magic,"RRTSCN1\0",8)==0,"invalid scene magic"); Require(r.Pod<std::uint32_t>()==Version,"unsupported scene version");
    Scene s; s.frame=r.Pod<std::uint32_t>(); s.width=r.Pod<std::uint32_t>(); s.height=r.Pod<std::uint32_t>(); s.clearColor=r.Pod<std::uint32_t>(); s.attempted=r.Pod<std::uint32_t>();
    auto cleared=r.Pod<std::uint32_t>(); Require(cleared<=1,"invalid clear flag"); s.cleared=cleared!=0;
    auto draws=r.Pod<std::uint32_t>(),rejects=r.Pod<std::uint32_t>(); Require(draws<=MaxDraws && rejects<=MaxDraws+1,"too many scene records");
    for(std::uint32_t i=0;i<rejects;++i) s.rejected.push_back({r.Pod<std::uint32_t>(),r.Pod<Reason>()});
    for(std::uint32_t i=0;i<draws;++i) {
        Draw d; d.ordinal=r.Pod<std::uint32_t>(); d.width=r.Pod<std::uint32_t>(); d.height=r.Pod<std::uint32_t>();
        auto vertices=r.Pod<std::uint32_t>(),indices=r.Pod<std::uint32_t>();
        auto mesh=r.Pod<Hash>(),texture=r.Pod<Hash>(),material=r.Pod<Hash>(); d.state=r.Pod<State>();
        d.vertices=r.Vector<Vertex>(vertices,MaxVertices); d.indices=r.Vector<std::uint32_t>(indices,MaxVertices*3);
        Require(d.width<=2048 && d.height<=2048,"texture exceeds budget"); d.texture=r.Vector<std::uint8_t>(d.width*d.height*4,MaxResourceBytes);
        Identify(d); Require(d.meshId==mesh && d.textureId==texture && d.materialId==material,"asset hash mismatch"); s.draws.push_back(std::move(d));
    }
    Require(r.cursor==bytes.size(),"trailing scene data"); Validate(s); if(sourceDigest) *sourceDigest=checksum; return s;
}
}
