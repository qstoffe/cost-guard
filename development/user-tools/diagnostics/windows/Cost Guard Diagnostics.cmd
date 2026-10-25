@echo off
rem Reuse this console; retire cmd before the persistent PowerShell runs Python.
rem Prefer PowerShell 7 when installed; Windows PowerShell remains supported.
where pwsh.exe >nul 2>nul
if %errorlevel% equ 0 (set "costguard_shell=pwsh.exe") else (set "costguard_shell=powershell.exe")
start "Cost Guard Diagnostics" /b %costguard_shell% -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\..\..\..\src\windows_launcher.ps1" -Mode diagnostics
exit /b 0
