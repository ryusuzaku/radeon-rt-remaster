# Texture resource failure context — 2026-09-08

The material-stage HL2 pass reached4096 attempts with0 captures. It identified80
texture_tracking_missing and192 texture_upload_proof_missing failures, plus30
topology failures. These labels alone do not identify the resource descriptor or
which upload path is missing. Game exited0 and proxy cleanup was verified.

New optional v18 texture_diagnostic appears only with a texture-input preflight
failure. It records sampler slot, existing resource ID, top-level descriptor
[width,height,format,usage,pool,multisample,quality], level count and whether a
shadow exists. It preserves the last creation admission step, revision, known
and total shadow bytes, pending mip count, upload source/revision, surface-copy
history count, last invalidation operation and last UpdateTexture proof check.

These fields are observations, never texture payloads or proof of an admissible
draw. Last admission step identifies the broad creation constraint, not necessarily
which member of a combined constraint failed; use the descriptor to interpret it.
Unobserved creation remains explicit. The last upload label describes the most
recent observed proof attempt and can remain after later invalidation. Native
failure/boundary-change records do not claim a preflight resource diagnosis.

Snapshots use descriptor queries and existing shadow masks only, without GPU
readback or scanning game memory. They are generated only after a texture-input
exception, bounded to one failing slot. Diagnostic query/allocation failure omits
the optional context. Creation and transfer admission conditions are unchanged;
dynamic/default direct writes remain unqualified. Metadata strings have static
storage and per-resource state is fixed-size. The existing shadow byte budget
remains unchanged; the new fields add a few pointers to each tracking object.

Superseded 2026-09-16 for **dynamic** DEFAULT textures: DEFAULT + `D3DUSAGE_DYNAMIC`
non-target textures written in place through observed locks are now admitted and
qualified (origin `observed_private_default_dynamic`). Non-dynamic DEFAULT
destination writes still require a proven `UpdateTexture`. See
[SURFACE_LOCK_QUALIFICATION.md](SURFACE_LOCK_QUALIFICATION.md).

The inspector validates shape, scope, descriptors, IDs, byte/level/history bounds,
tracking consistency and bounded labels, then groups identical contexts with
recorded_rejections counts. Old v18 ledgers remain readable; captured draw fields
are unchanged. No consumer promotes diagnostics into initialized scene assets.

Tests distinguish a dynamic default-pool texture rejected at creation, alias
invalidation (zero known bytes), and a rejected default-pool upload proof attempt.
Native/v17/v18 rendered output remains identical; malformed context rejects.
The next gameplay pass uses2560x1440:3 and full v18 flags to determine which
capture implementation is actually needed. Do not infer support from snapshots.

Validation: Release4/4 passed123.95s, final selection4.80s; Debug2/2
passed10.46s. Builds and Python compile passed; no test failures.
