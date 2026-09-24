// Standalone SDK research tool: bounded contexts/offline sequences, no renderer hooks.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <memory>
#include <ffx_api_loader.h>
#include <ffx_denoiser.h>

static_assert(FFX_DENOISER_VERSION_MAJOR==1 && FFX_DENOISER_VERSION_MINOR==2 && FFX_DENOISER_VERSION_PATCH==0,
              "Review the probe contract before changing the RR SDK version");
using Microsoft::WRL::ComPtr;
namespace {
void Require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
std::string QuoteBytes(const std::string& value) {
    std::ostringstream out; out << '"';
    for(const unsigned char c:value) {
        if(c=='"'||c=='\\') out << '\\' << c;
        else if(c<32) { const char hex[]="0123456789abcdef"; out << "\\u00" << hex[c>>4] << hex[c&15]; }
        else out << c;
    }
    out << '"'; return out.str();
}
std::string Quote(const char* value) { return QuoteBytes(value?std::string(value):std::string()); }
struct Module {
    HMODULE handle{};
    explicit Module(const std::filesystem::path& path) {
        Require(path.is_absolute()&&std::filesystem::is_regular_file(path),"SDK DLL missing or path is not absolute");
        handle=LoadLibraryExW(path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        Require(handle!=nullptr,"SDK DLL load failed (architecture, dependency or signature policy)");
    }
    ~Module() { if(handle) FreeLibrary(handle); }
    Module(const Module&)=delete;
    Module& operator=(const Module&)=delete;
};
UINT BoundedUnsigned(const wchar_t* text,UINT maximum) {
    Require(*text!=0,"unsigned value missing"); UINT result=0;
    for(const wchar_t* p=text;*p;++p) { Require(*p>=L'0'&&*p<=L'9',"expected an unsigned decimal value"); result=result*10+UINT(*p-L'0'); Require(result<=maximum,"unsigned value out of range"); }
    return result;
}
}
#include "rr_context.h"
#include "rr_isolation.h"
#include "rr_dispatch.h"
#include "rr_sequence.h"
#include "rr_recorded_dispatch.h"
int wmain(int argc,wchar_t** argv) {
    try {
        if(argc==3&&std::wstring(argv[1])==L"--isolation-child") return RrIsolationChild(argv[2]);
        if(argc==3&&std::wstring(argv[1])==L"--isolation-test") {
            if(std::wstring(argv[2])==L"parent-exit") { RrRunIsolated({L"--isolation-child",L"timeout"},30000,true); return 1; }
            const auto result=RrRunIsolated({L"--isolation-child",argv[2]},std::wstring(argv[2])==L"timeout"?100u:30000u);
            std::cout << result.Json() << '\n'; return 0;
        }
        std::filesystem::path directory; UINT index=0; bool debug=false,contextTest=false;
        std::filesystem::path inputPath,outputPath; bool dispatchTest=false,sequenceTest=false,recordingTest=false; UINT externalMiB=8;
        bool albedoOption=false,sqrtAlbedo=false,queryDefaults=false;
        bool settingOption=false,settingFailed=false; UINT settingId=0;
        bool scaleOption=false; UINT scaleId=0;
        bool guideOption=false; UINT guideId=0;
        UINT cycles=2,budgetMiB=64,failAt=0,timeoutMs=30000; bool contextOption=false,sdkAllocator=false,allocatorTest=false,isolated=false,child=false;
        for(int i=1;i<argc;++i) {
            const std::wstring arg=argv[i];
            if(arg==L"--help") std::cout << "Recorded --filter-setting PRESET: stability-default|stability-half|stability-zero|gaussian-default|gaussian-quarter|gaussian-half|gaussian-one|normal-default|normal-half|max-radiance-default|max-radiance-one (or none). Implies default inspection; configured output requires matching preset provenance.\n";
            if(arg==L"--help") std::cout << "Recorded dispatch also accepts --query-defaults: read-only repeated queries of six scalar filter defaults on each live context. No configuration overrides.\n";
            if(arg==L"--help") std::cout << "Recorded --coordinate-scale PRESET: unit-tenth|unit-one|unit-ten (or none). Applies one coherent scene-unit transform and requires matching output provenance.\n";
            if(arg==L"--help") std::cout << "Recorded --guide-preset PRESET: material-draw (or none). Encodes source draw classes in normal alpha and requires matching output provenance.\n";
            if(arg==L"--help") std::cout << "SDK research: --isolated-dispatch (one reset frame), --isolated-sequence (2..8 stationary frames), or --isolated-recording (2..8 recorded translation frames), with --input ABS_INPUT --output ABS_NEW_OUTPUT --debug [--external-budget-mib 1..8]. Recorded dispatch alone also accepts --albedo-encoding linear|sqrt (default linear). Use tools/rr_dispatch.py, tools/rr_sequence.py or tools/rr_recorded_dispatch.py for pinned supervised execution and source checks; these do not accept image quality.\n";
            if(arg==L"--help") { std::cout << "rrt_rr_probe --sdk-bin ABSOLUTE_DIRECTORY [--adapter 0] [--debug] [--allocator-test] [--context-test|--isolated-context [--cycles 1..3] [--budget-mib 1..64] [--fail-allocation 1..31|--sdk-allocator-control] [--worker-timeout-ms 1..60000]]\nDefault: queries only. Optional fixed 128x96 context lifecycle; no RR rendering. SDK allocator control is preflight-only, not hard-budgeted. Use tools/rr_worker.py for supervised decisions; --isolated-context returns a transport envelope, not SDK success. Raw allocation-failure injection may crash its process.\n"; return 0; }
            if(arg==L"--sdk-bin"&&i+1<argc&&directory.empty()) directory=argv[++i];
            else if(arg==L"--adapter"&&i+1<argc) index=BoundedUnsigned(argv[++i],31);
            else if(arg==L"--debug") debug=true;
            else if(arg==L"--context-test") contextTest=true;
            else if(arg==L"--isolated-context") { isolated=true; contextTest=true; }
            else if(arg==L"--isolated-dispatch") { isolated=true; dispatchTest=true; cycles=1; }
            else if(arg==L"--dispatch-test") { dispatchTest=true; cycles=1; }
            else if(arg==L"--isolated-sequence") { isolated=true; dispatchTest=sequenceTest=true; cycles=1; }
            else if(arg==L"--sequence-test") { dispatchTest=sequenceTest=true; cycles=1; }
            else if(arg==L"--isolated-recording") { isolated=true; dispatchTest=sequenceTest=recordingTest=true; cycles=1; }
            else if(arg==L"--recording-test") { dispatchTest=sequenceTest=recordingTest=true; cycles=1; }
            else if(arg==L"--query-defaults"&&!queryDefaults) queryDefaults=true;
            else if(arg==L"--filter-setting"&&i+1<argc&&!settingOption) {
                const std::wstring name=argv[++i]; bool found=false;
                for(UINT k=0;k<std::size(RrSettings);++k) {
                    const std::string candidate=RrSettings[k].name;
                    if(name==std::wstring(candidate.begin(),candidate.end())) { settingId=k; found=true; break; }
                }
                Require(found,"unknown filter setting preset"); settingOption=true;
            }
            else if(arg==L"--albedo-encoding"&&i+1<argc&&!albedoOption) {
                const std::wstring value=argv[++i]; Require(value==L"linear"||value==L"sqrt","albedo encoding must be linear or sqrt");
                albedoOption=true; sqrtAlbedo=value==L"sqrt";
            }
            else if(arg==L"--coordinate-scale"&&i+1<argc&&!scaleOption) {
                const std::wstring name=argv[++i]; bool found=false;
                for(UINT k=0;k<std::size(RrScalePresets);++k) {
                    const std::string candidate=RrScalePresets[k].name;
                    if(name==std::wstring(candidate.begin(),candidate.end())) { scaleId=k; found=true; break; }
                }
                Require(found,"unknown coordinate scale preset"); scaleOption=true;
            }
            else if(arg==L"--guide-preset"&&i+1<argc&&!guideOption) {
                const std::wstring name=argv[++i]; bool found=false;
                for(UINT k=0;k<std::size(RrGuidePresets);++k) {
                    const std::string candidate=RrGuidePresets[k].name;
                    if(name==std::wstring(candidate.begin(),candidate.end())) { guideId=k; found=true; break; }
                }
                Require(found,"unknown guide preset"); guideOption=true;
            }
            else if(arg==L"--input"&&i+1<argc&&inputPath.empty()) inputPath=argv[++i];
            else if(arg==L"--output"&&i+1<argc&&outputPath.empty()) outputPath=argv[++i];
            else if(arg==L"--external-budget-mib"&&i+1<argc) { externalMiB=BoundedUnsigned(argv[++i],8); Require(externalMiB>0,"external budget must be positive"); }
            else if(arg==L"--worker-child") child=true;
            else if(arg==L"--worker-timeout-ms"&&i+1<argc) { timeoutMs=BoundedUnsigned(argv[++i],60000); Require(timeoutMs>0,"worker deadline must be positive"); }
            else if(arg==L"--allocator-test") allocatorTest=true;
            else if(arg==L"--sdk-allocator-control") { sdkAllocator=true; contextOption=true; }
            else if((arg==L"--cycles"||arg==L"--budget-mib"||arg==L"--fail-allocation")&&i+1<argc) {
                const std::wstring value=argv[++i];
                { const UINT n=BoundedUnsigned(value.c_str(),arg==L"--budget-mib"?64u:31u); Require(n>0,"context option must be positive");
                    if(arg==L"--cycles") { Require(n<=3,"cycles must be 1..3"); cycles=n; }
                    else if(arg==L"--budget-mib") budgetMiB=n;
                    else failAt=n;
                }
                contextOption=true;
            }
            else throw std::runtime_error("unknown, duplicate or incomplete option");
        }
        Require(directory.is_absolute(),"--sdk-bin requires an explicit absolute directory");
        Require(!contextOption||contextTest||dispatchTest,"context options require --context-test");
        Require(!sdkAllocator||(budgetMiB==64&&!failAt),"SDK allocator control requires the default budget and no injected failures");
        Require(!child||(!isolated&&(contextTest||dispatchTest)),"invalid worker child mode");
        Require(dispatchTest||(inputPath.empty()&&outputPath.empty()&&externalMiB==8),"dispatch paths/options require dispatch mode");
        Require(!albedoOption||recordingTest,"albedo encoding option requires recorded dispatch");
        Require(!queryDefaults||recordingTest,"default queries require recorded dispatch");
        Require(!settingOption||recordingTest,"filter setting requires recorded dispatch");
        Require(!scaleOption||recordingTest,"coordinate scale requires recorded dispatch");
        Require(!guideOption||recordingTest,"guide preset requires recorded dispatch");
        if(settingId) queryDefaults=true;
        if(dispatchTest) {
            Require(isolated||child,"dispatch requires the isolated host");
            Require(!contextTest&&!allocatorTest&&!sdkAllocator&&cycles==1&&debug,"dispatch requires one bounded context and --debug");
            Require(inputPath.is_absolute()&&outputPath.is_absolute()&&!std::filesystem::exists(outputPath),"dispatch requires absolute input/new output paths");
        }
        if(isolated) {
            Require(!sdkAllocator&&!allocatorTest,"isolated context requires bounded context mode");
            std::vector<std::wstring> args={L"--worker-child",recordingTest?L"--recording-test":sequenceTest?L"--sequence-test":dispatchTest?L"--dispatch-test":L"--context-test",L"--sdk-bin",directory.wstring(),L"--adapter",std::to_wstring(index),
                                          L"--cycles",std::to_wstring(cycles),L"--budget-mib",std::to_wstring(budgetMiB)};
            if(debug) args.push_back(L"--debug");
            if(failAt) { args.push_back(L"--fail-allocation"); args.push_back(std::to_wstring(failAt)); }
            if(dispatchTest) { args.insert(args.end(),{L"--input",inputPath.wstring(),L"--output",outputPath.wstring(),L"--external-budget-mib",std::to_wstring(externalMiB)}); }
            if(albedoOption) args.insert(args.end(),{L"--albedo-encoding",sqrtAlbedo?L"sqrt":L"linear"});
            if(queryDefaults) args.push_back(L"--query-defaults");
            if(settingOption) {
                const std::string name=RrSettings[settingId].name;
                args.insert(args.end(),{L"--filter-setting",std::wstring(name.begin(),name.end())});
            }
            if(scaleOption) {
                const std::string name=RrScalePresets[scaleId].name;
                args.insert(args.end(),{L"--coordinate-scale",std::wstring(name.begin(),name.end())});
            }
            if(guideOption) {
                const std::string name=RrGuidePresets[guideId].name;
                args.insert(args.end(),{L"--guide-preset",std::wstring(name.begin(),name.end())});
            }
            const auto result=RrRunIsolated(args,timeoutMs); std::cout << result.Json() << '\n'; return 0;
        }
        if(child) SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
        std::unique_ptr<RrInputFile> dispatchInput;
        std::unique_ptr<RrSequence> sequenceInput;
        if(recordingTest) { sequenceInput=std::make_unique<RrSequence>(); LoadRrRecording(*sequenceInput,inputPath); }
        else if(sequenceTest) sequenceInput=std::make_unique<RrSequence>(inputPath);
        else if(dispatchTest) dispatchInput=std::make_unique<RrInputFile>(inputPath);
        ComPtr<ID3D12Debug> layer;
        if(debug) { Require(SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&layer))),"D3D12 debug layer unavailable"); layer->EnableDebugLayer(); }
        ComPtr<IDXGIFactory6> factory; ComPtr<IDXGIAdapter1> adapter; ComPtr<ID3D12Device> device;
        Require(SUCCEEDED(CreateDXGIFactory2(0,IID_PPV_ARGS(&factory))),"DXGI factory failed");
        Require(SUCCEEDED(factory->EnumAdapters1(index,&adapter)),"adapter unavailable");
        DXGI_ADAPTER_DESC1 desc{}; Require(SUCCEEDED(adapter->GetDesc1(&desc)),"adapter description failed");
        Require(!(desc.Flags&DXGI_ADAPTER_FLAG_SOFTWARE),"software adapter is not an RR candidate");
        Require(SUCCEEDED(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_12_0,IID_PPV_ARGS(&device))),"D3D12 device unavailable");
        ComPtr<ID3D12InfoQueue1> diagnostics; DWORD callbackCookie{};
        if(debug&&SUCCEEDED(device.As(&diagnostics))) {
            Require(SUCCEEDED(diagnostics->RegisterMessageCallback([](D3D12_MESSAGE_CATEGORY,D3D12_MESSAGE_SEVERITY severity,D3D12_MESSAGE_ID,const char* message,void*) {
                if(severity<=D3D12_MESSAGE_SEVERITY_WARNING) std::cerr << "D3D12: " << message << '\n';
            },D3D12_MESSAGE_CALLBACK_FLAG_NONE,nullptr,&callbackCookie)),"debug callback registration failed");
            diagnostics->SetBreakOnSeverity(D3D12_MESSAGE_SEVERITY_ERROR,FALSE);
            diagnostics->SetBreakOnSeverity(D3D12_MESSAGE_SEVERITY_CORRUPTION,FALSE);
        }
        D3D12_FEATURE_DATA_SHADER_MODEL sm{D3D_SHADER_MODEL_6_6};
        const bool sm66=SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL,&sm,sizeof(sm)))&&sm.HighestShaderModel>=D3D_SHADER_MODEL_6_6;
        // Explicitly preload the selected effect; never search the working directory/PATH.
        Module effect(directory/L"amd_fidelityfx_denoiser_dx12.dll");
        Module loader(directory/L"amd_fidelityfx_loader_dx12.dll");
        ffxFunctions api{}; ffxLoadFunctions(&api,loader.handle);
        Require(api.Query&&api.Configure,"SDK query/configure exports missing");
        ffxConfigureDescGlobalDebug logging{}; logging.header.type=FFX_API_CONFIGURE_DESC_TYPE_GLOBALDEBUG;
        logging.effectId=FFX_API_EFFECT_ID_DENOISER; logging.debugLevel=FFX_API_CONFIGURE_GLOBALDEBUG_LEVEL_WARNINGS;
        logging.fpMessage=[](uint32_t,const wchar_t* message) { std::wcerr << L"RR: " << (message?message:L"") << L'\n'; };
        Require(api.Configure(nullptr,&logging.header)==FFX_API_RETURN_OK,"SDK logging configuration failed");
        uint64_t count=0; ffxQueryDescGetVersions versions{};
        versions.header.type=FFX_API_QUERY_DESC_TYPE_GET_VERSIONS; versions.createDescType=FFX_API_EFFECT_ID_DENOISER;
        versions.device=device.Get(); versions.outputCount=&count;
        const auto versionResult=api.Query(nullptr,&versions.header);
        Require(versionResult==FFX_API_RETURN_OK,"SDK provider enumeration failed");
        Require(count<=64,"SDK returned excessive provider count");
        std::vector<uint64_t> ids(static_cast<size_t>(count)); std::vector<const char*> names(static_cast<size_t>(count));
        if(count) {
            const auto capacity=count; versions.versionIds=ids.data(); versions.versionNames=names.data();
            Require(api.Query(nullptr,&versions.header)==FFX_API_RETURN_OK&&count<=capacity,"SDK provider enumeration changed or failed");
        }
        char name[1024]{}; WideCharToMultiByte(CP_UTF8,0,desc.Description,-1,name,sizeof(name),nullptr,nullptr);
        std::ostringstream out;
        out << "{\"adapter\":" << index << ",\"name\":" << Quote(name)
            << ",\"shader_model_6_6\":" << (sm66?"true":"false") << ",\"sdk_api\":\"1.2.0\",\"providers\":[";
        bool queriesOk=true;
        for(size_t i=0;i<count;++i) {
            if(i) out << ',';
            out << "{\"id\":" << ids[i] << ",\"name\":" << Quote(names[i]) << ",\"memory\":[";
            const FfxApiDimensions2D sizes[]={{128,96},{960,540},{1920,1080}};
            for(size_t j=0;j<3;++j) {
                ffxOverrideVersion version{}; version.header.type=FFX_API_DESC_TYPE_OVERRIDE_VERSION; version.versionId=ids[i];
                FfxApiEffectMemoryUsage usage{}; ffxQueryDescDenoiserGetGPUMemoryUsage query{};
                query.header.type=FFX_API_QUERY_DESC_TYPE_DENOISER_GPU_MEMORY_USAGE; query.header.pNext=&version.header;
                query.device=device.Get(); query.maxRenderSize=sizes[j]; query.signalFlags=FFX_DENOISER_SIGNAL_INDIRECT_DIFFUSE; query.gpuMemoryUsage=&usage;
                const auto result=api.Query(nullptr,&query.header);
                if(j) out << ',';
                out << "{\"width\":" << sizes[j].width << ",\"height\":" << sizes[j].height << ",\"query_code\":" << result;
                if(result==FFX_API_RETURN_OK) {
                    Require(usage.aliasableUsageInBytes<=usage.totalUsageInBytes,"SDK returned invalid memory accounting");
                    out << ",\"total_bytes\":" << usage.totalUsageInBytes << ",\"aliasable_bytes\":" << usage.aliasableUsageInBytes
                        << ",\"persistent_bytes\":" << usage.totalUsageInBytes-usage.aliasableUsageInBytes;
                } else queriesOk=false;
                out << '}';
            }
            out << "]}";
        }
        out << "]";
        if(allocatorTest) { TestRrAllocator(device.Get()); out << ",\"allocator_contract\":\"pass\""; }
        UINT created=0,destroyed=0;
        UINT rrDispatches=0; std::unique_ptr<RrDispatchGpu> dispatchGpu;
        std::vector<std::vector<unsigned char>> sequenceOutputs;
        if(dispatchTest) {
            Require(sm66&&count&&queriesOk,"RR dispatch provider unavailable");
            dispatchGpu=std::make_unique<RrDispatchGpu>(device.Get(),sequenceTest?sequenceInput->frames[0]:*dispatchInput,uint64_t(externalMiB)*1024*1024,sqrtAlbedo,scaleId,guideId);
            std::vector<std::string> frameReports,contextReports;
            const size_t countFrames=sequenceTest?sequenceInput->frames.size():1;
            for(size_t begin=0;begin<countFrames;) {
                size_t end=countFrames;
                if(recordingTest) {
                    end=begin+1;
                    while(end<countFrames&&!sequenceInput->frames[end].header[7]) ++end;
                }
                // Recorded camera resets use a fresh context: the pinned SDK's
                // reset flag alone failed exact fresh-context equivalence after
                // motion. Never overlap SDK contexts or raise the live budget.
                const auto result=TestRrContext(api,device.Get(),ids[0],uint64_t(budgetMiB)*1024*1024,failAt,false,
                    [&](ffxContext* context) {
                        for(size_t i=begin;i<end;++i) {
                            if(i) dispatchGpu->Upload(sequenceInput->frames[i]);
                            if(recordingTest) dispatchGpu->Dispatch(api,context,sequenceInput->segmentIndices[i],sequenceInput->cameraDeltas[i].data());
                            else dispatchGpu->Dispatch(api,context);
                            ++rrDispatches;
                            if(sequenceTest) { sequenceOutputs.push_back(dispatchGpu->OutputBytes()); frameReports.push_back(dispatchGpu->Json()); }
                        }
                    },queryDefaults,settingId,dispatchGpu->width,dispatchGpu->height);
                created+=result.created; destroyed+=result.destroyed; queriesOk=queriesOk&&result.passed;
                contextReports.push_back(result.Json());
                Require(result.created&&result.destroyed&&!result.live&&!result.errors&&!result.denials,"RR dispatch context lifecycle failed");
                if(!result.setting.ready) { settingFailed=true; queriesOk=false; break; }
                begin=end;
            }
            dispatchGpu->Release(); out << ",\"context_tests\":[";
            for(size_t i=0;i<contextReports.size();++i) { if(i) out << ','; out << contextReports[i]; }
            out << "],\"dispatch_test\":" << dispatchGpu->Json();
            if(sequenceTest) {
                out << ",\"sequence_test\":{\"input_sha256\":" << Quote(RrHex(sequenceInput->digest).c_str()) << ",\"frames\":[";
                for(size_t i=0;i<frameReports.size();++i) { if(i) out << ','; out << frameReports[i]; }
                out << "]";
                if(recordingTest) {
                    out << ",\"reset_policy\":\"recreate-context\"";
                    out << ",\"albedo_encoding\":" << Quote(sqrtAlbedo?"sqrt":"linear");
                    if(settingId) out << ",\"filter_setting\":" << Quote(RrSettings[settingId].name);
                    if(scaleId) out << ",\"coordinate_scale\":" << Quote(RrScalePresets[scaleId].name);
                    if(guideId) out << ",\"guide_preset\":" << Quote(RrGuidePresets[guideId].name);
                    const char* keys[]={"scene_sha256","material_sha256","shader_sha256","settings_sha256"};
                    out << ",\"recording\":{";
                    for(UINT k=0;k<4;++k) { if(k) out << ','; out << Quote(keys[k]) << ':' << Quote(RrHex(sequenceInput->identities[k]).c_str()); }
                    out << '}';
                }
                out << '}';
            }
        }
        if(contextTest) {
            Require(sm66,"RR context test requires shader model 6.6");
            out << ",\"context_tests\":[";
            if(count&&queriesOk) for(UINT cycle=0;cycle<cycles;++cycle) {
                const auto result=TestRrContext(api,device.Get(),ids[0],uint64_t(budgetMiB)*1024*1024,failAt,sdkAllocator);
                if(cycle) out << ','; out << result.Json();
                created+=result.created; destroyed+=result.destroyed;
                if(!result.passed) queriesOk=false;
                if(!result.created||!result.destroyed||result.live||result.errors) break;
            }
            out << "]";
        }
        ComPtr<ID3D12InfoQueue> info;
        if(debug && SUCCEEDED(device.As(&info))) {
            for(UINT64 i=0;i<info->GetNumStoredMessagesAllowedByRetrievalFilter();++i) {
                SIZE_T length=0; info->GetMessage(i,nullptr,&length); std::vector<unsigned char> bytes(length);
                auto* message=reinterpret_cast<D3D12_MESSAGE*>(bytes.data());
                Require(SUCCEEDED(info->GetMessage(i,message,&length)),"debug message retrieval failed");
                Require(message->Severity>D3D12_MESSAGE_SEVERITY_ERROR,"D3D12 debug layer reported an error during RR queries");
            }
        }
        if(sequenceTest&&!settingFailed) sequenceInput->Save(outputPath,sequenceOutputs,sqrtAlbedo,settingId,scaleId,guideId);
        else if(dispatchGpu&&!settingFailed) dispatchGpu->Save(outputPath);
        out << ",\"dispatches\":" << rrDispatches << ",\"contexts_created\":" << created << ",\"contexts_destroyed\":" << destroyed
            << ",\"result\":" << Quote(!count?"no-provider":!queriesOk?"validation-failed":(contextTest||dispatchTest)?"context-tests-pass":"queried") << "}"; std::cout << out.str() << '\n';
        if(diagnostics) diagnostics->UnregisterMessageCallback(callbackCookie);
        return !queriesOk?1:count?0:77;
    } catch(const std::exception& error) { std::cerr << "rrt_rr_probe: " << error.what() << '\n'; return 1; }
}
