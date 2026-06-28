@echo off
title PaperVault - Start
cd /d "%~dp0"

:: Check if API (port 8000) is already running
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [API]      Port 8000 bereits belegt - ueberspringe API-Start.
    set API_RUNNING=1
) else (
    echo [API]      Starte API auf Port 8000...
    start "PaperVault API" /B .venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
    set API_RUNNING=0
)

:: Check if Frontend (port 5173) is already running
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [Frontend] Port 5173 bereits belegt - ueberspringe Frontend-Start.
    set FE_RUNNING=1
) else (
    echo [Frontend] Starte Frontend auf Port 5173...
    if %API_RUNNING%==0 timeout /t 2 /nobreak >nul
    start "PaperVault Frontend" /B cmd /c "cd frontend && npm run dev"
    set FE_RUNNING=0
)

echo.
echo API:      http://localhost:8000
echo Frontend: http://localhost:5173
echo.
start http://localhost:5173
exit
