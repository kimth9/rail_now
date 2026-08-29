@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
REM ==== Team standard run.bat - run entry point (auto port bypass, guide section 11) ====
REM Frontend(vite)는 포트 충돌 시 자체적으로 다음 포트로 넘어가므로 별도 처리 불필요.
REM Backend(express)는 그런 기능이 없어 여기서 빈 포트를 찾아 PORT/BACKEND_PORT로 넘긴다.

if not exist "node_modules" (
    echo [run] node_modules not found. Run setup.bat first.
    pause
    exit /b 1
)

set "PORT=3000"
set /a TRIES=0

:portcheck
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    set /a PORT+=1
    set /a TRIES+=1
    if !TRIES! geq 20 (
        echo [run] Ports 3000-3019 are all in use.
        pause
        exit /b 1
    )
    goto portcheck
)

set "BACKEND_PORT=%PORT%"

echo.
echo ============================================================
echo  japanese_style_timetable - backend port: %PORT%
echo  frontend URL은 아래 vite 로그(Local:)를 확인하세요.
echo ============================================================
echo  Press Ctrl+C to stop.
echo.

call npm run dev

endlocal
