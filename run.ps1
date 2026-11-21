# Start Chatbox: builds .venv on first run, serves the app, opens the browser.
# Prefer run.cmd on Windows: it avoids the PowerShell execution-policy block.
param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$url = "http://127.0.0.1:$Port"

function Test-ChatboxRunning {
    try {
        $response = Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Open-Chatbox {
    param([string]$Target)
    if ($NoBrowser) { return }
    # Wait until the server answers, then open the default browser at that moment.
    Start-Job -ArgumentList $Target -ScriptBlock {
        param($u)
        for ($i = 0; $i -lt 60; $i++) {
            try {
                Invoke-WebRequest -Uri "$u/api/health" -UseBasicParsing -TimeoutSec 1 | Out-Null
                Start-Process $u
                return
            } catch {
                Start-Sleep -Milliseconds 500
            }
        }
    } | Out-Null
}

if (Test-ChatboxRunning) {
    if ($NoBrowser) {
        Write-Host "Chatbox is already running at $url" -ForegroundColor Green
    } else {
        Write-Host "Chatbox is already running. Opening $url" -ForegroundColor Green
        Start-Process $url
    }
    exit 0
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (first run)..."
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -c "import fastapi, uvicorn, httpx, jwt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..."
    & .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
}

$env:PYTHONPATH = "."
Write-Host ""
Write-Host "Chatbox:  $url" -ForegroundColor Green
Write-Host "API docs: $url/docs"
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

Open-Chatbox -Target $url

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port $Port
