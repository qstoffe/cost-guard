@echo off
rem Use a separate console: never leave two interactive shells sharing caller input.
rem Prefer PowerShell 7 when installed; Windows PowerShell remains supported.
where pwsh.exe >nul 2>nul
if %errorlevel% equ 0 (set "costguard_shell=pwsh.exe") else (set "costguard_shell=powershell.exe")
start "Cost Guard Watch" %costguard_shell% -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\src\windows_launcher.ps1" -Mode watch
exit /b %errorlevel%
