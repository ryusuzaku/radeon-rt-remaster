# Game-sized isolated material comparison

`tools/replay_pixel_material.py --normalized-material` preserves the captured
target width/height and viewport, including XY offsets and depth range. It compares
the pinned original PS against the independent reconstruction using the original
VS, captured constants, vertices, texture bytes and admitted sampler settings.
Strict mode remains the default: 128x96 float target and fixed raster state.

The diagnostic uses a fresh A32B32G32R32F target without multisampling or a depth
attachment. It clears the entire target before setting the captured viewport.
Depth, alpha test, blend, stencil, sRGB output, scissor, culling, fog, dithering,
clip planes, line AA and N-patches are disabled. Fill is solid, clipping enabled,
all color lanes and samples enabled, and depth biases zero. Each report includes
the captured target/render state and the explicit comparison settings. Source
target format, multisampling, attachment history and composition are not replayed.
Sampler sRGB decoding remains captured; output sRGB conversion is disabled.

This is a material diagnostic, not a prediction of the game's final image.
Normalization can expose fragments that game depth/culling would hide. Float
output avoids source-format quantization. Pixel extent and viewport are retained
without resizing or tiling, so the diagnostic does not introduce a new UV scale.
`ready_for_frame_replay` remains false. Empty/near-empty outputs cannot pass the
existing minimum nonzero-lane check even when both outputs agree.

## Bounds and compatibility

Native payload RRT_PIXEL_REPLAY2 carries width, height and six viewport DWORDs
before the existing pinned shader/material payload. Both Python and native code
require dimensions 1..8192, at most 8,000,000 pixels, a nonempty in-bounds viewport
and finite ordered depth range within [0,1]. Native checks happen before device
creation. Version 1 remains supported with its original fixed viewport.

At the pixel limit, two CPU float images plus GPU target and system-memory
readback account for roughly 512 MB of raw image storage, excluding driver
overhead and textures. Hardware/resource allocation failure fails the diagnostic;
it never silently downscales. Readback pitch is validated. The image hash has its
own bounded input path; scene-file hash and storage budgets are unchanged.
Capture schema remains v18; no resource or composition admission was relaxed.

## Qualification and next gameplay pass

Release6/6 passed202.39s and Debug2/2 passed72.34s. At5120x1440 the maximum
normalized error is2.79876e-8; offset viewport2.11298e-8. Native changed-texture
controls differ; strict/normalized128x96 image hashes agree. Eight native and
four Python invalid-scope cases reject. Release report: `scope-comparison.json` in the `texture-scope-*` directory that
`ctest --test-dir build/x86-vs -C Release -R '^texture_scope$'` creates. The
directory suffix is random per run, so the artifact is identified by name and by
the test that regenerates it rather than by a path that goes stale immediately.

`texture_scope` creates fresh material evidence from the pinned local shader
inventory. It checks strict/normalized hash identity at 128x96, matching original
and reconstructed material at 5120x1440 and at an offset 320x240 viewport, changed
texture mismatch controls, and Python/native malformed-bound rejection.

Saved `hl2-multidraw-20260907` evidence confirms target [5120,1440,21,0] and viewport
[0,0,5120,1440,0,1]. Its v5 records lack UV/color/pixel constants and texture bytes;
fixture comparisons at that extent do not establish real-game material fidelity.

Another targeted HL2 gameplay pass is now useful after qualification passes.
Use a fresh reversible game-pass bundle, the existing provenance/baseline workflow,
and the full v19 flag chain through `--position-surface-locks`, with selection
`2560x1440:3`, multi-draw sampling and shader inventory. Capture a short repeatable
scene using the previously successful route. Keep the bounded capture defaults.
After normal exit and verified proxy cleanup, inspect the ledger/assets and run:

Superseded 2026-09-11: this recommendation originally named the v18 chain through
`--position-surface-uploads` and `5120x1440:3`. Surface locks are required to keep
the upload proof (SURFACE_LOCK_QUALIFICATION.md), and the observed 2560x1440 target
is the one that actually matches (HL2_MATERIAL_V18_RESULT.md).

```powershell
python tools/replay_pixel_material.py <capture.jsonl> --fixture build/x86-vs/Release/rrt_shader_fixture.exe --normalized-material
```

If no complete material draws are admitted, inspect rejection and shader evidence
before choosing another implementation slice. Partial UpdateTexture, unobserved
initialization, unsupported samplers and dynamic/direct-default writes remain
possible limits. Do not infer missing texture bytes or weaken admission to obtain
a pass. Texture upscaling remains a later reversible offline step in
`TEXTURE_ENHANCEMENT_ROADMAP.md`.
