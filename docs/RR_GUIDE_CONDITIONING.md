# Ray Regeneration guide conditioning

## Result

The offline Ray Regeneration path now supports strictly tagged material-class and filter-range experiments without changing renderer recordings. A bounded five-candidate comparison on textured and PBR motion found only small spatial/temporal tradeoffs. No candidate fixes the remaining spatial, disocclusion or fallback failures, so no guide representation, filter setting, renderer default, SDK, driver or game integration is promoted.

The result is reproducible: fresh Debug recordings and all ten Debug outputs are byte-exact with the Release measurement.

## Semantics and bounded contract

The pinned RR dispatch consumes octahedral normal XY, linear roughness, material type and diffuse albedo. AMD's [Ray Regeneration technique guide](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/Kits/FidelityFX/docs/techniques/denoising.md) defines four material IDs, encoded as `id / 3` in normal alpha; differing IDs prevent cross-material filtering. The [sample controls](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/docs/samples/denoiser.md) expose normal strength in `[0,1]` and maximum radiance up to `65504`.

The documentation demonstrates octahedral encoding but does not prescribe a world- versus view-space normal convention. This phase therefore does not guess a coordinate conversion. It also leaves roughness, albedo, radiance values, stability, scale and resolution unchanged.

The live pinned context reports normal strength `1` and maximum radiance `65504`. The fixed candidates are:

| Candidate | Guide/configuration change |
| --- | --- |
| `baseline` | Unconfigured guides and queried defaults |
| `material-draw` | Draw 1 remains class `0`; draw 2 becomes class `1/3` |
| `normal-half` | Cross-bilateral normal strength `0.5` |
| `material-normal-half` | Both changes above |
| `max-radiance-one` | Maximum radiance `1`; inputs remain unchanged and below `0.085` |

Guide-conditioned output uses `RRTRRD06`. Its tag carries native-resolution, guide, coordinate-scale and filter-setting identities. The worker report repeats the guide preset, and managed admission recomputes all six packed-plane hashes. A missing, substituted or mismatched guide identity is rejected. Historical unconfigured recordings and outputs retain their existing formats and bytes.

## Fixed measurement

The Release grid uses historical native `128x96`, coherent `unit-one` scale, seed 7, eight continuously moving frames, 512 samples per independent-reference batch, and shared same-input references/fallbacks. Counts compare each candidate with the baseline over seven transitions; a lower MSE is better.

| Surface | Candidate | Spatial better/worse | Temporal better/worse | Disoccluded better/worse | Mean spatial delta | Mean temporal delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Texture | `material-draw` | 0 / 7 | 7 / 0 | 1 / 6 | +7.98e-7 | -6.95e-8 |
| Texture | `normal-half` | 1 / 6 | 5 / 2 | 3 / 4 | +2.47e-7 | -5.08e-8 |
| Texture | combined | 0 / 7 | 7 / 0 | 1 / 6 | +3.08e-7 | -7.16e-8 |
| PBR | `material-draw` | 1 / 6 | 7 / 0 | 3 / 4 | +2.05e-7 | -3.84e-8 |
| PBR | `normal-half` | 2 / 5 | 4 / 3 | 5 / 2 | +5.29e-8 | -7.17e-9 |
| PBR | combined | 4 / 3 | 5 / 2 | 4 / 3 | -1.99e-8 | -3.10e-8 |

`max-radiance-one` is exactly equal to baseline in every reported metric on both surfaces. Its lower configured ceiling does not clip the fixture's input signal and has no observable effect here.

All ten candidates pass temporal non-regression. All ten still fail spatial non-regression, disocclusion non-regression, RR-versus-fallback, fallback-relative reference confidence and raw SDK acceptance. The material partition tends to trade worse edges for slightly better history; normal strength is smaller and mixed. Neither is a quality fix.

## Evidence

- Release measurement: `build/rr-sdk-probe/Release/rr-guide-conditioning-_b5h9mz1`, 311.88 seconds, two recordings, ten SDK outputs and two shared references.
- Fresh Debug replay: `build/rr-sdk-probe/Debug/rr-guide-replay-44352k11`, two recordings and ten outputs byte-exact against Release.
- Affected Release regressions: `rr_settings_contract`, `rr_recorded_dispatch`, `rr_guides`, `rr_native_resolution`, `rr_quality`, `rr_settings` and `rr_scale` pass 7/7.
- Focused Debug contracts: `rr_settings_contract` and `rr_guides` pass 2/2.

This is fixture-bounded offline research. It does not establish a universal normal space, validate arbitrary application material classes, demonstrate live game integration or make the pinned provider image-quality acceptable.
