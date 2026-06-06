"""
OrchestraAI — Codebase Search Tool (Local RAG)
==============================================
Performs hybrid search (semantic vector search using Gemini text-embedding-004
with a local persistent cache + fallback keyword TF-IDF ranking) across all 
source code and project documents.
"""

import os
import re
import math
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

from orchestra.config import api_keys, settings

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

CACHE_FILE = settings.project_root / ".orchestra_embeddings_cache.json"

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
    """Split file content into smaller chunks with overlap to retain semantic context."""
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

def load_cache() -> Dict[str, Any]:
    """Load cached vector embeddings from file."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, Any]):
    """Save vector embeddings cache to file."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[!] Error saving embeddings cache: {e}")

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate the cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def get_tf_idf_score(query: str, chunk: str) -> float:
    """Fallback TF-IDF style keyword relevance score for query against chunk."""
    words = re.findall(r"\w+", query.lower())
    chunk_lower = chunk.lower()
    score = 0.0
    for w in words:
        count = chunk_lower.count(w)
        if count > 0:
            # Simple TF-IDF approximation
            score += (1 + math.log(count)) * (1.5 / (len(words) + 0.5))
    return score

def get_gemini_client():
    """Import and return the Google GenAI client if available."""
    try:
        from google import genai
        if api_keys.gemini:
            return genai.Client(api_key=api_keys.gemini)
    except Exception:
        pass
    return None

def execute_codebase_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search the codebase using a hybrid TF-IDF + Gemini Embeddings vector similarity logic.
    Returns ranked chunks with file metadata and match score.
    """
    project_files = get_project_files()
    all_chunks = []
    
    # 1. Chunk all files
    for fp in project_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_file(content)
            for i, chunk in enumerate(chunks):
                # Unique ID based on relative path and chunk index
                rel_path = os.path.relpath(fp, settings.project_root).replace("\\", "/")
                all_chunks.append({
                    "id": f"{rel_path}#chunk{i}",
                    "rel_path": rel_path,
                    "filename": fp.name,
                    "content": chunk,
                    "mtime": fp.stat().st_mtime
                })
        except Exception:
            continue
            
    if not all_chunks:
        return []

    # 2. Try Semantic Search with Gemini Embeddings
    client = get_gemini_client()
    if client:
        try:
            cache = load_cache()
            # Find chunks that need updating in the cache
            to_embed = []
            for c in all_chunks:
                cache_entry = cache.get(c["id"])
                # If cached and modified time matches, use it; otherwise re-embed
                if not cache_entry or cache_entry.get("mtime") != c["mtime"]:
                    to_embed.append(c)
            
            # Embed new/modified chunks in batches (max 100 at a time to prevent API limits)
            batch_size = 80
            for i in range(0, len(to_embed), batch_size):
                batch = to_embed[i:i+batch_size]
                res = client.models.embed_content(
                    model="text-embedding-004",
                    contents=[b["content"] for b in batch]
                )
                
                for idx, item in enumerate(batch):
                    # In google-genai, the embedding object contains the vector values
                    vector = res.embeddings[idx].values
                    cache[item["id"]] = {
                        "mtime": item["mtime"],
                        "vector": vector
                    }
            
            # Save updated cache
            if to_embed:
                save_cache(cache)
                
            # Get query embedding
            q_res = client.models.embed_content(
                model="text-embedding-004",
                contents=query
            )
            q_vector = q_res.embeddings[0].values
            
            # Score similarity
            scored_results = []
            for c in all_chunks:
                vector_info = cache.get(c["id"])
                if vector_info and "vector" in vector_info:
                    sim = cosine_similarity(q_vector, vector_info["vector"])
                    scored_results.append((sim, c))
                else:
                    # Fallback to TF-IDF score normalized
                    sim = get_tf_idf_score(query, c["content"]) * 0.05
                    scored_results.append((sim, c))
                    
            scored_results.sort(key=lambda x: x[0], reverse=True)
            return [
                {
                    "rel_path": item["rel_path"],
                    "filename": item["filename"],
                    "content": item["content"],
                    "score": round(score, 4),
                    "type": "semantic"
                }
                for score, item in scored_results[:limit]
            ]
            
        except Exception as e:
            # Fallback to TF-IDF if API fails
            print(f"[!] Semantic search api error, falling back to TF-IDF: {e}")
            
    # 3. Fallback: Keyword TF-IDF ranking
    scored_results = []
    for c in all_chunks:
        score = get_tf_idf_score(query, c["content"])
        if score > 0:
            scored_results.append((score, c))
            
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
