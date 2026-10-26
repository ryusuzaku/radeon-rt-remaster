# Bounded RR sequence quality diagnostics

The optional `rr_sequence_quality` test extends the matched-hit
[quality reference](RR_QUALITY.md) to eight-frame renderer-owned sequences.
It measures lateral translation, translation with depth motion and a fixed
initial camera rotation, and an explicit reset at frame four. Two input seeds
are represented across these trajectories; they are not a paired multi-seed
quality study. The old stationary sequence admission remains unchanged.

Each recording stays at 128×96 with the existing constant-colour diffuse
fixture subset, zero sun radius and unchanged worker containment. The independent
float64 CPU tracer uses two 512-sample batches: **1,024 samples per active hit**,
with eight frames × 512 samples at the existing 4,096 work bound. Reference
variance, independent-batch differences, source/candidate/execution hashes and
geometric visibility masks are retained with the measured errors. No preview
image is used as a reference.

The existing spatial, geometric-disocclusion and stable temporal-residual
metrics retain their original thresholds. A separate reveal-age diagnostic
starts a cohort at a geometric disocclusion and follows it through compatible
nearest-pixel correspondences. Offscreen and unmatched points leave the cohort;
resets clear every age. Per-frame errors for ages zero through seven are saved
in JSON, with numeric age maps in the reference NPZ. Later-age non-regression
compares RR MSE directly against the matched packed noisy input. The reference
noise diagnostic still requires estimated mean variance ≤1% of raw MSE.
Missing cohort coverage is `null`, never a pass.

These tracks can duplicate or lose surface points through resampling. They
measure error after a reveal, not a complete perceptual ghosting oracle or proof
of exact ground truth. Eight frames cannot qualify longer-lived history.

The harness enforces geometric reveal and stable-region coverage, tracks cohorts
beyond their first reveal, repeats the complete moving dispatch byte-for-byte,
and compares all four frames after reset with an independently captured fresh
segment. A constructed 0.25 trail must produce 0.0625 MSE in later-age cohorts.
The CPU-only contract also checks remapping, duplicate correspondences, reset
clearing, offscreen/unmatched rejection, missing coverage, reference-noise failure
and six malformed age inputs. Validation remains active under `python -O`.

## Reproduce

Configure the optional x64 SDK build as described in
[the probe guide](RAY_REGENERATION.md), including the pinned DLLs and NumPy.
There is no RR SDK preset in `CMakePresets.json`; use its documented separate
build directory. Build both configurations, then run the focused regression:

```powershell
cmake --build build/rr-sdk-probe --config Debug
ctest --test-dir build/rr-sdk-probe -C Debug -R '^rr_(probe_contract|worker_boundary|dispatch|sequence|recorded_dispatch|quality|sequence_quality_contract|sequence_quality)$' --output-on-failure
cmake --build build/rr-sdk-probe --config Release
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(probe_contract|worker_boundary|dispatch|sequence|recorded_dispatch|quality|sequence_quality_contract|sequence_quality)$' --output-on-failure
```

`rr_sequence_quality` requires the harness, coverage and exact execution controls
to pass. A reset-to-fresh mismatch fails CTest with its evidence retained; it is
not admitted with a numerical tolerance. Spatial quality gates are saved before
coverage assertions and are reported independently. Every completed measurement
retains `quality_acceptance: not-qualified`; SDK execution still reports
`raw_sdk_acceptance: failed`. The separate exact-zero failures in `rr_dispatch`,
`rr_sequence` and `rr_quality` remain visible and unchanged.

Renderer defaults, SDK settings, shaders, memory ceilings, admission tolerances
and the stationary format are unchanged. Textured/PBR regressions, soft lights,
animated geometry, broader seeds/materials, longer histories and general
quality acceptance remain open.

## Observed exact-control failure

The initial complete Debug measurement retained all three trajectories in
`build/rr-sdk-probe/Debug/rr-sequence-quality-jl1oy7aq`. All narrow spatial,
disocclusion, temporal-residual, later-reveal and reference-noise gates passed
on this constant-colour fixture. The four-frame reset-to-fresh control failed:
all input records and camera matrices matched exactly, as did the SDK segment
indices, reset flags, camera deltas and six packed texture hashes per frame.
The first output frame matched; subsequent frames differed in 491, 5,717 and
10,773 RGBA components, with maximum RGB differences 0.0001220703125,
0.00384521484375 and 0.00567626953125. These are differences between two RR
outputs, not errors against the high-sample reference.

This extends the older two-frame reset control and does not establish an
SDK-internal cause. Later runs also exposed failures in the existing exact
reset-repeat/stationary compatibility controls. Preserve the individual reports;
a passing narrow spatial metric does not resolve execution repeatability.
The new test retains strict failure and writes per-frame mismatch counts,
maximum differences and MSE before failing. No renderer/worker workaround or
SDK modification is introduced by this test slice.

The finalized Debug retry
`build/rr-sdk-probe/Debug/rr-sequence-quality-dc8p7dq5/verification.json`
retains `result: failed-exact-controls`, `repeat_byte_equal: false` and
`reset_fresh_byte_equal: false`, with reset input and dispatch metadata equality
both true. Its maximum reset/fresh RGB difference is **0.00799560546875**;
even segment frame zero differs in that run. All three trajectories still pass
the narrow error/noise gates. Reveal counts are 340–342 per lateral non-reset
frame and 382–589 for the rotated/depth trajectory; cohorts reach age six
without a reset and age two within the four-frame reset segments. Missing age
seven remains unevaluated. These observations reinforce the execution failure,
not a general improvement or repeatability claim.

