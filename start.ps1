$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) {
    $Root = (Get-Location).Path
}

Write-Host "backend: uvicorn (http://127.0.0.1:8000)"
Push-Location (Join-Path $Root "backend")
try {
    uv run uvicorn server.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
