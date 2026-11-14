#include "position_capture.h"
#include "position.h"
#include "vs_interpreter.h"
#include "interpreted_programs.h"
#include "../scene/scene.h"
#include <algorithm>
#include <set>
#include <wrl/client.h>
#include <cstring>
#include <cmath>
#include <stdexcept>
namespace rrt::shader::position {
using Microsoft::WRL::ComPtr;
namespace {
void Need(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
std::string Hex(const void* p,std::size_t n){const auto* b=static_cast<const unsigned char*>(p);const char* h="0123456789abcdef";std::string s;s.reserve(n*2);for(std::size_t i=0;i<n;++i){s+=h[b[i]>>4];s+=h[b[i]&15];}return s;}
void Known(const Evidence& e,std::uint64_t offset,std::size_t size){Need(e.bytes.size()==e.initialized.size()&&offset<=e.bytes.size()&&size<=e.bytes.size()-offset,"buffer_range");for(std::size_t i=0;i<size;++i)Need(e.initialized[static_cast<std::size_t>(offset)+i]!=0,"uninitialized_bytes");}
std::string Tail(const D3DVIEWPORT9& viewport,const D3DSURFACE_DESC& t,UINT offset,UINT stride,Draw draw,const Evidence& ve,const Evidence& ie,std::uint64_t start,std::size_t corners){
    return ",\"viewport\":\""+Hex(&viewport,sizeof(viewport))+"\",\"target\":["+std::to_string(t.Width)+","+std::to_string(t.Height)+","+std::to_string(t.Format)+","+std::to_string(t.MultiSampleType)+"],\"offset\":"+std::to_string(offset)+",\"stride\":"+std::to_string(stride)+",\"base\":"+std::to_string(draw.base)+",\"minimum\":"+std::to_string(draw.minimum)+",\"vertices\":"+std::to_string(draw.vertices)+",\"start\":"+std::to_string(draw.start)+",\"primitives\":"+std::to_string(draw.primitives)+",\"vb_size\":"+std::to_string(ve.bytes.size())+",\"ib_size\":"+std::to_string(ie.bytes.size())+",\"indices\":\""+Hex(ie.bytes.data()+start,corners*2)+"\"";
}
// The 1420-byte static-prop program (docs/HL2_FLEX_POSITION_CONTRACT.md). Position evidence only: its texture, colour and
// lighting inputs are a different layout from the first program's, so material capture refuses it as unsupported.
std::string CaptureFlex(IDirect3DDevice9* d,Draw draw,const Evidence& ve,const Evidence& ie,const std::array<bool,256>& known,bool material,const Evidence* flex){
    Need(!material,"unsupported_shader");
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->GetVertexShader(&vs))&&vs,"missing_shader");UINT size{};
    std::array<DWORD,FlexProgramBytes/4> code{};
    Need(SUCCEEDED(vs->GetFunction(nullptr,&size))&&size==FlexProgramBytes&&SUCCEEDED(vs->GetFunction(code.data(),&size))&&size==FlexProgramBytes,"shader_query");
    AdmitFlex({reinterpret_cast<const std::uint8_t*>(code.data()),FlexProgramBytes});
    Need(draw.primitives&&draw.primitives<=4096&&draw.vertices&&draw.vertices<=65536,"draw_budget");
    ComPtr<IDirect3DVertexDeclaration9> declaration;Need(SUCCEEDED(d->GetVertexDeclaration(&declaration))&&declaration,"missing_layout");
    std::array<D3DVERTEXELEMENT9,65> elements{};UINT count=65;Need(SUCCEEDED(declaration->GetDeclaration(elements.data(),&count))&&count&&count<=65&&elements[count-1].Stream==255,"layout_query");
    // POSITION0 is FLOAT3 at the start of stream 0, POSITION1 is FLOAT4 at the start of stream 2; each exactly once.
    unsigned positions=0,flexes=0;for(UINT i=0;i+1<count;++i){auto e=elements[i];if(e.Usage!=D3DDECLUSAGE_POSITION)continue;
        if(e.UsageIndex==0){Need(e.Stream==0&&e.Offset==0&&e.Type==D3DDECLTYPE_FLOAT3&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");++positions;}
        else if(e.UsageIndex==1){Need(e.Stream==2&&e.Offset==0&&e.Type==D3DDECLTYPE_FLOAT4&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");++flexes;}}
    Need(positions==1&&flexes==1,"position_layout");
    ComPtr<IDirect3DVertexBuffer9> vb,fb;ComPtr<IDirect3DIndexBuffer9> ib;UINT offset{},stride{},frequency{},flexOffset{},flexStride{},flexFrequency{};
    Need(SUCCEEDED(d->GetStreamSource(0,&vb,&offset,&stride))&&vb&&SUCCEEDED(d->GetIndices(&ib))&&ib&&SUCCEEDED(d->GetStreamSource(2,&fb,&flexOffset,&flexStride))&&fb&&flex,"missing_binding");
    Need(vb.Get()==ve.resource&&ib.Get()==ie.resource&&fb.Get()==flex->resource,"resource_identity");
    Need(SUCCEEDED(d->GetStreamSourceFreq(0,&frequency))&&frequency==1&&stride>=12&&stride<=256,"stream_layout");
    // Stride 0 is how the title binds one flex value for the whole draw; a per-vertex stream is accepted too.
    Need(SUCCEEDED(d->GetStreamSourceFreq(2,&flexFrequency))&&flexFrequency==1&&(flexStride==0||(flexStride>=16&&flexStride<=256)),"stream_layout");
    D3DINDEXBUFFER_DESC desc{};Need(SUCCEEDED(ib->GetDesc(&desc))&&desc.Format==D3DFMT_INDEX16,"index_format");
    FlexConstants constants{};
    D3DVIEWPORT9 viewport{};ComPtr<IDirect3DSurface9> target;D3DSURFACE_DESC targetDesc{};
    Need(SUCCEEDED(d->GetViewport(&viewport))&&SUCCEEDED(d->GetRenderTarget(0,&target))&&target&&SUCCEEDED(target->GetDesc(&targetDesc)),"target_query");
    Need(std::isfinite(viewport.MinZ)&&std::isfinite(viewport.MaxZ),"viewport_nonfinite");
    for(unsigned i=0;i<FlexRegisters.size();++i){Need(known[FlexRegisters[i]],"unknown_constants");Need(SUCCEEDED(d->GetVertexShaderConstantF(FlexRegisters[i],constants.rows[i].data(),1)),"constant_query");constants.known[i]=true;}
    const std::size_t corners=std::size_t(draw.primitives)*3;const auto start=std::uint64_t(draw.start)*2;Known(ie,start,corners*2);
    std::vector<std::array<float,3>> inputs;std::vector<std::array<float,4>> flexes4;std::vector<Result> outputs;inputs.reserve(corners);flexes4.reserve(corners);outputs.reserve(corners);
    for(std::size_t i=0;i<corners;++i){std::uint16_t index{};memcpy(&index,ie.bytes.data()+start+i*2,2);Need(index>=draw.minimum&&std::uint64_t(index)<std::uint64_t(draw.minimum)+draw.vertices,"declared_index_range");
        auto vertex=std::int64_t(draw.base)+index;Need(vertex>=0,"negative_vertex");auto address=std::uint64_t(offset)+std::uint64_t(vertex)*stride;Known(ve,address,12);
        auto flexAddress=std::uint64_t(flexOffset)+std::uint64_t(vertex)*flexStride;Known(*flex,flexAddress,16);
        std::array<float,3> input;memcpy(input.data(),ve.bytes.data()+address,12);std::array<float,4> value;memcpy(value.data(),flex->bytes.data()+flexAddress,16);
        inputs.push_back(input);flexes4.push_back(value);outputs.push_back(EvaluateFlex(input,{value[0],value[1],value[2]},constants));}
    std::string rows="[";for(unsigned i=0;i<FlexRegisters.size();++i)rows+=(i?",":"")+std::to_string(FlexRegisters[i]);rows+="]";
    return "\"shader\":\""+Hex(code.data(),FlexProgramBytes)+"\",\"declaration\":\""+Hex(elements.data(),count*8)+"\",\"constants\":\""+Hex(constants.rows.data(),sizeof(constants.rows))+"\",\"constant_rows\":"+rows
        +Tail(viewport,targetDesc,offset,stride,draw,ve,ie,start,corners)+",\"positions\":\""+Hex(inputs.data(),corners*12)+"\",\"evaluated\":\""+Hex(outputs.data(),corners*32)+"\""
        +",\"flex\":{\"offset\":"+std::to_string(flexOffset)+",\"stride\":"+std::to_string(flexStride)+",\"vb_size\":"+std::to_string(flex->bytes.size())+",\"values\":\""+Hex(flexes4.data(),corners*16)+"\"}";
}
}
// The 3348-byte skinned program (docs/HL2_SKINNED_POSITION_CONTRACT.md). Position evidence only, as for the flex program.
std::string CaptureSkin(IDirect3DDevice9* d,Draw draw,const Evidence& ve,const Evidence& ie,const std::array<bool,256>& known,bool material,const Evidence* flex){
    Need(!material,"unsupported_shader");
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->GetVertexShader(&vs))&&vs,"missing_shader");UINT size{};
    std::array<DWORD,SkinProgramBytes/4> code{};
    Need(SUCCEEDED(vs->GetFunction(nullptr,&size))&&size==SkinProgramBytes&&SUCCEEDED(vs->GetFunction(code.data(),&size))&&size==SkinProgramBytes,"shader_query");
    AdmitSkin({reinterpret_cast<const std::uint8_t*>(code.data()),SkinProgramBytes});
    Need(draw.primitives&&draw.primitives<=4096&&draw.vertices&&draw.vertices<=65536,"draw_budget");
    ComPtr<IDirect3DVertexDeclaration9> declaration;Need(SUCCEEDED(d->GetVertexDeclaration(&declaration))&&declaration,"missing_layout");
    std::array<D3DVERTEXELEMENT9,65> elements{};UINT count=65;Need(SUCCEEDED(declaration->GetDeclaration(elements.data(),&count))&&count&&count<=65&&elements[count-1].Stream==255,"layout_query");
    // POSITION0 FLOAT3 at the start of stream 0, BLENDWEIGHT0 SHORT2 and BLENDINDICES0 D3DCOLOR in stream 0, POSITION1 FLOAT4 at the
    // start of stream 2; each exactly once. The weight and index offsets are recorded rather than pinned.
    unsigned positions=0,flexes=0,weights=0,indices=0;WORD weightOffset{},indexOffset{};
    for(UINT i=0;i+1<count;++i){auto e=elements[i];
        if(e.Usage==D3DDECLUSAGE_POSITION&&e.UsageIndex==0){Need(e.Stream==0&&e.Offset==0&&e.Type==D3DDECLTYPE_FLOAT3&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");++positions;}
        else if(e.Usage==D3DDECLUSAGE_POSITION&&e.UsageIndex==1){Need(e.Stream==2&&e.Offset==0&&e.Type==D3DDECLTYPE_FLOAT4&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");++flexes;}
        else if(e.Usage==D3DDECLUSAGE_BLENDWEIGHT&&e.UsageIndex==0){Need(e.Stream==0&&e.Type==D3DDECLTYPE_SHORT2&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");weightOffset=e.Offset;++weights;}
        else if(e.Usage==D3DDECLUSAGE_BLENDINDICES&&e.UsageIndex==0){Need(e.Stream==0&&e.Type==D3DDECLTYPE_D3DCOLOR&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");indexOffset=e.Offset;++indices;}}
    Need(positions==1&&flexes==1&&weights==1&&indices==1,"position_layout");
    ComPtr<IDirect3DVertexBuffer9> vb,fb;ComPtr<IDirect3DIndexBuffer9> ib;UINT offset{},stride{},frequency{},flexOffset{},flexStride{},flexFrequency{};
    Need(SUCCEEDED(d->GetStreamSource(0,&vb,&offset,&stride))&&vb&&SUCCEEDED(d->GetIndices(&ib))&&ib&&SUCCEEDED(d->GetStreamSource(2,&fb,&flexOffset,&flexStride))&&fb&&flex,"missing_binding");
    Need(vb.Get()==ve.resource&&ib.Get()==ie.resource&&fb.Get()==flex->resource,"resource_identity");
    Need(SUCCEEDED(d->GetStreamSourceFreq(0,&frequency))&&frequency==1&&stride>=12&&stride<=256&&weightOffset+4u<=stride&&indexOffset+4u<=stride,"stream_layout");
    Need(SUCCEEDED(d->GetStreamSourceFreq(2,&flexFrequency))&&flexFrequency==1&&(flexStride==0||(flexStride>=16&&flexStride<=256)),"stream_layout");
    D3DINDEXBUFFER_DESC desc{};Need(SUCCEEDED(ib->GetDesc(&desc))&&desc.Format==D3DFMT_INDEX16,"index_format");
    SkinConstants constants{};
    D3DVIEWPORT9 viewport{};ComPtr<IDirect3DSurface9> target;D3DSURFACE_DESC targetDesc{};
    Need(SUCCEEDED(d->GetViewport(&viewport))&&SUCCEEDED(d->GetRenderTarget(0,&target))&&target&&SUCCEEDED(target->GetDesc(&targetDesc)),"target_query");
    Need(std::isfinite(viewport.MinZ)&&std::isfinite(viewport.MaxZ),"viewport_nonfinite");
    for(unsigned i=0;i<SkinRegisters.size();++i){Need(known[SkinRegisters[i]],"unknown_constants");Need(SUCCEEDED(d->GetVertexShaderConstantF(SkinRegisters[i],constants.rows[i].data(),1)),"constant_query");constants.known[i]=true;}
    const std::size_t corners=std::size_t(draw.primitives)*3;const auto start=std::uint64_t(draw.start)*2;Known(ie,start,corners*2);
    std::vector<SkinInput> inputs;inputs.reserve(corners);std::array<bool,PaletteRows> used{};
    for(std::size_t i=0;i<corners;++i){std::uint16_t index{};memcpy(&index,ie.bytes.data()+start+i*2,2);Need(index>=draw.minimum&&std::uint64_t(index)<std::uint64_t(draw.minimum)+draw.vertices,"declared_index_range");
        auto vertex=std::int64_t(draw.base)+index;Need(vertex>=0,"negative_vertex");auto address=std::uint64_t(offset)+std::uint64_t(vertex)*stride;
        Known(ve,address,12);Known(ve,address+weightOffset,4);Known(ve,address+indexOffset,4);
        auto flexAddress=std::uint64_t(flexOffset)+std::uint64_t(vertex)*flexStride;Known(*flex,flexAddress,16);
        SkinInput input{};memcpy(input.position.data(),ve.bytes.data()+address,12);memcpy(input.weights.data(),ve.bytes.data()+address+weightOffset,4);memcpy(&input.indices,ve.bytes.data()+address+indexOffset,4);
        std::array<float,4> value;memcpy(value.data(),flex->bytes.data()+flexAddress,16);input.flex={value[0],value[1],value[2]};
        for(auto base:SkinBones(input.indices))used[base]=true;inputs.push_back(input);}
    // Only the bone rows the draw's vertices read are required and recorded: three registers per referenced bone.
    std::string bones="[";std::vector<Vec> boneRows;
    for(unsigned base=0;base<PaletteRows;++base){if(!used[base])continue;
        for(unsigned r=0;r<3;++r){Need(known[PaletteStart+base+r],"unknown_constants");Need(SUCCEEDED(d->GetVertexShaderConstantF(PaletteStart+base+r,constants.palette[base+r].data(),1)),"constant_query");constants.paletteKnown[base+r]=true;boneRows.push_back(constants.palette[base+r]);}
        bones+=(bones.size()>1?",":"")+std::to_string(base);}
    bones+="]";
    std::vector<Result> outputs;outputs.reserve(corners);std::vector<std::array<std::uint8_t,8>> blend(corners);std::vector<std::array<float,4>> flexes4(corners);
    for(std::size_t i=0;i<corners;++i){const auto& in=inputs[i];outputs.push_back(EvaluateSkin(in,constants));memcpy(blend[i].data(),in.weights.data(),4);memcpy(blend[i].data()+4,&in.indices,4);
        flexes4[i]={in.flex[0],in.flex[1],in.flex[2],0};std::uint64_t vertex=std::uint64_t(std::int64_t(draw.base)+*reinterpret_cast<const std::uint16_t*>(ie.bytes.data()+start+i*2));memcpy(&flexes4[i][3],flex->bytes.data()+flexOffset+vertex*flexStride+12,4);}
    std::string rows="[";for(unsigned i=0;i<SkinRegisters.size();++i)rows+=(i?",":"")+std::to_string(SkinRegisters[i]);rows+="]";
    std::vector<std::array<float,3>> positionsOut(corners);for(std::size_t i=0;i<corners;++i)positionsOut[i]=inputs[i].position;
    return "\"shader\":\""+Hex(code.data(),SkinProgramBytes)+"\",\"declaration\":\""+Hex(elements.data(),count*8)+"\",\"constants\":\""+Hex(constants.rows.data(),sizeof(constants.rows))+"\",\"constant_rows\":"+rows
        +",\"bones\":{\"offsets\":"+bones+",\"rows\":\""+Hex(boneRows.data(),boneRows.size()*16)+"\"}"
        +Tail(viewport,targetDesc,offset,stride,draw,ve,ie,start,corners)+",\"positions\":\""+Hex(positionsOut.data(),corners*12)+"\",\"evaluated\":\""+Hex(outputs.data(),corners*32)+"\""
        +",\"blend\":{\"weights_offset\":"+std::to_string(weightOffset)+",\"indices_offset\":"+std::to_string(indexOffset)+",\"values\":\""+Hex(blend.data(),corners*8)+"\"}"
        +",\"flex\":{\"offset\":"+std::to_string(flexOffset)+",\"stride\":"+std::to_string(flexStride)+",\"vb_size\":"+std::to_string(flex->bytes.size())+",\"values\":\""+Hex(flexes4.data(),corners*16)+"\"}";
}
// A program admitted through the vs_2_0 interpreter (docs/VS_INTERPRETER.md): clip positions only, from the program's own position
// slice. Every input the slice reads must come from bytes the proxy saw written, and every float register it reads, statically or
// through a0, must be known. Material capture refuses these programs as unsupported.
std::string CaptureInterpreted(IDirect3DDevice9* d,Draw draw,const Evidence& ie,const std::array<bool,256>& known,bool material,const StreamEvidence& streams,const std::vector<DWORD>& code){
    Need(!material,"unsupported_shader");
    const auto program=vsi::Analyse({reinterpret_cast<const std::uint32_t*>(code.data()),code.size()});Need(program.ok,"position program not admitted");
    Need(draw.primitives&&draw.primitives<=4096&&draw.vertices&&draw.vertices<=65536,"draw_budget");
    ComPtr<IDirect3DVertexDeclaration9> declaration;Need(SUCCEEDED(d->GetVertexDeclaration(&declaration))&&declaration,"missing_layout");
    std::array<D3DVERTEXELEMENT9,65> elements{};UINT count=65;Need(SUCCEEDED(declaration->GetDeclaration(elements.data(),&count))&&count&&count<=65&&elements[count-1].Stream==255,"layout_query");
    // Each input the slice reads: exactly one declaration element of its usage, a supported type, and a tracked stream binding.
    struct Bound {vsi::Input input;D3DVERTEXELEMENT9 element{};UINT offset{},stride{};const Evidence* evidence{};std::size_t size{};};
    std::vector<Bound> bound;
    for(const auto& input:program.inputs){Bound b{input};unsigned matches=0;
        for(UINT i=0;i+1<count;++i)if(elements[i].Usage==input.usage&&elements[i].UsageIndex==input.usageIndex){b.element=elements[i];++matches;}
        Need(matches==1&&b.element.Method==D3DDECLMETHOD_DEFAULT,"position_layout");
        try{b.size=vsi::InputSize(b.element.Type);}catch(...){Need(false,"position_layout");}
        ComPtr<IDirect3DVertexBuffer9> vb;UINT frequency{};
        Need(b.element.Stream<16&&SUCCEEDED(d->GetStreamSource(b.element.Stream,&vb,&b.offset,&b.stride))&&vb&&streams[b.element.Stream],"missing_binding");
        b.evidence=streams[b.element.Stream];Need(vb.Get()==b.evidence->resource,"resource_identity");
        Need(SUCCEEDED(d->GetStreamSourceFreq(b.element.Stream,&frequency))&&frequency==1&&b.stride<=256&&(b.stride==0||b.element.Offset+b.size<=b.stride),"stream_layout");
        bound.push_back(b);}
    ComPtr<IDirect3DVertexBuffer9> vb0;UINT offset0{},stride0{};Need(SUCCEEDED(d->GetStreamSource(0,&vb0,&offset0,&stride0))&&vb0&&streams[0]&&vb0.Get()==streams[0]->resource,"missing_binding");
    ComPtr<IDirect3DIndexBuffer9> ib;Need(SUCCEEDED(d->GetIndices(&ib))&&ib&&ib.Get()==ie.resource,"resource_identity");
    D3DINDEXBUFFER_DESC desc{};Need(SUCCEEDED(ib->GetDesc(&desc))&&desc.Format==D3DFMT_INDEX16,"index_format");
    D3DVIEWPORT9 viewport{};ComPtr<IDirect3DSurface9> target;D3DSURFACE_DESC targetDesc{};
    Need(SUCCEEDED(d->GetViewport(&viewport))&&SUCCEEDED(d->GetRenderTarget(0,&target))&&target&&SUCCEEDED(target->GetDesc(&targetDesc)),"target_query");
    Need(std::isfinite(viewport.MinZ)&&std::isfinite(viewport.MaxZ),"viewport_nonfinite");
    std::array<vsi::Vec,256> registers{};Need(SUCCEEDED(d->GetVertexShaderConstantF(0,registers[0].data(),256)),"constant_query");
    std::set<unsigned> used;for(unsigned r=0;r<256;++r)if(program.constants[r]){Need(known[r],"unknown_constants");used.insert(r);}
    auto lookup=[&](unsigned r)->const vsi::Vec*{return known[r]?&registers[r]:nullptr;};
    const std::size_t corners=std::size_t(draw.primitives)*3;const auto start=std::uint64_t(draw.start)*2;Known(ie,start,corners*2);
    std::vector<std::string> raw(bound.size());std::vector<vsi::Vec> clips;clips.reserve(corners);
    for(std::size_t i=0;i<corners;++i){std::uint16_t index{};memcpy(&index,ie.bytes.data()+start+i*2,2);Need(index>=draw.minimum&&std::uint64_t(index)<std::uint64_t(draw.minimum)+draw.vertices,"declared_index_range");
        const auto vertex=std::int64_t(draw.base)+index;Need(vertex>=0,"negative_vertex");
        std::array<vsi::Vec,16> inputs{};for(auto& v:inputs)v={0,0,0,1};
        for(std::size_t k=0;k<bound.size();++k){const auto& b=bound[k];const auto address=std::uint64_t(b.offset)+std::uint64_t(vertex)*b.stride+b.element.Offset;
            Known(*b.evidence,address,b.size);inputs[b.input.reg]=vsi::ConvertInput(b.element.Type,b.evidence->bytes.data()+address);raw[k]+=Hex(b.evidence->bytes.data()+address,b.size);}
        for(auto r:vsi::RelativeReads(program,inputs,lookup)){Need(known[r],"unknown_constants");used.insert(r);}
        clips.push_back(vsi::Evaluate(program,inputs,lookup));}
    // The camera the program's constant table names, when its registers are known: the converter needs it to place the clip positions.
    std::string camera="null";
    auto all=[&](unsigned first,unsigned n){for(unsigned r=first;r<first+n;++r)if(r>=256||!known[r])return false;return true;};
    if(program.camera.viewProjection&&all(*program.camera.viewProjection,4)){for(unsigned k=0;k<4;++k)used.insert(*program.camera.viewProjection+k);camera="{\"view_projection\":"+std::to_string(*program.camera.viewProjection)+"}";}
    else if(program.camera.modelViewProjection&&program.camera.model&&all(*program.camera.modelViewProjection,4)&&all(*program.camera.model,3)){
        for(unsigned k=0;k<4;++k)used.insert(*program.camera.modelViewProjection+k);for(unsigned k=0;k<3;++k)used.insert(*program.camera.model+k);
        camera="{\"model_view_projection\":"+std::to_string(*program.camera.modelViewProjection)+",\"model\":"+std::to_string(*program.camera.model)+"}";}
    std::string list="[",values,inputs="[";for(auto r:used){list+=(list.size()>1?",":"")+std::to_string(r);values+=Hex(registers[r].data(),16);}list+="]";
    for(std::size_t k=0;k<bound.size();++k){const auto& b=bound[k];inputs+=std::string(k?",":"")+"{\"register\":"+std::to_string(b.input.reg)+",\"usage\":"+std::to_string(b.input.usage)+",\"usage_index\":"+std::to_string(b.input.usageIndex)
        +",\"stream\":"+std::to_string(b.element.Stream)+",\"element_offset\":"+std::to_string(b.element.Offset)+",\"type\":"+std::to_string(b.element.Type)+",\"stream_offset\":"+std::to_string(b.offset)+",\"stride\":"+std::to_string(b.stride)
        +",\"vb_size\":"+std::to_string(b.evidence->bytes.size())+",\"values\":\""+raw[k]+"\"}";}
    inputs+="]";
    return "\"shader\":\""+Hex(code.data(),code.size()*4)+"\",\"declaration\":\""+Hex(elements.data(),count*8)+"\""
        +Tail(viewport,targetDesc,offset0,stride0,draw,*streams[0],ie,start,corners)+",\"clip\":\""+Hex(clips.data(),corners*16)+"\""
        +",\"interpreted\":{\"constants\":{\"registers\":"+list+",\"values\":\""+values+"\"},\"camera\":"+camera+",\"inputs\":"+inputs+"}";
}
std::string Capture(IDirect3DDevice9* d,Draw draw,const Evidence& ve,const Evidence& ie,const std::array<bool,256>& known,bool material,const Evidence* flex,const StreamEvidence* streams){
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->GetVertexShader(&vs))&&vs,"missing_shader");UINT size{};
    Need(SUCCEEDED(vs->GetFunction(nullptr,&size)),"unsupported_shader");
    if(streams&&size>=8&&size<=16384&&size%4==0){std::vector<DWORD> code(size/4);UINT read=size;
        Need(SUCCEEDED(vs->GetFunction(code.data(),&read))&&read==size,"shader_query");
        const auto digest=scene::Digest(code.data(),size);std::string hex;const char* h="0123456789abcdef";for(auto b:digest){hex+=h[b>>4];hex+=h[b&15];}
        if(std::find(vsi::InterpretedPrograms.begin(),vsi::InterpretedPrograms.end(),hex)!=vsi::InterpretedPrograms.end())return CaptureInterpreted(d,draw,ie,known,material,*streams,code);}
    if(size==FlexProgramBytes)return CaptureFlex(d,draw,ve,ie,known,material,flex);
    if(size==SkinProgramBytes)return CaptureSkin(d,draw,ve,ie,known,material,flex);
    Need(size==612,"unsupported_shader");std::array<DWORD,153> code{};
    Need(SUCCEEDED(vs->GetFunction(code.data(),&size))&&size==612,"shader_query");Admit({reinterpret_cast<const std::uint8_t*>(code.data()),612});
    Need(draw.primitives&&draw.primitives<=4096&&draw.vertices&&draw.vertices<=65536,"draw_budget");
    ComPtr<IDirect3DVertexDeclaration9> declaration;Need(SUCCEEDED(d->GetVertexDeclaration(&declaration))&&declaration,"missing_layout");
    std::array<D3DVERTEXELEMENT9,65> elements{};UINT count=65;Need(SUCCEEDED(declaration->GetDeclaration(elements.data(),&count))&&count&&count<=65&&elements[count-1].Stream==255,"layout_query");
    unsigned positions=0;for(UINT i=0;i+1<count;++i)if(elements[i].Usage==D3DDECLUSAGE_POSITION&&elements[i].UsageIndex==0){auto e=elements[i];Need(e.Stream==0&&e.Offset==0&&e.Type==D3DDECLTYPE_FLOAT3&&e.Method==D3DDECLMETHOD_DEFAULT,"position_layout");++positions;}Need(positions==1,"position_layout");
    ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;UINT offset{},stride{},frequency{};
    Need(SUCCEEDED(d->GetStreamSource(0,&vb,&offset,&stride))&&vb&&SUCCEEDED(d->GetIndices(&ib))&&ib,"missing_binding");
    Need(vb.Get()==ve.resource&&ib.Get()==ie.resource,"resource_identity");Need(SUCCEEDED(d->GetStreamSourceFreq(0,&frequency))&&frequency==1&&stride>=12&&stride<=256,"stream_layout");
    D3DINDEXBUFFER_DESC desc{};Need(SUCCEEDED(ib->GetDesc(&desc))&&desc.Format==D3DFMT_INDEX16,"index_format");
    std::array<Vec,2> materialConstants{};
    if(material){Need(draw.primitives<=1024&&stride==48,"material_layout_or_budget");
        for(auto expected:std::array<D3DVERTEXELEMENT9,3>{{{0,24,D3DDECLTYPE_D3DCOLOR,0,D3DDECLUSAGE_COLOR,0},{0,28,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,36,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,1}}}){
            unsigned matches=0;for(UINT i=0;i+1<count;++i)if(elements[i].Usage==expected.Usage&&elements[i].UsageIndex==expected.UsageIndex){Need(memcmp(&elements[i],&expected,8)==0,"material_layout_or_budget");++matches;}Need(matches==1,"material_layout_or_budget");}
        for(unsigned i=0;i<2;++i){UINT reg=i?16:12;Need(known[reg],"unknown_constants");Need(SUCCEEDED(d->GetVertexShaderConstantF(reg,materialConstants[i].data(),1)),"constant_query");}}
    Constants constants{};constexpr UINT registers[]={0,4,5,6,7,58,59,60};
    D3DVIEWPORT9 viewport{};ComPtr<IDirect3DSurface9> target;D3DSURFACE_DESC targetDesc{};
    Need(SUCCEEDED(d->GetViewport(&viewport))&&SUCCEEDED(d->GetRenderTarget(0,&target))&&target&&SUCCEEDED(target->GetDesc(&targetDesc)),"target_query");
    Need(std::isfinite(viewport.MinZ)&&std::isfinite(viewport.MaxZ),"viewport_nonfinite");
    for(unsigned i=0;i<8;++i){Need(known[registers[i]],"unknown_constants");Need(SUCCEEDED(d->GetVertexShaderConstantF(registers[i],constants.rows[i].data(),1)),"constant_query");constants.known[i]=true;}
    const std::size_t corners=std::size_t(draw.primitives)*3;const auto start=std::uint64_t(draw.start)*2;Known(ie,start,corners*2);
    std::vector<std::array<float,3>> inputs;std::vector<Result> outputs;inputs.reserve(corners);outputs.reserve(corners);
    std::vector<std::array<float,4>> uvs;std::vector<std::uint32_t> colors;std::vector<MaterialResult> materialOutputs;
    for(std::size_t i=0;i<corners;++i){std::uint16_t index{};memcpy(&index,ie.bytes.data()+start+i*2,2);Need(index>=draw.minimum&&std::uint64_t(index)<std::uint64_t(draw.minimum)+draw.vertices,"declared_index_range");
        auto vertex=std::int64_t(draw.base)+index;Need(vertex>=0,"negative_vertex");auto address=std::uint64_t(offset)+std::uint64_t(vertex)*stride;Known(ve,address,12);
        std::array<float,3> input;memcpy(input.data(),ve.bytes.data()+address,12);inputs.push_back(input);outputs.push_back(Evaluate(input,constants));
        if(material){Known(ve,address+24,20);std::array<float,4> uv;std::uint32_t color;memcpy(&color,ve.bytes.data()+address+24,4);memcpy(uv.data(),ve.bytes.data()+address+28,16);uvs.push_back(uv);colors.push_back(color);materialOutputs.push_back(EvaluateMaterial(input,uv,color,constants,materialConstants));}}
    std::string materialData;if(material)materialData=",\"material_inputs\":{\"constants\":\""+Hex(materialConstants.data(),32)+"\",\"uv\":\""+Hex(uvs.data(),corners*16)+"\",\"color\":\""+Hex(colors.data(),corners*4)+"\",\"evaluated\":\""+Hex(materialOutputs.data(),corners*40)+"\"}";
    return "\"shader\":\""+Hex(code.data(),612)+"\",\"declaration\":\""+Hex(elements.data(),count*8)+"\",\"constants\":\""+Hex(constants.rows.data(),128)+"\",\"viewport\":\""+Hex(&viewport,sizeof(viewport))+"\",\"target\":["+std::to_string(targetDesc.Width)+","+std::to_string(targetDesc.Height)+","+std::to_string(targetDesc.Format)+","+std::to_string(targetDesc.MultiSampleType)+"],\"offset\":"+std::to_string(offset)+",\"stride\":"+std::to_string(stride)+",\"base\":"+std::to_string(draw.base)+",\"minimum\":"+std::to_string(draw.minimum)+",\"vertices\":"+std::to_string(draw.vertices)+",\"start\":"+std::to_string(draw.start)+",\"primitives\":"+std::to_string(draw.primitives)+",\"vb_size\":"+std::to_string(ve.bytes.size())+",\"ib_size\":"+std::to_string(ie.bytes.size())+",\"indices\":\""+Hex(ie.bytes.data()+start,corners*2)+"\",\"positions\":\""+Hex(inputs.data(),corners*12)+"\",\"evaluated\":\""+Hex(outputs.data(),corners*32)+"\""+materialData;
}
}
