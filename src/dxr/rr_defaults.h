// Read-only inspection of the six documented scalar filter defaults.
// Failed queries retain raw bytes/codes; they never become invented defaults.
#pragma once
#include <cmath>
#include <cstring>
#include <iomanip>
#include <locale>
#include <limits>
#include <cstddef>

std::string RrQueryDefaults(ffxFunctions& api,ffxContext* context,const char* phase) {
    constexpr uint32_t sentinel=0x7fc0a55a,guard=0xa59c3e71;
    constexpr uint64_t keys[]={
        FFX_API_CONFIGURE_DENOISER_KEY_CROSS_BILATERAL_NORMAL_STRENGTH,
        FFX_API_CONFIGURE_DENOISER_KEY_STABILITY_BIAS,
        FFX_API_CONFIGURE_DENOISER_KEY_MAX_RADIANCE,
        FFX_API_CONFIGURE_DENOISER_KEY_RADIANCE_CLIP_STD_K,
        FFX_API_CONFIGURE_DENOISER_KEY_GAUSSIAN_KERNEL_RELAXATION,
        FFX_API_CONFIGURE_DENOISER_KEY_DISOCCLUSION_THRESHOLD};
    std::ostringstream out; out.imbue(std::locale::classic());
    out << std::setprecision(std::numeric_limits<float>::max_digits10)
        << "{\"phase\":" << Quote(phase) << ",\"format\":\"float32\",\"count\":1,\"queries\":[";
    bool first=true;
    for(const auto key:keys) {
        struct Guarded { uint32_t before; float value; uint32_t after; } cell{guard,0,guard};
        static_assert(sizeof(Guarded)==12&&offsetof(Guarded,value)==4&&offsetof(Guarded,after)==8);
        std::memcpy(&cell.value,&sentinel,sizeof(sentinel));
        ffxQueryDescDenoiserGetDefaultKeyValue query{};
        query.header.type=FFX_API_QUERY_DESC_TYPE_DENOISER_GET_DEFAULT_KEYVALUE;
        query.key=key; query.count=1; query.data=&cell.value;
        const uint32_t code=api.Query(context,&query.header);
        uint32_t bits; std::memcpy(&bits,&cell.value,sizeof(bits));
        const bool valid=code==FFX_API_RETURN_OK&&cell.before==guard&&cell.after==guard&&bits!=sentinel&&std::isfinite(cell.value);
        if(!first) out << ','; first=false;
        out << "{\"key\":" << key << ",\"code\":" << code << ",\"bits\":" << bits
            << ",\"guard_before\":" << cell.before << ",\"guard_after\":" << cell.after << ",\"value\":";
        // Plain "-0" is parsed as an integer by JSON readers and loses its
        // sign. Preserve all finite float32 values, including negative zero.
        if(valid&&cell.value==0&&std::signbit(cell.value)) out << "-0.0";
        else if(valid) out << cell.value;
        else out << "null";
        out << '}';
    }
    out << "]}"; return out.str();
}
