$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonLauncher -and -not $pythonCommand) {
    Write-Error "Python 3 was not found. Install Python from https://www.python.org/downloads/windows/ and enable 'Add Python to PATH'."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating the project virtual environment..."
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3 -m venv .venv
    } else {
        & $pythonCommand.Source -m venv .venv
    }
}

Write-Host "Installing Python dependencies..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next: .\start-backend.ps1"
