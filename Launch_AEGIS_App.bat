@echo off
title AEGIS AI Meeting Agent
cd /d "%~dp0"

echo ===================================================
echo     PROJECT A.E.G.I.S. // AI MEETING AGENT
echo ===================================================
echo.
echo [1/3] Checking Agent Server status...

:: Check if port 8000 is already active
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo [OK] AEGIS Server is already running.
) else (
    echo [STARTING] Launching AEGIS Server on port 8000...
    start /b python -m uvicorn backend.agent_server:app --host 127.0.0.1 --port 8000 >nul 2>&1
    timeout /t 3 /nobreak >nul
)

echo [2/3] Verifying server connection...
powershell -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/status' -UseBasicParsing -TimeoutSec 3).StatusCode } catch { 'waiting' }" >nul

echo [3/3] Opening AEGIS Native Desktop Application...

:: Check for Google Chrome application mode
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:8000" --window-size=1400,900
    exit /b
)

:: Check for Microsoft Edge application mode
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8000" --window-size=1400,900
    exit /b
)

:: Fallback to default browser
start http://127.0.0.1:8000
exit /b
