@echo off
call "%~dp0_postgresql_portable.bat" status
exit /b %ERRORLEVEL%
