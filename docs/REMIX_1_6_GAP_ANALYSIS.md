# RTX Remix 1.6 gap analysis

Status: **analysis**, 2026-10-26. Documentation only: no code, build, test or
format changes accompany this page.

This page compares the RTX Remix 1.6 release with this repository's current
state and extracts only the items that bear on a **D3D9 fixed-function capture
plus D3D12/DXR AMD runtime**. It is not a feature-parity plan and does not propose
copying Remix's architecture: Remix is an NVIDIA-only runtime with different
constraints, and several of its headline features have no AMD equivalent here.

## Provenance and citation rules

Every statement about Remix below is drawn from the single permitted source:

- `https://github.com/NVIDIAGameWorks/rtx-remix/releases/tag/remix-1.6.1`,
  release name "RTX Remix Release 1.6 Notes (October 23, 2026)", tag
  `remix-1.6.1`, published 2026-10-23T15:12:32Z.

Nothing else about Remix — not its shader code, not its cache implementation, not
its internal data layouts — is asserted. Where the release note is a one-line
summary and the underlying mechanism is unknown, the item says **(uncertain)**
and the recommendation is written so that it does not depend on the guess. Where
the note names a pull request (`PR-*` on `dxvk-remix`), only the note's own
description of that change is used.

Repository claims cite `file:line`. Repository claims describe the tree at the
commit this page was written against; they are not a promise about later
revisions.

## Scope

Assessed (seven items):

1. AMD default to the `TraceRay` path, versus our inline dispatch in `src/dxr`.
2. Sparse rendering with a compact GBuffer and sampling-rate controls, versus
   `--render-scale`.
3. NEE-cache sample aging, versus our radiance cache and temporal accumulation.
4. Per-material upscaler masks and selectable normal-map convention, versus our
   material manifest.
5. Headless host with MCP tool schemas over Streamable HTTP, as a model for
   exposing capture/replay tools.
6. Capture loading fixes (scene scale, up-axis), versus our capture format.
7. ComfyUI 2.0 workflows, versus our optional ROCm batch worker.

Explicitly out of scope, and **not** assessed here:

- **DLSS 5 / DLSS 3D-Guided Neural Rendering.** The release note files this under
  "DLSS 5 Integration"; there is no AMD path in this project for it and the
  roadmap defers neural denoising to "a later research track, not an MVP
  dependency" ([roadmap](../ROADMAP.md)). Item 4 therefore examines only the
  *material-data* consequence of the per-material control masks, not the
  rendering feature.
- **Multi Frame Generation (5×/6×).** The roadmap defers frame generation
  explicitly ([roadmap](../ROADMAP.md), [phase plan](../PHASE_PLAN.md), Phase 7).
- Also noted and deliberately not analysed, because they do not touch the capture
  or renderer path in this repository: Windows on ARM / ARM64EC artifacts, the
  NVIDIA 616.92 driver baseline, the Minecraft Fabric mod, OpenEXR texture and
  HDR skybox ingestion, Stage Manager edit-state filters and tag filters, USD hot
  reload, Aftermath crash capture, and the Thin Opaque subsurface retune.

## Effort and risk scales

Effort is for the *recommended action*, not for full parity:

| | Meaning |
|---|---|
| **S** | Under a day. A documentation change, a bounded field, a flag, or a test with no new subsystem. |
| **M** | Multi-day. One subsystem, or a cross-cutting change that needs new tests and an evidence entry. |
| **L** | Multi-week. A new renderer path, a new process/protocol boundary, or a change to a shipped data contract that needs migration. |

Risk is the risk of *doing the recommended action*, not of skipping it:

| | Meaning |
|---|---|
| **Low** | Contained and reversible; cannot change existing output or a shipped format's meaning. |
| **Medium** | Touches a versioned format, a quality path, or something a test currently asserts byte-exactly. |
| **High** | Changes the renderer's core dispatch or a published data contract without an obvious migration. |

---

## 1. AMD defaults to the `TraceRay` path

### What Remix 1.6 says

Under "Performance Optimizations → AMD Driver Improvements": *"Selected `TraceRay`
by default on AMD Windows drivers, improving performance by approximately 20% in
community measurements (from 53 to 63 FPS on driver 26.6.4, PR-146)."*

That is the whole claim. The note does not say what the previous default was, at
which shader stage the path is used, whether it is a runtime pipeline switch or a
build-time one, or whether the measurement generalises beyond that driver and
title **(uncertain)**.

### What we have today

Our renderer has **no `TraceRay` path at all**. Every ray in the project is an
inline `RayQuery`:

