# Cross-process shared D3D12 resources

The same-adapter shared-resource boundary now covers a mechanical round trip, real signed FidelityFX Radiance Cache inference/training, renderer-owned GPU path generation, guarded composition and an opt-in native presentation test. Defaults remain unchanged and the no-cache frame stays authoritative unless candidate application is explicitly requested.

## Contract

The parent creates two 1,573,120-byte committed default-heap buffers with `D3D12_HEAP_FLAG_SHARED` and one fence with `D3D12_FENCE_FLAG_SHARED`. Local upload and readback buffers are not shared. Three inheritable NT handles are created with `GENERIC_ALL`, then included explicitly in the suspended child's `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` before job assignment and resume.

The fixed sequence is:

1. Parent uploads deterministic bytes to shared input and signals fence value 1.
2. The child creates a device on the declared adapter, verifies exact adapter LUID, opens only the two buffers and fence, waits for value 1, copies input to output and signals value 2.
3. The child waits for its GPU work before exiting. The parent verifies child reaping, waits for value 2, copies shared output to local readback, signals/waits for value 3, and compares every byte.

Microsoft's D3D12 documentation confirms that committed resources and fences can receive NT handles through [`CreateSharedHandle`](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device-createsharedhandle) and be reopened using [`OpenSharedHandle`](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device-opensharedhandle). Default heaps use [`D3D12_HEAP_FLAG_SHARED`](https://learn.microsoft.com/en-us/windows/win32/direct3d12/shared-heaps); upload/readback heaps are not shareable. Same-adapter synchronization uses [`D3D12_FENCE_FLAG_SHARED`](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ne-d3d12-d3d12_fence_flags), not the cross-adapter flag.

## Evidence

On the RX 9070 XT:

- adapter LUID: `72687:0`;
- shared resources: 2;
- shared fences: 1;
- explicitly allowlisted extra handles: 3;
- payload bytes: 1,573,120;
- payload FNV-1a64: `10972558891643204389`;
- CPU payload-transfer bytes between processes: 0;
- fence values observed: 1, 2, 3;
- child exit/reaping: clean and exact.

Fresh runs are report-identical. Invalid adapter and direct invalid-handle child invocation fail closed. The complete RC suite now passes 7/7 in Release and Debug.

The second contract replaces the generic payload with the provider's exact five-buffer external interface:

| Buffer | Bytes | Stride | Child access |
|---|---:|---:|---|
| prediction input | 540,672 | 44 | read |
| prediction output | 147,456 | 12 | write |
| training input | 22,528 | 44 | read |
| training target | 6,144 | 12 | read |
| sample counters | 8 | 4 | clear |

The parent owns local upload/readback staging and shares only five default-heap UAV buffers plus one fence. It signals value 20 after initialization. A job-contained child opens the six explicitly allowlisted handles, verifies adapter LUID and every resource description, runs reset plus inference plus counter clearing through the signed provider, waits for completion and signals 21. The parent then performs local readback and signals 22.

Measured provider evidence is exact in Release and Debug:

- 716,808 shared external-buffer bytes and zero CPU interprocess payload bytes;
- all 36,864 prediction values finite, nonnegative and changed from their NaN sentinels;
- prediction hash `8439070038676242095`, identical to the established non-shared inference baseline;
- prediction/training inputs and training targets unchanged, both counters zero;
- clean child teardown, six inherited handles and fence sequence 20, 21, 22;
- repeated provider dispatches exact; invalid shared handles rejected.

## Persistent renderer-path sequence

`rrt_rc_probe --shared-path-sequence ABSOLUTE_RCRPATH1` and the no-file `--shared-stream-sequence` form both use the existing strict artifact decoder. The parent populates the five shared resources with the renderer's normalized query/training records, then a single job-contained provider child retains its context across reset/inference, one or two training batches, post-training inference and reset recovery. Only a bounded hash/count record returns on stdout; no path or prediction payload crosses the provider process boundary.

For the canonical 172-query renderer fixture, one batch produces baseline/post/reset hashes `4380958906282038366 / 17423046786485749504 / 4380958906282038366`. Two batches produce post hash `13270289865275143940`. All 516 populated RGB values change after training and reset is byte-exact. File and stdin reports match exactly. A 1 MiB provider budget and 1 ms deadline both fail closed, the child is reaped, and the next normal run recovers exactly.

## Renderer-owned GPU-direct path

