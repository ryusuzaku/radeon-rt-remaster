# Current implementation plan

## Texture-mip surface lock tracking (2026-09-11)

- [x] Confirm the recorded v18 failure chain and separate it from any implementation defect.
- [x] Add fixture alias-lock actions that isolate the alias proof from the fill proof.
- [x] Qualify v19 admission, rejection controls, the v18 regression and fail-closed option chains.
- [x] Run the focused texture suites in Release and Debug and document the contract.

v19 surface-lock tracking was already implemented and wired but had never been
exercised. Diagnosis: the v18 passes ran with `surfaceLocks` off, so every
mip-surface `LockRect`/`UnlockRect` invalidated the parent texture shadow instead
of being tracked — exactly the recorded `source_not_fully_dirty` /
`UnlockRect` diagnostics. Added `alias*` fixture actions and `texture_locks`,
which rewrites source mips with `D3DLOCK_NO_DIRTY_UPDATE` so only the alias lock
can supply the upload proof. `aliasfull` is admitted with `dirty_proof=top_lock`;
partial, lower-mip and read-only aliases, the DEFAULT destination alias, the
same case at v18 and three invalid option chains are all rejected. Release 7.61 s,
Debug 9.95 s; full `texture_*` group 7/7 Release 164.61 s and 7/7 Debug 217.80 s.
See docs/SURFACE_LOCK_QUALIFICATION.md. Remaining: real-game upstream admission,
the DEFAULT-pool `shadow_budget` ceiling and unsupported shader families.

## Compact texture coverage and precise upload checks (2026-09-08)

- [x] Verify last game closed and owned proxy absent.
- [x] Replace per-byte coverage mask with one flag per texel/DXT block.
- [x] Charge actual mask size within unchanged128MiB shared shadow budget.
- [x] Split dirty/epoch proof checks; preserve source lock flags/invalidation.
- [x] Qualify all native texture paths and regression checks.
- [x] Update handoff and launch next pass automatically.
- [x] Triggered once.0 captures: source_not_fully_dirty after source UnlockRect
  invalidation, with no direct Texture9 lock observed; residual shadow budget failures.
- [ ] Await closed/cleanup; qualify mip-surface lock tracking, then launch next pass.

All supported locks/copies cover complete mask units, including compressed tails.
Payload bytes/provenance remain unchanged. An initial PowerShell wildcard path
search failed; corrected to rg -g filters. Focused test initially expected zero source lock flags; the fixture deliberately
uses NO_DIRTY_UPDATE (32768). Corrected expected flags; focused test passes5.10s.
Added native64/96-texture pressure and release recovery controls, awaiting rebuild.

## Texture resource failure context (2026-09-08)

- [x] Verify previous game exit0, executable unchanged, proxy removed/absent.
- [x] Preserve rejected tracking admission step, last invalidation and upload check.
- [x] Add bounded read-only failing-slot descriptor/shadow diagnostic and validator.
- [x] Qualify native contexts and regressions.
- [x] Update handoff and launch next useful pass under standing authorization.
- [x] User-ready capture complete.0 materials; DXT5 DEFAULT sampler0 failures
  identify shadow-budget exhaustion and source_dirty_or_epoch upload failure.
- [ ] Wait for normal exit/cleanup, then address evidenced budget/proof limits.

No resource admission relaxed. Snapshot only on texture-input failure, no GPU
readback. Known byte counts refer to shadow masks, never assumed initialization.
Current focused test passes4.02s; adding untracked dynamic-resource fixture.

## Material-stage gameplay pass (2026-09-08)

- [x] Prepare fresh bundle/matching baseline and launch current proxy.
- [x] Triggered once;4096 attempts,0 captures.80 missing texture tracking and
  192 missing upload proof failures identified. Await normal game exit/cleanup.
- [ ] Verify game exit/cleanup, then implement/test next evidenced slice.
- [ ] Launch any needed subsequent pass automatically under standing authorization.

Bundle hl2-material-stages-v18-20260908; run material; runner session50934.
Still require user gameplay readiness before each trigger.

## Material rejection diagnostics (2026-09-08)

- [x] Verify normal game exit and proxy cleanup.
- [x] Add v18 failure-stage/detail evidence and separate unsupported-shader sampling.
- [x] Qualify named failures, stress budget, unchanged output and legacy evidence.
- [x] Update handoff and next gameplay gate.

Release3/3 passes106.13s plus focused selection4.26s; Debug2/2 passes9.42s.
Unsupported-VS stress initially hit fixture positive oracle; corrected to assert
rejection for that intentional negative fixture. No production failures remain.

Prior2560 pass:0 captures,168 generic evidence failures,1417 unsupported shaders.
No missing texture inference. Named pixel/material exceptions previously collapsed.
No gameplay launch in this slice. One PowerShell glob search failed; explicit files
already provided the needed source. Do not repeat that glob form.

## 2560x1440 material gameplay pass (2026-09-08)

- [x] Launch prepared bundle with full v18 and concurrent trace/inventory.
- [x] User-ready trigger complete.0 captures;168 generic missing-evidence failures
  on matching targets. Next stage-specific diagnostics and shader rejection budget.
- [ ] Verify normal exit and proxy cleanup; compare admitted material offline.
- [ ] Record outcome and next implementation work.

Runner session84987; bundle hl2-material-2560-v18-20260908; run material.

## Selection gameplay pass (2026-09-08)

- [x] Verify no active game/proxy, prepare fresh bundle and matching baseline.
- [x] Launch updated v18 diagnostics armed (runner session36239).
- [x] User-ready trigger complete; capture reached4096 attempts with83 sampled
  size rejections in868122 bytes. Observed2560x1440; next selection2560x1440:3.
- [x] Verified exit0, unchanged executable and removed/absent proxy.
  Fresh hl2-material-2560-v18-20260908 bundle prepared, NOT launched.
  Next run selection2560x1440:3 with full v18 flags.

Bundle build/game-passes/hl2-selection-v18-20260908; run selection.

## Selection diagnostics after HL2 v18 pass (2026-09-08)

- [x] Confirm normal exit0, executable unchanged and proxy removed/absent.
- [x] Record observed target descriptors on failed selection attempts.
- [x] Sample repeated v18 early selection rejections while retaining full write histories.
- [x] Add independent native selection tests and strict observation validation.
- [x] Finish regression checks and update gameplay gate/handoff.

Release capture/surface/workflow and final selection pass; Debug2/2 pass5.52s.
Stress4096 attempts =>67 records under1MiB; fixture rebuild required before
new stress test passed. No production test failures remain.

Policy: first4 per target/reason for at most64 keys, plus every64th global attempt.
Accepted draws and non-selection/native-failure rows remain unsampled. v18 header
explicitly advertises the optional policy; old v18 ledgers remain readable.
First focused test rejected the new header because the strict expected-header
shape lacked the optional policy. Fixed parser validation; focused test passes1.70s.
No new gameplay launch. Previous run lasted8698.844s, trace60 presents/9047 shader
draws/0 failed calls. Old actual target extent remains unknown.

## Targeted HL2 v18 material pass (2026-09-08)

- [x] Prepare fresh provenance-checked bundle and reuse matching successful baseline.
- [x] Armed launch and user-ready trigger complete (session30813).
  Capture finished byte_limit,0 admitted draws; target selection mismatched.
- [ ] Verify normal exit/cleanup, inspect ledger/assets and compare admitted material.
- [ ] Record outcome and select next implementation slice from evidence.

Use prior -steam -game hl2_complete arguments, target5120x1440:3 and full v18
flags. No settings changes. Native replay runs after game exit. Existing game
process/proxy absent at preflight. Planning skill catchup reported no pending data.

## Game-sized isolated material comparison (2026-09-08)

- [x] Preserve captured target extent and viewport with an explicit normalized mode.
- [x] Bound target memory and validate the native protocol independently.
- [x] Add fresh 5120x1440, offset-viewport, strict-compatibility and negative tests.
- [x] Finish Release/Debug checks and update handoff/gameplay instructions.

Release6/6 passed202.39s; Debug2/2 passed72.34s. Game-sized maximum error
2.79876e-8; offset2.11298e-8. Changed-texture and malformed-input controls pass.
Next targeted HL2 v18 material pass is useful; no launch/deployment in this slice.

8 million pixels maximum, dimensions <=8192. Float/no-MSAA diagnostic target,
normalized raster state, original samplers and material inputs. Frame equivalence
is not claimed. Saved v5 evidence confirms target [5120,1440,21,0] and viewport
[0,0,5120,1440,0,1], but has no captured material/texture bytes.
Initial large test exposed scene Digest's byte limit; diagnostic now hashes its
own bounded image without changing scene-file limits. An absent guessed color
fixture filename was resolved by repository search. No game launch/deployment.

## Partial UpdateSurface evidence v18 (2026-09-08)

- [x] Split upload qualification into independent CTest cases with fresh fixture input.
- [x] Track bounded SYSTEMMEM texture-mip rectangles copied to private DEFAULT texture mips.
- [x] Add v18 coverage/provenance validation, replay/runner support and native controls.
- [x] Run regressions and update the gameplay gate.

Only same-format, in-bounds, unscaled copies. Compressed partial rectangles are
block aligned; tiny mip copies must cover the whole destination. Complete mip
coverage is required before capture. Bounded transfer history replaces inferred
initialization; failed/unsupported copies invalidate the destination.

Focused surface test passed31.59s. Release14/14 passed166.82s; core capture41.09s,
surface28.92s. Builds and ten-file Python compile pass.32 accepted cases,51
native/proxy hash comparisons,32 replayed draws (6.93656e-8 maximum error),19
native negatives,48 malformed records and4 legacy cases. Debug8/8 passed201.57s
overall; each test remains within its bound (core capture48.83s, surface39.24s).
Two guessed scope/color filenames were absent; repository search located helpers
in intercept.cpp and replay restrictions in the Python comparator. No code/test failures.
Next game-sized material diagnostic scope, using saved5120x1440 evidence.

## Explicit whole-dirty evidence v17 (2026-09-08)

- [x] Add opt-in system-memory NO_DIRTY_UPDATE writes and full AddDirtyRect evidence.
- [x] Record/version dirty-proof provenance and expose runner/replay support.
- [x] Qualify changed bytes, missing/partial notifications, old-version gates and regressions.
- [x] Update handoff; UpdateSurface and partial-transfer tracking remain next.

Focused native suite passed (dirty-textures-wsmde_49). Release/Debug builds and
eight-file Python compile pass. Release10/10 passed134.06s (capture120.59s).
Debug4/4 passed164.23s (capture156.04s). No gameplay pass needed yet.
One test patch had an
out-of-order hunk; the atomic patch was reapplied without that unnecessary hunk.

## Whole-chain default-pool uploads v16 (2026-09-08)

- [x] Track initialized system-memory sources and proven full-dirty UpdateTexture transfers.
- [x] Add v16 default-pool transfer provenance, reader/replay/runner support.
- [x] Qualify native uploads, repeated full writes, partial/failed/unknown source rejection and legacy gates.
- [x] Run regressions and update handoff; defer gameplay until remaining update paths are assessed.

Only equal-format/equal-extent/equal-level usage-zero private 2D chains. Source
full-dirty proof starts at creation, is consumed by every observed UpdateTexture
attempt, and can be restored by a successful whole top-level write. No partial
dirty propagation, UpdateSurface or dynamic/default direct-write admission here.

Initial native suite failed at74.04s: this runtime faults on UpdateTexture with
a null destination. Replaced the negative fixture with a valid managed destination
(invalid pool for this API). Source proof must still be consumed after failure.
Two discovery commands used nonexistent/glob paths; corrected to generate_observers.py
and rg with -g '*.py'. Builds passed before native testing.

Focused suite passed after correction. Final Release10/10 passed117.42s
(position_capture103.75s);20 accepted cases,80 replayed draws (6.93656e-8 maximum
error),56 native/proxy image-hash comparisons,36 rejected scenarios,40 malformed
records and4 legacy runs. Release/Debug builds and eight-file Python compile pass.
Debug4/4 passed136.28s (position_capture127.97s). No HL2 process/deployment present
on final check. Next explicit dirty notifications and partial/UpdateSurface paths.

## Compressed capture v15 (2026-09-08)

- [x] Add opt-in v15 DXT1/DXT3/DXT5 block initialization tracking and external assets.
- [x] Extend reader, replay and runner with version-specific admission.
- [x] Qualify native full/partial writes, invalidation/recovery, captured bytes and replay.
- [x] Run regressions and update the gameplay gate and handoff.

Release/Debug builds, seven-file Python compile and initial position_capture
(65.02s) pass. Final Release10/10 (78.28s), Debug4/4 (90.85s) pass;
Debug position_capture82.40s. Next default-pool/update paths; no HL2 pass yet.
A search named nonexistent
tools/position_groups.py; resolved by rg --files to tools/replay_position_groups.py.

## Compressed native replay qualification (2026-09-08)

- [x] Restore DXT1/DXT3/DXT5 block rows in the isolated native replay diagnostic.
- [x] Qualify complete chains, small mips, alpha and malformed payload controls.
- [x] Run Release/Debug regressions and record the next capture implementation gate.

This prerequisite slice keeps v13/v14 capture admission unchanged. Compressed
write tracking and a new capture version follow after native restoration is proven.

Initial position_capture passed43.91s; Release10/10 passed58.29s. Twelve compressed
cases matched at maximum8.71039e-8; nine shader negative controls detected and18
malformed payloads rejected. Release/Debug fixture builds and Python compile pass.
Debug4/4 passed58.91s (position_capture50.49s). No implementation errors
encountered in this slice. Next compressed write tracking; no HL2 pass yet.

## External texture assets (2026-09-08)

- [x] Add opt-in v14 content-addressed mip storage with exclusive files and16MiB texture/256MiB session budgets.
- [x] Validate referenced assets and preserve importer/replay/runner compatibility.

- [x] Exercise larger native textures, deduplication, missing/corrupt assets and regressions; update gameplay gate.

Initial position_capture35.47s passed. Final Release10/10 (50.92s), Debug4/4
(57.01s), builds and Python compile pass. Larger restored shader error6.73376e-8.
Next compressed textures, then relevant default-pool/update paths; no new HL2 pass
needed yet. A final log patch had reversed hunk order and was reordered.

## Captured pixel-path reconstruction (2026-09-08)

- [x] Implement independently expressed five-sample lightmap/base-color/fog pixel shader and bounded native snapshot comparison.
- [x] Add v13 diagnostic replay tool and sampler/constant/texture negative controls.
- [x] Run Release/Debug comparisons and regressions; update handoff without launching HL2.

Single-draw material comparison only; no full composition or game-sized texture promotion.

Initial capture/comparison test35.05s; high-frequency controls35.00s. Builds pass.
Resolved compile namespace/DWORD typing errors and fixture teardown COM lifetime
crash; changing shader profile did not resolve that ownership bug. Resource
objects now release before Device unload. Release10/10 (49.33s), Debug4/4 (54.47s)
pass. Captured maximum error1.42296e-8; synthetic8.84655e-8; all eight negative
controls detected. Next bounded external texture assets. No HL2 pass needed yet.

## Initialized texture evidence (2026-09-08)

- [x] Track observed private managed 2D RGBA mip writes with bounds, partial initialization and conservative invalidation.
- [x] Add v13 texel capture, digest/shape validation, importer and runner plumbing.
- [x] Validate native transparency, partial/failed writes and alias/copy invalidation; run regressions and update handoff.

Initial admission: usage0, A8R8G8B8/X8R8G8B8, at most64KiB per texture.
Unsupported writes invalidate knowledge; no inferred copy or generated-mip contents.

Initial position_capture passed32.08s; Release/Debug builds pass. Full regression
runs include new runner and inherited hook assertions. One patch application
failed because hunks were in reverse source order; reordered before applying.

Complete: Release10/10 (45.13s), final affected Release5/5 (39.97s) after the
BaseTexture9 writer guard, Debug4/4 (47.87s), Python compile passes. Next paired
pixel-path reconstruction against captured mips, then larger bounded asset storage.
No additional HL2 gameplay pass needed yet.

## Paired material state (2026-09-08)

- [x] Add opt-in v12 exact paired PS constants, two sampler states and bound 2D descriptors/identities.
- [x] Preserve reader/importer/runner metadata and validate native state changes, invalidation and malformed records.
- [x] Run Release/Debug regressions and update handoff; no HL2 launch.

Texture contents remain unknown; texel/mip provenance follows this slice.

Complete: Release10/10 (55.79s), Debug4/4 (63.59s); both builds and Python compile
pass. No additional HL2 gameplay pass needed yet.

Initial position_capture passed40.00s. Full regression runs include additional
failed-write/refresh controls and inherited setter-guard assertions.
Implementation errors resolved: initial generator search used the wrong filename
(actual tools/generate_observers.py); initial Add File patch lacked '+' prefixes
and was reapplied with valid patch syntax before building.

## Pinned material vertex inputs (2026-09-08)

- [x] Add bounded initialized UV/color and c12/c16 capture plus exact CPU output evaluation, opt-in v11.
- [x] Verify native/CPU perspective interpolation, packed channel order and input/state failures; preserve importer and runner evidence.
- [x] Run Release/Debug regressions and update the next texture/material gate without launching HL2.

Complete: Release10/10 (39.52s), Debug4/4 (42.68s), Python compile passes.
Next paired PS constants and s0/s1 sampler/resource descriptors, then initialized
texture/mip provenance and texels. No HL2 gameplay pass needed yet.

## Real material audit and enhancement roadmap (2026-09-08)

- [x] Audit saved HL2 pixel programs paired with the pinned position VS and identify bounded implementation dependencies.
- [x] Save reproducible evidence and an exact next material implementation slice.
- [x] Plan texture upscaling, material authoring and related renderer/workbench dependencies; update handoff.

Reuse saved captures; no HL2 launch. Texture enhancement is future work, separate
from faithful source capture/replay and from screen-space upscaling.

