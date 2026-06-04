@echo off
REM Drops WinCC OA DB from .env. Requires confirmation:
REM   scripts\winccoa-drop.bat --yes
REM or WINCCOA_CONFIRM=yes in .env
call "%~dp0_postgresql_portable.bat" drop-winccoa %*
exit /b %ERRORLEVEL%
