@echo off
set "GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=git"

"%GIT_EXE%" add .
"%GIT_EXE%" commit -m "Update %date% %time%" 2>nul
"%GIT_EXE%" push origin main
echo [+] Updates pushed to GitHub!
