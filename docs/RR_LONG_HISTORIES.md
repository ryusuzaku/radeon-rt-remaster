# Eight-frame RR stability histories

This offline experiment asks whether the temporal penalty observed in the [four-frame multi-seed grid](RR_MULTI_SEED_SETTINGS.md) is only initial settling or persists later in history and after an explicit context reset. It does not change the renderer, shader, native worker, FidelityFX binaries, driver, installed games or default filter setting.

## Fixed design

The predeclared grid has 18 renderer-owned recordings and 54 isolated SDK outputs:

- texture and PBR conditions from the same source-verified surface fixture;
- renderer seeds 1, 7 and 23;
- eight stationary frames, eight frames translating 0.04 world units per frame, and the same translation with an explicit reset at frame 4;
- no override, stability 0.5 and stability 0.

Each reset recreates the SDK context and reapplies the selected preset only after its queried default has been admitted. Every configured output retains version-3 preset provenance. The harness revalidates source/material/shader/execution identities and requires identical common reference/fallback arrays across presets. Seed isolation treats indirect RGB and sampled bounce distance as stochastic while requiring components 4–23 and camera matrices to remain exact.

The independent CPU reference uses two PCG64 batches of 512 samples per hit, or 1024 total. Eight frames therefore exactly meet the unchanged `count * samples <= 4096` work cap. This is half the per-batch count used by the four-frame grid. The reference-versus-fallback confidence diagnostic may fail and will remain visible; neither its threshold nor the work cap is relaxed.

```powershell
python tools/rr_setting_histories.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --dxr build/rr-sdk-probe/Release/rrt_dxr.exe --scene build/rr-sdk-probe/Release/rr-surfaces-xt5d6i3h/source.rrscene --materials build/rr-sdk-probe/Release/rr-surfaces-xt5d6i3h/surface.rrmat --samples 512
```

The summary separates whole-sequence and late-frame deltas. “Late” means frames 4–7 for stationary/moving histories and frames 5–7 after the explicit reset. Reset-frame spatial response is reported separately. Temporal deltas compare against the unconfigured SDK default; the existing absolute gate instead compares RR with the raw signal. Thus a preset can be worse than default while still passing temporal non-regression versus raw.

## Results

Release evidence is `build/rr-sdk-probe/Release/rr-setting-histories-i7to8gpg/verification.json`, completed in 2004.30 seconds. It contains 18 recordings, 54 SDK outputs/execution/quality reports and 18 common numeric reference bundles, approximately 403 MB in total.

The complete paired late-window counts are:

| Trajectory | Preset | Spatial improved | Temporal improved / worsened | Disocclusion improved |
| --- | --- | ---: | ---: | ---: |
| Stationary, frames 4–7 | Half | 24/24 | 0 / 24 | n/a |
| Stationary, frames 4–7 | Zero | 24/24 | 0 / 24 | n/a |
| Moving, frames 4–7 | Half | 24/24 | 0 / 24 | 24/24 |
| Moving, frames 4–7 | Zero | 24/24 | 1 / 23 | 24/24 |
| Post-reset, frames 5–7 | Half | 18/18 | 0 / 18 | 18/18 |
| Post-reset, frames 5–7 | Zero | 18/18 | 0 / 18 | 18/18 |

Both variants match all six explicit reset frames exactly. The sole improved late temporal comparison is PBR moving seed 23 at frame 7 under zero bias; earlier transitions in that recording still fail temporal non-regression.

All 54 reports pass raw-relative and temporal reference-noise diagnostics. All 54 fail the stricter reference-noise-versus-fallback check at capped 512 samples per batch, so fallback rankings retain greater uncertainty than in the four-frame grid. No threshold or work cap changed. Every report fails spatial and fallback quality gates and retains the pinned SDK's failed raw-reporting acceptance. The default passes temporal non-regression versus raw in 18/18 recordings; half passes 5/18 and zero 2/18.

All three completed texture/stationary seeds show that lower-stability temporal error persists at frame 7 rather than disappearing after initial settling. Half bias has 38.6–39.4% of default spatial MSE but 4.35–4.96 times its temporal residual; zero bias has 25.8–26.4% of default spatial MSE and 5.59–6.27 times its temporal residual. Zero bias also fails the absolute temporal-versus-raw gate for seed 23; other stationary reports remain below raw temporally. All lower-bias stationary reports fail spatial/fallback gates, and the 512/batch reference-versus-fallback confidence diagnostic fails as anticipated.