Complete: same paired PS in231/294 original/multi-draw draws; required UV/color,
fog, PS constants and two sampler paths identified. CPU Release/Debug audit equality,
truncated-input rejection and Python compile pass. No native runtime changes.
Docs: HL2_MATERIAL_AUDIT.md and TEXTURE_ENHANCEMENT_ROADMAP.md. Next initialized
UV/color/fog output contract; no additional gameplay pass needed yet.

## Controlled color replay (current slice)

- [x] Add opt-in v10 exact constant-RGBA pixel program/effective constant and missing raster-state evidence.
- [x] Admit complete v9-qualified clear-to-draw prefixes with explicit supported state and replay captured clear/blending on native and CPU vertex paths.
- [x] Verify analytic blend/order/clear controls, rejected states and legacy compatibility in Release/Debug; update handoff.

Scope: 128x96 float color target, no depth/textures/MRT; no game material claims.
HL2 closed and proxy absent. Gameplay remains deferred during synthetic validation.

Complete: full Release10/10 (41.03s), Debug4/4 (42.56s); final setter-overlap guard
capture reruns passed Release26.99s/Debug33.26s. Both native builds and Python
compilation pass; no failures. HL2 closed/proxy absent. Contract:
docs/POSITION_COLOR_REPLAY.md. Next audit an actual HL2 pixel/material path from
saved inventory; no new gameplay pass needed for this synthetic pixel program.

## Closed standalone color-target scope (current slice)

- [x] Track native standalone target creation provenance and outstanding resource access with bounded, fail-closed accounting.
- [x] Add opt-in v9 scope evidence and strict qualification for private standalone RT0, no depth/MRT, closed access, retained clear and captured-only writes.
- [x] Verify positive/negative native controls and Release/Debug regressions; update handoff and gameplay gate.

This deliberately excludes texture subresources/aliases and shared or unknown
origins rather than claiming a general alias graph. Stateful replay remains a
separate qualification. HL2 closed and bin proxy absent at start.

Complete: Release10/10 (40.78s), Debug4/4 (41.68s), both native builds and Python
compilation pass. No failures. Positive narrow color-call scope qualification and
all native/reader exclusions pass with unchanged raster output. Final HL2 closed,
proxy absent. Contract docs/POSITION_SURFACE_SCOPE.md; next supported color replay
state/pixel shader contract, not another gameplay pass yet.

## Ordered surface-write evidence (current slice)

- [x] Audit writer hooks and define bounded ordered evidence with explicit scope/overflow/unobserved gaps.
- [x] Implement opt-in v8 producer, strict reader/import and conservative admission diagnostics.
- [x] Add synthetic success/failure/write/reset/binding/exhaustion controls; validate Release/Debug and update handoff.

No HL2 launch needed during this slice. Workspace has no Git metadata; preserve
existing files with targeted patches. Initial process/deployment check: HL2 closed,
bin/d3d9.dll absent. Planning session catchup produced no pending report.

Complete: full Release10/10 (30.31s), Debug4/4 (34.53s). Final native hardening
capture reruns passed Release19.87s/Debug24.65s. Fixed transient Windows report
polling PermissionError under the existing test deadline; final runner reruns
passed Release2.42s/Debug2.72s. Native builds/Python compilation pass, no outstanding
failures. HL2 closed/proxy absent; no game changes. Contract:
docs/POSITION_WRITE_EVIDENCE.md. Next closed single-target scope qualification
before any state-aware admission; no new gameplay pass needed yet.

## Clear-operation evidence and admission (current slice)

- [x] Capture bounded pre-call clear arguments/attachments/viewport, committing only successful calls; v7 opt-in retains latest observed clear or explicit unknown.
- [x] Validate clear identity/ranges and provide conservative initial-content admission reasons. Never infer known initial contents merely from a last-clear marker: intervening writes and incomplete capture must remain explicit.
- [x] Test native clear payloads, bounds/failures and legacy behavior; no game launch or automatic state-aware promotion.

Final Release10/10 pass32.01s; Debug4/4 pass27.17s. Native builds and Python
compilation pass. HL2 closed, bin proxy absent; no game launch/deployment.
Next bounded ordered surface-write evidence and gap markers before state-aware
replay. All initial-content assessments remain unknown pending that coverage.
See docs/POSITION_CLEAR_EVIDENCE.md.

## Target and composition-state evidence (current slice)

- [x] Add opt-in v6 surface lifetime IDs, clear/binding serials and selected effective depth/blend/raster states without altering native rendering.
- [x] Validate/preserve metadata and split diagnostic groups on evidence changes; do not apply incompletely captured state as game-faithful replay.
- [x] Test surface reuse/recreation, clear/binding boundaries and legacy capture compatibility before deployment. Clear serials are markers, not reconstructed clear operations.

Final Release10/10 pass30.15s; Debug4/4 pass26.36s. Both native builds and Python
compilation pass. Same-size target recreation, stable surface reuse, bound depth,
enabled ONE/ZERO blending, clear/binding changes and reader/runner controls pass.
No test failures; game not running, proxy absent. Next bounded clear-operation
payloads/initial-content validity, then state-aware replay. No new game capture
needed until that replay contract is ready. See docs/POSITION_COMPOSITION_EVIDENCE.md.

## Offline grouped position replay (current slice)

- [x] Group saved v3+ evidence by device/reset/interval, target, viewport and clip constants; preserve indexed-draw order and independent per-draw constants.
- [x] Add bounded native/CPU multi-draw diagnostic comparison with one clear per group (explicit depth-off overwrite policy, not reconstructed game rendering).
- [x] Test composition/order/input bounds and real four-interval evidence in Release/Debug; no game launch or live identity inference.

Complete: Release6/6 (15.88s), Debug3/3 (16.51s). Grouped Release/Debug reports
identical: four48-triangle groups,2593/2588/2555/2565 covered pixels, zero error.
Both fixture builds and Python compilation pass, proxy absent, no game launch.
Next capture actual target identity/clear boundaries and depth/blend state for
game-faithful grouping/composition. Current depth-off diagnostic is not original
game rendering or a live scene/lighting integration. No failures this slice.

## Multi-draw interval capture (current slice)

Final real v5 qualification complete: native exit0/124.297s, executable unchanged,
owned proxy removed/absence verified, runner98267 ended. Release/Debug replay:
12 visible matches with exact coverage/zero error;4 samples empty on both paths,
not counted as visible validation. Stable c0/model rows; clip rows agree within
each interval and differ across4 intervals. See docs/HL2_MULTIDRAW_RESULT.md.
Next build bounded multi-draw per-interval offline scene replay from saved evidence,
with explicit grouping/identity assumptions before further live integration.
No game running; pending-exit notes below are historical.

Real v5 triggered after user gameplay confirmation: capture_limit,16 accepted
from524 attempts. Four distinct position-content keys (3/35/4/6 triangles)
repeat across consecutive intervals207..210, four samples per interval, all
target5120x1440.192 submitted triangles, not192 unique triangles or16 objects.
Source SHA256dd0ef91fffbee117c325ffd4781a433c5f1743384a6a99bdd3655687262d2302.
Next await normal game exit, verify runner98267 cleanup and replay Release/Debug.
Do not replay while HL2 is running or alter its deployed proxy.

- [x] Add explicit v5 mode: at most4 accepted draws per interval,16 total, retaining selection and16MiB/4096-attempt/120-present limits.
- [x] Extend reader/import/replay bounds and verify same-interval quotas, rejection recovery and legacy compatibility.
- [x] Validate native builds before another guarded gameplay pass. Multiple draws are candidates, not guaranteed distinct objects; no hash-based suppression.

Final Release9/9 pass25.46s; Debug5/5 pass29.23s. Both builds/Python compilation
pass, saved v3/v4 reader imports preserved. No test failures. Prepared fresh
hl2-multidraw-20260907 using existing successful baseline and unchanged arguments.
Next guarded launch, await gameplay confirmation before trigger; replay after exit.

Launched and verified running: hl2-multidraw-20260907/runs/multidraw, PID35292,
runner session98267. Proxy SHA256da8e84c54203b0a250bd5a39ee4df68d815f37dbbe9992195fdbca18dd03ccdc.
Trigger and position ledger absent at verification. Await user "in game" before
triggering; do not rebuild/replace deployed DLL or stop runner. After capture,
ask normal exit, verify owned bin proxy cleanup and replay Release/Debug.

## Explicit target selection (current slice)

Final selected-pass qualification: native exit0 after723.656s, executable unchanged,
owned bin proxy removed/absence verified, runner72773 complete. Release and Debug
post-exit replay match all4 samples with exact coverage427 pixels each at128x96
and zero normalized error. This supersedes pending-exit notes below. Next broaden
bounded coverage beyond the first eligible draw (multiple candidates/interval or
explicit draw selection), preserving target policy and resource/timing evidence;
do not infer tracking from repeated identical position content. No game running.

Real selected pass triggered after user gameplay confirmation. v4 capture_limit,
225 attempts,4 accepted at ordinals35/98/161/224, consecutive intervals726..729,
target5120x1440. Each has18 triangles/40 unique indices; identical position content
across samples,54 positive-clip-W corners and0 degenerates per draw. Reconstructed
72 submitted triangles (not72 unique triangles). SHA256c3e1ee6e61abea13e8fc4ba4aed20ddc58af97198d5767f2970404770acfedaf.
Next await normal game exit, verify runner72773 cleanup, then Release/Debug GPU
replay. Do not run replay while HL2 is active. No visibility/object-tracking claim
until qualified; this is still repeated narrow geometry, not whole-scene coverage.

- [x] Add opt-in exact target dimensions/minimum triangle-count policy, recorded in v4 evidence; no inferred main-view classification.
- [x] Preserve v1/v2/v3 behavior; test selection, rejection, reader tampering, and runner propagation.
- [x] Qualify builds before preparing the next game pass. Use observed5120x1440 and minimum3 triangles to exclude prior two-triangle samples, without claiming visibility.

Release9/9 pass20.38s; Debug5/5 pass17.35s; both builds, Python compilation and
saved-v3 reader check pass. Prepared hl2-selected-20260907 with reused matching
native baseline and unchanged game arguments. Next launch selected v4 run, await
user gameplay confirmation, trigger, then replay only after normal game exit.

Selected run now launched: PID12352, runner session72773, status running.
Proxy SHA2561c5d2bdf8616dbd3ef3089a10fbcf120dd447eb9cd13af354c15462f0af0ee4a.
Bundle hl2-selected-20260907/run selected, policy5120x1440:3. Trigger/position
ledger absent on verification; await user "in game". Do not rebuild/replace the
deployed proxy or stop its runner; runner removes owned bin DLL after game exit.

Initial patch failed atomically on a partial-line context; corrected to explicit selection rejection returns.

## Frame-correlated position sampling (current slice)

Final real-game pass result: HL2 exited0 after177.563s; executable unchanged,
runner-owned bin/d3d9.dll removed and absence verified. Runner session94867 ended.
After exit, Release and Debug GPU replay both match all4 samples with exact
coverage (12288 diagnostic pixels each) and zero normalized position-output error.
Preserved initial while-game-running failure report; precise D3D failure cause
is not established. Next implementation is target/pass-aware selection, not
another identical earliest-draw capture. Historical in-progress notes below
are superseded by this final result.

- [x] Add opt-in v3 ledger session identity and device-local successful-Present intervals, with reset separation.
- [x] Sample at most one accepted draw per interval across four intervals; keep existing default v2 and byte/attempt limits.
- [x] Test native device/swap-chain presentation and reader/adapter propagation before any game deployment.

Release9/9 (15.83s), Debug5/5 (12.47s), final expanded Release sampling4.27s.
Native Release/Debug builds and Python compilation pass. In-scene Present negative
test returned success on this driver; removed that invalid test assumption, kept
S_OK-only guard and documented failure-path test limitation.

Fresh guarded HL2 pass launched: build/game-passes/hl2-frames-20260907, run frames,
PID41188, runner session94867. Proxy SHA256 ecac63e12f49f773f62a0993751edc38491c9b99af1e1c59637e1c313958f0aa.
User confirmed gameplay and trigger succeeded. Four accepted samples at consecutive
intervals1530..1533 all select the same two-triangle256x256-target geometry.
Offline validation/reconstruction passes; initial GPU replay failed with generic
D3D failure while HL2 was running. User asked to exit normally before retry.
Runner owns temporary bin/d3d9.dll and removes it on exit;
do not rebuild/replace the deployed DLL or terminate the runner during this pass.
Next: confirm native exit/cleanup, retry GPU replay to a new report filename,
then add explicit target/pass selection to avoid earliest-small-target bias.
Preserve initial reconstructed/gpu-release.json failure report. Trace has normal
frame_limit footer (222300 events); inventory completed at byte_limit with3104
draws and zero failed/unavailable queries. Do not infer object correspondence.

Discovery: PowerShell rg path globs were passed literally (error123); use directory arguments and -g filters. No files changed by those queries.

## Capture-to-scene adapter (current slice)

- [x] Load one bounded, validated ledger snapshot; preserve exact source digest and resource evidence.
- [x] Import only explicitly assigned draws into atomic position-scene deltas; report unassigned draws without guessing object identity.
- [x] Test real v1 input and native proxy v2 fixtures, including ambiguous assignments and rollback. No game launch needed for this slice.

Complete: Release7/7 (10.07s), Debug6/6 (8.83s), Python compilation passes.
Real v1 imports4 draws/57 triangles; native v2 reuse/recreation preserves evidence
without inferred merging. Next add coherent frame/session identifiers and bounded
multi-frame position sampling, then qualify correspondence before wiring these
scene deltas to renderer updates. A fresh game capture is useful only after that
producer change is built/tested; no launch requested yet. This slice is offline,
not live object tracking or relighting. No implementation/test failures.


## Cross-process shared D3D12 resource sprint

### Goal

Replace the live prototype's GPU readback/CPU pipe/provider upload with a crash-contained same-adapter shared-resource and shared-fence contract, then determine whether the renderer path buffers can safely cross that boundary without changing the authoritative fallback.

- [x] Establish a minimal native same-adapter shared committed-buffer/shared-fence round trip inside the existing job and handle allowlist, including exact payload integrity, adapter identity and child teardown.
- [x] Move the renderer path/query inputs and provider predictions through shared resources while retaining validated counts/mapping, persistent context, deadlines and no-cache fallback.
- [x] Measure static/camera/reset and crash/timeout behavior in Release/Debug, compare against the CPU-pipe baseline and document the remaining presented-composite/game boundary.

Scope: Windows D3D12 on the existing RX 9070 XT and the 128x96 synthetic scene only. The initial contract uses same-adapter `D3D12_HEAP_FLAG_SHARED` committed buffers and a `D3D12_FENCE_FLAG_SHARED` fence with narrowly inherited NT handles. It must not link the preview provider into `rrt_dxr`, enable the feature by default, share textures before buffer semantics pass, modify games/drivers or weaken job containment. Handle values, adapter LUID, resource descriptions, fence values, payload hashes and process teardown are evidence. Any sharing/open/wait/validation failure retains the current CPU/no-cache fallback.

Initial direction: add an independent native shared-transport contract before touching the renderer/provider data path. Parent uploads a deterministic bounded payload, signals shared fence value 1, a suspended/job-assigned child opens only the allowlisted resource/fence handles on the same adapter, copies input to shared output, signals value 2 and exits after completion; parent validates an exact readback. Only then replace the synthetic payload with cache buffers.

Current intermediate result: the generic round trip and exact five-buffer layout pass. File/stdin modes retain the CPU oracle, while explicit `rrt_dxr --rc-shared-probe` now generates raw paths, deterministically compacts/normalizes them into the five shared provider buffers, retains ascending pixel mapping on the renderer GPU, and launches the job-contained external provider worker directly. GPU counters discover 172 canonical queries; no renderer path readback or provider payload pipe occurs. One/two-batch training, camera identity, reset, budget failure, deadline termination and exact recovery pass while the no-cache frame remains authoritative. Milestone 3 remains open for quantitative GPU-direct quality/composite comparison and final Release/Debug/performance documentation.

Final result: the renderer now builds a guarded GPU candidate from the trained shared prediction buffer and retained pixel map, then reads back only the 196,608-byte diagnostic candidate/error surface. One batch yields composite MSE `7.68497e-5`; two batches improve it to `7.61978e-5`, with stable candidate SHA-256 identities and exact provider reset. Representative direct wall time is about 0.33–0.35 s versus roughly 1.0 s for the earlier two-frame CPU readback/pipe/upload prototype. Static repeat, camera identity, one/two-batch training, 1 MiB failure, 1 ms timeout and recovery pass in Release and Debug; all seven RC contracts pass. The candidate remains unapplied and the normal no-cache frame authoritative. Presented compositing, multi-frame game scheduling and D3D9 title integration are the next sprint, not silently enabled here.

## Isolated live Radiance Cache scheduling sprint

### Goal

Replace the offline path-file handoff with a renderer-driven, supervised frame transaction that preserves persistent cache state across bounded synthetic frames and returns a guarded candidate composite without enabling the default renderer path.

- [x] Audit the renderer/probe queue, process and resource ownership boundaries; choose the smallest crash-contained no-temporary-file transport and define reset/frame/provenance semantics.
- [x] Implement a bounded renderer-to-cache live transaction with persistent provider state, exact query mapping, counter/resource guards and explicit fallback to the unchanged no-cache frame.
- [x] Exercise repeated/static, reset/camera-change, provider failure/timeout and Release/Debug regressions; document measured quality/cost and the remaining D3D9/game integration boundary.

Scope: the existing 128x96 synthetic DXR scene, legacy diffuse materials and signed Radiance Cache 0.9.0 D3D12 provider only. The feature remains explicit and disabled by default. A provider crash must remain outside the renderer process and must yield the authoritative no-cache result; no installed game, proxy default, driver, SDK binary or ROCm runtime is modified. The first live transaction may use bounded CPU/shared-memory transport between supervised processes, but must not persist path data to disk or treat unvalidated/padded predictions as pixels. Provider context/buffers may persist only inside one job-contained worker and must reset on scene/settings/camera identity changes.

