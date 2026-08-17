"""
OrchestraAI — Task Classifier
================================
The brain of the routing system. Uses Groq's ultra-fast Llama 3.3 70B to
analyze incoming user prompts and classify them into task categories.
The classification determines which model and provider will handle the request.

The classifier solves the "chicken and egg" problem by using the fastest
model (Groq ~200ms) to make routing decisions for the heavier models.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from .config import TaskType, api_keys, settings, MODELS, ProviderName
from .providers.groq_provider import GroqProvider
from .providers.nvidia_provider import NvidiaProvider
from .providers.ollama_provider import OllamaProvider
from .providers.base import ProviderError


# ============================================
# Classification prompt — the core logic
# ============================================
CLASSIFIER_SYSTEM_PROMPT = """You are a task classifier for an AI routing system called OrchestraAI.
Your job is to analyze the user's input and classify it into EXACTLY ONE task category.

## Task Categories:

1. **deep_reasoning** — Complex analysis, mathematical proofs, multi-step logic, philosophical arguments, scientific explanations, detailed comparisons, research synthesis.

2. **code_generation** — Writing code, debugging code, code review, explaining code, writing algorithms, creating scripts, fixing errors, software architecture, database queries, API design.

3. **creative** — Creative writing, storytelling, brainstorming ideas, poetry, marketing copy, naming things, content creation, social media posts, jokes, role-playing.

4. **fast_utility** — Simple formatting, data extraction, translation, basic classification, converting formats (JSON to CSV, etc.), summarizing short text, spelling/grammar fixes, quick factual lookups, list generation.

5. **image_generation** — The user wants to CREATE or GENERATE an image, picture, illustration, artwork, photo, logo, icon, or visual content. Keywords: "draw", "create an image", "generate a picture", "make a logo", "design a", "visualize".

6. **web_scrape** — The user provides a URL and wants its content fetched, scraped, summarized, or analyzed. Look for URLs (http/https links) in the input.

7. **system_command** — The user wants to trigger local actions on their machine, launch apps, schedule meetings/events, set reminders, set timers, control system settings (volume, brightness), perform file operations, check/read/reply/send emails and inbox messages, check calendar items, or automate tasks (e.g. play music, send/read/check emails, schedule tasks). Keywords: "open", "launch", "run", "start", "schedule", "remind", "set volume", "delete file", "play", "send email", "read email", "check email", "inbox", "mail".

8. **web_search** — The user asks about current events, news, real-time information, weather, live stock/crypto prices, or questions that require searching the internet/live web for the latest info. Keywords: "news", "current", "weather", "latest", "today", "live price", "search for".

9. **agentic_chain** — Multi-step workflows requiring sequential actions, research combined with file-creation, multi-stage scripting, or complex goals where information needs to be retrieved first (via search or scrape) and then operated on (written to file, sent as email, etc.). Keywords: "first search X, then create Y", "find Z and write to file", "research and compile", "and then".

10. **general** — General conversation, greetings, questions that don't fit other categories, meta-questions about the AI itself.

