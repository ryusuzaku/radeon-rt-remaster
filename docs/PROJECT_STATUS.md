# Project status — 2026-11-14

The project is a working capture/replay and standalone AMD ray-tracing prototype.
It is **not yet a playable Remix-style runtime for a commercial game**, and no
version is tagged. The immediate blocker is Phase 3 material evidence at game
size; the DXR renderer is at Phase 5 and the live runtime at Phase 6.

## What changed since the 2026-09-06 revision

**The generic vs_2_0 position interpreter landed (2026-11-10, merged 2026-11-14).**
Q12 is decided: instead of one hand-written CPU evaluator per vertex program, an
interpreter runs each program's own position slice — backward slice of `oPos`,
named refusals, float32 evaluation in program order, camera read from the
program's own constant table. The 20 programs still refused in the 2026-11-10
gameplay frame are admitted position-only, each verified by an instrumented-bytecode
GPU point oracle (2,048 vertices, four variants, both boolean-constant settings):
all 20 plus the three hand-admitted programs pass with maximum error 0 on the
RX 9070 XT, and the interpreter equals the three hand-written evaluators bit for
bit over 4,000 random trials each. An independent double-precision Python
implementation agrees on every slice. Admission stays pinned per program: a
digest list in a JSON schema and a C++ header, kept identical by a contract test;
admitting another program means running its oracle, not editing C++. Material
capture still refuses interpreted programs, and the four programs with no named
camera are refused at scene conversion rather than placed under an assumed
camera. See [the interpreter contract](VS_INTERPRETER.md).

**Frame-level capture identified the vertex program as the limit, and two
per-program admissions followed (2026-11-10).** The first raised-quota frame
capture (`hl2-frame-20261027`, run `frame2`) captured 270 draws against 3,293
`unsupported_shader` refusals without reaching either quota: one frame is 92
indexed draws / 19,004 triangles from 23 vertex programs, of which the skinned
3348-byte program draws 48.8% of the triangles and the 1420-byte flex program
34.4%, while the one admitted program drew 0.3%. The run also exposed an
ill-conditioned reader check (float32 cancellation on map-sized positions), now
fixed with a bounded rounding allowance and the `position_conditioning` test.
The 1420-byte flex program ([contract](HL2_FLEX_POSITION_CONTRACT.md)) and the
3348-byte skinned program ([contract](HL2_SKINNED_POSITION_CONTRACT.md)) were
then admitted as the second and third position-only evaluators, with constant
tracking extended to all 256 registers. In game (pass `hl2-skin-20261110`), the
captured share of each frame rose from 5,608 to **13,520 of 18,745 triangles
(72.1%)**; 39 draws from all three programs convert as one scene under one camera
(clip error 8.5e-6). See [the frame result](HL2_FRAME_CAPTURE_RESULT.md). The
interpreter above then replaced the per-program treadmill for the remaining 20.

**The renderer's render resolution is now independent of the captured extent
(2026-10-19).** `--render-scale 1..100` sizes every per-pixel buffer, dispatch and
readback from an internal grid and upscales it at presentation; the 100% default
stays byte-identical. Captured scissors are mapped back into target space so clip
boundaries do not move, RR/RC evidence paths refuse a reduced grid, and
`dxr_render_scale` covers allocation, colour, clipping, exports, native
presentation and fail-closed inputs on x86 and x64. This is the buffer decoupling
FidelityFX upscaling needs; the upscale itself is still nearest-pixel. See
[DXR viewer](DXR_VIEWER.md).

**The 256 MiB shadow-cap experiment closed with a negative result (2026-10-14).**
The larger cap did not admit the missing material draws: the v19 chain stopped at
4096 attempts with zero captures, dominated by `pixel_material/pixel_material_shader`
rejections rather than texture budget. The validated inventory identifies a
`ps_2_x` family (1912 bytes) that needs a fifth constant row (c10 eye position) and
a different fog path; adding its hash to the allowlist is explicitly insufficient.
The default stays 128 MiB. See
[the experiment](HL2_SHADOW_CAP_EXPERIMENT.md).

**The 2026-10-15 evidence loss was apparent, not real, and is repaired
(2026-10-19).** The consolidation removed `build/` from the working tree, and an
earlier revision of this file recorded the pass bundles as lost. They were not:
the pre-consolidation tree was preserved in full — including gitignored content —
as a WIM image, with a 40,401-entry SHA-256 manifest. `build/game-passes` (738
files, 881 MiB, 22 passes) was extracted and verified **738/738 against that
manifest** with no missing, resized, mismatched or extra files. The verified copy
lives in the evidence root at
`P:/workspace/ninja-code/radeon-rt-remaster-evidence/restored-8cc61db052` and a
working copy sits in `build/game-passes`, so the 13 `local_evidence` tests run
again instead of skipping. The archive's own `build/dependencies` holds only a
bare `.git` for the FSR SDK, so that track is recoverable by checkout but is not
registered here yet. See [build guidance](BUILD.md) for the restore procedure.

