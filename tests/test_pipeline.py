"""Tests for RAG pipeline module."""

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.rag.context import BuiltContext, Citation
from src.rag.llm import LLMResponse
from src.rag.pipeline import (
    CitationChunk,
    Confidence,
    RAGPipeline,
    RAGResponse,
)
from src.rag.retriever import RetrievedChunk


def make_chunk(
    content: str = "Test content",
    score: float = 0.85,
    page: int = 1,
    chunk_index: int = 0,
    document_id: str = "doc-123",
    content_hash: str = "hash123",
) -> RetrievedChunk:
    """Helper to create test chunks."""
    return RetrievedChunk(
        content=content,
        score=score,
        page=page,
        chunk_index=chunk_index,
        document_id=document_id,
        content_hash=content_hash,
    )


@pytest.fixture
def mock_retriever():
    """Create a mock retriever."""
    return MagicMock()


@pytest.fixture
def mock_context_builder():
    """Create a mock context builder."""
    return MagicMock()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return MagicMock()


@pytest.fixture
def mock_settings():
    """Create mock settings."""

    @dataclass
    class MockSettings:
        pass

    return MockSettings()


@pytest.fixture
def pipeline(mock_retriever, mock_context_builder, mock_llm_client, mock_settings):
    """Create a RAG pipeline with mocked dependencies."""
    return RAGPipeline(
        retriever=mock_retriever,
        context_builder=mock_context_builder,
        llm_client=mock_llm_client,
        settings=mock_settings,
    )


class TestConfidenceEnum:
    """Tests for Confidence enum."""

    def test_confidence_values(self):
        """Confidence enum should have expected values."""
        assert Confidence.HIGH.value == "high"
        assert Confidence.MEDIUM.value == "medium"
        assert Confidence.LOW.value == "low"

    def test_confidence_is_string_enum(self):
        """Confidence should be usable as string."""
        assert str(Confidence.HIGH) == "Confidence.HIGH"
        assert Confidence.HIGH == "high"


class TestCitationChunk:
    """Tests for CitationChunk dataclass."""

    def test_citation_chunk_creation(self):
        """CitationChunk should store all fields."""
        chunk = CitationChunk(
            content="Test content",
            page=2,
            chunk_index=3,
            score=0.92,
        )

        assert chunk.content == "Test content"
        assert chunk.page == 2
        assert chunk.chunk_index == 3
        assert chunk.score == 0.92


class TestRAGResponse:
    """Tests for RAGResponse dataclass."""

    def test_response_creation(self):
        """RAGResponse should store all fields."""
        chunk = CitationChunk(
            content="Source",
            page=1,
            chunk_index=0,
            score=0.9,
        )
        response = RAGResponse(
            answer="The answer is 42.",
            citation_chunks=[chunk],
            confidence=Confidence.HIGH,
            has_relevant_content=True,
        )

        assert response.answer == "The answer is 42."
        assert len(response.citation_chunks) == 1
        assert response.confidence == Confidence.HIGH
        assert response.has_relevant_content is True


class TestRAGPipelineInit:
    """Tests for RAGPipeline initialization."""

    def test_pipeline_stores_components(
        self, mock_retriever, mock_context_builder, mock_llm_client, mock_settings
    ):
        """Pipeline should store its components."""
        pipeline = RAGPipeline(
            retriever=mock_retriever,
            context_builder=mock_context_builder,
            llm_client=mock_llm_client,
            settings=mock_settings,
        )

        assert pipeline.retriever is mock_retriever
        assert pipeline.context_builder is mock_context_builder
        assert pipeline.llm_client is mock_llm_client


