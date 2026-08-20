"""
DARKI AI — Global Hotkey Daemon (Low-Level Keyboard Hook)
==========================================================
Listens for:
  - Ctrl + 0 (Top Row 0)
  - Ctrl + Alt + 0
  - Ctrl + Numpad 0

Launches DARKI immediately or brings it to the front if already running.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
import keyboard

PROJECT_ROOT = Path(r"c:\Users\suyas\Documents\CODE\OrchestraAI-main\OrchestraAI-main")
RUN_SCRIPT = PROJECT_ROOT / "run_darki.py"
PYTHONW = PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable).parent / "pythonw.exe"

_last_trigger_time = 0.0

def is_darki_running() -> bool:
    try:
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            try:
                cmd = p.info['cmdline']
                if cmd and any('run_darki' in str(arg) or 'darki_widget' in str(arg) for arg in cmd):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False

def on_hotkey():
    global _last_trigger_time
    now = time.time()
    # Debounce 1.0 second to prevent double triggers
    if now - _last_trigger_time < 1.0:
        return
    _last_trigger_time = now

    try:
        # Always launch or ensure running
        subprocess.Popen(
            [str(PYTHONW), str(RUN_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        bat = PROJECT_ROOT / "run_darki.bat"
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat)],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW
        )

def main():
    # Register all variants
    hotkeys = ["ctrl+0", "ctrl+alt+0", "ctrl+num 0", "ctrl+numpad0", "ctrl+shift+0"]
    for hk in hotkeys:
        try:
            keyboard.add_hotkey(hk, on_hotkey, suppress=False)
        except Exception:
            pass

    # Keep daemon running silently in background
    keyboard.wait()

if __name__ == "__main__":
    main()
