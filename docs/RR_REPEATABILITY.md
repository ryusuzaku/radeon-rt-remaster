# Bounded RR repeatability diagnosis

The next Phase 5 gate after [sequence quality](RR_SEQUENCE_QUALITY.md) is
execution repeatability, before broader quality qualification. This diagnostic
uses the existing pinned workers and exact comparisons. It changes no renderer,
shader, SDK setting, allocation ceiling, admission tolerance or reset policy.
It is not a workaround or a fix.

This session does not reproduce the earlier same-run mismatches in the bounded
cases below. New outputs nevertheless differ from archived outputs for identical
recorded inputs. No cause or repeatability fix has been established.

## Controls

Three renderer-owned constant-colour fixture recordings are captured once with
zero sun radius, seed 1 and the existing 128×96 extent. Both build configurations
consume the same files and preparation shader. The stationary recording resets
at frame four; the lateral recording moves 0.03125 scene units per frame and
resets at frame four; an independent four-frame recording starts at its reset
pose (offset 0.125).

For each mode, run an initial fresh worker, a consecutive fresh worker, and a
third fresh worker after a two-second host pause. Every worker retains its
existing pinned-DLL checks, process containment, fenced upload/readback checks,
unchanged-input checks, poison/finite/alpha checks and lifecycle accounting.

| Mode | Frames | Contexts per worker | Within-worker control |
|---|---:|---:|---|
| Single reset | 1 | 1 | None |
| Stationary sequence | 8 | 1 | Identical four-frame segments; SDK reset flag |
| Stationary recording | 8 | 2 | Identical four-frame segments; context recreation |
| Moving recording | 8 | 2 | Second segment compared with independent fresh recording |
| Fresh moving segment | 4 | 1 | Same reset pose and four inputs as moving segment two |

The stationary sequence is packed from the first four stationary recording
inputs repeated verbatim. Its textures and staging resources persist across the
reset. Recorded contexts are recreated sequentially while the external textures
and staging resources persist. Fresh workers recreate their device and resources.
This controls resource lifetime/reuse, **not allocation placement**: no heap
addresses, residency, allocation offsets/order perturbations or driver-internal
allocations are measured or changed.

The pause begins after the preceding managed worker has completed and been
reaped. It is not verified GPU idle or a cold/warm clock measurement. Other GPU
clients, clocks and scheduling are unmeasured. Debug and Release both retain
the standard D3D12 debug layer; this does not compare debug-layer on/off.

Every input bundle, output bundle and per-frame RGBA payload has a SHA-256.
Each comparison also checks exact packed texture hashes, formats, reset/index,
camera delta and dispatch flags. Reset/fresh input comparison hashes every
float32 record, all five camera matrices, seed, random index and reset flag;
only the recording-global frame ordinal is omitted. Whole-file hashes retain
that ordinal. Output comparisons exclude bundle headers/input digests and
compare all RGBA payload bits, including alpha and signed zero. Mismatch reports
retain per-frame pixel/component counts, maximum RGB difference and RGB MSE.
Numerical errors never replace exact equality.

## Reproduce

Use the separate optional x64 SDK build in [the probe guide](RAY_REGENERATION.md).
There is no RR SDK preset. Install the documented NumPy dependency for the
existing quality regressions. Output directories below must be new.

```powershell
$rrSdkRoot = (Resolve-Path build/dependencies/fsr-2.3.0-probe).Path
cmake -S . -B build/rr-sdk-probe -G "Visual Studio 17 2022" -A x64 -DRRT_RENDERER_ONLY=ON "-DRRT_FSR_SDK=$rrSdkRoot"
cmake --build build/rr-sdk-probe --config Debug
cmake --build build/rr-sdk-probe --config Release
python tools/rr_repeatability.py prepare --dxr build/rr-sdk-probe/Release/rrt_dxr.exe --out build/rr-repeatability-inputs
python tools/rr_repeatability.py run --probe build/rr-sdk-probe/Debug/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --inputs build/rr-repeatability-inputs --out build/rr-repeatability-debug
python tools/rr_repeatability.py run --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --inputs build/rr-repeatability-inputs --out build/rr-repeatability-release
ctest --test-dir build/rr-sdk-probe -C Debug -R '^rr_(repeatability_contract|settings_contract|surface_settings_contract|history_settings_contract|coordinate_scale_contract|probe_contract|worker_boundary|dispatch|sequence|recorded_dispatch|quality|sequence_quality_contract|sequence_quality)$' --output-on-failure
ctest --test-dir build/rr-sdk-probe -C Release -R '^rr_(repeatability_contract|settings_contract|surface_settings_contract|history_settings_contract|coordinate_scale_contract|probe_contract|worker_boundary|dispatch|sequence|recorded_dispatch|quality|sequence_quality_contract|sequence_quality)$' --output-on-failure
```

