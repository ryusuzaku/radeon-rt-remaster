# The `ps_2_x` material program: recovered contract, 2026-10-19

Status: **admission, payload, reconstruction, the proxy capture path and the
comparison test are implemented and measured (2026-10-20).** The next game pass is
what exercises it against real draws; everything up to the capture boundary has
run here.

## Measured result

`pixel_program_variants` (CTest, `local_evidence`) pairs each program with the same
draw, constants, geometry and textures, and requires the accepted program to clear
the 2e-4 gate first. Across the sixteen paired draws in `hl2-attrib-v19d`:

| Program | Draws under 2e-4 | Worst accepted draw |
|---|---|---|
| 1792-byte (accepted) | 12 of 16 | 2.617e-4 |
| 1912-byte (candidate) | 12 of 16 | 2.617e-4 |

The candidate matches the accepted program to six significant figures on every
draw — 2.903e-7 against 2.903e-7, 2.746e-7 against 2.744e-7, 3.483e-7 against
3.483e-7 — and exceeds the gate on exactly the same four draws. Those four are a
property of the draws (the spline reconstruction, shared by both programs), not of
the fog variant.

Two controls make that number mean something:

- **Wrong fog.** Compiling the candidate against the `t4.w` path instead of the
  distance path moves its error from 2.9e-7 to 1.496e-3 and fails the test. So the
  gate is actually measuring the fog change.
- **Tampered program.** Flipping one byte makes the fixture refuse with `pixel
  program not admitted` rather than compare. So the gate is measuring an admitted
  program.

Native digests are also required to differ between the two runs, so a fixture that
silently ignored the program substitution would fail instead of reporting a perfect
match.


## What was blocking, and why it no longer is

The 2026-10-14 pass (`hl2-shadow256-v19-20261014`, run `material256-v2`) stopped at
4096 attempts with zero captured draws. 160 of 237 recorded rejections were
`pixel_material/pixel_material_shader`: the bound pixel shader was not the single
pinned program the proxy admits. The inventory identified the dominant family as a
1912-byte `ps_2_x` program, but its **bytes** were believed unavailable, so no
fixture could be built and the contract could not be tested.

They were available. `src/shader/inventory.cpp` writes the **full program bytes as
hex** into every inventory row (`"ps":"<hex>"`), not just a digest. Extracting them
from the recovered inventory:

| Field | Value |
|---|---|
| Bytes | 1912 |
| SHA-256 | `dbca89ccb0e1d72bae02fb44cef4b80a6088cec6d163f0d4fe3dbf8661b199b0` |
| Version token | `ffff0201` (`ps_2_x`) |
| Draws in the pass | 189 |
| Paired vertex shader | `0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2`, 612 bytes, the same 189 draws |
| Source | `build/game-passes/hl2-shadow256-v19-20261014/runs/material256-v2/shader-inventory.jsonl` |
| Local copy | `P:/workspace/ninja-code/radeon-rt-remaster-evidence/restored-8cc61db052/extracted/candidate-ps-1912.bin` |

The 612-byte vertex shader is the same program the pixel fixture already feeds, so
the vertex side needs no new work.

**These bytes are captured game content. They stay local. Never commit them and
never add them to a fixture that ships.** Any test that uses them is a
`local_evidence` test and must skip when the file is absent.

## What actually differs

`pixel-shader-dependency.diff` in the same run directory compares the accepted
1792-byte program with the candidate. Three differences, only one of which is
behavioural:

1. **Constant registers are renamed.** `def c3`/`def c4` swap, so the spline
   constants live in `c4` and `(-1.5, 0.5, 0, 0)` lives in `c3`. Same values, so
   this does not change output.
2. **`dcl t4` becomes `dcl t4.xyz`.** The program no longer reads the interpolated
   `w`, because it computes fog from a position instead.
3. **Fog input changes from an interpolant to eye distance.** This is the real
   difference:

```hlsl
// accepted, 1792 bytes: fog comes from the interpolated factor in t4.w
min_sat r1.w, t4.w*c11.w - c11.x, c11.z
mul     r0.w, r1.w, r1.w

// candidate, 1912 bytes: fog comes from distance to c10.xyz
add     r2.xyz, -t4, c10            // c10.xyz - t4.xyz
dp3     r0.w, r2, r2
rsq     r0.w, r0.w
rcp     r0.w, r0.w                  // length(t4.xyz - c10.xyz)
mad_sat r0.w, r0.w, c11.w, -c11.x
min     r1.w, r0.w, c11.z
max     r0.w, r1.w, c3.z            // c3.z == 0 in this program
mul     r0.w, r0.w, r0.w
```

**The clamp order is equivalent for every reachable parameter value.** The accepted
form is `saturate(min(x, z))`; the candidate is `max(min(saturate(x), z), 0)` with
`z = c11.z`. For `z ∈ [0,1]` both equal `clamp(x, 0, z)`. For `z > 1` the candidate
returns `saturate(x)` and the accepted form returns `saturate(x)`. For `z < 0` both
return 0. So the only behavioural change is the fog **input**, and the reconstruction
is the existing one with two edits:

```hlsl
float4 eyePosition:register(c10);
...
float fog=saturate(min(length(model.xyz-eyePosition.xyz)*fogParams.w-fogParams.x,fogParams.z));
```

