#pragma once
#include "snapshot.h"
#include <string>
namespace rrt::shader::position {
// CPU-only evidence serialization, no shader execution or resource readback.
// `flex` is the shadow of the buffer bound to stream 2, when one is tracked; only the second admitted program reads it.
std::string Capture(IDirect3DDevice9*,Draw,const Evidence&,const Evidence&,const std::array<bool,61>&,bool material=false,const Evidence* flex=nullptr);
}
