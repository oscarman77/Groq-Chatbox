# Start Chatbox. First run creates .venv and installs dependencies.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -c "import fastapi, uvicorn, httpx, jwt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..."
    & .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
}

$env:PYTHONPATH = "."
Write-Host "Chatbox: http://127.0.0.1:8000  (docs: /docs)"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
