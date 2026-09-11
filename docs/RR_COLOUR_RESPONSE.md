# RR analytic colour-response isolation

The [textured/PBR quality regression](RR_SURFACE_QUALITY.md) now has a smaller reproducer: a stationary, viewport-filling plane under constant ambient illumination. No PBR, occluder, direct light or noisy indirect sampling is needed to reproduce substantial spatial contrast loss. **This identifies a failing behavior, not the internal SDK cause or a fix.** Renderer defaults and the pinned SDK remain unchanged.

## Contract audit

The pinned SDK header (`Kits/FidelityFX/denoisers/include/ffx_denoiser.h`) describes indirect diffuse input and output as radiance, and supports linear diffuse albedo with `FFX_DENOISER_DISPATCH_NON_GAMMA_ALBEDO`. Our existing packing and dispatch use that pairing. The [AMD Ray Regeneration 1.2 manual](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/) documents the same convention. This audit does not prove that every aspect of our integration or the SDK implementation is correct.

The earlier textured recording's mean output RGB closely matches its reference despite high per-pixel error. Diagnostic multiplication/division by albedo and swapping red/blue increase its MSE. A simple global colour multiplier or channel swap therefore does not explain the observed regression. Those exploratory calculations did not modify stored SDK output.

## Analytic experiment

`tests/verify_rr_color_response.py` generates its own bounded, source-verified recordings. A single non-PBR plane fills the 128×96 viewport; the camera is stationary and direct-light intensity is zero. Every recorded secondary ray must miss. The expected indirect signal is therefore **independently traced linear base colour × recorded ambient**. It depends on the primary surface colour but not on the sampled bounce direction.

The test requires unchanged geometry, depth, normals and roughness across cases, exact full-viewport coverage, source identities, validated SDK execution and independently matched primary colour. It also compares the existing two-batch Monte Carlo reference to the analytic image. A tiny cancellation residue can remain in the variance estimator even for constant integrands; a float64 accumulation-roundoff bound is used for this test-only numerical check. It is not subtracted from candidate error or used to loosen RR gates.

| Control | Variable changed |
|---|---|
| White, grey, dark, constant colour | Uniform one-texel surface colour |
| Vertex | Varying vertex colour; white texture |
| Linear | Coloured 3×2 texture with linear sampling; white vertices |
| Point | Same texture/UVs, point sampling only |
| Black | White plane, ambient set to zero |
| Equivalent colour vertex | Move the same uniform colour from texture to vertices |
| Linear seed | Change input RNG seed from 1 to 23; radiance should not change |
| Linear history | Extend the same stationary linear-texture recording to eight frames |

The final three comparisons require identical packed SDK input prefixes and identical corresponding output RGB/alpha. All runs preserve the existing 64 MiB SDK / 8 MiB external allocation caps, source verification and supervised worker boundary. No malformed guide substitution, fabricated recording, alternate SDK flag or source-shader change is involved.

## Measurements and interpretation

`tools/rr_color_response.py` reports analytic-reference MSE, maximum absolute error, RGB means/bias, centered response gain and correlation for raw packed input, actual RR output and the matched CPU fallback. Centered gain is `cov(reference, candidate) / var(reference)` per channel: 1 preserves the reference's contrast in the least-squares sense, while 0 means no correlated variation. It is undefined for constant channels. It is not itself an image-quality score.

Diagnostic channel swapping, per-channel candidate scale and a fixed ±2-pixel offset scan are clearly labelled; none changes the candidate. Offset scans use a common two-pixel interior crop for this full-coverage experiment. Synthetic identity/offset/channel-swap/zero and input-immutability controls validate those metrics.

The initial complete eight-case Release run (`rr-colour-hwpx1hil`) found:

| Case, first frame | RR MSE | Raw half-float input MSE | Centered RGB gain |
|---|---:|---:|---|
| Varying vertex colour | 0.00021810 | 9.18e-10 | 0.412, 0.382, 0.218 |
| Linear texture | 0.00147845 | 3.08e-10 | 0.114, 0.367, 0.060 |
| Point texture | 0.00386386 | 3.44e-10 | 0.051, 0.214, 0.009 |

