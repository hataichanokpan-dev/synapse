"""
Test cases for Quick Wins fixes.

Tests:
- B6: Remove Duplicate FTS5
- B4: Default Embedding Model
- B8: Complete search_all()
"""

import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestB6RemoveDuplicateFTS5:
    """Test that FTS5 table is only created once."""

    def test_fts5_created_once(self):
        """Verify only one episodes_fts table is created."""
        from synapse.layers.episodic import EpisodicManager

        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test_episodic.db"
            manager = EpisodicManager(db_path=db_path)

            # Check that FTS5 table exists
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='episodes_fts'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None, "episodes_fts table should exist"
        finally:
            # Clean up
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_fts5_schema_has_both_columns(self):
        """Verify FTS5 table has both content_fts and summary_fts columns."""
        from synapse.layers.episodic import EpisodicManager

        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test_episodic.db"
            manager = EpisodicManager(db_path=db_path)

            # Insert a test episode to populate FTS
            manager.record_episode(
                content="test content for FTS",
                summary="test summary",
                preprocess=False
            )

            # Query FTS5 table directly
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT * FROM episodes_fts LIMIT 1")
            columns = [description[0] for description in cursor.description]
            conn.close()

            # Should have content_fts and summary_fts columns
            assert 'content_fts' in columns, "FTS5 should have content_fts column"
            assert 'summary_fts' in columns, "FTS5 should have summary_fts column"
        finally:
            # Clean up
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestB4DefaultEmbeddingModel:
    """Test default embedding model fallback."""

    def test_default_embedding_model_constant(self):
        """Verify default embedding model is defined."""
        from synapse.storage.qdrant_client import DEFAULT_EMBEDDING_MODEL

        assert DEFAULT_EMBEDDING_MODEL is not None
        assert 'multilingual' in DEFAULT_EMBEDDING_MODEL.lower()
        assert 'sentence-transformers' in DEFAULT_EMBEDDING_MODEL.lower()

    def test_uses_default_when_not_configured(self):
        """Verify default model is used when not configured."""
        from synapse.storage.qdrant_client import QdrantClient, DEFAULT_EMBEDDING_MODEL

        # Create client without embedding model config
        client = QdrantClient(
            url="http://localhost:6333",
            embedding_model=None,
        )

        assert client.embedding_model is None

        # Mock SentenceTransformer to verify default is used
        # Patch at the point of import inside the function
        mock_st_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.get_sentence_embedding_dimension.return_value = 384
        mock_st_module.SentenceTransformer.return_value = mock_instance

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            # Trigger embedder loading
            embedder = client._load_embedder()

            # Should have been called with default model
            mock_st_module.SentenceTransformer.assert_called_once_with(DEFAULT_EMBEDDING_MODEL)
            assert embedder is mock_instance

    def test_uses_configured_model_when_provided(self):
        """Verify configured model is used when provided."""
        from synapse.storage.qdrant_client import QdrantClient

        custom_model = "custom-model-name"

        # Create client with custom embedding model
        client = QdrantClient(
            url="http://localhost:6333",
            embedding_model=custom_model,
        )

        assert client.embedding_model == custom_model

        # Mock SentenceTransformer to verify custom model is used
        mock_st_module = MagicMock()
        mock_instance = MagicMock()
        mock_instance.get_sentence_embedding_dimension.return_value = 384
        mock_st_module.SentenceTransformer.return_value = mock_instance

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            # Trigger embedder loading
            embedder = client._load_embedder()

            # Should have been called with custom model
            mock_st_module.SentenceTransformer.assert_called_once_with(custom_model)

    def test_fallback_to_hash_when_model_load_fails(self):
        """Verify fallback to hash embedding when model load fails."""
        from synapse.storage.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333", embedding_model=None)

        # Mock SentenceTransformer to raise exception
        mock_st_module = MagicMock()
        mock_st_module.SentenceTransformer.side_effect = ImportError("No module")

        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            embedder = client._load_embedder()
            assert embedder is None

        # Verify hash embedding works
        vector = client._hash_embedding("test text")
        assert len(vector) == client.vector_size
        assert all(isinstance(v, float) for v in vector)


class TestB8CompleteSearchAll:
    """Test search_all() includes all layers."""

    def test_search_all_includes_user_model_layer(self):
        """Verify search_all includes USER_MODEL layer by default."""
        from synapse.layers.manager import LayerManager, MemoryLayer

        manager = LayerManager()

        # Search with default layers
        import asyncio
        results = asyncio.run(manager.search_all("test", user_id="test_user"))

        assert MemoryLayer.USER_MODEL in results

    def test_search_all_includes_working_layer(self):
        """Verify search_all includes WORKING layer by default."""
        from synapse.layers.manager import LayerManager, MemoryLayer

        manager = LayerManager()

        # Set some working memory
        manager.set_working("test_key", "test value")

        # Search with default layers
        import asyncio
        results = asyncio.run(manager.search_all("test"))

        assert MemoryLayer.WORKING in results

    def test_search_user_model_finds_expertise(self):
        """Verify _search_user_model finds matching expertise."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Update user model with expertise
        manager.update_user("test_user", add_expertise={"python": "expert"})

        # Search for expertise
        results = manager._search_user_model("python", "test_user")

        assert len(results) > 0
        assert results[0]["type"] == "expertise"
        assert results[0]["area"] == "python"

    def test_search_user_model_finds_topics(self):
        """Verify _search_user_model finds matching topics."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Update user model with topic
        manager.update_user("test_user", add_topic="machine learning")

        # Search for topic
        results = manager._search_user_model("machine", "test_user")

        assert len(results) > 0
        assert results[0]["type"] == "topic"

    def test_search_user_model_requires_user_id(self):
        """Verify _search_user_model returns empty without user_id."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Search without user_id
        results = manager._search_user_model("python", None)

        assert results == []

    def test_search_working_memory_finds_key(self):
        """Verify _search_working_memory finds matching key."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Set working memory
        manager.set_working("project_name", "synapse")

        # Search by key
        results = manager._search_working_memory("project")

        assert len(results) > 0
        assert results[0]["match_type"] == "key"
        assert results[0]["key"] == "project_name"

    def test_search_working_memory_finds_value(self):
        """Verify _search_working_memory finds matching value."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Set working memory
        manager.set_working("current_task", "fix bug in search function")

        # Search by value
        results = manager._search_working_memory("bug")

        assert len(results) > 0
        assert results[0]["match_type"] == "value"

    def test_search_working_memory_finds_list_item(self):
        """Verify _search_working_memory finds matching list item."""
        from synapse.layers.manager import LayerManager

        manager = LayerManager()

        # Set working memory with list
        manager.set_working("todos", ["implement feature", "write tests", "review code"])

        # Search for list item
        results = manager._search_working_memory("tests")

        assert len(results) > 0
        assert results[0]["match_type"] == "list_item"

    def test_search_all_respects_limit(self):
        """Verify search_all respects limit_per_layer."""
        from synapse.layers.manager import LayerManager, MemoryLayer

        manager = LayerManager()

        # Add multiple working memory entries
        for i in range(10):
            manager.set_working(f"test_key_{i}", f"test value {i}")

        # Search with limit
        import asyncio
        results = asyncio.run(manager.search_all("test", limit_per_layer=3))

        # Working memory results should be limited
        assert len(results[MemoryLayer.WORKING]) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
