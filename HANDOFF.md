# Session handoff — 2026-09-07

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

## Previous launched state (2026-09-08)

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

## Previous launched state (2026-09-08)

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

## Previous launch and standing authorization (2026-09-08)

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

## Previous state — material failure diagnostics (2026-09-08)

Previous2560x1440 game pass exited0, executable unchanged, proxy removed/absent.
No game is running. It captured0 materials;168 generic failures could not be
localized. New optional v18 evidence_failure fields now identify stage/detail;
unsupported-shader rejection sampling preserves ledger budget. Accepted-draw
admission and full recorded write histories remain unchanged. See newest
progress.md for checks and docs/MATERIAL_FAILURE_DIAGNOSTICS.md for the contract.
Next useful pass: fresh bundle/current proxy,2560x1440:3, full v18 flags, wait for
user gameplay readiness before trigger. Do not reuse a previous bundle/proxy hash.

## Previous armed state (2026-09-08)

User authorized launch and other diagnostics. Launched prepared bundle
build/game-passes/hl2-material-2560-v18-20260908, run material, runner session84987.
Full v18 flags and shader inventory/trace/target diagnostics together; selection
2560x1440:3,60 trace presents. No game settings changes. Armed, NOT triggered.
Wait for user gameplay readiness, then trigger once. Do not launch again or
rebuild deployed proxy. After capture inspect ledger/assets and inventory;
wait for normal exit and verified cleanup before native material comparisons.

## Previous prepared state (2026-09-08)

User confirmed closed. No HL2 process; bin/d3d9.dll independently absent.
Runner confirms exit0, proxy_removed true, executable unchanged,222.843s.
Trace60 presents/166252 events/11646 shader draws/0 failed calls.
Selection analysis remains4096 attempts,83 sampled size mismatches,0 captures.
Observed2560x1440 is the next material target; do not change game settings.
Prepared fresh provenance-checked bundle with matching baseline:
build/game-passes/hl2-material-2560-v18-20260908. NOT launched.
Next run material with full v18 flags, selection2560x1440:3,60 trace presents,
wait-trigger and shader inventory. Wait for user gameplay readiness before trigger.

## Previous capture result (2026-09-08)

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

## Previous armed state (2026-09-08)

User explicitly requested launch and will report gameplay readiness. Fresh bundle
build/game-passes/hl2-selection-v18-20260908; run selection; runner session36239.
Full v18 flags,5120x1440:3,60 trace presents. Updated selection sampling proxy.
Matching baseline provenance reused. Armed, NOT triggered. Wait for user readiness
then trigger once. Do not launch again or rebuild deployed proxy. After bounded
capture, normal game exit and runner cleanup must precede native material replay.

## Previous state — 2026-09-08

HL2 material pass exited0; executable unchanged, proxy removed and absent.
It recorded0 captures and1573 target-size mismatches; actual size was not saved.
Selection diagnostics are now implemented/tested: observed target descriptors,
first4 per target/reason (up to64 keys) plus every64th attempt for v18 selection
failures. Full write histories retained; accepted draws unsampled. Stress4096
attempts produces67 records under1MiB and normal attempt-limit completion.
Next step: another short targeted gameplay pass using a fresh bundle/current
proxy to learn actual target sizes. No game is currently launched. See
`docs/HL2_MATERIAL_V18_RESULT.md` and newest progress.md for checks.

## Start here

Continue implementation in `P:\RTXRemixButForAMD` (Windows, PowerShell).
Read this file, then the newest entries in `task_plan.md`, `progress.md`, and
`findings.md`. Those logs contain historical pending states below newer completed
entries: do not restart old game runs or treat historical runner IDs as active.

Game-sized isolated material comparison is implemented (2026-09-08).
The immediate next step is **a targeted HL2 v18 material gameplay pass** (qualification results in progress.md). The comparator now has explicit --normalized-material mode
for captured extent/viewport up to8 million pixels; strict mode remains default.
Saved v5 game evidence lacks the material/texture inputs needed for comparison.
V18 admits explicit SYSTEMMEM texture-mip rectangles with complete destination coverage.
V17 admits SYSTEMMEM NO_DIRTY_UPDATE writes plus explicit full AddDirtyRect proof.
V16 admits proven equal-chain SYSTEMMEM -> DEFAULT UpdateTexture transfers.
V15 admits initialized managed DXT1/DXT3/DXT5 chains; V14 admits16MiB per
managed uncompressed chain; inline v13 retains64KiB. See docs/TEXTURE_ASSET_STORAGE.md,
docs/SURFACE_UPLOAD_QUALIFICATION.md, docs/DIRTY_TEXTURE_QUALIFICATION.md, docs/TEXTURE_UPLOAD_QUALIFICATION.md,
docs/COMPRESSED_TEXTURE_QUALIFICATION.md, docs/PIXEL_MATERIAL_RECONSTRUCTION.md
and docs/HL2_MATERIAL_AUDIT.md. Texture upscaling remains planned in
docs/TEXTURE_ENHANCEMENT_ROADMAP.md. See docs/GAME_SIZED_MATERIAL_COMPARISON.md
for comparison scope and the next gameplay pass. This slice does not launch HL2.

