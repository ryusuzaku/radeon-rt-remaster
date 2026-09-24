# Renderer-exported Radiance Cache paths

`--rc-paths NEW_FILE` adds a bounded, offline diagnostic to the 128×96 headless legacy-diffuse GI renderer. It traces the same captured scene through a separate deterministic compute pass and writes `RCRPATH1`; it does not call FidelityFX, alter the normal frame, or enable cache rendering.

## Source contract

The artifact is fixed at 1,573,120 bytes: a 224-byte header, 12,288 rows of 128 bytes and a 32-byte whole-file SHA-256. The header binds version/dimensions, actual query/training counts, scene/shader/settings digests, world bounds and lighting/random settings.

Each pixel retains secondary position/validity, Cartesian normal and view direction, diffuse albedo/roughness, unfactorized target radiance, renderer-owned throughput, exact no-cache indirect radiance/distance, and direct-or-background radiance with primary validity. Only valid secondary hits become cache queries. Training uses the first `min(valid hits, 512)` rows in deterministic pixel order; no padded records are admitted.

The initial contract deliberately rejects PBR/material sidecars. For legacy diffuse paths:

`no-cache indirect = (primary albedo × secondary albedo) × secondary direct radiance`

This gives an independently checkable cache replacement:

`candidate RGB = direct/background + throughput × predicted radiance`

Misses and inactive pixels never receive a cache prediction.

## Validation

[`tools/inspect_rc_paths.py`](../tools/inspect_rc_paths.py) verifies the complete digest chain, fixed layout, counts, bounds, validity, unit directions, nonnegative ranges and the source factorization. It derives the provider's 11-float normalized input only after validating the Cartesian source row.

The canonical fixture produces 172 genuine queries/training records. A repeated export is byte-identical, and ordinary pixel and signal artifacts are byte-identical with and without path export. Malformed files, semantic mutations, unsupported rendering modes/options, collisions and overwrite attempts fail closed.

The same artifact now runs through the signed Radiance Cache 0.9.0 provider inside the existing isolated persistent context. Baseline inference hash is `4380958906282038366`; one 172-sample training batch changes all 516 mapped RGB predictions and produces hash `17423046786485749504`. Target MSE improves from `0.00125381` to `0.00124904`, while guarded query-composite MSE improves from `7.77365e-5` to `7.74054e-5`. Reset restores the baseline byte-for-byte.

The preview WMMA provider writes the full fixed-capacity output even with occupancy 172. All 36,864 output floats are therefore still guarded for finite, nonnegative writes, while only the 172 explicitly mapped entries participate in target/composite metrics. Padding can never affect the candidate image.

```powershell
cmake --build build/x64-renderer --config Release --target rrt_dxr
ctest --test-dir build/x64-renderer -C Release -R "rc_paths_export" --output-on-failure
py tools/inspect_rc_paths.py path.rcpaths
py tools/rc_sequence_worker.py --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin --path-sequence path.rcpaths
```

## Remaining boundary

The offline renderer-to-provider-to-composite evidence chain is complete. The next [isolated live transaction](RADIANCE_CACHE_LIVE.md) now removes the filesystem exchange while preserving crash containment. It demonstrates a small target-directed improvement on synthetic legacy-diffuse inputs, not convergence or commercial-game quality. Shared GPU resources, game injection, default replacement and performance claims remain out of scope.
