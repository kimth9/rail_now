@echo off
chcp 65001 >nul
REM ==== Team standard run.bat - run entry point ====
REM If using an external venv, update VENV_DIR the same way as in setup.bat.
set "VENV_DIR=.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [run] Venv not found. Run setup.bat first.
    pause
    exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" main.py %*
pause