## Latest implementation: game-sized material diagnostic (2026-09-08)

- Explicit normalized mode preserves target dimensions and viewport. Uses a fresh
  float, no-MSAA, no-depth target with reported fixed raster state. Original
  textures/samplers/shader inputs are retained. Never claims frame equivalence.
- Native protocol2 validates dimensions, pixel budget and viewport before device
  creation. Whole-target clear makes offset viewport readback deterministic.
  Diagnostic image hashing has its own budget; scene limits stay unchanged.
- Fresh texture_scope test covers5120x1440 and offset/depth-range viewports,
  strict-mode compatibility, changed-texture controls and malformed inputs.
- Next gameplay is useful to test whether real HL2 produces complete v18 material
  evidence. If captures reject, inspect missing evidence before extending scope.
  Partial UpdateTexture/dynamic writes and full composition remain unqualified.
  See progress.md for final checks; no game launch or proxy deployment here.

## Latest implementation: partial surfaces v18 (2026-09-08)

- --position-surface-uploads / RRT_POSITION_SURFACE_UPLOADS=1 requires v17.
  Resolves texture-mip aliases by COM identity, validates copied source regions,
  tracks destination coverage and copies rows only after stable native success.
  Supports RGBA/DXT1/3/5 whole mips, aligned partial blocks and differing levels.
- Up to128 transfer entries per destination; reserved metadata counts toward
  the128MiB shadow budget. Every mip must be fully known. Failed/unknown/gapped/
  unsupported copies invalidate; no inferred mixing with earlier UpdateTexture
  initialization. Later whole-chain UpdateTexture can replace surface history.
- New origin and surface_transfers provenance; Python independently validates
  bounds, alignment, source extents and complete coverage. Importer/replay/runner
  support v18; old versions retain their contract. Results in progress.md.
- Split compressed/upload/dirty/surface qualification into independent CTest
  matrices (120s each, fresh fixture inputs, shared native resource lock).
  Core position_capture is back to about41s in Release, retaining its180s limit.
- Next material comparison at game-sized targets and a clearly specified raster
  scope. Capture can record structural target metadata, but the current comparator
  rejects saved5120x1440 game targets. Partial UpdateTexture, dynamic/direct-default
  writes and full-frame composition remain unqualified. Reassess gameplay after
  a useful material comparison can run. No HL2 launch/deployment in this slice.

## Latest implementation: explicit dirty evidence v17 (2026-09-08)

- --position-dirty-textures / RRT_POSITION_DIRTY_TEXTURES=1 requires v16. Exact
  NO_DIRTY_UPDATE locks establish bytes on tracked SYSTEMMEM textures without
  creating dirty proof. Creation proof is retained until an upload consumes it.
- Successful null/whole AddDirtyRect proves the full source chain dirty while
  preserving known bytes. Partial notifications cannot upgrade proof; failed or
  invalid notifications, pending writes/epoch/overlap gaps invalidate. Unknown
  contents stay unknown. No rectangle union or partial transfer reconstruction.
- V17 default transfer objects add dirty_proof: creation/top_lock/notification.
  Reader/importer/replay/runner support it; v16 shape and runtime admission remain
  unchanged. Source byte revisions and dirty proof remain separate concepts.
- Fixtures compare exact blocks across16 draws per admitted case, all24 native
  float images with/without proxy and isolated replay. Missing/partial proof,
  unknown contents, invalid rectangles, bad records and legacy runs reject.
  Results in progress.md; contract in docs/DIRTY_TEXTURE_QUALIFICATION.md.
- Next UpdateSurface and partial uploads; no gameplay launch yet. Dynamic/default
  direct writes and full-frame composition remain separate qualification work.
- Latest Debug position_capture takes156s against its180s timeout. Before adding
  another large fixture matrix, split qualification tests or otherwise justify
  and adjust test organization rather than silently exceeding that bound.

