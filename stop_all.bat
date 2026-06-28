@echo off
echo Stopping PaperVault...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /PID %%a /F /T >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /PID %%a /F /T >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5174 " ^| findstr "LISTENING"') do taskkill /PID %%a /F /T >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5175 " ^| findstr "LISTENING"') do taskkill /PID %%a /F /T >nul 2>&1

echo Done.
taskkill /FI "WINDOWTITLE eq PaperVault" /F >nul 2>&1
exit
