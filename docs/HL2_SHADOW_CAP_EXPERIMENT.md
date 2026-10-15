# HL2 CPU shadow-cap experiment — 2026-10-14

## Autonomous windowed result

The user authorized autonomous launch, loading and capture without waiting for
their presence. The current guarded run `material256-v2` was used rather than
deploying another proxy. The UI showed Windowed 1920x1080. Loaded the latest
"A Red Letter Day" autosave and visually verified corridor/NPC gameplay before
triggering.

The v19 ledger stopped at 4096 attempts with zero captures. Of 237 recorded
rejections, 160 are `pixel_material/pixel_material_shader`, 63 sampled unsupported
vertex shaders and 14 primitive-minimum rejections. No `buffer_range` failure
appears in this sample, and no draw reaches sampler diagnostics. The route and
resolution differ from the earlier 128 MiB run, so this does not isolate the cap
as the cause of the changed rejection population.

The 256 MiB peak filled to within four bytes: 54171136 bytes buffers and
214264316 bytes textures (79.8% textures). At stop, 243204476 bytes remain with
1106 tracked textures. The trace completes 60 presents, 6120 shader draws and
zero failed calls. A further cap increase is not supported by these results;
the default remains 128 MiB.

The validated, byte-limited inventory contains one family using the pinned VS,
paired with pixel shader SHA256
`dbca89ccb0e1d72bae02fb44cef4b80a6088cec6d163f0d4fe3dbf8661b199b0`
(1912 bytes, `ps_2_x`, 189 inventory draws). Static disassembly shows samplers
s0/s1 and five texture reads, but external constants c10/c11/c12/c29/c30 rather
than the supported program's c11/c12/c29/c30. The new c10 is eye position;
the program computes distance from interpolated position for fog instead of
using t4.w. This is a candidate next shader contract, not a replay-ready program
or a draw-by-draw correlation with all 160 ledger failures. Supporting it requires
observed c10 provenance, a versioned five-row constant payload and independent
native/CPU fog controls; adding its hash to the current allowlist is insufficient.

Validated summaries, shader assembly, dependency audit and comparison remain
in the local run directory; no game shader bytecode is published. Ledger SHA256:
`5092f036e4ff9174d804922627759924e21b6ed8e7bc0b56524b62163b958d6a`.

Normal exit is pending: automated Escape/Alt-F4/native Close interactions did
not exit the game, and captured mouse input redirected title-bar clicks into
camera movement. The game and owning runner remain active. No forced termination,
deployed-proxy rebuild/removal or GPU replay was performed. Cleanup and executable
preservation for this run must be verified after normal exit.

The peak-instrumented HL2 run reached the shared 128 MiB CPU shadow ceiling.
An explicit `--shadow-mib 256` comparison is now available through the guarded
game-pass runner. The default remains 128 MiB. This is bounded diagnostic capture
storage in the 32-bit process; it is not a GPU VRAM allocation or live rendering.

## Observed run

The local `hl2-peak-v19-20260925` bundle, run `peak-20261014`, used the complete
v19 evidence chain with `any:3`, triggered only after gameplay readiness.

| Measurement | Result |
| --- | --- |
| Stop | attempt limit, 4096 attempts, 0 captured draws |
| Recorded rejections | 328; rejection sampling means this is not all attempts |
| Position-material buffer-range failures | 208 |
| Topology evidence failures | 41 |
| Sampled unsupported shaders / primitive minimum | 63 / 16 |
| Peak retained | 134217724 bytes, four bytes below 128 MiB |
| Peak buffers / textures | 27146264 / 107071460 bytes; textures 79.8% |
| Stop buffers / textures | 30346080 / 103871571 bytes |
| Tracked live textures at stop | 477 |
| Trace | 60 presents, 5966 shader draws, zero failed calls |
| Exit and cleanup | exit 0; owned DLL removed; executable SHA256 unchanged |

No rejected draw reached texture-input diagnostics. Earlier game passes failed
at sampler admission; this run failed earlier, primarily at buffer availability.
The shared ceiling admits resources in creation/lock order, so texture reservations
can prevent later buffer shadows from being initialized. A controlled fixture
exercises that mechanism independently. The ledger alone does not establish the
byte demand refused at each buffer lock or prove that every `buffer_range` failure
will disappear with additional capacity.

## Policy and provenance

Choose an opt-in 256 MiB experiment before promoting any new default or adding
eviction. Doubling the allowance provides room for the observed texture and buffer
populations to coexist, with a strict bound. It does not guarantee adequate
capacity for every scene, and it adds up to 128 MiB of CPU shadow reservations
inside an x86 address space. Driver allocations, metadata and transient capture
buffers remain additional. The measured peak does not identify a minimum
sufficient cap.

`RRT_POSITION_SHADOW_MIB` accepts exactly `128` or `256` in position-capture
mode. Invalid values disable the capture observer. The guarded runner validates
`--shadow-mib`, clears inherited `RRT_` variables, passes the selected value and
records `shadow_mib` in the run report. Both buffer and texture charges consult
the same limit. The shader-snapshot path retains its 16 MiB limit.

New ledger footers record `shadow_cap_bytes`; the reader checks allowed values
and rejects a retained total/peak above it. Historical footers without that field
remain readable. The analysis tool uses a recorded cap when present, falling back
to the historical source default for older ledgers. No capture-version change is
needed: this optional footer metadata changes no draw or texture proof.

Per-resource payload limits, shader allowlists, initialization/dirty/epoch checks,
capture count, ledger and asset limits stay in force. At the larger cap, newly
admitted resources still need the same observed write evidence.

## Qualification and next game comparison

The selection fixture compares the same 370 DEFAULT textures at 128 and 256 MiB,
then exercises 750 textures to exceed 256 MiB and verifies recovery after release.
A separate fixture holds 90 MANAGED DXT5 textures and locks a new 4 MiB vertex
buffer: it checks missing capture at 128 MiB, valid capture at 256 MiB and identical
native output. Invalid environment values and footer caps fail closed. The runner
lifecycle test checks that the selected cap reaches the child process.

Both Release and Debug proxy/fixture builds pass. The Release selection matrix
passes (22.91 seconds), and the focused analysis/version/runner checks pass.
The serial Debug regression run passes all ten suites (383.45 seconds): all seven
texture matrices, classic/Ex proxy equivalence and the runner lifecycle. Debug
shader snapshot/proxy and analysis/version checks also pass. A compressed-suite
timeout occurred during overlapping GPU runs; its serial rerun passes.
Code generation, evidence registration, whitespace and prospective published
references pass. The latter uses a temporary Git index including this new document.

After native qualification, prepare a new hash-pinned bundle, reuse the matching
unmodified-game baseline and run the same v19 chain with `--shadow-mib 256`.
Wait for gameplay readiness before triggering. Compare rejection stages,
capture count and retained peak; this is another sample, not an identical-frame
benchmark. Verify normal exit, owned-proxy cleanup and executable preservation.
No commercial-game compatibility or new default is accepted by fixture results.
