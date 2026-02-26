"""
Tests for Fog Layer: Retriever + Vector Store + Embeddings
Uses mocked models to avoid requiring actual ML model downloads.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.fog.vector_store import VectorStore, Document, SearchResult
from src.fog.retriever import Retriever, RetrievalResult


# ---- Vector Store Tests ----

class TestVectorStore:
    """Test FAISS-based vector store."""

    def test_create_empty_store(self):
        store = VectorStore(dimension=4)
        assert store.size == 0
        assert store.dimension == 4

    def test_add_count_mismatch_raises(self):
        store = VectorStore(dimension=4)
        docs = [Document(id="d1", content="test", source="s")]
        bad_emb = np.random.rand(3, 4).astype(np.float32)  # 3 != 1

        with pytest.raises(ValueError, match="Mismatch"):
            store.add_documents(docs, bad_emb)

    def test_add_dimension_mismatch_raises(self):
        store = VectorStore(dimension=4)
        docs = [Document(id="d1", content="test", source="s")]
        bad_emb = np.random.rand(1, 8).astype(np.float32)  # 8 != 4

        # This will trigger the FAISS lazy import, need to mock it
        with patch.dict("sys.modules", {"faiss": MagicMock()}):
            with pytest.raises(ValueError, match="dimension mismatch"):
                store.add_documents(docs, bad_emb)


# ---- Retrieval Result Tests ----

class TestRetrievalResult:
    """Test result formatting."""

    def test_to_context_string_with_results(self):
        results = [
            SearchResult(
                document=Document(id="d1", content="Fix: pip install numpy", source="docs/numpy.md"),
                score=0.92,
                rank=1,
            ),
            SearchResult(
                document=Document(id="d2", content="Use --legacy-peer-deps", source="docs/npm.md"),
                score=0.78,
                rank=2,
            ),
        ]
        rr = RetrievalResult(query="numpy not found", results=results, total_candidates=100)
        ctx = rr.to_context_string()
        assert "pip install numpy" in ctx
        assert "legacy-peer-deps" in ctx

    def test_to_context_string_empty(self):
        rr = RetrievalResult(query="test", results=[], total_candidates=0)
        assert "No relevant documentation" in rr.to_context_string()


# ---- Retriever Tests ----

class TestRetriever:
    """Test the retriever orchestration with mocked embeddings."""

    def test_retrieve_with_mocked_components(self):
        """Test retrieve() with fully mocked embedding generator and vector store."""
        mock_emb = MagicMock()
        mock_emb.encode_single.return_value = np.random.rand(384).astype(np.float32)

        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(
                document=Document(id="d1", content="Fix: pip install", source="docs"),
                score=0.9,
                rank=1,
            )
        ]
        mock_store.size = 10

        retriever = Retriever(embedding_generator=mock_emb, vector_store=mock_store)
        result = retriever.retrieve("ModuleNotFoundError numpy")

        assert isinstance(result, RetrievalResult)
        assert len(result.results) == 1
        assert result.results[0].score == 0.9
        mock_emb.encode_single.assert_called_once()
        mock_store.search.assert_called_once()

    def test_build_index_with_mocked_components(self):
        """Test build_index() with fully mocked components."""
        mock_emb = MagicMock()
        mock_emb.encode.return_value = np.random.rand(2, 384).astype(np.float32)

        mock_store = MagicMock()
        mock_store.size = 0

        retriever = Retriever(embedding_generator=mock_emb, vector_store=mock_store)
        retriever.build_index([
            {"id": "1", "content": "error fix", "source": "s"},
            {"id": "2", "content": "npm fix", "source": "s"},
        ])

        mock_emb.encode.assert_called_once()
        mock_store.add_documents.assert_called_once()