- Primary and shadow rays: `src/dxr/render.hlsl:115`, `:153`, `:165`, `:184`, `:222`.
- Radiance-cache path tracing: `src/dxr/rc_paths.hlsl:22`, `:43`.
- Ray-regeneration input preparation: `src/dxr/rr_inputs.hlsl:23`, `:41`.

The renderer is a compute-shader pipeline, not a ray-tracing pipeline. There is no
`DispatchRays`, no state object and no `RaytracingPipeline` anywhere in the tree;
the capability gate requires hardware DXR tier 1.1 and shader model 6.5
(`src/dxr/main.cpp:102-107`), the build compiles `render.hlsl` to compute shader
model 6.5 ([DXR viewer](DXR_VIEWER.md)), and the JSON report identifies itself as
`"renderer":"dxr-inline-1.1"` (`src/dxr/main.cpp:1032`).

This is a deliberate, documented choice — "the implementation uses Microsoft's
inline ray-query model" ([DXR viewer](DXR_VIEWER.md)) — but it has never been
measured against an RTPSO alternative on this hardware.

### First measurement (2026-10-27)

One RX 9070 XT, driver 32.0.32015.7029, x64 Release, `rrt_dxr --mode gi` at 1920x1080. The scenes are generated random triangle
soups (heavily overlapping, so a stress case for the acceleration structure, not a game scene), and the figure is GPU trace time,
best of three where repeated.

| Triangles | 1 sample | 4 samples | 16 samples | BVH build |
|---:|---:|---:|---:|---:|
| 1,000 | 1.0 ms | 4.1 ms | 16.3 ms | 0.2 ms |
| 20,000 | 2.0 ms | 8.1 ms | 32.4 ms | 0.4 ms |
| 100,000 | 9.4 ms | 39.5 ms | 151.5 ms | 2.0 ms |
| 400,000 | 48.3 ms | 168.9 ms | 698.1 ms | 8.4 ms |

Time is linear in samples. At 4 samples, 50% render scale costs 28-39% of the full-resolution time (1.2 ms against 4.1 ms at
1,000 triangles, 64 ms against 169 ms at 400,000), so the scale is sublinear.

The primary-visibility query uses `FORCE_NON_OPAQUE` so the shader can test the per-draw scissor. A scratch variant that forced
those two queries opaque produced identical pixels and was only 0-12% faster (for example 39.2 to 35.1 ms at 100,000 triangles and
4 samples; 42.9 against 43.5 ms at 400,000 and 1 sample). The shader round trip that is specific to the inline design is therefore not the
bottleneck. The cost is in traversal. This does not compare inline against a `TraceRay` pipeline, which still does not exist, so the
question stays open and the recommended action below is unchanged: no port without a profile that shows a shortfall on a game scene.

### Gap

Remix's note is evidence that, on AMD Windows drivers, *which* DXR path a renderer
uses is worth roughly 20% of frame rate in at least one community measurement. We
run exactly one path and have never measured the other. That is an unexamined
assumption, not a demonstrated defect: the note does not establish that inline
ray queries are the slower option, and a compute-shader inline trace is not
interchangeable with a pipeline `TraceRay` call.

### Recommended action

Do not port `TraceRay`. Record the hypothesis and make it cheap to test later:

1. Add a `ray_path` field to the `--probe`/report JSON that states `inline-1.1`
   explicitly, so any future comparison has an identity to cite. One string, no
   behaviour change.
2. Add a row to the Phase 7 profile plan (the "AMD quality pass" work in
   [phase plan](../PHASE_PLAN.md)) naming this as an open performance question
   with a named measurement, not an assumed result.
3. Only if our own profile shows the inline path is the shortfall on a target
   Radeon, scope a bounded RTPSO `TraceRay` variant behind a flag. That is the
   `L` case, and it should not start before the profile exists.

### Effort

**S** for steps 1–2. Step 3, if ever triggered, is **L** (a second pipeline, a
second shader entry point, and a parity test across both).

### Risk

**Low.** Reporting a string cannot change pixels. The risk of the *conditional*
step 3 is High — two dispatch paths means two sets of timings, two sets of
history/reset semantics, and a real chance of a silent divergence in temporal
state — which is why it stays gated on evidence.

---

## 2. Sparse rendering, compact GBuffer, sampling-rate controls

### What Remix 1.6 says

Under "Next-Gen Rendering → Sparse Rendering": *"Added uniform sparse rendering
with a compact GBuffer and DLSS Ray Reconstruction. Sampling-rate controls give
users a performance-versus-image-quality tradeoff, while compact resources reduce
memory requirements."*

