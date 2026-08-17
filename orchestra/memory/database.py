"""
OrchestraAI — SQLite Database Memory Engine
============================================
Manages local SQLite database for conversation storage, auto-purging,
and dynamic user profile insights (Local RAG).
"""

import os
import re
import sqlite3
import contextlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..config import settings

logger = logging.getLogger("orchestra.memory.database")

class MemoryDatabase:
    """Manages SQLite connection, schema, and queries for DARKI."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.project_root / "output" / "darki_memory.db"
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        """Get a thread-safe connection to the SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database tables and run the 30-day chat purge."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 1. Create chats table with full metadata support
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        model_used TEXT DEFAULT '',
                        provider TEXT DEFAULT '',
                        task_type TEXT DEFAULT '',
                        keep INTEGER DEFAULT 0,
                        processed_for_insights INTEGER DEFAULT 0
                    )
                """)

                # 1b. Migration: add processed_for_insights column to existing DBs
                try:
                    cursor.execute("ALTER TABLE chats ADD COLUMN processed_for_insights INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                # 2. Create insights table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS insights (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        importance INTEGER DEFAULT 5,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(category, key)
                    )
                """)

                # 3. Create connected relationships graph table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS relationships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        relation TEXT NOT NULL,
                        target TEXT NOT NULL,
                        details TEXT DEFAULT '',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(source, relation, target)
                    )
                """)
                conn.commit()
                logger.info("[+] SQLite database schema verified with connected memory graph.")
            
                # 4. Auto-purge chat history older than 30 days
                self.purge_old_history(days=30)
            
            except Exception as e:
                logger.error(f"[!] Database initialization failed: {e}")

    def add_relationship(self, source: str, relation: str, target: str, details: str = ""):
        """Add or update an entity relationship in the connected memory graph."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO relationships (source, relation, target, details, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(source, relation, target) DO UPDATE SET
                        details = excluded.details,
                        updated_at = CURRENT_TIMESTAMP
                """, (source.strip().lower(), relation.strip().lower(), target.strip().lower(), details.strip()))
                conn.commit()
                logger.info(f"[Graph] Connected: ({source}) -> [{relation}] -> ({target})")
            except Exception as e:
                logger.error(f"[!] Error adding graph relationship: {e}")

    def query_connected_graph(self, entity: str, depth: int = 2) -> List[Dict[str, str]]:
        """
        Traverse the connected memory graph starting from an entity up to N hops.
        Connects the dots (e.g. Yash -> College Friend -> Assignment -> Monday).
        """
        connections = []
        visited = set()
        to_visit = [entity.strip().lower()]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _ in range(depth):
                if not to_visit:
                    break
                current_nodes = list(to_visit)
                to_visit.clear()

                for node in current_nodes:
                    if node in visited:
                        continue
                    visited.add(node)

                    try:
                        cursor.execute("""
                            SELECT source, relation, target, details
                            FROM relationships
                            WHERE source = ? OR target = ?
                        """, (node, node))
                        rows = cursor.fetchall()
                        for r in rows:
                            src, rel, tgt, det = r["source"], r["relation"], r["target"], r["details"]
                            connections.append({
                                "source": src,
                                "relation": rel,
                                "target": tgt,
                                "details": det,
                            })
                            other = tgt if src == node else src
                            if other not in visited:
                                to_visit.append(other)
                    except Exception as e:
                        logger.error(f"[!] Graph query error: {e}")

        return connections

    def purge_old_history(self, days: int = 30):
        """Auto-deletes raw chat logs older than the specified number of days, unless kept."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM chats WHERE datetime(timestamp) < datetime('now', ?) AND keep = 0",
                    (f"-{days} days",)
                )
                deleted_rows = cursor.rowcount
                conn.commit()
                if deleted_rows > 0:
                    logger.info(f"[+] Purged {deleted_rows} old chat log entries older than {days} days.")
            except Exception as e:
                logger.error(f"[!] Error purging old chat logs: {e}")

    def add_chat_message(self, role: str, content: str, timestamp: str, model_used: str = "", provider: str = "", task_type: str = "", keep: int = 0):
        """Add a chat message (user or assistant) with metadata to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO chats (timestamp, role, content, model_used, provider, task_type, keep) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (timestamp, role, content, model_used, provider, task_type, keep)
                )
                conn.commit()
            except Exception as e:
                logger.error(f"[!] Error saving chat message: {e}")

    def get_recent_chats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent chats for context window memory."""
        messages = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT timestamp, role, content, model_used, provider, task_type, keep FROM chats ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                # Reverse to get chronological order
                for row in reversed(rows):
                    messages.append({
                        "timestamp": row["timestamp"],
                        "role": row["role"],
                        "content": row["content"],
                        "model_used": row["model_used"],
                        "provider": row["provider"],
                        "task_type": row["task_type"],
                        "keep": bool(row["keep"])
                    })
            except Exception as e:
                logger.error(f"[!] Error loading chat memory: {e}")
        return messages

    def add_or_update_insight(self, category: str, key: str, value: str, importance: int = 5):
        """Insert a new insight or update an existing one under a category/key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO insights (category, key, value, importance, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value=excluded.value,
                        importance=excluded.importance,
                        updated_at=CURRENT_TIMESTAMP
                """, (category.strip(), key.strip(), value.strip(), importance))
                conn.commit()
                logger.info(f"[+] Insight saved/updated: [{category}] {key} -> {value}")
            except Exception as e:
                logger.error(f"[!] Error saving insight: {e}")

    def get_all_insights(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all saved insights sorted by category and key."""
        insights = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT category, key, value, importance FROM insights ORDER BY importance DESC, category, key LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                for r in rows:
                    insights.append({
                        "category": r["category"],
                        "key": r["key"],
                        "value": r["value"],
                        "importance": r["importance"]
                    })
            except Exception as e:
                logger.error(f"[!] Error reading all insights: {e}")
        return insights

    def save_insights_batch(self, insights: List[Dict[str, Any]]):
        """Save a batch of extracted user insights with ON CONFLICT UPDATE."""
        if not insights:
            return
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                for item in insights:
                    cat = item.get("category", "GENERAL").strip()
                    k = item.get("key", "").strip().lower()
                    v = item.get("value", "").strip()
                    imp = int(item.get("importance", 5))
                    
                    if not k or not v:
                        continue
                        
                    cursor.execute("""
                        INSERT INTO insights (category, key, value, importance, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(category, key) DO UPDATE SET
                            value = excluded.value,
                            importance = excluded.importance,
                            updated_at = CURRENT_TIMESTAMP
                    """, (cat, k, v, imp))
                conn.commit()
                logger.info(f"[+] Saved/Updated batch of {len(insights)} user profile insights.")
            except Exception as e:
                logger.error(f"[!] Error saving insights batch: {e}")

    def get_relevant_insights(self, query_text: str) -> List[Dict[str, Any]]:
        """
        Queries insights and connected graph using conceptual associative matching (Local RAG).
        """
        words = re.findall(r'\b\w{3,20}\b', query_text.lower())
        stop_words = {
            "what", "where", "when", "which", "your", "that", "this", "there", 
            "their", "about", "write", "print", "explain", "code", "script", 
            "create", "open", "file", "make", "tell"
        }
        keywords = [w for w in words if w not in stop_words]

        # Conceptual synonyms expansion (Smart Associative Memory)
        synonym_map = {
            "machine": ["laptop", "pc", "ideapad", "computer", "system"],
            "laptop": ["machine", "pc", "ideapad", "computer"],
            "friend": ["buddy", "pal", "yash", "rahul", "mate"],
            "college": ["university", "assignment", "project", "campus", "exam"],
            "job": ["interview", "resume", "company", "career", "salary", "ctc"],
        }
        expanded_keywords = set(keywords)
        for kw in keywords:
            if kw in synonym_map:
                expanded_keywords.update(synonym_map[kw])
        
        if not expanded_keywords:
            return self.get_all_insights(limit=10)

        results = []
        
        # 1. Search Relational Insights
        where_clauses = []
        params = []
        for kw in expanded_keywords:
            where_clauses.append("value LIKE ? OR key LIKE ? OR category LIKE ?")
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
            
        query = f"""
            SELECT category, key, value, importance 
            FROM insights 
            WHERE {" OR ".join(where_clauses)}
            ORDER BY importance DESC
            LIMIT 15
        """
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                for r in rows:
                    results.append({
                        "category": r["category"],
                        "key": r["key"],
                        "value": r["value"],
                        "importance": r["importance"]
                    })
            except Exception as e:
                logger.error(f"[!] Error searching insights: {e}")

        # 2. Search Connected Graph for Multi-Hop Associations
        for kw in keywords:
            graph_facts = self.query_connected_graph(kw, depth=2)
            for gf in graph_facts:
                fact_str = f"({gf['source'].title()}) is {gf['relation']} ({gf['target'].title()}) {gf['details']}".strip()
                results.append({
                    "category": "CONNECTED_GRAPH",
                    "key": f"{gf['source']}_{gf['relation']}",
                    "value": fact_str,
                    "importance": 8
                })

        if not results:
            return self.get_all_insights(limit=10)
            
        return results

    def delete_chat_turn(self, timestamp: str) -> bool:
        """Delete a user chat message and its corresponding assistant response by timestamp."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Find the row id of the user message matching the timestamp
                cursor.execute("SELECT id FROM chats WHERE role = 'user' AND timestamp = ?", (timestamp,))
                row = cursor.fetchone()
                if not row:
                    return False
                user_id = row["id"]
            
                # Delete user message
                cursor.execute("DELETE FROM chats WHERE id = ?", (user_id,))
            
                # Delete corresponding assistant message
                cursor.execute("DELETE FROM chats WHERE id = (SELECT id FROM chats WHERE id > ? AND role = 'assistant' ORDER BY id ASC LIMIT 1)", (user_id,))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"[!] Error deleting chat turn: {e}")
                return False

    def toggle_chat_keep(self, timestamp: str) -> Optional[bool]:
        """Toggle the keep status for a user message and its corresponding assistant response."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id, keep FROM chats WHERE role = 'user' AND timestamp = ?", (timestamp,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_id = row["id"]
                new_keep = 0 if row["keep"] else 1
            
                cursor.execute("UPDATE chats SET keep = ? WHERE id = ? OR id = (SELECT id FROM chats WHERE id > ? AND role = 'assistant' ORDER BY id ASC LIMIT 1)", (new_keep, user_id, user_id))
                conn.commit()
                return bool(new_keep)
            except Exception as e:
                logger.error(f"[!] Error toggling keep status: {e}")
                return None

    def clear_chats(self):
        """Clear all records from the chats table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM chats")
                conn.commit()
            except Exception as e:
                logger.error(f"[!] Error clearing chats: {e}")

    # ============================================
    # Batch Insight Extraction Support
    # ============================================

    def get_unprocessed_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user-assistant message pairs that haven't been processed for insights yet."""
        messages = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id, role, content FROM chats WHERE processed_for_insights = 0 ORDER BY id ASC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                for row in rows:
                    messages.append({
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"],
                    })
            except Exception as e:
                logger.error(f"[!] Error getting unprocessed messages: {e}")
        return messages

    def mark_messages_processed(self, ids: List[int]):
        """Mark a batch of message IDs as processed for insights."""
        if not ids:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                placeholders = ",".join("?" for _ in ids)
                cursor.execute(
                    f"UPDATE chats SET processed_for_insights = 1 WHERE id IN ({placeholders})",
                    ids
                )
                conn.commit()
                logger.info(f"[+] Marked {len(ids)} messages as processed for insights.")
            except Exception as e:
                logger.error(f"[!] Error marking messages as processed: {e}")
