# Progressive standalone D3D12/DXR viewer

`rrt_dxr` renders complete `.rrscene` captures, including output from the offline
mod compiler, using hardware DXR 1.1 inline ray queries. It builds bottom-level
acceleration structures (BLAS) for draws and a top-level structure (TLAS), traces
primary visibility rays, directional shadow rays and optional one-bounce diffuse
lighting. GPU scene resources and acceleration structures persist across samples.

This is an **interactive viewer for static captured scenes**, not a full path
tracer, live game bridge or Remix-equivalent runtime. Progressive diffuse GI is
implemented, with optional analytical spatial filtering and inspectable renderer
signals, plus optional camera-reprojected temporal reuse. Optional stable-ID
[material sidecars](MATERIAL_INPUTS.md) add GGX direct shading, emission and light
colour/intensity inputs. Reflection bounces, advanced multi-scale denoising,
full PBR/colour-space conversion, FSR and radiance caching are not implemented.

## Build and run

The standalone renderer should normally be x64. Keep the game capture proxy x86:

```powershell
cmake --preset windows-x64-renderer
cmake --build --preset renderer-release
ctest --preset renderer-release
.\build\x64-renderer\Release\rrt_dxr.exe --probe
.\build\x64-renderer\Release\rrt_dxr.exe PATH_TO_CAPTURE.rrscene --mode relit --show
.\build\x64-renderer\Release\rrt_dxr.exe PATH_TO_CAPTURE.rrscene --mode gi --samples 256 --interactive
```

Use the [capture guide](SCENE_CAPTURE.md) to produce a scene with the x86 proxy,
or the [mod workflow](MOD_WORKFLOW.md) to produce a modified scene. The versioned
scene format is pointer-free and can be passed between x86 capture and x64
rendering without conversion.

`renderer-debug` and its matching CTest preset provide the Debug configuration.
The renderer-only preset builds no replacement `d3d9.dll` and no game harness;
it also builds the independent `rrt_replay` raster oracle. Do not substitute a
64-bit DLL into a 32-bit game.

The normal x86 presets still build/test `rrt_dxr` when DXC is available, but x86
address space and DXGI's pointer-sized memory fields make that a compatibility
test path, not the recommended renderer architecture.

### Dependencies

Windows SDK DXC is required **at build time** to compile `render.hlsl` into
`rrt_rayquery.dxil` (compute shader model 6.5). CMake looks on PATH and in the
standard Windows Kits SDK location; a nonstandard installation can be selected
with `-DRRT_DXC=C:/path/to/dxc.exe`. Without DXC, existing capture/replay targets
remain available and the DXR target is omitted with a warning.

Distribute `rrt_dxr.exe`, `rrt_rayquery.dxil`, `rrt_temporal.dxil`, `rrt_present.dxil`, `rrt_export.dxil`,
`rrt_display_vertex.dxil` and `rrt_display_pixel.dxil` together from
the same build. The viewer
does not dynamically load a shader compiler or require ROCm/HIP. The GPU/driver
must provide D3D12 feature level 12.0, hardware DXR tier 1.1 and shader model 6.5.
The implementation uses Microsoft's [inline ray-query model](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html)
and the documented [acceleration-structure resource states](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ns-d3d12-d3d12_build_raytracing_acceleration_structure_desc).

## Controls and diagnostics

