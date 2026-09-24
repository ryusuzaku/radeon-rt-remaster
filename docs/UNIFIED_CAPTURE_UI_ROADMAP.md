# Unified capture and workbench UI roadmap

Texture upscaling, reversible asset replacements, semantic material authoring and
their acceptance gates are planned in
[TEXTURE_ENHANCEMENT_ROADMAP.md](TEXTURE_ENHANCEMENT_ROADMAP.md).

Requested by the user on 2026-09-07. These are later product milestones, not a
replacement for the current HL2 initialized-input capture work.

## 1. Finish and qualify individual capture contracts

First capture and validate real vertex/index data, shader constants, transforms,
textures/material inputs and relevant frame/device state. Retain explicit known
state, resource generations, reset/state-block handling and unsupported-input
rejection. The current HL2 position evaluator passes synthetic GPU comparison;
real matching draw input capture and independent position-only GPU replay now
work for the pinned HL2 program. Broader geometry/material contracts remain next.

Future API/engine tracks are recorded in [API_ENGINE_ROADMAP.md](API_ENGINE_ROADMAP.md):
SM3/UE3, separate DX10/BioShock profiles, DX8-to-9 and earlier DirectX wrappers.

## 2. One coordinated capture session

Replace repeated diagnostic launches with one instrumented launch and one capture
action collecting all supported evidence into a coherent session bundle.

- Track initialization/resource changes from launch; a later trigger selects the
  desired frame/window without pretending earlier unobserved state is known.
- Give trace, shaders/layouts, geometry, constants, textures and frame metadata
  shared session/device/frame/draw identities and a coordinated selection window.
- Deduplicate shader and resource content, keep versioned references for changes,
  and preserve exact input provenance for replay and analysis.
- Apply a shared bounded memory/I/O budget with per-stream limits and explicit
  complete, partial, unsupported and failed outcomes. Never silently drop required
  inputs and call the result complete.
- Run validation and analysis on the same bundle offline, without another game
  launch merely to obtain a different evidence category.
- Keep narrow diagnostic modes for debugging, but make unified capture the normal
  workflow once its contracts pass. One capture covers observed supported content,
  not unseen levels, arbitrary shaders or every asset in the installation.

Acceptance: a single owned-game session yields correlated inputs sufficient for
the supported extraction/replay contract; reset and resource updates stay coherent;
budget exhaustion is reported; independent reconstruction matches the chosen gate.

## 3. Capture and authoring workbench UI

Build a UI over the tested runner/session APIs rather than duplicating safety or
capture logic. Choose UI technology later, after the backend contract stabilizes.
Started 2026-09-11 with a standard-library local page over `tools/game_pass.py`
covering prepare, run, trigger, inspect and cleanup; see
[WORKBENCH.md](WORKBENCH.md). The preview, authoring and export items below remain
unbuilt.

- Game/profile selection and checks for architecture, proxy conflicts and known
  compatibility limitations.
- Launch, arm, capture, progress, completion and safe cleanup controls. Clearly
  distinguish an ordinary running game from an instrumented, capture-ready session.
- Bundle browser with shader/layout coverage, missing inputs and rejection reasons.
- Geometry/material preview, selection and replacement workflow as those backend
  capabilities become supported.
- Replay/comparison and export controls with validation results and provenance.
- Later expose renderer/FidelityFX options only with their actual readiness and
  quality status visible; experimental dispatch is not a passed quality gate.

Acceptance: the user can perform the supported capture → inspect → edit → validate
workflow without shell commands, with recoverable installation changes and clear
failure/unsupported-state reporting. No requirement for an in-game overlay initially.
