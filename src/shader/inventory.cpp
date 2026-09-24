#include "inventory.h"
#include <wrl/client.h>
#include <mutex>
#include <array>
#include <stdexcept>

namespace rrt::shader::inventory {
using Microsoft::WRL::ComPtr;
namespace {
constexpr std::size_t MaxBytes=16*1024*1024;
std::wstring Env(const wchar_t* key){wchar_t value[32768]{};auto n=GetEnvironmentVariableW(key,value,32768);return n&&n<32768?value:L"";}
void Need(bool ok){if(!ok)throw std::runtime_error("inventory query rejected");}
std::string Hex(const void* data,std::size_t n){static const char h[]="0123456789abcdef";auto p=static_cast<const unsigned char*>(data);std::string s;s.reserve(n*2);for(std::size_t i=0;i<n;++i){s+=h[p[i]>>4];s+=h[p[i]&15];}return s;}
template<class T> std::string Program(T* shader){
    if(!shader)return "null";
    UINT size{};Need(SUCCEEDED(shader->GetFunction(nullptr,&size))&&size&&size<=16384&&size%4==0);
    std::vector<DWORD> code(size/4);const auto expected=size;
    Need(SUCCEEDED(shader->GetFunction(code.data(),&size))&&size==expected);
    return "\""+Hex(code.data(),size)+"\"";
}
struct Context {
    std::mutex mutex;std::wstring path=Env(L"RRT_SHADER_INVENTORY_FILE"),trigger=Env(L"RRT_SHADER_INVENTORY_TRIGGER_FILE");
    HANDLE file=INVALID_HANDLE_VALUE;std::size_t bytes{};std::uint64_t issued{},committed{},nextProbe{};unsigned limit=512;bool done{};
    Context(){auto v=Env(L"RRT_SHADER_INVENTORY_DRAWS");if(!v.empty()){wchar_t* end{};auto n=wcstoul(v.c_str(),&end,10);if(*end||v[0]==L'-'||!n||n>4096)done=true;else limit=n;}}
    bool Write(const std::string& line){DWORD written{};bool ok=WriteFile(file,line.data(),static_cast<DWORD>(line.size()),&written,nullptr)&&written==line.size();bytes+=written;return ok;}
    void Stop(const char* reason){if(file!=INVALID_HANDLE_VALUE){Write(std::string("{\"kind\":\"end\",\"reason\":\"")+reason+"\",\"committed\":"+std::to_string(committed)+"}\n");CloseHandle(file);file=INVALID_HANDLE_VALUE;}done=true;}
    bool Start(){
        if(done||path.empty()||issued>=limit)return false;
        if(file!=INVALID_HANDLE_VALUE)return true;
        if(!trigger.empty()){auto now=GetTickCount64();if(now<nextProbe)return false;nextProbe=now+100;auto a=GetFileAttributesW(trigger.c_str());if(a==INVALID_FILE_ATTRIBUTES||(a&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return false;}
        file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file==INVALID_HANDLE_VALUE){done=true;return false;}
        if(!Write("{\"kind\":\"header\",\"schema\":\"rrt-shader-inventory\",\"version\":1,\"draw_limit\":"+std::to_string(limit)+"}\n")){Stop("io_error");return false;}return true;
    }
};
Context& State(){static auto* c=new Context;return *c;}
}
std::unique_ptr<Pending> BeforeDraw(std::uint64_t id,IDirect3DDevice9* d,D3DPRIMITIVETYPE type) noexcept {
    std::unique_ptr<Pending> p;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Start())return {};
        p=std::make_unique<Pending>();p->ordinal=c.issued++;p->payload="\"query\":\"unavailable\"";
        ComPtr<IDirect3DVertexShader9> vs;ComPtr<IDirect3DPixelShader9> ps;ComPtr<IDirect3DVertexDeclaration9> decl;
        Need(SUCCEEDED(d->GetVertexShader(&vs))&&SUCCEEDED(d->GetPixelShader(&ps))&&SUCCEEDED(d->GetVertexDeclaration(&decl))&&decl);
        std::array<D3DVERTEXELEMENT9,65> elements{};UINT count=65;
        Need(SUCCEEDED(decl->GetDeclaration(elements.data(),&count))&&count&&count<=65&&elements[count-1].Stream==0xff);
        std::array<bool,16> seen{};std::string streams="[";bool first=true;
        for(UINT i=0;i+1<count;++i){auto slot=elements[i].Stream;Need(slot<16);if(seen[slot])continue;seen[slot]=true;
            ComPtr<IDirect3DVertexBuffer9> buffer;UINT offset{},stride{},frequency{};
            Need(SUCCEEDED(d->GetStreamSource(slot,&buffer,&offset,&stride))&&SUCCEEDED(d->GetStreamSourceFreq(slot,&frequency)));
            if(!first)streams+=",";first=false;
            streams+="["+std::to_string(slot)+","+std::to_string(offset)+","+std::to_string(stride)+","+std::to_string(frequency)+","+(buffer?"1":"0")+"]";
        }streams+="]";
        ComPtr<IDirect3DIndexBuffer9> ib;D3DINDEXBUFFER_DESC desc{};Need(SUCCEEDED(d->GetIndices(&ib))&&ib&&SUCCEEDED(ib->GetDesc(&desc)));
        p->payload="\"query\":\"ok\",\"device\":"+std::to_string(id)+",\"topology\":"+std::to_string(type)+",\"vs\":"+Program(vs.Get())+",\"ps\":"+Program(ps.Get())+",\"declaration\":\""+Hex(elements.data(),count*sizeof(elements[0]))+"\",\"streams\":"+streams+",\"index_format\":"+std::to_string(desc.Format);
    }catch(...){}return p;
}
void Commit(std::unique_ptr<Pending> p,HRESULT hr) noexcept {
    if(!p)return;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(c.done)return;
        auto line="{\"kind\":\"draw\",\"ordinal\":"+std::to_string(p->ordinal)+",\"hr\":"+std::to_string(static_cast<std::int32_t>(hr))+","+p->payload+"}\n";
        if(c.bytes+line.size()+256>MaxBytes){c.Stop("byte_limit");return;}
        if(!c.Write(line)){c.Stop("io_error");return;}++c.committed;
        if(c.committed==c.limit)c.Stop("draw_limit");
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);c.Stop("internal_error");}catch(...){}}
}
}