| Option | Behavior |
|---|---|
| `--probe` | JSON capability report for the selected adapter; no scene required |
| `--adapter N` | DXGI adapter index, default 0; no automatic vendor preference |
| `--mode albedo` | Texture × interpolated vertex colour, default |
| `--mode normals` | Camera-facing geometric face normals mapped to RGB |
| `--mode relit` | Albedo times ambient plus Lambertian directional light |
| `--mode gi` | Jittered primary rays, soft directional shadows and one diffuse bounce |
| `--samples N` | Accumulate 1–4096 samples, default 1; target per camera/settings state |
| `--seed N` | Deterministic unsigned 32-bit random seed, default 1 |
| `--sun-radius R` | GI light disk radius at unit distance, 0–1, default 0.04; 0 is a hard directional source |
| `--light X Y Z` | Direction from a surface toward the light; normalized internally |
| `--materials FILE.rrmat` | Opt-in stable-ID material factors and PBR direct shading; see [material inputs](MATERIAL_INPUTS.md) |
| `--light-color R G B` | Directional-light RGB, each 0..1, default white |
| `--light-intensity N`, `--ambient N` | Finite 0..32; default .85 and .15 |
| `--lighting-test` | Automatic lighting-history invalidation diagnostic; temporal GI, at least two samples, no other diagnostics/window |
| `--no-shadows` | Disable direct-light shadow queries; GI bounce intersections remain active |
| `--denoise` | Optional 5×5 geometry/albedo-guided spatial filter, active only in GI mode |
| `--variance-filter` | Experimental two-stage GI filter; failed its improvement gate, not the default. See [experiment and RR research](RAY_REGENERATION.md). |
| `--temporal` | Optional camera-reprojected GI history, capped at 32 effective samples; combines with `--denoise` |
| `--camera-offset X Y Z` | World-space translation relative to the captured camera |
| `--yaw DEG`, `--pitch DEG` | Local camera rotation; yaw ±360°, pitch ±89° |
| `--pixels NEW_FILE` | Write final tightly packed BGR8 readback without overwriting; with a window, save on close |
| `--signals NEW_FILE` | Export final raw/filtered float RGB and unjittered surface/motion guides; no overwrite |
| `--show` | Display the completed GPU image in a resizable native window |
| `--interactive` | Refine while idle; local keyboard navigation and lighting controls |
| `--history-test` | Headless reset/reuse diagnostic; renders nine changed/restored settings pairs |
| `--window-test` | Hidden-window message-loop diagnostic; requires the original captured camera, closes automatically |
| `--presentation-test` | Native window test plus three resizes, controlled minimize/restore and bounds rejection; verifies actual back-buffer pixels |
| `--gdi` | Explicit GDI fallback for `--show`, `--interactive` or `--window-test`; cannot be combined with `--presentation-test` |
| `--async-test` | Hidden asynchronous control/resize test with sparse verified snapshots; requires at least four target samples |
| `--no-frame-pacing` | Native-window opt-out from waitable-frame admission; retains vsync and fence protection |
| `--pacing-test` | Hidden paced resize/pause/suspend/early-close test; target at least eight samples, closes after seven |
| `--async-close-test` | Hidden normal-native path that closes after seven queued samples; requires a target of at least eight and no other window diagnostics |
| `--motion-test` | Render once, translate camera +0.1 world units in X and Y, render again; requires `--signals`, one sample and no window/other diagnostic |
| `--temporal-test move\|light\|cut\|reset` | Warm up for `--samples`, change camera/light/reset state, render one fresh sample; requires GI, `--temporal`, `--signals` and no other diagnostic/window |
| `--debug` | Enable the installed D3D12 debug layer; fail on reported errors/corruption |

For example:

```powershell
.\build\x64-renderer\Release\rrt_dxr.exe scene.rrscene --mode albedo --pixels albedo.pixels
.\build\x64-renderer\Release\rrt_dxr.exe scene.rrscene --mode normals --show
.\build\x64-renderer\Release\rrt_dxr.exe scene.rrscene --mode relit --light .6 .3 -1 --debug --show
```

The probe reports numeric `dxr_tier: 11` for tier 1.1 and
`shader_model_tested: 101` (`0x65`) for shader model 6.5. This is the tested shader
model, **not a maximum-capability search**. `process_bits` distinguishes x86/x64;
`dxgi_reported_dedicated_bytes` is DXGI's reported value, not a measured residency
budget. Unsupported adapters fail rendering with an actionable error. Use
`rrt_replay` explicitly as the raster fallback; no silent substitution occurs.

Interactive controls apply only while the viewer receives keyboard input:

- WASD: forward/left/back/right; Q/E: down/up, 0.05 captured-camera units per key event.
- Arrow keys: yaw/pitch in 3° steps; Home: original captured camera, preserving lighting.
- 1/2/3/4: albedo/normals/relit/GI; L: rotate light 90° around world Y; H: toggle shadows.
- F: toggle spatial filtering (GI only); the title shows whether it is active.
- T: toggle temporal reuse (GI only); R: explicitly clear accumulation and temporal history.
- Space: pause/resume refinement. Navigation while paused still displays one fresh sample.
- Escape or window close: exit. Held keys use Windows key repeat; mouse-look is not implemented.

Camera, mode, light, shadow, seed, sun-radius or filter changes reset **raw
stationary accumulation**. Unchanged settings preserve it. With `--temporal`, a
separate lighting history may survive a small camera move after per-pixel surface
checks; otherwise temporal history is also discarded. At the sample target the viewer sleeps until another
event. Use `--samples 256` for progressive refinement; the default remains one
sample for backward-compatible headless use.

The preview now defaults to a native two-buffer D3D12 flip-discard swapchain.
A fullscreen triangle reads the packed GPU output directly; no CPU image upload
feeds the display. Display resize uses nearest-pixel scaling without changing
the captured render resolution, camera or lighting history. `--show` remains a
static, completed-image preview. `--gdi` selects the older readback/GDI window
instead; it is an explicit selection, not a silent fallback after native failure.

