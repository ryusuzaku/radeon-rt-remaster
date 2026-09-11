# RR coordinate-scale experiment

This offline experiment tests whether the pinned Ray Regeneration 1.2 path is sensitive to scene units while keeping resolution, radiance, albedo, geometry, input seed and filter setting fixed. It does not change the renderer, recordings, SDK/provider binaries, driver, installed games or runtime default.

## Why this is a complete coordinate transform

The pinned `ffx_denoiser.h` contract consumes signed current linear depth, previous-minus-current linear-depth motion, previous-minus-current world-space camera delta, current row-vector view/projection matrices and indirect ray hit distance. It has no independent current-depth scale. Scaling only one of these would make the guides contradict each other.

For scale `s`, the recorded worker therefore changes only its SDK staging/dispatch data:

- signed depth, depth motion, camera delta and committed secondary-hit distance are multiplied by `s`;
- view is transformed as `V' = S^-1 V S`;
- projection is transformed as `P' = S^-1(sP)`;
- linear-depth bounds are multiplied by `s`;
- `S = diag(s,s,s,1)`, so projected NDC/UV remains unchanged.

Radiance, albedo, normals, roughness, material type, XY motion, resolution and the immutable recording stay exact. The renderer's exact secondary-ray `TMax` value 100000 denotes no committed hit; it remains the FP16-max unbounded sentinel instead of becoming a finite scaled distance.

Three fixed recorded-only presets are available: `unit-tenth`, `unit-one` and `unit-ten`. Scaled output uses `RRTRRD04` with the scale ID, optional setting ID and albedo-encoding bit in the tag. Readers reject it unless the exact scale, setting and encoding are requested. Native reports publish the scale, exact transformed view/projection hashes, scaled bounds and packed texture hashes. Ordinary unconfigured output is unchanged.

```powershell
python tools/rr_recorded_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input ABSOLUTE_RECORDING --output NEW_OUTPUT --scene ABSOLUTE_SCENE --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --coordinate-scale unit-ten
```

## Fixed measurement

The grid uses seed 7, texture/PBR surfaces, eight-frame 0.04-unit camera motion, and the same motion with an explicit reset at frame 4. Each of the four recordings has all three coordinate scales under the unconfigured default and `stability-zero`, plus an unconfigured compatibility output. This yields 24 measured candidates and four compatibility controls at the unchanged 128x96 resolution.

Every recording has one private source-verified surface reference and matched fallback shared exactly across its six candidates. Two independent PCG64 batches use 512 samples per hit, exactly meeting the existing `count * samples <= 4096` cap. The default-versus-zero comparison is repeated at every scale; scale comparisons are paired against `unit-one` within the same filter setting.

Release evidence is `build/rr-sdk-probe/Release/rr-coordinate-scales-nxw61kp4/verification.json`, completed in 653.31 seconds. The initial `rr-coordinate-scales-m7b3p4tu` grid is retained but superseded because it incorrectly scaled the no-hit sentinel to finite 10000 at `unit-tenth`. Corrected unit-tenth output changes more than 92,000 preserved alpha values in sampled bundles versus that run but zero denoised RGB rows, so the RGB metrics happen to remain exact.

## Results

All four `unit-one` compatibility controls reproduce every historical unconfigured inner SDK frame byte-for-byte. All three corrected scales have the same 743,788 aggregate no-hit clamps. All 24 candidates pass raw, temporal and disocclusion reference-confidence diagnostics. Every candidate still fails spatial, disocclusion and fallback quality gates, the stricter fallback-confidence check, and raw SDK reporting acceptance.

At the default filter, scale ten versus unit one gives:

- spatial improvement in 25/32 frame comparisons and 13/14 late comparisons;
- disocclusion improvement in 16/26 comparisons and 10/14 late comparisons;
- an exactly split 13/13 temporal count overall, but 9/14 late comparisons worsen;
- mean spatial delta `-5.18e-7` and mean temporal delta `+3.00e-8`.

Scale one tenth is mixed: 12/32 spatial comparisons improve, 20 worsen, and mean spatial delta is `+4.33e-8`. Its overall temporal count is 14 improved/12 worsened, but 10/14 late comparisons worsen. These are descriptive seed-7 fixture measurements, not confidence-bounded scale rankings.

With zero stability, scale ten improves 26/32 spatial comparisons and all 14 late spatial comparisons, while 16/26 temporal and 10/14 late temporal comparisons worsen. Scale one tenth remains mixed. The scale-ten default spatial shift is about one percent of the much larger unit-one zero-stability spatial shift; neither scale resolves the spatial-versus-temporal tradeoff.

That tradeoff is invariant across all three scales:

| Scale | Zero vs default spatial | Zero vs default temporal | Zero vs default disocclusion |
| --- | ---: | ---: | ---: |
| Unit tenth | 26 improved / 6 reset-equal | 26 worsened | 26 improved |
| Unit one | 26 improved / 6 reset-equal | 26 worsened | 26 improved |
| Unit ten | 26 improved / 6 reset-equal | 26 worsened | 26 improved |

The coordinate scale therefore changes RR output slightly, which is consistent with absolute internal thresholds or precision effects, but it neither explains nor fixes the failed spatial response. Scale ten cannot be promoted: every absolute spatial/disocclusion/fallback gate still fails and its later temporal response usually worsens. Unit one remains the only integration default.

Fresh optimized Debug replay `build/rr-sdk-probe/Debug/rr-coordinate-scale-replay-12k1gj8z` reproduces all 28 Release bundles byte-for-byte in 235.30 seconds. Affected Release regressions (`rr_recorded_dispatch`, `rr_quality`, `rr_settings`, `rr_scale` and the aggregation contract) pass 5/5 in 472.39 seconds. The new Debug contracts pass 2/2 in 53.86 seconds. Python compilation also passes. Full renderer, legacy D3D9 and unrelated optional SDK suites were not rerun for this isolated tool phase.

## Decision

Keep unit scale and the current filter default unchanged. Retain coordinate scales and zero stability as explicitly tagged research controls only. The next bounded input hypothesis should hold units fixed and examine resolution separately; larger game-facing work still requires qualification against an owned title and does not follow from this fixture.
