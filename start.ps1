$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) {
    $Root = (Get-Location).Path
}

Write-Host "[1/4] backend: uv sync"
Push-Location (Join-Path $Root "backend")
try {
    uv sync
}
finally {
    Pop-Location
}

Write-Host "[2/4] frontend: npm ci"
Write-Host "[3/4] frontend: npm run build"
Push-Location (Join-Path $Root "frontend")
try {
    npm ci
    npm run build
}
finally {
    Pop-Location
}

Write-Host "[4/4] backend: uvicorn (http://127.0.0.1:8000)"
Push-Location (Join-Path $Root "backend")
try {
    uv run uvicorn server.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