Native samples now skip the per-sample output copy/map and immediate fence wait.
Four submission slots and two back-buffer fences bound CPU/GPU overlap; Present
remains vsynced. Normal native viewing now also uses DXGI's frame-latency waitable
object with maximum frame latency one. Interactive rendering waits before the
first sample and every subsequent displayed sample. The 100 ms bounded wait
also wakes for window messages; a granted admission is retained while messages
are pumped again before rendering. Paused/completed views wait only when a repaint
or new sample is needed. Fence waits still protect resource reuse independently.
This is not an input-to-scanout latency measurement or performance guarantee.
`--no-frame-pacing` explicitly restores the unpaced native path; there is no silent
fallback after creation/wait failure. `--show` computes its static image before
opening the window, but gates display submissions. The comparison diagnostics
(`--window-test`, `--presentation-test`, `--async-test`) remain explicitly unpaced
because they issue extra verification presents. Normal native viewing reads the final
renderer image once on close for output/hash reporting. Headless/GDI and the
older window diagnostics retain synchronous per-sample comparison readback.
Minimized/zero-size
windows suspend rendering/display, and restoration repaints the preserved image.
Exclusive fullscreen/Alt+Enter is disabled; desktop DPI and true fullscreen
behavior are not qualified. Display sizes above 4096 in either dimension or
above the aggregate allocation cap fail with an explicit error. An interactive
resize beyond the cap currently exits the viewer rather than lowering quality.

## Scene admission and shading contract

- Complete, nonempty scenes, at most 1,024 draws. Partial captures are rejected.
- One shared captured view/projection pair; full-frame viewport with depth range
  0–1. Invertible finite camera matrices, no infinite far plane or homogeneous
  horizon crossing. Orthographic and perspective fixtures are tested.
- Affine per-draw world transforms, baked into uploaded vertex positions.
  Transformed positions, unprojected camera bounds and UVs are limited to ±1e6.
- The current capture format's XYZ/ARGB/UV triangle lists. World-space geometric
  normals are computed from triangle edges and faced toward the viewing ray;
  there are no imported smooth normals or normal maps.
- Opaque double-sided surfaces with Gouraud colour interpolation and all colour
  channels enabled. Alpha test, blending, culling, sRGB output and flat shading
  are rejected rather than silently approximated.
- One literal-colour mip-zero texture per draw. Matched point/point or
  linear/linear min/mag filtering, with wrap/mirror/clamp addressing. No sRGB
  sampler conversion, anisotropy, derivative-driven LOD or mip chains.
- Scissor rectangles filter primary-ray candidates. Secondary rays see the physical
  uploaded geometry, including portions clipped from the primary view.

The deterministic modes use integer D3D9 pixel-center coordinates; GI adds
uniform ±0.5-pixel jitter. Nearest geometric intersection replaces legacy draw-order visibility;
arbitrarily overlapping depth-disabled D3D9 draws need not match their original
raster result. Edge ownership and texture/interpolation rounding can also differ.
The D3D9 replay remains the exact legacy oracle; DXR import comparisons use
explicit tolerances and do not claim universal pixel equivalence.

Default legacy relighting uses ambient 0.15 plus directional intensity 0.85 times the cosine
term and visibility. Default light direction is `(-0.4, 0.6, -1)` before
normalization. Shadow rays use a fixed 0.0001 world-unit offset/TMin and 100,000
world-unit maximum distance. This bias/range is deliberately a first-fixture
choice, not a scale-independent solution for arbitrary game worlds. Output is
clamped directly to 8-bit display values without a physical exposure/tone mapper.

Legacy GI samples a soft directional light using a disk at unit distance. A
cosine-weighted hemisphere ray supplies either constant white environment
radiance 0.15 on a miss, or the hit surface's albedo times its shadowed direct
light on a hit. The default estimator stops there: it omits further bounces,
specular transport, smooth normals and physically calibrated materials. Primary
misses retain the captured background, distinct from the GI environment.

With `--materials`, opted-in surfaces also emit radiance and use GGX direct
lighting; their indirect path still samples only diffuse reflection. Emission
from a secondary hit can illuminate a legacy or PBR diffuse primary. See
[material inputs and constraints](MATERIAL_INPUTS.md) for exact semantics.

Each sample is averaged into an RGBA32F buffer before clamping/quantization.
Sample zero overwrites history without reading stale or uninitialized values.
Sampling is repeatable for identical inputs on the tested adapter/driver, not a
promise of cross-vendor or cross-driver bit identity. More samples reduce Monte
Carlo noise; a finite-sample comparison is not an exact ground-truth proof.

## Renderer signals and spatial filtering

A second unjittered primary visibility query writes stable surface guides for
each pixel. Camera motion projects that world-space hit into the **previous
completed sample's** camera, including across an accumulation reset. Motion is
previous minus current pixel position, X right/Y down, with no jitter component.
The first sample and background have invalid, zero motion. Out-of-frustum or
nonfinite previous projections are also invalid. On stationary later samples,
valid motion is approximately zero.

Motion validity means **projection valid**, not visibility/history safe. The
temporal pass separately records acceptance after previous-surface tests; there
is no animated-object motion. These signals are groundwork, not an FSR-compatible
input contract: ray distance differs from view-space Z/device depth, RGB still
uses the captured literal colour convention, and roughness/specular signals are
absent. Accumulated jittered radiance can contain mixed edge coverage while its
guide describes only the pixel center.

`--denoise` runs a separate GPU pass over raw accumulated radiance, or temporal
RGB when `--temporal` is active. Its 5×5
Gaussian kernel rejects background, different draw IDs, normal dot products
below 0.95, depth differences above max(0.005, 2% of center depth), and any
albedo-channel difference above 0.1. It filters demodulated diffuse lighting
using an albedo floor of 0.05, then remodulates the result. Raw history is never
modified by this pass. Non-GI modes and background bypass filtering.

