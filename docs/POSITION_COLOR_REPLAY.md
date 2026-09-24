# Controlled color replay (v10)

`--position-color-replay` requires `--position-surface-scope` and its existing
prerequisites. Environment: `RRT_POSITION_COLOR_REPLAY=1`. Older v1–v9 producers,
readers and diagnostic replay behavior remain available.

This contract replays a **captured clear-to-endpoint prefix** on a private float
color target. It compares the exact captured vertex program against CPU-evaluated
positions, using the same admitted pixel program and captured blend operations.
It is not a general material renderer, original game-frame reproduction, depth
replay or proof of pixel equivalence against a game-frame readback.

## Captured evidence and admitted state

Accepted v10 draw rows add `color_replay`:

- `pixel_shader`: bounded native GetFunction bytes (8–4096 bytes). Unknown programs
  remain inspectable evidence but are not replay-admitted.
- `rgba`: raw effective pixel constant c0, four float32 lanes.
- `extra_states`: fog enable, clipping, user clip-plane mask, dithering,
  multisample mask and line antialiasing, in that exact order.
- `npatch_mode`: raw float32 bits of GetNPatchMode.

The one admitted pixel program is exactly five DWORDs:
`ffff0200 02000001 800f0800 a0e40000 0000ffff` (`ps_2_0; mov oC0,c0; end`).
It uses no textures, samplers, interpolated colors or other constants. All RGBA
lanes must be finite and in [0,1]. The source vertex shader remains the existing
exact HL2 position shader; this pixel shader is a controlled synthetic program,
not a recovered HL2 material.

The admitted target/viewport is exactly 128×96, A32B32G32R32F, no multisampling,
full viewport and depth range [0,1]. The v9 closed scope must qualify (private
nonlockable standalone RT0, no depth or MRT, no open/unknown access). Additional
raster requirements are:

- Depth read/write, alpha test, separate-alpha blending, stencil, sRGB write,
  depth/slope bias, scissor, fog, user clip planes, dithering, line AA and N-patches
  are disabled; clipping is enabled and sample mask is all ones.
- Solid fill, no culling, all four color channels writable.
- Blending is disabled, or ADD with each factor chosen from ZERO, ONE,
  SRCALPHA and INVSRCALPHA. Separate-alpha blending stays disabled, so the same
  factors apply to alpha. Irrelevant blend factors are normalized only when
  blending is disabled.

No partly captured state is silently replayed as supported. Depth requires a
separate scope/initialization extension, and texture-backed targets remain excluded.
In v10, device state setters also participate in the native-call overlap window;
overlap with a draw marks the stream unqualified. Attachment setters and state-block
Apply already use writer windows. This is a fail-closed guard, not native concurrent
rendering qualification; the fixtures exercise serialized rendering.

## Prefix admission and replay

`tools/replay_position_colors.py` reads one immutable bounded ledger, retains its
SHA256, and chooses the latest captured endpoint for each device/epoch/target/clear
segment. It resolves **every** intervening captured ordinal from that retained
clear, verifies each draw's supported state, and verifies each earlier row agrees
with the required prefix. Missing, unsupported or inconsistent predecessors reject
the segment. It does not split a blend sequence on changing blend state or replay
only its last sampled draw. No claim extends beyond the explicitly reported write
serial endpoint, where later uncaptured draws may occur.

The native fixture's `RRT_POSITION_COLOR1` input carries bounded per-draw constants,
positions, RGBA, blend enable/factors, and the captured clear color. Its established
`RRT_POSITION_GROUP1` diagnostic protocol is unchanged. Both vertex paths apply the
same clear and per-draw supported state and compare all RGBA pixels. Bounded shape,
finite/range, factor, count and trailing-data checks happen before GPU creation.

The separate color report can set `ready_for_stateful_replay: true` for this
qualified prefix and reports GPU success/failure independently. Generic per-draw
initial-content admission remains false/unknown: a draw alone cannot recover its
prior pixel contents. `color_draw.supported_draw` is only the per-draw support gate;
it still requires prefix validation.

`nonzero_alpha_pixels` is an output statistic, not geometry coverage (a nonzero
clear can populate it). `center` and `background` are control samples. The FNV
fingerprint is diagnostic, not resource identity. A successful comparison does not
imply visible geometry when alpha or raster coverage happens to be empty.

Example after validating an eligible synthetic capture:

```powershell
python tools/replay_position_colors.py CAPTURE.jsonl --fixture build/x86-vs/Release/rrt_shader_fixture.exe --out RESULT.json
```

## Validation and next direction

Native capture/replay controls cover overwrite and two alpha-blended draws with a
nonzero clear. Independent arithmetic checks center/background values. Additional
controls change draw colors/order, disable blending on the later draw, and use
additive blending; the output must change as predicted. Missing predecessors,
unknown shaders, fog, unsupported blend operation, nonfinite constants, viewport,
depth/N-patch state and malformed evidence/native inputs are rejected. Legacy
position and grouped raster tests remain unchanged.

No new HL2 gameplay pass is useful for this exact synthetic pixel program: real
HL2 materials are not admitted. Next use the saved shader inventory to choose and
audit a bounded real pixel/material path, or extend depth scope independently.
Request gameplay only when a contract can capture and replay useful actual game
state; do not relabel this controlled color test as live game relighting.
