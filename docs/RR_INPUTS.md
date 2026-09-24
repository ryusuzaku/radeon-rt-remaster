# RR input preparation

`--rr-inputs NEW_FILE` runs an additional bounded GPU diagnostic after normal rendering. It prepares fresh inputs for later Ray Regeneration integration; **it does not call the SDK, allocate SDK textures, denoise an image or connect to a game**. The supervised SDK context policy and its reporting workarounds remain separate.

```powershell
.\build\x64-renderer\Release\rrt_dxr.exe SCENE.rrscene --mode gi --samples 8 --rr-inputs NEW.rrinputs --debug
python tools/inspect_rr_inputs.py NEW.rrinputs
ctest --preset renderer-release -R '^rr_inputs$' --output-on-failure
```

The scene must be 128×96 with an affine, orthonormal view matrix. This diagnostic is headless, uses the built-in shader, and refuses existing or colliding output paths. `--motion-test` (with `--signals`) and temporal move/cut/reset diagnostics can provide a previous camera. No previous RR texture/history is implied: only the final requested input frame is exported.

## Signal definitions

One unjittered primary ray at each texel centre (`x+0.5,y+0.5`) supplies every input. This deliberately differs from the legacy D3D9 integer-centre oracle. Lighting is freshly sampled at the recorded random index, not progressively or temporally averaged. Direct/emissive lighting is separated from the single diffuse bounce.

The opt-in preparation shader interprets captured 8-bit texture and vertex RGB as sRGB-encoded, decodes before texture filtering/vertex interpolation, and treats material factors, emission, light colour and ambient radiance as linear. This is an explicit authoring assumption, not proof of a captured game's original colour management. Legacy shading and exported pixels/signals remain unchanged, even when the additional diagnostic runs.

The per-pixel record has six float4 fields:

| Field | RGB / XYZ | A / W |
|---|---|---|
| `indirectDistance` | Fresh indirect diffuse radiance, including primary diffuse throughput | Bounce ray distance; 100000 for a secondary miss, -1 for inactive primary background |
| `directEmission` | Direct lighting plus emission; decoded clear colour for background | Primary hit: 1 or 0 |
| `normalRoughness` | Octahedral world-normal UV, linear roughness | Material type 0 |
| `diffuseAlbedo` | Linear base colour × (1 − metallic) | Diagnostic motion-valid bit, not an SDK albedo channel |
| `motionDepth` | Previous-minus-current UV and signed view-Z delta | Current signed view Z |
| `positionId` | World-space primary hit position | Draw index + 1, or 0 for background |

Default non-PBR materials use roughness 1 and metallic 0. PBR indirect transport remains diffuse-only; no specular signal is fabricated. The octahedral fold uses a nonzero sign at fold axes, including the negative-Z pole. First frames, cuts, explicit resets and lighting changes clear motion validity. Invalid previous projections produce zero motion and a false validity bit; finite offscreen motion is retained for future denoiser history rejection. Background has depth/normal/albedo/motion/position zero and indirect alpha -1.

Roughness is the unsquared authoring value, matching `material.perceptualRoughness` in [AMD's pinned sample](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Samples/Denoisers/FidelityFX_Denoiser/dx12/shaders/trace_rays_denoiser.hlsl), not the GGX alpha parameter used internally by our BRDF.

These conventions follow the [pinned SDK header](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/denoisers/include/ffx_denoiser.h) and [AMD's integration guide](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/). The [isolated reset dispatch](RR_DISPATCH.md) selects non-gamma albedo, UV motion scaling and matching unjittered matrices. Its explicit packing policy excludes diagnostic validity flags and clamps the 100000 distance sentinel to 65504; do not blindly cast these records to FP16 textures.

## File and memory contract

All fields are little-endian. The fixed-size file is 1,180,040 bytes:

1. Eight-byte magic `RRTRRI01`.
2. Eight uint32 values: version 1, width 128, height 96, stride 96, rendered frame index, random index, seed, reset flag.
3. Five float32 4×4 matrices: inverse view-projection, view, projection, previous view, previous view-projection. Storage is row-major; vectors multiply on the left.
4. 12,288 row-major records of 96 bytes each.
5. SHA-256 of all preceding bytes. This detects corruption, not malicious authorship.

The reader bounds file size before reading, checks header/checksum, rejects nonfinite values and invalid field combinations, and validates under optimized Python. The preparation pass requests two 1,179,648-byte buffers plus two 256-byte constant buffers: **2,359,808 additional requested bytes** within the unchanged 512 MiB budget. This is requested buffer accounting, not total residency. No extra buffers are allocated without `--rr-inputs`. GPU work is fenced before readback and local resource release.

Renderer JSON reports `rr_input_preparations: 1` and `rr_dispatches: 0`. Existing renderer timing fields exclude the additional preparation pass; they are not RR performance measurements.

## Verification and next gate

The independent CPU oracle traces scene triangles, samples decoded textures, evaluates direct BRDF/emission and the diffuse bounce, and checks positions, distances, normals, albedo, view depth and motion. Cases cover seeds/repetition, fresh versus accumulated samples, motion/cuts/resets, tilted surfaces, perspective, negative signed depth, invalid previous projection, scissor, bilinear colour decoding and PBR/emission. Secondary hits within 0.0001 barycentric distance of triangle edges are excluded from secondary-lighting comparisons to avoid ambiguous float32 ownership; primary coverage is still checked.

Tests also check unchanged legacy pixel/signal exports, exact additional allocation, unsupported camera/extent rejection, output preservation and ten corrupt files. All 15 cases pass in x86/x64 Debug/Release, including matrix round-trip and previous-camera consistency. Maximum normalized error including matrix checks is 1.54973e-6 against the unchanged 5e-4 limit. Final evidence: `verification.json` in the `rr-inputs-*` directory that
`ctest -R '^rr_inputs$'` creates in each of `build/x64-renderer/{Debug,Release}`
and `build/x86-vs/{Debug,Release}`. Directory suffixes are random per run, so the
artifacts are identified by name and by the test that regenerates them rather than
by paths that go stale on the next run. All nine baseline tests pass in each configuration, and the `verification.json` in the `temporal-*` directory created by `ctest -R '^dxr_temporal$'` under `build/x64-renderer/Release` matches 53 historical files byte-for-byte.

Follow-up: [budgeted typed textures and a fenced reset-only SDK dispatch](RR_DISPATCH.md), plus [bounded stationary history](RR_SEQUENCE.md), are implemented in the isolated worker. A separate [renderer-owned recording format](RR_RECORDING.md) now supplies source/settings provenance and camera continuity, without SDK admission. Execution tests pass, but the zero-light quality oracle fails slightly and no quality promotion is claimed. Next are actual SDK motion/cut tests and broader raw/high-sample comparisons. Live persistent-worker transport, animated-object motion, global camera jitter, advanced material classes and larger resolutions remain open. The existing denoiser quality gate is unchanged.
