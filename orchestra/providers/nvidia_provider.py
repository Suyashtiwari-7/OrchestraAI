"""
OrchestraAI — NVIDIA NIM Provider
====================================
Adapter for NVIDIA NIM API (build.nvidia.com).
Uses the OpenAI-compatible API format to route to free cloud-hosted
models: Llama 3.3 70B, DeepSeek R1, and Nemotron.

NVIDIA NIM provides free-tier access to enterprise-grade models
via an OpenAI-compatible endpoint at integrate.api.nvidia.com/v1.
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


class NvidiaProvider(BaseProvider):
    """Provider adapter for NVIDIA NIM API (OpenAI-compatible)."""

    # NVIDIA NIM endpoint — OpenAI-compatible format
    BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, api_key: str):
        """
        Initialize the NVIDIA NIM provider.

        Args:
            api_key: NVIDIA NIM API key (starts with 'nvapi-').
                     Get one free at https://build.nvidia.com
        """
        if not api_key:
            raise AuthenticationError("NVIDIA NIM")
        self._api_key = api_key
        self._client = OpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )

    @property
    def name(self) -> str:
        return "NVIDIA NIM"

    def generate_text(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        image_data: Optional[bytes] = None,
    ) -> GenerationResult:
        """
        Generate text using an NVIDIA NIM-hosted model.

        NVIDIA NIM uses the standard OpenAI chat completions format,
        so we can reuse the openai SDK with a custom base_url.
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
                raise ProviderError("NVIDIA NIM", "Empty response from model.")

            # Extract usage
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="nvidia_nim",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=choice.finish_reason or "stop",
            )

        except OpenAIRateLimitError:
            raise RateLimitError("NVIDIA NIM")
        except OpenAIAuthError:
            raise AuthenticationError("NVIDIA NIM")
        except OpenAIAPIError as e:
            raise ProviderError("NVIDIA NIM", f"API error: {e}")
        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("NVIDIA NIM", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test NVIDIA NIM API connectivity with a minimal request."""
        try:
            response = self._client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                temperature=0.0,
            )
            return bool(response.choices)
        except Exception:
            return False
