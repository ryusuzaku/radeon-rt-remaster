#pragma once
#include "snapshot.h"
#include <string>
namespace rrt::shader::position {
// CPU-only evidence serialization, no shader execution or resource readback.
std::string Capture(IDirect3DDevice9*,Draw,const Evidence&,const Evidence&,const std::array<bool,61>&,bool material=false);
}
