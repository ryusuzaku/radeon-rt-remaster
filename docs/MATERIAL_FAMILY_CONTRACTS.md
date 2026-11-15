# Material family contracts: recovered 2026-11-15

Status: **contracts recovered from the 2026-11-14 inventory; implementation started
2026-11-15 with the table-contract foundation** (single-source
`docs/schemas/pixel-programs.json`, a static sync test across schema/proxy/fixture/
reader, and a forward-compatible sampler `slot` field in the reader). Capture
behavior is unchanged so far; the sampler-slot generalization and cube support are
next. This is the material-side follow-up to the
[vs_2_0 position interpreter](VS_INTERPRETER.md): position capture now admits 23
vertex programs, but material capture still refuses every one of them. The
[interpreter coverage result](HL2_INTERP_FRAME_RESULT.md) measured 99.86% of the
frame's triangles as position-only evidence; this document scopes what admitting
their **materials** requires.

The decision (2026-11-15) is per-family admission, dominant-first — the proven
[`ps_2_x` methodology](MATERIAL_PS2X_CONTRACT.md), not a generic pixel-shader
interpreter. A generic PS path would have to evaluate texture sampling, fog and
envmap reflection for 23 families; it is a research task with no stop condition,
the pattern the RR track warns against.

## The census

`build/game-passes/hl2-interp-20261110/runs/frame/shader-inventory.jsonl`
(2,710 draws, ~30 frames of the same view) classifies by hashing each draw's `vs`
and `ps` bytecode:

| VS path | Draws | PS families | Pinned PS? |
|---|---:|---|---|
| first 612-byte (`0c16f3b5`) | 240 | `dbca89cc` (ps_2_x) | yes, already admitted |
| flex 1420-byte (`a84edfd2`) | 810 | `84a8ee5e` ×630, `1dc39d80` ×150, `ad310c3d` ×30 | no |
| skin 3348-byte (`c3c0fcaa`) | 180 | `d14e9f9e` | no |
| interpreted | 1,480 | ~19 families; `65a8e052` ×215, `8dcb8e47` ×210, `0534da28` ×155, … | no |
| interpreted, no PS (`2288ea1d`) | 180 | — | n/a |

22 distinct pixel-shader families (plus one program that binds no PS at all); only
`dbca89cc` is admitted today. The three dominant
unadmitted pairs — flex×`84a8ee5e` (630), `2aa6a2c3`×`65a8e052` (215),
`26169c60`×`8dcb8e47` (210) — are recovered below. Together they are 1,055 of the
2,470 unadmitted draws (42.7%).

**Program bytes are captured game content. They stay local. Never commit them and
never add them to a fixture that ships.** Every test that uses them is a
`local_evidence` test and must skip when the inventory is absent. Disassembly is
via `tools/disassemble_inventory.py` (bounded CPU subprocess, exact hash).

## Shared infrastructure gaps

All three families need changes the current material path does not have. These are
prerequisites, shared across families, and come first:

1. **Sampler slots beyond 0/1, and cube textures.** `PixelMaterial`
   (`src/shader/pixel_material.inc`) hardcodes slots 0 and 1 and requires
   `D3DRTYPE_TEXTURE`. The recovered programs bind detail at **s12**, bump at
   **s4**, and a **cube** envmap at s1. The pixel-program table must carry a
   per-program sampler list (slot + type), and the texture capture path must
   handle cube textures. This is the largest shared change.
2. **Per-VS material layout and interpolant evaluation.** The material path today
   pins the 612-byte VS's stride-48 layout (COLOR0 @24, TEXCOORD0 @28, TEXCOORD1
   @36) and `EvaluateMaterial`. Each admitted VS needs its own material-output
   evaluator (UV transforms, lightmap gamma, normal decode) and its own declaration
   contract, in the same style as `EvaluateFlex`/`EvaluateSkin` for position.
3. **Self-describing pixel payload.** Already present (`"rows"` beside
   `"constants"`); new programs add a row set, not a ladder level. The sampler list
   needs the same treatment: declared in the payload, validated by the reader.

