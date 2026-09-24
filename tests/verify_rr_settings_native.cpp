// CPU-only API-double tests: no DLL loading, device creation or GPU dispatch.
#include <windows.h>
#include <ffx_api_loader.h>
#include <ffx_denoiser.h>
#include <cstring>
#include <cstddef>
#include <iterator>
#include <string>
#include <sstream>
#include <iostream>
#include <stdexcept>
void Require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
std::string Quote(const char* text) { return '"'+std::string(text)+'"'; }
#include "../src/dxr/rr_settings.h"
namespace {
UINT selected,fault,queries,configures; ffxContext* expectedContext;
ffxReturnCode_t Query(ffxContext* context,ffxQueryDescHeader* header) {
    Require(context==expectedContext&&header->type==FFX_API_QUERY_DESC_TYPE_DENOISER_GET_DEFAULT_KEYVALUE&&!header->pNext,"query header/context");
    auto& q=*reinterpret_cast<ffxQueryDescDenoiserGetDefaultKeyValue*>(header);
    Require(q.key==RrSettings[selected].key&&q.count==1&&q.data,"query key/count/data"); ++queries;
    if(fault==1) return 6;
    if(fault==2) return 0; // A false success that wrote nothing.
    uint32_t bits=fault==3?0x7fc00000:fault==4?RrFloatBits(2):RrFloatBits(RrSettings[selected].expectedDefault);
    memcpy(q.data,&bits,4);
    if(fault==5) { const uint32_t bad=0; memcpy(static_cast<unsigned char*>(q.data)+4,&bad,4); }
    return 0;
}
ffxReturnCode_t Configure(ffxContext* context,const ffxConfigureDescHeader* header) {
    Require(context==expectedContext&&header->type==FFX_API_CONFIGURE_DESC_TYPE_DENOISER_KEYVALUE&&!header->pNext,"configure header/context");
    const auto& q=*reinterpret_cast<const ffxConfigureDescDenoiserKeyValue*>(header);
    Require(q.key==RrSettings[selected].key&&q.count==1&&q.data,"configure key/count/data");
    Require(RrFloatBits(*static_cast<const float*>(q.data))==RrFloatBits(RrSettings[selected].value),"configure changed value");
    ++configures; return fault==6?6:0;
}
}
int main() {
    try {
        ffxFunctions api{}; api.Query=Query; api.Configure=Configure;
        ffxContext context=reinterpret_cast<ffxContext>(uintptr_t(1)); expectedContext=&context;
        for(selected=1;selected<std::size(RrSettings);++selected) for(fault=0;fault<=6;++fault) {
            queries=configures=0; const auto result=RrConfigureSetting(api,&context,selected);
            Require(queries==1&&configures==UINT(fault==0||fault==6),"unadmitted default configured");
            Require(result.ready==(fault==0),"failed query/configure accepted");
            const auto code=fault==0?0u:fault==6?6u:UINT32_MAX;
            Require(result.json.find("\"configure_code\":"+std::to_string(code))!=std::string::npos,"raw configure code lost");
            std::cout << result.json << '\n';
        }
        std::cout << (std::size(RrSettings)-1)*7 << " native setting admission/ABI/failure cases passed\n"; return 0;
    } catch(const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
