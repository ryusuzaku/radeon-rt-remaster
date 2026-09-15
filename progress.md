## 2026-09-11 — HL2 v19 live run; unfiltered selection and trigger arming

- Ran the prepared v19 bundle against HL2. The proxy intercepted and v19 was
  active (header version 19, 4096 attempts, texture assets directory created),
  and the session produced a valid trace (60 presents, 129,997 events, 8716
  shader draws, 0 failed calls; exit 0, proxy removed, executable unchanged).
- The position capture nonetheless recorded 0 captures, and the cause was not
  texture evidence: after the trigger `presents` stayed 0 and `present_interval`
  was a constant 382 across every recorded draw, so all 4096 attempts were spent
  inside a single interval with no Present. Only 27 draws passed selection and all
  27 failed the `D3DPT_TRIANGLELIST` topology guard, so nothing reached
  `texture_inputs` and the run is neutral on v19. The dominant observed target was
  5120x1440 (58 of 79 sampled mismatches), not the 2560x1440 the previous result
  doc recommended.
- Root cause of the selection friction: `RRT_POSITION_MULTI_DRAW` refused to start
  unless `targetWidth` was non-zero, and every feature from v5 to v19 requires
  multi-draw. The evidence chain was therefore welded to a hardcoded
  `WIDTHxHEIGHT:MIN`, which cannot be right for a workflow meant to work on an
  arbitrary game.
- Added `any:MIN_TRIANGLES` (A). It applies the primitive minimum while accepting
  any render-target extent, so the chain runs without knowing the resolution; the
  header records `selection:{any_target,min_primitives}` and every rejected draw
  carries `selection_observed`. The exact form is unchanged, and `any` fails
  closed without multi-draw. Reader, runner and help text updated.
- Fixed trigger arming (B). A triggered capture now waits for the first successful
  Present after the trigger and restarts interval numbering there, so a trigger
  landing while the game is not presenting attempts nothing instead of spending
  the 4096-attempt budget. Untriggered sampling keeps the historical numbering, so
  the qualified v3 contract is untouched. The first attempt bounded attempts per
  interval by attempts rather than captures was reverted: that per-interval
  behaviour is deliberate and the diagnostic stress contract depends on it.
- New coverage in `texture_selection`: `any:1` admitted with 16 captures and no
  rejections, `any:4096` rejecting only with `selection_primitive_minimum` and
  observations at the real target, and `any:1` without multi-draw producing no
  capture file. Also fixed a latent assumption in `texture_locks`, where the
  sampler index was used as the fixture texture index even though the fixture
  binds `textures[(sampler+variant)%2]`; the index is now recovered from the bound
  extent.
- Validation: full `texture_*` group 7/7 Release 222.00s and 7/7 Debug 156.54s;
  `position_capture`, `shader_proxy`, `hl2_position`, `recorded_position_oracle`
  and `game_pass_workflow` pass in both configurations. Release/Debug rebuilds
  warning free; Python compile passes.

## 2026-09-11 — shared shadow-budget ceiling quantified and asserted

- Quantified the 128MiB shared shadow budget. `Retained()` is charged only in
  buffer `Lock` (total*2) and `TextureCreated` (payload+mask+128*sizeof(SurfaceTransfer)
  for DEFAULT), released only in `~Shadow`/`~TextureShadow`; every early return in
  `TextureCreated` reverts its charge and a rejected texture never sets
  `tag->texture`, so there is no leak or double release. The limit is a priority
  limit, not an accounting defect.
- Per-chain capacity reproduces the retired 64-accept/96-reject workload exactly
  (64x1485494=95.1MB in, 96x1485494=142.6MB out), validating the model.
  `sizeof(SurfaceTransfer)` verified as 56 (RECT 16, POINT 8, LLP64), so the
  DEFAULT history charge is 7168 bytes.
- From a fresh budget 512x512 DEFAULT DXT5 fits 354 times, but the recording pass
  had 155 tracked and 76 refused: creation order alone decides admission and
  nothing is reclaimed while a resource stays alive. Maps the residual as v19
  addressing the 305 `texture_upload_proof_missing` while the 76
  `texture_tracking_missing` are this ceiling, all pool 0.
- Added `defbudget`/`defexhaust`/`defrelease` fixture cases and assertions in
  `texture_selection`. A DEFAULT destination cannot be filled directly, so the
  cases allocate 512x512 DXT5 DEFAULT textures and supply the proof from a
  SYSTEMMEM source `UpdateTexture`. 300 is admitted with 16 captures and a
  whole-chain `top_lock` transfer; 370 is refused with no captures,
  `texture_inputs`/`texture_tracking_missing` evidence and a 512x512 pool-0
  `shadow_budget` diagnostic with zero total/known bytes; release restores 16.
- Validation: `texture_selection` Release 7.20s, Debug 11.14s; full `texture_*`
  group 7/7 Release 148.82s and 7/7 Debug 191.01s with no other test changed.
  Release/Debug fixture rebuilds warning free. Documentation only otherwise; no
  runtime or budget change was made.

## 2026-09-11 — v19 surface-lock qualification and version-control baseline

- Diagnosis of the 0-capture v18 pass completed. The ledger header selects
  `surfaceLocks?19:surfaceUploads?18`, and the pass ran at **18**: with surface
  locks off, every mip-surface `LockRect`/`UnlockRect` on a tracked texture fell
  through to `TextureInvalidate(resource, operation)`, which cleared the whole
  coverage mask, set `fullDirty=false` and dropped the dirty proof. Recorded
  diagnostics match exactly: `source_not_fully_dirty`, `upload_source_invalidation`
  `UnlockRect`, `upload_source_lock_flags` null, `known_bytes 0`, revision 1, on
  usage0 DEFAULT DXT5 slot resources. The v19 tracking was already implemented
  and wired but had never been run or tested.
- Added the missing fixture actions (`aliasfull`, `aliaspartial`, `aliasmip`,
  `aliasreadonly`) in `material_fixture.inc`. They rewrite the source mips with
  `D3DLOCK_NO_DIRTY_UPDATE` first, so only the alias lock can supply the upload
  proof. `aliasfull` (whole level-0 alias lock) is admitted with
  `dirty_proof=top_lock`; partial, lower-mip and read-only aliases are not.
- Added `texture_locks` (`tests/qualify_surface_locks.py`, wired through
  `verify_texture_paths.py --kind locks`) covering RGBA and DXT5 admission with
  byte-exact mips, extracted assets, capture-ledger equality, replay match,
  native-baseline equality, four rejection controls, the v18 regression and
  three fail-closed option chains.
- Validation: `texture_locks` passes Release 7.61 s and Debug 9.95 s; the full
  `texture_*` group passes 7/7 Release 164.61 s and 7/7 Debug 217.80 s with no
  other test changed. x86 Release/Debug proxy and fixture rebuilds are warning
  free. Documented in docs/SURFACE_LOCK_QUALIFICATION.md.
- Repository placed under version control with a single baseline commit of the
  2026-09-08 tree (283 files); `build/`, traces, pixels, scenes and bytecode
  caches are ignored. No game was launched and no proxy was deployed this
  session; HL2 remains un-run at v19.

## Compact-mask capture complete; exit pending (2026-09-08)

User ready; triggered once. Valid v18 attempt_limit4096,460 recorded rows,0 captures.
Failures:305 texture_upload_proof_missing,76 texture_tracking_missing,44 sampled
unsupported shaders;27 target mismatch/8 primitive minimum. All failed sampler0
resources are usage0 DEFAULT DXT5. Tracked512x512 (155 examples),512x256 (100),
128x512 (50) have0 known bytes after UpdateTexture; last upload source_not_fully_dirty,
source lock flags null (no observed direct Texture9 lock), source invalidation
UnlockRect. This points to source writes via mip surface aliases: current code
invalidates their texture shadow rather than tracking their lock/unlock payload.
76 examples512x512 remain untracked at shadow_budget. Sample populations differ
from prior pass; do not quantify memory improvement from draw-count differences.
Next implement/qualify observed texture-mip surface LockRect/UnlockRect tracking,
including alias identity, full-dirty semantics, partial initialization and failures.
Keep residual shared budget bounded; assess pressure separately after alias support.
Evidence: build/game-passes/hl2-compact-masks-v18-20260908/material-analysis.json.
Runner session15430 owns active game/proxy; await normal exit and cleanup before
rebuild. Standing launch authorization: automatically launch next useful tested
pass after closed, waiting for user ready before trigger.

## Compact coverage qualified; game launched (2026-09-08)

Release6/6 passed184.67s (capture46.08,compressed32.60,upload44.72,dirty24.51,
surface34.22,workflow2.54). Final focused selection/pressure test6.54s passes.
Debug2/2 passed13.62s (proxy4.03,selection9.58). Builds and3-file Python compile pass.
64 retained1024-square DXT5 textures permit16 captures;96 exhaust the unchanged
budget; releasing them restores16 captures. Mask ratios RGBA4/DXT5 16 validated,
legacy resource-context ledger readable. Source lock expected flags corrected
from0 toNO_DIRTY_UPDATE32768 in its deliberate fixture; no production failures.
Docs: docs/COMPACT_TEXTURE_COVERAGE.md. No texture/copy admission relaxed.

Standing authorization used to launch fresh bundle
build/game-passes/hl2-compact-masks-v18-20260908, run material, full v18,
2560x1440:3/60 trace presents/inventory. Armed, NOT triggered; wait for user ready.
Runner session15430 owns game/proxy until normal exit. Do not rebuild deployed proxy or launch
again. After capture and normal exit, verify cleanup then continue from actual
remaining proof failure, launching further useful passes automatically once tested.

## Compact coverage implementation; tests running (2026-09-08)

Prior texture-context game exited0 after97.344s, executable unchanged, proxy
removed/absent. Changed texture masks to one flag per texel/DXT block; payload
bytes unchanged. Reservation is payload+mask+surface history under unchanged
128MiB shared bound. Every existing admitted write covers whole units.
Diagnostics retain byte counts and add coverage_bytes with unit validation.
Split source dirty/pool/epoch/revision upload checks and snapshot source lock
flags/invalidation before consuming proof. Existing captures remain readable.
Focused test passed5.10s after correcting expected fixture lock flags to32768
(NO_DIRTY_UPDATE). Core46.08s, compressed32.60s, upload44.72s have passed; dirty,
surface/workflow and pressure-control rebuild still pending.64/96-texture pressure
and release recovery cases added. No gameplay launched yet; standing authorization
requires launching a useful pass after qualification. See docs/COMPACT_TEXTURE_COVERAGE.md.

## Texture-context capture complete; exit pending (2026-09-08)

User ready; triggered once. Valid v18 attempt_limit4096,384 recorded rows,0 captures.
Failures:93 texture_tracking_missing,190 texture_upload_proof_missing,19 topology,
50 sampled unsupported shaders;22 target mismatch/10 primitive minimum.
All failing texture contexts were sampler0,usage0,DEFAULT pool,DXT5:
-114 examples512x512, tracked,0/349184 known bytes,last invalidation UpdateTexture,
 last upload source_dirty_or_epoch.
-76 examples512x256, tracked,0/174080 bytes,same upload failure context.
-57 examples512x512 and36 examples128x512 untracked,admission shadow_budget.
These establish actual budget exhaustion and a source dirty/epoch proof failure;
the combined upload label does not prove which subcondition failed. Next inspect
shadow budget/accounting/lifetime and dirty-proof transitions; avoid assuming a
partial update mechanism without evidence or just raising bounds blindly.
Evidence: build/game-passes/hl2-texture-context-v18-20260908/material-analysis.json.
Runner session55846 still owns game/proxy; request normal exit. After closed,
verify cleanup, implement/test next evidenced slice, automatically launch needed
follow-up under standing authorization; wait for ready before every trigger.

## Texture context qualified; next game launched (2026-09-08)

Release capture/upload/surface/workflow4/4 passed123.95s. Final preflight guard
rebuild: Release selection passed4.80s; Debug proxy/selection2/2 passed10.46s.
Release/Debug builds and3-file py_compile pass. Old stage ledger still validates.
No test failures. Dynamic untracked usage512/default, alias UnlockRect invalidation,
and upload source_dirty_or_epoch contexts match independent fixture expectations.
No capture admission relaxed. Details in docs/TEXTURE_RESOURCE_DIAGNOSTICS.md.

Under standing user authorization launched fresh bundle
build/game-passes/hl2-texture-context-v18-20260908; run material; full v18,
2560x1440:3,60 trace presents and inventory. Armed, NOT triggered. Wait for user
ready. Runner session55846 owns the game/proxy and waits for exit.
Do not launch again or rebuild deployed proxy. After capture wait for normal
exit/cleanup, then use resource context to select implementation; launch next
useful pass automatically once tested, still waiting for readiness before trigger.

## Texture resource context implementation (2026-09-08)

Verified previous stage pass exited0, executable unchanged, proxy removed/absent.
Added optional v18 texture_diagnostic snapshot on texture-input preflight failure:
failing slot/descriptor/admission, shadow coverage, upload provenance and latest
invalidation/upload-proof check. Descriptor/shadow observations only, no readback
or new texture admission. Partial diagnostic failure omits context. Inspector
validates shape/bounds/scope and reports grouped contexts. New preflight guard
ensures a later native/boundary failure cannot retain misleading resource context.
Focused native test passed4.64s including dynamic creation rejection, alias byte
invalidation, failed upload check,6 malformed contexts and v17/v18 image parity.
Release core capture45.07s passed; upload/surface/workflow still running. Final
guard rebuild and focused Debug checks pending. No fixture/test failures so far.
Docs: docs/TEXTURE_RESOURCE_DIAGNOSTICS.md. Standing authorization requires launch
of next useful pass after tests; use fresh bundle,current proxy,2560x1440:3 and
full v18. Wait for user ready before trigger.

## Material-stage capture complete; exit pending (2026-09-08)

User ready; triggered once. v18 inspector passes attempt_limit4096,385 recorded
rows,0 captures. Failure details:80 texture_inputs/texture_tracking_missing,
192 texture_inputs/texture_upload_proof_missing,30 topology/generic,54 sampled
unsupported shaders. Selection mismatch22/minimum7. Thus pinned material draws
reach texture input checks; no inferred texture contents or successful replay.
Next work: inspect tracking creation/admission and default-pool initialization
proof, preserving resource descriptors/provenance in diagnostics if needed.
Do not assume a particular missing upload path from these labels alone.
Evidence saved to build/game-passes/hl2-material-stages-v18-20260908/material-analysis.json.
Game still needs normal exit/cleanup, runner session50934. Wait for closed before
rebuild/deployment. Standing authorization: implement/test needed slice and launch
next useful pass automatically after cleanup, then wait for user ready.

## Active material-stage pass and standing launch authorization (2026-09-08)

User explicitly authorized launching needed follow-up gameplay passes after each
closed pass. Verify exit/cleanup first; complete needed code/tests, then launch
without another permission round. Still wait for user ready before triggering.
Fresh bundle build/game-passes/hl2-material-stages-v18-20260908, run material,
runner session50934. Full v18,2560x1440:3,60 trace presents, shader inventory.
Armed, NOT triggered. Wait for user readiness. Do not launch again or rebuild
while proxy deployed. After bounded capture, user closes game, verify cleanup,
inspect stage details and continue implementation or comparisons as evidence allows.
Preparation succeeded; preflight Get-Process returned no match (PowerShell exit1),
not a preparation failure. Runner reports running with owned proxy installed.

## Material diagnostics qualified (2026-09-08)

HL22560 material pass exited0 after262.922s, executable unchanged, owned proxy
removed/absent. Trace60 presents/128329 events/8399 shader draws/0 failures.
Added optional v18 evidence_failure stage/detail preserving previously generic
pixel/material exceptions and named texture tracking/revision/upload/mip failures.
Added separate optional shader_rejections sampling policy/map; accepted draws,
other failures and full emitted write histories remain unchanged.
Focused selection suite passed4.26s: unknown PS constants, wrong PS, uninitialized
mip diagnostics; v17/v18 image parity; malformed fields;4096 unsupported-shader
attempts ->67 records and matching image hashes. Core Release capture63.88s passes;
surface39.79s/workflow2.44s pass (Release3/3 total106.13s), plus focused
selection4.26s. Debug2/2 passed9.42s (proxy3.50s,selection5.91s).
Builds/Python compile pass. Three saved
HL2 ledgers validate with the new reader. First stress test failed because the
fixture's internal positive oracle expected the deliberately unsupported VS to
be admitted; changed that case to explicitly assert rejection, then passed.
No new game launch. Next pass useful with updated failure diagnostics at2560x1440:3.
See docs/MATERIAL_FAILURE_DIAGNOSTICS.md. No texture failure inferred from old data.

## 2560x1440 capture complete; exit pending (2026-09-08)

User said ready; material run triggered once. Inspector passes v18 byte_limit,
2018 attempts/1611 recorded rows/0 captures,16772740 bytes. Recorded reasons:
1417 unsupported_shader,168 unsupported_or_missing_evidence,6 primitive minimum,
20 target mismatch.2560x1440 target is confirmed; generic failures do not isolate
which material/resource evidence stage failed. Repeated unsupported-shader full
histories dominate the ledger despite selection sampling. Inventory completed
2962 draws at byte_limit. Analysis saved in bundle material-analysis.json.
Next implementation: stage-specific evidence failures and bounded repeated
unsupported-shader diagnostics, preserving full histories on accepted draws.
No missing texture inference or material replay is justified from0 captures.
Runner session84987 still owns game/proxy; await normal exit and cleanup.
Do not trigger again or rebuild deployed proxy. No additional gameplay yet.

## Active 2560x1440 material pass (2026-09-08)

User authorized launch and other diagnostics. Launched prepared bundle
build/game-passes/hl2-material-2560-v18-20260908, run material, runner session84987.
Full v18 flags and shader inventory/trace/target diagnostics together; selection
2560x1440:3,60 trace presents. No game settings changes. Armed, NOT triggered.
Wait for user gameplay readiness, then trigger once. Do not launch again or
rebuild deployed proxy. After capture inspect ledger/assets and inventory;
wait for normal exit and verified cleanup before native material comparisons.

## Selection pass closed; next material bundle prepared (2026-09-08)

User confirmed closed. No HL2 process; bin/d3d9.dll independently absent.
Runner confirms exit0, proxy_removed true, executable unchanged,222.843s.
Trace60 presents/166252 events/11646 shader draws/0 failed calls.
Selection analysis remains4096 attempts,83 sampled size mismatches,0 captures.
Observed2560x1440 is the next material target; do not change game settings.
Prepared fresh provenance-checked bundle with matching baseline:
build/game-passes/hl2-material-2560-v18-20260908. NOT launched.
Next run material with full v18 flags, selection2560x1440:3,60 trace presents,
wait-trigger and shader inventory. Wait for user gameplay readiness before trigger.

## Selection capture complete; exit pending (2026-09-08)

User said Ready; triggered selection once. Inspector passes: v18 attempt_limit,
4096 total attempts,83 recorded rejections,0 captures,868122-byte ledger.
All recorded reasons selection_target_mismatch. Observed target descriptors:
32x32 (4 examples),256x256 (8),640x360 (5),1024x1024 (8),2560x1440 (58);
all format21/no multisampling. Counts are sampled examples, not total population.
No5120x1440 accepted target. Next material selection should be2560x1440:3,
using a fresh bundle and unchanged game settings. Evidence saved to
build/game-passes/hl2-selection-v18-20260908/selection-analysis.json.
Current game run still needs normal exit and runner cleanup (session36239).
Do not trigger again, relaunch or rebuild the deployed proxy while it runs.

## Active selection gameplay pass (2026-09-08)

User explicitly requested launch and will report gameplay readiness. Fresh bundle
build/game-passes/hl2-selection-v18-20260908; run selection; runner session36239.
Full v18 flags,5120x1440:3,60 trace presents. Updated selection sampling proxy.
Matching baseline provenance reused. Armed, NOT triggered. Wait for user readiness
then trigger once. Do not launch again or rebuild deployed proxy. After bounded
capture, normal game exit and runner cleanup must precede native material replay.

## Selection diagnostics complete (2026-09-08)

HL2 previous pass exited0; executable unchanged and proxy removed/absent.
Implemented selection_observed target/primitive metadata on rejected draws.
v18 optional advertised sampling retains first4 per descriptor/reason (64 keys)
plus every64th attempt. Full histories retained, accepted rows unsampled.
Inspector reports recorded observed target counts, policy, and total attempts.
Older headers remain readable; older strict readers reject new optional header.

Release capture61.94s, surface39.04s, workflow2.47s passed. Selection final1.96s
passed after fixture rebuild. Debug2/2 passed5.52s (proxy3.13,selection2.38).
Release/Debug builds and3-file py_compile pass. Stress4096 attempts =>67 records,
attempt_limit, under1MiB, unchanged native image hash. Matching16 admitted draws,
legacy unsampled selection, extent/minimum metadata and10 malformed cases pass.
First focused run lacked optional header admission; fixed. During regression the
new stress test ran before its fixture rebuild and failed partial completion;
rebuilt fixture and reran selection successfully. No production test failures remain.

Next targeted gameplay can identify actual dimensions and reach later targets
without early duplicate selection records filling the ledger. No launch here.
See docs/HL2_MATERIAL_V18_RESULT.md. No missing texture conclusions are justified.

## Triggered HL2 v18 result; exit pending (2026-09-08)

User said ready; capture triggered once. Ledger inspector passes: v18 byte_limit,
1574 attempts,1573 recorded rejections,0 captures. Every rejection is
selection_target_mismatch (requested5120x1440). Ledger16,774,831 bytes due to
repeated write histories on early rejection. Actual target dimensions are not
recorded in these rejected rows. Inventory2861 draws includes288 pinned VS/PS
pairs. No texture/material admission conclusion is possible. Analysis saved in
build/game-passes/hl2-material-v18-20260908/material-analysis.json.
HL2 PID54812 still running; runner session30813 owns proxy and waits for exit.
User asked to exit normally. Do not replay/rebuild deployed proxy or launch again.
Next implementation: compact early selection rejections and observed target
extent evidence, then reassess another pass. One guessed write_evidence.inc path
was absent during search; no files changed in source and no repeat search needed.

## Active HL2 v18 pass (2026-09-08)

Fresh bundle build/game-passes/hl2-material-v18-20260908; run material.
Native baseline reused with verified executable/argument provenance from
hl2-multidraw-20260907. Full v18 flags,5120x1440:3,60 trace presents.
Runner exec session30813 owns deployed bin/d3d9.dll and waits for normal exit.
Capture is armed but NOT triggered. Wait for user to report active gameplay,
then use game_pass.py trigger <bundle> --name material. Do not launch again.
After capture completion ask user to exit normally; wait for runner cleanup,
verify proxy absence, inspect ledger/assets, then run normalized material replay.

## Game-sized material diagnostic (2026-09-08)

Implemented --normalized-material with native RRT_PIXEL_REPLAY2. Captured target
extent/viewport preserved; explicit float/no-MSAA/no-depth fixed-state comparison
with captured material/samplers. Strict default and protocol1 retained. Bound:
8 million pixels,8192 per dimension; checked viewport and readback pitch, full-target
clear. Diagnostic-only hash budget avoids weakening scene-file constraints.

Release6/6 passed202.39s: capture59.90s, compressed28.27s, upload46.26s,
dirty27.35s, surface38.23s, scope2.36s. Scope report:
build/x86-vs/Release/texture-scope-lvqmik3r/scope-comparison.json.
5120x1440 maximum error2.79876e-8 (6,125,636 nonzero lanes); offset viewport
2.11298e-8 (43,000 lanes). Both changed-texture controls differ. Strict/normalized
128x96 hashes match;8 native and4 Python malformed scope cases reject.
Release/Debug fixture builds and three-file py_compile passed.
First scope run failed because scene::Digest rejects large images; fixed locally
with bounded diagnostic SHA256. No capture format or resource admission changes.

Another targeted HL2 v18 material pass is useful now: old v5 evidence has no
texture/material payload. Instructions/scope in docs/GAME_SIZED_MATERIAL_COMPARISON.md.
No HL2 process or deployed game-bin proxy on check. Texture upscaling stays in
its existing future roadmap. Debug2/2 passed72.34s: capture67.34s, scope4.99s.

# Progress Log

## 2026-09-08 — partial UpdateSurface evidence v18

- Added --position-surface-uploads / RRT_POSITION_SURFACE_UPLOADS=1 requiringv17.
  Canonical COM identity resolves SYSTEMMEM/DEFAULT private texture-mip aliases.
  Same-format, unscaled, bounded rectangles establish destination block/pixel
  coverage only after stable native success. Known source regions suffice even
  when the rest of the source is unknown. All destination mip bytes must be known.
- Added bounded128-entry surface history with storage charged to the128MiB
  shadow budget. Failure, unknown inputs, gaps/open access, unsupported copies
  and exhaustion invalidate destination evidence. UpdateTexture coverage is not
  implicitly mixed into a surface history; whole uploads may replace that history.
- V18 origin/surface_transfers records preserve source IDs/revisions, mip indices,
  extents and rectangles. Python validates independent coverage/bounds/alignment/
  consistency. Reader/importer/replay/runner support v18. Base/Ex hook order audited.
-32 admitted cases across RGBA/DXT1/3/5 checked exact bytes across16 draws each;
 32 restored comparisons matched at maximum6.93656e-8.51 native/proxy scenarios
  matched all24 float-image hashes.19 native negatives,48 malformed records and
 4 legacy runs reject. Offset/staged/mip-to-mip copies, recovery, history limits
  and transitions back to whole UpdateTexture uploads are covered.
- Split compressed/upload/dirty/surface matrices into independent fresh CTest
  cases, each120s with a shared native resource lock. Core position_capture keeps
 180s and now takes41.09s Release/48.83s Debug. Focused surface31.59s passed.
