"""
OrchestraAI — Task Classifier
================================
The brain of the routing system. Uses Gemini 2.0 Flash to analyze incoming
user prompts and classify them into task categories. The classification
determines which model and provider will handle the request.

The classifier solves the "chicken and egg" problem by using the fastest,
cheapest model (Flash) to make routing decisions for the heavier models.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from .config import TaskType, api_keys, settings, MODELS, ProviderName
from .providers.gemini_provider import GeminiProvider
from .providers.groq_provider import GroqProvider
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

9. **general** — General conversation, greetings, questions that don't fit other categories, meta-questions about the AI itself.

## Rules:
- If the input contains a URL (starts with http:// or https://), classify as "web_scrape".
- If the input explicitly asks to create/generate/draw an image or visual, classify as "image_generation".
- If the input is asking to open/launch/run/start local applications, websites, schedule tasks/meetings, set reminders, check/read/reply/send emails or read inbox/messages, check calendar events, control system settings, or run shell/Python scripts, classify as "system_command".
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
    Classifies user input into task categories using Gemini 2.0 Flash.

    Also handles manual overrides via @provider prefixes and
    special command detection (e.g., /image, /scrape).
    """

    def __init__(self):
        """Initialize the classifier with Gemini, Groq, and Ollama clients."""
        gemini_key = api_keys.get_key(ProviderName.GEMINI)
        if gemini_key:
            self._provider = GeminiProvider(api_key=gemini_key)
        else:
            self._provider = None

        groq_key = api_keys.get_key(ProviderName.GROQ)
        if groq_key:
            self._groq_provider = GroqProvider(api_key=groq_key)
        else:
            self._groq_provider = None

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
            "@gemini": TaskType.DEEP_REASONING,   # Routes to Gemini 2.5 Pro
            "@groq": TaskType.FAST_UTILITY,        # Routes to Groq Llama
            "@cerebras": TaskType.CODE_GENERATION,  # Routes to Cerebras Llama (via fallback)
            "@sambanova": TaskType.DEEP_REASONING,  # Routes to SambaNova Llama 405B
            "@mistral": TaskType.CODE_GENERATION,    # Routes to Mistral Codestral
            "@cohere": TaskType.WEB_SCRAPE,          # Routes to Cohere Command R+
            "@ollama": TaskType.GENERAL,             # Routes to Local Ollama
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
        Use Gemini 2.0 Flash to classify the task with AI.
        Falls back to Groq Llama 3.3 if Gemini fails or is not configured.
        """
        if self._provider:
            try:
                result = self._provider.generate_text(
                    prompt=f"Classify this user input:\n\n{text}",
                    model_id=self._classifier_model,
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    max_tokens=200,
                    temperature=0.1,  # Low temp for consistency
                )
                return self._parse_classification(result.content, text)
            except Exception:
                # Fall through to Groq if Gemini fails
                pass

        if self._groq_provider:
            try:
                result = self._groq_provider.generate_text(
                    prompt=f"Classify this user input:\n\n{text}",
                    model_id="llama-3.3-70b-versatile",
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    max_tokens=200,
                    temperature=0.1,
                )
                return self._parse_classification(result.content, text)
            except Exception:
                # Fall through to default if Groq also fails
                pass

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
                # Fall through to default if Ollama also fails
                pass

        return ClassificationResult(
            task_type=TaskType.GENERAL,
            confidence=0.3,
            reasoning="Both Gemini and Groq classifiers failed/unavailable — defaulting to general.",
            raw_input=text,
        )

    def _parse_classification(self, response: str, original_input: str) -> ClassificationResult:
        """
        Parse the JSON response from the classifier model.

        Handles edge cases like markdown-wrapped JSON, extra text, etc.
        """
        try:
            # Robustly extract balanced JSON block from the response
            json_str = None
            start = response.find('{')
            if start != -1:
                brace_count = 0
                in_string = False
                escape = False
                for i in range(start, len(response)):
                    char = response[i]
                    if escape:
                        escape = False
                        continue
                    if char == '\\':
                        escape = True
                        continue
                    if char == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = response[start:i+1]
                                break
            
            if not json_str:
                raise ValueError("No JSON found in response")

            # Robustly parse JSON (handling literal newlines and invalid escapes inside string values)
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                cleaned = []
                in_string = False
                i = 0
                n = len(json_str)
                while i < n:
                    char = json_str[i]
                    if not in_string:
                        if char == '"':
                            in_string = True
                        cleaned.append(char)
                        i += 1
                        continue
                    
                    if char == '"':
                        in_string = False
                        cleaned.append(char)
                        i += 1
                        continue
                    
                    if char == '\\':
                        # Check for valid escape
                        if i + 1 < n:
                            next_char = json_str[i + 1]
                            if next_char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                                cleaned.append('\\')
                                cleaned.append(next_char)
                                i += 2
                                continue
                            elif next_char == 'u':
                                if i + 5 < n and all(c in '0123456789abcdefABCDEF' for c in json_str[i+2:i+6]):
                                    cleaned.append('\\')
                                    cleaned.append('u')
                                    cleaned.extend(json_str[i+2:i+6])
                                    i += 6
                                    continue
                        # Not a valid escape sequence: escape the backslash itself
                        cleaned.append('\\\\')
                        i += 1
                    elif char in ('\n', '\r'):
                        cleaned.append('\\n')
                        i += 1
                    else:
                        cleaned.append(char)
                        i += 1
                data = json.loads("".join(cleaned))

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
