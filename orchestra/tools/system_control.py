"""
OrchestraAI — System Control Tools
====================================
Windows system-level controls: volume, brightness, lock screen,
screenshots, and system information.
"""

import os
import ctypes
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from ..config import settings

logger = logging.getLogger("orchestra.system_control")


def set_volume(level: int) -> Dict[str, Any]:
    """
    Set system volume level (0-100).
    Uses pycaw for precise Windows audio control.
    """
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # pycaw uses scalar 0.0-1.0
        scalar = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)

        return {
            "success": True,
            "action": "set_volume",
            "level": level,
            "details": f"System volume set to {level}%.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to set volume: {e}"}


def get_volume() -> Dict[str, Any]:
    """Get current system volume level."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        current = volume.GetMasterVolumeLevelScalar()
        level = int(current * 100)

        return {"success": True, "level": level, "details": f"Current volume: {level}%"}
    except Exception as e:
        return {"success": False, "error": f"Failed to get volume: {e}"}


def set_brightness(level: int) -> Dict[str, Any]:
    """
    Set screen brightness (0-100).
    Uses screen_brightness_control library.
    """
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return {
            "success": True,
            "action": "set_brightness",
            "level": level,
            "details": f"Screen brightness set to {level}%.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to set brightness: {e}"}


def get_brightness() -> Dict[str, Any]:
    """Get current screen brightness."""
    try:
        import screen_brightness_control as sbc
        level = sbc.get_brightness()
        if isinstance(level, list):
            level = level[0]
        return {"success": True, "level": level, "details": f"Current brightness: {level}%"}
    except Exception as e:
        return {"success": False, "error": f"Failed to get brightness: {e}"}


def lock_screen() -> Dict[str, Any]:
    """Lock the Windows workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return {
            "success": True,
            "action": "lock_screen",
            "details": "Workstation locked.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to lock screen: {e}"}


def take_screenshot(save_dir: str = None) -> Dict[str, Any]:
    """
    Take a screenshot and save it to disk.
    
    Args:
        save_dir: Directory to save the screenshot. Defaults to output/images/.
    """
    try:
        from PIL import ImageGrab

        if save_dir is None:
            save_dir = str(settings.output_images_dir)
        
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = Path(save_dir) / filename

        img = ImageGrab.grab()
        img.save(str(filepath))

        return {
            "success": True,
            "action": "screenshot",
            "path": str(filepath),
            "details": f"Screenshot saved: {filepath}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to take screenshot: {e}"}


def get_system_info() -> Dict[str, Any]:
    """Get basic system information (CPU, RAM, battery)."""
    info = {}
    try:
        import platform
        info["os"] = f"{platform.system()} {platform.release()}"
        info["machine"] = platform.machine()
        info["processor"] = platform.processor()
    except Exception:
        pass

    # Battery info
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject Win32_Battery).EstimatedChargeRemaining"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            info["battery_percent"] = int(result.stdout.strip())
    except Exception:
        pass

    # Uptime
    try:
        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
        uptime_hours = uptime_ms / (1000 * 60 * 60)
        info["uptime_hours"] = round(uptime_hours, 1)
    except Exception:
        pass

    return {
        "success": True,
        "action": "system_info",
        "info": info,
        "details": f"OS: {info.get('os', 'N/A')}, Battery: {info.get('battery_percent', 'N/A')}%",
    }
