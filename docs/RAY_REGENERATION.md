# Ray Regeneration investigation

Status (2026-09-03): **a real reset-only 128×96 RR dispatch now executes in the supervised worker on this RX 9070 XT**. Typed input/output and process recovery tests pass with explicit pinned-SDK reporting workarounds. Raw SDK acceptance still fails; the SDK binary has not been fixed. Image quality is not accepted: the exact-zero lighting oracle detects a small positive bias. See [dispatch evidence and limitations](RR_DISPATCH.md). The default renderer still uses its analytical filter. ROCm is not required for this DX12 path.

The user selected AMD RR after three custom-filter designs failed their improvement gate. Planning-file tracking keeps experiments, SDK availability and actual denoising acceptance separate.

## Reproduce the isolated probe

Normal x86/x64 builds have no SDK dependency. The optional x64 target uses FSR SDK v2.3.0 headers and checks for denoiser API 1.2.0 at compile time. CMake never downloads dependencies or copies DLLs into the renderer or a game.

```powershell
cmake -S . -B build/rr-sdk-probe -G "Visual Studio 17 2022" -A x64 -DRRT_RENDERER_ONLY=ON -DRRT_FSR_SDK=build/dependencies/fsr-2.3.0-probe
cmake --build build/rr-sdk-probe --config Release --target rrt_rr_probe
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(probe_contract|worker_boundary)$' --output-on-failure
.\build\rr-sdk-probe\Release\rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --debug
```

The local research subset contains five headers (`ffx_api.h`, `ffx_api_types.h`, `ffx_api_loader.h`, `dx12/ffx_api_dx12.h`, `ffx_denoiser.h`), both DLLs below and the complete license notice in their original `Kits/FidelityFX` layout. On another machine, supply a trusted SDK checkout and adjust the paths.

Pinned commit: `60f4ea81909200d8542eca14dccb2628b763a9a3` (v2.3.0). Both DLLs passed Authenticode verification with AMD as signer. The probe loads from the explicit SDK directory plus Windows system dependencies; it does not verify signatures itself, so trusted files are required.

| DLL | Recorded SHA-256 |
|---|---|
| amd_fidelityfx_denoiser_dx12.dll | 48f1e5888ba6a0a3d59a98b9751e37c392b0f7b8c223d0082d5c1f40642879d3 |
| amd_fidelityfx_loader_dx12.dll | e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa |

Headers and binaries have different terms; retain the SDK notices when distributing dependencies. No reverse engineering or binary modification is part of this work. See the [pinned license](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/docs/license.md).

By default the tool only enumerates providers, pins each ID for pre-context memory queries and prints JSON. Optional context/allocator diagnostics are described below. These modes never submit a rendering dispatch; the separate `--isolated-dispatch` mode is documented in [RR dispatch](RR_DISPATCH.md). For the direct query/context diagnostics, exit 0 means the requested checks succeeded; 77 means no provider; 1 means failure (a provider crash can instead terminate the diagnostic process). The contract test accepts a correctly labelled no-provider response, not as proof of RR rendering. `--debug` enables the standard D3D12 layer and rejects recorded errors; this is not GPU-based validation. Missing files, relative DLL paths and malformed arguments fail explicitly.

## Supervised context boundary and reporting workarounds

```powershell
python tools/rr_worker.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --cycles 3
```

This managed command checks both DLL SHA-256 values above before enabling either workaround. Its result is `context-ready-with-workarounds`, `raw_sdk_acceptance: failed`, `rr_rendering: false`. Exit 0 means only this bounded context policy passed, not that an RR image was rendered. Any unexpected report, budget violation, process failure or unreviewed DLL makes RR unavailable.

- Memory reporting: accept only the exact known invalid total/aliasable pair below, with the expected 19,988,480-byte preflight estimate and 20,971,520-byte callback peak. Require six successful allocations, six releases, no callback errors/denials and zero remaining tracked bytes. Callback accounting substitutes for the invalid query; it does not measure total device residency or CPU/driver memory.
- Provider metadata: tolerate only error 6 with a zero returned ID after enumerating RR 1.2.0 and successfully creating with its explicit override (`requested_provider_id: 4311875584`). This records requested selection, not successful post-context metadata confirmation.
- Allocation failure: never recover inside the crashed SDK process. Disable that attempt and launch a fresh worker for a subsequent explicit attempt. The real second-heap rejection and subsequent fresh-context recovery are tested.

