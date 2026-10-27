$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Project environment not found. Run .\setup.ps1 first."
}

Write-Host "Running the research calibration experiment..."
& $python backend\experiment.py --output research\results\results.csv

Write-Host ""
Write-Host "Running the comparative evaluation..."
& $python generate_and_evaluate.py

Write-Host ""
Write-Host "Research runs complete. Generated files are in research\results\."