Initial direction: do not link the preview provider directly into `rrt_dxr`, because its demonstrated allocation-failure access violation would turn a recoverable optional effect into a renderer crash. First audit whether the existing job isolation can accept a length-prefixed `RCRPATH1` payload over inherited pipes while returning a fixed, digest-bound prediction/composite response. Keep renderer GPU work and no-cache output authoritative; the worker owns provider GPU resources and context. Only after this crash-contained scheduling contract passes should shared D3D12 resources or in-process integration be considered.

Final result: `rrt_dxr --rc-stream` and the supervised live worker transfer the exact 1,573,120-byte artifact through a bounded inherited pipe with zero persistent path bytes. One and two static training frames retain state on one provider context; two frames improve target MSE to `0.00123874` and guarded composite MSE to `7.67191e-5`, then reset restores baseline exactly. Camera identity produces a different digest and clean contained context. Truncation/oversize/corruption, 1 MiB provider crash, 1 ms timeout and report mutations fail closed to the unchanged no-cache authority; fresh recovery is exact. Six RC tests pass in Release and Debug. Representative warm two-frame wall time is about 1.0 s, dominated by process/readback/pipe/upload overhead. See `docs/RADIANCE_CACHE_LIVE.md`; shared D3D12 resources and actual presented compositing remain next.

## Renderer-exported Radiance Cache path bridge sprint

### Goal

Replace the analytic cache records with a versioned offline fixture derived from the existing DXR renderer's real synthetic-scene ray hits, radiance, materials and camera, then validate guarded cache compositing against the renderer's unchanged no-cache output.

- [x] Audit current DXR/RR exports, shader hit data, scene bounds, throughput and independent reference paths; define the smallest source-verifiable RC path ABI without reconstructing missing semantics by guesswork.
- [x] Add a bounded renderer export plus strict inspector/managed conversion for cache queries, training input/targets, validity and throughput/no-cache compositing state, preserving all historical renderer/RR outputs.
- [x] Feed the exported fixture through an isolated cache sequence and guarded offline composite, compare with the exact no-cache source/reference, run Release/Debug and adjacent regressions, and document remaining live-integration gaps.

Scope: the existing 128x96 deterministic DXR synthetic scene only, offline files and isolated D3D12 cache work. The source renderer remains authoritative for camera matrices, scene bounds, hit positions/normals/material parameters, subpath radiance targets, query validity, throughput weights and no-cache accumulated RGB. The bridge may export at most 12,288 query records and 512 deterministic training records, use the existing 44/12-byte cache layouts and retain the 32 MiB provider ceiling/job boundary. It does not hook D3D9, add live IPC, modify installed games/drivers, replace the default one-bounce renderer, claim commercial-game quality/performance or move the shipped provider runtime to ROCm. Missing data must be added at the renderer/shader boundary or explicitly rejected; it must not be inferred from unrelated RR outputs.

Initial direction: inspect whether the current RR capture already contains enough world/camera/material/radiance identity to extend compatibly. Prefer a new independent `RCRPATH1` artifact so cache-specific throughput/target semantics do not broaden RR admission. Every record must be tied to renderer source identity and scene bounds, counters must equal admitted valid records, inactive pixels must remain excluded from cache composite, and `composite = direct/background + throughput * prediction` must be checked without overwriting the source output. First establish a byte-exact export/inspection contract; only then schedule provider work.

Final result: the canonical renderer fixture exports 172 exact secondary-hit queries/training records and feeds them through the existing isolated four-step provider sequence. One batch changes all 516 mapped RGB predictions, improves target MSE `0.00125381` → `0.00124904` and guarded composite MSE `7.77365e-5` → `7.74054e-5`; reset restores baseline hash `4380958906282038366` exactly after trained hash `17423046786485749504`. Full-capacity provider writes are guarded while only mapped records affect the composite. Managed identity/mutation/corruption checks, Release/Debug provider contracts and adjacent renderer/RR exports pass. Raw SDK acceptance remains failed only for the known metadata defect; live rendering remains disabled. See `docs/RADIANCE_CACHE_PATHS.md`.

## FidelityFX Radiance Cache persistent training sprint

### Goal

Prove whether bounded online training changes a later inference on the same Radiance Cache context, and whether an explicit reset restores the deterministic pre-training output without leaks, stale counters or device errors.

- [x] Define a same-context reset/infer → train-only batches → infer-without-reset → reset/infer sequence with exact per-step counter/resource/output admission and bounded training count.
- [x] Implement a separate persistent-sequence native/managed mode that reuses the audited external buffers safely across fenced dispatches and reports byte/numeric deltas without relaxing the single-dispatch contract.
- [x] Run Release/Debug repeatability, reset recovery, malformed/failure containment and adjacent RC regressions; document whether useful learning is demonstrated and the remaining renderer-path boundary.

Scope: offline synthetic D3D12 work only with the pinned Radiance Cache 0.9.0 provider, RX 9070 XT, 12,288/512 capacities, exact 716,808-byte external interface, 32 MiB provider ceiling and existing job containment. Use the same deterministic queries and analytic training targets as the completed single-dispatch fixture. The sequence may execute at most eight 512-sample train-only batches between inference probes, with counters cleared and a fence/readback at every step. It does not add game capture, live IPC, compositor integration, default renderer changes, quality promotion, driver/game changes or ROCm runtime substitution. A changed post-training output proves retained state only; “useful learning” additionally requires movement toward the analytic targets under a declared error metric, and reset must recover the baseline within an evidence-derived exact/tolerance contract.

Initial direction: add an explicit `sequence` mode rather than broadening `inference|combined` admission. Reuse one context and one exact buffer set, but reset the command allocator/list only after its fence. Record baseline, each training return/counter state, post-training inference and reset inference separately. Start with one training batch; expand only up to eight if the output is unchanged and every safety invariant holds. Keep the known provider-metadata defect as the sole hash-pinned workaround and preserve raw SDK failure.

Final result: one default 512-sample training batch changes all 36,864 later prediction values on the same context (`FNV-1a64 8439070038676242095` → `11036946020368386469`; pairwise MSE `2.97242e-9`, max delta `7.62939e-5`) and improves analytic-target MSE from `0.0500247` to `0.0500075`. The following reset restores every baseline byte exactly. All four fenced steps return code 0, clear counters, preserve inputs/targets and keep the device healthy; context allocation accounting remains exact. Managed mutation/non-finite checks, low-budget crash containment and fresh recovery pass. Release and Debug reproduce the exact hashes and all four RC contracts pass 4/4. Raw SDK acceptance remains failed only for the known metadata query; no rendered-frame claim is made. See `docs/RADIANCE_CACHE_TRAINING.md`. Next replace analytic data with an offline renderer-exported path/compositing fixture while retaining this sequence.

## FidelityFX Radiance Cache synthetic dispatch sprint

### Goal

Execute the pinned Radiance Cache provider's first isolated inference/training dispatch using renderer-shaped synthetic path records, with exact resource/counter/provenance admission and no claim of game-ready GI quality.

- [x] Audit the pinned DX12 resource wrapper, buffer state/stride requirements, sample normalization and dispatch lifetime; define a deterministic non-degenerate synthetic fixture and acceptance gates.
- [x] Extend the separate native/managed Radiance Cache boundary with bounded external buffers, reset/inference/training/counter-clear dispatch, guarded readback and strict report admission.
- [x] Run Release/Debug success, malformed/counter/resource/failure containment and repeatability tests; document output behavior and the remaining renderer integration gap without changing defaults.

Scope: optional offline D3D12 execution on the RX 9070 XT using the already pinned SDK 2.3.0 provider. Fixed capacities remain 12,288 inference and 512 training samples; the first dispatch may use smaller populated counts but must allocate the exact previously audited 716,808 API-visible bytes. Inputs are deterministic normalized synthetic path records with finite bounded training targets, not captured game data. The phase may reset, infer, train, clear counters and read back outputs/counters inside the isolated worker. It does not connect the D3D9 proxy, add live IPC, alter the normal renderer, composite into a game frame, modify installed games/drivers, claim converged GI quality or substitute ROCm for the provider's D3D12 runtime. Existing 32 MiB provider-allocation ceiling and process containment remain strict; external resources receive separate exact accounting and guard validation.

Initial direction: preserve the context-only mode byte/report behavior and add an explicit dispatch mode. First mirror the pinned sample's resource creation/state transitions exactly, then reduce populated counts—not capacities—to keep the fixture inspectable. Require non-finite/guard/counter rejection, full teardown and a no-training or reset control before interpreting radiance values. Do not assume the preview provider is deterministic until Release/Debug and fresh-process evidence proves the relevant tolerance.

Final result: separate inference-only and reset+inference+512-training modes execute successfully through the signed provider. Both clear counters, replace all 36,864 NaN output sentinels with finite nonnegative RGB, preserve every input/target byte, keep the device healthy and release all provider allocations. Their output is byte-identical across mode, repeat and Release/Debug (`FNV-1a64 8439070038676242095`, range `0.0265808..0.0398865`), consistent with inference occurring before training. The exact metadata code-4/ID-0 workaround remains the only managed exception and raw SDK acceptance stays failed. All three RC contracts pass 3/3 in both configurations; low-budget provider crash containment and fresh dispatch recovery pass. No rendered frame or useful learning is claimed. See `docs/RADIANCE_CACHE_DISPATCH.md`; next measure post-training inference on the same context and reset recovery before replacing analytic records with renderer paths.

## FidelityFX Radiance Cache foundation sprint

### Goal

Establish whether the pinned FidelityFX SDK exposes a usable D3D12 Radiance Cache provider on the RX 9070 XT, and build the smallest isolated, budgeted context boundary before connecting renderer rays or claiming GI quality.

- [x] Audit the pinned Radiance Cache API/provider/sample contract, required resources/callbacks and current renderer inputs; define the first context-only acceptance boundary and later dispatch gap.
- [x] Implement an optional x64 standalone support/context probe with exact provider/version identity, bounded callback accounting, deterministic teardown and managed admission/failure containment.
- [x] Run Debug/Release lifecycle and failure-path tests, document measured support/memory and specify the next renderer-owned trace/update/query slice without changing renderer defaults.

Scope: optional offline D3D12 research on the existing RX 9070 XT and pinned FSR SDK 2.3.0 package. This phase may query versions/support and create/destroy a small Radiance Cache context, but it does not dispatch cache updates, replace current one-bounce GI, share resources with the D3D9 proxy, add live IPC, alter installed games, change the driver or claim path-traced quality/performance. All SDK allocations require explicit ceilings and release accounting; unsupported/missing providers fail closed. ROCm remains an optional authoring/compute track, not the Windows presentation/runtime API: this feature's shipped integration boundary is whichever backend the pinned FidelityFX provider actually exposes.

Initial direction: mirror the proven RR isolation pattern only where the Radiance Cache API requires it. Prefer a separate executable/report namespace so RR workarounds and acceptance cannot leak into the cache path. First inspect the actual header, signed binaries and official sample before choosing context dimensions, cascade counts or memory budgets; do not infer those values from marketing documentation.

Final result: the signed Radiance Cache 0.9.0 provider enumerates on the RX 9070 XT (SM 6.6, wave32–64) and creates/destroys its WMMA context at fixed 12,288/512 capacities. The managed 32 MiB ceiling measures a repeatable 20,643,840-byte peak with 11/11 releases and no live allocations. Release and Debug contracts pass 2/2, including isolation, malformed evidence, provider-crash containment and fresh recovery. Raw SDK acceptance remains failed because post-create provider identity returns code 4/ID 0; only that exact hash-pinned defect is admitted. No dispatch or rendering is claimed. The next phase is precisely bounded to 716,808 bytes of API-visible query/output/target/counter buffers plus renderer-owned path/compositing state. See `docs/RADIANCE_CACHE.md`.

## RR exact-zero floor sprint

### Goal

Determine which valid RR inputs and history/configuration states produce the reproducible positive output from exactly zero indirect radiance, without subtracting, clamping or otherwise hiding it.

- [x] Audit retained reset/history/settings evidence and define a minimal set of valid active-surface, zero-albedo, zero-distance and all-background controls.
- [x] Add a bounded black-floor analyzer/reproducer with exact input/output provenance, spatial distribution and per-frame history diagnostics; preserve all existing strict zero oracles.
- [x] Run Release measurement and fresh Debug replication, affected regressions and documentation; either identify an integration error with a tested fix or retain the provider floor as an explicit failed gate.

Scope: isolated offline RR execution at historical 128x96 only. Input indirect RGB is exactly zero in every candidate. Start from a source-valid reset/history capture, then admit only mutations already valid under the RR input contract: zero diffuse albedo on active geometry, zero committed hit distance, or canonical inactive background records. Compare queried-default/unconfigured behavior and a small predeclared subset of already provenance-tagged settings only when they distinguish a cause. Do not apply output bias correction, epsilon thresholds, negative pre-bias, post-clamp, speculative guide transforms, SDK binary changes, driver changes, live IPC or game integration. Background must remain exactly zero and output alpha must remain the packed distance. Existing `--require-zero-light` failures remain strict and visible until exact zero is genuinely produced.

Initial evidence: the reset-only fixture reproduces maximum RGB `1.0907649993896484e-5` and MSE `9.602695114768744e-11`; two-frame stationary and recorded black paths also retain nonzero output. The current settings regression already contains fresh two-frame black outputs for every configured preset, so first analyze those retained bytes before scheduling redundant GPU work. The active/background localization and history trajectory are not yet summarized. A read-only inspection expected `tools/rr_record.py`, which does not exist; recording helpers are in `tools/rr_recorded_dispatch.py` and the existing test harness. No project file was affected by that failed lookup.

Final result: the mixed-coverage fixture has 9,976 active and 2,312 inactive pixels. Every active RGB component is positive and every inactive component exact zero over eight frames. Zero hit distance is RGB-exact with baseline; zero albedo and all existing scalar settings retain the floor. Mean declines only from `1.08757e-5` to `1.07135e-5`. Release and Debug reproduce the recording plus all nine output/input artifacts byte-for-byte; adjacent Release contracts pass 4/4 and the focused Debug contract passes. The signed provider implementation is not public enough to name an internal epsilon, so the supported diagnosis is a provider-boundary active-pixel floor, retained as a strict failed gate with no compensation. See `docs/RR_ZERO_FLOOR.md`.

## RR guide-conditioning sprint

### Goal

Determine whether the remaining RR spatial/fallback gap is caused by a valid but mismatched guide representation, holding native resolution, radiance samples, history, scale and filter setting fixed.

- [x] Audit the pinned descriptor/sample semantics for normal space/encoding, roughness/material type, diffuse albedo and radiance range; select only coherent, API-valid fixed variants.
- [x] Add recorded-worker-only guide presets with exact packed hashes and output provenance, preserving recordings and the historical unconfigured path byte-for-byte.
- [x] Run a bounded texture/PBR moving comparison against shared same-input references/fallbacks, replicate outputs, run affected regressions and document without promoting a guide preset.

Scope: offline recorded-worker research only at historical 128x96 and coherent `unit-one` scale. No renderer recording mutation, arbitrary guide edits, signal rescaling that changes the lighting quantity, SDK/driver changes, live IPC, game integration or default promotion. Candidate presets must be expressible within the pinned RR descriptor: octahedral normals plus linear roughness/material type, correctly encoded diffuse albedo, and documented configuration keys. Each candidate receives strict native/managed provenance and identical source/reference/fallback evidence. Texture and PBR moving controls use the same seed/history. Any ambiguity that cannot be resolved from the pinned headers or AMD documentation is excluded rather than guessed.

Initial audit: the renderer supplies world-space octahedral normals, linear roughness (`1` for legacy diffuse), material type `0`, diffuse albedo `baseColor*(1-metallic)`, signed view depth, UV/depth motion and indirect diffuse radiance. The pinned header confirms the packing and albedo convention but does not state normal space or define material-type values inline. Existing linear/sqrt albedo experiments already found no accepted representation. Valid remaining levers include documented context configuration (normal strength, maximum radiance, clipping K, disocclusion threshold) and, only if AMD documentation resolves it, a coherent normal-space/material-type representation. First verify semantics before implementation.

Selected fixed grid after documentation/live-default audit: `{baseline, material-draw} × {normal-default, normal-half}` plus a separate `max-radiance-one` signal-range candidate. `material-draw` maps the two fixture draws to AMD classes `0` and `1/3`; `normal-half` uses the documented cross-bilateral strength key with queried default `1`; max radiance `1` remains above the observed input maximum `0.08405`. No normal-space conversion, roughness fabrication, albedo change, radiance scaling or stability change is admitted.

Final result: native and managed `material-draw` packing, strict `RRTRRD06` provenance, new default-verified normal/max-radiance settings, output/report admission and shared-reference quality support are complete. The 10-candidate Release grid completes in 311.88 seconds. Material partitioning and half normal strength produce only small, mixed spatial/temporal changes; `max-radiance-one` is metric-exact with baseline. Every candidate still fails the spatial, disocclusion, fallback, fallback-confidence and raw SDK gates. Fresh Debug replay reproduces two recordings and all ten outputs byte-for-byte. Affected Release regressions pass 7/7 and focused Debug contracts pass 2/2. No preset is promoted. See `docs/RR_GUIDE_CONDITIONING.md`.

## RR resolution sprint

### Goal

Measure Ray Regeneration at native 128x96 versus 256x192 input resolution without resampling either guides or the independent reference, after first making extent an explicitly bounded part of every recording, worker and output contract.

- [x] Define a backward-compatible dynamic-extent RR input/recording/output ABI with fixed admitted extents, overflow-safe size formulas and exact rejection of cross-extent provenance.
- [x] Parameterize renderer preparation, isolated SDK resources/context/dispatch, managed readers and analytic/fallback references while preserving every historical 128x96 v1 byte.
- [x] Run native-resolution default/zero-bias texture/PBR motion controls, replicate results, run affected regressions and document without promoting a resolution.

