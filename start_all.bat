@echo off
title PaperVault
cd /d "%~dp0"

:: Start frontend first in background
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [Frontend] Port 5173 bereits belegt.
) else (
    echo [Frontend] Starte Frontend auf Port 5173...
    start "PaperVault Frontend" /B cmd /c "cd frontend && npm run dev"
)

:: Check if backend already running
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [API]      Port 8000 bereits belegt.
    echo.
    start http://localhost:5173
    echo Druecke eine Taste zum Beenden.
    pause >nul
    goto :eof
)

:: Start backend and wait until ready
echo [API]      Starte API auf Port 8000...
start "PaperVault API" /B cmd /c "cd backend && ..\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000"

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
