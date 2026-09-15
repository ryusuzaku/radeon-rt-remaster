# Capture workbench

Local UI for the game-pass loop, added 2026-09-11 as the first slice of roadmap
section 3. It exists so a capture can be prepared, launched, triggered, inspected
and cleaned up without shell commands.

```powershell
python tools\workbench.py --port 8765
```

Then open <http://127.0.0.1:8765>. Python standard library only — no new runtime or
build dependency.

## It does not own any resources

Every action shells out to `tools/game_pass.py`, so the workbench inherits the
runner's provenance checks, deployment rules and cleanup verification instead of
reimplementing them. Two consequences are deliberate:

- The workbench never copies, replaces or deletes a `d3d9.dll` itself. If a run
  cannot deploy, the runner's refusal is what the page shows.
- A UI action cannot be safer or more dangerous than the equivalent CLI command.

The tests confirm this by asserting the runner's own refusals surface through the
API: deploying over an existing `d3d9.dll`, and a proxy subdirectory that does not
exist next to the executable.

## Confinement and concurrency

- Bundle paths must resolve inside `build/game-passes`; `../` and repository
  paths outside it are refused. The page cannot address arbitrary directories.
- Only one pass may be active at a time, matching the rule that a deployed proxy
  must not be rebuilt or redeployed underneath a running game.
- Run options are whitelisted to the `--position-*`/`--frames`/`--note` set, so the
  page cannot smuggle in an option the runner does not expose.
- Request bodies are capped and must be JSON.

## What the page shows

Per bundle: the plan, the recorded runs, the last trace counters, and, when a
position ledger exists, its `version`, attempts, captures, rejection reasons,
`evidence_failures` and the effective selection policy. The active run's stdout
and stderr are streamed into the log pane, so a runner failure is readable in the
UI rather than only on a console.

The selection field defaults to `any:3`, which needs no advance knowledge of the
game's resolution (see [GAME_PASS.md](GAME_PASS.md)).

## Qualification

`workbench` (`tests/verify_workbench.py`) runs the real server against the real
runner and covers route handling, malformed and empty bodies, path confinement for
prepare/reuse-baseline/run/trigger/cleanup, run-option validation, the runner's
deployment refusals, and the single-active-pass guard. It prepares and removes its
own bundles and never launches a game.

Release 2.62 s and Debug 2.41 s.

## Not yet covered

Roadmap section 3 also calls for a bundle browser with coverage detail, geometry
and material preview, replacement authoring, and replay/export controls with
validation results. None of those are built; this slice covers the
capture → inspect → cleanup loop only.
