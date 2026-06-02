"""
OrchestraAI — Groq Provider
=============================
Adapter for Groq's ultra-fast LPU inference API via the official groq SDK.
Handles text generation with Llama, Qwen, and DeepSeek models.
"""

import time
from typing import Optional

from groq import Groq
from groq import (
    RateLimitError as GroqRateLimitError,
    AuthenticationError as GroqAuthError,
    APIError as GroqAPIError,
)

from .base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)


class GroqProvider(BaseProvider):
    """Provider adapter for Groq API (Llama, Qwen, DeepSeek)."""

    def __init__(self, api_key: str):
        """
        Initialize the Groq provider.

        Args:
            api_key: Groq console API key.
        """
        if not api_key:
            raise AuthenticationError("Groq")
        self._api_key = api_key
        self._client = Groq(api_key=api_key)

    @property
    def name(self) -> str:
        return "Groq"

    def generate_text(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate text using a Groq-hosted model.

        Groq uses the standard OpenAI chat completions format with
        messages array (system, user, assistant roles).
        """
        start = self._measure_latency()

        try:
            # Build messages array
            messages = []

            # System prompt
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt,
                })

            # Conversation history
            if history:
                for turn in history:
                    messages.append({
                        "role": turn["role"],
                        "content": turn["content"],
                    })

            # Current user prompt
            messages.append({
                "role": "user",
                "content": prompt,
            })

            # Make the API call
            response = self._client.chat.completions.create(
                model=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Extract response
            choice = response.choices[0]
            response_text = choice.message.content or ""

            if not response_text:
                raise ProviderError("Groq", "Empty response from model.")

            # Extract usage
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="groq",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=choice.finish_reason or "stop",
            )

        except GroqRateLimitError as e:
            raise RateLimitError("Groq")
        except GroqAuthError:
            raise AuthenticationError("Groq")
        except GroqAPIError as e:
            raise ProviderError("Groq", f"API error: {e}")
        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("Groq", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test Groq API connectivity with a minimal request."""
        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                temperature=0.0,
            )
            return bool(response.choices)
        except Exception:
            return False
