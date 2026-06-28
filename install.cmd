@echo off
:: Testing Toolkit - Windows Installer & Launcher
:: Double-click this file. That's it.
:: Installs packages, builds the .exe, and launches it.

setlocal
cd /d "%~dp0"

set "EMBED=%~dp0python-embed"
set "SRC=%~dp0src"
set "WH=%SRC%\wheelhouse"
set "REQ=%SRC%\requirements.txt"
set "PYTHON=%EMBED%\python.exe"
set "PTH=%EMBED%\python312._pth"
set "DIST=%SRC%\dist\TestingToolkit"
set "EXE=%DIST%\TestingToolkit.exe"

:: --- Verify embedded Python ---
if not exist "%PYTHON%" (
    echo [ERROR] python-embed\python.exe not found.
    echo         On a connected machine run: cd src ^& python make_portable.py
    pause
    exit /b 1
)

:: --- Always write correct ._pth ---
>"%PTH%" (
    echo python312.zip
    echo .
    echo ..\src
    echo Lib\site-packages
    echo import site
)
if not exist "%EMBED%\Lib\site-packages" mkdir "%EMBED%\Lib\site-packages"

echo.
echo ============================================
echo  Testing Toolkit - Install ^& Build
echo ============================================
echo.

:: --- Clean old builds and bytecode ---
echo [INFO] Cleaning old builds...
if exist "%SRC%\build" rmdir /s /q "%SRC%\build"
if exist "%SRC%\dist" rmdir /s /q "%SRC%\dist"
for /d /r "%SRC%" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d" >nul 2>&1
echo [OK] Clean done.

:: --- Ensure pip is available ---
"%PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing pip...
    if exist "%EMBED%\get-pip.py" (
        "%PYTHON%" "%EMBED%\get-pip.py" --no-index --find-links "%WH%" --no-warn-script-location
        if errorlevel 1 "%PYTHON%" "%EMBED%\get-pip.py" --no-warn-script-location
    ) else (
        echo [ERROR] get-pip.py not found and pip not installed.
        pause
        exit /b 1
    )
)

:: --- Install all packages (app deps + PyInstaller) ---
echo [INFO] Installing packages from wheelhouse...
"%PYTHON%" -m pip install --no-index --find-links "%WH%" --no-warn-script-location -r "%REQ%" --quiet
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)
echo [INFO] Installing PyInstaller...
"%PYTHON%" -m pip install --no-index --find-links "%WH%" --no-warn-script-location pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] PyInstaller installation failed.
    pause
    exit /b 1
)
echo [OK] All packages installed.

:: --- Build the .exe ---
echo.
"%PYTHON%" "%SRC%\build.py" --quiet
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)

:: --- Create distributable zip ---
if exist "%DIST%" (
    echo [INFO] Creating TestingToolkit.zip...
    powershell -NoProfile -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%SRC%\dist\TestingToolkit.zip' -Force"
    if errorlevel 1 (
        echo [WARN] Zip creation failed. Continuing anyway.
    ) else (
        echo [OK] TestingToolkit.zip created in dist folder.
    )
)

:: --- Launch the built app ---
if exist "%EXE%" (
    echo.
    echo [SUCCESS] Build complete. Launching...
    start "" "%EXE%"
) else (
    echo [ERROR] Expected exe not found at: %EXE%
    echo         Check build output above.
    pause
    exit /b 1
)