- Release/Debug builds and ten-file Python compile pass. Release14/14 passed
 166.82s (surface28.92s). Debug8/8 passed201.57s overall (surface39.24s); every
  individual test stays below its timeout. Release report:
  build/x86-vs/Release/texture-surface-ozf1aoix/surface-upload-comparison.json.
- Updated handoff and SURFACE_UPLOAD_QUALIFICATION.md. Next game-sized isolated
  material comparison/target-raster scope: saved game evidence is5120x1440 while
  the current comparator requires128x96/fixed state. No new HL2 pass yet; process
  and game-bin proxy absent on final check. Future upscaling roadmap retained.
- Two guessed scope/color filenames were absent; repository search located the
  helpers in intercept.cpp and the comparison restriction in Python. No build or
  native test failures in this slice.

## 2026-09-08 — explicit dirty texture evidence v17

- Added --position-dirty-textures / RRT_POSITION_DIRTY_TEXTURES=1 requiringv16.
  Exact SYSTEMMEM NO_DIRTY_UPDATE writes establish initialized bytes without
  creating dirty proof. Full null/explicit AddDirtyRect preserves known bytes
  and supplies full-chain notification proof. Partial rectangles cannot upgrade
  proof; invalid/failing/pending/epoch/overlap cases invalidate conservatively.
- Default v17 transfers record dirty_proof as creation/top_lock/notification.
  Reader/importer/replay/runner support it; v16 shapes and runtime rules remain.
  Managed NO_DIRTY_UPDATE remains outside admission. Generated AddDirtyRect
  pre/native/post hook order audited. Memory/asset/chain limits unchanged.
- Focused suite passed.20 admitted cases across RGBA/DXT1/3/5 checked exact bytes
  across16 captured draws each;20 replayed draws matched at maximum6.93656e-8.
  All36 native/proxy scenarios matched their24 float-image hashes.16 rejected
  scenarios,16 malformed proof records and4 native v16 rejection runs. Managed
  v17 control and invalid prerequisite cases covered.
- Release/Debug builds and eight-file Python compile pass. Final Release10/10
  passed134.06s (position_capture120.59s). Debug4/4 passed164.23s
  (position_capture156.04s). Release report:
  build/x86-vs/Release/position-capture-tkote04l/dirty-texture-comparison.json.
- Updated HANDOFF, DIRTY_TEXTURE_QUALIFICATION and related docs. Next
  UpdateSurface/partial transfers; no HL2 pass needed yet. No hl2 process or
  game-bin d3d9.dll present. Future upscaling roadmap retained.
- One atomic test patch failed due to an out-of-order hunk and was reapplied
  without the unnecessary hunk. No native/build/test failures in this slice.

## 2026-09-08 — whole-chain default-pool uploads v16

- Added --position-texture-uploads / RRT_POSITION_TEXTURE_UPLOADS=1 requiringv15.
  Private usage-zero SYSTEMMEM sources and DEFAULT destinations use bounded
  RGBA/DXT1/3/5 shadows. Full-dirty proof starts at creation, is consumed by every
  observed UpdateTexture attempt, and can return after a whole top-level write.
  Unknown/partial/lower-only inputs do not establish a whole-chain transfer.
- Generated base/Ex pre/post hooks retain COM references and source/destination
  revisions around native calls. Destination invalidated first; only native
  success, matching chains, stable epoch/revisions and no overlap/write gap copy
  complete shadows. Destinations retain independent bytes and source provenance.
  Reader validates pool/origin/transfer fields and shared-source consistency;
  importer/replay/runner supportv16. Old versions retain their pool restrictions.
-20 accepted scenarios across RGBA and DXT1/3/5 verified exact bytes across16
  draws each.80 restored draw comparisons matched (maximum6.93656e-8), plus
  managed v16 replay.56 native/proxy scenarios matched all24 float-image hashes.
 36 rejected write/chain scenarios,40 malformed records and4 native legacy runs.
  Incomplete mip chains, lower-only writes, consumed dirty proof, source changes,
  alias recovery and invalid-pool failures covered. Base/Ex hook order audited.
- Initial suite failed74.04s because this runtime faults on a null UpdateTexture
  destination. Replaced control with real resource objects and an invalid managed
  destination pool; focused suite passed. Discovery commands using wrong/globbed
  paths were corrected to generate_observers.py and rg -g '*.py'.
- Release/Debug builds and eight-file Python compile pass. Final Release10/10
  passed117.42s (position_capture103.75s). Debug4/4 passed136.28s
  (position_capture127.97s). Release artifact:
  build/x86-vs/Release/position-capture-vwxbzn9b/texture-upload-comparison.json.
- Updated HANDOFF, TEXTURE_UPLOAD_QUALIFICATION and related docs. Next explicit
  dirty notifications and UpdateSurface/partial paths; dynamic/default direct
  writes remain unqualified. No HL2 pass needed yet; no process or game-bin proxy
  present. Texture upscaling remains planned after faithful material evidence.

## 2026-09-08 — compressed texture capture v15

- Added --position-compressed-textures / RRT_POSITION_COMPRESSED_TEXTURES=1
  requiring v14 assets. Private managed usage-zero DXT1/DXT3/DXT5 now use tight
  block shadows and hashed assets. Whole mips and fully4x4-aligned partial writes
  merge initialized evidence; tiny tails retain full blocks. Copies occur before
  native unlock and become known only after success. Existing invalidation and
  memory/disk bounds remain. V13/v14 formats stay uncompressed.
- Reader independently validates block lengths, base alignment, mip count,
  pool/format/usage and content hashes. Importer preserves references; replay
  hydrates v15. Runner prerequisite and triggered v15 header tests pass.
- Native tests cover12 accepted cases with exact blocks across16 draws each,
 57 restored draws (maximum error7.00175e-8),30 proxy/native full-image hash
  comparisons,18 rejected write cases,24 malformed records and6 legacy rejection
  runs. DXT2/DXT4 rejection, uncompressed v15 replay and invalid flags covered.
- Release/Debug builds and seven-file Python compile pass. Initial capture test
 65.02s. Final Release10/10 passed78.28s (position_capture64.68s).
  Debug4/4 passed90.85s (position_capture82.40s).
  Artifact: build/x86-vs/Release/position-capture-f7ufd99y/compressed-capture-comparison.json.
- Updated handoff and compressed/asset/pixel docs. Next default-pool/update-path
  qualification; no HL2 pass needed yet. Final process/deployment check: no hl2
  process and no game-bin d3d9.dll. Future texture-upscaling plan retained.
- One search referenced missing tools/position_groups.py; rg --files found the
  actual tools/replay_position_groups.py. No implementation/test failures.

## 2026-09-08 — synthetic compressed native replay

- Native pixel payload restoration now supports DXT1/DXT3/DXT5 with bounded
  block rows, whole-block tiny tails and byte-for-byte read-only verification.
  Rejects unknown formats, misaligned compressed bases, excess mip count and
  wrong byte lengths before device creation. Native output includes alpha sum.
- Added tests/qualify_compressed_pixel.py to position_capture. Twelve synthetic
  cases exercise both samplers, rectangular chains, final1x1 LOD, filters and
  sRGB. DXT1 transparency, DXT3 explicit alpha and both DXT5 alpha modes tested.
  Nine changed-texel/alpha/LOD controls differ; opaque/zero-alpha fixtures match
  and satisfy output-alpha checks. Eighteen malformed payloads reject.
- Initial position_capture passed43.91s; selected Release10/10 passed58.29s,
  position_capture43.64s. Maximum compressed shader error8.71039e-8. Fixture
  Release/Debug builds and three-file Python compile pass. Debug4/4 passed58.91s,
  position_capture50.49s.
  Release report: build/x86-vs/Release/position-capture-d7xqoqfu/pixel-compressed-comparison.json.
- Updated handoff and docs/COMPRESSED_TEXTURE_QUALIFICATION.md. Capture admission
  stays v13/v14 uncompressed; next add versioned compressed write tracking and
  validation, then default-pool/update qualification. No HL2 pass needed yet;
  no hl2 process or game-bin d3d9.dll present. Upscaling roadmap remains deferred
  until faithful texture evidence. No implementation errors in this slice.

## 2026-09-08 — v14 external texture assets

- Added --position-texture-assets / RRT_POSITION_TEXTURE_ASSETS=1 requiringv13.
  Initialized managed uncompressed chains may now total16MiB per texture, with
 256MiB/512 exclusive new files per session in <ledger>.assets. SHA-256 filenames,
  compact {sha256,size} references and within-session deduplication. Failed writes
  charge reservations; no overwrite or automatic orphan cleanup.
- Reader/importer and diagnostic replay resolve and verify regular non-reparse
  sibling files, content hashes, sizes and budgets. Immutable verified-byte cache
  per inspection. Native pixel comparison accepts restored larger textures;
  v13 inline bounds and all format/pool/initialization admission remain unchanged.
- Native256x128 chains verified byte-for-byte, deduplicated across16 draws into
 18 files /349,528 bytes; ledger305,123 bytes. Restored original/reconstructed PS
  matched at6.73376e-8 maximum normalized error. Corrupt/missing/path/size/inline/
  legacy/budget cases rejected; relocation, cache stability and directory collision
  preservation tested. Runner flag and asset path reporting covered.
- Release/Debug target builds and ten-file Python compile pass. Initial capture
  test35.47s; selected Release10/10 (50.92s), position_capture36.71s. Debug4/4
  (57.01s), position_capture47.97s. Release artifacts: build/x86-vs/Release/position-capture-x4azddsl,
  including assets-texlarge.jsonl.assets and assets-texlarge-comparison.json.
- Updated HANDOFF and docs/TEXTURE_ASSET_STORAGE.md. Next compressed texture
  qualification, followed by default-pool/update paths before another useful HL2
  pass. No game launch; hl2 process and game-bin d3d9.dll absent on final check.
  Texture enhancement roadmap retained after faithful capture/replay.

## 2026-09-08 — captured five-sample pixel reconstruction

- Added independent HLSL cubic lightmap/base/tint/lighting/fog/alpha expression
  compiled as ps_2_b and a bounded --pixel-replay native payload. Restores original
  VS/PS, constants, input vertices, texture mip bytes and sampler/LOD settings.
  Compares original PS with reconstructed PS across all float target lanes.
- tools/replay_pixel_material.py validates completed v13 input, supports ordinal
  selection, strips inherited RRT flags and reports isolated_draw comparison with
  ready_for_frame_replay=false. Fixed128x96 raster and point/linear sampler subset;
  no production capture/proxy changes or independent CPU sampler claim.
- All16 captured draws and four synthetic high-frequency128x64 lightmap variants
  match. Release maximum normalized error1.42296e-8 captured,8.84655e-8 synthetic.
  Eight deliberately wrong fog/alpha/texel/address/sRGB/LOD/filter/one-sample
  controls differ (smallest maximum error0.00904281); threshold2e-4. Malformed
  payloads rejected. Reports in build/x86-vs/Release/position-capture-k88u_tyy/
  pixel-comparison.json and pixel-comparison-controls.json.
- Fixed initial C++ namespace/DWORD template errors and a COM lifetime teardown
  crash: restored textures were declared before Device and outlived runtime unload.
  Debugger localized cleanup after both draws completed; shader-profile change
  alone was not a fix. Native resources now release before the runtime.
- Release/Debug fixture builds and Python compile pass. Full selected Release
  regressions10/10 (49.33s), position_capture35.10s. Debug4/4 (54.47s),
  position_capture45.79s.
- Updated HANDOFF and docs/PIXEL_MATERIAL_RECONSTRUCTION.md. Next bounded external
  texture asset storage, then compressed/default-pool/update-path qualification
  before a useful new HL2 pass. No game launch; checked hl2 absent and game-bin
  d3d9.dll absent. Future texture enhancement roadmap retained.

## 2026-09-08 — v13 initialized texture/mip snapshots

- Added --position-texture-inputs / RRT_POSITION_TEXTURE_INPUTS=1 requiringv12.
  Admits observed private managed usage0 A8R8G8B8/X8R8G8B8 chains<=64KiB each.
  Tracks tight mip bytes and masks under the shared128MiB shadow budget. Partial
  direct locks merge only after successful unlock; copy occurs before native
  unlock. Direct read-only locks preserve knowledge without establishing it.
- Invalidates failed locks/unlocks, unsupported flags, dirty notifications,
  copies, generated mips and texture surface-alias writes; resets invalidate by
  epoch. Unsupported write paths do not synthesize texels. Final wrapper audit
  added BaseTexture9 GenerateMipSubLevels alongside derived interface coverage.
- V13 texture_inputs carries two sampler-matched IDs/revisions, observed origin,
  tight mip bytes and SHA-256. Reader checks shape/format/budget/identity/digest;
  importer preserves metadata. V12 descriptor contents stay unknown independently.
- Native controls verify every pattern byte after full/partial writes, read-only
  locks and alias refresh, and reject failed locks/copies, alias writes, generated
  mips and incomplete recovery. Mutated-ledger, native hook-order and reset-wiring
  checks included. No dedicated native failed-unlock/reset recovery case yet.
- Initial position_capture32.08s; full Release selected suite10/10 (45.13s),
  position_capture31.43s. Both builds and Python compile pass. Final affected
  Release5/5 (39.97s; position_capture29.99s), Debug4/4 (47.87s;
  position_capture39.40s) after base-interface writer correction. Final Release
  artifacts: build/x86-vs/Release/position-capture-dr2aliay.
- Updated HANDOFF and docs/POSITION_TEXTURE_INPUTS.md. Next independently
  reconstructed five-sample PS against captured synthetic mips; bounded external
  storage needed before game-sized textures. No HL2 launch; checked no hl2 process
  and game-bin d3d9.dll absent. Texture enhancement remains future faithful-replay
  work. One reverse-order patch failed and was reordered before applying.

## 2026-09-08 — v12 paired pixel material state

- Added --position-pixel-material / RRT_POSITION_PIXEL_MATERIAL=1, requiring
  v11 and the full evidence chain. Exact paired1792-byte PS, successful known
  external c11/c12/c29/c30 writes and finite getter values, s0/s1 effective
  sampler DWORDs, local bound texture IDs, LOD/autogen filter and mip descriptors.
  At most16 levels/dimensions16384; contents explicitly unknown.
- PS knowledge invalidates on state blocks/reset. Added inherited texture LOD
  and autogen-filter overlap guards and conservative v12 overlap rejection.
  Reader validates program/state/descriptor structure; importer retains metadata.
- Paired native fixture exercises patterned mip chains, binding swaps and
  changing constants/sampling. Original VS and evaluated passthrough use the same
  native PS; no independent PS reconstruction claim. Controls include missing/
  failed PS writes, state-block rejection and refresh, missing texture, wrong PS,
  invalid prerequisites and mutated records. All legacy tests remain enabled.
- Release/Debug builds pass. Release selected regressions10/10 (55.79s), including
  position_capture42.63s. Artifacts: build/x86-vs/Release/position-capture-lcpcvqmu.
  Debug selected regressions4/4 (63.59s), position_capture55.81s. Python compile passes for seven changed
  generator/tools/tests. Earlier position_capture pass40.00s before final controls.
- Updated HANDOFF, audit sequence and docs/POSITION_PIXEL_MATERIAL.md. Next
  initialized 2D texture/mip provenance and texels, then five-sample pixel replay.
  No HL2 launch; checked no hl2 process and game-bin d3d9.dll absent. Future texture
  enhancement roadmap remains after faithful source capture/replay.

## 2026-09-08 — v11 initialized material vertex inputs

- Added exact audited stride48 COLOR0/UV0/UV1 initialized-byte capture and known
  c12/c16 requirements. Ten evaluated lanes cover t0.xy/t2.xy, normalized RGBA,
  t4.w and raw fog scalar. Limit1024 triangles/draw retains bounded row size.
- Independent Python calculation and malformed-evidence rejection; importer
  preserves metadata. Runner exposes --position-material-inputs with v10 chain.
- Native fixture compares24 original-VS/CPU-passthrough probes for perspective
  UV, packed RGBA and distance/fog interpolation, including fog floor. Wrong CPU
  UV fails; uninitialized bytes, unknown constants, overflow and budget reject.
  Proxy state-block run rejects24 draws for unknown_constants. Fog observation
  uses duplicate oD1; no fixed-function fog or paired material replay claim.
- Full x86 Release/Debug builds pass. Selected Release regression suite10/10
  (39.52s); Debug4/4 (42.68s). Final position_capture tests26.18s/34.08s.
  Python compile passes for all seven changed tools/tests. Release capture
  artifacts: build/x86-vs/Release/position-capture-mzfv9a1e.
- Updated HANDOFF and docs/POSITION_MATERIAL_INPUTS.md. Next exact PS rows and
  sampler/resource descriptor evidence, then initialized texels/mips. No HL2
  launch; final check no hl2 process and game-bin d3d9.dll absent. Texture
  upscaling roadmap retained for future work after faithful material replay.

## 2026-09-08 — material audit and texture-enhancement roadmap

- Audited exact saved VS/PS pair with immutable bounded snapshot utility. Original
  inventory231 pair draws; multi-draw294. PS1792 bytes,5 texture instructions,
  external PS c11/c12/c29/c30. Saved JSON/assembly under build/material-audit-20260908.
  Same-input Release/Debug reports agree; malformed truncation rejected; py_compile
  passes. No native runtime changes or regressions requiring GPU rerun.
- Documented precise UV0/UV1/color/fog capture dependencies and next native/CPU
  interpolation slice in docs/HL2_MATERIAL_AUDIT.md. Independent inventory ordinals
  do not correlate the16 position captures to this PS.
- Added docs/TEXTURE_ENHANCEMENT_ROADMAP.md and linked workbench roadmap. Base-color
  enhancement follows faithful capture/replay, with reversible asset manifests,
  alpha/mip/seam handling, semantic texture paths and memory/runtime gates. Lightmap
  resizing deferred because exact shader has baked reference scaling. No models
  selected/downloaded and no game pass launched. HANDOFF updated.

## 2026-09-07 — controlled color replay

- Complete: full Release10/10 (41.03s), Debug4/4 (42.56s). Final audit extended
  v10 overlap windows to non-writer device state setters; regenerated forwards and
  both proxy builds pass, focused capture reruns pass Release26.99s/Debug33.26s.
  Python compilation passes. No failures. Serialized synthetic tests do not claim
  native concurrent rendering qualification.
- Analytic nonzero-clear/alpha blend, order, overwrite and additive controls pass
  with zero native-vs-CPU color error. Prefix/unsupported-state/native-input guards
  pass; generic legacy admission stays conservative. Color reports name nonzero
  alpha pixels separately from geometry coverage.
- Updated HANDOFF and docs/POSITION_COLOR_REPLAY.md. Final HL2 closed/bin proxy
  absent; no game launched or modified. Next use saved inventory to audit a bounded
  actual HL2 pixel/material path. No gameplay run useful for the exact synthetic PS.

- Full Release10/10 passed41.03s; all native/analytic blend, overwrite, order,
  additive and malformed-prefix controls pass. Both native builds and Python
  compilation pass. Added docs/POSITION_COLOR_REPLAY.md. Debug and final guard
  reruns subsequently passed above; no failures or game deployment.

- Added v10 pixel/state evidence, bounded reader/import/runner plumbing and separate
  replay_position_colors.py. Native fixture accepts RRT_POSITION_COLOR1 with actual
  clear, per-draw RGBA/blend state; legacy group mode retained. First Release capture
  controls passed26.59s including analytic alpha blend and missing-prefix rejection.
  Added remaining blend/order/native malformed controls and N-patch exclusion;
  final Release/Debug builds/regressions pending. No game launch or failures.

## 2026-09-07 — closed standalone color-target scope

- Complete: Release10/10 passed40.78s; Debug4/4 passed41.68s. Release/Debug native
  builds and Python compilation pass. No failures. Generated D3D9/Ex creation
  callbacks and origin/history/gap rejection controls pass. Native raster output
  remains exact. HANDOFF and docs/POSITION_SURFACE_SCOPE.md updated.
- Final check: HL2 closed, bin proxy absent, no game deployment or changes. Next
  qualify controlled pixel shader and supported color replay state for the admitted
  subset. v9 excludes depth and general texture aliases; no new gameplay pass yet.

- Full Release10/10 passed40.78s, including failed-unlock preservation and runner
  v9 propagation. Positive scopes now qualify complete color-write call coverage;
  native raster oracle remains exact. Debug subsequently passed as recorded above.

- Implemented v9 opt-in origin/MRT/access evidence and strict narrow color-call
  qualification. Release producer build passes; native positive/negative controls
  running. No game launch. Resource sharing is excluded by creation parameters;
  actual cross-process sharing is not induced in these tests.

## 2026-09-07 — ordered surface-write evidence

- Complete: full Release10/10 (30.31s), Debug4/4 (34.53s); final hardening capture
  reruns passed Release19.87s/Debug24.65s. Test report polling now tolerates only
  transient file absence/access denial under its original deadline; final runner
  reruns passed Release2.42s/Debug2.72s. All trigger/output/cleanup assertions remain.
  Both native builds and Python compilation pass. No outstanding failures.
- Added full writer audit and contract in docs/POSITION_WRITE_EVIDENCE.md and
  updated HANDOFF. Initial contents remain unknown and all state-aware/complete-
  coverage admission false. Next qualify a closed single-target scope (aliases,
  MRT/shared resource exclusion, outstanding write access) before supported replay.
- Final safety check: no HL2 process and bin/d3d9.dll absent. No game launched,
  deployed or changed. No further gameplay pass needed for this evidence-only slice.

- Full v8 Release10/10 passed30.31s; Debug4/4 passed34.53s. A final bounded-loop/
  serialization hardening rerun passed Release position_capture19.87s but exposed
  a transient Windows PermissionError in game-pass test polling of report.json.
  Resolved by the bounded polling fix and passing reruns above.

- Read HANDOFF and newest logs, checked HL2 closed/proxy absent, retained existing
  planning files. No gameplay launch. Implemented opt-in v8 producer/reader/import/
  runner plus per-draw grouped admission reports. Native Release build passes;
  focused capture controls running. No state-aware replay admission is enabled.

## 2026-09-07 — clear-operation evidence and admission

- Implemented v7 opt-in latest-clear payload, copied pre-call and committed only after native success. Captures flags/colour/depth bits/stencil, up to16 rectangles, target/depth IDs, descriptor, viewport/scissor and reset/serial. Successful unrecordable clears invalidate prior payload; failed clears preserve prior successful evidence.
- Reader/importer/group reports preserve/validate payload. Added conservative initial-content assessment: full-clear candidates are distinguished from known current contents; all remain unverified until ordered intervening-write coverage exists. No silent state-aware replay promotion.
- Initial Release capture/group/runner3/3 pass19.39s; native tests include full/partial/depth-stencil/failed/oversized clears, no output changes.
- Final Release10/10 pass32.01s; Debug4/4 pass27.17s. Both native builds and Python compilation pass; no test failures. HL2 closed and bin proxy absent, no game launch/deployment. Contract in docs/POSITION_CLEAR_EVIDENCE.md. Next bounded ordered surface-write evidence and gap markers; initial contents remain unknown until coverage is established.

## 2026-09-07 — target and composition-state evidence

- Final Release10/10 pass30.15s; Debug4/4 pass26.36s. Native Release/Debug builds and Python compilation pass. Positive depth-surface/enabled-blend evidence verified, along with same-size surface recreation and conservative grouping splits. No failures. HL2 not running; bin proxy absent, no game launch/deployment this slice.
- Documentation: POSITION_COMPOSITION_EVIDENCE.md. Next full bounded clear-operation evidence and initial-content guards before applying captured state in replay; do not mistake successful metadata collection for game-faithful composition.

- Added opt-in v6 identity/clear/binding/state metadata, strict reader and importer preservation, grouping separation and guarded runner option. Same-target reuse versus same-size surface recreation tests pass; clear/binding serials and alpha-reference changes remain visible. Initial Release capture/group/runner3/3 pass18.89s, native output unchanged. Added bound depth-surface/enabled-blend test and pending commit boundary guard; final suites pending.
- No full clear-operation capture or state-aware raster replay implemented: serials are conservative markers. No game launch yet and no errors so far.

## 2026-09-07 — offline grouped position replay

- Final Release6/6 pass15.88s; Debug3/3 pass16.51s. Both fixture builds and Python compilation pass, grouped JSON reports identical across configurations including native output fingerprints. No test failures. Proxy absent; game not launched or modified.
- Four48-triangle groups compose with exact coverage/zero error; native counts2593/2588/2555/2565. Real reports saved in hl2-multidraw-20260907/reconstructed/group-release.json and group-debug.json. Full contract/limitations in docs/HL2_GROUPED_POSITION_REPLAY.md.
- Next actual render-target identity and clear/depth/blend evidence, then state-aware composition. Do not call compatible descriptor grouping recovered pass identity.

- Added standalone --position-group fixture and replay_position_groups.py. Immutable ledger validation/digest, explicit interval/view grouping and ordered per-draw constants; one clear per group. Depth/blending-off overwrite semantics are diagnostic, not reconstructed game passes.
- Initial real Release replay matches all4 groups, covered2593/2588/2555/2565, zero error. Disjoint composition, independent model constants, overlapping order,16-draw bounds and malformed/grouping controls pass. No failures; Debug and regressions pending.

## 2026-09-07 — multi-draw pass qualified after exit

- Verified native exit0 after124.297s, executable unchanged and owned bin proxy removed; runner98267 complete. No HL2 process remains.
- Release/Debug GPU replay of16 inputs:12 visible matches,4 empty on both paths; all exact coverage and zero normalized error. Preserved reports in reconstructed/gpu-release-after-exit.json and gpu-debug-after-exit.json. No failures.
- Saved-input analysis:1 distinct c0,1 model-row set,4 clip-row sets; clip rows identical within each interval. Captured coverage changes agree on GPU, but cause is not labeled camera motion without further evidence.
- Trace60 presents/8131 shader draws/138309 events/0 failed calls. Inventory2957 draws/74 programs/48 families/0 failed or unavailable queries. Added docs/HL2_MULTIDRAW_RESULT.md; next offline per-interval composition using existing captures, not another immediate game pass.

