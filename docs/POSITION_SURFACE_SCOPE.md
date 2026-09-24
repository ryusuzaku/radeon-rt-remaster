# Closed standalone color-target scope (v9)

The opt-in `--position-surface-scope` runner flag requires
`--position-write-evidence` and its existing prerequisites. Native environment:
`RRT_POSITION_SURFACE_SCOPE=1`. Schemas v1–v8 remain available unchanged.

This slice qualifies **ordered color-write calls to a private standalone RT0**.
It does not reconstruct pixel shader output, initial pixels at a later draw,
materials or complete render state. Stateful replay remains disabled.

## Closing the resource scope

The producer records successful native `CreateRenderTarget` creation before
wrapping its returned surface. `CreateRenderTargetEx` is observed too; only Usage=0
can qualify. Resource-private lifetime tags retain owner device/reset epoch and
whether the shared-handle parameter was null and the target was nonlockable.

Only an observed private, nonlockable standalone creation qualifies. A non-null
shared-handle pointer is excluded whether it requests creation or opens a handle.
Texture-backed surfaces, backbuffers and unknown origins have no qualifying tag.
This excludes subresource/texture aliases; it does **not** implement a general
alias graph. Retrieving another interface to the same standalone surface preserves
its native lifetime tag. Sharing through unsupported interfaces is not enabled by
this contract; the proxy's existing unsupported-QueryInterface rejection remains.

At both Clear and captured draw, query device capabilities and every reported MRT
slot (bounded at 1–4) plus the depth surface. Qualification requires RT0 only, no
depth attachment, no multisampling and matching creation device/reset. Missing
queries cannot produce an accepted complete scope. Depth/blend replay and MRTs
are separate future contracts.

## Writable-access lifetimes

The producer tracks successful LockRect/LockBox and GetDC separately from the
64-event write ring. Successful matching UnlockRect/UnlockBox or ReleaseDC closes
access. Failed native calls preserve the prior access map. Readonly locks count
conservatively too; their flag does not grant a special admission path.

The map holds at most 64 native resource lifetime IDs process-wide. Duplicate
opens, unknown resource identity (including Volume9 access), unmatched closes,
kind mismatches, observer errors and exhaustion invalidate accounting with a
sticky gap. Concurrent locks of multiple subresources on one texture are not
silently merged into a clean access state. Open access on an unrelated resource
also excludes this deliberately conservative scope.

Clear never resets the access map. Consequently, access opened before a clear or
before the retained history cannot disappear merely because its opening event
was overwritten. Destruction/reset cannot silently discharge an unmatched access;
an unresolved entry continues to exclude qualification. No forced unlocks or
native resource mutation are performed by these hooks.

## Evidence and reader

Each accepted v9 row includes `surface_scope` with `draw` and `clear` snapshots.
The clear snapshot is null exactly when latest-clear payload is null. A successful
unrecordable clear invalidates both; a failed clear preserves both previous
snapshots. The latest clear can still belong to another target or epoch.

Each snapshot has:

- `attachments`: one ID per device-reported MRT slot, zero for unbound slots;
- `depth_id`, `open_accesses` (0–64), and boolean `access_gap`;
- `origin`: `observed`, `private`, `lockable`, creation `device` and `reset_epoch`.

Unknown origins encode false booleans and zero identities. The reader validates
exact keys/types/bounds, attachment linkage to composition/clear evidence,
immutable origins across lifetime IDs, consistent MRT slot counts, and sticky
access gaps. Import preserves the snapshots in immutable candidates. Rejected
draw rows may lack scope snapshots and never qualify for replay.

`color_scope` in initial-content/grouped reports names the precise scope
`private_standalone_rt0_color_calls`. Qualification requires:

1. Both clear and draw have the closed scope described above.
2. The latest clear fully initializes this target's color attachment in the current
   epoch, with exact matching identity/descriptor, no rectangles, full viewport,
   scissor disabled and only D3DCLEAR_TARGET.
3. That successful clear is retained in the ordered history, followed exclusively
   by captured indexed draws (failed calls do not count as successful writers).
   Observer/overlap gaps prevent qualification.

A dropped prefix is allowed only when a later clear remains retained and all
independent scope/access guards pass. The existing process-wide v8 `unobserved`
marker is retained; the v9 result narrows the claim to a proven standalone surface.
It does not assert full process-wide surface coverage.

`qualified` and `complete_color_write_call_coverage` can now be true for that
specific subset. `ready_for_stateful_replay` remains false and `initial_contents`
remains unknown at a captured draw: the intervening pixel results and replay state
are not reconstructed. Group reports assess each draw individually.

## Validation and next gate

Native controls cover ordinary/recreated targets, resets, closed and outstanding
access begun before clear, failed unlock, 65-access exhaustion, texture-backed
targets, extra MRT/depth bindings, lockable targets, successful intervening fills,
history exhaustion and partial/oversized/failed clears. Existing native/CPU raster
oracles must remain exact. Reader controls exercise missing/inconsistent metadata,
changed origins, disappearing gaps, legacy-schema impersonation and false scope
qualification. Shared-origin exclusion is a metadata negative plus generated
creation-hook audit; native cross-process sharing is not induced or qualified.

Next implement a supported replay-state contract for admitted color segments,
starting with a controlled pixel shader and explicit supported raster/blend state.
Depth requires its own initialization and write-scope qualification because v9
excludes depth attachments. Do not request another HL2 gameplay run until the
capture/replay contract can qualify more than diagnostic position geometry.
