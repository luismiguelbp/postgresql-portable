@echo off
call "%~dp0_postgresql_portable.bat" info
exit /b %ERRORLEVEL%
