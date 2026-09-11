# Matched RR quality measurements

The offline quality tool compares recorded AMD RR output against an **independent full-frame CPU Monte Carlo reference** at the exact recorded half-pixel primary rays. It does not reuse the renderer's differently sampled preview image. It measures indirect RGB only, not tonemapped screenshots, direct lighting, specular reconstruction or a complete path tracer.

The first constant-colour perspective fixture shows substantially lower RR error than noisy input, including newly revealed surfaces. **General quality acceptance remains `not-qualified`: the exact-zero test still fails, and the fixture/material coverage is deliberately narrow.** The original results below do not compare against the fallback blur. The new opt-in [textured/PBR reference and matched fallback comparison](RR_SURFACE_QUALITY.md) exposes substantial spatial regressions, so the initial positive result does not generalize.

## Scope and method

- Default strict mode: 128×96, 2–8 recorded frames, at most 16 triangles/draws and a 64 KiB source scene; each draw has at most 48 vertices/indices. Static geometry with constant vertex colour, one-texel textures and affine world transforms. Material sidecars/PBR, border sampling and nonzero sun radius reject. Fixed directional light, recorded light colour/intensity, shadows and ambient are supported. Explicit `--surface-reference` extends only the documented surface subset; it does not relax geometry or work limits.
- A separate NumPy float64 triangle tracer computes primary positions, IDs, normals and linear-sRGB albedo, checks them against the recorded guides, then traces cosine-weighted diffuse bounces and secondary shadow rays. No SDK or renderer is loaded during reference calculation.
- Two separate PCG64 streams use an explicit reference seed, frame, replicate and pixel-chunk identity. These are independent of the renderer's hash RNG; the validation test alone reproduces renderer sample directions to cross-check the estimator. Default: **512 samples per batch, 1,024 total per active pixel**.
- Numeric-only NPZ evidence stores means, estimated mean variances, independent-batch differences, primary draw IDs, visibility masks and recording identity. JSON binds the source scene/shader/settings, candidate output, execution report, reference file and analysis implementation hashes. This provides identity/integrity, not authentication of an arbitrary third-party report.
- The comparison baseline is the half-float-packed noisy indirect input actually supplied to the SDK. Output is validated against its input identity, preserved alpha, finite RGB, recorded dispatch report and changed-pixel counts before measurement.

Chunk sizes are fixed at 256 primary pixels × 64 samples. Supported samples per batch: 64,128,256,512,1024; frame count times samples per batch must not exceed 4096. Primary, reference and candidate arrays remain bounded. This is an offline CPU reference; its timings are not renderer or RR performance measurements.

The variance diagnostic requires estimated reference-mean variance to be at most 1% of raw-input MSE, separately for the full image, revealed surfaces and temporal residuals. Independent-batch differences are also reported. This is a convergence diagnostic, **not a formal confidence interval or proof of exact ground truth**; Monte Carlo reference noise contributes to measured error, and no error-floor subtraction is silently applied.

## Visibility and temporal metrics

For every active non-reset point, project its independently traced world position into the previous camera and trace the **exact previous-camera ray**. Compare first-hit identity and position. This separates actual geometry-hidden points from points previously outside the screen.

| Mask | Meaning |
|---|---|
| `disoccluded` | Previously inside the screen but hidden along the exact prior ray |
| `offscreen` | Outside the prior camera's screen region or D3D near/far clip range |
| `stable` | Visible along the prior ray and compatible with the nearest previous pixel's draw, plane and normal |
| `unmatched` | Geometrically visible, but nearest-pixel guides are incompatible |

These masks partition active non-reset pixels. Reset frames have no temporal masks. Stable temporal residual is the change in `(image − per-frame reference)` at the nearest compatible previous pixel. It discounts expected reference-image changes, but nearest-neighbour resampling is still approximate: this is a diagnostic, not a complete ghosting/perceptual oracle. Newly revealed pixels are assessed spatially against their new reference, not borrowed history.

## Run

NumPy is optional and isolated from normal renderer/SDK code:

```powershell
python -m pip install -r tools/requirements-rr-quality.txt
cmake --build build/rr-sdk-probe --config Release
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_quality$' --output-on-failure
```

