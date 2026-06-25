"""
OrchestraAI — Session Memory
================================
Manages conversation history for the current session.
Provides context to LLM calls so models can reference
prior turns in the conversation.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    keep: bool = False    # Whether this turn is kept permanently (exempt from auto-delete)


class SessionMemory:
    """
    Persistent conversation history for the current session.

    Manages a rolling window of conversation turns, keeping
    the most recent N turns to stay within token limits.
    Prunes history entries older than 15 days, unless marked as kept.
    """

    def __init__(self, max_turns: Optional[int] = None):
        """
        Initialize session memory.

        Args:
            max_turns: Maximum number of turns to keep. Uses config default if None.
        """
        self._history: list[MemoryEntry] = []
        self._max_turns = max_turns or settings.max_history_turns
        self._load_from_disk()

    @property
    def _history_file(self) -> Path:
        return settings.project_root / "output" / "history.json"

    def _load_from_disk(self):
        """Load conversation history from disk and prune entries older than 15 days."""
        try:
            file_path = self._history_file
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        entry = MemoryEntry(
                            role=item.get("role", ""),
                            content=item.get("content", ""),
                            model_used=item.get("model_used", ""),
                            provider=item.get("provider", ""),
                            task_type=item.get("task_type", ""),
                            timestamp=item.get("timestamp", datetime.now().isoformat()),
                            keep=item.get("keep", False)
                        )
                        self._history.append(entry)
                self._prune_old_entries()
                self._trim()
        except Exception:
            self._history = []

    def _save_to_disk(self):
        """Save conversation history to disk."""
        try:
            settings.ensure_dirs()
            file_path = self._history_file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = [
                {
                    "role": entry.role,
                    "content": entry.content,
                    "model_used": entry.model_used,
                    "provider": entry.provider,
                    "task_type": entry.task_type,
                    "timestamp": entry.timestamp,
                    "keep": entry.keep,
                }
                for entry in self._history
            ]
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _prune_old_entries(self):
        """Prune any entries older than 15 days, unless marked as kept."""
        now = datetime.now()
        fifteen_days_ago = now - timedelta(days=15)
        
        new_history = []
        for entry in self._history:
            try:
                # If marked as kept, always preserve it
                if getattr(entry, "keep", False):
                    new_history.append(entry)
                    continue
                    
                entry_time = datetime.fromisoformat(entry.timestamp)
                if entry_time >= fifteen_days_ago:
                    new_history.append(entry)
            except Exception:
                # Keep if timestamp format is not standard
                new_history.append(entry)
                
        self._history = new_history

    def add_user_message(self, content: str):
        """Record a user message."""
        self._history.append(MemoryEntry(
            role="user",
            content=content,
        ))
        self._prune_old_entries()
        self._trim()
        self._save_to_disk()

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
        self._prune_old_entries()
        self._trim()
        self._save_to_disk()

    def delete_turn(self, timestamp: str) -> bool:
        """
        Delete a specific turn (user message matching timestamp + following assistant message).
        """
        for idx, entry in enumerate(self._history):
            if entry.role == "user" and entry.timestamp == timestamp:
                # Remove user message
                self._history.pop(idx)
                # If next message is assistant, remove it too
                if idx < len(self._history) and self._history[idx].role == "assistant":
                    self._history.pop(idx)
                self._save_to_disk()
                return True
        return False

    def toggle_keep(self, timestamp: str) -> Optional[bool]:
        """
        Toggle keep flag on a specific user message and its corresponding assistant message.
        """
        toggled = None
        for idx, entry in enumerate(self._history):
            if entry.role == "user" and entry.timestamp == timestamp:
                entry.keep = not getattr(entry, "keep", False)
                toggled = entry.keep
                # Also toggle for the corresponding assistant response if it exists
                if idx + 1 < len(self._history) and self._history[idx+1].role == "assistant":
                    self._history[idx+1].keep = entry.keep
                self._save_to_disk()
                break
        return toggled

    def get_history(self) -> list[dict]:
        """
        Get conversation history in the format expected by providers.

        Returns:
            List of {"role": "user"|"assistant", "content": "..."} dicts.
        """
        self._prune_old_entries()
        return [
            {"role": entry.role, "content": entry.content}
            for entry in self._history
        ]

    def get_full_history(self) -> list[MemoryEntry]:
        """Get the full history with all metadata."""
        self._prune_old_entries()
        return list(self._history)

    def clear(self):
        """Clear all conversation history."""
        self._history.clear()
        self._save_to_disk()

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
                "keep": entry.keep,
            }
            for entry in self._history
        ]

        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return filepath