## Latest implementation: whole-chain uploads v16 (2026-09-08)

- --position-texture-uploads / RRT_POSITION_TEXTURE_UPLOADS=1 requires v15 and
  prerequisites. Tracks private usage-zero SYSTEMMEM and DEFAULT chains, formats
  RGBA/DXT1/3/5. Full-dirty proof starts at creation, is consumed on every observed
  source UpdateTexture attempt, and can be restored by whole top-level writes.
- Default destination invalidated before native call; only success with proven
  full source bytes, exact matching chains and stable revisions/epoch/no overlap
  establishes independent destination shadows. Source mutation afterward cannot
  alter destination bytes. Pool/operation/source/revision provenance in v16 rows;
  old versions cannot claim default transfers. Existing asset/memory bounds remain.
- Fixtures check whole/partial-initialization uploads, changed full rewrites,
  alias recovery and source changes after upload; native/proxy full-image hashes,
  exact blocks and replay. Partial/clean repeats, failures, incomplete chains,
  lower-only writes, aliases, mismatched chains and invalid provenance reject.
  Source IDs are session-local evidence, not persistent assets. Results in progress.md.
- A null destination faults this native runtime; failure control instead uses a
  valid managed destination (invalid pool for UpdateTexture). Both observer
  interfaces are generated and audited for pre/native/post hook order.
- Next explicit AddDirtyRect and UpdateSurface/partial paths; dynamic/default
  direct writes remain unqualified. Reassess gameplay after these can answer a
  useful material question. No HL2 launch or deployment in this slice.

## Latest implementation: compressed capture v15 (2026-09-08)

- Opt-in --position-compressed-textures / RRT_POSITION_COMPRESSED_TEXTURES=1
  requires v14 texture assets and prerequisites. Adds private managed usage-zero
  DXT1/DXT3/DXT5 alongside RGBA. Same external hash/size assets and budgets;
  v13/v14 format admission unchanged. Reader/importer/replay/runner support v15.
- Tracks block rows and known bytes across whole and4x4-aligned partial writes;
  small tails accept whole mip locks. Copies before native unlock, marks known
  only on success. Existing failure/alias/dirty/copy/reset invalidation applies.
- Native full/partial/readonly/alias-refresh captures verified for all3 formats;
  exact Python block bytes across16 draws per accepted case, proxy/native image
  hashes across24 fixture draws,57 restored draw comparisons. Failed, alias,
  dirty, incomplete, unsupported-flag and unaligned writes reject. DXT2/DXT4,
  malformed records and legacy compressed captures reject. Results in progress.md.
- Next qualify default-pool/update paths without inferred contents. Full frame
  composition and real-game compressed evidence remain unqualified. Another
  gameplay pass is not needed yet; preserve the future texture-upscaling roadmap.

## Latest implementation: synthetic compressed replay (2026-09-08)

- Native --pixel-replay accepts bounded DXT1/DXT3/DXT5 block payloads, restores
  tight block rows using native pitch and verifies every row with read-only locks.
  Tiny mips retain complete blocks. Format, base alignment, mip count and exact
  byte budgets are checked before device creation. V13/v14 capture is unchanged.
- Twelve synthetic cases cover rectangular chains, both samplers, final1x1 LOD,
  filtering, sRGB, color selectors and alpha modes. Changed texels/alpha/LOD must
  differ; transparent/opaque blocks test output alpha. Malformed payloads reject.
  Report: pixel-compressed-comparison.json beside fixture ledgers. Tests/results
  in progress.md; implementation gate in docs/COMPRESSED_TEXTURE_QUALIFICATION.md.
- Next add a new opt-in capture version, block-aware full/partial write tracking,
  independent asset validation and native capture transparency tests. Native
  sampling is shared by both shader paths; CPU decompression is not qualified.

## Latest implementation: external mip store (2026-09-08)

- Opt-in v14 --position-texture-assets / RRT_POSITION_TEXTURE_ASSETS=1 requires
  v13 and all prerequisites. New exclusive <ledger>.assets directory, SHA-256.bin
  files and compact {sha256,size} mip references.16MiB/chain,256MiB/512 new files
  per session; existing128MiB shadow and ledger/draw bounds retained.
- Deduplicates complete blobs. Existing directories/files are not overwritten;
  failed writes charge reservations and can leave unreferenced partial/orphan
  assets. Reader verifies regular non-reparse files, hashes, lengths and budgets.
  Immutable per-inspection cache; no inferred contents from a missing asset.
