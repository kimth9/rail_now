@echo off
chcp 65001 >nul
REM ==== Team standard setup.bat - create venv + install dependencies ====
REM Venv folder name is standardized as .venv (guide section 2.3).
REM To avoid OneDrive sync, change VENV_DIR below to an external path (guide section 7.1):
REM   set "VENV_DIR=%LOCALAPPDATA%\venvs\project-name"
set "VENV_DIR=.venv"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [setup] Creating venv: %VENV_DIR%
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [setup] Failed to create venv - check your Python installation.
        pause
        exit /b 1
    )
)

echo [setup] Installing dependencies: requirements.txt
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt

echo [setup] Done. Run run.bat to start.
pause
