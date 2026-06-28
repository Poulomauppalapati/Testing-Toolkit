@echo off
setlocal enabledelayedexpansion
title Testing Toolkit Agent - Installation
cd /d "%~dp0"

:: ============================================================
:: Testing Toolkit - offline installer launcher (Windows)
:: Finds a Python interpreter, then hands off to install.py,
:: which installs everything from THIS folder. No internet.
:: ============================================================

set "BUNDLE_DIR=%~dp0"
set "PYEXE="

:: 1) Prefer the portable Python bundled with this folder.
if exist "%BUNDLE_DIR%runtime\windows-amd64\python.exe" (
    set "PYEXE=%BUNDLE_DIR%runtime\windows-amd64\python.exe"
    goto run
)

:: 2) Fall back to a Python already on the machine.
where py >nul 2>&1 && (set "PYEXE=py -3" & goto run)
where python >nul 2>&1 && (set "PYEXE=python" & goto run)
where python3 >nul 2>&1 && (set "PYEXE=python3" & goto run)

echo [ERROR] No Python found and no bundled runtime present.
echo [ERROR] Install Python 3.9+ from the Microsoft Store, then re-run this file.
pause
exit /b 1

:run
echo [INFO] Using Python: %PYEXE%
%PYEXE% "%BUNDLE_DIR%install.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Installation failed with exit code %RC%.
    pause
)
exit /b %RC%
