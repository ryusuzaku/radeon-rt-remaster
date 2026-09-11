#pragma once
#include "snapshot.h"
#include <memory>
#include <string>
namespace rrt::shader::inventory {
struct Pending { std::string payload; std::uint64_t ordinal{}; };
std::unique_ptr<Pending> BeforeDraw(std::uint64_t,IDirect3DDevice9*,D3DPRIMITIVETYPE) noexcept;
void Commit(std::unique_ptr<Pending>,HRESULT) noexcept;
}
