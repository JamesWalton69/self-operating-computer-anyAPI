@echo off
setlocal
cd /d "%~dp0" 2>nul

echo ====================================================
echo   Starting Self-Operating Computer Studio GUI
echo ====================================================
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at %~dp0.venv
    echo Please ensure the virtualenv is installed.
    exit /b 1
)

set "PYTHONPATH=%~dp0;%PYTHONPATH%"
echo Using Python: %~dp0.venv\Scripts\python.exe
echo.

:: Running with stdin redirected from NUL completely prevents "Terminate batch job (Y/N)?"
call "%~dp0.venv\Scripts\python.exe" -m operate --gui %* <nul
exit /b %ERRORLEVEL%
