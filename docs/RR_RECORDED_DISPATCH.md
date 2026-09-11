# Recorded camera motion through AMD RR

The optional offline worker admits renderer-owned **2–8-frame recordings**, validates source identities and camera continuity, and dispatches the fresh indirect-diffuse signal through the pinned AMD RR SDK. This is execution research, not accepted reconstruction quality or live game integration. The [zero-light bias and SDK reporting defects](RR_DISPATCH.md) remain open.

## Run

Use the [optional SDK build](RAY_REGENERATION.md), then record and dispatch separately:

```powershell
.\build\rr-sdk-probe\Release\rrt_dxr.exe SCENE.rrscene --mode gi --samples 4 --rr-record NEW.rrcapture --rr-step 0.05 0 0 --debug
python tools/rr_recorded_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input NEW.rrcapture --output NEW.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(probe_contract|worker_boundary|dispatch|sequence|recorded_dispatch)$' --output-on-failure
```

All outputs must be new. A recording made with `--materials FILE.rrmat` requires the same sidecar passed to the managed dispatch command. Supplying a sidecar when none was recorded also rejects. Scene and preparation shader files are mandatory: their contents, not paths, must match the recording. The SDK DLLs retain their exact reviewed hash pins.

The renderer remains SDK-free. This command is explicitly separate from the older stationary bundle worker, which still rejects moving recordings. Fixed initial yaw/pitch and world-space translation are supported at 128×96; animated geometry, changing orientation/lighting, larger sizes, resizing and live IPC are not.

## Admission and motion

The native worker checks the complete bounded [RRTRRC01 recording](RR_RECORDING.md) before device or SDK startup. It verifies outer/settings/inner checksums, frame counts and indices, reset reasons, requested trajectory, rigid view matrices, camera displacement, previous matrices, projection continuity, per-pixel UV/depth reprojection and finite texture/depth ranges. Managed validation independently checks continuity and source files before launching the host; worker reports and output must bind to the originally read recording digest.

For active non-reset pixels, the previous projection must be valid. Finite offscreen UV motion is supported, but an invalid previous projection requires a recording reset; the worker does not invent valid motion. Motion components must fit half-float. Existing miss-distance packing alone clamps 100000 to 65504; output RGB is never clamped to hide a defect.

Camera delta is derived from the rigid view matrices as previous world-space eye position minus current eye position. UV and signed linear-depth motion use the same previous-minus-current convention, with unit scales. Reset camera delta is zero. SDK `frameIndex` is the segment index (0,1,0,1 across an explicit reset), while embedded input frame ordinals retain their recording-global indices. Jitter remains zero. These conventions follow the [pinned API header](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/denoisers/include/ffx_denoiser.h) and [AMD integration guide](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/).

Hashes establish integrity and source identity, not authentication or proof that arbitrary third-party pixels were actually rendered from those sources. Fixture recording tests separately trace geometry/lighting against a CPU oracle. The worker does not rerender a supplied scene to authenticate every sample.

## Reset issue and bounded workaround

The first moving-camera reset test found that the SDK reset flag alone did **not** produce exact fresh-context output: seven pixels differed by at most 0.00006103515625. Input identities matched and reset/index/camera delta were correct. Evidence is retained in `build/rr-sdk-probe/Debug/rr-recorded-dispatch-vvqmrm9j`: compare frame 2 of `reset.rrrecordout` with `reset.rrout`. This observation does not identify the SDK's internal cause.

Recorded resets now use **sequential context recreation**, not a relaxed equivalence tolerance. The previous segment completes all GPU work, then destroys its SDK context before the next is created. Every segment still starts with the SDK reset flag and frame index zero. Continuous segments reuse a single context, preserving actual temporal history. The recorded JSON contract requires `reset_policy: recreate-context` and validates one complete lifecycle per segment. The older stationary worker and its existing reset tests remain unchanged.

The six external textures and two staging buffers are reused across all segments: tracked allocation stays **1,900,544 bytes**, with eight final releases. Each SDK context retains six callback allocations/releases, **20,971,520 bytes** peak and zero live tracked bytes after destroy. Contexts never overlap. The limits remain 64 MiB SDK callbacks and 8 MiB external allocation; these are tracked allocations, not total driver residency. Context recreation adds offline overhead and is not a real-time performance solution.

