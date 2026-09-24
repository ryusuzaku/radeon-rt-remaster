# One-click trigger for the HL2 v19 material run.
# Only run this while the Run script terminal says running and you are in gameplay.
#   powershell -ExecutionPolicy Bypass -File tools\Trigger-HL2-v19b-material2.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python tools/game_pass.py trigger build/game-passes/hl2-any-target-v19b-20260911 --name material2
