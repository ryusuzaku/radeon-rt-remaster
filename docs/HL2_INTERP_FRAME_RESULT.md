# HL2 interpreter coverage result - 2026-11-14

The first gameplay pass with the [vs_2_0 position interpreter](VS_INTERPRETER.md)
admitted completes, converts and renders. It measures the interpreter's end-to-end
coverage on the same save and view as the [2026-11-10 frame capture](HL2_FRAME_CAPTURE_RESULT.md):
**every draw of at least three triangles is captured — 18,622 of the frame's 18,648
triangles (99.86%) — with zero `unsupported_shader` refusals.** This is position-only
geometry evidence, not relighting of the game's look.

## Evidence

- Pass: `build/game-passes/hl2-interp-20261110`, run `frame` (local, not committed).
  Prepared 2026-11-10 with a baseline reused from `hl2-frame-20261027` (normal exit).
- Ledger SHA256: `18be6e9c5c01b8ff4829d3ee69d11af9c7d9650ea64f0f92960595cfc78d3c20`;
  session `38010afa80da30b3680f544449b1a246`; version 5.
- Proxy: Release `aefcf71ef24a4c73522d8e3912dc2aadde227290a5705768fe758e8c50115820`
  (the interpreter build merged as PR #37), deployed to `bin\d3d9.dll` by the runner.
  Executable `0dbc5fb2…`, arguments `-steam -game hl2_complete`, RX 9070 XT.
- Options identical to `frame2`: `--position-selection any:3 --position-multi-draw
  --position-limits 256:1024 --position-frames --shader-inventory`, 128 MiB shadow cap.
  The user loaded the same save; capture was triggered on request and armed at the
  next Present.
- Run health: exit code 0, proxy removed, executable unchanged; trace 276 presents,
  24,912 draws, 0 failed calls.
- Ledger stop: `byte_limit` (16 MiB) after 236 attempts / 203 captures / 3 presents.
  Retained peak 63.2 MiB, all buffers, under the 128 MiB cap. Neither draw quota was
  reached; the per-corner evidence of the admitted draws fills the ledger first.

## Coverage, reconciled against the trace

The trace records 90 indexed draws and 18,648 triangles per frame, stable across all
277 presenting frames. Each full capture interval reconciles exactly:

| Outcome | Per frame |
|---|---:|
| Indexed draws (trace) | 90 |
| Captured | 77 |
| Refused, `selection_primitive_minimum` (1–2 triangles each) | 13 |
| Refused, `unsupported_shader` | **0** |
| Triangles captured | 18,622 |
| Triangles refused (the 13 tiny draws) | 26 |

Every draw of at least three triangles was captured: 203/203 across the run, with
zero evidence failures — the independent reader recomputed every corner. The 236
attempts are 90 + 90 + 56; the third interval stopped mid-frame at the ledger byte
limit. Captured targets: 188 draws to 1920×1080 (15,836 triangles per full frame)
and 15 to 1024×1024.

Comparison on the same view:

| Pass | Admitted programs | Captured per interval | `unsupported_shader` |
|---|---|---|---:|
| `hl2-frame-20261027/frame2` (2026-11-10) | 1 hand-written | 6 draws / 38 triangles to the main target | 3,293 |
| `hl2-skin-20261110` (2026-11-10) | 3 hand-written | 72.1% of frame triangles | — |
| `hl2-interp-20261110/frame` (this run) | 3 hand-written + 20 interpreted | **99.86% of frame triangles** | **0** |

## Which programs drew

Captured triangle share by program path (whole ledger):

| Path | Draws | Triangles | Share |
|---|---:|---:|---:|
| skinned 3348-byte (hand) | 12 | 15,824 | 34.5% |
| flex 1420-byte (hand) | 71 | 15,500 | 33.8% |
| **interpreted** | **102** | **14,442** | **31.5%** |
| first 612-byte (hand) | 18 | 114 | 0.2% |

14 of the 20 interpreted programs drew in this view: `26169c60` ×21, `8ed20434` ×15,
`2aa6a2c3` ×15, `2288ea1d` ×12, `4dfd4c0f` ×6, `66bfc25b` ×6, `bced3cb4` ×6,
`ee462668` ×4, `e5ece83d` ×4, `dde51af8` ×3, `1773be9a` ×3, `8e3211a8` ×3,
`7839f176` ×2, `88c6f759` ×2. The other six passed their oracles on 2026-11-10 but
did not draw in this view; nothing here re-qualifies them.

The two camera-less programs behave as designed: `2288ea1d` (`cModelViewProj` only)
and `88c6f759` (screen space) are captured with a `null` camera and refused at scene
conversion rather than placed under an assumed camera.

## Conversion and render

`tools/position_to_scene.py` groups each interval as [5, 65, 3, 4, 5] draws by camera
and converts the largest (group 1): **65 draws, 15,804 triangles, 15,655 vertices**
under one camera (shared-camera spread 0), a 1280×720 scene from the 1920×1080
viewport. Maximum relative clip error 1.75e-4 (within the reader's float32
conditioning allowance), model-output error 4.3e-8. Scene SHA256
`af15cebc4cafef46a35a9a1ea08233eee581fb58f9ac9aa9027a1647b3c52f62`. The smaller
groups keep their own cameras; a draw whose derived camera differs is not merged.

`rrt_dxr` (x86 Debug) admits the scene on the RX 9070 XT and renders headless in
albedo (1 sample) and GI (64 samples): 226,095,340 requested bytes, 2.6% of the
8 GiB limit. In albedo, 13,982 of 921,600 pixels (1.5%) differ from the uniform
background. As with the 2026-11-10 frame result, the image is a geometry sanity
check, not a recognisable frame: world-space meaning, units and handedness remain
unverified, and the rendered pixel fraction is not a coverage metric — the ledger
is. GI pixel counts are not comparable frame-to-frame (unfiltered Monte Carlo
background).

## What this does not establish

- Materials: interpreted programs are still refused by material capture; the
  position-only boundary is unchanged.
- Other views, saves, titles or later shader models: each program's oracle admission
  is per program, and this is one view of one save on one GPU.
- World-space meaning, units or handedness, as for every position capture to date.
- That the six interpreted programs which did not draw here appear in other views;
  their oracle evidence stands, their in-game behaviour is unmeasured.
- Live integration: this is offline capture, conversion and standalone rendering.
