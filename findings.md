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

# Findings & Decisions

- V18 UpdateSurface covers explicit initialized source regions independently of
  dirty flags. Canonical COM identity resolves mip ownership; native success and
  stable epoch/revisions/no gaps or open accesses establish destination coverage.
  Complete chain coverage is mandatory;128-entry history storage is charged to
  the existing shadow budget. Unsupported/failed copies discard the evidence.
- Python independently validates per-mip coverage, bounds, block alignment and
  source-extent consistency. UpdateTexture initialization is not mixed implicitly
  with partial surface history. Transitioning back to a full upload is qualified.
- Split texture matrices into independent fresh CTest jobs. Release core capture
  fell to41.09s;14/14 regressions passed166.82s.51 native/proxy scenarios and32
  isolated replays passed. Next useful gate is the comparator's128x96/fixed-state
  restriction versus saved5120x1440 gameplay evidence, not another blind game run.

- V17 separates SYSTEMMEM byte initialization from dirty proof: exact
  NO_DIRTY_UPDATE writes establish known rows while preserving, not creating,
  dirty proof. Full AddDirtyRect preserves bytes and establishes notification
  proof; partial notification cannot create full proof. Invalid/failed calls,
  pending writes, epoch and overlap/history gaps invalidate conservatively.
- V17 transfers serialize creation/top_lock/notification proof separately from
  source byte revision. V16 serialization and runtime rules remain unchanged.
  Focused RGBA/DXT1/3/5 fixtures passed exact-byte, native/proxy hash, isolated
  replay and negative checks. UpdateSurface/partial reconstruction remains next.

- V16 whole-chain upload admission needs initialized source bytes AND full-dirty
  proof. D3D9 clears source dirty regions on UpdateTexture; every observed attempt
  consumes proof conservatively. Creation/whole top-level writable lock can prove
  full dirty; lower-only/partial writes cannot restore it. Destination revisions,
  epoch and process overlap guard the native call. Default bytes are independent
  copies with source identity/revision provenance; managed shape is unchanged.
- Focused upload suite passed after replacing a null-destination failure control
  (native runtime fault) with an invalid-pool call using real resource objects.
  Exact blocks, source mutation isolation and native/proxy image hashes verified.
  Explicit AddDirtyRect and UpdateSurface/partial propagation remain next.

- V15 adds DXT1/DXT3/DXT5 only with the external-asset prerequisite. Shadow
  units are either pixels (RGBA) or4x4 blocks (DXT), with per-unit bytes and tight
  columns/rows. Whole tiny mips and fully block-aligned rectangles are admitted;
  other writes invalidate. Shared memory, per-chain and external asset budgets
  remain unchanged. V13/v14 keep their uncompressed format restrictions.
- Initial native compressed capture run passed:12 accepted full/partial/readonly/
  alias-refresh cases across3 formats, exact blocks across16 draws each,57 replay
  comparisons and30 baseline/proxy image-hash comparisons. Eighteen rejected
  write cases,24 malformed evidence cases and6 legacy-format rejection runs.
  DXT2/DXT4 remain rejected. Next default-pool/update paths; no new HL2 pass yet.

- Compressed native replay uses tight block rows (8 bytes DXT1,16 DXT3/DXT5),
  rounded-up4x4 blocks even for1x1 mips, and positive checked native pitch.
  Every uploaded mip is byte-verified with a read-only lock. Base dimensions
  must align to4; maximum mip count and chain budget reject before GPU creation.
- Twelve synthetic cases passed the initial native run, including final1x1 LOD
  and DXT1/3/5 alpha. Native sampling is shared; v13/v14 capture admission remains
  unchanged. Next compressed write tracking needs new-version admission and
  aligned partial/full/tiny lock evidence before a useful HL2 pass.

- V14 external mips use a newly owned <ledger>.assets directory and hash-only
  filenames, <=16MiB/texture and256MiB/512 files per session. Existing paths are
  never overwritten. Failed writes charge reservations; unreferenced orphan
  assets can remain after rejected draws and are not accepted evidence.
- Reader/importer validate hashes and dimensions, cache immutable verified bytes
  per inspection, and retain compact references. Pixel replay resolves v13/v14
  snapshots before native restoration. Formats/pools remain the v13 managed
  uncompressed subset; compressed/default-pool/update qualification is still next.

- Pixel reconstruction: express the lightmap path as separable cubic B-spline
  weights (w0..w3), paired positive/negative sample positions and four samples,
  then base/tint/vertex color, lighting scale and squared saturated fog. Preserve
  bytecode-owned1024x512 reference dimensions regardless of bound texture extent.
- First restored v13 draw matched at1.42296e-8 maximum normalized error. Native
  original and reconstructed PS use the same original VS and restored sampler/
  texture inputs; comparison is isolated with depth/blend off, not full frame.
- Resolved implementation issues: C++ namespace and DWORD/std::max typing;
  teardown crash from texture COM resources outliving Device/runtime unload.
  Crash localization ruled out the initial shader-profile hypothesis. Resource
  ownership now guarantees release before runtime unload. Reconstruction uses
  ps_2_b; no production proxy/capture hook changes in this slice.

- Final wrapper audit also added BaseTexture9 GenerateMipSubLevels to observed
  writer invalidation; derived texture interfaces were already covered. The
  generated-interface audit now explicitly checks this base-interface path.

- V13 texture admission is deliberately bounded to observed private managed,
  usage0 A8R8G8B8/X8R8G8B8 textures, complete mip chains <=64KiB each. This keeps
  two hex-encoded snapshots plus the largest v11 draw inside the1.2MB row bound.
  Larger game textures need a bounded external asset store before another HL2 pass.
- Writable direct lock rectangles establish initialization only after successful
  unlock. Row padding is excluded. Read-only direct locks preserve existing
  knowledge. Failed locks/unlocks, unsupported flags, copies, generated mips and
  surface-alias writes invalidate; alias writes are not reconstructed. Managed
  usage0 admission excludes render-target/depth and shared/default-pool paths.
- Texture reset epochs invalidate lazily. Metadata-only v12 descriptors continue
  to say contents unknown; v13 texture_inputs carries the separate initialized
  snapshot/digest evidence and must match the same draw's sampler identities.

- V12 implementation: descriptors and effective sampler settings can be queried
  without claiming initialized texels. PS c11/c12/c29/c30 require successful writes;
  state blocks/reset invalidate knowledge. Resource IDs are process/session-local
  observations, not content hashes, texture revisions or persistent asset IDs.
- Texture SetLOD/SetAutoGenFilterType previously lacked device-state overlap
  guards; added guards to all inherited texture wrappers. V12 rejects any observed
  overlap conservatively. Exact paired PS fixture uses the same native PS on both
  vertex paths, so it is not independent PS or full material replay validation.

- V11 material inputs2026-09-08: exact stride48 COLOR0/UV0/UV1 initialized-byte
  contract plus known VS c12/c16. Selected ten output lanes independently validated
  and preserved in scene candidate metadata. Bound1024 triangles keeps rows below
  the existing1.2MB reader limit. Legacy position geometry remains unchanged.
- Native/CPU probes agree with nonuniform clip W, distinct RGBA, out-of-range UVs
  and fog floor. The fog probe uses the duplicate oD1 output; fixed-function fog
  and general oFog rasterizer behavior remain unqualified. Incorrect CPU UV fails.
- Next exact paired PS rows and s0/s1 state/resource descriptors, followed by
  initialized texture/mip provenance and texels. No useful new HL2 pass yet.

- Actual material audit2026-09-08: PS ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11
  pairs with pinned VS in231/294 original/multi-draw inventory draws. It needs UV0,
  UV1, packed vertex color, fog coordinate, PS c11/c12/c29/c30 and s0/s1 contents/
  sampling. Current position evidence cannot reconstruct it. Next UV/color/fog
  output controls before texture provenance. No immediate new game run.
- Shader embeds1024×512 reference scaling for four s1 samples; actual bound extent
  is not recorded. Treat lightmap upscaling separately. User-requested future
  enhancement roadmap prioritizes reversible offline base-color replacements after
  faithful replay; no model/runtime choice or automatic generative material claims.

- v10 complete: Release10/10 (41.03s), Debug4/4 (42.56s), final setter-overlap
  capture reruns Release26.99s/Debug33.26s. Native builds/Python compilation pass.
  Narrow prefixes can now replay actual captured clear/RGBA/blend state with exact
  native-vs-CPU agreement and independent analytic samples. No original game pixel
  readback comparison or real material qualification. Next saved HL2 inventory
  audit; no new gameplay run for this synthetic constant shader. No failures.

- v10 uses exact texture-free ps_2_0 `mov oC0,c0` bytecode, effective pixel c0,
  missing fog/clipping/clip-plane/dither/sample-mask/line-AA states and N-patch mode.
  Supported replay is limited to128x96 A32B32G32R32F, full viewport, no depth/MRT,
  solid/no-cull raster and ADD blending with ZERO/ONE/SRCALPHA/INVSRCALPHA factors.
- Color replay resolves the entire captured prefix from a retained qualified clear,
  not a suffix or a group split on state differences. Initial positive native replay
  and independent alpha-blend/clear probe pass with zero native/CPU error. No game
  shader/material qualification or original-frame pixel readback comparison claimed.

- v9 complete: Release10/10 (40.78s), Debug4/4 (41.68s), native builds/Python
  compilation pass. Positive scopes now prove complete color-write call coverage
  for private standalone RT0; current pixel contents/stateful replay remain
  unqualified. Native texture/MRT/depth/lockable/open-access/overflow exclusions
  and failure preservation pass. No HL2 pass needed until supported pixel replay
  can be qualified. No failures or game deployment this slice.

- v9 scope design uses exclusion to close a bounded subset: native successful
  CreateRenderTarget (or Ex with Usage=0), null shared-handle parameter, nonlockable,
  owner/reset identity, RT0 only and no depth. Texture/volume aliases, backbuffers,
  shared or unknown origins are not admitted. No general alias graph claim.
- Outstanding potential CPU/DC access is tracked independently of the 64-event
  ring in a bounded 64-resource map. Duplicate/unknown/unmatched/overflow access
  sets a sticky gap; failed native calls preserve accounting. Clear and draw both
  snapshot access state and all MRT slots. Full color-call coverage can qualify
  narrowly, but initial pixel contents and stateful replay remain unknown/false.

- v8 complete: full Release10/10 and Debug4/4, final changed-code capture/runner
  checks pass both configurations. Generated-wrapper audit also covers inherited
  Ex and resource interfaces. Native raster equivalence remains unchanged. One
  transient Windows report-read PermissionError was fixed in bounded test polling;
  no production runner safety checks changed. Final HL2 closed/proxy absent.
- Next gate is closed single-target scope qualification, not another immediate
  HL2 run. Mandatory v8 unobserved gaps cannot be removed just because a retained
  clear-to-draw window contains only captured draws. Writable access that began
  before a clear, aliasing and external/shared/MRT writes still require proof.

- v8 design: fixed 64-event process-wide observed-call ring, pre-call target/depth
  lifetime tags, native HRESULT, device/reset/clear provenance and captured ordinal
  references. Complete surface coverage remains false: unobserved/external/shared
  writers, MRT and texture/surface/volume aliasing are explicit unresolved scope.
  Global history intentionally treats unrelated resource writes as blockers.
- Generator audit includes all four regular draws, patches, clears, copy/fill/
  texture updates/readbacks, texture/cube/volume/surface locks and unlocks, DC,
  mip generation/dirty markers, attachment switches, state-block Apply, reset and
  device/swap-chain presentation. ProcessVertices writes VB geometry, already
  invalidated by existing hooks; it does not write a render surface.
- Initial Release v8 native build passes. Scope/gap/history reader and synthetic
  controls added; regression in progress. Git status unavailable because this
  workspace has no .git; an initial wildcard rg lookup was invalid on Windows,
  so subsequent lookups use directory paths with -g filters.

- v7 regression complete: Release10/10, Debug4/4, native builds and Python compilation pass. Clear payload tests preserve native rendering, including failed-clear preservation and successful oversized-clear fallback. No real-game v7 qualification yet; no launch needed until the write-coverage/replay contract is ready.

- v7 latest-clear payload is bounded evidence, not complete write history. A failed Clear preserves prior success; a successful oversized/unavailable clear replaces it with unknown. Initial-content admission must remain false even for a full-target clear candidate until intervening draws/copies/locks/writes are covered. This prevents sampled state from being promoted to false game-frame equivalence.

- v6 native/reader/group/runner regression complete: Release10/10,Debug4/4, unchanged proxy raster equivalence including D3D9Ex. Depth surface identity and enabled ONE/ZERO blend state are observed correctly; same-descriptor recreated targets do not collapse. No game v6 evidence yet. Next clear payload and initial-content validity, not another diagnostic-only gameplay pass.

- v6 composition metadata uses native resource-private surface lifetime tags (not pointers), effective selected render states and device-local successful Clear/target-binding call serials. Same-descriptor surfaces remain distinct; serials conservatively split groups. Markers do not recover clear parameters, rectangles, initial contents, MRTs or full stencil/material behavior. Diagnostic replay still explicitly overrides depth/blending and does not claim game-frame equivalence.

- Final grouped replay Release/Debug reports are identical: four48-triangle groups,2593/2588/2555/2565 covered pixels,zero error. Controlled disjoint/overlap/order tests and existing capture tests pass (Release6/6,Debug3/3). This closes offline depth-off composition, not game-faithful scene replay; target identity/clear/depth/blend capture is the next missing boundary.

- Saved multi-draw evidence now composes in a standalone diagnostic: native shader and CPU-evaluated passthrough paths match four48-triangle groups with zero error. Group membership uses descriptor/viewport/clip compatibility, not actual target identity; captured material/depth/blend/pass boundaries remain missing. Controlled disjoint and overlapping draws prove the group path retains earlier contributions and applies each draw's own constants in order.

- Real v5 replay qualified after clean exit:12 visible matches and4 empty samples in both Release/Debug, exact coverage/zero error. All corners had positive clip-W, including empty samples: never use positive W as visibility proof. Stable c0/model rows and per-interval-changing clip rows preserve observed coverage changes. Next offline multi-draw composition can use existing saved evidence; no new capture required immediately. Full result in docs/HL2_MULTIDRAW_RESULT.md.

- Real v5 multi-draw pass expands position coverage from one content key to four in this sample:3/35/4/6-triangle blocks repeated across four consecutive intervals,16 accepted draws/192 submitted triangles. All selected5120x1440. This demonstrates broader bounded candidate capture, not whole-scene coverage or object tracking. Await normal exit/cleanup and GPU replay before raster-validation claims.

- Multi-draw v5 uses fixed4-per-interval/16-total accepted limits with separate pending reservation and accepted count. Content-hash suppression is intentionally absent because equal position bytes can belong to distinct instances/passes. Existing16MiB byte limit can terminate before16 samples. Found and corrected offline replay/reconstruction inconsistency: valid present_limit captures were previously rejected although the scene importer accepted them.

- Selected v4 real HL2 evidence now GPU-validated after clean game exit: all four18-triangle samples match in Release/Debug,427 covered diagnostic pixels each, zero error. Cleanup/executable preservation verified. Target filtering successfully avoids the earlier256x256 pass, but capture still repeats the first eligible geometry; next coverage work must collect/select additional candidates rather than relabel repetition as whole-scene capture.

- Real v4 selector successfully bypasses small targets/two-triangle draws: four5120x1440 samples each contain18 triangles, consecutive intervals726..729. Position content repeats exactly; do not count as72 unique triangles or infer persistent objects. Positive clip-W and no degenerates are offline checks, not GPU visibility proof. Replay/cleanup awaits user normal exit.

- v4 target selection is explicitly dimension/count-based, not inferred pass identity. Native selected fixture rejects an8x8 draw then captures128x96 within the same interval, preserving GPU output. Exact policy is recorded and reader-enforced; no match never falls back. Planned HL2 selector5120x1440:3 excludes both known two-triangle samples but does not establish visibility/world semantics.

- Closed HL2 v3 pass verified: native exit0 and owned proxy cleanup complete. Retrying after exit passes Release and Debug GPU position replay for every sample (12288 covered pixels each, zero error). Exact cause of prior generic D3D failure remains unproven; preserve failure evidence and schedule diagnostic GPU replay after game exit. Real interval timing works, but first-eligible-draw selection repeatedly chooses the256x256 target, motivating explicit target/pass selection next.

- Real v3 pass captured ordinals69/71/73/75 at consecutive device2/epoch0 intervals1530..1533, indexed_draw1. All share identical two-triangle position content and256x256 target, VB3487/IB2306 with advancing revisions. This proves interval-separated evidence, not main-scene/moving-object coverage; next sampler needs explicit target/pass selection to avoid earliest-draw bias. Source SHA2569370549a5682a308fe51ee5b032840e9eadbe794fbbe593f096ffc9a7a79cbff.
- Initial independent Release GPU replay failed all four draws with generic fixture D3D failure while HL2 was running. Cause not established; retry only after normal game exit, preserving first failure report. Offline source validation/reconstruction succeeded (4 draws/8 triangles).

- Native v3 fixtures validate four samples across Present intervals0..3 and reset-separated (epoch,interval)=(0,0),(0,1),(1,0),(1,1). Primary swap-chain Present resolves the wrapped device correctly. No-present run stays partial with one sample;120 successful presents stop with explicit count. One attempted failed-Present test actually succeeded on this driver, so failed-Present behavior is guarded in code but not claimed as induced/verified.
- Next real HL2 v3 pass is running and awaiting trigger in build/game-passes/hl2-frames-20260907/runs/frames; do not confuse synthetic timing tests with real-game temporal correspondence. No unified trace/inventory session IDs or inferred persistent game objects yet.

- Frame sampling will be opt-in, retain four accepted captures total, and call its index a successful-Present interval rather than a proven engine frame. Additional swap-chain presents are device-local boundaries too; no primary swap-chain inference. Existing v2 capture behavior stays the default.

- Offline Capture adapter now hashes the same immutable bounded bytes that the reader validates. It preserves position constants, target/viewport and v2 provenance, imports only digest-scoped explicit assignments and leaves unassigned draws unresolved. Partial/I/O-error ledgers and conflicting object assignments reject. Real v1:4 draws/57 triangles; fresh native v2: recreation and buffer reuse remain four explicitly distinct fixture instances. Release7/7 and Debug6/6 pass; no new evidence of live object correspondence.

- Capture-to-scene integration must not infer temporal object identity from process-local buffer IDs or capture ordinals. Current ledgers lack frame/session correspondence; explicit assignments will be scoped to the exact ledger digest, with unassigned draws retained as unresolved evidence.

- User advanced-engine reference archived in docs/ADVANCED_ENGINE_ARCHITECTURE.md with explicit caveats: optional version-pinned adapters, API/shader foundation retained, material identity includes bindings, lightmap removal is not automatic albedo recovery, cache invalidation extends beyond moved-object transforms, practical64-bit renderer split not a blanket D3D12/x86 prohibition. No raw engine-memory access implemented.
- Position ledger v2 now includes resource-shadow lifetime IDs, observed write/invalidation revisions, device reset epoch and constant-knowledge revision. v1 reader remains supported but does not invent provenance. Initial Release position capture passes1.96s; extended reuse-versus-recreation tests pending.

- Position-only scene-state prototype passes7 tests: geometry sharing preserves distinct explicit instances, transform updates reuse content, unseen instances persist, replacements/removals release unused data, stale epochs/sequences and conflicting/over-budget deltas reject atomically. This is an offline contract, not evidence of live HL2 object correspondence. Selected Release scene/GPU/reconstruction suites3/3 pass.

- Verified primary wrapper sources: crosire/d3d8to9 translates D3D8 calls/shaders to D3D9; dxwrapper supplies legacy DirectDraw/early-D3D conversion routes. Chaining into our proxy remains untested. Microsoft documents DX10/SM4 as separate from D3D9/SM3. Keep BioShock-specific build/API qualification separate from generic UE3 assumptions. Added API_ENGINE_ROADMAP.md; no binaries downloaded/installed.

- Real captured position-input GPU oracle now passes in Release: draw1/67/68 have 12,288/659/1,617 covered pixels at diagnostic128x96, exact coverage and zero normalized model-output difference versus CPU passthrough; draw66 empty on both paths, not counted as visible validation. Exact pinned VS uses real captured c0/c4–7/c58–60 and corner positions; unused UV/colour and fog constants are synthetic because this is position-only, not material replay.

- Offline reconstruction exports 4 independent draws / 57 triangles / 127 per-draw unique vertices, no degenerate triangles. All captured c0=(0,1,2,0.5) and c58–60 form identity, so input and model-output positions coincide for this sample. Draw1 uses target256x256 and a different clip transform; draws66–68 use5120x1440 and identical clip rows. Draw66 has all6 corners at negative clip w; never equate submitted geometry with visible scene. World-space interpretation remains unverified.

- Follow-up combined report resolves the apparent trace failure: normal frame-limit completion, 194,529 events, 60 presents, 13,395 shader draws, zero failed calls. Earlier zero-byte observations were provisional; precise activation delay cause remains unproven. Exit 0 after 332.406 s, executable unchanged, runner proxy_removed=true. No trace code fix is justified by the completed result alone.

- Combined gameplay trigger succeeded for position+inventory: four accepted position draws at ordinals 1,66,67,68 with 6/6/54/105 corners (57 total triangles), stride48, 1,572,864-byte VB and 65,536-byte IB. Only 65 unsupported shaders rejected before capture limit. Offline reader verified actual constants/initialized positions and evaluated outputs. Inventory: 2,919 draws, 49 families, 76 programs, zero native failures/unavailable queries, byte limit. Initial trace inspection reported empty trace; do not claim trace completion until checked again.

- Initial combined position/inventory proxy contract passes Release (1.94 s) and original shader_proxy passes (3.59 s). Exact candidate captures coexist with inventory; state-block invalidation rejects, explicit refresh recovers, failed native draws remain rejections, trigger/collision/disabled behavior preserved. Added direct undefined-byte/resource/range negatives and 256 KiB buffer coverage before deployment.

- Combined run needs initialized writes tracked from launch (not only after trigger), exact program selection at draw, and native-success commit. Existing shader hook already tracks resource-private shadows and reset/state-block knowledge. Extend that opt-in path without widening existing raster snapshot admission. Position output captures only the validated position subset, not textures/materials or complete scenes.