The diagnostic returns nonzero on any exact-control mismatch after saving all
completed measurements. An entirely equal sample reports
`observed-exact-sample`, never repeatability qualification; quality remains
`not-qualified` and raw SDK acceptance remains `failed`. Unexpected worker
admission or execution failure stops the experiment with its report retained.
The GPU/SDK-free `rr_repeatability_contract` is registered in ordinary builds
too. It checks injected RGB error, a signed-zero alpha difference, header-only
differences, metadata mutations, missing/count-mismatched comparisons and exact
input-hash normalization. It also passes under `python -O`.

## Optional second-process GPU load

The `run` command accepts `--with-gpu-load --load-dxr PATH`. This remains an
opt-in diagnostic; ordinary runs and CTest GPU regressions do not start load.
The five modes, three launches per mode, exact controls and tolerances are
identical in loaded and unloaded runs. `verification.json` now includes explicit
`exact_comparisons` totals (`match`/`differ`), per-case worker intervals and
`gpu_load` settings/lifecycle evidence. Per-frame RGBA and whole-file hashes are
retained as before. The report schema is `rr-repeatability-2`.

The Windows implementation starts a helper gated on stdin, assigns it to a
non-inherited kill-on-close job, then allows it to launch one headless renderer
at a time. The job permits two processes: helper and renderer. Normal exit,
exceptions and a watchdog terminate the job, reap the helper and verify zero
active job processes. Abrupt diagnostic exit closes its sole job handle and
kills both descendants. The CPU-only contract exercises these paths, early
helper exit, assignment failure, opt-in behavior, invalid bounds and exact
comparison accounting; its load fixtures execute Python sleepers, not GPU work.
Job lifecycle checks require Windows; portable comparison/worker-loop checks
still run elsewhere.

Load repeatedly renders an enlarged copy of the same synthetic scene at
2048×1536, adapter zero, headless GI, 1,024 samples and the standard debug layer.
It uses existing renderer options and shaders. `--load-samples` accepts 1..4096;
`--load-seconds` is a finite hard lifetime of 5..600 seconds (default 300),
including warmup. Each render also has a 60-second timeout. One successful
render with positive GPU trace time is required before measuring RR. Helper
exit or deadline expiry fails execution, with completed checkpoints retained;
it cannot silently label an unloaded remainder as loaded. Cleanup also stops
an in-flight renderer. `gpu-load.json`, `load-state.json` and
`load-settings.json` retain settings, scene/executable/shader hashes, completed
native render reports, monotonic intervals and cleanup results.

For example, use the same Release load executable for both RR configurations:

```powershell
python tools/rr_repeatability.py run --probe build/rr-sdk-probe/Debug/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --inputs build/rr-repeatability-inputs --out build/rr-repeatability-debug-loaded --with-gpu-load --load-dxr build/rr-sdk-probe/Release/rrt_dxr.exe --load-seconds 300 --load-samples 1024
```

Run the matching command without the load options and with a new output
directory for the unloaded condition; substitute the Release probe to repeat
both conditions in Release. Repeat these pairs in new directories, alternating
condition order, without running other GPU regressions concurrently. The
existing `--quiet-seconds` remains a host pause; load continues through it.
"Unloaded" means no load started by this diagnostic, not verified exclusive
GPU access. Live-helper checks before/after workers and completed GPU timings
establish concurrent workload execution, not continuous utilization, exact
GPU scheduling overlap, residency, clocks or power behavior.

## Controlled load follow-up (2026-10-23)

The operator reports that the original failing session had another process
using this GPU; that historical contention was not instrumented by these
diagnostics. This follow-up tests the hypothesis with a deliberately added
second workload, rather than assigning a cause to the historical observations.

Three complete matrices per build and condition use one newly prepared input
set and fixed executables throughout. Debug runs unloaded/loaded in rounds one
and three, loaded/unloaded in round two; Release reverses each of those orders.
All runs are serial. The Release load executable is shared by both builds.
The standard two-second host pauses are retained in every matrix, with load
continuing during pauses. Final matrix counts exclude all development attempts.

