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

## Shared shadow-budget ceiling

Measured 2026-09-11. `Retained()` is the process-wide reservation counter. It is
charged in exactly two places — buffer locks (`total*2` payload plus mask) and
`TextureCreated` (`payload + mask + 128*sizeof(SurfaceTransfer)` when the pool is
DEFAULT with surface uploads enabled) — and released only in `~Shadow` and
`~TextureShadow`. Every early return in `TextureCreated` reverts its own charge,
and a rejected texture never sets `tag->texture`, so its shadow is destroyed with
a zero reservation. There is no leak and no double release; `maskrelease` already
proves release on destruction.

The limit is therefore a *priority* limit, not an accounting defect. Per-chain
reservations and how many fit in the unchanged 128MiB cap:

| chain | payload | mask | history | total | fits |
| --- | --- | --- | --- | --- | --- |
| MANAGED 1024x1024 DXT5 | 1398112 | 87382 | 0 | 1416494 | 90 |
| DEFAULT 512x512 DXT5 | 349184 | 21824 | 7168 | 378176 | 354 |
| DEFAULT 512x256 DXT5 | 174080 | 10880 | 7168 | 192128 | 698 |
| DEFAULT 128x512 DXT5 | 86016 | 5376 | 7168 | 98560 | 1361 |

This reproduces the retired 64-texture accept / 96-texture reject workload
exactly (64x1485494 = 95.1MB accepted, 96x1485494 = 142.6MB rejected), so the
model above is the one the code implements.

`texture_selection` asserts the DEFAULT-pool boundary through the `defbudget` /
`defexhaust` / `defrelease` fixture cases. A DEFAULT destination cannot be filled
directly, so each case allocates 512x512 DXT5 DEFAULT textures and supplies the
proof from a SYSTEMMEM source `UpdateTexture`. 300 is admitted with 16 captures
and a whole-chain `top_lock` transfer; 370 is refused with no captures, an
`evidence_failures` entry of `texture_inputs`/`texture_tracking_missing`, and a
`shadow_budget` diagnostic whose descriptor is 512x512, pool 0, with zero total
and known bytes; releasing and reallocating restores 16 captures. With the 512x512
SYSTEMMEM source also charged (371008 bytes) the computed boundary is 353, so the
test brackets it to (300, 370] rather than pinning the exact count.

From a fresh budget, 512x512 DEFAULT DXT5 fits 354 times. The recording pass had
155 of these tracked and 76 refused, so the live set had already consumed
essentially the whole cap with textures created earlier in the session. Creation
order alone decides admission: the cap admits what the game creates until it is
full, and nothing is reclaimed while a resource stays alive.

Mapping onto the recorded failures: v19 surface-lock tracking addresses the 305
`texture_upload_proof_missing`; the 76 `texture_tracking_missing` are this
ceiling. All 76 are pool 0 (DEFAULT). Any change to that balance is an explicit
budget-policy decision; no larger budget has been adopted.

### Attribution (2026-09-16)

The footer now reports the split, so the policy question can be answered from
evidence rather than inference: `retained`, `retained_buffers`,
`retained_textures` and `live_textures`, written when the capture stops
(`capture_limit`/`attempt_limit`/`present_limit`). The reader validates them when
present, requires the total to equal the two parts, and a ledger with no stop
reason claims no attribution. The trace cannot supply this: `ObjectCreated`
records only the interface name, so no resource size or descriptor is recoverable
from it.

First measurement, from the `material3` trace window (60 presents): only **2
distinct buffers** were ever locked, and their total locked extent bounds their
shadow charge at **1,711,596 bytes = 1.63 MiB, 1.3% of the cap**. Buffer shadows
are therefore negligible here, and **partitioning the counter between buffers and
textures would buy essentially nothing** — that option is ruled out. The ceiling
is consumed by texture shadows, where the observed 1024x512 `A16B16G16R16`
dynamic inputs cost ~4.5 MiB each. The trace window is not the whole session, so
the exact split for a full pass comes from the new footer on the next run.

