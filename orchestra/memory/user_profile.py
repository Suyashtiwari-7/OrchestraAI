"""
OrchestraAI — Local User Profile Memory (SQLite-Backed)
======================================================
Stores persistent user details and preferences locally and privately in SQLite.
Scans incoming messages to learn about the user over time.
"""

import re
import logging
from pathlib import Path
from typing import List, Optional
from .database import MemoryDatabase

logger = logging.getLogger("orchestra.memory.user_profile")

class UserProfileMemory:
    """Manages the user's profile facts dynamically using SQLite insights table."""

    def __init__(self, db: Optional[MemoryDatabase] = None, filepath: Optional[Path] = None):
        """Initialize SQLite user profile memory."""
        self.filepath = filepath
        if filepath:
            db_path = filepath.parent / (filepath.stem + "_memory.db")
            self.db = MemoryDatabase(db_path=db_path)
            self._write_legacy_json()
        else:
            self.db = db or MemoryDatabase()

    @property
    def _facts(self) -> List[str]:
        """Backward compatibility: retrieve all facts from the SQLite insights table as a list of strings."""
        rows = self.db.get_all_insights(limit=100)
        return [row['value'] for row in rows]

    def _write_legacy_json(self):
        """Writes legacy JSON file representation for test suite compatibility."""
        if self.filepath:
            import json
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump({"facts": self._facts}, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _save(self):
        """Save method wrapper for test suites."""
        self._write_legacy_json()

    def extract_facts(self, text: str) -> List[str]:
        """
        Scan user prompt for statements like 'my name is X' or 'i prefer Y'
        and save them as permanent facts.
        """
        cleaned_text = text.strip().replace("\n", " ")
        new_facts = []

        # List of regex rules to match personal declarations
        rules = [
            (r"\bmy name is\b\s+([a-zA-Z0-9\s\-\_]{2,30})", "Personal Info", "name", "My name is {}"),
            (r"\bi prefer\b\s+([a-zA-Z0-9\s\-\_]{2,50})", "Preferences", "preference_{}", "I prefer {}"),
            (r"\bi am a\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "Personal Info", "occupation", "I am a {}"),
            (r"\bi live in\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "Personal Info", "location", "I live in {}"),
            (r"\bmy email is\b\s+([a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+)", "Personal Info", "email", "My email is {}"),
            (r"\bi work at\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "Personal Info", "company", "I work at {}"),
            (r"\bi use\b\s+([a-zA-Z0-9\s\-\_]{2,40})", "Preferences", "tool_{}", "I use {}"),
        ]

        for pattern, category, key_template, template in rules:
            matches = re.finditer(pattern, cleaned_text, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                value = re.sub(r"[\.\,\!\?\;\:]+$", "", value).strip()
                if value:
                    fact = template.format(value)
                    
                    # Generate a clean key
                    val_slug = re.sub(r'[^a-z0-9_]', '', value.lower().replace(" ", "_"))[:20]
                    key = key_template.format(val_slug) if "{}" in key_template else key_template
                    
                    # Save to SQLite only if not already saved
                    if fact not in self._facts:
                        self.db.add_or_update_insight(
                            category=category,
                            key=key,
                            value=fact,
                            importance=7
                        )
                        new_facts.append(fact)

        if new_facts:
            self._save()
        return new_facts

    def add_fact(self, fact: str, category: str = "User Profile"):
        """Manually add a fact to the profile."""
        key = re.sub(r'[^a-z0-9_]', '', fact.lower().replace(" ", "_"))[:30]
        self.db.add_or_update_insight(
            category=category,
            key=key,
            value=fact,
            importance=5
        )
        self._save()

    def get_system_context(self, query_text: Optional[str] = None) -> str:
        """Format saved facts to inject as context into LLM system prompts (RAG)."""
        if query_text:
            rows = self.db.get_relevant_insights(query_text)
        else:
            rows = self.db.get_all_insights(limit=15)
            
        if not rows:
            return ""

        facts_list = "\n".join(f"- {row['value']}" for row in rows)
        return (
            "\n\n--- USER PROFILE DETAILS (Extracted from chat context) ---\n"
            f"{facts_list}\n"
            "Use the details above to address the user by name or respect their stated preferences.\n"
            "--- End User Profile ---\n"
        )
