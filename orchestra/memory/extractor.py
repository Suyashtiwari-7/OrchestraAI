"""
OrchestraAI — Dynamic Insight Extractor
========================================
Extracts user preferences, traits, and facts from conversation history
using the LLM router and saves them to SQLite.

DESIGN: Runs as an idle-time background worker that processes batches of
unprocessed messages every N minutes, NOT on every individual message.
This eliminates the 1-2s latency penalty that previously slowed every chat.
"""

import json
import logging
import threading
from typing import Optional
from .database import MemoryDatabase
from ..router import ModelRouter, ClassificationResult
from ..config import TaskType

logger = logging.getLogger("orchestra.memory.extractor")


class InsightExtractor:
    """Extracts long-term personalization facts from chat logs in the background."""

    # How often (in seconds) to check for unprocessed messages
    EXTRACTION_INTERVAL = 300  # 5 minutes

    def __init__(self, db: MemoryDatabase, router: ModelRouter):
        self.db = db
        self.router = router
        self._timer: Optional[threading.Timer] = None
        self._running = False

    def start_background_timer(self):
        """Start the recurring background extraction timer."""
        if self._running:
            return
        self._running = True
        logger.info(f"[*] Background insight extractor started (interval: {self.EXTRACTION_INTERVAL}s).")
        self._schedule_next()

    def stop(self):
        """Stop the background extraction timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("[*] Background insight extractor stopped.")

    def _schedule_next(self):
        """Schedule the next extraction run."""
        if not self._running:
            return
        self._timer = threading.Timer(self.EXTRACTION_INTERVAL, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        """Timer callback: run batch extraction, then schedule next tick."""
        try:
            self._run_batch_extraction()
        except Exception as e:
            logger.error(f"[!] Batch extraction tick failed: {e}")
        finally:
            self._schedule_next()

    def _run_batch_extraction(self):
        """
        Process all unprocessed chat messages in a single batch LLM call.
        Groups user-assistant message pairs and sends them for insight extraction.
        """
        unprocessed = self.db.get_unprocessed_messages(limit=40)
        if not unprocessed:
            logger.debug("[*] No unprocessed messages for insight extraction.")
            return

        # Collect IDs to mark as processed regardless of extraction success
        all_ids = [msg["id"] for msg in unprocessed]

        # Build conversation summary from unprocessed messages
        conversation_lines = []
        for msg in unprocessed:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Truncate very long messages to keep prompt manageable
            content = msg["content"][:500] if len(msg["content"]) > 500 else msg["content"]
            conversation_lines.append(f"{role_label}: {content}")

        if not conversation_lines:
            self.db.mark_messages_processed(all_ids)
            return

        conversation_text = "\n".join(conversation_lines)

        prompt = f"""You are a silent memory extraction agent for a personalized AI assistant.
Your job is to read the recent conversation turns and extract permanent facts, style preferences, project context, or user behavioral traits that are valuable for personalizing future responses.

Recent conversation:
{conversation_text}

Guidelines:
1. Be selective. Only extract details that have long-term value. Do NOT extract temporary requests (e.g. "show me the directory", "run this command").
2. Dynamically categorize the insights. Invent appropriate categories (e.g. "Work Habits", "Coding Style", "College Context", "Personal Info").
3. Assign an importance score (1-10) to each fact.
4. Detect conflict updates: If the user corrects a previous fact or has a new pattern, output it with the same category and key so it gets updated.
5. Output ONLY valid JSON in this exact structure:
{{
    "insights": [
        {{
            "category": "High-level Category",
            "key": "snake_case_parameter_name",
            "value": "Detail of the fact or preference",
            "importance": 8
        }}
    ]
}}
If no long-term insights are found, output an empty list:
{{
    "insights": []
}}
Do not add any markdown formatting, backticks, or extra text. Output raw JSON.
"""

        # Use FAST_UTILITY task type for lightweight extraction
        classification = ClassificationResult(
            task_type=TaskType.FAST_UTILITY,
            confidence=1.0,
            reasoning="Silent background batch memory insight extraction",
            raw_input=prompt
        )

        try:
            result, _ = self.router.route_text(
                prompt=prompt,
                classification=classification,
                system_prompt="You are a JSON parser that outputs ONLY raw JSON conforming strictly to the requested schema. No markdown."
            )

            # Clean and parse JSON
            content = result.content.strip()
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
            else:
                json_str = content

            data = json.loads(json_str)
            insights = data.get("insights", [])

            logger.info(f"[*] Batch extraction found {len(insights)} insights from {len(unprocessed)} messages.")

            for item in insights:
                category = item.get("category")
                key = item.get("key")
                value = item.get("value")
                importance = item.get("importance", 5)

                if category and key and value:
                    self.db.add_or_update_insight(
                        category=category,
                        key=key,
                        value=value,
                        importance=importance
                    )

            logger.info("[+] Background batch extraction complete.")

        except Exception as e:
            logger.error(f"[!] Error in batch memory extraction: {e}")

        finally:
            # Always mark messages as processed to avoid re-processing
            self.db.mark_messages_processed(all_ids)
