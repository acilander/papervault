#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Stop-ProcessOnPort($port) {
    $proc = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess
    if ($proc) {
        Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue | Out-Null
    }
}

function Stop-ProcessTree($id) {
    taskkill /F /T /PID $id 2>$null | Out-Null
}

# Stop any leftover processes
Write-Host "[Frontend] Beende ggf. alten Prozess auf Port 5173..."
Stop-ProcessOnPort 5173

Write-Host "[API]      Beende ggf. alten Prozess auf Port 8000..."
Stop-ProcessOnPort 8000

# Start frontend
Write-Host "[Frontend] Starte Frontend auf Port 5173..."
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d `"$root\frontend`" && npm run dev" `
    -NoNewWindow -PassThru

# Start backend
Write-Host "[API]      Starte API auf Port 8000..."
$backend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d `"$root\backend`" && `"$root\.venv\Scripts\python.exe`" -m uvicorn api.main:app --host 0.0.0.0 --port 8000" `
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

# Store PIDs for the Ctrl+C handler
$script:frontendPid = $frontend.Id
$script:backendPid = $backend.Id

# Handle Ctrl+C
$script:cancelHandler = {
    param($sender, $e)
    Write-Host "`nBeende PaperVault..."
    $e.Cancel = $true
    Stop-ProcessTree $script:frontendPid
    Stop-ProcessTree $script:backendPid
    Stop-ProcessOnPort 5173
    Stop-ProcessOnPort 8000
    [Environment]::Exit(0)
}
[Console]::add_CancelKeyPress($script:cancelHandler)

# Wait for either process to exit
$frontend.WaitForExit()
$backend.WaitForExit()
