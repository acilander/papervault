@echo off
echo Stopping PaperVault...

:: Kill entire process tree on port 8000 (uvicorn + reloader)
:kill8000
powershell -NoProfile -Command "$p=(Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue).OwningProcess; if($p){taskkill /PID $p /F /T 2>$null}"
powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue){exit 1}else{exit 0}" && goto kill8000done || (timeout /t 1 /nobreak >nul && goto kill8000)
:kill8000done

:: Kill entire process tree on port 5173 (vite)
:kill5173
powershell -NoProfile -Command "$p=(Get-NetTCPConnection -LocalPort 5173 -State Listen -EA SilentlyContinue).OwningProcess; if($p){taskkill /PID $p /F /T 2>$null}"
powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 5173 -State Listen -EA SilentlyContinue){exit 1}else{exit 0}" && goto kill5173done || (timeout /t 1 /nobreak >nul && goto kill5173)
:kill5173done

echo Done - all PaperVault processes stopped.
timeout /t 2 >nul
