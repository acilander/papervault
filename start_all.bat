@echo off
title PaperVault
cd /d "%~dp0"

:: Check if Frontend (port 5173) is already running
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [Frontend] Port 5173 bereits belegt - ueberspringe Frontend-Start.
) else (
    echo [Frontend] Starte Frontend auf Port 5173...
    start "PaperVault Frontend" /B cmd /c "cd frontend && npm run dev"
    timeout /t 2 /nobreak >nul
)

:: Check if API (port 8000) is already running
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [API]      Port 8000 bereits belegt - ueberspringe API-Start.
    echo.
    echo Druecke Strg+C zum Beenden.
    pause >nul
) else (
    echo [API]      Starte API auf Port 8000...
    echo.
    start http://localhost:5173
    .venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
)
