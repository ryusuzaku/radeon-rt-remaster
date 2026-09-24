# Grouped position replay

`tools/replay_position_groups.py` validates one immutable saved ledger snapshot,
then groups v3–v5 accepted draws by device, reset epoch, presentation interval,
target descriptor, viewport bytes and captured clip rows. For v6, exact captured
surface/clear/binding/state metadata also separates groups (see
`POSITION_COMPOSITION_EVIDENCE.md`). Each group is ordered by indexed-draw
sequence; c0 and model rows remain independent per draw. Captured depth/blend
values are not yet applied by this diagnostic replay. Legacy
ledgers without timing and incomplete/error captures reject; accepted content is
required. The source SHA256 and session remain attached to the report.

Run with the local fixture, after closing the game:

```powershell
python tools/replay_position_groups.py build/game-passes/hl2-multidraw-20260907/runs/multidraw/position-capture.jsonl --fixture build/x86-vs/Release/rrt_shader_fixture.exe --out build/game-passes/hl2-multidraw-20260907/reconstructed/group-release.json
```

Output is exclusive-create. An existing report must not be overwritten.

## Diagnostic rendering contract

The native `--position-group` fixture takes a versioned text payload containing
one exact admitted shader and1–16 draws. Every draw has128 bytes of constants
and1–4096 triangles of corner positions. The parser bounds each input line,
requires newline termination/EOF, rejects mixed clip rows and validates all
finite CPU-evaluated outputs before creating a GPU device. At most65536 triangles
can enter one diagnostic request; no input resource pointers cross the boundary.

One128x96 RGBA32F target is cleared once per comparison path, not between draws.
The first path uses the captured vertex shader with each draw's constants; the
second uses independently CPU-evaluated positions/model outputs and a passthrough
shader. Both use captured draw order and the same diagnostic pixel shader.
Unused UV/colour inputs and extra fog constants are synthetic.

Depth testing/writes, alpha testing and blending are disabled. Later covering
draws overwrite earlier draws. This explicit policy tests position composition;
it does **not** reproduce the game's materials, depth, blend or clear behavior.
Matching target descriptors do not identify the same target resource or render
pass. Grouping is an offline compatibility assumption, not recovered pass identity.

Coverage must match exactly; normalized model-output error must stay at most
0.0002. Empty groups are reported separately. An FNV-1a64 fingerprint of native
output is diagnostic only, never a cryptographic source or asset identity.

## Real evidence and controls

The saved HL2 v5 capture supplies four groups, each four draws/48 submitted
triangles. Release and Debug replay covers2593,2588,2555 and2565 pixels respectively,
with exact coverage and zero error for every group. This exceeds last-draw-only
coverage and preserves contributions from multiple draws.

Release/Debug reports are identical, including the native output fingerprints.
Selected regression suites pass6/6 Release and3/3 Debug. No game launch or proxy
change was needed for this work.

Tests also exercise disjoint triangles (combined coverage equals the sum),
overlapping identical geometry with different model constants (last draw wins),
reversed order,16-draw bounds, malformed/truncated/oversized input, nonfinite
constants, mixed clip transforms and grouping isolation. Native proxy capture
behavior is unchanged; only the standalone diagnostic fixture is extended.

Next requirements for game-faithful composition: capture target resource identity
and pass boundaries/clears, depth and blend state, then qualify their replay before
feeding a composed scene into lighting or claiming whole-frame equivalence.
