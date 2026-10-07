@echo off
rem Reuse this console; retire cmd before the persistent PowerShell runs Python.
start "Cost Guard" /b powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\src\windows_launcher.ps1" -Mode report
exit /b 0
