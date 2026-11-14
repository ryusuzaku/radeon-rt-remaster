#include "vs_interpreter.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <map>
#include <stdexcept>

namespace rrt::shader::vsi {
namespace {
// Shader token layout (d3d9types.h): register type is split over bits 28-30 and 11-12.
constexpr std::uint32_t TypeOf(std::uint32_t t){return ((t>>28)&7)|((t>>8)&0x18);}
constexpr std::uint32_t RegOf(std::uint32_t t){return t&0x7ff;}
enum Type:std::uint32_t {Temp=0,InputReg=1,Const=2,Addr=3,RastOut=4,AttrOut=5,TexOut=6,ConstInt=7,ConstBool=14,Loop=15};
enum Op:std::uint32_t {Mov=1,Add=2,Sub=3,Mad=4,Mul=5,Dp3=8,Dp4=9,Min=10,Max=11,Call=25,CallNz=26,LoopOp=27,Ret=28,EndLoop=29,Label=30,Dcl=31,
    RepOp=38,EndRep=39,If=40,Ifc=41,Else=42,EndIf=43,Break=44,Breakc=45,Mova=46,DefB=47,DefI=48,Def=81,Comment=0xfffe,End=0xffff,Abs=35};
constexpr std::uint32_t Version20=0xfffe0200;
// sub is not accepted: the D3D9 runtime refuses it in vs_2_0 (the compiler emits add with a negated operand instead).
bool Supported(std::uint32_t op){return op==Mov||op==Add||op==Mad||op==Mul||op==Dp3||op==Dp4||op==Min||op==Max||op==Mova||op==Abs;}
unsigned Sources(std::uint32_t op){switch(op){case Mad:return 3;case Add:case Sub:case Mul:case Dp3:case Dp4:case Min:case Max:return 2;default:return 1;}}
[[noreturn]] void Refuse(const char* why){throw std::runtime_error(why);}
float F(float v){if(!std::isfinite(v))Refuse("position overflow");return v;}

// Which source components an instruction reads to produce the destination components in `mask`.
std::uint32_t SourceMask(std::uint32_t op,const Source& s,std::uint32_t mask){
    std::uint32_t out=0;
    if(op==Dp4){for(unsigned c=0;c<4;++c)out|=1u<<s.swizzle[c];return out;}
    if(op==Dp3){for(unsigned c=0;c<3;++c)out|=1u<<s.swizzle[c];return out;}
    for(unsigned c=0;c<4;++c)if(mask&(1u<<c))out|=1u<<s.swizzle[c];
    return out;
}

// D3DXSHADER_CONSTANTTABLE in the 'CTAB' comment: find the first register of the named float constants.
void ReadConstantTable(std::span<const std::uint32_t> body,Camera& camera){
    if(body.size()<8||body[0]!=0x42415443)return; // 'CTAB'
    auto bytes=reinterpret_cast<const std::uint8_t*>(body.data()+1);const std::size_t size=(body.size()-1)*4;
    auto u32=[&](std::size_t at)->std::uint32_t{if(at+4>size)return 0;std::uint32_t v;memcpy(&v,bytes+at,4);return v;};
    auto u16=[&](std::size_t at)->std::uint16_t{if(at+2>size)return 0;std::uint16_t v;memcpy(&v,bytes+at,2);return v;};
    const std::uint32_t count=u32(12),info=u32(16);if(count>256||info>=size)return;
    for(std::uint32_t i=0;i<count;++i){const std::size_t at=info+i*20;const std::uint32_t name=u32(at);if(name>=size)continue;
        std::string text;for(std::size_t k=name;k<size&&bytes[k]&&text.size()<64;++k)text+=char(bytes[k]);
        const std::uint16_t set=u16(at+4),index=u16(at+6),registers=u16(at+8);if(set!=2)continue; // D3DXRS_FLOAT4
        if(text=="cViewProj"&&registers>=4)camera.viewProjection=index;
        else if(text=="cModelViewProj"&&registers>=4)camera.modelViewProjection=index;
        else if(text=="cModel"&&registers>=3)camera.model=index;}
}
}

Program Analyse(std::span<const std::uint32_t> t){
    Program p;
    try{
        if(t.empty()||t[0]!=Version20)Refuse("unsupported_shader_model");
        std::size_t i=1;unsigned depth=0;
        auto dst=[&](std::uint32_t token){Destination d;d.type=TypeOf(token);d.reg=RegOf(token);d.mask=(token>>16)&15;
            const std::uint32_t mod=(token>>20)&15;if(mod&~3u)Refuse("unsupported_result_modifier");d.saturate=mod&1;if((token>>24)&15)Refuse("unsupported_result_shift");
            if(token&(1u<<13))Refuse("relative_destination");return d;};
        while(i<t.size()){
            const std::uint32_t token=t[i];const std::uint32_t op=token&0xffff;
            if(op==End)break;
            if(op==Comment){const std::uint32_t length=(token>>16)&0x7fff;if(i+1+length>t.size())Refuse("truncated_program");ReadConstantTable(t.subspan(i+1,length),p.camera);i+=1+length;continue;}
            const std::uint32_t length=(token>>24)&15;if(i+1+length>t.size())Refuse("truncated_program");
            if(token&(1u<<28))Refuse("predicated_instruction");
            auto params=t.subspan(i+1,length);
            if(op==Call||op==CallNz||op==Label||op==Ret)Refuse("subroutines");
            if(op==Dcl){if(length!=2)Refuse("malformed_dcl");auto d=dst(params[1]);
                if(d.type==InputReg){if(d.reg>=16)Refuse("malformed_dcl");p.inputDeclared[d.reg]=true;p.inputUsage[d.reg]=params[0]&31;p.inputUsageIndex[d.reg]=(params[0]>>16)&15;p.maxInput=std::max(p.maxInput,d.reg);}
                i+=1+length;continue;}
            if(op==Def){if(length!=5)Refuse("malformed_def");auto d=dst(params[0]);if(d.type!=Const||d.reg>=256)Refuse("malformed_def");Vec v;memcpy(v.data(),&params[1],16);p.defs[d.reg]=v;i+=1+length;continue;}
            if(op==DefB||op==DefI){i+=1+length;continue;}
            if(op==If||op==Ifc||op==LoopOp||op==RepOp){++depth;i+=1+length;continue;}
            if(op==Else){if(!depth)Refuse("malformed_flow_control");i+=1+length;continue;}
            if(op==EndIf||op==EndLoop||op==EndRep){if(!depth)Refuse("malformed_flow_control");--depth;i+=1+length;continue;}
            Instruction in;in.opcode=op;in.depth=depth;in.token=i;
            if(op==Break||op==Breakc){in.dst={};p.code.push_back(in);i+=1+length;continue;}
            if(length==0){i+=1;continue;}
            in.dst=dst(params[0]);std::size_t k=1;
            while(k<params.size()){Source s;const std::uint32_t token2=params[k++];s.type=TypeOf(token2);s.reg=RegOf(token2);
                for(unsigned c=0;c<4;++c)s.swizzle[c]=(token2>>(16+2*c))&3;s.modifier=(token2>>24)&15;
                if(token2&(1u<<13)){if(k>=params.size())Refuse("truncated_program");const std::uint32_t address=params[k++];s.relative=true;s.addressComponent=(address>>16)&3;
                    if(TypeOf(address)!=Addr||RegOf(address)!=0)Refuse("unsupported_relative_address");}
                in.src.push_back(s);}
            if(in.dst.type==Temp)p.maxTemp=std::max(p.maxTemp,in.dst.reg);
            if(in.dst.type==TexOut&&in.dst.reg<12)p.outputsWritten[in.dst.reg]=true;
            p.code.push_back(std::move(in));i+=1+length;
        }
        if(depth)Refuse("malformed_flow_control");
        // Backward slice from oPos, per component.
        std::map<std::pair<std::uint32_t,std::uint32_t>,std::uint32_t> needed;bool wrotePosition=false;
        for(auto it=p.code.rbegin();it!=p.code.rend();++it){auto& in=*it;
            std::uint32_t want=0;
            if(in.dst.type==RastOut&&in.dst.reg==0){want=in.dst.mask;wrotePosition=true;}
            else if(in.dst.type==Temp||in.dst.type==Addr){auto f=needed.find({in.dst.type,in.dst.reg});if(f!=needed.end()){want=f->second&in.dst.mask;f->second&=~in.dst.mask;}}
            if(!want)continue;
            in.slice=true;
            if(in.depth)Refuse("position_in_flow_control");
            if(!Supported(in.opcode))Refuse("unsupported_slice_opcode");
            if(in.src.size()!=Sources(in.opcode))Refuse("malformed_instruction");
            if(in.dst.saturate)Refuse("unsupported_result_modifier");
            for(const auto& s:in.src){
                if(s.modifier!=0&&s.modifier!=1)Refuse("unsupported_source_modifier"); // vs_2_0 has negate only; _abs is a later model
                const std::uint32_t comps=SourceMask(in.opcode,s,want);
                if(s.relative){if(s.type!=Const)Refuse("unsupported_relative_address");needed[{Addr,0}]|=1u<<s.addressComponent;p.relativeBases.push_back(s.reg);continue;}
                if(s.type==Temp||s.type==Addr)needed[{s.type,s.reg}]|=comps;
                else if(s.type==InputReg){if(s.reg>=16||!p.inputDeclared[s.reg])Refuse("undeclared_input");
                    auto f=std::find_if(p.inputs.begin(),p.inputs.end(),[&](const Input& x){return x.reg==s.reg;});
                    if(f==p.inputs.end())p.inputs.push_back({s.reg,p.inputUsage[s.reg],p.inputUsageIndex[s.reg],comps});else f->mask|=comps;}
                else if(s.type==Const){if(s.reg>=256)Refuse("constant_range");if(!p.defs[s.reg])p.constants[s.reg]=true;}
                else Refuse("unsupported_slice_register");}
        }
        if(!wrotePosition)Refuse("no_position_output");
        // Canonical order (by register), so the ledger and the Python reader list the same inputs in the same order.
        std::sort(p.inputs.begin(),p.inputs.end(),[](const Input& a,const Input& b){return a.reg<b.reg;});
        for(const auto& [key,mask]:needed)if(mask&&key.first==Temp)Refuse("uninitialised_temporary");
        if(auto f=needed.find({Addr,0});f!=needed.end()&&f->second)Refuse("uninitialised_address");
        p.ok=true;
    }catch(const std::exception& e){p.ok=false;p.reason=e.what();}
    return p;
}

namespace {
struct Machine {
    const Program& p;const std::array<Vec,16>& inputs;const Constants& constants;std::array<Vec,32> temps{};std::array<int,4> address{};
    std::vector<unsigned>* relative{};
    Vec Read(const Source& s){
        Vec raw;
        if(s.type==Temp)raw=temps.at(s.reg);
        else if(s.type==InputReg)raw=inputs.at(s.reg);
        else if(s.type==Addr){for(unsigned c=0;c<4;++c)raw[c]=float(address[c]);}
        else if(s.type==Const){long index=long(s.reg)+(s.relative?address[s.addressComponent]:0);if(index<0||index>=256)Refuse("constant_range");
            if(relative&&s.relative)relative->push_back(unsigned(index));
            if(p.defs[unsigned(index)])raw=*p.defs[unsigned(index)];else{auto v=constants(unsigned(index));if(!v)Refuse("unknown position constant");raw=*v;}
            for(float x:raw)if(!std::isfinite(x))Refuse("nonfinite constant");}
        else Refuse("unsupported_slice_register");
        Vec out;for(unsigned c=0;c<4;++c){float v=raw[s.swizzle[c]];if(s.modifier==1)v=-v;out[c]=v;}
        return out;
    }
};
}

static Vec Run(const Program& p,const std::array<Vec,16>& inputs,const Constants& constants,std::vector<unsigned>* relative){
    if(!p.ok)Refuse("position program not admitted");
    for(const auto& in:p.inputs)for(unsigned c=0;c<4;++c)if((in.mask>>c)&1&&!std::isfinite(inputs[in.reg][c]))Refuse("nonfinite position");
    Machine m{p,inputs,constants};m.relative=relative;Vec position{};
    for(const auto& in:p.code){if(!in.slice)continue;
        std::array<Vec,3> s{};for(std::size_t k=0;k<in.src.size();++k)s[k]=m.Read(in.src[k]);
        Vec r{};
        switch(in.opcode){
            case Mov:r=s[0];break;
            case Abs:for(unsigned c=0;c<4;++c)r[c]=std::fabs(s[0][c]);break;
            case Add:for(unsigned c=0;c<4;++c)r[c]=F(s[0][c]+s[1][c]);break;
            case Sub:for(unsigned c=0;c<4;++c)r[c]=F(s[0][c]-s[1][c]);break;
            case Mul:for(unsigned c=0;c<4;++c)r[c]=F(s[0][c]*s[1][c]);break;
            case Mad:for(unsigned c=0;c<4;++c)r[c]=F(F(s[0][c]*s[1][c])+s[2][c]);break;
            case Min:for(unsigned c=0;c<4;++c)r[c]=s[0][c]<s[1][c]?s[0][c]:s[1][c];break;
            case Max:for(unsigned c=0;c<4;++c)r[c]=s[0][c]>=s[1][c]?s[0][c]:s[1][c];break;
            case Dp3:{float v=0;for(unsigned c=0;c<3;++c)v=F(v+F(s[0][c]*s[1][c]));r={v,v,v,v};break;}
            case Dp4:{float v=0;for(unsigned c=0;c<4;++c)v=F(v+F(s[0][c]*s[1][c]));r={v,v,v,v};break;}
            case Mova:for(unsigned c=0;c<4;++c)if((in.dst.mask>>c)&1){const float v=std::floor(s[0][c]+.5f);if(!(v>=-1024&&v<=1024))Refuse("constant_range");m.address[c]=int(v);}continue;
            default:Refuse("unsupported_slice_opcode");}
        for(unsigned c=0;c<4;++c)if((in.dst.mask>>c)&1){if(in.dst.type==Temp)m.temps.at(in.dst.reg)[c]=r[c];else position[c]=r[c];}
    }
    return position;
}
Vec Evaluate(const Program& p,const std::array<Vec,16>& inputs,const Constants& constants){return Run(p,inputs,constants,nullptr);}
std::vector<unsigned> RelativeReads(const Program& p,const std::array<Vec,16>& inputs,const Constants& constants){
    // Relative reads are found with the address register as computed; constants that are unknown are reported, not refused,
    // so capture can name exactly the registers a vertex needs. Unknown statically-indexed constants still refuse.
    std::vector<unsigned> reads;static const Vec zero{};
    Constants lenient=[&](unsigned reg)->const Vec*{auto v=constants(reg);return v?v:&zero;};
    Run(p,inputs,lenient,&reads);return reads;
}

std::vector<std::uint32_t> Instrument(std::span<const std::uint32_t> t,const Program& p,std::uint32_t& pointInput){
    if(!p.ok)Refuse("position program not admitted");
    if(p.maxTemp+2>=12)Refuse("no_free_temporary");
    const std::uint32_t positionTemp=p.maxTemp+1,discardTemp=p.maxTemp+2;
    pointInput=16;for(std::uint32_t r=15;r<16;--r)if(!p.inputDeclared[r]){pointInput=r;break;}
    if(pointInput>=16)Refuse("no_free_input");
    auto dstToken=[](std::uint32_t type,std::uint32_t reg,std::uint32_t mask){return 0x80000000u|((type&7)<<28)|(((type>>3)&3)<<11)|(mask<<16)|reg;};
    auto srcToken=[](std::uint32_t type,std::uint32_t reg){return 0x80000000u|((type&7)<<28)|(((type>>3)&3)<<11)|(0xE4u<<16)|reg;};
    std::vector<std::uint32_t> out(t.begin(),t.end());
    for(const auto& in:p.code){if(in.opcode==Break||in.opcode==Breakc)continue;
        const std::size_t at=in.token+1;std::uint32_t& d=out[at];
        if(TypeOf(d)==RastOut&&RegOf(d)==0)d=(d&~(0x70001800u|0x7ffu))|(Temp<<28)|positionTemp;
        else if(TypeOf(d)==TexOut&&RegOf(d)==7)d=(d&~(0x70001800u|0x7ffu))|(Temp<<28)|discardTemp;}
    if(out.size()<2||out.back()!=0x0000ffffu)Refuse("truncated_program");const std::size_t end=out.size()-1; // the END token, never a scan: def data may hold the same value
    // dcl_texcoord15 v[pointInput] right after the version token; oPos = v[pointInput]; oT7 = r[positionTemp].
    std::vector<std::uint32_t> head={out[0],Dcl|(2u<<24),0x80000000u|5u|(15u<<16),dstToken(InputReg,pointInput,15)};
    std::vector<std::uint32_t> tail={Mov|(2u<<24),dstToken(RastOut,0,15),srcToken(InputReg,pointInput),Mov|(2u<<24),dstToken(TexOut,7,15),srcToken(Temp,positionTemp),0x0000ffffu};
    std::vector<std::uint32_t> result=head;result.insert(result.end(),out.begin()+1,out.begin()+std::ptrdiff_t(end));result.insert(result.end(),tail.begin(),tail.end());
    if(p.inputDeclared[pointInput])Refuse("no_free_input");
    for(unsigned r=0;r<16;++r)if(p.inputDeclared[r]&&p.inputUsage[r]==5&&p.inputUsageIndex[r]==15)Refuse("no_free_input");
    return result;
}

std::size_t InputSize(std::uint32_t type){
    switch(type){case 0:return 4;case 1:return 8;case 2:return 12;case 3:return 16;case 4:case 5:case 8:case 6:case 9:case 11:return 4;case 7:case 10:case 12:return 8;default:Refuse("unsupported_input_type");}
}
Vec ConvertInput(std::uint32_t type,const std::uint8_t* b){
    Vec v{0,0,0,1};
    auto s16=[&](unsigned i){std::int16_t x;memcpy(&x,b+2*i,2);return x;};auto u16=[&](unsigned i){std::uint16_t x;memcpy(&x,b+2*i,2);return x;};
    switch(type){
        case 0:case 1:case 2:case 3:for(unsigned i=0;i<=type;++i)memcpy(&v[i],b+4*i,4);break;          // FLOAT1..FLOAT4
        case 4:v={b[2]/255.f,b[1]/255.f,b[0]/255.f,b[3]/255.f};break;                                   // D3DCOLOR (BGRA in memory)
        case 5:v={float(b[0]),float(b[1]),float(b[2]),float(b[3])};break;                               // UBYTE4
        case 6:v={float(s16(0)),float(s16(1)),0,1};break;                                               // SHORT2
        case 7:v={float(s16(0)),float(s16(1)),float(s16(2)),float(s16(3))};break;                       // SHORT4
        case 8:v={b[0]/255.f,b[1]/255.f,b[2]/255.f,b[3]/255.f};break;                                   // UBYTE4N
        case 9:v={s16(0)/32767.f,s16(1)/32767.f,0,1};break;                                             // SHORT2N
        case 10:v={s16(0)/32767.f,s16(1)/32767.f,s16(2)/32767.f,s16(3)/32767.f};break;                  // SHORT4N
        case 11:v={u16(0)/65535.f,u16(1)/65535.f,0,1};break;                                            // USHORT2N
        case 12:v={u16(0)/65535.f,u16(1)/65535.f,u16(2)/65535.f,u16(3)/65535.f};break;                  // USHORT4N
        default:Refuse("unsupported_input_type");}
    return v;
}
}
