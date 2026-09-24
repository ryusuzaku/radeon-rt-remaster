#pragma once
#include <d3d9.h>
#include <array>
namespace rrt::shader {
// ps_2_0; mov oC0,c0; end. No textures, interpolators or implicit constants.
inline constexpr std::array<DWORD,5> ColorProgram={0xffff0200,0x02000001,0x800f0800,0xa0e40000,0x0000ffff};
inline constexpr std::pair<D3DRENDERSTATETYPE,DWORD> ColorExtraStates[]={
    {D3DRS_FOGENABLE,0},{D3DRS_CLIPPING,1},{D3DRS_CLIPPLANEENABLE,0},
    {D3DRS_DITHERENABLE,0},{D3DRS_MULTISAMPLEMASK,0xffffffff},{D3DRS_ANTIALIASEDLINEENABLE,0}};
}
