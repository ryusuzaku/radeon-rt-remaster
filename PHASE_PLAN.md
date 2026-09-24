# Phase Plan — Radeon RT Remaster (working title)

[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) is the **canonical status file** and is updated in place — read it for the current state rather than this page. Harness completion is not commercial-game acceptance. The phase follow-ups below retain development history and their original dates, so they describe the state at the time of writing rather than today.

## Product statement

Build a user-authorized, offline/single-player modding runtime for selected legacy Windows games. It captures a compatible game scene, lets creators replace assets/materials/lights, and renders the reconstructed scene with AMD-capable hardware ray tracing through D3D12/DXR.

ROCm 10 is an **optional developer/authoring accelerator**. Players must never need the HIP SDK to use a released mod.

## Fixed rules for every phase

- Ship one known-compatible title before adding a second API or title.
- Preserve the original game executable and assets; never redistribute them.
- Test only offline/single-player titles without anti-cheat or integrity-bypass work.
- Engineering stages advance through automated harness gates. Real-game support claims additionally require the per-title acceptance gates; that qualification is tracked separately in the compatibility ledger.
- Keep trace, capture, and mod formats versioned from day one.

## Phase 0 — Charter, reference title, and development harness

**Goal:** Create a reproducible, legal target environment.

**Work**

- Select one 32-bit, offline Direct3D 9 fixed-function title with a stable test scene.
- Use `docs/REFERENCE_TITLE.md` as the admission protocol; do not approve a game based only on a compatibility-list claim.
- Record game version, launch steps, settings, representative scenes, and redistribution restrictions.
- Establish baseline screenshots, frametimes, VRAM use, and driver versions.
- Create a tiny in-repo D3D9 test application with clear/present, textured geometry, device reset, and teardown cases.
- Define the Radeon test matrix: one minimum target GPU, one newer target GPU, supported Windows/driver versions, and a VRAM floor.

**Deliverables:** compatibility charter; test matrix; legal test assets; D3D9 sample; golden baseline capture set.

**Exit gate:** both the game and sample run repeatably on every test machine; baseline data is committed/documented.

## Phase 1 — Transparent D3D9 forwarding proxy

**Implementation status (2026-09-02):** Complete against the synthetic harness, including full device forwarding, resource identity, D3D9Ex, and exact baseline render checks. Commercial-title/fullscreen/second-GPU acceptance is pending.

**Goal:** Load beside the game without changing its behavior.

**Work**

- Implement a 32-bit `d3d9.dll` that loads the system D3D9 DLL and forwards every required export/interface call.
- Add structured, opt-in diagnostics: DLL load, adapter/device creation, reset, present, and teardown.
- Build a proxy-disable escape hatch and crash-safe logging.
- Exercise D3D9Ex/device-loss/reset paths in the sample before relying on game testing.

**Deliverables:** forwarding DLL, proxy smoke tests, log schema, installation/uninstall instructions.

**Exit gate:** original game output, inputs, settings persistence, and stability match the no-proxy baseline over repeated launches.

## Phase 2 — Frame observability and trace format

**Implementation status (2026-09-02):** Complete for versioned observation metadata, selected state values, bounded frame selection, and the validating CLI inspector. Resource payload snapshots and scene replay remain Phase 3.

**Goal:** Make the legacy render stream inspectable before attempting to change it.

**Work**

- Design a compact versioned trace: resources, state changes, transforms, draw calls, frame boundaries, and provenance.
- Track vertex/index buffers, textures, shader declarations, render states, and render-target changes.
- Implement per-frame recording with bounded memory and selective capture triggers.
- Build a CLI inspector with draw counts, texture/mesh inventory, state timeline, and capture-size reports.

**Deliverables:** trace specification, writer/reader, inspector CLI, representative captures.

**Exit gate:** two captures of the same controlled scene have stable ordering/IDs and explain all major visible draws.

## Phase 3 — Canonical scene extraction and raster replay

**Implementation status (2026-09-02):** First end-to-end slice implemented: lifetime-safe CPU payload shadows, selected-frame unlit triangle extraction, stable SHA-256 asset IDs, validated scene format, independent raster replay and glTF export. Four fixture frames replay with zero pixel error in D3D9/9Ex Debug and Release. See `docs/SCENE_CAPTURE.md` for the exact subset. Full reference-game acceptance and broader depth/light/material/format extraction are still pending.

