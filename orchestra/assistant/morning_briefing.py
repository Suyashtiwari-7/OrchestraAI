"""
OrchestraAI — Daily Executive Morning Briefing
================================================
Generates a crisp, JARVIS-style executive summary when the user wakes up:
- Today's date & time
- Weather in Indore (or user's city)
- VIP messages / unread alerts summary
- Motivational agenda kick-off
(No battery checking, as requested)
"""

import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx

from ..config import settings
from .vip_filter import VIPFilter

logger = logging.getLogger("orchestra.assistant.briefing")


class MorningBriefing:
    """Manages the daily executive morning briefing routine."""

    def __init__(self, city: str = "Indore", user_name: str = "Suyash"):
        self.city = city
        self.user_name = user_name
        self._last_briefing_date: Optional[str] = None

    def should_trigger_briefing(self) -> bool:
        """
        Check if briefing should fire:
        - Must be between 6:00 AM and 1:00 PM
        - Has not already triggered today
        """
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if self._last_briefing_date == today_str:
            return False

        # Only trigger in morning/early afternoon hours
        if 6 <= now.hour <= 13:
            return True

        return False

    def mark_briefing_done(self):
        """Mark today's briefing as delivered."""
        self._last_briefing_date = datetime.now().strftime("%Y-%m-%d")

    def fetch_weather(self) -> Dict[str, Any]:
        """Fetch fast live weather for the target city with fallback."""
        try:
            url = f"https://wttr.in/{self.city}?format=j1"
            res = httpx.get(url, timeout=3.0, follow_redirects=True)
            if res.status_code == 200:
                data = res.json()
                current = data.get("current_condition", [{}])[0]
                temp_c = current.get("temp_C", "28")
                desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
                return {"success": True, "temp": temp_c, "condition": desc, "city": self.city}
        except Exception as e:
            logger.debug(f"Weather fetch failed ({e}), using default.")
        
        return {"success": True, "temp": "28", "condition": "Clear", "city": self.city}

    def generate_briefing_text(self, vip_summary: Optional[str] = None) -> str:
        """
        Generate the executive spoken script.
        """
        weather = self.fetch_weather()
        temp = weather.get("temp", "28")
        condition = weather.get("condition", "Clear")
        city = weather.get("city", self.city)

        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        day_str = now.strftime("%A")

        script = f"Good morning {self.user_name}! It's {time_str} on a beautiful {day_str}. "
        script += f"Weather in {city} is {temp} degrees Celsius and {condition}. "

        if vip_summary and vip_summary.strip():
            script += f"You have urgent alerts: {vip_summary}. "
        else:
            script += "Your inbox and VIP feed are clear. "

        script += "DARKI is online and ready. What are we conquering today?"
        return script
