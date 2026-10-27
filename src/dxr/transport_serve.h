#pragma once
#include "../transport/transport.h"

// `rrt_dxr --transport-serve IN OUT`: the x64 renderer end of the proxy/renderer transport
// (docs/TRANSPORT_PROTOCOL.md). IN and OUT are inherited anonymous-pipe handle values; the scene
// arrives in an inherited file-mapping section, not on the pipe. Every message in both directions
// goes through the protocol session monitor, and a violation ends the session. Rendering reuses the
// headless path unchanged (`Renderer`, `RenderTo`, the BGRA pixel digest), so the output digest of a
// frame equals the `pixel_sha256_bgra` of the same scene and options run standalone.
namespace transport_serve {
namespace tp = rrt::transport;

struct Pipe {
    HANDLE in{}, out{}; DWORD idleMs{30000};
    void ReadExact(void* data, std::size_t size) const {
        auto* bytes = static_cast<std::uint8_t*>(data); std::size_t done = 0;
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(idleMs);
        while (done < size) {
            DWORD available = 0;
            if (!PeekNamedPipe(in, nullptr, 0, nullptr, &available, nullptr)) throw std::runtime_error("transport peer closed");
            if (!available) {
                if (std::chrono::steady_clock::now() > deadline) throw std::runtime_error("transport idle timeout");
                Sleep(1); continue;
            }
            DWORD read = 0; const DWORD want = DWORD(std::min<std::size_t>(available, size - done));
            if (!ReadFile(in, bytes + done, want, &read, nullptr) || !read) throw std::runtime_error("transport read failed");
            done += read;
        }
    }
    void Write(const std::vector<std::uint8_t>& message) const {
        DWORD written = 0;
        if (!WriteFile(out, message.data(), DWORD(message.size()), &written, nullptr) || written != message.size()) throw std::runtime_error("transport write failed");
    }
};

inline std::string Hex(const std::uint64_t (&words)[4]) {
    return rrt::scene::Hex(*reinterpret_cast<const rrt::scene::Hash*>(words));
}

// Returns the process exit code: 0 done or cleanly refused, 3 protocol violation, 5 peer closed or idle.
inline int Run(Options options) {
    Require(!options.interactive && !options.show && options.pixels.empty() && options.signals.empty() && options.rcProbe.empty() && options.rcSdkBin.empty() && options.rrRecord.empty() &&
        options.rrInputs.empty() && options.rcPaths.empty() && !options.rcStream && !options.historyTest && !options.lightingTest && !options.motionTest && options.temporalTest.empty() &&
        !options.windowTest && !options.presentationTest && !options.asyncTest && !options.asyncCloseTest && !options.pacingTest && options.materialPath.empty() && options.scene.empty(),
        "transport serve takes only render settings: no scene path, outputs, windows, RC, RR or test options");
    Require(options.transportIn && options.transportOut, "transport serve needs IN and OUT handles");
    Pipe pipe{options.transportIn, options.transportOut, options.transportIdleMs};
    tp::Session session; std::uint64_t sequence = 1; // renderer-to-proxy numbering
    std::unique_ptr<Device> gpu; std::unique_ptr<rrt::scene::Scene> scene; std::unique_ptr<Renderer> renderer;
    std::uint32_t sceneGeneration = 0, width = 0, height = 0; std::string sceneSha, lastOutput; UINT frames = 0;
    auto reply = [&](tp::Type type, const void* payload, std::uint64_t frameId = 0) {
        const auto message = tp::Build(type, sequence, frameId, payload);
        Require(session.Feed(tp::Direction::RendererToProxy, message.data(), message.size()) == tp::Error::Ok, "transport renderer sent a message its own monitor rejects");
        ++sequence; pipe.Write(message);
    };
    auto fail = [&](const char* result, const char* detail, int code) {
        std::printf("{\"result\":\"%s\",\"error\":\"%s\"}\n", result, detail); return code;
    };
    try {
        for (;;) {
            std::vector<std::uint8_t> message(sizeof(tp::Header));
            pipe.ReadExact(message.data(), sizeof(tp::Header));
            tp::Header header; std::memcpy(&header, message.data(), sizeof(header));
            if (header.payloadBytes > tp::MaxMessageBytes) return fail("transport-serve-error", "oversized", 3);
            message.resize(sizeof(tp::Header) + header.payloadBytes);
            if (header.payloadBytes) pipe.ReadExact(message.data() + sizeof(tp::Header), header.payloadBytes);
            if (const auto error = session.Feed(tp::Direction::ProxyToRenderer, message.data(), message.size()); error != tp::Error::Ok) return fail("transport-serve-error", tp::ErrorName(error), 3);
            tp::Parsed m; tp::Parse(message.data(), message.size(), m);
            switch (m.type) {
            case tp::Type::Hello: {
                gpu = std::make_unique<Device>(options);
                const std::uint64_t luid = (std::uint64_t(std::uint32_t(gpu->desc.AdapterLuid.HighPart)) << 32) | gpu->desc.AdapterLuid.LowPart;
                const std::uint32_t selected = tp::Negotiate(m.body.hello.minVersion, m.body.hello.maxVersion);
                tp::HelloAck ack{};
                ack.adapterLuid = luid;
                if (!selected) ack.status = tp::AckVersionMismatch;
                else if (m.body.hello.adapterLuid != luid) ack.status = tp::AckAdapterMismatch;
                else { ack.status = tp::AckOk; ack.selectedVersion = selected; ack.maxInFlight = tp::MaxInFlight; }
                reply(tp::Type::HelloAck, &ack);
                if (ack.status != tp::AckOk) { std::printf("{\"result\":\"transport-serve-refused\",\"status\":%u}\n", ack.status); return 0; }
                break;
            }
            case tp::Type::SceneAttach: {
                const auto& a = m.body.attach; tp::SceneAttachAck ack{}; ack.sceneGeneration = a.sceneGeneration; ack.status = tp::SceneDecodeFailed;
                std::vector<std::uint8_t> bytes;
                if (a.sectionBytes > rrt::scene::MaxBytes) ack.status = tp::SceneTooLarge;
                else if (void* view = MapViewOfFile(reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(a.sectionHandle)), FILE_MAP_READ, 0, 0, static_cast<SIZE_T>(a.sectionBytes))) {
                    bytes.assign(static_cast<const std::uint8_t*>(view), static_cast<const std::uint8_t*>(view) + a.sectionBytes); UnmapViewOfFile(view);
                    const auto digest = rrt::scene::Digest(bytes.data(), bytes.size());
                    if (std::memcmp(digest.data(), a.sha256, 32) != 0) ack.status = tp::SceneBadDigest;
                    else {
                        try {
                            rrt::scene::Hash source{}; auto decoded = std::make_unique<rrt::scene::Scene>(rrt::scene::Decode(std::move(bytes), &source)); Admit(*decoded);
                            if (renderer) { renderer->Drain(); renderer.reset(); }
                            scene = std::move(decoded); renderer = std::make_unique<Renderer>(*gpu, *scene, options);
                            ack.status = tp::SceneOk; ack.width = width = scene->width; ack.height = height = scene->height;
                            sceneGeneration = a.sceneGeneration; sceneSha = rrt::scene::Hex(source);
                        } catch (const std::exception&) { ack.status = tp::SceneDecodeFailed; ack.width = ack.height = 0; }
                    }
                }
                reply(tp::Type::SceneAttachAck, &ack);
                break;
            }
            case tp::Type::FrameSubmit: {
                const auto& f = m.body.submit; tp::FrameComplete c{};
                c.fenceValue = f.fenceValue; c.resourceSlot = f.resourceSlot; c.generations = f.generations; c.status = tp::FrameFailed;
                try {
                    // Each submitted frame is rendered from a clean history, so it equals the standalone render of the same settings.
                    renderer->Configure(options, true);
                    auto pixels = renderer->RenderTo(options.samples, true); renderer->Drain();
                    const auto digest = rrt::scene::Digest(pixels.data(), pixels.size() * 4);
                    std::memcpy(c.outputSha256, digest.data(), 32); c.status = tp::FrameReady; lastOutput = rrt::scene::Hex(digest); ++frames;
                } catch (const std::exception& error) { std::fprintf(stderr, "transport frame failed: %s\n", error.what()); std::memset(c.outputSha256, 0, sizeof(c.outputSha256)); }
                reply(tp::Type::FrameComplete, &c, m.header.frameId);
                break;
            }
            case tp::Type::Stop: {
                tp::StopAck ack{}; ack.completedFrames = session.Completed(); ack.discardedFrames = session.Discarded();
                reply(tp::Type::StopAck, &ack);
                std::printf("{\"result\":\"transport-serve-done\",\"protocol_version\":%u,\"frames\":%u,\"completed\":%u,\"discarded\":%u,\"scene_generation\":%u,\"width\":%u,\"height\":%u,"
                    "\"scene_sha256\":\"%s\",\"last_output_sha256\":\"%s\",\"adapter\":\"%s\",\"renderer\":\"dxr-inline-1.1\",\"requested_buffer_bytes\":%llu}\n",
                    unsigned(tp::SupportedVersion), frames, ack.completedFrames, ack.discardedFrames, sceneGeneration, width, height, sceneSha.c_str(), lastOutput.c_str(),
                    gpu ? JsonName(gpu->desc.Description).c_str() : "", gpu ? static_cast<unsigned long long>(gpu->allocated) : 0ull);
                return 0;
            }
            default: return fail("transport-serve-error", "unexpected_state", 3);
            }
        }
    } catch (const std::runtime_error& error) {
        const std::string text = error.what();
        if (text.rfind("transport ", 0) == 0) return fail("transport-serve-error", text.c_str(), 5);
        throw;
    }
}
}  // namespace transport_serve
