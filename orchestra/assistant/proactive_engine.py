"""
OrchestraAI — Proactive Executive Assistant Engine
===================================================
Coordinates:
- NotificationListener (WhatsApp Web, Windows toasts)
- VIPFilter (3-tier priority, Groq urgency evaluation)
- ScheduledReminders & Advance Event Alerts (e.g. reminding on Aug 18 for an Aug 19 interview)
- Spoken Voice Alerts via Kokoro-82M TTS
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable

from .vip_filter import VIPFilter, ContactTier, PriorityEvaluation
from .notification_listener import NotificationListener, CapturedNotification
from ..router import ModelRouter

logger = logging.getLogger("orchestra.assistant.engine")


@dataclass
class ScheduledReminder:
    """Represents a scheduled advance or real-time reminder."""
    id: str
    title: str
    target_timestamp: float
    message: str
    spoken_text: str
    source_event: Optional[str] = None
    fired: bool = False


class ProactiveEngine:
    """Central engine for proactive notifications, VIP filtering, and advance event reminders."""

    REMINDER_CHECK_INTERVAL = 5.0  # seconds

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        on_voice_alert: Optional[Callable[[str], None]] = None,
        on_notification_alert: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.router = router
        self.vip_filter = VIPFilter(router=router)
        self.listener = NotificationListener(on_notification=self._handle_incoming_notification)

        self.on_voice_alert = on_voice_alert
        self.on_notification_alert = on_notification_alert

        self._reminders: List[ScheduledReminder] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Start the proactive assistant and reminder loop."""
        if self._running:
            return
        self._running = True
        self.listener.start()
        self._thread = threading.Thread(target=self._reminder_loop, daemon=True, name="ProactiveEngineThread")
        self._thread.start()
        logger.info("[*] Proactive Executive Assistant Engine started.")

    def stop(self):
        """Stop the proactive assistant."""
        self._running = False
        self.listener.stop()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[*] Proactive Executive Assistant Engine stopped.")

    def _handle_incoming_notification(self, notif: CapturedNotification):
        """Evaluate an incoming notification through VIP and AI urgency filters."""
        eval_res = self.vip_filter.evaluate_message(
            sender=notif.sender,
            message=notif.body,
            is_group=notif.is_group,
            has_direct_mention=notif.has_direct_mention,
        )

        if not eval_res.should_alert:
            logger.debug(f"[Assistant] Suppressed low-priority notification from {notif.sender}: {eval_res.reason}")
            return

        # Build spoken executive assistant alert
        if notif.has_direct_mention:
            spoken_msg = f"Excuse me Suyash, you were directly mentioned in a WhatsApp group chat."
        elif eval_res.tier == ContactTier.TIER_1_VIP:
            spoken_msg = f"Hey Suyash, VIP message from {notif.sender}: {notif.body[:80]}"
        else:
            spoken_msg = f"Heads up Suyash, important update from {notif.sender}: {notif.body[:80]}"

        logger.info(f"[Assistant] PROACTIVE ALERT: {spoken_msg}")

        # Trigger desktop UI / notification callback
        if self.on_notification_alert:
            try:
                self.on_notification_alert({
                    "sender": notif.sender,
                    "title": notif.title,
                    "body": notif.body,
                    "urgency": eval_res.urgency_score,
                    "tier": eval_res.tier.value,
                    "spoken_text": spoken_msg,
                })
            except Exception as e:
                logger.error(f"[Assistant] Notification callback error: {e}")

        # Trigger Kokoro spoken voice alert
        if self.on_voice_alert:
            try:
                self.on_voice_alert(spoken_msg)
            except Exception as e:
                logger.error(f"[Assistant] Voice alert error: {e}")

        # If a future event was detected (e.g. interview on Aug 19), schedule advance reminder (Aug 18)
        if eval_res.event_detected and eval_res.event_date:
            self._schedule_advance_event_reminder(eval_res)

    def _schedule_advance_event_reminder(self, eval_res: PriorityEvaluation):
        """Schedule an automatic advance reminder (e.g. 1 day prior) for a detected event."""
        try:
            event_dt = datetime.strptime(eval_res.event_date, "%Y-%m-%d")
            # Schedule reminder for 1 day before at 9:00 AM
            advance_dt = event_dt - timedelta(days=1)
            advance_dt = advance_dt.replace(hour=9, minute=0, second=0)
            advance_ts = advance_dt.timestamp()

            if advance_ts > time.time():
                reminder_id = f"event_{int(advance_ts)}"
                reminder = ScheduledReminder(
                    id=reminder_id,
                    title=f"Upcoming {eval_res.event_detected}",
                    target_timestamp=advance_ts,
                    message=f"Reminder: You have a {eval_res.event_detected} tomorrow ({eval_res.event_date})!",
                    spoken_text=f"Good morning Suyash! Quick reminder: You have a {eval_res.event_detected} tomorrow, {eval_res.event_date}.",
                    source_event=eval_res.event_detected,
                )
                self.schedule_reminder(reminder)
                logger.info(f"[Assistant] Auto-scheduled advance reminder for {eval_res.event_detected} on {advance_dt.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            logger.debug(f"[Assistant] Could not parse event date for advance reminder: {e}")

    def schedule_reminder(self, reminder: ScheduledReminder):
        """Add a reminder to the schedule."""
        with self._lock:
            self._reminders.append(reminder)

    def _reminder_loop(self):
        """Check for due reminders and fire them."""
        while self._running:
            now = time.time()
            due_reminders = []

            with self._lock:
                for rem in self._reminders:
                    if not rem.fired and now >= rem.target_timestamp:
                        rem.fired = True
                        due_reminders.append(rem)

            for rem in due_reminders:
                logger.info(f"[Assistant] FIRING SCHEDULED REMINDER: {rem.title}")
                if self.on_voice_alert:
                    try:
                        self.on_voice_alert(rem.spoken_text)
                    except Exception as e:
                        logger.error(f"[Assistant] Reminder voice alert error: {e}")

                if self.on_notification_alert:
                    try:
                        self.on_notification_alert({
                            "sender": "DARKI Assistant",
                            "title": rem.title,
                            "body": rem.message,
                            "urgency": 9,
                            "tier": "VIP",
                            "spoken_text": rem.spoken_text,
                        })
                    except Exception as e:
                        logger.error(f"[Assistant] Reminder notification error: {e}")

            time.sleep(self.REMINDER_CHECK_INTERVAL)

    def get_all_reminders(self) -> List[Dict[str, Any]]:
        """Return list of all scheduled reminders."""
        with self._lock:
            return [
                {
                    "id": rem.id,
                    "title": rem.title,
                    "target_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rem.target_timestamp)),
                    "message": rem.message,
                    "fired": rem.fired,
                }
                for rem in self._reminders
            ]