**The first real HL2 material capture landed on 2026-09-16.** Every earlier HL2
pass captured zero material draws. `material3` in
`build/game-passes/hl2-dynamic-v19c-20260916` reached its capture limit with
**16 captured draws** at target `[1920,1080,21,0]`, carrying 32 texture inputs
(16 whole-chain `observed_private_default_update` with `top_lock` dirty proof, 16
in-place `observed_private_default_dynamic` with no transfer block) and 19
external assets totalling 5,327,872 bytes. See
[HL2 dynamic material capture](HL2_DYNAMIC_MATERIAL_CAPTURE.md).

That pass closed two structural gaps, and both were the reason earlier passes
captured nothing:

- **Selection no longer requires knowing the render-target extent in advance.**
  `--position-selection any:MIN_TRIANGLES` selects on primitive count alone and
  records `any_target` in the ledger header. The earlier v18 pass spent its entire
  byte limit on 1,573 `selection_target_mismatch` rejections against a hardcoded
  5120x1440 — see [the v18 result](HL2_MATERIAL_V18_RESULT.md), which records the
  failure honestly rather than hiding it.
- **Triggered capture arms on a real Present** and stops at the interval, instead
  of exhausting the 4,096-attempt budget inside a non-presenting interval. The
  material3 pass stopped after 4 presents / 668 attempts.

**The remaining texture failure in material3 is the shared budget, not shader
support.** 20 x `texture_tracking_missing` at slot 1 for a 1024x512
`D3DFMT_A16B16G16R16` DYNAMIC DEFAULT sampler input (~4.5 MiB each) are refused at
`shadow_budget`. The dynamic-admission and 16-bit-float format gates both pass.
Separately, 15 x `unsupported_shader` remain outside the pinned-program allowlist
and 6 x `selection_primitive_minimum`. This is a budget-policy decision, tracked
as the first open question in [the codebase map](../CODEBASE_MAP.md).

The peak-instrumented run on 2026-10-14 reached 128 MiB minus four bytes,
79.8% textures, but captured no materials and failed primarily at buffer-range
checks before sampler admission. A bounded 256 MiB CPU shadow-cap experiment
is implemented via `--shadow-mib 256`; the default remains 128 MiB. See
[the measured result and experiment](HL2_SHADOW_CAP_EXPERIMENT.md).

Also landed since the last revision: v19 texture-mip surface lock tracking
qualified ([surface locks](SURFACE_LOCK_QUALIFICATION.md)), a local capture
workbench over the runner APIs ([workbench](WORKBENCH.md)), the shared 128 MiB
shadow-budget ceiling documented with its boundary asserted, and resolution
independence in the DXR renderer — the whole expressible range up to 4096x4096 now
allocates inside an 8 GiB ceiling, where 1440p and 4K were previously refused
([DXR viewer](DXR_VIEWER.md)).

## Status by area

| Area | What works | Remaining gate |
|---|---|---|
| Reference title (Phase 0) | Repeatable in-repo fixtures on RX 9070 XT; HL2 gameplay observation with clean exit and proxy removal | Select and qualify an owned title; no commercial game is certified |
| D3D9 proxy/trace (Phases 1–2) | Transparent forwarding, D3D9Ex, reset/lifetime tests, bounded capture and inspectors | Real-title and broader device/display acceptance |
| Scene capture/replay (Phase 3) | Shader-aware selection on primitive count; **16 real HL2 material draws captured**; **23 vertex programs admitted position-only** (3 hand-written evaluators + 20 via the generic vs_2_0 interpreter); 72.1% of one in-game frame's triangles captured with the three hand-written evaluators (interpreter in-game coverage not yet measured); narrow fixed-function geometry/texture subset; exact fixture raster replay; stable asset IDs; glTF export | Shared shadow budget blocks 20 texture inputs; interpreted programs are position-only (materials refused); broader states/materials/animation; game-sized material comparison not yet run |
| Asset replacement (Phase 4) | Offline texture, mesh and material overrides with isolation tests | Live replacement and creator UI |
| Standalone DXR (Phase 5) | AMD hardware ray tracing, one-bounce diffuse GI, filtering/history, native presentation, **resolution-independent up to 4096x4096 and an internal render grid decoupled from the capture** | Full transport/scene coverage, filtered upscaling, performance and broader hardware qualification |
| Live runtime (Phase 6) | Shared-buffer transport, failure containment, frame admission and GPU buffer reuse foundations | Continuous game capture → renderer → game presentation, including reset/resize/fallback |
| FidelityFX (Phase 7) | Real RR dispatch/research; radiance-cache training/inference, guarded fixture composition and persistent session experiments | RR quality gates still fail; temporal upscaling, frame generation and full FSR integration remain pending |
| ROCm and broader APIs (Phases 8–9) | Architectural plan | Optional authoring worker; DX8/10+ and second-title work deferred |

