# Combined HL2 diagnostic capture

One instrumented launch can now arm trace, shader/layout inventory and a narrow
position-input capture together. This is an interim combined diagnostic, not the
future coherent all-assets session format or complete scene reconstruction.

Run through the existing game-pass runner with `--mode proxy --wait-trigger
--shader-inventory --position-capture`; the existing `trigger` command activates
all three outputs. Resource writes and constant initialization are tracked from
launch, before the marker. Individual trigger polling/Present boundaries and
budgets remain independent; do not equate draw ordinals across the three files.

## Position input evidence

Only the exact numerically validated HL2 shader is admitted. A capture records
successful native triangle-list INDEX16 draws, source shader/declaration bytes,
c0/c4–7/c58–60, stream offset/stride, draw ranges/base, selected indices and the
corresponding initialized FLOAT3 positions in corner order. Evaluated clip and
model-position output is retained, plus viewport and target dimensions/format/
multisampling. This is position-only evidence, not full raster/material replay.

Input layout requires one POSITION0 FLOAT3 at stream 0 offset 0, ordinary stream
frequency 1 and stride 12–256. Other declaration inputs remain recorded but are
not extracted: this exact shader's position path does not consume them.
Bound resource identity must match the resource-private shadow; every referenced
byte must be initialized through an observed successful writable Unlock. API lock
ranges are evidence, not CPU-store tracing. No new GPU readback/locking occurs
inside the game draw hook.

Limits: four captured draws, 4096 attempted indexed draws after activation,
4096 primitives per draw, 16 MiB output. Larger buffers are supported through
whole-buffer shadows capped at 16 MiB each and 128 MiB total byte+mask storage
in this opt-in mode. Only referenced ranges are serialized. This may impose
diagnostic overhead and may reject game buffers once a budget is exhausted;
sparse range tracking and production performance remain future work. Existing
standalone raster snapshot mode retains its original 64 KiB/16 MiB budgets.

Reset/state-block recording/application and wrapper retirement invalidate constant
knowledge. DISCARD and failed writes invalidate byte knowledge. ProcessVertices
invalidates tracked destination evidence. Unknown or unsupported inputs reject;
failed native calls never count as captured. Exclusive output preserves existing
files; a partial ledger without footer is not complete. Position mode and the
older single-draw shader snapshot mode are mutually exclusive.

Inspect with `python tools/inspect_position_capture.py path/to/position-capture.jsonl`.
The CPU reader validates budgets, source program identity, declarations, ranges,
finite data and independently recomputes recorded position outputs with tolerance
0.0002. It reports accepted draws and rejection reasons without creating GPU shaders.

## Verification

### Surface and composition-state evidence (position ledger version 6)

Selected multi-draw runs can opt into `--position-render-state` to record native
surface lifetime IDs, clear/binding serials and effective selected depth/blend/
raster state. See `POSITION_COMPOSITION_EVIDENCE.md` for the fields, conservative
grouping policy and missing clear/initial-content semantics. This option does not
enable state-aware or game-faithful replay; v5 remains the multi-draw default.

### Bounded multi-draw sampling (position ledger version 5)

Add `--position-multi-draw` to an explicitly selected interval capture. The runner
sets `RRT_POSITION_MULTI_DRAW=1`; explicit target/count selection is mandatory.
v5 fixes the accepted limits at4 per device/reset/Present interval and16 total.
The header records `sampling: bounded-per-present-interval` and
`limits: {per_interval:4,total:16}`. Unsupported/failed draws do not consume
accepted quota; in-flight reservations and completed accepted counts are separate.
Reset/presentation boundaries clear interval counts, not the global total.

Existing16MiB ledger,4096-attempt,120-Present and per-draw geometry limits remain.
The byte limit may stop a capture before16 samples, and fewer than4 qualifying
draws per interval may spread the samples across more intervals. There is no
fallback to unsupported shaders or mismatched targets. Process exit without a
footer remains partial. Reconstruction and GPU replay now accept a validated
`present_limit` completion with at least one accepted draw, matching the importer.

Each accepted draw retains its own timing/resource/constant evidence. Multiple
accepted draws with the same interval and indexed-draw key reject in the reader;
per-interval and total quotas are independently checked. No content-hash dedup
is applied during sampling: identical geometry can represent distinct instances
or passes. The importer reports submitted draws/triangles separately from unique
position-content count, never calling this count a number of game objects.
Legacy v1–v4 behavior and bounds are preserved when multi-draw is not selected.

Native quota fixtures submit six identical eligible draws and one failed draw
per interval. Only four successful samples remain, with16 total after four
intervals and unchanged raster output. Tests cover no-present partial captures,
120-Present completion/replay, policy/limit/timing tampering, explicit16-instance
import and guarded runner forwarding. Repeated fixture content is deliberate
quota testing, not proof of broader geometry coverage in HL2.

### Explicit target/triangle selection (position ledger version 4)

Optional runner `--position-selection WIDTHxHEIGHT:MIN_TRIANGLES` requires
`--position-frames` and the usual triggered inventory/position options. It sets
`RRT_POSITION_SELECTION`; canonical positive decimal values only, dimensions
at most16384 and minimum triangle count at most4096. Invalid policy disables
position capture instead of silently falling back to an unfiltered capture.

