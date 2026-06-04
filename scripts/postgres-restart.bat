@echo off
call "%~dp0_postgresql_portable.bat" restart
exit /b %ERRORLEVEL%