The explicit `rrt_dxr --rc-shared-probe ABSOLUTE_PROBE --rc-sdk-bin ABSOLUTE_SIGNEDBIN` mode removes the remaining live transport copy. The renderer first executes its unchanged path tracing shader into a GPU-only raw-row resource. A deterministic one-thread compaction shader scans pixels in ascending order, normalizes position/normal/view guides, writes all five exact shared provider buffers, writes inference/training counters, and retains a 49,152-byte pixel map on the renderer GPU. It then signals fence 30 and launches the external probe through the same suspended/job-assigned handle allowlist.

The child discovers the counts directly from the shared counter buffer and retains one context through baseline, one/two training batches, post-training inference and reset. On the canonical scene it discovers 172 queries. GPU normalization establishes a separate deterministic baseline/reset hash `566204800999108543`; one batch produces `6891511169378437159` and two produce `12625136704411306072`. The difference from CPU-mode hashes is preserved as evidence of GPU versus CPU math, not hidden. Repeats and resets are exact, camera identity changes, and budget/timeout failures return a successful renderer fallback report with `candidate_applied=false` and `authoritative_output=no-cache`.

```powershell
cmake --build build/rr-sdk-probe --config Release --target rrt_rc_shared rrt_rc_probe
ctest --test-dir build/rr-sdk-probe -C Release -R "rc_shared_transport_contract" --output-on-failure
```

## Guarded output and scheduled native presentation

The transport and guarded diagnostic composite are complete for the explicit research mode. After proving reset recovery, the child restores its trained prediction into the shared output. A renderer compute pass combines that buffer with the retained pixel map and renderer-owned direct/throughput/no-cache terms. It reads back only a 196,608-byte candidate/error surface: raw path data remains GPU-only.

One training batch gives composite MSE `7.68497e-5` and candidate SHA-256 `f46fd7afb78ece4edcfb6d70582073f6d545849a30bd8242eb7584462a81b3b8`. Two batches improve MSE to `7.61978e-5` with SHA-256 `079c9ae7a4cd98a3e8cfb986e22d46a86cab868e58e8ea8da502584af58acd48`. Representative direct wall time is 0.33–0.35 seconds, versus about 1.0 second for the earlier two-frame CPU readback/pipe/upload prototype. Release and Debug reproduce the semantic evidence and all seven RC contracts pass.

Default direct runs remain deliberately unapplied: `candidate_applied=false` and `authoritative_output=no-cache`. Explicit `--rc-present-candidate` adds a second GPU pass after every provider and quality guard succeeds. It uses the renderer-owned mapping rather than the diagnostic error value, patches only admitted pixels into the common packed-BGRA output, and retains a GPU backup for rollback if post-apply validation fails. A GPU-written 49,152-byte audit mask proves exactly 172 pixels were applied; all 12,116 unmapped pixels remain byte-identical. The canonical no-cache output SHA-256 is `f6dabb47da97f149b859a9645c10af922c097057995da7cac9a661136f46c641`, while the admitted output is `719b289967ea103fb13d98ad5661c9c3e31f8b417d17de98deb3dbdf6a4c1659`.

`--rc-presentation-test` additionally creates a hidden native window before provider execution. The transaction runs on a worker future while the main thread pumps Win32 messages; only after it completes does the single GPU owner create the swapchain and submit the output through latency-one frame admission. The canonical run processed two messages over 22 wait/pump cycles during a 340.153 ms provider wait, then presented one frame and passed exact back-buffer readback. Release and Debug each pass all seven RC contracts plus the existing native presentation contract.

## Stable-frame context amortization

Explicit `--rc-persistent-epochs 2` performs two training/inference epochs inside one contained child process, one provider context and the existing five shared resources. Epoch two first infers without reset and must reproduce epoch one's trained output exactly, then trains again. The canonical epoch-one post and epoch-two start both hash to `6891511169378437159`; the second epoch changes all 516 populated RGB values and finishes at `12625136704411306072`. Final reset still returns byte-exactly to baseline `566204800999108543`.

The final candidate and `7.61978e-5` composite MSE exactly match the established two-batch result. The two-epoch transaction performs seven provider dispatches in one process/context and measured 426.558 ms, below the sum of two independent launches in the same run. Tests compare this relationship rather than pinning wall-clock time. One-epoch wire output and hashes remain unchanged, low-budget failure stays no-cache, and Release/Debug each pass all eight adjacent RC/presentation contracts.

## Parent-commanded provider epochs

