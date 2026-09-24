# API and engine expansion roadmap

Requested 2026-09-07. These are future qualification tracks, not supported-game
claims. Current focus stays on validated HL2 position capture, scene updates and
material contracts. No third-party wrapper is installed by this roadmap change.

## D3D9 Shader Model 3 and Unreal Engine 3

Broaden from exact-program fixture support to representative SM3 vertex/pixel
program contracts: constant addressing, branching, skinning, instancing and
vertex-texture dependencies must be handled or explicitly rejected. An SM3 fixture
already exists, but arbitrary SM3 game programs are not supported.

Qualify an owned UE3 title separately: capture its actual program/layout families,
depth/material conventions, render passes and animation. Engine family names do
not establish a common binary shader contract. Maintain BioShock/BioShock2 as
separate named profiles rather than assuming their renderer equals a generic UE3
profile; identify exact edition/build and active API before each qualification.

## Direct3D 10 / BioShock follow-up

DX10 is a separate interception/backend milestone, not SM3 support on D3D9.
Microsoft documents its Shader Model4 pipeline and changed resource/state model:
[D3D9-to-D3D10 considerations](https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-d3d9-to-d3d10-considerations).

Plan DXGI/device/swap-chain observation, buffer/input-layout and DXBC shader
evidence, explicit resource/view/state semantics and programmable-stage handling.
Feed validated results into the shared scene representation, not a separate
game-specific renderer. Do not assume D3D9 shader bytecode/parser is reusable.

Local BioShock2 evidence remains authoritative for this machine: default native
path worked; forcing DX9 crashed uninstrumented. Keep its stable default-path
follow-up on the DX10 qualification track, with actual loaded API verified before
claiming a DX10 pass. Do not repeat forced DX9 merely to fit the current proxy.
Original and remastered editions must not share an assumed API profile.

## D3D8 via D3D9 translation

Candidate: [crosire/d3d8to9](https://github.com/crosire/d3d8to9), whose project
converts D3D8 API calls and shader bytecode to D3D9 equivalents.

Qualification sequence: pinned revision/license review → disposable DX8 fixture
baseline → wrapper-only comparison → verify wrapper loads our D3D9 proxy → combined
capture/replay/Reset tests → one owned DX8 title. Output API compatibility alone
does not prove geometry/material extraction. DLL search paths and wrapper chaining
must be tested; never overwrite existing game mods to force a chain.

## DirectDraw / early Direct3D through version 7

Candidate: [elishacloud/dxwrapper](https://github.com/elishacloud/dxwrapper), with
configuration documented in its [project wiki](https://github.com/elishacloud/dxwrapper/wiki/Configuration).
Evaluate its Dd7to9 route for the specific DirectDraw/early-D3D title, separately
from D3d8to9. Test palettes, surfaces, depth, transformed vertices, presentation and
device-loss behavior relevant to the selected game.

A wrapper may translate 2D surfaces into GPU operations without recovering a 3D
world. Distinguish DirectDraw/blitting games from actual 3D geometry submissions.
Translation does not create missing geometry, lighting semantics or off-camera
assets. Other wrappers targeting D3D11/12/Vulkan are not drop-in feeders for the
current D3D9 interception path.

All tracks retain the native → wrapper/proxy → disabled/control → bounded gameplay
acceptance workflow, provenance, conflict checks and recoverable cleanup. Unified
capture and the workbench UI should expose these profiles only at their actual
qualification level.