- Importer and diagnostic tools resolve sibling assets. Native pixel payload
  supports larger restored textures without embedding bytes in every ledger row.
  Tests verify patterned256x128 chains, deduplication, corruption/missing/path/size
  rejection, collision preservation, relocation and replay. Results in progress.md.
- No new formats/pools admitted. Still private managed usage0 A8R8G8B8/X8R8G8B8;
  compressed/default-pool/update qualification remains before another HL2 pass.

## Latest implementation: reconstructed pixel comparison (2026-09-08)

- New tools/replay_pixel_material.py restores a completed v13 draw, constants,
  mip bytes and sampler/LOD state, then compares exact original PS with independent
  HLSL cubic lightmap/base/tint/lighting/fog arithmetic. Native helper --pixel-replay
  compiles ps_2_b and retains the original VS. All float lanes compared at2e-4.
- Captured16-draw comparison and four synthetic high-frequency lightmap cases
  pass; wrong fog/alpha/texels/address/sRGB/LOD/filter and single-sample-lightmap
  controls detect differences. Comparison reports saved beside fixture ledgers.
  Release/Debug metrics are in progress.md.
- Isolated128x96 draw only, fixed raster subset, point/linear sampling and bounded
  addressing/LOD/sRGB states. Native texture sampling is shared by both programs;
  no independent CPU sampler, full frame or composition equivalence claimed.
- Resolved fixture COM lifetime teardown bug. No production proxy/capture changes
  in this slice. Larger assets and additional resource/update types are still
  needed before a useful new HL2 gameplay pass.

## Latest implementation: initialized mip evidence (2026-09-08)

- Opt-in v13 --position-texture-inputs / RRT_POSITION_TEXTURE_INPUTS=1 requires
  v12 and all prerequisites. Observed private managed usage0 A8R8G8B8/X8R8G8B8
  textures only; <=64KiB per complete mip chain. Copies initialized rows before
  native unlock and establishes knowledge only on success; partial writes merge.
- Failed locks/unlocks, unsupported flags, dirty notifications, copies, generated
  mips and surface-alias writes invalidate conservatively. Complete direct writes
  can restore knowledge. Successful resets invalidate through a global epoch.
- texture_inputs has sampler-matched IDs, local revisions, observed origin,
  ordered tight mip bytes and SHA-256. Reader verifies bounds/formats/digests;
  importer preserves metadata. V12 descriptors still say contents unknown; the
  separate v13 field is the initialized-byte evidence. No textured scene promotion.
- Native controls cover full/partial writes, readonly preservation, alias refresh,
  failed locks/copies, generated mips and incomplete recovery. Failed-unlock/reset
  recovery lacks a dedicated native scenario; hook ordering/reset wiring checked.
  Release/Debug validation results are in progress.md. No new HL2 pass yet.

## Latest implementation: paired material state (2026-09-08)

- Opt-in v12 --position-pixel-material / RRT_POSITION_PIXEL_MATERIAL=1 requires
  v11 and all prerequisites. Exact paired1792-byte PS, known finite external
  c11/c12/c29/c30, effective s0/s1 DWORD sampler values, bound 2D resource IDs,
  current LOD/autogen filter and bounded mip descriptors. Contents="unknown".
- Failed writes do not establish PS knowledge; state blocks/reset invalidate it.
  Added texture LOD/autogen-filter overlap guards; v12 conservatively rejects
  observed overlap. Reader and importer preserve/validate the new metadata.
- Native fixture uses patterned mip chains and changing bindings/constants/
  samplers. Original VS and CPU passthrough use the same PS: no independent PS
  replay or texture-content reconstruction claim. Includes rejection and refresh
  controls. Release/Debug results are in progress.md.

## Latest implementation: material vertex inputs (2026-09-08)

- Opt-in v11 `--position-material-inputs` / `RRT_POSITION_MATERIAL_INPUTS=1`
  requires v10 and all prerequisites. Exact audited stride48 declarations,
  initialized color/UV bytes and known VS c12/c16; bounded to1024 triangles/draw.
- Captures UV0/UV1, packed color and ten evaluated lanes: t0.xy/t2.xy,
  normalized RGBA, t4.w and raw oFog/oD1 scalar. Independent Python validation;
  scene importer preserves metadata without changing position-only assets.
- Native original VS versus CPU passthrough fixture uses24 UV/color/fog probes
  with nonuniform clip W. Fog is probed through duplicate oD1, not fixed-function
  fog. Includes incorrect-CPU control, missing initialized bytes/constants,
  state-block invalidation, overflow, budget and malformed-ledger checks.
