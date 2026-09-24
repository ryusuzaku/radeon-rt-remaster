# Radeon RT Remaster

An experimental AMD-focused legacy-game remastering runtime. The current build provides D3D9/9Ex observation, bounded fixed-function scene capture, independent raster replay, offline stable-ID asset replacement, glTF export and a standalone D3D12/DXR renderer. FidelityFX RR and radiance-cache experiments execute on the GPU; full path tracing, live game integration and quality/performance acceptance remain open. See the [whole-project status](docs/PROJECT_STATUS.md) for completed foundations and remaining product gates.

## Build and verify

Windows, Visual Studio 2022 C++ Build Tools with Windows SDK/x86 tools, CMake 3.25+, and Python 3.10+ for tests/inspection:

```powershell
cmake --preset windows-x86
cmake --build --preset debug
ctest --preset debug
```

Use the `release` build/test presets for optimized binaries. Python is optional for a runtime-only configuration with `-DBUILD_TESTING=OFF`.

## Implemented

- Typed forwarding for 20 D3D9/9Ex interfaces, including all 119 IDirect3DDevice9 methods, textures, vertex/index buffers, surfaces, swap chains, shader objects, queries, and state blocks.
- COM identity preservation across QueryInterface, GetDevice, GetDirect3D, and GetContainer; wrapping of returned interfaces and unwrapping of input interfaces.
- Lazy system-D3D9 loading; `RRT_PROXY_DISABLE=1` for native forwarding; standard D3DPERF exports.
- Opt-in bounded JSONL traces of resource metadata, locks/unlocks, state changes, transforms, shader use, draws, Present/PresentEx, Reset/ResetEx, and object lifetimes.
- Python inspector with validation, per-frame timelines, resource inventory, fixed-function/shader draw counts, and machine-readable output.
- Resource-owned buffer/texture snapshots, draw-time scene extraction, stable SHA-256 asset IDs and a bounded, integrity-checked scene format.
- Standalone `rrt_replay.exe` with preview, exact-pixel output, per-draw prefix replay and explicit rejection diagnostics; self-contained glTF export.
- Offline mod workflow: editable PNG/mesh extraction, strict manifests, hash-pinned dependencies, deterministic priority/conflict handling, and texture/mesh/material replacement into new replayable scenes. See the [creator quickstart](docs/MOD_WORKFLOW.md).
- Optional stable-ID material sidecars for the DXR viewer: tint, roughness/metallic GGX direct lighting, emission and diffuse-only bounce transport, plus light colour/intensity controls. Existing captures/default shading stay unchanged. See [material authoring and limits](docs/MATERIAL_INPUTS.md).
- Hardware DXR 1.1 inline-ray-query rendering with albedo, geometric normals, directional shadows and progressive one-bounce diffuse GI. Persistent GPU scenes, interactive camera/light controls, deterministic accumulation/reset tests and separate x64 renderer presets. See the [DXR viewer guide](docs/DXR_VIEWER.md).
- Versioned float radiance/albedo/normal/ray-depth/camera-motion exports with a bounded inspector, optional geometry-guided spatial filtering and camera-reprojected temporal reuse. Surface/disocclusion checks, bounded history, luminance moments and reset diagnostics preserve a separate raw accumulation path. FidelityFX integration and animated geometry remain future work.
- Compact float32 working/history buffers fit the full-HD synthetic fixture under the existing 512 MiB requested-buffer cap. Diagnostic exports use fixed-size GPU/readback chunks and streaming validation instead of full-frame staging.
- Native D3D12 swapchain preview with GPU-source display, bounded resizing, suspend/restore handling and back-buffer pixel verification. A fence-gated command/constant ring enables bounded asynchronous submission without per-sample native readback; snapshots, resize and teardown drain explicitly. Normal native viewing uses message-responsive DXGI frame admission with maximum frame latency one; `--no-frame-pacing`, headless and `--gdi` comparison paths remain available. Live game presentation and measured display-latency qualification remain later work.

## Evidence

AMD Ray Regeneration research now executes a real reset-only 128×96 indirect-diffuse dispatch in a supervised x64 worker on the RX 9070 XT. Execution, allocation cleanup and crash recovery pass using exact pinned-SDK reporting workarounds; raw SDK acceptance still fails. Image quality is not accepted: the strict zero-light oracle detects a small positive bias. The custom variance filter also remains experimental after failing its improvement gate. The existing renderer/filter stays unchanged. See [dispatch evidence and remaining gates](docs/RR_DISPATCH.md).

