"""
OrchestraAI — Ollama Provider
=============================
Adapter for local Ollama server.
Handles text generation using local models.
"""

import time
import requests
from typing import Optional, List, Dict, Any

from .base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)

class OllamaProvider(BaseProvider):
    """Provider adapter for local Ollama service."""

    def __init__(self, host: str = "http://localhost:11434"):
        """
        Initialize the Ollama provider.

        Args:
            host: The Ollama server endpoint (default: http://localhost:11434)
        """
        self._host = host.rstrip("/")

    @property
    def name(self) -> str:
        return "Ollama"

    def generate_text(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate text using local Ollama chat API."""
        start = self._measure_latency()

        # Build messages payload
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if history:
            for turn in history:
                messages.append({"role": turn["role"], "content": turn["content"]})
                
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        try:
            url = f"{self._host}/api/chat"
            response = requests.post(url, json=payload, timeout=90)
            
            if response.status_code != 200:
                raise ProviderError("Ollama", f"Ollama returned status {response.status_code}: {response.text}")
                
            data = response.json()
            response_text = data.get("message", {}).get("content", "").strip()
            
            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="ollama",
                latency_ms=latency,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                finish_reason="stop",
            )

        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError("Ollama", f"Could not connect to Ollama at {self._host}. Ensure Ollama is running. Error: {e}")

    def health_check(self) -> bool:
        """Verify Ollama service is reachable and responsive."""
        try:
            response = requests.get(f"{self._host}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
