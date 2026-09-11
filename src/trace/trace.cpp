#include "trace.h"
#include <algorithm>
#include <charconv>
#include <cstdio>
#include <limits>
#include <mutex>
#include <string_view>
#include <io.h>
#include <fcntl.h>

namespace rrt {
namespace {
std::uint64_t Setting(const wchar_t* name, std::uint64_t fallback) {
    wchar_t text[32]{};
    DWORD count = GetEnvironmentVariableW(name, text, 32);
    if(!count || count >= 32) return fallback;
    wchar_t* end{};
    const auto n = wcstoull(text, &end, 10);
    return end == text + count && text[0] != L'-' ? n : fallback;
}
struct Writer {
    std::mutex mutex;
    FILE* file{};
    std::uint64_t frame{}, sequence{}, bytes{}, count{}, limit{}, start{}, frames{};
    bool closed{};
    bool waiting{};
    wchar_t trigger[32768]{};
    Writer() noexcept {
        wchar_t path[32768]{};
        DWORD n = GetEnvironmentVariableW(L"RRT_TRACE_FILE", path, 32768);
        if(!n || n >= 32768) return;
        // Exclusive creation avoids destroying an earlier capture accidentally.
        HANDLE handle = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if(handle == INVALID_HANDLE_VALUE) { OutputDebugStringA("RRT: trace file unavailable; tracing disabled\n"); return; }
        const int descriptor=_open_osfhandle(reinterpret_cast<intptr_t>(handle),_O_BINARY);
        if(descriptor == -1) { CloseHandle(handle); return; }
        file=_fdopen(descriptor,"wb");
        if(!file) { _close(descriptor); return; }
        limit = (std::max)(std::uint64_t(4096), Setting(L"RRT_TRACE_MAX_BYTES", 64ull*1024*1024));
        start = Setting(L"RRT_TRACE_START_FRAME", 0);
        frames = Setting(L"RRT_TRACE_FRAME_COUNT", 300);
        const DWORD triggerLength=GetEnvironmentVariableW(L"RRT_TRACE_TRIGGER_FILE",trigger,32768);
        waiting=triggerLength!=0;
        if(triggerLength>=32768) trigger[0]=0; // Invalid trigger fails closed.
        if(!waiting) Header();
    }
    void Header() noexcept {
        char header[512]{};
        sprintf_s(header, "{\"type\":\"header\",\"schema\":\"rrt-observation\",\"version\":1,\"start_frame\":%llu,\"frame_count\":%llu,\"pointer_bits\":%u}\n", start, frames, unsigned(sizeof(void*)*8));
        Raw(header);
    }
    void Raw(std::string_view text) noexcept {
        if(!file) return;
        if(fwrite(text.data(), 1, text.size(), file) != text.size()) { fclose(file); file=nullptr; closed=true; return; }
        bytes += text.size();
    }
    void Close(const char* reason) noexcept {
        if(closed || !file) return;
        if(waiting) { start=frame; Header(); waiting=false; }
        char footer[256]{};
        sprintf_s(footer, "{\"type\":\"footer\",\"reason\":\"%s\",\"events\":%llu,\"present_count\":%llu}\n", reason, count, frame);
        Raw(footer);
        if(file) { fclose(file); file=nullptr; }
        closed=true;
    }
};
// Intentionally process lifetime: no CRT file/mutex teardown under DllMain.
Writer& GetWriter() { static auto* writer = new Writer; return *writer; }
}
bool TraceEnabled() noexcept { try { auto& w=GetWriter(); std::lock_guard lock(w.mutex); return w.file && !w.closed && !w.waiting && w.frame>=w.start && w.frame-w.start<w.frames; } catch(...) { return false; } }
void Event(std::uint64_t object, const char* method, HRESULT result, const std::string& fields) noexcept {
    try {
        auto& w=GetWriter(); std::lock_guard lock(w.mutex);
        if(!w.file || w.closed || w.waiting || w.frame<w.start || w.frame-w.start>=w.frames) return;
        auto line=std::string("{\"type\":\"event\",\"seq\":")+std::to_string(w.sequence)+",\"frame\":"+std::to_string(w.frame)+",\"thread_id\":"+std::to_string(GetCurrentThreadId())+",\"object\":"+std::to_string(object)+",\"method\":\""+method+"\",\"hr\":"+std::to_string(static_cast<std::int32_t>(result))+",\"args\":{"+fields+"}}\n";
        if(w.bytes+line.size()+256>w.limit) { w.Close("byte_limit"); return; }
        w.Raw(line); ++w.sequence; ++w.count;
    } catch(...) { OutputDebugStringA("RRT: event dropped due to diagnostics failure\n"); }
}
void EndPresent(HRESULT result) noexcept {
    if(result != S_OK) return;
    try { auto& w=GetWriter(); std::lock_guard lock(w.mutex); ++w.frame;
        if(w.waiting && w.file && !w.closed && w.frame>=w.start) {
            const DWORD attributes=GetFileAttributesW(w.trigger);
            if(attributes!=INVALID_FILE_ATTRIBUTES && !(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))) {
                w.start=w.frame; w.waiting=false; w.Header();
            }
        }
        if(w.waiting) return;
        if(w.frame>=w.start && w.frame-w.start>=w.frames) w.Close("frame_limit");
        if(w.file) fflush(w.file);
    } catch(...) {}
}
void FinishTrace() noexcept { try { auto& w=GetWriter(); std::lock_guard lock(w.mutex); w.Close("finished"); } catch(...) {} }
void Fields::Bytes(const char* name, const void* pointer, std::size_t size) {
    if(!pointer) return;
    // Only fixed-size structs and explicitly counted small state arrays enter here.
    size=(std::min)(size, std::size_t(4096));
    Key(name); data+='"';
    const auto* p=static_cast<const unsigned char*>(pointer);
    constexpr char hex[]="0123456789abcdef";
    for(std::size_t i=0;i<size;++i) { data+=hex[p[i]>>4]; data+=hex[p[i]&15]; }
    data+='"';
}
}
