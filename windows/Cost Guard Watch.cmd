@echo off
<nul set /p "=Cost Guard: Checking requirements..."
set "COST_GUARD_LAUNCHER_STATUS=pending"
rem Reuse this console; retire cmd before the persistent PowerShell runs Python.
rem Prefer PowerShell 7 when installed; Windows PowerShell remains supported.
where pwsh.exe >nul 2>nul
if %errorlevel% equ 0 (set "costguard_shell=pwsh.exe") else (set "costguard_shell=powershell.exe")
start "Cost Guard Watch" /b %costguard_shell% -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\src\windows_launcher.ps1" -Mode watch
exit /b 0