This simple, opt-in spatial filter can soften illumination/shadow details and
jittered silhouettes. It is biased and not variance-adaptive or multi-scale,
and neither it nor our temporal pass substitutes for FidelityFX Ray Regeneration. Draw boundaries
are deliberately conservative filter barriers, even if two draws share materials.

```powershell
.\build\x64-renderer\Release\rrt_dxr.exe scene.rrscene --mode gi --samples 8 --denoise --signals frame.signals --pixels filtered.pixels
python tools\inspect_signals.py frame.signals
```

### Temporal reuse and rejection

`--temporal` consumes a **fresh stochastic sample**, not the already accumulated
raw RGB. It reprojects the unjittered surface to the nearest previous pixel,
rejects invalid projections/background/different draw IDs/albedo/normal mismatch,
then compares world-space surfaces. This avoids comparing ray distances measured
from two different cameras. Normal agreement must be at least 0.95 and albedo
channels within 0.1. Plane separation must be at most max(0.001, 0.1% of current
ray distance), with total position separation at most max(0.002, 1.5× the larger
horizontal pixel footprint). These conservative, fixture-scale thresholds can
reject valid history in other scales or at steep angles.

Accepted history gets weight (n−1)/n, with effective count n capped at 32. Beyond
32 this is an exponential moving average, not an ever-growing sample average.
For moving pixels, previous RGB is clipped to the min/max fresh RGB in a 3×3
matching-surface neighborhood. Luminance second moments are blended alongside
RGB; reported variance is max(0, second moment − squared mean luminance). Clipped
history preserves its prior variance while shifting the mean. This is a biased
diagnostic estimator, not an unbiased variance of the final denoised image, and
variance does not drive the baseline spatial filter. The experimental variance
alternative uses these moments but has not passed its quality gate.

Lighting, seed, mode, filter toggles, explicit R/Home resets and detected camera
cuts invalidate temporal history and restart its RNG sequence. A cut means over
1 world unit of translation or at least 30° yaw/pitch change since the previous
completed sample. This scale-dependent heuristic is not universal cut detection.
Small camera changes reset raw accumulation but preserve the temporal RNG stream
and allow per-pixel history checks. Unknown/animated geometry is still unsupported.

Unchanged cameras reproduce ordinary sample means up to the 32-sample cap on
the verified fixture. For a long stationary high-quality render, disabling
temporal reuse retains the full progressive average (up to 4096 samples).
Background uses raw accumulation. Rejected surface pixels start with only their
fresh sample; spatial filtering, if enabled, is applied afterward. The two
temporal signal buffers are never used simultaneously as input and output.

```powershell
.\build\x64-renderer\Release\rrt_dxr.exe scene.rrscene --mode gi --temporal --denoise --samples 32 --interactive
```

### RRTSIG02 diagnostic file contract

All integers and IEEE-754 float32 values are little endian. The 36-byte header
contains eight ASCII bytes `RRTSIG02`, then seven uint32 fields: version (2),
width, height, record stride (144), raw accumulated sample count, flags (bit 0 =
spatial filter requested, bit 1 = temporal requested; other bits zero), and mode
(0 albedo, 1 normals, 2 relit, 3 GI).
Exactly width×height records follow in top-to-bottom, left-to-right order, with
no trailer. Each record contains nine float4 values:

| Byte offset | Signal | Meaning |
|---|---|---|
| 0 | Raw RGB, 1 | Accumulated unquantized output for the selected mode; never filtered |
| 16 | World normal XYZ, ray distance | Camera-facing unit geometric normal; distance from the unjittered near-plane ray origin in world units |
| 32 | Albedo RGB, hit validity | Texture×vertex colour, validity 1 for a surface |
| 48 | Motion XY, projection validity, draw ID | Pixel units, validity 0/1; draw index+1, not a stable material/content ID |
| 64 | Filtered RGB, 1 | Presentation RGB before clamp/8-bit quantization; raw RGB when temporal and spatial processing are inactive |
| 80 | World position XYZ, footprint | Unjittered hit and horizontal adjacent-ray spacing at that ray distance; zero for background |
| 96 | Fresh sample RGB, 1 | Single stochastic sample before raw or temporal averaging |
| 112 | Temporal RGB, second moment | Temporal mean and luminance second moment; fresh sample when rejected/inactive |
| 128 | Count, variance, accepted, reason | Effective sample count 1–32, nonnegative luminance variance, acceptance 0/1, rejection code |

Presentation RGB uses temporal rather than raw RGB when temporal reuse is active
on a surface; spatial filtering is a separate optional step. Temporal reason
codes are: 0 accepted; 1 disabled/non-GI; 2 first frame/global reset; 3 current
background; 4 invalid/out-of-bounds previous projection; 5 previous background;
6 draw/albedo/normal mismatch; 7 world-space depth/position mismatch. Checks are
ordered, so first-frame background reports 2. Projection validity at offset 48
does not imply temporal acceptance at offset 128.

