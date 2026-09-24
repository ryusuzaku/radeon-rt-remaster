#include "intercept.h"
#include "position_capture.h"
#include "color_contract.h"
#include "../scene/scene.h"
#include <cmath>
#include <wrl/client.h>
#include <mutex>
#include <atomic>
#include <unordered_map>
#include <algorithm>
#include <cstring>
#include <bcrypt.h>
namespace rrt::shader::hook {
using Microsoft::WRL::ComPtr;
namespace {
const GUID Guid={0xeb57f441,0x62a7,0x44c8,{0x99,0x12,0x14,0x2e,0x58,0x9a,0x77,0x1a}};
std::atomic<std::size_t>& Retained(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
// The shared ceiling is one counter, but attribution is what a budget decision needs: buffer
// shadows and texture shadows are charged and released alongside it so the footer can report both.
std::atomic<std::size_t>& RetainedBuffers(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
std::atomic<std::size_t>& RetainedTextures(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
std::atomic<std::size_t>& LiveTextures(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
// A texture can be refused against the ceiling only when the live total was higher than it is when
// the capture stops, so the split that decides policy is the one at the high-water mark.
std::atomic<std::size_t>& RetainedPeak(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
std::atomic<std::size_t>& PeakBuffers(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
std::atomic<std::size_t>& PeakTextures(){static auto* n=new std::atomic<std::size_t>{0};return *n;}
// Sampled from the authoritative split counters at whichever charge raises the total, so the split
// always adds up to the reported peak. Charges hold the state mutex; releases may not, so a torn
// sample is possible in principle and the peak is a diagnostic, never an admission input.
void UpdateRetainedPeak(){
    const auto buffers=RetainedBuffers().load(),textures=RetainedTextures().load(),total=buffers+textures;
    auto peak=RetainedPeak().load();
    while(total>peak&&!RetainedPeak().compare_exchange_weak(peak,total)){}
    if(total>=RetainedPeak().load()){PeakBuffers().store(buffers);PeakTextures().store(textures);}
}
std::atomic<std::uint64_t>& ShadowIds(){static auto* n=new std::atomic<std::uint64_t>{1};return *n;}
#include "texture_shadow.inc"
struct Shadow final:IUnknown {
    std::unique_ptr<TextureShadow> texture;const char* textureAdmission="unobserved";
    const std::uint64_t id=ShadowIds().fetch_add(1);std::uint64_t revision{};
    bool createdTarget{},privateTarget{},lockable{};std::uint64_t owner{},createdEpoch{};
    std::atomic<ULONG> refs{1};std::vector<std::uint8_t> bytes,known;
    const std::uint8_t* pointer{};UINT offset{},length{};bool pending{};
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid,void** p) override {if(!p)return E_POINTER;*p=nullptr;if(iid!=__uuidof(IUnknown))return E_NOINTERFACE;*p=this;AddRef();return S_OK;}
    ULONG STDMETHODCALLTYPE AddRef() override{return ++refs;}
    ULONG STDMETHODCALLTYPE Release() override{auto n=--refs;if(!n)delete this;return n;}
    ~Shadow(){const auto released=bytes.size()*2;Retained().fetch_sub(released);RetainedBuffers().fetch_sub(released);}
};
struct Knowledge {std::array<bool,61> constants{};std::array<bool,31> pixelConstants{};bool recording{},reserved{};std::uint64_t resetEpoch{},revision{},interval{},drawSequence{},clearSerial{},bindingSerial{};UINT samples{};std::string lastClear="null",lastClearScope="null";};
struct WriteEvent {WriterPending call;HRESULT hr{};std::uint64_t serial{},clearSerial{};std::int64_t ordinal=-1;};
// Capture ledger versions. The ladder is ordered and cumulative: each level adds
// evidence to the one below it, and the environment parser enforces that a level
// cannot be enabled without its predecessor. The version written into the ledger
// header is therefore the highest enabled level -- a fold over the flags, not an
// independent set of them.
//
// Levels 2..4 are emitted by the other header paths below (baseline, frame
// sampling, fixed-target selection) and are not part of this ladder.
//
// Adding a level means updating this enum, Level(), docs/schemas/capture-version.json
// and the accepted set in tools/inspect_position_capture.py.
// tests/verify_capture_version_contract.py fails if those disagree.
enum class CaptureLevel : int {
    Bounded           = 5,  // multi-draw baseline, no evidence level enabled
    RenderState       = 6,
    ClearEvidence     = 7,
    WriteEvidence     = 8,
    SurfaceScope      = 9,
    ColorReplay       = 10,
    MaterialInputs    = 11,
    PixelMaterial     = 12,
    TextureInputs     = 13,
    ExternalTextures  = 14,
    CompressedTextures= 15,
    TextureUploads    = 16,
    DirtyTextures     = 17,
    SurfaceUploads    = 18,
    SurfaceLocks      = 19,
};
struct Context {
    std::unordered_map<std::string,unsigned> selectionRejections,shaderRejections;
    std::recursive_mutex mutex;std::wstring path;std::uint64_t ordinal{},target{};bool done{};
    std::unordered_map<std::uint64_t,Knowledge> devices;
    bool positionMode{},triggered{};std::wstring trigger;std::uint64_t nextProbe{},attempts{},captured{};HANDLE file=INVALID_HANDLE_VALUE;std::size_t written{};
    bool frameSampling{};std::string session;std::uint64_t presents{};
    UINT targetWidth{},targetHeight{},minPrimitives{};
    bool anyTarget{};
    bool multiDraw{};
    bool renderState{};
    bool clearEvidence{};
    bool writeEvidence{},writeGap{},overlap{};unsigned inFlight{};
    bool surfaceScope{},accessGap{};std::unordered_map<std::uint64_t,int> accesses;
    bool colorReplay{},materialInputs{},pixelMaterial{},textureInputs{},externalTextures{},compressedTextures{},textureUploads{},dirtyTextures{},surfaceUploads{},surfaceLocks{};std::uint64_t textureEpoch{};
    std::uint64_t assetBytes{};UINT assetFileCount{};std::unordered_map<std::string,std::size_t> assetFiles;
    std::uint64_t writeSerial{};std::array<WriteEvent,64> writes{};
    UINT CaptureLimit() const{return multiDraw?16:4;}
    UINT IntervalLimit() const{return multiDraw?4:1;}
    // Highest enabled level wins. The parser above guarantees the ladder is
    // contiguous, so a highest-first scan is both correct and the single place to
    // edit when a level is added. Ordered highest-first deliberately.
    CaptureLevel Level() const{
        struct Entry{bool enabled;CaptureLevel level;};
        const Entry entries[]={
            {surfaceLocks,CaptureLevel::SurfaceLocks},
            {surfaceUploads,CaptureLevel::SurfaceUploads},
            {dirtyTextures,CaptureLevel::DirtyTextures},
            {textureUploads,CaptureLevel::TextureUploads},
            {compressedTextures,CaptureLevel::CompressedTextures},
            {externalTextures,CaptureLevel::ExternalTextures},
            {textureInputs,CaptureLevel::TextureInputs},
            {pixelMaterial,CaptureLevel::PixelMaterial},
            {materialInputs,CaptureLevel::MaterialInputs},
            {colorReplay,CaptureLevel::ColorReplay},
            {surfaceScope,CaptureLevel::SurfaceScope},
            {writeEvidence,CaptureLevel::WriteEvidence},
            {clearEvidence,CaptureLevel::ClearEvidence},
            {renderState,CaptureLevel::RenderState},
        };
        for(const auto& entry:entries)if(entry.enabled)return entry.level;
        return CaptureLevel::Bounded;
    }
    Context(){wchar_t p[32768]{};auto n=GetEnvironmentVariableW(L"RRT_SHADER_SNAPSHOT_FILE",p,32768);if(n && n<32768)path=p;
        wchar_t draw[32]{};n=GetEnvironmentVariableW(L"RRT_SHADER_SNAPSHOT_DRAW",draw,32);if(n){wchar_t* end{};target=wcstoull(draw,&end,10);if(n>=32 || *end || draw[0]==L'-' || target>10000)path.clear();}
        n=GetEnvironmentVariableW(L"RRT_POSITION_CAPTURE_FILE",p,32768);if(n&&n<32768){if(!path.empty()){path.clear();done=true;}else{path=p;positionMode=true;}}
        n=GetEnvironmentVariableW(L"RRT_POSITION_TRIGGER_FILE",p,32768);if(n&&n<32768)trigger=p;
        n=GetEnvironmentVariableW(L"RRT_POSITION_FRAME_SAMPLING",p,32768);if(n){if(n!=1||p[0]!=L'1'){done=true;return;}frameSampling=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_SELECTION",p,32768);if(n){
            if(!positionMode||!frameSampling||n>32){done=true;return;}
            const wchar_t* cursor=p;
            auto number=[&](UINT& value,UINT maximum){if(*cursor<L'0'||*cursor>L'9')return false;while(*cursor>=L'0'&&*cursor<=L'9'){value=value*10+(*cursor++-L'0');if(value>maximum)return false;}return value>0;};
            // "any:MIN" keeps the minimum-primitive filter but accepts any render-target extent, so the
            // evidence chain no longer requires knowing the game's resolution in advance.
            if(p[0]==L'a'&&p[1]==L'n'&&p[2]==L'y'&&p[3]==L':'){
                cursor+=4;anyTarget=true;
                if(!number(minPrimitives,4096)||*cursor||std::wstring(L"any:")+std::to_wstring(minPrimitives)!=p){done=true;return;}
            }
            else if(!number(targetWidth,16384)||*cursor++!=L'x'||!number(targetHeight,16384)||*cursor++!=L':'||!number(minPrimitives,4096)||*cursor||std::to_wstring(targetWidth)+L"x"+std::to_wstring(targetHeight)+L":"+std::to_wstring(minPrimitives)!=p){done=true;return;}
        }
        n=GetEnvironmentVariableW(L"RRT_POSITION_MULTI_DRAW",p,32768);if(n){if(n!=1||p[0]!=L'1'||!(targetWidth||anyTarget)){done=true;return;}multiDraw=true;}
        if(anyTarget&&!multiDraw){done=true;return;} // unfiltered selection belongs to the bounded multi-draw window
        n=GetEnvironmentVariableW(L"RRT_POSITION_RENDER_STATE",p,32768);if(n){if(n!=1||p[0]!=L'1'||!multiDraw){done=true;return;}renderState=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_CLEAR_EVIDENCE",p,32768);if(n){if(n!=1||p[0]!=L'1'||!renderState){done=true;return;}clearEvidence=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_WRITE_EVIDENCE",p,32768);if(n){if(n!=1||p[0]!=L'1'||!clearEvidence){done=true;return;}writeEvidence=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_SURFACE_SCOPE",p,32768);if(n){if(n!=1||p[0]!=L'1'||!writeEvidence){done=true;return;}surfaceScope=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_COLOR_REPLAY",p,32768);if(n){if(n!=1||p[0]!=L'1'||!surfaceScope){done=true;return;}colorReplay=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_MATERIAL_INPUTS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!colorReplay){done=true;return;}materialInputs=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_PIXEL_MATERIAL",p,32768);if(n){if(n!=1||p[0]!=L'1'||!materialInputs){done=true;return;}pixelMaterial=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_TEXTURE_INPUTS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!pixelMaterial){done=true;return;}textureInputs=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_TEXTURE_ASSETS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!textureInputs){done=true;return;}externalTextures=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_COMPRESSED_TEXTURES",p,32768);if(n){if(n!=1||p[0]!=L'1'||!externalTextures){done=true;return;}compressedTextures=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_TEXTURE_UPLOADS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!compressedTextures){done=true;return;}textureUploads=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_DIRTY_TEXTURES",p,32768);if(n){if(n!=1||p[0]!=L'1'||!textureUploads){done=true;return;}dirtyTextures=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_SURFACE_UPLOADS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!dirtyTextures){done=true;return;}surfaceUploads=true;}
        n=GetEnvironmentVariableW(L"RRT_POSITION_SURFACE_LOCKS",p,32768);if(n){if(n!=1||p[0]!=L'1'||!surfaceUploads){done=true;return;}surfaceLocks=true;}
        if(positionMode&&frameSampling){unsigned char random[16]{};if(BCryptGenRandom(nullptr,random,sizeof(random),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0){done=true;return;}
            constexpr char digits[]="0123456789abcdef";for(auto b:random){session+=digits[b>>4];session+=digits[b&15];}}
    }
    bool Active() const{return !path.empty()&&!done;}
    bool Line(const std::string& text){DWORD n{};bool ok=WriteFile(file,text.data(),static_cast<DWORD>(text.size()),&n,nullptr)&&n==text.size();written+=n;return ok;}
    void Stop(const char* reason){if(file!=INVALID_HANDLE_VALUE){Line(std::string("{\"kind\":\"end\",\"reason\":\"")+reason+"\",\"attempts\":"+std::to_string(attempts)+",\"captured\":"+std::to_string(captured)+(frameSampling?",\"presents\":"+std::to_string(presents):"")+",\"retained\":"+std::to_string(Retained().load())+",\"retained_buffers\":"+std::to_string(RetainedBuffers().load())+",\"retained_textures\":"+std::to_string(RetainedTextures().load())+",\"live_textures\":"+std::to_string(LiveTextures().load())+",\"retained_peak\":"+std::to_string(RetainedPeak().load())+",\"peak_buffers\":"+std::to_string(PeakBuffers().load())+",\"peak_textures\":"+std::to_string(PeakTextures().load())+"}\n");CloseHandle(file);file=INVALID_HANDLE_VALUE;}done=true;devices.clear();}
    bool Ready(){if(triggered)return attempts<4096&&captured<CaptureLimit()&&(!frameSampling||trigger.empty()||presents>0);if(!trigger.empty()){auto now=GetTickCount64();if(now<nextProbe)return false;nextProbe=now+100;auto a=GetFileAttributesW(trigger.c_str());if(a==INVALID_FILE_ATTRIBUTES||(a&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return false;}
        file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE){done=true;return false;}
        triggered=true;auto header=frameSampling?"{\"kind\":\"header\",\"schema\":\"rrt-position-capture\",\"version\":3,\"session\":\""+session+"\",\"sampling\":\"one-per-present-interval\"}\n":std::string("{\"kind\":\"header\",\"schema\":\"rrt-position-capture\",\"version\":2}\n");
        if(targetWidth)header="{\"kind\":\"header\",\"schema\":\"rrt-position-capture\",\"version\":4,\"session\":\""+session+"\",\"sampling\":\"one-per-present-interval\",\"selection\":{\"target_width\":"+std::to_string(targetWidth)+",\"target_height\":"+std::to_string(targetHeight)+",\"min_primitives\":"+std::to_string(minPrimitives)+"}}\n";
        if(multiDraw){auto selection=anyTarget?std::string("{\"any_target\":true,\"min_primitives\":")+std::to_string(minPrimitives)+"}":std::string("{\"target_width\":")+std::to_string(targetWidth)+",\"target_height\":"+std::to_string(targetHeight)+",\"min_primitives\":"+std::to_string(minPrimitives)+"}";
            header="{\"kind\":\"header\",\"schema\":\"rrt-position-capture\",\"version\":"+std::to_string(static_cast<int>(Level()))+",\"session\":\""+session+"\",\"sampling\":\"bounded-per-present-interval\",\"limits\":{\"per_interval\":4,\"total\":16},\"selection\":"+selection+"}\n";}
        if(surfaceUploads)header.insert(header.size()-2,",\"selection_rejections\":\"first4-per-target-reason-up-to64-keys-plus-every64th-attempt\"");
        if(surfaceUploads)header.insert(header.size()-2,",\"shader_rejections\":\"first4-per-target-reason-up-to64-keys-plus-every64th-attempt\"");
        if(!Line(header)){Stop("io_error");return false;}
        if(externalTextures&&!CreateDirectoryW((path+L".assets").c_str(),nullptr)){Stop("io_error");return false;}return !frameSampling||trigger.empty()||presents>0;}
};
Context& State(){static auto* c=new Context;return *c;}
void Need(bool ok){if(!ok)throw std::runtime_error("shader evidence rejected");}
ComPtr<Shadow> Get(IDirect3DResource9* r,bool create=false){
    ComPtr<Shadow> s;if(!r)return s;Shadow* raw{};DWORD size=sizeof(raw);
    if(SUCCEEDED(r->GetPrivateData(Guid,&raw,&size))&&raw)s.Attach(raw);
    else if(create){s.Attach(new Shadow);if(FAILED(r->SetPrivateData(Guid,static_cast<IUnknown*>(s.Get()),sizeof(IUnknown*),D3DSPD_IUNKNOWN)))s.Reset();}return s;
}
Knowledge& Device(Context& c,std::uint64_t id){Need(c.devices.contains(id)||c.devices.size()<16);return c.devices[id];}
std::string ColorEvidence(IDirect3DDevice9* d){
    ComPtr<IDirect3DPixelShader9> shader;Need(SUCCEEDED(d->GetPixelShader(&shader))&&shader);
    UINT size{};Need(SUCCEEDED(shader->GetFunction(nullptr,&size))&&size>=8&&size<=4096&&size%4==0);
    std::vector<DWORD> code(size/4);Need(SUCCEEDED(shader->GetFunction(code.data(),&size))&&size==code.size()*4);
    std::array<float,4> rgba{};Need(SUCCEEDED(d->GetPixelShaderConstantF(0,rgba.data(),1)));
    auto hex=[](const void* data,std::size_t length){std::string s;const char* digits="0123456789abcdef";auto b=static_cast<const unsigned char*>(data);for(std::size_t i=0;i<length;++i){s+=digits[b[i]>>4];s+=digits[b[i]&15];}return s;};
    std::string s=",\"color_replay\":{\"pixel_shader\":\""+hex(code.data(),size)+"\",\"rgba\":\""+hex(rgba.data(),16)+"\",\"extra_states\":[";
    bool first=true;for(auto [state,expected]:ColorExtraStates){DWORD value{};Need(SUCCEEDED(d->GetRenderState(state,&value)));if(!first)s+=",";first=false;s+=std::to_string(value);}
    float npatch=d->GetNPatchMode();DWORD npatchBits{};memcpy(&npatchBits,&npatch,4);
    return s+"],\"npatch_mode\":"+std::to_string(npatchBits)+"}";
}
#include "pixel_material.inc"
#include "texture_inputs.inc"
std::string SurfaceScope(Context& c,IDirect3DDevice9* d){
    D3DCAPS9 caps{};Need(SUCCEEDED(d->GetDeviceCaps(&caps))&&caps.NumSimultaneousRTs>=1&&caps.NumSimultaneousRTs<=4);
    std::string attachments="[";ComPtr<Shadow> targetTag;
    for(UINT slot=0;slot<caps.NumSimultaneousRTs;++slot){ComPtr<IDirect3DSurface9> surface;auto hr=d->GetRenderTarget(slot,&surface);
        Need((SUCCEEDED(hr)&&surface)||(slot>0&&hr==D3DERR_NOTFOUND));std::uint64_t id{};
        if(surface){auto tag=Get(surface.Get(),true);Need(bool(tag));id=tag->id;if(!slot)targetTag=tag;}
        if(slot)attachments+=",";attachments+=std::to_string(id);}
    Need(bool(targetTag));ComPtr<IDirect3DSurface9> depth;auto hr=d->GetDepthStencilSurface(&depth);Need(SUCCEEDED(hr)||hr==D3DERR_NOTFOUND);
    std::uint64_t depthId{};if(depth){auto tag=Get(depth.Get(),true);Need(bool(tag));depthId=tag->id;}
    auto boolean=[](bool value){return value?"true":"false";};const auto& t=*targetTag.Get();
    return "{\"attachments\":"+attachments+"],\"depth_id\":"+std::to_string(depthId)+",\"open_accesses\":"+std::to_string(c.accesses.size())+",\"access_gap\":"+boolean(c.accessGap)+",\"origin\":{\"observed\":"+boolean(t.createdTarget)+",\"private\":"+boolean(t.privateTarget)+",\"lockable\":"+boolean(t.lockable)+",\"device\":"+std::to_string(t.owner)+",\"reset_epoch\":"+std::to_string(t.createdEpoch)+"}}";
}
std::string WriteHistory(Context& c){
    const auto count=(std::min)(c.writeSerial,std::uint64_t(64));
    std::string s=",\"write_evidence\":{\"scope\":\"process_observed_calls\",\"unobserved\":true,\"observer_gap\":"+std::string(c.writeGap?"true":"false")+",\"overlap\":"+(c.overlap||c.inFlight?"true":"false")+",\"dropped_through\":"+std::to_string(c.writeSerial-count)+",\"through\":"+std::to_string(c.writeSerial)+",\"events\":[";
    for(std::uint64_t offset=0;offset<count;++offset){
        const auto serial=c.writeSerial-count+1+offset;
        const auto& e=c.writes[(serial-1)%64];if(serial!=c.writeSerial-count+1)s+=",";
        s+="{\"serial\":"+std::to_string(serial)+",\"operation\":\""+e.call.operation+"\",\"device\":"+std::to_string(e.call.device)+",\"target_id\":"+std::to_string(e.call.target)+",\"depth_id\":"+std::to_string(e.call.depth)+",\"reset_epoch\":"+std::to_string(e.call.epoch)+",\"clear_serial\":"+std::to_string(e.clearSerial)+",\"hr\":"+std::to_string(static_cast<std::int32_t>(e.hr))+",\"captured_ordinal\":"+std::to_string(e.ordinal)+"}";
    }
    return s+"]}";
}
std::string Composition(IDirect3DDevice9* d,const Knowledge& knowledge,bool clearEvidence){
    ComPtr<IDirect3DSurface9> target,depth;Need(SUCCEEDED(d->GetRenderTarget(0,&target))&&target);
    auto targetTag=Get(target.Get(),true);Need(bool(targetTag));
    auto hr=d->GetDepthStencilSurface(&depth);Need(SUCCEEDED(hr)||hr==D3DERR_NOTFOUND);
    std::uint64_t depthId=0;std::string depthDesc="null";
    if(depth){auto tag=Get(depth.Get(),true);Need(bool(tag));depthId=tag->id;D3DSURFACE_DESC desc{};Need(SUCCEEDED(depth->GetDesc(&desc)));
        depthDesc="["+std::to_string(desc.Width)+","+std::to_string(desc.Height)+","+std::to_string(desc.Format)+","+std::to_string(desc.MultiSampleType)+"]";}
    std::string result="\"render_state\":{\"target_id\":"+std::to_string(targetTag->id)+",\"depth_id\":"+std::to_string(depthId)+",\"depth_desc\":"+depthDesc+",\"clear_serial\":"+std::to_string(knowledge.clearSerial)+",\"binding_serial\":"+std::to_string(knowledge.bindingSerial)+",\"states\":{";
    const std::pair<const char*,D3DRENDERSTATETYPE> states[]={
        {"z_enable",D3DRS_ZENABLE},{"z_write",D3DRS_ZWRITEENABLE},{"z_func",D3DRS_ZFUNC},
        {"alpha_test",D3DRS_ALPHATESTENABLE},{"alpha_ref",D3DRS_ALPHAREF},{"alpha_func",D3DRS_ALPHAFUNC},
        {"blend_enable",D3DRS_ALPHABLENDENABLE},{"src_blend",D3DRS_SRCBLEND},{"dst_blend",D3DRS_DESTBLEND},{"blend_op",D3DRS_BLENDOP},
        {"separate_alpha",D3DRS_SEPARATEALPHABLENDENABLE},{"src_blend_alpha",D3DRS_SRCBLENDALPHA},{"dst_blend_alpha",D3DRS_DESTBLENDALPHA},{"blend_op_alpha",D3DRS_BLENDOPALPHA},
        {"blend_factor",D3DRS_BLENDFACTOR},{"color_write",D3DRS_COLORWRITEENABLE},{"cull",D3DRS_CULLMODE},{"fill",D3DRS_FILLMODE},
        {"scissor_enable",D3DRS_SCISSORTESTENABLE},{"stencil_enable",D3DRS_STENCILENABLE},{"srgb_write",D3DRS_SRGBWRITEENABLE},
        {"depth_bias",D3DRS_DEPTHBIAS},{"slope_depth_bias",D3DRS_SLOPESCALEDEPTHBIAS}};
    bool first=true;for(auto [name,state]:states){DWORD value{};Need(SUCCEEDED(d->GetRenderState(state,&value)));if(!first)result+=",";first=false;result+="\""+std::string(name)+"\":"+std::to_string(value);}
    RECT rect{};Need(SUCCEEDED(d->GetScissorRect(&rect)));
    return result+"},\"scissor\":["+std::to_string(rect.left)+","+std::to_string(rect.top)+","+std::to_string(rect.right)+","+std::to_string(rect.bottom)+"]"+(clearEvidence?",\"last_clear\":"+knowledge.lastClear:"")+"}";
}
void Write(const std::wstring& path,const void* data,std::size_t size) {
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE){OutputDebugStringA("RRT shader snapshot output unavailable\n");return;}
    DWORD written{};if(!WriteFile(file,data,static_cast<DWORD>(size),&written,nullptr)||written!=size)OutputDebugStringA("RRT shader snapshot output incomplete\n");CloseHandle(file);
}
}
void Invalidate(IDirect3DResource9* r) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active())return;auto s=Get(r);if(s){++s->revision;std::fill(s->known.begin(),s->known.end(),0);s->pending=false;s->pointer=nullptr;}}catch(...) {}}
void CreatedTarget(std::uint64_t id,IDirect3DResource9* resource,bool privateTarget,bool lockable) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.surfaceScope)return;
        auto tag=Get(resource,true);Need(bool(tag));Need(!tag->createdTarget);tag->createdTarget=true;tag->privateTarget=privateTarget;tag->lockable=lockable;tag->owner=id;tag->createdEpoch=Device(c,id).resetEpoch;
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);c.accessGap=true;}catch(...){}}
}
bool BeforeColorState() noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.colorReplay)return false;if(c.inFlight++)c.overlap=true;return true;}catch(...){return false;}
}
void AfterColorState(bool active) noexcept {
    if(!active)return;try{auto& c=State();std::lock_guard lock(c.mutex);if(c.inFlight)--c.inFlight;else c.writeGap=true;}catch(...){}
}
WriterPending BeforeWriter(std::uint64_t id,IDirect3DDevice9* device,IDirect3DResource9* resource,const char* operation,int access) noexcept {
    WriterPending p;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.writeEvidence)return p;
        p.active=true;p.operation=operation;p.device=device?id:0;p.access=access;
        if(c.inFlight++)c.overlap=true;
        if(device){p.epoch=Device(c,id).resetEpoch;
            ComPtr<IDirect3DSurface9> target,depth;
            Need(SUCCEEDED(device->GetRenderTarget(0,&target))&&target);auto tag=Get(target.Get(),true);Need(bool(tag));p.target=tag->id;
            auto hr=device->GetDepthStencilSurface(&depth);Need(SUCCEEDED(hr)||hr==D3DERR_NOTFOUND);
            if(depth){tag=Get(depth.Get(),true);Need(bool(tag));p.depth=tag->id;}}
        if(resource){auto tag=Get(resource,true);Need(bool(tag));p.target=tag->id;p.resource=tag->id;p.depth=0;
            bool dirtyNotification=c.dirtyTextures&&tag->texture&&tag->texture->pool==D3DPOOL_SYSTEMMEM&&strcmp(operation,"AddDirtyRect")==0;
            bool surfaceUpload=c.surfaceUploads&&strcmp(operation,"UpdateSurface")==0;
            bool trackedSurfaceLock=c.surfaceLocks&&(strcmp(operation,"LockRect")==0||strcmp(operation,"UnlockRect")==0)&&SurfaceTextureTracked(resource);
            if(!surfaceUpload&&!trackedSurfaceLock&&!(resource->GetType()==D3DRTYPE_TEXTURE&&(strcmp(operation,"LockRect")==0||strcmp(operation,"UnlockRect")==0||dirtyNotification)))TextureInvalidate(resource,operation);}
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);c.writeGap=true;}catch(...){}}
    return p;
}
void AfterWriter(WriterPending p,HRESULT hr) noexcept {
    if(!p.active)return;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(c.inFlight)--c.inFlight;else c.writeGap=true;
        if(!c.Active())return;
        if(c.surfaceScope&&p.access&&SUCCEEDED(hr)){
            // Bounded, process-wide access accounting. Unknown aliases or
            // unmatched closes cannot erase an outstanding write opportunity.
            if(!p.resource)c.accessGap=true;
            else if(p.access>0){if(c.accesses.contains(p.resource)||c.accesses.size()>=64)c.accessGap=true;else c.accesses.emplace(p.resource,p.access);}
            else{auto it=c.accesses.find(p.resource);if(it==c.accesses.end()||it->second!=-p.access)c.accessGap=true;else c.accesses.erase(it);}
        }
        if(c.writeSerial==UINT64_MAX){c.writeGap=true;return;}
        WriteEvent e;e.call=p;e.hr=hr;e.serial=++c.writeSerial;
        if(p.device){auto it=c.devices.find(p.device);if(it!=c.devices.end())e.clearSerial=it->second.clearSerial;else c.writeGap=true;}
        c.writes[(e.serial-1)%64]=e;
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);c.writeGap=true;}catch(...){}}
}
#include "texture_tracking.inc"
void Lock(IDirect3DResource9* r,UINT offset,UINT length,void* pointer,DWORD flags) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active() || flags&D3DLOCK_READONLY)return;
        ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;UINT total{};
        if(SUCCEEDED(r->QueryInterface(IID_PPV_ARGS(&vb)))){D3DVERTEXBUFFER_DESC d{};Need(SUCCEEDED(vb->GetDesc(&d)));total=d.Size;}
        else{Need(SUCCEEDED(r->QueryInterface(IID_PPV_ARGS(&ib))));D3DINDEXBUFFER_DESC d{};Need(SUCCEEDED(ib->GetDesc(&d)));total=d.Size;}
        Need(total && total<=(c.positionMode?16*1024*1024:MaxBuffer) && offset<=total && pointer);if(!length)length=total-offset;Need(length<=total-offset);
        auto s=Get(r,true);Need(bool(s));
        if(s->bytes.empty()){const auto reserved=std::size_t(total)*2;auto before=Retained().fetch_add(reserved);
            if(before+reserved>(c.positionMode?128:16)*1024*1024){Retained().fetch_sub(reserved);throw std::runtime_error("shadow budget");}
            RetainedBuffers().fetch_add(reserved);UpdateRetainedPeak();
            try{std::vector<std::uint8_t> bytes(total),mask(total);s->bytes.swap(bytes);s->known.swap(mask);}catch(...){Retained().fetch_sub(reserved);RetainedBuffers().fetch_sub(reserved);throw;}}
        Need(s->bytes.size()==total);if(flags&D3DLOCK_DISCARD){++s->revision;std::fill(s->known.begin(),s->known.end(),0);}
        s->offset=offset;s->length=length;s->pointer=static_cast<const std::uint8_t*>(pointer);s->pending=true;
    }catch(...){Invalidate(r);}
}
void BeforeUnlock(IDirect3DResource9* r) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active())return;auto s=Get(r);if(s&&s->pending){memcpy(s->bytes.data()+s->offset,s->pointer,s->length);s->pointer=nullptr;}}catch(...){Invalidate(r);}}
void AfterUnlock(IDirect3DResource9* r,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active())return;auto s=Get(r);if(!s)return;if(FAILED(hr)){Invalidate(r);return;}if(s->pending && !s->pointer){++s->revision;std::fill(s->known.begin()+s->offset,s->known.begin()+s->offset+s->length,1);s->pending=false;}}catch(...){Invalidate(r);}}
void Constants(std::uint64_t id,UINT start,UINT count,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||FAILED(hr))return;auto& d=Device(c,id);if(!d.recording){++d.revision;for(UINT i=0;i<61;++i)if(i>=start && std::uint64_t(i)<std::uint64_t(start)+count)d.constants[i]=true;}}catch(...) {}}
void PixelConstants(std::uint64_t id,UINT start,UINT count,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.pixelMaterial||FAILED(hr))return;auto& d=Device(c,id);if(!d.recording){++d.revision;for(UINT i=0;i<31;++i)if(i>=start&&std::uint64_t(i)<std::uint64_t(start)+count)d.pixelConstants[i]=true;}}catch(...) {}}
void Boundary(std::uint64_t id,int kind,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||FAILED(hr))return;auto& d=Device(c,id);++d.revision;if(kind==0){++d.resetEpoch;d.interval=0;d.drawSequence=0;d.reserved=false;d.samples=0;}d.constants.fill(false);d.pixelConstants.fill(false);d.recording=kind==1;}catch(...) {}}
bool FrameSampling() noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);return c.Active()&&c.positionMode&&c.frameSampling;}catch(...){return false;}}
void Presented(std::uint64_t id,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.positionMode||!c.frameSampling||hr!=S_OK)return;
    auto& d=Device(c,id);
    // Triggered captures open their window on a real frame boundary: the first present after arming
    // restarts interval 0, so a trigger landing while the game is not presenting cannot spend the
    // attempt budget on draws belonging to no frame. Untriggered sampling keeps the historical numbering.
    if(c.triggered&&++c.presents==1&&!c.trigger.empty())d.interval=0;else ++d.interval;
    d.drawSequence=0;d.reserved=false;d.samples=0;
    if(c.triggered&&c.presents>=120)c.Stop("present_limit");
}catch(...) {}}
void Applied(HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(c.Active()&&SUCCEEDED(hr))for(auto& [id,d]:c.devices){++d.revision;d.constants.fill(false);d.pixelConstants.fill(false);}}catch(...) {}}
void CompositionBoundary(std::uint64_t id,bool clear,HRESULT hr) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.renderState||FAILED(hr))return;auto& d=Device(c,id);if(clear)++d.clearSerial;else ++d.bindingSerial;}catch(...) {}}
std::unique_ptr<ClearPending> BeforeClear(std::uint64_t id,IDirect3DDevice9* d,DWORD count,const D3DRECT* rects,DWORD flags,D3DCOLOR color,float z,DWORD stencil) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.clearEvidence)return {};
        Need(count<=16&&(!count||rects));auto& knowledge=Device(c,id);auto pending=std::make_unique<ClearPending>();pending->serial=knowledge.clearSerial+1;
        ComPtr<IDirect3DSurface9> target,depth;Need(SUCCEEDED(d->GetRenderTarget(0,&target))&&target);auto targetTag=Get(target.Get(),true);Need(bool(targetTag));
        D3DSURFACE_DESC desc{};Need(SUCCEEDED(target->GetDesc(&desc)));auto hr=d->GetDepthStencilSurface(&depth);Need(SUCCEEDED(hr)||hr==D3DERR_NOTFOUND);
        std::uint64_t depthId{};if(depth){auto tag=Get(depth.Get(),true);Need(bool(tag));depthId=tag->id;}
        D3DVIEWPORT9 viewport{};DWORD scissor{};Need(SUCCEEDED(d->GetViewport(&viewport))&&SUCCEEDED(d->GetRenderState(D3DRS_SCISSORTESTENABLE,&scissor)));
        auto hex=[](const void* p,std::size_t n){const char* digits="0123456789abcdef";auto b=static_cast<const unsigned char*>(p);std::string s;for(std::size_t i=0;i<n;++i){s+=digits[b[i]>>4];s+=digits[b[i]&15];}return s;};
        DWORD depthBits{};memcpy(&depthBits,&z,4);
        pending->record="{\"serial\":"+std::to_string(pending->serial)+",\"reset_epoch\":"+std::to_string(knowledge.resetEpoch)+",\"target_id\":"+std::to_string(targetTag->id)+",\"depth_id\":"+std::to_string(depthId)+",\"target_desc\":["+std::to_string(desc.Width)+","+std::to_string(desc.Height)+","+std::to_string(desc.Format)+","+std::to_string(desc.MultiSampleType)+"],\"viewport\":\""+hex(&viewport,sizeof(viewport))+"\",\"scissor_enable\":"+std::to_string(scissor)+",\"flags\":"+std::to_string(flags)+",\"color\":"+std::to_string(color)+",\"depth_bits\":"+std::to_string(depthBits)+",\"stencil\":"+std::to_string(stencil)+",\"rects\":[";
        for(DWORD i=0;i<count;++i){if(i)pending->record+=",";auto r=rects[i];pending->record+="["+std::to_string(r.x1)+","+std::to_string(r.y1)+","+std::to_string(r.x2)+","+std::to_string(r.y2)+"]";}
        pending->record+="]}";if(c.surfaceScope)pending->scope=SurfaceScope(c,d);return pending;
    }catch(...){return {};}
}
void AfterClear(std::uint64_t id,std::unique_ptr<ClearPending> pending,HRESULT hr) noexcept {
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active()||!c.renderState||FAILED(hr))return;auto& d=Device(c,id);++d.clearSerial;
        if(c.clearEvidence)d.lastClear=pending&&pending->serial==d.clearSerial?std::move(pending->record):"null";
        if(c.surfaceScope)d.lastClearScope=pending&&pending->serial==d.clearSerial?std::move(pending->scope):"null";
    }catch(...){}
}
void Retire(std::uint64_t id) noexcept {try{auto& c=State();std::lock_guard lock(c.mutex);c.devices.erase(id);}catch(...) {}}
std::unique_ptr<Pending> BeforeDraw(std::uint64_t id,IDirect3DDevice9* d,D3DPRIMITIVETYPE type,Draw draw) noexcept {
    std::unique_ptr<Pending> result;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active())return {};
        if(c.positionMode){if(!c.Ready())return {};auto& timing=Device(c,id);auto drawSequence=timing.drawSequence++;
            if(c.frameSampling&&(timing.reserved||timing.samples>=c.IntervalLimit()))return {};
            result=std::make_unique<Pending>();result->position=true;result->writeSerial=c.writeSerial;result->ordinal=c.attempts;result->reason="unsupported_or_missing_evidence";result->record="\"device\":"+std::to_string(id)+",\"ordinal\":"+std::to_string(c.attempts++);
            if(c.frameSampling){result->sampled=true;result->device=id;result->epoch=timing.resetEpoch;result->interval=timing.interval;timing.reserved=true;
                result->record+=",\"timing\":{\"reset_epoch\":"+std::to_string(timing.resetEpoch)+",\"present_interval\":"+std::to_string(timing.interval)+",\"indexed_draw\":"+std::to_string(drawSequence)+"}";}
            result->stage="topology";Need(type==D3DPT_TRIANGLELIST);result->stage="device_state";auto& state=Device(c,id);Need(!state.recording);
            result->stage="selection";if(c.targetWidth||c.anyTarget){ComPtr<IDirect3DSurface9> surface;D3DSURFACE_DESC desc{};
                if(FAILED(d->GetRenderTarget(0,&surface))||!surface||FAILED(surface->GetDesc(&desc))){result->reason="selection_target_unavailable";return result;}
                result->selectionObserved="\"target\":["+std::to_string(desc.Width)+","+std::to_string(desc.Height)+","+std::to_string(desc.Format)+","+std::to_string(desc.MultiSampleType)+"],\"primitives\":"+std::to_string(draw.primitives);
                if(!c.anyTarget&&(desc.Width!=c.targetWidth||desc.Height!=c.targetHeight)){result->reason="selection_target_mismatch";return result;}
                if(draw.primitives<c.minPrimitives){result->reason="selection_primitive_minimum";return result;}}
            result->stage="buffer_binding";ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;UINT offset{},stride{};
            Need(SUCCEEDED(d->GetStreamSource(0,&vb,&offset,&stride))&&SUCCEEDED(d->GetIndices(&ib)));
            result->stage="buffer_tracking";auto v=Get(vb.Get()),i=Get(ib.Get());Need(v&&i&&!v->pending&&!i->pending);
            result->stage="position_material";auto data=position::Capture(d,draw,{vb.Get(),v->bytes,v->known},{ib.Get(),i->bytes,i->known},state.constants,c.materialInputs);
            if(c.renderState){result->stage="composition";data+=","+Composition(d,state,c.clearEvidence);result->composition=true;result->clearSerial=state.clearSerial;result->bindingSerial=state.bindingSerial;}
            if(c.surfaceScope){result->stage="surface_scope";data+=",\"surface_scope\":{\"draw\":"+SurfaceScope(c,d)+",\"clear\":"+state.lastClearScope+"}";}
            if(c.colorReplay){result->stage="color_evidence";data+=ColorEvidence(d);}
            if(c.pixelMaterial){result->stage="pixel_material";data+=PixelMaterial(d,state);}
            if(c.textureInputs){result->stage="texture_inputs";data+=TextureInputs(c,d,result.get());}
            result->record+=",\"provenance\":{\"vb_id\":"+std::to_string(v->id)+",\"vb_revision\":"+std::to_string(v->revision)+",\"ib_id\":"+std::to_string(i->id)+",\"ib_revision\":"+std::to_string(i->revision)+",\"reset_epoch\":"+std::to_string(state.resetEpoch)+",\"knowledge_revision\":"+std::to_string(state.revision)+"},"+data;result->reason.clear();return result;
        }
        if(c.ordinal++!=c.target)return {};
        result=std::make_unique<Pending>();result->failure="unsupported_or_missing_evidence";
        Need(type==D3DPT_TRIANGLELIST);auto& state=Device(c,id);Need(!state.recording);
        ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;UINT offset{},stride{};
        Need(SUCCEEDED(d->GetStreamSource(0,&vb,&offset,&stride))&&SUCCEEDED(d->GetIndices(&ib)));
        auto v=Get(vb.Get()),i=Get(ib.Get());Need(v&&i&&!v->pending&&!i->pending);
        std::array<bool,5> known{};std::copy_n(state.constants.begin(),5,known.begin());
        result->bytes=Encode(Capture(d,draw,{vb.Get(),v->bytes,v->known},{ib.Get(),i->bytes,i->known},known));result->failure=nullptr;
    }catch(const std::exception& e){if(result&&result->position){std::string reason=e.what();result->failureStage=result->stage;
        result->detail=reason.size()>0&&reason.size()<=96&&std::all_of(reason.begin(),reason.end(),[](char ch){return (ch>='a'&&ch<='z')||ch=='_'||ch==' ';})?reason:"unclassified_exception";
        const char* allowed[]={"unsupported_shader","position program not admitted","unknown_constants","uninitialized_bytes","buffer_range","position_layout","draw_budget","declared_index_range","negative_vertex","stream_layout","index_format","nonfinite position","nonfinite constant","position overflow"};for(auto s:allowed)if(reason==s)result->reason=reason;}}catch(...){}return result;
}
void Commit(std::unique_ptr<Pending> result,HRESULT hr) noexcept {
    if(!result)return;
    try{auto& c=State();std::lock_guard lock(c.mutex);if(!c.Active())return;
        if(result->position){bool ok=SUCCEEDED(hr)&&result->reason.empty();
            if(c.writeEvidence&&(c.writeSerial!=result->writeSerial+1||!c.writeSerial)){ok=false;result->reason="write_boundary_changed";c.writeGap=true;}
            if(c.writeEvidence&&c.writeSerial){const auto& e=c.writes[(c.writeSerial-1)%64];
                if(!e.call.target||e.call.device!=result->device||e.call.epoch!=result->epoch||c.inFlight||(c.pixelMaterial&&c.overlap)){ok=false;result->reason="write_boundary_changed";c.writeGap=true;}}
            if(result->sampled){auto it=c.devices.find(result->device);bool current=it!=c.devices.end()&&it->second.resetEpoch==result->epoch&&it->second.interval==result->interval;
                if(!current){ok=false;result->reason="presentation_boundary_changed";}
                if(current&&result->composition&&(it->second.clearSerial!=result->clearSerial||it->second.bindingSerial!=result->bindingSerial)){ok=false;result->reason="composition_boundary_changed";}
                if(current){it->second.reserved=false;if(ok)++it->second.samples;}}
            if(c.writeEvidence){
                if(ok)c.writes[(c.writeSerial-1)%64].ordinal=static_cast<std::int64_t>(result->ordinal);
            }
            // Repeated early selection failures are diagnostic samples, never captured draws.
            if(!ok&&SUCCEEDED(hr)&&c.surfaceUploads&&(result->reason=="selection_target_mismatch"||result->reason=="selection_primitive_minimum")){
                auto key=result->reason+result->selectionObserved.substr(0,result->selectionObserved.find(",\"primitives\":"));
                auto it=c.selectionRejections.find(key);bool keep=result->ordinal%64==0;
                if(it==c.selectionRejections.end()&&c.selectionRejections.size()<64)it=c.selectionRejections.emplace(key,0).first;
                if(it!=c.selectionRejections.end()&&it->second<4){++it->second;keep=true;}
                if(!keep){if(c.attempts>=4096)c.Stop("attempt_limit");return;}
            }
            if(!ok&&SUCCEEDED(hr)&&c.surfaceUploads&&(result->reason=="unsupported_shader"||result->reason=="position program not admitted")){
                auto key=result->reason+result->selectionObserved.substr(0,result->selectionObserved.find(",\"primitives\":"));
                auto it=c.shaderRejections.find(key);bool keep=result->ordinal%64==0;
                if(it==c.shaderRejections.end()&&c.shaderRejections.size()<64)it=c.shaderRejections.emplace(key,0).first;
                if(it!=c.shaderRejections.end()&&it->second<4){++it->second;keep=true;}
                if(!keep){if(c.attempts>=4096)c.Stop("attempt_limit");return;}
            }
            const bool preflightFailure=!ok&&SUCCEEDED(hr)&&c.surfaceUploads&&!result->failureStage.empty()&&result->reason!="write_boundary_changed"&&result->reason!="presentation_boundary_changed"&&result->reason!="composition_boundary_changed";
            if(preflightFailure)
                result->record+=",\"evidence_failure\":{\"stage\":\""+result->failureStage+"\",\"detail\":\""+result->detail+"\"}";
            if(preflightFailure&&result->failureStage=="texture_inputs"&&!result->textureDiagnostic.empty())result->record+=",\"texture_diagnostic\":"+result->textureDiagnostic;
            if(!ok&&!result->selectionObserved.empty())result->record+=",\"selection_observed\":{"+result->selectionObserved+"}";
            auto line=std::string("{\"kind\":\"draw\",\"status\":\"")+(ok?"captured":"rejected")+"\",\"hr\":"+std::to_string(static_cast<std::int32_t>(hr))+",\"reason\":\""+(FAILED(hr)?"native_draw_failed":result->reason)+"\","+result->record+(c.writeEvidence?WriteHistory(c):"")+"}\n";
            if(c.written+line.size()+256>16*1024*1024){c.Stop("byte_limit");return;}if(!c.Line(line)){c.Stop("io_error");return;}if(ok)++c.captured;if(c.captured>=c.CaptureLimit())c.Stop("capture_limit");else if(c.attempts>=4096)c.Stop("attempt_limit");return;}
        c.done=true;c.devices.clear();
        if(FAILED(hr)||result->failure){const char* reason=FAILED(hr)?"native_draw_failed\n":"unsupported_or_missing_evidence\n";Write(c.path+L".rejected",reason,strlen(reason));}
        else Write(c.path,result->bytes.data(),result->bytes.size());
    }catch(...){try{auto& c=State();std::lock_guard lock(c.mutex);if(c.writeEvidence){c.writeGap=true;c.done=true;c.Stop("io_error");}}catch(...){}}
}
}
