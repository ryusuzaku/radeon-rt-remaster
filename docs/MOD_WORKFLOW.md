# Offline asset replacement

Phase 4's first creator workflow operates on captured `.rrscene` files. It
extracts editable assets, validates mods, resolves stable-ID matches, and writes
a **new self-contained scene** for the existing native replay viewer or glTF
exporter. No game installation, original capture, or live rendering is changed.

## Working example: replace the fixture's static mesh

From the repository root, after a Release build:

```powershell
$modRun = [guid]::NewGuid().ToString()
$scenePath = Join-Path $PWD "build\source-$modRun.rrscene"
$editPath = Join-Path $PWD "build\edit-$modRun"
$outputPath = Join-Path $PWD "build\modified-$modRun.rrscene"
$env:RRT_SCENE_FILE = $scenePath
$env:RRT_SCENE_FRAME = '0'
try {
    .\build\x86-vs\Release\d3d9_smoke_sample.exe --scene-fixture
} finally {
    Remove-Item Env:\RRT_SCENE_FILE
    Remove-Item Env:\RRT_SCENE_FRAME
}
python tools\mod_scene.py extract $scenePath $editPath
$inventory = .\build\x86-vs\Release\rrt_replay.exe $scenePath --inspect | ConvertFrom-Json
$meshId = $inventory.draws[2].mesh_id
Copy-Item examples\mods\small-triangle.json (Join-Path $editPath 'small-triangle.json')
python tools\mod_scene.py make --kind mesh --target $meshId --asset small-triangle.json --id small-triangle --output "$editPath\mesh-mod.json"
python tools\mod_scene.py check $scenePath --mod "$editPath\mesh-mod.json"
python tools\mod_scene.py apply $scenePath --mod "$editPath\mesh-mod.json" --output $outputPath
.\build\x86-vs\Release\rrt_replay.exe $outputPath --show
```

The two right-hand fixture draws share that mesh ID, so **both** receive the
replacement. Their original transforms, cameras and scissor rectangles remain
intact. Asset matching is not draw-instance selection.

`extract` creates a new directory containing:

- `catalog.json`: mesh/texture IDs, paths, checksums and draw usage; material IDs
  and original render/sampler state for inspection.
- `textures/*.png`: editable texture pixels.
- `meshes/*.json`: editable object-space triangle geometry.
- `mod.json`: a runnable identity replacement for the first texture. Applying
  this unchanged starter produces a byte-identical scene.

To change a texture, edit its PNG with an image editor, save as non-interlaced
8-bit RGB/RGBA, then use `make --kind texture --target ORIGINAL_TEXTURE_ID
--asset textures/FILENAME.png --id my-texture --output NEW_MANIFEST.json`.
The asset path is relative to the **new manifest's parent directory**. The `make`
command computes a fresh file checksum; stale checksums fail validation.

For a material example, copy `examples/mods/linear-material.json` into the editing
directory and use `make --kind material` with the original material ID. Apply
multiple manifests by repeating `--mod`. Do not combine the identity starter and
a new replacement for the same texture at the same priority: that is a conflict.

`check` performs the same full resolution and output validation as `apply`, but
writes nothing. Both print a JSON report with source/output SHA-256 values,
manifest digests, matched draw ordinals, replacement provenance, resulting asset
IDs, unmatched targets and overridden entries. Shell-redirection of that report
is optional. The report is not embedded in the scene format.

The modified scene can also be exported with `tools/export_gltf.py`. It no longer
depends on the mod folder to replay; later asset edits require applying the mod
again to the original capture.

## Manifest v1

The machine-readable shape is in [mod-v1.schema.json](schemas/mod-v1.schema.json).
The runtime additionally checks dependency contents, paths, uniqueness and limits.

```json
{
  "schema": "rrt-mod",
  "version": 1,
  "id": "my-texture",
  "priority": 10,
  "replacements": [
    {
      "kind": "texture",
      "target": "ORIGINAL_64_CHARACTER_LOWERCASE_SHA256",
      "asset": "textures/replacement.png",
      "sha256": "SHA256_OF_THE_REPLACEMENT_FILE"
    }
  ]
}
```

The two placeholder hashes above must be replaced; use `make` to create a valid
one-entry manifest. Multi-entry manifests are editable JSON with the same shape.
Unknown fields, duplicate JSON keys, nonfinite numbers, booleans in integer
fields, unknown versions and duplicate `(kind, target)` entries are errors.

Resolution rules:

1. Match every entry against **original capture IDs**. Texture, mesh and material
   modifications cannot prevent one another's original-ID matches.
2. For each `(kind, target)`, the highest manifest priority wins. Priorities are
   integers from −1,000,000 to 1,000,000; larger means higher precedence.
3. Any equal-priority overlap is an error, even if another higher-priority entry
   would win. Duplicate mod IDs are errors. CLI argument order never breaks ties.
