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
}
