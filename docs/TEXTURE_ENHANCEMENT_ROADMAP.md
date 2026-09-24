# Texture enhancement and material authoring roadmap

Requested 2026-09-08. Planned work, not currently implemented texture upscaling
or live HL2 replacement. Keep source-faithful replay as the comparison baseline.

Current foundation: v15 captures initialized managed RGBA and DXT1/DXT3/DXT5
chains with external hashed assets and isolated native pixel comparisons.
V16 additionally admits proven whole-chain default-pool uploads, and v17 records
explicit full-dirty notifications. V18 adds partial UpdateSurface coverage.
V19 adds observed texture-mip surface lock/unlock tracking, so a game that
stages a SYSTEMMEM texture through a mip-surface alias lock no longer loses its
upload proof. See SURFACE_LOCK_QUALIFICATION.md.
Game-sized material comparison and real-game material evidence remain before replacement
or upscaling work. See COMPRESSED_TEXTURE_QUALIFICATION.md.

## Sequence and acceptance gates

| Stage | Deliverable | Gate before advancing |
| --- | --- | --- |
| 1. Reliable asset capture | Immutable texture/mip bytes, format, dimensions, color-space/sampler metadata, content hashes, lifetime/revision and per-draw bindings | Initialized contents and updates survive aliasing, locks, copies and Reset; incomplete inputs rejected |
| 2. Source material replay | Bounded actual HL2 base/lightmap path with UVs, vertex color, constants and supported state | Native comparison on patterned textures, alpha, mips, address/filter/LOD and color space |
| 3. Reversible replacement | External manifest mapping source digest + interpretation to an enhanced asset; original bytes retained | Deterministic selection, preview, disable/rollback, stale-source rejection and unchanged source replay |
| 4. Offline base-color upscaling | Small reviewed batch, initially2×, optional4×; deterministic resize baseline plus optional model-backed candidates | No seam/alpha/UV regressions; measurable memory/load costs; visual review against original at equal camera/view |
| 5. Semantic material authoring | Separately authored normal/roughness/metallic/emissive candidates with provenance | Correct channels/color space and shading checks; inferred maps clearly distinct from captured evidence |
| 6. Workbench and runtime integration | Asset browser, before/after comparison, per-material approval, bounded asynchronous processing/cache | No game-thread inference stalls; stable replacement bindings, eviction, device loss/reset and rollback |

Do not select or download an upscaling model yet. Compare available local AMD-capable
inference routes when this stage begins, using pinned model/runtime versions,
compatibility, artifact license, throughput, peak VRAM and reproducibility tests.
CPU fallback and cancel/resume are part of the workflow. Quality targets, not a
specific vendor/model, define the contract.

## Texture classes need different treatment

- **Base color/albedo:** first candidate. Preserve intended art, text and painted
  features; avoid treating baked shadows/highlights as recoverable geometry. Review
  generative changes explicitly and retain a non-generative baseline.
- **Alpha cutouts/transparency:** process color and alpha deliberately; preserve
  alpha-test coverage across mip levels and avoid fringes. Record straight versus
  premultiplied interpretation rather than guessing.
- **Tiling textures and atlases:** use wrap-aware borders/overlap and seam tests;
  retain UV layout, island padding and dimensions expected by the source shader.
- **Normal maps:** separate path with channel convention, vector reconstruction/
  renormalization and tangent-space validation. Do not run a photographic upscaler
  blindly over vector data.
- **Packed masks/roughness/metallic:** handle channels as data, not display RGB;
  preserve binary masks/ranges and use appropriate mip policies.
- **Lightmaps:** defer automatic enhancement. The audited HL2 PS embeds1024×512
  reference scaling in its four-sample filter. Atlas/filter dependencies and baked
  illumination must be understood before resizing or replacing lightmaps.
- **UI/fonts, cube maps, render targets and dynamic/video textures:** separate
  policies. Exclude them from the first batch; never replace transient render
  targets just because their dimensions resemble a captured asset.

## Artifact and runtime requirements

Each replacement records source digest, semantic role, original format/extent,
scale, algorithm/model digest, settings, output digest, mip policy and approval.
Do not infer persistent asset identity from one resource pointer or equal pixels.
Interpretation is part of the cache key: the same bytes may serve different roles.

Generate complete mip chains, then evaluate supported output/compression formats.
Budget both decoded and resident GPU memory: doubling each dimension produces
four times as many base-level texels;4× per dimension produces16 times as many,
before mip/compression choices. Bound disk cache, batch size, upload staging and
resident VRAM. No unbounded background inference or silent quality fallback.

Initial replacement applies to offline reconstructed scenes. Live replacement is
a later, separately qualified step with asynchronous preparation and explicit
resource ownership. Never edit installed game archives or overwrite captured
originals as the default workflow.

## Related future work

- Geometry coverage: UV/color first for the audited pair, then normals/tangents,
  skinning/instancing and explicit object correspondence where evidenced.
- Materials and lighting: preserve a source-rendering mode; make PBR conversion,
  lightmap replacement/removal, authored lights and emissives explicit authoring
  choices. Upscaling alone does not recover physically based materials.
- Rendering: depth scope, continuous capture-to-DXR presentation, temporal
  stability, denoising and ray-reconstruction quality before live relighting claims.
- Screen-space upscaling/FidelityFX: separate from asset-texture upscaling, with
  its own motion/depth/reactive/history inputs and quality/latency tests.
- Product workflow: integrate into the
  [unified capture/workbench plan](UNIFIED_CAPTURE_UI_ROADMAP.md), while retaining
  the [separate API/engine tracks](API_ENGINE_ROADMAP.md).

Immediate priority remains the [audited HL2 material inputs](HL2_MATERIAL_AUDIT.md).
Texture enhancement should build on trustworthy assets, not delay or obscure the
missing material capture/replay contract.
