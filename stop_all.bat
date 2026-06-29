@echo off
title PaperVault Stopper
echo =========================================
echo Stopping PaperVault Services...
echo =========================================

powershell -NoProfile -Command "^
    $stopped = 0; ^
    echo '[-] Suchen nach Python Backend-Prozessen (uvicorn)...'; ^
    $pythonProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'uvicorn api.main:app' }; ^
    if ($pythonProcs) { ^
        foreach ($p in $pythonProcs) { ^
            echo \"    - Beende Backend (PID: $($p.ProcessId))\"; ^
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; ^
            $stopped++; ^
        } ^
    } else { echo '    (Kein Backend gefunden)' }; ^
    ^
    echo '[-] Suchen nach Frontend-Prozessen (node/vite)...'; ^
    $nodeProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'node' -and $_.CommandLine -match 'vite' }; ^
    if ($nodeProcs) { ^
        foreach ($p in $nodeProcs) { ^
            echo \"    - Beende Frontend (PID: $($p.ProcessId))\"; ^
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; ^
            $stopped++; ^
        } ^
    } else { echo '    (Kein Frontend gefunden)' }; ^
    ^
    echo '[-] Schließe Konsolen-Fenster...'; ^
    $cmdProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'cmd' -and $_.CommandLine -match 'PaperVault' }; ^
    if ($cmdProcs) { ^
        foreach ($p in $cmdProcs) { ^
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; ^
            $stopped++; ^
        } ^
    }; ^
    echo \"\"; ^
    echo \"Erfolgreich $stopped Prozess(e) beendet.\"; ^
"

echo =========================================
echo PaperVault wurde vollstaendig gestoppt.
echo =========================================
timeout /t 3 >nul
