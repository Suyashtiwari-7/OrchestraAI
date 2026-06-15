"""
OrchestraAI — Ollama and User Profile Memory Tests
==================================================
Tests for local memory facts learning and Ollama provider.
"""

import json
import pytest
from pathlib import Path
from unittest import mock

from orchestra.config import TaskType, ProviderName, MODELS, RouteConfig, ROUTING_TABLE
from orchestra.memory.user_profile import UserProfileMemory
from orchestra.providers.ollama_provider import OllamaProvider
from orchestra.classifier import TaskClassifier
from orchestra.router import ModelRouter, RoutingDecision

def test_user_profile_memory_extraction(tmp_path):
    # Setup test file
    filepath = tmp_path / "user_profile.json"
    memory = UserProfileMemory(filepath=filepath)
    
    # Test initial state
    assert len(memory._facts) == 0
    
    # Test naming extraction
    new_facts = memory.extract_facts("Hello, my name is Alex. Nice to meet you.")
    assert "My name is Alex" in memory._facts
    assert len(new_facts) == 1
    assert new_facts[0] == "My name is Alex"
    
    # Test preference extraction
    new_facts = memory.extract_facts("I prefer writing Python code rather than JavaScript.")
    assert "I prefer writing Python code rather than JavaScript" in memory._facts
    
    # Test deduplication
    new_facts = memory.extract_facts("My name is Alex.")
    assert len(new_facts) == 0
    
    # Verify persistence
    assert filepath.exists()
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "My name is Alex" in data["facts"]
        
    # Verify context formatting
    context = memory.get_system_context()
    assert "USER PROFILE DETAILS" in context
    assert "- My name is Alex" in context


@mock.patch("requests.post")
def test_ollama_provider_generate(mock_post):
    # Mock Ollama API response
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "This is a local response."},
        "prompt_eval_count": 10,
        "eval_count": 20,
    }
    mock_post.return_value = mock_response
    
    provider = OllamaProvider(host="http://localhost:11434")
    assert provider.name == "Ollama"
    
    res = provider.generate_text(
        prompt="Tell me a joke",
        model_id="llama3.2",
        system_prompt="Be funny",
        history=[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
    )
    
    assert res.content == "This is a local response."
    assert res.model_used == "llama3.2"
    assert res.provider == "ollama"
    assert res.input_tokens == 10
    assert res.output_tokens == 20
    
    # Verify requests payload
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:11434/api/chat"
    payload = kwargs["json"]
    assert payload["model"] == "llama3.2"
    assert len(payload["messages"]) == 4
    assert payload["messages"][0] == {"role": "system", "content": "Be funny"}


def test_classifier_ollama_override():
    classifier = TaskClassifier()
    result = classifier.classify("@ollama how is the weather?")
    assert result.was_forced is True
    assert result.task_type == TaskType.GENERAL
    assert result.raw_input == "how is the weather?"
