@echo off
rem Stop the ASAPA server (port 8000).
setlocal
set "PORT=8000"
echo Stopping ASAPA (port %PORT%)...
set "FOUND="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo   Killing PID %%P
    taskkill /PID %%P /F >nul 2>&1
    set "FOUND=1"
)
if not defined FOUND echo   No server process found on port 8000.
endlocal