The renderer exports [fresh RR lighting and matched guides](docs/RR_INPUTS.md) using `--rr-inputs NEW_FILE` at 128×96, and [records 2–8 frames with source identity and camera continuity](docs/RR_RECORDING.md) using `--rr-record`. The isolated worker runs [stationary history](docs/RR_SEQUENCE.md) and now [source-verified moving recordings through AMD RR](docs/RR_RECORDED_DISPATCH.md). Recorded cuts/resets recreate the SDK context after a strict equivalence test exposed residual differences. Live memory caps are unchanged; image-quality acceptance and live integration remain open.

[Independent matched-hit quality measurements](docs/RR_QUALITY.md) show lower spatial/revealed-region error on a small constant-colour diffuse fixture. The new [textured/PBR and matched fallback comparisons](docs/RR_SURFACE_QUALITY.md) expose substantial RR spatial regressions instead. The exact-zero bias also remains. These retained counterexamples keep RR experimental; execution success is not image-quality acceptance.

[Analytic colour-response controls](docs/RR_COLOUR_RESPONSE.md) now reproduce spatial contrast loss on a stationary, noise-free plane without PBR or occlusion. This narrows the investigation; it does not fix the SDK output or change the default filter.

The worker now supports a [provenance-checked linear/square-root albedo comparison](docs/RR_ALBEDO_ENCODING.md). Both documented encodings retain the contrast failure; the default linear outputs remain byte-compatible. [Read-only live-context default queries](docs/RR_DEFAULT_SETTINGS.md) expose the six scalar filter settings with raw return codes and repeated-write validation; no filter overrides are applied.

A separate opt-in [single-setting experiment path](docs/RR_FILTER_SETTINGS.md) applies predefined stability/Gaussian overrides with per-context admission and configure evidence. Tagged output requires the matching explicit preset; default reapplication is checked against unchanged output before comparing any changed values. The renderer/filter default remains unchanged.

The bounded [multi-seed surface comparison](docs/RR_MULTI_SEED_SETTINGS.md) measures default/half/zero stability on textured and PBR motion with independent renderer seeds, paired temporal/disocclusion deltas and shared source-verified references. It does not select or promote a default.

The follow-up [eight-frame history experiment](docs/RR_LONG_HISTORIES.md) separates stationary settling, continuous camera motion and explicit reset recovery under the unchanged reference-work cap.

The [coherent coordinate-scale experiment](docs/RR_COORDINATE_SCALE.md) transforms every SDK-visible length and matching camera matrix while holding 128x96 resolution fixed. Scale ten slightly changes the spatial/temporal balance but fixes no failed absolute gate, so unit scale and all renderer defaults remain unchanged.

The [native-resolution experiment](docs/RR_NATIVE_RESOLUTION.md) adds a strict 256x192 v2 recording/worker ABI while preserving historical 128x96 bytes. Higher resolution improves spatial/disocclusion estimates but has mixed temporal behavior and still fails the absolute quality gates, so it is retained as sensitivity evidence rather than promoted.

The [guide-conditioning experiment](docs/RR_GUIDE_CONDITIONING.md) adds strict material-class and filter-range provenance, then compares five fixed candidates on the same moving texture/PBR recordings. Material partitioning and reduced normal strength create only small mixed tradeoffs, while a non-clipping maximum-radiance change is inert; every absolute spatial/fallback gate still fails and no preset is promoted.

The [exact-zero floor reproducer](docs/RR_ZERO_FLOOR.md) localizes the remaining black bias to SDK-active pixels: zero albedo, zero hit distance, scalar settings and eight history frames do not clear it, while inactive/background pixels remain exact zero. Fresh Debug evidence is byte-exact with Release. The strict zero-light gate remains failed; no bias compensation is applied.

The separate [FidelityFX Radiance Cache foundation](docs/RADIANCE_CACHE.md) verifies the signed 0.9.0 D3D12 provider on the RX 9070 XT inside a 32 MiB supervised context boundary. Allocation lifecycle and crash recovery pass in Release and Debug; raw provider metadata acceptance still fails under one exact hash-pinned workaround. That context-only phase records zero cache dispatches and makes no rendering or quality claim; its external-buffer design feeds the synthetic phase below.

The follow-up [Radiance Cache synthetic dispatch](docs/RADIANCE_CACHE_DISPATCH.md) executes reset, inference, 512-sample optional training and counter clearing over the exact 716,808-byte external interface. Release/Debug output and repeats are byte-identical, all guards and teardown pass, and the known raw metadata failure remains visible. It is real cache work but not yet game rendering; its deterministic fixture feeds the persistent sequence below.

The [persistent training sequence](docs/RADIANCE_CACHE_TRAINING.md) now proves that one default 512-sample batch changes every later prediction in a target-directed way on the same context, while reset restores the baseline exactly. All counters, buffers, device state and allocations remain clean in Release and Debug. This demonstrates synthetic online learning—not game-scene quality; renderer-exported paths and guarded compositing are next.

