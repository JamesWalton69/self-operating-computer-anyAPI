@echo off
setlocal
cd /d "%~dp0"

echo ====================================================
echo   Starting Self-Operating Computer Studio GUI
echo ====================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv
    echo Please ensure the virtualenv is installed.
    pause
    exit /b 1
)

set PYTHONPATH=%CD%
echo Using Python: %CD%\.venv\Scripts\python.exe
echo.
"%CD%\.venv\Scripts\python.exe" -m operate --gui %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTICE] Studio exited with code %ERRORLEVEL%.
    pause
)
