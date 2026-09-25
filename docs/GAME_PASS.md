# First owned-game observation pass

This is a baseline and D3D9 extractability pass, **not live ray-traced gameplay**.
Use a native 32-bit DX9 executable. BioShock 2 original is an unqualified,
shader-heavy observation candidate; its remaster is outside this DX9 pass.
Do not use anti-cheat protected/multiplayer sessions for this experiment.

## Prepare

Build Release targets `radeon_d3d9_proxy`, `d3d9_smoke_sample`, and `rrt_replay`
in `build/x86-vs`. Run CTest `game_pass_workflow` before deployment.
Close the game. Supply its actual executable, not Steam or a launcher:

```powershell
python tools/game_pass.py prepare --exe "PATH_TO_GAME.exe" --proxy build/x86-vs/Release/d3d9.dll --out build/game-passes/first --title "Owned DX9 title"
python tools/game_pass.py run build/game-passes/first --mode baseline
```

Preparation records PE architecture and SHA256 provenance without changing the
game directory. Existing `d3d9.dll` files are refused, never overwritten.
For a verified engine layout that searches its renderer directory, preparation
also accepts `--proxy-subdir bin`. Only the existing canonical `bin` directory is
allowed; arbitrary paths and redirected directories are rejected. DLL presence
is not proof it loaded: check trace output and runtime modules. Keep each run's
deployment location in the notes when changing placement within a prepared pass.
Optional launch arguments are a JSON string array in `--args-json`; only use
arguments verified for that title. The baseline must exit normally before the
runner permits deployment. An exit code alone is not proof of healthy gameplay.

## Observe the same scene

Play a short offline scene in the untouched baseline, note resolution, settings,
save location, visual defects and responsiveness, then close normally. Repeat:

```powershell
python tools/game_pass.py run build/game-passes/first --mode proxy --frames 300 --note "Startup and menu observation"
python tools/game_pass.py run build/game-passes/first --mode disabled
```

The runner exclusively creates the local proxy, sets bounded per-process trace
variables, waits for normal exit, and removes only its unchanged DLL. It does not
edit Steam settings, inject into another process, or force the game to terminate.
Disabled mode checks forwarding without observation overhead. Test the same save
and settings each time; do not infer equivalence from trace counts.

Startup/menu results do not qualify gameplay. For another unique run name, use
`--name gameplay --start-frame N --frames 300`; N counts successful presents from
process startup. Choose N from a reproducible route, not a wall-clock guess.
Optional `--scene-frame N` requests the narrow supported fixed-function capture;
shader draws may be observed without being extractable. Inspect a produced scene
with `rrt_replay --inspect PATH_TO_SCENE` before attempting replay.

## Review and recovery

For gameplay observation use `run PASS --mode proxy --name gameplay --wait-trigger`.
Load the repeatable save first, then issue `trigger PASS --name gameplay` from
another terminal. A fresh workspace marker starts tracing at the next successful
Present boundary. The header records the actual start frame; frame/byte limits
still apply. Scene asset capture is not supported in this mode. Before triggering
the file is empty; explicit finish produces a valid zero-event trace, but games
that never explicitly finish may leave an empty file on exit.

### Full material and texture evidence chain (v19)

The texture/material chain is ordered and each step requires the previous one, so a
full pass enables every flag from `--position-capture` through
`--position-surface-locks`:

```powershell
python tools/game_pass.py run build/game-passes/PASS --mode proxy --name material `
  --wait-trigger --shader-inventory --position-capture --position-frames `
  --position-selection any:3 --position-multi-draw `
  --position-render-state --position-clear-evidence --position-write-evidence `
  --position-surface-scope --position-color-replay --position-material-inputs `
  --position-pixel-material --position-texture-inputs --position-texture-assets `
  --position-compressed-textures --position-texture-uploads `
  --position-dirty-textures --position-surface-uploads --position-surface-locks
