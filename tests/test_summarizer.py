"""Tests for document summarization tool."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

from src.agent.tools.summarizer import SummarizerTool, SummaryResult
from src.rag.llm import LLMResponse


@dataclass
class MockPoint:
    """Mock Qdrant point."""
    payload: dict


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.generate = MagicMock(return_value=LLMResponse(
        content="This is a test summary of the document.",
        model="test-model",
        total_tokens=50,
        finish_reason="stop"
    ))
    return client


@pytest.fixture
def mock_qdrant_service():
    """Create mock Qdrant service."""
    service = MagicMock()
    service.collection_name = "test_collection"
    service.client = MagicMock()
    return service


@pytest.fixture
def summarizer(mock_llm_client, mock_qdrant_service):
    """Create SummarizerTool instance."""
    return SummarizerTool(
        llm_client=mock_llm_client,
        qdrant_service=mock_qdrant_service
    )


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        MockPoint(payload={
            "content": "This is the first chunk about contract terms and conditions.",
            "page": 1,
            "chunk_index": 0,
            "document_id": "doc-123"
        }),
        MockPoint(payload={
            "content": "This is the second chunk about payment and pricing.",
            "page": 1,
            "chunk_index": 1,
            "document_id": "doc-123"
        }),
        MockPoint(payload={
            "content": "This is the third chunk about termination clauses.",
            "page": 2,
            "chunk_index": 2,
            "document_id": "doc-123"
        }),
    ]


class TestSummaryResult:
    """Test SummaryResult dataclass."""

    def test_result_creation(self):
        """Test creating a summary result."""
        result = SummaryResult(
            executive_summary="This is the summary.",
            key_points=["Point 1", "Point 2"],
            section_summaries=[],
            word_count=5,
            chunk_count=3
        )
        assert result.executive_summary == "This is the summary."
        assert len(result.key_points) == 2
        assert result.word_count == 5
        assert result.chunk_count == 3

    def test_result_defaults(self):
        """Test result with default values."""
        result = SummaryResult(
            executive_summary="Summary",
            key_points=[]
        )
        assert result.section_summaries == []
        assert result.word_count == 0
        assert result.chunk_count == 0


class TestSummarizerInit:
    """Test SummarizerTool initialization."""

    def test_init(self, mock_llm_client, mock_qdrant_service):
        """Test basic initialization."""
        summarizer = SummarizerTool(
            llm_client=mock_llm_client,
            qdrant_service=mock_qdrant_service
        )
        assert summarizer.llm == mock_llm_client
        assert summarizer.qdrant_service == mock_qdrant_service

    def test_constants(self, summarizer):
        """Test default constants are set."""
        assert summarizer.CHUNK_BATCH_SIZE == 5
        assert summarizer.MAX_CHUNKS == 50


class TestGetAllChunks:
    """Test chunk retrieval."""

    @pytest.mark.asyncio
    async def test_get_all_chunks(self, summarizer, sample_chunks):
        """Test retrieving all chunks for a document."""
        summarizer.qdrant_service.client.scroll.return_value = (sample_chunks, None)

        chunks = await summarizer._get_all_chunks("doc-123")

        assert len(chunks) == 3
        summarizer.qdrant_service.client.scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_sorted_by_index(self, summarizer, sample_chunks):
        """Test chunks are sorted by chunk_index."""
        # Return in random order
        shuffled = [sample_chunks[2], sample_chunks[0], sample_chunks[1]]
        summarizer.qdrant_service.client.scroll.return_value = (shuffled, None)

        chunks = await summarizer._get_all_chunks("doc-123")

        indices = [c.payload["chunk_index"] for c in chunks]
        assert indices == [0, 1, 2]


class TestSummarizeChunk:
    """Test single chunk summarization."""

    @pytest.mark.asyncio
    async def test_summarize_chunk(self, summarizer, sample_chunks):
        """Test summarizing a single chunk."""
        result = await summarizer._summarize_chunk(sample_chunks[0])

        assert result == "This is a test summary of the document."
        summarizer.llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_chunk(self, summarizer):
        """Test handling empty chunk."""
        empty_chunk = MockPoint(payload={"content": "", "page": 1, "chunk_index": 0})

        result = await summarizer._summarize_chunk(empty_chunk)

        assert result == "[Empty chunk]"


class TestSummarizeChunksBatch:
    """Test batch chunk summarization."""

    @pytest.mark.asyncio
    async def test_batch_summarization(self, summarizer, sample_chunks):
        """Test batch summarization processes all chunks."""
        results = await summarizer._summarize_chunks_batch(sample_chunks)

        assert len(results) == 3
        assert all("summary" in r for r in results)
        assert all("page" in r for r in results)
        assert all("chunk_index" in r for r in results)

    @pytest.mark.asyncio
    async def test_batch_handles_errors(self, summarizer, sample_chunks):
        """Test batch summarization handles individual chunk errors."""
        # Make the second chunk fail
        call_count = [0]
        def mock_generate(prompt):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("LLM error")
            return LLMResponse(
                content="Summary",
                model="test",
                total_tokens=10,
                finish_reason="stop"
            )

        summarizer.llm.generate = mock_generate

        results = await summarizer._summarize_chunks_batch(sample_chunks)

        assert len(results) == 3
        assert results[1]["summary"] == "[Summary unavailable]"


class TestAggregateSummaries:
    """Test summary aggregation."""

    @pytest.mark.asyncio
    async def test_aggregate_summaries(self, summarizer):
        """Test aggregating chunk summaries."""
        summarizer.llm.generate.return_value = LLMResponse(
            content="""## Executive Summary
