$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Project environment not found. Run .\setup.ps1 first."
}

& $python clients\local_test.py