The [renderer path bridge](docs/RADIANCE_CACHE_PATHS.md) now carries a strict `RCRPATH1` artifact through the isolated signed provider. The canonical DXR fixture yields 172 real secondary-hit queries; one training batch improves both target and guarded composite MSE, and reset is exact. Ordinary pixels/signals remain unchanged and live replacement stays disabled; renderer-owned resource scheduling is the next boundary.

The [isolated live transaction](docs/RADIANCE_CACHE_LIVE.md) removes temporary path files: the renderer emits a fixed binary stream into a job-contained provider child. Two persistent static training frames improve the guarded candidate further; camera identity changes start clean state, and crash/timeout paths preserve the authoritative no-cache output. This is still a CPU readback/pipe/upload prototype, not shared-resource or game integration.

The [shared D3D12 transport](docs/RADIANCE_CACHE_SHARED.md) now includes renderer-owned GPU compaction, guarded composition, opt-in native presentation and a live fence-driven provider session. One contained process/context continues training across a stable frame, then accepts GPU-regenerated +0.05-camera inputs through fences 30–35 and explicitly resets provider state. The changed frame rediscovers 178 queries and exactly matches a fresh moved-camera candidate; timeout/premature exit remains no-cache and recoverable. Defaults remain no-cache, and no raw path payload crosses the process boundary. Moving this bounded three-epoch session into the interactive scheduler and then D3D9 game presentation remain separate gates.

The x86 harness compares exact image bytes against the system runtime in classic D3D9 and D3D9Ex. It renders a textured indexed triangle through fixed-function and shader paths, performs UP draws, presents through devices and swap chains, exercises an invalid reset followed by recovery and resize, checks COM identity, and recovers a device from a resource after releasing the original device wrapper.

Integration tests also check deterministic metadata/counts, tracing off, proxy disabled, selected frames, byte limits, existing/unwritable trace paths, resource lifetimes, and malformed/truncated input. Verification artifacts remain in the build directory.

The separate four-quadrant scene fixture replays with zero differing colour bytes in classic/Ex frames before and after Reset. It tests all four supported draw entry points, signed base vertices, 16/32-bit indices, partial buffer/texture updates, mid-frame texture changes, transforms and scissoring. Unsupported shaders/state/resource writes and budget overflows produce incomplete captures, rejected by default.

Validated hardware: Radeon RX 9070 XT, driver 32.0.31041.1004. Commercial-game acceptance, second-GPU validation, fullscreen/alt-tab/device-loss testing, and performance qualification remain open.

Mod tests independently change texture, mesh and material assets, check unaffected pixels are byte-identical, and verify composition across repeated captures and static mesh matching after Reset. This is offline captured-scene editing, not live game asset injection.

## Capture and inspect

```powershell
$captureId = [guid]::NewGuid().ToString()
$env:RRT_TRACE_FILE = Join-Path $PWD "build\capture-$captureId.rrt.jsonl"
$tracePath = $env:RRT_TRACE_FILE
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --frames 12
python tools\inspect_trace.py $tracePath
python tools\inspect_trace.py $tracePath --frame 0 --json
Remove-Item Env:\RRT_TRACE_FILE
```

See [scene capture, replay and glTF quickstart](docs/SCENE_CAPTURE.md), [build instructions](docs/BUILD.md), [trace format and limits](docs/TRACE_FORMAT.md), [phase plan](PHASE_PLAN.md), and [compatibility ledger](docs/COMPATIBILITY_LEDGER.md).

Observation traces contain metadata; `.rrscene` files separately contain geometry/texture payloads and content hashes. The first extraction subset is unlit XYZ/diffuse/UV triangle lists with one CPU-written 2D texture and no depth buffer; it is not a universal D3D9 scene converter. Unknown private COM interfaces and undocumented DLL exports remain outside the forwarding contract; no external game is certified yet.

## Status of this release

This is a **pre-release snapshot**, published for reference and experiment. It is
not a finished runtime and no commercial title is certified. **No version has
been tagged**: the first numbered release will come when a title actually runs
end to end. See
[whole-project status](docs/PROJECT_STATUS.md) for what is proven and what is
not, [compatibility ledger](docs/COMPATIBILITY_LEDGER.md) for the qualification
boundary, and [codebase map](CODEBASE_MAP.md) for the architecture, the known
technical debt and the proposed delivery plan.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE). Third-party and attribution notices
are in [NOTICE](NOTICE), which also records that no game content is distributed
and that the FidelityFX research paths are optional and not redistributed.
