# Scene capture and independent raster replay

Phase 3's first working slice captures a constrained, unlit fixed-function frame
and reconstructs it in a separate system-D3D9 process. It is a correctness oracle
for future DXR work, **not a ray tracer or universal game converter**.

## Run the fixture

Build with the presets in [BUILD.md](BUILD.md), then use a fresh output name:

```powershell
$sceneId = [guid]::NewGuid().ToString()
$scenePath = Join-Path $PWD "build\scene-$sceneId.rrscene"
$env:RRT_SCENE_FILE = $scenePath
$env:RRT_SCENE_FRAME = '0'
try {
    .\build\x86-vs\Release\d3d9_smoke_sample.exe --scene-fixture
} finally {
    Remove-Item Env:\RRT_SCENE_FILE
    Remove-Item Env:\RRT_SCENE_FRAME
}
.\build\x86-vs\Release\rrt_replay.exe $scenePath --inspect
.\build\x86-vs\Release\rrt_replay.exe $scenePath --show
python tools\export_gltf.py $scenePath "build\scene-$sceneId.gltf"
```

`--inspect` validates the file without creating a GPU device, and reports asset
IDs and rejection reasons as JSON. `--pixels NEW_PATH` emits tightly packed BGR
bytes, top to bottom. `--draw-count N` replays a prefix for draw-level diagnosis.
`--show` opens a native preview window; close it to exit. The viewer explicitly
loads Windows' D3D9 runtime, never the proxy beside its executable.

Scene capture is separate from `RRT_TRACE_FILE`: either or both can be enabled.
`RRT_SCENE_FILE` is required; capture is otherwise off. `RRT_SCENE_FRAME` defaults
to zero, accepts 0–1,000,000, and counts successful presents process-wide, matching
the observation trace's convention. Prior resource writes are tracked so a later
frame can be self-contained. The selected successful Present writes one file and
stops collecting. If that frame is never presented, no file is produced. A crash
during writing may leave an invalid partial file; readers reject it.

Output creation never overwrites an existing file or creates missing parent
directories. Save failures leave the game rendering unchanged and emit
`SceneSaveFailed` to the optional active observation trace and a debugger message.
`RRT_PROXY_DISABLE=1` bypasses both observation and scene capture.

## Supported subset

- One device, one primary swap chain, single-threaded submission. Classic D3D9
  and D3D9Ex, device or swap-chain Present, and later-frame capture after Reset.
- Non-MSAA X8R8G8B8 primary backbuffer, at most 4096×4096. The frame must begin
  with a full-target clear, with scissoring off; no intervening clear after draws.
- Triangle lists with exactly `XYZ | DIFFUSE | TEX1` FVF: object-space float XYZ,
  ARGB8 vertex colour and float UV. Solid fill; lighting, depth, stencil, fog,
  specular, vertex blending, clipping planes and coordinate wrap are disabled.
- Indexed/non-indexed buffer draws, DrawPrimitiveUP and DrawIndexedPrimitiveUP;
  16/32-bit indices, stream offset/stride and signed base-vertex addressing.
- World/view/projection, viewport, scissor, supported raster/blend states,
  stage-zero texture and sampler states are queried at each draw. Thus state
  restored by a D3D9 state block is observed rather than guessed from setters.
- One 2D A8R8G8B8 or X8R8G8B8 texture, mip zero, at most 2048×2048; no mip filtering
  or LOD offset to a higher level. Colour is texture × diffuse, alpha selects
  texture alpha; later texture stages are disabled. X8 texture alpha becomes 255.
- CPU writes through VB/IB Lock/Unlock and texture LockRect/UnlockRect. Pitch is
  removed from texture snapshots. Full initialization is required; subsequent
  partial writes are applied. DISCARD invalidates prior content, so a partial
  DISCARD cannot silently reuse stale vertices or texels.

Payloads live in a private-data object owned by each native resource. That object
does not retain the resource or device: pointer recycling and wrapper recreation
do not alias payloads, and no extra resource reference prevents Reset. Capture
storage is released with the resource. Read-only locks do not count as uploads.

Surface-alias writes, GPU texture updates and render-to-texture content invalidate
affected shadows instead of inventing replacement data. Shader draws, patches,
extra texture stages, incompatible state/targets, partial presentations and
unsupported frame operations are rejected. A frame with any rejected operation
is marked incomplete. Replay and export **refuse incomplete scenes by default**;
`--allow-partial` is an explicit diagnostic override, not a compatibility claim.

No shader translation, compressed textures, mip-chain extraction, lit/normal
formats, depth-buffer reconstruction, lights, instancing, DX8 translation,
shared-resource/external writers, or deterministic multithread capture is
qualified. Shared/external resource mutation must not be used for correctness
claims. An untested title may expose additional mutation paths: compare with a
native reference before treating a capture's completeness flag as fidelity proof.

## Limits and format versions

- Shadow payloads: 16 MiB/resource, 64 MiB total (plus bounded bookkeeping).
- Scene accumulation: 32 MiB estimated payload, 4,096 accepted draws, bounded
  rejection records; file cap 64 MiB. Exceeding a capture budget marks the scene
  incomplete; it never changes the native API's return value.
- Per draw: capture caps submitted triangles at 166,666; reader caps 500,000
  vertices and 1,500,000 indices. Texture payloads and all file arrays are bounded.
