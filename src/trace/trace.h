#pragma once
#include <windows.h>
#include <unknwn.h>
#include <cmath>
#include <cstdint>
#include <string>
#include <type_traits>

namespace rrt {
// Tracing never changes an API result. Disabled by default; noexcept boundaries
// isolate diagnostics failures from the host game.
bool TraceEnabled() noexcept;
void Event(std::uint64_t object, const char* method, HRESULT result,
           const std::string& fields = "") noexcept;
void EndPresent(HRESULT result) noexcept;
void FinishTrace() noexcept;
std::uint64_t ObjectId(IUnknown* object) noexcept;

class Fields {
public:
    std::string data;
    template<class T> void Value(const char* name, T value) {
        static_assert(std::is_arithmetic_v<T> || std::is_enum_v<T>);
        Key(name);
        if constexpr(std::is_floating_point_v<T>) data += std::isfinite(value) ? std::to_string(value) : "null";
        else if constexpr(std::is_signed_v<T>) data += std::to_string(static_cast<long long>(value));
        else data += std::to_string(static_cast<unsigned long long>(value));
    }
    void Object(const char* name, IUnknown* object) { Value(name, ObjectId(object)); }
    void Bytes(const char* name, const void* pointer, std::size_t size);
private:
    void Key(const char* name) { if(!data.empty()) data += ','; data += '"'; data += name; data += "\":"; }
};
}