All three texture/moving seeds retain the same direction at frame 7. Half bias has 28.4–30.2% of default spatial MSE and 37.1–40.4% of disoccluded-region MSE, while temporal residual is 1.17–1.19 times default. Zero bias reaches 20.3–21.4% spatial and 28.8–30.7% disoccluded MSE, with 1.29–1.30 times the default temporal residual. Both fail the absolute temporal-versus-raw gate for all three moving recordings. Camera motion narrows the temporal ratio relative to the stationary fixture but does not remove the penalty.

All three texture/reset cases validate two inspected/configured contexts and exactly reproduce default on reset frame 4. At post-reset frame 7, half bias has 37.37–37.49% of default spatial MSE and 38.66–40.01% of disocclusion MSE, while temporal residual remains 2.31–2.74 times default. Zero has 29.01–29.09% spatial and 30.63–32.40% disocclusion MSE, with temporal residual 2.71–3.24 times default. Context recreation restarts the response, but three post-reset frames do not eliminate the tradeoff.

All three PBR/stationary seeds have the same direction at frame 7. Half bias reaches 28.9–30.2% of default spatial MSE with 2.67–5.45 times its temporal residual; zero reaches 17.8–18.6% spatial with 2.78–6.92 times temporal. Half fails absolute temporal non-regression for seed 23 and zero fails it for every seed. The reduced spatial values are still 65–76 times (half) and 40–46 times (zero) the matched fallback MSE, while capped fallback-reference confidence remains false.

PBR/moving frame-7 temporal response varies more by seed. Half bias is 1.02–1.64 times default; zero is 0.95–1.69 times, including a roughly 4.8% temporal improvement for zero on seed 23 at that single transition. Spatial remains 22.5–24.5%/15.6–17.2% of default for half/zero, disocclusion 48.6–72.3%/41.3–55.5%, and spatial remains 20.6–22.5/14.3–15.8 times fallback. Earlier transitions still make every lower-bias PBR moving report fail absolute temporal non-regression. Final aggregate evidence must preserve this late exception rather than claim universal per-frame worsening.

All three PBR/reset cases are exact on frame 4. At frame 7, half spatial is 32.6–33.7% of default, disocclusion 47.8–50.1%, and temporal residual 2.07–3.05 times default. Zero spatial is 24.2–25.5%, disocclusion 41.1–43.1%, and temporal 2.57–3.67 times. Combined with texture, every configured reset frame is exact and all 36 post-reset temporal comparisons worsen.

The consistent result is therefore not “lower stability is better.” It restores spatial response while usually increasing temporal error, including late history and post-reset recovery. No operating point or SDK-internal cause is selected.

Optimized Debug fresh replay passes in 534.09 seconds (`build/rr-sdk-probe/Debug/rr-history-replay-w13fuyu4`), reproducing all 18 recordings and 54 SDK output bundles byte-for-byte. The extended moving recordings' first four frame payloads and all eighteen corresponding preset-output prefixes also match the completed four-frame grid exactly.

Affected Release regressions (`rr_quality`, `rr_surfaces`, `rr_settings` and both comparison contracts) pass 5/5 in 507.23 seconds; both contracts also pass Debug. Actual eight-frame cached-versus-standalone verification gives three exact report/array pairs, eight reference calls versus 24, and two cache/preset mismatch rejections. Python compilation, normal/optimized CPU contracts and 42 local documentation links pass. The full optional SDK suite, normal renderer, x86, legacy D3D9 and historical-render suites were not rerun in this tool-only phase.

## Decision and next hypothesis

Keep the renderer and RR setting defaults unchanged. Half and zero stability remain diagnostic presets only. The follow-up [coherent coordinate-scale experiment](RR_COORDINATE_SCALE.md) holds resolution, encoding, geometry, materials, light and seed fixed while reparameterizing every SDK-visible length. It changes output slightly but fixes no failed absolute gate and leaves the zero-bias tradeoff intact. Resolution remains a separate later variable; these results do not authorize game integration.