| RR build | Condition | Round 1 match / differ | Round 2 match / differ | Round 3 match / differ | Total match / differ |
|---|---|---:|---:|---:|---:|
| Debug | Unloaded | 25 / 0 | 25 / 0 | 25 / 0 | **75 / 0** |
| Debug | Loaded | 25 / 0 | 25 / 0 | 25 / 0 | **75 / 0** |
| Release | Unloaded | 25 / 0 | 25 / 0 | 25 / 0 | **75 / 0** |
| Release | Loaded | 25 / 0 | 25 / 0 | 25 / 0 | **75 / 0** |

That is **180 RR workers / 1,044 RR dispatches / 300 exact comparisons** across
the twelve final matrices. Every comparison's input records, matrices, packed
textures and dispatch metadata match. The six loaded runs each complete 13
large renders: **78 completed load renders**, including warmup, each with 1,024
dispatches and 754,993,008 requested buffer bytes. Every load job is verified
empty after cleanup; none expires its deadline. The in-flight load render is
terminated at matrix exit and is not counted as completed work.

Full byte comparisons across runs also match, with exact input/dispatch
controls in every pair:

| Pairing | Match | Differ |
|---|---:|---:|
| Loaded vs unloaded, corresponding round/build/case | 90 | 0 |
| Round one vs rounds two and three, same build/condition/case | 120 | 0 |
| Debug vs Release, corresponding condition/round/case | 90 | 0 |

These comparisons reuse the same outputs; they are not independent trials.
Concatenating raw RGBA payloads in sorted case-label order, then frame order,
produces the same **17,104,896-byte** stream in all twelve matrices. Its SHA-256,
the shared inputs and the fixed executable identities are:

| Identity | SHA-256 |
|---|---|
| RGBA payload stream, every final matrix | `b7f164e215bea9cda984f12ab16e3ca77bcb4792d776c2ff8480c22c0dec8a60` |
| Stationary recording | `1f2346a6bb326d8c75717a5ac555252036e12fa59a81bdfb336ef46110b13ea7` |
| Moving recording | `ddd7a9dd8eaa2a01147e90a57008b0c638f290f0fd190bfe7820c7f172dbe8f5` |
| Fresh recording | `33881c5ff1b9b46b8e18803fdf701802a7644e11f72678d7138239146fdc9705` |
| Debug RR probe | `99c26364a974bdc9f5eb426eb3bcc01c7e9f390c19a7896591fdda70e64271c3` |
| Release RR probe | `7ed5b0e0e3e11eb9b87afabb6adb72a54ec151763e18bc8592b4da47d9147634` |
| Release load renderer | `5254bbd1943b59c17054f94d0f89ccbf6320602ed5d56b9d94a557b5027bd17c` |
| Aggregate `experiment.json` | `45af24af80828a3f4592b81346545639efcb83d10954b5d7a4c6790ddec60db5` |
| `payload-identities.json` | `860e400e39924eee3da5c52d3a7a7e8cdd46cfdca2a8095c6356bb79b54f63c6` |

The aggregate binds all twelve individual verification-report hashes and
retains every cross-run per-frame comparison; individual reports retain input,
output and per-frame hashes. Payload identities additionally check unchanged
whole-file and per-frame hashes before hashing the concatenated streams. Load
scene and shader hashes, completed native timings, check intervals and actual
binaries are retained in the follow-up archive below.

**Load sensitivity is not reproduced in this bounded sample.** No cause or fix
is established. This tests the five prepared diagnostic modes above, not every
historical failing input under load. The original archived perspective witness
is not replayed under load in this follow-up. The workload also introduces CPU,
memory-transfer and residency activity; it does not isolate GPU scheduling.
Different concurrent applications, intermittent effects, clocks and broader
GPU/driver combinations remain untested. Earlier failures remain valid evidence.
Quality is still `not-qualified`, and raw SDK acceptance is still `failed`.

Two completed calibration matrices (one smaller workload, one final workload)
each had 25 matches / 0 differences. A preceding scene-construction error
stopped before load started. All three development attempts are retained
separately and excluded from the final counts above.

## Follow-up validation

Final CTest summaries for this follow-up, with no skipped tests:

| Subset | Configuration | Final summary | Total test time |
|---|---|---|---:|
| SDK + RR contracts | Debug | `100% tests passed, 0 tests failed out of 13` | 328.56 s |
| SDK + RR contracts | Release | `100% tests passed, 0 tests failed out of 13` | 327.55 s |
| Cheap CPU-only | x86 Debug | `100% tests passed, 0 tests failed out of 15` | 14.20 s |
| Cheap CPU-only | x86 Release | `100% tests passed, 0 tests failed out of 15` | 14.31 s |

