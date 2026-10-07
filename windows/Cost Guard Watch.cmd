@echo off
setlocal
set "CG_ROOT=%~dp0.."
call :detect_python
if errorlevel 1 goto :python_error
rem Run Watch as a direct Python child of PowerShell, then let this batch file
rem exit immediately. Ctrl-C therefore stops Cost Guard without cmd.exe asking
rem "Terminate batch job (Y/N)?". A clean stop (exit code 0) closes the window;
rem a non-zero exit keeps Cost Guard's own error visible until Enter is pressed.
start "Cost Guard Watch" powershell.exe -NoProfile -Command "& %CG_RUN% '%CG_ROOT%\cost-guard.py' --watch; $code = $LASTEXITCODE; if ($code) { Write-Host ''; Write-Host ('Cost Guard Watch exited unexpectedly (code ' + $code + ').'); Read-Host 'Press Enter to close' | Out-Null; exit $code }"
exit /b 0

:detect_python
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 set "CG_RUN=py -3"& exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
  if not errorlevel 1 set "CG_RUN=python"& exit /b 0
)
exit /b 1

:python_error
echo.
echo Cost Guard could not find Python 3.11 or newer.
echo Install Python 3.11+ and run this launcher again.
echo.
pause
exit /b 9009
