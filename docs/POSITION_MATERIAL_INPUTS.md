# Pinned material vertex inputs (v11)

The opt-in v11 position ledger adds initialized inputs and selected outputs for
the exact 612-byte HL2 vertex shader identified in HL2_MATERIAL_AUDIT.md. It does
not admit arbitrary shaders or establish full material/frame equivalence.

## Contract

The existing position contract remains mandatory. Stream 0 must have stride 48,
with unique COLOR0 D3DCOLOR at byte 24, TEXCOORD0 float2 at 28 and TEXCOORD1 float2
at 36. Indexed corner position bytes and bytes 24 through 43 must be initialized
in the tracked buffer revision. Normal and padding bytes are not read by this
pinned program. Extra declaration elements do not extend shader admission.

VS c12 and c16 must have known successful writes since the last knowledge
invalidation, alongside the existing eight constant rows. State-block application
invalidates that knowledge. Nonfinite inputs or outputs are rejected.

Each accepted row has `material_inputs` with lowercase, little-endian hex blobs:

| Field | Contents |
| --- | --- |
| `constants` | c12.xyzw then c16.xyzw, 32 bytes |
| `uv` | input UV0.xy and UV1.xy per indexed corner, 16 bytes each |
| `color` | original packed D3DCOLOR per corner, 4 bytes each |
| `evaluated` | ten float lanes per corner, 40 bytes each |

The ten evaluated lanes are oT0.xy, oT2.xy, oD0.rgba, oT4.w and the raw scalar
written to oFog/oD1. Packed color decodes ARGB DWORD into normalized RGBA. With
`a=c0.x`, `b=c0.y`, the homogeneous input is
`q=(x*b+a,y*b+a,z*b+a,x*a+b)`. The last two lanes are
`distance=dot(q,c12)` and `max(c16.x-distance*c16.w,c16.z)`.
UV0 passes through; UV1 is multiplied by b. These are the selected outputs
required by the audited paired material, rather than all unused VS registers.

V11 limits each draw to 1,024 triangles to retain the existing bounded row size.
Existing limits of 16 accepted draws, four per present interval, and ledger byte,
attempt and presentation budgets remain in force. The independent Python reader
validates layout, shapes, finiteness, ranges and numerical output agreement.
The scene importer preserves material inputs as candidate metadata; its geometry
assets and correspondence rules remain position-only.

## Enabling and validation

The runner option `--position-material-inputs` requires
`--position-color-replay` and its full prerequisite chain. The corresponding
native switch is `RRT_POSITION_MATERIAL_INPUTS=1`; missing prerequisites disable
capture. This version inherits color/write/surface evidence without extending
the constant-color replay tool's admitted pixel program.

`rrt_shader_fixture --material-inputs` takes the exact VS hex on stdin. It compares
the original native VS against CPU-evaluated passthrough vertices using separate
UV, RGBA and distance/fog probes on a float render target. Twenty-four probes use
nonuniform clip W, distinct channels/alpha, UVs outside [0,1], varied constants
and a fog-floor case. The fog probe consumes the duplicate oD1 scalar; it does
not prove fixed-function fog application or oFog rasterizer behavior.

Tests reject missing initialized attribute bytes, unknown c12/c16, excessive draw
size, nonfinite/overflow values, legacy layouts and altered ledger evidence.
A deliberately incorrect CPU UV must fail GPU comparison. Proxy-backed runs
check successful v11 capture, state-block rejection and importer preservation.

## Next slice and gameplay gate

Completed in v12; see POSITION_PIXEL_MATERIAL.md: capture the exact paired PS
c11/c12/c29/c30 and effective s0/s1 sampler settings,
bound resource identities and texture descriptors with state-invalidation and
native failure controls. Then add initialized texture/mip provenance and texel
capture before implementing the audited five-sample pixel path. Another HL2
gameplay pass should wait until that bounded evidence path can answer a new
material question. Texture enhancement remains planned in
TEXTURE_ENHANCEMENT_ROADMAP.md, after faithful source replay.
