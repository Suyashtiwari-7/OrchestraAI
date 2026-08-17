"""
OrchestraAI — Session Memory (SQLite-Backed)
==============================================
Manages conversation history using SQLite chats table to allow
auto-purge, metadata storage, and unified RAG database engine.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..config import settings
from .database import MemoryDatabase


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


class HistoryListWrapper:
    """Helper class to mock list behavior for backward compatibility in server.py error handling."""
    def __init__(self, memory_instance):
        self.memory_instance = memory_instance

    def __len__(self) -> int:
        return self.memory_instance.turn_count

    def pop(self, index=-1):
        self.memory_instance.revert_last_user_message()


class SessionMemory:
    """
    Persistent conversation history backed by SQLite database.
    
    Provides complete backward compatibility with the existing memory endpoints
    while storing all conversation logs inside orchestra's central database.
    """

    def __init__(self, max_turns: Optional[int] = None):
        """Initialize SQLite session memory."""
        self.db = MemoryDatabase()
        self._max_turns = max_turns or settings.max_history_turns

    @property
    def _history(self):
        """Backward compatibility helper for server.py error handlers."""
        return HistoryListWrapper(self)

    def revert_last_user_message(self):
        """Remove the last message if it was a user message (used for error recovery)."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id, role FROM chats ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if row and row["role"] == "user":
                    cursor.execute("DELETE FROM chats WHERE id = ?", (row["id"],))
                    conn.commit()
            except Exception:
                pass

    def add_user_message(self, content: str):
        """Record a user message."""
        timestamp = datetime.now().isoformat()
        self.db.add_chat_message(
            role="user",
            content=content,
            timestamp=timestamp,
            keep=0
        )

    def add_assistant_message(
        self,
        content: str,
        model_used: str = "",
        provider: str = "",
        task_type: str = "",
    ):
        """Record an assistant (model) response."""
        timestamp = datetime.now().isoformat()
        self.db.add_chat_message(
            role="assistant",
            content=content,
            timestamp=timestamp,
            model_used=model_used,
            provider=provider,
            task_type=task_type,
            keep=0
        )

    def delete_turn(self, timestamp: str) -> bool:
        """Delete a specific turn by its user message timestamp."""
        return self.db.delete_chat_turn(timestamp)

    def toggle_keep(self, timestamp: str) -> Optional[bool]:
        """Toggle keep/pinned flag for a specific chat turn."""
        return self.db.toggle_chat_keep(timestamp)

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history in the format expected by providers."""
        chats = self.db.get_recent_chats(limit=self._max_turns * 2)
        return [
            {"role": c["role"], "content": c["content"]}
            for c in chats
        ]

    def get_full_history(self, limit: int = 50) -> List[MemoryEntry]:
        """Get the full history with all metadata."""
        chats = self.db.get_recent_chats(limit=limit) # Retrieve a larger window for GUI history view
        entries = []
        for c in chats:
            entries.append(MemoryEntry(
                role=c["role"],
                content=c["content"],
                model_used=c["model_used"],
                provider=c["provider"],
                task_type=c["task_type"],
                timestamp=c["timestamp"],
                keep=c["keep"]
            ))
        return entries

    def clear(self):
        """Clear all conversation history."""
        self.db.clear_chats()

    @property
    def turn_count(self) -> int:
        """Number of turns in the conversation."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM chats")
            count = cursor.fetchone()[0]
        except Exception:
            pass
        finally:
            conn.close()
        return count

    def export_to_json(self, filepath: Optional[Path] = None) -> Path:
        """Export the conversation history to a JSON file."""
        if not filepath:
            settings.ensure_dirs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = settings.output_code_dir / f"conversation_{timestamp}.json"

        entries = self.get_full_history()
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
            for entry in entries
        ]

        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return filepath
