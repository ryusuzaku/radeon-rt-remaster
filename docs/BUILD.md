# Build, run, and inspect

## Prerequisites

- Windows with a D3D9-capable graphics driver for the GPU tests.
- **Visual Studio 2022** C++ Build Tools, x86 toolset, and Windows SDK.
- CMake 3.25+.
- Python 3.10+ for tests and inspection. Code generation uses only Python's standard library; generated C++ is checked in.

`CMakePresets.json` names the `Visual Studio 17 2022` generator explicitly, so a
machine with only a newer Visual Studio does not satisfy it: configure fails with
`could not find any instance of Visual Studio`. Install the 2022 toolset, or add a
preset for the generator you have. This is why CI pins `windows-2022` — the
`windows-latest` image is now `windows-2025-vs2026`, which ships Visual Studio 2026.

## Reproducible x86 commands

These Visual Studio presets do not require a developer shell:

```powershell
cmake --preset windows-x86
cmake --build --preset debug
ctest --preset debug
cmake --build --preset release
ctest --preset release
```

Outputs are in `build/x86-vs/Debug` and `build/x86-vs/Release`: `d3d9.dll`, `d3d9_smoke_sample.exe` and `rrt_replay.exe`. The scene codec uses Windows BCrypt SHA-256; there is no third-party runtime dependency.

With Windows SDK DXC available, these builds also include `rrt_dxr.exe` and
`rrt_rayquery.dxil`, `rrt_temporal.dxil`, `rrt_present.dxil`, `rrt_export.dxil`,
`rrt_display_vertex.dxil` and `rrt_display_pixel.dxil`. Deploy all six matching shaders with the
executable. Prefer the separate x64 renderer for standalone DXR work:

```powershell
cmake --preset windows-x64-renderer
cmake --build --preset renderer-debug
ctest --preset renderer-debug
cmake --build --preset renderer-release
ctest --preset renderer-release
```

This outputs only standalone renderers (no game proxy) into
`build/x64-renderer/Debug` and `Release`. See [DXR_VIEWER.md](DXR_VIEWER.md) for
capability requirements, DXC discovery, modes and limitations.

For a runtime-only build, configure a separate binary directory with `-DBUILD_TESTING=OFF` to avoid requiring Python. If using Ninja, activate an x86 Visual Studio environment and omit `-A Win32`; Ninja does not support that platform argument.

## Tests

The suite is defined in `CMakeLists.txt`, and its size depends on which optional
inputs are present, so no fixed count is quoted here — run
`ctest --test-dir build/x86-vs -C Debug -N` to list what your checkout has.

Always present: trace-reader and mod-validation suites, classic/Ex mod replay,
classic/Ex proxy equivalence, classic/Ex scene replay, the contract checks
(`codegen_freshness`, `capture_version_contract`, `published_references`,
`shadow_budget_tool`, `evidence_registration`, `evidence_archive`,
`restored_tree`) and smoke/help entry points. Integration tests load the system DLL explicitly for
baseline renders, confirm the proxy marker when requested, and compare raw image
bytes with proxy-on, trace-off, and proxy-disabled runs.

Added when DXC is available: `dxr_probe`, `dxr_render`, `dxr_temporal`,
`dxr_resolution`, `dxr_presentation`, `dxr_async`, `dxr_pacing`, `dxr_materials`
and the CPU-only `material_inputs`. The renderer-only x64 presets run these with
their own raster oracle. The DXR GPU tests skip explicitly on unsupported
adapters; they do not silently use a software renderer. Standard D3D12
debug-layer validation is enabled when the Windows Graphics Tools component is
installed.

All 13 local-evidence tests stay registered in the x86 build, including
`texture_*`, `position_capture` and the recorded-position suites. They carry the
`local_evidence` label. When a required file is unavailable, CTest lists the test
as **Skipped**, and verbose output names the path and the CMake variable to set.
Existing malformed evidence still fails the original validator. Evidence is
checked at execution time, so restoring or removing a file takes effect without
reconfiguring; changing the configured path requires another CMake configure.

```powershell
ctest --test-dir build/x86-vs -C Release -L local_evidence -V
cmake --preset windows-x86 "-DRRT_HL2_POSITION_INVENTORY=P:/owned-pass/shader-inventory.jsonl" "-DRRT_HL2_POSITION_CAPTURE=P:/owned-pass/position-capture.jsonl" "-DRRT_HL2_GROUP_CAPTURE=P:/owned-multidraw/position-capture.jsonl"
```