- No actual paired PS shading, textures or full-frame equivalence claimed.
  Release/Debug validation results are recorded in progress.md.

## Latest audit and roadmap (2026-09-08)

- Exact paired PS ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11,
  1792 bytes, ps_2_x; paired with the existing pinned612-byte VS in231 original
  inventory draws and294 multi-draw inventory draws. These are not automatically
  correlated with the16 position captures; inventory ordinals are independent.
- PS reads s0 once and s1 four times, vertex color, UV0/UV1, t4.w, PS c11/c12/c29/c30.
  Embedded constants encode1024×512 lightmap reference scaling, not measured texture
  dimensions. Bound textures, sampler state, texels and constant values are missing.
- VS stream0 inputs: float2 UVs at28/36, D3DCOLOR at24, stride48; add VS c12/c16
  output coverage. Qualify channel order, perspective interpolation and initialized
  bytes before texture capture. Other declared streams cannot be ignored generically.
- Reproducible CPU-only tool tools/audit_hl2_material.py. Saved audit.json/vs.asm/
  ps.asm under build/material-audit-20260908/multidraw and original-debug. Same-input
  Release/Debug reports agree exactly; truncated input rejected; Python compile
  passes. No native capture/runtime code changed by this audit.
- Future texture upscaling: source-faithful replay first, reversible hash-keyed
  replacement manifests, offline base-color2×/4× candidates, alpha/mip/seam/data-map
  policies, memory/cache budgets, then workbench/runtime integration. Lightmaps and
  transient textures excluded initially; no model chosen or downloaded.

## Goal and honest current status

Build an AMD-capable Remix-like legacy-game reconstruction/rendering pipeline.
HL2 is the active qualification game. Standalone AMD D3D12/DXR and radiance-cache/
denoiser experiments exist, but there is **no continuous commercial-game capture
to ray tracing to presentation pipeline or live relighting yet**.

Current proven work: stable guarded D3D9 proxy workflow; narrow exact-shader
position capture; validated offline scene import; native-vs-CPU position replay;
ordered grouped diagnostic replay; composition-state, latest-clear and bounded
ordered observed-write evidence with explicit gaps; closed standalone RT0 color-call
scope qualification. This qualifies a narrow call stream, not actual pixel replay.
V10 additionally replays an admitted synthetic constant-color prefix with captured
clear/blending, matching native-vs-CPU vertex paths and analytic blend controls.
Captured positions are not complete materials, normals, UVs, skinning or whole
scene coverage. Legacy grouped diagnostic replay disables depth/blending and uses its
own diagnostic clear. Never describe it as reproducing the original game frame.

User priorities retained: eventually unified one-run capture and a UI; broader
shader/engine support including SM3/UE3, a separate DX10/BioShock path, DX8/older
wrappers, FidelityFX features and deeper AMD ray-reconstruction/denoiser work.
These are roadmap items, not evidence that those integrations already work.

## Latest completed slice: v10 controlled color replay

Flag `--position-color-replay` requires `--position-surface-scope` and its
prerequisites. Environment `RRT_POSITION_COLOR_REPLAY=1`. v1–v9 are retained.

- Capture bounded native pixel program bytes, effective pixel c0, extra raster
  states (fog, clipping, clip planes, dither, sample mask, line AA), N-patch mode.
- Admit only exact ps_2_0 `mov oC0,c0`, finite RGBA0..1,128x96 float target/full
  viewport, closed v9 scope, fixed no-depth/no-cull/solid raster and supported ADD
  blending with ZERO/ONE/SRCALPHA/INVSRCALPHA factors. No textures/materials.
- New replay_position_colors.py validates immutable v10 input/digest and resolves
  every captured predecessor from the retained clear to the endpoint. Missing or
  unsupported prefix draws reject the segment. Later uncaptured writes are outside
  the explicit endpoint, not assumed absent.
- Native RRT_POSITION_COLOR1 fixture replays actual clear/per-draw color/blending
  on exact native VS and CPU-position paths. Analytic center/background checks,
  order, overwrite, additive controls and malformed/state negatives pass.
- Separate color report can mark this prefix ready_for_stateful_replay=true;
  generic per-draw initial contents/readiness remain unknown/false. This does not
  establish original-frame pixel readback equivalence or real HL2 material support.
- v10 device setters participate in overlap tracking. Native concurrent rendering
  is not qualified; the fixture is serialized. Legacy group protocol unchanged.