- User explicitly wants later single-session unified capture instead of repeated passes, followed by a workbench UI. Roadmap recorded separately; individual capture correctness remains the prerequisite. A newly running HL2 process (54224) has no installed bin proxy; do not assume it can receive capture triggers.

- Exact captured 612-byte HL2 shader executed in hardware-vertex-processing fixture with synthetic initialized inputs. 24 variants, 34,603 covered sample pixels, exact coverage and zero normalized float-output difference versus CPU-transformed pass-through geometry. Float32 RGBA target exposes oT4.xyz, so this is a raster/interpolation oracle rather than direct pre-raster register readback. No real game buffers/constants or world-coordinate meaning proven.

- CPU disassembly of selected 612-byte HL2 VS succeeds: vs_2_0, 19 straight-line slots; position preparation uses actual c0.xy then clip rows c4–c7 and oT4.xyz rows c58–c60. Embedded metadata calls these cModelViewProj/cModel, not sufficient to prove coordinate meaning. Exact shader declares only position/texcoord0/texcoord1/color0, so extra declaration normal/stream2 inputs are unused for this hash. No def c0: do not guess its values. Contract recorded in docs/HL2_POSITION_CONTRACT.md.

- HL2 inventory run exited normally (0, 185.797 s), executable unchanged, runner reports proxy_removed=true and bin/d3d9.dll is absent. No game process is needed for current offline shader analysis.

- HL2 inventory yields 42 VS, 37 PS and 55 families; independent trace has 60 presents, 10,466 shader draws and zero failed calls. Provisional simpler analysis family 34a26bb2... accounts for 231 draws with 612-byte VS 0c16f3b5..., float position/normal and stream-0 stride 48 plus stream-2 stride 0. Largest family has 566 draws and packed inputs/three streams. Do not equate declaration shape with static world geometry or discard zero-stride inputs without shader dependency analysis.

- Live HL2 inventory triggered after user confirmed in-game: 2,996 indexed draws, zero native draw failures and zero unavailable queries; stopped normally on 16 MiB byte budget before 4,096-draw cap. Exact programs and declarations now available. Full summary output is large; use compact aggregation for analysis. No replay admission expanded.

- Inventory byte-budget and unknown-program tests pass on RX 9070 XT: a valid shader with opaque comment data is recorded, renders unchanged, and remains rejected by snapshot admission; repeated large valid programs stop within 16 MiB. Family reader excludes failed native draws and distinguishes partial from bounded completion. Final tests Release 2.20 s / Debug 2.62 s.

- Initial shader_inventory contract passes Release (1.87 s): exact unchanged pixels, counts/families, partial ledgers, native draw failure, trigger/collision handling and malformed-reader rejection. Added throttled trigger metadata polling (100 ms), unknown-but-equivalent shader evidence and runner integration regressions before game deployment.

- Inventory can query native draw-bound shader/declaration objects without retaining them or modifying replay admission. Scope is indexed draws only; bounded sampling is not whole-game coverage. Use independent trigger and exclusive JSONL output, with explicit completion/partial status. No AGENTS.md found by workspace discovery (rg exit 1 means no matches).

- Added opt-in proxy shader interception with native-resource-owned byte/mask shadows (64 KiB per buffer, 16 MiB global retained bytes), wrapper-generation constant knowledge (16-device cap), conservative state-block/reset invalidation and indexed-draw ordinal selection. Capture is prepared before native draw and writes exclusively only on native success; unsupported evidence produces a bounded .rejected artifact. Default-off/disabled forwarding remains separate.
- Initial Release shader_proxy test passes (2.55 s): three draw variants and post-reset replay capture are byte-identical to standalone oracle, pixel-identical in fresh replay; state-block application/recording, partial DISCARD and failed native draw reject; explicit constants refresh recovers. Collision artifacts preserved. Generator discovery initially used unsupported PowerShell wildcard path; corrected to tools/generate_observers.py.

- Standalone shader snapshot gate passes on RX 9070 XT: all three variants match fresh-process replay exactly; reset replay and admission negatives pass. Final adjacent tests 5/5 Release (10.86 s), 5/5 Debug (11.95 s). No game installation changes. Production evidence tracking/proxy hookup and arbitrary HL2 programs remain unimplemented.

- Added standalone shader snapshot library and native fixture, separate from proxy/RRSCENE. Implementation uses an exact VS3/PS3 HLSL program allowlist (matrix rows c0-c3 and tint c4), not originally proposed VS1.1, to match existing compiler/runtime tooling. Capture queries actual device state and requires borrowed native resource identities plus initialized-byte evidence; it does not yet maintain evidence inside the proxy.
- RRTSHD01 artifacts preserve indexed draw parameters, viewport, layout, bounded bytecode/constants and referenced initialized buffer bytes (unused bytes zeroed), with SHA256 integrity. Fresh-process replay contract and admission negatives implemented; initial Release build succeeds.

- Adjacent regression exposed Windows report replacement race: live test reader briefly denied os.replace delete-sharing (WinError 5), aborting run reporting. Added fixed 200 ms retry only for Windows access/sharing PermissionError codes 5/32/33; other failures still propagate. No trace/capture correctness gate relaxed.

- Shader-profile implementation confirms every sampled HL2 draw uses a vertex shader. Default: 820 VS-only / 27,813 VS+PS; low-feature: 11,424 VS+PS. All use DrawIndexedPrimitive. Float constant update payloads are complete (85,617 / 21,922), but missing initial state, shader programs, declarations and buffer contents still prevent reconstruction. Offline profile never treats absent flags as known fixed-function state.
- First inspector patch failed atomically due mismatched CLI spacing/variable context; corrected against inspected source. Reader unit tests pass 8/8. Missing tests/verify_trace.py discovery was superseded by actual tests/test_trace_reader.py.

- Low-feature gameplay exited 0 after 128.204 s, proxy removed. Graphics backup comparison found only DXLevel_V1 changed among reviewed graphics DWORDs (95 to 80); restored that one value with game closed and expected-current-value guard. Config diff only showed dsp_volume 0.7 to 0.8; preserved this unrelated audio change rather than overwriting entire configs. Original settings backup remains available.

- User-triggered lower-feature HL2 capture completed at frame_limit: 60 successful presents, 134,212 events, 11,424 shader draws, zero fixed draws/failures. Requested 70/stored 80 does not expose supported fixed-function draws in this scene. Keep HL2 and investigate shader-aware extraction; first distinguish vertex/pixel shader use and required stream/declaration/constant semantics rather than assume a full shader translator is immediately necessary. User asked to close normally; cleanup and original settings restoration remain pending.

- Low-feature launch responds as native D3D9, but game graphics registry now reports DXLevel_V1=80 despite requested 70 (previously 95); resolution remains 5120x1440. This suggests clamping/fallback to level 80, not confirmed level-70 operation. All stdshader generations loaded, so module inventory cannot resolve actual draw-path coverage. Next trace must measure fixed vs shader draws rather than assume success.

- Installed HL2 includes stdshader_dx6/dx7/dx8/dx9 libraries; current hl2_complete graphics registry DXLevel_V1=95, 5120x1440, fullscreen. Expected cfg/video.txt absent; graphics settings instead found in HKCU Software/Valve/Source/hl2_complete/Settings and cfg/config.cfg. Low-feature test must preserve those settings before launch. Valve command-line page failed to load; NVIDIA tutorial and installed binaries provide the bounded experiment evidence.

- User chose HL2 as continued target, including shader-path work if needed. Triggered gameplay run exits 0 after 141.703 s, proxy_removed=true, executable unchanged. NVIDIA official Portal/HL2 Remix tutorial offers a low-feature configuration lead; must verify installed build honors it rather than infer general shader support.

- User-triggered HL2 gameplay trace validates: byte_limit, 368,506 events, 82 presents, 28,633 shader draws, zero fixed draws/failures. Shader-only sample identifies the next extractability barrier; do not claim the fixed-function capture/replay path supports this game scene. Trigger worked beyond startup; 64 MiB limit prevented full 120-frame request.

- Trigger integration: Release adjacent suite 3/3 (11.95 s), Debug 3/3 (11.04 s) pass including fixed-frame, preexisting/directory/missing trigger isolation. Added separate live-created trigger workflow test. Documentation patch initially targeted wrong TRACE_FORMAT heading; atomically rejected and corrected to actual heading.

- HL2 disabled-bin control passed: exit 0 after 47.765 s, proxy removed, executable unchanged, no trace, user accepts. All three native/proxy/disabled behavior checks now pass for this first run set. Gameplay capture still absent; trace writer currently admits only a fixed startup frame range. Opt-in trigger at a successful Present boundary will avoid guessing user load time.

- HL2 proxy-bin accepted by user and exits 0 with guarded cleanup confirmed. Startup failed-call breakdown: 74 CheckDeviceFormat (-2005530518), 2 GetAdapterIdentifier (-2005530516); no failed draw/present calls. This resembles capability enumeration, not demonstrated rendering failure. Initial PowerShell grouping also included two header/footer null records; those are not failed events and are excluded from the 76-event total.

- HL2 loader-placement experiment succeeded: bin/d3d9.dll is loaded and produces a complete bounded trace (300 successful presents, 20,387 events); game-root placement did not. Evidence supports bin placement for this installed build without binary patching or injection. Renderer compatibility remains unassessed until visual comparison, cleanup and broader state/scene checks.

- HL2 game-root proxy pass exited 0 after 63.125 s with proxy_removed=true and no trace. Installed shaderapidx9.dll resides in bin and references d3d9.dll. Bin placement is the next bounded loading experiment, not a proven fix. Extend runner only for explicit root/bin placement with canonical in-install directory checks; preserve the accepted baseline arguments/hash.

- HL2 native baseline exit 0, 97.656 s, user accepted, executable unchanged. First game-root proxy run starts as PID 53004 but initial modules show system d3d9.dll and trace.jsonl is absent. Do not call this a successful intercepted game pass. Await exit/cleanup, then inspect renderer DLL load-path behavior before selecting another deployment scope.

- User clarified the suspected overlay was Radeon, and reports disabling it. Previous Steam overlay module presence did not identify the suspected culprit; Steam overlay disable is neither requested nor assumed. With HL2 closed, game_pass_workflow passes again in 2.23 seconds. This recovery does not isolate the earlier failure's cause.

- HL2 live module evidence: Steam gameoverlayrenderer.dll, engine shaderapidx9.dll and system d3d9.dll. Prepared build/game-passes/hl2-20260907 without game mutations. Native harness baseline failed during concurrent HL2; existing assertion misleadingly said instrumented on any nonzero exit, now separated. Concurrent rendering/overlay causation remains unproven; clean rerun required.

- HL2 user reports good native gameplay but suspects an overlay causes DX9 issues; causation is not confirmed. Live process 53856 uses J:/SteamLibrary/steamapps/common/Half-Life 2/hl2.exe with -steam -game hl2_complete. Preserve those observed arguments for controlled baseline/proxy comparison; do not deploy while the existing game is running or alter overlay settings on the user's behalf.

- BioShock 2 -dx9 baseline failed with access violation 0xC0000005 without project DLLs. Default-mode baseline previously passed; pause BioShock proxy qualification rather than treating interception as a crash fix. Recent Application event query returned no matching crash detail.
- Inventory shell command initially used invalid direct foreach-to-pipeline syntax; corrected by wrapping enumeration in @(...).

- Installed BioShock2.exe UTF-16 strings contain adjacent dx9/dx10 selectors and BioDrv.BioRenderDevice / D3DDrv10.D3DRenderDevice10 names. Prepared independent bioshock2-sp-dx9-20260907 pass with identical -dx9 baseline/proxy arguments; launched baseline without local DLL. Roaming/local AppData probes found no BioShock2 folder. Runtime API confirmation remains pending actual rendering evidence.

- DX9 selection investigation: installed Default.ini includes D3DDrv10.D3DRenderDevice10; roaming AppData BioShock2 folder was not found. Web search found community -dx9 reports but no publisher flag documentation, so these are leads only; verifying the installed executable/config and runtime behavior before claiming DX9 selection.

- J: follow-up inventory: only Morrowind currently has game executables (7,233 files). Half-Life 2 contains four files and no executable; Amnesia, Dark Souls, Half-Life and HardReset directories are empty. Folder presence is not an installed/ready title; downloads may still be pending.

- Completed BioShock 2 baseline report confirms exit 0, executable unchanged, installed_by_runner=false, no trace/capture. User visually accepts baseline and suspects DX10; do not label API confirmed or attribute original reflections to our renderer. J: library now exposes six older-title directories for subsequent preflight.

- BioShock 2 SP baseline launched successfully as responding PID 42900, with no proxy installed. Loaded system modules include d3d9, dxgi, d3d10, d3d10core and d3d11; module presence alone cannot identify the active rendering API. Prepared provenance/report bundle: build/game-passes/bioshock2-sp-20260907. Await user scene review and normal exit before proxy comparison.

- 2026-09-07: user supplied original BioShock 2 installation on O:. Found SP/Builds/Binaries/Bioshock2.exe and separate MP binaries. Selected SP only; no existing local d3d9.dll or running BioShock process found. Initial INI/text search did not identify DX9 flags; checking executable strings before specifying any launch argument.

- Game-pass validation complete for classic DX9: Release 3/3 in 8.80 s, Debug 3/3 in 9.73 s (workflow, forwarding equivalence, scene replay). Native/proxy/disabled pixels match; selected-frame trace and scene extraction work; existing mods and changed executable provenance are rejected.
- The hidden harness caused S_PRESENT_OCCLUDED. Making its surface visible restored classic checks. Foreground activation did not repair Ex and was removed. Bounded presentation-only retries also fail on Ex's untouched Microsoft runtime; the harness now fails explicitly instead of claiming successful frames. No runtime semantics were relaxed.
- Registered Steam M: library is absent. Accessible registered libraries plus root-level standard Steam/GOG/game folders did not locate the proposed older titles. Real-title work needs an executable path; no installed game files were changed. Additional discovery found only unrelated modern installations/source-game projects, not a selected reference title.
- Documentation read used an invalid Get-Content -Skip parameter once; use Select-Object -Skip instead. docs/GAME_PASS.md now contains deployment, review, launcher limitations and guarded cleanup instructions.

- Added tools/game_pass.py: read-only preparation, x86 PE/hash provenance, baseline-first gating, exclusive DLL creation, per-child trace environment, bounded trace/optional scene capture, trace summaries and checksum-guarded cleanup. Existing d3d9.dll files block deployment; no game EXE/assets are rewritten. Added a disposable-game-directory GPU workflow test comparing baseline/proxy/disabled pixels and validating captured scene output. Discovery searches for verify_proxy.py/verify_equivalence.py were incorrect; actual existing proxy coverage is verify_runtime.py, now used in CTest selection.

- Confirmed M:/SteamLibrary/steamapps is unavailable; C: has only Steam redistributables, O: has two modern-title manifests, and registered J:/P: libraries have no app manifests. Asked asynchronously for a game executable path while preparing the runner. PowerShell discovery needed array-wrapping foreach output before ConvertTo-Json; the initial direct pipe was a parser error, corrected without filesystem changes.

- Steam's library manifest lists M:/SteamLibrary, O:/SteamLibrary, P:/SteamLibrary and J:/SteamLibrary. Direct M: manifest lookup failed with path-not-found; checking mounted-library availability before treating this stale registration as an installed game inventory. No game files changed.

- User requested persistence until a game pass. Existing proxy/trace infrastructure already supports a first qualification/observability pass; continuous cache presentation is not a prerequisite for measuring actual game API behavior. Steam registry points to C:/Program Files (x86)/Steam. Need local installed-title evidence and a reproducible reversible runner, rather than another isolated cache micro-sprint.

- Renderer session first run and Release path contract pass with --debug (53.33 s). Six epochs issue 18 dispatches, consume coalesced camera input, refresh counts 172/178/178/172/172/172, reject the stale first result and accept five others. Moved continuation hash is 8100200300773600753; base return/reset hashes exactly match the direct baseline. In-place frame constants reduce retained pool bytes by 256: staging now 10 allocations/17 reuses/246,528 bytes; full pool 30 allocations/78 reuses/2,880,264 bytes.

- Added renderer-owned six-epoch command test: base reset (made stale by coalesced camera requests), moved reset, moved continuation, return-to-base reset, base continuation and explicit identity reset. The same raw/compact/shared buffers and one provider context span all epochs. Frame constants now update in place after ownership returns, eliminating per-regeneration upload allocations. Each epoch reads back predictions for exact worker/renderer hash agreement while preserving no-cache pixels.

- Next integration connects RcFrameAdmission and renderer-owned raw/compact resources to mode-4 provider commands. The proof must consume coalesced pending camera input (rather than just report it), refresh sample counts through GPU regeneration, retain one context and validate reset/continuation plus shared output. Per-epoch native presentation is a separate remaining boundary.

- Whole-project status published in docs/PROJECT_STATUS.md and linked from README/PHASE_PLAN. Release path contract passes in 43.25 s with commanded-session repeatability, R-only stop, 16 resets, malformed-command rejection, deadline/budget failures and recovery alongside existing renderer/cache regressions. Debug provider builds successfully; corresponding contract running.

- First parent-commanded provider session succeeds on real shared buffers. Sequence RCRCC executes five epochs/15 dispatches inside one process/context: reset baseline 4380958906282038366, first post 17423046786485749504, second post 13270289865275143940, exact reset/replay of those hashes, then third training post 1061084142929051959. Stop acknowledges successful context destruction; parent reads back final shared output and verifies its hash. This uses the exported static fixture, not live game frames.

- Whole-project checkpoint: proxy/trace harness stages are complete; capture/replay and offline replacement implement a narrow fixed-function subset; standalone DXR exists. RR executes but quality gates fail, RC executes with guarded synthetic improvement and pooled buffers, and no commercial title is certified. Continuous D3D9-to-DXR presentation, reference-game qualification and remaining FSR features are still open. Next provider work must replace fixed epoch choreography with parent-commanded continue/reset/stop.

- Final eight-transaction Release contract passes with --debug in 31.30 s: 31 buffer allocations, 78 reuses, 2,880,520 retained bytes, seven restore submissions/61 restored buffers, and exact return to the 2,967,408-byte baseline. Both applied and diagnostic candidate states are covered. Shared handles, fences, pipelines and provider processes/contexts are still constructed per transaction; this proves buffer reuse, not continuous rendering or frame-rate improvement.

- Initial Release GPU-pool equivalence passes (29.48 s): 31 allocations, 54 reuses, 2,880,520 retained bytes and five restoration submissions/45 barriers, with exact teardown to baseline. Expanded the GPU-pool variant to eight transactions to test the candidate's diagnostic COPY_SOURCE end state as well as applied SRV state; diagnostic repeats must allocate no new buffers and preserve exact no-cache pixels. The GPU-pool contract explicitly enables --debug.

- Extended RcBufferPool (renamed from RcStagingPool) with exact descriptor matching, optional shared/default-heap mode bounded to 32 slots/8 MiB, and explicit successful-end-state annotations. Recycle restores nine changed buffers and synchronously fences the restore submission before reuse; failure releases all pooled resources. Upload/readback-only behavior remains supported. Added a GPU-pool variant of the six-transaction equivalence/failure test.

- Stateful-pool inspection: raw paths, pixel mapping and five shared buffers finish in NON_PIXEL_SHADER_RESOURCE; candidate finishes in COPY_SOURCE diagnostically or NON_PIXEL_SHADER_RESOURCE after application; audit finishes in COPY_SOURCE and backup remains COPY_DEST. Recycle must explicitly restore these to allocation states after child exit and final GPU work. Compaction clears unused provider inputs/targets and rewrites occupied mapping entries; only populated mapping entries are consumed.

- Release pooled/unpooled GPU equivalence passes in 31.04 s. Canonical six-transaction pool records 11 allocations and 17 reuses, retains 246,784 bytes, then returns exactly to the 2,967,408-byte renderer baseline. Stable repeat performs no new staging allocations, and low-budget failure empties the pool before recovery. No wall-time speedup is claimed.

- Added RcStagingPool with 16 slots/1 MiB bounds, exact size/heap matching and exclusive per-transaction leases. A slot cannot be borrowed twice concurrently; completed successful transactions retain staging resources, while failures invalidate the pool. The existing six-transaction resource test now has a pooled variant, checks zero extra staging allocations on the stable repeat, rebuild after failure, exact output equivalence and final budget return.

- Buffer-pool inspection: upload and readback buffers retain GENERIC_READ/COPY_DEST across transactions, so they can be pooled without additional barriers. Raw, compacted, shared, candidate and audit default-heap buffers change state and need explicit state restoration before reuse. Start with a bounded staging pool to establish lease ownership and failure recovery without guessing GPU states.

- Final lifetime evidence: all six transactions return to 2,967,408 live requested bytes, with 5,847,928 peak requested bytes. Recovery and changed-camera/live candidates remain exact. Release path and Debug path/native contracts pass; x64 Release/Debug and Win32 Release builds succeed. The remaining performance boundary is pooling resources and keeping a generalized provider epoch loop alive, not budget reclamation.

- RcTransientBuffers now owns every direct-path buffer/upload and its exact budget charge. It retains resources through child teardown and returns only its own charges after local references unwind. Added a six-transaction same-renderer fixture: stable, repeat, low-budget failure, recovery, changed camera and live three-epoch work. Each transaction must return to the same live-byte baseline; repeated stable work must not increase the high-water charge, and failure must preserve exact no-cache pixels.

- Repeated-frame resource inspection: Device::Buffer/SharedBuffer increments a cumulative byte charge; RC resources are local and released after each transaction but never uncharged. Scope RC allocations in an owning arena, retaining COM references until transaction teardown, then releasing and subtracting exactly that arena's charges. Leave scene and swapchain accounting unchanged. Provider protocol remains fixed to one/two/three epochs and needs separate generalization.

- Final review: the existing frame-wait diagnostic pumps messages internally, so publication also checks actual HWND lifetime before constructing the swapchain. This covers window destruction observed outside the admission-aware pump.