The inventory enables nine tests, the position capture three, and the grouped
capture one. These need the pinned HL2 programs/recording shapes described in
[the position contract](HL2_POSITION_CONTRACT.md) and
[grouped replay](HL2_GROUPED_POSITION_REPLAY.md); arbitrary JSONL is not a substitute.
Obtain the files from your owned local pass or a private backup. Game artifacts
remain excluded from the public repository; retention storage is still undecided.
The GPU-free `evidence_registration` contract checks registration of all 13 tests
and real CTest missing/restored/invalid evidence transitions, including paths with
spaces and preservation of child exit codes. CI runs this contract.

Measured 2026-10-19 with restored evidence on the RX 9070 XT: the whole
`local_evidence` label takes about 11 minutes in x86 Debug, and `texture_upload`
alone takes 156 s. Its CTest budget was 120 s and killed a passing test; it is now
300 s. If a texture test times out, time the underlying command before assuming a
defect.

### Pure-Python tool checks

A separate Linux CI job (the `python-tools` workflow) runs the part of the suite
that needs no Windows, GPU, game content or built binaries: standard-library-only
tools and tests. It byte-compiles everything under `tests` and `tools`, runs the
GPU-free contract scripts, and runs the standard-library unit tests:

```bash
python3 -m compileall -q tests tools
python3 tests/verify_codegen_freshness.py
python3 tests/verify_capture_version_contract.py
python3 tests/verify_published_references.py
python3 tests/verify_shadow_budget_tool.py
python3 tests/verify_evidence_archive.py
python3 tests/verify_restored_tree_contract.py
python3 tests/test_trace_reader.py
python3 tests/test_position_scene.py
python3 tests/test_material_inputs.py
python3 tests/test_mods.py
python3 tests/test_evidence_archive.py
python3 tests/test_png_texture.py
python3 tests/test_bench_rocm_attention.py
```

`evidence_registration` is excluded from that job because it drives CMake/CTest
against a configured build, and the NumPy-based `rr_*` settings contracts are
excluded because the job deliberately does not install
`tools/requirements-rr-quality.txt`; both stay on the Windows job.

### Restoring a preserved tree

A consolidation that removes `build/` does not necessarily destroy it. The
2026-10-15 move preserved the whole pre-move tree — gitignored content included —
as a WIM image plus a SHA-256 manifest, and that is how the pass bundles were
recovered on 2026-10-19. The pattern is worth knowing before writing evidence off:

```powershell
# List what the image holds without extracting anything.
wimlib-imagex.exe dir IMAGE.wim 1 | Select-String "game-passes"

# Extract one subtree, preserving its path, and check the image while doing it.
wimlib-imagex.exe extract IMAGE.wim 1 '\build\game-passes' --check `
    --preserve-dir-structure --no-acls --dest-dir=DEST

