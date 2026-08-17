"""
OrchestraAI — Smart Memory, Connected Graph & Digital Safe Tests
================================================================
Tests for MemoryVault (DPAPI Encryption), Connected Graph Memory, and Conceptual Local RAG.
"""

import pytest
from pathlib import Path
from orchestra.memory.database import MemoryDatabase
from orchestra.memory.vault import MemoryVault


class TestMemoryVault:
    """Test Windows DPAPI encryption and digital safe storage."""

    def test_encrypt_and_decrypt_secret(self):
        """Test plaintext string encryption and roundtrip decryption."""
        secret = "Expected_CTC_12_LPA_Confidential_Token_xyz123"
        encrypted = MemoryVault.encrypt(secret)

        assert encrypted != secret
        assert len(encrypted) > 0

        decrypted = MemoryVault.decrypt(encrypted)
        assert decrypted == secret

    def test_empty_string_handling(self):
        """Test encryption of empty string."""
        assert MemoryVault.encrypt("") == ""
        assert MemoryVault.decrypt("") == ""


class TestConnectedMemoryGraph:
    """Test multi-hop relationship graph and conceptual retrieval."""

    def setup_method(self, tmp_path_factory):
        import tempfile
        self.temp_db = Path(tempfile.mktemp(suffix=".db"))
        self.db = MemoryDatabase(db_path=self.temp_db)

    def teardown_method(self):
        if self.temp_db.exists():
            try:
                self.temp_db.unlink()
            except Exception:
                pass

    def test_add_and_query_connected_graph(self):
        """Test adding multi-hop relationships and connecting the dots."""
        # Connect: (Yash) -> [is friend of] -> (Suyash)
        self.db.add_relationship("yash", "is friend of", "suyash", details="from college")
        # Connect: (Yash) -> [working on] -> (assignment)
        self.db.add_relationship("yash", "working on", "assignment", details="due on Monday")

        # Query connections starting from "suyash" (depth=2)
        connections = self.db.query_connected_graph("suyash", depth=2)
        assert len(connections) >= 1

        connected_targets = {c["target"] for c in connections}.union({c["source"] for c in connections})
        assert "yash" in connected_targets

    def test_conceptual_associative_memory(self):
        """Test that searching for 'machine' retrieves facts saved about 'laptop'."""
        self.db.save_insights_batch([
            {
                "category": "HARDWARE",
                "key": "laptop_model",
                "value": "Lenovo IdeaPad Gaming 3 with RTX 3050",
                "importance": 9,
            }
        ])

        # Query using the concept 'machine' (which expands to 'laptop' / 'ideapad')
        results = self.db.get_relevant_insights("Tell me about my gaming machine")
        assert len(results) >= 1
        assert "Lenovo IdeaPad" in results[0]["value"]
