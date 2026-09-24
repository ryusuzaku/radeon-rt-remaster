# External texture assets (v14)

V14 stores initialized mip bytes outside the JSON ledger, enabling larger managed
textures while keeping each draw record bounded. Enable --position-texture-assets
or RRT_POSITION_TEXTURE_ASSETS=1 with the full v13 prerequisite chain.

The store is a sibling directory named `<ledger-path>.assets`. Each mip is saved
as `<lowercase-sha256>.bin`. A v14 texture_inputs mip entry contains exactly
`sha256` and `size`; dimensions/format still come from the same draw's sampler
descriptors. Identical mip bytes are stored once across textures and draws.
Ledger records never supply filenames or arbitrary paths.

## Bounds and ownership

- At most16MiB per complete texture mip chain; formats and resource admission
  remain private, observed, managed usage-zero A8R8G8B8/X8R8G8B8.
- At most256MiB and512 newly created files per capture session. Failed writes
  consume reservations too. The shared initialized shadow budget remains128MiB.
- The existing16MiB ledger,1.2MB record,16 accepted-draw and draw-size bounds
  remain unchanged. Inline v13 retains its64KiB-per-texture limit.

The native writer creates the asset directory exclusively after writing the
ledger header. An existing directory causes an I/O-error completion, preserving
its files. Blob creation is exclusive too; no existing file is overwritten.
Completed writes are reused within the session by hash. The writer rejects a
reparse-point asset directory. A rejected draw or failed write can leave orphan
assets or an incomplete blob; those remain within the budget and do not establish
accepted evidence. Cleanup/garbage collection is not automatic.

## Reading and replay

Path-based inspection and scene import locate the sibling directory automatically.
Raw inspect_bytes callers must provide a TextureAssets resolver for accepted v14
records. The resolver validates lowercase hashes, declared dimensions/byte sizes,
regular-file status, reparse/symlink status, SHA-256 and total referenced bytes.
Missing, shortened, corrupted or misleading references are rejected. There is no
fallback to another directory or an unverified cached asset.

Each inspection caches the bytes it verified, so its immutable snapshot remains
stable if files change afterward. A fresh inspection checks files again. This is
content verification, not a filesystem transaction against arbitrary concurrent
directory replacement. Move or rename a ledger together with its correspondingly
named `.assets` directory; content hashes and ledger identity remain unchanged.

The scene importer retains asset references as metadata. The pixel comparator
restores verified blobs from either v13 or v14 and supports the16MiB texture bound
in its native payload. It processes draws sequentially; restored bytes are not
expanded into every source JSON row. The isolated-draw/raster/sampler qualification
from PIXEL_MATERIAL_RECONSTRUCTION.md remains unchanged. Position and constant-color
diagnostic readers also resolve v14 assets without broadening their replay scope.

## Validation and next slice

Native tests capture complete256x128 mip chains beyond the old inline limit,
verify every patterned byte, check file deduplication and compact ledgers, import
the references, and compare original/reconstructed PS output after restoration.
Tests cover corrupt/missing files, path-like hashes, conflicting sizes, inline
payload injection, legacy downgrade, texture/session budgets, bundle relocation,
cached snapshot stability, missing prerequisites and existing-directory collision.

Next qualify compressed textures and relevant default-pool/update paths. V14
changes storage capacity, not supported texture formats or initialization rules.
Another HL2 pass should wait until capture covers those game resource paths and
the material comparison can answer a useful new question. Future enhancement
remains in TEXTURE_ENHANCEMENT_ROADMAP.md after faithful source capture/replay.
## V15 extension

V15 adds opt-in DXT1/DXT3/DXT5 initialized block capture while preserving the
external store contract above. V14 remains uncompressed. See
COMPRESSED_TEXTURE_QUALIFICATION.md for write rules, fixture evidence and limits.
