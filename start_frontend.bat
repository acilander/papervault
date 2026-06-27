@echo off
title Dokumentenarchiv Frontend
cd /d "%~dp0\frontend"
echo Starte React Frontend auf http://localhost:5173 ...
echo.
npm run dev
pause