Scope: offline RR research only. Initial admitted extents are exactly 128x96 and 256x192; no arbitrary resizing, upscaling, checkerboarding, dynamic resolution, live renderer integration or game modification. Each extent must be rendered natively from the same camera/frustum and evaluated against a same-extent independently traced reference/fallback. Sample count, seed, surface, camera trajectory, scale (`unit-one`) and filter setting are paired. The historical 128x96 v1 formats and outputs remain exact. Resolution metadata must be carried through native and managed reports rather than inferred from file size. A live 64x48 context was attempted and rejected because the pinned SDK internally requested zero-height D3D12 resources, so it is retained only as a documented rejected candidate—not an admitted ABI.

Initial audit: resolution is currently an ABI constant in `RRTRRI01`, `RRTRRC01`, `RRTRRO01`, native texture allocation/context creation, managed packing/output checks, quality/reference dimensions and numerous tests. The HLSL preparation shader and main renderer are already extent-driven, but RR admission deliberately requires 128x96. A valid experiment therefore needs a coordinated versioned contract migration; changing only SDK `renderSize`, downsampling existing guides or comparing an upscaled result would not isolate native resolution.

Final result: exact 128x96 v1 compatibility and a strict 256x192 v2 path are complete from native capture through SDK dispatch, independent reference and fallback. The original 64x48 candidate is rejected because the live provider creates zero-height resources. The four-case/eight-output Release grid completes in 686.94 seconds and fresh Debug replay reproduces four recordings/eight outputs byte-for-byte. Higher resolution improves every spatial/disocclusion aggregate but gives mixed temporal results, including a 51% default-PBR regression. All eight candidates still fail spatial/fallback acceptance, raw SDK reporting still fails, and no resolution or setting is promoted. See `docs/RR_NATIVE_RESOLUTION.md`.

## RR coordinate-scale sprint

### Goal

Determine whether the pinned RR 1.2 denoiser's poor spatial result or lower-stability temporal tradeoff is sensitive to a coherent change of scene units, with render resolution, source samples, radiance, albedo and filter settings held fixed.

- [x] Add three recorded-only, provenance-tagged coordinate presets (`unit-tenth`, `unit-one`, `unit-ten`) and verify that each scales every SDK-visible length consistently while leaving the immutable recording and reference/fallback inputs untouched.
- [x] Exercise strict native/Python admission, exact unit-one equivalence, reset/history/moving-camera behavior, malformed or mismatched provenance, and historical unconfigured-output compatibility.
- [x] Run a bounded default/zero-bias measurement grid at fixed 128x96, replicate the outputs, run affected regressions, and document the result without promoting a scale or filter setting.

Scope: offline recorded-worker research only. Uniform scale `s` applies to signed linear depth, signed depth motion, committed indirect ray hit distance, camera position delta, view translation, projection's homogeneous translation row, and linear-depth bounds. The exact 100000 no-secondary-hit sentinel remains unbounded at FP16 max. This is the row-vector homogeneous transform `V' = S^-1 V S`, `P' = S^-1(sP)`, so projected UV remains unchanged while all world/view lengths change units. Normals, roughness, material IDs, radiance, albedo, XY motion, resolution and original recordings do not change. `unit-one` is an explicitly tagged diagnostic control; the historical no-preset path must remain byte-for-byte compatible. Separate depth-only and hit-distance-only scaling are excluded because they violate the API's common-space guide relationship rather than representing a coherent scene-unit change. SDK/provider binaries, renderer shaders/defaults, drivers and games remain untouched. Existing raw SDK, independent-reference and fallback gates remain unchanged.

Initial contract audit: the pinned header requires signed current linear depth, previous-minus-current linear-depth motion, previous-minus-current world-space camera delta, current view/projection matrices and indirect ray hit distance. It exposes no independent current-depth scale. The current capture supplies mutually checked view-space depth/world position and clamps secondary misses to FP16 maximum during SDK packing. Therefore the first valid scale experiment must transform the complete length-bearing SDK input set, not only depth. Output format/probe reports still need scale provenance before measurement.

Final result: three fixed transforms, `RRTRRD04` output provenance, exact matrix/texture hashes, strict managed/native admission and shared-reference quality support are complete. The first 24-candidate grid exposed an invalid finite transformation of the exact no-secondary-hit sentinel and is retained as superseded evidence. The corrected grid preserves that sentinel at FP16 max, gives identical clamp totals across scales and completes 24 candidates plus four unit-one/unconfigured controls in 653.31 seconds. All unit-one inner SDK frames are exact. Every candidate still fails spatial/disocclusion/fallback gates and raw SDK acceptance; all confidence diagnostics except the existing fallback-relative one pass. Scale ten gives small spatial improvements but usually worsens late temporal response and does not change the zero-bias tradeoff (26 spatial/disocclusion improvements and 26 temporal regressions at every scale). No scale or setting promotion. Fresh Debug replay reproduces all 28 bundles exactly in 235.30 seconds; Release affected regressions pass 5/5 in 472.39 seconds and Debug contracts 2/2 in 53.86 seconds. See `docs/RR_COORDINATE_SCALE.md`. Next isolate resolution with unit scale fixed.

## Goal

Determine whether the lower-stability temporal penalty is only initial history settling or persists through eight-frame stationary/moving histories and after an explicit matched reset.

## RR longer-history sprint

- [x] Implement and independently test a fixed eight-frame texture/PBR × stationary/moving/reset × seeds 1/7/23 × default/half/zero harness.
- [x] Run the 54-dispatch/18-reference Release grid within count*samples<=4096 and retain per-frame reference-confidence failures rather than relaxing the cap.
- [x] Replicate outputs, run affected regressions and document whether late/post-reset temporal error persists without promoting a setting.

Scope: offline research only. Eighteen renderer recordings, 54 isolated SDK outputs, 512 samples per independent PCG64 reference batch (1024 total per hit), static geometry, fixed light, stationary or .04-unit camera translation, explicit reset at frame 4 for the reset trajectory. Same verified surface/material/shader and three input seeds as the completed four-frame grid. All sources, preset tags, default queries/configures, guide/camera seed isolation and common reference/fallback arrays remain checked. Lower reference confidence caused by the eight-frame work cap must remain visible. No renderer/shader/native worker/SDK/driver/game/default changes. Session catchup found no unsynced state.

Implementation complete: fixed trajectory/reset contracts, grouped all/late/post-reset spatial-temporal-disocclusion deltas, strict paired availability and seed-isolation audits. Python compilation, help, normal/optimized aggregation contract and two registered Release CTests pass. Full Release 54-dispatch/18-reference grid is running at 512 samples per batch. No reference cap or gate changed.

Release grid rr-setting-histories-i7to8gpg completes in 2004.30 seconds: 18 captures, 54 SDK bundles/reports and 18 numeric references (about 403 MB total). All 54 pass raw and temporal reference-confidence diagnostics; all 54 fail spatial and fallback gates, and all 54 retain failed raw SDK acceptance. The stricter fallback-reference confidence fails for every case at capped 512/batch. Default passes temporal-vs-raw in 18/18; half passes 5/18 and zero 2/18. Across late windows both variants improve all spatial/disocclusion comparisons and match all six explicit reset frames exactly. Half worsens all 66 late temporal comparisons; zero worsens 65/66, with one PBR moving seed-23 late improvement. No default promotion. Debug 18-recording/54-output replay and five affected Release regressions are running.

Final acceptance: optimized Debug fresh replay rr-history-replay-w13fuyu4 passes in 534.09 seconds, reproducing all 18 recordings and 54 SDK bundles byte-for-byte. Five affected Release tests pass in 507.23 seconds (rr_quality, rr_surfaces, rr_settings and both comparison contracts). Both contracts also pass Debug; eight-frame actual cached/standalone analysis matches all three reports/arrays with 8 versus 24 estimator calls and two mismatch rejections. Six moving capture prefixes and eighteen preset output prefixes match the prior four-frame grid exactly. Python compilation/two modes and 42 local documentation links pass. Three milestones manually complete; helper remains 0/0 for checklist format. Full SDK suite, normal renderer/x86/legacy/historical-render suites not rerun. Auxiliary prefix audit first used an expensive tuple decode, then a slow PowerShell byte loop; both were superseded/stopped and replaced by immediate byte-slice equality. No artifact mismatch or mutation.

Decision: do not promote half or zero stability. The evidence establishes a fixture-consistent spatial-versus-temporal tradeoff that usually persists late and always persists across the sampled post-reset windows, but does not identify SDK internals. Next bounded hypothesis should isolate depth/distance scale without combining resolution changes, using the default plus zero-bias response as diagnostic controls and retaining the same raw/fallback/reference gates. See docs/RR_LONG_HISTORIES.md.

## RR multi-seed surface sprint

- [x] Implement a bounded, provenance-checked six-recording/three-preset comparison harness and independently test aggregation/admission behavior.
- [x] Measure all predeclared cases against independent high-sample references and the matched fallback; preserve per-frame and per-seed results without selecting a default.
- [x] Verify regression/replication evidence and document findings, limits and next work.

Scope: offline tools only; renderer/shaders, worker/native SDK integration, vendor binaries, drivers and installed games remain unchanged. Fixed input seeds 1, 7, 23; four frames at camera step .04; identical existing surface fixture with and without the material sidecar; presets none, stability-half, stability-zero. Reference uses two independent PCG64 batches, 1024 samples each per hit, unchanged count*samples<=4096 cap. Preserve each run's provenance and equal reference/fallback arrays across presets. Paired comparisons against default are descriptive, not formal confidence bounds or general acceptance. Existing contrast/black-floor/raw SDK failures remain. Session catchup reports no unsynced context.

Initial inspection: existing surface artifacts contain source.rrscene and surface.rrmat; rr_quality already validates source/material/shader/execution/preset provenance and supports explicit surface references. A read-only rg command interpreted a pattern beginning with -- as an option; correct subsequent search with an explicit -- delimiter. No files affected.

Implementation complete: fixed grid, seed-isolation checks, paired deltas and private source-bound in-memory reference sharing. CPU contract passes normal/optimized Python and CTest. Optimized integration check on texture seed-1 proves exact report/array equality against three standalone analyses, four versus twelve estimator calls, and rejection of substituted preset/changed cache identity. Release full grid rr-setting-surfaces-um5fj4em is running at 1024/batch; prior quality/surface/settings regressions run alongside it. Initial incomplete run was deliberately interrupted after adding the final seed audit; no accepted evidence from that run. First texture case retains spatial/disocclusion/fallback failures and lower-bias temporal regression.

The completed 18-analysis run failed its new final seed-isolation assertion: that audit mistakenly included sampled secondary-ray hit distance (record component 3) among deterministic guides. Source rr_inputs.hlsl explicitly places this stochastic distance beside indirect RGB in indirectDistance; only components 0..3 should vary by seed. All per-preset quality/reference files remain retained. Diagnose exact differing columns, correct the audit to include distance in the stochastic signal, and revalidate existing artifacts before publishing a summary. Do not alter renderer data or quality gates to satisfy this audit.

Corrected audit passes on all six retained recordings. New regression controls distinguish stochastic distance from deterministic normal/camera changes. Recovery helper revalidates all 18 worker admissions/output tags/source/report/reference hashes against unchanged analysis implementation and publishes a clearly labelled recovered manifest (elapsed time unavailable, no reference recomputation). Half and zero bias each improve all 18 non-reset spatial and 18 disocclusion estimates versus default, leave six reset-frame estimates equal, but worsen all 18 temporal residuals. All reference diagnostics pass; every setting still fails spatial/disocclusion/fallback gates, while half/zero additionally fail temporal non-regression. Four targeted Release tests pass in 468.51 seconds. Debug six-recording/eighteen-output fresh replay is running.

Final acceptance: optimized Debug fresh replay passes in 64.27 seconds (rr-surface-replay-y0d3mw1c), reproducing all six recordings and eighteen SDK outputs exactly without recomputing references. Both historical texture/PBR recordings, default outputs, reference NPZs and all frame metrics remain exact. Final normal/optimized CPU contract, separate Debug/Release CTests, Python compilation and 38 local documentation links pass. The three current milestones are manually complete; planning helper still reports 0/0 for the unsupported checklist format. Full optional SDK, normal renderer/x86/legacy/historical-render suites were not rerun. No default promotion. Earlier running-status notes are superseded by this result; the corrected seed-audit error and recovered-manifest provenance remain documented.

Next bounded work: distinguish history settling from persistent temporal error using longer stationary/moving sequences with matched reset controls and independent reference uncertainty checks. Four-frame results do not establish steady state or an SDK-internal cause. Keep default/half/zero as experiments, preserve failed quality/raw SDK evidence, and treat depth/distance/resolution changes as separate hypotheses. See docs/RR_MULTI_SEED_SETTINGS.md.

## RR single-setting sprint

- [x] Add recorded-only, predefined single-key presets with per-context default admission/configure return evidence and distinguishable output provenance.
- [x] Verify idempotent controls, malformed/missing setting evidence, both encodings, resets and failure containment.
- [x] Measure small predeclared grids against unchanged analytic controls, run Debug/Release regressions, and document findings without promotion.

Scope: isolated research worker only; no renderer/shader/vendor SDK/driver/game changes. Seven predefined presets cover stability 1 (queried-default control), .5, 0 and Gaussian relaxation 0 (queried-default control), .25, .5, 1. Only one key per run. All presets imply read-only default inspection and are reapplied on context recreation. Session recovery found no unsynced state. Existing output readers must reject configured output unless the exact preset is explicitly expected.

Initial live stability-default configuration succeeds and preserves inner frame bytes exactly. Native API-double test passes 49 admission/ABI/failure cases; both native configurations build. Early two-frame linear/sqrt grids show reduced MSE for stability .5/0, but not a fix: linear second-frame .00116959 baseline versus .000607870 at zero bias. Gaussian changes are small/mixed. Longer history, reset, black and full verification follow; no filter promotion or internal-cause conclusion.

Eight-frame analytic history now gives MSE .001030857 baseline, .000211700 at stability .5 and .000146440 at stability 0 (about 85.8% lower than default). Gaussian variants remain near .00103–.00105. Moving reset also improves at stability 0 (.000491692 versus .000988832). These are predeclared fixture-specific results, not noisy-game acceptance. Add full history quality evidence for the zero-bias candidate and retain raw/fallback failure gates; no default promotion.

Expanded optimized Debug rr-settings-yn9yujur passes in 331.69 seconds: 40 grid runs, ten exact default-equivalence controls, five historical matches, 43 rejected cases, configured CLI/recovery and eight reset contexts with stdout 38,039 bytes under the existing 64 KiB cap. Full zero-bias history quality report still fails spatial/temporal/fallback gates. Native contract passes 49 CPU-only cases in Debug/Release. Full Release optional regression is still running; final new-test console output is compacted only (full measurements remain in verification.json).

While regressions run, add one bounded noise-tradeoff check using the already validated four-frame moving constant-diffuse fixture from rr_quality, testing none/stability-half/stability-zero against fresh 512-per-batch independent references and the matched fallback. This is a single-recording diagnostic, not multiseed qualification, and does not change the predeclared analytic grid or renderer defaults.

The initial noisy comparison (rr-setting-noise-v2t6g3to) measures lower later-frame MSE for half/zero bias, but one temporal comparison worsens and the reference-noise-versus-fallback gate fails at 512 samples per batch (reference variance ~5–6e-8). Retain that evidence and rerun with 1024 per batch, still within the existing count*samples<=4096 cap. Do not relax the gate or rank small differences without qualification.

Single-setting sprint final acceptance: Release optional SDK regression passes 12/12 in 1082.68 seconds; final rr_settings takes 309.06 seconds (rr-settings-tp8e7cvp). All 43 output bundles, six reference bundles, five recordings and measurement dictionaries match expanded optimized Debug exactly. A separate hash audit confirms five final historical default-output matches; the CTest invocation itself omits the optional baseline argument. Final noisy 1024/batch Debug diagnostic completes in 221.92 seconds (rr-setting-noise-4geqmsb0), passing all eight narrow gates for all three presets. Later-frame improvements coexist with early temporal/disocclusion tradeoffs. Its SDK outputs match the 512/batch Release run; reference estimates differ intentionally. No quality/default promotion; analytic contrast, black floor and raw SDK-reporting failures remain. Current three milestones manually complete; the planning helper again reports 0/0 because it cannot parse this checklist format. No build/runtime failures or threshold relaxation. Normal renderer/x86/legacy/historical-render suites not rerun. Earlier running-status checkpoints are superseded by this result.

Next bounded work: independent-input-seed noisy/PBR camera-motion and visibility-boundary characterization of default/half/zero stability before choosing an operating point. Keep existing exact-default, fresh-context and failed-quality controls. Animated geometry needs future capture-contract work; longer histories/depth/distance/resolution remain separate hypotheses. See docs/RR_FILTER_SETTINGS.md.

## RR default-query sprint

- [x] Add explicit bounded recorded-worker inspection, preserving typed values, raw return codes, sentinel/canary evidence and before/after snapshots without denoiser-context configuration overrides.
- [x] Validate inspection reports and add query-on/off, stability, malformed-report and compatibility tests.
- [x] Build and test Debug/Release against the pinned SDK; document actual defaults or query failures without promoting quality.

Scope: optional isolated research worker only. No filter tuning, renderer/shader changes, vendor SDK changes, drivers or installed games. Existing allocation/process caps and failed raw-SDK/quality evidence remain intact.

Initial Release rr-defaults-v35hm6p3 passes in 96.28 seconds: ten query-off/on pairs across both encodings, including eight sequential cut contexts, 34 rejected cases, five honest failures, two instability controls, CLI/quality revalidation and allocation-failure recovery. Eight historical bundles match byte-for-byte; every paired non-query native report field also matches. All six defaults are stable (1, 1, 65504, 50, 0, float32 .01). Maximum stdout 36,099 bytes, below unchanged 64 KiB cap. Optimized Debug and Release regression verification follow. No build/runtime failures or changed quality thresholds so far.

