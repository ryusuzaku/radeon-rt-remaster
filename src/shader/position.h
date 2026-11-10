#pragma once
#include <array>
#include <span>
#include <cstdint>
namespace rrt::shader::position {
using Vec=std::array<float,4>;
struct Constants {std::array<Vec,8> rows;std::array<bool,8> known{};}; // c0,c4..7,c58..60
struct Result {Vec clip,model;}; // model is oT4.xyz, not a validated world-space claim
void Admit(std::span<const std::uint8_t> code);
Result Evaluate(std::array<float,3> input,const Constants& constants);
// uv0.xy, scaled uv1.xy, RGBA, oT4.w, raw oFog/oD1 scalar.
using MaterialResult=std::array<float,10>;
MaterialResult EvaluateMaterial(std::array<float,3>,std::array<float,4>,std::uint32_t,const Constants&,const std::array<Vec,2>&);

// Second admitted program: the 1420-byte static-prop vertex program (docs/HL2_FLEX_POSITION_CONTRACT.md).
// Position path only: r1 = (v0.xyz + v4.xyz * c3.x, 1); r0 = (dot(r1,c58), dot(r1,c59), dot(r1,c60), c0.y);
// clip = (dot(r0,c8), dot(r0,c9), dot(r0,c10), dot(r0,c11)); model = r0.xyz (also written to oT7.xyz).
constexpr std::size_t FlexProgramBytes=1420;
constexpr std::array<unsigned,9> FlexRegisters={0,3,8,9,10,11,58,59,60};
struct FlexConstants {std::array<Vec,9> rows;std::array<bool,9> known{};}; // in FlexRegisters order
void AdmitFlex(std::span<const std::uint8_t> code);
Result EvaluateFlex(std::array<float,3> input,std::array<float,3> flex,const FlexConstants& constants);
}
