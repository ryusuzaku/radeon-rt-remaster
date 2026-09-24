# Renderer-owned RR input recording

The renderer can capture **2–8 fresh RR input frames in one scene lifetime**, with explicit source/settings identity, translation, automatic camera cuts and requested resets. Recording itself performs no SDK denoising. A separate [recorded dispatch command](RR_RECORDED_DISPATCH.md) now admits these files; the old stationary worker still rejects them. Default rendering and shader estimators are unchanged, and image quality is not accepted.

## Use

```powershell
.\build\x64-renderer\Release\rrt_dxr.exe SCENE.rrscene --mode gi --samples 4 --rr-record NEW.rrcapture --rr-step 0.05 0 0 --debug
python tools/inspect_rr_record.py NEW.rrcapture --scene SCENE.rrscene --shader build/x64-renderer/Release/rrt_rr_inputs.dxil
ctest --preset renderer-release -R '^rr_record$' --output-on-failure
```

Use `--materials FILE.rrmat` when rendering and `--materials FILE.rrmat` when inspecting to verify the recorded sidecar identity. Inspection without source arguments validates internal structure/continuity but does not verify external source files; `verified_sources` lists only files actually checked. Hashes provide integrity and identity, not authentication or proof that an arbitrary third-party recording is truthful.

Requirements: a 128×96 scene, built-in shaders, headless unfiltered GI, no temporal filter or other camera/history diagnostics. `--samples` is the recording frame count (2–8). `--rr-inputs` and `--rr-record` are mutually exclusive. Outputs must be new; pixel/signal/recording output collisions are rejected before rendering.

`--rr-step X Y Z` applies an absolute world-space translation per frame from the starting `--camera-offset`, with each step component in -2..2. Initial yaw/pitch are supported but remain fixed throughout the recording. Omit the step for a stationary sequence. A per-frame translation longer than one unit causes the existing automatic camera-cut reset. `--rr-reset-frame N` requests an additional reset at zero-based frame index N (1..7, inside the chosen count). For example, four frames with reset index 2 have random indices 0,1,0,1.

## What is bound to the recording

- **Scene:** the payload SHA-256 returned from the exact bytes successfully validated by the scene loader. This covers the full source, including offscreen geometry, textures and captured state. The file is not reread later to guess what was loaded. Scene serialization itself is unchanged.
- **Materials:** SHA-256 of the complete sidecar bytes already loaded, or 32 zero bytes when no sidecar was used.
- **Preparation shader:** SHA-256 of the actual DXIL loaded for preparation. Every frame must use the same hash; a mid-recording shader change rejects publication.
- **Settings:** canonical mode, seed, shadow flag, requested reset index, light vector/colour/intensity, ambient, sun radius, initial camera offset/yaw/pitch and translation step. No padding, timestamps or filenames enter the settings hash.
- **Frames:** ordinal, segment index, reset reason and requested pose, followed by the original independently checksummed RRTRRI01 input. One outer checksum binds identities, ordering and all frames.

The format version fixes the preparation conventions. Future changes to those conventions need an explicit version review; dependency hashes alone are not a build-reproducibility guarantee. There is no dynamic scene or lighting mutation during this recorder's lifetime.

## Sampling, camera and GPU lifetime

Each frame renders and then runs the separate matched-input preparation pass before the camera advances. That pass still provides fresh indirect/distance and matched direct/material/depth/motion guides from one unjittered primary hit. It does not denoise or average inputs.

For recording only, the preparation pass uses the renderer's continuous random sequence, restarting it at cuts/resets. This matters because the legacy non-temporal image sample index restarts whenever the camera moves. Existing single-input exports retain their prior sampling convention; stationary recorder frames match those prefix exports exactly. A moving recording's fresh RR sample should not be equated to the legacy image's accumulated radiance.

The independent reader checks frame/reset indices, requested translation, fixed projection, inverse-camera consistency, previous-camera continuity and per-pixel motion/depth reprojection using the existing 0.0005 numerical tolerance. CPU fixture tests independently trace geometry and lighting as well; internal checks alone cannot establish scene semantics without source evidence.