- Initial Release path/native contracts passed in 33.08 s. Follow-up review caught a second close window between provider completion and swapchain admission; the same message pump and identity check now cover that stage, with a dedicated close-admission fixture. Admission verifies rejection of overlapping epochs, foreign completion tokens and post-close requests.

- Added UI-owned RcFrameAdmission with one active request and one replaceable pending request. Scene, camera, lighting, material and settings revisions determine reset; failed epochs invalidate continuity. Native scheduled presentation now suppresses publication on close or newer camera identity, with deterministic camera/close message fixtures. The bounded harness reports pending work but does not yet execute it; this is admission integration, not continuous rendering.

- Renderer-loop inspection: RunRcScheduledPresentation gives the worker exclusive Renderer ownership while pumping UI messages, but currently ignores close requests and unconditionally constructs a display afterward. RunRcDirect allocates transient GPU buffers against a cumulative budget, so repeatedly launching whole transactions is not a sound continuous-loop design. Establish admission/coalescing policy and close-safe publication on the current native loop before extending provider epochs.

- PollFence now drains both bounded output pipes before checking fence completion, rejects the D3D12 device-removal sentinel, and rechecks completion after observing child exit. WaitFence calls it at intervals of at most 10 ms using the remaining deadline. Constructor resume failure explicitly terminates and reaps the child.
- The affected isolation CTest is named rc_worker_boundary; the initial regex rc_worker_contract selected only the path test. Run the actual boundary test separately.

- Live-session follow-up: WaitFence waits without draining pipes; a verbose child can block before signalling its fence. A nonblocking poll must drain output and enforce limits while observing completion and process exit.

## RR longer histories (2026-09-03)

- Final verification: Debug rr-history-replay-w13fuyu4 exactly matches all 18 recordings and 54 outputs (534.09 seconds). Release rr_quality/rr_surfaces/rr_settings plus both contracts pass 5/5 in 507.23 seconds; contracts also pass Debug. Python/static/doc checks pass. Conclusion: lower stability is a diagnostic response knob, not an accepted default—spatial recovery normally carries persistent temporal cost and remains far above fallback.
- Compatibility: all six extended moving recordings have first-four frame payloads identical to the prior four-frame grid, and all eighteen corresponding preset output-frame prefixes are byte-identical. This confirms extension to eight frames did not alter earlier history. An initially over-expensive tuple-decode audit and a per-byte PowerShell replacement were abandoned/stopped; direct byte-slice comparison produced the same intended check without changing artifacts.
- All three PBR/reset seeds are exact at frame 4. Frame 7 half spatial is 32.6–33.7%, disocclusion 47.8–50.1%, temporal 2.07–3.05x default; zero spatial 24.2–25.5%, disocclusion 41.1–43.1%, temporal 2.57–3.67x. Together with texture this makes all twelve configured reset-frame comparisons exact and all 36 post-reset temporal comparisons worse.
- First PBR/reset case is exact at frame 4 and retains large post-reset temporal cost. Frames 5–7 half spatial improves 54.8%→32.6% of default, disocclusion 58.4%→50.1%, while temporal is 6.16x/5.84x/2.07x; zero spatial 47.8%→24.2%, disocclusion 51.5%→42.0%, temporal 7.70x/7.27x/2.57x. The PBR context-recreation response agrees with texture direction.
- PBR/moving frame-7 temporal response is less uniform than texture: half is 1.02–1.64x default; zero is 0.95–1.69x, with seed 23 zero improving that single late transition by ~4.8%. Spatial remains 22.5–24.5%/15.6–17.2%, disocclusion 48.6–72.3%/41.3–55.5%, and spatial remains 20.6–22.5x/14.3–15.8x fallback. Earlier transitions still make every lower-bias PBR moving report fail absolute temporal non-regression. Final aggregation must preserve this late seed-23 exception rather than claim universal per-frame worsening.
- First PBR/moving seed-1 frame 7: half spatial is 22.7%, disoccluded 49.2%, temporal 1.64x default; zero spatial 16.0%, disoccluded 43.0%, temporal 1.69x. Both fail temporal-vs-raw and fallback gates; spatial remains 21.8x/15.4x fallback. PBR motion again narrows neither the sign nor acceptance impact of the temporal tradeoff.
- All three PBR/stationary seeds agree at frame 7: half spatial is 28.9–30.2% and temporal 2.67–5.45x default; zero spatial 17.8–18.6% and temporal 2.78–6.92x. Half fails the absolute temporal gate for seed 23; zero fails it for all three. Even reduced spatial results remain 65–76x (half) and 40–46x (zero) above fallback. PBR therefore confirms persistent late-history cost across seeds.
- First PBR/stationary case reproduces and strengthens the texture direction at frame 7: half spatial is 28.9% and temporal 4.78x default; zero spatial 17.8% and temporal 6.57x. Zero fails absolute temporal-vs-raw, while half remains below raw. Despite the spatial gain, half/zero remain 65.3x/40.1x worse than matched fallback, and capped fallback-reference confidence is false.
- All three texture/reset seeds use two contexts and match default exactly at reset frame 4. At post-reset frame 7, half spatial is 37.37–37.49%, disocclusion 38.66–40.01%, temporal 2.31–2.74x default; zero spatial is 29.01–29.09%, disocclusion 30.63–32.40%, temporal 2.71–3.24x. Cross-seed reset behavior is highly consistent and confirms the temporal penalty remains after three new-context history frames.
- First texture/reset seed-1 case validates two inspected/configured contexts and exact equality with default on reset frame 4. During post-reset frames 5–7, half spatial MSE improves from 58.2% to 37.4% of default and disocclusion 51.4% to 40.0%, but temporal residual remains 6.44x, 3.91x and 2.73x default. Zero reaches 51.6% to 29.0% spatial and 44.5% to 32.4% disocclusion, with temporal 7.99x, 5.16x and 3.18x. Recreated context resets the output response, but three subsequent frames do not remove the temporal penalty.
- All three texture/moving seeds agree at frame 7. Half-bias spatial MSE is 28.4–30.2% and disoccluded MSE 37.1–40.4% of default, while temporal residual is 1.17–1.19x default. Zero-bias spatial is 20.3–21.4%, disoccluded 28.8–30.7%, temporal 1.29–1.30x. Both presets fail absolute temporal non-regression in all three recordings. This cross-seed consistency strengthens the persistent motion tradeoff; it does not overcome fallback/reference-confidence failures.
- First texture/moving seed-1 case also has persistent late tradeoff. Frames 4–7: half spatial MSE is 29.5–35.4% and disoccluded MSE 38.7–42.3% of default, while temporal residual is 1.09–1.38x default; zero spatial is 20.9–26.5%, disoccluded 30.1–34.4%, and temporal 1.18–1.57x. Both lower-bias presets fail absolute temporal non-regression and fallback comparison/confidence gates. Camera motion narrows, but does not remove, the default-relative temporal penalty.
- All three texture/stationary seeds now agree at frame 7: half-bias spatial MSE is 38.6–39.4% of default but temporal residual is 4.35–4.96x default; zero-bias spatial MSE is 25.8–26.4% of default while temporal residual is 5.59–6.27x default. Zero bias also fails the absolute temporal-versus-raw gate for seed 23; the others remain below raw. All six lower-bias reports fail reference confidence versus fallback at capped 512/batch. This supports persistent late-history tradeoff, not an initial-only transient.
- Optimized integration verification on the first actual eight-frame case reproduces three standalone reports and numeric array sets exactly while reducing estimator calls from 24 to 8; changed-cache identity and substituted-preset evidence are rejected. Reference sharing remains within one recording only; separate renderer seeds are independently traced.
- First completed texture/stationary seed-1 case shows the tradeoff persists at frames 4–7: zero-bias spatial MSE falls from ~1.65e-4 default to ~4.29–5.70e-5, while temporal residual MSE rises from ~2.0–2.9e-8 to ~1.27–4.03e-7. All remain temporally better than raw, so the absolute temporal non-regression gate is true even though zero is worse than the default preset. As anticipated at 512/batch, reference-noise-small-versus-fallback is false; the raw-relative reference diagnostic remains true. Do not use this case alone as steady-state qualification.
- Predeclared design uses 18 eight-frame recordings and 54 configured/unconfigured outputs: texture/PBR × stationary/moving/reset × renderer seeds 1/7/23. Reset trajectories recreate the SDK context at frame 4. At eight frames the existing reference work cap permits 512 samples per batch, so this phase may have weaker fallback-reference confidence than the completed four-frame/1024-batch grid; thresholds and cap will not be relaxed.

## RR multi-seed surfaces (2026-09-03)

- Final replication: optimized Debug rr-surface-replay-y0d3mw1c passes in 64.27 seconds, reproducing all six recordings/eighteen outputs byte-for-byte. Both historical texture/PBR recordings, default outputs, reference NPZs and every frame metric remain exact. Final corrected CPU contract passes both Python modes and both CTest configurations. All current milestones complete; next is longer-history/reset characterization, not default promotion. The recovered Release manifest retains the audit correction and unavailable elapsed time rather than claiming a fresh measurement run.
- Completed grid: half/zero stability each improve all 18 non-reset spatial and all 18 disoccluded-region estimates versus default, with six equal reset frames, but worsen every one of the 18 temporal residual comparisons. All reference diagnostics pass. Every preset fails spatial/disocclusion/fallback gates; half/zero additionally fail temporal non-regression in every recording. Zero-bias final-frame MSE improves ~69–71% for texture and ~77–78% for PBR, but still exceeds fallback by ~51–63x and ~28–32x respectively. No operating point accepted.
- Final seed audit initially misclassified sampled bounce distance as a deterministic guide. Shader inspection and a column-wise audit show only components 0..3 (RGB plus secondary T) vary; matrices and components 4..23 remain exact. Corrected helper and three regression controls now enforce that contract. All saved artifacts were revalidated by tests/recover_rr_surface_grid.py without recomputing reference estimates; verification.json explicitly records recovery and unavailable elapsed time. Four Release regressions pass (468.51 seconds); full Debug capture/output replay is pending.
- Both textured and PBR optimized cached/independent checks pass: six exactly matching report/array pairs in total, four cached versus twelve independent reference calls per recording, and four identity/preset rejections. Historical texture seed-1 recording, unconfigured SDK output, 2048-total-sample reference NPZ and every frame metric match exactly; PBR seed-23 recording/output also match, with its final reference still computing. Existing rr_quality/rr_surfaces regression passes preserve prior evidence. No renderer/native/SDK changes occurred.
- All three texture seeds have completed their high-sample analyses. The observed later-frame spatial improvement with lower stability persists, but spatial/disocclusion/fallback gates remain failed and half/zero temporal non-regression also fails. Cached/independent texture validation completed with exact report/array equality and expected four-versus-twelve estimator calls. First PBR case finished; remaining PBR seeds and regression/replication checks are pending. Do not infer a cause or operating point from these partial results.
- First completed 1024/batch texture seed-1 case retains failed spatial gates for all three presets; reducing stability is not a general texture fix. Definitive Release grid is rr-setting-surfaces-um5fj4em. Added independent-versus-shared reference verification (four cached estimator calls versus twelve independent calls, exact arrays/reports, wrong-cache-identity and substituted-preset rejection); optimized check is running against this first completed case.
- Current reference/quality tools already support bounded textured/PBR sources, matched fallback and explicit filter presets. The previous surface cases used different seeds for texture/PBR and were not a multi-seed comparison. New predeclared grid uses the same three input seeds (1,7,23) in each scene/material condition, four translating frames and default/half/zero stability. Source artifacts remain available; normal renderer and shader changes are unnecessary.

## RR single-setting experiments (2026-09-03)

- Final verification: Release optional SDK suite passes 12/12 in 1082.68 seconds; rr_settings passes in 309.06 seconds. Its 43 outputs, six reference NPZs, five recordings and measurement dictionaries match optimized Debug exactly. Separate direct hash audit confirms five historical unconfigured outputs; CTest itself omits the optional baseline argument. All current implementation milestones complete; no renderer default or quality acceptance change.
- Higher-sample noisy control (Debug rr-setting-noise-4geqmsb0, 1024/batch, 221.92 seconds) passes all eight narrow gates for default/half/zero. Frame-three spatial MSE is 1.09088e-6 / 8.01169e-7 / 7.93963e-7; first temporal residual worsens from 1.93038e-7 to 2.47629e-7 / 2.65860e-7. Some disoccluded-region estimates worsen too. Three SDK outputs match the initial Release 512/batch run exactly, while fresh reference estimates differ with sample count. This is one fixture/seed, not general qualification; analytic contrast/black-floor and raw SDK-reporting failures persist. Next needs independent input seeds and noisy/PBR motion/visibility controls before any operating-point choice.

- A bounded additional noisy-control tool compares none/half/zero stability on an existing rr_quality moving diffuse recording with fresh independent references/fallback. Initial Release rr-setting-noise-v2t6g3to at 512 samples/batch reports later-frame MSE improvements but worsens one early temporal comparison. Reference variance ~5–6e-8 fails the existing 1%-of-fallback diagnostic; retain this failure and rerun at 1024/batch within the unchanged count*samples<=4096 cap. No multiseed/general qualification claim. Full Release regression has passed ten tests; defaults/settings remain running.

- Expanded optimized Debug rr-settings-yn9yujur passes (331.69 seconds): ten exact default controls, 43 rejection cases, five historical matches, maximum eight configured reset contexts, CLI failure-gate evidence and crash recovery. Maximum worker stdout 38,039 bytes. Its zero-bias eight-frame full quality report explicitly retains failed spatial, temporal and fallback gates plus failed raw SDK acceptance. Full Release regression remains in flight. New test console summary now omits the large measurement dictionary, which remains preserved in verification.json; no test logic/threshold changed.

- Initial Release rr-settings-3y4dazpv passes in 241.27 seconds: 40 grid runs, ten exact default-equivalence controls, five historical matches, 43 rejected inputs/reports/options and configured crash recovery. Zero stability bias reduces history frame-seven MSE 85.79%, from .001030857 to .000146440, with RGB gain improving .273/.461/.207 to .766/.793/.725. But it still exceeds the analytic fallback MSE by about 10,822x (fallback 1.35e-8, raw 3.08e-10), and maximum error remains .0821. Initial reset frames do not change with stability settings; black floor remains. Gaussian effects are mixed. No cause or accepted operating point established.
- Both native configurations and the CPU-only contract test pass. Expanded final tests include maximum eight-context configured output and full zero-bias history quality evidence. Full 12-test Release SDK regression and optimized Debug grid are running. Next must assess noisy/multiseed/temporal tradeoffs before any promotion.

- Rechecked official AMD RR technique/sample manuals: both chosen keys have sample UI range 0–1, and configuration belongs before dispatch. Pinned scalar descriptor key/count/data matches implementation. Documentation links and fixed preset/version-3 mapping are in docs/RR_FILTER_SETTINGS.md. Repeated default queries are explicitly not active-value readback. Early linear/sqrt grids reduce second-frame MSE at stability .5/0; Gaussian changes are small/mixed. Longer-history/reset/black results are still running, and no general acceptance follows.

- Recorded-only predefined single-key presets now cover stability 1/.5/0 and Gaussian relaxation 0/.25/.5/1; the 1 and 0 entries are queried-default controls. Native execution admits the selected live default before configuring once per reset context, preserving actual query/configure codes and requested float bits. Configured bundles use RRTRRD03, version 3 and tag (preset_id << 1) | sqrt_encoding_bit; canonical inputs and inner RRO frames are unchanged. Managed readers require the exact explicit preset and verify all contexts/default snapshots.
- Initial Release native build and actual stability-default dispatch pass. The SDK returns configure code 0 and all inner frame bytes match the preceding unconfigured linear recording. Default-query API still returns the same defaults afterward. No source-scoped AGENTS.md found; no unsynced recovery state. Settings remain isolated-worker-only and not promoted.

## RR default-setting inspection (2026-09-03)

- Final Release optional SDK suite passes 10/10, 692.00 seconds. rr-defaults-ycw6uxym passes in 129.45 seconds with 35 rejections/five honest failures/two instability controls; 22 bundles, five recordings and ten case dictionaries match final optimized Debug exactly. Eight final outputs match historical encoding evidence directly. All 14 paired outputs, eight numeric references (including CLI) and metrics from the old encoding regression are also byte-identical/identical to the previous run. Quality and raw SDK failures remain retained; no defaults changed. Current three milestones complete; normal renderer/x86/legacy/historical suites not rerun.

- Final optimized Debug rr-defaults-fh5vyha8 passes all ten off/on pairs, 35 rejected cases (including signed-zero consistency), five honest query failures propagated through execution assessment, two instability cases and eight historical matches. Runtime 145.42 seconds with independent Release regression running concurrently. All 22 bundles and per-case dictionaries still match initial Release exactly. Seven of ten Release SDK tests have passed; no quality-gate relaxation or default changes.

- Official AMD RR 1.2 technique and sample manuals checked: configure before dispatch, scalar count 1, defaults are not current-setting readback. Sample UI ranges are normal/stability/Gaussian 0–1, disocclusion .01–.05, cap/clip K 0–65504; these do not establish the complete API validator domain. Next requires explicit-setting provenance and a configure-to-queried-default idempotence control before one-key grids. Sources linked in docs/RR_DEFAULT_SETTINGS.md. One guessed sample-document URL returned an internal error; followed the actual technique-page link to /samples/denoiser/ successfully. No local files affected by that lookup.
- Initial optimized Debug rr-defaults-mp24l0ma passes in 99.875 seconds; all 22 output bundles and ten per-case inspection dictionaries match initial Release exactly. Final source review added signed-zero JSON preservation and a negative-zero malformed-value control (final expected rejection count 35), without changing the actual pinned positive/zero defaults. Full ten-test Release SDK regression is running.

- Initial Release harness rr-defaults-v35hm6p3 passes (96.28 seconds): ten off/on pairs, eight historical bundle matches, all non-query native report fields unchanged, 34 rejections, five honest-failure and two instability cases, CLI/quality validation and crash recovery. Maximum eight-context report is 36,099 bytes within the unchanged 64 KiB stream cap. Across 26 queried contexts / 624 queries in the ten pairs, all defaults are stable and finite, guards intact. Debug replication is running.

- Initial live pinned SDK queries succeed for all six scalar keys: normal strength 1, stability bias 1, maximum radiance 65504, clipping K 50, Gaussian relaxation 0, disocclusion threshold float32 0.01 (bits 0x3c23d70a). Two before and two after snapshots match, with actual writes and intact guards; initial queried output matches historical encoding evidence byte-for-byte. These are default API values, not internal shader-state readback or a diagnosis of the contrast failure.
- Added recorded-only --query-defaults, raw per-key codes/bits/canaries, fixed float32 count 1 and null values for failed/unwritten/nonfinite queries. Six filter keys only; debug-view bounds use another type and are out of scope. No denoiser-context configuration override; pre-existing null-context logging configuration remains unchanged. Managed inspection distinguishes successful stable defaults from honest failed/unstable results and rejects malformed/missing requested evidence.
- Release/Debug worker builds pass. Full paired inspection checks, eight automatic-cut contexts, quality revalidation, old output compatibility and failure/recovery tests are running. Existing raw SDK failures and resource/process caps remain unchanged.

## RR paired albedo encoding (2026-09-03)

- Final Release optional SDK suite passes 9/9, 553.45 seconds. Encoding artifact rr-encoding-n49hhhv5 passes seven pairs and 28 rejections in 140.24 seconds. Fourteen SDK bundles, seven numeric reference bundles and all measurement dictionaries match optimized Debug rr-encoding-d366h8er exactly. Six final default linear bundles still match pre-change rr-colour-0u48aq8r byte-for-byte. No encoding promotion or internal-cause claim; existing contrast/zero-light/raw SDK failures remain.
- Full optimized Debug paired run passes (rr-encoding-d366h8er): seven cases including motion/reset, 28 rejection checks, CLI exit-2 evidence retention, six pre-change default-output matches and sqrt allocation-failure recovery. Moving reset also shows mixed encoding changes rather than a general fix. Release full nine-test regression is still running.
- Next read-only setting inspection must use a live non-null denoiser context: pinned ffxQueryDescDenoiserGetDefaultKeyValue has uint64 key/count and a typed output pointer. Keys 1–6 are scalar floats (normal strength, stability bias, maximum radiance, clip K, Gaussian relaxation, disocclusion threshold); key 7 is debug depth bounds. Do not infer defaults from zero initialization or configure anything during that first query step.
- Implemented recorded-worker-only --albedo-encoding linear|sqrt. Canonical RRC/RRI and radiance stay unchanged. sqrt packs double sqrt rounded to float32 then binary16 and omits NON_GAMMA_ALBEDO; linear remains default. Native reports record the actual dispatch flags and encoding, and managed checks independently rebuild all packed hashes.
- New nondefault bundle RRTRRD02 has version 2 and encoding tag 1; same bounded length and embedded RRO frames as linear RRTRRD01. Readers require an explicit expected encoding. Historical reports lacking both metadata fields remain linear-only; partial fields reject. Recorded quality CLI propagates explicit expected encoding and records it in output evidence.
- Release and Debug worker builds pass. Paired analytic tests are running against prior pre-change linear evidence, including noise-free texture/history, invalid report/header/mode provenance, default-option equivalence and injected SDK-failure recovery. No source renderer/shader/SDK binary or resource-budget changes.

## RR colour-response isolation (2026-09-03)

