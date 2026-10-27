# Proxy/renderer transport protocol

Status: **stages 1 and 2 of [Phase 6](PHASE6_TRANSPORT_DECISION.md#test-plan).** Stage 1 is the protocol contract. Stage 2
adds a renderer serve mode and a test host that plays the proxy's part, and proves transport parity on fixtures. The real
proxy does not use the protocol yet, so no game-facing behaviour changes.

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
| `SceneAttach` | proxy to renderer | inherited section handle, byte size, SHA-256 of the bytes, scene generation |
| `SceneAttachAck` | renderer to proxy | status (ok, bad digest, too large, decode failed), scene generation, scene width and height |
| `FrameSubmit` | proxy to renderer | fence value, resource slot, width, height, scene/camera/lighting/material/settings generations |
| `FrameComplete` | renderer to proxy | fence value, status, resource slot, the five generations echoed back, SHA-256 of the rendered BGRA pixels |
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
- `SceneAttach` is valid after an ok `HelloAck`, with no frame outstanding and no attach pending, and is answered by exactly
  one `SceneAttachAck`. A failed attach leaves any previously attached scene in place. `FrameSubmit` needs an attached scene
  and must carry its generation.
- `FrameComplete` must name an outstanding frame, echo its slot and generations exactly, and carry a fence value no
  lower than the submitted one.
- `Stop` ends the session; only `StopAck` follows, after every outstanding frame is completed or discarded.
- A rejected message changes nothing, so the sender can correct and retry with the same sequence number, and the
  receiver decides whether to close.
- Reserved fields and unused flag bits must be zero, which keeps them available for a later version.

## Stage 2: serve mode and the test host

`rrt_dxr --transport-serve IN OUT [render options]` is the renderer end. IN and OUT are inherited anonymous-pipe handle
values; render settings (mode, samples, seed, denoise and so on) stay on the command line, exactly as standalone, and only
frame identity travels in messages. It validates every message in both directions through the session monitor, creates
the D3D12 device on `Hello` and refuses a version or adapter LUID mismatch, verifies the SHA-256 of the section before
decoding the scene, and renders each `FrameSubmit` from a clean history through the same `Renderer`/`RenderTo`/digest
path as a standalone run, so the frame's output digest is the standalone `pixel_sha256_bgra`.

`rrt_transport_host` (x86 or x64) plays the proxy's part. It copies the scene file into an inheritable file-mapping
section, starts the renderer under a kill-on-close job with an allowlisted handle list, drives one session and prints a JSON
report. Options: `--frames N`, `--repeat N`, `--corrupt-digest`, `--min-version/--max-version`, `--wrong-luid`,
`--inject-garbage`, and `--` followed by the renderer's render settings.

`tests/verify_transport_parity.py` (`transport_parity`, needs a DXR GPU, skips with 77 otherwise) renders two scenes,
a fixture and a 300-triangle one, with three settings each (1 sample GI, 4 sample GI with denoise, albedo). Every frame
of a two-frame session must equal the standalone render byte for byte, the session must repeat exactly, the child must be
reaped with exit code 0 and an empty stderr, and a bad digest, a version mismatch, a wrong adapter and a malformed header
must each end cleanly without a render. Six consecutive sessions in one host process must leave the handle count flat after
the first session (the first adds a few handles, 118 to 121 measured on the development machine, then none).
`transport_parity_x86_host` runs the same test with the 32-bit host when configured with `-DRRT_X86_TRANSPORT_HOST=<path>`.

Measured on 2026-10-27 (RX 9070 XT, driver 32.0.32015.7029): all eight pairs of x86 or x64 host, Debug or Release, with an
x64 Debug or Release renderer, pass. A frame costs about 30 ms for these 128x96 fixtures, which is the renderer's own
time; no latency or pacing claim is made (stage 5).

## What this does not establish

The real proxy does not speak this protocol: no capture, no D3D9 `Present`/`Reset` handling and no raster fallback are
involved, so the "raster path still matches the no-proxy baseline" half of stage 2 is untouched and untested here. The
scene crosses in shared memory; shared D3D12 resources, fence ownership across processes for pixels, the fault-injection
cases beyond the four refusals above, `Reset`/resize lifecycle, ten-cycle attach/detach counts and pacing are stages 3
to 6 of the [test plan](PHASE6_TRANSPORT_DECISION.md#test-plan). The pure-Python contract and the `transport_layout` test
cover the schema and session rules; the handle-count result is for the host side only.
