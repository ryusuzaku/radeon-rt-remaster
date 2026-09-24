# HL2 shader inventory — 2026-09-07

User confirmed gameplay before triggering the armed diagnostic. No graphics
settings or rendering effects were changed during this pass.

Evidence: `build/game-passes/hl2-inventory-20260907/runs/inventory/`.

- Inventory: 2,996 indexed draws, 0 failed draws, 0 unavailable queries.
- 42 unique vertex programs, 37 unique pixel programs, 55 combined families.
- Raw version tokens: every VS `fffe0200`; every PS `ffff0201`.
- Normal byte-limit completion: 16,772,448 bytes, below the 16 MiB cap.
- Inventory SHA256: `f293fcc57a07ee029e482fbaff900e92e5b3ebd6b63c77687f7befc306f6d3a6`.
- Independent trace: 60 presents, 149,007 events, 10,466 shader draws,
  0 fixed-function draws, 0 failed calls, normal frame-limit completion.

The trace and inventory have independent activation boundaries and limits;
their counts must not be treated as matching populations. This is one bounded
gameplay sample, not whole-game compatibility or visual-effect validation.

## First analysis target

Provisional target: family
`34a26bb21a5f97a014180fb48bad9200318f5109d55f7dee252b087f572391a5`,
231 draws (7.71% of the inventory), vertex program
`0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2`
(612 bytes).

It has an ordinary float position/normal declaration, colour and two texture
coordinate inputs in stream 0 (48-byte stride), plus declared stream 2 inputs
with zero stride. No declared blend-weight/index inputs appear in this family.
These observations make it a useful initial analysis candidate, **not proof of
static world geometry**. Stream 2 must not be silently ignored.

The most frequent family (`10bd8ea2...`) accounts for 566 draws but has packed
normal/tangent inputs and three streams, making it a more complex first contract.

Next: bounded offline shader inspection to establish position dependencies and
constant/stream usage for the provisional target. Then design and test explicit
input capture and transformation semantics. We have not identified camera/world
matrices, recovered vertex buffers, admitted these programs to replay, or added
DXR lighting to HL2.

Cleanup confirmed on the following turn: exit 0 after 185.797 seconds, executable
unchanged, owned proxy removed by runner and `bin/d3d9.dll` verified absent.

Offline inspection has now established the candidate's exact position path;
see [position contract](HL2_POSITION_CONTRACT.md). It still requires actual
buffer/constant capture and native numerical verification before admission.