## 2026-09-07 — real multi-draw HL2 capture

- User confirmed gameplay, trigger succeeded. v5 capture_limit:16 accepted from524 attempts;172 minimum-primitive,199 unsupported shader,137 target-mismatch rejections. Four position-content keys with3/35/4/6 triangles repeat at intervals207..210. All5120x1440.192 submitted triangles,48 triangles summed across distinct position-content blocks (not proof of unique world geometry).
- Source SHA256dd0ef91fffbee117c325ffd4781a433c5f1743384a6a99bdd3655687262d2302. Offline validation passed. GPU replay deferred until normal game exit; runner98267 owns proxy cleanup. No persistent-object identity inferred.

## 2026-09-07 — bounded multi-draw capture

- Guarded multidraw pass launched: PID35292, runner session98267, v5 policy5120x1440:3,4-per-interval/16-total. Proxy SHA256da8e84c54203b0a250bd5a39ee4df68d815f37dbbe9992195fdbca18dd03ccdc. Running verified; trigger and ledger absent, awaiting user in-game confirmation. Leave runner alive for cleanup; no real v5 results yet.

- Final Release9/9 pass25.46s; Debug5/5 pass29.23s. Both native builds/Python compilation pass; saved v3/v4 captures still import with4 submissions/1 position-content key. No failures. Prepared hl2-multidraw-20260907 with reused matching baseline; game not running and bin proxy absent before preparation.

- Implemented opt-in v5 with4 accepted draws per interval/16 total, explicit selection required; retained16MiB/4096-attempt/120-present limits. Separate pending reservation and accepted count preserve failed-draw recovery. No hash-based object inference/dedup.
- Reader validates fixed limits, duplicate indexed timing and interval/total quotas. Importer accepts up to16 explicit assignments and reports position-content count separately from submissions. Replay/reconstruction now accept nonempty validated present_limit captures.
- Initial native Release capture/runner tests2/2 pass17.43s, including repeated same-interval inputs, failed native draw, overflow skipping, no-present partial capture, present-limit replay, invalid options/metadata and16 explicit instances. Builds/tests so far have no failures. Final extended suites pending.

## 2026-09-07 — selected HL2 pass closed and qualified

- User confirmed closed. Native exit0 after723.656s, executable unchanged, runner-owned bin/d3d9.dll removed and absence verified. Runner72773 completed normally.
- Release and Debug post-exit GPU replay match all4 real18-triangle samples,427 covered pixels each at diagnostic128x96, exact coverage and zero normalized error. Reports: hl2-selected-20260907/reconstructed/gpu-release-after-exit.json and gpu-debug-after-exit.json. No failures.
- Final trace:60 presents,12360 shader draws,176386 events,0 failed calls,frame_limit. Inventory:2916 draws,80 programs,54 families,0 failed/unavailable queries,byte_limit.
- Selection/timing now qualified on this narrow real-game evidence. Same geometry across four samples is not broader scene coverage or object tracking. Next broaden bounded candidate coverage while retaining explicit selection and provenance; no further game launch made.

## 2026-09-07 — selected HL2 capture triggered

- User confirmed gameplay; guarded trigger succeeded. v4 captured4 samples across consecutive intervals726..729. All target5120x1440,18 triangles and40 unique indices each, same geometry hash.225 attempts with136 unsupported shader,22 minimum-primitive and63 target-mismatch rejections.
- Offline validation and reconstruction pass:72 submitted triangles across4 samples, no degenerates,54 positive clip-W corners each. Digest c3e1ee6e61abea13e8fc4ba4aed20ddc58af97198d5767f2970404770acfedaf. Native raster validation intentionally deferred until normal game exit. Trace has frame_limit footer176386 events. Runner72773 still owns cleanup.

## 2026-09-07 — explicit capture selection

- Guarded selected pass launched and verified running: PID12352, runner session72773, policy5120x1440:3. Proxy SHA2561c5d2bdf8616dbd3ef3089a10fbcf120dd447eb9cd13af354c15462f0af0ee4a. Trigger/position ledger absent, awaiting user gameplay confirmation. Leave runner alive for normal-exit cleanup and defer GPU replay until game closed.

- Final Release9/9 pass20.38s, Debug5/5 pass17.35s. Both native builds, Python compilation and saved-v3 inspection pass. Tests validate excluded-target recovery within one interval, count threshold, invalid policies, tampered evidence and runner forwarding. HL2 not running and bin proxy absent before preparation.
- Prepared build/game-passes/hl2-selected-20260907 with unchanged executable/arguments and reused successful baseline. Intended selected policy5120x1440:3, no automatic fallback. No real v4 results yet.

- Added v4 exact target dimensions/minimum primitives with explicit rejection reasons, strict reader admission and runner propagation. Initial patch failed atomically on partial-line context; corrected.
- Fixture compilation hit Windows `small` macro collision; renamed local surface to rejectedTarget. Initial chained CTest used stale fixture and failed selected completion; runner selection test passed. Subsequent tests must follow a successful build.

## 2026-09-07 — HL2 v3 pass closed and replay verified

- User confirmed game closed. Runner exit0,177.563s, executable unchanged; proxy_removed=true and bin/d3d9.dll absence independently verified. Runner session94867 completed normally.
- Release and Debug post-exit replay both matched all4 real samples: exact coverage,12288 covered pixels per diagnostic128x96 draw, zero normalized error. Reports saved exclusively as reconstructed/gpu-release-after-exit.json and gpu-debug-after-exit.json. Initial gpu-release.json failures preserved. Failure disappearing after game exit does not establish the exact graphics-device failure cause.
- Final trace:60 presents,17100 shader draws,222300 events,0 failed calls, normal frame_limit. Inventory:3104 draws,79 programs,57 families,0 failed/unavailable queries, byte_limit.
- Timing validation complete for this narrow real sample. Same256x256-target two-triangle content across four intervals remains limited scene coverage. Next target/pass-aware selection; no further game launch made.

## 2026-09-07 — real HL2 interval capture triggered

- Position capture complete:76 recorded attempts,4 accepted and72 rejections. Consecutive intervals1530..1533; repeated two-triangle256x256-target geometry. Reconstructed8 triangles in4 separate groups. First Release GPU replay failed with generic D3D failure on all draws while game running; report retained in reconstructed/gpu-release.json. Asked user to exit normally before retry/cleanup verification. Do not call this GPU-validated yet.

- User confirmed gameplay. Triggered hl2-frames-20260907/runs/frames through the guarded runner; marker creation succeeded. Awaiting evidence inspection, replay and normal-exit cleanup. Do not rebuild the deployed DLL or terminate runner session94867.

## 2026-09-07 — frame-correlated sampling in progress

- Implementation complete: v3 opt-in via runner --position-frames, random session identity, device-local successful-Present intervals, reset epochs, per-interval reservation and120-presentation bound. v1/v2 remain supported/default unchanged. Adapter preserves timing; reconstruction groups separately by interval. Explicit fixture instance updates reuse content and preserve changed constants; no automatic object matching.
- Final tests: Release9/9 (15.83s), Debug5/5 (12.47s); expanded final Release position_capture4.27s. Both native builds and Python compilation pass.
- Prepared fresh guarded HL2 bundle build/game-passes/hl2-frames-20260907 with unchanged executable/arguments and reused successful matching baseline. Launched run frames, PID41188, runner session94867; status running. Temporary bin proxy hash ecac63e12f49f773f62a0993751edc38491c9b99af1e1c59637e1c313958f0aa. Trigger and position ledger absent: awaiting user gameplay confirmation. Leave runner alive for owned-proxy cleanup after exit.

- Opt-in v3 producer and reader/adapter tests initially pass3/3 Release. Device and swap-chain successful-Present intervals and120-present termination pass; default remains v2.
- Extended negative fixture assumed Present inside BeginScene fails; this driver returned success. Removed that driver-dependent test (not the S_OK-only production guard); reset fixture validation continues. No claim of experimentally tested failed-Present behavior.

## 2026-09-07 — offline capture-to-scene integration

- Added tools/capture_position_scene.py: bounded validated snapshot, exact source digest, immutable candidates, explicit ordinal-to-instance assignment API/CLI and diagnostic provenance. Default inspection makes no assignments; duplicate target identities reject rather than merging draws. The plan skill kept this slice scoped to offline integration.
- Refactored position inspection to expose inspect_bytes so validation and digest share one byte snapshot. No D3D9 hook or game behavior changes.
- Real saved HL2 input imports4 draws/57 triangles with exact positions/constants. Added assignment/digest/stale/conflict/budget rollback, unresolved retention, removal/reset, incomplete/I/O-error rejection and CLI tests. Extended native proxy v2 tests for exact provenance preservation under buffer recreation/reuse.
- Release7/7 tests pass10.07s; Debug6/6 pass8.83s. Release native targets build, Python compilation passes. No test failures. HL2 bin/d3d9.dll absent; no game launch or installation change.
- Next: coherent frame/session capture metadata and bounded multi-frame sampling before any temporal identity claims or renderer integration. Tell the user to enter game only once that next capture producer is ready and a guarded pass is prepared.

## 2026-09-07 — advanced-engine reference and resource provenance

- Final results: Release selected suites5/5 (8.11s), Debug2/2 (6.07s). Final reader-v1/v2 regression3/3 Release (3.25s); Python compilation passes. No game launch and bin proxy remains absent. Next instance correspondence/update integration can proceed offline before asking for another gameplay capture.

- Archived advanced-engine user reference with qualifications in docs/ADVANCED_ENGINE_ARCHITECTURE.md. No engine memory hooks or sampler nullification implemented. API-aware capture remains the reusable foundation, engine adapters optional/version-pinned.
- Position ledger v2 adds tracked shadow-lifetime resource IDs, observed mutation revisions, wrapper-relative reset epoch and constant-knowledge revision. Native successful writes and invalidation advance revisions; IDs are not semantic object identities. v1 remains readable without invented provenance; exporter preserves v2 metadata.
- Added reuse/recreation fixture coverage: fresh VB/IB IDs differ, persistent VB/IB retain IDs with advancing write revisions, native GPU output unchanged. Existing real v1 capture replay and reconstruction pass. Full final test results pending.
- Documentation patch failed atomically due an unnecessary mismatched API-roadmap context. Removed that hunk and applied the intended reader/documentation changes successfully; no source changes were lost.

## 2026-09-07 — API/engine roadmap and scene-state prototype

- Final seven scene-state unit tests pass; selected Release scene/real GPU oracle/reconstruction CTests3/3 (1.06s), Python compilation passes. No game launch; temporary HL2 proxy remains absent.

- Added requested future SM3/UE3, separate DX10/BioShock-family, DX8 via d3d8to9 and early DirectDraw/Direct3D via dxwrapper tracks. Verified wrapper maintainer sources and Microsoft DX10/SM4 documentation; links and qualification gates in docs/API_ENGINE_ROADMAP.md. No wrapper installed or commercial game modified; exact BioShock edition/API remains its own profile rather than assumed generic UE3 support.
- Implemented bounded offline position_scene.py with content-addressed geometry, explicit instance identities, independent constants, atomic deltas, explicit removal, reference-based release and epoch/sequence invalidation. No automatic identity inference or live proxy/renderer integration. Initial five unit tests pass; extended copy-isolation/unseen-retention tests pending.
- Current capture ordinals cannot establish persistent object identity. Documented required resource-generation/update/instance-correspondence evidence before live integration in docs/POSITION_SCENE_STATE.md.

## 2026-09-07 — real-input independent GPU position replay

- Extended isolated position fixture with bounded --recorded-position input and exact program admission. Real corner positions/constants replay independently; original game index topology is validated and expanded to sequential corners. Native and CPU paths share diagnostic raster state, not game materials/occlusion. No runtime proxy changes.
- Three real draws match coverage and float position output exactly at128x96: ordinals1/67/68 cover12,288/659/1,617 samples; ordinal66 empty on both paths and explicitly not visible validation. Reports written exclusively as gpu-verification-release.json and gpu-verification-debug.json in reconstructed-grouped.
- Added local recorded_position_oracle and position_reconstruction CTests; malformed/oversized/nonfinite/truncated/trailing native inputs reject. Release selected tests5/5 (4.05s), Debug3/3 pass; Python compilation passes. Game bin proxy remains absent.
- Documented precise scope in docs/HL2_RECORDED_POSITION_REPLAY.md. Next capture selection/coverage and persistent identity/update handling, then material evidence; no universal engine/game compatibility or live relighting claim.

## 2026-09-07 — real captured geometry reconstructed offline

- Confirmed late trace completion: 194,529 events,60 presents,13,395 shader draws,zero failed calls. Game exited0 after332.406s, executable unchanged, owned DLL removed and absent. Earlier empty trace checks were provisional; no speculative trace code fix made.
- Added optional validated-record return to position reader and reconstruct_positions.py exporter. Exclusive new output directory, bounded source hash provenance, per-draw raw/model OBJ, independent index consistency/range checks, bounds, matrix analysis, clip-w/degenerate counts and exact render grouping.
- Exported four draws/57triangles/127 per-draw vertices to reconstructed-grouped. Draw1 target256x256 differs from5120x1440 draws66–68; latter share clip rows. All model rows identity; draw66 entirely negative clip-w. No camera/world/material semantics inferred and no cross-draw merging.
- Reconstruction tests pass (counts/indices, inverse, grouping, partial rejection, collision preservation). Release position_capture regression passes2.11s, Python compilation passes. Both initial reconstructed and final reconstructed-grouped artifacts retained; nothing overwritten/deleted.

## 2026-09-07 — combined live position/inventory result

- Triggered all outputs after user confirmed gameplay. Position reader validates four draws at ordinals1/66/67/68 (2/2/18/35 triangles), required constants and initialized source bytes from 1.5 MiB VB / 64 KiB IB; 65 unsupported shader rejections. Four-capture limit reached normally.
- Inventory validates 2,919 draws, 49 families, 76 programs, no failures/missing queries, byte-limit completion. Position ledger hash and scope recorded in docs/HL2_COMBINED_PASS_RESULT.md.
- Trace read failed twice as empty (0 bytes). Present-only activation differs from successful indexed-draw probes; cause not established. Preserve the failure and diagnose separately rather than claiming all three completed.
- HL2 PID45776 remains running/responding; runner session86621 owns cleanup after normal exit. No need for another game run to start offline position analysis.

## 2026-09-07 — combined position/inventory capture (in progress)

- Implementation validation complete. Final viewport/target metadata Release position+runner tests 2/2 (4.19 s), Debug position 2.63 s; Python compilation passes. Broader prior suites 9/9 Release, 4/4 Debug.
- Prepared hl2-combined-20260907 with Release proxy SHA256 665167756defad1c9e509c07a258bf2aa1f6d6223ad5c3c3814cac82a452a66a and reused matching accepted native baseline with provenance. Confirmed ordinary HL2 closed before launch. Started combined armed run (trace60 presents, inventory4096 attempts/16MiB, position4 captures/4096 attempts/16MiB). Await user in-game before triggering. No rendering/settings changes; runner owns temporary bin proxy and cleanup after normal exit.

- Combined capture + regressions pass 9/9 Release (18.88 s), 4/4 Debug (9.05 s). Includes exact synthetic raw input agreement and 256 KiB shadow case; direct undefined-byte/resource/range rejection preserves native rendering. Added viewport/target metadata and final rerun pending.
- Requested normal close before deployment. Subsequent process check finds no HL2 process and no bin proxy; ready to prepare a fresh hash-checked combined pass after final metadata tests. No process was killed or settings changed.

- Added opt-in position path to existing shadow/constant hook. Tracks initialization from launch with 61 register flags; exact shader input capture emits only referenced INDEX16 corner positions and c0/c4–7/c58–60, raw declaration and evaluated clip/model outputs. Commits native-success evidence only; bounded four captures / 4096 attempts / 16 MiB output with explicit rejections.
- Position-only mode permits 16 MiB buffers and 128 MiB retained byte+mask shadow budget (whole-buffer tracking, referenced-range serialization). Original snapshot budgets/admission remain unchanged. Added bounded independent CPU reader and combined game-runner option; testing pending.

## 2026-09-07 — unified capture/UI roadmap requested

- Recorded later milestones for one coordinated capture session and a capture/authoring workbench UI in docs/UNIFIED_CAPTURE_UI_ROADMAP.md. Shared evidence identities, deduplication, budget/completeness reporting and existing runner safety are required; unseen/unsupported content is not promised.
- User reports game running. Confirmed HL2 PID 54224, no bin/d3d9.dll, and loaded D3D9 path C:/WINDOWS/SYSTEM32/d3d9.dll only: ordinary uninstrumented session, not capture-ready. No deployment, restart, injection or settings changes performed. Current implementation priority remains initialized input capture for the numerically validated exact shader.

## 2026-09-07 — HL2 position evaluator/native raster gate

- Added src/shader/position.h/.cpp: pinned 612-byte hash admission, exact prepared-position and clip/model dot-product evaluator, known/finite constant checks and overflow rejection. Not called by the proxy capture path.
- Added isolated --hl2-position fixture using HAL hardware vertex processing, unmodified captured VS, synthetic initialized indexed inputs and RGBA32F model-position output. Compared against CPU-transformed pass-through rasterization for 24 c0/transform cases with varied offsets/base vertices. Exact coverage, 34,603 covered samples, zero normalized difference in Release and Debug; fixed tolerance 0.0002. Tests also reject all eight missing constant slots, nonfinite inputs/constants, overflow and modified program bytes.
- Added conditional local-evidence CTest hl2_position and reusable Python runner. Game bytecode remains in local inventory, not embedded into tests. Release shader suites 5/5 (6.70 s); Debug position/snapshot 2/2 (1.10 s); final verbose Debug position 0.47 s confirms zero error. Python compilation passes. No game launch and bin/d3d9.dll remains absent.
- Next: bounded initialized input capture for this exact program. Synthetic raster equivalence is not proof of live game buffer capture, world-space conventions or material reconstruction.

## 2026-09-07 — exact HL2 shader position path identified

- Added rrt_shader_disassemble (bounded CPU-only SDK disassembly) and validated hash-selected inventory wrapper. No GPU shader/device creation in diagnostic; no runtime proxy/replay admission change.
- Selected shader uses c0.xy to prepare position, c4–c7 for clip output and c58–c60 for oT4.xyz. Full program has 19 straight-line slots; additional normal and stream2 declaration inputs are not consumed by this exact shader. Documented evidence, unknown runtime values and next native numerical/input-capture gates in docs/HL2_POSITION_CONTRACT.md.
- Release shader tests 4/4 pass (6.52 s), Debug disassembly passes. Malformed/oversize/trailing input and absent hash rejected. Confirmed HL2 exit 0 (185.797 s), executable unchanged and owned bin proxy removed; no game installation changes this turn.

## 2026-09-07 — actual HL2 shader inventory captured

- Triggered inventory after user confirmed in-game. Validated 2,996 draws, no failed native draws or unavailable queries, 42 VS, 37 PS and 55 families; normal 16 MiB byte-budget stop (16,772,448 bytes). Independent trace: 60 presents / 10,466 shader draws / zero failed calls.
- Recorded source digest, provisional simpler 612-byte VS analysis candidate and limits in docs/HL2_INVENTORY_PASS.md. Actual buffers/constants/world transforms remain uncaptured. No replay admission or rendering changes.
- HL2 PID 52408 still running at inspection; told user capture finished and normal exit is safe. Runner session 40664 owns cleanup; confirm exit/hash-guarded bin DLL removal next turn. Initial full summary output was truncated; compact aggregations supplied complete counts and selected-family evidence.

## 2026-09-07 — bounded shader inventory (in progress)

- Implementation and offline/native validation complete. Release selected suites 9/9 (22.87 s), Debug 7/7 (17.00 s). Final extended unknown-program rejection and 16 MiB stop tests pass Release (2.20 s) and Debug (2.62 s); Python compilation passes.
- Prepared build/game-passes/hl2-inventory-20260907 with the new Release proxy hash and reused unchanged default native baseline through verified provenance. Launched armed inventory run; await user in-game before trigger. No graphics registry/config edits. Runner owns temporary bin/d3d9.dll and removes it after normal game exit.

- Added separately opt-in native shader/declaration/stream/index inventory, pre-draw queries and post-draw HRESULT evidence. Hard limits: 16 KiB/program, 65 declaration elements, 16 streams, 4096 draw attempts, 16 MiB ledger. No retained COM references, replay creation, buffer locks or constants inference. Release proxy builds.
- Added CPU-only family reader, proxy fixture tests and triggered game-runner option. Validation pending. Discovery error: tests/test_game_pass.py does not exist; use actual CTest game_pass_workflow target.

## 2026-09-07 — proxy-backed shader snapshot integration

- Connected generated D3D9/9Ex forwards to a separate opt-in shader hook. Resource-private shadows track writable Lock/Unlock ranges, DISCARD, failed Unlock and GPU ProcessVertices invalidation; retained byte/mask budget 16 MiB, per buffer 64 KiB. Device knowledge uses unique wrapper IDs, capped at 16, with conservative recording/Apply/Reset/retirement invalidation.
- Selected DrawIndexedPrimitive attempt captures native state before call, commits on success only, preserves outputs via exclusive create and records rejected evidence separately. No exceptions cross hook boundaries; default-off and RRT_PROXY_DISABLE preserve normal forwarding. Unknown HL2 programs/layouts remain rejected.
- Tests compare 3 intercepted variants and post-reset capture with standalone artifacts byte-for-byte and pixel-exact fresh-process replay. State-block/recording, partial DISCARD, failed draw, reset without constant refresh and retired-wrapper recovery cases tested; explicit refresh recovers admission. Output collisions preserved and missing output directory does not break rendering.
- Adjacent suites pass 6/6 Release (13.41 s), Debug (14.55 s). Additional retired-wrapper test passes Release (3.06 s); final Debug pending. No game launch/deployment this turn.
- Final retired-wrapper coverage also passes Debug (3.27 s). Python compilation passes and no HL2 bin proxy remains. Updated project status to reflect completed gameplay observation and the actual shader-extraction boundary.

## 2026-09-07 — bounded shader snapshot and isolated GPU replay

- Final adjacent suites pass 5/5 in Release (10.86 s) and Debug (11.95 s): shader snapshot, trace reader, proxy equivalence, game-pass workflow and scene replay. Python compilation passes; HL2 is closed and no bin proxy remains.

- Implemented separate rrt_shader_snapshot library and rrt_shader_fixture. Real native draw-boundary capture queries exact allowlisted VS3/PS3 programs, FLOAT3 declaration, five known constants, viewport/raster state and indexed stream parameters; referenced bytes require explicit initialization evidence. RRTSHD01 has bounded serialization and SHA256 integrity; unused buffer bytes are zeroed.
- Three variants change constants, geometry, stream offset/stride, index offset and base vertex. Fresh-process replay exactly matches source pixels; retained snapshot also replays exactly after native device reset. Negative cases cover unknown constants, undefined bytes, actual partial DISCARD, stale/replaced resource evidence, missing PS, instancing, bytecode/layout/range/finite admission, corrupt/truncated/trailing artifacts and malicious allocation counts.
- Added shader_snapshot CTest and updated docs/SHADER_GEOMETRY.md with explicit bounds and remaining integration requirements. This library is not linked into the game proxy and does not capture HL2 shaders yet; no installed game files changed.

## 2026-09-07 — shader-input audit and graphics restoration

- Adjacent reader/proxy/scene checks pass; workflow initially exposed a Windows live-report reader/atomic-replace sharing race. Added specific bounded 200 ms retry and workflow passes three consecutive runs (7.03 s total). Failed run never launched its fixture and removed its deployed DLL; no orphan test process found.

- Confirmed lower-feature gameplay exit 0 and proxy_removed=true. Reviewed settings/config differences, restored only DXLevel_V1 80 to original 95 with closed-game/current-value guards. Preserved unrelated dsp_volume change; no full registry/config overwrite. Backups retained.
- Added inspect_trace --shader-profile: separates vertex-only/pixel-only/both/fixed/unknown draws, successful input-update counts and complete/truncated float constant payloads. Unit coverage includes all binding categories, absent flags, failed-draw exclusion and malformed/truncated payloads; 8 reader tests pass.
- Default HL2: all 28,633 draws indexed, 820 vertex-only and 27,813 both stages; 85,617 complete float updates. Lower-feature: all 11,424 indexed draws use both stages; 21,922 complete updates. Neither sample includes shader/declaration creation. Existing capture cannot reconstruct programs/buffer contents from these traces.
- Published docs/SHADER_GEOMETRY.md defining bounded per-draw shader input snapshot and synthetic replay gate. No shader extraction or world-space reconstruction claimed.

## 2026-09-07 — lower-feature gameplay result

- Triggered hl2-dx70-20260907/gameplay on user's in-game confirmation. Valid frame_limit capture: 60 presents, 134,212 events, 11,424 shader draws, zero fixed-function draws and zero failed calls. Low-feature experiment did not solve extractability.
- Next work stays on HL2: audit shader draw state/geometry inputs, then define a bounded shader-aware capture fixture and contract. No scene extraction or relighting claimed. User requested normal exit; verify owned proxy removal and review settings-before restoration before another game launch.

## 2026-09-07 — lower-feature HL2 gameplay pass armed

- User accepts lower-feature baseline; report confirms exit 0 after 109.562 s, no proxy and executable unchanged. Requested level 70 previously persisted as 80; no fixed-function claim yet.
- Launched hl2-dx70-20260907/gameplay with same arguments, bin proxy, --wait-trigger and 60-frame bound. Runner session 47680. Await user in-scene confirmation before trigger; original settings backup retained until experimental runs end and restoration is reviewed.

## 2026-09-07 — HL2 retained as extraction target

