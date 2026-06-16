"""
OrchestraAI — Model Router
============================
Routes classified tasks to the optimal provider and model.
Implements automatic fallback chains — if the primary model fails
(rate limit, timeout, API error), the router seamlessly retries
with the fallback model from a different provider.
"""

import time
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

from .config import (
    TaskType,
    ProviderName,
    MODELS,
    ROUTING_TABLE,
    api_keys,
    settings,
    ModelConfig,
)
from .classifier import ClassificationResult
from .providers.base import (
    BaseProvider,
    GenerationResult,
    ImageResult,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)
from .providers.gemini_provider import GeminiProvider
from .providers.groq_provider import GroqProvider
from .providers.cerebras_provider import CerebrasProvider
from .providers.sambanova_provider import SambaNovaProvider
from .providers.mistral_provider import MistralProvider
from .providers.cohere_provider import CohereProvider
from .providers.ollama_provider import OllamaProvider


console = Console()


@dataclass
class RoutingDecision:
    """Records the routing decision for transparency and logging."""
    task_type: TaskType
    primary_model: str
    primary_provider: str
    fallback_model: str
    fallback_provider: str
    used_fallback: bool = False
    model_actually_used: str = ""
    provider_actually_used: str = ""
    classification_confidence: float = 0.0
    classification_reasoning: str = ""


