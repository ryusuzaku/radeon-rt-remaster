# FidelityFX Radiance Cache foundation

## Result

The pinned FidelityFX SDK 2.3.0 Radiance Cache 0.9.0 provider can create and destroy a bounded D3D12 context on the Radeon RX 9070 XT. The isolated WMMA path uses a measured peak of 20,643,840 callback-managed bytes, releases all 11 allocations, and recovers cleanly after deliberately crashed workers.

This document records the context-only foundation. The subsequent [synthetic dispatch phase](RADIANCE_CACHE_DISPATCH.md) now executes the first isolated inference/training work, while still making no game-rendering or quality claim.

AMD describes Radiance Cache 0.9 as a technical preview requiring Windows DirectX 12, Shader Model 6.6 and RX 9000-series-or-newer hardware in the [technique guide](https://gpuopen.com/manuals/fsr_sdk/techniques/radiance-cache/) and [sample requirements](https://gpuopen.com/manuals/fsr_sdk/samples/radiance-cache/). ROCm remains useful for separate authoring or compute experiments, but it is not the runtime API for this provider.

## Pinned provider

The optional dependency is a sparse Git/LFS checkout of official SDK tag `v2.3.0`, commit `60f4ea81909200d8542eca14dccb2628b763a9a3`. It is deliberately separate from the earlier reduced Ray Regeneration dependency.

| Component | SHA-256 | Verification |
| --- | --- | --- |
| `amd_fidelityfx_loader_dx12.dll` | `e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa` | Valid AMD Authenticode signature |
| `amd_fidelityfx_radiancecache_dx12.dll` | `256db18d924c8cd38923d04e3ecd210695d3f0f796b240eab9663ad4d54e31a0` | Valid AMD Authenticode signature |

The managed worker admits exactly these hashes. Provider enumeration is made with the Radiance Cache create-descriptor type and returns the provider dynamically; the numeric ID is evidence, not a source constant.

## Live support and lifecycle

The support query reports:

- adapter: AMD Radeon RX 9070 XT;
- Shader Model 6.6 available;
- wave lane range 32–64, so the documented wave32 reference fallback is eligible;
- sole enumerated provider name `0.9.0`, observed provider ID `12308798262227275776`;
- fixed capacities: 12,288 inference samples and 512 training samples (4.17% of inference capacity).

The context first attempts the provider's WMMA flag. It succeeds, so no fallback occurs. A cold run took about 38 seconds; warmed runs complete in under one second. The supervised deadline remains at most 60 seconds.

The provider does not expose an effect-specific pre-context memory query. Admission therefore uses a 32 MiB hard allocation-callback ceiling and exact lifecycle accounting:

| Measurement | Result |
| --- | ---: |
| Peak live callback bytes | 20,643,840 |
| Allocation attempts / accepted | 11 / 11 |
| Releases | 11 |
| Live bytes after destroy | 0 |
| Denials / callback errors | 0 / 0 |
| Cache dispatches | 0 |

After successful creation, the official context-provider query returns `FFX_API_RETURN_NO_PROVIDER` (code 4) and ID 0 even though creation explicitly selected the sole enumerated provider. Native validation preserves that failure. The managed boundary accepts only this exact result with the two pinned DLL hashes and requested/enumerated identity, reports `context-ready-with-workarounds`, and keeps `raw_sdk_acceptance` failed.

Allocation failure is not propagated safely by this preview provider. A 1 MiB ceiling and an injected failure on allocation 2 both make the child access-violate with Windows status `0xc0000005`. The one-process job contains, kills/reaps and reports each worker failure; a fresh normal process then reproduces the successful allocation lifecycle. The ceiling is not relaxed to hide this defect.

## Reproduce

Configure the optional x64 target against the pinned component, then build either configuration:

```powershell
cmake -S . -B build/rr-sdk-probe -DRRT_FSR_RC_SDK=build/dependencies/fsr-2.3.0-radiance-cache
cmake --build build/rr-sdk-probe --config Release --target rrt_rc_probe
cmake --build build/rr-sdk-probe --config Debug --target rrt_rc_probe
```

Run the managed context boundary with its 32 MiB default:

```powershell
py tools/rc_worker.py --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin
```

Run the registered contracts:

```powershell
ctest --test-dir build/rr-sdk-probe -C Release -R "rc_probe_contract|rc_worker_boundary" --output-on-failure
ctest --test-dir build/rr-sdk-probe -C Debug -R "rc_probe_contract|rc_worker_boundary" --output-on-failure
```

`rrt_rc_probe --help` exposes direct support/context modes for diagnosis. The managed worker is the admitted boundary because it verifies the binary hashes and strict JSON envelope.

## Next renderer-owned slice

The pinned sample defines an input record as 11 contiguous floats (44-byte stride): normalized position, octahedral normal, octahedral view direction, diffuse albedo and roughness. Output is RGB radiance at a 12-byte stride. Counter index 0 contains inference samples and index 1 training samples.

At the fixed capacities, the five API-visible external buffers are:

| Buffer | Count × stride | Bytes |
| --- | ---: | ---: |
| Prediction inputs | 12,288 × 44 | 540,672 |
| Prediction outputs | 12,288 × 12 | 147,456 |
| Training inputs | 512 × 44 | 22,528 |
| Training targets | 512 × 12 | 6,144 |
| Sample counters | 2 × 4 | 8 |
| Total |  | 716,808 |

The sample additionally owns a 147,456-byte per-pixel path-compositing state buffer; it is renderer state and is not passed in the FidelityFX descriptor.

The completed synthetic dispatch phase adds these external buffers with deterministic analytic path records and executes this sequence. Renderer-exported path replacement remains a later boundary:

1. Trace paths and enqueue one prediction query per eligible pixel plus bounded training queries/targets.
2. Apply UAV ordering and resource transitions required by the provider.
3. Dispatch reset when requested, inference before training, and clear both counters afterward.
4. Composite predicted radiance only where the renderer retained matching path weight/state.
5. Read back counters and outputs, retain a no-cache reference, and reject non-finite values, counter overflow, guard corruption, resource leaks or identity mismatch.

This remains an isolated synthetic fixture. D3D9 sharing, live IPC, game injection, quality promotion and performance claims wait until the dispatch and no-cache comparison pass.

## Verification

Release and Debug each pass `rc_probe_contract` and `rc_worker_boundary` (2/2). Those contracts cover support enumeration, argument rejection, strict binary identity, isolation fixtures, output caps, timeout/reaping, malformed and mutated reports, the exact provider-metadata workaround, low-budget/injected provider crashes, and fresh-process recovery.

No renderer default, SDK binary, driver, installed game or live integration path changed.