Contract: `docs/POSITION_COLOR_REPLAY.md`.
New code: `src/shader/color_contract.h`, `tools/position_color_replay.py`,
`tools/replay_position_colors.py`. Existing inspector/import/fixture/runner extended.

## Previous completed slice: v9 closed standalone color scope

Runner flag `--position-surface-scope` requires `--position-write-evidence` and its
prerequisites. Environment `RRT_POSITION_SURFACE_SCOPE=1`. v1–v8 remain available.

- Observe successful CreateRenderTarget/Ex before returned wrappers: private
  creation (shared-handle parameter null), nonlockable target, device/reset epoch.
  Ex Usage must be0. Exclude texture-backed, shared and unknown resource origins;
  no general texture/subresource alias graph has been implemented.
- At Clear and captured draw, query every reported MRT slot (1–4) and depth;
  require only RT0 and no depth/MSAA for the narrow scope.
- Independently track at most64 outstanding resource accesses, including locks
  begun before a clear or overwritten history. Failed calls preserve accounting;
  duplicate/unknown/mismatched/overflow access sets a sticky exclusion gap.
- Accepted v9 rows carry `surface_scope` clear/draw snapshots. Reader validates
  bounded exact shapes, attachment linkage, immutable origins and sticky gaps;
  importer preserves the evidence. Group reports include per-draw `color_scope`.
- `color_scope.qualified` and `complete_color_write_call_coverage` can be true only
  for this private standalone target with full retained color clear and exclusively
  captured subsequent writes. Global v8 `unobserved` remains true. Initial contents
  at captured draws stay unknown; all stateful-replay readiness remains false.
- Native controls: private/recreated/reset scopes, closed/open/failed/overflow
  access, texture/MRT/depth/lockable exclusions, fills/history exhaustion and clear
  variants. Shared-origin negative is metadata plus generated-hook audit, not a
  native cross-process sharing test. Existing raster comparison remains exact.

Contract: `docs/POSITION_SURFACE_SCOPE.md`.
New reader/qualifier: `tools/position_surface_scope.py`.

## Previous completed slice: v8 ordered observed-write evidence

Runner flag `--position-write-evidence` requires `--position-clear-evidence` and
all its prerequisites. Environment `RRT_POSITION_WRITE_EVIDENCE=1`. v1–v7 retained.

- A fixed process-wide ring retains 64 writer/boundary call outcomes, including
  excluded indexed shaders/draws, non-indexed/UP/patch draws, copies/fills/texture
  updates/readbacks, surface/texture/cube/volume locks/DC/mip/dirty calls, attachment
  switches, Apply, Reset and Present. Edit generator and regenerate forwards.
- Pre-call lifetime IDs, device/reset provenance, post-call clear serial and native
  HRESULT (synthetic S_OK for void calls); accepted DIP calls link capture ordinals.
- Per-row `write_evidence` contains contiguous history, dropped-prefix endpoint,
  sticky observer/overlap gaps, and mandatory `unobserved: true` scope marker.
  Histories are validated across rows and preserved by immutable scene import.
- `write_coverage.observed_segment` distinguishes captured-only observed segments,
  gaps and absent clear anchors. Group reports now assess every draw.
- All complete-coverage/stateful-replay admission remains false; initial contents
  unknown. Aliases, MRT, shared/external writers and access lifetimes are not
  qualified. Process-wide unrelated writes intentionally block local assessment.
- Native controls exercise regular draw forms, rejected same-output shader,
  failure preservation, fills/readback/locks, attachment changes, reset epochs,
  quota-excluded draws and 70-call overflow. Raster oracle remains exact. Overlap
  and observer-gap consumer tests are synthetic, not induced native concurrency.

Contract and full audit: `docs/POSITION_WRITE_EVIDENCE.md`.
New reader/admission helper: `tools/position_write_evidence.py`.
Serialization failure terminates v8 with I/O-error semantics rather than allowing
an uncommitted capture reference to continue in later snapshots.

## Previous completed slice: v7 clear evidence

Runner flag `--position-clear-evidence` requires `--position-render-state` and its
selected multi-draw prerequisites. Environment `RRT_POSITION_CLEAR_EVIDENCE=1`.
Default/older capture behavior is unchanged.

- Copies pre-call Clear flags, colour, raw float depth bits, stencil and at most
  16 rectangles, plus target/depth IDs, target descriptor, viewport, scissor
  enable, reset epoch and expected clear serial.
- Commits only native successful clears. Failed clears preserve previous success.
  Successful unrecordable/oversized clears invalidate the payload to null.
