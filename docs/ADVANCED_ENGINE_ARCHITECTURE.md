# Advanced engine reference and architecture decisions

User reference supplied 2026-09-07: skinning, instancing, material classification,
lightmap separation, radiance-cache invalidation and a 32→64-bit renderer bridge.
Retain these as future requirements, with the following scope and qualifications.

## Capture strategy

Continue API/resource/shader-aware capture as the reusable foundation. Optional
engine adapters may provide bone/instance/material/light identities from supported
SDKs, engine hooks or reviewed version-specific structures. Internal memory layouts
are not portable across builds and must not be guessed or modified generically.
The linked [dxvk-remix source](https://github.com/NVIDIAGameWorks/dxvk-remix) is an
architecture reference, not evidence that arbitrary engine internals are decoded.

## Geometry

- Capture initialized vertex/index data, declaration formats, bone indices/weights,
  actual constants or structured inputs, instance streams and update lifetimes.
  Avoid assuming that a raw VRAM read or a shader hash supplies missing semantics.
- Prove each supported deformation path against native execution. CPU evaluation
  is a correctness oracle; validated compute implementations are a later option.
- Rigid objects should normally share object-space BLAS geometry with per-instance
  TLAS transforms. Deformed meshes need an explicit deformed-space convention and
  suitable BLAS rebuild/refit policy; baking everything into world space sacrifices
  useful instancing and can double-apply transforms.
- Source buffers/ranges are not semantic objects. Resource generations, updates,
  instance data and explicit correspondence must be distinguished.

## Materials and baked lighting

- Pixel-shader hashes seed classification. A material key also needs texture and
  sampler bindings, constants, render states, texture coordinates and relevant
  permutations. Identical shader bytecode can serve many different materials.
- Map supported semantics to validated descriptors/material evaluators. Do not
  assume every shader requires a unique closest-hit shader or that legacy raster
  derivatives, screen-space effects and procedural inputs translate automatically.
- An AI-assisted offline tool may suggest mappings; uncertainty, human review and
  native/reference validation remain necessary. It is not an automatic PBR oracle.
- Separate lightmap contribution in our material representation where the binding
  and shader semantics are known. Do not blindly null a game sampler: that may
  sample black, alter unrelated effects or fail to remove lighting baked into the
  diffuse asset itself. Modifying original rendering requires a tested profile.
- For inseparably baked lighting, accept replacement/authored materials or an
  explicit approximation, not a claim that an unlit albedo pass was recovered.

## Radiance caching

Cache reuse requires compatible position, normal, material, lighting and scene
visibility—not only a spatial hash. A moved occluder can affect indirect light
outside its own bounds; transform/velocity changes are inputs to invalidation,
not a complete invalidation policy. Track geometry, lighting, emissive/material,
camera/scene epochs and provider history; evaluate disocclusion and ghosting.

Probe/surfel schemes and AMD's neural cache are different implementation choices.
AMD describes its current [FSR Radiance Caching](https://gpuopen.com/manuals/fsr_sdk/techniques/radiance-cache/)
as a learned path-tracing acceleration technique with training/query workflows;
do not substitute a generic hit/miss dictionary for its integration contract.
Our existing provider experiments remain separate from commercial-game integration.

## Process boundary

Keep the small legacy client and large 64-bit renderer separated for memory headroom
and failure isolation. [Remix bridge](https://github.com/NVIDIAGameWorks/dxvk-remix/blob/main/bridge/README.md)
is a concrete 32/64-bit reference. This is an architecture choice, not a blanket
claim that Direct3D12 cannot be used by any 32-bit process; Microsoft's
[D3D12 setup documentation](https://learn.microsoft.com/en-us/windows/win32/direct3d12/directx-12-programming-environment-set-up)
includes 32-bit library configurations.

Do not assume every 32-bit executable has 4 GiB usable address space. Keep CPU
address limits distinct from GPU resource allocation. The protocol needs fixed-width
IDs/offsets (never cross-process pointers), resource generations, bounded queues,
synchronization/fence ownership, back-pressure and reset/crash recovery. Existing
shared-buffer/session experiments are foundations, not a finished game renderer.

## Current next step

Versioned resource/update provenance for the proven HL2 position subset, then
explicit scene correspondence and update integration. Skinning/material/engine
adapters do not bypass these gates. No new gameplay request until the next useful
instrumented capture is built and tested.
