@echo off
rem Start the Industrial Academy server (http://127.0.0.1:8000).
setlocal
cd /d "%~dp0app\backend" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)
echo.
echo   AI-Powered Industrial Academy - starting...
echo   Web UI:  http://127.0.0.1:8000
echo   Close this window (or run stop-academy) to stop the server.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal