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
    
    Registers Ctrl+0 and Ctrl+Numpad0 to activate the DARKI popup
    from anywhere on the system.
    """

    DEFAULT_HOTKEYS = ["ctrl+0", "ctrl+num 0", "ctrl+numpad0", "ctrl+num_0"]

    def __init__(self, hotkey: Optional[str] = None, on_activate: Callable[[], None] = None):
        """
        Args:
            hotkey: Optional custom shortcut string. If None, registers both top-row 0 and Numpad 0.
            on_activate: Callback fired when any registered hotkey is pressed.
        """
        self.hotkeys = [hotkey] if hotkey else self.DEFAULT_HOTKEYS
        self.on_activate = on_activate
        self._registered_keys = []
        self._keyboard = None

    def start(self):
        """Register all global hotkey variants."""
        try:
            import keyboard
            self._keyboard = keyboard
        except ImportError:
            logger.warning("keyboard library not installed. Hotkey disabled.")
            return

        for hk in self.hotkeys:
            try:
                self._keyboard.add_hotkey(hk, self._on_hotkey_pressed, suppress=False)
                self._registered_keys.append(hk)
                logger.info(f"Global hotkey registered: {hk}")
            except Exception as e:
                logger.debug(f"Could not register hotkey variant '{hk}': {e}")

    def stop(self):
        """Unregister all registered hotkeys."""
        if self._keyboard:
            for hk in self._registered_keys:
                try:
                    self._keyboard.remove_hotkey(hk)
                except Exception:
                    pass
            self._registered_keys.clear()
            logger.info("Global hotkeys unregistered.")

    def _on_hotkey_pressed(self):
        """Called when any registered global hotkey is pressed."""
        logger.info("DARKI activation hotkey pressed!")
        if self.on_activate:
            self.on_activate()
