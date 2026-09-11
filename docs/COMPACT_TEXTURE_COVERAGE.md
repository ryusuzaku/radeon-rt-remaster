# Compact texture coverage — 2026-09-08

The texture-context HL2 pass confirmed shadow-budget exhaustion and a failed
source dirty/epoch upload check for sampler0 DXT5 DEFAULT textures. It admitted
no materials. Game closed normally; proxy removed and executable unchanged.

## Storage change

Each tracked mip now has one coverage flag per uncompressed texel or compressed
block instead of one per payload byte. Every admitted writable lock and surface
copy already covers complete units (RGBA4 bytes, DXT1 block8 bytes, DXT3/5 block16
bytes). Payload copies retain their original byte offsets and lengths. Only mask
indices, coverage counting and mask allocation change. A known flag therefore
proves exactly the same bytes as before; partial compressed blocks stay rejected.
Tiny compressed mip tails still require whole-block evidence.

Known-byte diagnostics multiply the flag count by unit size. New optional
coverage_bytes reports mask storage, independently validated against format and
payload size. The shadow reservation charges payload plus actual mask sizes and
existing surface-history capacity, within the unchanged128MiB shared limit.
Resource destruction returns that reservation. Buffer masks remain unchanged.
For DXT5, payload plus coverage storage drops from32 to17 bytes per block (46.875%
less); RGBA drops from8 to5 bytes per texel (37.5% less). Metadata/driver storage
is additional, as before. No larger per-texture, ledger or asset budget is used.

## Upload diagnostics

The former source_dirty_or_epoch label is split into source_not_fully_dirty,
source_dirty_proof_missing, source_pool, source_epoch and source_revision.
New optional upload_source_lock_flags and upload_source_invalidation snapshot
source history before consuming its dirty proof. Null flags mean no observed
source lock. They describe the most recent observed upload attempt, not necessarily
current source state. Older texture-diagnostic records remain readable.
No dirty-region inference, new pool/usage admission or copy semantics are added.

## Qualification

Native matrices verify original byte hashes, restored material comparisons,
partial and compressed copies, dirty notifications and failure rejection.
Focused tests check RGBA/DXT5 mask ratios and upload-source flags. A retained
64-texture DXT5 workload checks improved headroom;96 textures still exhaust the
limit, and releasing them permits a subsequent initialized texture to be captured.
The native renderer still compares each fixture image against the independent
vertex-material evaluation.

Next useful HL2 pass retains2560x1440:3/full v18 settings and observes whether the
smaller masks relieve tracking failures and which precise upload check remains.

Validation: Release6/6 passed184.67s plus final selection/pressure6.54s;
Debug2/2 passed13.62s.64-texture capture,96-texture rejection and release
recovery checks passed; builds and Python compile passed.
