"""Tests for context building module."""

from dataclasses import dataclass

import pytest

from src.rag.context import BuiltContext, Citation, ContextBuilder
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
def mock_settings():
    """Create mock settings."""

    @dataclass
    class MockContextConfig:
        max_chunks: int = 8
        max_tokens: int = 3000
        excerpt_length: int = 100

    @dataclass
    class MockSettings:
        context: MockContextConfig

    return MockSettings(context=MockContextConfig())


@pytest.fixture
def context_builder(mock_settings):
    """Create a context builder with mocked settings."""
    return ContextBuilder(settings=mock_settings)


class TestCitation:
    """Tests for the Citation dataclass."""

    def test_citation_creation(self):
        """Citation should store all fields correctly."""
        citation = Citation(
            index=1,
            page=5,
            chunk_index=3,
            document_id="doc-456",
            excerpt="First 100 chars...",
        )

        assert citation.index == 1
        assert citation.page == 5
        assert citation.chunk_index == 3
        assert citation.document_id == "doc-456"
        assert citation.excerpt == "First 100 chars..."


class TestBuiltContext:
    """Tests for the BuiltContext dataclass."""

    def test_built_context_creation(self):
        """BuiltContext should store all fields correctly."""
        context = BuiltContext(
            context_text="[1] Some text",
            citations=[Citation(1, 1, 0, "doc-1", "Some...")],
            chunk_count=1,
            total_tokens=5,
            has_relevant_content=True,
        )

        assert context.context_text == "[1] Some text"
        assert len(context.citations) == 1
        assert context.chunk_count == 1
        assert context.total_tokens == 5
        assert context.has_relevant_content is True


class TestContextBuilderInit:
    """Tests for ContextBuilder initialization."""

    def test_default_values_from_settings(self, mock_settings):
        """ContextBuilder should use config values by default."""
        builder = ContextBuilder(settings=mock_settings)

        assert builder.max_chunks == 8
        assert builder.max_tokens == 3000
        assert builder.excerpt_length == 100

    def test_custom_values_override_settings(self, mock_settings):
        """Custom values should override settings."""
        builder = ContextBuilder(
            max_chunks=4,
            max_tokens=1500,
            excerpt_length=50,
            settings=mock_settings,
        )

        assert builder.max_chunks == 4
        assert builder.max_tokens == 1500
        assert builder.excerpt_length == 50


