# RRT observation trace v1

Optional `RRT_TRACE_TRIGGER_FILE` arms observation until the named regular,
non-reparse file exists at a successful Present boundary. START_FRAME remains
a minimum; the header records the actual admitted frame and normal limits apply.
The proxy checks metadata only, never reads, creates or removes the marker. Use
a fresh local workspace path, not a network path. Directory triggers are ignored.

## Purpose

Determine which API paths a game uses and whether its draws can support later scene extraction. This format is an observation log. It does not yet contain a replay-complete command stream, vertex/index bytes, texture pixels, or shader bytecode.

UTF-8 JSON Lines: one header, zero or more ordered events, then a footer. A complete record ends in a newline. Inspector readers reject unknown versions, duplicate JSON keys, malformed records, missing sequence entries, invalid frame boundaries, and data after the footer.

## Header

```json
{"type":"header","schema":"rrt-observation","version":1,"start_frame":0,"frame_count":300,"pointer_bits":32}
```

`pointer_bits` describes the producer architecture. Scalar values use JSON numbers. Fixed-size state structures use lowercase hexadecimal bytes in Windows little-endian ABI layout; consumers need the corresponding D3D9 structure layout. Capture provenance should also include the game/version and GPU/driver in the compatibility ledger.

## Events

```json
{"type":"event","seq":0,"frame":0,"thread_id":1234,"object":1,"method":"ObjectCreated","hr":0,"args":{"interface":"IDirect3D9"}}
```

- `seq`: contiguous record number within this capture, starting at zero.
- `frame`: process-wide ordinal incremented by a successful (`S_OK`) intercepted Present or PresentEx. Device and swap-chain presents share this ordinal; it is not a per-device simulation-frame index.
- `thread_id`: Windows thread that completed the observed call. Sequence records serialization of post-call observations; concurrent native calls are not a deterministic replay order.
- `object`: session-local wrapper identity, not a pointer or stable asset hash. All known interfaces on a live wrapped COM object share identity. After the last public wrapper reference is released, a resource-held native object can later get a new wrapper/ID.
- `method`: SDK method name, or ObjectCreated/ObjectDestroyed/UnsupportedQueryInterface/TraceEncodingFailed.
- `hr`: signed 32-bit HRESULT. Non-HRESULT methods use S_OK here; their arbitrary return values are not generally recorded.
- `args`: scalar parameters, wrapped object IDs, resource creation descriptors, and selected state bytes. Output-interface IDs and state bytes are recorded only on successful calls. Null/unobserved object references are zero.

Draw records include `vertex_shader_bound` and `pixel_shader_bound`, sampled directly from the native device at that draw. This remains useful after state-block application. The inspector classifies both-null as fixed-function and either-bound as shader use; it is not a complete compatibility verdict.

Resource content changes are currently indicated by Lock/Unlock and update calls. Fixed-size transforms, materials, lighting, and selected state structures are recorded; shader constants are capped at 4096 bytes per argument. Multi-element structures other than explicitly counted shader constants are only recorded as a first element. Omitted/limited payloads must not be treated as complete scene snapshots.

## Footer

```json
{"type":"footer","reason":"finished","events":2,"present_count":1}
```

Reasons: `finished` (explicit RRTFinishTrace), `frame_limit` (selected range completed), or `byte_limit` (bounded observation prefix). `events` is the stored event count. `present_count` is the process-wide successful-present ordinal when recording closed.

Records flush at successful presents. An interrupted game can leave a valid prefix without a footer; use `--allow-incomplete` to inspect complete records in that prefix. A partial/truncated final record remains an error. A cap-induced footer does not claim that the entire requested scene was captured.

## Controls

| Environment variable | Default | Meaning |
|---|---|---|
| RRT_PROXY_DISABLE | unset | `1` returns native factory interfaces and disables observation. |
| RRT_TRACE_FILE | unset | Explicit output path; tracing is disabled without it. Parent directory must exist. Existing files are never overwritten. |
| RRT_TRACE_START_FRAME | 0 | First process-wide present ordinal to record. |
| RRT_TRACE_FRAME_COUNT | 300 | Maximum selected frame count. |
| RRT_TRACE_MAX_BYTES | 67108864 | Total file budget including reserved footer space; minimum 4096. |

Settings are read once on first tracing use. A frame-selected trace omits earlier creation/state events, so the inspector labels unseen IDs `external_to_capture`. It is an observation slice, not a restorable state snapshot.

Opening or writing a trace can fail without changing rendering HRESULTs. Diagnostics must never be required to run a game. The runtime streams records; it does not accumulate an unbounded frame buffer. The inspector independently caps line size (64 KiB), file size (512 MiB), and event count (1 million).

## Inspect

```powershell
python tools/inspect_trace.py build/my-capture.rrt.jsonl
python tools/inspect_trace.py build/my-capture.rrt.jsonl --frame 3 --json
```

The inspector returns exit code 2 for rejected input. JSON output contains method counts, per-frame draw/present counts, resource inventories, wrapper liveness, failures, and the requested frame timeline.