## Build and machine limits

Measured on 2026-10-23 with VS 2022, Python 3.12.10, NumPy 1.26.4 and an
RX 9070 XT. The documented pinned SDK subset was restored with its license;
both DLL hashes match the existing worker pins. The `windows-x86` preset and
the documented separate x64 `rr-sdk-probe` configuration build successfully in
Debug and Release. No RR SDK preset was added or inferred.

The final full x86 runs used the preserved private inventory, position capture
and grouped capture through the documented CMake cache inputs. All 50 tests
ran, including all 13 local-evidence tests; none skipped. The two CPU-only
local-evidence tests passed. Both runs retained 30 display-dependent failures:

| Configuration | Final CTest summary | Total test time |
|---|---|---:|
| x86 Debug | `40% tests passed, 30 tests failed out of 50` | 108.42 s |
| x86 Release | `40% tests passed, 30 tests failed out of 50` | 121.22 s |

This process runs in Windows **session 0**. Hardware headless DXR and RR
recording work, but D3D9 fixture/raster device creation returns `0x8876086c`
(D3D9Ex creation returns `0x8876086a`), and native swapchain creation returns
`0x887a0022`. Consequently these tests could not complete their display work:

- D3D9/raster: `dxr_render`, `shader_snapshot`, `shader_proxy`,
  `shader_inventory`, `shader_disassembly`, `hl2_position`, `position_capture`,
  `texture_compressed`, `texture_upload`, `texture_dirty`, `texture_surface`,
  `texture_locks`, `texture_scope`, `texture_selection`,
  `recorded_position_oracle`, `position_groups`, `mod_replay`, `mod_replay_ex`,
  `proxy_equivalence`, `game_pass_workflow`, `proxy_equivalence_ex`,
  `scene_replay`, `scene_replay_ex`, `d3d9_smoke_sample_run`.
- Native window/swapchain: `dxr_temporal`, `dxr_render_scale`,
  `dxr_presentation`, `dxr_async`, `dxr_pacing`, `dxr_materials`.

A representative four-test Debug retry reproduced the display failures. This
is not a passing full renderer/proxy qualification. Initial missing-evidence
skips and fixture/control development failures are retained separately in the
archive, rather than relabelled as final results.

Final focused SDK results (the eight-test subset above):

| Run | Final CTest summary | Total test time |
|---|---|---:|
| Debug full subset | `50% tests passed, 4 tests failed out of 8` | 255.94 s |
| Debug failed-test retry | `0% tests passed, 4 tests failed out of 4` | 214.19 s |
| Release full subset | `50% tests passed, 4 tests failed out of 8` | 261.51 s |

Both full runs pass `rr_probe_contract`, `rr_worker_boundary`, `rr_quality` and
`rr_sequence_quality_contract`. Both fail `rr_dispatch` (reset repeat),
`rr_sequence` (reset isolation), `rr_recorded_dispatch` (stationary
compatibility) and `rr_sequence_quality` (exact moving repeat; its separately
recorded reset/fresh control also fails). The final Debug retry reproduces all
four failures. No failure was marked expected or given a tolerance.

The final Release report is
`build/rr-sdk-probe/Release/rr-sequence-quality-zfwiw8by/verification.json`.
Its reset/fresh inputs and dispatch metadata match, but the fourth output frame
differs in 1,965 pixels / 3,889 components, with maximum RGB difference
0.000244140625; the first three match. Both final reports retain all per-case
quality/history gates, exact-control results and requested allocation peaks:
5,327,216 bytes renderer, 20,971,520 bytes SDK callbacks and 1,900,544 external
bytes. These are tracked/requested allocations, not total residency.

The final Debug/Release recordings and numeric reference arrays match for all
three trajectories; corresponding RR candidate bundles differ. This is
same-GPU evidence of the measured variability, not cross-GPU qualification.
Other optional SDK experiments and the normal x64 renderer suite were not
rerun. The original quality test still records its nonzero exact-black result.

## Evidence retention

`docs/EVIDENCE_LEDGER.jsonl` records the external archive
`rr-sequence-validation-20261022-221155.tar.gz`: 421 files, 654,298,546
uncompressed bytes, 50,963,442 archive bytes, SHA-256
`0f1b957b0f8bb5d6b8188bb3d967254e6edb8bba20a8959f1212185afe9828ec`.
The archive contains all development/final RR attempts, CTest logs, reference
arrays, exact-control diagnostics, cross-configuration checks and implementation/
binary identities. The ledger contains metadata only. Its timestamp is UTC;
the run date above uses local time. Use the documented archive `check` command
with the ledger, rather than relying on archive self-consistency alone.
The final ledger check verified all 421 files with no problems.

A later [bounded repeatability diagnosis](RR_REPEATABILITY.md) records fresh
worker, resource/context reuse, Debug/Release and host-pause controls separately
from replay of these exact archived inputs. Passing samples do not invalidate
the failures above or establish context recreation as a repeatability fix.