For background, offsets 16–63 are zero; raw/filtered RGB retain the background.
`inspect_signals.py` validates sizes, format, finite values, normal/validity/ID,
motion and temporal-statistics invariants. It still reads legacy `RRTSIG01`
(version 1, stride 80, only flag bit 0) without reinterpreting it as version 2.
The CLI streams at most 16,384 records per read, accepts up to 1 GiB of payload
and rejects trailing data. The Python `load_signals` random-access convenience
API retains its 256 MiB allocation cap; use `inspect_file` or the CLI for full HD.
This diagnostic format is not a replacement for `.rrscene` and
does not contain enough scene/camera/seed metadata to reproduce a render alone.

## Synchronization, bounds and timings

Acceleration-structure builds and tracing run on one direct command queue.
Explicit UAV barriers order BLAS/TLAS construction and successive history writes;
output transitions between UAV and copy source for each readback. A fence must complete before CPU access/resource
release on the successful path. Device removal, a 30-second fence timeout or
debug-layer errors cause failure.

Uploads are limited to 64 MiB, individual buffer requests to 256 MiB and total
requested buffer storage to 512 MiB. This accounting does **not** include driver
metadata/heap granularity and is not measured VRAM residency. The initial design
keeps input data in upload heaps, builds a BLAS per draw without deduplication,
and retains scratch buffers for the renderer lifetime. Uploads, BLAS/TLAS,
pipeline, accumulation and readback buffers are allocated once and reused;
camera/light changes do not rebuild geometry. There is no geometry streaming,
AS update/refit, mesh deduplication or live scene reload yet.

Runtime signals now use an 88-byte working record plus two 64-byte temporal
records: 216 bytes/pixel instead of 288. Lighting, guides, motion and moments
remain float32; only integer count/rejection/validity metadata is bit-packed.
The original motion pair is retained because reconstructing it from rounded
world positions can change projection validity at frustum boundaries.
Including raw accumulation and packed output/readback, frame buffers use
240 bytes/pixel, down from 312 (23% less). Full-HD fixture rendering now fits
the unchanged budgets; larger geometry can still exhaust the remaining space.

`--signals` adds a fixed 4.5 MiB GPU/readback staging pair (16,384 records each),
replacing the full-frame diagnostic readback. After rendering ends, a fourth
shader reconstructs unchanged 144-byte RRTSIG02 records in chunks, recomputing
only presentation colour and derived statistics. Exports do not run per sample
or modify lighting/history. A 1920×1080 file is 298,598,436 bytes (about 285 MiB)
and uses 127 export submissions, including the partial final chunk. Export
files are CREATE_NEW; a failed export may leave a partial new file to inspect.

Frame constants use four independent 256-byte upload regions, adding only 768
requested bytes versus the previous single-region path. Four command allocator/
list slots rotate with fence-gated reuse. Each slot also owns five timestamp
queries and a separate readback range; timing is collected after safe reuse or
drain, never read from a pending submission. UAV barriers separate tracing, temporal resolve,
presentation and successive samples. Presentation writes the next compact
temporal buffer, which transitions to SRV; the former SRV becomes the next UAV.
The working buffer stays UAV. Export staging transitions to copy source and back
for each bounded readback. Native display is a separate graphics submission on
the same direct queue: packed output transitions from COPY_SOURCE to pixel SRV
and back; the selected back buffer transitions from PRESENT to render target
and back. In window diagnostics only, it also transitions through COPY_SOURCE
for a row-pitch-aware readback before Present. Fences signaled after Present gate
back-buffer/allocator reuse; ordinary native display does not immediately wait
after submission. Explicit snapshots, resize, exports and normal teardown drain
all queued work first. Recorded references in every command-list slot are cleared
before releasing swapchain resources. All rendering remains on one ordered direct
queue: temporal histories are not evaluated concurrently on separate queues.
These ownership changes are not game-performance results.

Swapchain textures are charged using the device's allocation-size query, plus
any diagnostic display-readback buffer. Resize admission checks the new total
before releasing the old resources; old recorded references and RTV resource
pointers are released before ResizeBuffers. Render resources retain their prior
allocation; display resources are released on window teardown. Peak accounting
still excludes opaque driver metadata and is not measured VRAM residency.

The ownership model follows Microsoft's [D3D12 swapchain documentation](https://learn.microsoft.com/en-us/windows/win32/direct3d12/swap-chains).
The code handles an occluded Present with timed status probes and repaint on
recovery, but flip-model windows normally do not return this status. See the
[DXGI status contract](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/dxgi-status).
Hidden-window/status-injection tests therefore do not qualify real desktop occlusion.

Each render prints JSON with:

