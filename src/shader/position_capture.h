#pragma once
#include "snapshot.h"
#include <string>
namespace rrt::shader::position {
// CPU-only evidence serialization, no shader execution or resource readback.
// `flex` is the shadow of the buffer bound to stream 2, when one is tracked; the second and third admitted programs read it.
// `known` covers the 256 float registers of vs_2_0, since the skinned program's bone palette reaches c216.
// `streams[s]` is the shadow of the buffer bound to stream s, when one is tracked; programs admitted through the vs_2_0 interpreter
// (docs/VS_INTERPRETER.md) read whichever streams their position slice needs.
using StreamEvidence=std::array<const Evidence*,16>;
std::string Capture(IDirect3DDevice9*,Draw,const Evidence&,const Evidence&,const std::array<bool,256>&,bool material=false,const Evidence* flex=nullptr,const StreamEvidence* streams=nullptr);
}
