$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) {
    $Root = (Get-Location).Path
}

Write-Host "[1/3] backend: uv sync"
Push-Location (Join-Path $Root "backend")
try {
    uv sync
}
finally {
    Pop-Location
}

Write-Host "[2/3] frontend: npm ci"
Write-Host "[3/3] frontend: npm run build"
Push-Location (Join-Path $Root "frontend")
try {
    npm ci
    npm run build
}
finally {
    Pop-Location
}

Write-Host "setup done. run ./start.ps1 to serve."
