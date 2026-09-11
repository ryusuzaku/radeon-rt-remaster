# Paired RR albedo-encoding comparison

The isolated recorded worker can now compare the two albedo conventions documented by the pinned RR 1.2.0 header. **Changing the encoding does not repair the measured spatial contrast loss.** Linear remains the default; the renderer, source recordings, shaders, SDK binaries and resource limits are unchanged.

## Explicit pairing

| Requested mode | Uploaded diffuse albedo RGB | SDK flag on reset / continuing frames | Output bundle |
|---|---|---|---|
| `linear` (default) | Original linear albedo, packed to half | 3 / 2 (`RESET` when needed, plus `NON_GAMMA_ALBEDO`) | Historical `RRTRRD01` |
| `sqrt` (opt-in) | Square root of linear albedo, packed to half | 1 / 0 (`RESET` when needed, no `NON_GAMMA_ALBEDO`) | Tagged `RRTRRD02` |

This pairing follows `Kits/FidelityFX/denoisers/include/ffx_denoiser.h`, also described in [AMD's RR manual](https://gpuopen.com/manuals/fsr_sdk/techniques/denoising/). Neither input nor output radiance is divided by albedo or corrected afterward. This is a paired encoding experiment, not a deliberately incorrect guide or flag substitution.

The canonical recording always contains the renderer's original linear albedo. Square-root conversion happens only when packing the worker's albedo texture: double-precision square root, rounding to float32, then conversion to binary16. Python independently reproduces those rounding stages when verifying the packed bytes. Depth, motion, normals, indirect radiance/distance and output initialization remain identical between modes.

`--albedo-encoding` is accepted only for recorded dispatch, not standalone reset, old stationary-sequence or context-only modes. Duplicate, incomplete and unknown options reject. The isolated host forwards the choice to its supervised child. Existing allocation caps and reset-context lifetimes are unchanged.

## Provenance and compatibility

Each new native dispatch report records the actual `albedo_encoding`, `dispatch_flags` and six `packed_sha256` values. Recorded sequence reports also declare their encoding. Managed admission checks the caller's explicit expected mode against all those fields, independently packed inputs and the output header. The final dispatch report must still agree with the last per-frame report and final releases.

Historical linear reports lack encoding and flag fields; they remain readable only as linear. If either per-frame field is present, both are required and checked. Missing metadata cannot opt a square-root report into acceptance. Quality analysis also checks the top-level execution encoding and requires the same explicit mode to decode candidate output.

The default output is unchanged byte-for-byte. The opt-in output has the same bounded layout and size but a distinct header:

| Header field | Linear | Square-root |
|---|---|---|
| Eight-byte magic | `RRTRRD01` | `RRTRRD02` |
| Version at byte 8 | 1 | 2 |
| Frame count at byte 12 | 2–8 | 2–8 |
| Embedded frame size at byte 16 | 196696 | 196696 |
| Tag at byte 20 | 0 | 1 |

The canonical recording digest remains at byte 24; frames start at byte 56, followed by the bundle checksum. Embedded `RRTRRO01` frames retain their original input identity and size. Their encoding provenance is carried by the enclosing bundle and verified execution report: do not detach a square-root frame and present it as a standalone default dispatch. Checksums and consistency checks provide integrity, not authentication against fabricated third-party evidence.

## Run

```powershell
python tools/rr_recorded_dispatch.py --probe build/rr-sdk-probe/Release/rrt_rr_probe.exe --sdk-bin build/dependencies/fsr-2.3.0-probe/Kits/FidelityFX/signedbin --input INPUT.rrcapture --output NEW.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --albedo-encoding sqrt
```

Retain the returned JSON as the execution report. For a PBR recording, supply its original `--materials` sidecar as before. To analyze a bounded supported scene:

```powershell
python tools/rr_quality.py --recording INPUT.rrcapture --output NEW.rrrecordout --scene SCENE.rrscene --shader build/rr-sdk-probe/Release/rrt_rr_inputs.dxil --execution EXECUTION.json --surface-reference --fallback --albedo-encoding sqrt --samples 64 --report NEW-quality.json --reference NEW-reference.npz --require-gates
```

Omitting the mode selects linear and rejects square-root output. `--require-gates` retains measured evidence and exits 2 when any diagnostic gate is failed/unavailable; it does not turn execution into quality acceptance. All output paths must be new. Normal renderer usage and defaults are unaffected.

## Measured results

The paired experiment reuses the [analytic ambient-plane controls](RR_COLOUR_RESPONSE.md): identical canonical data, no indirect sampling uncertainty, independent reference, white/grey/black controls, point/linear textures and eight stationary frames. An additional translating four-frame recording includes a reset at frame 2. This is not a general PBR or game-scene qualification.

Initial Release evidence: `build/rr-sdk-probe/Release/rr-encoding-phy27gzm/verification.json`. All six original linear outputs match the pre-change `rr-colour-0u48aq8r` bundles byte-for-byte. Representative MSE values:

| Case / frame | Default linear encoding | Square-root encoding |
|---|---:|---:|
| Linear texture / 0 | 0.001478449 | 0.001477308 |
| Linear texture / 1 | 0.001169594 | 0.001162839 |
| Linear texture / 7 | 0.001030857 | 0.001029171 |
| Point texture / 0 | 0.003863858 | 0.003868483 |
| Point texture / 1 | 0.002830116 | 0.002841570 |

The linear-texture frame-seven difference is only about 0.16%; point-texture MSE worsens slightly. Square-root frame-seven centered RGB gain remains approximately **0.276, 0.458, 0.211**, far from preserved contrast. White, grey and black RGB/alpha pixel values match the two modes exactly (their bundle tags differ); the zero-light bias remains. Some textured pixels differ more substantially (maximum RGB difference 0.031128 across the eight-frame case), so the modes are not asserted to be bit-equivalent in general.

The actual uploaded albedo hashes and dispatch flags differ as intended. These results show that the tested encoding pairing is not a sufficient remedy. They do not prove why the SDK loses contrast or why individual pixels differ; no internal implementation claim, output correction or default promotion follows.

## Verification and next gate

`rr_encoding` is an optional NumPy-enabled SDK CTest. It checks paired packing, unchanged non-albedo resources and reference arrays, explicit mode/output-tag admission, malformed reports/headers/options, historical linear compatibility, omitted-native-option equivalence, quality-CLI failed-evidence retention, moving resets and recovery after an injected SDK allocation failure. Optional `--baseline PREVIOUS_ANALYTIC_DIRECTORY` additionally checks the six pre-change recordings and linear outputs exactly.

The expanded optimized-Python Debug run passes in `build/rr-sdk-probe/Debug/rr-encoding-d366h8er`: seven paired cases, 28 rejected inputs/reports/options and six historical default matches. The moving-reset case also retains large error: on its final frame, MSE is 0.000988832 for linear versus 0.000944798 for square-root; another moving frame worsens with square-root. These are mixed fixture-specific differences, not a general improvement or accepted reconstruction.

Final Release optional SDK regression passes **9/9** (553.45 seconds), including the encoding test in 140.24 seconds. Its evidence is `build/rr-sdk-probe/Release/rr-encoding-n49hhhv5/verification.json`. All fourteen paired SDK output bundles, seven numeric reference bundles and measurement dictionaries match optimized Debug exactly. The six historical linear outputs also remain byte-identical in this final run. The CLI preserves failed-gate evidence with exit 2, and sqrt-mode allocation-failure injection is reaped before a fresh worker reproduces the prior output.

Compilation, CLI help and local documentation links pass. The broader normal renderer, x86, legacy D3D9 and historical-render suites were not rerun; the changed native headers are included only by the optional research probe. The vendor SDK binaries, source renderer/shaders, driver, installed games, resource caps and default encoding remain unchanged.

The next diagnostic is now implemented: [read-only live-context default queries](RR_DEFAULT_SETTINGS.md), with actual values, return codes and repeated snapshots. No settings are changed. Individually identified setting experiments against these same controls follow that inspection. Depth/distance scale and resolution remain separate hypotheses with explicit budget gates. General image quality and the existing raw SDK reporting failures remain unaccepted.
