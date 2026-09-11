#pragma once
#include <d3d9.h>
#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace rrt::scene {
constexpr std::uint32_t Version=1;
constexpr std::size_t MaxBytes=64*1024*1024, MaxResourceBytes=16*1024*1024;
constexpr std::uint32_t MaxDraws=4096, MaxVertices=500000;
constexpr DWORD Fvf=D3DFVF_XYZ|D3DFVF_DIFFUSE|D3DFVF_TEX1;
// Fixed schema slots, not arbitrary API identifiers supplied by a capture file.
inline constexpr D3DRENDERSTATETYPE RenderStates[]={
    D3DRS_ZENABLE,D3DRS_FILLMODE,D3DRS_SHADEMODE,D3DRS_ZWRITEENABLE,
    D3DRS_ALPHATESTENABLE,D3DRS_SRCBLEND,D3DRS_DESTBLEND,D3DRS_CULLMODE,
    D3DRS_ZFUNC,D3DRS_ALPHAREF,D3DRS_ALPHAFUNC,D3DRS_DITHERENABLE,
    D3DRS_ALPHABLENDENABLE,D3DRS_FOGENABLE,D3DRS_SPECULARENABLE,D3DRS_STENCILENABLE,
    D3DRS_CLIPPING,D3DRS_LIGHTING,D3DRS_COLORVERTEX,D3DRS_VERTEXBLEND,
    D3DRS_CLIPPLANEENABLE,D3DRS_COLORWRITEENABLE,D3DRS_BLENDOP,D3DRS_SCISSORTESTENABLE,
    D3DRS_SLOPESCALEDEPTHBIAS,D3DRS_MULTISAMPLEANTIALIAS,D3DRS_MULTISAMPLEMASK,
    D3DRS_BLENDFACTOR,D3DRS_SRGBWRITEENABLE,D3DRS_DEPTHBIAS,
    D3DRS_SEPARATEALPHABLENDENABLE,D3DRS_SRCBLENDALPHA,D3DRS_DESTBLENDALPHA,D3DRS_BLENDOPALPHA};
inline constexpr D3DTEXTURESTAGESTATETYPE TextureStates[]={
    D3DTSS_COLOROP,D3DTSS_COLORARG1,D3DTSS_COLORARG2,D3DTSS_ALPHAOP,
    D3DTSS_ALPHAARG1,D3DTSS_ALPHAARG2,D3DTSS_TEXCOORDINDEX,D3DTSS_TEXTURETRANSFORMFLAGS};
inline constexpr D3DSAMPLERSTATETYPE SamplerStates[]={
    D3DSAMP_ADDRESSU,D3DSAMP_ADDRESSV,D3DSAMP_ADDRESSW,D3DSAMP_BORDERCOLOR,
    D3DSAMP_MAGFILTER,D3DSAMP_MINFILTER,D3DSAMP_MIPFILTER,D3DSAMP_MIPMAPLODBIAS,
    D3DSAMP_MAXMIPLEVEL,D3DSAMP_MAXANISOTROPY,D3DSAMP_SRGBTEXTURE,D3DSAMP_ELEMENTINDEX,
    D3DSAMP_DMAPOFFSET};
using Hash=std::array<std::uint8_t,32>;
struct Vertex { float x,y,z; std::uint32_t color; float u,v; };
static_assert(sizeof(Vertex)==24);
struct State {
    D3DMATRIX world{},view{},projection{};
    D3DVIEWPORT9 viewport{};
    RECT scissor{};
    std::array<DWORD,std::size(RenderStates)> render{};
    std::array<DWORD,std::size(TextureStates)> texture{};
    std::array<DWORD,std::size(SamplerStates)> sampler{};
};
static_assert(sizeof(State)==452);
enum class Reason : std::uint32_t {
    shader=1, topology, state, resource, target, budget, readback, clear, operation, multipleDevices
};
const char* ReasonName(Reason reason);
struct Rejection { std::uint32_t ordinal; Reason reason; };
struct Draw {
    std::uint32_t ordinal{},width{},height{};
    State state{};
    std::vector<Vertex> vertices;
    std::vector<std::uint32_t> indices;
    std::vector<std::uint8_t> texture;
    Hash meshId{},textureId{},materialId{};
    // Transient capture status; never serialized as a successful draw.
    Reason failure{};
};
struct Scene {
    std::uint32_t frame{},width{},height{},clearColor{},attempted{};
    bool cleared{};
    std::vector<Draw> draws;
    std::vector<Rejection> rejected;
};
Hash Digest(const void* data,std::size_t size);
void Identify(Draw& draw);
std::string Hex(const Hash& hash);
void Validate(const Scene& scene);
void Save(const Scene& scene,const std::filesystem::path& path);
Scene Load(const std::filesystem::path& path,Hash* sourceDigest=nullptr);
}
