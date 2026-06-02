"""
OrchestraAI — Classifier Tests
=================================
Tests for the task classification engine.
"""

import pytest
from orchestra.config import TaskType
from orchestra.classifier import TaskClassifier, ClassificationResult


class TestCommandDetection:
    """Test slash command detection (no API calls needed)."""

    def setup_method(self):
        """Create a classifier instance for testing."""
        # Note: AI classification will fallback to GENERAL if Gemini is not configured
        self.classifier = TaskClassifier()

    def test_image_command(self):
        """Test /image command is detected."""
        result = self.classifier.classify("/image a cat wearing a hat")
        assert result.task_type == TaskType.IMAGE_GENERATION
        assert result.confidence == 1.0

    def test_scrape_command(self):
        """Test /scrape command is detected."""
        result = self.classifier.classify("/scrape https://example.com")
        assert result.task_type == TaskType.WEB_SCRAPE
        assert result.confidence == 1.0

    def test_system_command(self):
        """Test /system command is detected."""
        result = self.classifier.classify("/system open brave")
        assert result.task_type == TaskType.SYSTEM_COMMAND
        assert result.confidence == 1.0

    def test_open_command(self):
        """Test /open command is detected."""
        result = self.classifier.classify("/open notepad")
        assert result.task_type == TaskType.SYSTEM_COMMAND
        assert result.confidence == 1.0

    def test_url_detection(self):
        """Test automatic URL detection."""
        result = self.classifier.classify("Summarize https://example.com/article")
        assert result.task_type == TaskType.WEB_SCRAPE

    def test_url_detection_with_www(self):
        """Test URL detection with www prefix."""
        result = self.classifier.classify("Check this: http://www.example.com")
        assert result.task_type == TaskType.WEB_SCRAPE


class TestProviderOverrides:
    """Test @provider prefix overrides."""

    def setup_method(self):
        self.classifier = TaskClassifier()

    def test_gemini_override(self):
        """Test @gemini forces routing to Gemini."""
        result = self.classifier.classify("@gemini explain quantum physics")
        assert result.was_forced is True
        assert result.task_type == TaskType.DEEP_REASONING
        assert result.raw_input == "explain quantum physics"

    def test_groq_override(self):
        """Test @groq forces routing to Groq."""
        result = self.classifier.classify("@groq format this text")
        assert result.was_forced is True
        assert result.task_type == TaskType.FAST_UTILITY

    def test_cerebras_override(self):
        """Test @cerebras forces routing to Cerebras."""
        result = self.classifier.classify("@cerebras write a sort function")
        assert result.was_forced is True
        assert result.task_type == TaskType.CODE_GENERATION


class TestClassificationResult:
    """Test ClassificationResult dataclass."""

    def test_default_values(self):
        """Test default values of ClassificationResult."""
        result = ClassificationResult(
            task_type=TaskType.GENERAL,
            confidence=0.5,
            reasoning="Test",
        )
        assert result.was_forced is False
        assert result.raw_input == ""

    def test_all_task_types_exist(self):
        """Test that all expected task types are defined."""
        expected = [
            "deep_reasoning", "code_generation", "creative",
            "fast_utility", "image_generation", "web_scrape",
            "system_command", "general",
        ]
        for name in expected:
            assert TaskType(name) is not None