- Data is little endian, fixed-width, pointer-free and versioned. Floats are IEEE
  binary32. The final 32 bytes are SHA-256 of every preceding byte.

| Record | Layout |
|---|---|
| Header (60 bytes, v2) | 8-byte `RRTSCN1\0`, then nine uint32: version, frame, width, height, clear ARGB, attempted successful draws, cleared flag, accepted draw count, rejection count; then the metadata block: units uint32, scale float32, up-axis uint32, handedness uint32 |
| Header (44 bytes, v1) | the same 8-byte magic and nine uint32, with no metadata block |
| Rejection (8 bytes each) | uint32 ordinal and reason; ordinal `0xffffffff` denotes a frame-wide issue |
| Draw prefix (116 bytes) | five uint32: ordinal, texture width, texture height, vertex count, index count; then 32-byte mesh, texture and material SHA-256 IDs |
| Draw state (452 bytes) | three row-major D3DMATRIX values; D3DVIEWPORT9; four-int32 scissor; 34 render-state, 8 texture-stage and 13 sampler uint32 values, in the slot order defined in `src/scene/scene.h` |
| Draw payload | 24-byte vertices (`3 float`, ARGB uint32, `2 float`), uint32 triangle indices, tightly packed BGRA8 texture texels |
| Footer (32 bytes) | SHA-256 integrity digest |

Version 2 writes the coordinate contract instead of leaving it implicit. The
metadata enumerations are append-only and defined in `src/scene/scene.h`: units
`unitless`, `metre`, `centimetre`, `millimetre`, `inch`, `foot`; up-axis one of
`+X`, `-X`, `+Y`, `-Y`, `+Z`, `-Z`; handedness `left` or `right`. `scale` is a
positive uniform factor from stored units to metres, and is exactly 1.0 when
units is `unitless`.

Version 1 carried no metadata block. Readers therefore apply the documented v1
interpretation — **unitless, scale 1.0, +Y up, left-handed** — rather than
guessing from the geometry, and a v1 file decodes to exactly the same draws and
pixels as before. The writer always emits v2. Both readers accept v1 and v2 and
reject any other version; the metadata values themselves are range-checked, so a
file cannot claim an unknown unit or axis.

Geometry is normalized into first-index-use vertex order and zero-based 32-bit
indices. Mesh ID hashes uint32 vertex/index counts followed by those payloads;
texture ID hashes uint32 width/height followed by BGRA8 bytes; material ID hashes
the texture ID followed by the render/texture/sampler arrays. Transforms, viewport,
scissor rectangle, session pointers and wrapper IDs do not enter asset identity.
Identical payloads thus remain stable across runs and resource recreation, while
geometry/texture changes acquire different IDs. The format currently stores
payloads per draw (no on-disk content deduplication).

C++ (`rrt_replay --inspect`) and Python (`tools/scene_io.py`) readers verify
checksums, IDs, dimensions, counts, index bounds, finite positions/transforms,
viewport bounds, required subset state, the metadata block and exact end-of-file.
These are integrity checks, not authentication or a security boundary for
arbitrary third-party files.

## glTF interchange

`tools/export_gltf.py` exports self-contained glTF 2.0 with embedded vertex/index
data and PNG images, unlit materials, and node transforms. It reads the v2
metadata rather than assuming a convention: a left-handed `+Y` capture is
converted by reflecting Z and reversing triangle winding; a right-handed `+Y`
capture passes through; any other up-axis is refused. The declared units, scale,
up-axis and handedness are retained in `extras`, and a non-unit scale is applied
to node transforms. Original view/projection, viewport, scissor and D3D9 material
state are retained in `extras`.

glTF is an asset interchange, **not the pixel-fidelity target**. Arbitrary D3D9
projection, cull orientation, blend/alpha-test functions, border addressing,
colour-space rules, scissoring and draw order are not all equivalent to glTF.
No glTF camera or physical material is inferred from arbitrary legacy matrices.
The exporter documents these differences rather than promising matching pixels.

## Automated evidence

`ctest --preset debug` / `ctest --preset release` include classic and Ex replay
gates. Each compares frames 0, 1, 6 and 7 (before/after resize and Reset) against
the independently loaded system runtime with **zero differing colour bytes**.
Four visible quadrants exercise buffer, UP and indexed-UP geometry, negative
base vertex, 32-bit indices, partial updates, mid-frame texture changes,
transforms and scissor state. The tests also verify cross-session byte stability,
draw-prefix output, explicit incomplete-scene rejection, draw budgets, no
overwrite, capture disable, damaged files, and glTF structure. The pure-Python
`scene_metadata` contract additionally checks that v1 and v2 headers decode to the
same draws, that the v1 defaults are stated rather than inferred, and that the
exporter follows or refuses the declared convention.

Artifacts remain under `build/x86-vs/<configuration>/scene-*`: captures, raw BGR
images, `reference.png`, `replay.png`, `image-diff.json`, glTF and negative inputs.
See the CTest `LastTest.log` for the exact directory. All images are generated
from in-repo fixture geometry; no commercial assets are involved.

Full Phase 3 acceptance still requires a measured reference-game scene, broader
geometry/material/light extraction, cross-GPU checks and performance budgets.