`--rc-renderer-session-test` now connects this protocol to renderer-owned GPU path regeneration and `RcFrameAdmission`. One context consumes six epochs: base reset, latest queued camera reset, stable moved-camera continuation, return-to-base reset, stable base continuation, and explicit identity reset. Two camera requests queued during the first epoch coalesce into one; the stale first result is rejected and the pending request is actually consumed. Query counts refresh as 172/178/178/172/172/172. The same frame-constant upload is updated only after ownership returns, so no renderer GPU buffers are allocated between epochs.

Each epoch's shared predictions are read back diagnostically and matched to the worker's hash. Base reset/training matches the established direct path; moved continuation reaches hash `8100200300773600753`. Four resets, two continuations, five admitted results and one discarded result execute in one process/context with 18 dispatches. Stop is acknowledged after teardown. Repeats, timeout/low-budget fallback and recovery are tested with D3D12 validation; `renderer-session.json` retains evidence.

This is a bounded scheduler test with synthetic camera requests, not an interactive game loop. It leaves no-cache pixels authoritative and reads 884,736 prediction bytes for verification. Per-epoch candidate application/native presentation, UI-driven requests, and D3D9 Present/Reset integration remain open.

The shared-path worker additionally accepts a versioned command loop on the existing fence. For epoch `e`, values `40 + 4e`, `41 + 4e` and `42 + 4e` mean reset, continue and stop; `43 + 4e` acknowledges completion. Inputs belong to the parent before command submission and after acknowledgement. The child rejects out-of-sequence values, requires reset before training, and allows at most 64 training epochs before stopping/restarting. Each wait is bounded. Stop acknowledgement follows successful context destruction and allocation-accounting checks.

The probe exposes `--shared-path-sequence ABSOLUTE_FILE --session-commands RCRCC` (also available with shared-stream input). The command string accepts 1–16 R/C entries beginning with R; the parent sends stop automatically. The test fixture holds inputs constant, so continuation starts exactly from the previous trained output and reset exactly reproduces the initial baseline. Five RCRCC epochs perform 15 dispatches in one process/context; parent readback verifies the final shared output hash `1061084142929051959`. Repeats, single-epoch stop, 16-epoch sequences, invalid commands, timeout, low-budget failure and recovery are covered in `commanded-session.json` and the path contract.

This replaces fixed choreography inside the worker with parent-selected commands, but the probe still uses an exported static fixture. Renderer-owned queued camera requests are covered above; live D3D9 frames remain unconnected. Renderer clients using count discovery must regenerate counters/inputs before each command; a continue command asserts that the supplied inputs are compatible with retained cache state.

## Live changed-frame fence session and buffer reuse

`RcBufferPool` also supports all direct-path buffers, including the five shared resources. Full mode is bounded to 32 entries/8 MiB and matches byte size, heap, initial state, flags and shared status. Successful completion records each changed buffer's final state, submits transitions back to its initial state, and waits for that GPU work before ending the lease. Failed transactions invalidate the entire pool instead of recycling uncertain states. Handles and provider contexts are still recreated per transaction in this direct-renderer path.

`--rc-gpu-pool-test` runs the six lifecycle cases plus two diagnostic-only repeats, with the D3D12 debug layer enabled by the Python contract. Stable repeated work allocates no new buffers, failure invalidates the pool, recovery rebuilds it, and applied candidates exactly match the unpooled results. Diagnostic repeats preserve exact no-cache output and the expected candidate hash. Seven successful transactions restore 61 buffer states in seven fenced submissions; `gpu-pool.json` retains the evidence. Continuous provider epochs and consumption of queued UI input remain outstanding; no frame-rate improvement is claimed from this test.

`RcBufferPool` in staging-only mode supports reuse of upload/readback buffers across direct transactions. The pool matches exact byte size and heap type, holds at most 16 entries/1 MiB, and allows one transaction lease at a time. Upload buffers remain GENERIC_READ and readback buffers remain COPY_DEST; buffers already borrowed by an active transaction cannot be borrowed again. Successful completion retains them, failure invalidates them, and pool destruction returns all retained budget charges.

`--rc-pool-test` repeats the six resource-lifetime transactions using this pool. The stable repeat performs no new staging allocations; failure empties the pool and recovery rebuilds it. All transaction reports match the unpooled path apart from timing/PID. The canonical run with reused frame constants records 10 staging allocations, 17 reuses and 246,528 retained bytes, then returns to 2,967,408 baseline live requested bytes at teardown. `staging-pool.json` retains the evidence. Full shared/default-heap pooling is covered below. This optional reusable path does not yet consume pending UI requests or generalize provider epochs.

