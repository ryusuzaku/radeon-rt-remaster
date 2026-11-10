#pragma once
// A CPU interpreter for the position path of a vs_2_0 vertex program (docs/VS_INTERPRETER.md).
//
// Analyse() parses the token stream, takes the backward slice of every instruction whose result reaches oPos (per register
// component, through write masks, swizzles and relative addressing) and refuses, with a named reason, anything outside a small
// subset: other shader models, subroutines, unsupported opcodes, source or result modifiers in the slice, and slice instructions
// inside flow control. Evaluate() runs only the slice, in program order, one float32 operation at a time, so compiler reordering
// and register allocation do not matter. Instrument() rewrites the program so a GPU oracle can read oPos back exactly.
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace rrt::shader::vsi {
using Vec=std::array<float,4>;

struct Source {std::uint32_t type{},reg{};std::array<std::uint8_t,4> swizzle{0,1,2,3};std::uint32_t modifier{};bool relative{};std::uint32_t addressComponent{};};
struct Destination {std::uint32_t type{},reg{},mask{};bool saturate{};};
struct Instruction {std::uint32_t opcode{};Destination dst;std::vector<Source> src;unsigned depth{};bool slice{};std::size_t token{};};

// An input register the slice reads, with its declared usage and the components it needs.
struct Input {std::uint32_t reg{},usage{},usageIndex{},mask{};};
// A camera named in the program's constant table, by its first register.
struct Camera {std::optional<unsigned> viewProjection,modelViewProjection,model;};

struct Program {
    bool ok{};std::string reason;               // reason names the first refusal when !ok
    std::vector<Instruction> code;              // every instruction; `slice` marks the position path
    std::vector<Input> inputs;                  // inputs the slice reads
    std::array<bool,256> constants{};           // float registers the slice reads by static index (excluding def'd ones)
    std::vector<std::uint32_t> relativeBases;   // base registers of relative reads, e.g. 58 for c58[a0.x]
    std::array<std::optional<Vec>,256> defs;    // def'd constants
    Camera camera;
    std::array<std::uint32_t,16> inputUsage{},inputUsageIndex{};std::array<bool,16> inputDeclared{};
    std::uint32_t maxTemp{},maxInput{};std::array<bool,12> outputsWritten{}; // for Instrument()
};

Program Analyse(std::span<const std::uint32_t> tokens);

// Float constant lookup for Evaluate(): return the register's value, or nullptr when it is not known (which refuses the vertex).
using Constants=std::function<const Vec*(unsigned reg)>;
// Runs the slice for one vertex. `inputs[r]` is input register r as the device would present it. Throws std::runtime_error with
// "unknown position constant", "constant_range", "nonfinite position" or "position overflow".
Vec Evaluate(const Program&,const std::array<Vec,16>& inputs,const Constants&);
// The float registers one vertex reads through relative addressing (for capture to require and record exactly those).
std::vector<unsigned> RelativeReads(const Program&,const std::array<Vec,16>& inputs,const Constants&);

// Rewrites a program for the GPU oracle: oPos writes go to a free temporary, the program's own oT7 writes to another, and two
// instructions are appended: oPos = v[input] (a fixed point position supplied per vertex) and oT7 = the temporary. Throws when no
// free temporary or input register exists.
std::vector<std::uint32_t> Instrument(std::span<const std::uint32_t> tokens,const Program&,std::uint32_t& pointInput);

// Converts one declaration element's bytes into the register value the device presents (missing components default to 0,0,0,1).
// Throws "unsupported_input_type" for types outside FLOAT1-4, D3DCOLOR, UBYTE4(N), SHORT2/4(N) and USHORT2/4N.
Vec ConvertInput(std::uint32_t declType,const std::uint8_t* bytes);
std::size_t InputSize(std::uint32_t declType);
}