Constant-colour cases have much smaller errors, though they are not exact pass-through. Black output still peaks at about 1.09e-5 instead of zero. Raw baseline error here is predominantly float16 quantization, not stochastic noise; huge RR/raw ratios on this analytic fixture must not be marketed as typical game-scene ratios. Use absolute error and contrast measurements instead. The regular Monte Carlo report is retained too, including any reference-noise gates affected by cancellation near a virtually exact baseline; the analytic comparison has no sampling uncertainty.

The spatial failure already occurs without PBR, motion or disocclusion. A small fixed pixel shift does not explain it. The evidence supports investigating spatial filtering/albedo preservation and startup history behavior. It does **not** establish an ignored SDK flag, an internal shader bug, a required radiance correction, or behavior at game resolutions.

The expanded Release run (`build/rr-sdk-probe/Release/rr-colour-0u48aq8r`) passes all eleven cases and three equivalence checks. Moving uniform colour from texture to vertices, changing the irrelevant input RNG seed, and extending the identical history prefix each preserve packed input hashes and SDK output exactly. Thus the colour-source location and that input RNG choice do not explain the failure.

The eight-frame linear-texture case improves, but remains far from the analytic signal:

| Frame index | RR MSE | Centered RGB gain |
|---|---:|---|
| 0 | 0.00147845 | 0.114, 0.367, 0.060 |
| 1 | 0.00116959 | 0.223, 0.431, 0.159 |
| 3 | 0.00107624 | 0.256, 0.451, 0.191 |
| 7 | 0.00103086 | 0.273, 0.461, 0.207 |

Maximum absolute RGB error at frame 7 is 0.100405. Eight frames do not establish a steady-state limit, but the failure is not confined to the reset frame. There is no camera reprojection, disocclusion or stochastic input variation to explain it in this control.

## Run and remaining work

```powershell
cmake -S . -B build/rr-sdk-probe
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_colour_response$' --output-on-failure
```

The test is optional alongside `rr_quality` and `rr_surfaces`, using the same NumPy dependency. It writes fresh per-case source/recording/output/execution JSON, quality JSON and numeric-only NPZ including the analytic reference. Evidence binds source, shader, SDK execution, reference and diagnostic implementation identities. Harness success is not quality acceptance; `quality_acceptance` remains `not-qualified`.

Final expanded Release evidence is `build/rr-sdk-probe/Release/rr-colour-0u48aq8r/verification.json` (95.43-second CTest); optimized-Python Debug evidence is `build/rr-sdk-probe/Debug/rr-colour-cm_unoww/verification.json` (94.77 seconds). All eleven SDK output bundles, numeric reference bundles and colour-response metrics are identical across configurations. Three invalid metric inputs reject, and a separate affine-control check confirms gain 0.25 and correlation 1 for `candidate = reference × 0.25 + 0.1`. Python compilation and local documentation links pass. This is fresh evidence for the analytic harness, not a rerun of the complete renderer or isolation suite.

The existing Release `rr_quality` and `rr_surfaces` regressions also pass **2/2** (139.79 seconds), retaining their prior passing/failing fixture measurements. Together with the new analytic CTest, all three quality harnesses pass. The full isolation, normal renderer, x86, legacy D3D9 and historical-image suites were not rerun in this tool-only slice. Raw SDK acceptance and image-quality acceptance remain unchanged and failed/not-qualified respectively.

Next experiments should keep these controls while isolating the documented albedo-encoding pair and queried default filter settings, then assess depth/distance scale and resolution effects under explicit budgets. Longer histories than eight frames, glossy transport and live integration are not covered. Do not change defaults or compensate SDK pixels based on this reproducer alone.

The [paired encoding experiment is now implemented](RR_ALBEDO_ENCODING.md): it retains canonical source/radiance inputs, verifies actual encoding/flags/packed hashes and tags nondefault output separately. Both documented pairings still lose substantial contrast; switching to square-root encoding does not fix this reproducer. Default output remains unchanged. Next query actual default filter settings before considering individual setting experiments.
