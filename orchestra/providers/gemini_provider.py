"""
OrchestraAI — Google Gemini Provider
======================================
Adapter for Google's Gemini API via the official google-genai SDK.
Handles both text generation (Gemini 2.5 Pro / 2.0 Flash) and
image generation (Imagen 3).
"""

import io
import time
from typing import Optional

from google import genai
from google.genai import types as genai_types

from .base import (
    BaseProvider,
    GenerationResult,
    ImageResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)


class GeminiProvider(BaseProvider):
    """Provider adapter for Google Gemini API."""

    def __init__(self, api_key: str):
        """
        Initialize the Gemini provider.

        Args:
            api_key: Google AI Studio API key.
        """
        if not api_key:
            raise AuthenticationError("Gemini")
        self._api_key = api_key
        self._client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return "Gemini"

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
        Generate text using a Gemini model.

        Uses the google-genai SDK's generate_content method with
        proper configuration for system instructions and generation params.
        """
        start = self._measure_latency()

        try:
            # Build the contents list from history + current prompt
            contents = []
            if history:
                for turn in history:
                    role = "user" if turn["role"] == "user" else "model"
                    contents.append(
                        genai_types.Content(
                            role=role,
                            parts=[genai_types.Part(text=turn["content"])],
                        )
                    )
            # Add the current user prompt
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=prompt)],
                )
            )

            # Build generation config
            gen_config = genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            # Add system instruction if provided
            if system_prompt:
                gen_config.system_instruction = system_prompt

            # Make the API call
            response = self._client.models.generate_content(
                model=model_id,
                contents=contents,
                config=gen_config,
            )

            # Extract response text
            response_text = ""
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        response_text += part.text

            if not response_text:
                raise ProviderError("Gemini", "Empty response from model.")

            # Extract usage metadata
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            latency = self._calc_latency(start)

            return GenerationResult(
                content=response_text,
                model_used=model_id,
                provider="gemini",
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=str(
                    response.candidates[0].finish_reason
                ) if response.candidates else "unknown",
            )

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "resource_exhausted" in error_str:
                raise RateLimitError("Gemini")
            elif "401" in error_str or "403" in error_str or "invalid" in error_str:
                raise AuthenticationError("Gemini")
            elif isinstance(e, (ProviderError, RateLimitError, AuthenticationError)):
                raise
            else:
                raise ProviderError("Gemini", f"API error: {e}")

    def generate_image(self, prompt: str, model_id: str) -> ImageResult:
        """
        Generate an image using Google Imagen 3.

        Uses the dedicated generate_images endpoint for high-quality
        text-to-image generation.
        """
        try:
            response = self._client.models.generate_images(
                model=model_id,
                prompt=prompt,
                config=genai_types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                ),
            )

            if not response.generated_images:
                raise ProviderError("Gemini", "No image was generated. The prompt may have been blocked by safety filters.")

            # Get the raw image bytes
            image = response.generated_images[0].image
            image_bytes = image._image_bytes if hasattr(image, '_image_bytes') else None

            # Fallback: try to save to buffer and read
            if not image_bytes:
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

            return ImageResult(
                image_data=image_bytes,
                mime_type="image/png",
                model_used=model_id,
                provider="gemini",
                prompt=prompt,
            )

        except Exception as e:
            if isinstance(e, (ProviderError, RateLimitError)):
                raise
            error_str = str(e).lower()
            if "429" in error_str or "resource_exhausted" in error_str:
                raise RateLimitError("Gemini")
            raise ProviderError("Gemini", f"Image generation error: {e}")

    def health_check(self) -> bool:
        """Test Gemini API connectivity with a minimal request."""
        try:
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Say 'OK' and nothing else.",
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.0,
                ),
            )
            return bool(response.candidates)
        except Exception:
            return False
