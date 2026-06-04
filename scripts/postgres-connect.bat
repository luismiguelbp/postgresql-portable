@echo off
call "%~dp0_postgresql_portable.bat" connect %*
exit /b %ERRORLEVEL%