Under "Performance Optimizations → Sparse Rendering": *"Reduced sparse-rendering
frame time by ~0.25 ms via resource and thread compaction."*

"Uniform sparse rendering", the GBuffer's layout, and how the sampling-rate
control is expressed (per tile, per material, per screen region) are all
unstated **(uncertain)**.

### What we have today

We have a **uniform global render-scale**, not sparse rendering.

- `--render-scale PERCENT` (1..100, default 100) renders on a smaller internal
  grid than the captured extent and upscales at presentation. Values are parsed
  strictly — non-numeric, missing, zero and out-of-range fail closed rather than
  clamp (`src/dxr/main.cpp:902-909`, and `:980` rejects it alongside the RR/RC
  evidence paths).
- The grid is derived with nearest-pixel rounding, clamped to at least one pixel
  and never above the captured extent, and the comment is explicit that this is "a
  reduction path, not supersampling" (`src/dxr/main.cpp:195-201`).
- Allocation, every per-pixel dispatch, camera ray generation, motion vectors,
  captured-scissor mapping, the display upscale, exports and the report all follow
  the render grid; the full table is in [DXR viewer](DXR_VIEWER.md). Scissor
  boundaries are mapped back into target space so clip edges do not move
  (`src/dxr/render.hlsl:40-43`).
- Per-pixel cost is a fixed 240 bytes (output 4, readback 4, history 16, signals
  88, previous/next 64+64), documented as a resolution-independent working set
  (`src/dxr/main.cpp:41-45`).
- Runtime records and diagnostic records are already separate: the shader retains
  "only consumed float32 values" and reconstructs diagnostics on demand
  (`src/dxr/render.hlsl:14-17`), which is the same intent as a compact GBuffer,
  applied to our own signal set rather than to a Remix-style GBuffer.

What we do **not** have: any per-region, per-material or per-draw sampling rate;
any tile or block classification; any compaction of thread groups to occupied
regions. The grid is uniform by construction.

### Gap

Two orthogonal levers are being conflated in the comparison. `--render-scale`
trades *spatial resolution* for time; sparse sampling trades *rays per pixel* for
time at full resolution. Our temporal accumulation assumes a stable full-grid
history keyed to render pixels ([DXR viewer](DXR_VIEWER.md), motion-vector row),
so a variable-rate path would change what "history" means, not just how much work
is issued.

The honest position: sparse rendering is not a gap we should close now. It is a
technique whose prerequisite — a compact, renderer-owned GBuffer — we have
partially, in a different form.

### Recommended action

Keep `--render-scale` as the shipping lever. Do not implement sparse rendering.
Instead, close the *documentation* gap so the next person does not re-derive it:

1. Record in [DXR viewer](DXR_VIEWER.md) that `--render-scale` is a global
   resolution scale, explicitly not a sampling-rate control, and that it is
   incompatible with the RR/RC evidence paths by design (`src/dxr/main.cpp:980`).
2. Note the prerequisite: any future per-region sampling rate must first define
   how motion vectors and history validity are expressed at differing rates, and
   must not break the exact-pixel `dxr_render_scale` assertions.

### Effort

**S** for the documentation. Full sparse rendering would be **L** (new signal
layout, new history semantics, new tests), and nothing in this release justifies
starting it before the Phase 6/7 gates.

### Risk

**Low** for the documentation. The rejected `L` path carries Medium–High risk: it
would touch the temporal rejection logic that currently has byte-exact test
coverage (`src/dxr/render.hlsl:260-314`).

---

## 3. NEE-cache sample aging

### What Remix 1.6 says

Under "Code & Community Contributions": *"PR-143: Restored NEE-cache sample aging
to prevent stale lighting from persisting. (Thanks @BinqAdams)"*

This is the entire description. "Sample aging", the cache's entry lifetime, and
the bug's trigger conditions are not described; the note says "restored", which
implies a regression against earlier behaviour **(uncertain)**. Nothing here says
whether aging is a decay, an eviction, a maximum age, or a per-entry timestamp.

### What we have today

Two separate mechanisms, neither of which has an aging rule.

**Analytical temporal accumulation** (`src/dxr/render.hlsl`):

- A running mean across samples for the current camera/settings state:
  `color=lerp(history[index].rgb,color,1.0/(sampleIndex+1))` (`:252`).
- A bounded history weight: `count=min(old.statistics.x+1,32.0)` (`:308`). The
  32-frame cap is the closest thing we have to aging — after 32 frames the history
  stops gaining influence, so a stale contribution is diluted but never expired.
