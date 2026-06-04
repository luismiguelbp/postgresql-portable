@echo off
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
set "PIP=%ROOT%\.venv\Scripts\pip.exe"

if exist "%PY%" (
    echo Using existing virtual environment: .venv
) else (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create .venv. Is Python installed?
        exit /b 1
    )
)

if not exist "%PY%" (
    echo .venv was not created correctly. Missing: %PY%
    exit /b 1
)

echo Installing package...
"%PY%" -m pip install -e .
if errorlevel 1 exit /b 1

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo Created .env from .env.example
    ) else (
        echo Warning: .env.example not found. Create .env manually.
    )
)

echo.
echo Setup complete. Run scripts\pg-info.bat to verify paths.
exit /b 0