class TestRAGPipelineQuery:
    """Tests for the query method."""

    def test_query_returns_response(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Query should return a RAGResponse."""
        # Setup mocks
        chunks = [make_chunk(score=0.9)]
        mock_retriever.retrieve.return_value = chunks

        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Test content",
            citations=[Citation(index=1, page=1, chunk_index=0, document_id="doc-123", excerpt="Test...")],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )

        mock_llm_client.generate.return_value = LLMResponse(
            content="Based on [1], the answer is...",
            model="test-model",
            total_tokens=20,
            finish_reason="stop",
        )

        response = pipeline.query("What is the answer?")

        assert isinstance(response, RAGResponse)
        assert response.answer == "Based on [1], the answer is..."
        assert response.has_relevant_content is True

    def test_query_with_document_filter(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Query should pass document_id to retriever."""
        mock_retriever.retrieve.return_value = [make_chunk()]
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Content",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        pipeline.query("Question?", document_id="doc-456")

        mock_retriever.retrieve.assert_called_once_with("Question?", "doc-456")

    def test_query_no_results_returns_low_confidence(self, pipeline, mock_retriever):
        """Query with no results should return appropriate response."""
        mock_retriever.retrieve.return_value = []

        response = pipeline.query("Unknown topic?")

        assert response.has_relevant_content is False
        assert response.confidence == Confidence.LOW
        assert "could not find" in response.answer.lower()
        assert response.citation_chunks == []

    def test_query_builds_context_from_chunks(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Query should build context from retrieved chunks."""
        chunks = [make_chunk(content="Chunk 1"), make_chunk(content="Chunk 2")]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Chunk 1\n\n[2] Chunk 2",
            citations=[],
            chunk_count=2,
            total_tokens=20,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        pipeline.query("Question?")

        mock_context_builder.build.assert_called_once_with(chunks)

    def test_query_generates_answer_with_llm(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Query should call LLM with proper prompt."""
        mock_retriever.retrieve.return_value = [make_chunk()]
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Context text",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="LLM answer",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        response = pipeline.query("What is X?")

        mock_llm_client.generate.assert_called_once()
        call_kwargs = mock_llm_client.generate.call_args[1]
        assert "What is X?" in call_kwargs["prompt"]
        assert "[1] Context text" in call_kwargs["prompt"]
        assert call_kwargs["system_prompt"] is not None


class TestConfidenceCalculation:
    """Tests for confidence scoring."""

    def test_high_confidence_threshold(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """High scores should result in HIGH confidence."""
        chunks = [make_chunk(score=0.95), make_chunk(score=0.90)]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="",
            citations=[],
            chunk_count=2,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        response = pipeline.query("High confidence query")

        assert response.confidence == Confidence.HIGH

    def test_medium_confidence_threshold(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Medium scores should result in MEDIUM confidence."""
        chunks = [make_chunk(score=0.80), make_chunk(score=0.78)]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="",
            citations=[],
            chunk_count=2,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        response = pipeline.query("Medium confidence query")

        assert response.confidence == Confidence.MEDIUM

    def test_low_confidence_threshold(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Low scores should result in LOW confidence."""
        chunks = [make_chunk(score=0.72), make_chunk(score=0.71)]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="",
            citations=[],
            chunk_count=2,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        response = pipeline.query("Low confidence query")

        assert response.confidence == Confidence.LOW


class TestCitationChunkBuilding:
    """Tests for citation chunk building."""

    def test_citation_chunks_match_context_count(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Citation chunks should only include chunks used in context."""
        chunks = [
            make_chunk(content="Chunk 1", score=0.9, page=1, chunk_index=0),
            make_chunk(content="Chunk 2", score=0.85, page=2, chunk_index=1),
            make_chunk(content="Chunk 3", score=0.8, page=3, chunk_index=2),
        ]
        mock_retriever.retrieve.return_value = chunks

        # Context only used 2 chunks (due to token limit or max_chunks)
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Chunk 1\n\n[2] Chunk 2",
            citations=[],
            chunk_count=2,  # Only 2 chunks used
            total_tokens=20,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        response = pipeline.query("Question?")

        assert len(response.citation_chunks) == 2
        assert response.citation_chunks[0].content == "Chunk 1"
        assert response.citation_chunks[1].content == "Chunk 2"

    def test_citation_chunks_preserve_metadata(self, pipeline, mock_retriever, mock_context_builder, mock_llm_client):
        """Citation chunks should preserve chunk metadata."""
        chunks = [make_chunk(content="Content", score=0.88, page=5, chunk_index=3)]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Content",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="Answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        response = pipeline.query("Question?")

        citation = response.citation_chunks[0]
        assert citation.content == "Content"
        assert citation.page == 5
        assert citation.chunk_index == 3
        assert citation.score == 0.88