- User explicitly chose continued HL2 work. Prior triggered gameplay run exits 0 after 141.703 s, owned proxy removed, executable unchanged. No more default-mode game trials needed for basic interception; focus is extractability.
- Investigated low-feature path using installed stdshader_dx6/7/8/9 libraries and NVIDIA's official Source compatibility tutorial. Tutorial requires modified Portal binaries, so its feature-level guidance is an experiment, not a stock-HL2 guarantee. No tutorial file replacement steps followed.
- Prepared hl2-dx70-20260907 with identical game identity and added -dxlevel 70. Backed up both hl2/hl2_complete cfg/config.cfg and HKCU Software/Valve/Source/hl2_complete/Settings in settings-before before launch. These settings may be changed by the game; preserve backup until restoration is reviewed with game closed.
- Native low-feature baseline launched, runner session 75268, no proxy. User to play same scene, assess stability, close normally. Actual fixed-function coverage requires subsequent triggered trace; low-feature success does not establish generic shader support.

## 2026-09-07 — first user-triggered HL2 gameplay trace

- User confirmed "in game"; issued trigger for hl2-gameplay-20260907/gameplay while PID 11732 was responding. Valid trace stops at byte_limit (64 MiB budget), 368,506 events, 82 successful presents, 28,633 shader draws, zero fixed-function draws and zero failed calls. Requested 120 frames were not fully captured; byte-bound stop is explicit.
- This demonstrates real gameplay interception, not complete scene extraction. Current fixed-function capture cannot extract this sampled shader-only draw population as supported geometry. User asked to close normally; final exit and owned-bin-DLL cleanup remain pending.

## 2026-09-07 — triggered gameplay capture armed

- Added opt-in RRT_TRACE_TRIGGER_FILE, evaluated after successful Present; delays header/event admission until a complete next frame. Existing start-frame minimum, bounds and default behavior retained. File metadata only; directory/reparse triggers rejected. Runner --wait-trigger and trigger command use a unique workspace marker; no scene capture in this mode.
- Added baseline reuse with identical executable path/hash/native arguments and successful uninstrumented report admission plus source-report provenance. New proxy remains separately hash-pinned; no prior run is relabeled as a fresh execution.
- Release adjacent proxy/workflow/scene tests 3/3 (11.95 s), Debug 3/3 (11.04 s). Additional live-trigger workflow passes Release 2.52 s and Debug 2.62 s; missing/directory trigger, pixels, cleanup and replay regressions pass. Python compilation passes.
- Prepared hl2-gameplay-20260907 and reused the accepted native report with explicit provenance. Launched gameplay with trigger waiting, 120-frame/64 MiB bound; runner session 95411. Await user "in game", then trigger via tools/game_pass.py trigger build/game-passes/hl2-gameplay-20260907 --name gameplay. Do not rebuild proxy while deployed. After capture user closes normally; verify cleanup.

## 2026-09-07 — HL2 traced pass accepted; forwarding-only control

- User accepts HL2 proxy-bin gameplay appearance/behavior. Report confirms exit 0 after 44.782 s, owned DLL removed, executable unchanged, complete 300-present trace. All 76 failed events are capability queries: 74 CheckDeviceFormat and 2 GetAdapterIdentifier. No failed draw/present events in this startup sample; not a proof all failures are harmless.
- Launched disabled-bin control with same executable/arguments/bin placement and RRT_PROXY_DISABLE=1; user to repeat scene then close. Representative gameplay trace and scene extraction remain open; startup sample has 301 shader draws and zero fixed-function draws.

## 2026-09-07 — first confirmed HL2 interception

- Verified game-root attempt exited 0 and removed owned DLL. Added explicit root/bin deployment support with canonical directory admission; arbitrary subdirectories rejected. Added real bin deployment/trace/cleanup test, preservation of unrelated root DLL, and mismatched-destination rejection. Release game_pass_workflow passes in 1.56 s; Python compilation passes.
- Prepared HL2 placement revision preserves accepted executable/hash/arguments and records earlier root placement. Launched proxy-bin (runner session 43114). Live modules confirm bin/d3d9.dll plus system forwarding target. Trace finishes at frame_limit with 20,387 events and 300 successful presents, 2,762,807 bytes.
- This is first confirmed commercial-title interception, not scene extractability or ray-traced gameplay acceptance. User scene comparison and normal exit/cleanup pending. Temporary bin DLL stays until process exit; no original game files replaced.

## 2026-09-07 — HL2 first proxy deployment

- Controlled native baseline completed with exit 0 after 97.656 seconds; executable unchanged, user accepts behavior. Launched first bounded proxy pass (300 startup presents, no scene capture) using exclusive game-root d3d9.dll deployment; runner session 92706 / PID 53004.
- Initial live module check shows only system d3d9.dll and no trace file. Local DLL installation is not proof of interception: proxy loading currently unconfirmed, likely a loader-path issue requiring investigation after normal exit and guarded cleanup. No alternate deployment location or live-process mutation attempted.

## 2026-09-07 — HL2 controlled baseline started

- User reports Radeon overlay disabled and readiness; HL2 process absent at preflight. Fresh Release game_pass_workflow passes in 2.23 seconds, including the clarified native-baseline diagnostic.
- Started build/game-passes/hl2-20260907 baseline with existing observed arguments and no proxy. Requested repeatable scene and normal exit before comparison. Steam overlay status is not assumed disabled; user specifically meant Radeon overlay.

## 2026-09-07 — HL2 preflight

- Verified active HL2 process loads shaderapidx9.dll, system d3d9.dll and Steam gameoverlayrenderer.dll. User reports good gameplay and suspects overlay interference, not proven. Preserved observed -steam -game hl2_complete arguments in a new x86/hash-checked test bundle; no DLL deployed or overlay setting modified.
- Harness workflow recheck failed at native baseline while HL2 remained open. Split its misleading combined assertion so future failures distinguish nonzero exit from instrumentation. This diagnostic-only edit does not relax any gate; rerun after game closes remains required.
- Updated compatibility ledger with BioShock native failure and HL2 preparation; awaiting user overlay disable and normal game exit before controlled runs.

## 2026-09-07 — BioShock DX9 baseline rejected

- DX9-requested untouched baseline exited with 3221225477 (0xC0000005 access violation) after 73.516 seconds. User reports it launched but crashed. No proxy installed, executable unchanged; do not proceed to proxy comparison on this unstable baseline. This does not prove all DX9 configurations fail or identify the faulting component.
- J: now contains real Half-Life 2 and Dark Souls PTDE executables, unlike earlier incomplete downloads. O: contains Max Payne and Tomb Raider Angel of Darkness directories. Native DX9 observation remains distinct from fixed-function extractability and future DX8 translation.

## 2026-09-07 — DX9-requested BioShock 2 baseline

- Verified installed executable contains dx9/dx10 option strings, then prepared a separate provenance bundle at build/game-passes/bioshock2-sp-dx9-20260907 with per-process -dx9. No Steam options, INIs or game binaries edited; no proxy installed.
- Baseline launched via runner session 60453. Await same-scene user review and normal exit before instrumented comparison. Presence of option strings/loaded modules is not treated as proof of active D3D9 rendering.

## 2026-09-07 — BioShock 2 baseline completed

- Untouched SP baseline exited normally (code 0) after 209.468 seconds; executable hash unchanged, no proxy installed, no trace or scene captured. User reports the game worked and looked good, and suspects DX10. Active API remains unverified; water reflections were original game rendering, not project additions.
- J:/SteamLibrary/steamapps/common now contains Amnesia The Dark Descent, Dark Souls Prepare to Die Edition, Half-Life, Half-Life 2, HardReset and Morrowind. These are available candidates, not certified fixed-function capture targets.

## 2026-09-07 — BioShock 2 original SP baseline launched

- User supplied O:/SteamLibrary/steamapps/common/BioShock 2. Verified SP executable is x86, no existing local d3d9.dll, and no previously running BioShock process. Multiplayer is excluded.
- Fresh Release game_pass_workflow passes (1.25 s). Prepared build/game-passes/bioshock2-sp-20260907 with SHA256 provenance and no launch arguments; executable contains D3D9 and D3D10 DLL references, so API selection still needs observation rather than assumption.
- Launched untouched single-player baseline, PID 42900, responding with BioShock 2 window. Runner session 60237 waits for normal exit. No proxy installed. User must review a short repeatable gameplay scene and close normally before the proxy pass; real-title compatibility remains unassessed.

## 2026-09-06 — first game-pass readiness

- Prioritized real-title observation over further optional RC work. Added tools/game_pass.py with x86/hash preflight, baseline-first gating, exclusive local deployment, per-process bounded trace settings, report artifacts and hash-guarded cleanup/recovery.
- Added game_pass_workflow CTest covering actual launch/deployment, exact baseline/proxy/disabled pixels, selected trace/scene capture and replay inspection, mod preservation and provenance/path rejection. Rebuilt Win32 proxy/sample/replay in Release and Debug.
- Classic workflow/proxy/scene tests pass 3/3 in Release (8.80 s) and Debug (9.73 s). Fixed the hidden sample window; bounded presentation retries now reject unavailable presentation explicitly. Ex remains occluded on Microsoft's native runtime, not just the proxy, and is not marked passing.
- Published docs/GAME_PASS.md and updated project status. Steam/library inventory did not locate an accessible proposed game. Asked for the actual executable path; first commercial-game baseline/observation remains pending, and no installed game was modified.

## 2026-09-06 — renderer-owned commanded session

- Added --rc-renderer-session-test, connecting RcFrameAdmission, GPU raw/compact regeneration and parent-commanded provider epochs. The scheduler consumes the latest of two queued camera updates, discards the stale first result and processes six epochs in one provider process/context.
- Four resets/two continuations execute 18 dispatches. Counts refresh as 172/178/178/172/172/172; base resets remain exact, and moved continuation reaches hash 8100200300773600753. All shared prediction readbacks match worker reports and all no-cache images remain unchanged by provider work.
- Reused the frame-constant upload in place after ownership returns. No renderer GPU buffers are allocated during the epoch loop. Retained staging/full pool bytes drop by 256 in the existing pool fixtures.
- Release path contract passes in 53.33 s with D3D12 validation, repeatability, timeout/low-budget failure and recovery. x64 Debug and Win32 Release builds plus Python compilation pass; final Debug path contract passes in 53.29 s.
- This is a bounded six-epoch scheduler fixture with synthetic requests and diagnostic readbacks. Per-epoch candidate application/native presentation, interactive UI requests and live D3D9 integration remain next.

## 2026-09-06 — whole-project checkpoint and commanded provider epochs

- Published docs/PROJECT_STATUS.md and linked it from README/PHASE_PLAN. Main progress is the standalone Phase 5 renderer, with Phase 6 infrastructure and experimental Phase 7 work; no commercial title is qualified and RR quality/other FSR integration remain open.
- Added RcEpochProtocol and a provider loop accepting reset/continue/stop through the existing shared fence. Parent sequences accept 1–16 commands; the child has a 64-epoch bound. Per-epoch acknowledgement transfers ownership; stop acknowledgement follows context destruction/accounting validation.
- Added --session-commands to shared path/stream probe modes. RCRCC executes five epochs/15 dispatches in one process/context, proves exact reset/continuation, and parent GPU readback verifies final hash 1061084142929051959.
- Repeat, R-only stop, 16 resets, invalid commands, timeout, low-budget failure and recovery pass. Release path contract passes in 43.25 s; Debug in 45.64 s. Release/Debug provider builds and Python compilation pass.
- This protocol test uses an exported static fixture. Connecting the command loop to queued renderer input, then D3D9 Present/Reset and real-game qualification, remains the next product work.

## 2026-09-06 — stateful RC buffer reuse

- Renamed/extended RcBufferPool with optional shared/default-heap pooling (32 entries/8 MiB), exact descriptor matching, success-state restoration and fenced reuse. Failures invalidate the pool; staging-only and unpooled modes remain available.
- Added --rc-gpu-pool-test: six lifecycle cases plus two diagnostic-only repeats. Applied results match unpooled transactions; diagnostic repeats preserve exact no-cache pixels. Stable repeats allocate no new buffers.
- Release contract passes with the D3D12 debug layer in 31.30 s. Eight transactions record 31 allocations, 78 reuses and seven submissions restoring 61 buffer states. Pool retains 2,880,520 bytes and releases them to return exactly to the 2,967,408-byte renderer baseline.
- x64 Release/Debug and Win32 Release builds and Python compilation pass. Final Debug contract passes in 35.25 s with the D3D12 debug layer. Shared handles/fences/pipelines and provider contexts are not yet persistent across transactions; continuous queue consumption remains next.

## 2026-09-05 — RC staging reuse

- Added bounded RcStagingPool (16 entries/1 MiB) with exact size/heap matching, exclusive transaction leases, success retention, failure invalidation and complete charge release at teardown. Direct calls accept an optional pool; default ownership remains scoped.
- Added --rc-pool-test and staging-pool.json evidence. Six same-renderer transactions exactly match unpooled results apart from timing/PID. Stable repeat allocates no new staging resources; failure empties the pool and recovery rebuilds it.
- Canonical run: 11 allocations, 17 reuses, 246,784 retained bytes, 2,967,408 live baseline bytes restored at teardown. No timing speedup claimed.
- Release path contract passes in 31.04 s; Debug passes in 32.73 s. x64 Release/Debug and Win32 Release builds and Python compilation pass. Shared/default-heap pooling and continuous provider/UI epoch consumption remain outstanding.

## 2026-09-05 — cache resource lifetime

- Added RcTransientBuffers ownership for every RC direct buffer/upload. Resources remain owned through worker teardown and their exact budget charges are returned when the scope releases them. Persistent renderer/swapchain accounting is unchanged.
- Added --rc-resource-test with six same-renderer transactions: stable, repeat, low-budget failure, recovery, camera change and live session. Exact candidate recovery and no-cache failure preservation pass. Live requested bytes return to 2,967,408 after every transaction; peak requested bytes are 5,847,928.
- Release path contract passes in 24.74 s. Debug path/native presentation contracts pass in 30.89 s. x64 Release/Debug and Win32 Release builds pass; Python compilation passes. The contract now saves resource-lifetime.json for subsequent runs.
- This fixes cumulative budget accounting, not allocation overhead. Buffer pooling, generalized provider epochs and continuous consumption of pending UI requests remain outstanding.

## 2026-09-05 — renderer cache admission policy

- Added RcFrameAdmission: one active epoch, one latest pending request, identity-based reset decisions and rejection of stale/closed results. Checks cover scene/camera/lighting/material/settings revisions, failures, overlapping work, foreign completion tokens and post-close requests.
- Integrated admission into the bounded native RC presentation loop. Camera notification bursts coalesce; close during provider work or swapchain admission suppresses all display submissions. Also check HWND lifetime after the frame-wait diagnostic's internal message pump.
- Added actual GPU camera/close/close-admission fixtures. Release path/native contracts pass in 34.93 s; Debug passes in 37.15 s. Final HWND lifetime guard rebuilds in x64 Release/Debug and Win32 Release; final focused Release rerun passes in 30.76 s. Python contract compilation passes.
- Continuous dispatch remains pending: the harness reports the latest queued request but does not run it. Generalized provider epochs and reusable GPU allocation accounting remain necessary. No game installation changed.

## 2026-09-05 — live session polling hardening

- Added PollFence with bounded pipe draining, overflow enforcement, device-removal detection and a completion recheck after process exit. WaitFence now services output at intervals of at most 10 ms within its deadline. Resume failure explicitly terminates/reaps the child.
- Added isolated live fixtures for normal premature exit, crash, timeout and overflowing output. Failure cleanup remains bounded but blocking, documented for future UI integration.
- Release worker boundary passes in 4.01 s and GPU path sequence in 25.51 s; Debug passes both in 30.64 s total. x64 Release/Debug provider/renderer and Win32 Release renderer builds pass. No interactive scheduler or game deployment added in this slice.

## Session: 2026-09-04

### RR native-resolution sensitivity

- Tested the initial 64x48 candidate live. Renderer serialization, managed decoding, independent reference and fallback all worked, but the pinned RR provider failed context creation after requesting seven zero-height D3D12 resources. Pivoted the exact v2 ABI to same-aspect 256x192 so the experiment measures native resolution without relying on an unsupported sub-minimum extent.
- First 256x192 native dispatch completed both frames and exposed the exact per-extent memory/accounting report. Tightened the managed workaround to those observed constants; the initial run was rejected as intended because the placeholder accounting values were not admitted.
- Completed the fixed Release native-resolution grid in 686.94 seconds (`rr-resolutions-uo3jk9d_`): four native recordings, eight default/zero SDK outputs and four same-extent references. Higher resolution consistently improves spatial/disocclusion aggregates but has mixed temporal response; all absolute spatial/fallback gates and raw SDK acceptance still fail.
- Fresh Debug replay (`rr-resolution-replay-xqpyt64d`) reproduces all four recordings and eight outputs byte-for-byte. Focused Release compatibility passes 5/5 in 84.26 seconds. Added strict cross-version rejection, a registered native-resolution test and `docs/RR_NATIVE_RESOLUTION.md`; no default or resolution promotion.
- Final boundary audit found and removed the remaining v1-only size check in the single-frame managed wrapper/preview. The registered native test now exercises fresh 256x192 reset dispatch admission and decoding.
- The attempted single/recorded byte-equality assertion failed and exposed tiny provider nondeterminism; two fresh singles also differ (981 pixels, max `6.103515625e-05`, MSE `7.44e-11`, alpha exact). Corrected the test to enforce successful strict v2 admission/extent/output decoding without asserting unsupported RGB bit determinism. The failed diagnostic is retained and documented, not hidden by a tolerance.

### RR guide conditioning

- Started a new bounded audit after resolution remained unqualified. Pinned headers confirm the current octahedral-normal/linear-roughness/diffuse-albedo channel layout, but leave normal space and material-type values unspecified inline. No input mutation will be implemented until those semantics are resolved; documented normal/radiance configuration controls are the fallback experimental path.
- Official AMD RR 1.2 documentation resolves material IDs as four classes encoded `id/3`, with cross-ID mixing rejected, and recommends default zero first. It still does not state a normal coordinate space, so normal-space conversion is excluded. A draw-partition material guide plus queried-default normal-strength controls are valid next candidates.
- Queried defaults and retained input ranges support a fixed five-candidate grid: baseline, draw partition, normal-half, their combination, and max-radiance-one. Recorded radiance is below 0.085, so the range candidate does not clip source samples. Stability, resolution and coordinate scale stay fixed.
- Implemented worker-only material classes, `RRTRRD06` provenance, normal/default/half and max-radiance/default/one settings, managed packing hashes/admission and a five-candidate shared-reference harness. Release native settings plus live guide contract pass 2/2 in 13.20 seconds; normal-default is exact and wrong/missing guide provenance is rejected.
- Completed the fixed Release guide-conditioning grid (`rr-guide-conditioning-_b5h9mz1`) in 311.88 seconds: two recordings, ten configured outputs and two shared 512/batch references. Material classes and normal-half make only small spatial/temporal tradeoffs; max-radiance-one is exact baseline. All ten remain spatial/fallback/raw-SDK failures. Debug replay and broader regressions remain.

## Session: 2026-09-03

### Longer RR histories

- Completed: optimized Debug replay rr-history-replay-w13fuyu4 reproduces all 18 captures/54 SDK outputs byte-for-byte in 534.09 seconds. Affected Release tests pass 5/5 in 507.23 seconds; both contracts also pass Debug. Compilation, both Python modes and 42 local doc links pass. Current three milestones manually complete (helper 0/0 unsupported format). No setting promotion. Full SDK, normal renderer/x86/legacy/historical-render suites not rerun.
- Exact compatibility audit confirms all six four-frame moving capture payload prefixes and all eighteen preset output-frame prefixes match the completed four-frame grid byte-for-byte. The first audit implementation decoded millions of output tuples and exceeded the bounded command wait; stopped that superseded Python diagnostic (PID 29036). A PowerShell per-byte replacement was also unnecessarily slow and its wrapper returned only the first line. Replaced both with direct bounded byte-slice equality, which completed immediately. No artifact was changed and no mismatch occurred.
- Full Release grid completes in 2004.30 seconds at rr-setting-histories-i7to8gpg: 18 recordings/54 outputs/54 reports/18 references, ~403 MB. All raw/temporal reference diagnostics pass; fallback-reference confidence fails all cases at the retained 512/batch cap. Every report fails spatial/fallback gates and raw SDK acceptance. Default passes temporal-vs-raw 18/18; half 5/18, zero 2/18. Late spatial/disocclusion improves universally, reset frames are exact, half worsens all 66 late temporal comparisons and zero worsens 65/66. Debug replay and affected Release regressions started.
- All PBR continuous-motion histories complete. A late exception appears: zero bias slightly improves frame-7 temporal residual on seed 23, although earlier transitions make every half/zero recording fail temporal-vs-raw overall. Raw per-frame evidence retained; PBR reset cases are the final grid group.
- All six stationary texture/PBR histories complete and consistently show persistent frame-7 temporal penalties alongside spatial improvement. PBR zero bias fails temporal-vs-raw in all seeds and remains 40–46x fallback. PBR moving/reset cases remain.
- All nine texture histories complete. Stationary, continuously moving and explicit-reset cases consistently retain better spatial/disocclusion estimates but worse late temporal residual at lower stability; reset frames remain exact across all seeds and both configured variants. PBR half of the grid is now running.
- First continuous-moving history completes and retains worse late temporal residual at half/zero bias, despite large spatial and disocclusion MSE reductions. Both variants fail temporal-vs-raw for that recording; capped fallback reference confidence also fails. Remaining seeds/reset/PBR cases continue.
- Actual eight-frame texture/stationary seed-1 cached-versus-independent validation passes: three exact report/array pairs, eight estimator calls versus 24 standalone calls, and two cache/preset mismatch rejections. This confirms the optimized comparison path at the new maximum frame count. Full grid continues with independently traced renderer seeds.
- First texture/stationary seed-1 high-sample case completes. Late zero-bias spatial error remains much lower than default, but late temporal residual remains materially higher. Absolute temporal-vs-raw gate still passes; fallback-reference-confidence gate fails at the capped 512/batch reference and is retained. Eight-frame cached-versus-independent validation is running on this completed case.
- Implemented eight-frame harness and grouped trajectory/late/post-reset summaries. Normal/optimized CPU aggregation tests pass; new and prior comparison contracts pass 2/2 Release CTest in 0.59 seconds. Full Release grid started with final source. No failures or threshold changes so far.
- Started the next fixed grid: eight-frame stationary, moving and frame-4 reset sequences for texture/PBR, seeds 1/7/23 and default/half/zero stability. Reference samples reduce to 512 per batch to preserve the unchanged count*samples<=4096 cap; any resulting reference-confidence failure remains evidence. Read planning skill and session recovery; no unsynced context. No renderer/native/default changes planned.

### Multi-seed RR surface comparison

- Completed: corrected six-recording/eighteen-analysis Release manifest is published with explicit local recovery provenance. Every lower-bias non-reset spatial/disocclusion estimate improves versus default, but all eighteen temporal estimates worsen per preset; all presets still fail spatial/disocclusion/fallback gates. Four targeted Release tests pass (468.51 seconds), and optimized Debug fresh replay matches six recordings/eighteen SDK outputs exactly in 64.27 seconds (rr-surface-replay-y0d3mw1c). Final corrected CPU contract passes normal/optimized Python plus Debug/Release CTest. Historical texture/PBR captures, outputs, reference NPZs and all frame metrics match exactly. Compilation/local links pass; all three milestones manually complete, helper 0/0 due checklist format. No renderer/default/SDK/driver/game changes. Full SDK, normal renderer/x86/legacy/historical-render suites were not rerun.
- Full 18 analyses completed but the new final seed audit rejected them because it included secondary-ray hit distance (component 3) in the deterministic-guide hash. Read rr_inputs.hlsl: this is the sampled bounce distance, correctly expected to vary with RNG seed alongside indirect RGB. Retain all results, correct only the audit classification, verify exact differing components and rerun artifact validation. No renderer or quality-threshold change.
- PBR cached/independent validation now also passes; six exact report/reference pairs total, with two mismatch rejections per surface condition. Five historical byte matches confirmed so far (two recordings/two default outputs/texture reference NPZ), plus exact texture frame metrics at the same 1024-per-batch sample count. Final PBR reference and all-grid manifest remain in flight.
- Existing Release rr_quality and rr_surfaces regressions pass (57.16 and 131.74 seconds) with unchanged quality thresholds; rr_settings remains running. Texture/PBR cached-versus-independent checks use actual recorded SDK artifacts, not fake estimates. Added a separate bounded fresh-render/fresh-worker cross-configuration replay verifier for all six recordings/eighteen outputs; it will run once the grid publishes its complete verification manifest.
- Optimized texture seed-1 cached/independent validation passes: three exactly equal reports/array sets, four cached estimator calls versus twelve independent, and two cache/preset mismatch rejections. Full Release grid uses final seed-audit source; first three texture seeds are progressing. Existing rr_quality/rr_surfaces/rr_settings plus CPU contract regression started concurrently. Documentation now describes fixed grid, source-bound cache, common reference streams and descriptive-only paired deltas.
- Implemented fixed-grid harness and private source-bound reference sharing; every candidate is still fully re-admitted. Added paired spatial/temporal/disocclusion summaries and explicit proof that renderer seeds change recording/noisy-signal hashes while guide/camera hashes remain fixed. Python compilation, normal/optimized CPU contract and registered Release CTest pass. Deliberately interrupted the initial measurement after its first reference because the seed audit was added while that process had the older source loaded; starting the definitive run from scratch. No failed implementation assertion or retained result from the incomplete run.
- Started the next bounded offline phase: fixed three input seeds across texture/PBR conditions and three stability presets, preserving source validation and reference uncertainty gates. Read planning skill completely; session catchup found no unsynced state. Existing scene/material artifacts located. One read-only rg pattern starting with -- lacked its option delimiter; no files affected, corrected for subsequent searches.