**Goal:** Prove that captured data is correct enough to rebuild the scene.

**Work**

- Normalize captured geometry, transforms, textures, materials, camera state, and lights into an engine-owned scene format.
- Produce stable mesh/material/texture IDs based on normalized inputs and context.
- Implement an external raster replay viewer before any ray tracing.
- Add image-diff testing against golden screenshots and per-draw diagnostics for mismatch investigation.
- Export a simple interchange representation (glTF first); keep USD optional.

**Deliverables:** capture bundle format, scene extractor, raster viewer, golden image-diff harness, glTF exporter.

**Exit gate:** a selected static scene replays pixel-close at a predefined tolerance; remaining mismatches are classified.

## Phase 4 — Mod format and asset replacement

**Implementation status:** First offline slice implemented: strict versioned manifests, editable PNG/mesh extraction, content-ID texture/mesh/fixed-function material replacements, priority/conflict rules and new replayable scene output. GPU tests verify intended draw changes and unchanged unrelated regions across repeated fixture captures; unchanged static mesh IDs survive Reset. Live game replacement, lights/PBR, GUI authoring and commercial-title acceptance remain open. See `docs/MOD_WORKFLOW.md`.

**Goal:** Make the capture useful to a creator without changing the renderer model yet.

**Work**

- Define a declarative mod manifest mapping stable IDs to texture, mesh, material, and light overrides.
- Implement deterministic priority and conflict rules; never infer replacement from filenames alone.
- Add a minimal inspector/editor workflow: preview asset, choose replacement, save manifest, validate dependencies.
- Test one texture replacement and one static mesh/material replacement.

**Deliverables:** mod schema, manifest validator, replacement resolver, sample mod.

**Exit gate:** replacements affect exactly the intended objects across repeated captures and game sessions.

## Phase 5 — D3D12/DXR relight viewer

**Implementation status:** DXR 1.1 inline-ray-query viewer implemented: capability probe, bounded persistent scene upload, reusable BLAS/TLAS and pipeline, albedo/normal/direct-light modes, progressive one-bounce diffuse GI, raw accumulation, keyboard navigation and GPU timestamps. Explicit signals, float export/inspection, spatial filtering and opt-in camera-reprojected temporal reuse include surface/disocclusion rejection, bounded history, luminance moments and camera/light/reset handling. Compact float32 buffers and chunked diagnostics fit the full-HD synthetic fixture under unchanged budgets. Native D3D12 swapchain presentation reads GPU output directly; a fence-gated allocator/list/constants ring now enables bounded asynchronous submission without mandatory per-sample native readback. Explicit snapshots, exports, resize and teardown drain safely; GDI/headless and verified window paths remain available. GPU tests cover colour transport, convergence, motion, filter isolation, revealed-ground rejection, moments, resource reuse, window controls and early-close parity. x64 renderer-only presets keep the game proxy x86; legacy raster replay remains the oracle/fallback. Full path tracing, PBR, animated-object/advanced denoising, measured display-latency pacing, real-title support and second-GPU/desktop/performance acceptance remain pending. See `docs/DXR_VIEWER.md`.

**Goal:** Render one extracted static scene with AMD hardware ray tracing.

**Presentation refinement:** native viewing now uses a DXGI waitable swapchain
with maximum frame latency one and message-responsive admission before rendering.
The first interactive sample is deferred until admission; resize retains handle
ownership and the creation flag. Explicit unpaced diagnostics remain available.
Hidden-window parity/wake/lifecycle tests do not establish input-to-scanout latency
or qualify commercial-game presentation.

**Material/light refinement (2026-09-03):** optional stable-material-ID sidecars
now provide base tint, bounded roughness/metalness, emission, GGX direct lighting
and diffuse-only one-bounce transport. Light colour/intensity/ambient are explicit
inputs with history invalidation checks. Existing captures and default shading
remain unchanged. This is not full PBR conversion: literal-colour capture data,
flat normals, absent specular indirect transport and incomplete reconstruction
guides remain constraints. See `docs/MATERIAL_INPUTS.md`. Next: stronger filtering,
material/normal guides and colour-management work before FidelityFX evaluation.

