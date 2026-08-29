@echo off
chcp 65001 >nul
REM ==== Team standard setup.bat - install dependencies ====

where node >nul 2>nul
if not %errorlevel%==0 (
    echo [setup] Node.js not found. Install Node.js 22+ first.
    pause
    exit /b 1
)

echo [setup] Installing dependencies: npm install
call npm install

echo [setup] Done. Run run.bat to start.
pause