**That trace-derived conclusion was wrong and is retracted.** The `material4`
footer, measured over the whole session, reports:

| | bytes | MiB | share of the 128MiB cap |
| --- | --- | --- | --- |
| retained total | 104499516 | 99.66 | 77.9% |
| buffer shadows | 22664152 | 21.61 | 16.9% |
| texture shadows | 81835364 | 78.04 | 61.0% |

with **636 live textures** (about 125KiB each). Buffers hold roughly 13x more than
the 60-present window suggested: in that window only two buffers happened to be
locked, while across a session many more are locked and held for life. The lesson
is the one that motivated the instrument — a window is not the session, and
attribution has to come from the accounting site. Handling 1024x512
`A16B16G16R16` dynamic inputs at ~4.5MiB each is still what tips the cap over, but
buffers are a real, non-trivial share and partitioning is back on the table.

Caveat on those numbers: the footer is written when the capture stops, and a
refused texture proves the total was higher at that moment (a 4.5MiB reservation
cannot be refused against 99.66MiB of 128MiB). The split at the *peak* is what
decides the policy, so the instrument should also report a high-water mark.

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

Next useful HL2 pass retains2560x1440:3 and adds the v19 surface-lock option
(`--position-surface-locks`) on top of the full v18 chain. The recorded v18 pass
ran with surface locks off, so every mip-surface lock invalidated the source
shadow and produced `source_not_fully_dirty`. See SURFACE_LOCK_QUALIFICATION.md.
**That pass has since run — see "Where the budget decision stands" below.**

Validation: Release6/6 passed184.67s plus final selection/pressure6.54s;
Debug2/2 passed13.62s.64-texture capture,96-texture rejection and release
recovery checks passed; builds and Python compile passed.

## Where the budget decision stands — 2026-09-24

The pass this document called for has run. `material3` (2026-09-16) captured 16
material draws with the v19 surface-lock chain enabled — the `top_lock` dirty and
dynamic proofs are its evidence — so v19 is no longer "qualified on fixtures but
never run against a game". See
[HL2 dynamic material capture](HL2_DYNAMIC_MATERIAL_CAPTURE.md).

What that pass did **not** resolve is the budget. Its 20 remaining
`texture_tracking_missing` failures are a 1024x512 `A16B16G16R16` DYNAMIC DEFAULT
input of ~4.5 MiB each, refused at `shadow_budget`. The dynamic-admission and
16-bit-float gates both pass, so capacity is the only obstacle.

**The decision cannot be made from the numbers we have.** The `material4` footer
reports 99.66 MiB retained against a 128 MiB cap while a 4.5 MiB reservation was
being refused, which is only consistent if the total was higher at the moment of
refusal. The split that decides policy is the one at the **peak**, not at the stop.

That instrument now exists. Charges sample `retained_peak`, `peak_buffers` and
`peak_textures` from the authoritative split counters; the reader validates that
the peak split sums and never sits below the stop value; `texture_selection`
asserts the same on fixtures. **No game pass has run since it landed**, so the peak
numbers do not exist yet.

The next step is therefore a measurement, not a policy change. One HL2 pass with
the instrument reports whether the peak is buffer-dominated or texture-dominated,
and that single number chooses between the candidates below.

### Candidates, and what each needs

| Option | What it would take | Blocked on |
| --- | --- | --- |
| Raise the cap | One constant plus a stated VRAM rationale | Knowing the peak, so the new cap is not another guess |
| Partition buffers vs textures | Separate counters and limits per kind | Knowing the peak split — the retraction above shows a 60-present window cannot supply it |
| Reclaim instead of holding for life | Eviction or re-creation of texture shadows | A quality and correctness argument; nothing is reclaimed while a resource stays alive today |

Raising the cap is the smallest change and the easiest to justify if the peak turns
out texture-dominated with legitimately live textures. It also needs the least new
machinery. None of the three should be chosen by inference from a window, which is
the mistake this document already records once.
