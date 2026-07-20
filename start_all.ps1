#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Stop-ProcessOnPort($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $id = $conn.OwningProcess
        if ($id) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue | Out-Null
        }
    }
}

function Stop-ProcessTree($id) {
    if ($id) {
        taskkill /F /T /PID $id 2>$null | Out-Null
    }
}

# Stop any leftover processes
Write-Host "[Frontend] Beende ggf. alten Prozess auf Port 5173..."
Stop-ProcessOnPort 5173

Write-Host "[API]      Beende ggf. alten Prozess auf Port 8000..."
Stop-ProcessOnPort 8000

# Start frontend
Write-Host "[Frontend] Starte Frontend auf Port 5173..."
$frontend = Start-Process -FilePath "node" `
    -ArgumentList "node_modules/vite/bin/vite.js" `
    -WorkingDirectory "$root\frontend" `
    -NoNewWindow -PassThru

# Start backend
Write-Host "[API]      Starte API auf Port 8000..."
$backend = Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn api.main:app --host 0.0.0.0 --port 8000" `
    -WorkingDirectory "$root\backend" `
    -NoNewWindow -PassThru

# Wait for API
$tries = 0
$apiReady = $false
while ($tries -lt 15) {
    Start-Sleep -Seconds 1
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $apiReady = $true
        break
    }
    $tries++
}

if (-not $apiReady) {
    Write-Host "[API]      Timeout."
    Stop-ProcessTree $frontend.Id
    Stop-ProcessTree $backend.Id
    exit 1
}

Write-Host "[API]      Bereit."
Write-Host ""
Start-Process "http://localhost:5173"
Write-Host "Fenster offen lassen fuer Logs. Strg+C zum Beenden."
Write-Host ""

# Store PIDs for cleanup
$frontendPid = $frontend.Id
$backendPid = $backend.Id

function Stop-All($frontendPid, $backendPid) {
    Stop-ProcessTree $frontendPid
    Stop-ProcessTree $backendPid
    Stop-ProcessOnPort 5173
    Stop-ProcessOnPort 8000
}

# Keep the script running. Ctrl+C raises an exception and the finally block cleans up.
try {
    while (-not ($frontend.HasExited -and $backend.HasExited)) {
        Start-Sleep -Milliseconds 200
    }
}
finally {
    Stop-All $frontendPid $backendPid
}
