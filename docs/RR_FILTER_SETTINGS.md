# Single-setting RR experiments

The isolated recorded worker can apply one predefined scalar override per run. This is research, not a new renderer default. The unconfigured path and its historical output formats remain unchanged; no renderer/shader, vendor SDK, driver or installed game is modified.

## Presets and admission

`--filter-setting` accepts only the following names. Values are exact float32 constants; there is no arbitrary-value parser or combined-settings mode.

| ID | Preset | SDK key | Value |
| --- | --- | --- | ---: |
| 0 | `none` (default) | No setting override | — |
| 1 | `stability-default` | Stability bias (2) | 1 |
| 2 | `stability-half` | Stability bias (2) | 0.5 |
| 3 | `stability-zero` | Stability bias (2) | 0 |
| 4 | `gaussian-default` | Gaussian relaxation (5) | 0 |
| 5 | `gaussian-quarter` | Gaussian relaxation (5) | 0.25 |
| 6 | `gaussian-half` | Gaussian relaxation (5) | 0.5 |
| 7 | `gaussian-one` | Gaussian relaxation (5) | 1 |

AMD's [sample controls](https://gpuopen.com/manuals/fsr_sdk/samples/denoiser/#23-configure) expose 0–1 for both keys. Its [configuration guidance](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/#26-configuring-settings) recommends querying defaults first and applying settings before dispatch. These are sample ranges, not quality guarantees. The pinned SDK header defines one float element for both keys. Sources checked 2026-09-03.

Every configured preset implies [default inspection](RR_DEFAULT_SETTINGS.md). Before the first dispatch of each recreated context, an additional guarded query must return the measured pinned default exactly: stability 1 or Gaussian 0. The two `-default` presets therefore reapply an actually admitted default, rather than blindly assuming that a literal is valid. Only then does the worker configure one key once. Failed admission or configuration suppresses subsequent dispatch/output publication, completes context/resource teardown and retains the actual query/configure evidence in the worker envelope. A process crash remains contained by the existing job boundary.

Context reports preserve preset, SDK key, float format/count, requested bits, actual default query code/bits/guards, whether configure was attempted and its actual return code. The four default-query snapshots remain around the work. They query **defaults**, not active configuration; their stability must not be described as current-setting readback. The managed reader requires successful, exact per-context evidence and matching sequence metadata. A failed configure is not relabelled successful through the existing unrelated SDK reporting workarounds.

## Output provenance

Every configured preset—including the two idempotent controls—uses `RRTRRD03`, version 3. The existing 24-byte header's final word is `(preset_id << 1) | sqrt_albedo_bit`. The record digest, frame offsets, inner `RRTRRO01` bytes, byte limits and final checksum stay unchanged. IDs 1–7 have the fixed mapping above; no additional values can be expressed by version 3.

Readers and quality analysis require the exact explicit expected preset and encoding. Unconfigured calls cannot silently accept configured output; different presets cannot substitute even if their pixels happen to match. Do not detach an inner frame from its setting-bearing bundle/report and present it as a default dispatch. These checks establish consistency, not authentication against forged third-party reports.

```powershell
python tools/rr_recorded_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input INPUT.rrcapture --output NEW.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --filter-setting stability-zero
```

Retain the command's execution JSON. Pass the same `--filter-setting` to `tools/rr_quality.py`; existing `--albedo-encoding sqrt` remains explicit for square-root output. Execution and configure success do not imply quality acceptance. `--require-gates` still retains evidence and exits 2 on failed quality gates.

## Experiment design and verification

The predeclared grid compares none and all seven presets on a two-frame textured plane (both encodings), eight-frame stationary history, a four-frame translating/reset recording and black input. Each case computes one independent matched-primary reference and CPU fallback on the unchanged source. Identical inputs, packed guides and dispatch flags allow reuse of those reference arrays across the one-key grid. Metrics include RGB MSE, centered channel gain, maximum error, and raw/fallback MSE. They are analytic-fixture measurements, not broad game-quality or ghosting qualification.

The two default controls must reproduce the unconfigured inner frame bytes exactly. Tests also exercise wrong/missing preset/report/header metadata, actual source identities, native/quality CLI forwarding, eight sequential reset contexts within existing stream/memory caps, allocation-failure recovery and historical unconfigured compatibility.

`rr_settings_contract` separately runs 49 CPU-only native API-double cases for the configure descriptor and admission/failure boundary, without loading a vendor DLL or using the GPU. `rr_settings` is the optional NumPy-enabled real-SDK grid test.

Initial Release evidence: `build/rr-sdk-probe/Release/rr-settings-3y4dazpv/verification.json`, passing in 241.27 seconds. Forty grid runs produce ten exact default-equivalence controls, five historical output matches and 43 rejected provenance/options cases. CLI failed-gate evidence and allocation-failure recovery pass. Expanded final tests add eight-context configured output and a full zero-bias history quality report.

