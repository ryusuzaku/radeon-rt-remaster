# First HL2 position contract: evidence and remaining gates

Exact vertex program SHA256:
`0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2`.
612 bytes, observed in 231 indexed draws of family
`34a26bb21a5f97a014180fb48bad9200318f5109d55f7dee252b087f572391a5`.

Offline inspection uses the Windows SDK CPU disassembler, not GPU execution:

```
python tools/disassemble_inventory.py build/game-passes/hl2-inventory-20260907/runs/inventory/shader-inventory.jsonl --disassembler build/x86-vs/Release/rrt_shader_disassemble.exe --sha256 0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2
```

## Actual position instructions

```
dcl_position v0
mad r0, v0.xyzx, c0.yyyx, c0.xxxy
dp4 oT4.x, r0, c58
dp4 oT4.y, r0, c59
dp4 oT4.z, r0, c60
dp4 oPos.x, r0, c4
dp4 oPos.y, r0, c5
dp4 oPos.z, r0, c6
dp4 oPos.w, r0, c7
```

For input `(x,y,z)`, prepared position is
`q=(x*c0.y+c0.x, y*c0.y+c0.x, z*c0.y+c0.x, x*c0.x+c0.y)`.
Clip position is `(dot(q,c4), dot(q,c5), dot(q,c6), dot(q,c7))`.
Output `oT4.xyz` is `(dot(q,c58), dot(q,c59), dot(q,c60))`.

Embedded compiler metadata names c4–c7 `cModelViewProj`, c58–c60 `cModel`,
c12 `cModelViewProjZ`, and c16 `cFogParams`. Names corroborate intended use but
do not establish runtime values, matrix decomposition or coordinate conventions.
There is no `def c0` in this program: do not substitute a guessed `(0,1,...)`.

The full listing is straight-line, 19 instruction slots. It declares only
POSITION0, TEXCOORD0, TEXCOORD1 and COLOR0 inputs. No relative addressing,
skinning loop, vertex-texture fetch or declared POSITION1/NORMAL1 reads appear.
The extra normal and stream-2 inputs in the device declaration are therefore
not consumed by this exact program. This does not generalize to other hashes.
Texture coordinates/colour plus c12/c16 are still needed for full raster output;
position-only extraction must not pretend it reproduces those outputs.

## Next implementation contract

1. Match this exact program and reviewed declaration/indexed topology. Preserve
   raw shader/declaration identities rather than admitting similar-looking code.
2. Capture initialized stream-0 FLOAT3 position bytes, actual index data, stream
   offset/stride, base vertex and draw ranges. Existing 64 KiB shadows may not
   cover game buffers; establish bounded range capture without claiming unknown
   pre-injection/pre-trigger bytes were initialized.
3. Require known actual c0, c4–c7 and c58–c60 values at the selected draw. Retain
   reset, wrapper-generation and state-block invalidation. Full raster replay
   also needs remaining program inputs/state and the pixel shader contract.
4. Test the exact position calculation against a native GPU fixture with varied
   c0 and matrices, nontrivial offsets/indices, missing-state negatives and an
   explicit numerical tolerance. The synthetic raster oracle below now passes;
   live initialized input capture remains unimplemented.
5. Validate `oT4.xyz` coordinate meaning and clip consistency using real captured
   input values before calling it world-space geometry or importing it into DXR.

Current result is an evidence-backed extraction design, not game geometry capture
or live relighting. No shader replay allowlist was widened in this slice.

## Implemented numerical gate

`src/shader/position.cpp` implements the prepared-position and seven dot products,
with exact program size/hash admission and explicit known/finite constant checks.
Nonfinite inputs and arithmetic overflow reject. `model` names the three-component
shader output, not a validated world-space interpretation.

The isolated fixture's `--hl2-position` mode takes only the pinned 612-byte program
as bounded hex input. It uses a HAL device with hardware vertex processing and
executes the unmodified captured VS against synthetic initialized vertex data.
A diagnostic PS exports oT4.xyz to an RGBA32F target. A second draw passes CPU
clip/model outputs through a simple VS. Both use indexed drawing with varied
stream offsets, base vertices and start index 1.

24 c0/transform cases cover 34,603 sample pixels. Coverage must match exactly;
all float components must be finite and satisfy
`abs(native-cpu)/(1+abs(cpu)) <= 0.0002`. Release and Debug result: maximum error 0.
Missing constants (each of eight slots), nonfinite inputs/constants, overflow,
and modified program bytes reject. Nonempty coverage is required in every case.

This tests raster coverage and interpolated position output, not direct VS register
readback, every possible float value, or game pixel-shader/material equivalence.
It does not bypass snapshot admission or integrate the evaluator into the proxy.

Run `python tests/verify_hl2_position.py --fixture build/x86-vs/Release/rrt_shader_fixture.exe --inventory build/game-passes/hl2-inventory-20260907/runs/inventory/shader-inventory.jsonl`.
CTest registers `hl2_position` only if the local capture exists; override its path
with `RRT_HL2_POSITION_INVENTORY`. Game bytecode is not embedded in repository tests.
