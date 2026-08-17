"""
OrchestraAI — Codebase Search Tests
====================================
Tests for the native keyword codebase search engine.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestra.tools.codebase_search import (
    chunk_file,
    execute_codebase_search,
    _score_chunk,
)

class TestCodebaseSearch:
    """Test text chunking, keyword scoring, and search execution."""

    def test_chunk_file(self):
        """Test split content logic with overlap bounds."""
        text = "abcdefghijklmnopqrstuvwxyz"
        # 10 chars per chunk, 2 chars overlap
        chunks = chunk_file(text, max_chars=10, overlap=2)
        
        # Chunks should be:
        # chunk 1: 0 to 10 ("abcdefghij")
        # chunk 2: 8 to 18 ("ijklmnopqr")
        # chunk 3: 16 to 26 ("qrstuvwxyz")
        assert len(chunks) == 3
        assert chunks[0] == "abcdefghij"
        assert chunks[1] == "ijklmnopqr"
        assert chunks[2] == "qrstuvwxyz"

    def test_chunk_file_empty(self):
        """Test chunking empty content."""
        assert chunk_file("") == []
        assert chunk_file("short", max_chars=100) == ["short"]

    def test_score_chunk_keyword_match(self):
        """Test keyword scoring with matches."""
        query_words = ["hello", "world"]
        chunk = "This is a hello world test with hello."
        score = _score_chunk(query_words, chunk, "test.py")
        assert score > 0.0

    def test_score_chunk_no_match(self):
        """Test keyword scoring with no matches."""
        query_words = ["hello", "world"]
        chunk = "No matches here at all."
        score = _score_chunk(query_words, chunk, "test.py")
        assert score == 0.0

    def test_score_chunk_path_bonus(self):
        """Test that matching file path gives bonus score."""
        query_words = ["router"]
        chunk = "Some content with router."
        # Path match should give higher score
        score_with_path = _score_chunk(query_words, chunk, "orchestra/router.py")
        score_without_path = _score_chunk(query_words, chunk, "orchestra/other.py")
        assert score_with_path > score_without_path

    @patch("orchestra.tools.codebase_search.get_project_files")
    def test_execute_codebase_search_keyword(self, mock_get_files, tmp_path):
        """Test keyword search over mocked project files."""
        # Create temp files
        file1 = tmp_path / "main.py"
        file1.write_text("def my_awesome_function():\n    return 42", encoding="utf-8")
        file2 = tmp_path / "config.json"
        file2.write_text('{"app_name": "Orchestra"}', encoding="utf-8")
        
        mock_get_files.return_value = [file1, file2]
        
        # Perform search query targeting file1
        results = execute_codebase_search("awesome function", limit=2)
        
        assert len(results) > 0
        assert results[0]["filename"] == "main.py"
        assert "my_awesome_function" in results[0]["content"]