Preparation drains and fences work before reading back. Its temporary resources are destroyed after each frame; only then does recording retire the known 2,359,808-byte buffer charge. The fixture's requested peak is **5,327,216 bytes** for both four and eight frames, with final requested accounting restored to 2,967,408 bytes. This is requested-buffer accounting, not allocation-info residency. Pipelines are currently recreated per preparation; this is an offline correctness path, not a performance implementation.

The recording remains in bounded CPU memory and its create-new output is opened only after all frames complete. Optional final pixels/signals retain their existing output semantics. Renderer JSON reports `rr_recorded_frames`, `rr_input_preparations` and `rr_dispatches: 0`; `samples` remains the legacy final-view accumulation count, while `dispatches` counts all recorded frames. Timings include recording overhead where previously defined as wall time; none are RR SDK performance measurements.

## RRTRRC01 binary layout

Little-endian, exact-length, maximum **9,440,876 bytes**:

| Offset | Content |
|---:|---|
| 0 | Eight-byte magic RRTRRC01 |
| 8 | Four uint32: version 1, frame count, inner stride 1180040, settings size 84 |
| 24 | Scene payload SHA-256 (32 bytes) |
| 56 | Full material-file SHA-256 (32 bytes; zero if absent) |
| 88 | Preparation DXIL SHA-256 (32 bytes) |
| 120 | Four uint32: mode 3, seed, shadows, reset index (UINT32_MAX means none) |
| 136 | Seventeen float32: light XYZ, light RGB, intensity, ambient, radius, initial offset XYZ, yaw, pitch, step XYZ |
| 204 | SHA-256 over the 84 settings bytes |
| 236 | Repeated frames: four uint32 (ordinal, segment index, reset-reason bits, reserved zero), five float32 requested pose values (camera offset XYZ/yaw/pitch), then complete RRTRRI01 |
| End−32 | SHA-256 over all preceding recording bytes |

Reset bits: 1 initial frame, 2 explicit request, 4 automatic translation cut; reasons can combine. The embedded frame index is the global ordinal, while its random index and outer segment index restart at reset. This intentionally differs from the old manually packed stationary bundle's reset-start indexing. Do not re-label or strip the recording header to bypass worker admission.

## Verification

Verification covers ten cases: stationary/repeated/eight-frame capture, translation, rotated depth motion, explicit reset, automatic cuts and source/material/settings identity changes. Stationary embedded inputs equal legacy exports byte-for-byte. Offscreen geometry changes the scene identity while leaving first-frame visible input records identical. The independent geometry/lighting oracle checks moving and reset frames. Corruption tests reject 21 malformed recordings; admission tests reject unsupported modes, overwrites and case-insensitive output collisions.

Both full x64 renderer suites pass 11/11; x86 Debug and Release each pass the input/recording subset 2/2. Stationary, translated and rotated-depth recording files are byte-identical across all four configurations. This is fixture reproducibility on the same GPU, not cross-GPU qualification. The legacy D3D9 suites and historical 53-file comparison were not rerun in this slice.

Final recorder reports: x64 Debug `rr-record-88to_qyf` (full optimized-Python verification), x64 Release `rr-record-17r75bt1`, x86 Debug `rr-record-9_51djnp`, x86 Release `rr-record-qeivvsju`, under their respective build configuration directories. Each contains `verification.json`; final optimized/x86 runs include all 21 malformed-file and ten invalid-mode/path checks. Release SDK compatibility also passes 4/4, with its existing raw-report and zero-light quality failures still explicitly reported. These results do not admit moving recordings to the SDK.

## Remaining gates

Native/managed admission and moving-camera execution are implemented separately in [recorded dispatch](RR_RECORDED_DISPATCH.md), including a fresh-context workaround for recorded resets. Compare high-sample references, establish geometric disocclusion/ghosting quality tests and investigate the existing zero-light bias before quality acceptance. Animated objects, general scripted rotations/lighting, live IPC and larger resolutions remain open. No SDK dispatch, driver or installed-game modification is part of recording itself.