# Verify every extracted file against the manifest that shipped with it.
python tools/verify_restored_tree.py MANIFEST.jsonl DEST --prefix "build\game-passes\"
```

The verifier compares path, byte count and SHA-256 for every declared file and
fails on anything missing, resized, changed or extra — the four ways an extraction
goes wrong quietly. It prints counts and names up to twenty problems.

The 2026-10-19 run extracted 881 MiB and verified 738/738 files with zero
problems. Verify before trusting: the image is a copy of a working tree, not a
signed artifact, and the manifest is what makes the comparison meaningful. Never
extract over a live working tree.

### Keeping a pass

`build/` is gitignored, so a cleanup or a workspace move deletes pass bundles
without warning. That happened on 2026-10-15 and took the shader inventory and the
candidate program's bytecode with it. The retention policy is now decided:

- **Archives live outside the working tree**, one file per pass. The root is
  `--evidence-root`, else `RRT_EVIDENCE_ROOT`, else
  `<repo parent>/radeon-rt-remaster-evidence`.
- **`docs/EVIDENCE_LEDGER.jsonl` is the only tracked artifact.** It records the
  pass name, file count, sizes and the archive's SHA-256 — never content — so it
  can live in git without redistributing anything captured from a game.
- **`check` is the verification command, not `verify`.** An archive carries its
  own manifest, so a rewrite that regenerates the manifest is self-consistent;
  the ledger is the record outside the artifact that detects it.
- **Nothing is committed from an archive.** No Git LFS, no object store, no
  captured content in history. A destination that git would track is refused
  outright rather than warned about, because that mistake has a legal consequence
  rather than a data one. Re-capture remains the fallback for content, but the
  ledger makes losing an archive a visible mismatch instead of a silent absence.

```powershell
python tools/game_pass.py archive build/game-passes/PASS --note "material pass, windowed 1920x1080"
python tools/evidence_archive.py check "P:/workspace/ninja-code/radeon-rt-remaster-evidence/PASS-20261019-091500.tar.gz" --ledger docs/EVIDENCE_LEDGER.jsonl
python tools/evidence_archive.py restore ARCHIVE --out P:/restored/PASS
```

The lower-level verbs are available directly: `create` (with `--out` for an exact
path or `--evidence-root` for the policy root), `verify` for self-consistency,
`list` for a summary, and `restore`. The archive manifest holds a SHA-256 per
file, so `verify` names any member that changed, disappeared or was added, and
exits 1 rather than reporting a plausible success. `restore` refuses a non-empty
target, refuses to overwrite, and refuses members that are not regular files or
that would land outside the target. Bounds are 200,000 files, 2 GiB per file and
8 GiB total; `--max-files` can only lower the file bound, never raise it. CTest
`evidence_archive` is the GPU-free contract covering corruption, truncation,
traversal, symlinks, ledger mismatch and the refusals.

The fixture draws textured indexed geometry through fixed-function and shader paths and includes UP draws, resource/stateblock identities, device/swap-chain Present, invalid-reset recovery, resize, readback, and resource-held device lifetime recovery. Trace checks cover record validation, deterministic IDs/counts, selected frame ranges, byte budgets, and unavailable/existing output paths.

Artifacts are retained under `build/x86-vs/<configuration>/verify-*`. Each directory includes pixel dumps and traces from that test. `LastTest.log` records the exact artifact directory.

Scene replay artifacts are under `scene-*`, including PNG previews, raw pixels, captures, image-diff JSON and glTF exports. See [SCENE_CAPTURE.md](SCENE_CAPTURE.md) for the supported subset, format, controls and replay commands.

Mod artifacts are under `mods-*`, including editable assets/manifests, modified scenes, PNGs and isolation reports. The [offline creator workflow](MOD_WORKFLOW.md) uses Python's standard library only; there is no extra SDK/image-library installation step.

## Troubleshooting a failing run

**`fixture present did not happen ... the fixture window is covered`.** The fixture
draws into its own D3D9 window, and Windows returns a *success-severity* status
such as `S_PRESENT_OCCLUDED` when that window is not visible. The frame is then
never presented, so a capture that samples frames stalls and produces no footer.
Bring the fixture window to the foreground and re-run; the message names the
condition so it does not look like a code defect. This is why a test that fails
with a present-related message should be retried before it is investigated.

**A test fails once and passes on retry.** The GPU suites are sensitive to the
desktop state — window occlusion above all, and occasionally a transient file lock
on a ledger read. Re-run before treating a red suite as evidence of a regression.
Wall time varies too: the same suite has been observed at 430 s and 638 s on
consecutive runs, both green.

**`error MSB6001: Invalid command line switch for "cmd.exe"` with
`Item has already been added. Key in dictionary: 'HTTPS_PROXY' Key being added:
'https_proxy'`.** The build is fine; the environment is not. MSBuild's C++ tasks
build a case-insensitive dictionary from the process environment, and it throws if
both spellings of a proxy variable are present. Unset one of them for the build:

```bash
env -u https_proxy -u http_proxy cmake --build build/x86-vs --config Release
```

This affects any MSBuild C++ project, not just this one, and the message points at
`cmd.exe` rather than at the real cause.

**`texture_*` or `position_capture` did not run at all.** They are gated on
`build/game-passes/hl2-inventory-20260907`. Without a captured pass those tests are
not registered, which is expected on a clean checkout.

## Direct use

```powershell
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --runtime system --frames 12
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --frames 12
.\build\x86-vs\Debug\d3d9_smoke_sample.exe --ex --frames 12
```

The sample prints render hashes for images at 256x192 and 320x240. `--pixels PATH` writes concatenated BGR byte arrays for exact comparison. `--read-frame N` selects a single image; `--scene-fixture` selects the four-draw replay fixture. The DLL is selected by an absolute path; neither fixture nor replay has a D3D9 import dependency that could accidentally load the wrong provider.

See [README](../README.md) for a trace example and [TRACE_FORMAT](TRACE_FORMAT.md) for all environment controls. The earlier automatic LOCALAPPDATA text log was replaced by explicit opt-in observation traces.

## Regenerate API forwards

```powershell
python tools/generate_observers.py
```

The generator uses the checked-in `tools/d3d9_interfaces.json` SDK signature inventory. API parameter unwrapping, returned-object wrapping, and trace policy live in the generator; identity ownership lives in `src/proxy/observers.cpp`.

## Current qualification

Verified on one Radeon RX 9070 XT (driver 32.0.31041.1004) in x86 Debug and Release. Unknown private COM interfaces and undocumented exports are unsupported. Real-game startup/input/fullscreen/alt-tab qualification, a second Radeon, and timing/VRAM budgets remain acceptance work. Commercial games have not been modified or tested.