- `gpu_build_ms`: GPU timestamp interval covering BLAS/TLAS work.
- `gpu_trace_ms`: sum of GPU intervals for lighting and guide queries and setup.
- `gpu_temporal_ms`: sum of temporal-resolve intervals, including diagnostics when reuse is off.
- `gpu_filter_ms`: sum of presentation/filter-pass intervals (also includes packing when filtering is disabled).
- `gpu_copy_ms`: sum of GPU intervals for all output transitions/readback copies.
- `gpu_export_ms`: separate sum of diagnostic reconstruction/copy intervals.
- `signal_export_ms`: diagnostic export wall time, including fences and file writes.
- `build_render_readback_ms`: CPU wall time including uploads, shader pipeline
  creation/driver compilation, submission and waiting. When a window is used,
  this also includes time spent there before closing—not steady-state FPS.
  Pixel/signal file writing and diagnostic export are excluded.
- `samples`: raw samples in the final view; `dispatches`: logical sample submissions, including discarded history. Each contains three compute dispatches (trace/guides, temporal resolve, presentation).
- `history_resets`: configuration changes that cleared history; initial configuration is not a reset.
- `scene_build_submissions`: queue submissions excluding logical samples, diagnostic exports, display and explicit readback submissions; one for the static scene's BLAS/TLAS build batch.
- `export_submissions`: diagnostic chunk submissions, zero without export; `export_chunk_pixels`: 16,384.
- `history_test`: whether the headless reset/reuse diagnostic passed.
- `denoised`: whether spatial filtering was active; `temporal`: whether temporal reuse was enabled in the final mode; `signal_stride`: 144 bytes.
- `temporal_resets`: global invalidations that discarded a valid temporal buffer, not per-pixel rejection counts. This may be lower than `history_resets` when returning from a non-GI mode.
- `working_stride`: 88 bytes; `temporal_stride`: 64 bytes per history buffer. These runtime layouts are distinct from the stable diagnostic format.
- `requested_buffer_bytes`: bounded requested buffer accounting.
- `presentation`: `headless`, `gdi` or `d3d12-swapchain`.
- `display_submissions`: graphics display submissions, separate from renderer samples; `display_verified`: diagnostic back-buffer comparisons (zero outside window tests).
- `display_presented` / `display_occluded`: successful/occluded real Present results; `display_buffer_mask`: bit mask of back buffers used (3 means both).
- `display_resizes`: successful ResizeBuffers calls; `display_suspended_ticks`: loop ticks suspended by minimize/zero-size messages; `display_rejected_resizes`: rejected resize attempts caught by the diagnostic.
- `peak_requested_bytes`: highest renderer-plus-display allocation accounting; includes temporary display readback when testing. `requested_buffer_bytes` after window teardown excludes released display resources.
- `frame_slots` / `frame_slot_mask`: four command slots and their used-bit mask (15 means all four).
- `async_submissions`: submissions without an immediate CPU fence wait; `max_inflight_submissions`: observed outstanding ring slots, at most four. Neither is a throughput guarantee.
- `fence_waits`: actual blocking fence waits, including slot/back-buffer reuse and drains; Present can also block separately.
- `render_readbacks`: CPU reads of the renderer pixel buffer; `readback_submissions`: separate snapshot copies (not copies within synchronous samples or diagnostic back-buffer reads).
- `timed_samples`: collected sample timestamp records; must equal `dispatches` after the final drain. `gpu_copy_ms` covers sample-tail transitions and any synchronous sample copy, not standalone snapshot/display copies.
- `pixel_sha256_bgra`: hash of the internal packed BGRA8 image. `--pixels` writes
  BGR8 instead, so its file hash is intentionally different.

The first cold shader/driver compilation can dominate wall time. Tiny synthetic
fixture timings must not be extrapolated into performance claims for real games.

## Automated verification

`dxr_render` generates a ground plane and a foreground occluder, then checks:

- Deterministic albedo readback, expected background/foreground/ground samples,
  and raster comparison (admission tolerance: fewer than 2% differing pixels).
- Camera-facing normals and localized darkening from actual secondary shadow
  queries; disabling shadows must remove that darkening without changing the
  background. A known point inside the projected shadow is checked separately.
- Perspective/view/world transforms, textured and vertex-coloured geometry,
  point/linear filtering and scissor state against D3D9. Fewer than 2% of pixels
  may differ by more than two 8-bit levels, with mean channel error below one.
- Import of the real offline mod compiler's texture replacement.
- Fixed-seed GI repeatability, changed-seed variation and lower 32-sample error
  than a single sample against a 256-sample reference. Allocation stays constant
  across sample counts, and there is exactly one scene-build submission.
- Actual diffuse colour transport: an edge-on red/blue wall leaves albedo
  visibility unchanged but changes the adjacent ground's corresponding GI channel.
- Eighteen history resets (camera translation/rotation, light, shadows, mode,
  seed, sun radius, filtering) restore a byte-identical reference with no new allocations.
- Finite float exports, known ground/foreground depths and normals, zero first-frame
  motion, stationary motion and a translated camera with expected (+6.4, −4.8)
  pixel motion. Projections outside the previous frame are marked invalid.
- Lower one-sample error with filtering, deterministic filtered output, unchanged
  raw lighting/guides, background isolation and a black/white albedo-edge check.
