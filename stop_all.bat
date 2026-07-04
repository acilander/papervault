@echo off
title PaperVault Stopper
echo =========================================
echo Stopping PaperVault Services...
echo =========================================

powershell -NoProfile -Command "$papervault = 'papervault'; $stopped = 0; $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn api.main' -or $_.CommandLine -match 'archiver' -or ($_.Name -match 'node' -and $_.CommandLine -match 'vite') -or ($_.Name -match 'python' -and $_.CommandLine -match 'papervault') }; foreach ($p in $procs) { Write-Host \"Beende PID $($p.ProcessId): $($p.Name)\"; Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; $stopped++ }; Write-Host \"$stopped Prozess(e) beendet.\""

echo =========================================
echo PaperVault wurde vollstaendig gestoppt.
echo =========================================
echo Dieses Fenster schliesst sich in 3 Sekunden...
timeout /t 3 >nul
