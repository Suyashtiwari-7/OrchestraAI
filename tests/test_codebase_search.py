"""
OrchestraAI — Codebase Search Tests
====================================
Tests for the local RAG codebase search system.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestra.tools.codebase_search import (
    chunk_file,
    cosine_similarity,
    get_tf_idf_score,
    execute_codebase_search,
)

class TestCodebaseSearch:
    """Test text chunking, vector operations, scoring, and crawled matches."""

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

    def test_cosine_similarity(self):
        """Test vector similarity edge cases and matches."""
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        
        assert cosine_similarity(v1, v2) == pytest.approx(1.0)
        assert cosine_similarity(v1, v3) == pytest.approx(0.0)
        assert cosine_similarity([], v2) == 0.0
        assert cosine_similarity([1, 2], [1, 2, 3]) == 0.0

    def test_get_tf_idf_score(self):
        """Test simple token overlap scoring."""
        query = "hello world"
        chunk_with_matches = "This is a hello world test."
        chunk_without_matches = "No matches here."
        
        assert get_tf_idf_score(query, chunk_with_matches) > 0.0
        assert get_tf_idf_score(query, chunk_without_matches) == 0.0

    @patch("orchestra.tools.codebase_search.get_project_files")
    def test_execute_codebase_search_keyword(self, mock_get_files, tmp_path):
        """Test fallback keyword search over mocked project files."""
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
