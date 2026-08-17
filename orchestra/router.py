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
from .providers.nvidia_provider import NvidiaProvider
from .providers.groq_provider import GroqProvider
from .providers.ollama_provider import OllamaProvider
from .providers.gemini_provider import GeminiProvider  # Kept solely for image generation


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

        # Initialize NVIDIA NIM (primary heavy-lift provider)
        if key_status.get(ProviderName.NVIDIA_NIM):
            try:
                self._providers[ProviderName.NVIDIA_NIM] = NvidiaProvider(
                    api_key=api_keys.get_key(ProviderName.NVIDIA_NIM)
                )
            except AuthenticationError:
                self._providers[ProviderName.NVIDIA_NIM] = None
        else:
            self._providers[ProviderName.NVIDIA_NIM] = None

        # Initialize Groq (ultra-fast utility)
        if key_status.get(ProviderName.GROQ):
            try:
                self._providers[ProviderName.GROQ] = GroqProvider(
                    api_key=api_keys.get_key(ProviderName.GROQ)
                )
            except AuthenticationError:
                self._providers[ProviderName.GROQ] = None
        else:
            self._providers[ProviderName.GROQ] = None

        # Initialize Ollama (100% offline fallback)
        if key_status.get(ProviderName.OLLAMA):
            self._providers[ProviderName.OLLAMA] = OllamaProvider(
                host=api_keys.get_key(ProviderName.OLLAMA)
            )
        else:
            self._providers[ProviderName.OLLAMA] = None

        # Initialize Gemini (solely for image generation)
        if key_status.get(ProviderName.GEMINI):
            try:
                self._providers[ProviderName.GEMINI] = GeminiProvider(
                    api_key=api_keys.get_key(ProviderName.GEMINI)
                )
            except AuthenticationError:
                self._providers[ProviderName.GEMINI] = None
        else:
            self._providers[ProviderName.GEMINI] = None

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
        image_data: Optional[bytes] = None,
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
        has_internet = True
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=1.0)
        except Exception:
            has_internet = False

        if not has_internet and "local-llama" in MODELS:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("No internet detected. Routing to offline local-llama.")
            primary_config = MODELS["local-llama"]
            fallback_config = MODELS["local-llama"]
        else:
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

        # --- Attempt 1 & 2: Adaptive Timeout Fallback ---
        import concurrent.futures
        
        primary_provider = self._providers.get(primary_config.provider)
        fallback_provider = self._providers.get(fallback_config.provider)
        last_error = None

        if primary_provider and fallback_provider and primary_config.provider != fallback_config.provider:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                primary_future = executor.submit(
                    self._execute_text, primary_provider, primary_config, prompt, system_prompt, history, image_data)
                
                try:
                    # Soft timeout of 4 seconds for the primary model
                    result = primary_future.result(timeout=4.0)
                    decision.used_fallback = False
                    decision.model_actually_used = primary_config.display_name
                    decision.provider_actually_used = primary_config.provider.value
                    return result, decision
                except concurrent.futures.TimeoutError:
                    print(f"  [!] Primary ({primary_config.display_name}) took >4s. Firing fallback concurrently...")
                    fallback_future = executor.submit(
                        self._execute_text, fallback_provider, fallback_config, prompt, system_prompt, history, image_data)
                    
                    done, not_done = concurrent.futures.wait(
                        [primary_future, fallback_future],
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    
                    for future in done:
                        try:
                            result = future.result()
                            if future == primary_future:
                                decision.used_fallback = False
                                decision.model_actually_used = primary_config.display_name
                                decision.provider_actually_used = primary_config.provider.value
                            else:
                                decision.used_fallback = True
                                decision.model_actually_used = fallback_config.display_name
                                decision.provider_actually_used = fallback_config.provider.value
                            return result, decision
                        except Exception as e:
                            last_error = e
                            continue
                            
                    # If first finished failed, wait for the other
                    for future in not_done:
                        try:
                            result = future.result()
                            if future == primary_future:
                                decision.used_fallback = False
                                decision.model_actually_used = primary_config.display_name
                                decision.provider_actually_used = primary_config.provider.value
                            else:
                                decision.used_fallback = True
                                decision.model_actually_used = fallback_config.display_name
                                decision.provider_actually_used = fallback_config.provider.value
                            return result, decision
                        except Exception as e:
                            last_error = e
                            
                except Exception as e:
                    print(f"  [!] Primary ({primary_config.display_name}) failed immediately: {e}")
                    last_error = e
                    # Primary failed fast, just run fallback normally
                    try:
                        result = self._execute_text(
                            provider=fallback_provider,
                            model_config=fallback_config,
                            prompt=prompt,
                            system_prompt=system_prompt,
                    history=history,
                    image_data=image_data,
                )
                        decision.used_fallback = True
                        decision.model_actually_used = fallback_config.display_name
                        decision.provider_actually_used = fallback_config.provider.value
                        return result, decision
                    except Exception as fe:
                        print(f"  [!] Fallback ({fallback_config.display_name}) failed: {fe}")
                        last_error = fe

        else:
            # Fallback to linear execution if one is missing or both use same provider
            if primary_provider:
                try:
                    result = self._execute_text(
                        provider=primary_provider,
                        model_config=primary_config,
                        prompt=prompt,
                        system_prompt=system_prompt,
                    history=history,
                    image_data=image_data,
                )
                    decision.used_fallback = False
                    decision.model_actually_used = primary_config.display_name
                    decision.provider_actually_used = primary_config.provider.value
                    return result, decision
                except Exception as e:
                    print(f"  [!] Primary ({primary_config.display_name}) failed: {e}")
                    last_error = e
                    
            if fallback_provider:
                try:
                    result = self._execute_text(
                        provider=fallback_provider,
                        model_config=fallback_config,
                        prompt=prompt,
                        system_prompt=system_prompt,
                    history=history,
                    image_data=image_data,
                )
                    decision.used_fallback = True
                    decision.model_actually_used = fallback_config.display_name
                    decision.provider_actually_used = fallback_config.provider.value
                    return result, decision
                except Exception as e:
                    print(f"  [!] Fallback ({fallback_config.display_name}) failed: {e}")
                    last_error = e

        # --- Attempt 3: Loop through remaining configured providers ---
        fallback_chain = [
            (ProviderName.NVIDIA_NIM, "nim-llama"),
            (ProviderName.GROQ, "groq-llama"),
            (ProviderName.OLLAMA, "local-llama"),
        ]
        
        for provider_name, model_key in fallback_chain:
            provider_inst = self._providers.get(provider_name)
            if provider_inst and model_key in MODELS:
                try:
                    model_cfg = MODELS[model_key]
                    print(
                        f"  [*] Attempting fallback to {provider_name.value} ({model_cfg.display_name})..."
                    )
                    result = self._execute_text(
                        provider=provider_inst,
                        model_config=model_cfg,
                        prompt=prompt,
                        system_prompt=system_prompt,
                    history=history,
                    image_data=image_data,
                )
                    decision.used_fallback = True
                    decision.model_actually_used = model_cfg.display_name
                    decision.provider_actually_used = model_cfg.provider.value
                    return result, decision
                except Exception as fe:
                    print(
                        f"  [!] Fallback to {provider_name.value} failed: {fe}"
                    )
                    last_error = fe
                    continue

        raise ProviderError(
            "Router",
            f"All configured text generation providers failed. Primary ({primary_config.display_name}) "
            f"and fallback ({fallback_config.display_name}) failed. Last error: {last_error}"
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
                print(f"  [!] Gemini image generation failed: {e}. Falling back to Pollinations.ai...")

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
        image_data: Optional[bytes] = None,
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
                    image_data=image_data,
                )
            except RateLimitError as e:
                last_error = e
                if attempt < settings.max_retries:
                    delay = settings.retry_delay * (2 ** attempt)
                    print(
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
