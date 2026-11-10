# Second HL2 position contract: the 1420-byte static-prop program

Exact vertex program SHA256:
`a84edfd28843f7c8aeac78bcb48c03184326c007593e8d49e99777c8cf1f11dc`, 1420 bytes.

It is the most frequent vertex program in all 18 local HL2 inventories (228 to 810 draws each). In the 2026-11-10 gameplay frame
it draws 34.4% of the triangles to the main target; the first admitted program draws 0.3%
([frame capture result](HL2_FRAME_CAPTURE_RESULT.md)). It was recorded as skinned on 2026-10-20; it is not.

Admission is **position-only**. Material capture refuses the program as `unsupported_shader`: its texture, colour and lighting
inputs are a different layout from the first program's and have no contract.

## The position path

From the Windows SDK CPU disassembly (`tools/disassemble_inventory.py`), the instructions that produce the position:

```
mov r0.w, c0.y
mov r1, v0                    ; dcl_position v0  (FLOAT3, so r1.w = 1)
mad r1.xyz, v4, c3.x, r1      ; dcl_position1 v4, cFlexScale
dp4 r0.x, r1, c58             ; cModel[0]
dp4 r0.y, r1, c59
dp4 r0.z, r1, c60
dp4 oPos.z, r0, c10
dp4 r1.x, r0, c8              ; cViewProj
dp4 r1.y, r0, c9
dp4 r1.w, r0, c11
mov oT7, r0                   ; after r0.w = dot(r0, c13); oT7.xyz is the model position
mov oPos.xyw, r1
```

So `r1 = (v0 + v4 * c3.x, 1)`, `r0 = (cModel[0] * r1, c0.y)` and `clip = cViewProj * r0`. The program declares the shared
`cModel[53]` table but uses no `mova` and no relative addressing: it reads `cModel[0]` only. The other 46 slots compute the
normal, tangent frame, fog, texture coordinates and colours, which this contract does not cover.

## The evidence contract

Capture (`src/shader/position_capture.cpp`, `CaptureFlex`) admits a draw only when all of these hold:

- the bound program is exactly these 1420 bytes (size, then SHA-256);
- the declaration has exactly one POSITION0, FLOAT3 at offset 0 of stream 0, and exactly one POSITION1, FLOAT4 at offset 0 of
  stream 2. The title's declaration (783 of 783 draws) also carries a UBYTE4 normal and tangent, a texture coordinate, a stream-1
  colour and a stream-2 FLOAT3 normal, which the position does not read;
- streams 0 and 2 are bound, frequency 1, to buffers the proxy tracks; stream 2 has stride 0 (one flex value for the whole draw,
  which is how the title binds it in every observed draw) or 16..256 (one per vertex);
- c0, c3, c8-c11 and c58-c60 were set since the last reset or state-block boundary;
- for every corner, the 12 position bytes and the 16 flex bytes were written while the proxy was observing, as for the first
  program. Buffers filled before the proxy loaded are refused as `uninitialized_bytes`, never guessed.

The ledger record is self-describing, as the second pixel program's is, so the capture-version ladder is unchanged: `shader`
holds 1420 bytes, `constants` holds nine rows with `constant_rows: [0,3,8,9,10,11,58,59,60]`, and a `flex` object holds the
stream-2 offset, stride, buffer size and one 16-byte value per corner. A reader that predates this program refuses such a
record as `program identity`.

## The numerical gates

- **Native oracle** (`--hl2-flex-position` in `rrt_shader_fixture`, `src/shader/flex_position_fixture.inc`). The unmodified program
  runs on a HAL device with hardware vertex processing and the title's exact declaration; a diagnostic pixel shader exports
  oT7.xyz. A second draw passes the CPU evaluator's clip and model results through a trivial program. 24 variants cover stride-0
  and per-vertex flex, varied c0.y, flex scale, matrices, stream offsets and base vertices. Coverage must match exactly and every
  component within `abs(native-cpu)/(1+abs(cpu)) <= 2e-4`. Result on an RX 9070 XT, Release: 32,458 covered pixels, maximum error 0.
- **What the oracle resolves.** Model x, y, z are compared directly and clip x, y, w through where each pixel lands. Clip z only
  shows through clipping, so every variant places the near plane through the triangle and the test requires that part of it was
  cut. Mutation runs confirm the gate: dropping the flex term fails (`position interpolation mismatch`), forcing the model w to
  one fails, and using c11 for clip z fails (`clip coverage mismatch`). **A 1% error in clip z passes**: it moves the clipped edge
  by less than a pixel. Clip z is verified to clipping resolution, not to the 2e-4 tolerance.
- **Negatives.** Each of the nine constants unknown, nonfinite inputs, overflow and a changed program byte are refused by the
  evaluator. Standalone capture refuses missing stream-2 evidence, material mode, a stream-2 resource mismatch, an unwritten flex
  byte, unknown c3, c8, c11 or c58, and an unbound stream 2.
- **Reader** (`tools/inspect_position_capture.py`, `flex_position_matches`). Recomputes every corner in double precision with the
  float32 allowance carried through both products, and checks the flex buffer range, the row list and the declaration.
- **Converter** (`tools/position_to_scene.py`). Folds the flex value into the vertex (`p + flex * c3.x`), uses the model rows as the
  world matrix and c8-c11 directly as the view-projection, requires c0.y to be one, and keeps the existing reprojection gate. Draws
  of both programs under one view share a scene.

## Tests

- `hl2_flex_position` (`tests/verify_hl2_flex_position.py`, local evidence, uses `RRT_HL2_POSITION_INVENTORY`): the native oracle,
  a changed byte refused, the fixture under the real proxy with position capture (four captured draws, stride 0 and 28, accepted by
  the reader), and the reader refusing a shifted flex value, a shortened row list, a changed program byte and a missing flex object.
- `position_to_scene` gains a synthetic second-program check: a mixed scene, a recorded flex value that differs from the evaluated
  one failing the gate, and the c0.y refusal.

## What this does not establish

- That the title's static-prop buffers are observed. They are probably filled at level load; the proxy shadows from process start
  within the 128 MiB budget, but only a game capture shows how many draws pass the `uninitialized_bytes` check.
- Anything about the normal, tangent, texture-coordinate, fog or colour outputs, or the pixel programs these draws use.
- World-space meaning, units or handedness of the model position, which stay unverified as for the first program.
- The 3348-byte program (48.8% of the frame) is skinned and remains refused.