The v4 header records `selection` with `target_width`, `target_height` and
`min_primitives`, alongside the v3 session/timing contract. Before copying
position evidence, the hook checks render target0's exact dimensions and the
triangle-list primitive count. Mismatches become explicit rejection records
and release the interval reservation, allowing a later draw in the same interval
to qualify. Existing byte, attempt, presentation and four-sample limits remain.
No matching draw is a bounded no-capture result, not permission to widen selection.
The reader independently checks every accepted draw against the recorded policy;
the scene adapter exposes the policy and retains unresolved correspondence.

The planned HL2 policy `5120x1440:3` uses dimensions observed in earlier captures
and excludes the two-triangle samples seen so far. This is **not** main-view,
material, visibility or engine-object classification: multiple passes can share
dimensions, and a submitted three-or-more-triangle draw can still be invisible.
No game resolution or graphics setting is changed by this selector. Without a
policy, existing v2/v3 capture behavior is unchanged; v1–v4 remain readable.

Native tests render an excluded8x8 target before an admitted128x96 target in
each interval, retain exact raster output, and verify recovery without consuming
the accepted-sample slot. They also cover nonmatching dimensions, minimum-count
rejection,120-present termination, malformed/out-of-range policy, missing frame
mode, tampered reader policy and guarded runner environment/report propagation.

### Opt-in presentation sampling (position ledger version 3)

Add `--position-frames` to the guarded runner's existing triggered
`--shader-inventory --position-capture` run. This sets
`RRT_POSITION_FRAME_SAMPLING=1`; without it the producer still writes v2.

v3 includes a random128-bit capture-session ID and per-draw timing:
`reset_epoch`, `present_interval`, `indexed_draw`. The interval counts observed
S_OK device Present/PresentEx or swap-chain Present calls since device tracking
began; successful Reset/ResetEx starts a new epoch and interval0. Swap chains
resolve their owning wrapped device. Multiple swap chains create multiple
boundaries, not a guessed primary-view or engine-frame timeline. `indexed_draw`
counts hooked indexed attempts after trigger activation, resets at boundaries,
and includes attempts skipped after an accepted sample. It is not all draw APIs.

At most one accepted draw per device/epoch/interval is captured, four total.
Failed/unsupported draws release the interval reservation; native failures do
not become accepted samples. A changed presentation/reset boundary between
snapshot and commit rejects the sample. Existing4096 attempted-capture/16MiB
limits remain;120 successful presentations across tracked devices after
activation stop the session with `present_limit`. The footer records that count.
No presentations and early process exit can leave a partial ledger, which is
not silently considered complete. This is bounded sampling, not whole frames.

The reader validates session/timing fields, matching reset provenance and unique
accepted device/epoch/interval keys. The scene adapter preserves them without
inferring objects; reconstruction keeps different intervals in separate groups.
Native fixture tests cover device and primary swap-chain presents, successful
reset separation, no-present partial capture,120-present termination, malformed
metadata and invalid opt-in configuration. Default v1/v2 replay stays supported.
The S_OK-only guard is implemented; failed-Present behavior was not induced in
the fixture (an attempted in-scene Present returned success on this driver).

This timeline is position-ledger-local. Trace and inventory do not yet share its
session/interval IDs. Real HL2 multi-frame sampling and correspondence still need
a fresh guarded game pass; no motion/whole-scene tracking claim follows from the
synthetic tests.

### Resource provenance (position ledger version 2)

New accepted records include shadow-lifetime VB/IB IDs and observed mutation
revisions, plus device reset epoch and constant-knowledge revision. IDs are
process-local opaque integers, not native pointers, cross-run asset IDs or engine
object IDs. Resource-private shadow destruction/recreation produces a fresh ID.
Successful tracked writes and invalidation/DISCARD boundaries advance revisions;
they do not prove that byte content changed. A resource/range plus revision is
input provenance, not enough to infer semantic instances sharing that resource.

Reset epochs are relative to the wrapper-generation device ID. Constants writes
and conservative state-block boundaries advance knowledge revisions. These fields
do not create a globally correlated frame timeline or track unsupported GPU writes.

The reader accepts original v1 captures with resource_provenance=false; it rejects
v1 records claiming new provenance. Version2 requires all bounded identity/revision
fields. Reconstruction manifests preserve validated provenance when available.
Tests verify fresh allocations receive different IDs and reused VB/IB retain IDs
while successive writes advance revisions, without changing the native oracle.

The exact captured shader fixture produces position and inventory outputs in one
process while preserving the 24-case hardware raster oracle result. Tests cover
raw source position/constant/index agreement, 256 KiB buffers, undefined byte and
resource/range rejection, state-block invalidation and refresh, native failure,
trigger gating, disabled mode, collisions, absent output parents and malformed
offline evidence. The disposable game runner also tests combined activation and
cleanup; its fixed-function sample correctly produces no accepted HL2 positions.

Still needed later: material/texture inputs, broader program coverage, verified
world-space interpretation, coherent cross-output frame identities and full
scene/runtime integration. No promise to capture all of these in this pass.