**Denoiser investigation (2026-09-03):** three custom-filter candidates failed
the improvement gate. The user selected deeper AMD RR research. An isolated
x64 SDK probe now enumerates RR 1.2.0 on the RX 9070 XT and queries per-resolution
memory; it performs no context creation or dispatch. Next: bounded 128x96 context
admission, fresh indirect-diffuse separation and matched linear-depth/motion/normal
textures, then actual RR dispatch and quality acceptance. Full-HD integration
needs a revised memory layout, not a silent budget increase. The analytical
filter remains the baseline. See `docs/RAY_REGENERATION.md`.

**RR context follow-up:** the isolated bounded harness now creates/destroys three
128x96 contexts in Debug/Release, tracking 20 MiB peak and zero leftover allocation
bytes. Post-context SDK memory reporting is invalid with both custom and default
allocators, and injected heap-allocation failure crashes the child instead of
cleanly failing. Context mechanics are verified, not full SDK acceptance; no RR
dispatch or game/runtime integration has been performed. Keep isolation and
explicit accounting while resolving these failures and preparing input guides.

**RR issue containment:** the optional supervised boundary now passes in Debug
and Release. It pins DLL hashes, requires exact known reporting anomalies with
strict callback accounting, bounds child output/deadlines, contains the real SDK
allocation crash, and verifies recovery in a fresh process. Raw SDK diagnostics
remain failed; no binary fix or RR rendering is claimed. Next: fresh diffuse and
matched guides, followed by isolated dispatch and GPU lifetime/quality tests.

**RR input preparation:** a separate 128x96 GPU pass now exports fresh diffuse
radiance/hit distance, direct/emission, matched linear-light albedo, octahedral
normal/roughness, signed view Z and UV/depth motion. It retains legacy shaders
and pixels, adds bounded buffers only on request, and has an independent CPU
oracle. Typed-texture packing inside the worker and actual SDK dispatch are the
next gate; this diagnostic is not RR rendering. See `docs/RR_INPUTS.md`.

**RR first dispatch follow-up:** bounded typed textures and a real reset-only
128x96 indirect-diffuse SDK dispatch now pass execution/containment tests in
Debug and Release. All tracked allocations are released; raw SDK reporting
still needs pinned workarounds. The exact-zero lighting oracle fails slightly,
so quality is not accepted and the default renderer is unchanged. Next: bounded
temporal sequence/history tests and high-sample quality comparisons, including
the brightness bias. See `docs/RR_DISPATCH.md`.

**RR stationary history follow-up:** a checksummed 2..8-frame offline sequence
now reuses one SDK context and the same bounded typed textures. Temporal influence,
repeatability and lit-to-dark reset isolation are verified without increasing
tracked GPU allocation. The zero-light bias and pinned reporting workarounds remain;
this is not quality acceptance. Next is renderer-owned sequence capture with
complete scene/settings identity and camera continuity, then motion/disocclusion
and high-sample quality tests. See `docs/RR_SEQUENCE.md`.

**RR recording follow-up:** renderer-owned 2..8-frame capture now binds the
loaded scene, materials, preparation shader, canonical settings and per-frame
camera/reset continuity. Stationary exports remain byte-identical; translated
and reset frames have CPU-oracle validation. The new recording format is kept
separate from stationary worker admission. Its explicit recorded SDK mode is
described below; high-sample/disocclusion quality remains open. See
`docs/RR_RECORDING.md`; zero-light bias and SDK reporting workarounds remain open.

**RR recorded dispatch:** native admission precedes GPU/SDK loading; managed
execution verifies scene/material/shader identities and actual camera motion.
Continuous segments retain SDK history. Strict moving-reset equivalence exposed
seven differing pixels, so recorded cuts/resets now destroy and recreate the
context sequentially, without increasing live memory caps. The old stationary
worker is unchanged. Tests cover resets/cuts, visibility-change execution and
failure recovery; no high-sample or ghosting quality is accepted. See
`docs/RR_RECORDED_DISPATCH.md`.

