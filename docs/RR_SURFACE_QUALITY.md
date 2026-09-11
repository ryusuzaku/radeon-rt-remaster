# Textured/PBR RR measurements and matched fallback

The opt-in surface reference extends [matched RR measurements](RR_QUALITY.md) to small textured and PBR fixtures. **The new fixtures fail RR spatial-quality gates.** This is useful negative evidence, not a denoiser fix or general qualification. The normal renderer, filter defaults and SDK binaries are unchanged.

## Supported scope

`--surface-reference` preserves the original reference's geometry, source-identity and work bounds: 128×96, 2–8 frames, at most 16 triangles/draws, 48 vertices/indices per draw, 64 KiB scene, fixed directional light and zero sun radius. It additionally supports:

- Textures up to 16×16, varying vertex colour, matched point or linear min/mag sampling, and wrap/mirror/clamp addressing. Texels and vertex colours are decoded from sRGB before interpolation. Border and anisotropic sampling reject.
- Optional original `.rrmat` sidecars, verified against the recording's whole-file identity and their own checksum. Entries must be sorted, unique, target known materials and obey the original base-colour, roughness, emission and metallic bounds; at most 16 entries.
- Independently traced primary barycentrics, texture/vertex/base colour, roughness and metallic-scaled diffuse albedo, checked against recorded guides. Diffuse throughput and secondary GGX/Smith/Schlick lighting follow the recorded estimator, with shadow rays and material emission. This is still one-bounce indirect diffuse, not primary specular reconstruction or general path tracing.

Emission prevents the zero-light analytic-black shortcut. The old strict reference remains the default and continues rejecting PBR and nonconstant surfaces. Reference batches retain independent PCG64 randomness; reproducing the GPU's sample directions is confined to estimator validation, not high-sample reference generation.

## Matched fallback comparison

`--fallback` applies a float64 CPU port of the default `presentationColor` spatial algorithm to exactly the same half-float indirect input supplied to RR. Its 5×5 Gaussian kernel preserves draw, normal, depth and albedo rejection, plus albedo demodulation/remodulation. It does not apply our temporal or experimental variance filter.

The legacy kernel's guides are **primary ray distance and base surface colour**, not RR view depth or metallic-scaled diffuse albedo. The port obtains those legacy-semantic guides by independently tracing the matched primary rays. It is not the legacy renderer's differently sampled/composited screenshot, GPU-bit-equivalent output or a runtime performance measurement. A hash of the reviewed `render.hlsl` source is pinned: changing that source requires reviewing the port before analysis can proceed.

JSON adds per-frame/region fallback MSE, RR-minus-fallback MSE, temporal residual and reference-noise diagnostics. NPZ additionally stores fallback RGB. The full-frame RR-versus-fallback gate and the reference-noise-versus-fallback gate remain separate: estimated reference-mean variance must be at most 1% of fallback MSE. No variance subtraction, output correction or threshold relaxation is applied.

## Run

With the optional SDK configuration and NumPy available:

```powershell
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_surfaces$' --output-on-failure
python tools/rr_quality.py --recording INPUT.rrcapture --output INPUT.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --execution EXECUTION.json --surface-reference --materials ORIGINAL.rrmat --fallback --samples 512 --report NEW-quality.json --reference NEW-reference.npz --require-gates
```

Omit `--materials` for recordings without a sidecar. Missing, unexpected or mismatched sidecars reject. Output paths must be distinct and new. Without `--require-gates`, exit 0 means measured, not accepted; with it, failed or unavailable diagnostic gates retain evidence and return 2. Malformed/unsupported inputs return 1. `quality_acceptance` stays `not-qualified` regardless of diagnostic results.

## Measured counterexamples

The bounded perspective fixture uses coloured 3×2 textures, varying vertex colours, out-of-range UVs and four frames translating 0.04 world units per frame. The texture-only case uses input seed 1; the PBR case uses seed 23 and two material overrides including emission. They are distinct cases, not a multi-seed comparison of the same scene.

At **2,048 reference samples per hit**, the final CLI measurement in `build/rr-sdk-probe/Release/rr-surfaces-xt5d6i3h/{texture,pbr}-quality-2048.json` gives these full-frame MSE ratios (larger than 1 is worse):

| Case | RR / noisy input, frames 0–3 | RR / matched CPU fallback, frames 0–3 |
|---|---|---|
| Texture | 21.11, 17.96, 16.14, 13.49 | 296.76, 251.70, 221.64, 175.16 |
| PBR | 23.53, 16.06, 11.71, 9.90 | 306.50, 214.45, 157.28, 144.50 |

Both cases fail spatial and revealed-region non-regression against noisy input, and spatial non-regression against the matched fallback. Their nearest-pixel temporal residual diagnostic is lower than raw noise; that does not rescue the spatial failure or establish ghosting quality. Reference variance passes the raw/disocclusion/temporal 1% diagnostics and is **0.66–0.75% of fallback MSE**, passing its separate 1% uncertainty target. Both CLI runs retain JSON/NPZ failure evidence and return 2 with `--require-gates`.

The earlier 1,024-total-sample reports in the same directory show the same large RR regression, but their reference variance is approximately 1.3–1.5% of fallback MSE and fails that stricter uncertainty diagnostic. Those reports remain intact. Doubling samples stays within the existing four-frame × 1,024-per-batch work limit; neither the limit nor the diagnostic threshold was changed.

CPU/GPU estimator disagreement is at most 1.10e-7 on these fixtures; independent scalar lighting agrees within the 1e-10 test threshold. Additional controls cover emission without ambient/sun, point-textured GPU inputs, texture seams and addressing, independently scalar fallback evaluation, all four fallback guide rejections, constant demodulated radiance, zero preservation, deterministic results and immutable input. These validate the measurement harness, not RR quality.

The initial low-sample `rr-surfaces-1ap_sjm3` used RR depth/albedo for the fallback before the legacy-guide audit. Its fallback metrics are superseded; do not cite those as the default algorithm. Its RR/raw comparison was unaffected. Raw SDK reporting acceptance and the separate exact-zero RR failure also remain failed.

## Verification

The optional Release SDK suite passes **7/7** (367.13 seconds). Final expanded surface evidence is `build/rr-sdk-probe/Release/rr-surfaces-1x1xqyi8/verification.json`; the full optimized-Python Debug run is `build/rr-sdk-probe/Debug/rr-surfaces-04wvhmhq/verification.json`. Each validates four actual GPU/SDK cases, 16 malformed/unsupported inputs and four isolated fallback guide controls. All four SDK output bundles, both numeric reference bundles and frame metrics match across configurations. These harness passes explicitly retain the quality failures.

CLI missing-sidecar rejection returns 1 without creating outputs; existing evidence cannot be overwritten. Python compilation, CLI help, CMake regeneration and local documentation links pass. The broader normal renderer, x86, legacy D3D9 and historical-image suites were not rerun in this tool-only slice; their previous results are not relabelled fresh.

## Next gate

The [analytic colour-response ablations](RR_COLOUR_RESPONSE.md) reproduce contrast loss without PBR, noisy sampling, occlusion or motion. The documented linear-albedo/radiance pairing matches our dispatch, but the internal cause remains unknown. Encoding and single-setting experiments are implemented; the [multi-seed stability comparison](RR_MULTI_SEED_SETTINGS.md) tests the same texture/PBR conditions under three independent renderer seeds. Longer histories and [coherent coordinate scale](RR_COORDINATE_SCALE.md) are also measured; neither fixes the failed gates. Resolution and light sampling remain separate hypotheses. Do not promote RR, change guide conventions speculatively, or integrate this path into a game on the basis of execution success.