class TestContextBuilderBuild:
    """Tests for the build method."""

    def test_build_with_single_chunk(self, context_builder):
        """Build should format a single chunk correctly."""
        chunks = [make_chunk(content="Payment is due in 30 days.")]

        result = context_builder.build(chunks)

        assert "[1]" in result.context_text
        assert "Payment is due in 30 days." in result.context_text
        assert result.chunk_count == 1
        assert result.has_relevant_content is True
        assert len(result.citations) == 1
        assert result.citations[0].index == 1

    def test_build_with_multiple_chunks(self, context_builder):
        """Build should format multiple chunks with sequential markers."""
        chunks = [
            make_chunk(content="First chunk content", chunk_index=0),
            make_chunk(content="Second chunk content", chunk_index=1),
            make_chunk(content="Third chunk content", chunk_index=2),
        ]

        result = context_builder.build(chunks)

        assert "[1]" in result.context_text
        assert "[2]" in result.context_text
        assert "[3]" in result.context_text
        assert result.chunk_count == 3
        assert len(result.citations) == 3
        assert result.citations[0].index == 1
        assert result.citations[1].index == 2
        assert result.citations[2].index == 3

    def test_build_empty_chunks(self, context_builder):
        """Build should handle empty chunk list gracefully."""
        result = context_builder.build([])

        assert result.context_text == ""
        assert result.citations == []
        assert result.chunk_count == 0
        assert result.total_tokens == 0
        assert result.has_relevant_content is False

    def test_build_respects_max_chunks(self, mock_settings):
        """Build should not include more than max_chunks."""
        builder = ContextBuilder(max_chunks=2, settings=mock_settings)
        chunks = [make_chunk(content=f"Chunk {i}") for i in range(5)]

        result = builder.build(chunks)

        assert result.chunk_count == 2
        assert len(result.citations) == 2
        assert "[3]" not in result.context_text

    def test_build_respects_token_limit(self, mock_settings):
        """Build should stop adding chunks when token limit is reached."""
        # cl100k_base: ~4 chars per token, so 100 tokens ≈ 400 chars
        builder = ContextBuilder(max_tokens=100, settings=mock_settings)
        # Each chunk is ~200+ tokens
        chunks = [make_chunk(content="x" * 800) for _ in range(5)]

        result = builder.build(chunks)

        # Should only fit 0-1 chunks depending on exact tokenization
        assert result.chunk_count <= 1
        assert result.total_tokens <= 100 or result.chunk_count == 0

    def test_build_citation_metadata(self, context_builder):
        """Build should populate citation metadata correctly."""
        chunks = [
            make_chunk(
                content="Test content here",
                page=5,
                chunk_index=10,
                document_id="doc-xyz",
            )
        ]

        result = context_builder.build(chunks)

        citation = result.citations[0]
        assert citation.index == 1
        assert citation.page == 5
        assert citation.chunk_index == 10
        assert citation.document_id == "doc-xyz"
        assert "Test content here" in citation.excerpt

    def test_build_excerpt_truncation(self, mock_settings):
        """Build should truncate excerpts longer than excerpt_length."""
        builder = ContextBuilder(excerpt_length=20, settings=mock_settings)
        long_content = "This is a very long content that should be truncated for the excerpt."
        chunks = [make_chunk(content=long_content)]

        result = builder.build(chunks)

        citation = result.citations[0]
        assert len(citation.excerpt) == 23  # 20 chars + "..."
        assert citation.excerpt.endswith("...")

    def test_build_excerpt_no_truncation_for_short_content(self, mock_settings):
        """Build should not add ellipsis for short content."""
        builder = ContextBuilder(excerpt_length=100, settings=mock_settings)
        short_content = "Short content"
        chunks = [make_chunk(content=short_content)]

        result = builder.build(chunks)

        citation = result.citations[0]
        assert citation.excerpt == short_content
        assert "..." not in citation.excerpt

    def test_build_chunks_separated_by_newlines(self, context_builder):
        """Chunks should be separated by double newlines."""
        chunks = [
            make_chunk(content="First chunk"),
            make_chunk(content="Second chunk"),
        ]

        result = context_builder.build(chunks)

        assert "\n\n" in result.context_text
        parts = result.context_text.split("\n\n")
        assert len(parts) == 2

    def test_build_preserves_chunk_order(self, context_builder):
        """Build should preserve the order of chunks (relevance order)."""
        chunks = [
            make_chunk(content="Most relevant", score=0.95),
            make_chunk(content="Second relevant", score=0.85),
            make_chunk(content="Third relevant", score=0.75),
        ]

        result = context_builder.build(chunks)

        # First citation should be most relevant
        assert "Most relevant" in result.citations[0].excerpt
        lines = result.context_text.split("\n\n")
        assert "[1] Most relevant" in lines[0]
        assert "[2] Second relevant" in lines[1]
        assert "[3] Third relevant" in lines[2]

    def test_build_token_counting(self, context_builder):
        """Build should accurately count tokens."""
        content = "This is a test sentence with some words."
        chunks = [make_chunk(content=content)]

        result = context_builder.build(chunks)

        # Token count should be positive
        assert result.total_tokens > 0
        # cl100k_base: this sentence is about 9-10 tokens
        assert 5 < result.total_tokens < 20


class TestContextBuilderEdgeCases:
    """Edge case tests for ContextBuilder."""

    def test_build_with_unicode_content(self, context_builder):
        """Build should handle unicode content correctly."""
        chunks = [make_chunk(content="Résumé with émojis 🎉")]

        result = context_builder.build(chunks)

        assert "Résumé" in result.context_text
        assert "🎉" in result.context_text
        assert result.has_relevant_content is True

    def test_build_with_multiline_content(self, context_builder):
        """Build should preserve newlines within chunks."""
        content = "Line 1\nLine 2\nLine 3"
        chunks = [make_chunk(content=content)]

        result = context_builder.build(chunks)

        assert "Line 1\nLine 2\nLine 3" in result.context_text

    def test_build_with_empty_content_chunk(self, context_builder):
        """Build should handle chunks with empty content."""
        chunks = [make_chunk(content="")]

        result = context_builder.build(chunks)

        assert result.has_relevant_content is True  # Chunk was provided
        assert result.chunk_count == 1
        assert result.citations[0].excerpt == ""

    def test_build_with_whitespace_only_chunk(self, context_builder):
        """Build should handle chunks with only whitespace."""
        chunks = [make_chunk(content="   \n\t  ")]

        result = context_builder.build(chunks)

        assert result.has_relevant_content is True
        assert result.chunk_count == 1

    def test_build_mixed_document_ids(self, context_builder):
        """Build should handle chunks from multiple documents."""
        chunks = [
            make_chunk(content="From doc 1", document_id="doc-1"),
            make_chunk(content="From doc 2", document_id="doc-2"),
            make_chunk(content="From doc 3", document_id="doc-3"),
        ]

        result = context_builder.build(chunks)

        assert result.chunk_count == 3
        assert result.citations[0].document_id == "doc-1"
        assert result.citations[1].document_id == "doc-2"
        assert result.citations[2].document_id == "doc-3"