The native `--isolated-context` host loads no SDK and creates no GPU device itself. It launches its own executable suspended, assigns a one-process Windows job before resuming, and inherits only the two output pipes and NUL input. Each output stream is capped at 65,536 bytes. A configurable 1–60,000 ms deadline (default 30,000) or output overflow terminates the job; cleanup waits at most another five seconds. Job-handle closure kills the assigned child if the host exits. This follows Microsoft's [job-object lifecycle](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) and [process creation API](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).

The native envelope preserves child exit codes and raw output, including embedded NUL bytes. Native host exit 0 means a valid transport envelope, even if the child failed; only the managed policy interprets SDK readiness. JSON duplicate keys, nonfinite constants, excessive nesting and malformed reports are rejected. Validation remains active under `python -O`. Hash pinning assumes trusted local files; this is fault containment, not a hostile-code security sandbox or protection against GPU-driver failure.

`rr_worker_boundary` verifies success/failure transport, malformed/NUL output, crash codes, deadline, output flooding, host-exit cleanup, DLL rejection, report mutations, real SDK failure and recovery. Both it and `rr_probe_contract` pass in Debug and Release. The unchanged baseline renderer suite passes 9/9 in x64 Release. No persistent worker rendering, shared textures/fences, automatic game fallback or live-game integration is implemented yet. Keep the analytical renderer as the separate working path.

Evidence: `build/rr-sdk-probe/Debug/rr-worker-rs6ouxp8/verification.json` and `build/rr-sdk-probe/Release/rr-worker-lpujrfgh/verification.json`. These reports deliberately retain `raw_sdk_acceptance: failed` and include the raw SDK child envelopes.

## Raw context lifecycle evidence and remaining SDK failures

```powershell
.\build\rr-sdk-probe\Release\rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --context-test --cycles 3 --debug
python tests/verify_rr_context.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin
```

Both currently return failure for the SDK acceptance gate, even though creation/destruction succeed. Reports: `build/rr-sdk-probe/Debug/rr-context-djpapm3v/verification.json` and `build/rr-sdk-probe/Release/rr-context-krgbcajb/verification.json`. They include deliberate allocation-failure runs as well; use `--exercise-allocation-failure` on the Python command only when reproducing that crash is intended. These SDK diagnostics are **not** registered as passing CTest acceptance.

The bounded path selects the first enumerated provider through an override descriptor, enables SDK validation, fixes resolution at 128×96 and admits the pre-context estimate before creation. Resource and heap callbacks enforce a 64 MiB ceiling, adjustable downward with `--budget-mib 1..64`. Every committed-resource allocation is charged using D3D12 allocation information; every heap is charged in full. No heap aliasing discount is taken. This accounts for resources/heaps routed through the callbacks, not CPU allocations, PSO/driver overhead or residency.

Measured in both builds: three consecutive contexts each create two heaps and four resources, reach **20,971,520 bytes (20 MiB)** peak tracked allocation, and release all six objects with zero tracked bytes left. These context-only tests submit no application GPU work. The separate dispatch path fences its queue before context destruction.

The SDK leaves a non-null handle after successful destruction here. Our initial RAII wrapper destroyed it twice; it now clears ownership immediately after successful destruction, matching the [official denoiser sample](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Samples/Denoisers/FidelityFX_Denoiser/dx12/denoiserrendermodule.cpp). Callback effect identifiers use the backend namespace (observed 22), not the public effect mask value.

Unresolved behavior:

- Post-context memory query returns success but reports total `18446744073689694208` bytes and aliasable `65536`. The tool marks `sdk_memory_valid: false`; it never uses that invalid total for allocation arithmetic. A fixed-size `--sdk-allocator-control` reproduces the same anomaly without our callbacks. That diagnostic is preflight-only and explicitly reports `hard_budget_enforced: false`; it is not a production alternative to the bounded path.
- The general provider-version query on the created context returns parameter error 6. The creation override uses the enumerated ID, but post-context metadata confirmation remains unavailable in this test.
- `--fail-allocation 2` deliberately rejects the second heap. The provider proceeds to an invalid `CreatePlacedResource` call and the child terminates with exception `0x87d` under the standard debug layer, rather than returning a clean creation failure. A fresh process subsequently creates/destroys a normal context, but that does not qualify graceful recovery inside the failed process.

