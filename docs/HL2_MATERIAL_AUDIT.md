# Exact HL2 material-path audit — 2026-09-08

Offline audit only; no game launch or runtime material admission.
`tools/audit_hl2_material.py` validates an immutable bounded inventory snapshot,
selects the exact successful VS/PS pair and disassembles in the existing bounded
CPU subprocess. It is an exact-program dependency audit, not a general shader
interpreter. Reproduce using `--disassembler .../rrt_shader_disassemble.exe --out
NEW_DIRECTORY` with either saved inventory below.

| Evidence | Original inventory | Multi-draw inventory |
| --- | --- | --- |
| Saved bundle under build/game-passes | hl2-inventory-20260907/runs/inventory | hl2-multidraw-20260907/runs/multidraw |
| Inventory draws | 2996 | 2957 |
| Successful exact-pair draws | 231 | 294 |
| Completion | byte_limit | byte_limit |
| Inventory SHA256 | f293fcc57a07ee029e482fbaff900e92e5b3ebd6b63c77687f7befc306f6d3a6 | db7fe896540d328f2bb432cf1f8b06ab30d29d6f9f21ae2faa173c5f1d5bb4ae |

Artifacts: `build/material-audit-20260908/multidraw/` and `original-debug/`, each
with audit.json, vs.asm and ps.asm. Release and Debug disassembly yield matching
program analyses. These inventory ordinals are **not** position-capture ordinals;
the streams lack a shared draw/session correlation contract. In particular, do
not label the16 saved position draws as having this material just from frequency.

Exact VS: `0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2`,
612 bytes, vs_2_0. Exact PS:
`ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11`,
1792 bytes, disassembler profile ps_2_x. Family:
`34a26bb21a5f97a014180fb48bad9200318f5109d55f7dee252b087f572391a5`.

## Required inputs

| Input | Observed dependency | Current gap |
| --- | --- | --- |
| Position | VS v0; c0, c4–7 produce clip position | Existing exact position contract |
| UV0 | VS v1 → oT0.xy → PS t0.xy | Read initialized stream0 float2 at byte28 |
| UV1 | VS v2 → oT2 using c0 → PS t2.xy | Read initialized stream0 float2 at byte36 |
| Vertex color | VS v3 → oD0 → PS v0 | Decode stream0 D3DCOLOR at byte24 with native equivalence control |
| Fog coordinate | VS position/c0/c12 → oT4.w → PS t4.w | Add VS c12; retain c16 for complete VS output/fog-state audit |
| Other VS outputs | c58–60 for oT4.xyz; c16 for oFog/oD1 | Existing position model rows; PS arithmetic here reads only t4.w |
| PS constants | c11,c12,c29,c30 | Capture effective rows with program/draw identity; embedded def c0–4 are shader-owned |
| s0 | Named BaseTextureSampler; one texld | Bound 2D resource, dimensions/format, initialized texels/mips, revisions, sampler and sRGB state |
| s1 | Named LightmapSampler; four texld | Same evidence; atlas/lightmap semantics and filtering require explicit qualification |

The recorded stream0 stride is48 bytes. The declaration also contains normal
and stream2 entries, but the exact VS declares only POSITION0, TEXCOORD0/1 and
COLOR0. Any omission must be justified by this pinned program's live inputs, not
by a broad assertion that other streams or normals never matter.

The PS reconstructs a weighted four-sample s1 result, multiplies it by c12.rgb,
s0.rgb and vertex RGB, scales by c30.x, then mixes toward c29.rgb using a squared
clamped factor derived from t4.w and c11. Output alpha is vertex alpha × c12.w ×
s0 alpha. Names and arithmetic support a base-texture/lightmap/fog interpretation;
they do not establish actual bound texture assets, formats or constant values.

Embedded constants include1024,512 and their reciprocals in the s1 coordinate
arithmetic. These are shader reference dimensions, **not measured bound dimensions**.
Resizing a presumed lightmap while retaining the bytecode may change filter/atlas
behavior. Do not treat s1 as ordinary base-color upscaling input.

## Implementation sequence

1. Completed in v11; see [POSITION_MATERIAL_INPUTS.md](POSITION_MATERIAL_INPUTS.md).
   Extend the pinned VS input/evaluator fixture with initialized UV0/UV1 and packed
   color, VS c12/c16, and explicit output lanes needed by the PS. Compare native
   interpolation with CPU-evaluated outputs using diagnostic PS controls, including
   channel order, alpha, perspective interpolation and malformed/uninitialized data.
2. Completed in v12; see [POSITION_PIXEL_MATERIAL.md](POSITION_PIXEL_MATERIAL.md).
   Capture the exact paired PS and four external PS rows in the same draw record.
   Record s0/s1 descriptors and sampler state; unknown texture contents stay unknown.
3. Bounded private managed mip capture completed in v13; see
   [POSITION_TEXTURE_INPUTS.md](POSITION_TEXTURE_INPUTS.md). Independent paired-PS
   reconstruction against captured/synthetic mips is now tested; see
   [PIXEL_MATERIAL_RECONSTRUCTION.md](PIXEL_MATERIAL_RECONSTRUCTION.md).
   Include address/filter/LOD/sRGB/alpha changes and failed/incomplete writes.
4. Expand real target/depth/composition scope only after those contracts pass.
   Request a guarded HL2 pass once correlated material evidence and useful replay
   can be collected in one launch. No gameplay pass is needed for the audit itself.

Enhancement work follows faithful capture/replay; see
[TEXTURE_ENHANCEMENT_ROADMAP.md](TEXTURE_ENHANCEMENT_ROADMAP.md).