- Rejection is by *reason code*, not by age: no temporal flag, no motion, no
  previous albedo, invalid projection, surface mismatch, plane error, and
  distance error each reset to `count=1` (`:271-288`).
- On camera motion the history is clipped to the 3×3 neighbourhood range of
  same-surface taps (`:295-307`), which bounds stale colour but does not age it.

**FidelityFX Radiance Cache** (research path, not the default renderer):

- The provider is a persistent online-trained cache, isolated in a supervised
  worker with pinned DLL hashes and a 32 MiB allocation ceiling
  ([radiance cache](RADIANCE_CACHE.md)).
- Training state persists across dispatches; an explicit `RESET` restores the
  baseline byte-for-byte, and the reset comparison is exact rather than
  tolerance-based ([radiance cache training](RADIANCE_CACHE_TRAINING.md)).
- Invalidation is **epoch-based and all-or-nothing**: any scene, camera, lighting,
  material or settings change requires a fresh epoch
  (`src/dxr/rc_admission.h:3-6`), one parent command per acknowledged epoch
  (`src/dxr/rc_epoch_protocol.h:4-8`), and a changed camera in the live prototype
  produces "a different artifact digest and a fresh supervised child/context"
  ([radiance cache live](RADIANCE_CACHE_LIVE.md)).

### Gap

We have two invalidation models and no aging model:

- The RC cache holds *all* training state until a full reset. A partially-changed
  scene cannot age out the stale part; it either resets everything or keeps
  everything. If Remix's fix addresses "stale lighting persisting", that is
  precisely the failure class our epoch model cannot express.
- The analytical temporal path has a hard 32-frame cap and a spatial clamp, which
  bounds but does not expire. There is no per-sample age in the exported signals
  or the report, so staleness is not observable.

This is a real design gap, but note the asymmetry: Remix's fix is a bug fix in a
cache that ships enabled; our RC path is disabled by default and makes no quality
claim (`rc_rendering` false throughout [radiance cache training](RADIANCE_CACHE_TRAINING.md)).
So the correct response is a *requirement*, not an emergency fix.

### Recommended action

Write the requirement before the cache is enabled, not after:

1. State an explicit aging policy for the RC path — either a maximum sample age
   with per-entry invalidation, or a documented argument that epoch-reset is
   sufficient because the cache is only admitted for a stable camera. Pick one;
   do not leave it implicit.
2. Add a **stale-lighting test** to the existing RC contract set: hold a light
   change, a material change and a camera cut, then assert the cache does not
   retain the old contribution past the declared policy. The harness already
   supports reset-exactness and identity-change assertions
   ([radiance cache live](RADIANCE_CACHE_LIVE.md)), so this is an extension, not a
   new fixture.
3. For the analytical path, expose the existing `count` and reason code in the
   signal export (they are already packed into `sample.w`,
   `src/dxr/render.hlsl:313`) so age is inspectable rather than inferred.

### Effort

**M.** One policy decision, one contract test, and one diagnostic field, each
bounded — but it touches the provider boundary and needs an evidence entry.

### Risk

**Medium.** The test must be added without relaxing the existing exact reset
comparisons, which are currently the strongest evidence in that track. A policy
that weakens reset exactness would be a regression dressed as a fix.

---

## 4. Per-material upscaler masks and normal-map convention

### What Remix 1.6 says

Two separate notes, both under the Toolkit:

- *"DLSS 3D-Guided Neural Rendering: Added global controls (Model A/B/C, highlight
  and volumetric tuning) to Render Settings and Preferences, plus per-material
  control masks."*
- *"Normal Map Conventions: Choose preferred normal map conventions during both
  model and material ingestion."*

