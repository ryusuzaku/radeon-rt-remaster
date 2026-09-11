# Project status — 2026-09-06

The project is a working capture/replay and standalone AMD ray-tracing prototype. It is not yet a playable Remix-style runtime for a commercial game. The main implementation is in Phase 5, with experimental FidelityFX work from Phase 7 and infrastructure for Phase 6.

| Area | What works | Remaining gate |
|---|---|---|
| Reference title (Phase 0) | Repeatable in-repo fixtures on RX 9070 XT | Select and qualify an owned game; no commercial title is certified |
| D3D9 proxy/trace (Phases 1–2) | Transparent harness forwarding, D3D9Ex, reset/lifetime tests, bounded capture and inspectors | Real-title and broader device/display acceptance |
| Scene capture/replay (Phase 3) | Narrow fixed-function geometry/texture subset, exact fixture raster replay, stable asset IDs, glTF export | Broader states/materials/animation and real-game scene extraction |
| Asset replacement (Phase 4) | Offline texture, mesh and material overrides with isolation tests | Live replacement and creator UI |
| Standalone DXR (Phase 5) | AMD hardware ray tracing, one-bounce diffuse GI, basic material/light controls, filtering/history and native presentation | Full transport/scene coverage, performance and broader hardware qualification |
| Live runtime (Phase 6) | Shared-buffer transport, failure containment, frame admission and GPU buffer reuse foundations | Continuous game capture → renderer → game presentation, including reset/resize/fallback |
| FidelityFX (Phase 7) | Real RR dispatch/research; real radiance-cache training/inference, guarded fixture composition and persistent session experiments | RR quality gates still fail; temporal upscaling, frame generation and full FSR integration remain pending |
| ROCm and broader APIs (Phases 8–9) | Architectural plan | Optional authoring worker; DX8/10+ and second-title work deferred |

## Current engineering focus

Future compatibility tracks: [SM3/UE3, DX10 and legacy wrapper qualification](API_ENGINE_ROADMAP.md).
The new [position-only scene-state prototype](POSITION_SCENE_STATE.md) separates
content reuse from explicit instance identity, but is not wired to live capture.

Later product milestones: [one coordinated capture session and workbench UI](UNIFIED_CAPTURE_UI_ROADMAP.md), requested after individual captures work. These do not replace the immediate initialized HL2 geometry/constant capture gate.

Radiance-cache buffers can be reused with explicit state restoration and fenced ownership. Applied/diagnostic outputs match the unpooled baseline through repeats, camera changes and failure recovery. The parent-commanded provider protocol now consumes coalesced renderer-owned camera requests in a bounded six-epoch test, retaining one context, refreshing GPU inputs and verifying exact reset/continuation without per-epoch renderer-buffer allocations. Connecting that session to per-epoch candidate application/native presentation and real UI input is next.

HL2 native/proxy/disabled runs passed user visual review and clean exits. Triggered
gameplay tracing works through bin/d3d9.dll, but every sampled draw used a vertex
shader; lower-feature selection did not expose the fixed-function subset. The
immediate priority is [shader-aware extraction](SHADER_GEOMETRY.md). A narrow
single-draw fixture now captures through the proxy and replays exactly in fresh
processes, with state-block/reset/resource evidence guards. Actual HL2 shader
families and geometry remain unsupported. All temporary game proxies were removed.

Continuous standalone rendering with a persistent provider session and the D3D9 Present/Reset bridge remain product milestones for live relighting. Initial baseline/API observation does not depend on their completion or every optional FidelityFX feature.

## Game and quality expectations

BioShock 2 original passed its default native baseline but crashed with requested
DX9 before proxy deployment. HL2 is the chosen extraction target, not a certified
relighting title. Its experimental graphics feature level was restored to 95.
DX8/10+ support is not implemented.

ROCm is an optional future authoring component; runtime ray tracing uses D3D12/DXR. Successful cache or RR dispatch does not establish usable game image quality or frame rate. Current hardware evidence is from one RX 9070 XT; broader GPU and commercial-game acceptance remain open.

See [phase plan](../PHASE_PLAN.md), [compatibility ledger](COMPATIBILITY_LEDGER.md), and [cache transport/session evidence](RADIANCE_CACHE_SHARED.md).
