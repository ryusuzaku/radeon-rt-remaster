# Compressed texture qualification

Opt-in capture v15 admits initialized private managed usage-zero DXT1, DXT3 and
DXT5 textures, alongside A8R8G8B8/X8R8G8B8. V13/v14 retain their uncompressed
format restrictions. Native fixtures qualify capture and isolated shader replay;
compressed resources from actual HL2 gameplay have not been tested yet.

Enable --position-compressed-textures / RRT_POSITION_COMPRESSED_TEXTURES=1 after
--position-texture-assets and all its prerequisites. V15 retains the external
hash/size mip representation,16MiB/chain,256MiB/512 files per session and128MiB
shared shadow budget. It creates the same exclusively owned <ledger>.assets store.

## Write evidence

Each compressed mip tracks known bytes in block coordinates. Successful direct
whole-mip locks and rectangles aligned on all four sides to4x4 blocks can declare
initialized regions. Tiny tails permit whole-mip locks only. Native pitch is
checked against the locked block-row width, and only those rows are copied before
native UnlockRect. Initialization becomes known only after successful unlock.
Disjoint partial writes merge; all mip bytes must be known before capture.

Failed locks/unlocks, unsupported flags, unaligned rectangles, surface-alias
writes, dirty notifications, copies and generated mips invalidate conservatively.
Read-only locks preserve existing knowledge; complete direct writes recover it.
Successful Reset invalidates through the existing global epoch. No destination
bytes are inferred from update/copy operations. Python independently computes
compressed sizes, checks base alignment and mip count, and resolves hashed assets.

## Storage and restoration

The existing RRT_PIXEL_REPLAY1 protocol carries tight compressed mip bytes.
DXT1 uses 8 bytes per 4x4 block; DXT3/DXT5 use 16. Row count and block count round
up, so a 2x2 or 1x1 mip still contains one whole block. D3D9 lock pitch is bytes
per block row ([Microsoft documentation](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dlocked-rect)).

The helper validates dimensions, format, maximum mip count and exact mip lengths
before creating a device. Base compressed dimensions must be multiples of four;
partial chains are allowed. Dimensions are bounded to16384 and chains to16MiB.
DXT2/DXT4 and other formats are rejected. Both write and read-only verification
locks require a positive pitch at least as large as the tight row. Every restored
row is compared byte-for-byte before shaders run, including tiny mip tails.

Both the exact original pixel shader and reconstructed HLSL sample the same
native textures. Matching results qualify restoration and shader arithmetic on
this machine; they do not independently validate DXT decompression or CPU sampling.

## Native fixtures

tests/qualify_compressed_pixel.py runs through position_capture. It constructs
known blocks with all color selectors, DXT1 one-bit transparency, DXT3 explicit
alpha and both DXT5 alpha endpoint modes. Twelve cases cover both samplers,
complete rectangular chains, final1x1 LOD, point/linear filtering, mip filtering
and sRGB. Changed texels, alpha constants and LOD must cause a mismatch.
Fully transparent blocks must produce zero output alpha; opaque blocks must
increase alpha relative to mixed blocks. Short tails, excess block bytes,
unsupported formats, misaligned base dimensions and excess mip counts reject.
Results are saved as pixel-compressed-comparison.json beside fixture ledgers.

tests/qualify_compressed_capture.py additionally checks full, quadrant-partial,
read-only and alias-refresh captures for all three formats. Every block in all16
accepted draws matches independently generated Python bytes. All24 native float
images have identical hashes with and without the proxy, including rejected-write
cases. Full captures replay every draw; other accepted cases replay their first
draw. Failed/alias/dirty/incomplete/unsupported-flag/unaligned writes reject, as do
DXT2/DXT4 resources and malformed/downgraded records. V13/v14 native runs reject
compressed textures. Uncompressed v15 and runner prerequisites are also checked.
Report: compressed-capture-comparison.json beside fixture ledgers.

## Next implementation gate

V16 now qualifies whole-chain default-pool uploads (TEXTURE_UPLOAD_QUALIFICATION.md).
Next qualify dirty notifications and partial/UpdateSurface paths. Another HL2 gameplay pass is
premature until those paths can provide useful material evidence. Texture
upscaling remains a later reversible offline step in TEXTURE_ENHANCEMENT_ROADMAP.md.
