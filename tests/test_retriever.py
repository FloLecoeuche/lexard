"""Tests for dense retrieval module."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.rag.retriever import RetrievedChunk, Retriever


class MockScoredPoint:
    """Mock Qdrant ScoredPoint for testing."""

    def __init__(self, score: float, payload: dict):
        self.score = score
        self.payload = payload


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = MagicMock()
    # Return a normalized 768-dim vector
    vector = np.random.randn(768).astype(np.float32)
    vector = vector / np.linalg.norm(vector)
    service.embed_query.return_value = vector
    return service


@pytest.fixture
def mock_qdrant_service():
    """Create a mock Qdrant service."""
    service = MagicMock()
    service.collection_name = "test_collection"
    return service


@pytest.fixture
def mock_settings():
    """Create mock settings."""

    @dataclass
    class MockRetrievalConfig:
        top_k: int = 8
        score_threshold: float = 0.7

    @dataclass
    class MockSettings:
        retrieval: MockRetrievalConfig

    return MockSettings(retrieval=MockRetrievalConfig())


@pytest.fixture
def retriever(mock_embedding_service, mock_qdrant_service, mock_settings):
    """Create a retriever with mocked dependencies."""
    return Retriever(
        embedding_service=mock_embedding_service,
        qdrant_service=mock_qdrant_service,
        settings=mock_settings,
    )


class TestRetrievedChunk:
    """Tests for the RetrievedChunk dataclass."""

    def test_chunk_creation(self):
        """RetrievedChunk should store all fields correctly."""
        chunk = RetrievedChunk(
            content="Test content",
            score=0.85,
            page=1,
            chunk_index=0,
            document_id="doc-123",
            content_hash="abc123",
        )

        assert chunk.content == "Test content"
        assert chunk.score == 0.85
        assert chunk.page == 1
        assert chunk.chunk_index == 0
        assert chunk.document_id == "doc-123"
        assert chunk.content_hash == "abc123"

    def test_chunk_comparison(self):
        """RetrievedChunks with same data should be equal."""
        chunk1 = RetrievedChunk(
            content="Test",
            score=0.9,
            page=1,
            chunk_index=0,
            document_id="doc-1",
            content_hash="hash1",
        )
        chunk2 = RetrievedChunk(
            content="Test",
            score=0.9,
            page=1,
            chunk_index=0,
            document_id="doc-1",
            content_hash="hash1",
        )

        assert chunk1 == chunk2


class TestRetrieverInit:
    """Tests for Retriever initialization."""

    def test_default_values_from_settings(
        self, mock_embedding_service, mock_qdrant_service, mock_settings
    ):
        """Retriever should use config values by default."""
        retriever = Retriever(
            embedding_service=mock_embedding_service,
            qdrant_service=mock_qdrant_service,
            settings=mock_settings,
        )

        assert retriever.top_k == 8
        assert retriever.score_threshold == 0.7

    def test_custom_values_override_settings(
        self, mock_embedding_service, mock_qdrant_service, mock_settings
    ):
        """Custom values should override settings."""
        retriever = Retriever(
            embedding_service=mock_embedding_service,
            qdrant_service=mock_qdrant_service,
            top_k=5,
            score_threshold=0.8,
            settings=mock_settings,
        )

        assert retriever.top_k == 5
        assert retriever.score_threshold == 0.8


class TestRetrieverRetrieve:
    """Tests for the retrieve method."""

    def test_retrieval_returns_chunks(self, retriever, mock_qdrant_service):
        """Retrieve should return RetrievedChunk objects."""
        # Mock Qdrant query_points results (returns object with .points attribute)
        mock_response = MagicMock()
        mock_response.points = [
            MockScoredPoint(
                score=0.9,
                payload={
                    "content": "Payment terms content",
                    "page": 1,
                    "chunk_index": 0,
                    "document_id": "doc-123",
                    "content_hash": "hash1",
                },
            ),
            MockScoredPoint(
                score=0.85,
                payload={
                    "content": "More payment info",
                    "page": 2,
                    "chunk_index": 1,
                    "document_id": "doc-123",
                    "content_hash": "hash2",
                },
            ),
        ]
        mock_qdrant_service.client.query_points.return_value = mock_response

        chunks = retriever.retrieve("What are the payment terms?")

        assert len(chunks) == 2
        assert all(isinstance(c, RetrievedChunk) for c in chunks)
        assert chunks[0].content == "Payment terms content"
        assert chunks[0].score == 0.9
        assert chunks[1].score == 0.85

    def test_retrieval_respects_top_k(self, retriever, mock_qdrant_service):
        """Retrieve should pass top_k to Qdrant."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("test query")

        mock_qdrant_service.client.query_points.assert_called_once()
        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        assert call_kwargs["limit"] == 8

    def test_retrieval_respects_score_threshold(self, retriever, mock_qdrant_service):
        """Retrieve should pass score_threshold to Qdrant."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("test query")

        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        assert call_kwargs["score_threshold"] == 0.7

    def test_retrieval_with_document_filter(self, retriever, mock_qdrant_service):
        """Retrieve should filter by document_id when provided."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("termination clause", document_id="doc-456")

        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        query_filter = call_kwargs["query_filter"]

        assert query_filter is not None
        assert len(query_filter.must) == 1
        assert query_filter.must[0].key == "document_id"
        assert query_filter.must[0].match.value == "doc-456"

    def test_retrieval_without_document_filter(self, retriever, mock_qdrant_service):
        """Retrieve should not filter when document_id is None."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("general query")

        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        assert call_kwargs["query_filter"] is None

    def test_retrieval_empty_results(self, retriever, mock_qdrant_service):
        """Retrieve should return empty list when no results match."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        chunks = retriever.retrieve("xyzzy gibberish query")

        assert chunks == []

    def test_retrieval_empty_query(self, retriever, mock_qdrant_service):
        """Retrieve should return empty list for empty query."""
        chunks = retriever.retrieve("")
        assert chunks == []

        chunks = retriever.retrieve("   ")
        assert chunks == []

        # Should not call Qdrant for empty queries
        mock_qdrant_service.client.search.assert_not_called()

    def test_retrieval_calls_embed_query(self, retriever, mock_embedding_service):
        """Retrieve should generate embedding for query."""
        retriever.retrieve("test question")

        mock_embedding_service.embed_query.assert_called_once_with("test question")

    def test_retrieval_uses_correct_collection(self, retriever, mock_qdrant_service):
        """Retrieve should search in configured collection."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("test")

        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        assert call_kwargs["collection_name"] == "test_collection"

    def test_retrieval_requests_payload(self, retriever, mock_qdrant_service):
        """Retrieve should request payload from Qdrant."""
        mock_response = MagicMock()
        mock_response.points = []
        mock_qdrant_service.client.query_points.return_value = mock_response

        retriever.retrieve("test")

        call_kwargs = mock_qdrant_service.client.query_points.call_args[1]
        assert call_kwargs["with_payload"] is True

    def test_retrieval_handles_missing_payload_fields(
        self, retriever, mock_qdrant_service
    ):
        """Retrieve should handle missing payload fields gracefully."""
        mock_response = MagicMock()
        mock_response.points = [
            MockScoredPoint(score=0.8, payload={}),  # Empty payload
            MockScoredPoint(score=0.75, payload=None),  # None payload
        ]
        mock_qdrant_service.client.query_points.return_value = mock_response

        chunks = retriever.retrieve("test")

        assert len(chunks) == 2
        assert chunks[0].content == ""
        assert chunks[0].page == 0
        assert chunks[1].content == ""

    def test_results_sorted_by_score(self, retriever, mock_qdrant_service):
        """Results should be sorted by score (descending)."""
        # Qdrant returns results sorted, but verify we preserve order
        mock_response = MagicMock()
        mock_response.points = [
            MockScoredPoint(
                score=0.95,
                payload={"content": "best", "page": 1, "chunk_index": 0,
                         "document_id": "d", "content_hash": "h1"},
            ),
            MockScoredPoint(
                score=0.85,
                payload={"content": "good", "page": 2, "chunk_index": 1,
                         "document_id": "d", "content_hash": "h2"},
            ),
            MockScoredPoint(
                score=0.75,
                payload={"content": "ok", "page": 3, "chunk_index": 2,
                         "document_id": "d", "content_hash": "h3"},
            ),
        ]
        mock_qdrant_service.client.query_points.return_value = mock_response

        chunks = retriever.retrieve("test")

        assert len(chunks) == 3
        assert chunks[0].score == 0.95
        assert chunks[1].score == 0.85
        assert chunks[2].score == 0.75


class TestRetrieverIntegration:
    """Integration tests with real embedding service (requires model)."""

    @pytest.fixture(scope="class")
    def real_embedding_service(self):
        """Create a real embedding service (slow, loads model)."""
        from src.rag.embeddings import EmbeddingService

        return EmbeddingService()

    @pytest.mark.skipif(
        True,  # Skip by default, enable when Qdrant is available
        reason="Requires running Qdrant instance",
    )
    def test_real_retrieval(self, real_embedding_service):
        """Integration test with real services (requires Qdrant)."""
        from src.db.qdrant import QdrantService

        qdrant = QdrantService()
        retriever = Retriever(
            embedding_service=real_embedding_service,
            qdrant_service=qdrant,
        )

        # This test would require indexed documents
        chunks = retriever.retrieve("test query")
        assert isinstance(chunks, list)
