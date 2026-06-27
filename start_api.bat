@echo off
title Dokumentenarchiv API
cd /d "%~dp0"
echo Starte FastAPI Server auf http://localhost:8000 ...
echo Swagger-Docs: http://localhost:8000/docs
echo.
.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
pause