- Keeps only the latest clear per device, not a complete event history.
- Reader validates payload; importer preserves it; grouped reports expose
  `initial_content_admission`.
- Every admission remains `initial_contents: unknown` and
  `ready_for_stateful_replay: false`, even for a full-target-clear candidate.
  Intervening draws/copies/locks/writes are not yet proven covered.

Contract: `docs/POSITION_CLEAR_EVIDENCE.md`.
Previous contract: `docs/POSITION_COMPOSITION_EVIDENCE.md`.

### Implementation map

- `src/shader/intercept.h`, `src/shader/intercept.cpp`: BeforeClear/AfterClear,
  device Knowledge lastClear/serials, composition metadata, capture/commit guards.
- `tools/generate_observers.py`: generated COM callbacks; edit the generator and
  regenerate rather than only editing generated forwarders.
- `tools/inspect_position_capture.py`: strict immutable bounded reader, v1–v10.
- `tools/capture_position_scene.py`: preserves v6+ render-state JSON.
- `tools/position_initial_contents.py`: conservative assessment of validated rows.
- `tools/replay_position_groups.py`: grouping plus admission report.
- `tools/game_pass.py`: guarded runner and CLI option.
- `src/shader/position_fixture.inc`: native clear fixture variants.
- `src/shader/position_group_fixture.inc`: bounded grouped native/CPU GPU fixture.
- `tests/verify_position_capture.py`, `tests/verify_position_groups.py`,
  `tests/verify_game_pass.py`: regression/negative controls.

### Capture constraints worth preserving

- Exact HL2 vertex shader: 612 bytes, SHA256
  `0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2`.
- Position-only raw triangle corners and eight constant rows (c0, c4–7, c58–60).
- v5+ selected multi-draw: 16 accepted total, 4 per successful-Present interval;
  4096 indexed attempts, 4096 triangles per draw, 16 MiB ledger, 120 Presents.
- v6 adds lifetime surface IDs, successful clear/binding serials, selected native
  effective render states, depth descriptor and scissor. Not complete stencil/MRT.
- v7 adds `render_state.last_clear` (null or bounded payload). It may refer to
  another target or an older reset, so consumers must check identity/epoch.
- v8 adds top-level `write_evidence` to every attempted draw row. It is a bounded
  observed-call window, not complete actual writes. Byte limits can stop earlier
  because rejected attempts carry history too.
- v9 adds `surface_scope` to accepted rows. Only standalone private RT0 color-call
  coverage can qualify; pixel materials/replay and depth remain unsupported.
- v10 adds `color_replay`; only its exact controlled shader/state subset can be
  replayed by the separate color tool. General pixel materials and depth remain out.
- Successful native draws only; capture reservations released on rejection;
  reset/state-block constant knowledge remains conservative. No automatic
  persistent-object identity inferred from matching content hashes.

## Validation at handoff

Native Release and Debug v10 proxy/fixture builds passed. Full Release regression
**10/10 passed, 41.03 seconds**; Debug **4/4 passed, 42.56 seconds**.
Final setter-overlap guard capture reruns pass Release26.99s and Debug33.26s.
Python compilation passed. No outstanding test failures. The v8 transient
Windows report-polling fix remains limited to bounded test polling.

Release test set: position_scene, capture_position_scene, position_capture,
recorded_position_oracle, position_reconstruction, shader_proxy,
game_pass_workflow, proxy_equivalence, proxy_equivalence_ex, position_groups.
Debug set: position_capture, shader_proxy, game_pass_workflow, position_groups.

Clear tests cover full/partial/depth-stencil clears, failed-clear preservation,
successful 17-rectangle unknown fallback, malformed metadata and conservative
admission. V8–v10 controls are listed above. Legacy raster output remains unchanged.
No real-game v6–v10 capture yet.

```powershell
cmake --build build/x86-vs --config Release --target radeon_d3d9_proxy rrt_shader_fixture
cmake --build build/x86-vs --config Debug --target radeon_d3d9_proxy rrt_shader_fixture
ctest --test-dir build/x86-vs -C Release -R "^(position_scene|capture_position_scene|position_capture|recorded_position_oracle|position_reconstruction|shader_proxy|game_pass_workflow|proxy_equivalence|proxy_equivalence_ex|position_groups)$" --output-on-failure
ctest --test-dir build/x86-vs -C Debug -R "^(position_capture|shader_proxy|game_pass_workflow|position_groups)$" --output-on-failure
```

