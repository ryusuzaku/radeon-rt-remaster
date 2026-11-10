# Third HL2 position contract: the 3348-byte skinned program

Exact vertex program SHA256:
`c3c0fcaab126f410ba5d7e63fe4215dc022535708d52ae18ccfa4d7ddbff4be2`, 3348 bytes.

In the 2026-11-10 gameplay frame it drew 48.8% of the triangles to the main target, in six draws of 92 to 3,421 triangles
([frame capture result](HL2_FRAME_CAPTURE_RESULT.md)). After the static-prop program
([its contract](HL2_FLEX_POSITION_CONTRACT.md)) it is most of what capture still refused. Admission is **position-only**, as for
the static-prop program: material capture refuses it as `unsupported_shader`.

## The position path

From the Windows SDK CPU disassembly (`tools/disassemble_inventory.py`):

```
def c4, 765.005859, 3.05175781e-005, ...   ; 765 + 3/512 and 2^-15, both exact in float32
dcl_position v0 ; dcl_blendweight v1 ; dcl_blendindices v2 ; dcl_position1 v5
add r1.xy, v1, c0.y
mul r1.xy, r1, c4.y                         ; two weights: (short + c0.y) / 32768
mul r2.xyz, v2.zyxw, c4.x
mova a0.xyz, r2.yxzw                        ; three palette offsets: 3 x the (G, B, R) bytes of the index colour
mul r3, r1.y, c60[a0.x]
mad r3, c60[a0.y], r1.x, r3
add r1.z, r1.y, r1.x
add r1.z, -r1.z, c0.y                       ; third weight: c0.y - (w1 + w0)
mad r2, c60[a0.z], r1.z, r3                 ; the same three-step blend for c58[a0] and c59[a0]
mov r6.w, v0.w
mad r6.xyz, v5, c3.x, v0                    ; the flex offset, as in the static-prop program
dp4 r2.w, r6, r2 ; dp4 r2.y, r6, r7 ; dp4 r2.z, r6, r1      ; model position in r2.yzw
...                                         ; four static light branches (b0..b3) read r2.yzw and write only r2.x
mov r2.x, c0.y
dp4 r0.x, r2.yzwx, c8 ; dp4 r0.y, r2.yzwx, c9
dp4 oPos.z, r2.yzwx, c10 ; dp4 oPos.w, r2.yzwx, c11 ; mov oPos.xy, r0
```

So each vertex blends three bones of `cModel[53]` (c58..c216) with weights `(w0, w1, c0.y - w0 - w1)` from two SHORT2 values,
applies the blended rows to `(v0 + v5 * c3.x, 1)`, and applies `cViewProj` to `(model, c0.y)`. The program also writes the model
position to `oT6.xyz`. Its normal, tangent, lighting, fog and texture-coordinate outputs are not covered.

## The evidence contract

Capture (`CaptureSkin` in `src/shader/position_capture.cpp`) admits a draw only when:

- the program is exactly these 3348 bytes (size, then SHA-256);
- the declaration has exactly one each of POSITION0 (FLOAT3, stream 0, offset 0), BLENDWEIGHT0 (SHORT2, stream 0),
  BLENDINDICES0 (D3DCOLOR, stream 0) and POSITION1 (FLOAT4, stream 2, offset 0); the weight and index offsets are recorded;
