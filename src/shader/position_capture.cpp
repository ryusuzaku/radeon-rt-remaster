#include "position_capture.h"
#include "position.h"
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
}
std::string Capture(IDirect3DDevice9* d,Draw draw,const Evidence& ve,const Evidence& ie,const std::array<bool,61>& known,bool material){
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->GetVertexShader(&vs))&&vs,"missing_shader");UINT size{};
    Need(SUCCEEDED(vs->GetFunction(nullptr,&size))&&size==612,"unsupported_shader");std::array<DWORD,153> code{};
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
