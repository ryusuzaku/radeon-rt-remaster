# Position composition evidence (v6)

Opt-in runner `--position-render-state` requires selected multi-draw capture.
It sets `RRT_POSITION_RENDER_STATE=1`; invalid configuration disables position
capture. Without the option, legacy v1–v5 contracts remain unchanged.

Each accepted v6 record contains `render_state`:

- `target_id`: render target0's resource-private lifetime tag. Different surfaces
  with identical dimensions/formats receive different IDs. These are process-local
  tags, not native pointers, cross-session IDs, asset hashes or engine objects.
- `depth_id` and `depth_desc`: bound depth/stencil surface identity and descriptor,
  or0/null when none is bound. Descriptors are width,height,format,multisample type.
- `clear_serial`: device-local count of successful observed Clear calls.
- `binding_serial`: device-local count of successful observed SetRenderTarget or
  SetDepthStencilSurface calls, including redundant same-resource bindings.
- `states`: raw DWORD values for depth enable/write/function, alpha-test fields,
  colour/separate-alpha blend fields and factor, colour write mask0, cull/fill,
  scissor/stencil enables, sRGB write and depth-bias fields.
- `scissor`: the effective rectangle, stored even when scissoring is disabled.

State queries use the native device at capture time, including state applied by
state blocks; captured position-constant admission retains its existing conservative
state-block invalidation. Surface tags use resource-owned private data without
resource/device back-references or pixel readbacks. Failure to gather required
metadata rejects that candidate. A tracked clear/binding boundary changing before
commit also rejects the candidate rather than accepting stale boundary evidence.

The reader requires exact fields, integer ranges, depth identity/descriptor
consistency and complete selected-state keys. Import/reconstruction preserve the
metadata; compatible-view grouping includes its exact value, separating target,
depth, clear, binding and selected-state changes. Legacy files cannot claim v6
metadata. Raw state validation is not an assertion that every value is executable
or supported by a future renderer.

## Deliberate limits

Opt-in v7 now adds a bounded latest successful clear payload; see
`POSITION_CLEAR_EVIDENCE.md`. It does not establish complete initial contents or
remove the v6 limitations below for files that contain markers only.

The serials are **markers, not replayable clear commands or semantic pass IDs**.
They count all successful observed device calls, including partial clears and
operations on other targets. They do not include clear flags/colour/depth/stencil,
rectangles, initial surface contents, MRT identities, surface writes via other
APIs, all stencil operations or material/pixel-shader behavior. Reset epochs and
Present intervals stay part of the grouping key. Conservative over-splitting is
possible; absence of a marker does not prove an uninterrupted engine pass.

The existing group replay remains a diagnostic: it clears once and uses depth-off,
blending-off overwrite order. Recorded state is shown and used for separation,
**not applied as a purported game-frame reconstruction**. Next capture bounded
clear-operation data and qualify state-aware replay, including explicit failure
or fallback for incomplete initial contents and unsupported state combinations.

## Verification

Native fixtures exercise stable target IDs, recreation of same-size targets,
clear/binding serial changes, alpha-reference changes, absent/present depth
surfaces and enabled ONE/ZERO blending while preserving the raster oracle.
Reader mutations test missing metadata, invalid IDs/serials/state values/scissors,
depth inconsistency and legacy-version spoofing. Runner tests verify opt-in
requirements and child environment/report propagation. Real-game v6 qualification
has not been performed by these synthetic tests.
