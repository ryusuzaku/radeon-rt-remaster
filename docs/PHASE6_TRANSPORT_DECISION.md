# Phase 6 transport decision

Status: **option B adopted for implementation 2026-10-27; the decision stays
proposed until the exit gate below holds.** The original page of 2026-10-23 was
documentation only. Stages 1 and 2 of the test plan are now written: the protocol
contract, transport parity on fixtures through a test host, and an opt-in client
inside the proxy for the one-shot scene capture, with the raster-baseline
comparison (see [Transport protocol](TRANSPORT_PROTOCOL.md)). Continuous capture
and presentation are not implemented. Stages 3 to 6 are not started.

[Phase 6](../PHASE_PLAN.md#phase-6--runtime-composition-and-presentation) asks for
one transport model before live composition starts: an in-process shared renderer,
or a thin 32-bit proxy with a 64-bit renderer process and versioned
IPC/shared-memory transport. This page compares the two against what the repository
has already documented and measured, and recommends one. Every constraint names the
document it comes from. Where no document establishes something, it is listed under
[open unknowns](#open-unknowns-common-to-both-options) rather than assumed.

## The two options

**(A) In-process shared renderer.** The x86 `d3d9.dll` proxy hosts the D3D12/DXR
renderer inside the 32-bit game process. Capture, rendering and presentation share
one address space; no cross-process protocol is needed for the core loop.

**(B) Thin 32-bit proxy plus 64-bit renderer process.** The x86 proxy keeps
forwarding, bounded capture and the raster fallback. A separate x64 renderer process
owns the D3D12 device, scene, acceleration structures and denoiser/cache providers.
They communicate through a versioned protocol carrying fixed-width IDs, with bulk
data in shared GPU resources (or shared memory where a CPU path is unavoidable) and
fences for ownership.

## What the repository already establishes

- The documented architecture already assumes the split. The codebase map describes
  a 32-bit proxy and "a separate 64-bit D3D12/DXR renderer", with two deliberately
  separate presets because "the proxy must be 32-bit to load into the game while the
  renderer wants 64-bit address space" ([codebase map](../CODEBASE_MAP.md)). The
  architecture note says to "keep the small legacy client and large 64-bit renderer
  separated for memory headroom and failure isolation"
  ([advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md)).
- That note also says this is an architecture choice, "not a blanket claim that
  Direct3D12 cannot be used by any 32-bit process"
  ([advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md)). The x86 presets
  do build and test `rrt_dxr`, but "x86 address space and DXGI's pointer-sized memory
  fields make that a compatibility test path, not the recommended renderer
  architecture" ([DXR viewer](DXR_VIEWER.md)). Option A is therefore technically
  open, not ruled out by the API.
- The scene format is pointer-free and passes between x86 capture and x64 rendering
  without conversion ([DXR viewer](DXR_VIEWER.md)).
- A cross-process D3D12 transport already exists for the radiance-cache research
  path: shared default-heap buffers and a shared fence, explicit handle allowlists,
  job-contained children, adapter-LUID verification, a fence-value command protocol,
  bounded waits, crash/timeout fallback and a latest-wins frame-admission mailbox
  ([cross-process shared resources](RADIANCE_CACHE_SHARED.md)). It runs between two
  x64 processes and is not connected to D3D9.
- Project status lists the Phase 6 foundations as "shared-buffer transport, failure
  containment, frame admission and GPU buffer reuse", with the remaining gate being
  "continuous game capture → renderer → game presentation, including
  reset/resize/fallback" ([project status](PROJECT_STATUS.md)).
- The early risk register made the 64-bit boundary conditional: use it "only after
  in-process replay proves data fidelity" ([roadmap](../ROADMAP.md)). Fixture-level
  replay fidelity exists; game-sized material evidence is still the current blocker
  ([project status](PROJECT_STATUS.md)).

## Constraint comparison

| Constraint | (A) In-process | (B) Proxy + x64 renderer | Source |
|---|---|---|---|
| Address space | Renderer, capture shadows and the game share one 32-bit space. The same GPU reports 3.00 GiB dedicated memory to the 32-bit renderer and 15.81 GiB to the x64 one, a clamp from the address space and not the hardware. Capture's CPU shadow ceiling is already 128 MiB inside that space (256 MiB opt-in), and the measured HL2 peak reached it. | Renderer gets the full x64 space; the game process carries only proxy and capture costs. | [codebase map](../CODEBASE_MAP.md), [shadow-cap experiment](HL2_SHADOW_CAP_EXPERIMENT.md), [advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md) |
| Renderer working set | Full-HD fixture rendering requests 497,682,288 bytes of GPU buffers under an 8 GiB flat ceiling. That is requested GPU accounting, not CPU address use, but upload heaps and readback staging are CPU-visible and would share the game's space. Not measured in-process. | Same renderer, unchanged; already qualified as x64. | [DXR viewer](DXR_VIEWER.md), [codebase map](../CODEBASE_MAP.md) |
| SDK bitness | The repo integrates FSR Ray Regeneration and Radiance Caching only as optional x64 targets. These docs do not evaluate 32-bit availability. | Matches the existing x64-only SDK targets. | [Ray Regeneration](RAY_REGENERATION.md), [radiance cache](RADIANCE_CACHE.md), [codebase map](../CODEBASE_MAP.md) |
| Provider fault behaviour | Both providers crash their host process on allocation failure (RR: invalid `CreatePlacedResource` and exception; RC: access violation). In-process, that host is the game. In practice the providers would still need a separate x64 worker, so A does not avoid IPC once Phase 7 features arrive. | Already the documented containment model: kill/reap the job, fall back, recover in a fresh process. | [Ray Regeneration](RAY_REGENERATION.md), [radiance cache](RADIANCE_CACHE.md), [radiance cache live](RADIANCE_CACHE_LIVE.md) |
| Crash isolation | A renderer fault, device-removal handling bug or leak terminates or destabilises the game. Phase 6 requires a "recoverable fallback". | A renderer crash or hang leaves the game process running; the proxy can revert to raster. Process isolation "cannot guarantee recovery from a GPU-driver failure" and is "not a hostile-code security sandbox". | [phase plan](../PHASE_PLAN.md), [RR recorded dispatch](RR_RECORDED_DISPATCH.md), [Ray Regeneration](RAY_REGENERATION.md) |
| Driver / adapter | One process, one adapter choice; no cross-process sharing rules. | Shared D3D12 resources need the same adapter; the existing transport verifies the exact adapter LUID and uses `D3D12_FENCE_FLAG_SHARED` (same-adapter), not cross-adapter sharing. Second-GPU acceptance is still pending from Phase 1. | [cross-process shared resources](RADIANCE_CACHE_SHARED.md), [phase plan](../PHASE_PLAN.md) |
| Latency | No process hop. Capture-to-render handoff is a function call. | Adds a fence handoff per frame. Shared GPU resources move zero CPU payload bytes between processes. No transport-only latency has been measured: the recorded 0.33–0.35 s (shared) versus about 1.0 s (CPU pipe) figures include provider work and process startup and are described as upper-bound prototype costs, not targets. | [cross-process shared resources](RADIANCE_CACHE_SHARED.md), [radiance cache live](RADIANCE_CACHE_LIVE.md) |
| Frame pacing | The game's `Present` cadence and the renderer share a thread/process; one pacing authority is easy to state. | Two cadences (game `Present`, renderer completion) need explicit admission. The renderer's standalone waitable swapchain (maximum frame latency one) does not establish input-to-scanout latency, and "the standalone swapchain does not imply that game capture and display are already bridged". Phase 7 Frame Generation will need strict frame IDs, swapchain control and pacing. | [DXR viewer](DXR_VIEWER.md), [phase plan](../PHASE_PLAN.md) |
| Synchronization | Intra-process fences and locks; D3D9 and D3D12 devices still need explicit ordering. | Requires "fixed-width IDs/offsets (never cross-process pointers), resource generations, bounded queues, synchronization/fence ownership, back-pressure and reset/crash recovery". The radiance-cache session already implements strict fence ownership, out-of-sequence rejection, bounded non-blocking polls and stale-result rejection. | [advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md), [cross-process shared resources](RADIANCE_CACHE_SHARED.md) |
| Security / integrity | No new cross-process surface. Larger code footprint inside the game. | New surface: shared handles and a protocol. The existing pattern uses inherited, explicitly allowlisted handles (no ambient discovery), pre-resume job assignment and kill-on-close. Scene-file checks are "not authentication or a security boundary". Offline/single-player titles without anti-cheat only, either way. | [cross-process shared resources](RADIANCE_CACHE_SHARED.md), [scene capture](SCENE_CAPTURE.md), [phase plan](../PHASE_PLAN.md), [reference title](REFERENCE_TITLE.md) |
| Build / test complexity | One x86 build. But the renderer's recommended and best-qualified configuration is x64, and the SDK targets are x64-only, so A would promote the "compatibility test path" to production. | Two presets already exist and are already required. Cross-arch tests need both builds on one GPU machine; renderer memory changes can only be validated on the target GPU with a full x64 build. | [codebase map](../CODEBASE_MAP.md), [DXR viewer](DXR_VIEWER.md), [build](BUILD.md) |
| Format versioning | Internal structs; versioning optional. | The protocol is a new versioned format, consistent with the rule to "keep trace, capture, and mod formats versioned from day one" and the existing capture-version schema/contract-test pattern. | [phase plan](../PHASE_PLAN.md), [project status](PROJECT_STATUS.md) |

## Open unknowns common to both options

These are not settled by any repository document, and the recommendation does not
depend on resolving them in a particular way. Each is a work item, not a fact.

1. **Return path into the game's presentation.** No document records how a D3D12
   frame reaches the game's D3D9 swapchain. The DXR viewer presents through its own
   swapchain ([DXR viewer](DXR_VIEWER.md)). Option A faces the same D3D9↔D3D12 step
   inside one process. Phase 6 must choose and qualify a mechanism. A per-frame CPU
   readback into a D3D9 surface is the obvious baseline to measure first; any
   GPU-sharing route needs its own evidence.
2. **Continuous capture.** Current capture writes one selected frame and stops
   ([scene capture](SCENE_CAPTURE.md)). Continuous capture with resource generations
   ([advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md)) is a
   prerequisite for both options.
3. **Device removal across APIs.** No document establishes whether a D3D12
   device-removal in the renderer affects the game's D3D9 device on the same
   adapter. Isolation does not cover driver failure
   ([RR recorded dispatch](RR_RECORDED_DISPATCH.md)).
4. **Who launches the renderer.** The existing pattern has an x64 parent spawning
   an x64 child ([cross-process shared resources](RADIANCE_CACHE_SHARED.md)). Under
   B, either the in-game proxy spawns the renderer or an external launcher starts
   both. The game-pass runner explicitly does not inject into other processes
   ([game pass](GAME_PASS.md)); whichever direction is chosen must keep that property.

## Recommendation: option B

Adopt **(B) a thin 32-bit proxy plus a separate x64 renderer process**, with a
versioned protocol and shared D3D12 resources/fences as the bulk transport. Keep the
game's own D3D9 raster presentation as the authority and the fallback.

Reasons, in order of weight:

1. **The providers force a process boundary anyway.** Both FidelityFX providers the
   project has integrated crash their host on allocation failure and are integrated
   only as x64 targets ([Ray Regeneration](RAY_REGENERATION.md),
   [radiance cache](RADIANCE_CACHE.md)). Under A, Phase 7 would still need an x64
   worker plus IPC. A would then have built two architectures, not one.
2. **The recoverable-fallback exit gate is much easier to prove with B.** Phase 6
   requires stable presentation with recoverable fallback
   ([phase plan](../PHASE_PLAN.md)). A renderer crash under B is an event the proxy
   can observe and survive; under A it ends the session.
3. **Address space.** The 32-bit clamp is already measured
   ([codebase map](../CODEBASE_MAP.md)), and capture's CPU shadow budget already
   claims 128–256 MiB of it ([shadow-cap experiment](HL2_SHADOW_CAP_EXPERIMENT.md)). Real-game memory
   headroom has not been measured, and the renderer budget was sized for x64.
4. **The hard parts already exist in x64.** Fence ownership, admission, bounded
   polling, kill-on-close jobs and buffer reuse have tests in the radiance-cache
   session ([cross-process shared resources](RADIANCE_CACHE_SHARED.md)). Codebase
   map task M5.1 ("move the proven RC fence/session state machine into the
   interactive renderer loop") already assumes this route
   ([codebase map](../CODEBASE_MAP.md)).
5. **It matches the stated architecture.** No documented decision needs reversing
   ([codebase map](../CODEBASE_MAP.md),
   [advanced engine architecture](ADVANCED_ENGINE_ARCHITECTURE.md)).

What B gives up: an extra per-frame handoff whose cost is unmeasured, a second
binary to version and ship, and a new cross-process surface. These are the risks
below. Nothing here says D3D12 cannot run in a 32-bit process.

### Scope of the first B slice

- Proxy (x86): forwarding as today, continuous bounded capture, protocol client,
  return-path import, raster fallback. No D3D12 renderer code.
- Renderer (x64): existing `rrt_dxr` scene/acceleration-structure path driven by
  protocol messages instead of a file, with the existing allocation ceiling.
- Protocol: versioned header and negotiation; fixed-width fields only; frame IDs;
  resource generations; latest-wins admission with one active and one pending frame;
  explicit stop/ack. Bulk payload in shared default-heap resources (upload/readback
  heaps are not shareable, per
  [cross-process shared resources](RADIANCE_CACHE_SHARED.md)).
- Handles: inherited and allowlisted, never named global objects; adapter LUID
  verified before any shared resource is opened.

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Return path needs a per-frame CPU copy into D3D9 | Added latency and CPU cost per frame; may dominate at high resolution | Measure the CPU path first as the baseline; keep `--render-scale` available to bound the size ([DXR viewer](DXR_VIEWER.md)); qualify a GPU-sharing route separately before relying on it |
| Unmeasured handoff latency | Visible input lag, or frame pacing worse than raster | Frame IDs and timestamps in the protocol from day one; latency is an exit-gate measurement, not an assumption |
| Two cadences drift (game `Present` vs renderer completion) | Stale or repeated frames, stutter | Latest-wins admission; present the newest completed frame or raster; never block the game's `Present` on the renderer beyond a bounded wait |
| Protocol or layout mismatch between x86 and x64 builds | Silent corruption | Fixed-width fields only; layout asserted identically in both builds; version negotiation fails closed |
| Renderer crash, hang or device removal | Lost RT output | Bounded fence waits that also watch the process handle; revert to raster; relaunch only on explicit request ([cross-process shared resources](RADIANCE_CACHE_SHARED.md)). Driver failure is explicitly not covered by isolation |
| Adapter mismatch (hybrid or multi-GPU) | Shared open fails | LUID check fails closed to raster; second-GPU qualification stays a separate gate ([phase plan](../PHASE_PLAN.md)) |
| Handle or protocol abuse by another local process | Integrity of renderer input | Inherited allowlisted handles only, no named objects, job containment; documented as fault containment, not a sandbox ([Ray Regeneration](RAY_REGENERATION.md)) |
| Spawning a process from inside the game | Conflicts with launcher, overlay or anti-cheat expectations | Offline, anti-cheat-free titles only ([reference title](REFERENCE_TITLE.md)); decide launch direction explicitly (open unknown 4) |
| Cross-arch test cost | Slower iteration; GPU-only validation | GPU-free protocol contract tests runnable in CI; GPU tests run on the target machine as today ([build](BUILD.md)) |

## Test plan

Each stage runs in x86 proxy Debug and Release against x64 renderer Debug and
Release on the target GPU, unless marked GPU-free.

1. **Protocol contract (GPU-free, CI).** Version negotiation; mismatched version,
   truncated, oversized and out-of-sequence messages rejected; identical struct
   sizes/offsets asserted in both architectures; machine-readable schema kept in
   agreement with C++ and Python, following the capture-version pattern
   ([project status](PROJECT_STATUS.md)).
2. **Transport parity on fixtures.** The x86 smoke/scene fixture through the proxy
   drives the x64 renderer. Its output for a fixed scene, camera and seed must match
   the standalone headless render byte for byte. The raster path must still match
   the no-proxy system baseline exactly
   ([compatibility ledger](COMPATIBILITY_LEDGER.md)).
3. **Fault injection.** Kill the renderer, hang past the deadline, flood output,
   return the device-removal fence sentinel, mismatch version and adapter LUID. In
   every case the fixture keeps presenting raster with exact baseline pixels, the
   child is reaped, and a later explicit start recovers. This mirrors the existing
   live-session fixtures ([cross-process shared resources](RADIANCE_CACHE_SHARED.md)).
4. **Lifecycle.** `Reset`/`ResetEx`, resize, minimize/restore and clean shutdown in
   both orders (game first, renderer first), on D3D9 and D3D9Ex. Handle counts and
   renderer requested bytes return to their baseline after every cycle.
5. **Pacing and latency.** Per-frame IDs and timestamps at capture, renderer
   completion and the game's `Present`. Report added latency (frames and ms),
   stale-frame rejections, raster substitutions and fence waits. No target is
   assumed in advance; the numbers are recorded as evidence.
6. **Soak.** Repeated proxy-on sessions with the stress-test script that Phase 6
   lists as a deliverable ([phase plan](../PHASE_PLAN.md)); no growth in handles,
   requested bytes or process count.

Reference-title play sessions are the Phase 6 exit gate itself and are not repeated
here.

## Exit gate for this decision

Option B is **confirmed** and M5.2 (D3D9 Present/Reset bridge,
[codebase map](../CODEBASE_MAP.md)) proceeds on it when all of these hold:

- Test-plan stages 1–4 pass in all four proxy/renderer configuration pairs.
- Stage 3: every injected fault leaves the fixture presenting raster with pixels
  identical to the no-proxy baseline, with no game-process exit and no orphaned
  renderer process.
- Stage 4: zero growth in handle count and renderer requested bytes across at least
  ten repeated attach/detach cycles.
- Stage 5 has produced a recorded latency and pacing measurement for the chosen
  return path, at the fixture's captured extent, committed as evidence alongside
  its method.
- The protocol schema and contract test are published, and the version is
  negotiated, not assumed.

**Reopen this decision** (and evaluate A, at least for the presentation leg) if
either of these holds:

- No return path can be qualified that keeps the game's raster fallback intact.
- The measured stage-5 handoff cost exceeds one game frame at the fixture
  resolution and cannot be reduced by a qualified GPU-sharing route.

Record the outcome in this file and in [project status](PROJECT_STATUS.md).
