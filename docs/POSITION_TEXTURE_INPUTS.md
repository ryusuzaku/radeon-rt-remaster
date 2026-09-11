# Initialized texture evidence (v13)

V13 adds actual mip bytes to the paired material ledger. The initial contract
admits observed, private, managed 2D textures with usage zero and format A8R8G8B8
or X8R8G8B8. Each complete mip chain must fit within 64 KiB. Shared resources,
render targets, depth textures, default/system-memory pools, compressed formats
and larger textures are not admitted by this slice.

Enable `--position-texture-inputs` or `RRT_POSITION_TEXTURE_INPUTS=1`, with the
full v12 prerequisite chain. No game installation or launch is needed for the
synthetic validation. All previous capture budgets and shader restrictions apply.

## Initialization and invalidation

Texture creation must be observed. Tracking starts with every byte unknown.
A successful writable direct Texture9 LockRect with flags zero declares a write
rectangle; those bytes become unknown until a successful UnlockRect. The tracker
copies rows immediately before native unlock, then marks the rectangle known only
after success. Row padding is omitted. Multiple partial writes can initialize an
entire mip. As with buffer capture, the application's writable lock rectangle is
its declared initialized region; individual CPU stores are not instrumented.

Direct read-only locks preserve existing knowledge and do not establish new
knowledge. Unsupported flags (including NO_DIRTY_UPDATE), failed locks/unlocks,
and unsafe bounds invalidate the texture. Pending writable locks prevent capture.
All mips must be completely known, even when the current sampler might select
only a subset. The shared buffer/texture shadow budget is 128 MiB, counting byte
storage and initialization masks; resource destruction releases its reservation.

Surface aliases are resolved through native GetContainer. Observed surface writes
invalidate their parent texture. Copies, dirty notifications and mip generation
also invalidate their destination; no source bytes or generated values are
inferred. Invalidation occurs before those calls, including failures, so rejection
is deliberately conservative. Successful device resets invalidate texture
knowledge by epoch. Direct complete writes can restore knowledge afterward.

This is an observed-call contract. Existing unobserved-write and scope limitations
remain visible; resource IDs do not prove correspondence across sessions. Managed
usage-zero admission excludes GPU render-target/depth writes to captured textures.

## Ledger contract

`texture_inputs` has two entries, in s0/s1 order. Each entry contains:

- `id`: the matching v12 sampler resource identity.
- `revision`: a positive local texture-knowledge revision.
- `origin`: exactly `observed_private_managed`.
- `mips`: ordered entries with tightly packed lowercase hex `bytes` and `sha256`.

Mip dimensions and format come from the same draw's `pixel_material` descriptors.
The v12 descriptor field `contents="unknown"` remains metadata-only; the separate
v13 `texture_inputs` field supplies the initialized-byte evidence. The reader
checks identity, provenance shape, admitted format/pool/usage, chain size, byte
lengths and hashes. If both slots refer to one texture, snapshots must agree.
The importer retains this data as candidate metadata, not as textured scene assets.

Two 64 KiB hex snapshots plus the largest admitted position/material draw stay
within the existing 1.2 MB record limit. V14 now provides bounded external asset
storage for larger textures; see TEXTURE_ASSET_STORAGE.md.

## Validation and next work

Native controls compare original-VS and CPU-evaluated vertices under the same
native paired PS. Tests verify every patterned mip byte, binding identity and
hash after full writes, partial writes, read-only locks and alias invalidation
followed by refresh. Failed locks, failed managed-destination copies, surface alias
writes, generated mips and incomplete reinitialization reject capture. Malformed
records and inherited hook ordering are checked as well. Failed-unlock and reset
invalidation are implemented; reset-hook wiring is checked, but these do not yet
have a dedicated native recovery scenario in this slice.

The audited five-sample pixel path and sampler controls are now implemented;
see PIXEL_MATERIAL_RECONSTRUCTION.md. V14 external storage is also implemented.
Next qualify compressed textures and relevant default-pool/update paths. Request a
guarded HL2 pass when the evidence and replay paths can provide a useful material
comparison in one launch. Future enhancement remains in
TEXTURE_ENHANCEMENT_ROADMAP.md after faithful source replay.
