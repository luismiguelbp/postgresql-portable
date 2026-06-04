@echo off
call "%~dp0_postgresql_portable.bat" create-winccoa
exit /b %ERRORLEVEL%
