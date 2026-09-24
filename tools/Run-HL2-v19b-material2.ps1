# One-click HL2 v19 material run — no copypaste needed.
# Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File tools\Run-HL2-v19b-material2.ps1
# Then, once in gameplay and presenting, trigger from a second terminal:
#   powershell -ExecutionPolicy Bypass -File tools\Trigger-HL2-v19b-material2.ps1
# Or open the workbench UI and press Trigger instead.
$ErrorActionPreference = 'Stop'
# Resolve repo root (tools\ -> repo root)
Set-Location (Join-Path $PSScriptRoot '..')
python tools/game_pass.py run build/game-passes/hl2-any-target-v19b-20260911 `
  --mode proxy --name material2 `
  --wait-trigger --shader-inventory `
  --position-capture --position-frames --position-selection any:3 `
  --position-multi-draw --position-render-state --position-clear-evidence `
  --position-write-evidence --position-surface-scope --position-color-replay `
  --position-material-inputs --position-pixel-material --position-texture-inputs `
  --position-texture-assets --position-compressed-textures --position-texture-uploads `
  --position-dirty-textures --position-surface-uploads --position-surface-locks `
  --note "unfiltered any:3 target; v19 surface locks; arm on first present."