RC direct buffers now have explicit transaction ownership through `RcTransientBuffers`. The arena retains COM references until transaction teardown, releases them, then returns their exact charges to the renderer's allocation budget. This fixes cumulative accounting growth across repeated transactions. It does not pool buffers or eliminate their allocation cost. Scene resources and swapchain accounting retain their existing ownership.

`--rc-resource-test` exercises six transactions on one renderer: initial work, repeat, a 1 MiB provider-budget failure, recovery, changed camera, and a three-epoch live session. Every transaction must return to the same live-byte baseline; repeated stable work must retain the same allocation high-water mark. The failure preserves exact no-cache pixels, recovery matches the original candidate, and changed-camera/live results match. The path contract retains the nested reports in `resource-lifetime.json`. These are renderer-requested byte charges, not a measurement of driver VRAM residency. Generalized provider epochs remain outstanding; optional staging/full buffer reuse is covered above.

Native presentation now uses a UI-owned admission mailbox with one active epoch and one pending latest request. New camera notifications replace pending work, and completion can publish only while its identity is current and the window remains open. Close is checked both during provider work and before swapchain admission. The worker retains exclusive renderer ownership until its future completes; closing the window suppresses publication while the bounded transaction finishes.

`RcFrameAdmission` treats scene, camera, lighting, material and settings revisions as explicit cache identity. Initial work, changed identity and recovery after failure require reset; successful unchanged identity permits continuation. Callers must issue revisions when relevant inputs change. Current native camera notifications are synthetic test messages, not wired keyboard controls. `--rc-scheduler-test camera|close|close-admission` exercises coalescing and suppressed publication using the actual GPU transaction. The bounded harness retains/reports a pending request but exits without executing it. Connecting reusable buffers to a generalized provider epoch protocol is still required for continuous interactive scheduling; these tests do not claim live game integration.

The live wrapper exposes `PollFence` for scheduler integration. Each poll drains bounded stdout/stderr, enforces overflow, rejects the device-removal fence sentinel and checks child exit; it rechecks the fence after observing exit to handle completion races. Normal pending polls do not wait. Failure cleanup may wait up to five seconds for termination, so a UI caller must retain asynchronous teardown. `WaitFence` uses this poll with waits of at most 10 ms and one elapsed-time deadline, preventing a verbose worker from blocking on a full pipe until timeout. Dedicated live fixtures cover premature normal exit, crash, timeout and output overflow. Interactive-loop wiring remains pending.

Explicit `--rc-live-session-test` adds an RAII live-process wrapper with the same suspended creation, inherited-handle allowlist, pre-resume job assignment, kill-on-close policy and 64 KiB output cap as the one-shot boundary. Fence waits have bounded deadlines and also watch the process handle, so timeout or premature child exit terminates/reaps the job before the renderer returns an authoritative no-cache fallback.

One child process/context handles three parent-controlled epochs. The initial GPU inputs are submitted at fence 30 and complete at 31. Fence 32 continues the unchanged identity without reset and completes at 33. The parent then renders a +0.05 camera-offset frame, regenerates raw paths, all five provider buffers and the pixel map on GPU, and signals 34; the child rediscovers occupancy, resets provider state for the changed identity, trains/infers, restores the trained output and signals 35. Parent and child never write the shared resources concurrently.

The initial frame has 172 queries. Stable continuation begins at exact hash `6891511169378437159`, trains to `12625136704411306072`, and changes all 516 populated RGB values. The changed camera has 178 queries; reset baseline/trained/reset hashes are `9990495896441858603 / 587237281996004111 / 9990495896441858603`, with all 534 populated values changed by training. Candidate SHA-256 `31f8700b024782226c43284f4849cb0a5539a47a4eb45cd7e0aa5985adde7761` and MSE `7.68404e-5` exactly match a fresh process launched at that camera. A contract-detected stale-count bug was fixed by repeating count discovery after fence 34.

This is a bounded three-epoch live-session proof, not an unbounded production scheduler. The next boundary is moving the fence/session state into the interactive frame loop, adding lighting/material identity policy and back-pressure, then connecting captured D3D9 Present/Reset events to that scheduler. Nothing here changes installed games, drivers or SDK binaries.
