# Position-only scene-state prototype

`tools/position_scene.py` supplies an offline, bounded state contract for future
continuous scene updates. `tools/capture_position_scene.py` now connects validated
proxy ledger files to this state offline. Neither is wired to live DXR rendering.

- Geometry identity hashes exact triangle-corner position bytes with a schema
  domain. It ignores buffer addresses, draw offsets and transform constants.
  It is deliberately **not** a full mesh/material or game-object identity.
- Instances require an explicit caller-provided ID and carry separate captured
  position constants. Equal geometry can belong to multiple instances; changing
  a transform does not allocate new position content.
- Updates are transactional deltas: unseen instances remain present until an
  explicit removal or reset. Removed/replaced geometry is released when no live
  instance references it. No automatic cross-object merge or visibility deletion.
- Reset advances an epoch and clears state; updates from older epochs or stale
  sequence numbers reject. Duplicate/conflicting entries reject before commit.
- Defaults:128 instances,16 MiB retained unique geometry. Configurable hard maxima
  are4096 instances/64 MiB,4096 delta entries and4096 triangles per geometry.
  Budget failures preserve previous state and sequence. These are state-storage
  limits, not a performance qualification or bound on caller-owned input objects.

Tests cover content sharing, transform-only reuse, two distinct instances,
replacement/release, unseen retention, explicit removal, epoch/sequence rejection,
invalid inputs, safe snapshot copies and atomic budget/conflict failure.

## Required before live integration

The current capture ledger has draw ordinals, not trustworthy persistent object
IDs. Do not use a draw ordinal or a geometry hash as an inferred object identity.
Opt-in v3 now adds session/Present-interval/reset metadata, preserved by the
adapter. It is bounded sampling, not an automatic correspondence policy or a
cross-output unified frame timeline.
Position ledger v2 now supplies source shadow-lifetime IDs and observed mutation
revisions. The offline adapter requires explicit caller assignments and reports
all other draws as unresolved. Automatic temporal correspondence still needs
frame/session evidence and an engine/profile policy. Then connect capture
deltas through the tested scheduler to renderer acceleration-structure updates.
Animation, material/texture identity and scene eviction require further contracts.

This prototype demonstrates storage/update semantics only. A repeated synthetic
delta is not evidence that a moving HL2 object has been tracked across frames.

## Offline capture adapter

Inspect without assigning any objects:

```powershell
python tools/capture_position_scene.py build/game-passes/hl2-combined-20260907/runs/combined/position-capture.jsonl
```

To exercise a fresh offline scene, supply `--assign ORDINAL=INSTANCE` (repeat for
up to the ledger's accepted limit: four for v1–v4, sixteen for v5) and
`--source-sha256` with the digest from inspection.
Assignments are assertions about instances, not a discovered mapping; ordinals
are local evidence references only. Multiple draws assigned to one instance
reject instead of silently overwriting or merging geometry. Multi-part game
objects need a future explicit object/part contract.

The Python `Capture.apply(scene, epoch, sequence, digest, assignments, removes)`
API imports raw input triangle positions and all eight captured constant rows.
It preserves distinct instances even when they share position content. Unassigned
draws do not change or remove scene entries. All assignment validation and scene
budget checks precede commit. Removal remains explicit; caller epoch/sequence
is scheduling metadata, **not** an inferred game frame number.

The reader validates and hashes the same bounded immutable byte snapshot, so a
path changing between separate validation/hash reads cannot mislabel an import.
Partial and I/O-error captures reject. v1 supplies no invented resource identity;
v2 reports device, lifetime IDs, revisions, reset epoch and source draw ranges.
Those fields are diagnostic evidence, not a matching key. The report preserves
target/viewport context but does not classify render passes or claim world-space
semantics. Constants remain attached to each imported instance.

Tests use the real four-draw HL2 v1 ledger (57 triangles) and fresh native v2
proxy fixtures for resource recreation/reuse. They cover exact input preservation,
unresolved reporting, explicit identity, digest rejection, rollback, reuse,
removal/reset and incomplete-input rejection. No live motion, materials, or new
game capture is claimed by these tests.
