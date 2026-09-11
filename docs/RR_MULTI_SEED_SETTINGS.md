# Multi-seed RR stability tradeoffs

This offline experiment extends the [single-setting work](RR_FILTER_SETTINGS.md) to the same textured and PBR moving fixtures under three renderer noise seeds. It does not change the renderer default, shader, native worker, SDK binaries, driver or any installed game.

## Predeclared grid

The grid is fixed: texture and PBR conditions, renderer seeds 1/7/23, four frames with camera translation 0.04 units per frame, and presets none/stability-half/stability-zero. Eighteen independently admitted SDK runs use six renderer-owned recordings. PBR uses the same verified material sidecar as the earlier [surface reference experiment](RR_SURFACE_QUALITY.md). Geometry is static; this is not animated-geometry or live-game testing.

Each recording uses two independent PCG64 reference batches of 1024 samples per hit, the maximum allowed for four frames under the existing reference work cap. The reference seed is fixed at 20260903 and independent of renderer sampling. Using the same reference stream across input seeds holds reference noise fixed while varying the renderer signal; it is not six independent reference realizations. All original raw/fallback/reference-uncertainty gates remain unchanged.

The new `analyze_comparison` entry point shares four freshly calculated reference frames privately in memory across the three presets. It accepts no persisted or external reference cache. Every source, material, shader, execution report, preset tag and primary guide is revalidated for each candidate. A changed recording/reference identity fails closed. Each candidate recomputes the matched fallback and must reproduce the same reference/fallback arrays exactly. Existing standalone `analyze` and CLI behavior are unchanged.

Renderer seed validation requires three distinct recording and stochastic-signal hashes per condition, with identical deterministic-guide/camera hashes. The stochastic signal is the full `indirectDistance` float4: RGB **and sampled secondary-ray distance**; fixed guides begin at record component 4. Each preset retains its own output, execution and complete quality report. One numeric-only NPZ per recording contains the common reference/fallback arrays; every corresponding quality report names its SHA-256.

```powershell
python tools/rr_setting_surfaces.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --dxr build/rr-sdk-probe/Release/rrt_dxr.exe --scene build/rr-sdk-probe/Release/rr-surfaces-xt5d6i3h/source.rrscene --materials build/rr-sdk-probe/Release/rr-surfaces-xt5d6i3h/surface.rrmat --samples 1024
```

Output goes into a new `rr-setting-surfaces-*` directory beside the probe. Failure keeps any execution evidence already produced. No quality gate is converted into an execution failure or a general acceptance claim.

## Interpreting paired deltas

The summary counts lower/equal/higher MSE relative to the unconfigured SDK default for spatial, temporal residual and geometric-disocclusion groups. Negative deltas are improvements. Per-frame and per-seed reports remain primary evidence: a mean can hide a bad transition or visibility boundary.

Counts include the unchanged reset frame for spatial comparisons. Empty temporal/disocclusion groups are omitted. Comparisons are correlated across frames and share references; they are descriptive observations, not independent statistical trials or formal confidence intervals. The temporal metric remains nearest-compatible-pixel error residual, not exact motion-compensated ground truth. An early contrast correction can itself raise the residual metric; it does not by itself establish a particular SDK-internal ghosting mechanism.

## Verification and findings

Completed Release evidence is `build/rr-sdk-probe/Release/rr-setting-surfaces-um5fj4em/verification.json`. Across both conditions and three seeds, each lower-bias preset produces this paired result against default:

| Metric | Improved | Equal | Worsened |
| --- | ---: | ---: | ---: |
| Spatial MSE, all 24 frames | 18 | 6 reset frames | 0 |
| Disoccluded-region MSE, 18 eligible frames | 18 | 0 | 0 |
| Temporal residual MSE, 18 eligible transitions | 0 | 0 | 18 |

At the final frame, zero bias reduces spatial MSE approximately 69–71% on texture and 77–78% on PBR relative to default. It still has approximately **51–63 times** the matched fallback MSE on texture and **28–32 times** on PBR. All reference-uncertainty diagnostics pass at 1024 samples per batch. Every preset fails spatial/disocclusion/fallback gates on every recording; half and zero bias additionally fail temporal non-regression on every recording. Thus better contrast recovery does not yield an accepted operating point.

Normal and optimized CPU contract tests pass, including explicit controls for sampled-distance versus normal/camera seed classification. Actual texture and PBR cached/independent checks give six exact report/array pairs, four cached versus twelve independent estimator calls per recording, and four source-cache/preset mismatch rejections. Existing Release `rr_quality`, `rr_surfaces`, `rr_settings` and the new contract test pass 4/4 in 468.51 seconds. The final corrected CPU contract also passes separately in Debug and Release (0.30 seconds each).

Optimized-Python Debug fresh-render/fresh-worker replication passes in 64.27 seconds (`build/rr-sdk-probe/Debug/rr-surface-replay-y0d3mw1c`): all six recordings and eighteen SDK bundles match Release byte-for-byte. This replay does not recompute the Monte Carlo references. Both historical source recordings, their unconfigured outputs and their 2048-total-sample reference NPZs remain byte-identical, and every historical texture/PBR frame metric matches exactly. Python compilation and local documentation links pass. The full optional SDK suite, normal renderer, x86, legacy D3D9 and historical-render suites were not rerun in this tool-only slice.

The first final seed audit incorrectly treated secondary-ray distance as fixed. It rejected the run after all 18 analyses had been saved. The shader and exact differing-column audit confirmed the error in the harness; no renderer data or quality threshold was changed. `tests/recover_rr_surface_grid.py` revalidated saved worker admissions, output tags, source/report/reference hashes and unchanged analysis implementation before publishing the corrected manifest. This manifest explicitly records recovery and leaves elapsed time unavailable; it does not claim a fresh reference calculation. The helper is for this retained local evidence, not third-party certification.

No operating point is selected. The earlier analytic contrast loss, positive black floor and raw SDK-reporting failures remain open, even if a particular noisy case improves.

The follow-up [eight-frame history experiment](RR_LONG_HISTORIES.md) now shows that the temporal penalty usually persists through late stationary/moving frames and after context recreation. It preserves one late PBR moving exception and the weaker capped fallback-reference confidence. The later [coherent coordinate-scale grid](RR_COORDINATE_SCALE.md) changes output slightly but leaves the tradeoff and failed gates intact. Resolution remains a separate hypothesis; no live-game integration follows from these results.
