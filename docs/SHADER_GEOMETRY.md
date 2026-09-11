# Shader-aware geometry: HL2 evidence and next contract

Status: input audit, standalone snapshot/replay and opt-in proxy interception
implemented for the narrow fixture. HL2 shader geometry extraction is unimplemented.

## Implemented snapshot contract

`rrt_shader_fixture --fixture EXISTING_DIRECTORY` captures three real D3D9 draws
and writes `.rrshader` snapshots plus source pixels. `--replay SNAPSHOT PIXELS`
loads an artifact and reconstructs shaders, layout, buffers, constants and raster
state on a fresh device. CTest `shader_snapshot` compares exact pixels in fresh
processes and tests reset replay and invalid-input rejection.

The `rrt_shader_snapshot` library only admits its exact compiled VS3/PS3
matrix-row/color programs, one FLOAT3 position stream, INDEX16 triangle lists,
five known float constant registers, a bounded viewport and the declared simple
raster-state configuration. This is an allowlist, not arbitrary bytecode replay.
Targets are non-MSAA X8R8G8B8 backbuffers up to 512x512; buffers are at most 64 KiB
each, programs at most 4 KiB each, files at most 160,000 bytes and draws at most
4,096 triangles/declared vertices. Referenced position values must be finite.

`RRTSHD01` is a Windows little-endian v1 artifact with shader programs, declaration,
draw/range parameters, viewport, constants, copied initialized referenced bytes
and SHA256 integrity. Unreferenced bytes are zeroed rather than copied. Decode
validates budgets, digest, exact program/layout admission and arithmetic before
GPU creation. The fixture controls the initial clear; this is not a full-frame
capture format and stores no prior framebuffer, texture or material payload.

Capture queries actual native device state, but requires caller-supplied byte
initialization masks, resource identities and constant-initialization evidence.
The fixture tracks its own writes, including DISCARD invalidation. The proxy now
supplies evidence from native-resource-owned shadows and generation-keyed device
knowledge, rather than trusting pointer addresses as persistent identities.

## Opt-in proxy interception

Set `RRT_SHADER_SNAPSHOT_FILE` to a fresh local workspace artifact path and
optionally `RRT_SHADER_SNAPSHOT_DRAW` to a zero-based DrawIndexedPrimitive attempt
ordinal (0 by default, maximum 10,000). This selector is not a frame or trigger.
At the selected draw boundary the proxy snapshots supported input before the
native call, and commits only if that call succeeds. Rejected evidence/native
failure writes an exclusive `.rejected` sidecar; existing artifacts are never
overwritten. I/O failure does not change the native return value. A selection
never reached produces no artifact. `RRT_PROXY_DISABLE=1` bypasses this path.

Per-resource private-data shadows retain at most 64 KiB of bytes and a matching
initialization mask; global byte+mask retention is capped at 16 MiB. A successful
writable Lock/Unlock declares that lock range initialized; this observes API
ranges, not individual CPU stores. DISCARD invalidates prior knowledge; READONLY
does not initialize data. Failed Unlock and ProcessVertices invalidate evidence.
Shadows do not retain the native resource or device and expire with the resource.

At most 16 device-wrapper generations retain five constant-known flags. Successful
float constant writes establish knowledge outside state-block recording. Reset,
recording boundaries and wrapper retirement invalidate it. Any successful state
block Apply conservatively invalidates known constants for all tracked devices;
explicit refresh is required. This is safe rejection, not complete state-block
emulation. Native COM calls remain outside snapshot error propagation.

`shader_proxy` verifies oracle-identical intercepted artifacts and exact replay,
state-block/reset/retired-wrapper rejection and refresh recovery, partial DISCARD,
failed native draw, default-off/disabled behavior and output failure isolation.
No game-pass runner option enables this experiment yet; do not deploy it into HL2
expecting unknown programs, large backbuffers or arbitrary layouts to be accepted.

Tests include changed constants/geometry/subranges, unknown constants, missing
vertex/index initialization, actual partial DISCARD, resource replacement,
missing pixel shader, instancing, malformed program/layout, negative/overflowing
ranges, nonfinite constants, corrupted/truncated/trailing files, oversized counts
with a recomputed digest, exact serialization roundtrip and post-reset replay.

## Observed evidence

`tools/inspect_trace.py TRACE --shader-profile` reports only observed successful
events. Missing draw flags remain unknown in this profile (the older aggregate
fixed/shader counters retain their existing behavior). Constant payload lengths
are checked, but completeness of an update does not imply complete device state.

| Sample | Indexed draws | Vertex-only | Vertex + pixel | Float constant updates |
|---|---:|---:|---:|---:|
| HL2 default gameplay, 82 presents, byte limit | 28,633 | 820 | 27,813 | 85,617 |
| Requested level 70 / stored 80, 60 presents | 11,424 | 0 | 11,424 | 21,922 |

All observed float updates have full declared payloads. Neither triggered sample
includes shader or declaration creation events. Bindings/IDs cannot recover their
contents. Every draw uses a vertex shader, so supporting pixel shaders alone will
not unlock fixed-function vertex extraction. These samples are not synchronized
benchmarks; do not compare draw counts as a performance result.

## Next HL2 admission gate

Inventory actual HL2 program/declaration families in a separate bounded diagnostic
mode before expanding replay admission. Keep unknown programs out of the accepted
snapshot path; no skinning, instancing, vertex-texture fetch or feedback yet.

Snapshot provenance must include exact vertex shader bytecode, declaration,
stream offset/stride/frequency, index format/range/base vertex, initialized source
buffer bytes, the complete referenced constant state, viewport and draw arguments.
Capture at the draw boundary, not by guessing state at trigger time. Retain
explicit byte/count budgets and fail closed on unsupported or undefined input.
The supported shader profile and bytecode lengths must be validated before copy.

Standalone and intercepted replay now match the fixture, including changed
constants and buffer subranges. New program/layout support must retain these
acceptance gates, not merely rely on successful driver shader creation.

Only after that gate should real HL2 shader/declaration families be inventoried
with bounded snapshots. Shader output in clip space is not automatically world
geometry: camera/world transform identification, skinning and material semantics
need separate validated contracts before DXR import. Do not infer matrices merely
from likely constant-register positions.

## Cleanup

The separate [shader inventory](SHADER_INVENTORY.md) diagnostic is implemented.
It records unknown programs as opaque evidence only. Actual HL2 families still
need a triggered game sample before selecting an extraction contract.

Both HL2 gameplay runs exited normally and their owned bin proxies were removed.
The experiment's graphics feature setting was restored from 80 to its original
95 with HL2 closed. An unrelated audio-volume config change was preserved.
