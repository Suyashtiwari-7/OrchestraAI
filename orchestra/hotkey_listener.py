"""
OrchestraAI — DARKI Global Hotkey Listener
=============================================
Registers system-wide keyboard shortcuts that work even when
another application has focus. Default: Ctrl+Num0.
"""

import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger("orchestra.hotkey")


class HotkeyListener:
    """
    Global hotkey listener using the `keyboard` library.
    
    Registers Ctrl+Num0 (or custom combo) to activate the DARKI popup
    from anywhere on the system.
    """

    def __init__(self, hotkey: str = "ctrl+0", on_activate: Callable[[], None] = None):
        """
        Args:
            hotkey: Keyboard shortcut string (e.g. 'ctrl+0', 'ctrl+shift+d').
            on_activate: Callback fired when the hotkey is pressed.
        """
        self.hotkey = hotkey
        self.on_activate = on_activate
        self._registered = False
        self._keyboard = None

    def start(self):
        """Register the global hotkey."""
        try:
            import keyboard
            self._keyboard = keyboard
        except ImportError:
            logger.warning("keyboard library not installed. Hotkey disabled.")
            return

        try:
            self._keyboard.add_hotkey(self.hotkey, self._on_hotkey_pressed, suppress=False)
            self._registered = True
            logger.info(f"Global hotkey registered: {self.hotkey}")
        except Exception as e:
            logger.error(f"Failed to register hotkey '{self.hotkey}': {e}")

    def stop(self):
        """Unregister the hotkey."""
        if self._registered and self._keyboard:
            try:
                self._keyboard.remove_hotkey(self.hotkey)
                self._registered = False
                logger.info(f"Global hotkey unregistered: {self.hotkey}")
            except Exception:
                pass

    def _on_hotkey_pressed(self):
        """Called when the global hotkey is pressed."""
        logger.info(f"Hotkey {self.hotkey} pressed!")
        if self.on_activate:
            self.on_activate()
