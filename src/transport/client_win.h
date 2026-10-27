#pragma once
// Proxy-side client of the proxy/renderer transport (docs/TRANSPORT_PROTOCOL.md). Header-only, Win32 and
// standard library only, so the x86 proxy (d3d9.dll) and the x86/x64 test host (rrt_transport_host) share it.
//
// RunSession() is synchronous and bounded by deadlines: it launches the x64 renderer in --transport-serve
// mode under a kill-on-close job with an allowlisted handle list, hands it the scene bytes in an inherited
// file-mapping section, drives Hello / SceneAttach / FrameSubmit / Stop over anonymous pipes, and returns a JSON
// report. Every message in both directions also goes through the protocol session monitor. It never throws,
// never writes to the game's state and never blocks past `timeoutMs` per exchange; callers run it off the render
// thread. DXGI is loaded lazily and only to resolve an adapter LUID, so nothing here links d3d or dxgi.
#include "transport.h"
#include "../scene/scene.h"

#include <windows.h>
#include <dxgi.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace rrt::transport::client {
namespace tp = rrt::transport;

struct Config {
    std::wstring renderer;                    // absolute path to rrt_dxr.exe
    std::vector<std::wstring> rendererArgs;   // render settings, as on the standalone command line
    std::uint32_t adapterOrdinal{0};          // used to resolve the LUID when adapterLuid is 0
    std::uint64_t adapterLuid{0};             // 0 = resolve through DXGI
    std::uint32_t frames{1}, sceneGeneration{11}, minVersion{1}, maxVersion{1}, timeoutMs{60000};
    // Test-only switches that exercise the renderer's refusal paths.
    bool corruptDigest{}, wrongLuid{}, injectGarbage{}, killAfterHello{};
    const std::atomic<bool>* cancel{};        // checked while waiting; set to abandon the session
};

struct Result {
    bool ok{};            // the session ended in an expected state (pass, or a clean refusal)
    std::string result;   // "transport-session-pass", "-refused", "-scene-refused", "-injected", "-frame-failed", "-error"
    std::string json;
};

namespace detail {
struct Handle {
    HANDLE value{};
    Handle() = default;
    Handle(const Handle&) = delete; Handle& operator=(const Handle&) = delete;
    ~Handle() { Close(); }
    void Close() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); value = nullptr; }
};
[[noreturn]] inline void Fail(const std::string& text) { throw std::runtime_error(text); }
inline void Need(bool ok, const char* text) { if (!ok) Fail(text); }

template <class... Args> std::string Format(const char* format, Args... args) {
    const int length = std::snprintf(nullptr, 0, format, args...); std::string out(static_cast<std::size_t>(length), ' ');
    std::snprintf(out.data(), out.size() + 1, format, args...); return out;
}
inline std::string Quote(const std::string& text) {
    std::string out = "\"";
    for (const unsigned char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 0x20) { char buffer[8]; std::snprintf(buffer, sizeof(buffer), "\\u%04x", c); out += buffer; }
        else out += static_cast<char>(c);
    }
    return out + "\"";
}
inline std::wstring Argument(const std::wstring& value) {  // CreateProcess command-line quoting
    std::wstring result = L"\""; std::size_t slashes = 0;
    for (const wchar_t c : value) {
        if (c == L'\\') { ++slashes; continue; }
        result.append(c == L'"' ? slashes * 2 + 1 : slashes, L'\\'); result += c; slashes = 0;
    }
    result.append(slashes * 2, L'\\'); result += L'"';
    return result;
}

