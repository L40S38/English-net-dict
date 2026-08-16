$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) {
    $Root = (Get-Location).Path
}

$FrontendHost = if ($env:FRONTEND_HOST) { $env:FRONTEND_HOST } else { "127.0.0.1" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }
$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }

Write-Host "frontend: vite preview (http://${FrontendHost}:${FrontendPort})"
$FrontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npx vite preview --host $FrontendHost --port $FrontendPort --strictPort" `
    -WorkingDirectory (Join-Path $Root "frontend") `
    -NoNewWindow -PassThru

try {
    Write-Host "backend: uvicorn (http://${BackendHost}:${BackendPort})"
    Push-Location (Join-Path $Root "backend")
    try {
        uv run uvicorn server.main:app --host $BackendHost --port $BackendPort
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($FrontendProcess -and -not $FrontendProcess.HasExited) {
        & taskkill /PID $FrontendProcess.Id /T /F 2>$null | Out-Null
    }
}