4. A winning material entry is a patch over captured state. Fields from losing
   material entries are **not** merged into it. Even losing dependencies must be
   present, hash-correct and valid.
5. Unmatched IDs fail by default. `--allow-unmatched` records them and applies
   the matching entries; it does not guess substitutes from filenames.
6. Incomplete captures fail by default. `--allow-partial` is diagnostic only;
   the resulting scene retains its rejection records and remains incomplete.

All instances sharing an ID change. IDs describe payload content, not a persistent
game-object identity: an animated texture update has a different ID, while an
unchanged static mesh survives resource recreation/Reset. Material IDs include
the captured texture ID, so updated texture content can also change material IDs.

## Replacement payloads

### Texture: PNG

Non-interlaced 8-bit RGB or RGBA, maximum 2048×2048. All five PNG scanline filters
are supported. Alpha is preserved; RGB receives alpha 255. Palette, grayscale,
16-bit, APNG, `tRNS` and unknown critical chunks are rejected. Compressed-stream
lengths, chunk CRCs, dimensions and end-of-file are validated before use.

Pixels are imported literally, with no colour-profile/gamma conversion. Render
and sampler sRGB flags remain captured state. Save an ordinary RGB/RGBA PNG and
check the preview rather than assuming colour-managed editing is equivalent.

### Mesh: JSON v1

```json
{
  "version": 1,
  "vertices": [
    [-0.35, -0.35, 0.5, 4294967295, 0.0, 1.0],
    [0.0, 0.35, 0.5, 4294967295, 0.5, 0.0],
    [0.35, -0.35, 0.5, 4294967295, 1.0, 1.0]
  ],
  "indices": [0, 1, 2]
}
```

Vertex layout is `[x, y, z, argb_uint32, u, v]`, in captured D3D9 object space,
not glTF's converted coordinate convention. Values must fit finite float32;
indices are zero-based triangle lists. Limits are 500,000 vertices and 1,500,000
indices, within the overall file/output limits. Meshes contain no normals,
skinning, animation or lights in this first slice.

### Material: JSON v1 patch

`version: 1` plus at least one of these fields:

| Field | Values / meaning |
|---|---|
| `min_filter`, `mag_filter` | `point` or `linear` |
| `address_u`, `address_v` | `wrap`, `mirror` or `clamp` |
| `double_sided` | Boolean; true disables culling, false explicitly selects D3D9 CCW culling |
| `alpha_mode` | `opaque`, `blend` or `mask` |
| `alpha_cutoff` | Integer 0–255; requires `alpha_mode: mask`, defaults to 128 |

Opaque disables alpha test/blending. Blend disables alpha testing, uses
SRCALPHA/INVSRCALPHA with ADD, and disables separate-alpha blending. Mask disables
blending and uses GREATER_EQUAL alpha testing. Omitted fields retain the source
state. This is a fixed-function patch, not a PBR or arbitrary-shader material.

## Safety and bounds

- Input captures are read-only. Outputs and editing directories must be new;
  existing paths are never replaced. Parent directories must already exist.
- Asset paths must remain within the manifest directory after resolution.
  Absolute paths, URLs, `..`, backslashes, drive/stream syntax and symlink/junction
  escapes are rejected. Dependencies are local data, never executable hooks.
- A manifest is at most 1 MiB with 256 entries; at most 32 manifests per run.
  Each dependency file is at most 20 MiB. Combined dependency file bytes plus
  decoded texel/geometry payload accounting are capped at 64 MiB.
- Output scenes retain the 64 MiB scene cap. Extraction is capped at 64 MiB and
  each editable asset must fit the dependency-file limit. These are data budgets,
  not a guarantee that Python's total resident memory is below 64 MiB.
- Validation finishes before output files/directories are created. A disk-write
  failure can leave a new partial output, but never alters the source. Scene
  integrity checks reject truncated output.
- SHA-256 provides integrity and reproducibility, not mod-author authentication.
  This is local tooling, not a sandbox/security boundary for hostile inputs.

## Verification and remaining work

CTest includes offline validation plus classic D3D9 and D3D9Ex GPU mod tests.
Texture, static mesh and material changes are tested independently and together;
unmatched draw data and unaffected quadrants must remain byte-identical. Tests
also cover no-op byte identity, repeated captures, CLI-order independence, mesh
matching after Reset, unmatched dynamic texture IDs, path escapes, checksum
failure, PNG bounds/filters and preservation of existing outputs.

Artifacts are retained in `build/x86-vs/<configuration>/mods-*`, including
manifests/assets, modified scenes, PNG previews, glTF and `isolation-report.json`.

Live game replacement, GUI authoring, light/PBR overrides, broader capture
formats, reference-title qualification, D3D12/DXR and FidelityFX remain later work.
