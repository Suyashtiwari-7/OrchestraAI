"""
OrchestraAI — HuggingFace Provider
==================================
Adapter for HuggingFace Inference API.
Handles text generation using HuggingFace hosted models.
"""

import time
import requests
from typing import Optional

from .base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)


class HuggingFaceProvider(BaseProvider):
    """Provider adapter for HuggingFace Inference API."""

    def __init__(self, api_token: str):
        """
        Initialize the HuggingFace provider.

        Args:
            api_token: HuggingFace API Token (User Access Token).
        """
        if not api_token:
            raise AuthenticationError("HuggingFace: Missing API Token.")
        self._api_token = api_token

    @property
    def name(self) -> str:
        return "HuggingFace"

    def generate_text(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate text using a HuggingFace Inference model."""
        start = self._measure_latency()

        headers = {"Authorization": f"Bearer {self._api_token}"}
        api_url = f"https://api-inference.huggingface.co/models/{model_id}"

        # Build prompt format
        formatted_prompt = ""
        if system_prompt:
            formatted_prompt += f"<system>\n{system_prompt}\n</system>\n"
        if history:
            for turn in history:
                role = turn["role"]
                content = turn["content"]
                formatted_prompt += f"<{role}>\n{content}\n</{role}>\n"
        formatted_prompt += f"<user>\n{prompt}\n</user>\n<assistant>\n"

        payload = {
            "inputs": formatted_prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            }
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 401:
                raise AuthenticationError("HuggingFace")
            elif response.status_code == 429:
                raise RateLimitError("HuggingFace")
            elif response.status_code != 200:
                raise ProviderError("HuggingFace", f"API returned status code {response.status_code}: {response.text}")

            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                response_text = data[0].get("generated_text", "").strip()
            elif isinstance(data, dict):
                response_text = data.get("generated_text", "").strip()
            else:
                response_text = str(data)

            # Strip any trailing assistant tags if the model repeated them
            if response_text.endswith("</assistant>"):
                response_text = response_text[:-12].strip()

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="huggingface",
                latency_ms=latency,
                input_tokens=0,
                output_tokens=0,
                finish_reason="stop",
            )

        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            raise ProviderError("HuggingFace", f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """Test authentication token exists."""
        return bool(self._api_token)
