@echo off
title Push DARKI to GitHub
echo ============================================================
echo   Pushing DARKI to GitHub (Suyashtiwari-7/OrchestraAI)
echo ============================================================
echo.

set "GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=git"

echo [*] Staging and verifying commit...
"%GIT_EXE%" add .
"%GIT_EXE%" commit -m "feat: add standalone desktop build, 1-click release workflow, and updated README" 2>nul
"%GIT_EXE%" branch -M main

echo.
echo [*] Pushing to GitHub (A browser login window will open if not already signed in)...
echo.
"%GIT_EXE%" push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   [+] SUCCESS! Code is now pushed to your GitHub repository!
    echo ============================================================
) else (
    echo.
    echo [!] Push failed or cancelled. Check the message above.
)
echo.
pause
