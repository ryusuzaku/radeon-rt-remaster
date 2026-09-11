# Captured material pixel comparison

The offline comparator restores a v13-v18 draw and runs the original pinned pixel
shader and an independently expressed HLSL reconstruction over the same original
vertex shader, mip bytes, constants and effective sampler settings. It compares
all float-render-target lanes, rather than screenshots or only a center pixel.
This is an isolated draw diagnostic, not composition or game-frame replay.

## Reconstructed arithmetic

`src/shader/reconstructed_pixel.inc` expresses the audited four-sample lightmap
path as a separable cubic B-spline filter. For fractional reference-grid position
f, its weights are `(1-f)^3/6`, `(3f^3-6f^2+4)/6`,
`(-3f^3+3f^2+3f+1)/6` and `f^3/6`. Pairing adjacent weights gives two sample
positions per axis and four texture samples. The reference scale remains
1024x512, as embedded in the original bytecode; it is not the texture extent.

The filtered lightmap multiplies base-texture RGB, vertex RGB, c12 RGB and c30.x.
The saturated minimum of `t4.w*c11.w-c11.x` and c11.z is squared and mixes the
lit result toward c29 RGB. Alpha is vertex alpha times c12.w times base alpha.
The reconstruction compiles as ps_2_b. Both shader implementations use native
D3D9 texture sampling; this is not an independent CPU sampling implementation.

## Running the comparison

From the workspace root:

```powershell
python tools/replay_pixel_material.py <completed-v13.jsonl> --fixture build/x86-vs/Release/rrt_shader_fixture.exe
```

Use `--ordinal N` to select one captured draw. Otherwise all captured draws are
compared. The input file is bounded and independently validated before payload
construction. The native helper accepts `--pixel-replay` with its bounded
`RRT_PIXEL_REPLAY1` stdin protocol, validates shader digests, dimensions, constants
and sampler bounds before GPU creation, and restores tight mip rows into managed
textures. The Python runner strips inherited RRT environment variables.

The report includes source SHA-256, per-draw error, coverage and both native pixel
hashes. A draw matches when every lane is finite, more than100 lanes are nonzero,
and maximum `abs(reconstructed-native)/(1+abs(native))` is <=2e-4. Hashes need not
match because small floating-point differences are expected. The report always
sets `ready_for_frame_replay=false`; its clear is diagnostic black and prior
draws, captured target contents and blend/depth composition are not replayed.

## Qualified subset

- Completed v13/v14 evidence for the exact pinned VS/PS pair; existing initialized
  private managed usage-zero format21/22 limits apply:64KiB inline in v13 or16MiB
  with v14 external assets (TEXTURE_ASSET_STORAGE.md).
- V15 adds initialized private managed usage-zero DXT1/DXT3/DXT5 block assets
  with the same16MiB chain budget (COMPRESSED_TEXTURE_QUALIFICATION.md).
- V16 admits proven whole-chain default-pool uploads (TEXTURE_UPLOAD_QUALIFICATION.md).
  Replay restores their bytes into managed diagnostic textures; it does not
  reenact the upload operation or default-pool lifetime.
- 128x96 float target and full viewport, depth/blend/alpha-test/stencil/fog off,
  no culling/scissor and the existing fixed raster subset.
- Wrap, mirror, clamp and border addressing; point/linear minification and
  magnification; none/point/linear mip filtering. Finite LOD bias within +/-4,
  valid texture LOD/max-mip, anisotropy1, sRGB0/1, element/displacement index0.

Captured sampler and texture LOD values are restored on both paths. Autogeneration
filter metadata has no sampling effect for the admitted usage-zero textures.
Unsupported states are reported as unqualified. No shader/capture admission or
stateful constant-color replay rule is relaxed by this tool.

## Evidence and next slice

Tests compare all16 captured fixture draws and four explicitly synthetic variants
with higher-frequency128x64 lightmaps and varied address/filter/mip/LOD/sRGB,
lighting, alpha and fog inputs. Negative controls alter fog, alpha, texels,
addressing, sRGB, LOD, magnification and the four-sample lightmap filter. A single
lightmap sample must visibly differ on the higher-frequency control. Malformed
payloads are rejected. Reports are saved beside fixture ledgers as
pixel-comparison.json and pixel-comparison-controls.json.

External asset storage is implemented in v14; compressed capture and native
restoration are implemented in v15 (COMPRESSED_TEXTURE_QUALIFICATION.md).
V16 adds whole-chain default-pool UpdateTexture evidence; v17 adds explicit
full-dirty proof (DIRTY_TEXTURE_QUALIFICATION.md). V18 adds explicit surface-copy
coverage (SURFACE_UPLOAD_QUALIFICATION.md). Next qualify game-sized diagnostic
target/raster scope. Another HL2 pass should wait
until capture can preserve those textures and this comparison can answer a new
material question. Full target/depth/composition scope remains a separate gate.
Future texture enhancement is planned in TEXTURE_ENHANCEMENT_ROADMAP.md.