`--allocator-test` independently verifies resource limits, injected rejection, heap offset/size validation and release accounting without passing a failure into the SDK. These checks are included in the passing `rr_probe_contract` CTest. A 1 MiB context budget rejects at preflight, with no context attempt or allocation.

Expanded contract reports: `build/rr-sdk-probe/Debug/rr-probe-syw5t5pv/verification.json` and `build/rr-sdk-probe/Release/rr-probe-i9t79i5m/verification.json`. In context JSON, return-code value `4294967295` means that query/action was not attempted; use `create_attempted`, `created` and `destroyed` to interpret preflight rejection. The reported provider ID is zero when the post-context metadata query fails; it is not a replacement for the selected enumerated override ID.

Do not connect this experimental path to a game yet. The supervised boundary supplies process containment and documented accounting/metadata workarounds, without changing this raw diagnostic's failing result. Matched inputs, reset dispatch and bounded stationary history are implemented; general moving-camera history, live GPU interop and image-quality acceptance remain open. No driver update or SDK binary modification was attempted.

## Measured readiness

Provider: `4311875584`, `FSR Ray Regeneration - 1.2.0`. The explicit SM 6.6 check succeeds. The renderer's old `shader_model_tested: 101` only checked 6.5; it was not a hardware maximum.

Final probe reports: `build/rr-sdk-probe/Debug/rr-probe-h5simqj2/verification.json` and `build/rr-sdk-probe/Release/rr-probe-0mhmnub4/verification.json`. Both contract tests pass. The baseline renderer suite passes all nine entries in all four configurations; `build/x64-renderer/Release/temporal-flc8v06_/verification.json` confirms all 53 historical files remain byte-identical. Legacy D3D9 qualification was not rerun in this slice.

Indirect diffuse alone, without checkerboard or SDK debugging flags:

| Render size | Total internal bytes | Aliasable bytes | Persistent bytes |
|---|---:|---:|---:|
| 128 × 96 | 19,988,480 | 17,498,112 | 2,490,368 |
| 960 × 540 | 79,298,560 | 57,409,536 | 21,889,024 |
| 1920 × 1080 | 279,576,576 | 208,797,696 | 70,778,880 |

These are provider estimates, not measured residency or application totals. External textures, scene, presentation and allocation granularity are additional. Aliasable memory occupies space during dispatch; subtract it from peak accounting only after implementing and testing actual heap aliasing.

Our full-HD fixture already requests 497,682,288 bytes. Even RR's persistent allocation exceeds the remaining space below the unchanged 536,870,912-byte cap. Start at 128×96, then 960×540. Full HD needs reclaimed/replaced analytical-history storage, texture budgeting and potentially heap aliasing, not a silent cap increase.

AMD requires RX 9000-series or newer, Windows 11, DX12 and SM 6.6. RR denoises separately from upscaling. Requirements do not replace provider enumeration or a context/dispatch test. See the [official manual](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/).

## Input gaps

Update: a separate bounded 128×96 GPU preparation pass exports fresh indirect/distance, direct/emission and matched linear-light guides with numerical CPU checks. See [the input contract and tests](RR_INPUTS.md). These float32 diagnostic records are not themselves SDK textures; the separate [reset dispatch worker](RR_DISPATCH.md) now validates and packs them. The table distinguishes legacy inputs from the implemented research path.

Use the [pinned header](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/denoisers/include/ffx_denoiser.h), not older Input1/2/4 examples. Our current structured-buffer exports are not directly consumable RR textures.

| Required input | Current gap | First implementation |
|---|---|---|
| Fresh indirect diffuse and bounce distance | Legacy combined RGB; no distance alpha | Separate reset-frame SDK denoising and offline composition implemented. |
| Signed view-space depth | Legacy ray-distance depth | Prepared from the shared primary hit; negative Z tested. |
| Current-to-previous motion | Legacy XY pixel displacement only | Prepared UV/Z deltas; invalid projections and cuts tested. |
| Normal/roughness/material texture | Legacy XYZ normals and per-draw factors | Octahedral/roughness/type-0 records prepared and packed. |
| Diffuse albedo | Legacy literal captured colours | Opt-in per-texel/vertex linear conversion prepared, preserving defaults. |
| Camera matrices and jitter | Legacy combined matrices and independent ray jitter | Separate matrices exported; matched unjittered texel-centre rays. Global jitter remains open. |
| Typed textures and states | Root-addressed structured buffers | Bounded typed upload/readback, two fenced submissions and cleanup verified for reset dispatch. |

