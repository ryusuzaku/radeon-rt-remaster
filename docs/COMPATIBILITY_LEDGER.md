# Compatibility ledger

Only the in-repo harness has passed proxy comparisons. External native baselines have begun; no external game is certified. Historical Ex harness passes below are not fresh qualification: the latest session returned S_PRESENT_OCCLUDED even through Microsoft's native Ex runtime.

| Target | API/mode | Forwarding and lifetime | Observation result | Status |
|---|---|---|---|---|
| Textured fixture, x86 Debug/Release | D3D9 | Exact system/proxy pixels; identity, reset failure/recovery, resize, resource-held device lifetime | 12 presents; 24 fixed-function and 12 shader draws; expected resources/state updates | Harness baseline |
| Textured fixture, x86 Debug/Release | D3D9Ex | Same pixel comparison plus Ex factories, resource arrays, ResetEx, PresentEx and swap-chain Present | Same expected counts; deterministic IDs/metadata; bounded and selected traces pass | Harness baseline |
| Four-quadrant scene fixture, x86 Debug/Release | D3D9 and D3D9Ex | Exact system/proxy and independent replay pixels in frames 0/1/6/7, including resize/reset | Four fixed-function draw entry points; partial writes; stable content IDs; scene validation and glTF export | Phase 3 subset baseline |
| Offline fixture mods, x86 Debug/Release | Captured D3D9/9Ex scenes | Texture/mesh/material isolation; untouched draw data and image regions remain identical | Six GPU cases per mode; deterministic combined output; static mesh ID survives Reset | Phase 4 offline baseline |
| Ground/occluder and perspective fixtures, x86/x64 Debug/Release | D3D12 / hardware DXR 1.1 | Repeatable GPU readback; standard debug-layer validation; albedo oracle and localized shadow checks | Modded scene import; camera/texture/scissor tolerances; GPU timestamps | Phase 5 static-renderer baseline |
| BioShock 2 original | Default / requested -dx9 | No proxy deployed | Default native baseline exit 0 and user visual acceptance; -dx9 native baseline access violation 0xC0000005 after 73.516 s | DX9 baseline blocked |
| Half-Life 2, hl2_complete | D3D9Ex observed | Native/bin-proxy/disabled controls exit 0; user accepts visuals; owned DLLs removed, executable unchanged | Triggered gameplay: 82 presents, 28,633 shader draws, 0 fixed draws/failures; 64 MiB byte limit reached before requested 120 frames | Gameplay observation demonstrated; final triggered-run exit/cleanup pending |
| Half-Life 2, material capture | D3D9Ex observed, v19 ledger | Bundle under `build/game-passes/`, not version controlled; proxy removed and executable unchanged after the pass | **16 material draws captured** at target `[1920,1080,21,0]`, 32 texture inputs, 19 external assets / 5,327,872 bytes; 668 attempts over 4 presents | Material capture demonstrated on a real title; 20 texture inputs blocked by the shared shadow budget; game-sized material comparison not yet run |
| Commercial reference title | To select | Untested | Unassessed | Pending |

HL2 follow-up: default gameplay run subsequently exited 0 and removed its proxy.
Requested `-dxlevel 70` persisted as level 80 in this build. Its native baseline
passed; triggered gameplay produced 60 presents and 11,424 shader-only draws,
with zero failed calls. Lower-feature run shutdown/cleanup and backed-up
graphics-settings restoration remain pending.

HL2 material follow-up: the fixed-function subset was never the path that worked.
Shader-aware extraction on primitive count did. See
[HL2 dynamic material capture](HL2_DYNAMIC_MATERIAL_CAPTURE.md) for the result and
for the two structural gaps — render-target extent assumed in advance, and a
trigger firing outside a presenting interval — that kept every earlier pass at
zero captured material draws.

Verified GPU: AMD Radeon RX 9070 XT, driver 32.0.31041.1004. These results do not establish performance or compatibility on other GPUs.

## Admission data

Record exact executable version, graphics mode, proxy revision, GPU/driver, deterministic scene, and proxy/system comparison. Game qualification must cover startup, input, settings, alt-tab, fullscreen, shutdown, and repeated launch. API load success alone does not establish extractability.

Inspect shader/fixed-function draw counts, dynamic resource updates, render-target changes, and stable scene content before selecting a real Phase 3 replay target. Mesh/texture snapshots and exact replay have been verified only for the in-repo subset; game payload completeness remains unassessed.
