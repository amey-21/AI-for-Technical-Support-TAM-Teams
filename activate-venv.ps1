# Dot-source this file from PowerShell: `. .\activate-venv.ps1`
# Some Windows Python distributions omit Activate.ps1 from new virtualenvs.
$venvPath = Join-Path $PSScriptRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Create it first with: python -m venv .venv"
}

$env:VIRTUAL_ENV = $venvPath
$env:Path = "$(Join-Path $venvPath 'Scripts');$env:Path"
Write-Host "Activated virtual environment: $venvPath"