`rsq` followed by `rcp` is `sqrt` with two reciprocal roundings; that belongs inside
the existing 2e-4 normalized tolerance rather than being assumed exact.

## What has to change

Ordered so each step is independently verifiable. **All five are implemented**
(2026-10-20); what remains is a game pass that captures a draw with the new program.

1. **Proxy admission — done.** `src/shader/pixel_material.inc` now holds a table:
   `{1792, ad230bcd…, rows {11,12,29,30}}` and
   `{1912, dbca89cc…, rows {10,11,12,29,30}}`. c10 provenance needed no new code:
   `Knowledge::pixelConstants` is `std::array<bool,31>` and `PixelConstants()`
   marks any register in `[start, start+count)`, so a write to c10 is already
   observed and already invalidated by state-block apply and reset. The proxy path
   itself is exercised by `position_capture`, which now drives the fixture with the
   candidate's real bytes and requires 16 captured rows, `"rows":[10,11,12,29,30]`,
   a 160-character blob whose first row is the eye position, and a payload the
   validator accepts — plus rejection of that payload when it under-declares its
   rows.
2. **Self-describing payload — done.** The payload emits `"rows":[10,11,12,29,30]`
   beside `"constants"` and the blob length follows the row count (128 hex chars for
   four rows, 160 for five). This is deliberately **not** a new ladder level: the
   ladder gates which evidence objects exist, and level 12 still means "paired
   pixel material". What varies is which program was bound, which belongs in the
   payload. `tools/position_pixel_material.py` accepts both shapes — rows present
   means declared, absent means the original four-row program — so older captures
   still validate, and `position_capture` passes unchanged.
3. **Replay fixture — done.** `src/shader/pixel_replay_fixture.inc` reads a program
   of either admitted size, derives the row set and the constant-blob length from
   it, and selects the fog variant by compiling the shared reconstruction with
   `RRT_DISTANCE_FOG`. One spline expression, two fog inputs.
4. **Replay tooling — no change needed.** `tools/replay_pixel_material.py` passes
   the program and constant blob through as lines; the fixture derives the rest.
5. **Tests — done.** `tests/verify_pixel_program_variants.py` (CTest
   `pixel_program_variants`, `local_evidence`, 23 s) extracts the program from the
   local inventory, requires the accepted program to clear the gate on the same
   draw, then requires the candidate to match. It skips without the inventory or a
   paired pixel-material capture.


## What is behind it: the vertex program

Admitting the second pixel program does not produce captures, and the inventory says
why. Classifying all 2,734 inventoried draws in the recovered pass by which gate
would refuse them (hash each draw's `vs` and `ps`, compare against the admitted
sets — three lines with `hashlib`, no tool needed):

| Gate | Draws | Share |
|---|---:|---:|
| vertex program not admitted | 2,545 | 93.1% |
| both admitted | 189 | 6.9% |
| pixel program not admitted | 0 | 0% |

The 189 admitted draws are exactly the pair this change created: the 1912-byte pixel
program with the 612-byte vertex program. Every other admitted pixel program in the
inventory pairs with a vertex program that is still refused, so there are no draws
that the pixel work unblocks beyond those 189. **The pixel program was the smaller
half of the problem.**

The inventory holds 23 vertex families and 26 pixel families. Three were examined:

| Bytes | Draws | What it is |
|---:|---:|---|
| 1420 | 729 | Skinned. Indexed `cModel[53]`, `cFlexScale`, compressed-normal decode (`def c1, -128, -64, 0.0159`), base and detail texture-coordinate transforms, writes `oT4.xyz = normalize(modelPos)`. |
| 228 | 208 | `oPos = cModelViewProj * v0`, four `dp4`s, rows `c4..c7`, and **no pixel shader bound at all**. |
| 1172, 3348, 1116 | 590 | Not examined. |

Two consequences worth stating plainly:

- The 228-byte family is trivial to evaluate on the CPU, but it writes no model
  position and binds no pixel shader. Admitting it would yield position evidence
  without material evidence, which is not what the material goal needs.
- The 1420-byte family is the dominant one and is a skinning problem: bone-indexed
  matrices, normal decompression, two texture-coordinate transforms. It is not a
  digest-and-row-table change like the pixel program was. `src/shader/position.cpp`
  evaluates one program's arithmetic exactly; admitting this family means writing a
  second evaluator, and the capture path's position claims depend on that evaluator
  being right.

That makes the next step a decision rather than a task: continue per-family
admission, which is a treadmill where each family needs its own CPU evaluator, or
define a generic vertex path with a documented transform contract and a way to
validate it without a per-program oracle. The second is the larger design and the
only one that scales to 23 families.

## What this does not claim

- Nothing here is a captured draw from the game. The program is admitted, the proxy
  emits its five-row payload under a synthetic device, and its reconstruction is
  measured against the real bytecode on borrowed geometry. A pass that captures a
  real draw with it has not run.
- Admitting it moves the rejection population rather than clearing it: 93.1% of
  inventoried draws are refused by the **vertex** program, 14 by the primitive
  minimum, and the rest sit behind those.
- The clamp-order equivalence was argued from the disassembly before it was
  measured. The measurement above is what settles it; the argument is why the
  two-line change was worth trying first.
