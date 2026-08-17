"""
OrchestraAI — Windows Auto-Start Registration
=================================================
Manages auto-start on Windows login by adding/removing a shortcut
in the user's Startup folder.
"""

import sys
import logging
from pathlib import Path

logger = logging.getLogger("orchestra.autostart")

STARTUP_FOLDER = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_NAME = "OrchestraAI DARKI.lnk"


def is_autostart_enabled() -> bool:
    """Check if DARKI is set to auto-start with Windows."""
    shortcut_path = STARTUP_FOLDER / SHORTCUT_NAME
    return shortcut_path.exists()


def enable_autostart() -> dict:
    """Add DARKI to Windows startup."""
    try:
        import win32com.client

        shortcut_path = STARTUP_FOLDER / SHORTCUT_NAME

        # Determine the target script
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            target = sys.executable
            arguments = ""
        else:
            # Running from source
            target = sys.executable  # python.exe
            script = Path(__file__).resolve().parent / "darki_main.py"
            arguments = f'"{script}"'

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(target)
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = str(Path(target).parent)
        shortcut.Description = "OrchestraAI DARKI Desktop Assistant"
        shortcut.save()

        logger.info(f"Auto-start enabled: {shortcut_path}")
        return {
            "success": True,
            "action": "enable_autostart",
            "details": "DARKI will now start automatically when you log in.",
        }
    except Exception as e:
        logger.error(f"Failed to enable auto-start: {e}")
        return {"success": False, "error": f"Failed to enable auto-start: {e}"}


def disable_autostart() -> dict:
    """Remove DARKI from Windows startup."""
    try:
        shortcut_path = STARTUP_FOLDER / SHORTCUT_NAME
        if shortcut_path.exists():
            shortcut_path.unlink()
            logger.info("Auto-start disabled.")
            return {
                "success": True,
                "action": "disable_autostart",
                "details": "DARKI will no longer start automatically.",
            }
        else:
            return {
                "success": True,
                "action": "disable_autostart",
                "details": "Auto-start was already disabled.",
            }
    except Exception as e:
        return {"success": False, "error": f"Failed to disable auto-start: {e}"}