This is the executive summary of the document.

## Key Points
- Point 1
- Point 2
- Point 3""",
            model="test",
            total_tokens=100,
            finish_reason="stop"
        )

        summaries = [
            {"page": 1, "chunk_index": 0, "summary": "Summary 1"},
            {"page": 1, "chunk_index": 1, "summary": "Summary 2"},
        ]

        result = await summarizer._aggregate_summaries(summaries)

        assert "executive_summary" in result
        assert "key_points" in result
        assert len(result["key_points"]) == 3

    @pytest.mark.asyncio
    async def test_aggregate_empty_summaries(self, summarizer):
        """Test aggregation with no valid summaries."""
        summaries = [
            {"page": 1, "chunk_index": 0, "summary": "[Summary unavailable]"},
        ]

        result = await summarizer._aggregate_summaries(summaries)

        assert "Unable to generate summary" in result["executive_summary"]


class TestParseSummaryResponse:
    """Test response parsing."""

    def test_parse_structured_response(self, summarizer):
        """Test parsing properly formatted response."""
        text = """## Executive Summary
This is a well-structured executive summary with multiple sentences.
It covers the main points of the document.

## Key Points
- First key point
- Second key point
- Third key point"""

        result = summarizer._parse_summary_response(text)

        assert "executive summary" in result["executive_summary"].lower()
        assert len(result["key_points"]) == 3
        assert "First key point" in result["key_points"]

    def test_parse_unstructured_response(self, summarizer):
        """Test parsing unstructured response."""
        text = "This is just a plain text summary without any structure."

        result = summarizer._parse_summary_response(text)

        assert result["executive_summary"] == text
        # Should extract sentences as fallback key points
        assert len(result["key_points"]) >= 0

    def test_parse_alternate_format(self, summarizer):
        """Test parsing alternate formatting (without ##)."""
        text = """Executive Summary
This is the summary.

Key Points
- Point A
- Point B"""

        result = summarizer._parse_summary_response(text)

        assert "This is the summary" in result["executive_summary"]
        assert len(result["key_points"]) >= 2

    def test_parse_asterisk_bullets(self, summarizer):
        """Test parsing with asterisk bullets."""
        text = """## Executive Summary
Summary here.

## Key Points
* Point 1
* Point 2"""

        result = summarizer._parse_summary_response(text)

        assert len(result["key_points"]) == 2


class TestSummarize:
    """Test main summarize method."""

    @pytest.mark.asyncio
    async def test_summarize_document(self, summarizer, sample_chunks):
        """Test full document summarization."""
        summarizer.qdrant_service.client.scroll.return_value = (sample_chunks, None)
        summarizer.llm.generate.return_value = LLMResponse(
            content="""## Executive Summary
This document covers contract terms.

## Key Points
- Payment terms defined
- Termination clauses included""",
            model="test",
            total_tokens=50,
            finish_reason="stop"
        )

        result = await summarizer.summarize("doc-123")

        assert isinstance(result, SummaryResult)
        assert result.chunk_count == 3
        assert len(result.key_points) >= 2

    @pytest.mark.asyncio
    async def test_summarize_no_chunks(self, summarizer):
        """Test summarization with no chunks raises error."""
        summarizer.qdrant_service.client.scroll.return_value = ([], None)

        with pytest.raises(ValueError, match="No chunks found"):
            await summarizer.summarize("nonexistent-doc")

    @pytest.mark.asyncio
    async def test_summarize_detailed_style(self, summarizer, sample_chunks):
        """Test detailed style includes section summaries."""
        summarizer.qdrant_service.client.scroll.return_value = (sample_chunks, None)
        summarizer.llm.generate.return_value = LLMResponse(
            content="Summary",
            model="test",
            total_tokens=10,
            finish_reason="stop"
        )

        result = await summarizer.summarize("doc-123", style="detailed")

        assert len(result.section_summaries) == 3

    @pytest.mark.asyncio
    async def test_summarize_executive_style(self, summarizer, sample_chunks):
        """Test executive style excludes section summaries."""
        summarizer.qdrant_service.client.scroll.return_value = (sample_chunks, None)
        summarizer.llm.generate.return_value = LLMResponse(
            content="Summary",
            model="test",
            total_tokens=10,
            finish_reason="stop"
        )

        result = await summarizer.summarize("doc-123", style="executive")

        assert len(result.section_summaries) == 0


class TestLongDocuments:
    """Test handling of long documents."""

    @pytest.mark.asyncio
    async def test_max_chunks_limit(self, summarizer):
        """Test long documents are limited to MAX_CHUNKS."""
        # Create 60 chunks (more than MAX_CHUNKS=50)
        many_chunks = [
            MockPoint(payload={
                "content": f"Chunk {i}",
                "page": i // 10,
                "chunk_index": i,
                "document_id": "doc-123"
            })
            for i in range(60)
        ]

        summarizer.qdrant_service.client.scroll.return_value = (many_chunks, None)
        summarizer.llm.generate.return_value = LLMResponse(
            content="Summary",
            model="test",
            total_tokens=10,
            finish_reason="stop"
        )

        result = await summarizer.summarize("doc-123")

        # Should process at most MAX_CHUNKS
        assert result.chunk_count == 50
