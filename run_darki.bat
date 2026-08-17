@echo off
title DARKI Desktop AI
cd /d "%~dp0"
echo [*] Starting DARKI Desktop AI & Floating Mascot...
venv\Scripts\python.exe run_darki.py
pause