Both RR subsets run after the matrices, with the added workload stopped.
The unchanged `rr_dispatch`, `rr_sequence`, `rr_recorded_dispatch` and
`rr_sequence_quality` controls pass in both builds. The quality harness still
retains and rejects positive exact-black output: maximum RGB
**0.000010967254638671875** in both builds. These passes validate the harness
and strict controls, not general image quality or raw SDK acceptance.

The CPU-only comparison/load contract also passes with `python -O`. Published
reference and changed-file privacy checks pass. The existing two CPU evidence
tests consume a restored local position ledger; no missing-evidence skip is
counted. **Display tests are not run and are not counted in this follow-up.**
The earlier display failures below remain historical results. No full renderer,
proxy, cross-GPU or broader optional-SDK qualification is claimed.

## Follow-up evidence retention

The appended ledger record binds
`rr-gpu-load-validation-20261022-232642.tar.gz`: **1,392 files**,
1,083,571,874 uncompressed bytes, 70,360,447 archive bytes, SHA-256
`6a048228797ab4981b36f91d2f92f8326321d24c986d81fbca1e46a95623db84`.
The ledger-bound `check` verified all 1,392 files with no problems. The archive
timestamp is UTC; the follow-up date above is local time.

The external archive retains all final matrices and their checkpoints, inputs,
per-frame/cross-run comparisons, payload identities, load settings and native
timings, development attempts, final CTest logs and RR artifacts/reference
arrays, implementation snapshots, actual binaries/shaders and the pinned SDK
subset with its license. Documentation snapshots precede insertion of the
archive's own digest. The public ledger contains metadata only.

To inspect or replay with the retained inputs and binaries, restore into a new
directory; the new run's output directory must also be new:

```powershell
python tools/evidence_archive.py check ARCHIVE --ledger docs/EVIDENCE_LEDGER.jsonl
python tools/evidence_archive.py restore ARCHIVE --out build/rr-gpu-load-restored
python tools/rr_repeatability.py run --probe build/rr-gpu-load-restored/binaries/Debug/rrt_rr_probe.exe --sdk-bin build/rr-gpu-load-restored/sdk/Kits/FidelityFX/signedbin --inputs build/rr-gpu-load-restored/inputs --out build/rr-gpu-load-debug-new --with-gpu-load --load-dxr build/rr-gpu-load-restored/binaries/Release/rrt_dxr.exe --load-seconds 300 --load-samples 1024
```

## Earlier observations and limits

Measured on 2026-10-23 in Windows session 0 with one RX 9070 XT, driver
32.0.32015.7029, VS 2022/MSVC 19.44, Python 3.12.10 and NumPy 1.26.4.
The pinned SDK subset was restored from the documented commit with its license;
both DLL hashes match the existing pins. Debug and Release builds succeed.

The initial matrix completed **15 workers / 87 dispatches per configuration**.
All **25 exact comparisons per configuration** matched, including repeated
fresh processes, same-context resets, recreated-context resets, single/sequence
compatibility, stationary recorded/sequence compatibility and moving reset/fresh
segments. Corresponding RGBA payloads also match across all 15 Debug/Release
case pairs. The quiet-interval samples match their initial samples; this does
not establish a relationship to GPU idleness or clocks.

The prior sequence archive was checked against its existing ledger before
recovering the original failing lateral/reset/fresh recordings and outputs.
All 421 files verified with no problems. This preserves the earlier observed
failure as evidence rather than treating a new passing sample as its correction.

The archived witness uses the perspective fixture from the preceding sequence
quality run, including its exact original source scene and lateral/reset/fresh
recordings. Its inputs are not regenerated. The retained replay script performs
three launches per recording with the same consecutive/host-pause ordering.
The archived outputs are decoded against their original recordings before
comparison. The archive's original lateral/repeat mismatch is independently
reconfirmed (maximum RGB difference 0.00830078125), as is its reset/fresh mismatch
(0.00799560546875).

All nine current witness comparisons are exact in each configuration, and all
nine corresponding Debug/Release case pairs match. Against historical
outputs, each new lateral run differs from the old lateral output (maximum
0.00836181640625) and also from the old repeat output (0.01123046875). The old
reset output is reproduced, while the old fresh output differs in both builds
(six historical mismatches per build: three lateral and three fresh). These numbers
compare RR outputs, not errors against a reference. Full per-frame counts and
hashes are retained rather than substituting these maxima for exact equality.

