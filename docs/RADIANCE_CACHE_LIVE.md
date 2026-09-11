# Isolated live Radiance Cache transaction

The first no-file renderer-to-cache transaction is implemented for the 128×96 synthetic legacy-diffuse scene. It remains explicit, supervised and disabled by default. The normal renderer output is always authoritative; the cache candidate is measured but never applied.

## Architecture

`rrt_dxr --rc-stream` renders normally, prepares the exact self-checksummed `RCRPATH1` payload in memory and writes only its fixed 1,573,120 bytes to binary stdout. It rejects file outputs, recordings, windows, filtering, temporal work, custom shaders and material sidecars in this mode.

[`tools/rc_live_worker.py`](../tools/rc_live_worker.py) validates that stream, starts `rrt_rc_probe --isolated-stream-sequence`, and transfers the payload through a bounded inherited stdin pipe. The probe host assigns the suspended child to the one-process kill-on-close job before resuming it. The child reads the exact payload and EOF before provider initialization, verifies both SHA-256 chains, and then executes the existing persistent sequence.

The preview provider is intentionally not linked into the renderer. Its demonstrated allocation-denial access violation therefore terminates only the job-contained optional worker. A crash, timeout, malformed stream or unadmitted report leaves `authoritative_output: no-cache`, `candidate_applied: false`, and `fallback_available: true`.

## Persistent-frame evidence

The canonical stream contains 172 valid query/training records. One training frame reproduces the file-backed result exactly. Two consecutive training frames on one provider context give:

| Metric | Baseline | One frame | Two frames |
|---|---:|---:|---:|
| Target MSE | 0.00125381 | 0.00124904 | 0.00123874 |
| Guarded composite MSE | 0.0000777365 | 0.0000774054 | 0.0000767191 |
| Prediction hash | 4380958906282038366 | 17423046786485749504 | 13270289865275143940 |

All 516 mapped RGB values change after training. Reset returns the baseline hash exactly. The provider still writes all 36,864 fixed-capacity output floats; every value is guarded, while only the explicit 172 mappings participate in the candidate.

A camera offset produces a different artifact digest and a fresh supervised child/context. That changed input independently improves its target and composite metrics and passes exact reset, proving scene/camera identity cannot inherit stale state in this prototype.

## Failure and timing evidence

The contract rejects truncation, any extra byte, checksum corruption, wrong modes, report identity/count/composite mutation and unreviewed provider metadata. A 1 MiB provider budget contains the known provider crash; a 1 ms worker deadline reaps the child; the next normal transaction recovers the exact accepted decision.

A representative warm two-frame Release run on the RX 9070 XT measured approximately 350 ms for renderer process/export, 538 ms for isolated provider work and 998 ms end-to-end. These process-startup/readback figures establish an upper-bound prototype cost, not a performance target.

```powershell
python tools/rc_live_worker.py `
  --dxr build/rr-sdk-probe/Release/rrt_dxr.exe `
  --scene path/to/fixture.rrscene `
  --probe build/rr-sdk-probe/Release/rrt_rc_probe.exe `
  --sdk-bin build/dependencies/fsr-2.3.0-radiance-cache/Kits/FidelityFX/signedbin `
  --training-batches 2
```

## Remaining boundary

This is live process scheduling, but not yet a shared-GPU-resource renderer integration. It still performs a renderer readback, CPU pipe transfer and separate provider upload, and it does not produce a presented cache-composited image. The next optimization boundary is shared D3D12 resources/fences across the crash-contained process boundary, followed by temporal quality evaluation. D3D9 game integration remains behind those gates.
