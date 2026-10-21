$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Project environment not found. Run .\setup.ps1 first."
}

if (-not $env:MYSQL_PASSWORD) {
    $securePassword = Read-Host "Enter your MySQL password" -AsSecureString
    $env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
}

Write-Host "Seeding the MySQL database..."
& $python backend\database_seeder.py

Write-Host "Starting the Flask backend at http://127.0.0.1:5000"
& $python backend\app.py