All previous tool/test/game runner sessions have completed. Last checked: HL2
closed and `J:\SteamLibrary\steamapps\common\Half-Life 2\bin\d3d9.dll` absent.
Recheck current processes and deployment before future native builds/deployment.

## Next implementation slice

1. Implement the pinned VS's initialized UV0/UV1, packed color and fog outputs,
   following docs/HL2_MATERIAL_AUDIT.md; verify native/CPU interpolation and failures.
2. Add correlated exact paired PS/constants, sampler/resource descriptors, then
   initialized texel/mip provenance and bounded textured fixtures. Extend target
   sizes/formats only with evidence; v10 admits128x96 synthetic float targets only.
3. Keep depth scope/initialization and full material/alias support separate. Retain
   complete-prefix checks and all gaps. Do not claim game-frame equivalence merely
   because an offline renderer produces matching synthetic color.
4. Validate Release/Debug, then decide whether gameplay can provide useful actual
   game qualification. No HL2 run is needed for the completed constant-color slice.

## Saved real-game evidence (reuse before requesting another run)

Latest v5 bundle: `build/game-passes/hl2-multidraw-20260907`.
Ledger: `runs/multidraw/position-capture.jsonl`.
SHA256: `dd0ef91fffbee117c325ffd4781a433c5f1743384a6a99bdd3655687262d2302`.
Native game exited successfully after 124.297 seconds, executable unchanged,
runner-owned proxy removed and absence verified.

- 16 accepted / 524 attempts, four samples each at intervals 207–210, target
  5120x1440. Four repeated position-content blocks of 3/35/4/6 triangles.
- 192 submitted triangles; not 192 unique triangles or 16 identified objects.
- Per-draw Release/Debug replay: 12 visible matches, 4 empty on both paths;
  all exact coverage and zero normalized error. Empty is not visible validation.
- Grouped replay: four 48-triangle groups, covered pixels 2593/2588/2555/2565,
  zero error and identical Release/Debug output fingerprints.
- Reports under `reconstructed`: `gpu-release-after-exit.json`,
  `gpu-debug-after-exit.json`, `group-release.json`, `group-debug.json`.
- Docs: `docs/HL2_MULTIDRAW_RESULT.md`, `docs/HL2_GROUPED_POSITION_REPLAY.md`.

Other configured test evidence:

- Original v1: `build/game-passes/hl2-combined-20260907/runs/combined/position-capture.jsonl`;
  CMake `RRT_HL2_POSITION_CAPTURE` points here, tests include v1 expectations.
- Shader inventory: `build/game-passes/hl2-inventory-20260907/runs/inventory/shader-inventory.jsonl`;
  CMake `RRT_HL2_POSITION_INVENTORY` points here.
- Group evidence: CMake `RRT_HL2_GROUP_CAPTURE` points to latest v5 ledger above.
- Reusable native baseline: `build/game-passes/hl2-20260907/runs/baseline/report.json`.

## Game safety / workflow

HL2 executable: `J:\SteamLibrary\steamapps\common\Half-Life 2\hl2.exe`.
Arguments: `-steam -game hl2_complete`.
32-bit executable SHA256:
`0dbc5fb2f27e9a5fef519d3e05e6c8f4444986010ca1f2e9cbfb4cc1ca9f97fe`.
Correct proxy location is **bin/d3d9.dll**, not game root.

Use the existing guarded game-pass runner; preserve ownership/hash checks and
cleanup. Never rebuild/replace a deployed DLL while the game is running. Await
the user's "in game" before triggering capture. Ask for normal exit when done;
verify runner cleanup and executable preservation. Run GPU diagnostic replay
after game exit: an earlier replay failed while HL2 was running and passed after
exit; exact cause was not established.

The user disabled Radeon overlay; do not change overlays/game settings yourself.
BioShock 2 works in its default path but forcing DX9 crashed natively with
0xC0000005. Do not repeat forced-DX9 experiments; DX10 is a separate future path.
BioShock installation is `O:\SteamLibrary\steamapps\common\BioShock 2`.

Preserve existing workspace edits. Use apply_patch for local edits; avoid
destructive Git/filesystem operations. Do not infer authorization for engine
memory manipulation or unrelated game changes from roadmap discussion.

## Suggested opening prompt for the new session

Read HANDOFF.md and the newest planning logs in P:\RTXRemixButForAMD. Continue
after the completed material audit with pinned-VS UV/color/fog output capture and
native/CPU interpolation controls. Keep the texture-enhancement roadmap for later.
Preserve conservative admission/native rendering and tell me when gameplay is needed.