Final optimized Debug rr-defaults-fh5vyha8 passes in 145.42 seconds (concurrent with the independent Release suite), including added signed-zero and integrated honest-failure validation: 35 rejections, five honest failures, two instability controls, ten off/on pairs and eight historical matches. All 22 output bundles/case dictionaries match initial Release exactly. Full optional Release suite has passed its first seven tests, including retained textured/PBR quality regressions; final three are running. Two auxiliary read-only URL/log-path lookup errors were corrected and recorded in progress.md; no test/build failures or quality threshold changes.

Final acceptance: Release optional SDK suite passes 10/10 in 692.00 seconds; rr_defaults passes in 129.45 seconds (rr-defaults-ycw6uxym). All 22 output bundles, five recordings and per-case dictionaries match final optimized Debug exactly, and eight final bundles match historical encoding evidence directly. Final checks retain 35 rejections, five honest failures, two instability cases, CLI/quality revalidation and crash recovery. Fourteen old encoding outputs, eight reference bundles including CLI reference and all encoding metrics also remain identical. Current milestones manually complete; no quality/default promotion. Normal renderer/x86/legacy/historical-render suites were not rerun. See docs/RR_DEFAULT_SETTINGS.md.

The planning helper again reports 0/0 because it does not parse this checklist format; all three current milestones were manually verified complete. Earlier running-status paragraphs above are chronological checkpoints, superseded by final acceptance.

Next bounded implementation: explicit single-key setting provenance and a configure-to-queried-default equivalence control, then small one-key Gaussian-relaxation/stability grids within AMD's documented sample ranges. Reapply per recreated context; do not treat default queries as active-setting readback. Preserve budgets, failed gates and default output; depth/distance scale and resolution remain separate later hypotheses.

## RR paired encoding sprint

- [x] Implement explicit recorded-worker linear/square-root packing modes, with verified metadata and distinguishable nondefault output.
- [x] Add same-input analytic comparisons, malformed-provenance checks and default-output compatibility tests.
- [x] Build Debug/Release, run real SDK and compatibility tests, and document measured results without default promotion.

Scope: recorded isolated research worker only. Canonical RRC/RRI inputs, renderer/shaders, SDK binaries, driver and installed games remain unchanged. Linear is the default; square-root mode must pair encoded albedo with NON_GAMMA_ALBEDO absent. Nondefault output must not silently pass as historical linear output. Historical linear reports remain readable; new reports explicitly bind encoding/flags/packed hashes. Session recovery found no unsynced state.

Initial Release paired verification passes (rr-encoding-phy27gzm, 116.02 seconds), including six pre-change byte-identical linear baselines, 25 rejections and sqrt crash recovery. Encoding change does not resolve contrast loss: frame-seven linear-texture MSE differs by only about 0.16%, while point texture worsens slightly. Added final quality CLI and moving-reset checks. Release full optional SDK regression and optimized Debug are running. No build/runtime failures or threshold changes so far.

Final acceptance: Release optional SDK suite passes 9/9 (553.45 seconds), including final rr_encoding in 140.24 seconds (rr-encoding-n49hhhv5). Optimized Debug rr-encoding-d366h8er passes all seven pairs, 28 rejections, CLI failure-evidence retention, moving resets and recovery. Fourteen SDK output bundles, seven numeric reference bundles and metrics match configurations exactly; six historical linear outputs remain byte-identical. All current milestones manually reviewed complete (skill helper cannot parse checklist style). No runtime/build failures or tolerance changes occurred. Normal renderer, x86, legacy and historical-render suites were not rerun; modified native headers are exclusive to the research probe.

Next bounded work: query actual default values on a live pinned denoiser context, preserve per-key return codes/typed values and verify no output/default changes. Do not configure speculative values or treat the encoding comparison as a fix. Then test individual settings with separate provenance; depth/distance scale and resolution remain later hypotheses. See docs/RR_ALBEDO_ENCODING.md.

## RR colour-response isolation sprint

- [x] Audit the pinned signal/albedo contract and quantify candidate colour-response relationships in existing evidence.
- [x] Build bounded one-variable-at-a-time colour/texture experiments with independently validated analytic controls; establish whether PBR is necessary to reproduce the failure.
- [x] Run real SDK comparisons and regression checks; document the strongest supported diagnosis and remaining uncertainty.

Scope: offline diagnosis and test tooling, no speculative SDK flags, shader fixes or default promotion. Use a single lit plane with ambient-only secondary misses where possible to remove Monte Carlo uncertainty. Session recovery found no unsynced state. Initial SDK header lookup used a nonexistent api/include path; resolve the installed header with rg --files before reading it. No files affected by that lookup.

Initial analytic test exactly matched the mean but its proposed 1e-20 variance assertion rejected 5.51e-20 float64 cancellation residue in E[x^2]-E[x]^2. Replaced that new test-only arbitrary threshold with an explicit float64 accumulation-roundoff bound; no RR quality gate or output was changed. Artifact rr-colour-2o23tkeh retained.

Expanded Release rr_colour_response passes (95.43 seconds, rr-colour-0u48aq8r): eleven actual GPU/SDK cases, three equivalent packed-input/output pairs and three malformed metric inputs. PBR is not necessary: noise-free vertex/texture variation loses contrast on one stationary plane. At eight frames the linear-texture MSE is still .00103086 and centered RGB gain .273/.461/.207. Documented linear-albedo/radiance pairing matches current dispatch; encoding multipliers/channel swaps are not supported fixes. Optimized Debug and old quality-reference regression checks follow. No native, shader, SDK, driver or game changes.

Final acceptance: optimized Debug rr-colour-cm_unoww passes (94.77 seconds); all eleven output/NPZ bundles and frame metrics match Release exactly. Old Release rr_quality and rr_surfaces pass 2/2 (139.79 seconds), retaining both prior positive/negative fixture evidence. New analytic CTest plus these two quality tests pass; full isolation/native/x86/legacy suites were not rerun. Three rejection cases, three equivalent-prefix pairs and independent affine-gain/correlation controls pass, as do compilation and local links. Current milestones manually reviewed complete (skill helper reports 0/0 for checklist style).

Next bounded implementation: provenance-checked worker encoding choice comparing the two documented albedo encodings on unchanged canonical recordings, with actual flags/packed hashes verified and unchanged default output. Then query default filter settings, and separately consider depth/distance scale and resolution. No SDK-internal cause or fix has been established. See docs/RR_COLOUR_RESPONSE.md.

## RR surface and baseline sprint

- [x] Add a source-verified textured/PBR reference while preserving the strict constant-colour reference and its regression evidence.
- [x] Implement a clearly labelled matched-input CPU port of the fallback spatial algorithm, validate it independently, and report RR/fallback/raw metrics.
- [x] Exercise material/texture boundaries, negative cases and actual SDK recordings; document measurements without general quality promotion.

Scope: keep fixed directional lights and bounded fixtures; soft lights and longer histories remain later gates. No native renderer/shader/SDK changes planned. Session recovery found no unsynced state or source-scoped AGENTS.md. The fallback comparison is an offline algorithm port on RR indirect input, not the legacy renderer's differently sampled/composited image.

First low-sample surface test passes all CPU/GPU/scalar estimator checks, but both textured and PBR fixtures fail some RR spatial quality gates. No output correction or tolerance relaxation. A deeper guide audit found fallback uses primary ray T (not RR view Z) and base surface colour (not metallic-scaled diffuse albedo); corrected the comparison to supply independently traced matched-hit legacy-semantic guides before final measurement. Initial fallback values from rr-surfaces-1ap_sjm3 are superseded, while its RR/raw evidence is retained.

Final Release optional SDK suite passes 7/7 (367.13 seconds); surface harness rr-surfaces-1x1xqyi8 passes four actual GPU/SDK cases, 16 rejection cases and four independent fallback guide controls. CPU/GPU maximum estimator error is 1.10e-7, scalar lighting error zero. Harness success explicitly retains failed RR spatial/disocclusion/fallback gates. Optimized Debug is running; the higher-sample texture CLI run already passes the fallback-reference uncertainty target while retaining RR regression. Missing-material and overwrite CLI checks both return 1 with no unwanted output. No runtime failure or tolerance relaxation; final Python edits were documentation-only and CMake's omitted-test message now names both optional tests.

One local documentation-link audit mistakenly treated an HTTPS license URL ending in .md as a local path. Corrected the read-only audit to skip HTTP(S) URLs; all local links pass. No documentation link was actually broken.

Final acceptance: optimized-Python Debug surface harness passes (rr-surfaces-04wvhmhq), with identical SDK output bundles, numeric reference arrays and frame metrics to Release. Both 2,048-total-sample CLI runs now pass every reference-noise diagnostic, including fallback variance at 0.66–0.75% of fallback MSE. RR still fails spatial/disocclusion/fallback gates: RR/raw 9.90–23.53, RR/fallback 144.50–306.50. Both retain evidence and return the required exit 2. Higher-sample reports are in rr-surfaces-xt5d6i3h with -quality-2048.json/-reference-2048.npz suffixes. All three milestones manually reviewed complete; the planning helper again cannot parse this checklist style (0/0). Normal renderer, x86, legacy and historical suites were not rerun; no native renderer/shader/SDK/driver/game changes.

Next bounded work: one-variable-at-a-time colour/vertex/texture/PBR ablations, checking documented albedo and indirect-radiance conventions to isolate the large spatial response error. Keep RR nondefault and preserve exact-zero/raw-report failures. The new reference/fallback tools are implemented, not a fix for the SDK output. See docs/RR_SURFACE_QUALITY.md.

## RR quality reference sprint

- [x] Implement a bounded independent CPU reference with independent sample streams, source/record identity checks and a quantified reference-convergence diagnostic.
- [x] Measure raw versus RR error on matched primary hits, with geometric visibility masks and temporal residuals; retain exact-zero failure and avoid unsupported quality claims.
- [x] Add deterministic/negative/control tests, run actual moving recordings, and document measured outcomes and remaining limitations.

Scope: a deliberately supported fixture subset first; fail closed on unsupported materials/settings. Prefer no renderer/SDK changes. Session recovery found no unsynced state or source-scoped AGENTS.md. The existing CPU input oracle supplies a separately implemented triangle tracer and sampling conventions; evaluate practical reference cost before selecting full-frame versus explicitly labelled sparse coverage.

Implemented full-frame chunked float64 NumPy reference with two PCG64 batches and independent visibility tracing. First validation found a 5.19e-9 scalar/vector discrepancy: the test scalar oracle used Python decimal defaults while the new reference used recorded float32 settings. Fixed the test to use the same canonical recorded settings; no numerical threshold was relaxed. A Windows rg glob failed earlier; corrected to explicit source paths.

Initial 256-per-batch test passes, including actual perspective motion and black SDK output. Expanded tests now check analytic ambient-plane lighting, independently scalar-traced disocclusions, normal guides and unsupported inputs. A read-only PowerShell reporting command piped a foreach statement without collecting it first and failed parsing; corrected with a task-specific intermediate variable.

Final acceptance: optional Release SDK suite passes 6/6; final hardened Release quality rerun passes (42.79 seconds, rr-quality-uvvuebjr). Full optimized-Python Debug quality test passes (rr-quality-anz2918z), with identical reference arrays and numerical metrics across configurations. Both final reports include 12 rejected inputs, 386 independent scalar visibility checks, two frustum controls and CLI failure/overwrite tests. At 1,024 samples per pixel, RR has 96.3–99.2% lower frame MSE on this one diffuse fixture; 431 pixels are genuinely revealed each moving frame. All six narrow diagnostic gates pass, but exact-zero bias remains (1.0967254638671875e-5 on the black perspective fixture) and general quality remains not-qualified. No native renderer/SDK or shader source changed; normal renderer/x86/legacy/historical suites were not rerun this tool-only slice. Milestones reviewed complete manually; the skill helper does not recognize this checklist style.

Next bounded work: broaden the matched reference to textured/PBR surfaces and soft lights; compare the fallback filter on exactly matched inputs; add multiple input-noise seeds, harder depth/normal boundaries and longer ghosting tests. Keep the exact-zero failure visible and do not promote RR based on this single fixture. Details and evidence: docs/RR_QUALITY.md.

## RR recorded dispatch sprint

- [x] Validate complete recordings natively before GPU/SDK startup and require managed source identity checks.
- [x] Dispatch bounded recordings using segment indices and previous-minus-current world camera delta, preserving stationary compatibility and allocation ceilings.
- [x] Verify motion, cuts/reset isolation, visibility-change coverage, malformed input and failure recovery in Debug/Release; retain failed quality evidence. Geometric disocclusion/ghosting quality remains a separate gate.

Scope: recorded offline translation with fixed orientation, not animated objects or live integration. No renderer/shader changes or quality promotion. Research confirms the pinned SDK cameraPositionDelta is PreviousPosition - CurrentPosition in world space. One inspection command used a word rather than a numeric line count and failed; corrected the read, no files affected.

Initial native build and real four-frame moving dispatch pass. First compatibility test correctly rejected stochastic direct lighting under the older stationary contract; set zero sun radius only for that compatibility fixture, preserving both admission contracts. A documentation lookup used docs/PHASE_PLAN.md instead of the root PHASE_PLAN.md; corrected the path.

Strict moving-reset equivalence exposed seven changed pixels (maximum RGB difference 0.00006103515625) in Debug rr-recorded-dispatch-vvqmrm9j. Same input identity, frame index zero, reset flag and zero camera delta; cannot attribute the internal SDK cause. Preserve evidence and use sequential fresh SDK contexts at recorded reset boundaries, with unchanged live caps and the same external textures. No tolerance relaxation or correction of output pixels. Stationary legacy reset behavior remains unchanged.

Final acceptance: optional SDK suites pass 5/5 Debug and Release. Final expanded Release report rr-recorded-dispatch-pq85bdel and optimized-Python Debug report rr-recorded-dispatch-wpqr2gu0 each reject 18 reports, 23 inputs, five outputs and five source mismatches; eight-cut resets match fresh contexts, with unchanged live allocation. Eight output bundles match configurations byte-for-byte. Normal Release rebuild and SDK-free input/recording subset pass 2/2; the other renderer tests, x86, legacy D3D9 and historical 53-file comparison were not rerun. Existing raw SDK and zero-light acceptance remain failed. All current milestones manually reviewed complete (skill helper does not parse this checklist format). See docs/RR_RECORDED_DISPATCH.md.

Next bounded work: independent high-sample references with matched primary hits; temporal/disocclusion and ghosting error comparisons; investigate the exact-zero bias. Keep quality and live integration unaccepted until their gates pass. Recorded context recreation is an offline correctness workaround, not a real-time performance claim.

## RR recorder sprint

- [x] Define a checksummed recording contract binding the loaded scene, material inputs, render settings and every frame.
- [x] Record 2..8 fresh frames in one renderer lifetime with explicit translation/reset controls, preserving existing exports and defaults.
- [x] Verify stationary equivalence, motion/cuts/resets, identity and corruption checks plus renderer regression; document the separate worker-admission gate.

Scope: faithful input recording first. The stationary worker continues rejecting general motion. No SDK quality promotion, live game changes or driver work. Existing shader estimators remain unchanged.

Initial recorder test passes nine cases, including stationary prefix equivalence, translation, explicit/automatic resets and source/material/settings identities. SDK output is not involved. Added offscreen-geometry identity, rotated view-Z motion, invalid rechecksummed settings and case-insensitive output collision rejection before final regression. No compile/runtime error or tolerance relaxation occurred; an intermediate misplaced JSON field was caught and moved before any build/run.

Final acceptance: full x64 Debug/Release renderer suites pass 11/11; x86 Debug/Release RR input/recording subsets pass 2/2. Optional Release SDK regression passes 4/4 with raw SDK/zero-light quality failures still explicitly reported. Full optimized-Python recorder verification passes ten cases, 21 malformed recordings and ten invalid mode/path checks (Debug rr-record-88to_qyf). Other artifacts: x64 Release rr-record-17r75bt1, x86 Debug rr-record-9_51djnp, Release rr-record-qeivvsju. Stationary/moving/rotated-depth recordings match all four configurations byte-for-byte. See docs/RR_RECORDING.md. Next is explicit native/managed admission of RRTRRC01 and actual SDK camera-motion/disocclusion tests, not quality promotion. Current milestones manually reviewed complete; the skill helper does not parse these checklist headings.

## RR stationary history sprint

- [x] Define and validate a checksummed 2..8-frame stationary sequence contract; reject gaps, changed guides/cameras and missing reset provenance.
- [x] Reuse bounded typed textures and one supervised SDK context for sequential fenced dispatches; preserve reset-only compatibility.
- [x] Verify repeatability, temporal influence, reset isolation, malformed sequences and cleanup in Debug/Release; document quality separately.

Scope: offline stationary history first. Existing exporter only captures the final requested frame, so build sequences from independently verified deterministic prefixes with strict matching guides/camera/seed. Camera motion/disocclusion sequences require a later explicit recorder; do not fabricate those histories. No live game integration, driver changes, budget increases or quality promotion.

Initial compile: vector allocation using size_t(size) triggered C++'s function-declaration ambiguity. Replaced with static_cast<size_t>(size); no runtime/SDK failure involved.

Final acceptance: optional SDK CTests pass 4/4 in Debug and Release; normal x64 Release renderer CTests pass 10/10. Optimized-Python full sequence checks pass. Reports: Debug rr-sequence-h1u2u4h7, Release rr-sequence-wdl___wc, optimized Release rr-sequence-cd7frnye. Each sequence report rejects 17 malformed inputs, 13 reports and five outputs, and retains failed-zero-light-oracle. Resource reuse, temporal influence, reset isolation and SDK crash recovery pass. See docs/RR_SEQUENCE.md. Next: renderer-owned sequence recording with complete scene/settings identity before camera motion/disocclusion and high-sample quality acceptance. Checklist milestones were reviewed manually; the skill completion helper does not parse this plan's heading/checklist style (0/0 phases).

## RR isolated dispatch sprint

- [x] Verify pinned dispatch/resource contracts and implement bounded packing/validation.
- [x] Execute a reset-only 128x96 indirect-diffuse dispatch inside the supervised SDK child, with explicit GPU lifetime and readback checks.
- [x] Verify input/output, failure containment and baseline compatibility; document execution separately from image-quality acceptance.