## Pair 1 — flex × `84a8ee5e` (630 draws): WorldVertexLitGeneric + envmap

| Field | Value |
|---|---|
| PS bytes | 1332 |
| PS SHA-256 | `84a8ee5e49444dcd752b5bfc5c2c49799531cd43e988e143da1fce8eb9c9458f` |
| Version | `ps_2_x` |
| VS | flex `a84edfd28843f7c8aeac78bcb48c03184326c007593e8d49e99777c8cf1f11dc`, 1420 bytes |
| PS constant rows | c0, c1, c2, c3, c12, c20, c21, c29, c30 (9 rows) |
| Samplers | s0 2D base, **s1 CUBE envmap** |
| PS inputs | t0.xy base UV, t2 lightmap gamma, t3.xyz eye vector, t4.xyz normal, t6.xyz clip, t7.xyz model pos |

**PS algorithm.** Cube-envmap reflection `R = 2(N·E)N − |N|²E` from t4 (normal) and
t3 (eye−model), sampled on s1; base texture on s0; envmap scaled by c30.z, masked by
`1 − baseAlpha`, tinted by c0, contrast-shaped by c2, saturation-mixed toward
luma (c4 = luminance weights) by c3; added to `base · c1 (diffuse modulation) · t2
(lightmap gamma)`. Distance fog from `length(c20 − t7)` with c21 params, squared,
lerped to c29 fog colour. Alpha selects between a c12.w/c1.w blend and `t6.z·c29.w`
on c12.y. ~37 slots, 2 texture.

**VS material outputs** (the flex position evaluator already exists; these are the
additional interpolants):

- `oT0.xy` = base UV: `dp4 v3, c48` / `dp4 v3, c49` (cBaseTexCoordTransform).
- `oT1.xy` = detail UV: `dp4 v3, c52` / `dp4 v3, c53` (unused by this PS variant).
- `oT2.xyz` = lightmap gamma: `(2·v2.rgb)^2.2` (`v2+v2`, log, ×c4.z=2.2, exp);
  `oT2.w = c0.x`.
- `oT3.xyz` = `c2.xyz − modelPos` (cEyePosWaterZ − flexed model position).
- `oT4.xyz` = normalized world normal: compressed-normal decode of v1/v5
  (c1 = −128, −64, 0.015873, 1; c4 = −2, 1, 2.2, 0), flex-blended by c3.x,
  transformed by cModel[0] (c58–c60), normalized.
- `oT6` = clip position (c8/c9/c11 rows; z from c13); `oT7` = model position + c13 depth.
- `oFog`/`oD1.w` = fog from c16 and c13 depth; `oD1.xyz = c0.x`.

The normal decode is the hard part: it is not a linear transform, and the material
evaluator must reproduce it exactly (the position interpreter already refuses
`_abs`/`sub`, but this decode uses `abs`/`slt`/`mad` — a per-family evaluator, not
the position slice).

## Pair 2 — `2aa6a2c3` × `65a8e052` (215 draws): lightmapped world + detail

| Field | Value |
|---|---|
| PS bytes | 2144 |
| PS SHA-256 | `65a8e052d77af48b339692c0e6d0a3214b55b53755bb8710b0319dc9eb29b150` |
| VS | `2aa6a2c31c794457c53f9baaca1c457e2899eeb8d9a547382421720772f336ad`, 1116 bytes |
| PS constant rows | c8, c10, c11, c12, c29, c30 (6 rows) |
| Samplers | s0 2D base, s1 2D lightmap, **s12 2D detail** |
| PS inputs | t0.xy base UV, t1.xy detail UV, t2.xy lightmap UV, t4 model pos + fog w, v0.xyz (= oD0, white) |

**PS algorithm.** The lightmap is a **4-tap bicubic B-spline** over a 1024×512
atlas (c0 = 1024, 512, 0.5, 3; c2 = 1/1024, 1/512, −1.5, 0.5) — the same spline the
admitted program's replay fixture already reconstructs, and the source of the four
draws that exceed 2e-4 in `pixel_program_variants`. Detail texture on s12 tinted by
c8, blended by c3.z/c3.w and c8.w; multiplied by base (s0) and v0; lightmap scaled
by c12; distance fog from `length(c10 − t4)` with c11; alpha `t4.w·c29.w`. ~82
slots, 6 texture.