### Single-setting RR experiment path

- Completed: Release optional SDK suite passes 12/12 in 1082.68 seconds; rr_settings passes in 309.06 seconds (rr-settings-tp8e7cvp). All 43 output bundles, six reference NPZs, five recordings and measurement dictionaries match expanded optimized Debug exactly. A separate direct hash audit confirms five historical default-output matches (CTest does not supply the optional baseline argument). Native contract passes both configurations; current three milestones manually complete. Planning helper returns 0/0 for this unsupported checklist style. No build/runtime failures or relaxed thresholds; renderer/x86/legacy/historical-render suites not rerun.
- Final noisy 1024/batch optimized Debug diagnostic passes all eight narrow quality/reference gates for none/half/zero in 221.92 seconds (rr-setting-noise-4geqmsb0). Three SDK bundles match initial Release 512/batch exactly; independent reference estimates differ intentionally, and all presets share exact reference/fallback arrays within each run. The default bundle also matches the source rr_quality output. Later-frame spatial/temporal improvements coexist with worse early temporal and some disocclusion estimates versus default. Retained the initial 512/batch reference-confidence failure, analytic contrast/black-floor failures and raw SDK reporting failures. Documentation records evidence and next multiseed noisy/PBR work; no default promotion.

- Added bounded tools/rr_setting_noise.py for a three-preset follow-up on existing source-verified constant-diffuse recordings. Initial 512/batch Release run completes (rr-setting-noise-v2t6g3to), preserving failed reference-noise-versus-fallback gate. A 1024/batch optimized Debug run is in progress, within the existing sample/frame cap; input identity and exact common reference/fallback arrays are checked. Later-frame estimates improve at half/zero, but an early temporal comparison worsens. No threshold relaxation or setting promotion.

- Expanded optimized Debug rr-settings-yn9yujur passes in 331.69 seconds, including all 43 negative cases and maximum eight configured contexts (38,039 stdout bytes). Full zero-bias history quality analysis retains failed spatial/temporal/fallback and raw SDK gates. First two current milestones complete; Release regression remains running. Compacted only the new test's final console summary; its complete measurement dictionary is retained in verification.json.

- Additional byte-level audit confirms all twelve reset-frame comparisons are identical for stability half/zero versus no override; the benefit is later-frame response, not correction of the initial frame. Python compilation, both CLI help paths and local documentation links pass. Source include audit confines changed native headers to the research probe and new CPU-only test. First six Release tests pass; optimized Debug reproduces both encodings and eight-frame metrics so far.

- Initial Release grid rr-settings-3y4dazpv passes in 241.27 seconds: ten default-equivalence controls, five historical matches, 43 rejection cases, CLI failure-evidence retention and recovery. Zero stability bias reduces the eight-frame analytic MSE 85.79% but remains ~10,822x above the near-zero matched fallback; the initial reset-frame loss and black floor persist. Gaussian changes are mixed. Expanded final Debug verification and the full twelve-test Release SDK regression are running; no promotion or threshold changes.

- Added seven predefined, recorded-only one-key presets, selected-default admission and actual configure return evidence per recreated context. All imply repeated default inspection. Configured RRTRRD03 output has a preset/encoding tag; legacy/unconfigured readers reject it unless the exact setting is explicitly expected. No arbitrary float parser or default filter changes.
- First actual Release stability-default control returns code 0 with inner frame bytes identical to the historical baseline. Native CPU-only API-double CTest passes 49 preset/admission/ABI/failure cases (query failure, unwritten sentinel, nonfinite/wrong default, guard overwrite and configure failure); no vendor DLL/device/GPU is used in that test.
- Added predeclared analytic grids with unchanged independent references/fallback, idempotent controls, malformed preset/report/header checks, CLI gate retention and allocation-failure recovery. Release measurement is running; no build/test failures so far.

### Read-only RR default settings

- Completed: full Release optional SDK regression passes 10/10 in 692.00 seconds; final rr_defaults in 129.45 seconds, rr-defaults-ycw6uxym. Cross-configuration checks find 22 identical output bundles, five identical recordings and identical per-case inspection dictionaries; eight outputs also match historical encoding evidence directly. Existing encoding outputs/reference bundles/metrics remain exact. Final evidence and next bounded single-setting/idempotence experiment are documented; current three milestones manually complete. No source/build/test failures or changed quality thresholds. One documentation-only final patch had an extra mismatched hunk; it made no changes and was reapplied with the correct context. Normal renderer/x86/legacy/historical suites were not rerun.

- Final Debug queried linear-texture quality frame metrics and every gate match the previous Release encoding test exactly. Spatial, temporal and fallback quality failures are preserved; inspection adds evidence, not an image correction. Eight of ten Release SDK regression tests have passed; encoding/defaults remain in flight.

- Read-only auxiliary log lookup used LastTest.log.tmp, but this CTest run uses a randomized temporary suffix; rg --files located LastTest.log.tmp22e2c. No test or artifact was modified. This and the sample-document lookup were diagnostic lookup errors, not build/SDK/test failures.

- Initial optimized Debug passes in 99.875 seconds (rr-defaults-mp24l0ma), with 22 byte-identical Release output bundles and identical inspection values/cases. Source review adds correct negative-zero JSON spelling and a signed-zero validation control; rebuilt both native configurations. Full ten-test Release SDK regression is running. Existing null-context logging configuration is untouched; there are no denoiser-setting overrides. Official AMD sample ranges and a next-step idempotent-configure control are documented. A failed guessed sample URL was corrected via the actual manual link.

- Initial Release rr-defaults-v35hm6p3 passes in 96.28 seconds, including ten off/on pairs, 34 rejected cases, five honest failures, two instability controls and eight byte-identical historical outputs. All non-query native report fields also match. Eight sequential cut contexts remain within existing budgets and produce at most 36,099 stdout bytes. Optimized Debug replication is running; no build/runtime failures or threshold changes.

- Implemented optional recorded-worker queries for all six documented float filter keys. Four fixed snapshots per live context surround completed GPU work; each query preserves its code, float bits and guard words and starts from a nonfinite sentinel. No configuration overrides or renderer/shader/vendor SDK changes.
- Added strict managed query assessment and quality-report revalidation. Query failure or instability publishes no defaults; damaged guards/malformed or missing required snapshots reject. Query-off historical reports remain accepted. Native Release/Debug builds pass and the first live probe returns all six defaults successfully with byte-identical historical output.
- Added rr_defaults CTest covering both encodings, stationary/history/moving resets/maximum cut count, malformed and honest-failure reports, CLI forwarding and allocation-failure recovery. Paired Release validation is running against prior encoding artifacts.

### Paired RR albedo encodings

- Implemented recorded-worker-only linear/sqrt mode with paired packing/SDK flag. Native reports expose actual encoding and flags; managed validation rebuilds all packed resource hashes. Canonical renderer recordings, radiance, geometry, shader source and existing GPU/process limits remain unchanged.
- Linear output remains byte-compatible RRTRRD01. Square-root output uses RRTRRD02/version 2/tag 1, requiring explicit expected encoding in output decoding, recorded execution assessment and quality analysis. Historical reports remain readable only as linear; incomplete metadata rejects. Added CLI support and an optional rr_encoding CTest.
- Both worker builds pass. Initial paired Release run rr-encoding-phy27gzm passes six cases, 25 rejection checks, default-option equivalence and injected-failure recovery. All six linear outputs are byte-identical to pre-change rr-colour-0u48aq8r evidence. Square-root encoding does not repair the spatial failure: linear-texture frame-seven MSE .00102917 versus default .00103086, while point-texture error worsens slightly. White/grey/black outputs match encodings exactly.
- Final expanded tests add quality-CLI explicit-mode/evidence checks and a moving four-frame reset case. Full nine-test Release SDK regression and optimized Debug paired verification are running. Raw SDK reporting and zero-light acceptance remain failed; no default promotion or output correction.
- Expanded optimized Debug passes (rr-encoding-d366h8er): seven paired cases, 28 rejections, six historical linear matches, CLI failure-evidence retention and SDK crash recovery. Reset flags are [1,0,1,0] with two sequential contexts in sqrt mode. The first eight Release SDK regression tests have passed; the final encoding test is finishing in rr-encoding-n49hhhv5. Source include audit confirms modified native headers are used only by rr_probe; renderer/shaders remain untouched. Python compilation, CLI help and local links pass.
- Final full optional Release SDK suite passes 9/9 (553.45 seconds); rr_encoding takes 140.24 seconds and passes all seven pairs/28 rejections. Fourteen output bundles, seven numeric reference bundles and metric dictionaries match optimized Debug exactly. Six default linear outputs also match historical pre-change evidence byte-for-byte. All current milestones manually reviewed complete and plan/evidence updated. No runtime/build errors or tolerance changes; normal renderer/x86/legacy/historical-render suites were not rerun. Next is read-only default-setting queries on a live context, not speculative tuning or a claim that encoding fixed the contrast loss.
### Analytic RR colour-response isolation

- Audited pinned SDK header and AMD's current RR 1.2 manual: existing linear albedo plus NON_GAMMA_ALBEDO and indirect-radiance input/output pairing matches the documented contract. Existing textured evidence has nearly correct global colour means; simple albedo multiply/divide or red/blue swap worsens MSE. No speculative flags or output corrections.
- Added read-only spatial-response metrics and eight analytic single-plane controls. Every secondary ray misses, so expected radiance is base colour times ambient, without PBR/motion/occlusion/sample noise. Geometry and normal/depth guides must match exactly across all cases; CPU primary colour and GPU values independently agree.
- Initial test-only variance assertion was below float64 cancellation residue (5.51e-20 despite exact mean). Replaced it with an explicit float64 accumulation-roundoff bound, without changing any RR quality gate. Initial source header lookup path was corrected using rg --files.
- First complete Release analytic harness passes (rr-colour-hwpx1hil, 51.83 seconds). Constant-colour error is small, but varying vertex/texture inputs lose substantial spatial contrast even with analytic noise-free input. Black output still has a positive floor. Added three final controls: equivalent vertex/texture colour, changed irrelevant RNG seed and eight-frame stationary history. Existing SDK/native renderer unchanged; final tests follow.
- Expanded Release colour-response CTest passes (rr-colour-0u48aq8r, 95.43 seconds), as does full optimized-Python Debug (rr-colour-cm_unoww, 94.77 seconds). All eleven cases retain quality not-qualified. Three equivalent packed-input/output pairs pass: colour-through-vertex versus texture, irrelevant seed change, and two/eight-frame shared prefix. Frame-seven linear-texture MSE remains .00103086, with .273/.461/.207 centered gain and .100405 maximum error. This isolates contrast loss beyond reset without proving an internal cause or infinite-history behavior.
- Final source audit keeps the documented format pairing unchanged. Python compilation and local documentation links pass; no renderer/shader/SDK/driver/game modifications. Existing constant/surface quality tests are rerunning, while final cross-configuration byte/metric comparisons and independent affine-gain controls are checked. The planning helper cannot parse checklist phases; final milestones are reviewed manually.
- Final comparison confirms all eleven SDK/NPZ bundles and frame metrics identical across Debug/Release, with affine-gain/correlation controls passing. Release rr_quality and rr_surfaces pass 2/2 in 139.79 seconds; together with the analytic CTest all three quality harnesses pass, without declaring quality accepted. Current milestones manually reviewed complete and evidence/plan updated. Full isolation, normal renderer, x86, legacy and historical suites were not rerun. Next is explicit paired albedo encoding with verified packing/flag provenance, not speculative output correction.

### Textured/PBR reference and matched fallback

- Added opt-in surface reference with bounded point/linear textures, varying vertex colours, canonical source-verified PBR sidecars, independent primary guide checks and one-bounce secondary PBR/emission lighting. Strict original reference mode remains unchanged. Emission explicitly prevents the analytic-black shortcut.
- Added a matched-indirect float64 CPU port of the default spatial filter. Source audit corrected guides to primary ray distance and base surface colour, not RR view depth/metallic-scaled albedo. The initial low-sample fallback artifact is superseded; no renderer or filter defaults changed. A reviewed shader-source hash prevents unnoticed divergence.
- Corrected-guide 512-per-batch run (Release rr-surfaces-xt5d6i3h) passes CPU/GPU/scalar checks but exposes failed RR spatial and disocclusion gates: RR/raw full-frame MSE ratios 13.50–21.09 for texture and 9.89–23.50 for PBR. RR/fallback ratios are 143.85–303.38 across these cases. Reference variance passes raw diagnostics but narrowly exceeds the fallback 1% target, retained as failure. No claim about the internal SDK cause.
- Expanded final tests add actual point-textured GPU/SDK inputs, each fallback guide's independent rejection control, malformed PBR factors/targets and changed shader-source pin rejection. Final Release seven-test SDK suite is running; a 1,024-per-batch CLI comparison also exercises explicit materials/fallback and failed-gate evidence retention without increasing the existing work cap. Documentation records counterexamples and next isolated colour/albedo ablations. Optimized Debug verification follows.
- Final Release optional SDK suite passes 7/7 (367.13 seconds), including surface harness rr-surfaces-1x1xqyi8. Optimized-Python Debug rr-surfaces-04wvhmhq also passes (143.97 seconds). Each includes four GPU/SDK cases, 16 invalid inputs and four fallback-guide controls; all output bundles, reference arrays and frame metrics match configurations exactly.
- Final 2,048-total-sample CLI runs retain the large RR spatial failure while now passing the fallback-reference uncertainty target (0.66–0.75% versus required <=1%). RR/raw MSE ratios span 9.90–23.53 and RR/fallback 144.50–306.50. Reports and NPZs use *-quality-2048.json and *-reference-2048.npz in rr-surfaces-xt5d6i3h. Both --require-gates runs exit 2 after writing evidence. No cap/threshold or SDK pixel changes.
- CLI missing-material and overwrite failures both return 1; missing-material creates no evidence. Python compilation, CLI help, CMake regeneration and local documentation links pass. Fixed a read-only audit that misclassified an HTTPS .md link as local. Skill completion helper again reports 0/0 for the checklist style; all current milestones manually reviewed complete. Normal renderer/x86/legacy/historical suites were not rerun. Plan and evidence updated; next isolates colour/albedo/signal conventions, with defaults and raw SDK/zero-light failures unchanged.

### Independent RR quality reference

- Added optional NumPy float64 CPU reference for bounded constant-colour, non-PBR, zero-radius-light scenes. Exact recorded half-pixel rays independently trace primary geometry/albedo/normals; two PCG64 batches trace fresh diffuse bounces/shadows. Chunked 256-primary/64-sample work stays bounded. No renderer, shader or SDK implementation changed.
- JSON/NPZ evidence binds recording, source/settings/shader, candidate output, execution report, implementation and reference hashes. Packed half-float noisy input is the comparison baseline. Reference means/variance/batch differences are numeric-only arrays; no candidate bias clamping or hidden variance subtraction occurs.
- Geometric disocclusion is determined by tracing the exact old-camera ray to the current point, with separate viewport/near/far-frustum handling. Stable temporal metrics compare reference-relative residuals at compatible nearest prior pixels; this is not a complete perceptual/ghosting oracle. Per-region and temporal reference-noise diagnostics remain explicit.
- First scalar/vector check exposed canonical-setting precision mismatch (5.19e-9): fixed the test to use recorded float32 values instead of Python decimal defaults, preserving the 1e-10 scalar agreement threshold. Corrected two read-only shell lookup/reporting errors documented in task_plan.md.
- Initial 256-per-batch run passed in 30.49 seconds (Release rr-quality-qmef4xd5). Expanded 512-per-batch run passed in 44.10 seconds (rr-quality-sjgynid6): max CPU/GPU sample disagreement 7.4908071e-8, exact scalar sample agreement, 386 scalar visibility comparisons, analytic ambient-plane and injected-trail controls, ten rejection cases. Perspective motion reveals 431 pixels each frame. Full-frame RR/raw MSE ratios are 0.00815,0.00921,0.03715,0.01916; this is one small diffuse fixture only.
- Actual perspective black input still fails exact zero (max 1.0967254638671875e-5). `--require-gates` writes failed evidence then returns 2; passing narrow metrics never changes general quality_acceptance from not-qualified. Final SDK regression, optimized Debug and CLI safety checks follow.
- Optional Release SDK regression passes 6/6 (203.91 seconds), including existing dispatch/history/isolation checks. Added final small-fixture scene/vertex bounds and near/far-frustum controls; optimized Debug and Release quality-only reruns validate this last hardening. Documentation links and Python compilation pass. No renderer/SDK implementation, shaders, binaries, drivers or games were modified.
- Full optimized-Python Debug quality verification passes in 48.89 seconds: rr-quality-anz2918z. All six narrow diagnostic gates pass on the lit fixture; the actual black quality gate still fails as intended. Includes 12 rejected input cases, 386 scalar visibility comparisons, two frustum controls, analytic/determinism/convergence/trail tests and CLI exit-2 evidence retention/overwrite refusal. Final Release quality-only rerun is in progress. The planning helper cannot parse the checklist format (0/0); current milestones are being reviewed manually.
- Final hardened Release quality rerun passes in 42.79 seconds: rr-quality-uvvuebjr. Its reference arrays and all frame/gate metrics match optimized Debug exactly. Both reports preserve not-qualified and the black bias. All current milestones manually reviewed complete; optional Release regression remains 6/6. Normal renderer, x86, legacy D3D9 and historical suites were not rerun in this tool-only slice. Next broadens reference coverage and adds a matched fallback comparison, not automatic RR promotion.

### Recorded RR dispatch and reset isolation

- Added explicit native/managed RRTRRC01 admission, independent source identity checks and fixed-orientation translation dispatch. SDK camera delta comes from actual view matrices (previous world eye minus current); UV/depth motion remains recorded, reset delta is zero and SDK frame index follows segment rather than global ordinal.
- Complete native recording validation precedes device/SDK startup. Managed invocation requires scene/shader and the original material sidecar when present, with matching worker/output identities. RRTRRD01 output and reset-policy metadata stay distinct from older stationary bundles. Integrity/identity is not authentication.
- First stationary compatibility fixture used stochastic sun lighting, correctly rejected by the older contract; limited that fixture to zero sun radius. Then exact moving-reset equivalence found seven differing pixels, maximum 6.103515625e-5 (Debug rr-recorded-dispatch-vvqmrm9j). Kept failing artifacts and did not relax output tolerances. The SDK-internal cause is unknown.
- Recorded reset boundaries now fence and destroy the previous context before creating a fresh one. Continuous segments preserve actual history; six textures/two staging buffers remain reused. SDK peak is unchanged at 20 MiB per non-overlapping context, external allocation 1,900,544 bytes. All segment lifecycles and eight final external releases are checked.
- Initial full recorded test passes after context recreation, including exact reset-to-fresh output, moving repeats, cuts, identities and injected SDK-crash recovery. Expanded final tests include the maximum eight reset segments, source/report/output mutations and Python optimization checks; final results follow. Existing zero-light/raw-report failures remain separate from execution acceptance.
- Debug optional SDK suite passes 5/5 (182.49 seconds). Recorded artifact rr-recorded-dispatch-l1lnsqo4 verifies eight non-overlapping contexts at cuts, identical fresh outputs and unchanged 20 MiB callback peak. Visibility-change coverage counts are 6,14,25; these are nearest-neighbour diagnostics, not geometric disocclusion quality. This run has 16 malformed reports, 22 inputs, five outputs and four source failures. Final test expansion adds strict final-report types, mismatched material source and self-consistent metadata/actual-camera disagreement; Release and optimized Debug runs cover those final additions.
- Final Release optional SDK suite passes 5/5 (158.26 seconds). Artifact rr-recorded-dispatch-pq85bdel includes all 18 report mutations, 23 malformed recordings, five bad outputs and five source failures. Eight-cut controls match fresh contexts; callback peak remains 20,971,520 bytes. Injected SDK exit 2173 is reaped and fresh-worker output recovers exactly. Normal Release renderer rebuild passes; optimized Debug and SDK-free input/recording subset checks follow. Documentation links, Python compilation and both CLI help paths pass. The planning helper still reports 0/0 for the checklist format; milestones are reviewed manually.
- Full final optimized-Python test passes with the Debug worker: rr-recorded-dispatch-wpqr2gu0, all 18/23/5/5 report/input/output/source rejection counts. Eight output bundles match Debug/Release byte-for-byte on the same device. No validation uses removable assert statements. The SDK-free Release input/recording subset is the final running compatibility check; no renderer or shader source was edited.
- Final SDK-free Release input/recording subset passes 2/2 (67.49 seconds), after the normal renderer rebuild. Other renderer tests, x86, legacy D3D9 and historical comparisons were not rerun this worker-only slice; prior full-suite evidence is not relabelled fresh. Current three milestones reviewed complete and next high-sample/disocclusion/ghosting quality work recorded. All known quality/raw SDK failures remain explicit. No game, driver or SDK binary changes occurred.

### Renderer-owned RR input recording

- Implemented opt-in --rr-record for 2..8 frames in one renderer scene lifetime, with fixed initial orientation, explicit translation step, automatic translation cuts and optional reset index. Recording prepares each fresh matched input before advancing the camera; it does not dispatch the SDK or stack the existing filters.
- RRTRRC01 binds the exact validated loaded scene payload hash, loaded material-file hash, actual preparation DXIL hash, canonical settings and all frame metadata/inputs. The scene loader's optional digest output avoids rereading the source later. Shader changes during recording reject publication. Existing scene and single-RRI formats remain unchanged.
- Extracted byte preparation from SaveRrInputs without changing shaders. Only recording selects the continuous randomSequence, because legacy per-view accumulation indices restart on camera movement. Temporary preparation buffers are fenced/destroyed before retiring their 2,359,808-byte accounting charge; peak requested bytes remain 5,327,216 for four and eight frames.
- Added a bounded independent reader with source-file identity verification, camera/motion/reset continuity and exact-length/checksum validation. Recorded formats remain separate from stationary worker admission. Checksums are integrity, not authentication; inspector reports which external sources were actually verified.
- Initial nine-case test passed. Expanded tests cover rotated view-Z motion and offscreen geometry that changes source identity without changing visible first-frame records. Stationary frames are byte-identical to legacy prefix exports; final pixels match. An intermediate JSON placement was corrected before compiling. Final review added early malformed-pose rejection and case-insensitive output collision testing; no numerical tolerance was relaxed.
- Full x64 Debug and Release renderer suites pass 11/11. Debug report rr-record-r1cp1t4t includes ten cases/20 malformed files; Release rr-record-17r75bt1 includes ten cases/21 malformed files after the final reader hardening. Final x86/optimized-Python and stationary SDK compatibility checks follow below. No installed games, drivers or SDK binaries changed.
- x86 Debug and Release input/recording subsets pass 2/2: rr-record-9_51djnp and rr-record-qeivvsju, each ten cases, 21 malformed recordings and ten invalid-mode/path checks. Stationary, translated and rotated-depth .rrcapture files match byte-for-byte across all four configurations. All four preparation DXIL hashes also match. The Release case-insensitive collision check was separately verified after its full suite. Legacy D3D9 and historical 53-file comparisons were not rerun.
- Final optional Release SDK compatibility passes 4/4; known raw SDK reporting and zero-light quality failures remain explicitly separate from execution. Full optimized-Python recorder test passes ten cases, 21 malformed files and ten invalid-mode/path checks: build/x64-renderer/Debug/rr-record-88to_qyf/verification.json. Python compilation, source verification CLI and documentation links pass. All three current milestones were reviewed complete manually; next is native/managed admission and actual SDK moving-camera tests. No quality promotion is claimed.

### Bounded stationary RR history

- Added checksummed RRTRRS01/RRTRRT01 bundles for 2..8 frames, with per-input/output integrity and ordering identity. Native admission validates every frame before device/SDK startup. Stationary segments require initial reset, contiguous frame/random indices, fixed seed/camera, matching direct/material/geometry guides and valid near-zero motion. New reset segments explicitly discard history.
- Reused the same six typed textures and two staging buffers through one SDK context, with two fences and byte-exact input/output validation per frame. External tracked allocation remains 1,900,544 bytes; SDK peak remains 20,971,520 bytes. Reports distinguish live per-frame ownership from final eight-resource release. Output is published only after all frames, context cleanup and debug-layer checks succeed.
- First compilation hit C++ declaration ambiguity in the sequence byte-vector allocation; corrected with static_cast. A Windows rg wildcard was rejected; subsequent searches target the directory. The workspace remains non-Git. No renderer shader/source, game installation, driver or SDK binary was changed.
- Repeated four-frame segments match exactly after reset; repeats and fresh-worker recovery are byte-identical. The first frame matches the existing single-reset command. A same-final-sample reset ablation differs in 38,037 output payload bytes, proving temporal influence but not better reconstruction. Lit-to-dark reset output matches an independently started dark segment.
- Zero-light bias remains: maximum 1.0907649993896484e-5 on both first and second frames; MSE 9.602695114768744e-11 and 9.556961443289251e-11. Execution reports retain failed-zero-light-oracle; optional --require-zero-light enforces exact zero. No clamping, relaxed quality threshold or default promotion.
- Final expanded Debug SDK suite passes 4/4, including 17 malformed sequences, 13 report mutations and five malformed outputs. Artifact: build/rr-sdk-probe/Debug/rr-sequence-h1u2u4h7/verification.json. Initial Release suite also passed 4/4; final expanded Release and compatibility checks follow below.
- Final expanded Release SDK suite passes 4/4: build/rr-sdk-probe/Release/rr-sequence-wdl___wc/verification.json. Normal x64 Release renderer build and CTests pass 10/10 (170 seconds). Other architectures/configurations and historical byte comparisons were not rerun; their prior evidence is not relabelled fresh. Python compilation, CLI help and optimized-Python packing pass.
- Full optimized-Python sequence verification also passes: build/rr-sdk-probe/Release/rr-sequence-cd7frnye/verification.json, retaining failed-zero-light-oracle. All current sprint milestones are manually checked complete; the skill helper does not recognize this plan's checklist headings. Remaining quality/provenance work is explicit, not marked accepted.
- Documented an important provenance limit: matching visible guides cannot prove the same occluded geometry/settings were used across independent prefix exports. The caller must retain the source/options; a renderer-owned recorder with complete scene/settings identity is required before general camera/lighting sequences. See docs/RR_SEQUENCE.md.

