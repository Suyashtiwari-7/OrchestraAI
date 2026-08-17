"""
OrchestraAI — Proactive Executive Assistant Tests
==================================================
Tests for VIPFilter, NotificationListener, and ProactiveEngine.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from orchestra.assistant.vip_filter import VIPFilter, ContactTier
from orchestra.assistant.notification_listener import NotificationListener, CapturedNotification
from orchestra.assistant.proactive_engine import ProactiveEngine, ScheduledReminder


class TestVIPFilter:
    """Test 3-tier contact categorization and urgency filtering."""

    def setup_method(self):
        self.vip_filter = VIPFilter(router=None)  # Uses heuristic fallback

    def test_vip_tier_1_always_alerts(self):
        """Test that Tier 1 VIP contacts always trigger an alert."""
        self.vip_filter.add_vip("Yash", "Best Friend")
        eval_res = self.vip_filter.evaluate_message(
            sender="Yash",
            message="Hey what's up",
            is_group=False,
        )
        assert eval_res.should_alert is True
        assert eval_res.tier == ContactTier.TIER_1_VIP
        assert "Yash" in eval_res.reason

    def test_muted_group_chat_is_silent(self):
        """Test that Tier 3 Muted group chats do not trigger alerts."""
        self.vip_filter.mute_group("College Batch 2026")
        eval_res = self.vip_filter.evaluate_message(
            sender="College Batch 2026",
            message="Check out this funny meme!",
            is_group=True,
            has_direct_mention=False,
        )
        assert eval_res.should_alert is False
        assert eval_res.tier == ContactTier.TIER_3_MUTED

    def test_muted_group_chat_with_direct_mention_alerts(self):
        """Test that @mention direct tag in a muted group triggers an alert."""
        self.vip_filter.mute_group("College Batch 2026")
        eval_res = self.vip_filter.evaluate_message(
            sender="College Batch 2026",
            message="@Suyash when is the assignment due?",
            is_group=True,
            has_direct_mention=True,
        )
        assert eval_res.should_alert is True

    def test_standard_contact_urgent_keyword_alerts(self):
        """Test that standard contacts alert on actionable deadlines/meetings."""
        eval_res = self.vip_filter.evaluate_message(
            sender="Recruiter",
            message="Your interview is scheduled for tomorrow at 5 PM",
            is_group=False,
        )
        assert eval_res.should_alert is True
        assert eval_res.tier == ContactTier.TIER_2_STANDARD


class TestNotificationListener:
    """Test WhatsApp Web tab badge parsing."""

    def setup_method(self):
        self.listener = NotificationListener()

    @patch.object(NotificationListener, "_get_open_window_titles")
    def test_whatsapp_unread_badge_detection(self, mock_titles):
        """Test detection of '(2) WhatsApp' unread badge in window title."""
        mock_titles.return_value = ["(2) WhatsApp - Brave", "Visual Studio Code"]
        notif = self.listener.check_whatsapp_tab_badge()

        assert notif is not None
        assert notif.unread_count == 2
        assert notif.has_direct_mention is False

    @patch.object(NotificationListener, "_get_open_window_titles")
    def test_whatsapp_direct_mention_badge(self, mock_titles):
        """Test detection of '(@) WhatsApp' direct mention badge."""
        mock_titles.return_value = ["(@) WhatsApp - Google Chrome"]
        notif = self.listener.check_whatsapp_tab_badge()

        assert notif is not None
        assert notif.has_direct_mention is True


class TestProactiveEngine:
    """Test advance event reminders and scheduler."""

    def test_schedule_and_fire_reminder(self):
        """Test scheduling a reminder and firing when due."""
        voice_alerts = []
        engine = ProactiveEngine(
            router=None,
            on_voice_alert=lambda text: voice_alerts.append(text),
        )

        # Create a reminder due 0.1s in the past
        due_reminder = ScheduledReminder(
            id="test_rem_1",
            title="Interview Prep",
            target_timestamp=time.time() - 1.0,
            message="Prepare for interview",
            spoken_text="Good morning! Interview tomorrow.",
        )
        engine.schedule_reminder(due_reminder)

        # Trigger one check pass
        engine.start()
        time.sleep(0.2)
        engine.stop()

        assert due_reminder.fired is True
        assert len(voice_alerts) >= 1
        assert "Interview tomorrow" in voice_alerts[0]
