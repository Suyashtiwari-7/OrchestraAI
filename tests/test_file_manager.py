"""
OrchestraAI — File Manager Tests
================================
Tests for file system helper methods (create, move, rename, delete, read, search).
"""

import os
import shutil
import pytest
from pathlib import Path
from orchestra.tools.file_manager import (
    create_file,
    move_file,
    rename_file,
    search_files,
    delete_file,
    read_file_content,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Fixture providing a clean temporary directory for file operations."""
    return tmp_path


class TestFileManager:
    """Test suite for local file manager operations."""

    def test_create_file(self, temp_dir):
        test_file = temp_dir / "test_create.txt"
        res = create_file(str(test_file), "hello world")
        
        assert res["success"] is True
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "hello world"

    def test_read_file_content(self, temp_dir):
        test_file = temp_dir / "test_read.txt"
        test_file.write_text("file content to read", encoding="utf-8")
        
        res = read_file_content(str(test_file))
        assert res["success"] is True
        assert res["content"] == "file content to read"

    def test_move_file(self, temp_dir):
        src = temp_dir / "src.txt"
        src.write_text("move me", encoding="utf-8")
        dst = temp_dir / "subdir" / "dst.txt"
        
        res = move_file(str(src), str(dst))
        assert res["success"] is True
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "move me"

    def test_rename_file(self, temp_dir):
        old_file = temp_dir / "old.txt"
        old_file.write_text("rename me", encoding="utf-8")
        
        res = rename_file(str(old_file), "new.txt")
        new_file = temp_dir / "new.txt"
        
        assert res["success"] is True
        assert not old_file.exists()
        assert new_file.exists()
        assert new_file.read_text(encoding="utf-8") == "rename me"

    def test_search_files(self, temp_dir):
        f1 = temp_dir / "match_one.txt"
        f1.write_text("content", encoding="utf-8")
        f2 = temp_dir / "match_two.log"
        f2.write_text("content", encoding="utf-8")
        f3 = temp_dir / "other_file.txt"
        f3.write_text("content", encoding="utf-8")
        
        results = search_files("match", str(temp_dir))
        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "match_one.txt" in names
        assert "match_two.log" in names

    def test_delete_file(self, temp_dir):
        target = temp_dir / "delete_me.txt"
        target.write_text("data", encoding="utf-8")
        
        res = delete_file(str(target))
        assert res["success"] is True
        assert not target.exists()