Scope: one-frame offline research only. No game integration, persistent history, driver update, cap increase or denoiser promotion. Retain exact pinned SDK workarounds and raw failure reporting.

First isolated run: typed upload/readback checks pass; SDK Dispatch returns 0 and the GPU fence completes, but strict output checks fail (nonfinite/negative RGB or alpha mismatch). No accepted image was written. Add precise channel/pixel diagnostics before deciding whether the cause is a packing, SDK or contract issue; do not relax acceptance blindly.

Resolved: the documented preserved output alpha must be initialized, rather than poisoned. Seeding alpha with packed input distance while retaining poisoned RGB produces a complete finite output; input textures are unchanged. First managed reset dispatch succeeds with existing reporting workarounds, 1,900,544 external allocation bytes and 20 MiB callback peak, all resources released. Raw SDK acceptance still fails; image quality is not yet accepted. Add independent packing/output/failure tests next.

Quality finding: the strict zero-light oracle fails; SDK output has a positive floor up to 1.090765e-5 (MSE 9.6027e-11) on the black-indirect fixture. Preserve the exact-zero requirement as a separate --require-zero-light gate, record its failure, and finish execution/containment evidence before returning that quality failure. Do not clamp away the bias or promote RR as a quality improvement.

Final execution acceptance: optional SDK CTests pass 3/3 in Debug and Release, including 11 dispatch cases, 18 malformed reports, nine malformed inputs and six malformed outputs. Optimized Python passes execution checks; normal x64 Release renderer CTests pass 10/10. Final reports: Debug rr-dispatch-_ol2jef3 and Release rr-dispatch-ajfh25q9. Both retain failed-zero-light-oracle and raw SDK acceptance failed. See docs/RR_DISPATCH.md. Next: bounded sequence/history provenance, temporal RR tests and high-sample quality investigation; no default promotion or live game integration.

## RR input preparation sprint

- [x] Verify pinned SDK signal conventions and choose a bounded input/export contract.
- [x] Implement fresh diffuse/hit-distance separation and matched camera/material guides without changing legacy defaults.
- [x] Test numerical inputs, repeatability and baseline compatibility; document remaining texture/dispatch gates.

Scope: input preparation only; preserve the supervised SDK boundary and raw failure evidence. No installed games, driver changes or SDK dispatch claimed.

Final acceptance: separate 128x96 GPU preparation/export passes 15 CPU-oracle scenarios in all four configurations, including final matrix consistency checks (maximum normalized error 1.54973e-6). Ten malformed files reject. Evidence: x64 Debug rr-inputs-zbnlbnpi, Release rr-inputs-60ribafz; x86 Debug rr-inputs-_ega9x02, Release rr-inputs-wy0abny6. All nine baseline renderer/authoring tests pass in each configuration; x64 full CTests pass 10/10 and x86 input tests pass separately. All five baseline compute DXIL files and all 53 historical outputs remain byte-identical (temporal-tfxl8br7). SDK probe/worker CTests remain 2/2 in both builds, with raw SDK acceptance still failed. Typed textures and actual SDK dispatch remain subsequent milestones, not implied by the diagnostic export.

Corrections during this slice: broad file discovery included build artifacts; narrowed scope. One exact-context patch failed without changing main.cpp. Fixture mutation found immutable vertices and then sampler tuples; recursively converted the fixture to mutable lists. A new extent-rejection fixture used the wrong resized signature; inspected and corrected it. No renderer tolerance, SDK acceptance or quality gate was relaxed.

## RR issue-resolution sprint

- [x] Audit the public API wrapper/descriptor contracts and correct any client-side misuse.
- [x] Establish valid resource accounting and safe failure containment without claiming the SDK binary itself was patched.
- [x] Add repeatable acceptance/recovery tests, run Debug/Release, and update the next input/dispatch milestone.

Outcome: supervised context policy passes with exact hash-pinned reporting workarounds; raw SDK acceptance remains failed. Native job containment covers deadlines, output overflow, SDK crash and assigned-child cleanup on parent exit. Callback peak remains 20 MiB with six allocations/releases and zero outstanding bytes. Both optional CTests pass in Debug/Release; x64 Release baseline passes 9/9. Next is the fresh diffuse/matched-guide input slice, then actual isolated dispatch and quality acceptance. No renderer/game integration or SDK binary repair is claimed.

User explicitly requested fixing the issues and proceeding. Preserve the strict raw SDK diagnostic evidence; any workaround needs its own clearly labelled acceptance criteria. No binary reverse engineering, driver updates or game modifications.

## RR context lifecycle sprint

- [x] Add opt-in 128x96 context creation with pinned provider, validation flags, preflight memory admission and bounded allocation callbacks.
- [x] Evaluate creation/destruction, actual accounting, repeated lifecycles and deliberate budget rejection/failure cleanup in Debug/Release. Mechanics pass; SDK acceptance fails explicitly.
- [x] Record GPU evidence and update the integration plan; keep renderer output unchanged and identify the next input/dispatch gate.
- [x] Qualify a separate managed context boundary using documented accounting/metadata substitutes and process-contained failure. Raw SDK acceptance stays failed; runtime dispatch/integration is still open.

Scope: isolated optional x64 SDK probe. No renderer signal changes, SDK dispatch, full-HD context, driver installation or game modifications in this slice. Enforce a small independent context allocation ceiling rather than expanding renderer budgets.

Initial compile correction: the private context header included standard-library headers inside the caller's anonymous namespace. Moved its include to global scope. Numeric context-option parsing now accepts the entire documented 1..64 MiB range rather than reusing the adapter's 0..31 range.

First context execution terminated with Windows exception 0x0000087d before producing JSON. The 1 MiB preflight rejection succeeds without entering context creation. Added D3D12 message callbacks and creation/allocation diagnostics to identify the exact failure; disabled debugger breaks, not error validation. Removed an unverified exact effect-ID restriction from allocation callbacks (the isolated scope already owns the only context).

Teardown correction: SDK destruction returned OK but left a non-null handle; RAII retried destruction and crashed. Explicitly clear ownership after successful destruction, as the official sample does. Three repeated context lifecycles now release six allocations each, with 20,971,520-byte peak and zero remaining tracked bytes.

Final evidence: Debug rr-context-djpapm3v and Release rr-context-krgbcajb under build/rr-sdk-probe. Both report lifecycle_mechanics pass and acceptance-failed. Post-context memory query returns an invalid near-uint64-wrap total even with default SDK allocators; the metadata query returns 6. Injected second-heap failure crashes the child with 0x87d; a fresh process recovers. Do not loosen these gates or call this working RR rendering. Both builds and the expanded provider/allocator contract CTest pass. Shader/renderer/D3D9 code and default budgets were not changed in this slice.

## Ray Regeneration investigation

- [x] Verify current official SDK/API, hardware, signal and memory requirements; map concrete renderer gaps.
- [x] Implement and test a bounded readiness/probe improvement based on the verified API; do not claim an RR dispatch without one.
- [x] Verify baseline renderer compatibility across all four configurations and preserve the failed experimental quality evidence.

User chose deeper denoiser research and specifically AMD's RR after the third filter experiment. This supersedes the tuning pause below; investigate the SDK path before further custom-filter tuning. Do not install drivers or change games. Existing memory limits and default filtering stay in place.

Result: official SDK 2.3.0 / RR 1.2.0 probe finds provider 4311875584 on the RX 9070 XT and SM 6.6 support. All memory queries pass in Debug/Release; no context or dispatch is implemented. Integration gaps and bounded next slices are in docs/RAY_REGENERATION.md. All nine baseline renderer/authoring tests pass in all four configurations, and Release temporal-flc8v06_ matches all 53 historical files. The variance experiment's mechanics pass in x64 Debug/Release, while its original quality gate still fails. It remains opt-in research, not an accepted improvement.

Next implementation: budgeted 128x96 context admission, fresh indirect-diffuse/hit-distance separation, matched linear-depth/motion/normal/material textures and then actual SDK dispatch. Full-HD memory redesign and RR quality acceptance remain open.

## Phase 5 variance-filter sprint

- [x] Implement the experimental bounded two-stage filter with luminance variance, world-surface rejection and conservative glossy-material support; reuse retired previous-history storage without new full-frame buffers.
- [x] Evaluate an independent CPU reference, raw/history isolation, boundaries, high-sample quality and native/full-HD behavior. Mechanics pass; quality acceptance fails.
- [x] Run all baseline renderer configurations and historical comparisons; document measured quality and reconstruction limitations. Do not promote the candidate.

Scope: an experimental variance-aware two-stage filter, not a complete SVGF implementation or an SDK denoiser. Existing --denoise and default output remain unchanged. Temporal moments are available; short-history/raw input needs a local spatial variance estimate. PBR roughness can conservatively restrict support through existing draw metadata without changing the signal format.

Initial experiment: builds and CPU reference/isolation checks pass, but the first single-pass variance filter fails the quality gate. Across seeds 1/7/23 its BGR8 MSE is 30.47/42.43/35.31 versus the old spatial filter's 29.24/40.62/32.91. Keep the stronger-quality gate intact and diagnose the image regions/weighting before changing the estimator.

Second experiment: expanding short-history variance estimation to 7x7 did not fix the quality regression (31.22/42.54/35.65). Interior/shadow errors are close to the old filter; noisy-centre edge stopping and larger support remain biased around silhouettes. Reconsidered the architecture: two 3x3 stages at steps 1 and 2, with propagated variance and a prefiltered centre in stage two. The old previous-history buffer is dead after temporal resolve and already supports UAV; reuse its temporal slot as scratch, then overwrite it normally when it becomes next-frame storage. This requires explicit state/lifetime/export checks but no new full-frame allocation. Do not ship a quality-regressing candidate as complete.

Third design: two-stage MSE is 29.21/40.80/33.87 across seeds 1/7/23. Its mean 34.63 remains slightly worse than the old filter's 34.26 and fails the unchanged 5% improvement gate. Following planning-with-files' three-attempt rule, paused filter tuning and asked the user whether to continue denoiser research or prioritize material/normal guides. Remaining work in this turn is safety/compatibility verification, not another tuning attempt. The optional flag remains experimental and is not promoted into the default denoiser or registered as passing acceptance. The test now finishes mechanics checks and records their outcome before reporting the unchanged quality failure.

## Phase 5 material/light sprint

- [x] Implement a bounded, checksummed material sidecar and strict JSON authoring compiler; bind by existing material IDs and reject unmatched/duplicate targets.
- [x] Add base tint, roughness/metallic GGX direct shading, emission and diffuse-only one-bounce transport; expose light colour/intensity and ambient controls with correct history identity.
- [x] Verify CPU BRDF reference, localized overrides, malformed inputs, HDR signals, default historical parity and all renderer configurations; document limits.

Scope: optional static material sidecars, no scene-format migration or live material editing. PBR direct lighting plus diffuse-bounce transport is not specular path tracing or glTF conformance. Existing literal-colour capture behavior remains unchanged; factors are interpreted in that working space. Plan tracking separates this bounded feature from later colour-management, normals/maps, advanced filtering and FidelityFX work.

Initial verification: strict authoring CPU tests pass 5/5; default rendering remains byte-identical across all 53 historical files (`build/x64-renderer/Debug/temporal-rriya_x2`). Numerical direct-BRDF checks passed before a transport assertion encountered antialiased silhouettes: the unjittered guide material does not describe every jittered sample. Corrected the oracle to use a silhouette-free ground interior and compare emissive-on/off signals, leaving rendering unchanged. Code inspection also found the per-sample flag mask needed to retain the new colour bit; fixed both configuration and sample masks before GPU acceptance.

Status: implemented. All four builds are warning-free and the nine-test renderer/authoring suite passes in x86/x64 Debug/Release. Final expanded material tests (including repeated full-HD PBR) also pass in all four configurations. Release material evidence: `build/x64-renderer/Release/materials-5869_ix8/verification.json`; x86 Debug `materials-25gnbj_5`, Release `materials-wa1f89a5`. CPU compiler tests pass 5/5; 16 corrupt binary cases reject before pixel output. Numerical direct-BRDF normalized error is below 2.64e-7 on the tested fixture. Final Release historical parity `build/x64-renderer/Release/temporal-fo40zxcb/verification.json` matches all 53 baseline files. Python compilation passes. No installed game or D3D9 runtime/capture code changed; full legacy suites were not rerun, so their prior occluded-Present caveat remains open. Planning-file tracking keeps this opt-in static shading slice separate from full PBR conversion, FidelityFX, live bridging and desktop/game qualification.

## Phase 5 frame-pacing sprint

- [x] Implement waitable swapchain ownership, one-frame admission and responsive message/timeout handling.
- [x] Test paced early close, resize/suspend and wait outcomes; compare output with unpaced/headless results.
- [x] Run renderer build/test matrices and record evidence and remaining desktop qualification limits.

Existing comparison-window diagnostics remain explicitly unpaced because they issue additional synchronous verification presents. Normal native viewing defaults to paced; a documented opt-out retains the previous path. No claim of measured scanout/input latency is implied.

Initial Debug evidence: `build/x64-renderer/Debug/pacing-1jusmly9/verification.json`. Exact seven-sample parity across headless/unpaced/paced/repeated resize lifecycles at three sizes through full HD; smaller cases also compare float signal bytes. All three synthetic wait outcomes pass independently of the real DXGI gate. A zero-target RenderTo assertion found while deferring sample one was fixed by skipping the initial render call, preserving RenderTo validation. No shaders, scene/signal formats, budgets or D3D9 code changed.

Status: implemented. Final four builds are warning-free and all seven renderer tests pass in x86/x64 Debug/Release. Final pacing evidence: x64 Release `pacing-s9rbk9t0`, Debug `pacing-ch0lc79k`; x86 Release `pacing-prej64ix`, Debug `pacing-zc77p8rv` under their build/configuration folders. Historical parity `build/x64-renderer/Release/temporal-yk7ybp2w/verification.json` compares all 53 prior files byte-for-byte. Python compilation passes. Full legacy suites were not rerun in this renderer-only slice; the previous six occluded-Present failures remain an open qualification item, not a new failure or a claimed fix. Planning completion helper still reports 0/0 for this project's heading convention; the three current checklist milestones were verified manually.

## Current state

Phases 1/2 and the first Phase 3 capture/replay, Phase 4 offline-mod and Phase 5 static-DXR slices are implemented and tested. Broader extraction, full path tracing, live integration and real-game qualification remain open.

## Phase 5 asynchronous submission/readback sprint

- [x] Introduce a bounded command allocator/list ring with fence-gated reuse and per-slot constants/timestamps.
- [x] Remove per-sample native readback; drain safely for explicit snapshots, resize, export and teardown.
- [x] Exercise asynchronous control/resize paths and compare checkpoints, final pixels and signal exports with synchronous baselines.
- [x] Run build/test matrices and document evidence, legacy qualification status and pacing limits.

Status: implemented and renderer acceptance passes in all four configurations. One ordered direct queue retains temporal dependencies; bounded CPU/GPU overlap is not parallel temporal evaluation or a live-game bridge. Full legacy qualification still has the recurring occluded-Present caveat.

Initial Debug acceptance: `build/x64-renderer/Debug/async-44rkl_nb/verification.json`. At 128x96 the control test queues 129 samples with six explicit renderer readbacks, versus per-sample readback previously. Early close queues seven samples and reads once at exit; pixels/signals match headless seven-sample output. All four slots are used, measured pending submissions never exceed four, every sample timestamp is retired, resize/control resets preserve reference output, and 1920x1080 remains below 512 MiB. Renderer constants add 768 requested bytes; signal layouts and shaders remain unchanged.

Final evidence: `build/x64-renderer/Release/async-4noh41bt/verification.json`; early close also verifies that a queued-but-unrendered mode change does not relabel output. Historical parity `build/x64-renderer/Release/temporal-xkf1p403/verification.json` matches all 53 baseline files byte-for-byte. Four builds are warning-free and all six DXR tests pass in x86/x64 Debug/Release; both full x86 runs finish 10/16 due to the same six legacy capture/mod/proxy cases. Fresh Debug trace `verify-classic-z7ei6shp/capture.rrt.jsonl` has 12/12 Present results 141953144 (S_PRESENT_OCCLUDED). No capture semantics or legacy code changed. Python compilation passes. Planning-file tracking kept the legacy caveat separate from the completed async implementation.

## Phase 5 native presentation sprint

- [x] Add GPU-buffer-to-swapchain presentation with explicit barriers/fences and bounded display allocations.
- [x] Connect window paint/resize/minimize/restore/occlusion handling; retain GDI fallback and headless output.
- [x] Verify actual back-buffer pixels against headless output, including non-aligned widths, resizing and repeated lifecycle changes.
- [x] Run all configurations and update evidence, deployment instructions and remaining synchronization limits.

Status: implemented and native-renderer acceptance passes in all four configurations. Full legacy-suite qualification remains open under the recurring S_PRESENT_OCCLUDED condition below. This slice establishes standalone presentation ownership; asynchronous buffering and live game injection are not included.

Initial evidence: `build/x64-renderer/Debug/presentation-46or8aea/verification.json`. Five native cases (128x96 and 257x129 albedo/GI, 1920x1080 GI) each verify 21 display submissions pixel-for-pixel, both back buffers, three resizes and suspend/restore handling. Headless/GDI images match. Full-HD peak including enlarged display buffers and diagnostic readback is 525,341,028 bytes, below 512 MiB; rejected display growth leaves prior buffers usable. Hidden-window tests do not establish real scanout, desktop occlusion, DPI, exclusive fullscreen or device-removal recovery.