The optional SDK CMake configuration adds `rr_quality` only when its selected Python can import NumPy; otherwise configuration explicitly says the test was omitted. Reconfigure after installing the dependency. The validated local dependency is NumPy 1.26.4 on Python 3.12.

For existing source-verified recordings and outputs, retain the JSON returned by `tools/rr_recorded_dispatch.py` as the execution report, then run:

```powershell
python tools/rr_quality.py --recording INPUT.rrcapture --output INPUT.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --execution EXECUTION.json --samples 512 --report NEW-quality.json --reference NEW-reference.npz
```

Both destinations must be distinct new files. Exit 0 means analysis completed, **not quality accepted**. `--require-gates` saves the evidence and returns 2 unless every narrow diagnostic gate is true; absent coverage (`null`) is not a pass. Invalid inputs/destinations return 1. Even a successful narrow gate run retains `quality_acceptance: not-qualified` and the known raw SDK reporting failure.

## Initial results

Fixture: three opaque constant-colour triangles, four perspective-camera positions spaced 0.04 units apart, fixed white directional light, one-bounce diffuse. At 1,024 reference samples per hit:

| Frame | Raw MSE | RR MSE | RR/raw error | Newly revealed pixels |
|---:|---:|---:|---:|---:|
| 0 | 5.58715e-5 | 4.55248e-7 | 0.00815 | — |
| 1 | 5.32471e-5 | 4.90415e-7 | 0.00921 | 431 |
| 2 | 5.13650e-5 | 1.90808e-6 | 0.03715 | 431 |
| 3 | 5.83468e-5 | 1.11807e-6 | 0.01916 | 431 |

That is roughly **96.3–99.2% lower per-frame MSE** on this fixture only. Revealed-region RR/raw MSE ratios are 0.0173,0.0174,0.0206; stable temporal-residual ratios are 0.00249,0.01013,0.01002. Estimated full-frame reference noise is about 0.093–0.107% of raw MSE. The earlier 512-total-sample run gives the same qualitative conclusion. Do not infer textured/PBR/game-scene quality or superiority over the fallback filter from these results.

Initial expanded evidence: `build/rr-sdk-probe/Release/rr-quality-sjgynid6/quality.json`, `reference.npz`, `black-quality.json` and `verification.json`. CPU/GPU single-sample maximum absolute disagreement is 7.4908071e-8; the independently implemented scalar sample check agrees exactly, and 386 scalar visibility checks agree. An isolated ambient-lit plane has the analytic constant result; a deliberately injected 0.25 trail yields the expected 0.0625 MSE in revealed regions. These control checks validate the harness, not production quality.

The black perspective fixture has an exactly zero analytic reference but nonzero actual RR output: maximum **1.0967254638671875e-5**. The known bias is not clamped, subtracted or hidden by an epsilon. Its quality gate fails and its report is retained even when the harness CTest passes.

The optional Release SDK regression passes **6/6**. The full final quality test also passes with the Debug worker under `python -O`: `build/rr-sdk-probe/Debug/rr-quality-anz2918z/verification.json`. This includes 12 unsupported/corrupt-input rejections, 386 independent scalar visibility checks, two near/far-frustum controls, reference determinism/convergence and numeric-only round-trip checks, plus CLI failure-evidence retention and overwrite refusal. No validation is disabled by Python optimization.

Final hardened Release quality evidence: `build/rr-sdk-probe/Release/rr-quality-uvvuebjr/verification.json` (42.79-second CTest). All reference arrays and numerical metrics match the optimized Debug run exactly. The normal renderer, x86, legacy D3D9 and historical-output suites were not rerun in this tool-only slice; no prior results are relabelled fresh.

## Remaining gates

The textured/PBR reference and matched fallback comparison are now implemented; their [failed spatial gates](RR_SURFACE_QUALITY.md) require isolated colour/albedo/signal-convention investigation next. Broaden to soft lights, stronger depth/normal discontinuities, more motion and multiple noise seeds; assess spatial detail loss and longer-lived ghosting. Investigate the zero-light floor separately. This work changes no renderer shader, SDK binary, driver or installed game, and does not promote RR as the default filter.