**VS material outputs** (world, cModelViewProj):

- `oT4.xyz` = cModel[0]·pos; `oT4.w` = cModelViewProjZ (c12) depth.
- `oPos` = cModelViewProj (c4–c7)·pos.
- `oT0.xy` = base UV affine transform (c48/c49): `u·c.x + v·c.y + c.w`.
- `oT1.xy` = detail/bump UV (c50/c51); `oT1.zw = 0`.
- `oT2` = lightmap UV from v2 (texcoord1): `(v2.x, v2.y, 0, 0)`.
- `oT3.zw` = blend-mask UV (c14/c15); `oT3.xy = 0`.
- `oD0` = (1, 1, 1, c47.w) (cModulationColor alpha); `oFog`/`oD1` from c16.

## Pair 3 — `26169c60` × `8dcb8e47` (210 draws): lightmapped world + bump + detail

| Field | Value |
|---|---|
| PS bytes | 4572 |
| PS SHA-256 | `8dcb8e47247096a56fbd013e51141b6b3986c7e2f9c7762b41c773bdc8de948e` |
| VS | `26169c607a20889d9da923745d03a7919c6a2e3f01fa97f7d77e2a1e265bb168`, 1172 bytes |
| PS constant rows | c8, c10, c11, c12, c29, c30 (6 rows) |
| Samplers | s0 2D base, s1 2D lightmap, **s4 2D bump**, **s12 2D detail** |
| PS inputs | t0 base, t1 detail, t2 lightmap, t3.xy bump UV, t4 model+fog, v0 |

Same lightmapped-world structure as pair 2 (same spline, same fog, same constant
set) plus a bumpmap on s4 with a tangent-frame basis (c0–c2 hold 0.816/0.577/0.707
directions). The VS differs from pair 2 only in the lightmap/bump UV combination:
it reads a third texcoord v3 and writes `oT2 = (v3+v2, …)`, `oT3.xy` from v3. The
reconstruction can share pair 2's spline/fog/detail path with a bump addition.

## Implementation order

Ordered so each step is independently verifiable, following the `ps_2_x` precedent:

1. **Sampler infrastructure** — per-program sampler list (slot + type) in the
   pixel-program table and payload; cube texture support in the capture and reader.
   Fixture: a synthetic cube-bind program captured and validated; negative controls
   for a wrong slot/type. No game content needed.
2. **World-VS material evaluator** — pairs 2 and 3 share the world VS layout; one
   evaluator covers both (UV transforms, lightmap UV, oD0, fog). Declaration
   contract + per-corner evaluation, verified against the disassembly on synthetic
   vertices before any real bytes.
3. **Pair 2 admission + reconstruction** (simplest complete family: no cube, no
   bump; spline already in the fixture). Pixel-program row, replay-fixture variant,
   `local_evidence` test requiring the candidate to match the admitted program on
   borrowed geometry, wrong-fog and tampered-program controls.
4. **Pair 3** — bump addition on pair 2's path.
5. **Flex material evaluator + pair 1** — the normal decode and cube envmap; the
   largest per-family step, last because it depends on step 1's cube support.
6. **Game pass** — a triggered material-chain pass on the same view, measuring
   captured material draws per family. Needs the operator.

Steps 1–5 are fixture work; only step 6 needs game time. Each admission moves the
rejection population rather than clearing it: the census still leaves ~1,400
interpreted draws in smaller families behind these three.

## What this does not claim

- Nothing here is a captured material draw from the game. The contracts are
  recovered from disassembly; the reconstructions are unimplemented and unmeasured.
- The 42.7% figure is a share of inventoried draws in one view, not a coverage
  guarantee; smaller families and other views are unscoped.
- The flex normal decode and the bump tangent frame are argued from disassembly,
  not measured. The fixture oracle is what will settle them, as it settled the
  `ps_2_x` clamp order.
- World-space meaning, units and handedness remain unverified, as for all position
  capture to date.
