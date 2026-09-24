# Project status — 2026-09-24

The project is a working capture/replay and standalone AMD ray-tracing prototype.
It is **not yet a playable Remix-style runtime for a commercial game**, and no
version is tagged. The immediate blocker is Phase 3 material evidence at game
size; the DXR renderer is at Phase 5 and the live runtime at Phase 6.

## What changed since the 2026-09-06 revision

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

**The remaining texture failure is now only the shared budget, not shader
support.** 20 x `texture_tracking_missing` at slot 1 for a 1024x512
`D3DFMT_A16B16G16R16` DYNAMIC DEFAULT sampler input (~4.5 MiB each) are refused at
`shadow_budget`. The dynamic-admission and 16-bit-float format gates both pass.
Separately, 15 x `unsupported_shader` remain outside the pinned-program allowlist
and 6 x `selection_primitive_minimum`. This is a budget-policy decision, tracked
as the first open question in [the codebase map](../CODEBASE_MAP.md).

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
| Scene capture/replay (Phase 3) | Shader-aware selection on primitive count; **16 real HL2 material draws captured**; narrow fixed-function geometry/texture subset; exact fixture raster replay; stable asset IDs; glTF export | Shared shadow budget blocks 20 texture inputs; broader states/materials/animation; game-sized material comparison not yet run |
| Asset replacement (Phase 4) | Offline texture, mesh and material overrides with isolation tests | Live replacement and creator UI |
| Standalone DXR (Phase 5) | AMD hardware ray tracing, one-bounce diffuse GI, filtering/history, native presentation, **resolution-independent up to 4096x4096** | Full transport/scene coverage, performance and broader hardware qualification |
| Live runtime (Phase 6) | Shared-buffer transport, failure containment, frame admission and GPU buffer reuse foundations | Continuous game capture → renderer → game presentation, including reset/resize/fallback |
| FidelityFX (Phase 7) | Real RR dispatch/research; radiance-cache training/inference, guarded fixture composition and persistent session experiments | RR quality gates still fail; temporal upscaling, frame generation and full FSR integration remain pending |
| ROCm and broader APIs (Phases 8–9) | Architectural plan | Optional authoring worker; DX8/10+ and second-title work deferred |

## Current engineering focus

The immediate priority is **closing the material-capture budget decision** and then
running the first game-sized material comparison. The v18 failure is instructive:
the capture machinery was working and the selection was wrong, so the next pass
should re-run at 2560x1440 rather than at the 5120x1440 the earlier attempt
assumed. See [game-sized material comparison](GAME_SIZED_MATERIAL_COMPARISON.md)
for what the comparator already supports.

The capture-version ladder is now a named enum with a
[machine-readable schema](schemas/capture-version.json) and a contract test that
keeps the C++ and Python descriptions in agreement, so adding v20 no longer means
editing an unreadable ternary. See [the codebase map](../CODEBASE_MAP.md) for the
architecture, the debt register and the delivery plan.

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
