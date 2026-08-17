@echo off
setlocal enabledelayedexpansion
title DARKI Installation & Setup Wizard

echo ============================================================
echo   DARKI / OrchestraAI — Automated Setup ^& Bootstrap Wizard
echo ============================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python is not installed or not added to PATH.
    echo [*] Please install Python 3.10+ from https://www.python.org/
    echo [*] Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected:
python --version

:: 2. Create Virtual Environment
if not exist "venv" (
    echo.
    echo [*] Creating virtual environment (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created.
) else (
    echo [+] Existing virtual environment found.
)

:: 3. Upgrade Pip & Install Requirements
echo.
echo [*] Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo [*] Installing all project dependencies from requirements.txt...
echo [*] (This may take 1-3 minutes depending on your internet connection)
venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] Dependency installation encountered errors.
    pause
    exit /b 1
)
echo [+] All dependencies installed successfully.

:: 4. Setup .env file
if not exist ".env" (
    if exist ".env.example" (
        echo.
        echo [*] Creating initial .env configuration from .env.example...
        copy ".env.example" ".env" >nul
        echo [+] Created .env configuration file.
    )
) else (
    echo [+] Active .env file found.
)

:: 5. Create Desktop Shortcut
echo.
echo [*] Creating Desktop Shortcut (DARKI AI)...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\"$env:USERPROFILE\Desktop\DARKI AI.lnk\"); $Shortcut.TargetPath = \"$PSScriptRoot\run_darki.bat\"; $Shortcut.WorkingDirectory = \"$PSScriptRoot\"; $Shortcut.Save(); if (Test-Path \"$env:USERPROFILE\OneDrive\Desktop\") { Copy-Item \"$env:USERPROFILE\Desktop\DARKI AI.lnk\" \"$env:USERPROFILE\OneDrive\Desktop\DARKI AI.lnk\" -Force }" >nul 2>&1
echo [+] Desktop shortcut ready!

:: 6. Verification
echo.
echo ============================================================
echo   [+] SETUP COMPLETE! DARKI IS READY TO RUN!
echo ============================================================
echo.
echo  Quick Launch Options:
echo    1. Double-click "DARKI AI" on your Desktop.
echo    2. Or double-click "run_darki.bat" in this folder.
echo.
echo  Hotkeys ^& Activation:
echo    - Press Ctrl + 0 or Ctrl + Num 0 to open chat.
echo    - Say "Hey DARKI" for hands-free voice commands.
echo.
pause
