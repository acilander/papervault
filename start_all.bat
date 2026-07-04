@echo off
title PaperVault
cd /d "%~dp0"

:: Run the PowerShell launcher that handles Ctrl+C and cleanup reliably
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
