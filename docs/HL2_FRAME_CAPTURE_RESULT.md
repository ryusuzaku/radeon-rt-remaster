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

## What this does not establish

- No materials, UVs or textures; world-space meaning, units and handedness remain unverified.
- One save, one view, one GPU. The six draws were not identified as game objects.
- Vertex-program coverage is the next decision: the other programs, skinning among them, are a separate piece of work.
