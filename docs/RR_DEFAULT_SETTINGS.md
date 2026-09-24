# Read-only RR default-setting inspection

The optional recorded research worker queries the pinned RR 1.2.0 SDK's six scalar filter defaults on a live context. This is inspection, not tuning or a fix for the retained spatial contrast loss. No denoiser-context configuration override is made; the pre-existing null-context SDK logging configuration is unchanged. The renderer, shaders, canonical recordings, vendor SDK binaries, drivers, installed games and resource limits are unchanged.

## Measured values

Initial RX 9070 XT / pinned SDK 2.3.0 live queries returned code 0 for all six keys:

| Key | Scalar default |
| --- | ---: |
| Cross-bilateral normal strength | 1 |
| Stability bias | 1 |
| Maximum radiance | 65504 |
| Radiance clipping standard-deviation K | 50 |
| Gaussian kernel relaxation | 0 |
| Disocclusion depth threshold | 0.01 (float32) |

The threshold's exact bits are `0x3c23d70a`; its native JSON round-trip representation is `0.00999999978`. Gaussian relaxation zero is an actual successful write, distinguishable from untouched output memory. These are values returned by the **default-value** API, not a readback of internal shader constants or evidence that a specific setting causes the contrast loss. Debug-view depth bounds (key 7, a different struct type) are deliberately outside this six-filter-scalar inspection.

Contract source: the pinned `Kits/FidelityFX/denoisers/include/ffx_denoiser.h`, `ffxQueryDescDenoiserGetDefaultKeyValue` and keys 1–6 of `FfxApiConfigureDenoiserKey`. The descriptor requires a non-null live denoiser context, a key, element count and typed destination.

## Execution and evidence

Pass `--query-defaults` to `tools/rr_recorded_dispatch.py` or the isolated recorded native worker. It is rejected for non-recorded modes and as a duplicate native option. Both existing albedo encodings are supported; linear is still the default.

```powershell
python tools/rr_recorded_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input INPUT.rrcapture --output NEW.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --query-defaults
```

For each sequential reset context, the worker takes two snapshots before dispatch and two after its GPU work has completed. Each snapshot queries exactly one float32 element for each of the six keys. There are 24 queries per context, at most eight contexts per recording. Every call starts with a quiet-NaN sentinel (`0x7fc0a55a`) between two guard words (`0xa59c3e71`). Native evidence preserves the actual return code, output bits and both guard words. A numeric value is emitted only after success, an actual write, intact guards and a finite result; otherwise it is null. Guards are diagnostic checks, not a memory sandbox.

The managed reader validates types, key order, count, phases, guards and value/bit consistency. It compares all repeated snapshots, including across recreated contexts. `default_inspection.status` is separate from rendering and quality:

- `not-requested`: historical/default execution without query evidence.
- `defaults-ready`: every query succeeded with stable, finite written values.
- `default-query-failed`: honest query failure, unwritten sentinel or nonfinite output; no usable values published.
- `default-query-unstable`: successful values differ across snapshots; no usable values published.

Malformed reports or damaged guards reject execution assessment. Explicitly requested inspection cannot silently accept missing evidence; partial evidence rejects even for callers that did not require inspection. Quality analysis independently revalidates native snapshots rather than trusting saved inspection summaries. A successful execution CLI exit still means execution, not successful inspection or quality—check the separate status.

No query evidence is added to query-off native reports, and no output format/version changes are needed: inspection is read-only. The tests require query-off/on output bytes **and all other native report fields** to match, including dispatch flags, packed texture hashes, context accounting and the retained raw SDK metadata failures. Existing 64 MiB SDK / 8 MiB external live limits and 64 KiB worker stream caps remain enforced.

## Verification

`rr_defaults` is an optional NumPy-enabled SDK CTest. It exercises both encodings with a two-frame textured plane, black input, eight-frame history, moving explicit reset and eight automatic-cut contexts. It also tests malformed query reports, honest failed/nonfinite/unwritten results, within/across-context instability, signed-zero consistency, CLI forwarding, quality revalidation, injected allocation failure and fresh-worker recovery. Optional `--baseline PREVIOUS_ENCODING_DIRECTORY` checks unchanged historical recordings/output bundles.

Initial Release verification passes in `build/rr-sdk-probe/Release/rr-defaults-v35hm6p3` (96.28 seconds). Final optimized-Python Debug passes in `build/rr-sdk-probe/Debug/rr-defaults-fh5vyha8` (145.42 seconds, while the independent Release suite was also running): ten off/on pairs, 35 rejections, five honest-failure controls, two instability controls and eight historical output matches.

Final Release optional SDK regression passes **10/10** in 692.00 seconds. The new `rr_defaults` test passes in 129.45 seconds; evidence: `build/rr-sdk-probe/Release/rr-defaults-ycw6uxym/verification.json`. All 22 output bundles, five canonical recordings and per-case inspection dictionaries match final Debug and initial Release exactly. Eight final output bundles also match the previous encoding experiment directly. The ten pairs cover 26 queried contexts and 624 successful queries, with no changed non-query report fields and maximum stdout 36,099 bytes.

The older encoding regression (`rr-encoding-v9sohl75`) retains byte-identical results versus `rr-encoding-n49hhhv5`: fourteen paired SDK bundles, eight reference bundles including the CLI reference, and all measurement dictionaries. The queried linear-texture quality frame metrics and gates also match that previous experiment. Contrast/zero-light failures and raw SDK acceptance failure remain; no quality threshold was relaxed.

Both native configurations, Python compilation, CLI help and local documentation links pass. Normal renderer, x86, legacy D3D9 and historical-render suites were not rerun; the modified native headers are exclusive to the optional research probe. No vendor SDK binary, renderer/shader source, driver, installed game or default filter was changed.

## Next bounded experiment

The following implementation is now available as the separate [single-setting experiment path](RR_FILTER_SETTINGS.md). Read-only queries alone still configure nothing.

AMD's [configuration guidance](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/#26-configuring-settings), checked 2026-09-03, says to query defaults first and apply changes before dispatch; settings need not be rewritten every frame. Its [sample configuration controls](https://gpuopen.com/manuals/fsr_sdk/samples/denoiser/#23-configure) expose these ranges: normal strength, stability bias and Gaussian relaxation 0–1; disocclusion threshold 0.01–0.05; radiance cap and clipping K 0–65504. These are sample UI ranges, not a complete SDK validation specification or a guarantee of quality throughout the ranges.

Next implementation order:

1. Add a single-key override path that records requested float bits and actual configure return code for every reset context, keeps default execution unchanged and binds nondefault output to setting provenance. Do not mistake another default query for current-setting readback.
2. First configure a queried value back to itself and require exact output equivalence. Keep this idempotent control distinct from no configuration.
3. Test small predeclared Gaussian-relaxation and stability-bias grids within the sample's ranges, changing only one key per run. Their effects on this reproducer are hypotheses, not established causes.
4. Compare the same noise-free texture/history, black and moving-reset controls plus the matched fallback, retaining all quality failures and resource caps. Add independent seeds/geometry before any general improvement claim.

Do not combine speculative changes, correct SDK output after the fact or relax quality gates. Depth/distance scale and resolution remain separate hypotheses. This inspection does not establish a vendor-internal cause or qualify RR for default use.
