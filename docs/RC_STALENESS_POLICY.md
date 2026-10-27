# Radiance Cache staleness policy and stale-lighting test plan

Status: **design proposal**, 2026-10-26. Documentation only: no code, shader,
test, build or format change accompanies this page. It is the design response to
shortlist item 3 in the [Remix 1.6 gap analysis](REMIX_1_6_GAP_ANALYSIS.md#3-cache-staleness-policy-and-stale-lighting-test-item-3).

## Summary

The Radiance Cache path has one invalidation mechanism: an epoch is either
continued with all retained training state or reset to nothing. There is no way
to say "this entry is stale, that one is valid". This page proposes a policy
that makes staleness **expressible and observable without weakening the exact
reset evidence**, and a test plan that exercises stale lighting on the existing
128x96 fixture.

The recommendation is deliberately split:

- **Correctness (default for the opt-in RC path): generation-tagged hard
  reset.** Scene, lighting, material and settings each get an explicit
  generation. Any generation change forces `reset`; `continue` across a
  generation change is rejected. This closes the stale-lighting failure class
  exactly and keeps the existing zero-delta reset comparisons.
- **Observability (default off): per-entry age and generation tags.** These are
  renderer-side metadata. They do not enter the provider's 44-byte record, the
  `RCRPATH1` artifact, or the five provider buffers. They let a report state
  which entries were stale and which were refused.
- **Efficiency (default off, deferred): age-bounded camera continuation and
  selective re-seed.** These are the only ways to express partial staleness
  against an opaque provider, but they need evidence that does not exist yet.
  Weighted decay is rejected as the primary mechanism because it hides stale
  state in the composite rather than removing it.

No part of this proposal enables cache rendering, applies a candidate by
default, or changes an existing byte-exact result.

## Scope and non-goals

In scope:

- the renderer-owned policy around the FidelityFX Radiance Cache provider;
- the `RcFrameAdmission` identity and `RcEpochProtocol` command sequence;
- the `RCRPATH1` path rows and the guarded composite;
- a synthetic stale-lighting scenario and its pass/fail metrics;
- the split between pure-Python checks and Windows/D3D device checks.

Out of scope:

- modifying the signed provider, its 44-byte input record, its 12-byte output
  record or its five external buffers;
- adding a field to `RCRPATH1` or changing its 1,573,120-byte layout;
- D3D9 `Present`/`Reset` integration or live game injection;
- a quality, convergence or performance claim for the cache;
- enabling `rc_rendering` or making the candidate authoritative by default.

## Current mechanism, as it is

### Identity and reset

`RcFrameAdmission::Identity` has five caller-issued revisions: `scene`,
`camera`, `lighting`, `material` and `settings` (`src/dxr/rc_admission.h:6-13`).
`Begin()` sets `reset` when there is no completed epoch or when the identity
differs from the last completed one (`src/dxr/rc_admission.h:28-31`). Repeated
notifications for the same active or pending identity add no work; a newer
identity replaces the pending one and increments `coalesced`
(`src/dxr/rc_admission.h:20-27`).

The queue is unit-tested for every field: the loop at
`src/dxr/rc_admission.h:61-66` increments `scene`, `lighting`, `material` and
`settings` in turn and requires a reset each time. That test proves the queue
can express the distinction. It does not prove the renderer ever issues those
revisions.

### Epoch commands

One parent command is sent per acknowledged epoch on the shared fence
(`src/dxr/rc_epoch_protocol.h:3-6`). The four values per ticket are
`reset`, `continue`, `stop` and `ack` (`src/dxr/rc_epoch_protocol.h:7-17`).
`MaxEpochs` is 64 (`src/dxr/rc_epoch_protocol.h:9`), so a periodic-reset or
aging schedule must either fit inside 64 epochs or stop and restart the
session.

### What the provider exposes

The provider's external interface is fixed: five buffers, 716,808 bytes total,
with a 44-byte prediction/training input (`src/dxr/rc_dispatch.h:3-11`) and a
12-byte RGB output. The layout is documented in
[the Radiance Cache foundation](RADIANCE_CACHE.md#next-renderer-owned-slice).
There is **no age, timestamp, generation or per-entry invalidation field** in
that interface. The provider is a black box that retains online training state
until reset ([persistent training](RADIANCE_CACHE_TRAINING.md)).

Whether the provider ages samples internally is not stated in the pinned SDK
material this repository cites. That is marked **(uncertain)** and the policy
below does not depend on it.

### What the renderer sends

`rc_paths.hlsl` computes the primary direct term with the current light colour
(`src/dxr/rc_paths.hlsl:36-37`), the secondary target radiance with the current
light (`src/dxr/rc_paths.hlsl:52`), and the no-cache indirect term as
`weight * target` (`src/dxr/rc_paths.hlsl:62`). A lighting change therefore
changes `targetRadiance`, `noCacheIndirectDistance` and
`directBackgroundPrimaryValid` in the path rows, while the secondary position,
normal, view direction, albedo and throughput are unchanged for the same
camera and geometry.

The `RCRPATH1` header binds a settings digest that already includes seed,
shadows, flags, light direction, intensity, light colour, ambient and sun
radius (`src/dxr/rc_paths.h:66-69`). That digest is artifact identity, not
admission identity: the provider never sees it.

### What the live paths actually bump

This is the concrete gap. Outside the unit test:

- the native camera notification bumps `camera` (`src/dxr/main.cpp:754`);
- the renderer-session test bumps `settings` at epoch 4
  (`src/dxr/rc_renderer_session.h:42`);
- `lighting` and `material` are never incremented by a renderer path;
- `scene` is never incremented by a renderer path.

The shared-session document already names the consequence: "adding
lighting/material identity policy and back-pressure" is outstanding
([cross-process shared resources](RADIANCE_CACHE_SHARED.md#live-changed-frame-fence-session-and-buffer-reuse)).
The camera case is covered and proven: a camera offset produces a fresh
child/context and an exact reset ([isolated live transaction](RADIANCE_CACHE_LIVE.md#persistent-frame-evidence)).
The lighting case is not.

## 1. Failure class: stale lighting after a scene or light change

### The pipeline scenario

Use the canonical 128x96 legacy-diffuse fixture. Render it once with the
default white light and once with the colour mutation the temporal path
already uses: from white, red is flipped to `0.2` and green/blue are set to
`0.3`/`0.4`, giving `lightColor = (0.2, 0.3, 0.4)`
(`src/dxr/main.cpp:824`). The two
`RCRPATH1` exports must have the same 172 queries, the same secondary positions,
normals, view directions and albedos, and the same throughput. Only the target
radiance, the no-cache indirect term and the direct/background term should
differ; the test asserts this invariant before using the pair.

Now run a persistent provider session:

1. epoch 0: `reset`, train on the white-light paths;
2. epoch 1: the light changes to `(0.2, 0.3, 0.4)`, the renderer regenerates
   the paths, and the session sends the next command;
3. epoch 2: a fresh session trains on the changed-light paths, as the reference.

At step 2, `RcFrameAdmission` has no lighting revision to compare. The pipeline
never issues one, so `Begin()` sees the same identity and returns
`reset = false` (`src/dxr/rc_admission.h:30`). The worker receives `continue`
and the provider retains the model trained under white light. Inference returns
the old prediction, and the guarded composite computes

```text
candidate = direct(changed light) + throughput * prediction(old light)
```

which is exactly the formula documented in
[renderer-exported paths](RADIANCE_CACHE_PATHS.md#source-contract). The frame
is a blend of two lighting states: the direct term flips immediately, the
indirect bounce does not.

The stale term does not wash out quickly. The provider uses a prediction-weight
smoothing of `0.99` and a learning rate of `0.002`
([persistent training](RADIANCE_CACHE_TRAINING.md#sequence)). One 512-sample
batch moves the prediction by a pairwise MSE of `2.97242e-9` and a maximum
absolute delta of `7.62939e-5` on the synthetic fixture
([persistent training](RADIANCE_CACHE_TRAINING.md#measurement)). The old
contribution is therefore not diluted on the frame where the light changes; it
persists across the epochs that follow.

A scene change is worse. The provider's position input is normalized against
the scene bounds (`src/dxr/rc_compact.hlsl:40`, mirrored by the CPU decoder at
`src/dxr/rc_path_sequence.h:50`). After a bounds change, the same normalized
coordinate denotes a different world point. Continuing a
session across a scene change applies learned radiance to the wrong surface,
even if the camera and light are unchanged. The `scene` revision exists in the
identity but is never issued by a renderer path.

### Why this is not already caught

- `--rc-paths` rejects `--lighting-test` outright
  (`src/dxr/main.cpp:987`). The existing lighting diagnostic proves that the
  analytical temporal history resets on a light change
  (`src/dxr/main.cpp:826`), but it cannot be combined with the RC path export.
- The RC path export requires one sample, GI mode, no temporal, no denoise and
  no material sidecar (`src/dxr/main.cpp:987`), so it is a separate offline
  pipeline rather than a frame of the temporal path.
- The RC reports carry no age or generation field. `RcSequenceResult` reports
  reset exactness and changed-value counts (`src/dxr/rc_sequence.h:39-43`), and
  the step record reports counters, hashes and pass flags
  (`src/dxr/rc_sequence.h:5-16`), but not why an entry was admitted.
- The current policy is all-or-nothing by construction. Even when the caller
  does issue `lighting`, the only action available is a full reset
  (`src/dxr/rc_admission.h:30`), which discards every valid sample along with
  the stale ones.

### What "partial staleness" would mean here

The current renderer path has one directional sun plus a scalar ambient
(`src/dxr/render.hlsl:95-96`, `:155`). A light change is therefore
global: every indirect target changes. "Selective invalidation by light" has no
non-empty valid subset to keep. "Selective invalidation by region" is meaningful
for camera disocclusion and for future local lights, not for a global sun
change.

That asymmetry matters for the recommendation. The first thing to fix is not a
decay curve; it is the missing generation and the missing fail-closed check.
Partial retention is a later optimization, and it should not be used to excuse
a stale global light.

## 2. Options for sample aging and per-entry staleness

All options below are renderer-side unless stated otherwise. The provider
cannot accept a per-entry age field, so "aging" can only mean one of:

- metadata that decides whether an entry may be submitted or composited;
- a reset plus re-seed from a retained subset;
- a blend that reduces a stale prediction's visible weight.

Memory figures use the current capacities: 12,288 inference samples and 512
training samples (`src/dxr/rc_probe.cpp:27-28`), a 49,152-byte pixel map and a
196,608-byte candidate/error readback
([cross-process shared resources](RADIANCE_CACHE_SHARED.md#renderer-owned-gpu-direct-path)).
The provider's 32 MiB ceiling covers callback-managed allocations only
([Radiance Cache foundation](RADIANCE_CACHE.md#live-support-and-lifecycle));
renderer buffers are outside it but are counted by the renderer's allocation
accounting (`src/dxr/rc_renderer_session.h:38`).

### A. Status quo: full epoch reset only

**Mechanism.** Any identity change resets everything; an unchanged identity
continues with everything (`src/dxr/rc_admission.h:28-31`).

**Memory.** Zero.

**Determinism.** Exact. Reset restores the baseline byte-for-byte, and repeats
are identical ([persistent training](RADIANCE_CACHE_TRAINING.md#measurement)).

**Effect on existing coverage.** None.

**Verdict.** Necessary as the enforcement action, insufficient as a policy.
It cannot express partial staleness, and it silently continues when a caller
forgets a revision.

### B. Per-entry age counters

**Mechanism.** A renderer-side `u16` or `u32` age per inference slot, and
optionally per training slot. Age is incremented once per logical epoch for
entries that were not refreshed, and reset to zero when the renderer submits a
fresh target for that slot. Age gates submission and compositing; it does not
change the provider's input.

**Memory.** `12,288 x 2 = 24,576` bytes for `u16`, or `12,288 x 4 = 49,152`
bytes for `u32`. Training adds `512 x 4 = 2,048` bytes (`u32`) or `1,024`
bytes (`u16`). Worst case is about 51,200 bytes, roughly 7% of the 716,808-byte
provider interface and 0.16% of the 32 MiB provider ceiling. If the age buffer
is shared, it adds one shared resource and one allowlisted handle; the current
contract asserts exactly five shared buffers and six handles
([cross-process shared resources](RADIANCE_CACHE_SHARED.md#contract),
tests/verify_rc_path_sequence.py:45). Keeping it renderer-local avoids that
change.

**Determinism.** Integer ages are deterministic if they are driven by a logical
epoch counter, not by wall-clock time or a variable frame rate. The provider
inputs are unchanged, so the existing hashes are unchanged when the policy is
inactive.

**Effect on existing coverage.** None when off. When on, an age violation is a
new failure mode that must be reported; it does not by itself remove stale
provider state.

**Verdict.** Useful as diagnostics and as a gate. Not sufficient alone: an age
counter can refuse to composite an entry, but the provider still returns a
stale prediction for it.

### C. Epoch- or generation-tagged entries

**Mechanism.** Each entry carries a tag for the generation of the input that
produced its target: `scene`, `lighting`, `material` or `settings`. The tag can
be packed with the age into one `u32` (for example 16 bits of age, 16 bits of
generation) or kept as a separate `u16`. A composited entry must match the
current generation; a mismatch is rejected, and a session-level mismatch forces
`reset`.

**Memory.** Same order as option B: 24,576 to 49,152 bytes for inference, plus
at most 2,048 bytes for training. No provider-side cost.

**Determinism.** Integer tags are deterministic. The tags do not enter the
44-byte record, so the provider sees exactly the same bytes as today. The
fail-closed check is deterministic.

**Effect on existing coverage.** None when off. When on, it converts a silent
stale composite into a reported rejection. It does not weaken reset exactness;
it strengthens the reason a reset is required.

**Verdict.** The right policy substrate. It is the smallest change that makes
"partially stale" expressible and testable, and it composes with option A.

### D. Weighted decay in the composite

**Mechanism.** Multiply the prediction by a per-entry or global weight before
compositing, for example `candidate = direct + throughput * prediction * w`,
with `w` decreasing with age. A global `w` costs nothing; a per-entry `w` costs
one float per query.

**Memory.** Zero for a global weight, or 49,152 bytes for a per-entry float.

**Determinism.** Float blending is deterministic only for a fixed order and a
fixed device/driver. The project already treats provider output as repeatable
on the tested adapter/driver rather than byte-exact across all drivers
([DXR viewer](DXR_VIEWER.md#sampling)). A decay weight changes candidate pixels
immediately, so it breaks the candidate SHA-256 and the applied-pixel audit
([cross-process shared resources](RADIANCE_CACHE_SHARED.md#guarded-output-and-scheduled-native-presentation)).

**Effect on existing coverage.** Breaks the candidate identity, the
`172 applied / 12,116 unchanged` audit, and the post-training hashes. It does
not remove the stale provider state; the next inference still returns the old
prediction, and the decay only hides it. It also interacts with the provider's
own `0.99` smoothing.

**Verdict.** Reject as the primary mechanism. It is a tuning knob that makes a
correctness failure less visible, which is the opposite of the stated goal.

### E. Selective invalidation by region or light

**Mechanism.** Since the provider has no partial reset, selective invalidation
means: reset the provider, then re-seed training from a retained archive of
rows whose tags still match. A region mask selects which rows are retained or
re-submitted; a light mask would do the same per light.

**Memory.** A per-pixel region mask is 12,288 bytes (one byte per pixel); an
8x8 tile mask is 192 bytes. A retained training archive at the current
capacity is `512 x (44 + 12) = 28,672` bytes, plus tags. The total is roughly
43,000 bytes with the per-pixel mask, or 31,000 with the tile mask. If the
archive exceeds 512 rows it cannot be
re-seeded in one batch; it must be sampled or spread over epochs, which changes
the training order and the resulting hashes.

**Determinism.** Deterministic only if the retained subset and its order are
fixed. The existing contract admits the first `min(valid, 512)` rows in
deterministic pixel order ([renderer-exported paths](RADIANCE_CACHE_PATHS.md#source-contract));
a re-seed must preserve that rule or it becomes a new, undocumented sampling
policy.

**Effect on existing coverage.** The reset baseline stays exact, but every
post-training hash changes because the training sequence changes. The
persistent-epoch amortization evidence (`426.558 ms` versus two independent
launches, [cross-process shared resources](RADIANCE_CACHE_SHARED.md#stable-frame-context-amortization))
would need to be re-established for the re-seed burst.

**Verdict.** The only option that actually removes stale state without
discarding everything, but it has no valid subset for a global light change
today. Defer until a multi-light capture exists and option C has produced
evidence.

### Comparison

| Option | Renderer bytes (max) | Provider bytes | Determinism | Existing byte-exact coverage | Verdict |
|---|---:|---:|---|---|---|
| A. Full reset | 0 | 0 | Exact | Unchanged | Enforcement action |
| B. Age counters | ~51,200 | 0 | Integer, logical epochs | Unchanged when off | Diagnostics and gate |
| C. Generation tags | ~51,200 | 0 | Integer, logical epochs | Unchanged when off | Recommended substrate |
| D. Weighted decay | 0 or 49,152 | 0 | Float, device-dependent | Breaks candidate and applied-pixel hashes | Rejected as primary |
| E. Selective re-seed | ~31,000-43,000 | 0 | Deterministic only with fixed subset/order | Breaks post-training hashes; reset stays exact | Deferred |

## 3. Recommendation and staged rollout

### Policy

Adopt **C + A**: generation-tagged entries with a hard reset as the enforcement
action, and age counters (B) as diagnostics. The decision table is:

| Change | Generation | Action | Reason |
|---|---|---|---|
| Scene geometry or bounds | `scene` | Hard reset | Normalized positions denote different world points |
| Sun direction, sun radius, light colour, intensity, ambient, shadows | `lighting` | Hard reset | Every indirect target changes; one global sun |
| Material set or sidecar | `material` | Hard reset | No valid subset today; RC paths reject sidecars |
| Seed, denoise, temporal, render scale, other render settings | `settings` | Hard reset | Path realization or accumulation changes |
| Camera only | `camera` | Reset by default; optional `continue` when every composited entry has `age <= max_age` | Positions are camera-independent; targets are view-dependent and unmeasured |
| No change | none | `continue` | Existing behaviour |

The lighting generation must be derived from the same tuple that already feeds
the path settings digest (`src/dxr/rc_paths.h:66-69`), split so that lighting
and render settings are distinct. Deriving it mechanically is the point: the
failure class is a forgotten manual bump, so a caller-issued integer that
nothing computes is not a fix.

`max_age` defaults to `0`. A stable identity re-submits the same rows every
epoch, so their age stays zero and `continue` remains allowed. An entry that
was not refreshed in the current epoch has age greater than zero and is not
composited. This makes the default stricter than today for off-screen or
unrefreshed entries, but it does not change any existing scenario, where every
epoch refreshes its rows.

### Why not the alternatives

- **Weighted decay** hides the stale term and breaks the candidate audit; it
  would make the project's strongest RC evidence weaker.
- **Selective re-seed** has an empty valid subset for a global light change and
  an all-invalid set for a scene change. It is a real optimization for camera
  disocclusion and future local lights, not a fix for stale lighting.
- **Provider-side aging** is not available: the interface has no field for it,
  and the provider is pinned and hash-verified.

### Staged rollout

**Stage 0 — policy and pure-Python contract (this document).**
No behaviour change. Declare the table above, add a pure-Python policy contract
and the metric definitions, and leave every existing test untouched. Default
off. Everything stays byte-identical. **Implemented:** the reference model is
[tools/rc_staleness.py](../tools/rc_staleness.py) and the contract test is
[tests/verify_rc_staleness_contract.py](../tests/verify_rc_staleness_contract.py).

**Stage 1 — generation wiring and diagnostics (opt-in RC mode only).**
Derive `scene`, `lighting`, `material` and `settings` generations from the
renderer's own inputs. Add report fields for the current generation, the
maximum observed age and the number of rejected stale entries. Do not change
compositing. The canonical scenarios have constant generations and no stale
entries, so their hashes must remain identical.

**Stage 1 status: written, not yet validated on a device.**
[`src/dxr/rc_generation.h`](../src/dxr/rc_generation.h) derives the four hard
generations from the frame's lighting and settings fields and from the scene
digest, and replaces the constant `{1,1,1,1,1}` identities in the scheduled
presentation and the renderer session. The values are only compared for
equality, exactly like the constants, so behaviour and every hash must be
unchanged. The renderer-session report gains `generations` and
`hard_generation_changes` (expected `1`, the scripted settings bump). The C++
derivation is pinned to the Python model by known answers: `VerifyRcGenerations()`
checks them on the device and `tests/verify_rc_staleness_contract.py` requires
the header to carry the same numbers. The maximum-age and rejected-stale-entry
fields are deferred: per-entry ages do not exist until Stage 2 needs them, and
reporting a constant zero would claim a measurement that is not made. The
material generation uses a fixed tag when there is no sidecar and the sidecar
path otherwise, a placeholder until a content digest exists. To validate, run
the RC path sequence contract on the RX 9070 XT and confirm the existing hashes
are unchanged.

**Stage 2 — enforcement (opt-in RC mode only).**
Reject `continue` when any generation differs, and fail closed with `reset`.
This changes only the bug case. The existing camera, settings and reset
scenarios must still produce the same hashes, because their generations are
constant within each scenario.

**Stage 2 status: implemented and validated on a device (2026-10-27, RX 9070 XT, driver 32.0.32015.7029).**
`RcFrameAdmission::MustReset` is now the single decision (any identity change, including camera, or no completed epoch resets) and
[`src/dxr/rc_staleness.h`](../src/dxr/rc_staleness.h) re-derives it at the command boundary through `RcStalenessGate::Enforce`: a
Continue is never signalled across a scene, lighting, material, settings or camera change, and a disagreeing admission is refused
(fail closed). `VerifyRcStalenessGate()` checks the table on the device. The existing renderer session routes its commands through
the gate and its hashes are unchanged. The test-only `--rc-staleness-test` runs the stale-lighting scenario in one provider context
([`src/dxr/rc_staleness_session.h`](../src/dxr/rc_staleness_session.h)): epoch 0 trains at the default light, epoch 1 changes only
the light intensity, epochs 2 and 3 repeat that light under new camera revisions. `--rc-staleness-force-continue` is the negative
control and is valid only with that test. The device contract is `tests/verify_rc_staleness_device.py` (`rc_staleness_device`,
`SKIP_RETURN_CODE 77`; it also writes `staleness.json`). The policy run resets at every change and matches the fresh session exactly
(`stale_mse`, `stale_max_abs`, `stale_fraction` all 0, 516 compared values); repeats are exact.

**Fixture and negative control.** Under the default light every training target of the canonical scene is exactly zero: the secondary
hits are on surfaces that light does not reach (the primary hits are lit, so the exported artifacts and candidate hashes still change),
so no lighting change can alter the provider's trained output. A first Stage 2 run reported that as the provider being independent of
lighting. It is a property of the fixture, not of the provider. The contract therefore runs with a sideways light
(`--light 1 0 0 --light-intensity 5 --rc-training-batches 2`), which makes 90 of 172 targets non-zero at the default intensity. There
the policy run still matches the fresh session exactly, and the forced-continue control shows stale values: `stale_fraction` 1.0 (516
of 516 values closer to the old epoch than to the fresh one), `stale_mse` 3.4e-7, `stale_max_abs` 6.6e-4. The negative-control gate in
section 4 is met and the contract asserts it. The effect is small in absolute terms because the provider learns slowly, and it is not
monotonic in the setting (at intensity 20 the fraction fell to 0.25 with two batches), so the settings are tuned and recorded here.
Untested: a scene with more than one light, and the visible composite. The ledger entry is `rc-staleness-stage2-validation-20261027-072108.tar.gz` in `docs/EVIDENCE_LEDGER.jsonl`.

**Stage 3 — age-bounded camera continuation (default off).**
Add `--rc-max-sample-age N`. Only camera-only changes may continue, and only
when every composited entry is within the age bound. This is the first mode
that can change a candidate for a reason other than a generation change; it
gets its own expected values and never becomes the default.

**Stage 4 — selective re-seed (default off).**
Only after Stage 3 evidence and a capture with more than one light. Re-seed
must use a deterministic subset and preserve the existing first-`min(valid,
512)` order, or it is a new sampling policy that needs its own contract.

### What stays default-off

- `rc_rendering` stays false; the cache path remains a research mode.
- `candidate_applied` stays false; `authoritative_output` stays `no-cache`.
- Native presentation stays explicit.
- All aging, age-bounded continuation and selective re-seed.
- Any change to the provider interface or the `RCRPATH1` format.

### What must stay byte-identical

- Ordinary no-cache pixels and signals, with and without the RC diagnostics.
- The `RCRPATH1` artifact: 1,573,120 bytes, the 224-byte header, 12,288 rows
  of 128 bytes and the 32-byte SHA-256
  ([renderer-exported paths](RADIANCE_CACHE_PATHS.md#source-contract)).
- The five provider buffers: 716,808 bytes, exact sizes, strides and order
  ([Radiance Cache foundation](RADIANCE_CACHE.md#next-renderer-owned-slice)).
- Baseline and reset hashes, including the exact reset comparison: zero changed
  values, zero MSE and zero maximum difference
  ([persistent training](RADIANCE_CACHE_TRAINING.md#measurement)).
- Repeat runs, including the deterministic projection used by the path contract
  (tests/verify_rc_path_sequence.py:32).
- The applied-pixel audit: 172 applied and 12,116 unmapped pixels unchanged
  ([cross-process shared resources](RADIANCE_CACHE_SHARED.md#guarded-output-and-scheduled-native-presentation)).
- The provider allocation lifecycle: 20,643,840-byte peak, 11 allocations,
  11 releases, zero live bytes
  ([Radiance Cache foundation](RADIANCE_CACHE.md#live-support-and-lifecycle)).
- The existing 8 RC/presentation contracts. The new contract is additive.

## 4. Test plan

### Synthetic stale-lighting scenario

The fixture is the canonical 128x96 legacy-diffuse scene. Two path artifacts are
exported at the same camera and geometry:

- **L0**: the default white light.
- **L1**: the same scene with `--light-color 0.2 0.3 0.4`, the mutation the
  temporal lighting test applies to the default white light
  (`src/dxr/main.cpp:824`). Two stronger variants are `--ambient` toggled to
  zero (`src/dxr/main.cpp:822`) and `--light-intensity 0`
  (`src/dxr/main.cpp:823`).

`--rc-paths` cannot be combined with `--lighting-test`
(`src/dxr/main.cpp:987`), but it does not reject the light options, so two
separate invocations produce the two artifacts.

**Scenario invariant.** L0 and L1 must have the same 172 queries and identical
`secondaryPositionValid`, `secondaryNormalRoughness`, `secondaryViewInstance`,
`secondaryDiffuseAlbedo` and `throughput` rows. Only `targetRadiance`,
`noCacheIndirectDistance`, `directBackgroundPrimaryValid`, the header settings
digest and the checksum may differ. This follows from the row layout
(`src/dxr/rc_paths.h:3-7`) and the shader factorizations
(`src/dxr/rc_paths.hlsl:36-37`, `:52`, `:62`). If the invariant fails, the
scenario is not isolating lighting and the test is invalid.

**Session.** One provider process and one context:

1. epoch 0: `reset`, train on L0, infer on L0; record `C_old`.
2. epoch 1: submit L1 with the policy under test. For the policy path this must
   be `reset` because the lighting generation changed. For the negative control,
   a test-only flag forces `continue`. Record the result as `C_policy`; in the
   negative control this is the forced-continue result, also called
   `C_continue`.
3. epoch 2: `reset`, train on L1, infer on L1; record `C_fresh`.
4. epoch 3: `reset` and verify exact recovery of the L1 baseline.

The negative control is the evidence that the fixture can actually produce
stale lighting. It must never be a shipped mode.

### Metrics

Let `N` be the 516 mapped RGB values (172 queries x 3). Let `C_old` be the
candidate composite at L0, `C_policy` the composite after the policy action at
L1, and `C_fresh` the composite from a fresh L1 session. In the negative
control, `C_policy` is the forced-continue result `C_continue`.

| Metric | Definition | Policy gate | Negative-control gate |
|---|---|---|---|
| `stale_mse` | mean of `(C_policy - C_fresh)^2` | `0` | `> 0` |
| `stale_max_abs` | max of `abs(C_policy - C_fresh)` | `0` | `> 0` |
| `stale_fraction` | fraction of values where `abs(C_policy - C_fresh) > abs(C_policy - C_old)` | `0` | `> 0` on at least one value |
| `generation_violations` | composited entries whose tag differs from the current generation | `0` | not asserted |
| `age_violations` | composited entries with `age > max_age` | `0` | not asserted |
| `reset_exact` | `reset_changed_values == 0 && reset_mse == 0 && reset_max_abs == 0` | required | required |
| `repeat_exact` | two runs produce the same deterministic projection | required | required |
| `no_cache_unchanged` | no-cache SHA-256 unchanged; `candidate_applied == false`; `authoritative_output == "no-cache"` | required | required |
| `step_guards` | counters zero, inputs unchanged, targets unchanged, device healthy | required | required |
| `allocation_lifecycle` | peak, allocations/releases, zero live bytes | required | required |

The policy gate is exact, not tolerance-based, because a generation change
forces a full reset and a reset is already proven exact. The negative control
proves the metric discriminates: if `stale_fraction` is zero even when
`continue` is forced across a light change, the fixture is too weak and must be
strengthened before the policy is trusted.

For Stage 3 aging, `stale_fraction` must remain zero and `stale_mse` must stay
within a predeclared budget. Do not pin that budget before the first device
run; record it as a measured value with the run that established it.

### Where each test runs

**Pure Python, no GPU, runs on the Linux CI runner and on pop-os:**

- the policy decision table: given old and new `(scene, lighting, material,
  settings, camera)` generations and ages, does the policy request `reset` or
  `continue`, and which entries are refused;
- generation derivation from the light/render tuple, including the split
  between `lighting` and `settings`;
- age accounting and the packed tag layout, including saturation and wrap;
- the metric math on synthetic arrays, including the `stale_fraction`
  definition and a case where it must be non-zero;
- the report schema: additive fields, no change to the strict envelope;
- `tests/verify_published_references.py` for the links in this page;
- `python3.12 -m compileall -q tests tools` for the new pure-Python module.

The proposed pure-Python contract is tests/verify_rc_staleness_contract.py. It
must not require a built binary, a scene file or a provider DLL. It is added to
the `python-tools` workflow (`.github/workflows/python-tools.yml:33-34`).

**Windows/D3D device, cannot run on the Linux runner or on pop-os:**

- `RCRPATH1` export at L0 and L1, because it needs a DXR-capable adapter and
  the DXIL shaders (`rc_paths_export`, `CMakeLists.txt:248-249`);
- the persistent provider session, because it needs the signed FidelityFX
  Radiance Cache 0.9.0 DLLs, Shader Model 6.6 and RX 9000-series-or-newer
  hardware ([Radiance Cache foundation](RADIANCE_CACHE.md#pinned-provider));
- the stale-lighting scenario, the negative control, reset exactness, repeat
  exactness and the allocation lifecycle;
- the Stage 2 generation enforcement and the Stage 3 age-bound mode.

The proposed device contract is tests/verify_rc_staleness_device.py, registered
like `rc_path_sequence_contract` with `SKIP_RETURN_CODE 77` for an unsupported
adapter (`CMakeLists.txt:222-223`).

**Why the Linux runner and pop-os cannot run these.** The project is
Windows-only: the renderer, the probe and the provider boundary use D3D12, DXIL,
Windows process/job objects and signed FidelityFX DLLs. The Linux
`python-tools` job is explicitly the "part of the suite that is honest on a
Linux runner" and runs only pure-Python checks over files in the checkout
(`.github/workflows/python-tools.yml:1-11`). A pop-os workstation has no D3D12
device, no Windows job object and no admitted provider, so it cannot produce
this evidence either.

**Why the hosted Windows job cannot run these either, as configured.** The
`build` workflow states that it does not run the D3D9, D3D12 or DXR suites
because they need a display and a GPU (`.github/workflows/build.yml:12-19`),
and the RC targets are behind an optional SDK checkout
(`CMakeLists.txt:145-151`). Device evidence must come from the RX 9070 XT
machine with the pinned SDK, not from `windows-2022` as configured.

### Test sequence and evidence

- Keep the existing RC contracts unchanged; add the new contract beside them.
- Use new expected hashes for L1; never reuse the L0 baseline, post-training or
  candidate hashes for a different lighting state.
- Retain the report as `staleness.json`, following the existing
  `renderer-session.json`, `commanded-session.json` and `gpu-pool.json`
  pattern.
- Register the Stage 2 result in the evidence ledger, as the gap analysis
  requires for an item that touches the provider boundary.

## 5. Open questions

1. **Does the provider age samples internally?** The pinned material does not
   say. If it does, a renderer-side age policy may double-age. The proposed
   policy is safe either way because a generation change resets, but the
   Stage 3 age bound would need to account for it. **(uncertain)**
2. **Is camera-only continuation safe?** The provider's position input is
   scene-bounds-normalized, but its target is view-dependent. The current
   policy resets on camera and the live test proves that reset matches a fresh
   process; it does not prove that continuation is wrong. This needs a quality
   experiment before Stage 3. **(uncertain)**
3. **Is a light-colour change linear enough to rescale predictions?** For the
   legacy diffuse path, `target = direct * lightColor` and
   `noCacheIndirect = throughput * target` are linear in the light colour, but
   the trained prediction is not, and ambient is additive. An analytic rescale
   is not exact and is not proposed. **(uncertain)**
4. **Per-light invalidation.** The capture subset has one directional sun and
   one ambient scalar. There is no local-light set to invalidate selectively.
   The `lighting` generation should hash the whole light tuple until a
   multi-light capture exists.
5. **Material staleness.** The RC path export rejects material sidecars
   (`src/dxr/main.cpp:987`), so a material-change scenario cannot be built on
   this pipeline today.
6. **Scene bounds.** A bounds change reinterprets every normalized position
   (`src/dxr/rc_compact.hlsl:40`). A `scene` generation is therefore
   mandatory even if the geometry is otherwise similar.
7. **The 64-epoch cap.** `RcEpochProtocol::MaxEpochs` is 64
   (`src/dxr/rc_epoch_protocol.h:9`). Any periodic-reset or long aging schedule
   must stop and restart the session, which loses state and changes timing.
8. **Allocation accounting and handles.** A renderer-local age buffer changes
   the `renderer.gpu.allocated` baseline, which the session test asserts is
   constant across epochs (`src/dxr/rc_renderer_session.h:38`). It must be
   allocated once at session start. A shared age buffer would also change the
   five-buffer/six-handle contract, so keep it local.
9. **Age units.** Frames, logical epochs and wall time diverge under variable
   frame rate. Use logical epochs for determinism; a frame-based age makes the
   test depend on pacing.
10. **Coalescing can drop a revision.** `RequestFrame` replaces the pending
    request with the newest identity (`src/dxr/rc_admission.h:20-27`). If a
    camera change and a lighting change arrive in the same frame, the caller
    must merge both revisions into one identity; two separate calls can lose
    the first. This is a real path to the same stale-lighting bug.
11. **Report envelope compatibility.** The workers validate strict JSON
    envelopes (`tools/rc_sequence_worker.py:17-18`). New fields must be
    additive, and the worker's assessment must be updated in the same change
    that emits them, or the report is rejected as malformed.
12. **The fixture is small.** 172 queries on a 128x96 legacy-diffuse scene are
    enough to detect a global light change, but not to characterize a game
    scene, local lights, or spatially varying materials. Do not generalize the
    Stage 3 result from this fixture.
13. **Convergence budget.** The provider's `0.99` smoothing and 512-sample
    training cap bound how fast a re-seed can move the model. A short aging
    window may be dominated by the provider's own inertia rather than by the
    policy. **(uncertain)**

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A policy that weakens reset exactness | The track's strongest evidence becomes tolerance-based | Keep hard reset as the default; aging is opt-in and never claims exactness |
| Hash churn invalidates existing evidence | Every post-training and candidate hash changes | Freeze the canonical scenarios; add new expected values only for the new scenario |
| Silent identity omission remains | The same stale-lighting bug survives the new fields | Derive generations mechanically from the light/render tuple; test the derivation and the decision table |
| False confidence from the small fixture | A policy that passes 172 queries may fail a game scene | State the fixture boundary; require a second capture before a quality claim |
| Performance regression from re-seed or per-epoch readback | The 426 ms two-epoch transaction grows | Keep Stage 3/4 default off; measure the re-seed burst separately |
| Policy/model divergence | The Python contract and the C++ implementation disagree | One JSON policy table or one shared decision function; a contract test compares both |
| Provider crash on allocation denial | The known 1 MiB access violation | No new provider allocations; renderer-local tags only |
| Float decay is device-dependent | Repeatability claims become adapter-specific | Reject weighted decay as the primary mechanism |
| Coalescing loses a revision | A light change is silently dropped | Merge identities before `RequestFrame`; test the combined change |
| Scene change without a `scene` bump | Learned radiance applied to the wrong world point | Make `scene` a mandatory generation, not an optional caller hint |

## Decision record

**Decision.** For the opt-in Radiance Cache path, adopt generation-tagged hard
reset as the correctness policy, with renderer-side age and generation tags as
diagnostics. Keep age-bounded camera continuation and selective re-seed default
off and gated on device evidence. Reject weighted decay as the primary
mechanism. Do not change the provider interface, the `RCRPATH1` format or any
existing byte-exact result.

**Consequence.** A light or scene change can no longer silently continue the
cache. The cost is a full reset on every such change, which is what the current
policy already does when a caller remembers to issue the revision. The gain is
that the revision is derived rather than remembered, and that a stale entry is
reported instead of composited.

**Follow-up.** Stage 1 and Stage 2 are the smallest useful implementation. They
need one renderer diagnostic for the two-lighting session, one pure-Python
policy contract, one device contract and an evidence entry. Stage 3 is a
separate decision after that evidence exists.