class ModelRouter:
    """
    Routes tasks to the optimal LLM provider based on classification.

    The router maintains a pool of provider instances and handles:
    - Selecting the right model based on task type
    - Automatic fallback when the primary provider fails
    - Retry logic with configurable delays
    - Transparent routing decisions for logging
    """

    def __init__(self):
        """Initialize the router with available provider instances."""
        self._providers: dict[ProviderName, Optional[BaseProvider]] = {}
        self._init_providers()

    def _init_providers(self):
        """
        Create provider instances for all configured API keys.

        Providers with missing or invalid keys are set to None
        and will be skipped during routing.
        """
        key_status = api_keys.validate()

        # Initialize Gemini
        if key_status.get(ProviderName.GEMINI):
            try:
                self._providers[ProviderName.GEMINI] = GeminiProvider(
                    api_key=api_keys.get_key(ProviderName.GEMINI)
                )
            except AuthenticationError:
                self._providers[ProviderName.GEMINI] = None
        else:
            self._providers[ProviderName.GEMINI] = None

        # Initialize Groq
        if key_status.get(ProviderName.GROQ):
            try:
                self._providers[ProviderName.GROQ] = GroqProvider(
                    api_key=api_keys.get_key(ProviderName.GROQ)
                )
            except AuthenticationError:
                self._providers[ProviderName.GROQ] = None
        else:
            self._providers[ProviderName.GROQ] = None

        # Initialize Cerebras
        if key_status.get(ProviderName.CEREBRAS):
            try:
                self._providers[ProviderName.CEREBRAS] = CerebrasProvider(
                    api_key=api_keys.get_key(ProviderName.CEREBRAS)
                )
            except AuthenticationError:
                self._providers[ProviderName.CEREBRAS] = None
        else:
            self._providers[ProviderName.CEREBRAS] = None

        # Initialize SambaNova
        if key_status.get(ProviderName.SAMBANOVA):
            try:
                self._providers[ProviderName.SAMBANOVA] = SambaNovaProvider(
                    api_key=api_keys.get_key(ProviderName.SAMBANOVA)
                )
            except AuthenticationError:
                self._providers[ProviderName.SAMBANOVA] = None
        else:
            self._providers[ProviderName.SAMBANOVA] = None

        # Initialize Mistral
        if key_status.get(ProviderName.MISTRAL):
            try:
                self._providers[ProviderName.MISTRAL] = MistralProvider(
                    api_key=api_keys.get_key(ProviderName.MISTRAL)
                )
            except AuthenticationError:
                self._providers[ProviderName.MISTRAL] = None
        else:
            self._providers[ProviderName.MISTRAL] = None

        # Initialize Cohere
        if key_status.get(ProviderName.COHERE):
            try:
                self._providers[ProviderName.COHERE] = CohereProvider(
                    api_key=api_keys.get_key(ProviderName.COHERE)
                )
            except AuthenticationError:
                self._providers[ProviderName.COHERE] = None
        else:
            self._providers[ProviderName.COHERE] = None

        # Initialize Ollama
        if key_status.get(ProviderName.OLLAMA):
            self._providers[ProviderName.OLLAMA] = OllamaProvider(
                host=api_keys.get_key(ProviderName.OLLAMA)
            )
        else:
            self._providers[ProviderName.OLLAMA] = None

    def get_provider(self, provider_name: ProviderName) -> Optional[BaseProvider]:
        """Get a provider instance by name."""
        return self._providers.get(provider_name)

    def get_available_providers(self) -> list[ProviderName]:
        """Return list of providers that are configured and available."""
        return [
            name for name, provider in self._providers.items()
            if provider is not None
        ]

    def route_text(
        self,
        prompt: str,
        classification: ClassificationResult,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> tuple[GenerationResult, RoutingDecision]:
        """
        Route a text generation request to the optimal model.

        Process:
        1. Look up the routing table for the classified task type.
        2. Attempt generation with the primary model.
        3. If primary fails, automatically retry with the fallback model.
        4. If both fail, raise ProviderError.

        Args:
            prompt: The user's input (cleaned, without @overrides).
            classification: The classification result from the classifier.
            system_prompt: Optional system instruction.
            history: Optional conversation history.

        Returns:
            Tuple of (GenerationResult, RoutingDecision).

        Raises:
            ProviderError: If both primary and fallback models fail.
        """
        route = ROUTING_TABLE.get(classification.task_type, ROUTING_TABLE[TaskType.GENERAL])

        primary_config = MODELS[route.primary]
        fallback_config = MODELS[route.fallback]

        decision = RoutingDecision(
            task_type=classification.task_type,
            primary_model=primary_config.display_name,
            primary_provider=primary_config.provider.value,
            fallback_model=fallback_config.display_name,
            fallback_provider=fallback_config.provider.value,
            classification_confidence=classification.confidence,
            classification_reasoning=classification.reasoning,
        )

        # --- Attempt 1: Primary model ---
        primary_provider = self._providers.get(primary_config.provider)
        if primary_provider:
            try:
                result = self._execute_text(
                    provider=primary_provider,
                    model_config=primary_config,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history=history,
                )
                decision.used_fallback = False
                decision.model_actually_used = primary_config.display_name
                decision.provider_actually_used = primary_config.provider.value
                return result, decision
            except (RateLimitError, ProviderError) as e:
                console.print(
                    f"  [yellow][!] Primary ({primary_config.display_name}) failed: {e}[/yellow]"
                )
                # Fall through to fallback
        else:
            console.print(
                f"  [yellow][!] Primary provider {primary_config.provider.value} not configured.[/yellow]"
            )

        # --- Attempt 2: Fallback model ---
        fallback_provider = self._providers.get(fallback_config.provider)
        if fallback_provider:
            try:
                result = self._execute_text(
                    provider=fallback_provider,
                    model_config=fallback_config,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history=history,
                )
                decision.used_fallback = True
                decision.model_actually_used = fallback_config.display_name
                decision.provider_actually_used = fallback_config.provider.value
                return result, decision
            except (RateLimitError, ProviderError) as e:
                # Fall through to Ollama if available
                ollama_provider = self._providers.get(ProviderName.OLLAMA)
                if ollama_provider:
                    try:
                        ollama_config = MODELS["local-llama"]
                        result = self._execute_text(
                            provider=ollama_provider,
                            model_config=ollama_config,
                            prompt=prompt,
                            system_prompt=system_prompt,
                            history=history,
                        )
                        decision.used_fallback = True
                        decision.model_actually_used = ollama_config.display_name
                        decision.provider_actually_used = ollama_config.provider.value
                        return result, decision
                    except Exception as oe:
                        raise ProviderError(
                            "Router",
                            f"Both primary ({primary_config.display_name}) and "
                            f"fallback ({fallback_config.display_name}) failed (Last error: {e}). "
                            f"Attempted local Ollama fallback but failed: {oe}",
                        )
                raise ProviderError(
                    "Router",
                    f"Both primary ({primary_config.display_name}) and "
                    f"fallback ({fallback_config.display_name}) failed. Last error: {e}",
                )
        else:
            # Check if local Ollama is available as a global fallback
            ollama_provider = self._providers.get(ProviderName.OLLAMA)
            if ollama_provider:
                try:
                    ollama_config = MODELS["local-llama"]
                    result = self._execute_text(
                        provider=ollama_provider,
                        model_config=ollama_config,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        history=history,
                    )
                    decision.used_fallback = True
                    decision.model_actually_used = ollama_config.display_name
                    decision.provider_actually_used = ollama_config.provider.value
                    return result, decision
                except Exception as e:
                    raise ProviderError(
                        "Router",
                        f"No available providers for task type '{classification.task_type.value}'. "
                        f"Attempted fallback to local Ollama but failed: {e}"
                    )
            raise ProviderError(
                "Router",
                f"No available providers for task type '{classification.task_type.value}'. "
                f"Primary: {primary_config.provider.value} (not configured), "
                f"Fallback: {fallback_config.provider.value} (not configured).",
            )

    def route_image(self, prompt: str) -> tuple[ImageResult, RoutingDecision]:
        """
        Route an image generation request.
        Attempts Gemini first, and falls back to Pollinations.ai (Flux) for free unlimited generation.

        Args:
            prompt: Text description of the image to generate.

        Returns:
            Tuple of (ImageResult, RoutingDecision).
        """
        route = ROUTING_TABLE[TaskType.IMAGE_GENERATION]
        primary_config = MODELS[route.primary]

        decision = RoutingDecision(
            task_type=TaskType.IMAGE_GENERATION,
            primary_model=primary_config.display_name,
            primary_provider=primary_config.provider.value,
            fallback_model="Flux (Pollinations.ai)",
            fallback_provider="pollinations",
            classification_confidence=1.0,
            classification_reasoning="Image generation request.",
        )

        # Attempt 1: Gemini (Imagen)
        gemini = self._providers.get(ProviderName.GEMINI)
        if gemini and api_keys.validate().get(ProviderName.GEMINI):
            try:
                result = gemini.generate_image(
                    prompt=prompt,
                    model_id=primary_config.model_id,
                )
                decision.model_actually_used = primary_config.display_name
                decision.provider_actually_used = primary_config.provider.value
                return result, decision
            except Exception as e:
                console.print(f"  [yellow][!] Gemini image generation failed: {e}. Falling back to Pollinations.ai...[/yellow]")

        # Attempt 2: Pollinations.ai (Free Fallback)
        try:
            import urllib.parse
            import httpx
            encoded_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&private=true"
            
            response = httpx.get(url, timeout=30.0)
            if response.status_code == 200:
                result = ImageResult(
                    image_data=response.content,
                    mime_type="image/jpeg",
                    model_used="Flux (Pollinations.ai)",
                    provider="pollinations",
                    prompt=prompt,
                )
                decision.used_fallback = True
                decision.model_actually_used = "Flux (Pollinations.ai)"
                decision.provider_actually_used = "pollinations"
                return result, decision
            else:
                raise ProviderError("Pollinations", f"HTTP {response.status_code} response.")
        except Exception as pe:
            raise ProviderError("Router", f"Image generation failed on all providers. Details: {pe}")

    def _execute_text(
        self,
        provider: BaseProvider,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> GenerationResult:
        """
        Execute a text generation request with retry logic.

        Retries up to settings.max_retries times with exponential backoff
        on rate limit errors.
        """
        last_error = None

        for attempt in range(settings.max_retries + 1):
            try:
                return provider.generate_text(
                    prompt=prompt,
                    model_id=model_config.model_id,
                    system_prompt=system_prompt,
                    history=history,
                    max_tokens=model_config.max_tokens,
                    temperature=model_config.temperature,
                )
            except RateLimitError as e:
                last_error = e
                if attempt < settings.max_retries:
                    delay = settings.retry_delay * (2 ** attempt)
                    console.print(
                        f"  [dim]Rate limited, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{settings.max_retries})...[/dim]"
                    )
                    time.sleep(delay)
                continue
            except ProviderError:
                raise

        raise last_error or ProviderError(provider.name, "Max retries exceeded.")

    def health_check_all(self) -> dict[str, bool]:
        """
        Run health checks on all configured providers.

        Returns:
            Dict mapping provider names to their health status.
        """
        results = {}
        for name, provider in self._providers.items():
            if provider:
                try:
                    results[name.value] = provider.health_check()
                except Exception:
                    results[name.value] = False
            else:
                results[name.value] = False
        return results