- streams 0 and 2 are bound to tracked buffers with frequency 1, stream 2 with stride 0 or 16..256 (both occur in the title:
  four of the frame's six skinned draws use stride 0, two have per-vertex flex with stride 28);
- c0, c3 and c8-c11 are known, and so are the three registers of **every bone a vertex reads**. Bones no vertex reads may be
  unknown. A colour byte above 52 (past `cModel[52]`) is refused as `bone_range`;
- every corner's position, weight, index and flex bytes were written while the proxy was observing.

The proxy now tracks all 256 float registers of `vs_2_0` instead of c0..c60, since the palette reaches c216.

The record is self-describing: `constant_rows: [0,3,8,9,10,11]`, a `bones` object with the palette offsets the draw reads and
their rows, a `blend` object with the weight and index offsets and eight bytes per corner, and the `flex` object of the static-prop
program. The reader's per-line bound rises from 1.2 MB to 4 MB: a 4,096-triangle skinned draw is about 1.7 MB of hex. The 16 MiB
ledger cap is unchanged.

## The numerical gates

- **Native oracle** (`--hl2-skin-position`, `src/shader/skin_position_fixture.inc`): the unmodified program on a HAL device with
  the title's exact declaration and a full 53-bone palette of distinct matrices; three distinct bones per vertex including bone 52,
  uneven weights; stride-0 and per-vertex flex; the four light branches off and on; a clip-z plane placed from the blended model
  positions so the near plane cuts every triangle. 24 variants, 4,270 covered pixels, maximum error 0 (RX 9070 XT, Release).
  Coverage is lower than for the other programs because the bones rotate the small test triangle; every variant still clears the
  100-pixel floor and must lose part of its triangle to the near plane.
- **Mutations** each fail the oracle: bone byte order swapped (`clip coverage mismatch`), the two weights swapped, the third weight
  computed from 1 instead of c0.y, the flex term dropped (`position interpolation mismatch`) and c11 used for clip z. As for the
  static-prop program, clip z is verified to clipping resolution only.
- **Negatives**: each fixed row unknown, a referenced bone row unknown or nonfinite, a byte past bone 52, nonfinite flex, a changed
  program byte; in capture, missing stream-2 evidence, material mode, unknown c3, c10 or a referenced bone register, and unwritten
  weight or index bytes. An unknown bone that no vertex reads is accepted.
- **Reader** (`skin_position_matches`): recomputes each corner from the recorded bones, weights, index bytes and flex value with the
  float32 allowance carried through the blend and both products; requires the recorded bone list to equal the bones the vertices
  read; cross-checks the weight and index offsets against the declaration.
- **Converter**: a skinned draw has no single world matrix, so its vertices are the reader-verified model positions under an
  identity world, with c8-c11 as the view-projection and c0.y required to be one. The reprojection gate is unchanged.

## Tests

- `hl2_skin_position` (`tests/verify_hl2_skin_position.py`, local evidence, uses `RRT_HL2_POSITION_INVENTORY`): the oracle, a
  changed byte refused, the fixture under the real proxy (four captured draws, stride 0 and 28, nine recorded bones each), and the
  reader refusing altered weights, an altered bone row, a vertex reading an unrecorded bone, a dropped bone, a wrong weight offset,
  a shortened row list and a missing bone object.
- `position_to_scene` gains a synthetic skinned check: a mixed scene, identity world and model-position vertices, a recorded clip
  position the gate refuses, and the c0.y refusal.

## Measured in game (2026-11-10)

Pass `build/game-passes/hl2-skin-20261110`, run `frame` (local), with the same options as the two earlier frame captures and the
proxy built from this change.

- The ledger reached its 16 MiB byte cap after 3 presents and 255 attempts: 116 captured draws (17 skinned, 81 static-prop, 18 of
  the first program), 109 `unsupported_shader`, 29 under the primitive minimum, **no evidence failures**. Every skinned draw passed:
  its bone registers were set and its buffers written while the proxy observed.
- Per complete frame: 18,745 attempted triangles, of which **13,520 were captured (72.1%)**: 7,912 skinned, exactly the share the
  inventory analysis predicted, 5,570 static-prop and 38 from the first program. The two earlier captures of this view got 38 and
  5,608.
- The reader accepts the ledger. The first frame converts into one scene of 39 draws (6, 27 and 6 of the three programs) under one
  camera: clip error 8.5e-6, shared-camera spread 0. `rrt_dxr` admits it, with geometry on 19.2% of pixels in albedo. A character
  standing on the walkway is drawn from skinned geometry in place among the static props. The transported frame's digest equals
  the standalone render.

## What this does not establish

- That every skinned draw in every scene passes: in this save, all did.
- What the model space of a skinned draw means: like the other programs, the model position's world-space meaning is unverified.
- Normals, lighting, texture coordinates or materials of these draws.