### First isolated RR dispatch (execution verified; quality not accepted)

- Implemented reset-only 128x96 indirect-diffuse dispatch in the optional supervised SDK worker. Native bounded input validation precedes device/SDK creation; five typed inputs plus output are independently packed and hashed. Two fenced submissions verify uploads, unchanged inputs and complete finite SDK output. The main renderer and installed games remain untouched.
- Added RRTRRO01 checksummed output with input identity, a managed pinned-SDK dispatch command, and an equal-exposure raw/RR offline composite preview. Eight external resources use 1,900,544 allocation-info bytes under a separate 8 MiB maximum; six SDK allocations peak at 20,971,520 bytes and all tracked objects are released. Post-submit uncertain GPU lifetime terminates the child without unsafe stack cleanup.
- First dispatch returned success but preserved poisoned output alpha. Diagnostics isolated the channel; the documented preserved-alpha contract requires initializing it from packed input distance. RGB remains poisoned to detect missing writes. Secondary-miss distance alone clamps from 100000 to 65504 for half-float packing; no SDK output bias is clamped away.
- The strict black-input oracle fails with maximum 1.0907649993896484e-5 and MSE 9.602695114768744e-11, reproduced in Debug and Release. Initial suites stopped on that quality assertion. Execution tests now finish recording their own evidence, explicitly retaining failed-zero-light-oracle; --require-zero-light enforces the separate exact-zero gate. This is not quality acceptance or a default-filter promotion.
- Optional SDK builds and all three CTests pass in Debug and Release. Dispatch reports cover 11 cases, 18 rejected report mutations, nine malformed inputs and six malformed outputs, including budget rejection and byte-identical recovery after the real injected SDK crash. Optimized Python and Python compilation pass. Normal x64 Release renderer suite passes 10/10; other renderer configurations/historical comparisons retain prior evidence and were not rerun this slice.
- Final artifacts: build/rr-sdk-probe/Debug/rr-dispatch-_ol2jef3/verification.json and build/rr-sdk-probe/Release/rr-dispatch-ajfh25q9/verification.json. Raw SDK reporting acceptance remains failed under exact pinned workarounds. Documentation and next gates are in docs/RR_DISPATCH.md: temporal sequence/history, brightness bias and high-sample quality tests before live integration. No driver or SDK binary modification occurred.

### RR matched input preparation (implemented; not SDK dispatch)

- Added a separate opt-in 128x96 GPU preparation pass and checksummed RRTRRI01 export. One unjittered texel-centred primary hit supplies fresh indirect diffuse/distance, direct/emission, linear diffuse albedo, octahedral normal/roughness, signed view Z, UV/Z motion and world position/draw ID. The existing renderer's integer-centred/jittered estimators and buffers are untouched.
- New shader compilation alone enables per-texel/vertex sRGB decoding before interpolation; material factors stay linear. The official pinned sample confirms unsquared authoring roughness. Type zero is used for materials; specular indirect is not invented. First frame/cuts/reset/appearance changes invalidate motion. Invalid previous projections and finite offscreen motion have explicit handling.
- Added early headless/extent/camera admission, create-new output protection, strict bounded binary reader and CPU oracle. Additional requested GPU buffers are exactly 2,359,808 bytes; default allocation and all five baseline compute shader hashes remain unchanged. File size is 1,180,040 bytes. No SDK is loaded by this pass.
- Initial fixture tests encountered immutable vertex/sampler tuples; converted the decoded fixture recursively before editing. Corrected a size-fixture helper call after inspecting its signature. All lighting/geometry checks passed without changing shader output or relaxing tolerances. A failed exact-context patch applied no main.cpp changes and was reapplied with correct context. Initial broad discovery included build artifacts; later searches were source-scoped. Workspace remains non-Git.
- Fifteen GPU/CPU cases pass on x86/x64 Debug/Release, including PBR/emission, filtering, scissor, negative signed depth, nonzero depth motion and invalid projections. Ten malformed files are rejected; unsupported extent/camera, overwrite/collision refusal and unchanged normal outputs pass. Initial numerical maximum was 5.31947e-7 against an unchanged 5e-4 limit. Final matrix round-trip/previous-camera consistency checks are also included. Python compilation and an optimized-Python run pass.
- All nine existing renderer/authoring tests pass in every architecture/configuration; x64 full CTests pass 10/10 and x86 new input CTests pass separately. Builds have no warnings. Release temporal-tfxl8br7 compares all 53 historical files byte-for-byte. Existing optional SDK probe/worker CTests still pass 2/2 in both configurations, with raw SDK acceptance deliberately failed. Full legacy D3D9 suites were not rerun; their prior occluded-Present qualification caveat remains open.
- Planning-file tracking and docs distinguish the tested preparation export from typed-texture/dispatch acceptance. No game, driver or SDK binary changed. Next: bounded texture packing/upload in the isolated worker, frame/reset provenance, actual SDK dispatch and GPU lifetime/quality tests; no persistent bridge or RR image is claimed.
- Final matrix-inclusive evidence: x64 Debug rr-inputs-zbnlbnpi and Release rr-inputs-60ribafz; x86 Debug rr-inputs-_ega9x02 and Release rr-inputs-wy0abny6. Maximum normalized error is 1.54973e-6 including camera matrix checks; all 15 cases pass with 10 malformed-file rejections in each run. Current checklist reviewed complete; only typed resources/dispatch and later integration remain open.
- Planning completion helper still reports 0/0 for this repository's checklist-style headings; the three current milestones were checked manually against the implementation and final reports.

### RR issue resolution (managed context boundary verified)

- Audited AMD's public v2.3.0 API wrapper: the pointer-to-context query and override chain are correct; no supported client-call change was found to correct the invalid SDK totals. Preserve the earlier double-destroy ownership fix and raw SDK failure evidence.
- Added a native suspended-start, one-process Windows job boundary. Only explicit pipe/NUL handles are inherited; SDK/GPU work stays in the child. Output is bounded per stream, deadlines and overflow terminate the job, child exit codes are preserved, and assigned-child termination on host exit is tested.
- Added a separate managed policy that verifies exact SDK DLL hashes, accepts only the observed reporting anomalies, and requires the expected bounded callback accounting: 20 MiB peak, six allocations/releases, no outstanding bytes/errors/denials. It reports context-ready-with-workarounds alongside raw_sdk_acceptance failed and rr_rendering false. Unknown SDK/report failures disable the attempt.
- Tested malformed/NUL/deeply nested/duplicate-key/nonfinite JSON, transport failures, timeout, output flood, parent exit, missing/unreviewed DLLs, 22 report mutations/malformed cases, budget rejection, the real second-heap SDK crash and recovery in a fresh worker. Validation uses explicit checks and also passes under optimized Python. Hash streaming retains Python 3.10 compatibility; execution was tested on the installed Python 3.12, not 3.10.
- Both optional CTests pass 2/2 in Debug and Release. Final regular evidence: build/rr-sdk-probe/Debug/rr-worker-rs6ouxp8/verification.json and build/rr-sdk-probe/Release/rr-worker-lpujrfgh/verification.json. Builds are warning-free. Python compilation passes. Fresh x64 Release renderer suite passes 9/9; other baseline configurations and legacy suites were not rerun in this probe-only slice.
- Updated plan, RR guide, roadmap, viewer and README. Planning tracking distinguishes the passing containment/workaround contract from unchanged failing raw SDK acceptance. No persistent rendering worker, shared textures/fences, denoising dispatch, game changes, driver update or SDK binary fix. Next: separate fresh diffuse/hit distance and matched guide textures, then isolated GPU dispatch/lifetime and image-quality acceptance.

### RR bounded context lifecycle (mechanics verified; SDK acceptance open)

- Added opt-in 128x96 context tests using the enumerated provider override, SDK validation, pre-context admission and resource/heap callbacks with a 64 MiB ceiling. No SDK rendering dispatch, renderer shaders or game files changed.
- Initial compilation fixed private-header placement outside the anonymous namespace. Removed an incorrect assumption that callback effect IDs equal public API effect IDs (backend reports 22).
- Fixed our teardown double-destroy: the provider leaves the handle non-null after successful destruction; explicit ownership clearing matches AMD's sample. Repeated lifecycles now create two heaps/four resources, peak at 20,971,520 tracked bytes, and release all objects with zero tracked bytes left.
- Added allocator-contract tests (bounded allocation, injected failure, heap metadata validation, exact release) and separate real SDK acceptance diagnostics. Preflight rejects 1 MiB without calling CreateContext. Normal SDK querying remains the default and creates no context.
- SDK post-context memory reporting returns an invalid near-uint64-wrap total in both custom-allocator and default-allocator control cases. General provider-version query returns 6. Denying the second heap crashes the isolated child at CreatePlacedResource (0x87d), not a clean failure. A new child can create/destroy again. These remain explicit failures, not a green RR acceptance claim.
- Debug evidence: build/rr-sdk-probe/Debug/rr-context-djpapm3v/verification.json. Release: build/rr-sdk-probe/Release/rr-context-krgbcajb/verification.json. Three normal lifecycles pass mechanics in each; both overall acceptance reports intentionally fail. Both builds and expanded rr_probe_contract CTests pass; Python compilation passes.
- Fresh x64 Release baseline renderer/authoring suite passes 9/9. Other renderer configurations and legacy suites were not rerun because no renderer, shader, D3D9 or CMake source changed in this slice; their previous evidence is retained, not relabelled as a new run. The planning completion helper still reports 0/0 for this checklist convention; the implemented milestones and open SDK acceptance item were reviewed manually.
- Updated RR guide, README, viewer and roadmap. Planning keeps verified lifecycle mechanics separate from unresolved SDK acceptance. Actual RR dispatch/input guides and robust runtime isolation remain next work. Full legacy/game qualification remains open; no installed game or driver was modified.

### Variance experiment and AMD RR provider investigation

- Implemented an opt-in two-stage variance filter with retired-history scratch reuse and no new full-frame allocations. Three candidate designs failed the unchanged 5% quality-improvement gate. The final candidate's mean MSE is 34.63 versus 34.26 for the old filter; it is not promoted and its failing quality test is not registered as passing CTest acceptance.
- Final-candidate x64 Debug mechanics evidence: variance-bskfko08; Release: variance-5fr36xe4 (under the respective build configuration). CPU/GPU error below 1.45e-6, raw/history isolation, native controls/resets, glossy/boundary checks and repeated full-HD output pass. Both reports still say quality-gate-failed.
- Following the planning skill's three-attempt rule, asked for direction. User selected deeper denoiser research and AMD RR. Read current official documentation and pinned 2.3.0 headers, then mapped missing renderer inputs and memory constraints instead of further filter tuning.
- Downloaded only the required SDK research subset to build/dependencies/fsr-2.3.0-probe from commit 60f4ea81909200d8542eca14dccb2628b763a9a3; retained license notice. Both DLL signatures verify as AMD. No drivers, games or renderer DLL search paths were changed.
- Added optional x64 rrt_rr_probe, using explicit SDK paths and official API structures. Actual RX 9070 XT results: SM 6.6 supported; RR 1.2.0 provider ID 4311875584; one-signal internal estimates 19,988,480 bytes at 128x96 and 279,576,576 at 1920x1080. Debug/Release contract tests pass, including error handling and D3D12 debug-message checks. Zero contexts and dispatches: this does not establish RR image quality.
- All four renderer builds are warning-free; all nine baseline renderer/authoring tests pass in x86/x64 Debug/Release. Historical comparison build/x64-renderer/Release/temporal-flc8v06_/verification.json matches 53/53 prior files. Python compilation passes. Full legacy suites were not rerun; previous occluded-Present qualification caveat remains open.
- Added docs/RAY_REGENERATION.md and roadmap/viewer/README links. Next: bounded context admission and correctly defined fresh diffuse/guide textures, then real RR dispatch. Existing defaults and budgets remain unchanged. No installed commercial game was touched.

### Phase 5 static material/light inputs

- Added strict JSON authoring/template commands and deterministic RRTMAT1 sidecars, with checksums, immutable renderer inputs and stable material-ID matching. Existing scene/mod formats remain untouched.
- Added per-draw tint/roughness/metallic/emission, GGX/Smith/Schlick direct shading, secondary emission and diffuse-only PBR bounce transport. Legacy records retain the existing branch; no specular path tracing, sRGB conversion, new full-frame buffers or budget increases.
- Added light RGB/intensity/ambient controls, provenance JSON and actual light-history invalidation tests (including non-white to non-white changes), with no forced resets or GPU reallocation.
- Added CPU authoring validation plus GPU BRDF, override-isolation, shadow, emissive transport, metallic diffuse suppression, native parity and corrupt-file tests. Corrected a silhouette-sensitive transport test oracle; initial GPU flags review fixed colour-bit retention before acceptance.
- Initial x64 Debug evidence: build/x64-renderer/Debug/materials-xx24cx1e/verification.json, normalized BRDF error 2.64e-7; historical default parity in temporal-rriya_x2 matches all 53 files. Expanded nine-test x64 Debug/Release suites pass; x86 matrix in progress. Docs now explain authoring, binary bounds and rendering/FidelityFX limitations.
- Final: all four builds warning-free, all nine renderer/authoring CTest entries pass in x86/x64 Debug/Release. After adding the full-HD material case, both material entries passed again in all four configurations. Final Release material evidence materials-5869_ix8; x86 Debug materials-25gnbj_5 and Release materials-wa1f89a5. Sixteen malformed binaries rejected, CPU unit tests 5/5, and Python compilation passed. Final Release historical check temporal-fo40zxcb matches 53/53 prior files. Full legacy suites were not rerun; prior S_PRESENT_OCCLUDED acceptance caveat remains open. No commercial installation was touched.

## Session: 2026-09-02

### Phase 5 message-responsive frame admission

- Added waitable swapchain creation/resize flags, one-frame maximum latency, RAII handle ownership and explicit --no-frame-pacing opt-out.
- Deferred the first native interactive sample behind admission. Waits wake for messages or after 100 ms; consumed admission persists across the message pump. No timeout bypass, silent fallback, scene/shader/signal-format changes or raised memory budgets.
- Added dxr_pacing: headless/unpaced/paced output parity, repeated resize/pause/suspend/early-close paths, three synthetic wait outcomes and invalid-option checks. Smaller fixtures also compare float signals; full HD compares pixels and memory accounting. Existing async diagnostics explicitly remain unpaced; their early-close path now checks the real paced route.
- Initial x64 Debug pacing evidence: build/x64-renderer/Debug/pacing-1jusmly9/verification.json. The initial deferred-render call tripped RenderTo's positive-target assertion; fixed by skipping that call for zero initial samples, not weakening validation.
- Updated guides and phase plan; planning-file tracking keeps hidden-window mechanism evidence separate from still-open real desktop/game qualification.
- Final x86/x64 Debug/Release builds are warning-free and all four renderer suites pass 7/7. Release pacing artifact: build/x64-renderer/Release/pacing-s9rbk9t0/verification.json; x86 Debug pacing-zc77p8rv and Release pacing-prej64ix also pass. Historical comparison build/x64-renderer/Release/temporal-yk7ybp2w/verification.json matches all 53 prior files byte-for-byte. Python compilation passes. Legacy D3D9 suites were not rerun in this renderer-only slice; their previously recorded occluded-Present qualification issue remains open.

### Phase 5 asynchronous submissions and sparse readback (implemented; legacy qualification caveat)
- Used planning-with-files to keep this slice scoped to GPU ownership/readback decoupling, retaining the existing legacy qualification caveat. Consulted Microsoft allocator/fence resource guidance and recorded primary references.
- Added four command allocator/list slots, fence-gated reuse, per-slot 256-byte constant regions, per-slot timestamp ranges and deferred timing collection. Native samples/display submit without immediate waits; the ordered direct queue and existing resource barriers preserve raw/temporal dependencies. Back-buffer fences bound display reuse; Present remains vsynced.
- Native viewing omits each sample's renderer output copy/map, then snapshots once on close for final pixels/hash. Synchronous headless/GDI/window diagnostics remain intact. Explicit snapshot/export/resize/normal teardown drains pending GPU work and clears references in every command slot before releasing display buffers. Reported scene-build counts exclude new snapshot submissions; metrics expose slots, outstanding submissions, readbacks, waits and retired sample timings.
- Added --async-test and --async-close-test plus dxr_async. Verified 129-sample control sequence with six snapshots, all four slots, two back buffers, three resizes, sparse back-buffer checks, history resets and deterministic pixels/signals. Closing after seven queued samples produces the exact seven-sample reference with one readback. Full-HD pixel parity stays within the unchanged 512 MiB cap; exports are compared on smaller fixtures to bound test artifact size.
- Fixed final-image provenance during close: defer configuration while unable to render, and report last-rendered options rather than a queued-but-unrendered change. Early-close tests exercise this by posting a mode change just before close. Evidence: build/x64-renderer/Release/async-975mqyl1/verification.json. No rendering shaders, scene/signal formats, capture/proxy/sample code or installed games were changed.
- Final builds are warning-free; all six DXR tests pass in x86/x64 Debug/Release, with standard D3D12 debug-layer checks. Both full x86 runs finish 10/16 because the same six legacy capture/mod/proxy cases encounter S_PRESENT_OCCLUDED; fresh Debug verify-classic-z7ei6shp/capture.rrt.jsonl contains 12/12 Present results 141953144. Kept the failure explicit without changing legacy capture admission. Final async evidence: build/x64-renderer/Release/async-4noh41bt/verification.json. Python compilation passes; historical parity still matches all 53 files in build/x64-renderer/Release/temporal-xkf1p403/verification.json.
- Updated viewer/build/README/phase/work guides for async ownership, sparse readbacks, final-image provenance, counters, diagnostic commands and limits. Present remains vsynced with fence-based back-pressure; no waitable-object latency controller, throughput claim, device-loss recovery or live game bridge is implied. Next: measured latency/presentation refinements and material/light inputs; legacy qualification still needs normal Present conditions.

### Phase 5 native standalone presentation (implemented; legacy qualification caveat)
- Used planning-with-files to recover the next gate and keep async presentation/live injection outside this slice. Consulted Microsoft D3D12 swapchain and DXGI status documentation; recorded primary links and the flip-model occlusion caveat in findings/viewer guide.
- Added presentation.h ownership and display.hlsl vertex/pixel stages, making six deployed DXIL files. Native windows default to a two-buffer flip-discard swapchain and fullscreen GPU-source pixel pass; --gdi retains the earlier window explicitly. Render output/history resolution remains independent of display resolution.
- Added resource transitions and a fence after Present, resize admission/peak accounting, old-reference release, window suspension/restoration and timed occlusion probing/repaint. Native display is still synchronous; CPU renderer readback remains per sample. No proxy/capture/game-installation edits.
- Added --presentation-test and dxr_presentation. Actual back-buffer copies use device-reported row pitch and compare every pixel with the headless reference, including 257-pixel non-aligned source width and resized targets. Five fixture cases include full-HD GI, both buffers, three resizes, controlled WM_SIZE suspension/restoration, deterministic occlusion-status handling, bounds rejection followed by valid drawing, GDI equivalence and repeated process lifecycles.
- Initial acceptance passed: build/x64-renderer/Debug/presentation-46or8aea/verification.json. Full-HD peak 525,341,028 requested bytes, below unchanged 512 MiB. Hidden-window checks establish buffer content/API ownership, not real scanout/desktop occlusion/DPI/fullscreen/device-loss recovery. Over-budget interactive resize currently exits explicitly.
- Historical baseline remains byte-exact for all 53 files after native display changes: build/x64-renderer/Release/temporal-1fkn55n6/verification.json. Python compilation passes. A documentation patch encountered a stale context hunk; reapplied with the matching context, without code/test changes.
- Final builds warning-free in x86/x64 Debug/Release. Both x64 suites pass 5/5. Both x86 suites pass all five DXR tests, including presentation, but finish 9/15 overall: six older classic/Ex capture/mod/proxy cases hit missing captures/zero committed Presents. Debug verify-classic-mw51wbg3/capture.rrt.jsonl has 12 Present results of 141953144 (0x08760878, SDK S_PRESENT_OCCLUDED). System/proxy pixel equality passes before the present-count assertion. An isolated classic rerun after all other renderer work ended reproduces it. No proxy/capture/sample changes or weakened admission rules; full legacy qualification awaits normal presentation conditions. This is the recurring historical display condition, not a passing full-suite claim.
- Release presentation evidence: build/x64-renderer/Release/presentation-qa1p1_w_/verification.json. Updated README/build/viewer/phase/work plans with direct GPU-source display, six matching shaders, exact tests and lifecycle/performance caveats. Next implementation is readback decoupling/per-frame ownership; full legacy regression rerun remains a separate outstanding gate.

### Phase 5 compact buffers and full HD (complete for this slice)
- Used planning-with-files to recover the previous gate, track the memory/layout work, and leave native presentation as an explicit next slice. No proxy/capture/sample or installed-game changes.
- Split the 144-byte diagnostic layout into an 88-byte current record and two 64-byte temporal buffers, retaining full float32 values. Frame-buffer cost including raw/output/readback drops from 312 to 240 bytes/pixel (23.1%). Runtime signals alone drop from 288 to 216 (25%). No allocation caps were increased.
- Added rrt_export.dxil and bounded, on-demand 16,384-pixel export submissions with a fixed 4.5 MiB staging pair. Diagnostic format remains RRTSIG02/144 bytes. Shared root binding, separate export counters/timings, frame/history barriers and compact ping-pong transitions preserve one scene build with no per-sample allocations.
- Streaming inspection now validates up to 1 GiB without materializing an entire file; random-access load_signals remains capped at 256 MiB. Both use the same per-record invariants. Added dxr_resolution and optional --full-hd-export coverage for HD rendering, deterministic GI, chunk tails/late corruption, export colour parity and unchanged budget rejection.
- Important correction: initial 80-byte layout recomputed motion and passed normal tests, but historical parity exposed tiny frustum-edge rounding differences and altered temporal reuse. Restored original motion values in the 88-byte record; the final --baseline temporal diagnostic matches 53 scene/pixel/signal artifacts exactly. Evidence: build/x64-renderer/Release/temporal-0yv_0b_r/verification.json, baseline temporal-r1d7hezu. Original temporal quality/rejection metrics are unchanged.
- Full-HD evidence: build/x64-renderer/Release/resolution-gaes_1le/verification.json. Requested allocation 497,681,520 bytes (474.63 MiB); with exports 502,399,856 (479.13 MiB). The 298,598,436-byte export validates in 127 chunks with byte-identical presentation. The 2560x1440 fixture rejects with GPU allocation budget exceeded and creates no outputs. Timing is synthetic evidence, not game FPS or measured VRAM residency.
- Final builds warning-free; x86 Debug/Release each pass 14/14, x64 Debug/Release each pass 4/4. RX 9070 XT tests use the standard D3D12 debug layer, not GPU-based validation. Python compilation passes; standalone full-HD-export and historical-parity diagnostics also pass. Earlier 80-byte test artifacts remain as historical intermediate evidence only.
- Updated README, phase/work plans, build guide and renderer guide for four-shader deployment, compact memory, streaming exports, validation and native-presentation boundary. Next: standalone swapchain with headless oracle, resize/occlusion/back-buffer ownership tests, then GPU-only display and buffered fences. Live game integration, animated objects, FSR and radiance caching remain later gates.

### Phase 5 temporal reuse (complete for static-scene slice)
- Used planning-with-files to track fresh-sample reuse, rejection/variance, diagnostics and verification. Added a third compute pass (rrt_temporal.dxil) and double-buffered signal SRV/UAV state transitions without geometry rebuilds or per-sample allocations.
- --temporal blends fresh stochastic samples, not cumulative raw radiance. Nearest-pixel reprojection checks projection, prior hit, draw/albedo/normal and world-space plane/position agreement. Moving histories get matching-surface neighborhood clipping; effective count is capped at 32 and luminance second moments/variance are exported.
- Separate raw accumulation still resets on view changes. Small camera moves preserve temporal history/RNG; lighting/settings/mode changes, explicit R/Home and scale-dependent camera cuts reset it. Added T toggle, reset controls and move/light/cut/reset diagnostics. --history-test forces fresh comparison on changed/restored settings even when temporal mode is enabled.
- Extended signal export to RRTSIG02, stride 144, with world hit/footprint, fresh RGB, temporal RGB/second moment and count/variance/acceptance/reason. Inspector retains explicit RRTSIG01 compatibility and validates bounds/statistics/projection prerequisites.
- Added dxr_temporal acceptance: stationary means and moments independently reconstructed from fresh samples, cap/reset checks, deterministic movement, genuine newly revealed ground with identical draw/material/normal, separate material rejection, quality comparisons and resource reuse. First run caught a test expectation error (18 raw resets versus 17 valid temporal invalidations); corrected the assertion after inspecting actual runtime counters, without weakening image checks.
- Final results: x86 Debug/Release 13/13 each, x64 Debug/Release 3/3 each. All four builds warning-free; Python compilation checks pass. Hardware tests run with standard D3D12 debug-layer validation on RX 9070 XT, not skipped. No proxy/capture/sample or game installation changes.
- Release evidence: build/x64-renderer/Release/temporal-r1d7hezu/verification.json. Accepted moving pixels have MSE 0.000017343 versus fresh 0.00028201 against 256 samples. 1,419 newly revealed ground pixels explicitly reject old foreground history. Overall: 9,111 accepts, 1,449 world-position rejects, 1,728 projection rejects. Light/cut/manual reset output matches fresh rendering.
- Inspected earlier same-code Release temporal-zeierock moved/reference PNGs: stable regions smooth, rejected regions retain fresh grain, localized shadow retained. Updated viewer/build guide, README and phase/work plans with thresholds, variance meaning, three-shader deployment and explicit limitations.
- Next practical gate is memory/layout and native presentation: current debug-rich ping-pong buffers use 288 bytes/pixel plus optional 144-byte readback and reject full HD under existing limits. Temporal reuse remains static-opaque/camera-only, conservative and biased; no animated geometry, advanced variance-adaptive denoiser, FSR, radiance cache or live game bridge is claimed.

