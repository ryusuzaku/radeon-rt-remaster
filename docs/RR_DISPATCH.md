# Isolated Ray Regeneration dispatch

Status (2026-09-03): the first real 128×96 reset-frame indirect-diffuse RR dispatch executes on this RX 9070 XT. Execution and containment tests pass; **image quality is not accepted**. The strict zero-light oracle fails slightly, and raw SDK reporting still fails under the separately documented [pinned reporting workarounds](RAY_REGENERATION.md). The default renderer/filter is unchanged.

## Reproduce

Use the optional SDK configuration in [the probe guide](RAY_REGENERATION.md), then build both the probe and renderer:

```powershell
cmake --build build/rr-sdk-probe --config Release
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(probe_contract|worker_boundary|dispatch)$' --output-on-failure
python tools/rr_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input RESET.rrinputs --output NEW.rrout --preview NEW.png
```

Generate `RESET.rrinputs` from a 128×96 scene with the renderer's `--mode gi --samples 1 --rr-inputs RESET.rrinputs` options; see [input preparation](RR_INPUTS.md). All output paths must be new. The managed command resolves absolute paths and validates both pinned DLL hashes before launch. Its success status is `dispatch-executed-with-workarounds`, not raw SDK or quality acceptance. Generic runs report `quality_acceptance: not-evaluated`.

The native entry point is `rrt_rr_probe --sdk-bin ABS_DIR --isolated-dispatch --input ABS_INPUT --output ABS_NEW_OUTPUT --debug`. Host exit 0 means valid process transport; the child still reports exit 1 and `validation-failed` for the exact known post-context SDK reporting failures. Never interpret the host exit alone as dispatch success. Unexpected reports, failures or unreviewed DLLs make managed RR unavailable.

## Signal packing and lifetime

The worker validates the bounded, checksummed input before creating a device or loading the SDK. It accepts reset frames only: a fresh process has no preceding SDK history. Five matched inputs and a separate output are uploaded as typed textures:

| Texture | Format | Content |
|---|---|---|
| Depth | R32_FLOAT | Signed view-space Z |
| Motion | R16G16B16A16_FLOAT | Zero UV/Z motion on reset |
| Normal/material | R16G16B16A16_FLOAT | Octahedral normal, roughness, material type zero |
| Diffuse albedo | R16G16B16A16_FLOAT | Linear diffuse RGB; alpha zero, excluding diagnostic validity |
| Indirect diffuse | R16G16B16A16_FLOAT | Fresh RGB radiance and secondary hit distance |
| Output | R16G16B16A16_FLOAT | RR RGB; preserved alpha initialized from packed distance |

Only the 100000 distance sentinel is clamped to the largest finite half value, 65504; inactive -1 is retained. Out-of-range RGB is rejected, not clamped. Output RGB starts at a negative poison value to detect missing writes. Initial testing found that output alpha retained its poison: the SDK contract says this channel is preserved, so alpha is now seeded explicitly. No output bias correction is applied. Conventions follow [AMD's integration guide](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/) and the [pinned DX12 sample](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Samples/Denoisers/FidelityFX_Denoiser/dx12/denoiserrendermodule.cpp).

The dispatch uses non-gamma albedo, reset, frame index zero, unit UV motion scale, zero jitter/camera delta, and the exported row-major view/projection matrices. This path does not stack our temporal or spatial filter over RR.

There are two fenced submissions: upload/readback verification, then SDK dispatch and readback. All six uploads must match byte-for-byte; all five inputs must remain unchanged after dispatch. Every output RGB must be finite/nonnegative and alpha must equal its initialized half value. Independent Python packing hashes cover all six textures. Context destruction and external releases happen only after completed GPU work; an uncertain post-submit wait terminates the isolated process instead of unwinding resources with unknown GPU lifetime.

External textures and staging use an independent maximum 8 MiB allocation-info budget, adjustable downward. Measured total is 1,900,544 bytes across eight resources (six textures plus upload/readback), all explicitly released. SDK callback peak remains 20,971,520 bytes with six allocations/releases under its separate 64 MiB ceiling. Combined tracked allocation is 22,872,064 bytes; this excludes scene preparation, CPU/driver overhead and is not residency measurement. Process containment is not a hostile-code sandbox or a GPU-driver recovery guarantee.

## Output and evidence

`RRTRRO01` is exactly 196,696 bytes: eight magic bytes, four little-endian uint32 values (version 1, width 128, height 96, pixel stride 16), the source input payload's 32-byte SHA-256, 128×96 float32 RGBA pixels decoded from SDK half output, and a final 32-byte SHA-256 over all preceding output bytes. Creation refuses existing files.

The optional preview shows raw indirect plus direct/emission on the left and RR indirect plus the same direct/emission on the right, with shared exposure 1 and sRGB display conversion. It is a single-frame research view, not antialiasing, full path tracing or evidence of a quality win.

Final execution reports:

- Debug, including optimized Python: `build/rr-sdk-probe/Debug/rr-dispatch-_ol2jef3/verification.json`.
- Release: `build/rr-sdk-probe/Release/rr-dispatch-ajfh25q9/verification.json`.
- Each covers 11 cases, 18 rejected report mutations, nine rejected malformed inputs and six rejected malformed outputs. Reset repeats and fresh-worker recovery after the injected SDK allocation crash are byte-identical. Budget rejection, overwrite protection and missing-history rejection pass.
- Optional SDK CTests pass 3/3 in Debug and Release. The normal x64 Release renderer suite passes 10/10. Other renderer configurations and historical byte comparisons retain their prior input-preparation evidence; they were not rerun in this dispatch-only slice.

The zero-light fixture produces a maximum positive RGB value of **1.0907649993896484e-5**, with MSE **9.602695114768744e-11** against exact zero, reproduced in Debug and Release. Reports explicitly contain `quality_acceptance: failed-zero-light-oracle`. The ordinary `rr_dispatch` CTest qualifies execution only. Run `tests/verify_rr_dispatch.py` with its required `--probe`, `--sdk-bin`, `--dxr` paths and `--require-zero-light` to enforce the separate exact-zero quality gate; it currently fails after saving execution evidence. Do not remove the failure, relax it silently, or promote RR based on passing execution tests.

## Next gates

A [bounded stationary sequence](RR_SEQUENCE.md) now reuses one SDK context and the same textures across 2–8 frames, with tested history influence and reset isolation. [Renderer-owned recording](RR_RECORDING.md) adds source/settings provenance and camera continuity without yet admitting those recordings to the SDK. Next implement that admission and actual motion/cut/disocclusion dispatches. Investigate the zero-light bias and compare high-sample references across seeds, lighting and material boundaries before quality acceptance. Performance, asynchronous interop, larger resolutions, animated geometry and live game integration remain open. No installed game, driver or default renderer path was changed.