- Final old-reference regression passes: Release rr_quality + rr_surfaces 2/2, 139.79 seconds. New analytic harness passes Release/optimized Debug with exact cross-configuration matches. This confirms the isolated reproducer does not require modifying the existing references. All three current milestones complete; broad native/legacy regressions are not relabelled fresh. Raw SDK and quality acceptance remain failed/not-qualified.
- Optimized Debug rr-colour-cm_unoww passes all eleven controls in 94.77 seconds. SDK output bundles, numeric reference bundles and per-frame colour-response metrics match Release rr-colour-0u48aq8r byte-for-byte/numerically exactly. Independent affine synthetic control confirms centered gain .25 and correlation 1. No default/native changes. Existing constant quality CTest has passed again; textured/PBR suite is still running.
- Next concrete experiment: retain canonical renderer-owned linear inputs, add an explicit provenance-checked worker packing choice for linear+NON_GAMMA_ALBEDO versus sqrt+flag absent. Verify flags/packed hashes/default compatibility; do not forge recordings or blindly change only the flag. This remains planned, not an observed fix.
- Expanded Release analytic run passes eleven cases (rr-colour-0u48aq8r, 95.43-second CTest). Uniform colour through vertex versus texture, irrelevant input RNG seed, and the longer recording's prefix each have identical packed SDK inputs and output arrays. Eight stationary frames reduce linear-texture MSE from .00147845 to .00103086, but centered RGB gain remains .273/.461/.207 and max absolute error .100405. This is not solely a reset-frame artifact; eight frames do not establish infinite-history behavior.
- Pinned denoisers/include/ffx_denoiser.h and AMD's Ray Regeneration 1.2 manual agree: indirect diffuse input/output are radiance, and NON_GAMMA_ALBEDO selects linear diffuse albedo. Existing dispatch matches that documented pairing. Source: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/ . No speculative encoding changes.
- Existing texture frame zero has nearly matching global mean RR/reference RGB (.03231/.03222, .01904/.01923, .01722/.01719), despite large spatial MSE. Candidate multiplication/division by albedo or red/blue swapping increases MSE. A uniform colour-gain mistake is therefore not a sufficient explanation; measure spatial detail on an analytic plane next.
- Added a bounded ambient-only, single-plane analytic experiment with constant white/grey/dark/colour, varying vertex colour, linear/point texture and black controls. Every secondary must miss, the plane must fill the viewport, and geometry/normal/depth guides must remain identical across cases. Expected indirect RGB is independently traced base colour times recorded ambient; Monte Carlo reference must agree with negligible variance. Fitted gain/offset/channel-swap diagnostics never modify outputs.
- Initial analytic results isolate the failure without PBR, motion, stochastic lighting or occlusion: constant colours have small absolute bias, but vertex-varying radiance has frame-zero centered response gains .412/.382/.218 and linear textures .114/.367/.060. These are spatial contrast diagnostics, not proof of the SDK-internal cause. Add equivalent colour-through-vertex inputs, a different input RNG seed and the existing maximum eight-frame stationary history before concluding this is merely startup behavior.

## RR textured/PBR and fallback comparison (2026-09-03)

- Final 2,048-total-sample CLI texture/PBR measurements pass all reference-noise diagnostics, with variance 0.66–0.75% of fallback MSE. The quality counterexample persists: RR/raw MSE 9.90–23.53 and RR/matched CPU fallback 144.50–306.50. Both --require-gates runs save evidence and exit 2. No work-cap or tolerance increase. Reports: Release rr-surfaces-xt5d6i3h, *-quality-2048.json and *-reference-2048.npz.
- Optimized Debug rr-surfaces-04wvhmhq passes the complete surface harness. All four SDK bundles and both reference-array/frame-metric sets are exactly identical to Release rr-surfaces-1x1xqyi8. Missing-sidecar CLI writes no outputs; overwrite attempts reject. Normal renderer/x86/legacy/historical tests were not rerun. Only a read-only documentation audit needed correction to skip HTTPS .md URLs. See docs/RR_SURFACE_QUALITY.md; remaining work is diagnosis, not claiming the regression fixed.
- Full Release optional SDK regression passes 7/7. The final surface fixture rr-surfaces-1x1xqyi8 includes texture/PBR/emission/point GPU and SDK dispatch, 16 invalid-input rejections and four isolated fallback guide controls. Point-textured CPU/GPU maximum sample error is 5.23e-8; all scalar sample differences are zero. No source shader or native implementation was modified.
- At 1,024 total reference samples per hit, corrected-guide RR/raw full-frame ratios span 9.89–23.50 and RR/fallback 143.85–303.38 across both cases. Raw/disocclusion/temporal reference-noise diagnostics pass, but estimated reference variance is 1.3–1.5% of the smaller fallback MSE and correctly misses its 1% target. A 2,048-total-sample CLI rerun is underway: texture already passes the fallback-noise target while retaining the spatial/disocclusion/RR-versus-fallback failures. Next is an isolated colour/albedo/signal-convention ablation, not speculative SDK flag changes.
- Initial low-sample textured/PBR sample validation agrees with GPU within 1.10e-7 and independently scalar lighting exactly; emissive inputs also match and do not take an analytic-black shortcut. However RR/raw spatial and revealed-region gates fail, unlike the earlier constant-colour fixture. Confirm at higher sample counts before reporting the magnitude.
- Important fallback semantic correction found during source audit: guide depth is CommittedRayT and guide albedo is s.color, not the RR view-Z and colour*(1-metallic) fields. The port now consumes independently traced matched primary ray distance, normal and base surface colour. Initial fallback numbers are superseded; do not call the earlier RR-guide substitution the unchanged legacy kernel.

- Default fallback is presentationColor's 5x5 Gaussian spatial kernel, with draw-ID equality, normal dot >=.95, depth tolerance max(.005,.02*centerDepth), albedo delta <=.1, and demodulation/remodulation floor .05. Preserve those exact rules for an explicitly labelled float64 CPU algorithm port on RR indirect inputs; do not compare differently sampled legacy screenshots or call the port GPU-bit-equivalent.
- Extend Reference via an opt-in subclass that uses the existing independent triangle tracer plus barycentrics, decoded texel/vertex sRGB interpolation, point/linear wrap/mirror/clamp sampling, canonical sidecar factors and one-bounce PBR throughput/secondary lighting. Keep strict original mode intact. Emissive material scenes must disable the base zero-intensity/ambient analytic-black shortcut.

## RR quality reference (2026-09-03)

- Initial 256-per-batch full-frame reference test passes in 30.49 seconds (Release rr-quality-qmef4xd5). CPU/GPU fresh-sample max absolute error is 7.4908e-8; vector/scalar disagreement is zero after aligning float32 canonical settings. All initial spatial, geometric disocclusion and temporal diagnostic gates pass on the perspective fixture, but quality remains not-qualified. The actual black perspective fixture still fails exact zero, maximum 1.0967254638671875e-5.
- Reference arrays are numeric-only NPZ with exact round-trip checks and recording identity; summaries bind scene/shader/settings, execution report and candidate output. Memory/work are bounded by 16 triangles, 256-primary/64-sample chunks and frame-count times samples-per-batch <=4096. Optional NumPy dependency is isolated from renderer/SDK builds.
- Expanded 1,024-total-sample result (Release rr-quality-sjgynid6) gives RR/raw MSE ratios 0.00815,0.00921,0.03715,0.01916; each moving frame reveals 431 geometrically occluded pixels. Revealed-region ratios are 0.0173,0.0174,0.0206. Full-frame reference noise is 0.093–0.107% of raw MSE. These are narrow diffuse-fixture diagnostics, not a fallback-filter comparison or general acceptance.
- Optional Release SDK suite passes 6/6 (203.91 seconds), including quality harness/CLI failure retention. Final hardening explicitly bounds scene input to 64 KiB and per-draw vertices/indices to 48, and classifies old-camera near/far clipping as outside the prior frustum, not geometry disocclusion. Final optimized Debug and Release quality reruns cover those additions; no native source changes occurred.
- Final quality evidence: Debug python -O rr-quality-anz2918z and Release rr-quality-uvvuebjr, with identical numeric reference arrays and metrics. Each passes 12 rejection cases, 386 scalar visibility comparisons, two frustum controls, analytic lighting/variance/determinism/trail checks and CLI gate-failure/overwrite behavior. Quality remains not-qualified despite passing narrow lit-fixture gates; the black reference is exactly zero while RR peaks at 1.0967254638671875e-5. See docs/RR_QUALITY.md for full assumptions and next coverage gates.

- Existing test Oracle independently traces triangles and implements the fresh diffuse estimator, but scalar full-frame high-sample tracing would be costly. NumPy 1.26.4 is available locally. Implement a chunked vectorized CPU reference for an explicitly admitted constant-colour, non-PBR, fixed-direction-light subset; compare its low-sample output against both the existing scalar oracle and GPU inputs before trusting high-sample results.
- The legacy rendered image uses different primary sampling and cannot serve as a matched RR reference. Reference rays must use each recording's exact half-pixel camera matrices, with independent high-sample randomness and two independent batches for convergence diagnostics. Keep this an offline quality tool, not a shader or SDK change.
- A Windows rg glob tools/scene* was rejected; subsequent searches name the directory/file explicitly. No files were changed by that lookup.

## RR recorded SDK dispatch (2026-09-03)

- Initial recorded-reset test exposed seven RGB pixel differences (max 6.103515625e-5) versus a fresh SDK context, despite identical input bytes/reset/index/delta. Retained artifact Debug rr-recorded-dispatch-vvqmrm9j. This establishes failure of exact reset equivalence, not the internal cause. Recorded mode now recreates contexts sequentially at resets, retaining history within segments and keeping live caps unchanged. Initial expanded test passes after this fix (109.76 seconds); final suites follow.
- Managed admission checks mandatory source identities before host launch, and native admission validates all bytes/matrices/motion before GPU/SDK startup. New RRTRRD01 output binds the whole recording; report validation independently verifies camera deltas, segment indices and source/settings identities. All commands still report raw SDK failure under pinned workarounds and quality not evaluated.
- Debug optional SDK regression passes 5/5, including eight automatic-cut contexts with fresh output equivalence and unchanged peak allocation. Nearest-neighbour visibility-change coverage is 6,14,25 pixels across the moving fixture. This is execution coverage, not ghosting/disocclusion quality acceptance. Final Release and optimized Debug validation are pending; no renderer or shader source changed in this slice.
- Final Release SDK suite passes 5/5 with 18 rejected report mutations, 23 malformed recordings, five damaged outputs and five source mismatches: rr-recorded-dispatch-pq85bdel. Eight sequential cut contexts match independent fresh controls, each peaking at 20 MiB. Crash injection exits 2173 and the reaped worker is followed by byte-identical recovery. Exact-zero quality remains failed in the existing sequence suite. The tested context-recreation workaround is offline only, not evidence of real-time performance or an SDK binary fix.
- SHA-256 comparison confirms eight complete recorded output bundles (stationary, moving, rotated, reset, fresh, cut, eight continuous frames and material inputs) are byte-identical between Debug rr-recorded-dispatch-l1lnsqo4 and Release rr-recorded-dispatch-pq85bdel. This is same-device configuration reproducibility, not cross-GPU or quality qualification.
- Final optimized-Python Debug report rr-recorded-dispatch-wpqr2gu0 passes the full final 18/23/5/5 report/input/output/source rejection suite. SDK-free Release input/recording compatibility passes 2/2 after rebuilding. No renderer/shader source changed and no other architecture, legacy suite or historical comparison was rerun. Next is independent high-sample/temporal/disocclusion quality, not automatic live integration or filter promotion.

- The pinned ffx_denoiser.h defines cameraPositionDelta as previous-minus-current world position. Derive it from actual view matrices; reset frames get zero delta and SDK segment index zero. UV/Z motion stays as recorded. Reference: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/ and the pinned SDK header.
- Keep explicit recorded-dispatch mode and output magic distinct from stationary batches. Managed invocation must verify scene/material/preparation-shader identities; native admission independently validates the bounded recording and all guide/matrix continuity before GPU/SDK creation. Identity checks are not authentication.

## RR renderer-owned recording (2026-09-03)

- Final acceptance: x86 Debug/Release input+record subsets pass 2/2; full x64 suites pass 11/11 each. Release optional SDK regression passes 4/4, retaining the known raw-report and zero-light failures separately. Full python -O recorder test passes ten cases/21 malformed recordings/ten invalid mode/path checks (x64 Debug rr-record-88to_qyf). Stationary, moving and rotated-depth recordings match across all four configurations. No code changes followed final validation. Next is native/managed admission of the provenance-bearing format; current stationary SDK admission remains unchanged.

- Full x64 Release suite passes 11/11; its final reader tests reject 21 malformed files. x86 Debug input/recording subset passes 2/2. A separate Release command confirms case-insensitive pixel/recording output collision is rejected before writing. External scene/shader verification CLI succeeds; all four renderer configurations use the identical preparation DXIL SHA-256 a53c9933fa406d315ac9fe85618d33e5427c01e2afd67eb16850547e558d4452. Local documentation links resolve.

- Full x64 Debug renderer suite passes 11/11 with ten recorder cases. Offscreen geometry changes source identity while leaving first-frame visible input records exactly unchanged. Added a final defensive reader check that rejects a malformed huge pose before float32 distance arithmetic, plus its corruption fixture; no native code or numerical threshold changed.

- Initial recorder test passes nine cases; stationary embedded RRI bytes equal independent legacy prefix exports and final pixels are unchanged. Moving/reset frames pass the existing CPU lighting/geometry/motion oracle. Added a stronger identity fixture with offscreen geometry rather than merely changed scene metadata, rotated/depth motion and Windows case-insensitive output-path admission. No shader changes or relaxed tolerances.

- First three-frame translation capture passes native preparation and independent reader continuity checks. Scene payload checksum is captured from the same successfully validated Load bytes (no reread race); material identity comes from loaded sidecar bytes; settings use explicit canonical fields; the actual loaded preparation DXIL hash must remain constant across frames. No SDK accepts RRTRRC01 yet.
- New recording uses the renderer's continuous randomSequence for the dedicated fresh preparation pass, because the legacy non-temporal image sample index restarts on camera movement. Existing single exports keep their old index convention. Per-frame temporary GPU charge (2,359,808 bytes) is retired only after fenced preparation returns and its resources are destroyed. Measured peak is 5,327,216 requested bytes, independent of frame count on this fixture.

- The exporter currently runs only after RenderTo; extracting its byte preparation permits per-frame capture in the same renderer lifetime without changing shaders. Keep this new provenance-bearing recording distinct from the old manually packed stationary bundle, so old worker admission cannot silently accept motion.
- Session recovery found no unsynced context and source-scoped AGENTS search found none. Initial combined source inspection was truncated; subsequent reads use focused ranges.

## RR stationary sequence design (2026-09-03)

- Final compatibility: normal x64 Release build/CTest passes 10/10. Full python -O sequence verification passes with the same execution/failed-quality separation (Release rr-sequence-cd7frnye). No source changes followed final verification. Other configurations and historical comparisons retain prior evidence. The planning skill's completion helper reports 0/0 for this checklist-based format; reviewed the three current milestones manually.

- Final expanded SDK CTests pass 4/4 in Debug and Release. Reports: Debug rr-sequence-h1u2u4h7 and Release rr-sequence-wdl___wc, each with 17 rejected malformed sequences, 13 report mutations and five malformed outputs. All reset-only regression checks remain passing. Python compilation, command help and optimized-Python pack CLI pass; relative documentation links resolve.

- Initial Debug and Release sequence checks pass, including lit-to-dark reset isolation and real SDK allocation-failure recovery. The first two zero-light frames retain the same maximum bias (1.0907649993896484e-5); MSE is 9.602695114768744e-11 then 9.556961443289251e-11. Temporal history changes 38,037 payload bytes versus resetting the same final sample; this is influence, not a quality improvement metric. Added explicit exact-zero gate and additional changed-guide/validity rejection cases before final verification.
- Integrity is not complete scene provenance: RRI files do not identify occluded geometry or all settings. Stationary prefix preparation requires the caller to use the same source/options; matching visible guides cannot prove that independently. Document this limitation and require a renderer-owned sequence recorder before arbitrary camera/lighting histories.

- First persistent-context sequence executes: eight frames reuse the same eight external resources and one SDK context. Repeated four-frame segments match after reset, fresh-process repeats match, and a lit-to-dark reset matches an independently started dark sequence. Same-final-sample reset ablation differs from history-enabled output, establishing temporal influence but not better quality. Original three Debug SDK CTests still pass after the texture reuse refactor.

