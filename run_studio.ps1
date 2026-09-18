$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  Starting Self-Operating Computer Studio GUI" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $PSScriptRoot
Write-Host "Using Python: $pythonExe" -ForegroundColor Gray
Write-Host ""

& $pythonExe -m operate --gui @args
exit $LASTEXITCODE
