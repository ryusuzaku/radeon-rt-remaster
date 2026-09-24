# Radeon Remix — proposed direction

## The honest framing

This can be a **Remix-inspired legacy-game remastering runtime for AMD-capable PCs**. It should not promise universal game support or describe ROCm as the renderer. The viable first target is a narrow, offline/single-player **32-bit Direct3D 9 fixed-function** game, where legacy draw calls still contain enough geometry, textures, transforms, and fixed-function material/light state to reconstruct a scene.

The product loop is:

```text
DX9 game → local d3d9.dll proxy → scene recorder → reconstructed scene
                                                  ├─ capture/export → mod author tools
                                                  └─ D3D12/DXR renderer → present
                                                                  ↘ FSR/upscaler
```

ROCm belongs beside that loop, not in its critical rendering path:

```text
Captured textures / meshes → ROCm/HIP optional batch tools → PBR assets / metadata
```

## Architecture choices

| Layer | Recommended choice | Why |
|---|---|---|
| Initial game boundary | Per-game `d3d9.dll` proxy; 32-bit | The smallest faithful analogue to Remix’s proven interception point. |
| Canonical scene | Engine-owned C++ data model; export glTF first, add USD only if its authoring benefits justify the dependency | Keeps capture, runtime, and tooling decoupled from a heavyweight platform. |
| Real-time renderer | D3D12 + DXR + HLSL/DXC | Windows-native ray tracing API with AMD driver support; no ROCm installation required for players. |
| Denoising / reconstruction | Start with temporal accumulation, motion vectors where recoverable, and a modest spatial denoiser | Neural denoising is a later research track, not an MVP dependency. |
| Upscaling | FidelityFX SDK integration after a stable native-resolution render | AMD’s open FSR path supports D3D12/Vulkan, but needs motion/depth/UI discipline. |
| Asset identity | Stable hashes of normalized geometry/material/texture inputs plus game/object context | Enables deterministic mesh/material replacement and avoids filename dependence. |
| Offline enhancement | HIP/ROCm command-line worker behind an optional feature flag | Useful for texture transforms, embeddings, or future ML; limits Windows support risk. |
| Tool UI | A simple desktop/web inspector that reads captures and edits a declarative mod manifest | Prove authoring workflow before committing to a large DCC integration. |

## MVP: `Radeon Remix Capture & Relight`

**Do build**

- A DX9 proxy that forwards every call to the system runtime while recording a selected fixed-function subset: device lifecycle, transforms, render states, vertex/index buffers, textures, draw calls, and frame boundaries.
- A replay viewer that loads a captured frame and renders it rasterized first. This is the crucial correctness oracle.
- A DXR path-traced viewer for static opaque meshes with basic PBR conversion, one directional light, and a sky/environment light.
- A replacement manifest mapping asset IDs to mesh, texture, and material overrides.
- Capture inspection: draw-call list, extracted meshes/textures, frame statistics, and mismatch diagnostics.

**Explicitly defer**

- DX8, shader-heavy DX9, OpenGL, D3D10/11/12, Vulkan, and arbitrary engine support.
- Dynamic/skinned meshes, particles, water, decals, portals, translucency, UI, post-processing, and multiplayer/anti-cheat use.
- Frame generation, neural texture upscaling, full scene USD authoring, and game-wide auto-lighting.

The first success criterion is not "looks like a remaster." It is: **a captured known-good scene replays pixel-close in the raster viewer, then renders as a stable static path-traced scene with one material replacement.**

## Milestones and gates

| Milestone | Output | Gate |
|---|---|---|
| 0. Reference title and harness | One legal/offline DX9 fixed-function test title; proxy load test | `d3d9.dll` loads, forwards, and exits cleanly. |
| 1. Observability | Structured frame trace and inspector | Counts/ordering of draws, textures, and presents are repeatable. |
| 2. Capture | Geometry, states, texture snapshots, frame bundle | Raster replay matches a set of golden screenshots within an agreed tolerance. |
| 3. Replacement | Canonical IDs and mod manifest | Replacing one texture/mesh affects only the intended draws. |
| 4. DXR relight | Static opaque DXR viewer | Stable camera, acceleration structures, PBR material, basic denoise. |
| 5. Runtime composition | Rendered frame presented through the proxy path | Repeated play sessions remain stable; no leaks/device-loss regressions. |
| 6. AMD quality pass | Radeon profiling and scaling | GPU timing/memory budgets documented on two Radeon generations. |
| 7. Tooling/ROCm experiment | Offline HIP worker prototype | Demonstrably improves an authoring task; if not, keep it optional or remove it. |

## First repository shape

```text
src/
  proxy_d3d9/       # 32-bit forwarding DLL + recorder hooks
  trace/            # versioned trace schema, serialization, capture writer
  scene/            # canonical geometry/material/texture model + asset IDs
  replay/           # raster replay correctness viewer
  renderer_dxr/     # D3D12/DXR renderer and presentation
  mod_runtime/      # manifest loading and replacement resolution
  tools/inspector/  # trace/capture inspection UI or CLI
  tools/hip_worker/ # optional offline ROCm jobs, never required by runtime
tests/
  golden/           # legal captures, expected images, trace invariants
docs/
  compatibility.md
  trace-format.md
  mod-format.md
```

## Risk register

| Risk | Mitigation / decision rule |
|---|---|
| A game’s commands lack semantic scene information | Treat compatibility as per-title; provide capture diagnostics, not a universal-support promise. |
| 32-bit proxy cannot host modern renderer resources conveniently | Keep capture/proxy thin; communicate via a versioned IPC/shared-memory boundary to a 64-bit renderer only after in-process replay proves data fidelity. |
| Ray tracing performance is not viable on target GPUs | Begin with 720p/one sample per pixel/static scenes; offer raster fallback and set a strict VRAM budget. |
| HIP SDK support differs across Windows GPUs | Ship no HIP dependency in the runtime; make the offline worker an opt-in developer tool with capability detection. |
| D3D9 driver quirks and device loss | Build forwarding/device-reset tests before renderer work. |
| Anti-cheat / game integrity | Support only user-authorized offline/single-player games; do not attempt to bypass protection. |
| Licensing/content redistribution | Never ship extracted game content; distribute manifests and user-created replacement assets only. |

## Decisions to make before code

1. Choose the first reference title (offline, legally testable, D3D9 fixed-function, 32-bit) and a second title only after Milestone 2.
2. Choose a runtime mode: start with **capture then external replay**, or accept a larger initial risk with live replacement. Capture-first is recommended.
3. Define target Radeon generations and a minimum VRAM budget. The answer determines whether DXR is required or a compute/raster preview is the first renderer.
4. Decide whether the goal is a community modding platform or a proof-of-concept for one game. The platform path should only begin after two titles pass capture fidelity.

## Immediate next task

Create Milestone 0: a 32-bit D3D9 forwarding proxy with logging, a tiny D3D9 test application, and an automated smoke test that verifies device creation, a clear/present loop, and teardown.