**RR matched quality reference:** a bounded independent float64 CPU tracer now
provides two Monte Carlo batches at exact recorded primary hits. A four-frame
perspective fixture measures lower RR spatial, revealed-region and temporal
residual error than packed noisy input; reference variance and all failure
evidence remain explicit. General quality is still not qualified: zero-light
bias persists. The opt-in textured/PBR reference and matched CPU fallback now
expose substantial RR spatial regressions, despite close CPU/GPU estimator
agreement. Colour/albedo/signal-convention ablations and longer ghosting tests
remain open. See `docs/RR_QUALITY.md` and `docs/RR_SURFACE_QUALITY.md`.
No renderer or SDK implementation changed. A new analytic ambient-plane
reproducer confirms spatial contrast loss without PBR, occlusion, motion or
sampling noise. Equivalent vertex/texture colour and input RNG controls match
exactly; contrast remains suppressed after eight stationary frames. The paired
linear/square-root worker encoding experiment is now implemented, with verified
flags/hashes, tagged nondefault output and unchanged linear results; neither
encoding resolves contrast loss. Read-only live-context queries now expose all
six scalar defaults with repeated before/after snapshots and raw code/byte
validation. A separate opt-in single-key preset experiment now records per-context
configure evidence and tags configured output; default reapplication preserves
frame bytes. Lower stability bias improves later-frame analytic contrast but
does not meet raw/fallback quality gates. A bounded multi-seed textured/PBR
motion comparison now tests those presets with paired temporal/disocclusion
metrics and source-bound shared references. Further qualification, then separate depth/distance scale and resolution investigations
under explicit budgets. See `docs/RR_DEFAULT_SETTINGS.md` and
`docs/RR_COLOUR_RESPONSE.md`; the reproducer does not establish an SDK-internal
cause or a fix. Encoding details: `docs/RR_ALBEDO_ENCODING.md`.
Setting experiments: `docs/RR_FILTER_SETTINGS.md`.
Multi-seed comparison: `docs/RR_MULTI_SEED_SETTINGS.md`.
Longer history/reset evidence: `docs/RR_LONG_HISTORIES.md`.
Coordinate-scale evidence: `docs/RR_COORDINATE_SCALE.md`.

**Work**

- Build a D3D12 renderer with adapter feature checks and a raster fallback.
- Add BLAS/TLAS construction, static opaque geometry, PBR material conversion, environment/directional lighting, and camera controls.
- Start at a conservative resolution/sample budget; add temporal accumulation and a simple spatial denoiser.
- Instrument GPU time, VRAM, acceleration-structure build time, and shader compilation.

**Deliverables:** DXR viewer, renderer capability report, performance/VRAM budget, comparison captures.

**Exit gate:** the chosen scene produces a stable, visually plausible relit image on both Radeon test GPUs without device removal or unbounded memory growth.

### Deferred Phase 5 extension — radiance caching

- Evaluate **FSR Radiance Caching** only after the path tracer emits stable, normalized position, normal, view direction, albedo, roughness, training radiance, and query buffers. It is a DX12 technical preview with online training; integrate it behind a capability/configuration flag and retain the uncached tracer as the correctness baseline.
- Evaluate **Brixelizer GI** as an alternative/fallback GI route once the extractor can supply stable static/dynamic geometry and a G-buffer. It uses sparse distance fields and a temporal radiance/irradiance cache, rather than hardware-DXR path-tracer samples.
- Do not make either technique mandatory in the first released runtime. Both require temporal invalidation rules for camera cuts, asset replacement, dynamic lights, and scene reloads.

## Phase 6 — Runtime composition and presentation

**Goal:** Present the reconstructed DXR frame through the running game path.

**Work**

- Decide and implement one transport model: in-process shared renderer first, or a thin 32-bit proxy with a 64-bit renderer process and versioned IPC/shared-memory transport.
- Synchronize capture, rendering, and presentation; handle resize, alt-tab, reset, and clean shutdown.
- Preserve original raster presentation as an immediate fallback.
- Add a simple in-game status overlay and a per-title config file.

**Deliverables:** live runtime prototype, fallback mode, diagnostics bundle, stress test script.

