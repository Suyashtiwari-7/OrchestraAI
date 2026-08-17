"""
OrchestraAI — Document Reader Tests
====================================
Tests for the local document reader tool.
Uses temporary directories and mocking for PDF extraction.
"""

import pytest
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestra.tools.document_reader import (
    extract_file_paths,
    read_local_file,
    gather_referenced_documents,
)

class TestDocumentReader:
    """Test path extraction, file reading, and content formatting."""

    def test_extract_file_paths(self):
        """Test extraction of supported file paths from plain text prompts."""
        text = "Please read report.pdf and explain the contents of src/main.py. Also look at index.html."
        paths = extract_file_paths(text)
        assert "report.pdf" in paths
        assert "src/main.py" in paths
        assert "index.html" in paths
        assert len(paths) == 3

    def test_extract_file_paths_ignores_unsupported(self):
        """Test that unsupported formats are ignored."""
        text = "Check photo.jpg, setup.exe, and raw_data without extension."
        paths = extract_file_paths(text)
        assert len(paths) == 0

    def test_read_txt_file(self, tmp_path):
        """Test reading a standard text file."""
        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello World from OrchestraAI!", encoding="utf-8")

        result = read_local_file(test_file)
        assert result["success"] is True
        assert result["type"] == "text"
        assert result["filename"] == "hello.txt"
        assert result["content"] == "Hello World from OrchestraAI!"

    def test_read_csv_file(self, tmp_path):
        """Test reading and formatting a CSV file."""
        test_file = tmp_path / "data.csv"
        with open(test_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Age", "Role"])
            writer.writerow(["Alice", "30", "Developer"])
            writer.writerow(["Bob", "25", "Designer"])

        result = read_local_file(test_file)
        assert result["success"] is True
        assert result["type"] == "csv"
        # The reader formats CSV rows separated by tabs
        assert "Name\tAge\tRole" in result["content"]
        assert "Alice\t30\tDeveloper" in result["content"]

    @patch("orchestra.tools.document_reader.PdfReader")
    def test_read_pdf_file(self, mock_pdf_reader, tmp_path):
        """Test reading a PDF file with mocked extraction."""
        # Create a dummy pdf file on disk (pypdf requires the file exists, but we mock the parsing)
        test_file = tmp_path / "doc.pdf"
        test_file.write_text("dummy pdf contents", encoding="utf-8")

        # Mock PdfReader instance and pages
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Page 1 Content"
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Page 2 Content"

        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page_1, mock_page_2]
        mock_pdf_reader.return_value = mock_reader_instance

        result = read_local_file(test_file)
        assert result["success"] is True
        assert result["type"] == "pdf"
        assert "--- Page 1 ---" in result["content"]
        assert "Page 1 Content" in result["content"]
        assert "--- Page 2 ---" in result["content"]
        assert "Page 2 Content" in result["content"]

    def test_gather_referenced_documents(self, tmp_path):
        """Test resolving relative paths and gathering matching files."""
        file1 = tmp_path / "doc1.txt"
        file1.write_text("Content of doc 1", encoding="utf-8")
        file2 = tmp_path / "doc2.md"
        file2.write_text("Content of doc 2", encoding="utf-8")

        prompt = "Compare doc1.txt with doc2.md and missing.txt"
        docs = gather_referenced_documents(prompt, tmp_path)

        # Only doc1.txt and doc2.md should be loaded successfully
        assert len(docs) == 2
        filenames = [d["filename"] for d in docs]
        assert "doc1.txt" in filenames
        assert "doc2.md" in filenames
        assert "missing.txt" not in filenames
