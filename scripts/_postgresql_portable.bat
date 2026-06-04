@echo off
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Virtual environment not found at .venv
    echo Run scripts\pg-setup.bat or:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e .
    exit /b 1
)

"%PY%" -m postgresql_portable %*
exit /b %ERRORLEVEL%
