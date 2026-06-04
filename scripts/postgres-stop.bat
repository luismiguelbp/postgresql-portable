@echo off
call "%~dp0_postgresql_portable.bat" stop
exit /b %ERRORLEVEL%
