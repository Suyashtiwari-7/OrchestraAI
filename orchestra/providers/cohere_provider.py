"""
OrchestraAI — Cohere Provider
===============================
Adapter for Cohere API. Connects to Cohere's V2 Chat API using
direct HTTP requests via httpx.
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


class CohereProvider(BaseProvider):
    """Provider adapter for Cohere API (Command R+)."""

    def __init__(self, api_key: str):
        """
        Initialize the Cohere provider.

        Args:
            api_key: Cohere developer portal API key.
        """
        if not api_key:
            raise AuthenticationError("Cohere")
        self._api_key = api_key
        self._url = "https://api.cohere.com/v2/chat"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "Cohere"

    def generate_text(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> GenerationResult:
        """
        Generate text using Cohere's V2 Chat endpoint.
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

            # Request payload (Cohere V2 format)
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
                raise AuthenticationError("Cohere")
            elif response.status_code == 429:
                raise RateLimitError("Cohere")
            elif response.status_code != 200:
                raise ProviderError("Cohere", f"HTTP Error {response.status_code}: {response.text}")

            data = response.json()
            
            # Extract response text from Cohere V2 structure: data["message"]["content"][0]["text"]
            message_obj = data.get("message", {})
            content_list = message_obj.get("content", [])
            
            response_text = ""
            if content_list and len(content_list) > 0:
                response_text = content_list[0].get("text", "")

            if not response_text:
                raise ProviderError("Cohere", "Empty response from model.")

            # Extract usage
            usage = data.get("usage", {})
            tokens = usage.get("tokens", {})
            input_tokens = tokens.get("input_tokens", 0)
            output_tokens = tokens.get("output_tokens", 0)

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="cohere",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=data.get("finish_reason", "COMPLETE"),
            )

        except httpx.RequestError as e:
            raise ProviderError("Cohere", f"Connection error: {e}")
        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("Cohere", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test Cohere connectivity with a minimal request."""
        try:
            payload = {
                "model": "command-r",
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
