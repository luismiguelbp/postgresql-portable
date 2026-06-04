@echo off
call "%~dp0_postgresql_portable.bat" init
exit /b %ERRORLEVEL%
