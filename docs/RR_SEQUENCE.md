# Stationary RR history

The optional SDK worker now supports a bounded offline sequence of **2–8 frames in one context**, reusing the same typed textures and staging resources. This establishes stationary temporal execution and reset isolation, not quality acceptance or a live renderer integration. The [zero-light bias and raw SDK reporting workarounds](RR_DISPATCH.md) remain unresolved.

## Prepare and run

Use the optional SDK build described in [the probe guide](RAY_REGENERATION.md). For a fixed 128×96 scene, export deterministic prefixes with the same renderer options and seed:

```powershell
.\build\rr-sdk-probe\Release\rrt_dxr.exe SCENE.rrscene --mode gi --samples 1 --sun-radius 0 --rr-inputs frame0.rrinputs --debug
.\build\rr-sdk-probe\Release\rrt_dxr.exe SCENE.rrscene --mode gi --samples 2 --sun-radius 0 --rr-inputs frame1.rrinputs --debug
python tools/rr_sequence.py pack --output NEW.rrseq frame0.rrinputs frame1.rrinputs
python tools/rr_sequence.py run --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input NEW.rrseq --output NEW.rrseqout
```

All output paths must be new. `pack` performs no GPU/SDK work. The renderer still exports only the final fresh sample of each prefix, not an averaged input or an SDK history. The worker supplies the actual persistent SDK history by dispatching those files in order. Do not enable our temporal/spatial filter as an RR input-processing stage.

Use the same source scene, materials, lighting and options across each segment. The diagnostic format does not carry a complete scene/settings identity, so matching visible guides is necessary but cannot prove identical occluded geometry or indirect illumination. Caller-controlled provenance is a limitation of this research format, not a general-purpose capture guarantee. Zero sun radius makes direct lighting deterministic for this first strict contract.

## Admission and resets

Native and Python readers check the outer sequence checksum and every inner input checksum before dispatch. The native worker validates the complete sequence before creating a device or loading the SDK.

- The first frame must be a reset with both frame and random index zero.
- A non-reset frame must increment both indices by one, retain its seed, and have exactly matching current camera matrices, direct/emission, material and geometry guides.
- Previous camera matrices must match the preceding stationary camera within the existing 0.0005 matrix tolerance. Active motion must be valid; stationary UV/Z residuals are bounded to 0.00001 and packed as supplied, not replaced with invented motion.
- A reset starts a new zero-indexed segment. It may change scene/settings and must carry reset-valid input guides. Missing reset, gaps, reorderings, changed stationary guides and unsupported motion are rejected.
- Total sequence length is 2–8, including all segments. Single-reset commands retain their prior contract.

Each dispatch receives its segment frame index and explicit reset flag. Camera delta and jitter remain zero. These fields follow the [pinned SDK API](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/denoisers/include/ffx_denoiser.h) and [AMD integration guide](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/).

## Bounded lifetime and evidence

One SDK context owns temporal history through the batch. The same six external textures and two staging buffers are reused only after their prior work completes. Every frame has an upload/readback fence and a dispatch/readback fence, byte-exact upload checks, unchanged input checks, independent half-float packing hashes and complete finite output validation. Poisoned output RGB is refreshed every frame; preserved distance alpha is explicitly initialized.

Tracked external allocation remains **1,900,544 bytes**, irrespective of sequence length. Eight resources release after context teardown. The SDK still reports six callback allocations/releases and a **20,971,520-byte** peak under its unchanged ceiling. Per-frame reports correctly show zero external releases while those resources remain owned; the final report must show eight releases. This is allocation accounting, not total residency or performance measurement.

All GPU work is fenced before reuse/teardown. An uncertain submitted-GPU lifetime terminates the isolated child. No output bundle is opened until every dispatch, context teardown and debug-layer check succeeds. Native host exit 0 is transport success only; managed success requires all per-frame reports, final cleanup and output checks. Raw SDK acceptance remains failed under the exact pinned workarounds. Job isolation does not guarantee GPU-driver recovery.

Tests compare repeated sequences byte-for-byte, replay identical segments after reset, compare the first frame against the single-reset path, and use the same final noisy sample with history discarded as a temporal-influence control. A lit-to-dark reset must match a separately started dark sequence. These checks demonstrate working history/reset semantics on the fixture, not reduced reconstruction error or freedom from ghosting.

## Binary contracts

Both formats are little-endian and require exact lengths; neither embeds filenames or accepts arbitrary frame sizes.

| Format | Header and payload | Maximum bytes |
|---|---|---:|
| `RRTRRS01` input | Magic; uint32 version 1, count, inner stride 1180040, reserved 0; count complete RRTRRI01 files; SHA-256 of all preceding bytes | 9,440,376 |
| `RRTRRT01` output | Magic; uint32 version 1, count, inner stride 196696, reserved 0; source bundle payload SHA-256 (32 bytes); count complete RRTRRO01 files; SHA-256 of all preceding bytes | 1,573,656 |

Each inner output still binds to its corresponding input digest. The outer digest additionally binds frame ordering and resets. Per-frame execution metadata stays in the managed JSON report. Retain it with the bundle. The formats provide integrity, not authentication or complete scene provenance.

## Verification and remaining gates

```powershell
cmake --build build/rr-sdk-probe --config Release --target rrt_rr_probe
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(probe_contract|worker_boundary|dispatch|sequence)$' --output-on-failure
```

`rr_sequence` is an execution test. Its report explicitly retains `quality_acceptance: failed-zero-light-oracle`: the first two zero-input frames have a maximum positive value of 1.0907649993896484e-5. Add `--require-zero-light` to `tests/verify_rr_sequence.py` with the required probe/SDK/renderer arguments to enforce the exact-zero oracle; it currently fails after recording execution evidence. No bias correction or relaxed threshold is applied.

Final SDK suites pass 4/4 in Debug and Release. Sequence evidence: `build/rr-sdk-probe/Debug/rr-sequence-h1u2u4h7/verification.json` and `build/rr-sdk-probe/Release/rr-sequence-wdl___wc/verification.json`. Each rejects 17 malformed sequences, 13 report mutations and five malformed outputs, verifies budget/crash recovery, and retains the failed zero-light quality result. Same-final-sample history ablation changes 38,037 payload bytes; no high-sample improvement claim follows from that difference.

The normal x64 Release renderer build and all 10 CTests also pass after this change. No renderer source/shader was changed. Other renderer configurations, legacy D3D9 suites and historical byte comparisons retain their prior evidence; they were not rerun in this worker-only slice.

Full optimized-Python sequence verification passes too: `build/rr-sdk-probe/Release/rr-sequence-cd7frnye/verification.json`. Validation uses explicit checks and remains active with `python -O`.

Follow-up: a [renderer-owned recorder](RR_RECORDING.md) supplies explicit source/settings identity, camera continuity and per-frame input checks. Its distinct RRTRRC01 format is now handled by a [separate recorded dispatch mode](RR_RECORDED_DISPATCH.md), not this stationary worker. Recorded resets use fresh contexts after motion-reset equivalence exposed residual differences. High-sample/disocclusion quality comparisons, animated objects, general lighting changes, resizing, live IPC, asynchronous interop, larger resolutions and default promotion remain open. No game installation or driver was changed.
