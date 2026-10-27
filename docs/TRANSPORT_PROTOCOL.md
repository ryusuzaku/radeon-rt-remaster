# Proxy/renderer transport protocol

Status: **stage 1 of [Phase 6](PHASE6_TRANSPORT_DECISION.md#test-plan), the protocol contract.** The message layout, the
session rules and their tests exist; nothing sends these messages yet. No proxy or renderer code uses them, so no
runtime behaviour changes.

This is the wire protocol for option B of the [transport decision](PHASE6_TRANSPORT_DECISION.md): a thin 32-bit
D3D9 proxy talking to a 64-bit renderer process. A message carries identities and fence values, never pixels or scene
data. Bulk data lives in shared default-heap D3D12 resources, and ownership moves by fence value, exactly as in the
[radiance-cache session](RADIANCE_CACHE_SHARED.md).

## One definition, three implementations

| What | Where |
|---|---|
| Machine-readable definition | [docs/schemas/transport-v1.json](schemas/transport-v1.json) |
| C++ (x86 proxy and x64 renderer include the same file) | `src/transport/transport.h` |
| Python reference codec and session monitor | `tools/transport_io.py` |
| Golden scenarios with hand-written expected outcomes | `tests/transport_vectors.py` |

Adding or changing a message means updating all of them. `tests/verify_transport_contract.py` (pure Python, runs on
the Linux runner) fails if the schema, the header's `sizeof`/`offsetof` assertions and constants, the C++ error enum or
the Python codec disagree. The `transport_layout` ctest runs the compiled `rrt_transport_check` in each architecture,
compares its layout with the schema, and feeds the same scenarios to the C++ session monitor and requires the outcome
the scenario states for every message.

## Wire format

Little-endian, fixed-width fields only, no pointers or `size_t`, every field naturally aligned, so the layout is
identical in x86 and x64 (the build fails in either architecture if it is not). A message is a 32-byte header followed
by a payload whose size is fixed per type; the whole message is at most 4096 bytes.

| Header field | Type | Meaning |
|---|---|---|
| `magic` | u32 | `RRTP` |
| `version` | u16 | protocol version in use; the Hello header always carries a version the receiver can parse |
| `type` | u16 | message type |
| `payload_bytes` | u32 | must equal the type's fixed payload size |
| `flags` | u32 | bit 0 `SUPERSEDE_PENDING`, valid only on `FrameSubmit` |
| `sequence` | u64 | per-direction message number, 1, 2, 3, ... |
| `frame_id` | u64 | frame identity; zero for session messages |

| Type | Direction | Payload |
|---|---|---|
| `Hello` | proxy to renderer | version range, adapter LUID, process id, capabilities, capture ladder level |
| `HelloAck` | renderer to proxy | selected version, status, adapter LUID, max frames in flight |
| `FrameSubmit` | proxy to renderer | fence value, resource slot, width, height, scene/camera/lighting/material/settings generations |
| `FrameComplete` | renderer to proxy | fence value, status, resource slot, the five generations echoed back |
| `Stop` | proxy to renderer | none |
| `StopAck` | renderer to proxy | completed and discarded frame counts |

The five generations are the same identity the radiance-cache admission uses (`RcFrameAdmission::Identity`); echoing them
lets the proxy reject a completion for a frame whose inputs have since changed.

## Session rules

The full list is `session_rules` in the schema. In short:

- Negotiation picks the highest version in both ranges. No overlap, or an adapter LUID that differs from the
  renderer's, is answered with a non-ok `HelloAck` and the session closes.
- At most two frames are outstanding (one active, one pending). A third `FrameSubmit` is refused unless it sets
  `SUPERSEDE_PENDING`, which discards the pending frame: latest wins.
- `FrameComplete` must name an outstanding frame, echo its slot and generations exactly, and carry a fence value no
  lower than the submitted one.
- `Stop` ends the session; only `StopAck` follows, after every outstanding frame is completed or discarded.
- A rejected message changes nothing, so the sender can correct and retry with the same sequence number, and the
  receiver decides whether to close.
- Reserved fields and unused flag bits must be zero, which keeps them available for a later version.

## What this does not establish

No message has crossed a process boundary. Handle inheritance, adapter LUID verification against a real device,
fence ownership, the fault-injection cases, lifecycle and pacing are stages 2 to 6 of the
[test plan](PHASE6_TRANSPORT_DECISION.md#test-plan) and are not covered here.
