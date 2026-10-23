# The `ps_2_x` material program: recovered contract, 2026-10-19

Status: **the program is recovered and the behavioural difference is specified.
Implementation has not started.** This page exists so the next session does not
have to rediscover any of it.

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

Ordered so each step is independently verifiable.

1. **Proxy admission.** `src/shader/pixel_material.inc` hardcodes one size (1792),
   one digest and the row set `{11,12,29,30}`. Replace with a table:
   `{1792, ad230bcd…, rows {11,12,29,30}}` and
   `{1912, dbca89cc…, rows {10,11,12,29,30}}`. c10 provenance needs no new code:
   `Knowledge::pixelConstants` is `std::array<bool,31>` and `PixelConstants()`
   marks any register in `[start, start+count)`, so a write to c10 is already
   observed and already invalidated by state-block apply and reset.
2. **Self-describing payload.** Emit `"rows":[10,11,12,29,30]` beside
   `"constants"` and let the blob length follow the row count (128 hex chars for
   four rows, 160 for five). This is deliberately **not** a new ladder level: the
   ladder gates which evidence objects exist, and level 12 still means "paired
   pixel material". What varies is which program was bound, which belongs in the
   payload. `tools/position_pixel_material.py` must accept both shapes — rows
   present means declared, absent means the original four-row program — so the
   twelve existing captures still validate.
3. **Replay fixture.** `src/shader/pixel_replay_fixture.inc` reads a fixed 1792-byte
   program and a 64-byte constant blob. It needs variable lengths, a row set chosen
   by program, and a second reconstruction selected by program identity.
4. **Replay tooling.** `tools/replay_pixel_material.py` builds the payload from a
   captured row; it must pass the row set and blob length through rather than
   assuming four.
5. **Tests.** A `local_evidence` case that loads the extracted bytes, runs the
   fixture, and requires the reconstructed program to match the native one within
   the existing tolerance. Negative controls: a 1912-byte program with one byte
   changed must be rejected by the allowlist; a five-row payload with four rows of
   data must be rejected by the validator.

## What this does not claim

- Nothing here is a captured draw. The program is admitted, not replayed in a
  frame.
- Admitting it will move the rejection population, not eliminate it: the same pass
  reported 63 sampled unsupported **vertex** shaders, 14 primitive-minimum
  rejections and buffer-range failures behind them.
- The equivalence argument above is from the disassembly. The reconstruction still
  has to be measured against the real bytes before anyone calls it matched.
