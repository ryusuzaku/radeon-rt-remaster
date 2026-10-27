// Test host that plays the proxy's part of the transport (docs/TRANSPORT_PROTOCOL.md, Phase 6 stage 2).
// Built for x86 and x64. It launches the x64 renderer in `--transport-serve` mode under a kill-on-close
// job with an allowlisted handle list, hands it the scene bytes in an inherited file-mapping section,
// drives Hello / SceneAttach / FrameSubmit / Stop over anonymous pipes, and prints one JSON report.
// Every message in both directions also goes through the protocol session monitor.
#include "transport.h"
#include "../scene/scene.h"

#include <windows.h>
#include <dxgi.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace tp = rrt::transport;

namespace {
struct Handle {
    HANDLE value{};
    Handle() = default; explicit Handle(HANDLE h) : value(h) {}
    Handle(const Handle&) = delete; Handle& operator=(const Handle&) = delete;
    ~Handle() { Close(); }
    void Close() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); value = nullptr; }
};
[[noreturn]] void Fail(const std::string& text) { throw std::runtime_error(text); }
void Need(bool ok, const char* text) { if (!ok) Fail(text); }

std::string Quote(const std::string& text) {
    std::string out = "\"";
    for (const unsigned char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 0x20) { char buffer[8]; std::snprintf(buffer, sizeof(buffer), "\\u%04x", c); out += buffer; }
        else out += static_cast<char>(c);
    }
    return out + "\"";
}
std::wstring Argument(const std::wstring& value) {  // CreateProcess command-line quoting
    std::wstring result = L"\""; std::size_t slashes = 0;
    for (const wchar_t c : value) {
        if (c == L'\\') { ++slashes; continue; }
        result.append(c == L'"' ? slashes * 2 + 1 : slashes, L'\\'); result += c; slashes = 0;
    }
    result.append(slashes * 2, L'\\'); result += L'"';
    return result;
}

struct Options {
    std::filesystem::path renderer, scene; std::uint32_t adapter{}, frames{1}, sceneGeneration{11}, minVersion{1}, maxVersion{1}, timeoutMs{60000};
    std::uint32_t repeat{1}; bool corruptDigest{}, wrongLuid{}, injectGarbage{}; std::vector<std::wstring> rendererArgs;
};

struct Link {
    HANDLE read{}, write{}; DWORD timeoutMs{60000};
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
            DWORD available = 0;
            if (!PeekNamedPipe(read, nullptr, 0, nullptr, &available, nullptr)) Fail("renderer closed the transport");
            if (!available) { if (std::chrono::steady_clock::now() > deadline) Fail("renderer reply timed out"); Sleep(1); continue; }
            DWORD got = 0; const DWORD want = DWORD(std::min<std::size_t>(available, size - done));
            if (!ReadFile(read, bytes + done, want, &got, nullptr) || !got) Fail("transport read failed");
            done += got;
        }
    }
};

std::string DrainText(HANDLE pipe) {
    std::string text; char buffer[4096]; DWORD got = 0;
    for (;;) {
        DWORD available = 0;
        if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr) || !available) break;
        if (!ReadFile(pipe, buffer, sizeof(buffer), &got, nullptr) || !got) break;
        text.append(buffer, got); if (text.size() > 65536) break;
    }
    return text;
}

std::uint64_t AdapterLuid(std::uint32_t index) {
    IDXGIFactory1* factory = nullptr; Need(SUCCEEDED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), reinterpret_cast<void**>(&factory))), "DXGI factory");
    IDXGIAdapter1* adapter = nullptr; const bool found = SUCCEEDED(factory->EnumAdapters1(index, &adapter));
    DXGI_ADAPTER_DESC1 desc{}; if (found) adapter->GetDesc1(&desc);
    if (adapter) adapter->Release(); factory->Release();
    Need(found, "adapter index");
    return (std::uint64_t(std::uint32_t(desc.AdapterLuid.HighPart)) << 32) | desc.AdapterLuid.LowPart;
}

template <class... Args> std::string Format(const char* format, Args... args) {
    const int length = std::snprintf(nullptr, 0, format, args...); std::string out(static_cast<std::size_t>(length), ' ');
    std::snprintf(out.data(), out.size() + 1, format, args...); return out;
}

DWORD HandleCount() { DWORD n = 0; GetProcessHandleCount(GetCurrentProcess(), &n); return n; }

