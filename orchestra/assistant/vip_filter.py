"""
OrchestraAI — VIP & Smart Urgency Filter
=========================================
3-Tier Contact Categorization & Groq-Powered Urgency Scoring:
- Tier 1 (VIP): Always Alert immediately.
- Tier 2 (Standard): Alert only if message has actionable question, meeting, or deadline.
- Tier 3 (Muted Groups): 100% Silent unless directly @mentioned.
"""

import json
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set

from ..router import ModelRouter, ClassificationResult
from ..config import TaskType

logger = logging.getLogger("orchestra.assistant.vip")


class ContactTier(Enum):
    TIER_1_VIP = "VIP"              # Always alert
    TIER_2_STANDARD = "STANDARD"    # Alert on actionable content
    TIER_3_MUTED = "MUTED"          # Silent unless @tagged


@dataclass
class PriorityEvaluation:
    """Evaluation result for an incoming notification/message."""
    should_alert: bool
    tier: ContactTier
    urgency_score: int              # 1 to 10
    reason: str
    action_required: bool = False
    event_detected: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None


class VIPFilter:
    """Manages VIP lists, muted groups, and AI message urgency classification."""

    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router
        self._vips: Dict[str, str] = {}  # name.lower() -> relationship
        self._muted_groups: Set[str] = set()

    def add_vip(self, name: str, relationship: str = "VIP"):
        """Add a contact to Tier 1 VIP whitelist."""
        clean = name.lower().strip()
        self._vips[clean] = relationship
        logger.info(f"[Assistant] Added VIP contact: {name} ({relationship})")

    def remove_vip(self, name: str):
        """Remove a contact from VIP whitelist."""
        clean = name.lower().strip()
        self._vips.pop(clean, None)

    def mute_group(self, group_name: str):
        """Add a group chat to Tier 3 Muted list."""
        clean = group_name.lower().strip()
        self._muted_groups.add(clean)
        logger.info(f"[Assistant] Muted group chat: {group_name}")

    def unmute_group(self, group_name: str):
        """Unmute a group chat."""
        clean = group_name.lower().strip()
        self._muted_groups.discard(clean)

    def get_tier(self, sender: str, is_group: bool = False) -> ContactTier:
        """Determine contact tier for a sender or group."""
        clean = sender.lower().strip()

        # Check Tier 1 VIPs
        if clean in self._vips:
            return ContactTier.TIER_1_VIP

        # Check Tier 3 Muted Groups
        if is_group and clean in self._muted_groups:
            return ContactTier.TIER_3_MUTED

        return ContactTier.TIER_2_STANDARD

    def evaluate_message(
        self,
        sender: str,
        message: str,
        is_group: bool = False,
        has_direct_mention: bool = False,
    ) -> PriorityEvaluation:
        """
        Evaluate incoming message importance using tier rules + Groq AI analysis.
        """
        tier = self.get_tier(sender, is_group=is_group)

        # 1. Tier 1 VIP: Always alert!
        if tier == ContactTier.TIER_1_VIP:
            relation = self._vips.get(sender.lower().strip(), "VIP")
            return PriorityEvaluation(
                should_alert=True,
                tier=ContactTier.TIER_1_VIP,
                urgency_score=9,
                reason=f"Message from Tier 1 VIP contact ({sender} - {relation}).",
                action_required=True,
            )

        # 2. Tier 3 Muted Groups: Ignore unless directly @mentioned
        if tier == ContactTier.TIER_3_MUTED and not has_direct_mention:
            return PriorityEvaluation(
                should_alert=False,
                tier=ContactTier.TIER_3_MUTED,
                urgency_score=1,
                reason=f"Muted group chat ({sender}). No direct mention.",
                action_required=False,
            )

        # 3. Tier 2 Standard (or Tier 3 with @direct_mention): AI Urgency Check
        return self._ai_evaluate_urgency(sender, message, has_direct_mention)

    def _ai_evaluate_urgency(self, sender: str, message: str, has_direct_mention: bool) -> PriorityEvaluation:
        """Use fast AI (Groq Llama 3.3) to classify urgency, meeting requests, and deadlines."""
        # Simple heuristic fallback if router is not initialized
        if not self.router:
            # Fallback keyword checks
            urgent_keywords = ["urgent", "call me", "meet", "interview", "deadline", "important", "asap", "by 5", "by 4"]
            msg_lower = message.lower()
            is_urgent = any(kw in msg_lower for kw in urgent_keywords) or has_direct_mention
            return PriorityEvaluation(
                should_alert=is_urgent,
                tier=ContactTier.TIER_2_STANDARD,
                urgency_score=8 if is_urgent else 3,
                reason="Heuristic evaluation: Actionable keyword detected" if is_urgent else "Casual message",
                action_required=is_urgent,
            )

        prompt = f"""You are an executive assistant importance classifier.
Analyze this incoming message from "{sender}":
"{message}"

Directly Mentioned User: {has_direct_mention}

Classify into JSON:
{{
    "should_alert": true or false,
    "urgency_score": 1 to 10,
    "reason": "short explanation",
    "action_required": true or false,
    "event_detected": "Meeting / Interview / Task / None",
    "event_date": "YYYY-MM-DD or null",
    "event_time": "HH:MM or null"
}}

Rules:
- General banter, memes, one-word replies ("ok", "lol", "nice"), or marketing promos -> should_alert = false.
- Meeting requests ("let's meet at 5pm"), interview invites, deadlines, or direct questions needing user action -> should_alert = true.
- Output raw JSON only.
"""
        classification = ClassificationResult(
            task_type=TaskType.FAST_UTILITY,
            confidence=1.0,
            reasoning="Fast notification importance classification",
            raw_input=prompt,
        )

        try:
            result, _ = self.router.route_text(
                prompt=prompt,
                classification=classification,
                system_prompt="You are a strict JSON classifier. Output ONLY valid raw JSON.",
            )

            content = result.content.strip()
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
            else:
                json_str = content

            data = json.loads(json_str)
            return PriorityEvaluation(
                should_alert=data.get("should_alert", False),
                tier=ContactTier.TIER_2_STANDARD,
                urgency_score=data.get("urgency_score", 5),
                reason=data.get("reason", "AI classified"),
                action_required=data.get("action_required", False),
                event_detected=data.get("event_detected"),
                event_date=data.get("event_date"),
                event_time=data.get("event_time"),
            )
        except Exception as e:
            logger.debug(f"[Assistant] AI urgency evaluation error: {e}")
            return PriorityEvaluation(
                should_alert=has_direct_mention,
                tier=ContactTier.TIER_2_STANDARD,
                urgency_score=5,
                reason="Default fallback evaluation",
            )
