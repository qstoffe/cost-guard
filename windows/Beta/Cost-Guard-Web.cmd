@echo off
setlocal
rem Delegate before Python discovery, instance restart or browser handoff. No /wait.
start "" /min "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0..\..\src\web\windows_launch.ps1" -Detached <nul >nul 2>nul
if not errorlevel 1 exit /b 0
rem A failed process creation retains the supported, visible diagnostic path.
echo Cost Guard Web Beta: Background handoff failed; starting with visible status...
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\src\web\windows_launch.ps1"
exit /b %errorlevel%
