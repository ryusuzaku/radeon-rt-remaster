// Predeclared one-key research experiments, not an unrestricted tuning API.
#pragma once
struct RrSetting {
    const char* name; uint64_t key; float value,expectedDefault;
};
inline constexpr RrSetting RrSettings[]={
    {"none",0,0,0},
    {"stability-default",FFX_API_CONFIGURE_DENOISER_KEY_STABILITY_BIAS,1,1},
    {"stability-half",FFX_API_CONFIGURE_DENOISER_KEY_STABILITY_BIAS,.5f,1},
    {"stability-zero",FFX_API_CONFIGURE_DENOISER_KEY_STABILITY_BIAS,0,1},
    {"gaussian-default",FFX_API_CONFIGURE_DENOISER_KEY_GAUSSIAN_KERNEL_RELAXATION,0,0},
    {"gaussian-quarter",FFX_API_CONFIGURE_DENOISER_KEY_GAUSSIAN_KERNEL_RELAXATION,.25f,0},
    {"gaussian-half",FFX_API_CONFIGURE_DENOISER_KEY_GAUSSIAN_KERNEL_RELAXATION,.5f,0},
    {"gaussian-one",FFX_API_CONFIGURE_DENOISER_KEY_GAUSSIAN_KERNEL_RELAXATION,1,0},
    {"normal-default",FFX_API_CONFIGURE_DENOISER_KEY_CROSS_BILATERAL_NORMAL_STRENGTH,1,1},
    {"normal-half",FFX_API_CONFIGURE_DENOISER_KEY_CROSS_BILATERAL_NORMAL_STRENGTH,.5f,1},
    {"max-radiance-default",FFX_API_CONFIGURE_DENOISER_KEY_MAX_RADIANCE,65504,65504},
    {"max-radiance-one",FFX_API_CONFIGURE_DENOISER_KEY_MAX_RADIANCE,1,65504}};

uint32_t RrFloatBits(float value) { uint32_t bits; memcpy(&bits,&value,4); return bits; }

struct RrSettingResult {
    std::string json;
    bool ready=true;
};

RrSettingResult RrConfigureSetting(ffxFunctions& api,ffxContext* context,UINT id) {
    Require(id>0&&id<std::size(RrSettings),"invalid setting preset");
    const auto& setting=RrSettings[id];
    constexpr uint32_t guard=0xa59c3e71,sentinel=0x7fc0a55a;
    struct Guarded { uint32_t before; float value; uint32_t after; } cell{guard,0,guard};
    static_assert(sizeof(Guarded)==12&&offsetof(Guarded,value)==4&&offsetof(Guarded,after)==8);
    memcpy(&cell.value,&sentinel,4);
    ffxQueryDescDenoiserGetDefaultKeyValue query{};
    query.header.type=FFX_API_QUERY_DESC_TYPE_DENOISER_GET_DEFAULT_KEYVALUE;
    query.key=setting.key; query.count=1; query.data=&cell.value;
    const uint32_t queryCode=api.Query(context,&query.header),bits=RrFloatBits(cell.value);
    const bool admitted=queryCode==0&&cell.before==guard&&cell.after==guard&&bits==RrFloatBits(setting.expectedDefault);
    uint32_t configureCode=UINT32_MAX;
    if(admitted) {
        ffxConfigureDescDenoiserKeyValue config{};
        config.header.type=FFX_API_CONFIGURE_DESC_TYPE_DENOISER_KEYVALUE;
        config.key=setting.key; config.count=1; config.data=&setting.value;
        configureCode=api.Configure(context,&config.header);
    }
    std::ostringstream out;
    out << "{\"preset\":" << Quote(setting.name) << ",\"key\":" << setting.key
        << ",\"format\":\"float32\",\"count\":1,\"value_bits\":" << RrFloatBits(setting.value)
        << ",\"default_query_code\":" << queryCode << ",\"default_bits\":" << bits
        << ",\"guard_before\":" << cell.before << ",\"guard_after\":" << cell.after
        << ",\"configure_attempted\":" << (admitted?"true":"false") << ",\"configure_code\":" << configureCode << '}';
    return {out.str(),admitted&&configureCode==0};
}
