# HL2 dynamic material capture — 2026-09-16

The first HL2 pass to capture material draws. Every earlier HL2 pass captured
zero, and the reasons why are recorded below rather than smoothed over.

Bundle: `build/game-passes/hl2-dynamic-v19c-20260916`. That directory is not
version controlled, because a game-pass bundle can embed extracted game content
and the project does not redistribute game assets. The command that produces one
is in [the game pass workflow](GAME_PASS.md).

## Result

`material3` reached its capture limit with **16 captured draws** at render target
`[1920,1080,21,0]`.

| | |
|---|---|
| Captured draws | 16 |
| Texture inputs | 32 |
| External assets | 19 files, 5,327,872 bytes |
| Attempts | 668, stopping after 4 presents |
| Selection | `--position-selection any:3` |

The 32 texture inputs split evenly:

- 16 whole-chain `observed_private_default_update`, dirty proof `top_lock`.
- 16 in-place `observed_private_default_dynamic`, dynamic proof `top_lock`, no
  transfer block.

## What unblocked it

Two structural gaps, and either one alone would have kept the pass at zero.

**1. Selection required knowing the render-target extent in advance.** The
earlier v18 pass completed its ledger with 1,574 attempts, 1,573 recorded
rejections and **0 material captures** — every recorded reason
`selection_target_mismatch` for a hardcoded 5120x1440, with the actual target
dimensions never present in the header. See
[the v18 result](HL2_MATERIAL_V18_RESULT.md), which records that failure in full.
`--position-selection any:MIN_TRIANGLES` now selects on primitive count alone and
records `any_target`, so no extent has to be guessed before the run.

**2. The trigger fired outside a presenting interval.** The v18 pass consumed its
entire byte limit before any position-capture Present was recorded. Triggered
capture now arms on a real Present and stops at the interval, so material3
finished in 4 presents / 668 attempts instead of exhausting the 4,096-attempt
budget inside a non-presenting interval.

## Remaining failures in the same pass

| Reason | Count | Cause |
|---|---:|---|
| `texture_tracking_missing` | 20 | 1024x512 `D3DFMT_A16B16G16R16` DYNAMIC DEFAULT sampler input, ~4.5 MiB each, refused at `shadow_budget` |
| `unsupported_shader` | 15 | outside the pinned-program allowlist |
| `selection_primitive_minimum` | 6 | below the 3-triangle floor |

The dynamic-admission and 16-bit-float format gates both pass, so the 20 texture
failures are **purely the shared budget** — not a format or tracking limitation.
Whole-session attribution is in
[compact texture coverage](COMPACT_TEXTURE_COVERAGE.md): 77.9% of the 128 MiB cap
retained, of which texture shadows are 61.0% and buffer shadows 16.9% across 636
live textures.

That document also records a retraction worth repeating here: an earlier estimate
taken from a 60-present trace window put buffer shadows at 1.3% of the cap and
concluded that partitioning the counter would buy nothing. The `material4` footer,
measured over the whole session, shows 16.9%. A window is not the session, and
attribution has to come from the accounting site.

## What this does not establish

Captured draws are recorded draws, not unique scene objects; draws may repeat
geometry or represent additional passes. Coordinate interpretation, material
fidelity, full-scene reconstruction and live relighting are **not** validated. A
game-sized material comparison — native vs proxy vs replay on a captured draw —
has not been run; see
[game-sized material comparison](GAME_SIZED_MATERIAL_COMPARISON.md) for what the
comparator already supports, including the 5120x1440 and offset-viewport cases
that were previously assumed to be blocked by tooling.

Capturing material evidence is not the same as reproducing the game's image.
