# Build, run, and inspect

## Prerequisites

- Windows with a D3D9-capable graphics driver for the GPU tests.
- Visual Studio 2022 C++ Build Tools, x86 toolset, and Windows SDK.
- CMake 3.25+.
- Python 3.10+ for tests and inspection. Code generation uses only Python's standard library; generated C++ is checked in.

## Reproducible x86 commands

These Visual Studio presets do not require a developer shell:

```powershell
cmake --preset windows-x86
cmake --build --preset debug
ctest --preset debug
cmake --build --preset release
ctest --preset release
```

Outputs are in `build/x86-vs/Debug` and `build/x86-vs/Release`: `d3d9.dll`, `d3d9_smoke_sample.exe` and `rrt_replay.exe`. The scene codec uses Windows BCrypt SHA-256; there is no third-party runtime dependency.

With Windows SDK DXC available, these builds also include `rrt_dxr.exe` and
`rrt_rayquery.dxil`, `rrt_temporal.dxil`, `rrt_present.dxil`, `rrt_export.dxil`,
`rrt_display_vertex.dxil` and `rrt_display_pixel.dxil`. Deploy all six matching shaders with the
executable. Prefer the separate x64 renderer for standalone DXR work:

```powershell
cmake --preset windows-x64-renderer
cmake --build --preset renderer-debug
ctest --preset renderer-debug
cmake --build --preset renderer-release
ctest --preset renderer-release
```

This outputs only standalone renderers (no game proxy) into
`build/x64-renderer/Debug` and `Release`. See [DXR_VIEWER.md](DXR_VIEWER.md) for
capability requirements, DXC discovery, modes and limitations.

For a runtime-only build, configure a separate binary directory with `-DBUILD_TESTING=OFF` to avoid requiring Python. If using Ninja, activate an x86 Visual Studio environment and omit `-A Win32`; Ninja does not support that platform argument.

## Tests

CTest runs ten entries: trace-reader and mod-validation suites, classic/Ex mod replay, classic/Ex proxy equivalence, classic/Ex scene replay, and smoke/help entry points. Integration tests load the system DLL explicitly for baseline renders, confirm the proxy marker when requested, and compare raw image bytes with proxy-on, trace-off, and proxy-disabled runs.

When DXC is available, `dxr_probe`, `dxr_render`, `dxr_temporal`, `dxr_resolution`,
`dxr_presentation`, `dxr_async`, `dxr_pacing`, `dxr_materials` and CPU-only
`material_inputs` make nineteen x86 entries. The renderer-only x64 presets run
these nine entries (eight GPU tests and one CPU authoring test) with their own raster oracle.
The DXR GPU test skips explicitly on unsupported adapters; it does not silently
use a software renderer. Standard D3D12 debug-layer validation is enabled when
the Windows Graphics Tools component is installed.

The fixture draws textured indexed geometry through fixed-function and shader paths and includes UP draws, resource/stateblock identities, device/swap-chain Present, invalid-reset recovery, resize, readback, and resource-held device lifetime recovery. Trace checks cover record validation, deterministic IDs/counts, selected frame ranges, byte budgets, and unavailable/existing output paths.

Artifacts are retained under `build/x86-vs/<configuration>/verify-*`. Each directory includes pixel dumps and traces from that test. `LastTest.log` records the exact artifact directory.

Scene replay artifacts are under `scene-*`, including PNG previews, raw pixels, captures, image-diff JSON and glTF exports. See [SCENE_CAPTURE.md](SCENE_CAPTURE.md) for the supported subset, format, controls and replay commands.

Mod artifacts are under `mods-*`, including editable assets/manifests, modified scenes, PNGs and isolation reports. The [offline creator workflow](MOD_WORKFLOW.md) uses Python's standard library only; there is no extra SDK/image-library installation step.

## Direct use

```powershell
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --runtime system --frames 12
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --frames 12
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --ex --frames 12
```

The sample prints render hashes for images at 256x192 and 320x240. `--pixels PATH` writes concatenated BGR byte arrays for exact comparison. `--read-frame N` selects a single image; `--scene-fixture` selects the four-draw replay fixture. The DLL is selected by an absolute path; neither fixture nor replay has a D3D9 import dependency that could accidentally load the wrong provider.

See [README](../README.md) for a trace example and [TRACE_FORMAT](TRACE_FORMAT.md) for all environment controls. The earlier automatic LOCALAPPDATA text log was replaced by explicit opt-in observation traces.

## Regenerate API forwards

```powershell
python tools/generate_observers.py
```

The generator uses the checked-in `tools/d3d9_interfaces.json` SDK signature inventory. API parameter unwrapping, returned-object wrapping, and trace policy live in the generator; identity ownership lives in `src/proxy/observers.cpp`.

## Current qualification

Verified on one Radeon RX 9070 XT (driver 32.0.31041.1004) in x86 Debug and Release. Unknown private COM interfaces and undocumented exports are unsupported. Real-game startup/input/fullscreen/alt-tab qualification, a second Radeon, and timing/VRAM budgets remain acceptance work. Commercial games have not been modified or tested.
