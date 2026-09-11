# HL2 bounded multi-draw result — 2026-09-07

The selected v5 position capture completed and replays consistently in Release
and Debug. This is narrow shader-aware position validation, not live relighting,
material reconstruction or complete scene capture.

## Evidence

- Bundle: `build/game-passes/hl2-multidraw-20260907`.
- Source SHA256: `dd0ef91fffbee117c325ffd4781a433c5f1743384a6a99bdd3655687262d2302`.
- Session: `7735b19442b3ccabf3f47880543e87d9`.
- Selection: target5120x1440, minimum3 triangles, exact pinned vertex shader.
- Accepted16 draws from524 attempts, four each at intervals207–210, reset epoch0.
- Four position-content blocks contain3/35/4/6 triangles respectively and repeat
  in each interval.192 triangles were submitted across the samples; this does not
  mean192 unique triangles or16 game objects.
- Rejections:172 minimum-count,199 unsupported-shader,137 target-size mismatches.

## GPU position replay

Each sample uses its recorded positions and constants on a fresh diagnostic
128x96 native raster device. Both configurations produce the same results:

| Position block | Triangles | Covered pixels across four intervals |
|---|---:|---|
| First | 3 | 0,0,0,0 |
| Second | 35 | 2368,2345,2309,2319 |
| Third | 4 | 112,110,110,110 |
| Fourth | 6 | 496,591,602,616 |

All comparisons have exact coverage agreement and zero normalized model-output
error. Twelve samples are visible diagnostic matches. Four are empty on both
paths and **not** visible validation. Positive clip-W alone did not guarantee
coverage: all recorded corners had positive W, including the empty block.

Reports are `reconstructed/gpu-release-after-exit.json` and
`reconstructed/gpu-debug-after-exit.json`. Per-draw input/model-output OBJ exports
and a manifest are in the same directory; no cross-draw semantic merge is made.

## Temporal interpretation

c0 and model rows are identical throughout this capture. Clip rows are identical
within each interval and differ across its four intervals. Thus the evidence
contains stable position content with changing clip transforms, and the GPU
oracle preserves the resulting coverage changes. It does not establish that the
cause was camera motion rather than another view/projection change, nor that
matching geometry/resource IDs are stable engine-object IDs.

## Game safety and next step

HL2 exited0 after124.297s. Its executable was unchanged; the runner removed its
temporary bin/d3d9.dll and absence was independently verified. Trace completed
at60 presents:138309 events,8131 shader draws,zero failed calls. Inventory reached
its byte limit with2957 draws,74 programs,48 families,zero failed or unavailable
queries. GPU replay ran only after game exit.

Next, use these saved inputs for a bounded multi-draw, per-interval scene replay
with explicit view grouping and identity assumptions. Verify composition and
transform handling offline before asking for additional game captures or feeding
these candidates into the live renderer. Materials, normals, skinning, broader
shader coverage and continuous scene identity remain separate work.