## Current engineering focus

The material-capture budget question is **closed with a negative result**: a
larger CPU shadow cap does not admit the missing draws, so the blocker is the
pixel-shader family, not capacity. That family is now identified *and recovered*:
the inventory stores full program bytes, and the dominant rejected program is a
1912-byte `ps_2_x` (`dbca89cc…`, 189 draws) whose only behavioural difference from
the admitted program is that it derives fog from `length(t4.xyz - c10.xyz)` instead
of an interpolant. The contract, the evidence and the five implementation steps are
in [the recovered contract](MATERIAL_PS2X_CONTRACT.md). It is now implemented: two
programs admitted, a self-describing five-row payload, and a measured reconstruction
at 2.9e-7. That unlocked 189 of 2,734 inventoried draws — but 93.1% were refused by
the vertex program instead. That question (Q12) is now decided and implemented:
after the flex and skinned per-program admissions took the in-game captured share
to 72.1% of one frame's triangles, the [generic vs_2_0 interpreter](VS_INTERPRETER.md)
admitted the remaining 20 refused programs of the 2026-11-10 frame, position-only,
each cleared by its own GPU point oracle at maximum error 0. What remains on the
vertex side: material capture still refuses interpreted programs, programs outside
the pinned list each need their oracle run, and a fresh gameplay pass measuring the
interpreter's end-to-end coverage has not been run yet. Selection still uses
`any:3` to observe actual targets rather than assuming a configured resolution;
[game-sized material comparison](GAME_SIZED_MATERIAL_COMPARISON.md) describes what
the comparator supports.

Renderer work does not depend on that evidence; its last change remains the
2026-10-19 decoupling of the internal render grid from the captured extent.

The capture-version ladder is now a named enum with a
[machine-readable schema](schemas/capture-version.json) and a contract test that
keeps the C++ and Python descriptions in agreement, so adding a level — v20 now
declares the scene's units, scale, up-axis and handedness — no longer means
editing an unreadable ternary. See [the codebase map](../CODEBASE_MAP.md) for the
architecture, the debt register and the delivery plan.

Build/contract CI is in place. All 14 qualification tests that depend on private
game evidence now stay visible on clean checkouts as explicit CTest skips, with
missing paths and configuration guidance. A GPU-free contract verifies their
registration and missing/restored/invalid evidence behavior. See
[build and local-evidence instructions](BUILD.md). Private evidence retention and
the larger-cap gameplay comparison remain open.

Future compatibility tracks: [SM3/UE3, DX10 and legacy wrapper qualification](API_ENGINE_ROADMAP.md).
The [position-only scene-state prototype](POSITION_SCENE_STATE.md) separates
content reuse from explicit instance identity, but is not wired to live capture.

Later product milestones: [one coordinated capture session and workbench UI](UNIFIED_CAPTURE_UI_ROADMAP.md).
These do not replace the immediate material-capture gate.

Continuous standalone rendering with a persistent provider session and the D3D9
Present/Reset bridge remain product milestones for live relighting. Initial
baseline/API observation does not depend on their completion.

## Game and quality expectations

BioShock 2 original passed its default native baseline but crashed with requested
DX9 before proxy deployment. HL2 is the extraction target, not a certified
relighting title; its experimental graphics feature level was restored to 95.
DX8/10+ support is not implemented.

ROCm is an optional future authoring component; runtime ray tracing uses
D3D12/DXR. **Successful capture, cache or RR dispatch does not establish usable
game image quality or frame rate.** Current hardware evidence is from one RX 9070
XT; broader GPU and commercial-game acceptance remain open.

See [phase plan](../PHASE_PLAN.md), [compatibility ledger](COMPATIBILITY_LEDGER.md),
and [cache transport/session evidence](RADIANCE_CACHE_SHARED.md).
