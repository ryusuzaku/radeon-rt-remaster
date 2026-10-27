# Position ledger to renderable scene

`tools/position_to_scene.py` turns one render group of an HL2 position-capture ledger into a v2 `.rrscene` that the DXR
renderer admits and the [transport](TRANSPORT_PROTOCOL.md) can carry, so a real title's geometry can be drawn and sent
through the proxy/renderer path. It is an offline tool; nothing in the proxy runs it.

```powershell
python tools/position_to_scene.py LEDGER.jsonl --out build/some-new-folder [--group N] [--max-extent 1280]
```

The output folder must not exist. It receives `scene.rrscene` and `provenance.json`.

## What it uses

For each accepted draw the ledger holds the indexed corner positions, the exact vertex program's constants (c0, the clip
rows c4-c7 and the model rows c58-c60) and the clip and model positions the program produced
([position contract](HL2_POSITION_CONTRACT.md)). The tool:

1. groups draws that share a device, reset epoch, present interval, target, viewport and clip rows (the same grouping the
   [reconstruction](HL2_GROUPED_POSITION_REPLAY.md) tools use) and converts one group, by default the largest;
2. requires c0 to be the affine `(0, 1)` preparation, so the prepared position is `(x, y, z, 1)`, and a non-singular model
   matrix;
3. uses each draw's model rows as its world matrix and derives one view-projection from `clip rows x inverse(model)`,
   converting both to Direct3D's row-vector layout. Every draw gets the same bit-identical camera, which the renderer
   requires;
4. de-duplicates vertices (a repeated index with different positions is refused) and widens indices to 32 bits;
5. maps the capture's viewport to a scene extent of at most `--max-extent` pixels on the long side, keeping the aspect
   ratio. The format limits a side to 4096 and the captured 5120 x 1440 target becomes 1280 x 360; only the pixel grid
   shrinks, the projection is untouched;
6. renumbers draws 0..n-1, since the scene format wants increasing ordinals below the attempted count; the ledger's own
   ordinals are kept in `provenance.json`.

## The correctness gate

Nothing is assumed about conventions. Before anything is written, every vertex is projected through the scene's own stored
matrices exactly as Direct3D does (a row vector times world, view and projection) and must land on the clip position the
ledger recorded, within a relative 2e-4. The model-output position must match as well, and the result is checked against the
rules `rrt_dxr` enforces (one shared camera, full-frame viewport, affine world, opaque double-sided Gouraud state). A missing
transpose or a dropped model matrix fails the gate: the unit tests mutate the converter in exactly those two ways and require
the failure. No GPU is involved.

## What it does not claim

- **Geometry only.** The position ledgers carry no UVs, vertex colours, textures or materials. Every draw gets a 1 x 1 grey
  texture, white vertex colours and zero UVs, so the renderer shows relit grey geometry, not the game's look.
- **World space is the vertex program's model-output space.** The position contract calls its world-space meaning, units and
  handedness unverified, so the scene carries default metadata and the provenance sidecar says so.
- **Only one vertex program is admitted by capture.** It covered 231 of 2,996 indexed draws in the inventory pass (7.7%), so
  even a complete capture of the admitted program is a fraction of a frame. The 42 vertex programs a title uses, skinning
  among them, are a separate piece of work.
- **The existing ledgers are tiny.** The multidraw pass has 16 draws in four render groups of four draws and 48 triangles each.
  A recognisable frame needs a new capture session with larger limits.
- **No live path.** The proxy's HL2 capture writes position ledgers, not scenes. Using this from the proxy would mean
  porting the conversion to C++.

## Measured on the local HL2 passes

On 2026-10-27, RX 9070 XT (driver 32.0.32015.7029): the `hl2-multidraw-20260907` pass converts in all four groups, each of 4
draws, 48 triangles and 106 vertices, to a 1280 x 360 scene; the largest relative clip-position error is about 1e-6, the
float32 limit, and the shared-camera spread is zero. Rendered standalone, 95,374 of 460,800 pixels (21%) show geometry. The
frame through the transport (x86 `rrt_transport_host` driving the x64 renderer) has the same digest as the standalone render,
and the Debug and Release renderers agree. The other local ledgers with accepted draws (`hl2-combined`, `hl2-selected`,
`hl2-frames`) convert as well.

## Tests

- `tests/test_position_to_scene.py` (`position_to_scene`, also run by the Linux CI job): synthetic ledger records with
  asymmetric matrices cover the round trip and the gate, a wrong camera convention, de-duplication, the refusals (non-affine
  c0, singular model, partial viewports, mismatched record lengths), grouping and extent scaling, and exclusive output.
- `tests/verify_position_scene_local.py` (`position_scene_local`, local evidence): converts a real ledger, checks `rrt_dxr`
  admits it and draws geometry, and requires the transported digest to equal the standalone render. It skips with 77 when the
  ledger, the renderer (`-DRRT_X64_DXR=<x64 rrt_dxr.exe>`) or DXR hardware is missing. The ledger is the user's own capture;
  nothing derived from it is committed.
