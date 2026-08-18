"""
Unit Tests — Dynamic Multi-Step Agentic Executor
================================================
Tests dynamic 1-to-5 step budgeting, early stopping, anti-stall guards, and output formatting.
"""

import pytest
from unittest.mock import MagicMock
from orchestra.tools.agentic_executor import AgenticExecutor
from orchestra.router import ModelRouter, GenerationResult, RoutingDecision
from orchestra.config import TaskType


class TestAgenticExecutor:
    """Test suite for AgenticExecutor dynamic execution loop."""

    def test_single_step_completion(self):
        """Test that a simple 1-step task completes immediately without extra iterations."""
        mock_router = MagicMock(spec=ModelRouter)
        mock_router.route_text.return_value = (
            GenerationResult(
                content='{"thought": "Direct answer", "action": "complete", "target": "25 * 4 is 100", "options": []}',
                model_used="test-model",
                provider="test-provider",
                latency_ms=10.0,
            ),
            RoutingDecision(
                task_type=TaskType.AGENTIC_CHAIN,
                primary_model="test-model",
                primary_provider="test-provider",
                fallback_model="",
                fallback_provider="",
            ),
        )

        executor = AgenticExecutor(mock_router, base_steps=5, absolute_max_steps=5)
        response, options = executor.execute_chain("What is 25 * 4?")

        assert "25 * 4 is 100" in response
        assert executor.max_steps <= 5
        assert mock_router.route_text.call_count == 1

    def test_multi_step_dynamic_completion(self):
        """Test multi-step chaining (e.g. step 1 search -> step 2 complete)."""
        mock_router = MagicMock(spec=ModelRouter)
        mock_router.route_text.side_effect = [
            (
                GenerationResult(
                    content='{"thought": "Searching for laptop data", "action": "web_search", "target": "top laptops 2026"}',
                    model_used="test-model",
                    provider="test-provider",
                    latency_ms=10.0,
                ),
                RoutingDecision(
                    task_type=TaskType.AGENTIC_CHAIN,
                    primary_model="test-model",
                    primary_provider="test-provider",
                    fallback_model="",
                    fallback_provider="",
                ),
            ),
            (
                GenerationResult(
                    content='{"thought": "Data collected, synthesizing summary", "action": "complete", "target": "Here are the top laptops: ...", "options": []}',
                    model_used="test-model",
                    provider="test-provider",
                    latency_ms=10.0,
                ),
                RoutingDecision(
                    task_type=TaskType.AGENTIC_CHAIN,
                    primary_model="test-model",
                    primary_provider="test-provider",
                    fallback_model="",
                    fallback_provider="",
                ),
            ),
        ]

        executor = AgenticExecutor(mock_router, base_steps=5, absolute_max_steps=5)
        # Mock _execute_action to avoid making real network calls
        executor._execute_action = MagicMock(return_value="[Mocked search results: Dell XPS, MacBook Air]")

        response, options = executor.execute_chain("Find top laptops and summarize")

        assert "Here are the top laptops" in response
        assert "Completed in 2 dynamic steps" in response
        assert mock_router.route_text.call_count == 2

    def test_max_step_ceiling_enforcement(self):
        """Test that execution never exceeds the max 5-step ceiling."""
        mock_router = MagicMock(spec=ModelRouter)
        mock_router.route_text.return_value = (
            GenerationResult(
                content='{"thought": "Still working", "action": "web_search", "target": "some query"}',
                model_used="test-model",
                provider="test-provider",
                latency_ms=10.0,
            ),
            RoutingDecision(
                task_type=TaskType.AGENTIC_CHAIN,
                primary_model="test-model",
                primary_provider="test-provider",
                fallback_model="",
                fallback_provider="",
            ),
        )

        executor = AgenticExecutor(mock_router, base_steps=5, absolute_max_steps=5)
        executor._execute_action = MagicMock(return_value="[Mocked search result]")

        response, options = executor.execute_chain("Infinite loop task")

        # Must stop at max 5 steps (+ 1 final summary reasoning)
        assert mock_router.route_text.call_count <= 6

    def test_cancellation_killswitch(self):
        """Test that calling cancel() stops the chain immediately."""
        mock_router = MagicMock(spec=ModelRouter)
        executor = AgenticExecutor(mock_router, base_steps=5, absolute_max_steps=5)
        executor.cancel()

        response, options = executor.execute_chain("Do something long")
        assert "Task Cancelled" in response
        assert mock_router.route_text.call_count == 0
