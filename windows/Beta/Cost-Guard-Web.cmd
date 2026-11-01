@echo off
setlocal
rem Keep this status console until verified host readiness and the browser-open request.
rem The Python lifecycle still starts a detached, tray-owned server.
echo Launching web...
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\src\web\windows_launch.ps1"
exit /b %errorlevel%
