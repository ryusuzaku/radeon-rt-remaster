# Reference-title selection protocol

Do not select a commercial game by reputation alone. The first game must be a controlled **compatibility target**, not a promise of broad support.

## Required properties

- User-owned, offline/single-player, legally obtained Windows game.
- 32-bit executable using native Direct3D 9.0 or early Direct3D 9.0 fixed-function rendering; no API translation layer in the first test.
- Published approximately 2000–2005, with graphics settings that can reduce shader effects.
- A stable, repeatable scene available within a few minutes of launch.
- No active anti-cheat, multiplayer requirement, DRM bypass, or protected executable modification.
- A modest, mostly static environment with opaque geometry and conventional texture assets.

## Disqualifiers for the first target

- DX9.0c title with a shader-dominant renderer.
- Primarily OpenGL, Direct3D 8, or newer API; those may be later research targets via translation but complicate the first diagnosis.
- Heavy screen-space effects, deferred rendering, portals, streaming-world dependence, or mandatory complex character animation in the chosen scene.
- An unsupported game version, mod, or distribution that cannot be reproduced by every developer.

## Selection test sequence

1. Run the title untouched and archive baseline screenshots, settings, frame time, and version hash.
2. Install only the proxy in a reversible per-game test directory.
3. Verify clean launch, input, alt-tab, shutdown, and repeated device creation/reset behavior.
4. Compare proxy-on/off screenshots and run logs. Any behavioral difference is a Phase 1 bug, not a game workaround.
5. Once trace capture exists, measure per-frame draw count, fixed-function state use, shader creation/use, dynamic-buffer churn, and render-target changes.
6. Accept only if a selected scene has a high share of stable, extractable opaque geometry; record unsupported effects separately.

## Evidence to record

| Field | Why it matters |
|---|---|
| Executable/version and graphics API evidence | Makes results reproducible. |
| Title ownership/distribution notes | Prevents accidental redistribution or unsupported setup advice. |
| Reference scene and deterministic route | Enables image and trace regression tests. |
| Device lifecycle and proxy-on/off result | Proves the proxy is transparent before capture. |
| Fixed-function vs shader draw ratio | Predicts extractability. |
| Dynamic draw/texture count | Sets a realistic first capture scope. |

## Candidate status

No external game is approved yet. The in-repo smoke sample remains the Phase 1 reference.

- Need for Speed Carbon: **negative research candidate only**. Community reports identify shader-related capture problems; do not use it for the first acceptance target.
- BioShock 2 (original 2010 release): **secondary observability candidate**. It is a 32-bit title with DX9.0c/DX10 modes, and can be forced to DX9 mode, but its modified Unreal Engine renderer is shader-heavy and the game's 2010 vintage puts it outside the initial fixed-function profile. Use it only after `Present`/reset and trace diagnostics work. The Remastered release is DX11 and is out of scope for the D3D9 proxy.
- A title is nominated only after a developer can supply a lawful local installation and it passes the selection sequence above.
