@echo off
rem Reuse this console; retire cmd before the persistent PowerShell runs Python.
start "Cost Guard Diagnostics" /b powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\..\src\windows_launcher.ps1" -Mode diagnostics
exit /b 0
