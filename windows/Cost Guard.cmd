@echo off
setlocal
set "CG_ROOT=%~dp0.."
call :detect_python
if errorlevel 1 goto :python_error
start "Cost Guard" powershell.exe -NoProfile -NoExit -Command "& %CG_RUN% '%CG_ROOT%\cost-guard.py'"
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