**Exit gate:** a full game session in the reference title runs repeatedly with stable presentation, recoverable fallback, and documented frametime/VRAM metrics.

## Phase 7 — FidelityFX and AMD quality pass

**Goal:** Make the result usable rather than merely demonstrable.

**Work**

- Integrate temporal FSR upscaling only after native-resolution output is correct; supply depth, motion, exposure, reactive/transparency masks, and UI composition data deliberately. Use FSR 2/3 as the broad fallback; use ML FSR Upscaling 4 through capability selection on supported Radeon hardware.
- Evaluate FSR Ray Regeneration after the DXR renderer exports correctly defined ray-traced signals. It is a strong denoising option, but currently requires RX 9000-series-or-newer Radeon hardware, Windows 11, DX12, and Shader Model 6.6; retain an analytical denoiser elsewhere.
- Add Frame Generation only after stable live presentation and UI separation. It requires strict frame IDs, motion/depth inputs, swapchain control, pacing, and a UI composition callback; provide it as an opt-in enhancement, never a correctness dependency.
- Profile on target Radeon GPUs with AMD tooling; eliminate major CPU stalls, VRAM spikes, and shader compilation hitches.
- Establish performance tiers and config presets; retain a native-resolution and raster fallback.
- Build compatibility diagnostics explaining unsupported content rather than silently rendering it incorrectly.

**Deliverables:** FSR path, profiler captures, settings presets, performance guide, compatibility report.

**Exit gate:** published quality/performance targets pass on the two-GPU matrix and every fallback path is verified.

## Phase 8 — ROCm 10 authoring worker

**Goal:** Use ROCm only where it produces a measurable creator benefit.

**Work**

- Define an isolated `hip_worker` protocol: input files, deterministic job manifest, output files, no runtime dependency.
- Prototype one task with a clear CPU baseline: texture metrics/classification, mip processing, mesh clustering, image embedding, or a denoiser experiment.
- Implement GPU/driver capability detection, CPU fallback, job cancellation, and reproducibility tests.
- Measure end-to-end creator time, not kernel time alone.

**Deliverables:** optional ROCm 10 worker, benchmark report, CPU fallback, installation guidance.

**Exit gate:** the worker materially improves one authoring task on supported hardware; otherwise it remains experimental or is removed.

## Phase 9 — Second title and DX10/11 research track

**Goal:** Validate whether this is a platform or a one-title runtime.

**Work**

- Pass Phases 1–4 on a second compatible DX9 title with minimal bespoke rules.
- Add Direct3D 8 only after native-DX9 capture is proven, through an explicit D3D8-to-D3D9 translation layer and a separate regression matrix. It is a plausible path, but must not obscure whether a capture defect originates in the game, translator, or runtime.
- Separately create a read-only DX10/11 inspector: resources, shader metadata, draws, render targets, and frame graph evidence.
- Do **not** commit to DX10+ relighting until a target game’s world geometry, camera, UI, and material semantics can be reliably distinguished.
- Build per-title adapters only when the capture evidence justifies them.

**Deliverables:** second-title report; DX10/11 observability prototype; platform-go/no-go decision.

**Exit gate:** two DX9 titles reach raster replay fidelity. DX10/11 advances only with a scoped target title and a written extraction plan.

## Decision checkpoints

| After phase | Decide |
|---|---|
| 3 | Is capture fidelity sufficient to justify a renderer? |
| 5 | Is DXR quality/performance viable on target Radeons? |
| 6 | Is live runtime composition stable enough to productize? |
| 8 | Does ROCm add more value than maintenance cost? |
| 9 | Is the architecture genuinely reusable across titles/APIs? |

## First implementation sprint

Implement only Phase 0 and the thin vertical slice of Phase 1:

1. Set the reference-title compatibility charter and GPU matrix.
2. Create the tiny 32-bit D3D9 sample.
3. Build a forwarding `d3d9.dll` that logs `Direct3DCreate9`, device creation, `Present`, reset, and shutdown.
4. Automate proxy-on/proxy-off smoke runs and compare baseline screenshots.

No capture format, DXR renderer, FSR, or ROCm worker should be started until this proxy is behaviorally transparent.
