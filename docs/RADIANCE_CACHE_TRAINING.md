# FidelityFX Radiance Cache persistent training

## Result

The pinned Radiance Cache 0.9.0 provider retains online training state across dispatches on one D3D12 context. One default 512-sample training batch changes every subsequent prediction, moves the deterministic synthetic output slightly toward its analytic target, and an explicit reset restores the original prediction byte-for-byte.

This proves bounded online learning and reset behavior for the synthetic fixture. It does not establish game-scene accuracy, compositing quality, convergence speed or performance. The managed result keeps `rc_rendering` false.

Raw SDK acceptance remains failed because the post-context provider query still returns code 4/ID 0. Only the existing exact SDK-hash-pinned metadata workaround is admitted.

## Sequence

One context and the exact 716,808-byte external buffer set are preserved across four fenced stages:

1. `RESET | INFERENCE` with counters `{12288, 0}` establishes the baseline.
2. `TRAINING` with counters `{0, 512}` updates the model using the analytic input/target pairs.
3. `INFERENCE` with counters `{12288, 0}` observes retained state without reset.
4. `RESET | INFERENCE` with counters `{12288, 0}` verifies recovery.

Every stage also requests both counter clears. Before each dispatch, the worker uploads its exact occupancy and NaN prediction sentinel, transitions the reused buffers, submits a fresh command list, waits on the shared bounded fence, and reads all five buffers back. Command allocators and lists never reset before their work completes.

The sequence deliberately uses the SDK defaults: learning rate `0.002` and prediction-weight smoothing `0.99`. No override is used to amplify the effect.

## Measurement

| Measurement | Baseline | After one training batch | Reset |
| --- | ---: | ---: | ---: |
| Output FNV-1a64 | `8439070038676242095` | `11036946020368386469` | `8439070038676242095` |
| Output minimum | 0.0265808 | 0.0266418 | 0.0265808 |
| Output mean | 0.0350016 | 0.0350256 | 0.0350016 |
| Output maximum | 0.0398865 | 0.0399475 | 0.0398865 |
| Analytic-target MSE | 0.0500247 | 0.0500075 | 0.0500247 |

Post-training comparison against baseline:

- changed RGB values: 36,864 / 36,864;
- pairwise MSE: `2.97242e-9`;
- maximum absolute delta: `7.62939e-5`;
- analytic-target MSE reduction: approximately 0.0344%.

The effect is small, as expected after one batch with 0.99 smoothing, but it is nonzero and target-directed. That is sufficient to demonstrate retained learning state in this fixture. The experiment does not extend to eight batches because the predeclared expansion condition—no change after one batch—did not occur.

The final reset comparison has zero changed values, zero MSE and zero maximum difference. Reset recovery is therefore exact, not tolerance-based.

## Safety evidence

Every dispatch returns code 0, completes its fence and leaves both counters at zero. Prediction/training inputs and training targets remain byte-exact after every stage. The training-only step leaves the prediction buffer at all NaN sentinels, confirming that it does not write inference output. The device remains healthy throughout.

The provider allocation lifecycle remains unchanged: 20,643,840-byte peak, 11 allocations, 11 releases and zero live bytes/errors/denials after destruction. A 1 MiB context ceiling still causes the preview provider to access-violate; the job contains and reaps it, and a fresh normal sequence reproduces the accepted hashes.

The managed contract rejects incorrect step order/count, counter residue, output hashes, target-error direction, reset mismatch, input/target mutation, resource leakage, non-finite report data and unreviewed workarounds.

## Reproduce

```powershell
cmake --build build/rr-sdk-probe --config Release --target rrt_rc_probe
py tools/rc_sequence_worker.py --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin
ctest --test-dir build/rr-sdk-probe -C Release -R "rc_probe_contract|rc_worker_boundary|rc_dispatch_contract|rc_sequence_contract" --output-on-failure
```

Use `-C Debug` for the second build configuration. Release and Debug reproduce the same baseline, trained and reset hashes.

## Next boundary

The renderer side of the next step is now defined by the strict [`RCRPATH1` export](RADIANCE_CACHE_PATHS.md). Provider ingestion must retain this exact sequence and all lifecycle gates. The source contract supplies:

- normalized scene-bound positions and matching octahedral normal/view directions from actual ray hits;
- subpath radiance targets with the documented primary-albedo factorization;
- renderer-owned throughput weights and query-validity state;
- guarded multiply-add compositing against the existing no-cache path-traced output;
- independent no-cache and analytic scene references before any quality claim.

Live IPC, D3D9 game injection, default replacement and performance promotion remain out of scope until that offline renderer path passes.

No renderer default, SDK/provider binary, driver, installed game or live integration path changed.
