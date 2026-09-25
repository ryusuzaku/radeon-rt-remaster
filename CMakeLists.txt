cmake_minimum_required(VERSION 3.25)

project(RadeonRTRemaster LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "Radeon RTRemaster's D3D9 proxy harness builds on Windows only.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(rrt_scene STATIC src/scene/scene.cpp)
target_compile_definitions(rrt_scene PUBLIC UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_link_libraries(rrt_scene PUBLIC bcrypt)

option(RRT_RENDERER_ONLY "Build standalone scene renderers without a game proxy/harness" OFF)
if(NOT RRT_RENDERER_ONLY)
add_library(radeon_d3d9_proxy SHARED
    src/proxy/d3d9_proxy.cpp
    src/proxy/observers.cpp
    src/trace/trace.cpp
    src/capture/capture.cpp
    src/shader/intercept.cpp
    src/shader/inventory.cpp
    src/proxy/d3d9_proxy.def
)
target_compile_definitions(radeon_d3d9_proxy PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_link_libraries(radeon_d3d9_proxy PRIVATE user32 rrt_scene)
set_target_properties(radeon_d3d9_proxy PROPERTIES
    OUTPUT_NAME d3d9
    PREFIX ""
)

add_executable(d3d9_smoke_sample
    src/sample/d3d9_smoke_sample.cpp
)
target_compile_definitions(d3d9_smoke_sample PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN)
target_link_libraries(d3d9_smoke_sample PRIVATE d3dcompiler user32)
add_library(rrt_shader_snapshot STATIC src/shader/snapshot.cpp src/shader/position.cpp src/shader/position_capture.cpp)
target_link_libraries(rrt_shader_snapshot PUBLIC rrt_scene d3dcompiler)
target_link_libraries(radeon_d3d9_proxy PRIVATE rrt_shader_snapshot)
add_executable(rrt_shader_fixture src/shader/fixture.cpp)
add_executable(rrt_shader_disassemble src/shader/disassemble.cpp)
target_link_libraries(rrt_shader_disassemble PRIVATE d3dcompiler)
target_link_libraries(rrt_shader_fixture PRIVATE rrt_shader_snapshot user32)
endif()

add_executable(rrt_replay src/replay/main.cpp)
target_link_libraries(rrt_replay PRIVATE rrt_scene user32)

# Windows SDK DXC is a build-time dependency only. Override RRT_DXC for a
# separately installed compiler; the viewer consumes compiled DXIL at runtime.
file(GLOB RRT_DXC_CANDIDATES "C:/Program Files (x86)/Windows Kits/10/bin/*/x64/dxc.exe")
list(SORT RRT_DXC_CANDIDATES COMPARE NATURAL ORDER DESCENDING)
find_program(RRT_DXC NAMES dxc)
if(NOT RRT_DXC AND RRT_DXC_CANDIDATES)
    list(GET RRT_DXC_CANDIDATES 0 RRT_DXC)
endif()
if(RRT_DXC)
    add_executable(rrt_dxr src/dxr/main.cpp)
    target_link_libraries(rrt_dxr PRIVATE rrt_scene d3d12 dxgi user32 gdi32)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rr_inputs.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E prepareRr -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rr_inputs.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/rr_inputs.hlsl"
        DEPENDS src/dxr/rr_inputs.hlsl src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_paths.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E prepareRcPaths -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_paths.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/rc_paths.hlsl"
        DEPENDS src/dxr/rc_paths.hlsl src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_compact.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E compactRcPaths -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_compact.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/rc_compact.hlsl"
        DEPENDS src/dxr/rc_compact.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_composite.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E compositeRcPaths -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_composite.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/rc_composite.hlsl"
        DEPENDS src/dxr/rc_composite.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_apply.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E applyRcCandidate -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_apply.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/rc_apply.hlsl"
        DEPENDS src/dxr/rc_apply.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_rayquery.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E main -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_rayquery.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/render.hlsl"
        DEPENDS src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_present.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E present -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_present.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/render.hlsl"
        DEPENDS src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_temporal.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E temporalResolve -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_temporal.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/render.hlsl"
        DEPENDS src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_export.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E exportSignals -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_export.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/render.hlsl"
        DEPENDS src/dxr/render.hlsl VERBATIM)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_variance.dxil"
        COMMAND "${RRT_DXC}" -T cs_6_5 -E variancePrepare -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_variance.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/render.hlsl"
        DEPENDS src/dxr/render.hlsl VERBATIM)
    foreach(STAGE vertex pixel)
        if(STAGE STREQUAL "vertex")
            set(PROFILE vs_6_5)
        else()
            set(PROFILE ps_6_5)
        endif()
        add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_${STAGE}.dxil"
            COMMAND "${RRT_DXC}" -T ${PROFILE} -E ${STAGE} -HV 2021 -WX -O3 -Fo "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_${STAGE}.dxil" "${CMAKE_CURRENT_SOURCE_DIR}/src/dxr/display.hlsl"
            DEPENDS src/dxr/display.hlsl VERBATIM)
    endforeach()
    add_custom_target(rrt_dxr_shader
        COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:rrt_dxr>"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rr_inputs.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rr_inputs.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_paths.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rc_paths.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_compact.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rc_compact.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_composite.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rc_composite.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_apply.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rc_apply.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_rayquery.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_rayquery.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_present.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_present.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_temporal.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_temporal.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_export.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_export.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_variance.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_variance.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_vertex.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_display_vertex.dxil"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_pixel.dxil" "$<TARGET_FILE_DIR:rrt_dxr>/rrt_display_pixel.dxil"
        DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/rrt_rr_inputs.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_paths.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_compact.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_composite.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_rc_apply.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_rayquery.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_present.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_temporal.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_export.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_variance.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_vertex.dxil" "${CMAKE_CURRENT_BINARY_DIR}/rrt_display_pixel.dxil")
    add_dependencies(rrt_dxr rrt_dxr_shader)
else()
    message(WARNING "DXC not found: rrt_dxr omitted. Set RRT_DXC to Windows SDK dxc.exe.")
endif()

include(CTest)
set(RRT_FSR_SDK "" CACHE PATH "Optional FSR SDK 2.3.0 root for the standalone x64 RR research probe")
if(RRT_FSR_SDK)
    if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
        message(FATAL_ERROR "The optional RR SDK probe requires an x64 build; leave RRT_FSR_SDK empty for x86.")
    endif()
    if(NOT EXISTS "${RRT_FSR_SDK}/Kits/FidelityFX/denoisers/include/ffx_denoiser.h")
        message(FATAL_ERROR "RRT_FSR_SDK must contain Kits/FidelityFX/denoisers/include/ffx_denoiser.h")
    endif()
    add_executable(rrt_rr_probe src/dxr/rr_probe.cpp)
    target_include_directories(rrt_rr_probe PRIVATE "${RRT_FSR_SDK}/Kits/FidelityFX/api/include" "${RRT_FSR_SDK}/Kits/FidelityFX/denoisers/include")
    target_compile_definitions(rrt_rr_probe PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX PLATFORM_WINDOWS)
    target_link_libraries(rrt_rr_probe PRIVATE d3d12 dxgi bcrypt)
endif()
set(RRT_FSR_RC_SDK "" CACHE PATH "Optional FSR SDK 2.3.0 root for the standalone x64 Radiance Cache research probe")
if(RRT_FSR_RC_SDK)
    if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
        message(FATAL_ERROR "The optional Radiance Cache probe requires an x64 build; leave RRT_FSR_RC_SDK empty for x86.")
    endif()
    if(NOT EXISTS "${RRT_FSR_RC_SDK}/Kits/FidelityFX/radiancecache/include/ffx_radiancecache.h")
        message(FATAL_ERROR "RRT_FSR_RC_SDK must contain Kits/FidelityFX/radiancecache/include/ffx_radiancecache.h")
    endif()
    add_executable(rrt_rc_probe src/dxr/rc_probe.cpp)
    target_include_directories(rrt_rc_probe PRIVATE "${RRT_FSR_RC_SDK}/Kits/FidelityFX/api/include" "${RRT_FSR_RC_SDK}/Kits/FidelityFX/radiancecache/include")
    target_compile_definitions(rrt_rc_probe PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX PLATFORM_WINDOWS)
    target_link_libraries(rrt_rc_probe PRIVATE d3d12 dxgi bcrypt)
    add_executable(rrt_rc_shared src/dxr/rc_shared.cpp)
    target_compile_definitions(rrt_rc_shared PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_link_libraries(rrt_rc_shared PRIVATE d3d12 dxgi)
endif()
if(BUILD_TESTING)
find_package(Python3 COMPONENTS Interpreter REQUIRED)
if(TARGET rrt_rr_probe)
    add_executable(rrt_rr_settings_contract tests/verify_rr_settings_native.cpp)
    target_include_directories(rrt_rr_settings_contract PRIVATE "${RRT_FSR_SDK}/Kits/FidelityFX/api/include" "${RRT_FSR_SDK}/Kits/FidelityFX/denoisers/include")
    target_compile_definitions(rrt_rr_settings_contract PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX PLATFORM_WINDOWS)
    add_test(NAME rr_settings_contract COMMAND rrt_rr_settings_contract)
    set_tests_properties(rr_settings_contract PROPERTIES TIMEOUT 10)
    add_test(NAME rr_probe_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_probe.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rr_probe_contract PROPERTIES TIMEOUT 60)
    add_test(NAME rr_worker_boundary COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_worker.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rr_worker_boundary PROPERTIES TIMEOUT 120)
    if(TARGET rrt_dxr)
        add_test(NAME rr_dispatch COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_dispatch.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rr_dispatch PROPERTIES TIMEOUT 180)
        add_test(NAME rr_sequence COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_sequence.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rr_sequence PROPERTIES TIMEOUT 180)
        add_test(NAME rr_recorded_dispatch COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_recorded_dispatch.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rr_recorded_dispatch PROPERTIES TIMEOUT 240)
        add_test(NAME rr_guides COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_guides.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rr_guides PROPERTIES TIMEOUT 180)
        add_test(NAME rr_black_floor COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_black_floor.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rr_black_floor PROPERTIES TIMEOUT 240)
        execute_process(COMMAND ${Python3_EXECUTABLE} -c "import numpy" RESULT_VARIABLE RRT_NUMPY_STATUS OUTPUT_QUIET ERROR_QUIET TIMEOUT 10)
        if(RRT_NUMPY_STATUS STREQUAL "0")
            add_test(NAME rr_native_resolution COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_native_resolution.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_native_resolution PROPERTIES TIMEOUT 180)
            add_test(NAME rr_quality COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_quality.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_quality PROPERTIES TIMEOUT 300)
            add_test(NAME rr_surfaces COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_surfaces.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_surfaces PROPERTIES TIMEOUT 420)
            add_test(NAME rr_colour_response COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_color_response.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_colour_response PROPERTIES TIMEOUT 300)
            add_test(NAME rr_encoding COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_encoding.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_encoding PROPERTIES TIMEOUT 360)
            add_test(NAME rr_defaults COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_defaults.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_defaults PROPERTIES TIMEOUT 300)
            add_test(NAME rr_settings COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_settings.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_settings PROPERTIES TIMEOUT 420)
            add_test(NAME rr_surface_settings_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_setting_surfaces.py)
            set_tests_properties(rr_surface_settings_contract PROPERTIES TIMEOUT 10)
            add_test(NAME rr_history_settings_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_setting_histories.py)
            set_tests_properties(rr_history_settings_contract PROPERTIES TIMEOUT 10)
            add_test(NAME rr_scale COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_scale.py --probe $<TARGET_FILE:rrt_rr_probe> --sdk-bin "${RRT_FSR_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
            set_tests_properties(rr_scale PROPERTIES TIMEOUT 360)
            add_test(NAME rr_coordinate_scale_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_coordinate_scales.py)
            set_tests_properties(rr_coordinate_scale_contract PROPERTIES TIMEOUT 10)
        else()
            message(STATUS "NumPy RR quality/settings tests omitted: install tools/requirements-rr-quality.txt in the selected Python environment")
        endif()
    endif()
endif()
if(TARGET rrt_rc_probe)
    add_test(NAME rc_shared_transport_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_shared.py --probe $<TARGET_FILE:rrt_rc_shared> --provider-probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rc_shared_transport_contract PROPERTIES TIMEOUT 60)
    add_test(NAME rc_probe_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_probe.py --probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rc_probe_contract PROPERTIES TIMEOUT 90)
    add_test(NAME rc_worker_boundary COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_worker.py --probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rc_worker_boundary PROPERTIES TIMEOUT 240)
    add_test(NAME rc_dispatch_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_dispatch.py --probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rc_dispatch_contract PROPERTIES TIMEOUT 240)
    add_test(NAME rc_sequence_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_sequence.py --probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin")
    set_tests_properties(rc_sequence_contract PROPERTIES TIMEOUT 240)
    if(TARGET rrt_dxr)
        add_test(NAME rc_path_sequence_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_path_sequence.py --probe $<TARGET_FILE:rrt_rc_probe> --sdk-bin "${RRT_FSR_RC_SDK}/Kits/FidelityFX/signedbin" --dxr $<TARGET_FILE:rrt_dxr>)
        set_tests_properties(rc_path_sequence_contract PROPERTIES TIMEOUT 240 SKIP_RETURN_CODE 77)
    endif()
endif()
if(TARGET rrt_dxr)
    add_test(NAME dxr_probe COMMAND rrt_dxr --probe)
    add_test(NAME dxr_render COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_dxr.py --dxr $<TARGET_FILE:rrt_dxr> --replay $<TARGET_FILE:rrt_replay>)
    set_tests_properties(dxr_render PROPERTIES TIMEOUT 120 SKIP_RETURN_CODE 77)
    add_test(NAME dxr_temporal COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_temporal.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_temporal PROPERTIES TIMEOUT 120 SKIP_RETURN_CODE 77)
    add_test(NAME dxr_resolution COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_dxr_resolution.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_resolution PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77)
    add_test(NAME dxr_presentation COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_presentation.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_presentation PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77)
    add_test(NAME dxr_async COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_async.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_async PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77)
    add_test(NAME dxr_pacing COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_pacing.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_pacing PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77)
    add_test(NAME material_inputs COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_material_inputs.py)
    set_tests_properties(material_inputs PROPERTIES TIMEOUT 30)
    add_test(NAME dxr_materials COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_materials.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(dxr_materials PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77)
    add_test(NAME rr_inputs COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_inputs.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(rr_inputs PROPERTIES TIMEOUT 120 SKIP_RETURN_CODE 77)
    add_test(NAME rc_paths_export COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rc_paths.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(rc_paths_export PROPERTIES TIMEOUT 120 SKIP_RETURN_CODE 77)
    add_test(NAME rr_record COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_rr_record.py --dxr $<TARGET_FILE:rrt_dxr>)
    set_tests_properties(rr_record PROPERTIES TIMEOUT 180)
endif()
if(NOT RRT_RENDERER_ONLY)
  add_test(NAME trace_reader COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_trace_reader.py)
  add_test(NAME position_scene COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_position_scene.py)
# The checked-in generated forwards must stay current with their generator;
# nothing else verifies them, so a hand edit or schema change would ship silently.
add_test(NAME codegen_freshness COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_codegen_freshness.py)
set_tests_properties(codegen_freshness PROPERTIES TIMEOUT 120)
# The capture-version ladder is the project's central artifact contract and is
# described in three places (C++ enum/fold, the JSON schema, the Python reader).
# Nothing else checks that they agree.
add_test(NAME capture_version_contract COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_capture_version_contract.py)
set_tests_properties(capture_version_contract PROPERTIES TIMEOUT 60)
# The repository is public, so a doc that points at an unpublished file sends
# readers looking for something that was never shipped.
add_test(NAME published_references COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_published_references.py)
set_tests_properties(published_references PROPERTIES TIMEOUT 60)
# The shadow-budget analysis turns one game pass into a policy decision, so it must
# read the cap from source and refuse to answer from a ledger that cannot answer.
add_test(NAME shadow_budget_tool COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_shadow_budget_tool.py)
set_tests_properties(shadow_budget_tool PROPERTIES TIMEOUT 60)
add_test(NAME shader_snapshot COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_shader_snapshot.py --fixture $<TARGET_FILE:rrt_shader_fixture>)
set_tests_properties(shader_snapshot PROPERTIES TIMEOUT 120)
add_test(NAME shader_proxy COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_shader_proxy.py --fixture $<TARGET_FILE:rrt_shader_fixture> --proxy $<TARGET_FILE:radeon_d3d9_proxy>)
set_tests_properties(shader_proxy PROPERTIES TIMEOUT 180)
add_test(NAME shader_inventory COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_shader_inventory.py --fixture $<TARGET_FILE:rrt_shader_fixture> --proxy $<TARGET_FILE:radeon_d3d9_proxy>)
set_tests_properties(shader_inventory PROPERTIES TIMEOUT 180)
add_test(NAME shader_disassembly COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_shader_disassembly.py --fixture $<TARGET_FILE:rrt_shader_fixture> --proxy $<TARGET_FILE:radeon_d3d9_proxy> --disassembler $<TARGET_FILE:rrt_shader_disassemble>)
set_tests_properties(shader_disassembly PROPERTIES TIMEOUT 120)
# This opt-in local-evidence test is registered only where the owned game capture exists.
set(RRT_HL2_POSITION_INVENTORY "${CMAKE_CURRENT_SOURCE_DIR}/build/game-passes/hl2-inventory-20260907/runs/inventory/shader-inventory.jsonl" CACHE FILEPATH "Local HL2 inventory for exact-program position oracle")
if(EXISTS "${RRT_HL2_POSITION_INVENTORY}")
add_test(NAME hl2_position COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_hl2_position.py --fixture $<TARGET_FILE:rrt_shader_fixture> --inventory "${RRT_HL2_POSITION_INVENTORY}")
set_tests_properties(hl2_position PROPERTIES TIMEOUT 120)
add_test(NAME position_capture COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_position_capture.py --fixture $<TARGET_FILE:rrt_shader_fixture> --proxy $<TARGET_FILE:radeon_d3d9_proxy> --inventory "${RRT_HL2_POSITION_INVENTORY}")
set_tests_properties(position_capture PROPERTIES TIMEOUT 180)
foreach(texture_kind compressed upload dirty surface locks scope selection)
add_test(NAME texture_${texture_kind} COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_texture_paths.py --kind ${texture_kind} --fixture $<TARGET_FILE:rrt_shader_fixture> --proxy $<TARGET_FILE:radeon_d3d9_proxy> --inventory "${RRT_HL2_POSITION_INVENTORY}")
set_tests_properties(texture_${texture_kind} PROPERTIES TIMEOUT 120 RESOURCE_LOCK native_texture_fixture)
endforeach()
set_tests_properties(position_capture PROPERTIES RESOURCE_LOCK native_texture_fixture)
  endif()
set(RRT_HL2_POSITION_CAPTURE "${CMAKE_CURRENT_SOURCE_DIR}/build/game-passes/hl2-combined-20260907/runs/combined/position-capture.jsonl" CACHE FILEPATH "Local real HL2 position capture for raster verification")
if(EXISTS "${RRT_HL2_POSITION_CAPTURE}")
add_test(NAME recorded_position_oracle COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_recorded_position_oracle.py --fixture $<TARGET_FILE:rrt_shader_fixture> --capture "${RRT_HL2_POSITION_CAPTURE}")
set_tests_properties(recorded_position_oracle PROPERTIES TIMEOUT 180)
add_test(NAME position_reconstruction COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_position_reconstruction.py --capture "${RRT_HL2_POSITION_CAPTURE}")
add_test(NAME capture_position_scene COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_capture_position_scene.py --capture "${RRT_HL2_POSITION_CAPTURE}")
endif()
add_test(NAME mod_validation COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_mods.py)
set(RRT_HL2_GROUP_CAPTURE "${CMAKE_CURRENT_SOURCE_DIR}/build/game-passes/hl2-multidraw-20260907/runs/multidraw/position-capture.jsonl" CACHE FILEPATH "Local multi-draw HL2 capture for grouped position replay")
if(EXISTS "${RRT_HL2_GROUP_CAPTURE}")
add_test(NAME position_groups COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_position_groups.py --capture "${RRT_HL2_GROUP_CAPTURE}" --fixture $<TARGET_FILE:rrt_shader_fixture>)
set_tests_properties(position_groups PROPERTIES TIMEOUT 180)
endif()
add_test(NAME mod_replay COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_mods.py --sample $<TARGET_FILE:d3d9_smoke_sample> --replay $<TARGET_FILE:rrt_replay>)
add_test(NAME mod_replay_ex COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_mods.py --sample $<TARGET_FILE:d3d9_smoke_sample> --replay $<TARGET_FILE:rrt_replay> --ex)
set_tests_properties(mod_replay mod_replay_ex PROPERTIES TIMEOUT 120)
add_test(NAME proxy_equivalence COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_runtime.py --sample $<TARGET_FILE:d3d9_smoke_sample>)
add_test(NAME game_pass_workflow COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_game_pass.py --sample $<TARGET_FILE:d3d9_smoke_sample> --proxy $<TARGET_FILE:radeon_d3d9_proxy> --replay $<TARGET_FILE:rrt_replay>)
set_tests_properties(game_pass_workflow PROPERTIES TIMEOUT 120)
add_test(NAME workbench COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_workbench.py --fixture $<TARGET_FILE:d3d9_smoke_sample> --proxy $<TARGET_FILE:radeon_d3d9_proxy>)
set_tests_properties(workbench PROPERTIES TIMEOUT 300)
add_test(NAME proxy_equivalence_ex COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_runtime.py --sample $<TARGET_FILE:d3d9_smoke_sample> --ex)
add_test(NAME scene_replay COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_scene.py --sample $<TARGET_FILE:d3d9_smoke_sample> --replay $<TARGET_FILE:rrt_replay>)
add_test(NAME scene_replay_ex COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_scene.py --sample $<TARGET_FILE:d3d9_smoke_sample> --replay $<TARGET_FILE:rrt_replay> --ex)
set_tests_properties(scene_replay scene_replay_ex PROPERTIES TIMEOUT 120)
set_tests_properties(proxy_equivalence proxy_equivalence_ex PROPERTIES TIMEOUT 120)
add_test(NAME d3d9_smoke_sample_help COMMAND d3d9_smoke_sample --help)
add_test(NAME d3d9_smoke_sample_run COMMAND d3d9_smoke_sample)
endif()
endif()
