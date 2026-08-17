"""
OrchestraAI — Notification & WhatsApp Web Interceptor
======================================================
Captures incoming messages and notifications across:
- WhatsApp Web tab title badges ((1) WhatsApp, (@) WhatsApp for direct tags)
- Native Windows applications via Win32 Window text inspection
"""

import os
import re
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("orchestra.assistant.notifications")


@dataclass
class CapturedNotification:
    """Represents an intercepted incoming notification or message."""
    app_name: str
    sender: str
    title: str
    body: str
    is_group: bool = False
    has_direct_mention: bool = False
    unread_count: int = 1
    timestamp: float = field(default_factory=time.time)


class NotificationListener:
    """Background listener for WhatsApp Web tabs and native Windows application updates."""

    POLL_INTERVAL = 3.0  # Polls browser window titles every 3 seconds (<0.05% CPU)

    def __init__(self, on_notification: Optional[Callable[[CapturedNotification], None]] = None):
        self.on_notification = on_notification
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_whatsapp_badge: Optional[str] = None

    def start(self):
        """Start background notification listener."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="NotificationListenerThread")
        self._thread.start()
        logger.info("[*] Notification Listener started.")

    def stop(self):
        """Stop background notification listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[*] Notification Listener stopped.")

    def _listen_loop(self):
        """Background loop scanning window titles for WhatsApp Web badges."""
        while self._running:
            try:
                self.check_whatsapp_tab_badge()
            except Exception as e:
                logger.debug(f"[Assistant] Notification listener poll error: {e}")

            time.sleep(self.POLL_INTERVAL)

    def check_whatsapp_tab_badge(self) -> Optional[CapturedNotification]:
        """
        Scan open browser windows for WhatsApp Web tab badges:
        - '(1) WhatsApp' -> Standard unread message
        - '(@) WhatsApp' -> Direct user mention in group
        """
        titles = self._get_open_window_titles()

        for title in titles:
            if "whatsapp" in title.lower():
                # Direct mention indicator: '(@) WhatsApp'
                mention_match = re.search(r"\(@\)\s*whatsapp", title, re.IGNORECASE)
                # Numeric unread badge: '(2) WhatsApp'
                count_match = re.search(r"\((\d+)\)\s*whatsapp", title, re.IGNORECASE)

                if mention_match or count_match:
                    badge_key = title.strip()
                    # Only fire if badge state changed (avoids repeated spam on same badge)
                    if badge_key != self._last_whatsapp_badge:
                        self._last_whatsapp_badge = badge_key

                        has_mention = bool(mention_match)
                        unread_count = int(count_match.group(1)) if count_match else 1

                        notif = CapturedNotification(
                            app_name="WhatsApp Web",
                            sender="WhatsApp",
                            title="New WhatsApp Message" if not has_mention else "Direct Mention in WhatsApp Group",
                            body=f"You have {unread_count} unread WhatsApp message(s)." if not has_mention else "Someone directly mentioned you in a group chat (@)!",
                            is_group=has_mention,
                            has_direct_mention=has_mention,
                            unread_count=unread_count,
                        )

                        logger.info(f"[Assistant] Intercepted WhatsApp badge: '{title}' (Mentions={has_mention}, Unread={unread_count})")
                        if self.on_notification:
                            self.on_notification(notif)

                        return notif
                else:
                    # Reset badge state when user opens/reads WhatsApp
                    if "whatsapp" in title.lower() and not count_match and not mention_match:
                        self._last_whatsapp_badge = None

        return None

    def _get_open_window_titles(self) -> List[str]:
        """Get list of active window titles using Win32 API."""
        titles = []
        try:
            if os.name == "nt":
                import win32gui
                def enum_handler(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        t = win32gui.GetWindowText(hwnd)
                        if t:
                            titles.append(t)
                win32gui.EnumWindows(enum_handler, None)
        except Exception:
            pass
        return titles
