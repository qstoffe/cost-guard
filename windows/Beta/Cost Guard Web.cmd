@echo off
setlocal
echo Cost Guard Web Beta: Checking Python and Windows tray support...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\src\web\windows_launch.ps1"
exit /b %errorlevel%
