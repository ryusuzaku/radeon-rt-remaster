# Combined gameplay capture result — 2026-09-07

Bundle: `build/game-passes/hl2-combined-20260907/runs/combined`.
Triggered after the user confirmed gameplay.

## Validated outputs

- Position capture completed at its four-draw limit after 69 indexed attempts.
- Accepted ordinals 1, 66, 67, 68: respectively 2, 2, 18, 35 triangles (57 total).
- All use stream stride 48, a 1,572,864-byte vertex buffer and 65,536-byte index
  buffer. Referenced initialized positions, indices and required constants were
  admitted; the offline reader independently validated computed position outputs.
- The 65 other attempts rejected as unsupported shaders. No missing-state fallback
  was used to produce the accepted captures.
- Position ledger SHA256:
  `a978e1db6315866071257cdc9bce0d1183c54ffc7b35179ad5cbbf49ec1579bd`.
- Shader inventory: 2,919 draws, 49 combined families, 76 programs, zero failed
  draws or unavailable queries. Normal byte-limit completion.

These are real game position-input captures, not merely the earlier synthetic
fixture. Triangle counts describe four recorded draws, not unique scene geometry;
draws may repeat geometry or represent additional passes. Coordinate interpretation,
materials, full-scene reconstruction and live relighting are not validated.

## Trace limitation and cleanup

Resolved on follow-up: the trace later completed normally at 60 presents,
194,529 events, 13,395 shader draws and zero failed calls. The earlier empty
observations below were provisional, not a final failed capture. Exact activation
delay cause is not established. HL2 exited 0 after 332.406 seconds; executable
unchanged, runner removed its owned DLL, and bin/d3d9.dll was verified absent.

Trace remained zero bytes on two inspections after the other outputs completed.
The trace reader correctly rejected it as empty. The trace trigger is checked
only on an observed `S_OK` Present, unlike the indexed-draw-triggered outputs.
That difference is a diagnostic lead, not an established cause. Do not label this
a successful trace pass or infer whole-session API failure counts from inventory.

HL2 PID 45776 was still running/responding at inspection; runner cleanup remains
pending normal exit. No settings changes, forced exit or proxy replacement were
performed while the game ran.

Next: reconstruct and inspect the four accepted position draws offline, verify
their clip/model-space interpretation, and separately diagnose trace activation
without discarding these successful captures. No repeat game pass is needed just
to begin offline analysis of the captured inputs.

## Offline reconstruction completed

`reconstructed-grouped/` in the pass directory contains eight OBJ files: separate
input-space and model-output-space meshes for each captured draw, with a provenance
and coordinate-analysis manifest. 57 triangles and 127 per-draw unique vertices,
zero detected degenerate triangles. No cross-draw deduplication or materials.

All four draws have c0=(0,1,2,0.5) and identity model rows, so input/model-output
positions agree in this sample. They must not be treated as a single camera pass:
draw1 uses a256x256 target and different clip rows; draws66–68 use5120x1440 and
share clip rows. Draw66 has all six corners at negative clip w. The manifest groups
draws by exact target/viewport/clip transform and records bounds and clip-w counts.
These are evidence-based render groups, not semantic camera/material labels.

Reconstruction tests cover face indices/counts, matrix inversion, render grouping,
partial-input rejection and preserving existing output. The position capture
regression also passes after exposing validated records to the exporter.

Next: independently preview/replay the reconstructed geometry per render group,
then expand capture selection/coverage and material evidence. Geometry extraction
has progressed beyond the synthetic fixture, but world-space semantics and live
game relighting remain unvalidated.
