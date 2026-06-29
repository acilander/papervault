@echo off
title PaperVault
cd /d "%~dp0"

:: Kill any leftover process on port 5173
echo [Frontend] Beende ggf. alten Prozess auf Port 5173...
powershell -NoProfile -Command "$p = (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"

:: Start frontend in background
echo [Frontend] Starte Frontend auf Port 5173...
start "PaperVault Frontend" /B cmd /c "cd /d "%~dp0frontend" && npm run dev"

:: Kill any leftover process on port 8000
echo [API]      Beende ggf. alten Prozess auf Port 8000...
powershell -NoProfile -Command "$p = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"

:: Start backend and wait until ready
echo [API]      Starte API auf Port 8000...
start "PaperVault API" /B cmd /c "cd /d "%~dp0backend" && "%~dp0.venv\Scripts\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000"

set /a tries=0
:wait_api
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto api_ready
set /a tries+=1
if %tries% lss 15 goto wait_api
echo [API]      Timeout.
goto :eof

:api_ready
echo [API]      Bereit.
echo.
start http://localhost:5173
echo Fenster offen lassen fuer Logs. Strg+C oder stop_all.bat zum Beenden.
echo.
