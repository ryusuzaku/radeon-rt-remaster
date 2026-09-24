# Texture-mip surface lock qualification — v19

Requested 2026-09-08; qualified 2026-09-11. Clause-v19 tracks observed
`IDirect3DSurface9::LockRect`/`UnlockRect` on the mip surfaces of a tracked
texture instead of invalidating the parent texture's shadow.

## Why this exists

The v18 material passes captured no textures at all. Every failing sampler0
resource was an initialized-but-unproven DEFAULT texture and every recorded
upload label was `source_not_fully_dirty`, with `upload_source_invalidation`
`UnlockRect` and no observed direct texture lock.

The cause was the version itself: the ledger header selects
`surfaceLocks?19:surfaceUploads?18:…`, and those passes ran at **18**. With
`surfaceLocks` off, `BeforeWriter` treated every surface `LockRect`/`UnlockRect`
on a tracked texture as an untracked write and called
`TextureInvalidate(resource, operation)`, which clears the whole coverage mask,
sets `fullDirty=false` and drops the dirty proof (see `texture_shadow.inc`,
`intercept.cpp`). A game that stages SYSTEMMEM textures by locking a mip
surface therefore lost its upload proof on every refresh.

v19 was already implemented and wired (`texture_tracking.inc`,
`generated_observers.inc`, `tools/game_pass.py --position-surface-locks`) but
had never been exercised against a game or covered by a test.

## Contract

- A **whole level-0** surface alias lock/unlock on a **MANAGED or SYSTEMMEM**
  owner declares `fullDirty=true` with dirty proof `top_lock`, so a following
  whole-chain `UpdateTexture` is admitted.
- A **partial** alias lock, a **lower-mip** alias lock and a **read-only** alias
  lock never declare a whole-chain proof. Coverage is updated only for the
  locked blocks, exactly as for a direct texture lock.
- The owner texture is resolved by container identity plus the level-identity
  walk; unresolved level identity falls back to invalidation, never to a
  dimension guess.
- **DEFAULT-pool** owners stay untracked at this stage, except **DYNAMIC**
  textures: a DEFAULT texture with `D3DUSAGE_DYNAMIC` and no render/depth-target
  bits is tracked when the v19 option is on. It is written in place through
  observed locks, never through `UpdateTexture`, so a fully observed revision is
  admitted with origin `observed_private_default_dynamic` and in-place proof
  `dynamic_proof=top_lock` instead of a transfer block. A `DISCARD` lock drops
  previous coverage (contents are lost); partial and read-only locks never
  declare whole-mip proof. A lock attempt on a non-dynamic DEFAULT destination
  surface invalidates its shadow, which is the intended rejection: an
  `UpdateTexture` source must be SYSTEMMEM.
- **Driver limits found while qualifying.** This driver returns
  `D3DERR_INVALIDCALL` for `D3DLOCK_NOOVERWRITE` on textures at any level, so the
  in-place path is exercised through `DISCARD` (which is only accepted when it
  covers the whole level — pass a null rect) and plain locks on the tail mips.
  The engine still accepts `NOOVERWRITE` where a driver does offer it.
- 16-bit float (`D3DFMT_A16B16G16R16`) texels are byte-opaque unit-1 payloads,
  admitted only on dynamic textures. Static float textures keep the
  `format_or_alignment` rejection.
- Option admission is unchanged and fails closed: locks require surface uploads,
  which require dirty tracking, uploads, compressed formats, external assets,
  texture inputs and the full multi-draw position chain. An out-of-range or
  broken value disables the capture rather than defaulting on.

## Qualification

`texture_locks` (`tests/verify_texture_paths.py --kind locks`,
`tests/qualify_surface_locks.py`) rewrites the source mip bytes **without** a
dirty declaration first, so only the alias lock can supply the proof. For RGBA
and DXT5 it asserts the accepted `aliasfull` case (16 captures, replay matched,
whole-chain `UpdateTexture` transfer with `dirty_proof=top_lock`, every mip
digest and extracted asset byte-exact, native output equal to the no-proxy
baseline) and the rejected `aliaspartial`, `aliasmip`, `aliasreadonly` and
`destalias` cases. The identical `aliasfull` case under v18 options must still
reject, and three invalid option chains must produce no capture file.

Fixture coverage added in `material_fixture.inc` (`alias*` actions) alongside
the pre-existing `sourcealias`, `dirtytop` and `partial` controls. Dynamic
coverage (`dynamic*` modes, full mip chains, RGBA plus float payloads) asserts
the accepted `dynamicfull`, `dynamicnodiscard` and `dynamicfloat` cases (16
captures, in-place proof, every mip digest and extracted asset byte-exact,
native output equal to the no-proxy baseline; RGBA also replays exactly — the
replay harness only rebuilds RGBA/DXT payloads) and the rejected
`dynamicpartial` and `dynamicreadonly` cases, plus the v18 rejection of
`dynamicfull`. Surface aliases of dynamic owners resolve through the same lock
path by container identity.

## Limits

This qualifies the tracking contract on the native fixture matrix; it does not
prove HL2 material capture. Real-game upstream admission, the DEFAULT-pool
`shadow_budget` ceiling and the 44 sampled unsupported shader families remain
open. See [COMPACT_TEXTURE_COVERAGE.md](COMPACT_TEXTURE_COVERAGE.md).

Validation: `texture_locks` passes Release 7.61 s and Debug 9.95 s; the full
`texture_*` group passes 7/7 in Release 164.61 s and 7/7 in Debug 217.80 s with
no other test changed. Release and Debug rebuilds of the x86 proxy and shader
fixture produce no warnings.