The first is part of the DLSS 5 integration and is out of scope as a *feature*
(see [Scope](#scope)). What is in scope is the data-model consequence: a material
record in Remix now carries per-material mask data and an explicit normal-map
convention, both authored at ingestion time. The mask channel count, encoding and
semantics are unstated **(uncertain)**.

### What we have today

Our material model is a fixed-function patch plus a small PBR sidecar. It has
neither masks nor normal maps.

- **Manifest v1** (`docs/MOD_WORKFLOW.md:69-115`) supports three replacement
  kinds — `texture`, `mesh`, `material` — keyed on original capture IDs with
  priority/conflict rules. The material entry is a patch over captured D3D9 state
  with exactly six fields: `min_filter`, `mag_filter`, `address_u`, `address_v`,
  `double_sided`, `alpha_mode`, `alpha_cutoff` (`docs/MOD_WORKFLOW.md:154-165`).
  The document states plainly that this "is a fixed-function patch, not a PBR or
  arbitrary-shader material."
- **PBR sidecar** `RRTMAT1` carries a 32-byte record per material: base colour,
  roughness, emission, metallic (`src/dxr/material_inputs.h:2-5`, `:18`). No
  auxiliary channels, no masks, no normal map.
- **Normals are geometric only.** The renderer derives a face normal from the
  triangle's vertex positions and flips it toward the view
  (`src/dxr/render.hlsl:105-106`). There is no tangent basis, no normal texture,
  no convention selector. The viewer's forward work lists "smooth normals,
  material maps and colour management" as unstarted ([DXR viewer](DXR_VIEWER.md)).
- **Capture has no normal input.** The supported subset is one 2D A8R8G8B8 or
  X8R8G8B8 texture at mip zero with `XYZ | DIFFUSE | TEX1` FVF; "lit/normal
  formats" are listed as not qualified ([scene capture](SCENE_CAPTURE.md)).
- The one place we already handle a normal *convention* is the RR input export,
  which packs octahedral world normals with an explicit fold-sign rule
  ([RR inputs](RR_INPUTS.md)).

### Gap

Two missing fields, one of which is cheap now and expensive later.

1. **No convention selector.** The moment a normal map is ingested — from a mod
   author, from a DCC export, or from a future upscaler's guide set — the project
   will have to decide between D3D (Y-down), OpenGL (Y-up), and tangent-space
   handedness, per asset or per project. Remix made this an ingestion-time choice;
   we currently have nowhere to record one.
2. **No reserved auxiliary channel.** Our material record is 32 bytes and our
   manifest schema is strict about unknown fields (`docs/MOD_WORKFLOW.md:92-94`).
   Adding a mask later means a schema version bump with no forward slot.

Note the asymmetry that matters for planning: Remix needed per-material masks
*because* it has a neural upscaler consuming them. We have no such consumer, so
building masks now would be speculative. But a *convention field* is not
speculative — it is required by any normal-map path at all, including the
"smooth normals, material maps" work already on our own forward list.

### Recommended action

Split the two, and only do the cheap half:

1. **Do now:** reserve an explicit `normal_convention` field in the mod schema
   (values such as `d3d_y_down`, `gl_y_up`, with an explicit "unspecified" that
   fails closed on any asset that needs it), and document the default for
   captured D3D9 data. This is a schema and documentation change; it commits to
   nothing about when normal maps arrive.
2. **Do now, cheaply:** record in the same schema document that per-material
   auxiliary channels (masks, guides) are a reserved future kind, so the next
   version bump has a stated slot rather than an argument.
3. **Do not now:** implement masks, a mask authoring path, or a normal-map
   ingestion pipeline. Both are gated on a consumer that does not exist.

### Effort

**S** for steps 1–2 (schema field, default, documentation, and a contract-test
case for the new value). A real normal-map path would be **M** (capture subset,
tangent basis, shader, and an oracle comparison).

### Risk

**Low** for the reserved field — it is additive and can fail closed. The `M` path
carries Medium risk: it changes the capture subset and the replay oracle's pixel
expectations, which are currently asserted exactly.

---

## 5. Headless host with MCP tool schemas

### What Remix 1.6 says

- *"Expand Agent Automation: Deploy headless Toolkit instances with standardized
  MCP tool schemas."*
- Breaking change: *"The MCP server now defaults to Streamable HTTP at
  `http://127.0.0.1:18014/mcp` (previously SSE at `http://127.0.0.1:8000/sse`).
  Existing MCP client configurations must be updated to connect to the new
  endpoint."*
- *"Added a headless Toolkit host and a packaged modding-agent skill, with
  documented setup using public prebuilt development packages. Self-contained MCP
  tool schemas also expand compatibility with strict clients such as llama.cpp."*

The note does not enumerate the tools, their schemas, or what the headless host
can do without a viewport **(uncertain)**.

### What we have today

No MCP, no agent surface, no HTTP server. A repository-wide search for `MCP`,
`headless host` and `Streamable` in the documentation returns nothing.

What we do have is a **CLI tool surface with machine-readable reports**, which is
the same problem solved differently:

- `rrt_dxr --probe` emits a JSON capability report with no scene required
  ([DXR viewer](DXR_VIEWER.md)), and the full render report is a single JSON line
  including `pixel_sha256_bgra` and per-stage GPU timings
  (`src/dxr/main.cpp:1032`).
- `rrt_replay --inspect` validates a scene and reports asset IDs and rejection
  reasons as JSON without creating a GPU device
  ([scene capture](SCENE_CAPTURE.md)).
- The Python workers (`tools/rc_worker.py`, `rc_sequence_worker.py`,
  `rc_live_worker.py`) already enforce strict JSON envelopes, binary hash pinning,
  bounded output and timeouts, and they are registered as contracts.
- `tools/game_pass.py` and `tools/workbench.py` drive capture runs, and the
  runner explicitly does not inject into other processes
  ([phase 6 transport decision](PHASE6_TRANSPORT_DECISION.md), open unknown 4).

So the gap is not "we cannot be automated". It is "our automation surface is a
set of shell commands with ad-hoc argument shapes, and each new tool invents its
own JSON".

### Gap

Remix's change is worth taking as a **shape**, not as a stack:

- Self-contained tool schemas — the note's own justification is compatibility
  with strict clients. That is a schema-quality argument, and it applies to us
  regardless of transport.
- A headless host distinct from the interactive application. We already have
  this: `rrt_dxr` runs headless by default and only opens a window with `--show`
  or `--interactive`.
- The transport (Streamable HTTP at a fixed localhost port) is the part we should
  **not** copy. A local HTTP listener inside or beside a process that is attached
  to a game is a new attack surface, and this project's existing security posture
  is explicitly "fault containment, not a sandbox"
  ([phase 6 transport decision](PHASE6_TRANSPORT_DECISION.md)).

### Recommended action

Define a **tool schema document** over the existing CLI, with stdio transport, and
no server:

1. One schema file per tool group (capture, inspect, replay, render, mod), each
   declaring inputs, outputs, exit codes and the JSON envelope, with the envelope
   already used by the workers as the base.
2. Keep the boundary at "spawn a process, read its JSON, read its exit code". No
   socket, no port, no ambient discovery. This is consistent with the inherited,
   allowlisted-handle pattern already established for the RC transport.
3. Only if an external agent client actually needs it, add a thin adapter that
   exposes those same schemas over a transport — as a separate, optional
   executable, never linked into the proxy or the renderer.

### Effort

**M.** The schemas themselves are small; the work is agreeing one envelope across
`rrt_dxr`, `rrt_replay` and the Python tools, and adding contract tests that the
schemas and the actual output agree.

### Risk

**Low** for the stdio schemas — no new listener, no new privilege. Adding a
transport later is Medium: a localhost port reachable by any local process is a
different threat model from an inherited pipe, and would need its own
documentation of what it does and does not protect.

---

## 6. Capture loading fixes: scene scale and up-axis

### What Remix 1.6 says

Under "Notable Toolkit Fixes": *"Older Captures: Captures taken prior to moving
Remix config into the `remix` namespace load with correct scene scale and up-axis,
resolving particle sizing and orientation issues."*

Also relevant, same section: *"Open Project with Capture"*, *"faster capture
discovery"*, and *"Capture Cameras & Lights: Loading captures clears stale
game-camera overrides; orthographic cameras properly frame capture meshes."*

The note does not say how scale and up-axis are recorded, only that older captures
lacked the information needed to load them correctly **(uncertain)**.

### What we have today

Our capture format records **no scale, no units and no up-axis**, by design.

The v1 header is 44 bytes: `RRTSCN1\0`, then nine `uint32` — version, frame,
width, height, clear ARGB, attempted draws, successful draws, cleared flag,
accepted draw count, rejection count ([scene capture](SCENE_CAPTURE.md)). The
in-memory equivalent carries `frame`, `width`, `height`, `clearColor`, `attempted`,
`cleared` and the draw/rejection lists (`src/scene/scene.h:61-67`), with
`Version=1` (`src/scene/scene.h:10`).

Coordinate handling is entirely implicit and delegated downstream:

- Geometry is stored in **captured D3D9 object space** — the mesh replacement
  format says so explicitly ("in captured D3D9 object space, not glTF's converted
  coordinate convention", `docs/MOD_WORKFLOW.md:144-148`).
- The glTF exporter "converts handedness by reflecting Z and reversing triangle
  winding", and keeps the original matrices in `extras`
  ([scene capture](SCENE_CAPTURE.md)).
- The DXR renderer consumes world/view/projection directly and never re-derives a
  scene transform (`src/dxr/main.cpp`, `Admit` requires one shared camera).
- The only explicit convention record anywhere is the RR input export's octahedral
  normal fold rule ([RR inputs](RR_INPUTS.md)).

The project does have the right *mechanism* to fix this safely: formats are
versioned from day one ([phase plan](../PHASE_PLAN.md)), the version ladder is a
named enum with a machine-readable schema (`docs/schemas/capture-version.json`),
and a contract test keeps the C++ and Python descriptions in agreement
([project status](PROJECT_STATUS.md)).

### Gap

We are structurally exposed to exactly the class of bug Remix just fixed: a
consumer that has to *guess* a coordinate convention from the data. Today the
guess is safe because there is one producer (our own proxy) and one consumer (our
own renderer), both D3D9-native. That safety disappears the moment a second
producer exists — a converted DX8 capture, a hand-authored scene, an imported
glTF, or a capture from a different title with different world units.

The absence is currently *documented* rather than *encoded*, which is the weaker
of the two.

### Recommended action

Add the metadata now, while it is free:

1. Define a **v2 header extension** carrying scene units (or an explicit
   unitless flag), up-axis, handedness, and the convention of the stored
   matrices. Extend the version ladder and the C++/Python contract test in the
   same change.
2. Make v1 readers keep their current interpretation explicitly, so the v1 path
   is a *stated* default rather than an unstated one — the same "fails closed"
   posture the manifest already uses for unknown versions.
3. Have the glTF exporter read the record instead of assuming, and reject a
   mismatch rather than silently reflecting Z.

This is the cheapest item in this document and the one with the clearest
precedent.

### Effort

**S.** Four fields, one version bump, one contract-test update, one exporter
change. No renderer change, because the renderer already consumes matrices
directly.

### Risk

**Low.** Additive to a versioned format with an existing schema/contract
mechanism. The main risk is procedural: a v2 writer must not silently emit v1
files for new captures, which the ladder's contract test is designed to catch.

---

## 7. ComfyUI 2.0 workflows versus the ROCm batch worker

### What Remix 1.6 says

- *"ComfyUI Integration Version 2.0: Replaced legacy AI Tools with a
  ComfyUI-based workflow for texture and mesh outputs. Workflow names,
  descriptions, and type filters make workflows easier to discover, while
  per-output application choices give modders more control over replacing or
  appending generated assets."*
- *"Streamline Asset Generation: Leverage ComfyUI 2.0 for customizable AI texture
  and mesh workflows."*

The note does not describe the node graph, the model dependencies, or whether the
workflows run locally or remotely **(uncertain)**.

### What we have today

Phase 8 is **not implemented**. The status table lists ROCm as "Architectural
plan" ([project status](PROJECT_STATUS.md)), and the roadmap's own rule is that
the worker must "demonstrably improve an authoring task; if not, keep it optional
or remove it" ([roadmap](../ROADMAP.md)).

What exists:

- A defined, unimplemented protocol: "an isolated `hip_worker` protocol: input
  files, deterministic job manifest, output files, no runtime dependency"
  ([phase plan](../PHASE_PLAN.md), Phase 8).
- `tools/bench_rocm.py` — but this is a **PyTorch attention benchmark**, not an
  asset pipeline. It sets MIOpen workspace limits, runs SDPA backend selection and
  isolated base/heavy op timing, and is covered by
  `tests/test_bench_rocm_attention.py`. It measures the platform, not a creator
  task.
- `tools/sanity_rocm.py` and `tools/verify_rocm_env.py` for environment checks.
- The runtime constraint that governs the design: ROCm is "an optional
  developer/authoring accelerator. Players must never need the HIP SDK to use a
  released mod" ([phase plan](../PHASE_PLAN.md)).

There is no texture-generation or mesh-generation path at all, in ROCm or on CPU.

### Gap

Remix 1.6's asset generation is a **node-graph authoring environment with a
discovery and application layer** — names, descriptions, type filters, and a
per-output decision to replace or append. We have neither the generation nor the
application layer; our equivalent of "apply" is the offline mod manifest, which
already handles replacement deterministically with priority and conflict rules
(`docs/MOD_WORKFLOW.md:96-110`).

So the comparison is asymmetric. Remix replaced a legacy AI tool with a graph
editor. We have not yet built the first task.

### Gap-relevant observation

The one part of the ComfyUI change that maps onto our design is the **per-output
application choice**: replace versus append, decided per generated asset. Our
manifest already encodes replacement only — there is no "append" or "additive"
concept, and unmatched targets fail by default
(`docs/MOD_WORKFLOW.md:107-108`). If generated assets ever arrive, that gap will
be the first friction point, not the generation itself.

### Recommended action

Do not build a node graph, and do not adopt ComfyUI as a dependency. Keep the
Phase 8 protocol as the boundary, and make it the thing an external graph would
call:

1. Specify the `hip_worker` job manifest concretely (inputs, outputs, model
   identity, determinism claim, cancellation), as Phase 8 already requires.
2. Note explicitly that a ComfyUI-style graph, if wanted, is an **external client**
   of that protocol — not a linked dependency and never a runtime requirement.
3. When generated assets do arrive, extend the manifest with an explicit
   `replace`/`append` intent per entry rather than overloading the current
   replacement-only semantics.

Phase 8's own gate still applies and should not be pre-empted: no worker ships
until it beats a CPU baseline on a named authoring task.

### Effort

**S** for steps 1–2 (protocol specification and a decision record). The worker
itself is **M**, and is gated on a measured benefit rather than on this release.

### Risk

**Low** for the specification. Adopting a graph runtime would be High: a large
Python/ML dependency tree inside an authoring tool that must remain optional, with
its own GPU memory competition against the capture and renderer processes.

---

## Summary

| # | Item | Our state | Recommended action | Effort | Risk |
|---|---|---|---|---|---|
| 1 | `TraceRay` default on AMD | Inline `RayQuery` only, unmeasured | Report the path; gate an RTPSO variant on our own profile | S | Low |
| 2 | Sparse rendering, sampling-rate controls | Uniform `--render-scale`; no sparse path | Document the distinction and the prerequisite; do not implement | S | Low |
| 3 | NEE-cache sample aging | Epoch reset (RC) and a 32-frame cap (temporal); no aging rule | Declare a staleness policy and add a stale-lighting test | M | Medium |
| 4 | Per-material masks, normal convention | Six-field fixed-function patch, 32-byte PBR sidecar, geometric normals | Reserve `normal_convention` and an auxiliary slot; no masks yet | S | Low |
| 5 | Headless host, MCP schemas | Rich CLI + JSON reports, no schema, no transport | One tool-schema document over stdio; no listener | M | Low |
| 6 | Capture scale / up-axis | v1 header has no units, scale or up-axis | v2 header extension + contract test + exporter | S | Low |
| 7 | ComfyUI 2.0 | Phase 8 unimplemented; only a benchmark | Specify the job protocol; graph is an external client | S | Low |

## Ranked shortlist

Ranked by value per unit of effort, with the constraint that each must be
completable without unblocking anything else.

### 1. Capture metadata: units, scale, up-axis, handedness (item 6)

**Effort S, risk Low.** This is the highest-value item in the document because it
is the only one where a competitor's release notes describe a bug we are
*structurally* exposed to. We are currently safe only because there is exactly one
producer and one consumer; every plausible next step — a second title, a converted
DX8 capture, a glTF import, a generated asset — breaks that. The fix is four
fields and a version bump, and the mechanism (named version ladder, machine-readable
schema, C++/Python contract test) already exists and is cheap to extend. Doing it
after a second producer exists means writing a migration instead of a field.

### 2. Normal-map convention and reserved auxiliary slot (item 4)

**Effort S, risk Low.** Same class of decision, one layer up. The manifest is
strict about unknown fields, so every convention or channel we do not reserve now
becomes a schema break later. `normal_convention` is required by work already on
our own forward list ("smooth normals, material maps" in
[DXR viewer](DXR_VIEWER.md)), independent of anything Remix ships. The mask half
should be reserved and *not* implemented — there is no consumer, and building one
speculatively would violate the roadmap's own rule for optional accelerators.

### 3. Cache staleness policy and stale-lighting test (item 3)

**Effort M, risk Medium.** The only shortlisted item that addresses a *quality
failure mode* rather than a format decision. Our RC path invalidates by full epoch
reset and holds training state indefinitely otherwise, which cannot express
"partially stale". Remix's fix is evidence that this matters in a shipping cache.
Our advantage is timing: the RC path is disabled by default and makes no quality
claim, so the policy can be written and tested *before* anything depends on it.
This ranks third rather than first because it is the only item that touches a
provider boundary and must not weaken the exact reset comparisons that are
currently the track's strongest evidence.

### Deferred, with reasons

| Item | Why not now |
|---|---|
| 1 — `TraceRay` | No evidence our inline path is the slow one. Building a second dispatch path to chase a 20% figure from another renderer's community measurement would be copying a result, not testing a hypothesis. The `S` half (reporting the path) is included in the shortlist's context but is not worth ranking. |
| 2 — Sparse rendering | **L**, and it invalidates the temporal history semantics that currently have byte-exact coverage. The prerequisite — a per-region motion/history model — does not exist. |
| 5 — Tool schemas | **M**, and the value lands after Phase 6 gives the tools something worth automating. A schema over a CLI that is still moving would be rewritten. |
| 7 — ComfyUI / ROCm worker | Blocked by Phase 8's own gate: no worker ships until it beats a CPU baseline on a named task. The specification step is cheap and can ride along with item 6's format work. |
