"""
OrchestraAI — Local Semantic Vector Memory Engine
===================================================
Provides fast, zero-dependency semantic vector embeddings and cosine similarity search
using numpy and character/subword n-gram hashing for local-first cognitive retrieval.
"""

import re
import math
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger("orchestra.memory.vector_engine")


class VectorMemoryEngine:
    """
    Lightweight, embedded semantic vector engine.
    Computes dense subword/n-gram frequency embeddings and fast vector cosine search.
    """

    def __init__(self, dimension: int = 256):
        self.dim = dimension

    def _tokenize(self, text: str) -> List[str]:
        """Extract words and character n-grams from text."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower()).strip()
        words = cleaned.split()
        tokens = list(words)
        
        # Add character 3-grams and 4-grams for subword semantic robustness
        for word in words:
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    tokens.append(f"_{word[i:i+3]}")
            if len(word) >= 4:
                for i in range(len(word) - 3):
                    tokens.append(f"_{word[i:i+4]}")
                    
        return tokens

    def encode(self, text: str) -> np.ndarray:
        """
        Encodes a text string into a normalized dense vector of fixed dimensionality.
        Uses feature hashing with sign bit weighting.
        """
        if not text or not text.strip():
            return np.zeros(self.dim, dtype=np.float32)

        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.dim, dtype=np.float32)

        vec = np.zeros(self.dim, dtype=np.float32)

        for token in tokens:
            # Deterministic hash mapping
            h = hash(token)
            idx = abs(h) % self.dim
            # Alternate sign to reduce hash collisions
            sign = 1.0 if (h & 1) == 0 else -1.0
            
            # Weight full words slightly higher than subword n-grams
            weight = 1.5 if not token.startswith("_") else 0.75
            vec[idx] += sign * weight

        # L2 Normalize the vector so cosine similarity equals dot product
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm

        return vec

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Compute cosine similarity between two normalized vectors (returns float between -1.0 and 1.0)."""
        if vec_a is None or vec_b is None:
            return 0.0
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def search(
        self,
        query: str,
        corpus: List[Dict[str, Any]],
        text_key: str = "text",
        top_k: int = 5,
        threshold: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Semantic vector search over a list of dictionary documents.
        Returns top_k items scoring above the similarity threshold.
        """
        if not query or not corpus:
            return []

        query_vec = self.encode(query)
        scored_items: List[Tuple[float, Dict[str, Any]]] = []

        for item in corpus:
            content = str(item.get(text_key, "") or "")
            if not content:
                continue
                
            doc_vec = item.get("_vec")
            if doc_vec is None or not isinstance(doc_vec, np.ndarray):
                doc_vec = self.encode(content)

            score = self.cosine_similarity(query_vec, doc_vec)
            if score >= threshold:
                item_copy = dict(item)
                item_copy["similarity_score"] = round(score, 4)
                scored_items.append((score, item_copy))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_items[:top_k]]