### Phase 5 renderer signals and spatial filtering (complete for this slice)
- Used planning-with-files to recover state and track signal, filtering, acceptance and documentation milestones. Kept prior code/captures intact; no subagents or external game changes.
- Added 80-byte GPU signal records: raw accumulated mode RGB, unjittered world normal/ray distance, albedo/hit validity, camera motion/projection validity/draw ID, and filtered RGB. Motion uses the previous completed sample, survives accumulation resets as diagnostic provenance, and invalidates background/first/out-of-frustum projections.
- Added a separately compiled rrt_present.dxil compute pass. Optional 5x5 geometry/albedo-guided filtering reads raw signals and never overwrites accumulation. Reusable constant-buffer upload replaces root constants; explicit UAV/transition/fence ordering covers both passes and optional signal readback.
- Added --denoise, F key, --signals and a bounded RRTSIG01 binary inspector, with mode in the 36-byte header. Signal files and pixel outputs cannot overwrite existing files or use the same case-insensitive normalized path. --motion-test renders a known +0.1 world-X/Y camera move for acceptance.
- Extended GPU tests for finite signals, known depth/normal/albedo values, motion (+6.4,-4.8 pixels), stationary/first/out-of-frame validity, raw/filter separation, deterministic noise reduction, albedo/background edge isolation, malformed signal rejection, and filter resets/window controls. History test now performs 152 sample submissions and 18 resets; geometry builds once.
- All four configurations build without warnings. Full x86 Debug and Release pass 12/12 each; x64 Debug and Release pass 2/2 each on RX 9070 XT with standard D3D12 debug layer. Previous S_PRESENT_OCCLUDED condition cleared; no proxy/capture/sample semantics changed. Python compilation checks pass.
- Release evidence: build/x64-renderer/Release/dxr-df3x44pj/verification.json. Filter lowers one-sample fixture MSE from 109.3787 to 29.2402 against 256 samples. Raw signals remain identical on filter toggle. Inspected Debug dxr-glgtoq6c raw/filtered PNGs: reduced grain, expected modest smoothing, triangle/shadow retained.
- Updated viewer/build guides, README, phase plan and work logs. Explicit limitations: literal RGB, near-plane ray distance rather than FSR depth, camera-only projection validity rather than disocclusion safety, no temporal reuse, roughness/specular signals or FidelityFX integration. Signal overhead is 80 bytes/pixel GPU plus optional equal readback, included in allocation limits.

### Phase 5 progressive/interactive sprint
- Used planning-with-files for the persistent-resource, sampling, controls and verification milestones; updated task_plan.md before implementation.
- Refactored one-shot rendering into a persistent Renderer with one BLAS/TLAS build batch, fenced allocator/list reuse, output state transitions and float-history UAV barriers.
- Added deterministic bounded GI sampling: jittered primary rays, disk-sampled directional light, one cosine-weighted diffuse bounce and pre-quantization running averages. Preserved deterministic albedo/normal/relit modes and old raster comparisons.
- Added --samples/--seed/--sun-radius, headless camera transforms, interactive keyboard navigation, mode/light/shadow controls, Home and pause/resume. Parameter changes invalidate history without allocating or rebuilding geometry. Preview remains GDI readback rather than a D3D12 swapchain.
- Added finite CLI/camera bounds, headless history diagnostics and hidden native-window message-loop acceptance. Paused movement displays one fresh sample; restored settings produce byte-identical images.
- GPU acceptance now covers fixed-seed repeatability, changed-seed variation, convergence against a finite reference, independently demonstrated colour bleeding, resource reuse, sixteen history resets and the hidden-window controls. Invalid options must fail without output.
- All four builds succeed without warnings. DXR tests pass on actual RX 9070 XT in x86/x64 Debug/Release; both x64 suites pass 2/2. Full x86 suites each pass 6/12: six pre-existing presentation-dependent tests encounter S_PRESENT_OCCLUDED and consequently do not commit captures. Proxy/system equivalence assertions pass before successful-present counts fail. No unrelated proxy/capture/sample source was modified or assertions weakened. Asked the user whether the desktop/display needs unlocking/waking.
- Release renderer evidence: build/x64-renderer/Release/dxr-kz90jed1/verification.json. MSE 109.3787 at one sample versus 3.5835 at 32 against 256; diffuse colour gain about 20.6 channel levels. History: 136 dispatches/16 resets/one build. Window: 33 dispatches/four resets/one build. Allocation stays 311,920 requested bytes for the two-draw fixture. Inspected bounce-red.png.
- Updated README, PHASE_PLAN and DXR viewer guide with implemented scope, controls, timing semantics, sampling limitations and next renderer-buffer/denoising gates. No game installation was touched; no full path tracer, FidelityFX, radiance cache or live-runtime integration is claimed.

### Phase 5 DXR first-render sprint (complete for static first slice)
- Implemented a standalone D3D12 renderer using hardware DXR 1.1 inline ray queries, per-draw BLAS and a TLAS, imported camera/geometry/texture state, albedo and normal modes, and directional relighting with secondary shadow rays.
- Windows SDK DXC compiles cs_6_5 at build time; runtime consumes DXIL without a compiler DLL dependency.
- First native run detects RX 9070 XT, DXR tier 1.1 and shader-model-6.5 support. Albedo rendering passes with the D3D12 debug layer enabled; relit rendering also completes. First-run wall time includes shader/driver compilation, not steady-state GPU performance.
- GPU fidelity, actual shadow occlusion, bounded rejection and modded-scene tests are next. x86 DXGI memory reporting is not a trustworthy full-VRAM capacity measurement; plan a separate x64 renderer preset.
- Added a renderer-only x64 preset; its DXGI report sees approximately 16 GiB instead of the x86 report's limited SIZE_T capacity. No x64 game proxy is built in that preset.
- First x64 test exercised albedo, normals, localized shadow occlusion and mod import successfully, then exposed a test-only tuple-mutation error in negative-case construction; converted those copied fields to mutable lists.
- Added separate GPU timestamp measurements for acceleration-structure build, trace dispatch and readback copy. They are distinct from CPU/driver first-run wall time.
- x64 Debug/Release renderer suites pass with installed D3D12 debug-layer checks. Added perspective/view/world, point/linear, vertex-colour and scissor comparisons, finite-range admission and no-output-on-rejection checks. Full x86 Debug also passes all twelve entries; final Release regression is running.
- Release x64 evidence: `build/x64-renderer/Release/dxr-_9iqyq5w`. Ground/occluder albedo has zero differing pixels; shadow toggle changes 240 pixels. Camera comparisons have zero pixels with error above two levels. Inspected relit/camera PNGs visually; scene geometry and localized shadow agree with the tests.
- Added docs/DXR_VIEWER.md including runnable x64 commands, API sources, hardware requirements, exact rendering subset, timing meanings and unimplemented full-path-tracing/live-game/FidelityFX work.
- Final regression: all twelve x86 CTest entries pass in Debug and Release; both renderer-only x64 entries pass in Debug and Release. DXR cases ran on hardware (not skipped), with standard D3D12 debug-layer validation. `tests/verify_dxr.py` passes py_compile.
- Completed static scene rendering/diagnostics; interactive frame presentation, camera movement, GI/reflections, PBR, temporal accumulation/denoising, FidelityFX and game qualification remain future gates.

### Phase 4 offline mod sprint (complete for offline slice)
- Implemented strict versioned manifests, pinned dependency hashes, portable root-contained asset paths, bounded PNG/mesh/material loaders and deterministic priority/conflict resolution against original capture IDs.
- Added editable asset extraction, identity starter mods, manifest creation/check/application CLI and a byte-compatible Python scene encoder. Output is a new self-contained scene; input captures are untouched.
- First eight offline test methods pass, including all PNG filters, malformed JSON/assets, conflicts, unmatched targets, symlink escape, partial captures and no-op byte identity.
- First classic GPU run passes six cases: texture/mesh/material isolation, composition, repeated-session/order independence and static mesh matching after Reset. Unaffected quadrants have zero changed pixels.
- Review added decoded PNG/geometry budgeting (compressed file sizes alone are insufficient) and retained runnable valid mod artifacts separately from deliberately damaged dependencies.
- Final Release suite passes all ten CTest entries; Debug also passes all ten. Offline validation now has nine test methods, including a compressed-payload budget regression. Python modules compile cleanly.
- GPU tests pass six replacement cases each for classic and Ex. Release evidence: `build/x86-vs/Release/mods-classic-4zof63vk` and `mods-ex-mh1zgo4t`. `isolation-report.json` shows zero changes in every unaffected quadrant; combined output hash repeats exactly across captures/argument orders.
- Visually inspected combined.png: the lower-left triangle is magenta, both right-hand meshes shrink, and the top pair use linear texture filtering, matching the intended edits.
- Added `docs/MOD_WORKFLOW.md`, JSON manifest schema, mesh/material examples and updated build/phase documentation. This completes the offline creator workflow, not live game modding, lights/PBR or DXR.

### Phase 3 capture/replay sprint (complete for first supported slice)
- Added resource-owned CPU-write shadows, canonical scene structures, SHA-256 asset IDs and integrity-checked binary serialization.
- Added generated interception hooks and an independent system-D3D9 replay executable; capture is opt-in via RRT_SCENE_FILE/RRT_SCENE_FRAME.
- First build found a Windows type mismatch (DWORD versus UINT for GetStreamSourceFreq); corrected the query variable.
- Added a four-quadrant scene fixture with partial writes, negative base-vertex/32-bit indices, UP/16-bit indexed-UP draws, transforms and scissoring. Exact replay passed for frames 0, 1, 6 and 7 in classic/Ex Debug, including resize/reset and swap-chain presents.
- All seven Debug CTest entries passed with negative cases for shaders, surface writes, partial DISCARD, wireframe, missing clear and draw budget. Adding PNG QA exposed a Python local variable shadowing the PNG encoder; renamed that test variable before final verification.
- The same test-report addition accidentally dedented capture indexing out of the frame loop (KeyError in repeatability check); restored loop indentation. These were test-report regressions, not image mismatches.
- Final verification: all seven CTest entries pass in both x86 Debug and Release. Classic and Ex each prove exact pixels for frames 0/1/6/7, before/after reset and across device/swap-chain presents. Ten malformed scene variants are rejected by both the C++ and Python readers.
- Added self-contained glTF export (embedded PNG textures, vertex/index data, unlit materials and transformed nodes); exporter tests cover structure, refusal of partial captures and existing-output preservation.
- Added README/build updates and docs/SCENE_CAPTURE.md with exact supported subset, budgets, schema, failure behavior and replay/export commands.
- Final Release evidence: build/x86-vs/Release/scene-classic-iko0j8ys and scene-ex-f720n79u. Inspected replay.png visually: all four textured quadrants are present, including the clipped lower-right triangle. image-diff.json records zero differing channels for all four frames. Python modules also pass py_compile.
- Broad extraction (lights/depth/other formats), commercial reference scene, multithread/shared-resource writers and second-GPU/performance qualification remain open; no DXR/FSR implementation claimed.

### Implementation sprint: next two phases
- Replaced the top-level-only proxy with generated typed forwards for 20 D3D9/9Ex interfaces, canonical COM identity tracking, native argument unwrapping, and resource/swap-chain return wrapping.
- Removed logging/locks from DllMain; system runtime is initialized once on first API use. Added explicit disable mode and documented D3DPERF exports.
- Added a textured triangle harness, shader/fixed-function/UP draws, pixel readback, COM identity tests, swap-chain presentation, resize/reset, and an explicit system-runtime baseline.
- Fixed two build issues (IUnknown include and treating HDC as scalar metadata), and a real wrapper selection bug caught by the vertex-buffer test (choose derived resource interfaces before their bases).
- Classic D3D9 and D3D9Ex now execute the textured harness; baseline and proxy image hashes match in initial runs.
- Trace format, inspector, and validation suites completed. Final Debug and Release preset runs passed all five CTest entries in each configuration.
- Final classic capture: 305 events, 12 presents, 36 draws (24 fixed-function / 12 shader), expected deliberate failures, and zero live wrappers at finish. Exact BGR images match native D3D9, proxy, disabled proxy, and trace-off runs.
- Verified final CLI report against build/x86-vs/Release/verify-classic-u29ir3y1/capture.rrt.jsonl. Other artifacts remain alongside it under verify-* directories.
- Added README, CMake presets, trace-format documentation, updated build instructions, and a qualification ledger. No commercial-game install was modified.

### Phase 1: Feasibility discovery
- **Status:** complete
- Actions taken:
  - Checked for prior planning context; none was found.
  - Inspected the workspace; it contains no project files.
  - Initialized durable planning files.
  - Researched current ROCm Windows support and the published RTX Remix runtime architecture/compatibility constraints.
  - Researched D3D12/DXR, HIP-Vulkan interoperability, and FidelityFX FSR integration boundaries.
  - Produced the proposed architecture, MVP, milestone gates, risks, and initial repository shape in ROADMAP.md.
  - Expanded the roadmap into an implementation-ready, phase-gated plan including ROCm 10 and a constrained DX10/11 research track.
  - Began Phase 0/1 with a CMake D3D9 smoke harness and an initial system-D3D9 forwarding proxy scaffold.
  - Verified that FSR Radiance Caching and Brixelizer GI are viable deferred integrations after renderer/capture correctness.
  - Built the x86 Debug configuration with Visual Studio 2022 Build Tools and ran both CTest and the actual 120-present smoke sample through the proxy.
  - Added an `IDirect3D9` observer that logs `CreateDevice`, then rebuilt and verified the proxy path.
  - Added a reference-title admission protocol so a local, lawful DX9 title is selected from measured proxy/trace evidence rather than a compatibility-list guess.
  - Added the actual 120-present smoke path to CTest and verified both x86 tests pass.
  - Classified BioShock 2 original as a later DX9 shader-observability target and excluded the DX11 Remastered release from the current interposer scope.
  - Added an automated device-reset event to the D3D9 smoke sample and initialized the measured compatibility ledger.
- Files created/modified:
  - task_plan.md
  - findings.md
  - progress.md
  - ROADMAP.md
  - PHASE_PLAN.md
  - CMakeLists.txt
  - src/proxy/d3d9_proxy.cpp
  - src/proxy/d3d9_proxy.def
  - src/sample/d3d9_smoke_sample.cpp
  - docs/BUILD.md
  - docs/REFERENCE_TITLE.md
  - docs/COMPATIBILITY_LEDGER.md

## Test Results
| Test | Input | Expected | Actual | Status |
|---|---|---|---|---|
| Workspace inventory | File listing | Existing project context or empty directory | Empty directory | ✓ |
| Feasibility review | Current official AMD, Microsoft, and GPUOpen docs | Choose renderer/runtime separation | D3D12/DXR baseline; HIP optional offline tooling | ✓ |
| x86 configure/build | Visual Studio 17 2022 generator, Win32 | Build proxy and smoke sample | Both targets built successfully | ✓ |
| CTest | `d3d9_smoke_sample --help` | Test passes | 1/1 passed | ✓ |
| Live proxy smoke | `d3d9_smoke_sample.exe` beside generated proxy | 120 presents; proxy logs real D3D9 load | Passed; proxy log recorded system DLL and `Direct3DCreate9` | ✓ |
| Device observation | Smoke sample through proxy | `CreateDevice` is forwarded and logged | Passed; log recorded successful device creation | ✓ |
| Automated proxy smoke | CTest `d3d9_smoke_sample_run` | Complete 120 presents through generated `d3d9.dll` | Passed (2/2 CTest tests) | ✓ |
| Reset lifecycle smoke | 120 presents with a reset at frame 60 | Reset succeeds and presentation continues | Passed in CTest and direct x86 run | ✓ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|---|---|---:|---|
| — | None | — | — |
| 2026-09-02 | CMake Ninja generator rejects `-A Win32` | 1 | Updated the documented x86 build command to use the Visual Studio generator. |
| 2026-09-02 | Existing `build/x86` cache used Ninja | 2 | Used clean `build/x86-vs` for validation; retained failed cache rather than deleting it. |
| 2026-09-02 | CMake Ninja generator rejects `-A Win32` | 1 | Updated the documented x86 build command to use the Visual Studio generator. |

## 5-Question Reboot Check
| Question | Answer |
|---|---|
| Where am I? | Phase 5 optional temporal reuse, surface rejection and moments implemented; all four acceptance configurations pass (13 x86 / 3 x64 tests). |
| Where am I going? | Compact full-resolution buffers, native D3D12 presentation, PBR/light inputs and stronger variance-guided filtering; FidelityFX and external-title qualification remain pending. |
| What's the goal? | An AMD-focused legacy-game remastering runtime. |
| What have I learned? | COM return paths require resource/swap-chain wrapping; harness images match the system runtime on RX 9070 XT. |
| What have I done? | D3D9 capture/replay and offline mods; standalone AMD DXR, progressive diffuse GI, persistent scenes, camera controls and GPU/window regression tests. |
# 2026-09-04 RR coordinate-scale sprint

- Recovered the completed eight-frame history phase and started the next bounded hypothesis at fixed 128x96.
- Audited the pinned RR 1.2 header, current HLSL record semantics, native packing/dispatch code and recorded-worker admission. Established the coherent row-vector world-unit transform and explicitly excluded inconsistent depth-only/hit-only changes from the primary experiment.
- Planned three fixed recorded-only presets with exact output/report provenance and a historical unconfigured compatibility control. No renderer, recording, SDK/provider, driver or game state changed during the audit.
- Initial build command named a nonexistent build preset; switched to the existing `build/rr-sdk-probe --config Release` tree and built successfully. The first live unit-tenth run exposed an overly strict exact JSON-float comparison for depth bounds; retained the exact matrix/texture hashes and changed only the human-readable bound check to finite relative tolerance. A first contract-test mutation accidentally wrote the correct unit-one bounds and was therefore accepted; corrected the test mutation to genuinely different values. These were harness/admission issues, not GPU failures.
- The first low-sample quality-path contract used the fixture's nonzero default sun radius, which the existing analytic reference correctly rejects. Added the already supported zero-radius capture option; no reference condition or gate changed.
- First Release 24-candidate/four-control grid (`rr-coordinate-scales-m7b3p4tu`, 652.08 s) completed with all references, but its clamp audit found zero unit-tenth clamps versus 743,788 each for unit-one/unit-ten. Root cause: the initial transform scaled the exact 100000 no-secondary-hit sentinel to finite 10000. Marked the grid superseded, changed native/managed packing to preserve no-hit as FP16 max while scaling only real hit distances, and retained the invalid grid for diagnostic provenance rather than deleting it.
- Corrected Release grid `rr-coordinate-scales-nxw61kp4` completed in 653.31 s with identical 743,788 aggregate no-hit clamps for each scale. All 24 raw SDK reports still fail; every candidate fails spatial, disocclusion and fallback gates; all reference-confidence diagnostics pass; all 12 default-filter candidates pass temporal non-regression and all 12 zero-bias candidates fail it. The corrected unit-tenth outputs changed 92k+ preserved alpha rows in sampled bundles but zero RGB rows versus the superseded grid, so the measured RGB summaries remain exactly equal. Initial replay-script launch lacked the tools path and failed before execution; added the same bounded local import setup used by other standalone contracts.
- Final acceptance passes: fresh optimized Debug replay reproduces all 28 corrected bundles byte-for-byte in 235.30 s (`rr-coordinate-scale-replay-12k1gj8z`); affected Release tests pass 5/5 in 472.39 s; new Debug scale tests pass 2/2 in 53.86 s. Release/Debug native builds and Python compilation pass. Added `docs/RR_COORDINATE_SCALE.md` and linked the result from the roadmap-facing documentation. No renderer/default/SDK/provider/driver/game change and no scale/filter promotion.
- Final documentation audit resolves 95/95 local Markdown links. A PowerShell inventory command misbound a filename array to `Get-ChildItem -Filter`; replaced it with `Get-Item`. The remembered planning-helper filename did not exist in the installed skill; used its actual `check-complete.ps1`, which reports 0/0 because the long-lived plan's checklist format is unsupported. Manual current-sprint completion is explicit above. No runtime process remains.

# 2026-09-04 RR resolution sprint

- Audited extent dependencies after closing coordinate scale. Confirmed that a native-resolution experiment requires a versioned end-to-end contract migration; HLSL/renderer dispatch are already dynamic, while RR files, worker resources and offline analysis are fixed at 128x96.
- A read-only `rg` pattern beginning with `--width` was interpreted as an option; the preceding complete hardcoded-extent search supplied the needed audit, and future option-like patterns will use the explicit `--` delimiter. No files or processes were affected.

# 2026-09-04 RR guide-conditioning sprint

- Audited the pinned descriptor, official AMD technique guide/sample controls and live context defaults. Selected five coherent candidates while excluding undocumented normal-space conversion, roughness/albedo fabrication, radiance rescaling and stability changes.
- Added native/managed material-class packing, normal-strength and maximum-radiance settings, `RRTRRD06` guide provenance, exact packed hashes, report/output admission, shared-reference comparison support and focused malformed-provenance contracts. Historical unconfigured recording/output paths remain unchanged.
- Release measurement `rr-guide-conditioning-_b5h9mz1` completes in 311.88 seconds with two moving recordings, ten outputs and two shared references. Material classes and half normal strength show only small mixed spatial/temporal changes; maximum radiance 1 is metric-exact with baseline because all fixture inputs are below 0.085. Every candidate retains the spatial/disocclusion/fallback/fallback-confidence/raw-SDK failures, so none is promoted.
- Fresh Debug replay `rr-guide-replay-44352k11` reproduces both recordings and all ten outputs byte-for-byte. Affected Release regressions pass 7/7; focused Debug settings/guide contracts pass 2/2. Added `docs/RR_GUIDE_CONDITIONING.md` and linked it from the README.
- Final Python compilation and all 97 local Markdown links pass. A read-only `rg` call used a Windows-incompatible `docs/RR_*.md` path and returned an error; reran it with `-g "RR_*.md"` successfully. The planning helper reports 0/0 because this long-lived plan's checklist headings are unsupported; the three current sprint items were reviewed manually and are complete.

# 2026-09-04 RR exact-zero floor sprint

- Started from the retained strict zero-light failure after closing guide conditioning. Scope freezes resolution, SDK/provider and game-facing behavior, forbids bias compensation, and requires exact background/output-alpha preservation.
- Initial helper inspection named nonexistent `tools/rr_record.py`; recording decoding/orchestration lives in `tools/rr_recorded_dispatch.py` and existing tests. Logged the read-only error and changed the audit path rather than repeating it.
- Audited retained `rr-settings-dmg4o19c` black evidence. All twelve unconfigured/configured presets retain essentially the same `~1.18e-10` MSE and `~1.09e-5` maximum; no scalar setting clears the floor. The new measurement can therefore focus on input localization and longer history rather than duplicating the expensive settings grid.
- Added `tools/rr_black_floor.py`, which captures eight exact-zero frames, runs a persistent history, dispatches four checksum-bound reset controls, verifies output alpha/background and records active/inactive distributions without compensation.
- Release full-coverage and partial-geometry runs pass. The partial fixture proves the floor is present in every active RGB value and absent from every inactive value across all eight frames; zero albedo/distance do not remove it. Retained artifacts: `rr-black-floor-hu1tbcz0`, `rr-black-floor-nhwwvjen`, and decisive mixed-coverage `rr-black-floor-2hx9k0b7`.
- Checked the pinned local package and AMD's public repository/docs for an inspectable RR shader clamp. Only the API/docs and signed provider boundary are available for this path, so no internal epsilon cause will be asserted from source.
- First cross-build replay compared against a Release artifact created before `rgb_matches_active` was added to the manifest and failed at that missing summary key after all ten byte-file comparisons had already passed. The evidence bytes were valid; regenerate the Release manifest with the finalized analyzer, then replay against that exact schema.
- Final Release baseline `rr-black-floor-v_0xe0sn` uses the completed manifest. Fresh Debug replay `rr-black-floor-vtkbudp8` matches all ten binary artifacts and all stable statistics/hashes exactly. Release adjacent contracts pass 4/4 in 105.55 seconds; focused Debug contract passes in 13.98 seconds.
- Added `docs/RR_ZERO_FLOOR.md`, linked it from the README and closed the phase without altering the strict oracle or compensating output.
- Final Python compilation and CTest discovery pass; 98/98 local Markdown links resolve. The three current checklist items were reviewed complete.

# 2026-09-04 FidelityFX Radiance Cache foundation sprint