## Next implementation slices

The [read-only default-setting inspection](RR_DEFAULT_SETTINGS.md) queries six scalar defaults repeatedly around recorded dispatch without overrides. A separate [single-setting experiment path](RR_FILTER_SETTINGS.md) applies predefined stability/Gaussian presets with default admission, per-context configure evidence and tagged output. The [multi-seed textured/PBR comparison](RR_MULTI_SEED_SETTINGS.md) and [eight-frame history/reset experiment](RR_LONG_HISTORIES.md) show a consistent spatial/temporal tradeoff: lower stability restores spatial response but usually worsens temporal error even late and after context recreation. A [coherent coordinate-scale grid](RR_COORDINATE_SCALE.md) preserves camera/guide geometry across one-tenth/one/ten scene units; it changes results slightly but fixes no absolute quality gate. The renderer default remains unchanged.

1. **Context admission (supervised policy passes; raw SDK acceptance fails):** bounded 128×96 creation/destruction, strict callback accounting, pinned reporting workarounds and process-contained failure/recovery are verified. Keep those controls when implementing dispatch. Analytical fallback must not be labelled RR.
2. **Inputs (preparation and reset packing implemented):** fresh diffuse/distance and matched guides have a numerical oracle; worker packing has independent half-float hashes, strict invalid-input handling and separate budgets. Add bounded sequence provenance before non-reset dispatches. Do not fabricate specular data.
3. **Dispatch (offline recorded motion):** SDK output, offline direct/emissive composition, fences and crash recovery pass. A [2–8-frame stationary batch](RR_SEQUENCE.md) reuses one context and external allocation. [Source-verified recorded dispatch](RR_RECORDED_DISPATCH.md) adds actual translation/depth motion and fresh-context isolation at recorded resets, after the SDK reset flag alone failed strict equivalence. [Matched CPU quality measurements](RR_QUALITY.md) show lower error on one constant-colour diffuse fixture, but the new [textured/PBR and matched fallback measurements](RR_SURFACE_QUALITY.md) fail spatial gates. Those failures and the zero-light bias need investigation before resizing/async integration. RR history replaces our temporal filter on this path instead of unknowingly stacking both.
4. **Quality (zero-light gate failed):** investigate the small positive bias, then compare high-sample references across seeds, camera/lighting motion, disocclusions and glossy/emissive boundaries. Record error, ghosting, detail, GPU time and peak memory. Passing execution does not satisfy this gate.
5. **Expansion:** evaluate 960×540, upscaling and memory reuse; add direct/specular signals alongside actual specular transport. Radiance caching stays a separate path-tracing feature with a cache-off oracle. Retain analytical filtering for GPUs without RR.

## Custom filter: retained, not accepted

`--variance-filter` selects the experimental GI-only two-stage variant; `--denoise` keeps the original 5×5 filter. It uses luminance variance, surface rejection and reduced glossy-material support. Retired previous-history storage supplies scratch without new full-frame allocation. This is neither full SVGF nor AMD RR.

The first two single-pass designs failed. The two-stage candidate also failed: mean BGR8 MSE across seeds 1/7/23 is about 34.63 versus 34.26 for the old filter against a 256-sample reference. Lower is better. It reduces raw noise but misses the required 5% improvement over the old filter. Thresholds were not relaxed.

`tests/verify_variance.py` completes mechanics checks before returning failure for quality; it is deliberately not registered as passing CTest acceptance. Evidence: `build/x64-renderer/Debug/variance-bskfko08/verification.json` (`mechanics: pass`, `result: quality-gate-failed`). Checked CPU/GPU filter error is below 1.45e-6. Raw/history isolation, temporal counts, glossy/boundary cases, native control/reset parity and repeated full-HD output pass on this fixture.

Renderer JSON adds `denoiser` (`none`, `spatial`, `variance`) and `variance_dispatches`. Signal-format filter flags remain generic; keep JSON provenance with exports. The old filter remains the supported baseline.

Release replication in `build/x64-renderer/Release/variance-5fr36xe4/verification.json` has the same quality failure and passing mechanics. It is confirmation of the retained candidate, not a fourth tuning attempt.