- Bounded signal parsing rejects malformed headers, sizes, NaN and validity;
  existing signal output cannot be overwritten.
- A hidden native window exercises its message loop: paused navigation, Home,
  resume, mode/light/shadow/filter changes and automatic close. Restored output matches
  headless rendering. This does not qualify visible-window DPI/fullscreen behavior.
- Rejection of incompatible materials, singular/multiple cameras, partial
  captures, out-of-range geometry, invalid adapters and output overwrite.
- The installed D3D12 debug layer, when available. This is standard API-layer
  validation, not GPU-based validation or a PIX capture.

The GPU test returns CTest skip code 77 if the selected adapter lacks hardware
DXR 1.1/SM 6.5. A skipped result does not establish renderer support.
Artifacts remain in `build/<configuration-root>/<configuration>/dxr-*`, with
`capabilities.json`, `verification.json`, input scenes, raw pixels and PNGs.

The separate `dxr_temporal` test verifies fresh-sample means/moments, the 32-sample
cap, light/camera-cut/manual reset equivalence, deterministic moved-camera output,
and revealed-ground rejection even when foreground and ground share a draw,
albedo and normal. It separately checks material mismatch rejection, v1 export
compatibility and invalid temporal statistics. Its `temporal-*` artifact folders
contain the inputs, signal dumps, images and verification report.
For same-GPU/driver refactors, `tests/verify_temporal.py --baseline <prior-temporal-folder>`
additionally requires every generated scene, pixel and diagnostic file to match
the prior run byte for byte (also pass `--dxr` as usual). This optional historical
comparison is not a cross-vendor image-hash requirement.

`dxr_resolution` checks 1920×1080 albedo and repeatable four-sample temporal/spatial
GI, unchanged allocation across samples, and a 257×129 three-chunk export with a
partial tail. It checks exported presentation against pixel output, streaming
and random-access summary equality, late-chunk corruption, and budget rejection
at 2560×1440 without creating outputs. Artifacts are retained in `resolution-*`.
The optional large-file test retains a full-HD export and validates it through
the streaming CLI (allow roughly 330 MiB of disk space for this invocation):

```powershell
python tests/verify_dxr_resolution.py --dxr build/x64-renderer/Release/rrt_dxr.exe --full-hd-export
```

Recorded RX 9070 XT full-HD fixture allocation: 497,681,520 requested bytes
(474.63 MiB), or 502,399,856 (479.13 MiB) with export. The exported and non-exported
images match. A same-GPU comparison of 53 historical scene/pixel/signal files
also matches byte for byte. These checks do not qualify larger game scenes.

Verified on the RX 9070 XT: the ground/occluder albedo fixture matched the raster
oracle exactly, 240 pixels changed under shadowing, and the perspective tests
had no pixels differing by more than two levels in the recorded run. This does
not supersede the tolerances or establish commercial-game compatibility.

Progressive fixture evidence on the same GPU: 32-sample MSE 3.58 versus
single-sample MSE 109.38 against the 256-sample reference (8-bit channel units
squared). The red/blue wall contributes about 20.6 channel levels in the checked
ground region. The current history diagnostic performs 152 sample submissions and 18 resets
with one scene-build submission and unchanged buffer allocation.

With one sample, the spatial filter lowers this fixture's MSE from 109.38 to
29.24 against the same 256-sample reference. This is fixture evidence, not a
general image-quality/performance guarantee. Unfiltered signal RGB remains
identical when filtering is enabled.

Temporal perspective-fixture evidence: accepted-pixel float-RGB MSE decreases
from 0.00028201 (fresh sample) to 0.000017343 against a 256-sample reference after
a camera move. The same-draw/two-depth fixture accepts 9,111 pixels and rejects
1,449 world-position/depth mismatches, plus 1,728 out-of-frame projections.
These are targeted prototype tests, not proof of ghost-free arbitrary game scenes.

`dxr_presentation` exercises native albedo/GI at 128x96 and 257x129, plus full-HD
GI, with exact comparison of every back-buffer pixel against headless output.
It uses both swapchain buffers, three actual ResizeBuffers calls, controlled
WM_SIZE minimize/restore messages, an injected occlusion-status branch and a
rejected resize followed by a successful draw. Bounds rejection includes the
aggregate memory limit in the full-HD case. GDI/headless output and repeated
native lifecycles are compared too. Each case retains one scene build and
unchanged renderer history after resizing. Artifacts are in `presentation-*`.

The hidden-window tests verify GPU content and API/resource ownership, not
visible desktop scanout, actual minimize/taskbar behavior, actual occlusion,
HDR, DPI scaling, fullscreen or recovery from device removal. Initial RX 9070 XT
full-HD peak, including enlarged display buffers and test readback, is
525,341,028 bytes (501 MiB), below the unchanged 512 MiB cap.