- Pivoted from the diagnosed RR provider floor to the Radiance Cache foundation. Planned a separate optional D3D12 context/support boundary first; no cache dispatch, renderer replacement, ROCm runtime substitution or game integration is included in this slice.
- Audited the local SDK and official 2.3 API/technique documentation. The current dependency is RR-only and lacks the cache header/provider; official Radiance Cache 0.9.0 requires its separate DX12 provider and CS 6.6 on RX 9000-series hardware. Acquisition of the official component is now the first gate.
- A read-only check guessed a root `LICENSE.txt`, but the retained subset keeps the notice under its original SDK documentation path. The same command confirmed Git 2.55 and Git LFS 3.7 are available, so use an official sparse checkout instead of ad-hoc binary downloads.
- Verified official tag `v2.3.0` resolves to the existing pinned commit, then completed a sparse official Git/LFS checkout containing the cache API/provider and notices in a separate build dependency directory. No source tree, renderer output or game directory was modified by acquisition.
- Verified real LFS object sizes, exact SHA-256 values and valid AMD signatures. Read the complete pinned 0.9.0 header; context creation needs only bounded sample capacities, while inference/training buffers belong to the next dispatch phase.
- Audited the RR probe/context implementation for reusable mechanisms. Chose a separate cache probe and managed policy; only generic D3D12 loading/isolation/allocation patterns carry over. No cache-specific preflight memory query exists in the pinned header, so the initial boundary must use a hard callback ceiling and measured lifecycle accounting.
- Added only AMD's NRC sample source to the sparse checkout and audited its context sequence. Selected initial capacities of 12,288 inference and 512 training samples, explicit enumerated provider override, WMMA-first attempt and separately reported fallback eligibility.
- A read-only `rg` command again placed a Windows wildcard in a directory argument and failed before reading files. Use the directory plus `-g "ffx_api*.h"` for the return-code/type lookup; no files were affected.
- Implemented a separate `rrt_rc_probe` and `rc-isolation-1` job boundary with fixed 12,288/512 capacities, enumerated provider override, WMMA-first/reference fallback policy, 256 MiB callback ceiling, allocation failure injection, D3D12 debug validation and zero dispatches. Added the independent `RRT_FSR_RC_SDK` CMake option; Release compiles successfully without changing `rrt_rr_probe`.
- Live support query succeeds and enumerates Radiance Cache 0.9.0. The first isolated context attempt reached the provider (`Hello, NRC Create Context!`) but exceeded the initial 30-second worker deadline and was killed/reaped by its job with no output overflow. AMD's sample explicitly warns initialization may take a while; retry once at the existing maximum 60-second bound rather than weakening process containment.
- The 60-second retry completes: WMMA context create/destroy succeeds, peak callback memory is 20,643,840 bytes, and 11/11 allocations release cleanly. Post-context provider metadata query returns code 4/ID 0, so native result remains `validation-failed`; implement a cache-specific managed admission that preserves this raw failure.
- Added `tools/rc_worker.py` with strict JSON, exact DLL hashes and cache-specific admission. A warm managed run passes under 32 MiB with the sole metadata workaround; raw acceptance stays failed and no rendering/dispatch is claimed.
- Exercised low-budget and injected-allocation failure in parallel isolated workers. Both provider processes access-violate (`0xc0000005`) instead of returning a memory error; jobs reap them and managed reports fail closed. Preserve hard allocation bounds and test fresh-process recovery rather than attempting unsafe in-process cleanup.
- Added native/managed support and worker contracts to CTest. Release and Debug each pass 2/2; both include crash containment and fresh recovery. Python compilation and both native builds pass.
- Audited the official NRC sample's exact CPU/HLSL structured-buffer layout and frame ordering. At 12,288/512 capacities the five API-visible buffers total 716,808 bytes; a separate 147,456-byte path-compositing buffer remains renderer-owned. The next slice is now specified as trace/enqueue, inference-before-training dispatch with counter clearing, then guarded composite/readback—not game integration.
- Standardized the native context diagnostic's default hard ceiling to the managed boundary's measured 32 MiB while retaining the explicit 1–256 MiB test range. Added `docs/RADIANCE_CACHE.md`, linked it from the README and closed all three foundation milestones without claiming a cache dispatch or rendered output.
- Final verification first guessed a nonexistent planning helper `scripts/check_plan.py`; the skill actually provides `scripts/check-complete.ps1`. Python compilation had already succeeded earlier in that command. Logged the read-only lookup error and switched to the provided PowerShell helper.
- Final rebuild after the 32 MiB default change passes for both Release and Debug. The focused Radiance Cache CTests pass 2/2 in each configuration (2.86 s / 2.87 s), Python compilation passes and all 99 local Markdown links resolve. The planning helper still reports 0/0 because this long-lived plan uses checklist milestones rather than its recognized phase format; the three current items are manually checked and complete.

# 2026-09-04 FidelityFX Radiance Cache synthetic dispatch sprint

- Opened a new isolated dispatch phase with fixed capacities and exact 716,808-byte application buffer accounting. Context-only CLI/report semantics remain separate; games, live renderer wiring and default GI are excluded.
- Added `src/dxr/rc_dispatch.h` with the pinned 44/12-byte layouts, deterministic normalized prediction/training fixtures, five exact default-heap resources, matching upload/readback staging, reset/inference/optional-training/counter-clear dispatch, fence wait, complete readback, input/target immutability checks, output finiteness/nonnegativity/sentinel replacement and provider allocation lifecycle reporting.
- Extended `rrt_rc_probe` with mutually exclusive direct/isolated dispatch modes and explicit `inference|combined` selection. Dispatch still preserves raw provider metadata failure independently of its mechanical execution result; allocation failure injection and multiple cycles remain context-only until separately designed.
- First Release compile failed because one C++ `auto` declarator list attempted to copy both input-vector and output-vector types. Split the three immutable fixture copies into separate declarations; no runtime evidence existed yet and the fix does not alter layout or data.
- First isolated Release inference and combined dispatches both pass mechanically with D3D12 debug enabled. Each clears both counters, overwrites all 36,864 prediction values with finite nonnegative output, preserves inputs/targets, keeps the device valid and releases the exact context allocation set. Their output hashes are byte-identical, consistent with training occurring after inference.
- Added `tools/rc_dispatch_worker.py` as a distinct hash-pinned managed admission path and `tests/verify_rc_dispatch.py` as a separate CTest. It validates both modes, a fresh repeat, malformed/mutated reports, explicit metadata-workaround policy, low-budget provider-crash containment and fresh recovery. Python compilation, configure/build and the Release dispatch contract pass; the focused test takes 2.17 seconds.
- Debug rebuild passes. All Radiance Cache contracts pass 3/3 in Debug (5.19 s) and Release (5.09 s), preserving the original support/context regressions alongside the new dispatch path. The dispatch hash is exact across modes, repeats and configurations.
- Added `docs/RADIANCE_CACHE_DISPATCH.md`, linked it from the foundation document and README, and closed the synthetic dispatch milestones. The documented next boundary is same-context post-training inference plus reset recovery; renderer path replacement waits behind that evidence.
- Final source audit caught that the intended FNV-1a64 label used an offset basis missing its final decimal digit. Corrected the implementation to the standard 64-bit offset basis before final evidence; rebuild and repin the resulting deterministic hash rather than preserving a mislabeled diagnostic.
- Repinned the corrected standard FNV-1a64 output to `8439070038676242095`. Final Python compilation and Debug rebuild pass; all three RC contracts pass again in Release (5.28 s) and Debug (5.19 s), including cross-mode/repeat exactness and crash recovery.
- Final documentation validation resolves 101/101 local Markdown links with no unchecked plan milestone. The planning helper continues to report 0/0 because the long-lived file uses checklist sprints rather than its recognized phase headings; the current sprint was manually reviewed complete.

# 2026-09-04 FidelityFX Radiance Cache persistent training sprint

- Opened a same-context sequence phase using the completed deterministic fixture and default learning parameters. The fixed order is reset/infer, 1–8 train-only batches, infer without reset and reset/infer, with per-step counter upload/clear, complete readback and fence.
- Added `src/dxr/rc_sequence.h` with persistent context/buffer reuse, fresh fenced command submissions, per-step output/target error summaries, baseline/post/reset pairwise deltas and strict reset/resource lifecycle gates. Before compiling, caught and split a repeated mixed-type `auto` declarator pattern already diagnosed in the prior phase; no failed build or runtime action occurred.
- The first broad CLI patch missed the exact final JSON lines and applied nothing. Re-read the bounded parser/output region and split the change into smaller verified patches; no partial source mutation occurred from the failed patch.
- Release builds and the first isolated one-batch sequence completes all four dispatches. Training changes all later inference values, slightly lowers analytic-target MSE and reset restores the exact baseline. The train-only row exposed non-standard `inf/-inf` JSON for its intentionally untouched NaN output; normalized empty statistics to zero before managed parsing/tests.
- Added `tools/rc_sequence_worker.py` with exact hashes, per-step/counter/error admission and the sole existing metadata workaround. Added `tests/verify_rc_sequence.py` for fresh exact repetition, CLI bounds, row/step mutation and non-finite rejection, low-budget provider-crash containment and recovery. Python compilation, CMake regeneration/build and the focused Release sequence contract pass in 1.84 seconds.
- Debug rebuild and adjacent regression pass: all four RC contracts complete 4/4 in Release (6.73 s) and Debug (7.04 s). Added `docs/RADIANCE_CACHE_TRAINING.md`, linked it from the dispatch guide and README, and closed the persistent training milestones without expanding beyond one batch or claiming renderer quality.
- Final CLI audit separated option presence from default values so `--training-batches 1` cannot leak into single-dispatch mode and `--dispatch-mode` cannot leak into sequence mode. Added both rejection cases before the final rebuild/regression pass.
- Final Python compilation and both native rebuilds pass. All four RC contracts pass 4/4 in Release (6.95 s) and Debug (7.20 s). Documentation validation resolves 103/103 local links and no unchecked milestone remains. The planning helper still reports 0/0 because of the long-lived checklist-sprint format; the current phase is manually complete.

# 2026-09-04 cross-process shared D3D12 resource sprint

- Opened a new disabled-by-default same-adapter shared-resource phase. The first milestone is an independent buffer/fence integrity contract inside the existing suspended-child job and explicit handle allowlist; renderer/provider buffers remain unchanged until it passes.
- Added `rrt_rc_shared` and its strict Python contract. The Release round trip opens two shared default-heap buffers and one shared fence in the job-contained same-adapter child, copies 1,573,120 deterministic bytes entirely on GPU between handoffs, and validates exact parent readback/hash, adapter LUID, fence sequence, allowlisted handle count and child reaping. Direct invalid adapter/handle use fails closed.
- Debug builds successfully and the complete RC suite passes 7/7 in Release (21.58 s) and 7/7 in Debug (21.77 s). Added the shared-resource guide; the first milestone is complete while provider/cache-specific shared buffers remain deliberately pending.
- Python compilation passes and all 110 local Markdown links resolve. The planning helper reports 0/0 because of the established checklist-sprint format; manual review shows milestone 1 complete and milestones 2–3 intentionally open.

# 2026-09-04 isolated live Radiance Cache scheduling sprint

- Opened a disabled-by-default synthetic live-transaction phase. Architecture keeps the crash-prone preview provider in the existing job-contained process and selects bounded inherited-pipe transport before considering shared GPU resources or in-process linkage.
- Added `rrt_dxr --rc-stream`, which emits only the exact self-checksummed `RCRPATH1` bytes to binary stdout and rejects every file output, recording, presentation and incompatible render option. The stream is byte-identical to the existing file export and the Release renderer contract passes.
- Added the first bounded stdin-pipe supervisor and fixture comparison. Its initial end-to-end test reached the new transport but the isolation host returned a non-admitted status; expanded the local error with bounded exit/stdout/stderr diagnostics before changing transport logic.
- Diagnosis showed Windows anonymous-pipe EOF as `ERROR_BROKEN_PIPE`, not a successful zero-byte read. Accept that exact EOF result while continuing to reject any extra payload byte; no size/checksum guard was relaxed.
- The first two-batch measurement command referenced an expired/incorrect temporary fixture directory and the renderer rejected the missing scene before producing bytes. Locate the current test fixture explicitly, then rerun the same read-only measurement; no implementation change is indicated.
- Native two-batch evidence is deterministic and stronger (`post hash 13270289865275143940`, target MSE `0.00123874`, composite MSE `7.67191e-5`, exact reset). The first managed two-batch admission returned `unavailable`; inspect the bounded report rather than weakening the test expectation.
- The two-batch report was valid; managed admission still required exactly four dispatches from the one-batch contract. Generalized that invariant to `training_batches + 3` while keeping the supported live bound at one or two batches and preserving every per-step hash/order guard.
- Added dynamic camera-fixture admission bound to the exact artifact digest and populated counts. A changed camera runs in a fresh contained child, improves its target/composite metrics and resets exactly. Added low-budget crash, 1 ms timeout and exact recovery assertions with explicit no-cache authority.
- Complete final RC regression passes 6/6 in Release (18.43 s) and 6/6 in Debug (18.98 s). A representative warm two-frame live run measured ~350 ms renderer/export, ~538 ms provider and ~998 ms total. Added the live scheduling guide and closed all three sprint milestones without applying the cache candidate.
- Final Python compilation passes and all 109 local Markdown links resolve. The planning helper still reports 0/0 because this long-lived plan uses checklist sprint headings; the three current live-scheduling milestones were manually reviewed complete.

# 2026-09-04 renderer-exported Radiance Cache path bridge sprint

- Opened a new independent `RCRPATH1` bridge rather than broadening RR formats. Audit selected secondary-surface cache queries, legacy-diffuse exact albedo factorization, renderer-owned throughput/no-cache output and actual-valid counters; PBR/emissive targets remain rejected rather than guessed.
- Added the first cache path preparation shader and build/deployment wiring. Its initial DXC compile failed because one `direct` call accidentally supplied an unused view-direction fourth argument; corrected it to the renderer's exact three-argument lighting helper before any runtime execution.
- Added the host-side `RCRPATH1` exporter plus CLI/report plumbing and built `rrt_dxr` Release successfully with the cache path compute shader deployed beside the executable.
- The first strict fixture test rejected every true background row because the inspector's zero-range accidentally included the intentional distance sentinel at float 27. Narrowed the zero check to floats 0–26 while still requiring float 27 to equal `-1`; the renderer artifact was not changed.
- The live Release export contract now passes. It independently decodes 172 actual secondary hits, verifies all source factorization/provenance, proves exact repeatability, proves ordinary pixels/signals remain byte-identical, and exercises no-overwrite plus malformed/unsupported-option rejection.
- Added the path-export design/evidence guide and linked it from the README and persistent-training guide. Release `dxr_render`, `rr_inputs`, and `rc_paths_export` pass; Debug rebuild, Python compilation and `rc_paths_export` pass. A final lookup again guessed a repository `scripts` directory that does not exist; the read-only search changed nothing, and the actual planning-skill helper still reports 0/0 because this long-lived plan uses checklist sprints.
- The first isolated renderer-fixture sequence reached the signed provider and returned code 0, but the preview WMMA backend overwrote all 12,288 fixed-capacity prediction outputs despite an occupancy counter of 172; the initial guard expected only 172 writes and correctly stopped after baseline. Retain complete-output finiteness/nonnegativity validation, but limit target/composite metrics and pixel mapping to the 172 admitted records.
- Updated the full-output guard accordingly and completed the four-step renderer-fed sequence. Native and managed admission pass mechanically: training changes all 516 mapped RGB predictions, improves both target and guarded composite MSE, and reset is byte-exact. The hash-pinned provider metadata workaround remains the sole raw SDK exception.
- Added the independent end-to-end `rc_path_sequence_contract`, including fresh exact repetition, artifact/count/composite report mutation, corruption, relative-path and wrong-mode rejection. The original analytic sequence remains unchanged and passes beside it. Release and Debug builds plus the four initially selected provider contracts pass; final verification expands to all six `rc_` tests.
- Final complete RC regression passes 6/6 in Release (9.45 s) and 6/6 in Debug (9.71 s): context, managed worker/crash containment, synthetic dispatch, analytic persistent sequence, renderer-fed sequence and renderer export. Closed all three bridge milestones without enabling a live/default cache path.
## 2026-09-04 — provider-shaped shared transport contract

- Added an exact five-resource cache layout to `rrt_rc_shared`: 716,808 bytes across five shared default-heap UAV buffers plus one shared fence.
- The parent initializes all resources, the isolated child opens only six explicitly inherited handles, rewrites prediction/counter outputs, and the parent verifies immutable inputs and exact output hashes after fence values 10/11/12.
- Extended `verify_rc_shared.py` with two exact layout runs plus invalid child-handle rejection. Release `rc_shared_transport_contract` passes in 2.00 seconds.
- Added explicit `rrt_rc_probe --shared-dispatch`: the parent owns upload/readback staging, while a job-contained same-adapter child opens the five shared resources and shared fence and executes the signed Radiance Cache provider.
- First Release run passed with output hash `8439070038676242095`, 36,864 finite values, exact immutable inputs, cleared counters, fence values 20/21/22, six allowlisted handles and zero CPU interprocess payload bytes.
- The strict shared contract now covers exact repeatability and invalid-handle rejection for both the mechanical layout child and the signed provider child. All seven `rc_*` tests pass: Release 16.05 s, Debug 17.05 s.
- Updated the shared-resource guide, README and current plan with the five-buffer/provider evidence and the still-open renderer-path/persistent-training boundary. Python compilation passes and all 110 project-local Markdown links resolve.
## 2026-09-04 — persistent renderer-path shared resources

- Added `rrt_rc_probe --shared-path-sequence ABSOLUTE_RCRPATH1 --training-batches 1|2`. The parent strictly decodes the renderer artifact and populates the five fixed shared buffers; one contained provider child keeps its context across baseline/reset inference, training, post-training inference and reset recovery.
- One batch reproduces baseline/post/reset hashes `4380958906282038366 / 17423046786485749504 / 4380958906282038366`; two batches reproduce post hash `13270289865275143940`. All 516 populated RGB values change after training and reset recovery is byte-exact.
- Extended shared and renderer-path tests with exact repeatability, both batch counts, corrupt artifact rejection and direct invalid-handle rejection. Focused Release tests pass 2/2 in 10.69 seconds.
- Focused Debug tests pass 2/2 in 11.13 seconds. Full adjacent suites pass 7/7 in Release (19.92 s) and Debug (20.43 s).
- Added exact no-file `--shared-stream-sequence`, configurable provider allocation budget and worker deadline. One MiB failure and one-millisecond timeout are contained; a subsequent shared run recovers byte-exactly. Post-change focused tests pass Release 2/2 (14.03 s) and Debug 2/2 (14.59 s); full suites pass Release 7/7 (23.51 s) and Debug 7/7 (24.75 s).
- Updated the plan/README/shared guide with the precise remaining renderer-GPU boundary. Final Release rebuild and Python compilation pass; all 110 project-local Markdown links resolve. The planning helper reports 0/0 because the long-lived plan uses checklist sprints; manual review keeps shared milestone 2 open for renderer-owned GPU compaction/direct handle launch.
## 2026-09-05 — renderer-owned GPU compaction and direct provider launch

- Added `compactRcPaths`, a deterministic single-thread GPU pass that converts ascending valid renderer rows directly into the exact five provider layouts and GPU-written counters.
- Added explicit `rrt_dxr --rc-shared-probe ... --rc-sdk-bin ...`. The renderer creates five shared UAV buffers and one shared fence, launches the external probe through the existing pre-resume job/handle allowlist, and performs no renderer path readback or provider IPC payload transfer.
- Canonical GPU-direct hashes are baseline/reset `566204800999108543`, one-batch post `6891511169378437159`, and two-batch post `12625136704411306072`; 172 counts are discovered from the GPU counter. Low budget and one-millisecond timeout return authoritative no-cache fallback, fresh recovery is exact, and camera identity changes while reset remains exact.
- Focused Release renderer-path contract passes in 13.37 seconds.
- Full RC suites pass 7/7 in Release (27.18 s) and Debug (30.33 s). Added the renderer-owned 49,152-byte ascending valid-pixel map without another shared handle; post-change focused Release passes in 15.37 s. Shared milestone 2 is complete, while composite quality/performance milestone 3 remains open.
- Post-mapping focused Debug passes in 16.09 s. The valid Visual Studio x86 Release renderer also rebuilds successfully with the new shader deployed; direct execution remains explicitly rejected outside x64. A stale `build/x86` Ninja/Win32 generator mismatch was logged and bypassed using `build/x86-vs`.
- Final Python compilation and all 110 project-local Markdown links pass. The planning helper reports 0/0 because the long-lived plan uses checklist sprints; manual review marks shared transport milestone 2 complete and leaves milestone 3 open for GPU composite metrics/performance.
## 2026-09-05 — guarded GPU-direct composite

- The provider now restores the trained prediction into the shared output after separately proving exact reset recovery. Existing file/stream parents validate the trained final buffer.
- Added a renderer compute composite using raw renderer terms, the shared trained predictions and the retained pixel mapping. It emits a diagnostic candidate/error surface; only that 196,608-byte surface is read back, while raw paths remain GPU-only.
- Canonical one-batch composite MSE is `7.68497e-5` with candidate SHA-256 `f46fd7afb78ece4edcfb6d70582073f6d545849a30bd8242eb7584462a81b3b8`. Two batches improve MSE to `7.61978e-5`, candidate SHA-256 `079c9ae7a4cd98a3e8cfb986e22d46a86cab868e58e8ea8da502584af58acd48`.
- Representative direct wall time is 0.33–0.35 s. Focused path contracts pass Release 13.42 s and Debug 13.62 s; final full RC suites pass 7/7 in Release 26.52 s and Debug 28.11 s.
- Final compatibility validation: Visual Studio Win32 Release rebuilds `rrt_dxr` and deploys the composite shader successfully; `verify_rc_path_sequence.py` and `verify_rc_shared.py` both pass Python byte-compilation.
- Documentation validation resolves all 110 project-local Markdown links across 36 files. The planning helper retains its known `0/0` result because this long-lived plan uses checklist sprints; manual review confirms all three cross-process shared D3D12 resource milestones are checked complete.

## 2026-09-05 — opt-in Radiance Cache presentation buffer

- Added `rrt_rc_apply.dxil` and explicit `--rc-present-candidate`. After provider/composite quality admission, the GPU pass uses the retained mapping to patch only admitted pixels into the common packed-BGRA renderer output.
- A GPU-written 49,152-byte application mask proves exactly 172 mapped pixels were applied; CPU validation proves all 12,116 unmapped pixels remain byte-identical. A pre-apply GPU backup restores authoritative no-cache output if post-dispatch validation fails.
- Canonical no-cache output SHA-256 is `f6dabb47da97f149b859a9645c10af922c097057995da7cac9a661136f46c641`; applied output is `719b289967ea103fb13d98ad5661c9c3e31f8b417d17de98deb3dbdf6a4c1659`. Default mode remains unapplied/no-cache, and opt-in low-budget/timeout failures remain no-cache.
- Updated Release `rc_path_sequence_contract` passes in 15.23 seconds after rebuilding its owning renderer tree. Python compilation passes.
- Added `--rc-presentation-test`: a hidden native window exists before the provider starts, the provider/composite transaction runs on a worker future while the main thread pumps Win32 messages, and GPU work remains single-owner. The admitted output is then submitted through a latency-one swapchain and verified by exact back-buffer readback.
- Manual native evidence: two provider-wait messages, 22 pump cycles over 340.153 ms, one-frame admission, one present, one exact validation and buffer mask 1. The expanded Release path contract passes in 16.41 seconds.
- Final validation passes 8/8 in Release (40.45 s) and 8/8 in Debug (41.08 s): all seven `rc_*` contracts plus `dxr_presentation`. The x64 Debug and Win32 Debug/Release renderers rebuild successfully with `rrt_rc_apply.dxil`; RC direct mode remains x64-only.
- Both modified Python contracts compile, and all 110 project-local Markdown links across 36 files resolve. The planning helper retains its known `0/0` checklist-format limitation; manual review marks all four presentation/scheduling milestones complete.

## 2026-09-05 — persistent stable-frame context amortization

- Added explicit `--rc-persistent-epochs 1|2`. Two epochs retain one contained child process, one FidelityFX provider context and the same five shared GPU resources for seven dispatches.
- Epoch two starts byte-exactly from epoch one's trained hash `6891511169378437159`, changes all 516 populated values again, and finishes at `12625136704411306072`; reset still returns exactly to `566204800999108543`.
- Final two-epoch composite MSE `7.61978e-5` and candidate SHA-256 `079c9ae7a4cd98a3e8cfb986e22d46a86cab868e58e8ea8da502584af58acd48` exactly match the established two-batch quality result. Representative wall time is 426.558 ms, safely below two measured independent launches.
- Default one-epoch protocol/hashes stay unchanged. Repeatability, low-budget no-cache failure recovery and invalid epoch counts are covered; focused Release `rc_path_sequence_contract` passes in 18.22 seconds.
- Cross-configuration builds pass. Final adjacent suites pass 8/8 in Release (42.10 s) and 8/8 in Debug (43.20 s), including all RC contracts and native presentation.
- Final Python compilation and all 110 project-local Markdown links pass. The planning helper retains its known `0/0` checklist-format limitation; manual review confirms all four stable-frame context-amortization milestones are complete.

## 2026-09-05 — live Radiance Cache fence session

- Added `RcIsolatedSession`, retaining suspended launch, explicit inherited-handle allowlist, pre-resume job assignment, kill-on-close, 64 KiB output cap, per-fence deadlines, premature-exit detection and final reaping.
- Added explicit `--rc-live-session-test`. One child/context handles initial training (`30→31`), stable continuation (`32→33`), then parent-regenerated +0.05-camera GPU inputs with provider reset (`34→35`). GPU command-list ownership remains serialized.
- The contract caught and fixed stale occupancy reuse: changed-frame count discovery now refreshes after fence 34. Initial frame has 172 queries; changed frame has 178. Stable hashes continue `6891511169378437159 → 12625136704411306072`; changed baseline/trained/reset are `9990495896441858603 / 587237281996004111 / 9990495896441858603`.
- Changed-frame candidate SHA-256 `31f8700b024782226c43284f4849cb0a5539a47a4eb45cd7e0aa5985adde7761` and MSE `7.68404e-5` exactly match a fresh moved-camera run. Low budget, one-millisecond fence timeout and fresh recovery pass; focused Release path contract passes in 24.23 seconds.
- Final builds pass for x64 Debug provider/renderer and Win32 Debug/Release renderer. Adjacent suites pass 8/8 in Release (51.44 s) and 8/8 in Debug (52.71 s).
- Final Python compilation and all 110 project-local Markdown links pass. The planning helper retains its known `0/0` checklist-format limitation; manual review confirms all four live fence-session milestones are complete.