- Pinned SDK dispatch takes a frame index and explicit RESET flag; reuse one context between stationary frames with unchanged camera, unit motion scaling and no camera delta. Official integration reference: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/ . Reset begins a new zero-indexed segment. Input motion retains the export's tiny numerical residuals (bounded at 1e-5), not invented motion.
- Windows rg does not expand src/dxr/*.h; search the directory with rg -g instead. Direct-light noise can vary with random sun samples, so this first strict stationary contract requires identical direct/emission and material/geometry guides; prepare with zero light radius where necessary. It rejects unsupported changes rather than assuming continuity.

- The existing worker only accepts reset frames and creates one context per process. Next slice is a bounded 2..8-frame stationary sequence in one context, not a persistent live service. Deterministic prefix exports can supply successive fresh samples if seed, frame counters, camera and all non-random guides/direct lighting match exactly. Moving-camera sequence recording remains separate work.
- Session catchup reported no unsynced context; no source-scoped AGENTS.md was found. Existing execution/quality results remain separate; zero-light bias is unresolved.

## RR typed textures / first dispatch (2026-09-03)

- Final optional SDK CTests pass 3/3 in Debug and Release; optimized-Python dispatch verification passes execution checks. Normal x64 Release renderer suite passes 10/10. Final reports are Debug rr-dispatch-_ol2jef3 and Release rr-dispatch-ajfh25q9: 11 cases, 18 report mutations, nine malformed inputs and six malformed outputs. Both record failed-zero-light-oracle, not accepted image quality. Reproduction and next sequence/history gates are in docs/RR_DISPATCH.md. No default renderer source/shader was changed in this slice.

- Strict zero-light quality check fails with maximum 1.0907649993896484e-5, 29,928 nonzero RGB components and MSE 9.602695114768744e-11; execution/input-isolation checks already pass. This is retained, not clamped or relabelled as a quality pass. The test records execution evidence to completion and provides --require-zero-light to enforce the separate unchanged exact-zero oracle.

- First managed SDK output is real: one Dispatch call, two fenced submissions (upload roundtrip and SDK/output roundtrip), 9,976 active pixels changed, unchanged input textures, exact six-allocation SDK cleanup and eight external resources released. External allocation-info total is 1,900,544 bytes; internal callback peak remains 20,971,520. Raw memory/metadata failures persist and remain reported separately.
- Added independent Python half-float packing hashes for all six textures, output checksum/input identity/alpha checks, zero-light oracle, reset repeatability and budget/SDK-failure recovery tests. Output alpha is seeded from clamped distance; RGB remains poisoned before dispatch. Preview is a generated raw-versus-RR composite at equal exposure, not a quality acceptance result.

- First execution returns FFX_OK and completes GPU work. Diagnostic rerun shows only active output alpha retaining its poison sentinel: RR preserves that output channel rather than copying input alpha. Initialize output alpha from the packed input distance, retain poisoned RGB, and continue requiring all RGB writes/finite nonnegative values and unchanged alpha. This matches the public contract's "Preserved" output-alpha wording; no raw acceptance check is removed.

- Reset-only 128x96 indirect diffuse is the first execution gate. The input exporter is not a sequence recorder, so reject non-reset files rather than pretending SDK history exists. Keep raw diagnostics and post-context reporting workarounds separate from dispatch execution/quality.
- Public pinned SDK includes DX12 resource conversion helpers; use declared compute-read/UAV states and separate input/output textures. External textures/staging will have their own hard 8 MiB allocation-info budget in addition to the existing 64 MiB SDK callback ceiling. No renderer or game process loads the SDK.

## RR input preparation (2026-09-03)

- Final independent matrix round-trip checks pass in all four configurations. Their maximum normalized error (1.54973e-6) is larger than the original per-pixel-only maximum but far below the unchanged 5e-4 threshold. Final reports: x64 Debug rr-inputs-zbnlbnpi, Release rr-inputs-60ribafz; x86 Debug rr-inputs-_ega9x02, Release rr-inputs-wy0abny6. No source changes followed final acceptance.

- Final official-sample audit confirms the normals channel receives material.perceptualRoughness directly, not alphaRoughness; the implemented unsquared authoring roughness matches that sample despite the header's "linear roughness" wording. AMD uses 65504 for missed diffuse rays in its FP16 sample; our diagnostic retains float32 ray TMax=100000 and explicitly leaves FP16 conversion/clamping to the typed-texture gate. Sources: pinned Samples/Denoisers/FidelityFX_Denoiser/dx12/shaders/{material,trace_rays_denoiser}.hlsl at commit 60f4ea81909200d8542eca14dccb2628b763a9a3.
- Optional SDK contract/worker tests still pass 2/2 in both configurations. Final 15-case RR input checks pass on x86/x64 Debug/Release, and python -O passes. Historical renderer comparison matches all 53 files in temporal-tfxl8br7. A final git-status check confirms this workspace still has no Git repository; no Git operations were performed.

- Fourteen initial GPU/CPU scenarios pass, including PBR/emission, per-texel linear filtering, scissor, negative signed depth, and nonzero view-Z motion. Maximum normalized error is 5.31947e-7 on this fixture (unchanged 5e-4 threshold). Added invalid-previous-projection coverage and early camera/extent rejection. A new size-rejection test initially called resized with a scene argument; inspected the helper and corrected to its two-argument width/height signature.

- The next fixture setup reached the same tuple mutability issue in sampler state. Replaced piecemeal conversion with recursive tuple-to-list conversion at the fixture boundary, covering all editable decoded fields. This is a test-authoring error, not GPU/API failure; no tolerance or acceptance gate was relaxed.

- Initial GPU/CPU cases passed through stationary/seed/motion/cut/reset. The test fixture mutation then hit immutable decoded vertex tuples; convert fixture vertices to lists before mutation. Also aligned the new PBR test adapter with the existing target/emissive authoring schema. No shader correction was required.
- All five rebuilt baseline compute DXIL hashes are byte-identical to pre-change files (rayquery 18b00ad9..., present afc48fa1..., temporal ee1ad399..., export 6a6fe33e..., variance 39d25d7e...). The new macro leaves legacy compiled shading unchanged.

- Added dedicated half-pixel-centred, unjittered primary rays for RR; all new signals share that hit. Legacy integer-centred primary rays are untouched. Material class stays zero, and invalid/first-frame motion is explicitly marked in a diagnostic channel.
- A search included a nonexistent verify_dxr_temporal.py; the existing helper is verify_temporal.py. One main.cpp patch failed an exact-context match and applied no changes; reapplied using complete matching lines. Neither failure changed design or data.

- Pinned 2.3.0 header confirms row-major row-vector matrices; diffuse albedo BaseColor*(1-Metalness); signed view Z; previous-minus-current UV/Z motion; indirect RGB radiance with hit distance in alpha. GPUOpen recommends initial material type zero. Source: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/ .
- Choose a separate opt-in 128x96 GPU preparation/export pass, not changes to the legacy GI estimator. Compile reused shading functions with linear texel/vertex decoding only for the new shader. Six float4 records (96 bytes/pixel) plus five camera matrices in a versioned checksummed export permit an independent CPU oracle before typed textures and SDK dispatch. Default shaders, buffers and pixel/signal formats remain unchanged.

- Existing GI uses independently jittered primary samples but unjittered diagnostic guides; those cannot be passed together to RR. New opt-in input generation must share the primary hit and leave default sample RNG/output unchanged.
- Initial file discovery accidentally included build artifacts and truncated its output; narrowed subsequent discovery to source/test paths and excluded build. No file changes resulted. No AGENTS.md found outside build; session catchup returned no unsynced context.

## RR containment acceptance (2026-09-03)

- The managed context contract now passes with exact DLL-hash-pinned reporting workarounds; strict raw SDK diagnostics still fail. Callback accounting is a substitute for this known bad memory report, not total residency. The requested provider override is recorded independently of the failed metadata query.
- Debug/Release optional CTests pass 2/2; x64 Release renderer regression passes 9/9. Evidence: build/rr-sdk-probe/Debug/rr-worker-rs6ouxp8/verification.json and build/rr-sdk-probe/Release/rr-worker-lpujrfgh/verification.json. Real SDK allocation failure is contained and a fresh worker succeeds. Parent-exit cleanup, deadlines, output flooding, malformed/deep JSON and unreviewed DLL rejection are verified.
- Final review replaced Python 3.11-only hashlib.file_digest with bounded streaming SHA-256 to retain the declared Python 3.10 floor. Actual runtime verification uses installed Python 3.12. Explicit validation survives python -O. This process boundary is not a hostile-code sandbox, a GPU-driver failure guarantee, a persistent rendering worker or a live-game bridge.

## Variance-aware filtering design (2026-09-03)

- Current presentation performs a 5x5 geometry/albedo-guided blur with albedo demodulation, without luminance edge weights. Temporal resolve already retains luminance moments/counts; no raw per-pixel second-moment accumulation exists.
- Keep the old filter unchanged and add an opt-in single-pass variance-aware alternative. Use local spatial variance for short/no temporal history, temporal variance/count for mature history, world-plane/distance and material/albedo/normal rejection, and direct radiance filtering (avoiding diffuse demodulation of specular/emissive PBR values).
- SVGF motivates variance-guided edge stopping but is a hierarchical wavelet algorithm; this bounded implementation must not be called SVGF. Primary reference: https://research.nvidia.com/labs/rtr/publication/schied2017spatiotemporal/ .

## Material/light input design (2026-09-03)

- RRTMAT1 uses a 16-byte header, sorted 64-byte records (material SHA-256 plus eight float32 values), and a 32-byte payload digest. Renderer and compiler independently enforce count/size/range/identity bounds. Factors extend GPU draw metadata to 84 bytes; 224-byte frame data still fits the existing per-slot 256-byte allocation.
- Shader compatibility is preserved by explicit per-draw opt-in and a coloured-light flag. Initial historical comparison matches all 53 prior files. Light-colour components beyond the original 128-byte configuration prefix are included explicitly in history identity; the sample flag mask also preserves the new bit.
- The first metal-transport test incorrectly treated unjittered guide IDs as jittered sample IDs at silhouettes. Interior-only emissive-on/off comparisons correctly isolate transport without changing rendering or tolerances. GGX normal/angled/tangent lighting and tilted-view checks match the independent CPU reference; initial maximum normalized error was 2.64e-7.

- Scene v1 already exposes SHA-256 material IDs incorporating texture ID and fixed-function state. A separate material-ID sidecar can be shared by matching captures without changing the raster oracle, capture format or existing mod compiler.
- Existing renderer uses literal RGB, flat geometric normals, white directional lighting and one diffuse bounce. Optional PBR records must be explicitly opt-in; do not relabel the default pipeline or promise specular reflections/full colour-managed glTF rendering.
- Use GGX distribution, correlated Smith visibility and Schlick Fresnel for direct lighting; bounded roughness avoids the zero-roughness singularity. References: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html and https://google.github.io/filament/main/filament.html .
- Inspection command using a nonexistent tools/rrt_mod* pattern failed; actual existing authoring tool is tools/mod_scene.py. Reused its strict JSON/field validation helpers after inspecting the real file.

## Waitable-frame admission (2026-09-02)

- DXGI frame-latency handles require the waitable creation flag, explicit handle closure, and admission before the first rendered frame. The flag is preserved during ResizeBuffers. Maximum latency one is explicitly set and read back; this is separate from the four-slot command/fence ring.
- The message-aware wait uses QS_ALLINPUT and MWMO_INPUTAVAILABLE with a 100 ms timeout. A consumed permit survives the next message-pump pass so new input can be applied without losing admission. Timeout does not grant permission or submit more rendering; device status is checked on each new wait.
- Normal native interactive startup now defers sample one until admission. Static --show remains a precomputed-image preview. Comparison-window diagnostics issue extra presents and remain explicitly unpaced; --no-frame-pacing provides a native opt-out.
- Hidden-window Radeon tests do signal real DXGI admission. Separate event-based checks cover message/timeout return paths; do not conflate them with physical display stalls. Exact pixels/signals and lifecycle/resource tests do not measure scanout or input latency.
- Microsoft primary references: [waitable handle](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_3/nf-dxgi1_3-idxgiswapchain2-getframelatencywaitableobject), [maximum latency](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_3/nf-dxgi1_3-idxgiswapchain2-setmaximumframelatency), [message-aware wait](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-msgwaitformultipleobjectsex).

## Requirements
- Map the design space for an RTX Remix-inspired AMD project, with ROCm considered as the compute platform.
- Recommend a practical MVP and roadmap rather than assume feature parity is immediately possible.

## Research Findings
- Final async evidence: build/x64-renderer/Release/async-4noh41bt/verification.json; all six DXR tests pass on both architectures/configurations. Both full x86 suites report 10/16, with the same six legacy failures and fresh S_PRESENT_OCCLUDED evidence (Debug verify-classic-z7ei6shp, 12/12 Presents). Historical scene/pixel/signal parity remains exact for 53 files in build/x64-renderer/Release/temporal-xkf1p403/verification.json. Allocation remains bounded; no performance guarantee follows from reduced CPU readbacks.
- Async acceptance initially passes at 128x96, 257x129 and 1920x1080. The 129-sample control sequence uses six renderer snapshots, and early close after seven queued samples uses one final readback; small-scene signal files and all pixel files match synchronous references exactly. Four slots are exercised with at most four observed in-flight submissions; all sample timings are collected. Final-layout full-HD peak is 525,341,796 requested bytes with resize validation, still below 512 MiB. Evidence: build/x64-renderer/Release/async-975mqyl1/verification.json.
- Close-path correctness: unrendered queued controls must not change exported-image metadata. Defer pending configuration while the window cannot render, and restore the reported options to the last actually submitted sample at close. The early-close diagnostic now queues a mode change immediately before close and checks both output bytes and mode/filter/temporal labels.
- Async/readback design: four allocator/list slots bound queued CPU submissions, with a fence per slot and per-back-buffer display fences. Each renderer slot owns a 256-byte constant region and five timestamp queries/readback offsets. Temporal resources stay shared on one ordered queue with existing barriers; no cross-queue or concurrent temporal evaluation is introduced. Microsoft references: https://learn.microsoft.com/en-us/windows/win32/direct3d12/fence-based-resource-management and https://learn.microsoft.com/en-us/windows/win32/direct3d12/recording-command-lists-and-bundles .
- Native samples omit output copy/map and immediate fence waits; explicit snapshots, exports, resize and normal shutdown drain queued work. Timestamp intervals are collected on safe slot reuse or drain. Present remains vsynced; allocator/back-buffer fences provide bounded back-pressure, not a DXGI waitable-object latency controller. Synchronous headless/GDI/window diagnostics remain comparison paths; new asynchronous diagnostics verify sparse checkpoints and final images.
- Final native-sprint matrix: new DXR tests pass in all four builds; x64 Debug/Release 5/5 each, x86 Debug/Release 9/15 overall because six legacy capture/mod/proxy tests encounter the recurring S_PRESENT_OCCLUDED status. Inspected classic trace has 12/12 Present results 0x08760878; exact system/proxy pixels agree before the successful-Present assertion. Isolated classic rerun reproduces after other rendering ended, so concurrent tests alone do not explain it. Desktop cause is not established, and no presentation/capture semantics were changed. Do not claim full regression qualification until a normal-Present rerun passes.
- Native presentation acceptance passes five fixture cases including 1920x1080 temporal/spatial GI. In the initial run, all 21 display submissions per case compare every back-buffer pixel exactly, both buffers are used, three actual resizes preserve renderer history, and controlled minimize/restore suppresses then resumes display. Full-HD peak allocation is 525,341,028 bytes (including resized back buffers and diagnostic readback), under 512 MiB; too-large growth rejects before releasing old resources, and a subsequent draw verifies those remain usable. Non-diagnostic over-budget resizing is currently fail-fast, not adaptive resolution.
- Native display does not remove renderer readback or per-sample waits yet. The next bounded slice is readback decoupling and per-frame allocator/constants/fence ownership with frame pacing. A post-change temporal baseline run matches all 53 prior scene/pixel/signal files: build/x64-renderer/Release/temporal-1fkn55n6/verification.json.
- Native presentation design: use a two-buffer FLIP_DISCARD HWND swapchain on the existing D3D12 direct queue, with a fullscreen graphics pass reading packed GPU pixels. Source render dimensions/history stay fixed; display resizes use nearest-pixel integer mapping. Preserve an explicit --gdi path; do not mix GDI drawing into a swapchain HWND. Microsoft references: https://learn.microsoft.com/en-us/windows/win32/direct3d12/swap-chains and https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ne-dxgi-dxgi_swap_effect .
- Synchronization remains deliberately synchronous: fence after Present before reuse/resize/release, release all back-buffer and recorded-command references before ResizeBuffers. Diagnostic display readback uses GetCopyableFootprints row pitch and compares every actual back-buffer pixel against the CPU/headless oracle, including resized windows. Display allocations count toward the same aggregate budget, with peak accounting separate from final persistent renderer storage.
- Occlusion caveat: Microsoft documents that flip-model swapchains do not normally return DXGI_STATUS_OCCLUDED. Handle/test the status branch conservatively but do not claim hidden windows prove real desktop occlusion/scanout. Minimize/restore acceptance uses controlled WM_SIZE messages in a hidden window; visible desktop/DPI/fullscreen/device-loss qualification remains open. Reference: https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/dxgi-status .
- Compact-buffer sprint: the final working record is 88 bytes and each temporal record is 64 bytes, retaining full float32 lighting/guides/motion/moments. Runtime signal memory drops from 288 to 216 bytes/pixel; with raw/output/readback the total drops from 312 to 240 (23.1%). Export uses a fixed 4.5 MiB GPU/readback pair and a separate reconstruction pass, not a full-frame signal readback.
- Precision finding: reconstructing motion from the stored hit position in an initial 80-byte layout changed floating-point rounding at the frustum boundary. Basic acceptance passed, but comparison with saved temporal artifacts found changed projection validity at 85 pixels and downstream history differences. Preserving the original motion pair and bit-packing only integer validity/count/reason restored byte-exact matching across all 50 historical pixel/diagnostic files. No lighting precision reduction was needed.
- Final-layout full-HD Release evidence: build/x64-renderer/Release/resolution-gaes_1le/verification.json. Four-sample temporal/spatial GI requests 497,681,520 bytes (474.63 MiB); exporting requests 502,399,856 bytes (479.13 MiB), under unchanged 256 MiB individual/512 MiB aggregate limits. Export is 298,598,436 bytes in 127 chunks, stream-validated with matching output hash. The 2560x1440 fixture rejects before creating outputs. These are requested buffers, not measured VRAM or game-scale performance.
- Inspector now shares validation across a 256 MiB random-access API and a 1 GiB bounded streaming CLI/API. Chunk tests cover a partial tail, finite/valid signals, exported colour parity, late corruption and size errors. Native swapchain work remains separate; first preserve headless output as an oracle and establish back-buffer ownership/resize/occlusion handling before removing GDI/per-sample CPU waits.
- Visually inspected Release temporal-zeierock/moved.png against reference.png: stable areas are smooth, while newly revealed/rejected regions still show expected fresh-sample grain and the shadow remains localized. This confirms the intended lack of old-surface ghosting in the fixture, not full denoiser quality; rejected-region spatial filtering is optional and was off in this comparison.
- Historical temporal-sprint limit (resolved by the compact-buffer sprint above): 144 bytes/pixel per ping-pong buffer plus optional 144-byte readback exceeded full-HD budgets.
- Temporal sprint design: double-buffer complete renderer signals; consume fresh stochastic RGB, not cumulative radiance. Conservative nearest-pixel reprojection checks draw/albedo/normal plus world-space plane/position agreement. Separate moments and effective history cap (32) support diagnostics while raw accumulation remains unchanged.
- Temporal GPU suites pass after correcting a test's reset-counter assumption: 18 raw resets include a return from non-GI, so only 17 valid temporal buffers are discarded. Stationary means and second luminance moments match independent fresh-sample calculations; translated-camera reuse reduces accepted-pixel float-RGB MSE from 0.00028201 to 0.000017343 against 256 samples. Same-draw/two-depth fixture rejects 1,449 surface-position mismatches and accepts 9,111 pixels; 1,419 genuinely revealed ground pixels explicitly reject the old foreground. Final x86 Debug/Release each pass 13/13, x64 each 3/3. Release evidence: build/x64-renderer/Release/temporal-r1d7hezu/verification.json.
- Signal/filter sprint: raw unquantized mode RGB, unjittered albedo/geometric-normal/near-plane ray distance, camera-only previous-minus-current pixel motion and separate filtered RGB now have an 80-byte GPU record and bounded RRTSIG01 export/inspector. The 36-byte file header identifies mode as well as dimensions, samples and requested filtering.
- A separate GPU presentation pass performs opt-in 5x5 geometry/albedo-guided filtering without feeding back into accumulation. One-sample fixture MSE drops from 109.3787 to 29.2402 against 256 samples; raw RGB/guides remain byte-identical when the filter is toggled. Inspected Debug dxr-glgtoq6c signals-raw.png and signals-filtered.png: visibly reduced grain, foreground triangle/shadow retained, some expected edge/illumination softening.
- Motion is current surface projected through the previous completed sample's camera, without jitter. A +0.1 world-X/Y move produces (+6.4,-4.8) pixels in the 128x96 orthographic fixture. First/background/out-of-previous-frustum motion is invalid; stationary later motion is approximately zero. Validity is projection-only, not disocclusion safety or animated-object motion.
- The previous occluded-display regression condition cleared in this sprint: full x86 Debug and Release each pass all twelve entries with no changes to D3D9 capture/trace/sample semantics. Both renderer-only x64 configurations pass 2/2. Release signal/filter evidence is in build/x64-renderer/Release/dxr-df3x44pj/verification.json.
- Progressive Phase 5: scene uploads, BLAS/TLAS, pipeline, float accumulation and readback resources now persist across samples. Stationary accumulation resets on camera/lighting/render-setting changes; no reprojection or motion buffers are claimed. Each sample still synchronizes and reads back to a GDI preview.
- RX 9070 XT GI tests: fixed-seed output repeats exactly; 32 samples reduce MSE from 109.3787 (one sample) to 3.5835 against a 256-sample reference. An edge-on red/blue wall is invisible in the albedo image but produces approximately 20.6 corresponding colour-channel levels on nearby ground through secondary diffuse transport.
- History diagnostic: 136 dispatches, 16 resets, one scene-build submission, 311,920 requested buffer bytes throughout. Hidden-window diagnostic: 33 dispatches/four resets, paused navigation and Home/resume restore the headless result exactly. This validates the application's message loop, not fullscreen/DPI behavior or game integration.
- Current sprint DXR tests pass in x86/x64 Debug/Release with standard D3D12 debug-layer checks. Six older x86 capture/mod/equivalence tests per configuration fail in this run with Present status 141953144 (0x08760878, S_PRESENT_OCCLUDED in the installed Windows SDK). Existing capture and trace gates intentionally require S_OK; pixel/summary equality with system D3D9 passes before the present-count assertion. Desktop state is suspected, not confirmed; capture semantics were left unchanged and full qualification awaits a normal-presentation rerun.
- Inspected progressive `build/x64-renderer/Release/dxr-kz90jed1/bounce-red.png`: visible red indirect tint and wall shadow on the ground, with the foreground triangle and captured background retained. Full evidence is in that directory's verification.json.
- Phase 5 now executes hardware inline ray queries on RX 9070 XT (DXR tier 1.1, SM 6.5 checked). The x64 probe reports 16,974,905,344 DXGI dedicated bytes; x86 reports a limited pointer-sized value, so standalone rendering has its own x64 preset while capture remains x86.
- DXR ground/occluder albedo matches the D3D9 oracle exactly in the recorded fixture; actual secondary shadow rays darken 240 expected pixels. Perspective/world/view/scissor checks have zero pixels over two levels of error, with mean channel errors 0.00472 (point) and 0.09435 (linear). These are synthetic acceptance results, not a universal equivalence claim.
- Visually inspected x64 Release `dxr-_9iqyq5w/relit.png` and `camera-2.png`: the foreground triangle casts the expected offset dark shadow on the ground; the perspective textured plane and clipped foreground agree with the tested scene. Shader output is real GPU readback; its static preview uses GDI, not a new presentation loop.
- GPU timestamp intervals are measured separately from CPU/driver wall time. Tiny fixture timing is not indicative of game-scale performance. Requested buffer byte accounting also excludes driver heap granularity and is not residency measurement.
- Phase 4 verification: all ten CTest entries pass in Debug and Release on the recorded RX 9070 XT. Per-kind replacement tests leave unmatched draw data and unaffected image quadrants byte-identical. Combined scene output is deterministic across fresh fixture sessions and mod argument order; a static mesh target continues matching after Reset. The combined visual preview agrees with the numeric isolation report.
- Phase 4 resolver matches against original capture IDs and composes mesh, texture and material replacements independently. This avoids a texture replacement changing material identity before the material match. IDs describe content, not persistent game objects: a genuinely updated animated texture correctly needs a different target, while unchanged static mesh content survives Reset.
- Priority is per (kind, original asset ID); equal-priority overlaps are errors, not command-line-order wins. Material patches from losing entries are not field-merged. Both encoded dependency bytes and decoded texture/geometry sizes are budgeted.
- Phase 3 first slice now reconstructs CPU-written XYZ/diffuse/UV triangle geometry and mip-zero 2D textures into a versioned scene. Native-resource-owned private-data shadows avoid stale pointer identity and extra COM references that would block Reset. SHA-256 mesh/texture/material IDs are independent of session wrapper IDs.
- The independent native-system-D3D9 replay matches every colour byte of four visible fixture draws for frames 0/1/6/7 in classic/Ex, Debug/Release on the recorded RX 9070 XT. Six negative-case categories and ten malformed variants are tested; the final seven-entry CTest suite passes in both configurations.
- glTF is useful for asset interchange but not an exact substitute for the D3D9 raster oracle: arbitrary camera matrices, culling, alpha/blend functions, scissor and colour-space conventions cannot all be preserved automatically. Export retains legacy state in extras and documents this boundary.
- Implementation verification: native and proxied D3D9/9Ex produce identical textured-fixture image bytes on Radeon RX 9070 XT, driver 32.0.31041.1004. Debug and Release each pass five CTest entries, including capture validation, identity/lifetime recovery, selected ranges, byte budgets, and trace failure isolation.
- Phase 2 session object IDs describe wrapper lifetimes, not stable geometry hashes. Frame-selected observation traces intentionally omit prior state; the separate Phase 3 scene capture tracks earlier resource writes and snapshots effective state at the selected frame's draws.
- ROCm/HIP is available on Windows, but AMD explicitly describes the HIP SDK as a subset of ROCm and notes that some HIP runtime API functionality is not yet supported on Windows. Supported GPU coverage is SKU-specific. This makes HIP a poor *mandatory* dependency for a broad consumer-game runtime.
- RTX Remix's useful reference architecture is: a local `d3d9.dll` interposer captures legacy fixed-function Direct3D calls; a renderer reconstructs scene data, hashes assets for replacements, and path traces the reconstructed scene. Its practical target is DX8/9 fixed-function games, not arbitrary old titles.
- NVIDIA's own compatibility guidance highlights the core technical limit: a renderer needs sufficient semantic geometry/material/light information to reconstruct a scene; this is not extractable in a standard way from every game.
- AMD's current tools cover graphics profiling on Vulkan/DX12 and compute profiling on HIP/OpenCL. They are useful for validation, not substitutes for an end-user runtime graphics API.
- DXR is exposed through the standard D3D12 ray-tracing interfaces, so it is a more appropriate baseline for a Windows renderer than HIP RT. HIP can interoperate with Vulkan external memory/semaphores, but that is an optimization/research path, not required for an MVP.
- FidelityFX FSR provides source integrations for D3D12 and Vulkan. Frame generation requires deliberate swapchain, frame-pacing, and UI handling, so it should follow renderer correctness rather than precede it.
- FSR Radiance Caching is a DX12 technical preview. It is an online-learned cache driven by training/query samples emitted by a Monte Carlo path tracer, and requires normalized hit positions, normal, view direction, albedo, roughness, and radiance buffers.
- Brixelizer GI is a separate compute-based GI technique using sparse distance fields, G-buffer inputs, and internal temporal radiance/irradiance caches. It is a possible non-DXR fallback after scene extraction is reliable.
- Current FSR SDK 2.3 candidates: FSR Upscaling 4.1.1 with automatic FSR 3.1.5 fallback on unsupported hardware; Frame Generation 4.0.1 with FSR 3.1.6 fallback; Ray Regeneration 1.2.0 for RX 9000-series-or-newer, Windows 11, DX12, and SM 6.6; and Radiance Caching 0.9.0 as technical preview. Upscaling is the first production-facing integration; frame generation follows only when the runtime owns presentation/UI pacing.
- Reference title rule of thumb is early DX9/2000–2005 with mostly fixed-function draws. The selection must be based on proxy/trace evidence; existing compatibility reports are leads only. Shader-heavy DX9 games are negative tests, not a first target.
- BioShock 2 original supports D3D9.0c/D3D10 and can be forced to D3D9, but its 2010 modified Unreal Engine renderer should be treated as a later shader-heavy observability target. BioShock 2 Remastered lists D3D11 and is out of scope for this D3D9 interposer.

## RR follow-up investigation (2026-09-03)

- Issue-resolution audit: public v2.3.0 ffx_api.cpp confirms our pointer-to-context query shape and provider-override chain; it does not guarantee clearing the caller's handle after destruction. No supported client-side query change was identified that fixes the bad totals. Preserve raw results. Next mitigation: a suspended-start Windows job boundary for the SDK child, bounded output/deadline, authoritative callback accounting, and an explicit pinned-SDK workaround policy rather than relaxing the raw SDK diagnostic.
- Public source inspected: https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/v2.3.0/Kits/FidelityFX/api/internal/ffx_api.cpp . The closed denoiser binary is not being inspected or modified.
- Implemented suspended-start native child/job ownership before loading the SDK, inherited-handle allowlist, 64 KiB-per-stream limits, deadline termination, and kill-on-job-close. The outer native process returns an envelope, not a claim of SDK success. Source references: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects and https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw . One attribute-list reference failed to open; the local Windows SDK declaration supplies the compiled contract.
- The managed Python policy checks exact DLL SHA-256 values before enabling reporting workarounds. It requires the known 128x96 context, matching provider override, six successful/released allocations, 20 MiB peak, zero outstanding bytes/errors/denials and exact known bad report signatures. Other errors fail closed. Raw SDK acceptance remains failed; this separately qualifies containment and callback-accounting substitution, not SDK rendering.

- Context sprint: callbacks receive backend effect ID 22, not public API effect ID 0x50000. Exact-ID rejection was incorrect and removed. After that fix, real 128x96 context creation returns OK with two heap/four resource allocations, and actual memory query succeeds. The optional general provider-version query returns parameter error 6, and destruction currently access-violates. Investigating callback destruction semantics against the official sample; no dispatch or renderer changes have been made.
- Teardown root cause resolved: successful SDK destruction leaves the caller's handle non-null on this provider, causing our RAII destructor to destroy it a second time. The official denoiser sample explicitly sets its context to nullptr after destruction. Mirrored that ownership rule; creation and destruction now return OK, all six tracked allocations release, and callback live bytes return to zero. Peak committed allocation is 20,971,520 bytes.
- New accounting anomaly: with custom heap/resource callbacks, the post-context memory query returns code OK but total 18446744073689694208 bytes (near uint64 wrap), aliasable 65536. Keep this invalid result explicit; do not describe it as valid residency or lift budgets. Investigate SDK-vs-callback accounting independently from the now-working context lifetime.
- Default SDK allocator control reproduces the exact invalid post-context total, so the anomaly is not specific to our allocation callbacks. The default control is explicitly labelled preflight-only, not hard-budgeted, and is restricted to the fixed small 128x96 case. General provider-version metadata query returns 6 in both modes.
- Deliberately denying the second heap allocation returns FFX_API_RETURN_ERROR_MEMORY from our callback, but the provider then passes an invalid heap to CreatePlacedResource. Standard D3D12 diagnostics report a corrupt first parameter and the isolated child exits with exception code 2173 (0x87d). This is not graceful SDK failure cleanup. No driver restart/game changes or automatic runtime fallback were attempted.
- Expanded standalone tests separate allocator-contract correctness and context mechanics from SDK acceptance: callback resource/heap budgets, injected rejection and exact releases pass; three ordinary context lifecycles create/destroy and return tracked bytes to zero; a fresh process can create/destroy again after the injected crash. Full SDK acceptance intentionally still returns failure because accounting/failure handling are unresolved. No context test is registered as passing CTest acceptance.

- User selected deeper denoiser research after the three custom-filter quality failures. AMD RR is the next target, not another claim that the experimental filter passed.
- Official RR 1.2 documentation exposes per-signal dispatch descriptions (direct/indirect diffuse/specular and visibility), unlike older Input1/2/4 examples. Use pinned headers and actual provider enumeration instead of guessing ABI or treating GPU family as sufficient support.
- Current renderer has combined accumulated RGB, ray-distance depth, pixel-space XY motion, unencoded geometric normals, literal captured colours and independently jittered rays. These are not an RR-ready G-buffer. Start with a separated fresh indirect-diffuse signal; keep emission/direct lighting out of that signal and defer specular transport/hit-distance work.
- Memory is a real gate: our full-HD requested allocations already approach 512 MiB. AMD's published one-signal internal allocation exceeds our remaining headroom even for persistent history. Initial integration should use a smaller fixture and a pre-context memory query, not raise budgets silently or assume aliasable memory is free without implementing heap aliasing.
- Sources: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/ and https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/releases . SDK distribution/header details and actual provider availability are still being checked.
- SDK v2.3.0 resolves to commit 60f4ea81909200d8542eca14dccb2628b763a9a3. Downloaded only five headers, the loader/effect DLLs and full license notice to build/dependencies/fsr-2.3.0-probe, not the renderer output or any game directory. Both DLLs have valid AMD Authenticode signatures. Header licenses are permissive; binaries carry AMD's separate distribution notice (retained with the dependency); do not label the whole SDK MIT or reverse-engineer it.
- Pinned denoiser header confirms indirect-diffuse alpha is a bounce hit distance too. It must be generated by the tracer, not filled with the existing accumulation alpha. The first prototype will need to add that alongside signal separation.
- Added an optional, x64-only standalone query tool using official header structures and explicit DLL paths. It does not create contexts, dispatch shaders, raise renderer budgets or infer RR readiness from SM/GPU names. Provider results and memory queries remain pending execution.
- Executed the probe: RX 9070 XT supports the SM 6.6 query and enumerates provider 4311875584, "FSR Ray Regeneration - 1.2.0". For indirect diffuse alone, pre-context total/aliasable/persistent bytes are 19988480/17498112/2490368 at 128x96; 79298560/57409536/21889024 at 960x540; 279576576/208797696/70778880 at 1920x1080. This is actual provider-query evidence, not context/dispatch/image-quality acceptance. Do not treat the earlier renderer's capped SM 6.5 query as a hardware maximum.
- Shell discovery correction: PowerShell returned a JSON array as one pipeline object for contents; using the recursive tree and explicit JSON formatting recovered exact paths. No dependency content was guessed.

## Technical Decisions
| Decision | Rationale |
|---|---|
| Keep graphics presentation based on standard Windows APIs | A game-injection runtime must interoperate with legacy games and Windows graphics stacks. |
| Treat ROCm 10 as an optional authoring worker | HIP 10 improves general GPU compute tooling, but does not replace the D3D12/DXR player runtime. |
| Add DX10/11 only as a post-MVP research track | Their fully programmable pipelines prevent universal semantic scene reconstruction. |

## Issues Encountered
| Issue | Resolution |
|---|---|
| Empty workspace | Treat deliverable as architecture/roadmap; avoid inventing an existing codebase. |
| Ninja does not support CMake's `-A Win32` switch | The documented x86 build uses the Visual Studio 2022 generator; a clean alternate build directory validated it. |

## Resources
- AMD HIP FAQ: https://rocm.docs.amd.com/projects/HIP/en/latest/faq.html
- AMD HIP SDK for Windows: https://rocm.docs.amd.com/projects/install-on-windows/en/latest/index.html
- AMD Windows system requirements: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/shared/hipsdk/reference/system-requirements.html
- RTX Remix repository: https://github.com/NVIDIAGameWorks/rtx-remix
- RTX Remix architecture overview: https://github.com/NVIDIAGameWorks/rtx-remix/wiki/Home
- RTX Remix compatibility notes: https://github.com/NVIDIAGameWorks/rtx-remix/wiki/Compatibility
- Microsoft Direct3D 12 Raytracing: https://learn.microsoft.com/en-us/windows/win32/direct3d12/direct3d-12-raytracing
- HIP external resource interop: https://rocm.docs.amd.com/projects/HIP/en/docs-7.2.0/how-to/hip_runtime_api/external_interop.html
- FidelityFX FSR 3 manual: https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-interpolation/
- FSR Radiance Caching preview: https://gpuopen.com/manuals/fsr_sdk/techniques/radiance-cache/
- FidelityFX Brixelizer GI: https://gpuopen.com/manuals/fidelityfx_sdk/techniques/brixelizer-gi/
- AMD FSR SDK 2.3: https://gpuopen.com/amd-fsr-sdk/
- FSR Ray Regeneration: https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/
- FSR Frame Generation API: https://gpuopen.com/manuals/fsr_sdk/techniques/frame-interpolation-api/
- RTX Remix compatibility guidance: https://github.com/NVIDIAGameWorks/rtx-remix/wiki/Compatibility
- BioShock 2 original Steam requirements: https://store.steampowered.com/app/8850/BioShock_2/
- BioShock 2 API and DX9 launch information: https://www.pcgamingwiki.com/wiki/BioShock_2

## Visual/Browser Findings
- None.
# 2026-09-04 RR coordinate-scale audit

- The pinned RR 1.2 dispatch contract has no general current-depth scale field. It consumes signed linear depth directly, signed previous-minus-current depth motion with a separate convention scale, previous-minus-current camera position in world space, current row-vector view/projection matrices, and indirect ray hit distance.
- Consequently, changing only depth, only depth motion, or only camera delta would create contradictory geometry guides. A uniform scene-unit transform can be defined exactly for row vectors: scale current depth, depth delta, camera delta and ray distance by `s`; use `V' = S^-1 V S`; use `P' = S^-1(sP)`; and scale the admitted linear-depth bounds. This preserves NDC/UV while changing every SDK-visible length coherently.
- A hit-distance-only experiment remains possible as a synthetic sensitivity test, but it is not a scene-unit test and could not identify a valid integration setting. It is excluded from this sprint unless the coherent test later provides a specific reason to isolate that channel.
- The original renderer recording must remain immutable. Scaling belongs in isolated worker staging/dispatch data, with output-format and JSON provenance sufficient for old readers to reject configured results unless the exact preset is expected.
- The first full grid revealed that the exact recorded value 100000 is not an ordinary distance: `rrBounce` initializes it from ray `TMax` and retains it only when no secondary triangle commits. Scaling it to 10000 at `unit-tenth` changed the semantic no-hit sentinel into a finite distance, while unit-one/ten still clamped it to FP16 max. That first grid (`rr-coordinate-scales-m7b3p4tu`) is retained but rejected as a coordinate-scale comparison. A valid transform preserves this no-hit sentinel as FP16 max and scales only committed-hit distances.
- The corrected grid has identical aggregate miss clamps for all scales. Correcting unit-tenth changes preserved output alpha for more than 92,000 rows in sampled bundles but changes zero RGB rows versus the superseded run. This fixture therefore shows no denoised-RGB response to that miss-sentinel difference even though the SDK preserves the signal alpha.
- Coordinate scale is not perfectly invariant: unit-ten improves default-filter spatial MSE in 25/32 comparisons and 13/14 late comparisons, but temporal is split overall and worsens in 9/14 late comparisons. Mean changes (`-5.18e-7` spatial, `+3.00e-8` temporal) are small relative to the zero-stability response.
- Zero stability has the same directional tradeoff at every scale: 26 non-reset spatial improvements, six reset equalities, 26 temporal regressions and 26 disocclusion improvements. Coordinate scale does not explain or cure that behavior.
- All 24 candidates still fail spatial, disocclusion, fallback, fallback-relative confidence and raw SDK reporting acceptance. Scale ten is not a valid default despite its paired spatial tendency. Unit scale remains unchanged; resolution is the next isolated hypothesis.

# 2026-09-04 RR resolution audit

- The renderer and RR preparation HLSL already use runtime scene dimensions, but the RR research boundary intentionally freezes 128x96 across the input/recording/output byte layouts, worker texture/context allocation, managed hashes/decoders, quality/reference arrays and tests.
- A low-resolution experiment cannot safely set only `desc.renderSize` or downsample a 128x96 recording: both approaches would mismatch resources/guides or combine sampling/resampling with the SDK-resolution variable. The renderer must produce a native low-resolution recording and the reference must trace the same native pixel centres.
- The migration should admit only 128x96 and 256x192 initially, use checked dimension-derived sizes everywhere, preserve 128x96 v1 bytes exactly and add explicit cross-extent output/report rejection. A live 64x48 context reached the pinned provider but failed context creation because it requested D3D12 resources with height zero; same-aspect 256x192 is therefore the valid paired extent. Arbitrary/dynamic resolution and upscaling remain out of scope.
- The first 256x192 live dispatch succeeds for both reset and history frames. Its exact bounded contract is 21,561,344 predicted context bytes, 22,544,384 callback peak bytes, 6,553,600 external bytes and 2,162,688 staging bytes. The pinned SDK repeats its known unsigned-underflow memory-report defect at an extent-specific value (`0xfffffffffeb90000`, aliasable 65,536), so managed admission pins that exact tuple rather than accepting a range.
- Across texture/PBR and default/zero settings, 256x192 reduces aggregate spatial error to 60–84% and disocclusion error to 50–63% of 128x96. Temporal error falls for both texture settings and PBR zero, but default PBR rises to 151%. The CPU fallback changes only to 97.5–98.2%, so RR is resolution-sensitive beyond the baseline filter. Absolute spatial/fallback gates still fail every candidate; no promotion follows.
- A proposed byte-exact v2 single-reset/recorded-reset invariant is invalid. Two fresh 256x192 single-context executions differ at 981 pixels (maximum RGB delta one small half-float step, `6.103515625e-05`; MSE `7.44e-11`) while alpha remains exact. Keep strict input/report/output-format admission, but treat SDK RGB byte determinism as evidence to measure—not a universal contract.

# 2026-09-04 RR guide-conditioning audit

- The pinned dispatch header explicitly requires RG octahedral normals, B linear roughness, A material type, and diffuse albedo `BaseColor*(1-Metalness)` with either sqrt encoding or the non-gamma flag. Current packing matches those channel-level requirements.
- The header does not state the required normal coordinate space and refers elsewhere for material-type meanings; guessing either would make an invalid guide experiment. Existing albedo encoding evidence already excludes a simple linear-versus-sqrt flag mistake as the remaining explanation.
- The SDK exposes documented configuration keys for cross-bilateral normal strength, maximum radiance, radiance clipping standard-deviation K, Gaussian relaxation, stability and disocclusion threshold. Normal strength/radiance controls are the safest next guide-conditioning candidates if their default/range semantics can be pinned from official documentation/sample code.
- AMD's current RR 1.2 technique guide defines material type exactly: four IDs `0..3`, encoded as `id/3` in normal alpha; mismatched IDs prevent cross-material mixing. It explicitly recommends starting with type 0 and adding IDs where mixing causes artifacts. Our draw IDs are already source-validated, so the fixed two-draw worker preset keeps draw 1 at the recommended class `0`, maps draw 2 to class `1/3`, and leaves background/default zero without changing the recording.
- The official guide demonstrates octahedral encoding but does not prescribe world versus view space. Because the supplied current view matrix can reconstruct view-centered positions and our existing decoded normals match world-space geometry, no normal-space conversion will be guessed in this sprint.
- The official sample exposes cross-bilateral normal strength `[0,1]`, disocclusion threshold `[0.01,0.05]`, Gaussian relaxation/stability `[0,1]`, and max-radiance/radiance-clip-K `[0,65504]`. Defaults must still be queried from the pinned live context; sample UI ranges alone do not identify useful values.
- The pinned live context reports stable defaults: normal strength `1`, stability `1`, max radiance `65504`, radiance clip K `50`, Gaussian relaxation `0`, and disocclusion threshold approximately `0.01`. These are exact float32 admission values already verified over repeated pre/post queries.
- In the retained moving fixtures, maximum input radiance is only `0.08405` (texture) / `0.08324` (PBR). A `max-radiance-one` configuration therefore changes the denoiser's range without clipping any recorded sample and is a coherent signal-conditioning candidate; lower caps are excluded initially.
- The texture recording contains material IDs 0(background), 1 and 2; PBR also has roughness `0.28` and `0.5` on those draws. A `material-draw` preset can encode draw 1 as class `0` and draw 2 as class `1/3`, exactly following AMD's four-class format while retaining the recommended default class on the first material.
- Fixed initial candidates: unconfigured baseline; `material-draw`; `normal-half`; their combination; and `max-radiance-one`. Resolution remains 128x96, scale remains explicit `unit-one`, and stability remains at its queried default so this sprint does not re-open the known stability tradeoff.
- The focused live contract confirms `normal-default` is byte-exact with the baseline inner SDK frames at 128x96. `material-draw` changes only the packed normal/roughness/material plane hash, leaves the immutable recording and all five other texture planes unchanged, and requires `RRTRRD06`/matching report provenance. Combined material/normal and max-radiance configurations are admitted through queried exact defaults.
- The 10-candidate Release grid completes in 311.88 seconds. `material-draw` worsens spatial error on 7/7 texture transitions and 6/7 PBR transitions while improving temporal residual on all 14; disocclusion mostly worsens. This is a small edge/history tradeoff, not a cure.
- `normal-half` is also small/mixed: spatial worsens on 6/7 texture and 5/7 PBR transitions, while temporal improves on 5/7 texture and 4/7 PBR transitions; mean disocclusion improves slightly on both surfaces. Combining material classes with normal-half does not consistently improve spatial or disocclusion response.
- `max-radiance-one` produces exact baseline quality metrics on every frame for both surfaces. With all inputs below 0.085, reducing the configured maximum from 65504 to 1 has no observable output effect in this fixture.
- Every one of the ten reports still fails spatial non-regression, disocclusion non-regression, RR-versus-fallback, fallback-relative confidence and raw SDK acceptance. All retain temporal non-regression, but no guide/range preset is promotable.
- Fresh optimized Debug replay is exact: both newly captured recordings and all ten guide-conditioned outputs match the retained Release evidence byte-for-byte. The affected Release suite passes 7/7 and the focused Debug contracts pass 2/2, so the result is not a build-configuration artifact.

# 2026-09-04 RR exact-zero floor audit

- The latest retained two-frame black settings grid has exact-zero raw input and fallback for every case, but every preset retains a positive RR floor. Baseline MSE is `1.1850511370814498e-10` on reset and `1.1767446739252563e-10` on frame 1; maximum output remains `1.0907649993896484e-5`.
- Explicit queried defaults are exact with the unconfigured output. Stability half/zero, Gaussian quarter/half/one, normal strength half and maximum radiance one change the floor only at tiny numerical levels; none makes it zero. Gaussian one slightly raises reset maximum to `1.0967254638671875e-5`. This rules out the existing scalar setting presets as a black-floor fix and avoids rerunning that full grid.
- The single-dispatch input contract admits active pixels with zero albedo and zero indirect distance, plus canonical inactive background records `(0,0,0,-1,0...)`. These are valid synthetic localization controls because each complete input is checksum-bound and native/managed admission revalidates every row. They do not require changing source shaders or output acceptance.
- The first full-coverage Release localization (`rr-black-floor-hu1tbcz0`) shows every one of 36,864 active RGB values positive, using only two half-float values on reset. Zero hit distance is output-exact with the active baseline; zero albedo changes only the distribution slightly. The all-background control is exactly zero.
- A second full-coverage textured scene reproduces the same outcome. The decisive partial-geometry fixture (`rr-black-floor-2hx9k0b7`) has 9,976 active and 2,312 inactive pixels: all 29,928 active RGB values are positive while all 6,936 inactive RGB values remain exact zero on every history frame. The reset active mean is `1.087570271687022e-5`; frame 7 falls only to `1.07134628888599e-5`.
- Reset-only `active` output exactly matches the first inner chunk of the recorded eight-frame run. Zero distance is exactly inert in RGB. Zero albedo retains the same floor range and shifts mean only slightly (`1.0869781686099129e-5` versus `1.087570271687022e-5`). This localizes the floor to SDK-classified active pixels and rules out output-resource initialization leakage, background processing, albedo demodulation, hit-distance magnitude and the existing settings as primary causes.
- The pinned SDK package exposes the RR 1.2 API header and signed provider binaries, but no Ray Regeneration shader/model implementation source. AMD's public 2.3 documentation describes RR as ML-based and the repository structure as using prebuilt runtime libraries with only a limited collection of HLSL; repository search exposes the denoiser API/docs but no inspectable RR implementation matching the floor. Therefore the measurements support “provider-local active-pixel floor” as an inference, not a proven internal epsilon constant.
- Final Release/Debug evidence is byte-exact across the source recording, persistent history output and four reset input/output pairs. The new integration contract plus adjacent dispatch/sequence contracts pass. The floor is far too small to explain the separate textured/PBR contrast loss, but exact black remains formally failed and must not be silently thresholded.

# 2026-09-04 FidelityFX Radiance Cache foundation audit

- The existing pinned SDK directory is a deliberately reduced RR package: it contains only `api`, `denoisers`, `docs`, the common DX12 loader and `amd_fidelityfx_denoiser_dx12.dll`. It has no `radiancecache` headers or provider DLL, so a cache probe cannot be built or run against that subset.
- AMD's current official SDK 2.3 documentation identifies Radiance Caching 0.9.0 as a technical preview for RX 9000-series-or-newer GPUs with Shader Model 6.6. The shipped sample/runtime path is Windows DirectX 12; it requires `ffx_radiancecache.h` and `amd_fidelityfx_radiancecache_dx12.dll` alongside the common loader. This confirms D3D12, not ROCm, as the immediate game-runtime boundary.
- The API creates a context from maximum inference/training sample counts. Typical inference capacity equals maximum viewport pixels; training is usually 1–5% of pixels. Dispatch consumes structured prediction/training input/output buffers plus sample counters and supports inference, training, counter clearing and reset. It requires HLSL CS 6.6 and continuous online training, so integrating it is materially more than substituting a post-process denoiser.
- The public SDK license inventory confirms the radiance-cache header, helper header, provider DLL and sample exist in the full SDK distribution. The next prerequisite is acquiring/verifying that official component through the same SDK media-delivery mechanism used for the reduced RR package, not fabricating headers or reusing denoiser IDs.
- Official tag `v2.3.0` resolves to the already pinned commit `60f4ea81909200d8542eca14dccb2628b763a9a3`. A sparse Git/LFS checkout of only `api`, `radiancecache`, `signedbin` and SDK docs completed at `build/dependencies/fsr-2.3.0-radiance-cache`, preserving the RR-only dependency unchanged.
- Git LFS materialized the real 798,992-byte cache provider. Both loader and cache DLLs have valid AMD Authenticode signatures. SHA-256 is `e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa` for the common loader and `256db18d924c8cd38923d04e3ecd210695d3f0f796b240eab9663ad4d54e31a0` for the radiance-cache provider.
- The pinned header is API 0.9.0. Its context descriptor contains only flags, version, maximum inference samples and maximum training samples. The only create flag attempts to force the WMMA backend and must fail with `ErrorParameter` when unavailable. This makes a context-only probe possible without inventing scene data; dispatch remains a later structured-buffer integration.
- The existing RR native boundary is too denoiser-specific to reuse wholesale: it hardcodes denoiser provider IDs, memory-query descriptors, resolution/signal flags and two known provider workarounds. Only its generic D3D12 adapter selection, DLL loading, job isolation and allocation callbacks are suitable patterns. The cache needs a separate executable/report/managed policy so RR defects cannot be admitted implicitly.
- The 0.9 header exposes no effect-specific pre-context GPU-memory query. Context admission therefore cannot rely on RR's predicted-size gate. The viable first boundary is a conservative hard callback ceiling, exact allocation/release accounting, support/version enumeration, create/destroy lifecycle and failure injection; measured peak becomes evidence rather than a preflight promise.
- AMD's pinned NRC sample sets inference capacity to viewport pixels and training capacity to 32,768, first attempts `TRY_FORCE_WMMA`, and if creation fails checks that the reference backend supports wave lane count 32 before retrying without the flag. For our 128x96 foundation, a bounded 12,288 inference / 512 training pair follows the documented 1–5% guidance and is materially smaller than the sample default.
- Generic SDK guidance requires version enumeration with `createDescType=FFX_API_CREATE_CONTEXT_DESC_TYPE_RADIANCECACHE`; returned provider IDs must not be hard-coded and the selected override must be used consistently. The official NRC sample currently uses default selection, but the probe should enumerate/copy names and explicitly override the selected returned ID for reproducible evidence.
- Live enumeration succeeds on the RX 9070 XT: SM 6.6, wave lanes 32–64, provider ID `12308798262227275776`, name `0.9.0`. No context or dispatch is required for this query.
- A 60-second isolated attempt creates and destroys the fixed-capacity WMMA context successfully in about 38 seconds. The provider makes 11 callback allocations, peaks at 20,643,840 bytes, releases all 11 and leaves zero live bytes/errors/denials. No fallback or dispatch occurs.
- Raw lifecycle acceptance still fails one official API expectation: querying the created context's provider returns `FFX_API_RETURN_NO_PROVIDER` (4) and ID 0 despite explicit creation with the sole enumerated provider. This mirrors the class of metadata defect seen in RR but is a distinct cache result/code and must receive its own exact hash-pinned managed policy, not inherit the RR workaround.
- Repeating after driver/PSO warm-up completes in under a second at a 32 MiB ceiling with the same exact 20,643,840-byte peak and 11-allocation lifecycle. The managed `rc_worker` admits only the reviewed DLL hashes and exact code-4/ID-0 metadata defect, reports `context-ready-with-workarounds`, keeps `raw_sdk_acceptance: failed`, and explicitly reports `rc_rendering: false`/zero dispatches.
- The provider does not propagate allocation-callback failure safely: both a 1 MiB ceiling and injected failure at allocation 2 terminate the worker with Windows access violation `0xc0000005` after `Hello, NRC Create Context!`, without JSON. The one-process job reaps each crash and the managed policy reports `worker-crash`; no in-process recovery is possible or acceptable. This is a provider robustness defect, not a reason to remove the hard ceiling.
- Fresh recovery after both provider crashes succeeds with the exact prior peak/counts. Release and Debug support/worker contracts each pass 2/2, including isolation fixtures, parent-exit kill, strict DLL hashes, malformed/mutated report rejection, crash containment and recovery. The boundary is mechanically ready for a later dispatch slice, but raw provider metadata acceptance and actual cache rendering remain false.
- The pinned sample's CPU and HLSL layouts agree exactly: `RadianceCacheInput` is 11 contiguous `float` values (44-byte structured-buffer stride: position3, octahedral normal2, octahedral view direction2, diffuse albedo3, roughness1), while `RadianceCacheOutput` is three floats (12-byte stride). The counter buffer is two `uint32_t` values: inference count at index 0 and training count at index 1.
- At the admitted 12,288 inference / 512 training capacities, the five API-visible external buffers total 716,808 bytes: 540,672 prediction input, 147,456 prediction output, 22,528 training input, 6,144 training target and 8 counter bytes. The sample also owns a separate 147,456-byte per-pixel path-compositing state buffer; it is renderer state, not part of the FidelityFX dispatch descriptor.
- The official sample sequence is renderer/path-trace enqueue, UAV ordering, optional counter readback, transition training inputs plus prediction/training outputs and counters from UAV to non-pixel-shader resource, then one cache dispatch with inference before training and counters cleared afterward, followed by compositing predicted radiance. Reset is added only when requested. The next slice therefore needs renderer-owned normalized query/training export and compositing state before any cache dispatch can honestly be called rendering.

# 2026-09-04 FidelityFX Radiance Cache synthetic dispatch audit

- The pinned sample creates all five external buffers as default-heap row-major buffers with `ALLOW_UNORDERED_ACCESS`, then wraps them with `ffxApiGetResourceDX12(..., COMPUTE_READ, 0)` and manually replaces the helper's buffer stride with the actual element stride. This manual stride assignment is required because the generic helper otherwise derives buffer stride from D3D12 `Height` (always 1 here).
- The provider receives the resources as compute-readable `FfxApiResource` handles even though application-side path generation and later compositing use UAV access. The sample begins buffers in `COMMON`, uses UAVs from the renderer, then transitions training input, both outputs and counters to `NON_PIXEL_SHADER_RESOURCE` around `ffx::Dispatch`; prediction input is notably not included in that explicit transition list, relying on common-state promotion/read behavior.
- A standalone fixture cannot merely upload default buffers and call dispatch: it needs an upload command/fence before provider work, exact `FfxApiResourceDescription.size/stride/usage/state`, readback copies after provider execution and explicit final device-idle teardown. Keeping the external buffers outside the provider callback tracker preserves the distinction between the fixed 716,808-byte application contract and the measured provider context peak.
- The loader exposes `Dispatch` directly as `ffxReturnCode_t(ffxContext*, const ffxDispatchDescHeader*)`; it records provider work into the caller's open D3D12 command list. The sample closes/executes that list and fences it before CPU statistics/readback. The fixture must do the same and must not destroy the context or external buffers before the queue fence completes.
- The official flags guarantee inference is enqueued before training and both counter clears occur only after inference/training. A first combined dispatch can therefore upload counters `{InferenceSamples, TrainingSamples}`, request reset + inference + training + clear-all, and require readback counters `{0,0}` after a successful fenced execution. A separate inference-only/reset control is still needed to distinguish dispatch viability from online-learning behavior.
- The existing `rc-isolation-1` envelope already preserves stdout/stderr, exit status, deadline, output cap and crash reporting independently of context report contents, so dispatch can use the same process boundary without weakening containment. A new managed assessor should be separate from `rc_worker.py`; otherwise context-only `dispatches==0` admission could accidentally broaden when dispatch fields are added.
- The CMake integration currently registers only context support/worker contracts. Add a distinct dispatch contract and timeout rather than expanding those tests: this preserves the fast foundation regression and makes any preview-provider dispatch crash attributable to the new path.
- First real Release inference-only execution succeeds mechanically under D3D12 debug validation. The provider returns dispatch code 0, the GPU fence completes, both counters clear to zero, every one of 36,864 output floats replaces its NaN sentinel with a finite nonnegative value, all prediction/training inputs and targets remain byte-exact, the device remains valid and all 11 provider allocations release. Output spans `0.0265808..0.0398865`, mean `0.0350016`, standard FNV-1a64 `8439070038676242095`.
- The successful dispatch retains the exact known metadata defect only: post-context provider query returns code 4/ID 0, so native raw acceptance remains failed while `mechanical_pass` is true. Provider callback peak remains exactly 20,643,840 bytes; the external/default buffers are separately exact at 716,808 bytes and upload/readback staging at 1,433,616 bytes.
- The Release combined reset + inference + 512-sample training dispatch also succeeds mechanically with the same clean counters/resources/device. Its prediction output is byte-identical to inference-only (`8439070038676242095`), directly matching the API guarantee that inference is enqueued before training; this equality does not yet prove that training changed later cache state because both tests destroy their fresh contexts immediately afterward.
- The strict managed dispatch boundary admits the expected output only with the reviewed SDK hashes and exact provider-metadata exception. It deliberately distinguishes `rc_dispatch_executed: true` from `rc_rendering: false`; finite cache output alone is not evidence of correct scene lighting or compositing.
- Release and Debug each pass the context query, context worker and dispatch contracts 3/3. The dispatch test covers inference, combined training, fresh repeat, report mutation/non-finite rejection, the low-budget access-violation boundary and successful recovery. The pinned output hash is identical across both build configurations and all accepted fresh contexts.

# 2026-09-04 FidelityFX Radiance Cache persistent training audit

- The official guide confirms the cache is an online model rather than a pretrained fixed model. Default learning rate is `0.002` and prediction-weight exponential smoothing is `0.99`; therefore one 512-sample batch may produce only a small visible prediction change even if optimizer state updates correctly. The first sequence should retain defaults rather than using an override to force an effect.
- Reset executes before inference/training but explicitly does not clear sample counters; every step must upload its own `{inference,training}` occupancy and request counter clear afterward. A train-only dispatch is API-valid with counters `{0,512}` and the training flag; the subsequent inference must use `{12288,0}` without reset to observe retained state.
- “Movement toward target” can be evaluated over all 12,288 deterministic query positions because the analytic target function is defined from the same normalized position fields used to generate the 512 subsampled training records. Report baseline/post/reset MSE against that function plus pairwise RGB MSE/max delta; do not interpret improvement as scene quality.
- The existing single-dispatch implementation owns one context, buffer set, queue and command list but submits only once. Persistent mode must turn upload/transition/dispatch/readback/fence into a per-step routine, track each resource's restored state and reset the command allocator/list only after its prior fence completes. A separate sequence result schema is safer than weakening the pinned single-dispatch hash contract.
- The first one-batch Release sequence succeeds mechanically and proves retained optimizer/model state. Every one of 36,864 post-training RGB values changes; post hash is `11036946020368386469`, pairwise MSE `2.97242e-9`, maximum absolute delta `7.62939e-5`. Analytic-target MSE improves slightly from `0.0500247` to `0.0500075`. A following reset restores the baseline hash `8439070038676242095` and every output byte exactly.
- All four steps return code 0, clear both counters, preserve inputs/targets and keep the device healthy. The train-only prediction output remains entirely at its uploaded NaN sentinel, confirming that training does not spuriously write the prediction buffer. Its empty-stat minimum/maximum initially serialized as non-standard `inf/-inf`; set both to zero when no finite values exist before building managed strict-JSON admission.
- Fresh repeats and the Debug build reproduce baseline, trained and reset hashes exactly. One batch is enough to satisfy the predeclared retained-state condition, so the experiment does not expand toward eight batches. The approximately 0.0344% analytic-target MSE reduction demonstrates target-directed synthetic learning, not game-scene quality or convergence.

# 2026-09-04 renderer-exported Radiance Cache path bridge audit

## Cross-process shared D3D12 resource audit

- Microsoft documents that both committed resources and fences can receive NT handles through `ID3D12Device::CreateSharedHandle`, and a second D3D12 device opens them with `OpenSharedHandle`. `GENERIC_ALL` is currently the only accepted access mask. Handle inheritance is controlled by `SECURITY_ATTRIBUTES`; this project will additionally retain the explicit `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` allowlist.
- Same-adapter shared buffers use default heaps with `D3D12_HEAP_FLAG_SHARED`; upload/readback heaps are explicitly not shareable. A local upload and local readback must surround the shared default-heap round trip. `D3D12_FENCE_FLAG_SHARED` is sufficient because cross-adapter sharing is deliberately excluded.
- Shared resources carry extra zeroing/creation overhead and require explicit synchronization. The capability contract will serialize parent upload → fence 1 → child copy → fence 2 → parent readback. It does not set cross-adapter or simultaneous-access flags because only one queue/process owns the resources between fence handoffs.
- Primary references: Microsoft Learn `ID3D12Device::CreateSharedHandle`, `OpenSharedHandle`, `Shared heaps`, `D3D12_HEAP_FLAGS`, and `D3D12_FENCE_FLAGS` (all consulted 2026-09-04).
- The first live RX 9070 XT round trip succeeds over two 1,573,120-byte shared committed buffers and one shared fence. Parent upload/fence 1, child copy/fence 2 and parent readback/fence 3 reproduce FNV-1a64 `10972558891643204389` exactly with zero CPU payload-transfer bytes. The child is job-contained, reaped and receives exactly three extra inherited handles; adapter LUID is `72687:0` on this host.
- The provider's external interface maps cleanly to five separately shared UAV-capable default-heap buffers: 540,672-byte prediction input (stride 44), 147,456-byte prediction output (12), 22,528-byte training input (44), 6,144-byte targets (12) and 8-byte counters (4). The next independent layout contract should preserve three read-only buffers while allowing child writes only to prediction output and counters.

## Isolated live scheduling audit

- The existing RC isolation boundary deliberately connects child stdin to `NUL` and caps captured stdout/stderr at 64 KiB. It cannot carry the 1,573,120-byte `RCRPATH1` payload without an explicit bounded input pipe; binary predictions should not be returned through the JSON evidence channel.
- Linking the preview provider into `rrt_dxr` would discard the already-proven crash boundary: allocation denial can access-violate inside the provider. The smallest safe no-file step is an explicit renderer binary-stream mode feeding an inherited stdin pipe of a job-contained provider child. The child can retain context state later, while the renderer's ordinary output remains authoritative.
- `PrepareRcPaths` already returns the complete artifact in memory before `SaveRcPaths` performs exclusive file creation. A stream-only CLI can reuse those exact bytes without changing shader semantics or the historical file contract; it must be mutually exclusive with regular artifacts/presentation and suppress the normal stdout JSON to keep the binary framing unambiguous.
- The renderer's final report is emitted directly through multiple `printf` calls, so multiplexing JSON and binary on stdout would require a risky unrelated report refactor. A fixed-size `--rc-stream` mode should instead emit only the self-checksummed 1,573,120-byte artifact, return immediately after preparation and use stderr solely for failures.
- The first no-file renderer → isolation host → child transaction produces the exact same managed decision and provider hashes as the file-backed fixture. Windows reports normal anonymous-pipe writer closure as `ERROR_BROKEN_PIPE`; admission now accepts only that exact EOF or a successful zero-byte read after the fixed payload, while any extra byte remains rejected.
- Two consecutive 172-sample training frames on the same streamed fixture/context further improve target MSE to `0.00123874` and guarded composite MSE to `7.67191e-5`; post hash is `13270289865275143940` and reset remains exact. This is persistent state across bounded static synthetic frames, still never applied to the authoritative no-cache output.
- A `.05` camera-X change produces a distinct renderer artifact identity and is admitted only with its own query counts/digest. The supervisor uses a fresh job-contained child/context, its target and guarded composite errors improve, and reset is exact. Low-budget crash and 1 ms timeout both preserve explicit no-cache authority; the following transaction recovers exactly.
- The stream prototype's representative warm two-frame wall time is about 1.0 second (roughly 350 ms renderer/export and 538 ms provider). CPU readback, process startup, pipe transfer and re-upload dominate, so the next performance boundary is shared D3D12 resources/fences across the isolation boundary—not tuning the cache model yet.

- The current `RRTRRI01/02` renderer export already carries source-rendered indirect RGB/distance, direct/emission, octahedral primary normal/roughness, diffuse albedo, motion/depth, world-space primary hit position and instance ID plus camera matrices and a whole-file digest. It is valuable provenance but not a valid NRC path record by itself.
- The RR preparation shader traces one cosine-weighted secondary ray and computes `indirect = primary throughput * incoming secondary lighting`, but exports only that product and secondary distance. NRC needs the secondary hit's normalized world position, secondary normal/view direction, secondary diffuse albedo/roughness and the unfactorized extant-radiance target separately; these cannot be reconstructed from the existing 96-byte pixel row.
- A valid one-bounce bridge can query the cache at the secondary surface: cache target is the shader's `secondaryLight` result before primary throughput multiplication, renderer-owned throughput is the existing primary diffuse/PBR factor, and the unchanged RR indirect product is the exact no-cache comparison. Misses have no surface query and must retain their renderer ambient contribution rather than fabricate a cache input.
- Preserve RR formats unchanged. Add a new cache-specific shader/export carrying the secondary hit tuple, target, primary throughput, no-cache indirect/direct output, active/query validity and scene-bound metadata. Up to 512 deterministic secondary hits can serve as training records while all valid secondary hits remain prediction queries; counters must use actual valid counts, not viewport size.
- The new `prepareRcPaths` shader and C++ `RCRPATH1` export path compile successfully in the x64 Release renderer. The configured renderer tree is `build/x64-renderer`; repository-level `build` is only a container and is not itself a CMake build directory.
- Existing diagnostic tooling uses strict fixed-size structs, whole-file SHA-256, finite/range checks, immutable output creation and CPU-side scene oracles. The cache-path inspector should follow that contract but retain Cartesian source values; normalized NRC inputs are a derived view, not a replacement for renderer evidence.
- `RCRPATH1` is exactly 1,573,120 bytes: a 224-byte header, 12,288 fixed 128-byte rows and a 32-byte whole-file digest. Invalid secondary rows intentionally retain primary direct/background and miss ambient factorization, so strict validation must distinguish primary validity from query validity instead of requiring a zero row.
- The renderer CTest structure already gives `rrt_dxr` tests a capability-probe/skip boundary. A dedicated `rc_paths_export` contract can reuse the canonical scene fixture, compare ordinary pixels/signals with and without the extra diagnostic dispatch, and remain independent from the provider-backed RC contracts.
- The first live canonical fixture yields 172 genuine secondary-surface queries, so its bounded training set is 172 rather than the maximum 512. This is correct actual-occupancy behavior and prevents padded/fabricated samples. A path-only run reports one cache readback submission in addition to the renderer's separately counted ordinary render readback.
- The existing persistent provider sequence is structurally reusable but currently constructs fixed analytic vectors and evaluates an analytic target inside its step lambda. Renderer ingestion should parameterize populated prediction/training arrays and target/error evaluation while retaining the same fixed-capacity allocations, fenced step order, counter clearing and teardown—not create a second looser dispatch implementation.
- Release adjacent renderer/RR contracts and the new export contract pass, as does the Debug export contract. This closes source production and conversion while leaving the third milestone intentionally open: no provider output has yet been composited into the offline renderer fixture.
- Provider ingestion can safely reuse `TestRcSequence` by making populated inference/training counts and target evaluation fixture-driven while leaving allocations at the audited 12,288/512 capacities. Unpopulated output slots must remain NaN sentinels and be excluded from hashes/error denominators that describe populated predictions.
- The native probe's isolated mode reconstructs an explicit child argument list, so any artifact path must be validated as absolute, restricted to sequence mode, and forwarded explicitly. Otherwise the managed job would test a synthetic fallback rather than the renderer file.
- The repository already uses Windows CNG's one-shot `BCryptHash(BCRYPT_SHA256_ALG_HANDLE, ...)` for strict artifact verification. The RC probe can adopt the same bounded pattern by adding `bcrypt` to its existing D3D12/DXGI link line rather than introducing a custom checksum implementation.
- The fixture-aware Release probe compiles successfully after adding native SHA-256 validation and actual populated-count handling. The signed provider directory remains the pinned SDK 2.3.0 sparse checkout; a fresh canonical `paths.rcpaths` artifact is available from the passing renderer export test for the first isolated provider run.
- On the first live renderer-fixture dispatch, the 0.9.0 WMMA provider clears counters but writes all 36,864 floats in the fixed-capacity prediction output, not only the first 172 occupied records. This is compatible with guarded compositing only if padding is initialized deterministically, every output remains validated, and only the explicit 172 query-to-pixel mappings affect metrics or a candidate image.
- Managed admission of the real renderer fixture succeeds with exact hashes. Baseline target MSE is `0.00125381`; after one 172-sample batch it is `0.00124904`. All 516 mapped RGB values change, query-composite MSE improves from `7.77365e-5` to `7.74054e-5`, and reset recovers the baseline exactly. This is a guarded offline composite metric, not live renderer replacement.
- The RC build registers six relevant tests: five provider boundaries plus the renderer export. The first cross-configuration run used a suffix regex that intentionally omitted `rc_worker_boundary` and `rc_paths_export`; run the complete `^rc_` set before closing the phase.
- The complete `^rc_` regression passes all six tests in both configurations. Existing context/dispatch/analytic behavior remains intact alongside the new renderer bridge, including the low-budget provider-crash containment exercised by the managed worker boundary.
- The renderer uploads vertices after applying every captured draw's affine world transform, so both DXR traversal and shader hit positions are already in one world space. A cache export can recompute exact min/max bounds from those same transformed source vertices on CPU and verify every secondary hit lies inside them; it does not need to infer bounds from an RR depth plane.
- The existing 128x96 RR preparation is an independent texel-centre diagnostic trace with its own deterministic RNG state, not the jittered ordinary GI frame. The cache bridge should similarly carry its own source output from the exact same shader invocation and prove historical pixel/signal/RR exports unchanged, rather than incorrectly compare two different sample trajectories byte-for-byte.
- A compact per-pixel `RCRPATH1` source row can use eight float4 fields (128 bytes): secondary position/validity, normal/roughness, incident view/instance, diffuse albedo, unfactorized target radiance, primary throughput, exact no-cache indirect/distance, and direct-or-background/primary validity. This preserves Cartesian source data for independent inspection; cache-specific normalization and octahedral packing belong in the strict converter/worker.
## Shared five-buffer layout implementation note (2026-09-04)

- The provider-shaped transport implementation uses `std::array` for the five exact cache resources, so `src/dxr/rc_shared.cpp` now explicitly includes `<array>`.
- The configured SDK-enabled build tree is `build/rr-sdk-probe`; the workspace-level `build` directory is only a container and has no `CMakeCache.txt`.
- Release now builds the five-buffer layout cleanly. Two direct runs produced the same exact report: 716,808 external bytes; sizes `[540672,147456,22528,6144,8]`; strides `[44,12,44,12,4]`; hashes `[920219675992757029,16317131794596865829,18030334235379617445,9233023709800616485,12161962213042174405]`; fence values `[10,11,12]`; six explicitly inherited handles; and zero CPU interprocess payload bytes.
- The parent verified buffers 0/2/3 were immutable, the isolated child rewrote prediction buffer 1 and cleared counter buffer 4, and the child was reaped normally.
## Actual provider shared-resource integration seam (2026-09-04)

- `rrt_rc_probe` currently constructs all five `RcExternalBuffer` objects internally in `TestRcDispatch`; each object combines a default-heap GPU resource with local upload and readback staging.
- The provider only consumes `RcExternalBuffer::gpu` through `RcWrap`, while upload/readback helpers are harness concerns. This is the clean seam for imported shared GPU resources: preserve the wrapper/stride contract, but make local staging optional and owned by the parent process.
- `RcRunIsolated` already supports an explicit inherited-handle allowlist, but launches the current executable. Keeping the real shared provider mode inside `rrt_rc_probe` avoids a broad cross-executable launcher change and keeps SDK loading/crash containment in the existing worker architecture.
- The first provider-mode compile caught one MSVC rule: a comma-separated `const auto` declaration cannot deduce three different vector types. The fixture snapshots are now separate declarations, with immutable resource checks kept byte-exact via `memcmp`.
- The first real-provider child reached context creation and destruction successfully. Two admission details needed correction: the SDK destroy call does not null the opaque context for the caller (matching the existing probe behavior), and global diagnostic configuration emits provider greeting text to stderr. The dedicated shared child now skips optional logging so its stdout/stderr protocol remains exact.
- The real shared-provider contract is deterministic in both configurations: Release passes in 3.10 s and Debug in 3.17 s, including two exact provider runs and invalid-handle rejection. Both reproduce the pre-existing inference hash `8439070038676242095`, showing that changing the transport did not change provider output.
## Documentation validation note (2026-09-04)

- A first recursive Markdown-link audit unintentionally descended into the downloaded SDK documentation under `build/dependencies`, reporting 547 links that are outside this project's documentation boundary. It did not modify files. The correct audit scope is the root project Markdown plus `docs/`, excluding generated/downloaded build content.
## Shared renderer-path continuation audit (2026-09-04)

- Session recovery found the current shared-resource sprint already synchronized: the generic transport and real five-buffer provider dispatch pass, while renderer-exported query population and persistent shared training remain open.
- The next implementation must reuse the existing strict `RCRPATH1` decoder/mapping semantics rather than introduce a second path interpretation, and must preserve the current CPU-pipe mode as the fallback oracle.
- `DecodeRcPathSequence` already supplies the exact normalized prediction/training inputs, target radiance, pixel mapping, throughput/direct/source-indirect terms and artifact SHA-256 needed for shared-path admission. The renderer fixture has a smaller populated count but still uses the fixed 12,288/512-capacity provider buffers.
- `TestRcSequence` contains the established four-step persistent oracle (reset inference → bounded training → post-training inference → reset inference), including full-capacity finite-output guarding, populated-only quality metrics and exact reset recovery. The shared implementation should reuse these semantics rather than stop at a single inference.
- A read-only Windows `rg` command used the unsupported `src/dxr/*.h` path glob and guessed a nonexistent `tests/verify_rc_live.py`; it changed nothing. Subsequent searches must use directory roots with `-g` filters and discover exact test filenames first.
- `PrepareRcPaths` currently materializes a 1,572,864-byte `RcPathRow` GPU buffer, reads it to CPU, validates it and builds the self-checksummed artifact. Direct renderer sharing therefore ultimately requires splitting/normalizing that compute output into the five provider layouts before readback; the current shared probe can first prove identical semantics using the strict decoded fixture.
- The existing end-to-end test already pins renderer query count 172, artifact identity, one/two-batch provider hashes, improvement and exact reset. A shared-path sequence should compare against those same hashes while transferring only bounded result metadata from the contained provider child.
- The first persistent shared-path implementation builds cleanly in Release. It leaves prediction/training inputs and targets resident in parent-created shared GPU resources, keeps one provider context across all steps, and uses child-local staging only to reset/read prediction output and the eight-byte counter buffer for strict evidence.
- The child returns a six-token bounded metadata record (three hashes and two changed counts) rather than any path or prediction payload. The parent independently reopens/readbacks the final shared state, verifies immutable buffers, counters and reset hash, and emits the admitted JSON report.
- The first direct invocation was rejected before GPU work because the established option validator treated `--training-batches` as valid only for the older sequence mode. The validator now explicitly admits the new shared-path sequence while retaining rejection for every unrelated mode.
- The provider sequence itself immediately reproduced the exact canonical hashes and changed counts, but the parent rejected the valid record because formatted whitespace extraction sets stream EOF/failure state while consuming the end. Admission now records successful extraction separately and rejects only an actual extra token.
- The canonical renderer fixture passes the persistent shared path in both configurations, including exact one/two-batch hashes and corrupt-artifact/direct-invalid-handle rejection. Full adjacent RC suites pass 7/7: Release 19.92 s and Debug 20.43 s.
- This closes provider-boundary payload migration for decoded renderer records, but not renderer-to-host transport: the current explicit mode still accepts a file. The next bounded increment is an exact stdin form plus configurable worker deadline/budget so live no-file scheduling and crash/timeout fallback can be compared without claiming GPU-direct renderer generation.
- `--shared-stream-sequence` now accepts the exact fixed artifact on stdin and produces the same admitted report as file mode. Worker budget and deadline are forwarded to the shared child boundary; the report records the admitted budget while the child retains fixed allocation accounting.
- After adding stream/failure coverage, all seven adjacent RC contracts pass in Release (23.51 s) and Debug (24.75 s). Provider-side shared migration is exact; the remaining performance boundary is renderer-owned GPU generation of compact normalized records, since the current renderer still readbacks raw `RcPathRow` data before the probe host uploads the shared inputs.
## Renderer-owned shared-path audit (2026-09-05)

- Session recovery confirms the provider-side shared path is complete and exact; the only open milestone is renderer-owned GPU compaction/normalization plus direct worker launch.
- `prepareRcPaths` currently writes one fixed 128-byte row per pixel into a non-shared UAV. CPU code reads every row, validates/compacts 172 valid hits, normalizes positions/spherical guides, and only then creates the five provider layouts in the probe host.
- The renderer `Device::Buffer` always uses `D3D12_HEAP_FLAG_NONE`, so direct sharing needs a narrowly scoped shared-buffer allocator rather than changing all renderer allocation semantics. The current path shader already has every field needed to write provider-shaped records on GPU; the missing pieces are deterministic compaction/mapping/counts and the scene-bounds normalization constants.
- A second read-only audit repeated the Windows-incompatible `src/dxr/*.h` glob while successfully reading the explicit files; it changed nothing. Directory searches must continue using `rg ... src/dxr -g '*.h'`.
- Deterministic compaction is important because the established hashes assume ascending pixel order. At the fixed 128×96 research extent, a deliberately single-threaded second compute pass can scan all 12,288 raw rows, write compact 44/12-byte provider records, and set both counters without atomics or CPU normalization. This prioritizes exact semantics before optimizing the prefix scan.
- The new `compactRcPaths` shader and deployment target compile successfully. It preserves ascending pixel order, emits exact 44/12/44/12/4 layouts, initializes inactive capacity deterministically, and writes query/training counts on GPU.
- `RcRunIsolated` now accepts an optional explicit executable path while preserving the same suspended creation, handle allowlist, pre-resume job assignment, timeout and teardown code for all existing self-worker callers.
- The first renderer integration compile exposed two ordinary include/declaration issues before linking: `rc_isolation.h` uses `std::cout`, so the renderer must explicitly include `<iostream>`, and the DXIL byte vector hit the MSVC most-vexing-parse form. Both are corrected without changing runtime behavior. An initial combined patch for these fixes had an invalid empty hunk and was not applied; this corrected patch is the distinct retry.
- The first GPU-direct renderer run succeeds with 172 GPU-discovered queries, zero renderer path readback bytes and zero provider IPC payload bytes. GPU math yields a new deterministic baseline hash `566204800999108543` rather than the CPU-normalized `4380958906282038366`; this is expected evidence to qualify, not silently alias.
- Repeats are exact. One GPU-direct training batch produces `6891511169378437159`, two produce `12625136704411306072`, and both reset exactly to the GPU baseline. A 1 MiB budget and 1 ms deadline each return an explicit no-cache fallback report while keeping the renderer process successful.
- The compaction shader now retains a 49,152-byte renderer-owned pixel mapping in ascending valid-pixel order. It is deliberately not shared with the provider and therefore adds no inherited handle; it is the input needed for the later GPU composite.
- Full pre-mapping RC suites pass 7/7 in Release (27.18 s) and Debug (30.33 s). The post-mapping focused Release path contract passes in 15.37 s with unchanged GPU-direct hashes.
- Post-mapping focused Debug passes in 16.09 s. A compatibility build attempt against `build/x86` failed during CMake regeneration because that stale directory combines a Ninja generator with a Win32 platform specification; no compilation ran and no source changed. The valid Visual Studio x86 tree is `build/x86-vs`.
## GPU candidate composite continuation (2026-09-05)

- The first combined composite patch was not applied because one long-line context in `rc_shared_path.h` did not match exactly. The retry is split into shader/build and provider-final-output edits so unrelated successful hunks cannot be obscured.
- The first composite dispatch correctly failed its guard because it read the provider sample-counter buffer after the provider had cleared it to zero. The renderer already has the strictly admitted populated count from child metadata, so the corrected shader receives that value through a 16-byte constant buffer instead of weakening counter-clear semantics.
- The corrected GPU composite measures one-batch MSE `7.68497e-5` and two-batch MSE `7.61978e-5`, with stable candidate hashes and 172 mapped pixels; the second batch improves the guarded candidate. The first updated test failed only because it compared nondeterministic wall-clock milliseconds during recovery. Recovery admission now excludes timing while retaining every semantic/hash field.
- The final Visual Studio Win32 Release compatibility build regenerates cleanly with `rrt_rc_composite.dxil` and links `rrt_dxr`; the direct shared-provider mode remains intentionally x64-only. Both modified Python contract scripts compile without syntax errors.
- Final documentation audit resolves all 110 project-local links. The planning helper still cannot count the long-lived checklist layout and reports `0/0`; direct inspection confirms the three-item shared-resource sprint is fully checked, so the next implementation boundary is presentation-capable composition and real frame scheduling.

## Presentation compositor continuation (2026-09-05)

- Session recovery reported no unsynchronized context. The guarded diagnostic composite is the stable starting point; presentation integration must preserve authoritative no-cache fallback until frame-local admission and failure recovery are proven.
- The renderer already owns a tested native D3D12 swapchain path (`presentation.h`) and a presentation compute pass (`presentPso`) that writes the normal `output` buffer before swapchain submission. The RC direct experiment currently allocates and readbacks an isolated candidate buffer only after rendering, so the narrow integration boundary is to retain a GPU candidate plus validity/admission metadata and select it in the existing presentation stage, without changing the raw/history resources.
- Existing `dxr_presentation`, asynchronous-slot and pacing tests cover buffer rotation, resize, occlusion, frame latency and readback accounting. The first RC presentation increment should extend the canonical RC path contract rather than rebuild swapchain ownership or claim live D3D9 integration.
- The renderer's presentation compute writes packed BGRA8 into `Renderer::output`, transitions it to `COPY_SOURCE`, and both headless snapshots and `NativeDisplay::Draw` consume that same buffer. The RC candidate is float RGB plus diagnostic error, so an opt-in GPU apply pass can patch only mapped pixels into `output` after strict admission; no swapchain changes are required for the first presented-candidate proof.
- Applying inside `RunRcDirect` keeps the candidate resource alive through the dispatch but requires explicit `output` state transitions and a refreshed readback before final pixel hashing. Failure must occur before any output mutation, or restore the no-cache buffer if a later apply-stage error is possible.
- Main currently invokes the RC direct path after headless rendering, draining and optional snapshot/save work, and then exits with the RC JSON report. RC modes are intentionally forbidden from windowed execution. Therefore the bounded first presentation slice is an explicit opt-in that patches the common renderer output buffer and validates its readback/hash; native swapchain scheduling remains the following milestone.
- The apply pass should use the retained ascending pixel mapping and admitted count, not diagnostic error `w`, because a correctly predicted mapped pixel can have zero error. It must preserve all unmapped packed BGRA8 pixels exactly and expose separate candidate-surface and applied-output identities.
- The first combined apply-shader/CMake patch was rejected atomically because the existing composite shader command uses different formatting than the assumed context. No file changed; the retry must inspect and patch the exact local CMake block rather than repeat the failed context.
- The corrected shader/build integration compiles in x64 Release and deploys `rrt_rc_apply.dxil`. The standalone provider remains in `build/rr-sdk-probe/Release`; its configured SDK root is `build/dependencies/fsr-2.3.0-radiance-cache`, while the renderer build intentionally has no link-time RC SDK dependency.
- The first opt-in application succeeds: all 172 admitted pixels are marked and changed, the 12,116 unmapped pixels remain exact, no-cache output SHA-256 is `f6dabb47da97f149b859a9645c10af922c097057995da7cac9a661136f46c641`, and applied presentation output SHA-256 is `719b289967ea103fb13d98ad5661c9c3e31f8b417d17de98deb3dbdf6a4c1659`. Direct wall time was 340.772 ms.
- The first updated CTest run used the stale renderer executable owned by `build/rr-sdk-probe`, so the new JSON field lookup raised `KeyError: apply_audit_readback_bytes` after 2.11 seconds. This is a build-tree synchronization error, not a runtime failure; rebuild that tree's `rrt_dxr` before retrying the contract.
- Rebuilding the RC test tree resolves the stale-binary issue; the expanded Release path contract passes in 15.23 seconds.
- `Show` already separates Win32 message pumping, frame-latency admission and `NativeDisplay::Draw`. A bounded native RC scheduling test can create its hidden window first, run the synchronous provider transaction on a worker future while the main thread continues pumping messages, then construct the swapchain and submit the admitted output through a paced, validating `NativeDisplay`. This avoids concurrent D3D command-list access while proving the UI thread was not blocked by the provider wait.
- The first `--rc-presentation-test` run succeeds. During the 340.153 ms provider wait the main thread processes two messages over 22 bounded pump cycles; the native latency-one swapchain then admits in one retry, submits/presents one frame, and exact back-buffer validation passes. The presentation output retains SHA-256 `719b289967ea103fb13d98ad5661c9c3e31f8b417d17de98deb3dbdf6a4c1659`.
- Final adjacent validation passes all eight selected contracts in both configurations: Release 40.45 s and Debug 41.08 s. These include all seven `rc_*` tests plus the pre-existing native `dxr_presentation` regression. x64 Debug and Win32 Debug/Release renderer targets also rebuild with the new shader; RC direct execution remains x64-only.
- A read-only documentation command used `Select-Object -Index 55..72`, which PowerShell treated as a string rather than an integer range; the shared guide tail was still retrieved and no files changed. Use array indexing on loaded lines or omit the redundant README reread.
- Final Python compilation and all 110 project-local Markdown links pass. The planning helper still reports its known `0/0` result for this long-lived checklist format; manual inspection confirms the four-item Radiance Cache presentation/scheduling sprint is complete.

## Persistent Radiance Cache worker continuation (2026-09-05)

- Session recovery reported no unsynchronized context. The starting point is an exact one-frame native scheduling proof; the next boundary is reusing one contained provider process/context across multiple renderer frame identities without sharing renderer command-list ownership across threads.
- `RcSharedPathChild` currently opens five shared buffers/fence, creates one provider context, performs baseline → training batch(es) → post inference → reset inference, restores the post output, signals fence 31, destroys the context and exits. This proves within-transaction persistence but forces a process/context launch for every renderer invocation.
- Direct renderer mode passes fixed handle/LUID/count/batch/budget arguments and consumes a bounded six-token record only after `RcRunIsolated` waits for child exit. A multi-frame worker therefore needs a bounded control protocol or shared control block plus reusable fence epochs; merely looping the current function would deadlock because every transaction assumes initial fence 30 and completion 31.
- `RcRunIsolated` deliberately owns process creation, handle allowlisting, job assignment, deadline enforcement, output limiting and final reaping as one blocking call. Reusing a process across parent-updated frames will require a live-session variant; refactoring that boundary simultaneously with renderer frame mutation would be unnecessarily broad.
- The next bounded increment will first prove amortization inside the existing contained transaction: two stable-frame training/inference epochs on one child process and one provider context, followed by exact reset recovery and restoration of the second trained output. This establishes cumulative context reuse and exact accounting before adding the bidirectional parent/child fence protocol needed for changed frame identities.
- The first two-epoch run passes. One process/context executes seven dispatches; epoch-one post and epoch-two start both hash to `6891511169378437159`, the second epoch changes all 516 populated RGB values, and final hash `12625136704411306072` resets exactly to baseline `566204800999108543` afterward. Final composite MSE is `7.61978e-5` with candidate SHA-256 `079c9ae7a4cd98a3e8cfb986e22d46a86cab868e58e8ea8da502584af58acd48`, exactly matching the established two-batch result.
- Representative persistent wall time is 426.558 ms, compared with 409.967 ms for one epoch in the same concurrent measurement and roughly twice that for two independent launches. The performance claim should be enforced only as persistent time below the sum of two same-run independent timings, not as an absolute 427 ms pin.
- Final cross-configuration validation is green: x64 Debug provider/renderer and Win32 Debug/Release renderer builds pass; all eight adjacent contracts pass in Release (42.10 s) and Debug (43.20 s). Direct/shared provider work remains intentionally x64-only.
- Final syntax and documentation audits pass: both modified Python RC contracts compile and all 110 project-local Markdown links resolve. The planning helper continues to report `0/0` for the long-lived checklist layout; direct inspection confirms the four-item amortization sprint is fully checked.

## Live Radiance Cache session continuation (2026-09-05)

- Session recovery reported no unsynchronized context. Stable-frame context amortization is the exact starting point; this slice must add a parent-controlled live process lifetime and fence epochs before attempting D3D9 integration.
- The existing isolation helper is intentionally blocking and owns job/process/stdout handles until child exit. A live session needs the same suspended launch, explicit handle allowlist, pre-resume job assignment, output cap and kill-on-close semantics exposed through an RAII process object whose final wait has a bounded deadline.
- The bounded live proof will use three fence-coordinated epochs on the same five shared resources: initial reset/train/post (`30→31`), stable-identity continuation without reset (`32→33`), and a renderer-updated camera frame with explicit provider reset (`34→35`). The parent will update shared inputs only after the preceding child completion fence, preventing concurrent resource ownership.
- The changed-frame parent can reuse the existing raw/compact pipelines: after fence 33, render a +0.05 camera-offset frame, transition raw/shared/mapping buffers back to UAV, regenerate provider inputs on GPU, return them to SRV state and signal fence 34. Final composition then targets the changed renderer output.
- The first live run succeeds without protocol retries. One child/context executes ten dispatches over fences 30–35. Stable epoch hashes are `6891511169378437159 → 12625136704411306072`; the camera-updated reset baseline is `9990495896441858603`, trained output `2371221569272493135`, and reset returns exactly to the updated baseline. The final changed-frame composite MSE is `7.68411e-5`, candidate SHA-256 `d35c845367cf6d02e7393d280e55c2876ce1e02aba97e86fd06fa98cc561cd40`, and initial/final frame identities differ.
- The first focused live contract failed only on an overly strict full-`Frame` digest comparison. A live camera update legitimately retains previous-view/history fields, while a fresh process launched at the same offset has no prior frame; their full structs must differ even though their camera/path candidate hashes match. The corrected gate requires the live initial/final identities to differ and separately pins exact changed-camera provider/composite equivalence.
- The second focused run reached the next comparison and rejected live-versus-fresh moved composite equality. The live candidate remains independently hash-pinned, so the next action is to inspect both reports from the same deterministic fixture rather than weaken the gate speculatively.
- Direct inspection exposed a real live-session count bug: the fresh +0.05 frame has 178 queries, while the live child retained the initial frame's 172 count after the parent replaced shared inputs. This explains the different trained/candidate hashes. The fix is to factor count discovery into a reusable child operation and rerun it after fence 34 before any changed-frame dispatch; the live report must then surface final-frame count separately from the initial count.
- Count discovery is now reusable and runs after fence 34; initial-value comparisons remain bounded to the original population while changed-frame/reset comparisons use the refreshed population. A follow-up attempt to insert an extra initial-count JSON field used shortened context against the serializer's single long physical line and was rejected atomically; no code changed in that attempt, and the existing `changed/3` protocol value already retains the initial population internally.
- The corrected live run discovers 178 changed-frame queries, changes all 534 populated RGB values, and exactly matches a fresh +0.05-camera run: trained hash `587237281996004111`, candidate SHA-256 `31f8700b024782226c43284f4849cb0a5539a47a4eb45cd7e0aa5985adde7761`, and composite MSE `7.68404e-5`. Reset remains exact to changed baseline `9990495896441858603`.
- Final cross-configuration validation passes: x64 Debug provider/renderer and Win32 Debug/Release renderer builds succeed. All eight adjacent contracts pass in Release (51.44 s) and Debug (52.71 s), including live-session timeout/early-exit recovery and the independent native presentation regression.
- Final syntax/documentation audit passes: both Python RC contracts compile and all 110 project-local Markdown links resolve. The planning helper still reports `0/0` for this long-lived checklist format; direct inspection confirms the four-item live fence-session sprint is fully checked.