inline std::uint64_t AdapterLuidFromDxgi(std::uint32_t ordinal) {
    HMODULE dxgi = LoadLibraryExW(L"dxgi.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32); Need(dxgi != nullptr, "dxgi.dll unavailable");
    using Create = HRESULT(WINAPI*)(REFIID, void**);
    const auto create = reinterpret_cast<Create>(GetProcAddress(dxgi, "CreateDXGIFactory1")); Need(create != nullptr, "CreateDXGIFactory1 unavailable");
    IDXGIFactory1* factory = nullptr; Need(SUCCEEDED(create(__uuidof(IDXGIFactory1), reinterpret_cast<void**>(&factory))), "DXGI factory");
    IDXGIAdapter1* adapter = nullptr; const bool found = SUCCEEDED(factory->EnumAdapters1(ordinal, &adapter));
    DXGI_ADAPTER_DESC1 desc{}; if (found) adapter->GetDesc1(&desc);
    if (adapter) adapter->Release(); factory->Release();
    Need(found, "adapter index");
    return (std::uint64_t(std::uint32_t(desc.AdapterLuid.HighPart)) << 32) | desc.AdapterLuid.LowPart;
}

struct Link {
    HANDLE read{}, write{}; DWORD timeoutMs{60000}; const std::atomic<bool>* cancel{};
    std::vector<std::uint8_t> Receive() const {
        std::vector<std::uint8_t> message(sizeof(tp::Header)); Read(message.data(), message.size());
        tp::Header header; std::memcpy(&header, message.data(), sizeof(header));
        if (header.payloadBytes > tp::MaxMessageBytes) Fail("renderer sent an oversized message");
        message.resize(sizeof(tp::Header) + header.payloadBytes);
        if (header.payloadBytes) Read(message.data() + sizeof(tp::Header), header.payloadBytes);
        return message;
    }
    void Send(const std::vector<std::uint8_t>& message) const {
        DWORD written = 0;
        if (!WriteFile(write, message.data(), DWORD(message.size()), &written, nullptr) || written != message.size()) Fail("write to the renderer failed");
    }
private:
    void Read(void* data, std::size_t size) const {
        auto* bytes = static_cast<std::uint8_t*>(data); std::size_t done = 0;
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
        while (done < size) {
            if (cancel && cancel->load()) Fail("cancelled");
            DWORD available = 0;
            if (!PeekNamedPipe(read, nullptr, 0, nullptr, &available, nullptr)) Fail("renderer closed the transport");
            if (!available) { if (std::chrono::steady_clock::now() > deadline) Fail("renderer reply timed out"); Sleep(1); continue; }
            DWORD got = 0; const DWORD want = DWORD(std::min<std::size_t>(available, size - done));
            if (!ReadFile(read, bytes + done, want, &got, nullptr) || !got) Fail("transport read failed");
            done += got;
        }
    }
};

inline std::string DrainText(HANDLE pipe) {
    std::string text; char buffer[4096]; DWORD got = 0;
    for (;;) {
        DWORD available = 0;
        if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr) || !available) break;
        if (!ReadFile(pipe, buffer, sizeof(buffer), &got, nullptr) || !got) break;
        text.append(buffer, got); if (text.size() > 65536) break;
    }
    return text;
}

struct Session {
    const Config& config; const std::vector<std::uint8_t>& scene;
    Handle toRendererRead, toRendererWrite, fromRendererRead, fromRendererWrite, outRead, outWrite, errRead, errWrite, input, section, job, process;
    tp::Session monitor; std::uint64_t sequence = 1, luid = 0; DWORD processId = 0;
    std::string result = "transport-session-pass", error, frames, rendererOut, rendererErr; rrt::scene::Hash sceneDigest{};
    std::uint32_t ackStatus = 0, sceneStatus = 99, width = 0, height = 0; tp::StopAck stopAck{}; bool stopped = false, reaped = false; DWORD exitCode = 0;

    Session(const Config& c, const std::vector<std::uint8_t>& bytes) : config(c), scene(bytes) {}

    void Send(const Link& link, tp::Type type, const void* payload, std::uint64_t frameId = 0) {
        const auto message = tp::Build(type, sequence, frameId, payload);
        Need(monitor.Feed(tp::Direction::ProxyToRenderer, message.data(), message.size()) == tp::Error::Ok, "client sent a message its own monitor rejects");
        ++sequence; link.Send(message);
    }
    void Receive(const Link& link, tp::Parsed& parsed) {
        const auto message = link.Receive();
        const auto problem = monitor.Feed(tp::Direction::RendererToProxy, message.data(), message.size());
        if (problem != tp::Error::Ok) Fail(std::string("renderer message rejected: ") + tp::ErrorName(problem));
        tp::Parse(message.data(), message.size(), parsed);
    }

