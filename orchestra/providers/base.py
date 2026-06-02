"""
OrchestraAI — Base Provider
============================
Abstract base class that all LLM provider adapters must implement.
Ensures a consistent interface for text generation, image generation,
and health checks across Google Gemini, Groq, and Cerebras.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time


class ProviderError(Exception):
    """Base exception for all provider-related errors."""

    def __init__(self, provider: str, message: str, retriable: bool = False):
        self.provider = provider
        self.retriable = retriable
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    """Raised when the API returns a rate limit (429) error."""

    def __init__(self, provider: str, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__(
            provider,
            f"Rate limited. Retry after {retry_after}s" if retry_after else "Rate limited.",
            retriable=True,
        )


class AuthenticationError(ProviderError):
    """Raised when the API key is invalid or missing."""

    def __init__(self, provider: str):
        super().__init__(provider, "Invalid or missing API key.", retriable=False)


@dataclass
class GenerationResult:
    """Standardized result from any provider's generation call."""
    content: str                          # The generated text
    model_used: str                       # Actual model ID that responded
    provider: str                         # Provider name (gemini, groq, cerebras)
    latency_ms: float = 0.0              # Round-trip time in milliseconds
    input_tokens: int = 0                # Tokens consumed (input)
    output_tokens: int = 0               # Tokens consumed (output)
    finish_reason: str = "stop"          # Why generation stopped
    metadata: dict = field(default_factory=dict)  # Provider-specific extra data


@dataclass
class ImageResult:
    """Standardized result from image generation."""
    image_data: bytes                     # Raw image bytes
    mime_type: str = "image/png"          # MIME type of the image
    model_used: str = ""                  # Model that generated the image
    provider: str = ""                    # Provider name
    prompt: str = ""                      # Original prompt used


class BaseProvider(ABC):
    """
    Abstract base class for LLM API providers.

    All provider adapters (Gemini, Groq, Cerebras) must implement:
    - generate_text() for text completions
    - health_check() to verify API connectivity

    Optionally implement:
    - generate_image() for image generation (only Gemini supports this)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider."""
        ...

    @abstractmethod
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
        Generate text from the given prompt.

        Args:
            prompt: The user's input text.
            model_id: The specific model to use (e.g., 'gemini-2.5-pro').
            system_prompt: Optional system instruction to guide behavior.
            history: Optional list of prior conversation turns
                     [{"role": "user"|"assistant", "content": "..."}].
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).

        Returns:
            GenerationResult with the response content and metadata.

        Raises:
            RateLimitError: If the API rate limit is exceeded.
            AuthenticationError: If the API key is invalid.
            ProviderError: For any other API error.
        """
        ...

    def generate_image(self, prompt: str, model_id: str) -> ImageResult:
        """
        Generate an image from a text prompt.

        Only supported by providers with image generation capability (Gemini/Imagen).
        Other providers will raise NotImplementedError.

        Args:
            prompt: Text description of the image to generate.
            model_id: The image generation model to use.

        Returns:
            ImageResult with the raw image bytes and metadata.
        """
        raise NotImplementedError(
            f"{self.name} does not support image generation."
        )

    @abstractmethod
    def health_check(self) -> bool:
        """
        Test if the provider's API is reachable and the key is valid.

        Returns:
            True if the provider is healthy and ready to accept requests.
        """
        ...

    def _measure_latency(self):
        """Context-manager-style utility: call at start, returns elapsed ms."""
        return time.perf_counter()

    def _calc_latency(self, start_time: float) -> float:
        """Calculate elapsed time in milliseconds."""
        return (time.perf_counter() - start_time) * 1000