All 11 native RR source files match the archived base revision byte-for-byte;
the preparation shader hashes also match. The rebuilt native probe and renderer
executable hashes differ from the prior reported binaries in both configurations.
Replaying the same input therefore does not hold historical executable identity
fixed. These observations cannot assign the difference to the SDK, application,
compiler/build, allocation placement, driver, clocks or scheduling. No driver or
SDK binary modification was made during this task.

The current contexts retain 20,971,520 callback bytes peak and 1,900,544 external
bytes, with the existing 64 MiB / 8 MiB ceilings and validated releases. These
are tracked/requested allocations, not total GPU residency.

## Earlier validation

Final CTest summaries, with no skips in these subsets:

| Subset | Configuration | Final summary | Total test time |
|---|---|---|---:|
| Focused SDK + RR contracts | Debug | `100% tests passed, 0 tests failed out of 13` | 332.94 s |
| Focused SDK + RR contracts | Release | `100% tests passed, 0 tests failed out of 13` | 325.37 s |
| Cheap CPU-only | x86 Debug | `100% tests passed, 0 tests failed out of 15` | 7.92 s |
| Cheap CPU-only | x86 Release | `100% tests passed, 0 tests failed out of 15` | 8.13 s |
| Representative display attempts | x86 Debug | `0% tests passed, 2 tests failed out of 2` | 0.56 s |
| Representative display attempts | x86 Release | `0% tests passed, 2 tests failed out of 2` | 0.56 s |

The focused subset includes the prior eight-test sequence-quality subset plus
the new comparison contract and four existing native/settings CPU contracts.
`rr_dispatch`, `rr_sequence`, `rr_recorded_dispatch` and `rr_sequence_quality`
all pass their unchanged exact controls in both current runs. The original
quality test still records positive exact-black output: maximum RGB
**0.000010967254638671875** in both builds. Its passing CTest validates retention
and rejection of that quality failure, not acceptance of the biased output.

The CPU subset includes trace/position/mod/material, generation/version,
published-reference, budget, evidence registration/archive, restored-tree,
workbench and exact-comparison contracts. Its two existing private-evidence CPU
tests run against a restored position ledger supplied through the documented
CMake cache input. No missing-evidence skip is counted as a pass. The published
file-set check uses a disposable index containing the proposed new files; the
real index and refs are unchanged. An initial registration error exposed by the
synthetic CMake fixture is fixed, with the failed attempts retained separately
from the final passing runs.

Display work **cannot complete in this session**: `d3d9_smoke_sample_run`
returns device error `0x8876086c`, and `dxr_presentation` returns native swapchain
error `0x887a0022`. These are recorded failures, not display passes or full
renderer/proxy qualification. Other display tests, the full x86/x64 renderer
suites and other optional SDK experiments were not rerun.

## Earlier evidence retention

`docs/EVIDENCE_LEDGER.jsonl` records the external archive
`rr-repeatability-validation-20261022-224102.tar.gz`: **849 files**,
899,889,356 uncompressed bytes, 57,139,962 archive bytes, SHA-256
`48e2badd93a6075de7f7e836c9c4ec61f8ec722ee033059d0bd9ca381f7bb4f5`.
The final ledger-bound `check` verified all 849 files with no problems. The
archive timestamp is UTC; the measurement date above uses local time.
The archive retains input/output bundles, all worker/renderer reports,
per-frame exact comparisons and checkpoints, historical controls, cross-build
checks, reference arrays from the regressions, development/final CTest logs,
source snapshots and the actual current native binaries/shader with their
identities. The ledger contains names, counts, sizes and hashes only.

To replay the original witness from the retained archive, first build the pinned
worker as above, then restore the archive into a new directory with the recorded
layout. These commands assume that layout is restored at the path below; replay
outputs must be new:

```powershell
python tools/evidence_archive.py check ARCHIVE --ledger docs/EVIDENCE_LEDGER.jsonl
python tools/evidence_archive.py restore ARCHIVE --out build/rr-repeatability-validation
python build/rr-repeatability-validation/replay-witness.py Debug build/rr-witness-debug-new
python build/rr-repeatability-validation/replay-witness.py Release build/rr-witness-release-new
```

No SDK-internal cause has been established. Exact equality on a bounded sample
cannot disprove intermittent variability. The exact-zero bias, textured/PBR
regressions, SDK reporting defects, cross-GPU behavior and general quality
acceptance remain open. Context recreation remains the existing offline reset
policy; these measurements do not establish it as a repeatability fix.