Previous asynchronous-sprint verification caveat: the six DXR tests passed in x86/x64 Debug/Release,
but the two full x86 suites finish 10/16 because six older D3D9 capture/mod/proxy
tests encounter `S_PRESENT_OCCLUDED` instead of `S_OK`. Exact proxy/system pixels
still agree. An isolated retry reproduces the condition; capture semantics were
not changed. Full legacy acceptance needs a rerun under normal presentation conditions.

`dxr_async` checks sparse readback and slot reuse against synchronous pixels and
signal exports at 128x96 and 257x129, plus pixel parity at 1920x1080. It exercises
camera/light/filter resets, three display resizes, all four command slots, both
back buffers, suspend/restore and early close with queued work. Every sample's
timing must be collected and allocation stays under the unchanged cap. A 129-sample
control run uses six renderer readbacks (five checkpoints plus final output),
while an early-close run produces the exact seven-sample image with one final
readback. Export/resize/shutdown are deliberate synchronization boundaries.
The close test queues an unrendered mode change and verifies the final image
retains the actual rendered mode/filter metadata. The additional constant regions
raise the full-HD resize-test peak to 525,341,796 requested bytes, still below
512 MiB. Artifacts remain in `async-*`; hidden-window limitations still apply.

## Next renderer work

The selected denoiser direction is now AMD RR: its supervised bounded context
policy passes on the local RX 9070 XT with pinned reporting workarounds and
process-contained failure/recovery. Raw SDK acceptance still fails; this is not
an SDK binary fix. A separate bounded preparation pass exports matched inputs
with CPU-reference checks; the isolated worker now executes a fenced reset-only
dispatch and [bounded stationary history](RR_SEQUENCE.md). The strict zero-light quality oracle fails slightly;
moving-camera SDK history, image-quality acceptance and viewer integration remain open. [Renderer-owned input recording](RR_RECORDING.md)
now captures source/settings identity and camera continuity without SDK admission. See [RR input preparation](RR_INPUTS.md)
and [isolated dispatch evidence](RR_DISPATCH.md).
See [the bounded integration sequence and failure evidence](RAY_REGENERATION.md).
The variance-filter candidate is retained only for research, not promoted as an
improvement over the existing filter.

Display-latency measurement and visible-desktop lifecycle qualification; shared mesh acceleration structures; default-heap
streaming and further resource optimization; smooth normals, material maps and colour management;
reflection/multi-bounce transport; adaptive variance-guided spatial filtering,
stronger temporal validation and animated-object history;
then evaluate FidelityFX upscaling, ray regeneration
and radiance caching against stable renderer buffers. Live game bridging and
reference-title qualification remain separate engineering/acceptance gates.

The next presentation refinements are fewer submissions and measured desktop
pacing, while preserving headless/back-buffer comparisons.
The submission-ring ownership follows Microsoft's [fence-based resource guidance](https://learn.microsoft.com/en-us/windows/win32/direct3d12/fence-based-resource-management).
More realistic desktop lifecycle qualification remains necessary. The standalone
swapchain does not imply that game capture and display are already bridged.

## Waitable-frame admission verification

`dxr_pacing` compares paced, explicitly unpaced and headless seven-sample output
at 128x96, 257x129 and 1920x1080, with exact signal parity at the smaller sizes.
Repeated lifecycles cover actual waitable-swapchain resize, controlled pause and
WM_SIZE suspend/restore, and close after seven samples with one final readback.
An independent test event exercises ready, seen-but-unconsumed message and timeout
results of the same wait helper; these synthetic wake tests are not represented
as actual DXGI stalls. Hidden tests do not qualify physical scanout, real taskbar
minimization, display refresh behavior or input latency. Results are in `pacing-*`.

JSON reports `maximum_frame_latency` (one when enabled; zero means disabled),
`pacing_waits`, `pacing_ready`, `pacing_messages`, `pacing_timeouts` and cumulative
`pacing_wait_ms`. The latter is CPU time spent inside admission waits, not frame
latency. `pacing_test_mask` is seven only after all three synthetic wake checks.
The frame handle is owned for the swapchain lifetime, retained across resize
with the waitable flag preserved, and closed on normal or exceptional teardown.
Closing before the first sample returns an explicit error without saving output.

Recorded Release evidence: `build/x64-renderer/Release/pacing-s9rbk9t0/verification.json`.
At the frame-pacing milestone, all seven renderer CTest entries passed in x86/x64 Debug/Release. The legacy D3D9
suites were not rerun in this renderer-only slice; their prior qualification caveat remains open.
The full-HD repeated paced lifecycle uses 516,556,656 requested bytes at peak,
under the unchanged 512 MiB limit. Historical parity in
`build/x64-renderer/Release/temporal-yk7ybp2w/verification.json` matches all 53
prior scene/pixel/signal files byte for byte. These are same-GPU fixture results.

Implementation follows Microsoft's [waitable handle contract](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_3/nf-dxgi1_3-idxgiswapchain2-getframelatencywaitableobject),
[maximum frame latency API](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_3/nf-dxgi1_3-idxgiswapchain2-setmaximumframelatency)
and [message-aware wait API](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-msgwaitformultipleobjectsex).
