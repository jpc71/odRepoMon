@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-user.ps1" %*
exit /b %errorlevel%