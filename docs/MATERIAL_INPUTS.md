# Static material and light inputs

The standalone DXR viewer accepts an optional `.rrmat` sidecar keyed by the
SHA-256 material IDs already present in a complete `.rrscene`. This does not
change the capture, raster replay, scene-v1 format or existing offline mod files.
Omitting the sidecar preserves the legacy shading path. An empty sidecar does too.
Every material listed in a sidecar explicitly opts into the new shading model,
even when its factors use their defaults.

## Authoring

Use the final scene that you intend to render (after applying any mesh/texture
mods). Changing texture or fixed-function material state changes the material ID.

```powershell
python tools/material_inputs.py template capture.rrscene --output materials.json
# Edit materials.json; remove records that should keep legacy shading.
python tools/material_inputs.py compile capture.rrscene --input materials.json --output materials.rrmat
.\build\x64-renderer\Release\rrt_dxr.exe capture.rrscene --materials materials.rrmat --mode gi --samples 64 --temporal --denoise --interactive
```

Both authoring commands create new files only. Neither overwrites the capture
or an existing output. The compiler reads data, not executable plugins or remote
dependencies. Inputs are strict JSON: duplicate keys, unknown fields, booleans
in numeric fields, nonfinite/out-of-range numbers, duplicate IDs and unmatched
IDs are errors. JSON input is capped at 2 MiB and records at 4,096. Renderer scene
admission limits still apply independently. No partial-scene opt-out is supplied.

The top-level object has exactly `schema: "rrt-materials"`, integer `version: 1`
and a `materials` array. Each record requires `target`, a lowercase 64-character
material ID from the template; other fields are optional:

| Field | Default | Allowed values / meaning |
|---|---|---|
| `base_color` | `[1,1,1]` | Three factors in 0..1, multiplied by captured texture × vertex RGB |
| `roughness` | `1` | Perceptual roughness in .05..1; GGX alpha is roughness squared |
| `metallic` | `0` | Metal/dielectric interpolation in 0..1 |
| `emissive` | `[0,0,0]` | Additive RGB radiance in 0..32 per channel; not multiplied by albedo |

One ID applies to every draw carrying that ID. Targets are not draw ordinals or
frame numbers. All listed targets must match; unrelated unused records are errors.
Sidecars can be reused with other captures containing the same material IDs.
The compiler sorts records deterministically. The renderer independently validates
the binary checksum, structure, target ordering, matching and numerical ranges.

Material inputs are immutable for the renderer lifetime. Recreate the renderer
with a new sidecar to change them; there is no hot-reload or in-game editor yet.

## Lighting and shading

`--light X Y Z` remains the direction toward the directional light.
New options apply to both legacy and PBR surfaces:

| Option | Default | Range |
|---|---|---|
| `--light-color R G B` | `1 1 1` | Each channel 0..1 |
| `--light-intensity N` | `.85` | 0..32 |
| `--ambient N` | `.15` | 0..32 |

The scene clear/background RGB is independent of these settings. These are
prototype radiometric scales, not calibrated lux or exposure values. Directional
intensity scales incident lighting; ambient controls the legacy fill and the
constant environment returned by diffuse rays that miss the scene. PBR `relit`
uses a simple diffuse ambient approximation, not environment-map specular lighting.

For opted-in surfaces, `relit` uses GGX microfacet distribution, height-correlated
Smith visibility, Schlick Fresnel with dielectric F0=.04, and a Fresnel-weighted
Lambert diffuse term. Metalness interpolates dielectric and metallic reflection.
Directional shadow queries remain enabled unless `--no-shadows` is selected.
`gi` samples the existing soft directional light and adds one cosine-sampled
**diffuse-only** bounce. Secondary surfaces contribute direct lighting and emission;
pure metallic primaries have no diffuse bounce. Emissive geometry is found only
when a sampled ray hits it: no emissive-light sampling/MIS is implemented.

