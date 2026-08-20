"""
DARKI AI — Dedicated Background Hotkey Daemon (Win32 API)
=========================================================
Uses native Windows Win32 RegisterHotKey to listen for:
  - Ctrl + 0 (Top Row 0)
  - Ctrl + Numpad 0
  - Ctrl + Alt + 0

Runs silently in the background with 0% CPU and zero console windows.
"""

import os
import sys
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess

# Win32 Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_0 = 0x30       # Top-row '0'
VK_NUMPAD0 = 0x60 # Numpad '0'
WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROJECT_ROOT = Path(r"c:\Users\suyas\Documents\CODE\OrchestraAI-main\OrchestraAI-main")
RUN_SCRIPT = PROJECT_ROOT / "run_darki.py"
PYTHONW = PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable).parent / "pythonw.exe"

def launch_darki():
    """Launch or focus DARKI seamlessly without opening any console window."""
    try:
        # Check if pythonw is available
        if PYTHONW.exists() and RUN_SCRIPT.exists():
            subprocess.Popen(
                [str(PYTHONW), str(RUN_SCRIPT)],
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        else:
            bat = PROJECT_ROOT / "run_darki.bat"
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat)],
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
    except Exception as e:
        pass

def main():
    # Register Hotkeys
    # ID 1: Ctrl + 0
    # ID 2: Ctrl + Num 0
    # ID 3: Ctrl + Alt + 0
    user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_NOREPEAT, VK_0)
    user32.RegisterHotKey(None, 2, MOD_CONTROL | MOD_NOREPEAT, VK_NUMPAD0)
    user32.RegisterHotKey(None, 3, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_0)
    user32.RegisterHotKey(None, 4, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_NUMPAD0)

    # Windows message loop
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            launch_darki()
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    main()
