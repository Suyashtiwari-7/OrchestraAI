"""
OrchestraAI — DARKI Global Hotkey Listener (Native Win32)
===========================================================
Uses Windows native RegisterHotKey API directly inside the Qt
event loop. No external libraries needed. No admin privileges required.
Works system-wide even when another app has focus.

Primary Hotkey: Alt+Space (Spotlight/Raycast style)
Secondary Hotkeys: Ctrl+0 (top row), Ctrl+Numpad0
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
from typing import Callable, Optional

logger = logging.getLogger("orchestra.hotkey")

# Win32 constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20     # Space key
VK_0 = 0x30         # Top-row '0'
VK_NUMPAD0 = 0x60   # Numpad '0'
WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32

# Hotkey IDs
HOTKEY_ALT_SPACE = 1
HOTKEY_CTRL_0 = 2
HOTKEY_CTRL_NUMPAD0 = 3


class NativeHotkeyFilter:
    """
    Qt-native event filter that catches WM_HOTKEY messages from
    Windows RegisterHotKey. Runs inside the existing Qt event loop
    with zero extra threads or background processes.
    """

    def __init__(self, on_activate: Optional[Callable[[], None]] = None):
        self.on_activate = on_activate
        self._registered = []

    def start(self):
        """Register global hotkeys with Windows."""
        hotkeys = [
            (HOTKEY_ALT_SPACE, MOD_ALT | MOD_NOREPEAT, VK_SPACE, "Alt+Space"),
            (HOTKEY_CTRL_0, MOD_CONTROL | MOD_NOREPEAT, VK_0, "Ctrl+0"),
            (HOTKEY_CTRL_NUMPAD0, MOD_CONTROL | MOD_NOREPEAT, VK_NUMPAD0, "Ctrl+Numpad0"),
        ]
        for hk_id, modifiers, vk, label in hotkeys:
            result = user32.RegisterHotKey(None, hk_id, modifiers, vk)
            if result:
                self._registered.append(hk_id)
                logger.info(f"Global hotkey registered: {label} (ID={hk_id})")
            else:
                err = ctypes.GetLastError()
                logger.warning(f"Failed to register {label}: Win32 error {err}")

    def stop(self):
        """Unregister all hotkeys."""
        for hk_id in self._registered:
            user32.UnregisterHotKey(None, hk_id)
        self._registered.clear()
        logger.info("Global hotkeys unregistered.")

    def check_message(self) -> bool:
        """
        Non-blocking check for WM_HOTKEY messages in the Windows message queue.
        Call this periodically from a QTimer (e.g. every 100ms).
        Returns True if a hotkey was detected and the callback was fired.
        """
        msg = wintypes.MSG()
        PM_REMOVE = 0x0001
        if user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
            if msg.message == WM_HOTKEY:
                logger.info(f"Hotkey pressed! ID={msg.wParam}")
                if self.on_activate:
                    self.on_activate()
                return True
        return False


class HotkeyListener:
    """
    Drop-in replacement for global hotkey handling.
    Uses native Win32 RegisterHotKey + a QTimer polling loop.
    """

    def __init__(self, hotkey: Optional[str] = None, on_activate: Callable[[], None] = None):
        self.on_activate = on_activate
        self._native = NativeHotkeyFilter(on_activate=on_activate)
        self._timer = None

    def start(self):
        """Register hotkeys and start the QTimer polling loop."""
        self._native.start()

        # Start a lightweight QTimer that polls for WM_HOTKEY every 100ms
        try:
            from PyQt6.QtCore import QTimer
            self._timer = QTimer()
            self._timer.timeout.connect(self._native.check_message)
            self._timer.start(100)  # 100ms = responsive, near-zero CPU
            logger.info("Hotkey polling timer started (100ms interval for Alt+Space / Ctrl+0).")
        except ImportError:
            logger.warning("PyQt6 not available — hotkey polling disabled.")

    def stop(self):
        """Stop polling and unregister hotkeys."""
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._native.stop()