Options Parse(int argc, wchar_t** argv) {
    Options o; bool rest = false;
    for (int i = 1; i < argc; ++i) {
        const std::wstring a = argv[i];
        auto number = [&](std::uint32_t& out) { Need(i + 1 < argc, "missing value"); wchar_t* end{}; const auto v = wcstoul(argv[++i], &end, 10); Need(*end == 0, "bad number"); out = std::uint32_t(v); };
        if (rest) o.rendererArgs.push_back(a);
        else if (a == L"--") rest = true;
        else if (a == L"--renderer" && i + 1 < argc) o.renderer = argv[++i];
        else if (a == L"--scene" && i + 1 < argc) o.scene = argv[++i];
        else if (a == L"--adapter") number(o.adapter);
        else if (a == L"--frames") number(o.frames);
        else if (a == L"--repeat") number(o.repeat);
        else if (a == L"--scene-generation") number(o.sceneGeneration);
        else if (a == L"--min-version") number(o.minVersion);
        else if (a == L"--max-version") number(o.maxVersion);
        else if (a == L"--timeout-ms") number(o.timeoutMs);
        else if (a == L"--corrupt-digest") o.corruptDigest = true;
        else if (a == L"--wrong-luid") o.wrongLuid = true;
        else if (a == L"--inject-garbage") o.injectGarbage = true;
        else Fail("unknown argument");
    }
    Need(o.renderer.is_absolute() && std::filesystem::is_regular_file(o.renderer), "--renderer must be an absolute path to rrt_dxr");
    Need(!o.scene.empty() && std::filesystem::is_regular_file(o.scene), "--scene must name an existing scene file");
    Need(o.repeat >= 1 && o.repeat <= 32, "repeat must be 1..32");
    Need(o.frames >= 1 && o.frames <= 64 && o.timeoutMs >= 1000, "frames must be 1..64 and timeout at least 1000 ms");
    return o;
}
}  // namespace

