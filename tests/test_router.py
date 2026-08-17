"""
OrchestraAI — Router Tests
============================
Tests for the model routing and fallback logic.
"""

import pytest
from orchestra.config import (
    TaskType,
    ProviderName,
    MODELS,
    ROUTING_TABLE,
    RouteConfig,
)


class TestRoutingTable:
    """Test that the routing table is correctly configured."""

    def test_all_task_types_have_routes(self):
        """Every TaskType must have a corresponding route."""
        for task_type in TaskType:
            assert task_type in ROUTING_TABLE, (
                f"TaskType.{task_type.name} is missing from ROUTING_TABLE"
            )

    def test_all_routes_reference_valid_models(self):
        """All model keys in routes must exist in the MODELS dict."""
        for task_type, route in ROUTING_TABLE.items():
            assert route.primary in MODELS, (
                f"Route for {task_type.name} references unknown primary model: {route.primary}"
            )
            assert route.fallback in MODELS, (
                f"Route for {task_type.name} references unknown fallback model: {route.fallback}"
            )

    def test_routes_have_descriptions(self):
        """All routes must have a non-empty description."""
        for task_type, route in ROUTING_TABLE.items():
            assert route.description, (
                f"Route for {task_type.name} has no description"
            )


class TestModelConfigs:
    """Test that model configurations are valid."""

    def test_all_models_have_provider(self):
        """Every model must be associated with a provider."""
        for model_key, config in MODELS.items():
            assert isinstance(config.provider, ProviderName), (
                f"Model {model_key} has invalid provider type"
            )

    def test_all_models_have_model_id(self):
        """Every model must have a non-empty model_id."""
        for model_key, config in MODELS.items():
            assert config.model_id, f"Model {model_key} has empty model_id"

    def test_all_models_have_display_name(self):
        """Every model must have a non-empty display_name."""
        for model_key, config in MODELS.items():
            assert config.display_name, f"Model {model_key} has empty display_name"

    def test_temperature_in_range(self):
        """Temperature must be between 0.0 and 2.0."""
        for model_key, config in MODELS.items():
            assert 0.0 <= config.temperature <= 2.0, (
                f"Model {model_key} has invalid temperature: {config.temperature}"
            )

    def test_max_tokens_positive(self):
        """max_tokens must be positive."""
        for model_key, config in MODELS.items():
            assert config.max_tokens > 0, (
                f"Model {model_key} has non-positive max_tokens: {config.max_tokens}"
            )


class TestFallbackDiversity:
    """Test that fallback models use different providers than primaries."""

    def test_fallback_uses_different_provider_when_possible(self):
        """
        For non-image tasks, the fallback should ideally use a different
        provider than the primary to ensure resilience.
        """
        exemptions = {TaskType.IMAGE_GENERATION}  # Image gen only has Gemini

        for task_type, route in ROUTING_TABLE.items():
            if task_type in exemptions:
                continue

            primary = MODELS[route.primary]
            fallback = MODELS[route.fallback]

            # This is a recommendation, not a hard failure
            if primary.provider == fallback.provider:
                pytest.skip(
                    f"Route {task_type.name}: primary and fallback both use "
                    f"{primary.provider.value} (consider diversifying)"
                )
