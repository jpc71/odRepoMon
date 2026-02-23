@echo off
setlocal
set "INSTALL_ROOT=%LOCALAPPDATA%\odRepoMon"
set "LAUNCHER=%INSTALL_ROOT%\Launch-odRepoMon-Agent.cmd"

if not exist "%LAUNCHER%" (
  echo odRepoMon user install not found.
  echo Run scripts\windows\install-user.cmd first.
  exit /b 1
)

call "%LAUNCHER%"
exit /b %errorlevel%