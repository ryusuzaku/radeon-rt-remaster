#include "position.h"
#include "../scene/scene.h"
#include <cmath>
#include <stdexcept>
namespace rrt::shader::position {
void Admit(std::span<const std::uint8_t> code){
    constexpr scene::Hash expected={0x0c,0x16,0xf3,0xb5,0xa2,0xba,0x1f,0x9f,0x33,0x16,0x27,0x27,0xe7,0xed,0xa8,0x1e,0x02,0xd5,0x99,0xe2,0x0d,0x95,0x74,0x3f,0x05,0xa3,0xda,0xab,0x84,0x67,0x98,0xd2};
    if(code.size()!=612||scene::Digest(code.data(),code.size())!=expected)throw std::runtime_error("position program not admitted");
}
Result Evaluate(std::array<float,3> p,const Constants& c){
    for(auto value:p)if(!std::isfinite(value))throw std::runtime_error("nonfinite position");
    for(unsigned i=0;i<8;++i){if(!c.known[i])throw std::runtime_error("unknown position constant");for(auto v:c.rows[i])if(!std::isfinite(v))throw std::runtime_error("nonfinite constant");}
    auto a=c.rows[0][0],b=c.rows[0][1];Vec q={p[0]*b+a,p[1]*b+a,p[2]*b+a,p[0]*a+b};
    auto dot=[&](Vec row){float sum=0;for(unsigned j=0;j<4;++j)sum+=q[j]*row[j];if(!std::isfinite(sum))throw std::runtime_error("position overflow");return sum;};
    Result result{};for(unsigned i=0;i<4;++i)result.clip[i]=dot(c.rows[i+1]);for(unsigned i=0;i<3;++i)result.model[i]=dot(c.rows[i+5]);result.model[3]=1;return result;
}
void AdmitFlex(std::span<const std::uint8_t> code){
    constexpr scene::Hash expected={0xa8,0x4e,0xdf,0xd2,0x88,0x43,0xf7,0xc8,0xae,0xac,0x78,0xbc,0xb4,0x8c,0x03,0x18,0x43,0x26,0xc0,0x07,0x59,0x3e,0x8d,0x49,0xe9,0x97,0x77,0xc8,0xcf,0x1f,0x11,0xdc};
    if(code.size()!=FlexProgramBytes||scene::Digest(code.data(),code.size())!=expected)throw std::runtime_error("position program not admitted");
}
Result EvaluateFlex(std::array<float,3> p,std::array<float,3> flex,const FlexConstants& c){
    for(auto value:p)if(!std::isfinite(value))throw std::runtime_error("nonfinite position");
    for(auto value:flex)if(!std::isfinite(value))throw std::runtime_error("nonfinite position");
    for(unsigned i=0;i<9;++i){if(!c.known[i])throw std::runtime_error("unknown position constant");for(auto v:c.rows[i])if(!std::isfinite(v))throw std::runtime_error("nonfinite constant");}
    // Row order follows FlexRegisters: 0=c0, 1=c3, 2..5=c8..c11, 6..8=c58..c60. Each step is one float32 operation, as in the program.
    auto dot=[](const Vec& a,const Vec& row){float sum=0;for(unsigned j=0;j<4;++j)sum+=a[j]*row[j];if(!std::isfinite(sum))throw std::runtime_error("position overflow");return sum;};
    const float scale=c.rows[1][0];Vec r1{};for(unsigned i=0;i<3;++i){r1[i]=flex[i]*scale+p[i];if(!std::isfinite(r1[i]))throw std::runtime_error("position overflow");}r1[3]=1;
    Vec r0{dot(r1,c.rows[6]),dot(r1,c.rows[7]),dot(r1,c.rows[8]),c.rows[0][1]};
    Result result{};for(unsigned i=0;i<4;++i)result.clip[i]=dot(r0,c.rows[2+i]);for(unsigned i=0;i<3;++i)result.model[i]=r0[i];result.model[3]=1;return result;
}
MaterialResult EvaluateMaterial(std::array<float,3> p,std::array<float,4> uv,std::uint32_t color,const Constants& c,const std::array<Vec,2>& extra){
    Evaluate(p,c);for(float v:uv)if(!std::isfinite(v))throw std::runtime_error("nonfinite material input");
    for(auto row:extra)for(float v:row)if(!std::isfinite(v))throw std::runtime_error("nonfinite constant");
    auto a=c.rows[0][0],b=c.rows[0][1];Vec q={p[0]*b+a,p[1]*b+a,p[2]*b+a,p[0]*a+b};float distance=0;
    for(unsigned i=0;i<4;++i)distance+=q[i]*extra[0][i];float fog=extra[1][0]-distance*extra[1][3];if(fog<extra[1][2])fog=extra[1][2];
    MaterialResult result={uv[0],uv[1],uv[2]*b,uv[3]*b,((color>>16)&255)/255.f,((color>>8)&255)/255.f,(color&255)/255.f,((color>>24)&255)/255.f,distance,fog};
    for(float v:result)if(!std::isfinite(v))throw std::runtime_error("material output overflow");return result;
}
}