## Rules:
- If the input requires a complex series of steps, a compound command, opens an application AND performs another action in it (e.g., "open notepad and write Hello World"), OR involves sending messages in chat apps (e.g. Teams, Slack, WhatsApp) where account clarification might be needed, classify as "agentic_chain".
- If the input contains a URL (starts with http:// or https://), classify as "web_scrape".
- If the input explicitly asks to create/generate/draw an image or visual, classify as "image_generation".
- If the input is asking to open/launch/run/start local applications (WITHOUT typing), schedule tasks/meetings, set reminders, check/read/reply/send emails via Outlook, check calendar events, control system settings, or run shell/Python scripts, classify as "system_command".
- If the input requires real-time information, current news, weather, live data, or queries starting with "search", classify as "web_search".
- If unsure between categories, prefer "general".
- The confidence score should reflect how certain you are (0.0 to 1.0).

## Output Format:
You MUST respond with ONLY a valid JSON object, no markdown, no explanation:
{"task_type": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}
"""


@dataclass
class ClassificationResult:
    """Result of classifying a user's task."""
    task_type: TaskType
    confidence: float
    reasoning: str
    was_forced: bool = False   # True if user used @provider override
    raw_input: str = ""


class TaskClassifier:
    """
    Classifies user input into task categories using Groq Llama 3.3 70B.

    Also handles manual overrides via @provider prefixes and
    special command detection (e.g., /image, /scrape).
    """

    def __init__(self):
        """Initialize the classifier with Groq (primary), NVIDIA NIM, and Ollama clients."""
        # Primary: Groq (ultra-fast classification <200ms)
        groq_key = api_keys.get_key(ProviderName.GROQ)
        if groq_key:
            self._groq_provider = GroqProvider(api_key=groq_key)
        else:
            self._groq_provider = None

        # Fallback: NVIDIA NIM
        nvidia_key = api_keys.get_key(ProviderName.NVIDIA_NIM)
        if nvidia_key:
            self._nvidia_provider = NvidiaProvider(api_key=nvidia_key)
        else:
            self._nvidia_provider = None

        # Offline fallback: Ollama
        ollama_host = api_keys.get_key(ProviderName.OLLAMA)
        if ollama_host:
            self._ollama_provider = OllamaProvider(host=ollama_host)
        else:
            self._ollama_provider = None

        self._classifier_model = MODELS[settings.classifier_model].model_id

    def classify(self, user_input: str) -> ClassificationResult:
        """
        Classify the user's input into a task type.

        Processing order:
        1. Check for special commands (/image, /scrape, /help, etc.)
        2. Check for @provider overrides (@gemini, @groq, @cerebras)
        3. Check for URL patterns (auto-detect web_scrape)
        4. Use Gemini Flash for AI-powered classification

        Args:
            user_input: The raw text from the user.

        Returns:
            ClassificationResult with the detected task type and confidence.
        """
        cleaned = user_input.strip()

        # --- Step 1: Special commands ---
        command_result = self._check_commands(cleaned)
        if command_result:
            return command_result

        # --- Step 2: Provider overrides ---
        override_result = self._check_overrides(cleaned)
        if override_result:
            return override_result

        # --- Step 3: URL pattern detection ---
        if self._contains_url(cleaned):
            return ClassificationResult(
                task_type=TaskType.WEB_SCRAPE,
                confidence=0.95,
                reasoning="Input contains a URL — routing to web scraper.",
                raw_input=cleaned,
            )

        # --- Step 4: AI-powered classification ---
        return self._ai_classify(cleaned)

    def _check_commands(self, text: str) -> Optional[ClassificationResult]:
        """Check for slash commands that map directly to task types."""
        lower = text.lower()

        if lower.startswith("/image "):
            return ClassificationResult(
                task_type=TaskType.IMAGE_GENERATION,
                confidence=1.0,
                reasoning="User used /image command.",
                raw_input=text,
            )

        if lower.startswith("/scrape "):
            return ClassificationResult(
                task_type=TaskType.WEB_SCRAPE,
                confidence=1.0,
                reasoning="User used /scrape command.",
                raw_input=text,
            )

        if lower.startswith("/system ") or lower.startswith("/open "):
            cmd = "/system" if lower.startswith("/system ") else "/open"
            return ClassificationResult(
                task_type=TaskType.SYSTEM_COMMAND,
                confidence=1.0,
                reasoning=f"User used {cmd} command.",
                raw_input=text,
            )

        if lower.startswith("/search "):
            return ClassificationResult(
                task_type=TaskType.WEB_SEARCH,
                confidence=1.0,
                reasoning="User used /search command.",
                raw_input=text,
            )

        return None

    def _check_overrides(self, text: str) -> Optional[ClassificationResult]:
        """
        Check for @provider prefixes that force a specific provider.

        Examples:
            @gemini What is quantum computing?
            @groq Format this JSON
            @cerebras Explain merge sort
        """
        override_map = {
            "@nvidia": TaskType.DEEP_REASONING,
            "@groq": TaskType.FAST_UTILITY,
            "@ollama": TaskType.GENERAL,
        }

        lower = text.lower()
        for prefix, task_type in override_map.items():
            if lower.startswith(prefix):
                return ClassificationResult(
                    task_type=task_type,
                    confidence=1.0,
                    reasoning=f"User forced routing with {prefix} override.",
                    was_forced=True,
                    raw_input=text[len(prefix):].strip(),
                )

        return None

    def _contains_url(self, text: str) -> bool:
        """Check if the text contains an HTTP/HTTPS URL."""
        url_pattern = r'https?://[^\s<>\"\']+|www\.[^\s<>\"\']+' 
        return bool(re.search(url_pattern, text))

    def _ai_classify(self, text: str) -> ClassificationResult:
        """
        Use Groq Llama 3.3 70B to classify the task with AI.
        Falls back to NVIDIA NIM, then Ollama if Groq fails.
        """
        # Primary: Groq (ultra-fast)
        if self._groq_provider:
            try:
                result = self._groq_provider.generate_text(
                    prompt=f"Classify this user input:\n\n{text}",
                    model_id=self._classifier_model,
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    max_tokens=200,
                    temperature=0.1,
                )
                return self._parse_classification(result.content, text)
            except Exception:
                pass

        # Fallback: NVIDIA NIM
        if self._nvidia_provider:
            try:
                result = self._nvidia_provider.generate_text(
                    prompt=f"Classify this user input:\n\n{text}",
                    model_id="meta/llama-3.3-70b-instruct",
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    max_tokens=200,
                    temperature=0.1,
                )
                return self._parse_classification(result.content, text)
            except Exception:
                pass

        # Offline fallback: Ollama
        if self._ollama_provider:
            try:
                result = self._ollama_provider.generate_text(
                    prompt=f"Classify this user input:\n\n{text}",
                    model_id=api_keys.ollama_model or "llama3.2",
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    max_tokens=200,
                    temperature=0.1,
                )
                return self._parse_classification(result.content, text)
            except Exception:
                pass

        return ClassificationResult(
            task_type=TaskType.GENERAL,
            confidence=0.3,
            reasoning="All classifiers (Groq, NVIDIA NIM, Ollama) failed/unavailable — defaulting to general.",
            raw_input=text,
        )

    def _parse_classification(self, response: str, original_input: str) -> ClassificationResult:
        """
        Parse the JSON response from the classifier model.

        Handles edge cases like markdown-wrapped JSON, extra text, etc.
        """
        try:
            from .utils.json_utils import extract_json
            data = extract_json(response)

            # Map the task type string to enum
            task_type_str = data.get("task_type", "general").lower()
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                task_type = TaskType.GENERAL

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

            reasoning = data.get("reasoning", "Classified by AI.")

            return ClassificationResult(
                task_type=task_type,
                confidence=confidence,
                reasoning=reasoning,
                raw_input=original_input,
            )

        except (json.JSONDecodeError, ValueError, KeyError):
            return ClassificationResult(
                task_type=TaskType.GENERAL,
                confidence=0.4,
                reasoning="Could not parse classifier response — defaulting to general.",
                raw_input=original_input,
            )
