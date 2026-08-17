"""
OrchestraAI — GUI Automation Tool
=====================================
Gives DARKI direct control over the desktop: type into any app,
click anywhere on screen, press keyboard shortcuts, and focus windows.
This is the bridge that makes DARKI act like JARVIS — no limitations.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger("orchestra.gui_automation")


_last_synthetic_pos: Optional[tuple] = None


def wait_for_human_idle(idle_seconds: float = 4.5, check_interval: float = 0.5):
    """
    Checks if the user moved the mouse. If human activity is detected,
    yields control and pauses execution until the mouse is steady for `idle_seconds`.
    """
    global _last_synthetic_pos
    try:
        import pyautogui
        current_pos = pyautogui.position()

        # If user moved the mouse away from where DARKI left it
        if _last_synthetic_pos is not None and current_pos != _last_synthetic_pos:
            logger.info(f"[GUI] Human mouse movement detected at {current_pos}. Yielding control to user...")

            still_time = 0.0
            last_check_pos = current_pos

            while still_time < idle_seconds:
                time.sleep(check_interval)
                new_pos = pyautogui.position()
                if new_pos == last_check_pos:
                    still_time += check_interval
                else:
                    still_time = 0.0
                    last_check_pos = new_pos

            logger.info(f"[GUI] Mouse stationary for {idle_seconds}s. Resuming autonomous action.")

        _last_synthetic_pos = pyautogui.position()
    except Exception as e:
        logger.debug(f"[GUI] Idle check bypassed: {e}")


def focus_window(title_substring: str) -> dict:
    """Find and bring a window to the foreground by partial title match."""
    try:
        import win32gui
        import win32con

        target_hwnd = None

        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if title_substring.lower() in window_title.lower():
                    results.append(hwnd)

        results = []
        win32gui.EnumWindows(enum_callback, results)

        if results:
            target_hwnd = results[0]
            # Restore if minimized
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            # Bring to foreground
            win32gui.SetForegroundWindow(target_hwnd)
            actual_title = win32gui.GetWindowText(target_hwnd)
            return {"success": True, "window_title": actual_title}
        else:
            return {"success": False, "error": f"No window found matching '{title_substring}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def type_text(text: str, interval: float = 0.02) -> dict:
    """Type text into the currently focused window using keyboard simulation."""
    try:
        wait_for_human_idle()
        import pyautogui
        # Small delay to ensure the target window is ready
        time.sleep(0.3)
        # Use pyperclip + hotkey for reliable Unicode support
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        return {"success": True, "typed_length": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_hotkey(*keys) -> dict:
    """Press a keyboard shortcut (e.g., ctrl+s, alt+f4, ctrl+shift+n)."""
    try:
        wait_for_human_idle()
        import pyautogui
        time.sleep(0.2)
        pyautogui.hotkey(*keys)
        return {"success": True, "keys": "+".join(keys)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_key(key: str, presses: int = 1) -> dict:
    """Press a single key (e.g., enter, tab, escape, down, up)."""
    try:
        wait_for_human_idle()
        import pyautogui
        time.sleep(0.1)
        pyautogui.press(key, presses=presses)
        return {"success": True, "key": key, "presses": presses}
    except Exception as e:
        return {"success": False, "error": str(e)}


def click_position(x: int, y: int, button: str = "left") -> dict:
    """Click at a specific screen coordinate."""
    global _last_synthetic_pos
    try:
        wait_for_human_idle()
        import pyautogui
        time.sleep(0.1)
        pyautogui.click(x, y, button=button)
        _last_synthetic_pos = (x, y)
        return {"success": True, "position": f"({x}, {y})", "button": button}
    except Exception as e:
        return {"success": False, "error": str(e)}


def open_app_and_type(app_command: str, text: str, wait_seconds: float = 1.5) -> dict:
    """
    Open an application via command, wait for it to load, then type text into it.
    This is the JARVIS-style 'open notepad and write my name' handler.
    """
    try:
        import subprocess
        import pyautogui

        # Launch the application
        subprocess.Popen(app_command, shell=True)
        logger.info(f"Launched '{app_command}', waiting {wait_seconds}s for it to load...")

        # Wait for the app to fully load
        time.sleep(wait_seconds)

        # Type the text using clipboard paste for Unicode safety
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)

        return {
            "success": True,
            "action": "open_app_and_type",
            "app": app_command,
            "typed_length": len(text),
            "details": f"Opened '{app_command}' and typed {len(text)} characters into it."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
