"""
OrchestraAI — Session Memory
================================
Manages conversation history for the current session.
Provides context to LLM calls so models can reference
prior turns in the conversation.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings


@dataclass
class MemoryEntry:
    """A single conversation turn."""
    role: str             # "user" or "assistant"
    content: str          # The text content
    model_used: str = ""  # Which model generated this (for assistant turns)
    provider: str = ""    # Which provider was used
    task_type: str = ""   # Classification result
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SessionMemory:
    """
    In-memory conversation history for the current session.

    Manages a rolling window of conversation turns, keeping
    the most recent N turns to stay within token limits.
    """

    def __init__(self, max_turns: Optional[int] = None):
        """
        Initialize session memory.

        Args:
            max_turns: Maximum number of turns to keep. Uses config default if None.
        """
        self._history: list[MemoryEntry] = []
        self._max_turns = max_turns or settings.max_history_turns

    def add_user_message(self, content: str):
        """Record a user message."""
        self._history.append(MemoryEntry(
            role="user",
            content=content,
        ))
        self._trim()

    def add_assistant_message(
        self,
        content: str,
        model_used: str = "",
        provider: str = "",
        task_type: str = "",
    ):
        """Record an assistant (model) response."""
        self._history.append(MemoryEntry(
            role="assistant",
            content=content,
            model_used=model_used,
            provider=provider,
            task_type=task_type,
        ))
        self._trim()

    def get_history(self) -> list[dict]:
        """
        Get conversation history in the format expected by providers.

        Returns:
            List of {"role": "user"|"assistant", "content": "..."} dicts.
        """
        return [
            {"role": entry.role, "content": entry.content}
            for entry in self._history
        ]

    def get_full_history(self) -> list[MemoryEntry]:
        """Get the full history with all metadata."""
        return list(self._history)

    def clear(self):
        """Clear all conversation history."""
        self._history.clear()

    @property
    def turn_count(self) -> int:
        """Number of turns in the conversation."""
        return len(self._history)

    def _trim(self):
        """Remove oldest turns if we exceed max_turns."""
        if len(self._history) > self._max_turns * 2:
            # Keep the last max_turns * 2 entries (user + assistant pairs)
            self._history = self._history[-(self._max_turns * 2):]

    def export_to_json(self, filepath: Optional[Path] = None) -> Path:
        """
        Export the conversation history to a JSON file.

        Args:
            filepath: Optional custom path. Defaults to output directory.

        Returns:
            Path to the exported file.
        """
        if not filepath:
            settings.ensure_dirs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = settings.output_code_dir / f"conversation_{timestamp}.json"

        data = [
            {
                "role": entry.role,
                "content": entry.content,
                "model_used": entry.model_used,
                "provider": entry.provider,
                "task_type": entry.task_type,
                "timestamp": entry.timestamp,
            }
            for entry in self._history
        ]

        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return filepath
