"""
OrchestraAI — Codebase Search Tool
====================================
Fast native keyword/regex search across all project source code and documents.
Replaces the previous heavy TF-IDF + Gemini embedding hybrid engine with a
lightweight, zero-dependency approach that runs in milliseconds.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any

from orchestra.config import settings

# Supported search files
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".html", ".css", ".json",
    ".csv", ".md", ".txt", ".toml", ".yaml", ".yml", ".sh", ".ini"
}

# Directories to ignore
IGNORE_DIRS = {
    ".git", "venv", ".venv", "__pycache__", ".pytest_cache",
    "output", "node_modules", "dist", "build"
}


def get_project_files() -> List[Path]:
    """Recursively find all supported code and text files in the project."""
    project_files = []
    root_dir = settings.project_root

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude ignored directories in-place to prune walk
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for name in filenames:
            file_path = Path(dirpath) / name
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                project_files.append(file_path)

    return project_files


def chunk_file(content: str, max_chars: int = 800, overlap: int = 200) -> List[str]:
    """Split file content into smaller chunks with overlap to retain context."""
    chunks = []
    if not content:
        return chunks

    start = 0
    while start < len(content):
        end = start + max_chars
        chunk = content[start:end]
        chunks.append(chunk)
        if end >= len(content):
            break
        start += (max_chars - overlap)
    return chunks


def _score_chunk(query_words: List[str], chunk: str, rel_path: str) -> float:
    """
    Score a chunk based on keyword match count + path relevance.

    Scoring heuristics:
    - +1.0 per keyword occurrence in the chunk text
    - +2.0 bonus if keyword appears in the file path (higher signal)
    - Normalized by number of query words to avoid bias toward long queries
    """
    chunk_lower = chunk.lower()
    path_lower = rel_path.lower()
    score = 0.0

    for word in query_words:
        # Count occurrences in chunk content
        count = chunk_lower.count(word)
        score += count

        # Bonus for matching in file path (strong relevance signal)
        if word in path_lower:
            score += 2.0

    # Normalize by query length to keep scores comparable
    if query_words:
        score /= len(query_words)

    return score


def execute_codebase_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search the codebase using fast native keyword matching.
    Returns ranked chunks with file metadata and match score.
    """
    # Extract meaningful search words (3+ chars, skip common stop words)
    stop_words = {"the", "and", "for", "with", "this", "that", "from", "have", "are"}
    query_words = [
        w.lower() for w in re.findall(r"\w{3,}", query)
        if w.lower() not in stop_words
    ]

    if not query_words:
        return []

    project_files = get_project_files()
    scored_results = []

    for fp in project_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Quick check: skip entire file if no query word appears at all
        content_lower = content.lower()
        if not any(w in content_lower for w in query_words):
            continue

        rel_path = os.path.relpath(fp, settings.project_root).replace("\\", "/")
        chunks = chunk_file(content)

        for i, chunk in enumerate(chunks):
            score = _score_chunk(query_words, chunk, rel_path)
            if score > 0:
                scored_results.append((score, {
                    "rel_path": rel_path,
                    "filename": fp.name,
                    "content": chunk,
                    "chunk_index": i,
                }))

    # Sort by score descending and return top results
    scored_results.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "rel_path": item["rel_path"],
            "filename": item["filename"],
            "content": item["content"],
            "score": round(score, 4),
            "type": "keyword"
        }
        for score, item in scored_results[:limit]
    ]
