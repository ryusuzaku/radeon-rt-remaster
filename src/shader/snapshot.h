#pragma once
#include <d3d9.h>
#include <array>
#include <span>
#include <vector>
#include <cstdint>

namespace rrt::shader {
constexpr std::size_t MaxBuffer=65536, MaxFile=160000;
struct Evidence {
    IDirect3DResource9* resource{}; // Borrowed, exact native resource identity.
    std::span<const std::uint8_t> bytes, initialized;
};
struct Draw { INT base{}; UINT minimum{},vertices{},start{},primitives{}; };
struct Snapshot {
    Draw draw;
    UINT width{},height{},offset{},stride{};
    D3DVIEWPORT9 viewport{};
    std::array<float,20> constants{};
    std::array<D3DVERTEXELEMENT9,2> declaration{};
    std::vector<DWORD> vs,ps;
    std::vector<std::uint8_t> vertex,index;
};
std::vector<DWORD> Program(bool pixel);
void Configure(IDirect3DDevice9* device);
Snapshot Capture(IDirect3DDevice9*,Draw,const Evidence&,const Evidence&,std::array<bool,5> initializedConstants);
void Validate(const Snapshot&);
std::vector<std::uint8_t> Encode(const Snapshot&);
Snapshot Decode(std::span<const std::uint8_t>);
void Replay(IDirect3DDevice9*,const Snapshot&);
}