    void Launch() {
        Need(!scene.empty() && scene.size() <= tp::MaxSceneBytes, "scene size");
        sceneDigest = rrt::scene::Digest(scene.data(), scene.size());
        luid = config.adapterLuid ? config.adapterLuid : AdapterLuidFromDxgi(config.adapterOrdinal);
        SECURITY_ATTRIBUTES inheritable{sizeof(inheritable), nullptr, TRUE};
        Need(CreatePipe(&toRendererRead.value, &toRendererWrite.value, &inheritable, 0) && CreatePipe(&fromRendererRead.value, &fromRendererWrite.value, &inheritable, 0), "message pipes");
        Need(CreatePipe(&outRead.value, &outWrite.value, &inheritable, 65536) && CreatePipe(&errRead.value, &errWrite.value, &inheritable, 65536), "output pipes");
        for (HANDLE parentEnd : {toRendererWrite.value, fromRendererRead.value, outRead.value, errRead.value}) Need(SetHandleInformation(parentEnd, HANDLE_FLAG_INHERIT, 0), "pipe inheritance");
        input.value = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING, 0, nullptr); Need(input.value != INVALID_HANDLE_VALUE, "NUL input");
        const std::uint64_t total = scene.size();
        section.value = CreateFileMappingW(INVALID_HANDLE_VALUE, &inheritable, PAGE_READWRITE, DWORD(total >> 32), DWORD(total & 0xffffffffu), nullptr); Need(section.value != nullptr, "scene section");
        { void* view = MapViewOfFile(section.value, FILE_MAP_WRITE, 0, 0, scene.size()); Need(view != nullptr, "scene section map"); std::memcpy(view, scene.data(), scene.size()); UnmapViewOfFile(view); }
        job.value = CreateJobObjectW(nullptr, nullptr); Need(job.value != nullptr, "job");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{}; limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        Need(SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits)), "job limits");

        std::wstring command = Argument(config.renderer) + L" --transport-serve " + std::to_wstring(reinterpret_cast<std::uintptr_t>(toRendererRead.value)) + L" " +
            std::to_wstring(reinterpret_cast<std::uintptr_t>(fromRendererWrite.value)) + L" --transport-idle-ms " + std::to_wstring(config.timeoutMs);
        for (const auto& a : config.rendererArgs) command += L" " + Argument(a);
        std::vector<HANDLE> inherited{toRendererRead.value, fromRendererWrite.value, section.value, outWrite.value, errWrite.value, input.value};
        SIZE_T size = 0; InitializeProcThreadAttributeList(nullptr, 1, 0, &size); std::vector<unsigned char> storage(size);
        auto* list = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
        Need(InitializeProcThreadAttributeList(list, 1, 0, &size), "attribute list");
        if (!UpdateProcThreadAttribute(list, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited.data(), inherited.size() * sizeof(HANDLE), nullptr, nullptr)) { DeleteProcThreadAttributeList(list); Fail("handle allowlist"); }
        STARTUPINFOEXW startup{}; startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = list; startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = input.value; startup.StartupInfo.hStdOutput = outWrite.value; startup.StartupInfo.hStdError = errWrite.value;
        PROCESS_INFORMATION info{};
        const BOOL created = CreateProcessW(config.renderer.c_str(), command.data(), nullptr, nullptr, TRUE, CREATE_SUSPENDED | CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT, nullptr, nullptr, &startup.StartupInfo, &info);
        DeleteProcThreadAttributeList(list); Need(created, "renderer launch failed");
        process.value = info.hProcess; processId = info.dwProcessId;
        if (!AssignProcessToJobObject(job.value, process.value)) { TerminateProcess(process.value, 1); CloseHandle(info.hThread); Fail("job assignment failed"); }
        const DWORD resumed = ResumeThread(info.hThread); CloseHandle(info.hThread); Need(resumed != DWORD(-1), "renderer resume");
        toRendererRead.Close(); fromRendererWrite.Close(); outWrite.Close(); errWrite.Close(); input.Close();  // the renderer owns its ends now
    }

    void Execute() {
        Launch();
        const Link link{fromRendererRead.value, toRendererWrite.value, config.timeoutMs, config.cancel};
        tp::Hello hello{}; hello.minVersion = config.minVersion; hello.maxVersion = config.maxVersion; hello.adapterLuid = config.wrongLuid ? luid + 1 : luid;
        hello.processId = GetCurrentProcessId(); hello.captureLevel = 20;
        Send(link, tp::Type::Hello, &hello);
        tp::Parsed m; Receive(link, m); Need(m.type == tp::Type::HelloAck, "expected HelloAck"); ackStatus = m.body.ack.status;
        if (ackStatus != tp::AckOk) { result = "transport-session-refused"; return; }
        if (config.killAfterHello) TerminateProcess(process.value, 9);  // test-only: the renderer vanishes mid-session
        if (config.injectGarbage) {
            std::vector<std::uint8_t> garbage(sizeof(tp::Header), 0); std::memset(garbage.data(), 0xAA, 4);  // wrong magic, zero payload size
            link.Send(garbage); result = "transport-session-injected"; return;
        }
        tp::SceneAttach attach{}; attach.sectionHandle = reinterpret_cast<std::uintptr_t>(section.value); attach.sectionBytes = scene.size(); attach.sceneGeneration = config.sceneGeneration;
        std::memcpy(attach.sha256, sceneDigest.data(), 32); if (config.corruptDigest) attach.sha256[0] ^= 1;
        Send(link, tp::Type::SceneAttach, &attach); Receive(link, m); Need(m.type == tp::Type::SceneAttachAck, "expected SceneAttachAck");
        sceneStatus = m.body.attachAck.status; width = m.body.attachAck.width; height = m.body.attachAck.height;
        if (sceneStatus != tp::SceneOk) result = "transport-session-scene-refused";
        else for (std::uint32_t n = 1; n <= config.frames; ++n) {
            tp::FrameSubmit submit{}; submit.fenceValue = 100 + n; submit.resourceSlot = n % tp::MaxSlots; submit.width = width; submit.height = height;
            submit.generations = {config.sceneGeneration, 1, 1, 1, 1};
            const auto started = std::chrono::steady_clock::now(); Send(link, tp::Type::FrameSubmit, &submit, n); Receive(link, m);
            Need(m.type == tp::Type::FrameComplete && m.header.frameId == n, "expected FrameComplete");
            const auto wallMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
            rrt::scene::Hash digest{}; std::memcpy(digest.data(), m.body.complete.outputSha256, 32);
            frames += Format("%s{\"frame_id\":%u,\"status\":%u,\"wall_ms\":%.3f,\"output_sha256\":\"%s\"}", frames.empty() ? "" : ",", n, m.body.complete.status, wallMs, rrt::scene::Hex(digest).c_str());
            if (m.body.complete.status != tp::FrameReady) result = "transport-session-frame-failed";
        }
        Send(link, tp::Type::Stop, nullptr); Receive(link, m); Need(m.type == tp::Type::StopAck, "expected StopAck"); stopAck = m.body.stopAck; stopped = true;
    }

    void Reap() {
        if (!process.value) return;
        const DWORD wait = WaitForSingleObject(process.value, error.empty() ? config.timeoutMs : 3000);
        reaped = wait == WAIT_OBJECT_0 && GetExitCodeProcess(process.value, &exitCode);
        if (!reaped) { TerminateJobObject(job.value, 1); reaped = WaitForSingleObject(process.value, 5000) == WAIT_OBJECT_0 && GetExitCodeProcess(process.value, &exitCode); if (error.empty()) error = "renderer did not exit"; }
        rendererOut = outRead.value ? DrainText(outRead.value) : std::string(); rendererErr = errRead.value ? DrainText(errRead.value) : std::string();
    }

    Result Report() {
        Reap();
        if (!error.empty()) result = "transport-session-error";
        const bool ok = result == "transport-session-pass" || result == "transport-session-refused" || result == "transport-session-scene-refused" || result == "transport-session-injected";
        std::string json = Format("{\"result\":\"%s\",\"error\":%s,\"protocol_version\":%u,\"host_pointer_bytes\":%zu,\"adapter_luid\":%llu,\"ack_status\":%u,\"scene_status\":%u,\"scene_width\":%u,\"scene_height\":%u,"
            "\"scene_file_sha256\":\"%s\",\"frames\":[%s],\"stopped\":%s,\"stop_completed\":%u,\"stop_discarded\":%u,\"session_completed\":%u,\"session_discarded\":%u,"
            "\"renderer_pid\":%lu,\"renderer_exit_code\":%lu,\"child_reaped\":%s,\"renderer_stdout\":%s,\"renderer_stderr\":%s}",
            result.c_str(), Quote(error).c_str(), unsigned(tp::SupportedVersion), sizeof(void*), static_cast<unsigned long long>(luid), ackStatus, sceneStatus, width, height,
            rrt::scene::Hex(sceneDigest).c_str(), frames.c_str(), stopped ? "true" : "false", stopAck.completedFrames, stopAck.discardedFrames, monitor.Completed(), monitor.Discarded(),
            static_cast<unsigned long>(processId), static_cast<unsigned long>(exitCode), reaped ? "true" : "false", Quote(rendererOut).c_str(), Quote(rendererErr).c_str());
        return Result{ok && error.empty(), result, std::move(json)};
    }
};
}  // namespace detail

inline Result RunSession(const Config& config, const std::vector<std::uint8_t>& sceneBytes) noexcept {
    try {
        detail::Session session(config, sceneBytes);
        try { session.Execute(); } catch (const std::exception& problem) { session.error = problem.what(); }
        return session.Report();
    } catch (const std::exception& problem) {
        return Result{false, "transport-session-error", detail::Format("{\"result\":\"transport-session-error\",\"error\":%s}", detail::Quote(problem.what()).c_str())};
    } catch (...) {
        return Result{false, "transport-session-error", "{\"result\":\"transport-session-error\",\"error\":\"unknown\"}"};
    }
}
}  // namespace rrt::transport::client
