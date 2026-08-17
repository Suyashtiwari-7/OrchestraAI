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


def set_power_mode(mode: str) -> Dict[str, Any]:
    """
    Set Windows power plan and battery saver threshold.
    Supported modes: 'saver', 'balanced', 'high'
    """
    import subprocess
    import psutil
    
    # Standard Windows Power Scheme GUIDs
    schemes = {
        "saver": "a1841308-3541-4fab-bc81-f71556f20b4a",     # Power saver
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",  # Balanced
        "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"       # High performance
    }
    
    target_mode = mode.lower()
    if target_mode not in schemes:
        return {"success": False, "error": f"Unknown power mode: {mode}. Use saver, balanced, or high."}
        
    guid = schemes[target_mode]
    try:
        # 1. Set the Power Plan
        subprocess.run(f"powercfg /setactive {guid}", shell=True, capture_output=True)
        
        # 2. Adjust modern Windows 11 Energy Saver threshold (SUB_ENERGYSAVER ESBATTTHRESHOLD)
        if target_mode == "saver":
            # Set threshold to 100% so it activates immediately on battery
            subprocess.run("powercfg /setdcvalueindex SCHEME_CURRENT SUB_ENERGYSAVER ESBATTTHRESHOLD 100", shell=True, capture_output=True)
            subprocess.run("powercfg /setacvalueindex SCHEME_CURRENT SUB_ENERGYSAVER ESBATTTHRESHOLD 100", shell=True, capture_output=True)
        else:
            # Restore default 20% threshold
            subprocess.run("powercfg /setdcvalueindex SCHEME_CURRENT SUB_ENERGYSAVER ESBATTTHRESHOLD 20", shell=True, capture_output=True)
            subprocess.run("powercfg /setacvalueindex SCHEME_CURRENT SUB_ENERGYSAVER ESBATTTHRESHOLD 0", shell=True, capture_output=True)
            
        # Apply the threshold changes
        subprocess.run("powercfg /setactive SCHEME_CURRENT", shell=True, capture_output=True)
        
        details_msg = f"Power mode set to '{target_mode}'."
        
        # 3. Check if plugged in (Windows disables battery saver on AC power)
        if target_mode == "saver":
            battery = psutil.sensors_battery()
            if battery and battery.power_plugged:
                details_msg += " (Note: Windows restricts the 'Energy Saver' toggle while the PC is plugged into a charger. It will activate automatically when unplugged.)"

        return {
            "success": True,
            "action": "system_power_mode",
            "mode": target_mode,
            "details": details_msg
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to set power mode: {e}"}


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


# ============================================
# Active Window Context — "What am I looking at?"
# ============================================

def get_active_window_details() -> Dict[str, Any]:
    """
    Get the currently focused window's title and owning process name.
    Uses win32gui/win32process for accurate results on Windows.
    """
    try:
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        window_title = win32gui.GetWindowText(hwnd)

        # Get the process ID that owns this window
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        process_name = "Unknown"
        try:
            import psutil
            proc = psutil.Process(pid)
            process_name = proc.name()
        except Exception:
            pass

        return {
            "success": True,
            "window_title": window_title,
            "process_name": process_name,
            "pid": pid,
            "details": f"Active window: '{window_title}' ({process_name})",
        }
    except ImportError:
        # Fallback if pywin32 is not installed — use ctypes
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

            return {
                "success": True,
                "window_title": title,
                "process_name": "Unknown (pywin32 not installed)",
                "pid": 0,
                "details": f"Active window: '{title}'",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get active window: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to get active window: {e}"}


# ============================================
# Clipboard Helpers — Read/Write clipboard
# ============================================

def clipboard_get() -> Dict[str, Any]:
    """Read current text content from the system clipboard."""
    try:
        import pyperclip
        content = pyperclip.paste()
        return {
            "success": True,
            "content": content,
            "length": len(content) if content else 0,
            "details": f"Clipboard contains {len(content)} characters." if content else "Clipboard is empty.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to read clipboard: {e}"}


def clipboard_set(text: str) -> Dict[str, Any]:
    """Write text content to the system clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return {
            "success": True,
            "length": len(text),
            "details": f"Copied {len(text)} characters to clipboard.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to write to clipboard: {e}"}


# ============================================
# Live Telemetry — CPU, RAM, Disk, Battery
# ============================================

def get_live_telemetry() -> Dict[str, Any]:
    """
    Get real-time hardware diagnostics: CPU usage, RAM, disk, battery, and top processes.
    Uses psutil for accurate cross-platform metrics.
    """
    telemetry = {}
    try:
        import psutil

        # CPU
        telemetry["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        telemetry["cpu_count"] = psutil.cpu_count()
        telemetry["cpu_freq_mhz"] = round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else None

        # Memory
        mem = psutil.virtual_memory()
        telemetry["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)
        telemetry["ram_used_gb"] = round(mem.used / (1024 ** 3), 1)
        telemetry["ram_percent"] = mem.percent

        # Disk (primary drive)
        disk = psutil.disk_usage("C:\\")
        telemetry["disk_total_gb"] = round(disk.total / (1024 ** 3), 1)
        telemetry["disk_used_gb"] = round(disk.used / (1024 ** 3), 1)
        telemetry["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
        telemetry["disk_percent"] = disk.percent

        # Battery
        battery = psutil.sensors_battery()
        if battery:
            telemetry["battery_percent"] = battery.percent
            telemetry["battery_plugged"] = battery.power_plugged
            secs = battery.secsleft
            if secs > 0 and secs != psutil.POWER_TIME_UNLIMITED:
                telemetry["battery_time_left_min"] = round(secs / 60, 0)
        else:
            telemetry["battery_percent"] = None
            telemetry["battery_plugged"] = None

        # Top 5 processes by memory usage
        procs = []
        for proc in psutil.process_iter(["name", "memory_percent"]):
            try:
                info = proc.info
                if info["memory_percent"] and info["memory_percent"] > 0.5:
                    procs.append({"name": info["name"], "mem_pct": round(info["memory_percent"], 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x["mem_pct"], reverse=True)
        telemetry["top_processes"] = procs[:5]

        # Summary string
        bat_str = f"{telemetry.get('battery_percent', 'N/A')}%"
        if telemetry.get("battery_plugged"):
            bat_str += " (charging)"
        telemetry["summary"] = (
            f"CPU: {telemetry['cpu_percent']}% | "
            f"RAM: {telemetry['ram_used_gb']}/{telemetry['ram_total_gb']} GB ({telemetry['ram_percent']}%) | "
            f"Disk: {telemetry['disk_free_gb']} GB free | "
            f"Battery: {bat_str}"
        )

        return {"success": True, "telemetry": telemetry, "details": telemetry["summary"]}

    except ImportError:
        return {"success": False, "error": "psutil not installed. Run: pip install psutil"}
    except Exception as e:
        return {"success": False, "error": f"Failed to get telemetry: {e}"}