Regression audit: all four builds are warning-free; x64 Debug/Release each pass 5/5, x86 Debug/Release each pass all five DXR tests but finish 9/15 overall. Six older capture/mod/proxy tests fail with missing captures/zero committed Presents. Debug classic trace verify-classic-mw51wbg3/capture.rrt.jsonl reports all 12 Present calls as 141953144 (0x08760878), S_PRESENT_OCCLUDED in the installed SDK. Proxy/system pixel equality passes before the successful-Present assertion. An isolated classic rerun, with no other renderer process running, reproduces the same condition. No capture/proxy/sample code or S_OK semantics changed. Full legacy acceptance requires normal presentation conditions and another run; do not label the full suite green. Documentation needed one context-corrected patch; no code changes were necessary for that.

Final Release native evidence: `build/x64-renderer/Release/presentation-qa1p1_w_/verification.json`. Historical parity: `build/x64-renderer/Release/temporal-1fkn55n6/verification.json` (53 files identical). Python compilation passed. Guides/phase plan cover six-shader deployment, the --gdi escape hatch, fail-fast display bounds, synchronous/readback limits and precise hidden-window qualification.

## Phase 5 compact-buffer/full-HD sprint

- [x] Separate an 88-byte current working record and 64-byte temporal records from the 144-byte diagnostic format; retain float32 data and raw results.
- [x] Generate diagnostic exports in bounded chunks on demand instead of retaining full-frame export/readback copies.
- [x] Validate full-HD rendering, exact diagnostic parity, temporal rejection/variance, and memory accounting under the unchanged limits.
- [x] Run all configurations, update the guides and assess the next native-presentation boundary.

Status: complete for this slice. All four builds are warning-free; x86 Debug/Release each pass 14/14, x64 Debug/Release each pass 4/4, on RX 9070 XT with standard D3D12 debug-layer validation. Native swapchain presentation remains a separate integration step; this slice removes the known full-HD allocation blocker without increasing budgets.

Parity finding: the initial 80-byte candidate passed acceptance but reconstructed motion from rounded stored world positions. Historical artifact comparison exposed tiny projection changes and different temporal acceptance at frustum boundaries. Retaining the original float32 motion pair (88-byte working record) plus packed integer validity/count/reason metadata restores exact matching. All configurations were re-run on this final layout.

Evidence: `build/x64-renderer/Release/resolution-gaes_1le/verification.json` proves full-HD four-sample temporal/spatial GI at 497,681,520 requested bytes (474.63 MiB), or 502,399,856 bytes (479.13 MiB) with export. A 298,598,436-byte full-HD RRTSIG02 dump validates through the streaming inspector in 127 chunks. The 257x129 tail/late-corruption checks pass; the 2560x1440 fixture still rejects before output creation. `build/x64-renderer/Release/temporal-0yv_0b_r/verification.json` records all 53 historical scene/pixel/signal files byte-identical with the pre-refactor baseline.

Next gate: standalone native D3D12 swapchain, retaining headless readback as the oracle; test back-buffer ownership, resize, minimize/restore, occlusion and cleanup before buffered/asynchronous presentation. No live game bridge, title qualification, FSR or radiance cache is implied. Planning-file recovery and these gates kept the implementation within the compact-buffer slice.

## Phase 5 temporal-reuse sprint

- [x] Double-buffer temporal signals; reproject a fresh sample against previous surface guides, without re-averaging cumulative radiance.
- [x] Reject mismatched surface/depth/projection history and invalidate on lighting/settings/camera cuts; bound history and track luminance moments.
- [x] Extend versioned diagnostics and GPU acceptance for motion reuse, disocclusion, resets, variance, determinism and quality.
- [x] Run all build/test configurations and update the renderer guide and next gates.

Status: complete for this slice. All four builds are warning-free; x86 Debug/Release each pass 13/13 and x64 Debug/Release each pass 3/3 on RX 9070 XT with standard D3D12 debug-layer validation. Static opaque geometry and camera-only motion remain the contract. Temporal reuse is opt-in; no FidelityFX or live-game integration is implied.

Temporal acceptance issue resolved: the first suite incorrectly expected 18 valid temporal invalidations. Returning from a non-GI mode has no valid temporal buffer to discard; the tested diagnostic correctly reports 18 raw resets and 17 temporal invalidations. Fresh-render equality checks remained in place.

Evidence: `build/x64-renderer/Release/temporal-r1d7hezu/verification.json`. Stationary means/second moments match independently computed fresh-sample values; history caps at 32. Moving-camera accepted-pixel float-RGB MSE improves from 0.00028201 to 0.000017343 against 256 samples. Tests identify 1,419 genuinely revealed ground pixels behind the old foreground and require all to reject old history, even with matching draw/material/normal. Overall fixture acceptance/rejection: 9,111 accepted, 1,449 depth/position failures, 1,728 projection failures. Light/cut/manual resets reproduce fresh renders; raw data remains separate. Release moved/reference PNGs inspected.

Historical limit (resolved by the compact-buffer sprint above): double-buffered 144-byte diagnostic records exceeded full-HD allocation budgets. Synthetic timings and small scenes still do not establish game-scale performance.

## Phase 5 signal/denoising sprint

- [x] Export versioned radiance, albedo, world-normal, linear ray-depth and camera-motion signals with explicit validity.
- [x] Add a separate GPU spatial filter, guided by geometry/material edges; retain raw accumulation and opt-in output.
- [x] Verify finite signals, known depths/normals, motion convention, noise reduction, edge isolation and reset/resource reuse.
- [x] Rebuild all configurations, rerun renderer and legacy acceptance, and document limitations.

Status: complete for this slice. All four builds are warning-free; full x86 Debug/Release pass 12/12 each and renderer-only x64 Debug/Release pass 2/2 each. The previous occluded-display condition cleared without modifying the proxy/capture/sample. This is analytical spatial filtering, not FSR Ray Regeneration or temporal reprojection. Geometry remains static; camera-only motion is not animated-object motion.

Evidence: `build/x64-renderer/Release/dxr-df3x44pj/verification.json`. Filtered one-sample MSE is 29.2402 versus raw 109.3787 against 256 samples; raw lighting/guides remain identical with filtering enabled. Camera motion matches (+6.4,-4.8) pixels; first-frame/background/out-of-previous-frustum signals are invalid, and stationary motion is approximately zero. History diagnostics now cover filter toggles too (152 samples, 18 resets, one build). Export/inspection rejects malformed sizes, NaN, invalid validity flags and overwrite. Debug raw/filtered PNGs visually inspected.

## Phase 5 progressive/interactive sprint

- [x] Keep uploads, BLAS/TLAS and pipeline alive across dispatches; track builds, samples and resets.
- [x] Deterministic stochastic diffuse lighting with a bounded sample count and floating-point accumulation.
- [x] Camera navigation, mode/light controls and correct history invalidation; retain headless use.
- [x] Test repeatability, convergence, camera/light resets and resource reuse on the actual GPU.
- [x] Update viewer instructions and measured limitations.

Status: implemented and new DXR acceptance passes on RX 9070 XT in x86/x64 Debug/Release, including the hidden native-window message-loop test. Preview uses readback/GDI; no live-game swapchain integration or denoiser/FSR claim.

Evidence: `build/x64-renderer/Release/dxr-kz90jed1/verification.json`. 32-sample MSE 3.5835 versus 109.3787 at one sample against the 256-sample reference. Red/blue secondary-bounce gains about 20.6 channel levels. History diagnostic: 136 dispatches, 16 resets, one scene-build submission, unchanged requested buffer allocation. Window test: 33 dispatches, four resets, byte-identical restored result. PNG inspected.

Historical qualification caveat for the progressive sprint: x86 Debug and Release each passed 6/12 because Present returned `S_PRESENT_OCCLUDED` (0x08760878), not S_OK. No capture frame was committed; proxy/system pixels still matched. Resolved by a normal-presentation rerun in the subsequent signal/denoising sprint: both full suites now pass 12/12 without capture/trace/sample changes.

## Phase 5 DXR first-render sprint

- [x] D3D12 adapter selection, DXR 1.1 / shader-model capability report and clear unsupported-device handling.
- [x] Bounded scene upload, BLAS/TLAS builds and inline-ray-query compute renderer.
- [x] Captured camera/texture/geometry import; albedo and geometric-normal diagnostics, simple directional relighting/shadows.
- [x] Native preview/readback, repeatability, modded-scene and GPU validation tests.
- [x] Renderer documentation, measured evidence and explicit limits.

Status: complete for the first static renderer. All twelve x86 tests and both x64 renderer tests pass in Debug and Release. Existing D3D9 raster replay remains the accuracy oracle and fallback tool. No live-game or full path-tracing claim.

Phase 5 evidence: `build/x64-renderer/Release/dxr-_9iqyq5w/verification.json`. Ground/occluder albedo matches exactly, 240 pixels receive localized shadowing, point/linear perspective cases stay within two levels, real mod output imports successfully, and standard D3D12 debug-layer checks pass. Preview images inspected. GPU timing is instrumented; game-scale performance is not qualified.

## Phase 4 offline replacement sprint

- [x] Versioned manifest and dependency validation; priorities, conflicts and unmatched-target diagnostics.
- [x] Editable mesh/texture extraction and bounded texture/mesh/material replacement loading.
- [x] Match against original capture IDs, then compose replacements into a new validated scene without modifying inputs.
- [x] Native replay tests proving intended changes and byte-identical unaffected regions across captures.
- [x] Creator quickstart, example workflow, status and limitations.

Status: complete for the offline slice. This stage operates on captured scenes, not live game injection. All ten CTest entries pass in Debug and Release, including all prior fixture fidelity tests.

Phase 4 evidence: Release `mods-classic-4zof63vk` and `mods-ex-mh1zgo4t`; six GPU cases each. Texture replacement changes only draw 0; mesh replacement affects only shared-ID draws 2/3; material replacement affects only shared-ID draws 1/2. Unaffected quadrants have zero changed pixels. Combined output is byte-identical across repeated captures and CLI ordering. Static mesh targeting survives Reset. Nine offline validation test methods also pass.

## Phase 3 implementation sprint

- [x] Capture lifetime-safe CPU-written buffer/texture payloads without retaining native resources or blocking Reset.
- [x] Extract selected-frame triangle geometry, texture content and draw-time fixed-function state; reject unsupported paths explicitly.
- [x] Versioned, bounded scene format and independent native-system-D3D9 raster replay tool.
- [x] GPU fidelity tests including selected frames after Reset, state changes, UP/indexed draws, malformed files and unsupported draws.
- [x] Self-contained unlit glTF export with documented interchange limitations.
- [x] Document supported subset and remaining Phase 3 acceptance work honestly.

**Sprint status: complete.** This does not close the full reference-game/broader extraction acceptance gate.

Design: resource-owned private-data shadows avoid COM pointer reuse and avoid extra native references. Canonical geometry uses XYZ/diffuse/UV vertices and 32-bit indices; the first replay target is an accuracy oracle, not yet the DXR renderer. No commercial game installation will be modified.

## Phase 1 — D3D9 observation

- [x] Lazy system runtime loading and no work under DllMain's loader lock.
- [x] Forward all 119 base device methods and the known resource/swap-chain interfaces.
- [x] D3D9Ex factory/device/swap-chain observation.
- [x] Preserve COM identity, unwrap native inputs, and wrap returned interfaces.
- [x] Device Present, swap-chain Present, Reset and Ex paths.
- [x] Documented D3DPERF exports and a disable escape hatch.
- [x] Exact system/proxy render comparisons using textured geometry.
- [x] COM identity, state-block, failure/reset recovery, resize, and resource-held lifetime checks.
- **Engineering status:** complete.
- **External acceptance:** pending reference-title tests, fullscreen/alt-tab/device loss, and second-GPU qualification.

## Phase 2 — Trace and inspection

- [x] Versioned JSONL format with session object IDs, frame/sequence/thread provenance, and completion status.
- [x] Record resource metadata, lock/update operations, transforms/states, shaders, and draw/present/reset events.
- [x] Determine fixed-function/shader use directly at each draw.
- [x] Opt-in capture, finite frame selection, streaming output, byte budget, and no overwrite.
- [x] CLI validator, inventory, per-frame timeline, and JSON report.
- [x] Repeatability, trace failure isolation, corrupt/truncated records, selected ranges, and byte-limit tests.
- **Engineering status:** complete.
- **Scope:** observations and selected state fields; geometry/texture snapshots and replay fidelity belong to Phase 3.

## Verification

- x86 Debug and Release, Visual Studio 2022, Windows SDK 10.0.26100.0.
- Radeon RX 9070 XT, driver 32.0.31041.1004.
- Current temporal-reuse sprint: thirteen x86 CTest entries pass in both Debug and Release; both renderer-only x64 suites pass 3/3. Actual Radeon DXR and standard debug-layer validation run, not skip. The previous occluded-display failures no longer reproduce.
- Each equivalence capture records 12 presents and 36 draws (24 fixed-function, 12 shader draws), validates one failed and one successful reset, and compares exact pixels with the system runtime.
- Test artifacts are retained in the build tree; no commercial game installation was changed.
- Replay frames 0, 1, 6 and 7 match every BGR byte at 256×192 and 320×240; repeat captures are byte-identical. Ten malformed scene variants are rejected by both readers. Negative shader/state/resource/clear/budget cases are explicit incomplete captures.
- Final Release artifacts: build/x86-vs/Release/scene-classic-iko0j8ys and scene-ex-f720n79u. PNG preview visually inspected; image-diff.json records zero error and matching SHA-256 values.

## Decisions

- Use typed COM forwarding instead of patching runtime vtables.
- Keep tracing optional and separate trace failures from graphics results.
- Keep session wrapper IDs separate from stable SHA-256 asset hashes.
- Qualify external games using measured trace evidence; owned games are candidates rather than presumed compatible.
- DXR captured-scene rendering is implemented; FidelityFX/ROCm integration and live-game bridging remain separate gates in PHASE_PLAN.md.

## Errors resolved this sprint

- RR documentation patch used a shortened README paragraph as an exact context match and was rejected atomically. Confirmed no new file was created, then applied the new document and heading-only README update separately.
- Documentation search initially used docs/PHASE_PLAN.md; the roadmap is at the workspace root. Corrected the path. SDK contents discovery also required explicit array handling/JSON output in PowerShell; the recursive upstream tree supplied exact paths.

- Progressive refactor patch initially mismatched the timestamp validation line; reread the exact source and split the patch. No partial patch was applied.
- Camera-control test key array produced an int-to-UINT narrowing warning; corrected the explicit type. All four final builds are warning-free.
- Previous sprint x86 presentation tests received S_PRESENT_OCCLUDED. Current signal/denoising sprint reruns pass all tests without changing runtime semantics; the display condition no longer reproduces.
- Planning skill completion helper reports 0/0 phases because this project's checklist headings do not use its expected status format; manually verified the four signal/denoising milestones and actual CTest results. No implementation/test failures occurred in this sprint.

- DXR negative-case test tried to modify decoded tuples; converted copied state/matrix fields to lists. Final suites pass in both architectures/configurations.
- x86 DXGI pointer-sized dedicated-memory reporting was misleading for renderer capacity; added an x64 renderer-only preset and explicit process width/reported-memory labels.

- Scene hook build: corrected DWORD to UINT for GetStreamSourceFreq.
- PNG test reporting: corrected a local variable shadowing the encoder and restored capture-map indexing inside its loop. Final full Debug/Release runs pass.

- Initial source replacement patch used unsupported delete/add operations on the same file; changed to a normal update patch.
- Build initially lacked IUnknown in the trace header and attempted to serialize HDC as a scalar; fixed includes and generator policy.
- Vertex-buffer creation initially selected the base resource wrapper; fixed factory ordering to prefer the most-derived interface.
- Older Ninja/Win32 generator cache remains preserved in build/x86; current presets use the verified build/x86-vs directory.

## Radiance Cache presentation and scheduling sprint

- [x] Add an explicit, opt-in GPU apply pass that patches only admitted cache pixels into the renderer's common presentation buffer while preserving an exact no-cache fallback.
- [x] Prove deterministic applied-output identity, unchanged unmapped pixels, failure recovery and default-authority isolation in the renderer-path contract.
- [x] Connect admitted cache work to the native display/frame-admission loop without blocking message handling, then measure scheduling behavior.
- [x] Rebuild all supported configurations, rerun adjacent suites and document the remaining D3D9/live-game boundary.

Status: complete for this slice. Output application and one-frame native scheduled presentation are exact. The worker transaction runs while the UI thread pumps messages, then the admitted candidate passes latency-one swapchain and back-buffer verification. Release and Debug pass all seven RC contracts plus native presentation; Win32 Debug/Release rebuild successfully. Continuous per-frame cache-state reuse remains outside this bounded test.

## Persistent Radiance Cache context amortization sprint

- [x] Extend the contained shared-path worker with an explicit two-epoch stable-frame mode using one process, one context and the existing five shared resources.
- [x] Prove the second epoch begins from the first trained state, changes predictions again, improves the guarded composite, and still resets to the original baseline exactly.
- [x] Add strict report/accounting, repeatability, failure recovery and default one-epoch isolation tests; measure one persistent transaction against two independent launches.
- [x] Rebuild supported configurations, rerun adjacent suites and document the remaining changed-frame bidirectional fence/session boundary.

Status: complete for this slice. Stable-frame process/context amortization, cumulative training, exact reset and failure recovery pass in Release and Debug. Parent-updated camera/frame identities still require a reusable live process session with bidirectional fence epochs.

## Live Radiance Cache fence-session sprint

- [x] Add a reusable RAII isolated-process session retaining the existing handle allowlist, pre-resume job containment, bounded output and deadline teardown guarantees.
- [x] Add a three-epoch shared-fence protocol: initial training, stable-identity continuation, then parent-updated camera inputs with provider reset.
- [x] Prove one process/context, exact stable continuity, changed-frame identity/reset, final composite improvement, timeout/crash fallback and fresh recovery.
- [x] Rebuild supported configurations, rerun adjacent suites and document the remaining D3D9 capture/presentation boundary.

Status: complete for this slice. The bounded three-epoch live process/fence protocol, stable continuation, parent-updated camera inputs, reset, timeout/early-exit fallback and recovery pass in Release and Debug. No D3D9 process or installed game is modified.

## Next phase

