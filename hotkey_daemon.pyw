"""
DARKI AI — Global Low-Level Keyboard Daemon (Universal Hook)
=============================================================
Uses Windows Low-Level Keyboard Hooks to listen globally for:
  - Ctrl + 0
  - Ctrl + Shift + D  (D for DARKI)
  - Ctrl + Shift + 0
  - Ctrl + Numpad 0
  - Alt + D

Runs 100% silently in background with zero console windows.
"""

import sys
import time
import logging
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(r"c:\Users\suyas\Documents\CODE\OrchestraAI-main\OrchestraAI-main")
RUN_SCRIPT = PROJECT_ROOT / "run_darki.py"
PYTHONW = PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable).parent / "pythonw.exe"

_last_launch_time = 0

def launch_darki():
    """Launch or focus DARKI seamlessly with debounce protection."""
    global _last_launch_time
    now = time.time()
    if now - _last_launch_time < 1.5:
        return  # Debounce: avoid double launches within 1.5s
    _last_launch_time = now

    try:
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
    except Exception:
        pass

def main():
    import keyboard

    # Register global hotkeys
    hotkeys = [
        "ctrl+0",
        "ctrl+num 0",
        "ctrl+shift+d",
        "ctrl+shift+0",
        "alt+d",
    ]

    for hk in hotkeys:
        try:
            keyboard.add_hotkey(hk, launch_darki, suppress=False)
        except Exception:
            pass

    # Block indefinitely in background
    keyboard.wait()

if __name__ == "__main__":
    main()