Each frame still uses two fences, independently checked packing hashes, unchanged-input verification and complete finite output checks. Poisoned RGB detects unwritten pixels; distance alpha is initialized and must remain unchanged. No bundle is published until all frames, context teardown and debug checks succeed. Process isolation retains the existing deadline, output caps and kill-on-close job; it cannot guarantee recovery from a GPU-driver failure.

## Output and acceptance

`RRTRRD01` is a distinct little-endian recording-output format. Header: eight-byte magic followed by four uint32 values (version 1, frame count, inner stride 196696, reserved zero), the 32-byte source recording payload digest, the complete per-frame RRTRRO01 outputs, then a 32-byte SHA-256 of all preceding bytes. Maximum size is **1,573,656 bytes**. Inner and outer hashes bind input identity, ordering and reset metadata. The older RRTRRT01 output is not accepted here.

This remains the default linear-albedo output. The opt-in [paired encoding experiment](RR_ALBEDO_ENCODING.md) adds recorded-only `--albedo-encoding sqrt`, with verified packing/dispatch metadata and a distinct `RRTRRD02` output tag. Readers and quality analysis require the matching explicit encoding; ordinary linear calls reject nondefault output. Canonical recordings, reset lifetimes and resource limits are unchanged.

Recorded-only `--query-defaults` adds [read-only live-context scalar-setting inspection](RR_DEFAULT_SETTINGS.md). It preserves raw query codes/bytes and repeated before/after snapshots, never configures a setting and does not change the output format. Inspection and image-quality acceptance remain separate from execution.

Recorded-only `--filter-setting PRESET` adds a separate [one-key override experiment](RR_FILTER_SETTINGS.md), implies default inspection and publishes preset-tagged `RRTRRD03` output. Readers require the exact preset and encoding; no override is applied by ordinary calls.

Recorded-only `--coordinate-scale unit-tenth|unit-one|unit-ten` adds the [coherent scene-unit experiment](RR_COORDINATE_SCALE.md). It publishes `RRTRRD04` output carrying scale, optional filter-setting and encoding provenance. It transforms every length-bearing SDK guide plus the matching view/projection matrices; ordinary calls and source recordings remain unchanged.

The managed report says `recording-executed-with-workarounds` only after reports and output agree. `raw_sdk_acceptance` remains `failed`; `quality_acceptance` remains `not-evaluated`. Retain JSON evidence alongside the input/output bundles. An isolated host exit of zero alone never means success.

Tests cover stationary compatibility, moving/rotated-depth inputs, deterministic replay, reset-to-fresh equivalence, automatic cuts, eight frames/segments, material identity, source mismatch before host launch, malformed records/reports/outputs, budget rejection and fresh-worker recovery after the injected SDK crash. Nearest-neighbour prior draw-ID mismatch/offscreen reprojection counts provide visibility-change coverage only: they are not a full disocclusion oracle or proof of ghost-free output.

Debug and Release optional SDK suites pass **5/5**. Final Release evidence is `build/rr-sdk-probe/Release/rr-recorded-dispatch-pq85bdel/verification.json`: 18 rejected report mutations, 23 malformed recordings, five damaged outputs and five pre-launch source failures. Eight automatic cuts create/destroy eight sequential contexts, each with the unchanged 20 MiB callback peak; all outputs match independent fresh-context controls. The injected SDK failure exits with code 2173 and its child is reaped; a fresh worker reproduces the original moving output. Visibility-change counts are 6,14,25 across the moving fixture. Existing stationary tests still explicitly retain `failed-zero-light-oracle`.

The full final test also passes under `python -O` with the Debug worker: `build/rr-sdk-probe/Debug/rr-recorded-dispatch-wpqr2gu0/verification.json`, including all the rejection counts above. Eight complete output bundles match Debug/Release byte-for-byte on this GPU. Validation remains active with Python assertions disabled; this is not cross-GPU qualification.

The SDK-free Release renderer rebuild and input/recording compatibility subset pass **2/2**. No renderer/shader source changed in this slice. Other renderer tests, x86, legacy D3D9 and historical 53-file comparisons were not rerun; their earlier evidence is not relabelled current.

Follow-up: [independent matched-hit CPU references and geometric visibility/error measurements](RR_QUALITY.md) now cover a small constant-colour diffuse perspective fixture. It improves over noisy input in those measurements, but the exact-zero bias remains and textured/PBR coverage, fallback comparison and longer ghosting tests are still open. No default-filter promotion, full RR feature set, specular input, driver modification or installed-game change is claimed.
