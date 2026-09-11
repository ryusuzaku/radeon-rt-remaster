# HL2 v18 material pass result — 2026-09-08

Bundle: build/game-passes/hl2-material-v18-20260908. User confirmed gameplay before
trigger. HL2 exited0 after8698.844s, executable unchanged, owned proxy removed
and independently absent. Trace completed60 presents,137181 events,9047 shader
draws,0 failures. Inventory captured2861 draws including288 exact pinned VS/PS pairs.

Position ledger completed byte_limit with1574 attempts,1573 recorded rejections,
0 material captures. Every recorded reason is selection_target_mismatch for
5120x1440:3. Repeated64-event histories consumed16,774,831 bytes before any
position-capture Present was recorded. Actual target dimensions were absent.
This says nothing about whether HL2 texture initialization would be admitted.
No material comparison was run and no rendering settings changed.

## Selection diagnostic follow-up

Failed selections now include optional selection_observed with target descriptor
[width,height,format,multisample] and primitive count. The inspector validates it
and reports observed_rejection_targets, whose counts mean recorded examples.
Older records remain valid. Captured draw schema and admission are unchanged.

New v18 writers explicitly advertise optional selection_rejections policy in the
header: first4 per target/reason, up to64 keys, plus every64th global attempt.
Only successful native draws rejected by target mismatch or primitive minimum
are sampled. Every accepted draw and other failure remains recorded. Full write
histories remain on saved rows; omitted rejected draws still exist in the native
write history as uncaptured events. Footer attempts count all attempts. Readers
must not interpret recorded rejection counts as the full attempted population.
The updated inspector accepts old headers and validates the new optional policy;
older strict readers will reject the new header rather than misinterpret it.

At most320 sampled selection-rejection rows are emitted over4096 attempts. The
64-key map is bounded and uses target descriptor/reason, excluding primitive
count. No resource evidence is inferred and no capture limit is raised.

Another short gameplay pass is useful after regression checks: it will reveal
actual render-target sizes and may reach matching targets beyond the old byte
limit. Do not change game resolution or infer a new selection from the old data.
Use a fresh bundle and wait for gameplay readiness before triggering.

Validation: Release position_capture61.94s, texture_surface39.04s,
game_pass_workflow2.47s and final texture_selection1.96s pass. Debug proxy and
selection2/2 pass5.52s. Native stress4096 attempts produces67 full-history rows
under1MiB, unchanged float-image hashes and attempt_limit completion. All16
matching draws retained;10 malformed observation/policy cases rejected.
