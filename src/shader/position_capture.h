#pragma once
#include "snapshot.h"
#include <string>
namespace rrt::shader::position {
// CPU-only evidence serialization, no shader execution or resource readback.
// `flex` is the shadow of the buffer bound to stream 2, when one is tracked; the second and third admitted programs read it.
// `known` covers the 256 float registers of vs_2_0, since the skinned program's bone palette reaches c216.
std::string Capture(IDirect3DDevice9*,Draw,const Evidence&,const Evidence&,const std::array<bool,256>&,bool material=false,const Evidence* flex=nullptr);
}
