# FidelityFX Radiance Cache synthetic dispatch

## Result

The pinned FidelityFX Radiance Cache 0.9.0 provider now executes real D3D12 inference and training work in the supervised x64 worker on the Radeon RX 9070 XT. Reset, inference, optional training, counter clearing, GPU submission, fence completion and full readback all succeed in both Release and Debug.

This is a deterministic synthetic interface fixture, not a rendered game frame. The managed report sets `rc_dispatch_executed` true while keeping `rc_rendering` false. Nothing is connected to the D3D9 proxy, normal renderer or installed games.

The provider still returns `FFX_API_RETURN_NO_PROVIDER` (4) and ID 0 from its post-context identity query. Raw SDK acceptance remains failed; the managed path admits only that exact result with the already pinned SDK DLL hashes.

## Fixture contract

The fixture uses the exact layout audited from AMD's sample:

- 12,288 prediction records at 44 bytes each;
- 12,288 RGB prediction outputs at 12 bytes each;
- 512 training records at 44 bytes each;
- 512 RGB training targets at 12 bytes each;
- two 32-bit sample counters.

The five default-heap buffers total exactly 716,808 bytes. Matching upload and readback buffers total 1,433,616 staging bytes and are reported separately from the provider's callback-managed context memory.

Prediction records contain deterministic normalized position, octahedral normal/view direction, diffuse albedo and roughness gradients. Training targets are bounded analytic RGB values derived from position. Every prediction output begins as a NaN sentinel.

The command list uploads all five resources, transitions them to compute-readable state, then dispatches:

1. cache reset;
2. inference over 12,288 populated queries;
3. optional training over 512 populated records;
4. clearing of both sample counters;
5. transitions and copies of all five buffers to readback resources.

The worker waits on a bounded fence before examining bytes or destroying the context.

## Measured output

Both `inference` and `combined` modes pass the same strict checks:

| Measurement | Result |
| --- | ---: |
| Dispatch return code | 0 |
| Inference/training counters after dispatch | 0 / 0 |
| Finite output values | 36,864 / 36,864 |
| Nonnegative output values | 36,864 / 36,864 |
| NaN sentinels replaced | 36,864 / 36,864 |
| Minimum radiance | 0.0265808 |
| Mean radiance | 0.0350016 |
| Maximum radiance | 0.0398865 |
| Output FNV-1a64 | `8439070038676242095` |
| Provider callback peak | 20,643,840 bytes |
| Provider allocations/releases | 11 / 11 |
| Live provider bytes after destroy | 0 |

All prediction inputs, training inputs and training targets remain byte-exact after provider execution. Both counters clear, the device removed reason remains `S_OK`, and D3D12 debug validation reports no error.

Inference-only, combined inference+training and a fresh combined repeat are byte-identical in Release and Debug. This matches the documented ordering: inference is executed before training, so training cannot change that dispatch's prediction output. It does **not** yet prove useful learning; a later inference on the same context without reset is required to observe trained state.

## Failure containment

The managed boundary rejects malformed or duplicate JSON, non-finite JSON values, changed layout/accounting, counter residue, partial/non-finite output, sentinel residue, mutated inputs/targets, device removal, callback leaks and any unreviewed metadata workaround.

A 1 MiB provider ceiling still causes the preview provider to access-violate instead of returning a memory error. The job contains and reaps that child. A fresh 32 MiB dispatch immediately reproduces the accepted output, proving process-level recovery.

## Reproduce

```powershell
cmake --build build/rr-sdk-probe --config Release --target rrt_rc_probe
py tools/rc_dispatch_worker.py --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin --mode inference
py tools/rc_dispatch_worker.py --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin --mode combined
ctest --test-dir build/rr-sdk-probe -C Release -R "rc_probe_contract|rc_worker_boundary|rc_dispatch_contract" --output-on-failure
```

The same CTest command with `-C Debug` verifies the second build configuration.

## Next boundary

The [persistent-context training sequence](RADIANCE_CACHE_TRAINING.md) now completes these steps:

1. reset and capture the default inference output;
2. execute one or more bounded training batches;
3. infer again without reset;
4. measure exact output delta, counter behavior and finite/nonnegative stability;
5. reset and require recovery of the original output.

Trained-state behavior and exact reset recovery are now understood for the analytic fixture. The next phase may replace those records with renderer-exported paths and add guarded compositing against the existing no-cache result. Live IPC, game injection, quality promotion and performance qualification remain later phases.

No renderer default, SDK/provider binary, driver, installed game or live integration path changed.
