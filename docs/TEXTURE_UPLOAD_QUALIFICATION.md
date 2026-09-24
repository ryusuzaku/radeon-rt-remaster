# Whole-chain texture uploads (v16)

V16 admits captured private usage-zero default-pool 2D textures initialized by a
proven whole-chain UpdateTexture from a tracked system-memory texture. Managed
v15 textures remain supported. Enable --position-texture-uploads or
RRT_POSITION_TEXTURE_UPLOADS=1 after --position-compressed-textures and its full
prerequisite chain. Formats remain A8R8G8B8/X8R8G8B8 and DXT1/DXT3/DXT5.

## Full-transfer proof

D3D9 creates textures fully dirty, but UpdateTexture clears source dirty regions;
later calls may copy only a subset. A complete byte shadow alone is insufficient.
See Microsoft's [dirty-region contract](https://learn.microsoft.com/en-us/windows/win32/direct3d9/texture-dirty-regions)
and [UpdateTexture reference](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-updatetexture).

The tracker starts with full-dirty proof on observed creation. Every observed
UpdateTexture source attempt consumes that proof, including failed or unsupported
transfers. A successful whole top-level writable lock can restore it, because
that lock dirties the entire chain. Lower-mip locks alone cannot restore it.
Existing conservative invalidation clears proof as well as initialized bytes.

The source must have every byte known, no pending writes, matching epoch and a
positive revision. Source/destination dimensions, format and mip count must match
exactly; usage is zero and pools are SYSTEMMEM/DEFAULT respectively. BeforeWriter
invalidates the destination first. The upload hook retains COM references and
revisions across the native call. Only native success, unchanged revisions/epoch
and no observed overlap or write-history gap establish destination bytes.
Preallocated destination shadows receive independent byte copies and source
provenance. Later source writes cannot change captured destination contents.

Default-pool direct writes are not admitted. Partial updates, clean-source
repeats, aliases, uncertain sources and failures leave destination contents
unknown. Differing mip counts are rejected even when native D3D9 can match a
suffix. UpdateSurface, dynamic textures and explicit dirty-region accumulation
remain separate qualification work.

## Evidence and limits

Default-pool texture_inputs records have origin observed_private_default_update
and transfer {operation:UpdateTexture, scope:whole_chain, source, revision}.
Source denotes a session-local observed system-memory resource identity. It is
not a persistent asset ID. Managed records keep their previous shape and origin.
Python validates origin/pool, transfer shape and IDs, and rejects contradictory
shared-source snapshots. Existing asset hashes, dimensions and limits still apply.
V15 and older versions cannot claim these default-pool transfers.

The external store,16MiB per chain,128MiB combined shadow allocation and
256MiB/512-file session limits are unchanged. Both source and destination shadows
count toward the memory bound. Serialized source IDs do not retain resource
objects. Pending native calls retain COM references only until completion.

The isolated replay restores verified bytes into managed diagnostic textures.
Pool/lifetime/update execution itself is not reenacted by replay. Native source
and reconstructed shaders share texture sampling; full-frame equivalence and
real-game uploaded-material behavior are not claimed.

## Native fixture matrix

tests/qualify_texture_upload.py runs in the independent texture_upload CTest and can also run
directly with --capture <existing-material-ledger> --fixture <exe> --proxy <dll>.
RGBA and DXT1/3/5 cover first uploads, partial initialization before first upload,
changed full rewrites, alias recovery and post-upload source mutations. Every
accepted block/texel is checked independently across16 draws; all full-capture
draws and the first draw of other accepted cases replay. Native/proxy output
hashes cover all24 float images per fixture scenario.

Partial repeats, lower-only writes, incomplete chains, consumed dirty proof, invalid-pool failures, unknown/aliased
sources, destination aliases and mismatched mip chains reject. Malformed transfer
records, legacy versions and invalid prerequisites reject. The failed-call test
uses valid resource objects with an invalid pool combination: this runtime faults
when given a null UpdateTexture destination. Reports are saved as
texture-upload-comparison.json beside fixture ledgers.

Final Release fixtures cover20 accepted cases,80 uploaded draw comparisons,
56 native/proxy hash comparisons,36 rejected scenarios,40 malformed records and
four legacy runs. Maximum uploaded shader error6.93656e-8. Build and regression
results come from `ctest --test-dir build/x86-vs -C Release -R '^texture_upload$'`,
which regenerates this evidence rather than recording it in a document.

V17 now qualifies explicit full-dirty notifications and SYSTEMMEM NO_DIRTY_UPDATE
writes (DIRTY_TEXTURE_QUALIFICATION.md). V18 adds explicit UpdateSurface rectangles
(SURFACE_UPLOAD_QUALIFICATION.md). Next game-sized isolated material comparison,
then reassess a targeted HL2 gameplay pass. No new pass is needed yet.