Final optional Release SDK regression passes **12/12 in 1082.68 seconds**, including `rr_settings` in 309.06 seconds (`rr-settings-tp8e7cvp`). Optimized Debug grid replication passes in 331.69 seconds (`rr-settings-yn9yujur`). All 43 output bundles, six numeric reference bundles, five recordings and the measurement dictionaries match across configurations exactly. The final CTest invocation does not supply the optional historical-baseline argument; a separate direct hash audit confirms its five unconfigured outputs still match `rr-defaults-ycw6uxym`. Maximum configured stdout is 38,039 bytes, below the unchanged 64 KiB limit. Both native configurations pass the 49-case API-double test. Normal renderer, x86, legacy and historical-render suites were not rerun; the changed native headers are exclusive to the research probe and its CPU-only contract test.

## Measured response

On the same noise-free texture fixture, reducing stability bias improves later-frame spatial response:

| Case / final frame | No override | Stability 0.5 | Stability 0 |
| --- | ---: | ---: | ---: |
| Linear texture / 1 | 0.001169594 | 0.000658385 | 0.000607870 |
| Square-root encoding / 1 | 0.001162839 | 0.000643299 | 0.000594407 |
| Eight-frame linear history / 7 | 0.001030857 | 0.000211700 | 0.000146440 |
| Moving explicit reset / 3 | 0.000988832 | 0.000526428 | 0.000491692 |

Numbers are RGB MSE, lower is better. In eight-frame history, zero bias reduces MSE by 85.79% relative to the SDK default, and centered RGB gain rises from approximately 0.273/0.461/0.207 to 0.766/0.793/0.725. Both explicit-default presets reproduce the unconfigured result exactly. The first reset frame remains unchanged by the stability variants; the improvement appears in subsequent frames.

This is still a large error on a deliberately noise-free input. For that history frame, raw MSE is about 3.08e-10 and matched fallback MSE 1.35e-8; zero-bias RR remains about 10,822 times worse than the fallback. This ratio belongs to this analytic fixture, not the earlier noisy/PBR measurements. Maximum RGB error remains about 0.0821. Gaussian variants are small/mixed changes, not a remedy. Black input retains roughly 1.09e-5 positive output; zero bias does not eliminate that floor.

The experiment establishes a reproducible response to stability bias, not the SDK-internal cause of contrast loss. Next: compare zero/half/default stability on genuinely noisy controls with independent seeds, temporal residuals, camera motion and geometric visibility boundaries before choosing any operating point. Retain the exact-default and fresh-context controls. Animated geometry requires later capture-contract work; longer histories and depth/distance/resolution hypotheses remain separate bounded work.

## One noisy-control follow-up

`tools/rr_setting_noise.py` compares none/half/zero stability on an existing source-verified constant-colour recording, saving fresh independent references, matched fallback, execution reports and full quality gates. It never promotes a setting. Example inputs for this run are `build/rr-sdk-probe/Release/rr-quality-76v9tlg9/moving.rrcapture` and that folder's `source.rrscene`.

The initial 512-per-batch Release run (`rr-setting-noise-v2t6g3to`) measures lower later-frame spatial error for half/zero bias on this moving diffuse fixture, while one earlier temporal metric worsens. Reference variance is about 5–6e-8; the existing 1%-of-fallback diagnostic fails. That evidence is retained.

The 1024-per-batch optimized Debug rerun (`rr-setting-noise-4geqmsb0`, 221.92 seconds) passes all eight quality/reference diagnostics for each of the three presets, within the unchanged maximum frame-count-times-samples budget. No gate was loosened. The three SDK output bundles match the earlier Release run byte-for-byte; the independent reference estimates intentionally differ with sample count. Within each run, reference/fallback arrays match exactly across presets, and the unconfigured SDK output matches the source `rr_quality` run.

| Noisy control metric | No override | Stability 0.5 | Stability 0 |
| --- | ---: | ---: | ---: |
| Spatial RGB MSE, frame 2 | 1.88046e-6 | 9.16457e-7 | 8.74359e-7 |
| Spatial RGB MSE, frame 3 | 1.09088e-6 | 8.01169e-7 | 7.93963e-7 |
| Temporal residual MSE, frame 1 | 1.93038e-7 | 2.47629e-7 | 2.65860e-7 |
| Temporal residual MSE, frame 3 | 9.62422e-7 | 4.78138e-7 | 4.24945e-7 |

Lower bias improves these later-frame estimates but worsens the first temporal transition and some disoccluded-region estimates relative to the default. Passing the existing raw/fallback non-regression gates is not proof that every preset improves upon the default or that half/zero differences are statistically decisive. One recording and one input seed cannot establish a general operating point; `quality_acceptance` remains `not-qualified`, and raw SDK-reporting acceptance remains failed.

No default change or internal SDK cause is established by this implementation. Preserve the retained contrast, zero-light and raw SDK-reporting failures when interpreting any fixture-specific improvement.

The next [multi-seed textured/PBR comparison](RR_MULTI_SEED_SETTINGS.md) now has a bounded six-recording/three-preset harness, with seed-isolation checks and paired temporal/disocclusion summaries. Its findings are recorded separately from this initial grid.
