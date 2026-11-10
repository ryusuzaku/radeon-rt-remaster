# HL2 frame-level geometry capture result - 2026-11-10

The first capture with raised multi-draw quotas completed, converts and renders. It shows that **the quotas are not what limits
a frame: the admitted vertex program is.** This is position-only geometry evidence, not relighting of the game's look.

## Evidence

- Bundle: `build/game-passes/hl2-frame-20261027`, run `frame2` (local, not committed).
- Ledger SHA256: `47b6cf51ed9499cabf27a84a91d1518f9dde88538ad72a4dba71a103ffad3252`; session `9d1cf0cfa331181e371fd4118c01c1f5`.
- Options: `--position-selection any:3 --position-multi-draw --position-limits 256:1024`, triggered on a loaded save; the
  ledger header reports quotas 256 and 1024. RX 9070 XT, proxy `54b09060...` (Release).
- The run stopped at the 4,096-attempt cap after 45 presents, with a retained peak of 66.1 MiB (buffers only) under the 128 MiB
  cap. The game exited with code 0 and the runner removed its proxy.
- An earlier run, `frame`, exited after 7.7 s as `proxy-load-unconfirmed` with nothing captured: Steam was not running, and
  the game that then appeared had been started by Steam without the proxy. Start Steam before a pass.

## What was captured

| Outcome | Draws |
|---|---:|
| Captured | 270 |
| Rejected, `unsupported_shader` | 3,293 |
| Rejected, `selection_primitive_minimum` | 533 |

Every one of the 45 intervals accepted the same six draws (4, 11, 5, 6, 3 and 9 triangles; 38 in total) out of about 92 indexed
draws per present, all on the 1920 x 1080 target. Neither quota was reached: six per interval against 256, 270 in total against
1,024. Raising the quotas further cannot add geometry. The 80% of attempts refused as `unsupported_shader` are the vertex
programs the capture does not admit; the 6.6% accepted here is in line with the 7.7% coverage measured in the inventory pass.

## Conversion and render

`tools/position_to_scene.py` finds 45 render groups of six draws and converts the first to a 1280 x 720 scene of 6 draws, 38
triangles and 68 vertices; the largest relative clip-position error is 3.8e-6, the model-output error is zero and the
shared-camera spread is zero. `rrt_dxr` admits it: 113,512 of 921,600 pixels (12.3%) show geometry in albedo mode and 114,374
(12.4%) in 64-sample GI. The image is a few grey quads, not a recognisable frame.

## The reader defect this exposed

The reader first refused the ledger with `position calculation mismatch`. One draw per interval (45 of 270) has a clip z of
0.0933 formed from products near 4,945: a map-sized position against a near-plane row. The reader recomputed the program in
double precision and compared with a tolerance relative to the result, which float32 cancellation exceeds (5.2e-4 against
2e-4). All 135 failing components are **bit-identical** to a float32 evaluation of the same constants, and the error is 0.88
float32 rounding units of the products' magnitude, so the capture was right and the check was ill-conditioned.

`position_matches` in `tools/inspect_position_capture.py` now adds eight float32 rounding units of the products' magnitude to
the relative 2e-4. That is about 5e-7 of a well-conditioned value. `tests/test_position_conditioning.py` (`position_conditioning`,
also in the Linux CI job) reproduces the shape with synthetic numbers, requires the old rule to refuse it, and requires a
constant off by one part in a thousand, a moved position or an error four allowances wide to be refused still.

## Which vertex programs draw the frame

The run also wrote a shader inventory (2,701 draws, byte limit). Inventory and ledger count draws from different starts; the
offset that maps every captured draw to the admitted program and no `unsupported_shader` draw to it is 25 (or -67, one 92-draw
frame earlier). Both give the same table because the frames repeat: the inventory is identical from one frame to the next for
all 2,609 comparable draws, and the 44 complete ledger frames differ in a single refused draw (18 or 16 triangles). One frame is
92 indexed draws, 19,004 triangles, 16,212 of them to the 1920 x 1080 target, from 23 vertex programs:

| Vertex program | Bytes | Draws | Triangles to 1920 x 1080 | Share | Position path |
|---|---:|---:|---:|---:|---|
| `c3c0fcaa` | 3348 | 6 | 7,912 | 48.8% | skinned: `mova a0`, three bone-indexed `cModel[a0]` rows; blend weights and indices in the declaration |
| `a84edfd2` | 1420 | 27 | 5,570 | 34.4% | **not skinned**: `cViewProj * cModel[0] * (v0 + v4 * cFlexScale.x)`, no relative addressing |
| `e5ece83d` | 3212 | 2 | 566 | 3.5% | blend weights and indices in the declaration (not disassembled) |
| `26169c60` | 1172 | 7 | 506 | 3.1% | not disassembled |
| 19 others | | 50 | 1,658 | 10.2% | the admitted `0c16f3b5` (612 bytes) is one of them, at 42 triangles (0.3%) |

Seven programs declare blend weights and indices. One of them, `8ed20434`, draws 2,786 triangles, all to other targets.

`a84edfd2` is the most frequent vertex program in every local HL2 inventory (18 of them, 228 to 810 draws each). It declares
the shared `cModel[53]` table but reads only `cModel[0]` (c58-c60). Its prepared position adds `v4`, a stream-2 `position1`
scaled by `cFlexScale.x`; stream 2 has stride 0 in all 783 draws of this inventory, so `v4` is one value per draw. Clip x, y and
w come from `cViewProj` (c8, c9, c11) and z from c10, applied to the model-space result, which the program also writes to `oT7`.
That is the same shape the converter already handles, with the view-projection given directly instead of derived. Admitting it
would need its own exact CPU evaluator and the stream-2 vertex in the ledger, but not skinning. It would take the captured share
of this frame from 0.3% to about 35% of the triangles.

## What this does not establish

- No materials, UVs or textures; world-space meaning, units and handedness remain unverified.
- One save, one view, one GPU. The six draws were not identified as game objects.
- The `a84edfd2` description is from its disassembly, not from evaluating captured vertices; an evaluator still has to match
  the program's output numerically before any claim about its positions. The triangle shares are for one view of one save.
