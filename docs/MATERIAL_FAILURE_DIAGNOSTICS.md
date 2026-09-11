# Material failure diagnostics — 2026-09-08

The2560x1440 HL2 material run recorded0 captures,168 generic evidence failures and
1417 unsupported-shader rejections before the16MiB limit (2018 attempts). These
records cannot identify a missing texture or a failing capture stage retroactively.
Inventory contains281 exact pinned VS/PS pairs. Game exited0; proxy removed and
independently absent. Trace completed60 presents/8399 shader draws/0 failures.
Evidence: build/game-passes/hl2-material-2560-v18-20260908/material-analysis.json.

## New optional v18 diagnostic fields

Rejected preflight draws can carry evidence_failure with stage and detail.
Stages distinguish topology, device state, selection, buffer binding/tracking,
position/material input, composition, surface scope, color evidence, pixel
material, and texture input. A stage means the check failed there; it does not
claim the later checks would pass. Existing reason values and admission remain
unchanged. Specific internal pixel/material exception details previously hidden
by the generic reason are now preserved as bounded diagnostic text. Texture
checks name missing tracking, invalid epoch/revision, missing upload proof,
pending mip locks and uninitialized mip bytes. Unnamed checks retain their generic
exception detail under the stage; this is not exhaustive per-resource telemetry.
Details are1..96 lowercase ASCII letters, underscores or spaces; other exceptions
are reported as unclassified_exception. Native draw failures and later commit
boundary failures are not relabeled as preflight failures.

The optional shader_rejections header advertises separate bounded sampling for
unsupported_shader and position program not admitted: first4 per target/reason
for at most64 keys, plus every64th global attempt. It groups unsupported draws
by reason/target, not by shader identity. Shader inventory remains the evidence
for individual programs. Selection and shader sampling each have their own
bounded64-key map. Other failures and accepted draws remain unsampled. Full
write histories remain on emitted records; omitted rejected calls stay uncaptured
in subsequent histories. Footer attempts count all attempts, report rejection
counts count only recorded examples. Combined eligible selection/shader examples
are bounded by640 records across4096 attempts. Other failures can still consume
the byte budget; no complete-population or complete-frame claim is made.

Updated inspector accepts prior v18 headers and validates new optional fields;
older strict readers reject the new header. It reports evidence_failures grouped
by stage/detail and shader_rejection_sampling separately from selection sampling.

## Qualification and gameplay gate

Native fixtures distinguish wrong PS, unknown PS constants and unknown mip bytes,
compare v17/v18 rendered output, and reject malformed stage/detail/shape/version
claims. A semantically equivalent VS with an added NOP is intentionally outside
the exact shader contract:4096 attempts yield67 records and normal attempt-limit
completion while preserving image hashes. Accepted16-draw behavior is retained.

Next useful gameplay pass: fresh bundle with current proxy, full v18 flags,
selection2560x1440:3, shader inventory,60 trace presents and user-ready trigger.
Inspect failure stages before implementing new capture support. Do not weaken
admission to obtain material bytes. No gameplay launched for this code slice.

Final checks: Release capture/surface/workflow3/3 passed106.13s, focused selection
passed4.26s; Debug proxy/selection2/2 passed9.42s. Release/Debug builds and Python
compile passed. All three saved gameplay ledgers remain readable.
