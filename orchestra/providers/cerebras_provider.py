"""
OrchestraAI — Cerebras Provider
=================================
Adapter for Cerebras Cloud inference API.
Cerebras uses an OpenAI-compatible API, so we use the official openai SDK
with a custom base URL pointing to Cerebras endpoints.

Free tier: 1,000,000 tokens/day — excellent as a fallback provider.
"""

import time
from typing import Optional

from openai import OpenAI
from openai import (
    RateLimitError as OpenAIRateLimitError,
    AuthenticationError as OpenAIAuthError,
    APIError as OpenAIAPIError,
)

from .base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)


# Cerebras API base URL (OpenAI-compatible)
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"


class CerebrasProvider(BaseProvider):
    """Provider adapter for Cerebras Cloud API (OpenAI-compatible)."""

    def __init__(self, api_key: str):
        """
        Initialize the Cerebras provider.

        Args:
            api_key: Cerebras Cloud API key.
        """
        if not api_key:
            raise AuthenticationError("Cerebras")
        self._api_key = api_key
        self._client = OpenAI(
            api_key=api_key,
            base_url=CEREBRAS_BASE_URL,
        )

    @property
    def name(self) -> str:
        return "Cerebras"

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
        Generate text using a Cerebras-hosted model.

        Uses the OpenAI-compatible chat completions format since
        Cerebras exposes a standard /v1/chat/completions endpoint.
        """
        start = self._measure_latency()

        try:
            # Build messages array (same format as OpenAI)
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
                raise ProviderError("Cerebras", "Empty response from model.")

            # Extract usage
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="cerebras",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=choice.finish_reason or "stop",
            )

        except OpenAIRateLimitError:
            raise RateLimitError("Cerebras")
        except OpenAIAuthError:
            raise AuthenticationError("Cerebras")
        except OpenAIAPIError as e:
            raise ProviderError("Cerebras", f"API error: {e}")
        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("Cerebras", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test Cerebras API connectivity with a minimal request."""
        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                temperature=0.0,
            )
            return bool(response.choices)
        except Exception:
            return False
