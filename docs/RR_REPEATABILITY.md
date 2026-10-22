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

## Observations and limits

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

## Validation

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

## Evidence retention

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