## First real-game pass

Latest: capture-to-scene offline adapter complete; see current slice at top.
Explicit digest-scoped assignments work for real v1 and native v2 evidence, with
unresolved draws and atomic rejection. Frame/session-correlated sampling is next;
the older next-step notes below are historical checkpoints.

Resource provenance slice complete: advanced-engine notes archived with qualifications; position v2 includes tracked resource-lifetime IDs, mutation revisions and wrapper-relative reset/knowledge revisions. Reuse/recreation tests preserve native output. Release5/5 (8.11s), Debug2/2 (6.07s); final reader regression3/3 (3.25s). Next explicit instance correspondence and bounded update integration; no game capture requested yet. Engine adapters remain optional/version-pinned. One atomic documentation patch failed on mismatched roadmap context, then succeeded after removing the unnecessary hunk.

User future tracks added: SM3/general D3D9 + UE3 qualification, separate DX10/BioShock-family profiles, DX8 via d3d8to9 and early DirectDraw/D3D≤7 via dxwrapper candidates. See docs/API_ENGINE_ROADMAP.md; no wrapper deployment or broad support claim. Bounded position-geometry cache/explicit instance delta prototype implemented:7 unit tests pass; selected scene/replay/reconstruction CTests3/3 (1.06s). Next capture resource generations/range update provenance and explicit instance correspondence before live integration; do not infer object identity from draw ordinals/content hashes.

Real-input raster validation complete: actual captured constants/corner positions replay on fresh hardware devices against CPU-evaluated passthrough. Three nonempty draws match with zero measured error; one empty draw explicitly excluded from visible validation. Release 5/5 (4.05s), Debug 3/3; report/docs in HL2_RECORDED_POSITION_REPLAY.md. Next useful scene selection/coverage and stable identity/update tracking, then material inputs. No new game launch or expanded shader admission.

Offline reconstruction complete: validated per-draw input/model OBJ exports and grouped provenance manifest in hl2-combined-20260907/reconstructed-grouped. Four draws /57 triangles /127 per-draw unique vertices; identity model rows, two distinct target/clip groups, one fully negative-w draw. Exporter tests and Release position_capture regression pass. Trace ultimately completed normally; game exit0, proxy cleanup verified. Next per-group offline preview/replay, then expanded selection/material inputs, not another blind capture pass.

Offline reconstruction slice: completed trace now validates (60 presents / 13,395 shader draws / zero failed calls), game exit 0 and proxy removed. Export validated position records to separate raw/model-output meshes with provenance and coordinate analysis; do not merge repeated draws or infer materials/world-space semantics.

Combined live capture obtained: four real position draws (57 triangles across draws), validated initialized inputs/constants; inventory 2,919 draws / 49 families / 76 programs, no draw failures. Trace remains empty on two inspections, so trace pass is not accepted; Present-gated activation needs separate diagnosis. Result in docs/HL2_COMBINED_PASS_RESULT.md. Next inspect/reconstruct accepted draws offline; verify normal exit and owned proxy cleanup for running PID45776/session86621.

Combined capture slice implemented and fixture-tested. Exact HL2 position capture + inventory + trace share one runner launch/trigger, with independent bounded windows. Release regression 9/9 (18.88 s), Debug 4/4 (9.05 s); final metadata Release 2/2 (4.19 s), Debug position 2.63 s. Previous ordinary HL2 session closed normally without intervention. Fresh hl2-combined-20260907 pass launched armed after baseline provenance verification. Await user in-game, trigger run name combined, inspect all three outputs, then verify normal exit/owned DLL cleanup. No all-scene or material capture claim.

User roadmap additions (2026-09-07): after individual capture contracts work, unify all supported evidence into one correlated capture session/action and build a capture/authoring workbench UI. See docs/UNIFIED_CAPTURE_UI_ROADMAP.md for sequencing and acceptance. Keep current focus on real HL2 initialized vertex/index/constant capture; UI and session unification are deferred, not started now.

Position numerical slice complete: finite/known-state CPU evaluator with pinned program admission and hardware raster oracle passes 24 variants (34,603 covered pixels, zero measured normalized error) in Release and Debug. Release shader regression 5/5 (6.70 s), Debug position/snapshot 2/2 (1.10 s). Next implement bounded initialized vertex/index range and c0/c4–7/c58–60 capture at an exact matching game draw, retaining reset/state-block/resource identity rejection. No game deployment or live relighting in this slice.

Offline slice implemented: bounded CPU disassembler and hash-selected inventory inspection; selected 612-byte VS position path established (c0 preparation, c4–c7 clip rows, c58–c60 position output). Contract in docs/HL2_POSITION_CONTRACT.md. Release shader suites 4/4 pass (6.52 s), Debug disassembly passes. Confirmed inventory pass exit 0 and owned proxy removed. Next: exact-program position evaluator/native oracle with varied c0/matrices, then bounded initialized input capture; do not equate metadata names with validated world geometry.

Live inventory obtained: 2,996 successful indexed draws, 42 VS / 37 PS / 55 families, normal byte-budget stop; independent 60-Present trace has 10,466 shader draws and no failed calls. See docs/HL2_INVENTORY_PASS.md. Provisional first analysis candidate is 612-byte VS 0c16f3b5... / family 34a26bb2... (231 draws), pending offline position-dependency analysis; no world-geometry claim. User may close HL2; verify runner cleanup after exit. No additional game capture needed for shader analysis.

Current inventory slice implemented and tested: separately gated indexed-draw shader/layout ledger and CPU reader, unchanged fixture pixels, unknown-program snapshot rejection, draw/byte limits and runner trigger lifecycle. Release 9/9 (22.87 s), Debug 7/7 (17.00 s); final extended inventory tests Release 2.20 s / Debug 2.62 s. Fresh hl2-inventory-20260907 pass prepared with baseline provenance and armed launch. Await user in-game, trigger inventory, inspect actual families, then choose the first extraction contract. Unknown programs remain opaque diagnostic data.

Proxy shader integration: opt-in single indexed-draw capture; native-resource-owned initialized-byte shadows with bounded retained memory; constant knowledge keyed by wrapper generation and invalidated on Reset, state-block recording/application and wrapper retirement. Query exact native draw state; commit only successful draw. Test proxy capture vs standalone oracle, failed/undefined/state-block/reset paths and default-off behavior. No arbitrary HL2 programs or game deployment yet.

Proxy integration implemented and oracle-tested, including reset/state-block/retired-wrapper recovery. Next bounded task: diagnostic inventory of actual HL2 shader bytecode/declarations and program families without admitting unknown code into replay, then select one vertex-transform/layout contract for extraction. No requirement for user game interaction until that diagnostic is tested.

Single-draw shader snapshot implementation: separate C++ bounded snapshot contract, known VS1.1 matrix/color program, FLOAT3 stream and indexed triangle list, explicit initialized-byte evidence. Capture actual device shader/layout/constants at draw boundary; serialize and replay on independent device state. Test changed constants/ranges, malformed artifacts, missing initialization, unsupported layout/program and stale identity. No game proxy hookup until this standalone contract passes.

Standalone implementation complete using exact VS3/PS3 program allowlist (not VS1.1): three captured variants replay pixel-exactly in fresh processes and after Reset, with bounded serialization/negative admission tests. Next integrate evidence tracking at actual proxy draw boundary, including constant initialization/state-block/reset semantics; do not expose arbitrary HL2 shader execution or infer world geometry yet.

Shader audit increment: separate vertex/pixel shader-bound draw populations and inventory declaration/stream/constant evidence in existing traces, with a bounded offline analyzer and synthetic classification tests. Preserve missing state as unknown; do not infer shader bytecode, camera matrices or world-space geometry from hashes/counts. Lower-feature gameplay exited 0 with DLL removed; review/restore backed-up settings now.

Audit implemented: every sampled draw is indexed and VS-bound; full float-update payloads but absent creation snapshots. Graphics level restored to 95; unrelated audio config retained. Next concrete implementation is the single-draw shader snapshot and exact synthetic raster replay gate in docs/SHADER_GEOMETRY.md, before HL2 program-family/world-transform extraction.

HL2 committed target: native low-feature test next, with original graphics config/registry backed up because -dxlevel may persist settings. Installed bin includes stdshader_dx6/7/8/9. Prior gameplay exited/cleaned successfully. If low-feature mode yields fixed-function draws, measure capture admission; otherwise proceed to an explicit shader-aware geometry contract, not another title by default.

Low-feature baseline launched in hl2-dx70-20260907 after cfg/registry backups (settings-before). Await normal exit and user visual/stability report, then trace same-scene low-feature coverage. Restore original settings after experiment with game closed and reviewed changes; no game assets/binaries replaced.

Low-feature baseline passed exit 0 and user acceptance. Lower-feature gameplay proxy now armed for 60 frames; await "in game", trigger hl2-dx70-20260907/gameplay, inspect fixed/shader coverage, then verify exit/cleanup. Settings restoration remains outstanding.

Lower-feature capture complete: 60 presents / 11,424 shader draws / 0 fixed draws / 0 failures. This path does not unlock existing extraction. Next confirm exit/cleanup and restore reviewed original settings, then audit vertex/pixel bindings, streams/declarations/constants and define bounded shader-aware geometry capture. HL2 remains user-selected target.

Gameplay-trigger increment: add opt-in bounded trigger-file admission at successful Present boundary, preserve existing fixed-frame/default traces, verify delayed and never-triggered cases on harness, then prepare a new hash-pinned HL2 pass. Do not infer gameplay content from menu traces or bypass baseline provenance after rebuilding proxy.

Trigger increment implemented/tested Release+Debug; HL2 gameplay run armed in hl2-gameplay-20260907, 120 frames, no scene assets. Await user-confirmed loaded scene, trigger, inspect actual gameplay draw coverage, then normal exit/cleanup. Previous native/proxy/disabled controls all passed exit/visual review with owned DLLs removed.

Gameplay trace obtained after user trigger: valid 64 MiB byte-limit stop at 82 presents / 28,633 shader draws / 0 fixed draws / 0 failures. Next confirm exit/cleanup, then select supported low-feature rendering experiment or define shader-aware capture scope; do not assume existing fixed-function extraction can reconstruct this scene.

Verification: classic DX9 workflow/proxy/scene checks pass 3/3 in Release and Debug after making the harness visible. Present retries are bounded to three seconds and do not repeat draws. D3D9Ex still returns S_PRESENT_OCCLUDED with the native system runtime and is explicitly not requalified; runtime S_OK-only frame semantics remain unchanged.

- [x] Inventory installed owned candidates and choose a concrete qualification target from local evidence: user supplied original BioShock 2 on O:, single-player SP/Builds/Binaries/Bioshock2.exe.
- [x] Build a reversible baseline/proxy observation runner with executable/proxy provenance and bounded reports.
- [x] Verify the complete classic D3D9 game-pass workflow on the harness and rebuild Release/Debug proxies.
- [x] Reach a concrete real-title pass: original BioShock 2 SP untouched baseline launched on 2026-09-07; user gameplay review and normal exit requested.
- [ ] Review baseline outcome and API mode, then run the bounded proxy/disabled comparison on the same scene.

HL2 controlled native baseline passed (exit 0, user acceptance). First game-root proxy deployment launched; initial process uses system d3d9.dll and produces no trace. Next: normal exit, verify owned-DLL cleanup, investigate load-path mismatch. Do not treat deployment alone as proxy qualification.

Resolved placement: root attempt exited/cleaned; explicit guarded bin option passes workflow tests and loads in HL2. proxy-bin captures 300 presents / 20,387 events, footer frame_limit. Await user visual comparison and normal exit/cleanup; then disabled pass and representative gameplay trace/extractability checks remain.

BioShock DX9 gate failed: untouched -dx9 run crashed with 0xC0000005 after 73.516 seconds. Default run passed. Pause its proxy comparison; investigate another native DX9 candidate before considering a separate BioShock crash diagnosis or DX8 translation expansion.

HL2 next: prepared build/game-passes/hl2-20260907 with observed -steam -game hl2_complete arguments. User reports native gameplay works; system D3D9 and shaderapidx9 plus Steam overlay verified loaded. Existing HL2 process prevents a clean comparison. User will disable overlay; after normal exit rerun harness, then controlled baseline and proxy. Latest harness baseline failed while HL2 was running; do not claim readiness until rerun passes.

Priority: real-title qualification now takes precedence over optional radiance-cache refinements. A first game pass establishes baseline/proxy behavior and draw extractability; it is not a claim of live relighting support.

2026-09-07: user supplied O:/SteamLibrary/steamapps/common/BioShock 2. Single-player executable exists and no local d3d9.dll was found. Preparing untouched baseline; interactive scene review remains needed before proxy qualification. Multiplayer is out of scope.

## Renderer-owned commanded cache session

- [x] Connect renderer GPU regeneration and admission decisions to the commanded provider loop.
- [x] Exercise coalesced camera requests, stable continuation and return-to-base reset with one process/context.
- [x] Verify shared output, allocation bounds and failure recovery; record presentation boundary.

Renderer-commanded session slice complete: Release/Debug path contracts pass in 53.33/53.29 s with D3D12 validation. Coalesced input is consumed, reset/continuation and refreshed counts are exact, and no per-epoch renderer GPU buffer allocations occur. x64 Release/Debug and Win32 Release builds pass. Next: apply/present each admitted result while keeping this session alive, then connect UI and D3D9 input. Completion helper retains the 0/0 checklist-format limitation; these milestones were manually checked.

## Whole-project checkpoint and provider protocol

- [x] Publish a concise current-status map separating harness completion from real-game acceptance.
- [x] Add a parent-commanded provider epoch loop with continue/reset/stop and bounded protocol validation.
- [x] Exercise the loop on real shared GPU buffers and record remaining runtime integration work.

Checkpoint/session slice complete: Release path contract passes in 43.25 s and Debug in 45.64 s. Parent-commanded R/C sequences preserve trained state, reset exactly, stop after verified context destruction and match final shared-output readback. Bounds, invalid input, low-budget/timeout failure and recovery pass. The new loop still uses static exported-fixture inputs; next wire it to queued renderer input, then the D3D9 runtime bridge and real-title qualification. Planning helper retains the 0/0 checklist-format limitation; these three milestones were manually verified.

## Stateful RC buffer reuse

- [x] Extend the bounded pool to shared/default-heap buffers with exact descriptor matching.
- [x] Restore known end states and fence completion before recycling; invalidate on failure.
- [x] Prove pooled/unpooled equivalence across repeat, failure and changed-camera/live work.

Stateful buffer reuse complete: eight-transaction GPU-pool equivalence passes in Release (31.30 s) and Debug (35.25 s), with the D3D12 debug layer enabled. x64 Release/Debug and Win32 Release builds pass. Evidence: 31 allocations, 78 reuses, seven fenced restore submissions/61 buffer states, exact budget return. Next is generalized provider epochs and continuous consumption of pending UI requests. Completion helper retains its 0/0 checklist-format limitation; these milestones were manually verified.

## RC staging buffer reuse

- [x] Add a bounded reusable pool for upload/readback buffers with invariant resource states.
- [x] Prove allocation reuse and failure recovery on repeated same-renderer transactions.
- [x] Validate and document reuse limits before pooling stateful GPU resources.

Staging reuse complete: Release path contract passes in 31.04 s and Debug in 32.73 s; x64 Release/Debug and Win32 Release builds pass. Canonical pool has 11 allocations, 17 reuses and 246,784 retained bytes, with exact budget return at teardown. Shared/default-heap state restoration and generalized provider epochs remain next. Completion helper retains the 0/0 checklist-format limitation; these three milestones were manually verified.

## Cache resource lifetime

- [x] Give RC temporary buffers explicit scope ownership and return their budget charges on release.
- [x] Exercise repeated work, failure and recovery on one renderer with exact live-byte checks.
- [x] Verify GPU contracts and document the remaining provider protocol work.

Resource lifetime slice complete. Release path contract passes (24.74 s); Debug path/native contracts pass (30.89 s). x64 Release/Debug and Win32 Release builds pass. Same-renderer six-transaction probe returns to 2,967,408 live requested bytes with a 5,847,928-byte peak. Buffer pooling and generalized provider epochs remain next; this change releases/reclaims transient resources rather than reusing them. Completion helper still reports 0/0 for this checklist format; three milestones manually checked.

## Renderer cache admission policy

- [x] Implement a latest-request mailbox with one active epoch, stale-result rejection and explicit identity changes.
- [x] Connect it to the native RC presentation loop and test queued camera changes and close behavior.
- [x] Verify affected contracts and document the remaining persistent interactive provider boundary.

Admission slice complete. Release/Debug path and native presentation contracts pass; final HWND-guard Release path rerun passes in 30.76 s. x64 Release/Debug and Win32 Release builds pass. The latest pending request is retained/reported but not executed by this bounded harness. Next: reusable GPU resources and generalized provider epochs to consume queued input continuously. The planning helper retains its 0/0 checklist-format limitation; these three milestones were manually checked.

## Live session polling hardening

- [x] Add nonblocking fence polling with output draining and overflow enforcement.
- [x] Exercise live-session timeout, crash and verbose-worker behavior.
- [x] Run affected contracts and document results before interactive-loop integration.

Polling hardening complete: rc_worker_boundary and rc_path_sequence_contract pass in Release and Debug; x64 Release/Debug and Win32 Release builds pass. Normal polling is nonblocking; failure teardown remains bounded and must run off the UI thread. Interactive-loop scheduling remains the next implementation stage. Completion helper still reports 0/0 for this checklist layout; all three items manually verified.

Discovery errors: isolation tests are in verify_rc_worker.py, not verify_rc_isolation.py. An initial planning patch used the wrong findings heading; corrected after inspection.

Next renderer stage: move the proven fence/session state machine into the interactive renderer loop with bounded back-pressure and explicit camera/lighting/material identity policy. Then connect captured D3D9 Present/Reset events to that scheduler and qualify an owned reference game. Stronger variance-guided filtering, richer normal/material guides and colour management remain parallel quality work; no commercial installation has been changed.
