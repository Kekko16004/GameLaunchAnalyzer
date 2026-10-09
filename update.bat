@echo off
rem game-launch-strategist - update from GitHub, then reinstall in every IDE with the last choices.
rem   update.bat              everything
rem   update.bat -Test        also run the skill's unit tests
rem   update.bat -NoSelf      no download, only reinstall      update.bat -NoInstall   download only
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
exit /b %RC%
