"""
OrchestraAI — Local User Profile Memory
=======================================
Stores persistent user details and preferences locally and privately.
Scans incoming messages to learn about the user over time.
"""

import json
import re
from pathlib import Path
from typing import List, Optional

from ..config import settings

class UserProfileMemory:
    """Manages the user's local profile and extracts personal facts dynamically."""

    def __init__(self, filepath: Optional[Path] = None):
        """
        Initialize the User Profile memory.

        Args:
            filepath: Path to save/load user profile facts (default: output/user_profile.json)
        """
        self._filepath = filepath or settings.project_root / "output" / "user_profile.json"
        self._facts: List[str] = []
        self._load()

    def _load(self):
        """Load user profile facts from disk."""
        try:
            if self._filepath.exists():
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._facts = data.get("facts", [])
        except Exception:
            self._facts = []

    def _save(self):
        """Save user profile facts to disk."""
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump({"facts": self._facts}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def extract_facts(self, text: str) -> List[str]:
        """
        Scan user prompt for statements like 'my name is X' or 'i prefer Y' 
        and save them as permanent facts.
        """
        cleaned_text = text.strip().replace("\n", " ")
        new_facts = []

        # List of regex rules to match personal declarations
        rules = [
            # My name is X
            (r"\bmy name is\b\s+([a-zA-Z0-9\s\-\_]{2,30})", "My name is {}"),
            # I prefer X
            (r"\bi prefer\b\s+([a-zA-Z0-9\s\-\_]{2,50})", "I prefer {}"),
            # I am a X (e.g. developer)
            (r"\bi am a\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "I am a {}"),
            # I live in X
            (r"\bi live in\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "I live in {}"),
            # My email is X
            (r"\bmy email is\b\s+([a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+)", "My email is {}"),
            # I work at X
            (r"\bi work at\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "I work at {}"),
            # I use X (e.g. Brave browser)
            (r"\bi use\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "I use {}"),
        ]

        for pattern, template in rules:
            matches = re.finditer(pattern, cleaned_text, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                # Clean value of punctuation at the end (e.g. period or comma)
                value = re.sub(r"[\.\,\!\?\;\:]+$", "", value).strip()
                if value:
                    fact = template.format(value)
                    # Deduplicate facts
                    if fact not in self._facts:
                        self._facts.append(fact)
                        new_facts.append(fact)

        if new_facts:
            self._save()

        return new_facts

    def add_fact(self, fact: str):
        """Manually add a fact to the profile."""
        if fact not in self._facts:
            self._facts.append(fact)
            self._save()

    def get_system_context(self) -> str:
        """Format saved facts to inject as context into LLM system prompts."""
        if not self._facts:
            return ""

        facts_list = "\n".join(f"- {fact}" for fact in self._facts)
        return (
            "\n\n--- USER PROFILE DETAILS (Extracted from chat context) ---\n"
            f"{facts_list}\n"
            "Use the details above to address the user by name or respect their stated preferences.\n"
            "--- End User Profile ---\n"
        )
