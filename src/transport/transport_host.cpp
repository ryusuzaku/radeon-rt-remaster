// Test host that plays the proxy's part of the transport (docs/TRANSPORT_PROTOCOL.md, Phase 6 stage 2).
// Built for x86 and x64. A thin command-line wrapper around the client the proxy itself uses
// (client_win.h): it launches the x64 renderer in `--transport-serve` mode, hands it a scene file, drives
// one or more sessions and prints a JSON report that adds the host's handle counts.
#include "client_win.h"

#include <filesystem>
#include <fstream>

namespace cl = rrt::transport::client;
using cl::detail::Fail;
using cl::detail::Need;

namespace {
struct Options {
    std::filesystem::path scene; cl::Config config; std::uint32_t repeat{1};
};

DWORD HandleCount() { DWORD n = 0; GetProcessHandleCount(GetCurrentProcess(), &n); return n; }

Options Parse(int argc, wchar_t** argv) {
    Options o; bool rest = false; std::filesystem::path renderer;
    o.config.timeoutMs = 60000;
    for (int i = 1; i < argc; ++i) {
        const std::wstring a = argv[i];
        auto number = [&](std::uint32_t& out) { Need(i + 1 < argc, "missing value"); wchar_t* end{}; const auto v = wcstoul(argv[++i], &end, 10); Need(*end == 0, "bad number"); out = std::uint32_t(v); };
        if (rest) o.config.rendererArgs.push_back(a);
        else if (a == L"--") rest = true;
        else if (a == L"--renderer" && i + 1 < argc) renderer = argv[++i];
        else if (a == L"--scene" && i + 1 < argc) o.scene = argv[++i];
        else if (a == L"--adapter") number(o.config.adapterOrdinal);
        else if (a == L"--frames") number(o.config.frames);
        else if (a == L"--repeat") number(o.repeat);
        else if (a == L"--scene-generation") number(o.config.sceneGeneration);
        else if (a == L"--min-version") number(o.config.minVersion);
        else if (a == L"--max-version") number(o.config.maxVersion);
        else if (a == L"--timeout-ms") number(o.config.timeoutMs);
        else if (a == L"--corrupt-digest") o.config.corruptDigest = true;
        else if (a == L"--wrong-luid") o.config.wrongLuid = true;
        else if (a == L"--inject-garbage") o.config.injectGarbage = true;
        else if (a == L"--kill-after-hello") o.config.killAfterHello = true;
        else Fail("unknown argument");
    }
    Need(renderer.is_absolute() && std::filesystem::is_regular_file(renderer), "--renderer must be an absolute path to rrt_dxr");
    o.config.renderer = renderer.wstring();
    Need(!o.scene.empty() && std::filesystem::is_regular_file(o.scene), "--scene must name an existing scene file");
    Need(o.repeat >= 1 && o.repeat <= 32, "repeat must be 1..32");
    Need(o.config.frames >= 1 && o.config.frames <= 64 && o.config.timeoutMs >= 1000, "frames must be 1..64 and timeout at least 1000 ms");
    return o;
}
}  // namespace

int wmain(int argc, wchar_t** argv) {
    try {
        const Options o = Parse(argc, argv);
        std::vector<std::uint8_t> bytes;
        { std::ifstream f(o.scene, std::ios::binary | std::ios::ate); Need(f.good(), "cannot open scene"); const auto n = f.tellg(); Need(n > 0, "scene size");
          bytes.resize(static_cast<std::size_t>(n)); f.seekg(0); f.read(reinterpret_cast<char*>(bytes.data()), bytes.size()); Need(f.good(), "scene read"); }
        cl::detail::AdapterLuidFromDxgi(o.config.adapterOrdinal);  // load DXGI first, so the handle baseline excludes its runtime handles
        const DWORD before = HandleCount(); std::string each; cl::Result last;
        for (std::uint32_t cycle = 0; cycle < o.repeat; ++cycle) { last = cl::RunSession(o.config, bytes); each += (each.empty() ? "" : ",") + std::to_string(HandleCount()); }
        last.json.pop_back();  // reopen the last session's report to append the host's own fields
        std::printf("%s,\"repeat\":%u,\"host_handles_each\":[%s],\"host_handles_baseline\":%lu}\n", last.json.c_str(), o.repeat, each.c_str(), static_cast<unsigned long>(before));
        return last.ok ? 0 : 1;
    } catch (const std::exception& error) {
        std::printf("{\"result\":\"transport-session-error\",\"error\":%s}\n", cl::detail::Quote(error.what()).c_str());
        return 2;
    }
}
