# Real captured HL2 position replay

The synthetic GPU gate is now extended to actual captured inputs. Each accepted
draw is validated on the CPU, then replayed in its own fixture process on a fresh
HAL hardware-vertex-processing device. No game or proxy injection is required.

The bounded native input is the pinned 612-byte shader, eight captured constant
rows and captured FLOAT3 positions in triangle-corner order. Sizes, program hash
and finite data are checked before GPU creation. Indexed source topology is
validated by the reader and expanded to an independent sequential corner stream
for replay. This does not repeat original resource allocation/offset behavior.

The unmodified shader computes position output; a diagnostic PS exports oT4.xyz
to RGBA32F. A second render uses CPU-evaluated clip/model outputs with a passthrough
VS. Raster coverage must match exactly and normalized float difference must not
exceed0.0002. Both use128x96 diagnostic resolution, not the source target resolution.
Unused UV/colour inputs and fog-related constants are synthetic. No texture,
material, depth/occlusion or final game pixel comparison is claimed.

## First real capture results

| Draw ordinal | Triangles | Covered pixels | Result |
|---|---:|---:|---|
| 1 | 2 | 12,288 | Matched; zero measured float difference |
| 66 | 2 | 0 | Empty on both paths; not visible validation |
| 67 | 18 | 659 | Matched; zero measured float difference |
| 68 | 35 | 1,617 | Matched; zero measured float difference |

Source digest:
`a978e1db6315866071257cdc9bce0d1183c54ffc7b35179ad5cbbf49ec1579bd`.
Results are stored in the combined pass `reconstructed-grouped` directory.
An all-empty bundle cannot pass the visible-oracle regression.

Use `python tools/verify_recorded_positions.py CAPTURE --fixture FIXTURE_EXE
--out NEW_REPORT.json`; existing reports are preserved. The conditional local
CTest `recorded_position_oracle` runs when `RRT_HL2_POSITION_CAPTURE` exists,
alongside reconstruction tests. Malformed, truncated, oversized, nonfinite and
trailing native inputs are rejected. Real game data is not embedded in the source.

This establishes independent position-raster agreement for three captured draws.
It does not establish world-coordinate semantics, general shader support or full
game compatibility. Next work is selecting useful scene draws/coverage, stable
resource identity across updates, and the required material/texture contracts.
