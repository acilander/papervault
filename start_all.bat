@echo off
title Dokumentenarchiv - Start
cd /d "%~dp0"

:: Check if API (port 8000) is already running
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [API]      Port 8000 bereits belegt - ueberspringe API-Start.
    set API_RUNNING=1
) else (
    echo [API]      Starte API auf Port 8000...
    start "Dokumentenarchiv API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
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
    start "Dokumentenarchiv Frontend" cmd /k "cd frontend && npm run dev"
    set FE_RUNNING=0
)

echo.
echo API:      http://localhost:8000
echo Frontend: http://localhost:5173
echo Docs:     http://localhost:8000/docs
echo.
timeout /t 3 /nobreak >nul
start http://localhost:5173
