#pragma once
// Vertex programs captured through the vs_2_0 interpreter (docs/VS_INTERPRETER.md). Generated from, and checked against,
// docs/schemas/interpreted-vertex-programs.json by tests/verify_interpreted_program_list.py. Each passed the GPU point oracle.
#include <array>
#include <string_view>
namespace rrt::shader::vsi {
constexpr std::array<std::string_view,20> InterpretedPrograms={
    "e5ece83d9727f677ed30b22fc9e74b08cb036ce8cdabd6e99a3735f9d893347f", // 3212 bytes, skinned (teeth lighting)
    "26169c607a20889d9da923745d03a7919c6a2e3f01fa97f7d77e2a1e265bb168", // 1172 bytes, world, cModelViewProj
    "bced3cb48e003e67abd4b74a2f4b6c6c8e301a36cc9a6a2f8811341d8b1dbfa6", // 3080 bytes, static prop, cViewProj with flex
    "2aa6a2c31c794457c53f9baaca1c457e2899eeb8d9a547382421720772f336ad", // 1116 bytes, world, cModelViewProj
    "2e0c8bf54e310e7f200bd237c54aed2e9cba6eaea956dc77d590449571835b71", // 2624 bytes, skinned
    "8e3211a8e3f03b4aa1f101aad4198d4e92a615096de4531ae7a6af84e4434f90", // 1368 bytes, static prop, cViewProj with flex
    "7839f17642e1d96f35c5f8d6c7b7e54922765583e67287318286a352b05a80eb", // 2644 bytes, skinned
    "ee4626681027961fd488a6574b1b8b3b5a4e0347bc935ccf9c332a29811170b7", // 2368 bytes, skinned (eyes)
    "66bfc25ba9fb8557983300799f702fd4f875c024e0eedb2f0755c801110ea138", // 1296 bytes, world, cModelViewProj
    "4dfd4c0f6449db6f82e63d8638fa067b0206fac086e5608a2a675562025794c6", // 656 bytes, world, cModelViewProj
    "2288ea1d2aacd3382eedc7ac2b1fe62b0ad9961b559b7a73859152a4cec2060b", // 228 bytes, cModelViewProj only, no model position
    "1773be9a55aec697ab584685865204f68dea6e52b0e08d28e725909f4a95a7d6", // 748 bytes, static, cViewProj without flex
    "88c6f75957d94001604f56c8707596b575cfdeb5ab5deaabbb1b66296e6e49ba", // 232 bytes, screen space
    "dde51af897b281f06300943511e1bb2054575af89c9c517bc4559d00a2d75d2f", // 720 bytes, world, cModelViewProj
    "3850187ece74a4f51aff07890730056eea49c49f63a4fca68fa0d2f5d2ca6bdd", // 1288 bytes, skinned, two bones
    "d45261e1aed4faa00bbd3b47a8706899f108675e97ae3425471e7c6cf93ec407", // 512 bytes, static, cViewProj without flex
    "2bb9d0ef192eb75adfc45fb52f6808c8765cced833e91e3a882e50b96e7fa9d7", // 1024 bytes, static prop, cViewProj with flex
    "8ed20434baeda1a15d7cfb972ebc8bb18c04baf009bc9564114c597539bb892c", // 1112 bytes, skinned
    "3017f18ebfe830c69aba2f93fd95d73305f3a21bfa1819c0c129567b7a6d4bcc", // 256 bytes, screen space
    "433848bcb2df4776b92696d462c4185b933d29fddc357441234fd58a648eabb7", // 300 bytes, screen space
};
}
