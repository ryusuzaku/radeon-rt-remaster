# Paired material state (v12)

V12 adds a bounded observation of the exact HL2 pixel shader paired with the
pinned vertex shader. It records constants, effective sampler settings and bound
2D texture descriptors. Texture contents remain explicitly unknown.

## Admission and record

Enable `--position-pixel-material` in the game-pass runner, or set
`RRT_POSITION_PIXEL_MATERIAL=1`. This requires v11 material inputs and the full
v10 prerequisite chain. The existing sampling, file and 1,024-triangle bounds
remain unchanged. No gameplay launch is needed for this implementation slice.

The shader in `color_replay.pixel_shader` must be exactly 1,792 bytes with SHA-256
`ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11`.
Embedded shader constants remain shader-owned. Four external rows, PS
c11/c12/c29/c30, must have known successful writes since knowledge invalidation.
Failed writes do not establish knowledge. Reset, state-block recording boundaries
and successful application invalidate knowledge; explicit successful writes can
restore it. Native getters supply the effective finite values at capture time.

An accepted draw adds `pixel_material`:

| Field | Meaning |
| --- | --- |
| `constants` | Four float4 rows in c11,c12,c29,c30 order; 64 little-endian bytes encoded as lowercase hex |
| `samplers` | Two entries in s0,s1 order |
| `samplers[].states` | 13 raw DWORD values in D3DSAMP enum order 1 through 13 |
| `samplers[].texture` | Bound 2D resource identity and descriptor observation |

Sampler order is address U/V/W, border color, mag/min/mip filter, mip LOD bias
bits, maximum mip level, maximum anisotropy, sRGB, element index and displacement
map offset. These values are observations, not a general sampler replay contract.

Each texture record contains a process/session-local `id`, resource `type=3`,
`levels`, current `lod`, `autogen_filter`, `contents="unknown"`, and `descriptors`.
Descriptors are arrays in mip order of width, height, format, usage, pool,
multisample type and quality. Capture admits at most 16 levels and dimensions
up to 16,384. Missing textures and non-2D bindings are rejected. Resource IDs do
not establish initialized bytes, texture revisions, alias relationships, asset
identity across sessions, or persistent source content.

Device setters and texture SetLOD/SetAutoGenFilterType carry overlap guards.
V12 rejects draws after an observed overlap, conservatively for the remaining
session. Existing unobserved-write and surface-scope limitations remain visible.
The Python reader validates the exact program, record shapes, constants, bounds,
mip dimensions and matching descriptors when the same resource occupies both
slots. Candidate import preserves the metadata without changing position assets
or admitting this PS to constant-color replay.

## Validation and limits

`rrt_shader_fixture --pixel-material` reads exact VS and PS hex on separate stdin
lines. It creates initialized patterned managed textures with distinct extents
and mip chains, varies constants/address/sRGB/LOD and swaps bindings. Native
original VS and CPU-evaluated passthrough vertices use the same original PS;
their outputs are compared over 24 draws. This verifies capture transparency and
the vertex path under the material, not an independent PS reconstruction.

Controls cover missing constants, failed constant writes, successful state-block
application, explicit refresh, absent textures, wrong PS, missing prerequisites,
and malformed or misleading metadata. The actual PS arithmetic, texture bytes,
write/alias tracking and full-frame equivalence remain unimplemented here.

Implemented in v13 (POSITION_TEXTURE_INPUTS.md): bounded initialized 2D texture/mip
provenance and texel capture, including
partial locks, failed writes, copies, generated mips and alias invalidation.
Then reconstruct the audited five-sample pixel path against synthetic patterns.
Request another HL2 gameplay pass when that evidence path and useful comparison
can run together. Texture enhancement remains in TEXTURE_ENHANCEMENT_ROADMAP.md.
