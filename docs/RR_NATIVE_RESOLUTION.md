# Ray Regeneration native-resolution sensitivity

## Result

The offline RR path now admits exactly two native, same-aspect extents: historical `128x96` and versioned `256x192`. The renderer traces and records each extent directly; no guide, candidate, reference or fallback image is resized. The 128x96 v1 bytes remain unchanged.

Higher native resolution improves aggregate spatial and disocclusion error in all four surface/setting pairs, but it does not make the pinned FSR Ray Regeneration 1.2 provider acceptable. Default PBR temporal error worsens by about 51%, every spatial/fallback gate still fails, and zero stability retains its spatial-versus-temporal tradeoff. No resolution, setting, renderer default, SDK, driver or game integration is promoted.

## Bounded contract

`RRTRRI02`, `RRTRRC02`, `RRTRRO02` and `RRTRRD05` carry 256x192 provenance. Managed and native readers admit only the exact `(magic, version, width, height, stride, length)` tuples; a v2 payload relabelled as v1 is rejected. Dimension-derived allocations, dispatch groups, texture footprints, recording strides, single-frame previews and output lengths are checked throughout. Both single-frame reset and recorded-history execution are admitted at v2.

A stricter fresh-single versus recorded-reset equality diagnostic was deliberately tried and rejected: two fresh single-context executions themselves differed at 981 of 49,152 pixels, with maximum RGB delta `6.103515625e-05`, MSE `7.44e-11`, and identical alpha. This is tiny half-float-level provider nondeterminism, but it means byte equality would be a flaky contract. The retained four-recording/eight-output cross-build replay happened to be byte-exact; quality evidence uses measured arrays and never assumes general SDK bit determinism.

The first proposed 64x48 candidate was rejected live. Capture, decoding and CPU reference paths worked, but the provider requested seven D3D12 resources with height zero during context creation. It is not an admitted format. The valid second point is 256x192, which preserves the 4:3 camera frustum and exercises a larger native input without resampling.

At 256x192 the observed exact accounting is:

- context preflight: 21,561,344 bytes;
- callback peak: 22,544,384 bytes;
- worker-owned external resources: 6,553,600 bytes;
- upload/readback staging: 2,162,688 bytes.

The provider repeats its known post-context unsigned-underflow report at an extent-specific value (`0xfffffffffeb90000`, aliasable 65,536 bytes). Admission pins that exact tuple and still labels raw SDK acceptance failed.

## Fixed measurement

The Release grid uses seed 7, eight continuously moving frames, 256 samples per independent-reference batch, texture and PBR surfaces, explicit coherent `unit-one` scale, and default versus `stability-zero`. Ratios below are `256x192 / 128x96`; less than one is lower error.

| Surface | Setting | Spatial | Temporal | Disoccluded | Fallback |
| --- | --- | ---: | ---: | ---: | ---: |
| Texture | default | 0.799 | 0.654 | 0.523 | 0.982 |
| Texture | zero | 0.843 | 0.705 | 0.496 | 0.982 |
| PBR | default | 0.637 | 1.510 | 0.630 | 0.975 |
| PBR | zero | 0.601 | 0.951 | 0.530 | 0.975 |

The raw half-float baseline MSE is about 6% higher at 256x192 for both surfaces, while the independent CPU fallback changes by only 2–2.5%. This makes the large RR spatial/disocclusion shifts a genuine resolution sensitivity rather than a matching fallback shift. Default passes the temporal non-regression diagnostic at both extents; zero stability fails it at both. All eight candidates fail spatial non-regression, RR-versus-fallback and fallback-relative reference-confidence gates. Only the 256x192 texture/zero candidate passes the narrow disocclusion non-regression gate.

## Evidence

- Release measurement: `build/rr-sdk-probe/Release/rr-resolutions-uo3jk9d_`, 686.94 seconds, four recordings and eight SDK outputs.
- Fresh Debug replay: `build/rr-sdk-probe/Debug/rr-resolution-replay-xqpyt64d`, four recordings and eight outputs byte-exact against Release.
- Focused Release compatibility: `rr_native_resolution`, `rr_inputs`, `rr_record`, `rr_worker_boundary` and `rr_dispatch` pass 5/5 in 84.26 seconds.

The evidence is offline, fixture-bounded research. It is not AMD “RTX” game readiness, a general denoiser benchmark, dynamic-resolution support, an upscaler, or a BioShock 2 integration claim.