int wmain(int argc, wchar_t** argv) {
    try {
        const Options o = Parse(argc, argv);
        std::vector<std::uint8_t> sceneBytes;
        { std::ifstream f(o.scene, std::ios::binary | std::ios::ate); Need(f.good(), "cannot open scene"); const auto n = f.tellg(); Need(n > 0 && std::uint64_t(n) <= tp::MaxSceneBytes, "scene size");
          sceneBytes.resize(static_cast<std::size_t>(n)); f.seekg(0); f.read(reinterpret_cast<char*>(sceneBytes.data()), sceneBytes.size()); Need(f.good(), "scene read"); }
        const auto sceneDigest = rrt::scene::Digest(sceneBytes.data(), sceneBytes.size());
        const std::uint64_t luid = AdapterLuid(o.adapter);  // loads DXGI first, so the handle baseline excludes its runtime handles
        const DWORD handlesBefore = HandleCount();
        std::vector<DWORD> handlesAfterEach; std::string lastJson; bool lastOk = true;
        for (std::uint32_t cycle = 0; cycle < o.repeat; ++cycle) {
        {
            SECURITY_ATTRIBUTES inheritable{sizeof(inheritable), nullptr, TRUE};
            Handle toRendererRead, toRendererWrite, fromRendererRead, fromRendererWrite, outRead, outWrite, errRead, errWrite, input, section, job, process, thread;
            Need(CreatePipe(&toRendererRead.value, &toRendererWrite.value, &inheritable, 0) && CreatePipe(&fromRendererRead.value, &fromRendererWrite.value, &inheritable, 0), "message pipes");
            Need(CreatePipe(&outRead.value, &outWrite.value, &inheritable, 65536) && CreatePipe(&errRead.value, &errWrite.value, &inheritable, 65536), "output pipes");
            for (HANDLE parentEnd : {toRendererWrite.value, fromRendererRead.value, outRead.value, errRead.value}) Need(SetHandleInformation(parentEnd, HANDLE_FLAG_INHERIT, 0), "pipe inheritance");
            input.value = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING, 0, nullptr); Need(input.value != INVALID_HANDLE_VALUE, "NUL input");
            section.value = CreateFileMappingW(INVALID_HANDLE_VALUE, &inheritable, PAGE_READWRITE, DWORD(std::uint64_t(sceneBytes.size()) >> 32), DWORD(std::uint64_t(sceneBytes.size()) & 0xffffffffu), nullptr); Need(section.value != nullptr, "scene section");
            { void* view = MapViewOfFile(section.value, FILE_MAP_WRITE, 0, 0, sceneBytes.size()); Need(view != nullptr, "scene section map"); std::memcpy(view, sceneBytes.data(), sceneBytes.size()); UnmapViewOfFile(view); }

            job.value = CreateJobObjectW(nullptr, nullptr); Need(job.value != nullptr, "job");
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{}; limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            Need(SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits)), "job limits");

            std::wstring command = Argument(o.renderer.wstring()) + L" --transport-serve " + std::to_wstring(reinterpret_cast<std::uintptr_t>(toRendererRead.value)) + L" " +
                std::to_wstring(reinterpret_cast<std::uintptr_t>(fromRendererWrite.value)) + L" --transport-idle-ms " + std::to_wstring(o.timeoutMs);
            for (const auto& a : o.rendererArgs) command += L" " + Argument(a);
            std::vector<HANDLE> inherited{toRendererRead.value, fromRendererWrite.value, section.value, outWrite.value, errWrite.value, input.value};
            SIZE_T size = 0; InitializeProcThreadAttributeList(nullptr, 1, 0, &size); std::vector<unsigned char> storage(size);
            auto* list = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
            Need(InitializeProcThreadAttributeList(list, 1, 0, &size), "attribute list");
            Need(UpdateProcThreadAttribute(list, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited.data(), inherited.size() * sizeof(HANDLE), nullptr, nullptr), "handle allowlist");
            STARTUPINFOEXW startup{}; startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = list; startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
            startup.StartupInfo.hStdInput = input.value; startup.StartupInfo.hStdOutput = outWrite.value; startup.StartupInfo.hStdError = errWrite.value;
            PROCESS_INFORMATION info{};
            const BOOL created = CreateProcessW(o.renderer.c_str(), command.data(), nullptr, nullptr, TRUE, CREATE_SUSPENDED | CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT, nullptr, nullptr, &startup.StartupInfo, &info);
            DeleteProcThreadAttributeList(list); Need(created, "renderer launch failed");
            process.value = info.hProcess; thread.value = info.hThread;
            if (!AssignProcessToJobObject(job.value, process.value)) { TerminateProcess(process.value, 1); Fail("job assignment failed"); }
            Need(ResumeThread(thread.value) != DWORD(-1), "renderer resume"); thread.Close();
            toRendererRead.Close(); fromRendererWrite.Close(); outWrite.Close(); errWrite.Close(); input.Close();  // the renderer owns its ends now

            Link link{fromRendererRead.value, toRendererWrite.value, o.timeoutMs}; tp::Session session; std::uint64_t sequence = 1;
            auto send = [&](tp::Type type, const void* payload, std::uint64_t frameId = 0, std::uint32_t flags = 0) {
                const auto message = tp::Build(type, sequence, frameId, payload, flags);
                Need(session.Feed(tp::Direction::ProxyToRenderer, message.data(), message.size()) == tp::Error::Ok, "host sent a message its own monitor rejects");
                ++sequence; link.Send(message);
            };
            auto receive = [&](tp::Parsed& parsed) {
                const auto message = link.Receive();
                const auto error = session.Feed(tp::Direction::RendererToProxy, message.data(), message.size());
                if (error != tp::Error::Ok) Fail(std::string("renderer message rejected: ") + tp::ErrorName(error));
                tp::Parse(message.data(), message.size(), parsed);
            };

            std::string result = "transport-host-pass"; std::uint32_t ackStatus = 0, sceneStatus = 99, width = 0, height = 0; std::string frames; tp::StopAck stopAck{}; bool stopped = false;
            tp::Hello hello{}; hello.minVersion = o.minVersion; hello.maxVersion = o.maxVersion; hello.adapterLuid = o.wrongLuid ? luid + 1 : luid; hello.processId = GetCurrentProcessId(); hello.captureLevel = 20;
            send(tp::Type::Hello, &hello);
            tp::Parsed m; receive(m); Need(m.type == tp::Type::HelloAck, "expected HelloAck"); ackStatus = m.body.ack.status;
            if (ackStatus != tp::AckOk) result = "transport-host-refused";
            else if (o.injectGarbage) {
                // A header the renderer must reject; it ends the session and the pipe closes.
                std::vector<std::uint8_t> garbage(sizeof(tp::Header), 0); std::memset(garbage.data(), 0xAA, 4);  // wrong magic, zero payload size
            link.Send(garbage); result = "transport-host-injected";
            } else {
                tp::SceneAttach attach{}; attach.sectionHandle = reinterpret_cast<std::uintptr_t>(section.value); attach.sectionBytes = sceneBytes.size(); attach.sceneGeneration = o.sceneGeneration;
                std::memcpy(attach.sha256, sceneDigest.data(), 32); if (o.corruptDigest) attach.sha256[0] ^= 1;
                send(tp::Type::SceneAttach, &attach); receive(m); Need(m.type == tp::Type::SceneAttachAck, "expected SceneAttachAck");
                sceneStatus = m.body.attachAck.status; width = m.body.attachAck.width; height = m.body.attachAck.height;
                if (sceneStatus != tp::SceneOk) result = "transport-host-scene-refused";
                else for (std::uint32_t n = 1; n <= o.frames; ++n) {
                    tp::FrameSubmit submit{}; submit.fenceValue = 100 + n; submit.resourceSlot = n % tp::MaxSlots; submit.width = width; submit.height = height;
                    submit.generations = {o.sceneGeneration, 1, 1, 1, 1};
                    const auto started = std::chrono::steady_clock::now(); send(tp::Type::FrameSubmit, &submit, n); receive(m);
                    Need(m.type == tp::Type::FrameComplete && m.header.frameId == n, "expected FrameComplete");
                    const auto wallMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
                    rrt::scene::Hash digest{}; std::memcpy(digest.data(), m.body.complete.outputSha256, 32);
                    char row[256]; std::snprintf(row, sizeof(row), "%s{\"frame_id\":%u,\"status\":%u,\"wall_ms\":%.3f,\"output_sha256\":\"%s\"}", frames.empty() ? "" : ",", n, m.body.complete.status, wallMs, rrt::scene::Hex(digest).c_str());
                    frames += row; if (m.body.complete.status != tp::FrameReady) result = "transport-host-frame-failed";
                }
                send(tp::Type::Stop, nullptr); receive(m); Need(m.type == tp::Type::StopAck, "expected StopAck"); stopAck = m.body.stopAck; stopped = true;
            }
            const DWORD wait = WaitForSingleObject(process.value, o.timeoutMs); DWORD exitCode = 0;
            const bool reaped = wait == WAIT_OBJECT_0 && GetExitCodeProcess(process.value, &exitCode);
            if (!reaped) { TerminateJobObject(job.value, 1); WaitForSingleObject(process.value, 5000); result = "transport-host-error"; }
            const std::string rendererOut = DrainText(outRead.value), rendererErr = DrainText(errRead.value);
            process.Close(); job.Close(); toRendererWrite.Close(); fromRendererRead.Close(); outRead.Close(); errRead.Close(); section.Close();
            std::string json = Format("{\"result\":\"%s\",\"protocol_version\":%u,\"host_pointer_bytes\":%zu,\"adapter_luid\":%llu,\"ack_status\":%u,\"scene_status\":%u,\"scene_width\":%u,\"scene_height\":%u,"
                "\"scene_file_sha256\":\"%s\",\"frames\":[%s],\"stopped\":%s,\"stop_completed\":%u,\"stop_discarded\":%u,\"session_completed\":%u,\"session_discarded\":%u,"
                "\"renderer_exit_code\":%lu,\"child_reaped\":%s,\"host_handles_before\":%lu,\"host_handles_after\":%lu,\"renderer_stdout\":%s,\"renderer_stderr\":%s}\n",
                result.c_str(), unsigned(tp::SupportedVersion), sizeof(void*), static_cast<unsigned long long>(luid), ackStatus, sceneStatus, width, height,
                rrt::scene::Hex(sceneDigest).c_str(), frames.c_str(), stopped ? "true" : "false", stopAck.completedFrames, stopAck.discardedFrames, session.Completed(), session.Discarded(),
                static_cast<unsigned long>(exitCode), reaped ? "true" : "false", static_cast<unsigned long>(handlesBefore), static_cast<unsigned long>(HandleCount()), Quote(rendererOut).c_str(), Quote(rendererErr).c_str());
            lastOk = result == "transport-host-pass" || result == "transport-host-refused" || result == "transport-host-scene-refused" || result == "transport-host-injected";
            lastJson = json;
        }
        handlesAfterEach.push_back(HandleCount());
        }
        std::string handles; for (const DWORD h : handlesAfterEach) handles += (handles.empty() ? "" : ",") + std::to_string(h);
        lastJson.pop_back(); lastJson.pop_back();  // drop the closing brace and newline of the last session's report
        std::printf("%s,\"repeat\":%u,\"host_handles_each\":[%s],\"host_handles_baseline\":%lu}\n", lastJson.c_str(), o.repeat, handles.c_str(), static_cast<unsigned long>(handlesBefore));
        return lastOk ? 0 : 1;
    } catch (const std::exception& error) {
        std::printf("{\"result\":\"transport-host-error\",\"error\":%s}\n", Quote(error.what()).c_str());
        return 2;
    }
}