`albedo` displays tinted base colour without lighting/emission. `normals` remains
the geometric-normal diagnostic. Surface guide albedo includes the tint. Raw and
temporal lighting retain float32 HDR values; the existing 8-bit display/export
clamps them. There is no tone mapper, automatic exposure or HDR scanout.

This is an opt-in shading prototype, **not full physically based path tracing**:

- Captured RGB is still literal, with no sRGB-to-linear conversion. Factors and
  light/emission values use that working space. No glTF conformance is claimed.
- Normals are flat geometric normals; no normal/roughness/metalness maps, tangents,
  transmission, clear coat, specular indirect rays or multi-bounce transport.
- A roughness floor avoids the singular mirror limit. No multiple-scattering
  energy compensation or firefly clamp has been added.
- Existing spatial/temporal filtering is not specifically qualified for sharp
  moving specular highlights. RRTSIG02 is unchanged and does not yet export
  roughness/metalness/emission guides needed by later reconstruction integrations.

The mathematical choices follow the [Khronos BRDF discussion](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#appendix-b-brdf-implementation)
and [Filament material model](https://google.github.io/filament/main/filament.html#materialsystem).
This implementation does not import either engine's shader source.

## Ownership, diagnostics and verification

Factors extend the existing GPU draw record from 48 to 84 bytes, uploaded once;
the 224-byte frame constants still fit each existing 256-byte submission slot.
No additional full-frame buffers or acceleration-structure rebuilds are needed.
The unchanged per-resource and aggregate allocation caps remain enforced.

Lighting changes reset raw and temporal lighting. Colour values participate in
the history key even when both the old and new colours are non-white. Unchanged
inputs retain history; the diagnostic `--lighting-test` checks this with temporal
GI and at least two samples, without forced resets or new GPU allocations.

The final JSON reports `pbr_draws`, `material_records`, `material_sha256` (whole
sidecar bytes; empty string if absent), `light_color`, `light_intensity`, and
`ambient`. Existing renderer/presentation counters and signal layouts are unchanged.

`material_inputs` is a CPU-only CTest entry for strict authoring, canonical encoding,
edge values, scene matching and overwrite protection. `dxr_materials` compares GPU
direct lighting with an independent double-precision BRDF reference, verifies
per-ID/localized tint, shadows, HDR emission, diffuse transport, metal suppression,
light-history invalidation, native/headless parity and malformed binary rejection.
Its retained artifacts live in `materials-*`. Tests use synthetic scenes, not
commercial-game captures, and do not establish performance or general material quality.
The suite also repeats full-HD temporal/spatial GI with two opted-in materials,
comparing exact pixels and enforcing the original 512 MiB requested-allocation cap.
Those larger runs omit full diagnostic dumps to keep test disk use bounded.

Recorded RX 9070 XT evidence: `build/x64-renderer/Release/materials-5869_ix8/verification.json`.
All nine renderer/authoring entries pass in x86/x64 Debug/Release. Numerical
direct-light error on the normal/angled/tangent reference grid is below 2.64e-7
using `abs(GPU - CPU) / max(1, abs(CPU))`; tilted-view agreement is also checked.
All 53 historical default files match in
`build/x64-renderer/Release/temporal-fo40zxcb/verification.json`. The full legacy
D3D9 suites were not rerun here; the previously recorded occluded-Present issue
remains an independent acceptance caveat.

## Binary format: RRTMAT1

All numbers are little-endian; no implicit padding or trailing bytes are permitted.

| Offset | Contents |
|---|---|
| 0 | 8 bytes: `RRTMAT1` followed by zero |
| 8 | uint32 version = 1 |
| 12 | uint32 record count, 0..4096 |
| 16 | Records, each 64 bytes: 32-byte material ID then eight float32 values |
| `16 + 64 * count` | 32-byte SHA-256 of all preceding bytes |

Record floats are base R/G/B, roughness, emissive R/G/B, metallic, in that order.
IDs must be strictly increasing in byte order. File size is exactly
`48 + 64 * count` bytes, at most 262,192 bytes. The checksum detects corruption;
it is not a signature or an assertion that untrusted content is safe.