python tools/game_pass.py trigger build/game-passes/PASS --name material
```

Omit `--position-surface-locks` and the pass runs at v18: every mip-surface
`LockRect`/`UnlockRect` on a tracked texture then invalidates the parent shadow, so
uploads report `source_not_fully_dirty` and no material is admitted. The option
must be present for the evidence chain to work at all; see
[SURFACE_LOCK_QUALIFICATION.md](SURFACE_LOCK_QUALIFICATION.md).

`any:MIN_TRIANGLES` accepts any render-target extent while still applying the
minimum-primitive filter, so **the chain no longer requires knowing the game's
resolution in advance**. The exact `WIDTHxHEIGHT:MIN_TRIANGLES` form is unchanged
and still selects one target precisely. In `any` mode every rejected draw carries
`selection_observed`, so the ledger reports which targets the game actually
rendered and which of them reach the scene passes; `any` requires
`--position-multi-draw` and fails closed without it.

### Reading the shadow-budget result

A pass built after the peak instrument landed writes `retained_peak`,
`peak_buffers` and `peak_textures` into the ledger footer alongside the stop
values. **The peak is the one that decides policy**: a reservation that was
*refused* proves the total was higher at that moment than at the stop, so a
capture that stops below the cap tells you nothing about what filled it.

```powershell
python tools/analyse_shadow_budget.py build/game-passes/PASS --refused-bytes 94371840
```

Pass a ledger directly, or a pass directory and it finds the newest
`position-capture.jsonl` under `runs/`. It reads the 128 MiB cap from the proxy
source rather than repeating it, reports the stop and peak splits side by side,
names whether the peak is buffer- or texture-dominated, and — given the refused
demand in bytes — says what cap would have admitted it.

It **exits 3 and refuses to answer** if the ledger has no peak fields. That is
deliberate: the stop split cannot answer the question, and a tool that quietly
analysed it anyway would produce a confident wrong recommendation. `20 * 4718592`
is the 90 MiB that `material3`'s twenty refused 1024x512 `A16B16G16R16` inputs
represent.

A triggered capture arms on the first successful Present after the trigger and
starts its interval numbering there. If the game is not presenting when the
trigger lands — the usual case when the window is in the background — nothing is
attempted and the attempt budget is untouched, so the pass waits for a real frame
instead of draining itself. Untriggered sampling keeps the historical interval
numbering.

After rebuilding only the proxy, `reuse-baseline NEW_PASS --from-pass OLD_PASS`
can retain an earlier successful native baseline. Executable path/hash and native
arguments must match, and the original report must show uninstrumented normal
exit and unchanged executable. Its path/hash are stored in the derived report.
This does not requalify a changed proxy or imply a fresh native run occurred.

Each run saves `report.json`, and observed proxy runs save `trace.jsonl` plus
`trace-summary.json`. Review successful presents, fixed/shader draw counts,
failed calls, trace completeness, native/proxy/disabled behavior, and cleanup.
Record API/executable variant, settings, save route and visual observations with
the artifacts. `observation-ready-for-review` does not mean compatible: every
report deliberately keeps game compatibility unassessed.

If Steam relaunches the executable or a launcher exits early, an absent trace is
`proxy-load-unconfirmed`. Stop and inspect the launch path; do not bypass DRM.
If interrupted while the game is alive, close it before explicit recovery:

```powershell
python tools/game_pass.py cleanup build/game-passes/first --name proxy --game-closed
```

The acknowledgement is the operator's confirmation that the game is closed.
Changed or replaced DLLs are preserved for manual review. Rebuilding the source
proxy invalidates a prepared plan, so finish cleanup before rebuilding.

## Current qualification boundary

The workflow is covered by an actual x86 harness baseline/proxy/disabled run,
exact pixel comparison, selected trace/scene capture, replay inspection, and
existing-mod/path/provenance rejection checks. No commercial title is qualified.
On this session, classic DX9 tests pass; DX9Ex native system-runtime presentation
returns S_PRESENT_OCCLUDED even with a visible window and bounded retries. Ex
qualification remains blocked by that presentation result, not silently accepted.
