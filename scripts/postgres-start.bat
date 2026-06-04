@echo off
call "%~dp0_postgresql_portable.bat" start
exit /b %ERRORLEVEL%
