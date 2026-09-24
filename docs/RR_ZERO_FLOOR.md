# Ray Regeneration exact-zero floor

## Result

The pinned Ray Regeneration 1.2 provider emits a small positive RGB value for every SDK-active pixel when indirect diffuse input is exactly zero. SDK-inactive background pixels remain exactly zero. The floor survives zero diffuse albedo, zero indirect hit distance, every previously measured scalar setting, and eight frames of valid history.

This is a failed quality gate. No subtraction, clamp, epsilon tolerance or negative pre-bias is applied. The existing strict zero-light oracles remain unchanged.

The evidence localizes the floor to active-pixel processing beyond the application's upload/resource boundary. It does not prove a particular internal clamp or ML-model constant: the pinned SDK package exposes the API and signed provider binaries, not the RR shader/model implementation. AMD describes RR as an [ML-based denoiser](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/Kits/FidelityFX/docs/techniques/denoising.md), and its [SDK structure documentation](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/main/docs/getting-started/sdk-structure.md) explains that shipped effects include prebuilt runtime code with only a limited public HLSL collection.

## Bounded reproducer

`tools/rr_black_floor.py` captures eight stationary 128x96 frames with zero ambient, zero light intensity and exact-zero indirect RGB. It verifies recording/source identity, runs an unconfigured persistent-context history, then derives four checksum-bound reset inputs:

| Variant | Change from source-valid reset frame |
| --- | --- |
| `active` | Exact-zero radiance; all canonical geometry/material guides retained |
| `zero-albedo` | Diffuse albedo is also zero on active pixels |
| `zero-distance` | Indirect hit distance is also zero on active pixels |
| `background` | Every pixel becomes the canonical inactive record |

All inputs pass the existing native and managed row validation. Each dispatch rechecks packed texture hashes, immutable uploads, resource accounting, output identity, finite/nonnegative RGB, exact preserved alpha and exact-zero background. The analyzer reports active/background value counts, minima, maxima, means, MSE and distinct positive half-float values. It never edits candidate output.

## Mixed-coverage measurement

The decisive Release fixture contains 9,976 active and 2,312 inactive pixels. Results below cover its reset frame; values/counts are RGB components.

| Variant | Positive active values | Positive inactive values | Active mean | Active MSE | Maximum | RGB exact with `active` |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `active` | 29,928 / 29,928 | 0 / 6,936 | 1.0875703e-5 | 1.1828179e-10 | 1.0907650e-5 | yes |
| `zero-albedo` | 29,928 / 29,928 | 0 / 6,936 | 1.0869782e-5 | 1.1815298e-10 | 1.0967255e-5 | no, tiny distribution shift |
| `zero-distance` | 29,928 / 29,928 | 0 / 6,936 | 1.0875703e-5 | 1.1828179e-10 | 1.0907650e-5 | yes |
| `background` | 0 | 0 / 36,864 | 0 | 0 | 0 | no |

The first inner history output is byte-exact with the isolated `active` reset dispatch. Every active RGB component remains positive on all eight frames; every inactive component remains zero. Active mean declines only from `1.0875703e-5` on frame 0 to `1.0713463e-5` on frame 7, with MSE changing from `1.1828179e-10` to `1.1477954e-10`. History therefore attenuates the floor slightly but does not converge to zero within the admitted sequence.

The retained two-frame settings grid independently shows the same floor under unconfigured/query-default, stability, Gaussian relaxation, normal-strength and maximum-radiance presets. None clears it. Maximum-radiance one is inert; Gaussian one slightly increases one reset maximum.

## Diagnosis boundary

These controls rule out:

- output-resource poison/clear leakage, because inactive and all-background output is exact zero;
- nonzero source radiance or CPU fallback, both of which are exact zero;
- diffuse-albedo demodulation as the source, because zero albedo retains the floor;
- indirect hit-distance magnitude, because zero distance is RGB-exact;
- persistent history contamination, because reset-only equals the first recorded frame;
- the existing six scalar configuration keys, based on the retained settings grid.

The supported conclusion is a reproducible active-pixel floor inside the signed provider boundary for these admitted inputs. Without inspectable RR implementation source or a provider update, naming a specific internal epsilon would be speculation. It is too small to explain the much larger textured/PBR contrast regression, but exact black remains formally unacceptable.

## Evidence

- Final Release measurement: `build/rr-sdk-probe/Release/rr-black-floor-v_0xe0sn`.
- Fresh Debug replay: `build/rr-sdk-probe/Debug/rr-black-floor-vtkbudp8`; recording, history, four inputs and four outputs match Release byte-for-byte.
- Final Release adjacent contracts: `rr_black_floor`, `rr_dispatch`, `rr_sequence` and `rr_recorded_dispatch` pass 4/4 in 105.55 seconds.
- Focused Debug `rr_black_floor` passes in 13.98 seconds.

No renderer default, SDK/provider binary, driver, installed game or live integration path changed.
