"""
OrchestraAI — SambaNova Provider
==================================
Adapter for SambaNova Cloud API. Connects to SambaNova's OpenAI-compatible
endpoint using direct HTTP requests via httpx.
"""

import time
from typing import Optional
import httpx

from .base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)


class SambaNovaProvider(BaseProvider):
    """Provider adapter for SambaNova Cloud API (Llama 405B)."""

    def __init__(self, api_key: str):
        """
        Initialize the SambaNova provider.

        Args:
            api_key: SambaNova Cloud API key.
        """
        if not api_key:
            raise AuthenticationError("SambaNova")
        self._api_key = api_key
        self._url = "https://api.sambanova.ai/v1/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "SambaNova"

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
        Generate text using SambaNova's OpenAI-compatible endpoint.
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

            # Request payload
            payload = {
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Make direct HTTP POST call
            with httpx.Client() as client:
                response = client.post(
                    self._url,
                    headers=self._headers,
                    json=payload,
                    timeout=60.0
                )

            # Error handling based on status codes
            if response.status_code == 401 or response.status_code == 403:
                raise AuthenticationError("SambaNova")
            elif response.status_code == 429:
                raise RateLimitError("SambaNova")
            elif response.status_code != 200:
                raise ProviderError("SambaNova", f"HTTP Error {response.status_code}: {response.text}")

            data = response.json()
            
            # Extract response
            choice = data["choices"][0]
            response_text = choice["message"]["content"] or ""

            if not response_text:
                raise ProviderError("SambaNova", "Empty response from model.")

            # Extract usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="sambanova",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=choice.get("finish_reason", "stop"),
            )

        except httpx.RequestError as e:
            raise ProviderError("SambaNova", f"Connection error: {e}")
        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("SambaNova", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test SambaNova connectivity with a minimal request."""
        try:
            payload = {
                "model": "Meta-Llama-3.1-8B-Instruct",
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
                "temperature": 0.0,
            }
            with httpx.Client() as client:
                response = client.post(
                    self._url,
                    headers=self._headers,
                    json=payload,
                    timeout=5.0
                )
            return response.status_code == 200
        except Exception:
            return False
