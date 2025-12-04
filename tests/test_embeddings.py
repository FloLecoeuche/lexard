"""Tests for embedding generation module."""

import numpy as np
import pytest

from src.rag.embeddings import EmbeddingError, EmbeddingService


# Module-scoped fixture to avoid reloading the model for each test
@pytest.fixture(scope="module")
def embedding_service():
    """Create a shared EmbeddingService instance for all tests in this module.

    The model is expensive to load (~5s), so we share it across tests.
    """
    return EmbeddingService()


class TestEmbeddingService:
    """Tests for the EmbeddingService class."""

    @pytest.fixture
    def service(self, embedding_service):
        """Use the shared embedding service."""
        return embedding_service

    def test_dimension_property(self, service):
        """Dimension should be 768 for all-mpnet-base-v2."""
        assert service.dimension == 768

    def test_model_lazy_loading(self):
        """Model should not be loaded until accessed."""
        service = EmbeddingService()
        assert service._model is None

        # Access model property - this loads the model
        _ = service.model
        assert service._model is not None

    def test_embed_query_dimension(self, service):
        """Single query embedding should have correct dimension."""
        embedding = service.embed_query("test query")
        assert embedding.shape == (768,)

    def test_embed_query_normalized(self, service):
        """Query embedding should be L2 normalized."""
        embedding = service.embed_query("test query")
        norm = np.linalg.norm(embedding)
        assert np.isclose(norm, 1.0, atol=1e-5)

    def test_embed_query_empty_raises_error(self, service):
        """Empty query should raise EmbeddingError."""
        with pytest.raises(EmbeddingError, match="cannot be empty"):
            service.embed_query("")

        with pytest.raises(EmbeddingError, match="cannot be empty"):
            service.embed_query("   ")

    def test_batch_embedding_dimension(self, service):
        """Batch embedding should have correct dimensions."""
        texts = ["text 1", "text 2", "text 3"]
        embeddings = service.embed(texts)
        assert embeddings.shape == (3, 768)

    def test_batch_embedding_normalized(self, service):
        """Batch embeddings should be L2 normalized."""
        texts = ["text 1", "text 2", "text 3"]
        embeddings = service.embed(texts)

        for embedding in embeddings:
            norm = np.linalg.norm(embedding)
            assert np.isclose(norm, 1.0, atol=1e-5)

    def test_empty_texts_returns_empty_array(self, service):
        """Empty texts list should return empty array with correct shape."""
        embeddings = service.embed([])
        assert embeddings.shape == (0, 768)

    def test_similar_texts_have_similar_embeddings(self, service):
        """Semantically similar texts should have high cosine similarity."""
        text1 = "The cat sat on the mat."
        text2 = "A cat was sitting on the mat."
        text3 = "The stock market crashed yesterday."

        emb1 = service.embed_query(text1)
        emb2 = service.embed_query(text2)
        emb3 = service.embed_query(text3)

        # Cosine similarity (embeddings are normalized)
        sim_1_2 = np.dot(emb1, emb2)
        sim_1_3 = np.dot(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_1_2 > sim_1_3

    def test_different_texts_have_different_embeddings(self, service):
        """Different texts should produce different embeddings."""
        emb1 = service.embed_query("Hello world")
        emb2 = service.embed_query("Goodbye universe")

        # Embeddings should not be identical
        assert not np.allclose(emb1, emb2)

    def test_embed_chunks(self, service):
        """embed_chunks should work with Chunk-like objects."""
        from dataclasses import dataclass

        @dataclass
        class MockChunk:
            content: str

        chunks = [
            MockChunk(content="First chunk content"),
            MockChunk(content="Second chunk content"),
        ]

        embeddings = service.embed_chunks(chunks)
        assert embeddings.shape == (2, 768)

    def test_custom_batch_size(self, service):
        """Custom batch size should work correctly."""
        texts = [f"text {i}" for i in range(10)]
        embeddings = service.embed(texts, batch_size=2)
        assert embeddings.shape == (10, 768)

    def test_custom_model_name(self):
        """Custom model name should be stored."""
        service = EmbeddingService(model_name="paraphrase-MiniLM-L6-v2")
        assert service.model_name == "paraphrase-MiniLM-L6-v2"

    def test_custom_device(self):
        """Custom device should be stored."""
        service = EmbeddingService(device="cuda")
        assert service.device == "cuda"

    def test_deterministic_embeddings(self, service):
        """Same text should produce same embedding."""
        text = "This is a test sentence."
        emb1 = service.embed_query(text)
        emb2 = service.embed_query(text)
        assert np.allclose(emb1, emb2)


class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService with real chunks."""

    def test_embed_real_chunks(self, embedding_service):
        """Test embedding actual Chunk objects from chunking module."""
        from src.rag.chunking import Chunk

        chunks = [
            Chunk(
                content="This is the first chunk of text.",
                chunk_index=0,
                page=1,
                pages=[1],
                token_count=8,
                content_hash="abc123",
            ),
            Chunk(
                content="This is the second chunk of text.",
                chunk_index=1,
                page=1,
                pages=[1],
                token_count=8,
                content_hash="def456",
            ),
        ]

        embeddings = embedding_service.embed_chunks(chunks)
        assert embeddings.shape == (2, 768)
