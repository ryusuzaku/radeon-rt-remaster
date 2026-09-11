# Partial surface uploads (v18)

V18 adds --position-surface-uploads / RRT_POSITION_SURFACE_UPLOADS=1 after v17
dirty-texture evidence and all prerequisites. It tracks explicit UpdateSurface
copies between observed private usage-zero SYSTEMMEM and DEFAULT 2D texture mips.
RGBA and DXT1/3/5 remain the supported formats. Earlier versions are unchanged.

## Copy and initialization rules

Surface owners and mip levels are resolved through GetContainer and canonical
COM identity. Matching dimensions alone do not identify a mip. Source and
destination formats must match; rectangles and destination points must be in
bounds with no scaling. These follow the [D3D9 UpdateSurface contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-updatesurface).

Only the copied source region needs known bytes. Explicit copies do not depend
on UpdateTexture dirty proof. Pixel/block rows are copied into preallocated
destination shadows only after native success, unchanged source/destination
revisions and epoch, and no observed overlap, history gap or open resource access.
Compressed partial copies require complete4x4 blocks; whole-mip copies can carry
tiny tails. Source and destination mip indices may differ.

Each successful copy marks its destination rectangle known. Every byte in every
mip must be known before capture. Later patches preserve other initialized
regions. Unknown source bytes, failed or unsupported copies, aliases, reset/gap
conditions and history exhaustion invalidate the destination conservatively.
Standalone off-screen sources, render-target textures, conversion, scaling,
dynamic textures and partial UpdateTexture reconstruction are not admitted.

UpdateTexture and UpdateSurface proofs are not mixed to establish coverage.
Switching from a whole-chain upload to surface history discards the old shadow
knowledge; subsequent surface copies must establish all mips again. A later
qualified whole-chain UpdateTexture can replace the surface history entirely.

## Bounded provenance and independent validation

Surface-initialized records use origin observed_private_default_surface and a
surface_transfers array. Each entry contains source identity/revision, source
and destination mip indices, source mip extent, source rectangle and destination
point. IDs are session-local provenance, not persistent object correspondence.

History is capped at128 entries per texture. Its reserved storage is charged
against the existing128MiB shared shadow budget. Exhaustion invalidates coverage;
a subsequent fresh sequence can re-establish the chain. Existing16MiB chain and
external asset limits remain. Invalidated history releases its entries while
retaining the charged bounded capacity.

Python independently validates history shape, IDs, bounds, block alignment,
source-extent consistency and complete destination coverage. Mip asset hashes and
sizes remain independently verified. V17 cannot admit the new record shape.
Importer preserves provenance; isolated pixel replay consumes final verified mip
bytes, not the transfer history as a sequence of native commands.

## Evidence and tests

The new texture_surface CTest case covers whole/partial copies, offset patches,
changed-chain refreshes, staged source initialization, differing mip indices,
recovery and switching back to UpdateTexture. It checks every recorded byte in
all16 captured draws per accepted case, native/proxy hashes of all24 float images
per scenario and one restored shader comparison per accepted scenario.
Incomplete coverage, unknown source data, failed copies, unaligned compressed
copies and history exhaustion reject. Reader negatives include missing/duplicate
coverage, invalid IDs/revisions/bounds/levels, history budgets, inconsistent source
extents, format alignment and legacy downgrade.

Release results:32 accepted cases,19 rejected native scenarios,48 malformed
records and four legacy runs. All51 native/proxy scenarios match;32 replayed
draws match at maximum6.93656e-8 normalized error. Reports are saved as
surface-upload-comparison.json in each fresh texture-surface-* test directory.

The compressed, upload, dirty and surface matrices are separate CTest cases,
each with a120s timeout and freshly generated fixture evidence from the pinned
local shader inventory. They require no previous test artifact. A shared CTest
resource lock serializes these native texture tests. position_capture retains
its original180s limit and the core capture/synthetic pixel checks.

## Gameplay gate

Texture transfer qualification is now broad enough to move on to the material
comparison scope. Saved HL2 evidence uses5120x1440 targets, while the isolated
material comparator still requires128x96 and fixed depth/blend/raster state.
Next qualify a clearly defined game-sized diagnostic comparison using saved
evidence and native fixtures, then reassess a targeted gameplay pass. Capturing
structural target metadata is not the same as replaying target/depth composition.
No new HL2 pass is needed for the completed surface-copy slice. Texture upscaling
remains planned after faithful material evidence.
