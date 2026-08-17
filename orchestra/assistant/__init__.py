"""
OrchestraAI — Proactive Personal Executive Assistant Engine
============================================================
Autonomous background monitoring and proactive assistance:
- NotificationListener: Intercepts Windows toasts and WhatsApp Web unread badges.
- VIPFilter: 3-tier VIP contact management & Groq AI urgency classification.
- ProactiveEngine: Advance reminder scheduling & voluntary voice alert delivery.
"""

from .vip_filter import VIPFilter, ContactTier, PriorityEvaluation
from .notification_listener import NotificationListener, CapturedNotification
from .proactive_engine import ProactiveEngine, ScheduledReminder

__all__ = [
    "VIPFilter",
    "ContactTier",
    "PriorityEvaluation",
    "NotificationListener",
    "CapturedNotification",
    "ProactiveEngine",
    "ScheduledReminder",
]
