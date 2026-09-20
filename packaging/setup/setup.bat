@echo off
setlocal
title ASAPA - Setup
echo ============================================================
echo   ASAPA - Industrial Automation Training Platform - Offline Setup
echo ============================================================
echo.
set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup.ps1" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================================
if "%EXITCODE%"=="0" (
  echo   Setup completed. Look for "ASAPA" on your
  echo   Desktop / Start Menu to launch the server.
) else (
  echo   Setup finished with warnings or errors (exit %EXITCODE%).
  echo   Scroll up for details.
)
echo ============================================================
echo.
pause
exit /b %EXITCODE%