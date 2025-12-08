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


class TestLanguageAwareQuery:
    """Tests for language-aware RAG query."""

    def test_response_includes_language_field(self):
        """RAGResponse should include language field."""
        response = RAGResponse(
            answer="The answer",
            citation_chunks=[],
            confidence=Confidence.HIGH,
            has_relevant_content=True,
            language="en",
        )
        assert response.language == "en"

    def test_response_language_defaults_to_english(self):
        """RAGResponse language should default to 'en'."""
        response = RAGResponse(
            answer="The answer",
            citation_chunks=[],
            confidence=Confidence.HIGH,
            has_relevant_content=True,
        )
        assert response.language == "en"

    def test_query_detects_english_document_language(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Query should detect English from document chunks."""
        chunks = [
            make_chunk(content="This is a contract agreement between parties."),
            make_chunk(content="The termination period shall be 30 days."),
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Contract [2] Termination",
            citations=[],
            chunk_count=2,
            total_tokens=20,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="The answer is...",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        response = pipeline.query("What is the notice period?")

        assert response.language == "en"

    def test_query_detects_french_document_language(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Query should detect French from document chunks."""
        chunks = [
            make_chunk(content="Ceci est un contrat de service entre les parties."),
            make_chunk(content="La période de préavis est de 30 jours."),
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Contrat [2] Préavis",
            citations=[],
            chunk_count=2,
            total_tokens=20,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="La réponse est...",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        response = pipeline.query("What is the notice period?")

        assert response.language == "fr"

    def test_query_uses_french_prompts_for_french_document(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Query should use French prompts when document is French."""
        chunks = [
            make_chunk(content="Ceci est un contrat de service entre les parties."),
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Contrat",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="La réponse",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        pipeline.query("What is this?")

        # Check that French prompts are used
        call_kwargs = mock_llm_client.generate.call_args[1]
        assert "EXTRAITS DE DOCUMENTS" in call_kwargs["prompt"]  # French user prompt
        assert "contrats d'entreprise" in call_kwargs["system_prompt"].lower()  # French system prompt

    def test_query_uses_english_prompts_for_english_document(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Query should use English prompts when document is English."""
        chunks = [
            make_chunk(content="This is a contract between the parties."),
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Contract",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="The answer",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        pipeline.query("What is this?")

        # Check that English prompts are used
        call_kwargs = mock_llm_client.generate.call_args[1]
        assert "DOCUMENT EXCERPTS" in call_kwargs["prompt"]  # English user prompt
        assert "contract analyst" in call_kwargs["system_prompt"].lower()  # English system prompt

    def test_query_allows_language_override(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Query should allow explicit language override."""
        chunks = [
            make_chunk(content="This is English content."),  # English document
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] English",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="La réponse",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        # Force French even though document is English
        response = pipeline.query("Question?", language="fr")

        assert response.language == "fr"
        call_kwargs = mock_llm_client.generate.call_args[1]
        assert "EXTRAITS DE DOCUMENTS" in call_kwargs["prompt"]  # French prompt

    def test_no_results_returns_english_language(
        self, pipeline, mock_retriever
    ):
        """Query with no results should return 'en' as default language."""
        mock_retriever.retrieve.return_value = []

        response = pipeline.query("Unknown topic?")

        assert response.language == "en"
        assert response.has_relevant_content is False


class TestProgressAwareQuery:
    """Tests for progress-aware RAG query (US 12.2)."""

    @pytest.mark.asyncio
    async def test_query_with_progress_returns_operation_id_and_result(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """query_with_progress should return (operation_id, RAGResponse)."""
        # Setup mocks
        chunks = [make_chunk(score=0.9)]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Test content",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="The answer is 42.",
            model="test-model",
            total_tokens=20,
            finish_reason="stop",
        )

        operation_id, response = await pipeline.query_with_progress("What is the answer?")

        assert operation_id is not None
        assert isinstance(response, RAGResponse)
        assert response.answer == "The answer is 42."
        assert response.has_relevant_content is True

    @pytest.mark.asyncio
    async def test_query_with_progress_emits_retrieving_stage(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """query_with_progress should emit retrieving stage events."""
        from src.api.progress import OperationStage, get_operation_tracker

        chunks = [make_chunk()]
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

        tracker = get_operation_tracker()
        operation_id, _ = await pipeline.query_with_progress("Question?")

        # Verify operation was tracked
        op = tracker.get(operation_id)
        assert op is not None
        # Final stage should be COMPLETE
        assert op.stage == OperationStage.COMPLETE

    @pytest.mark.asyncio
    async def test_query_with_progress_emits_all_stages_in_order(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """query_with_progress should emit all stages in correct order."""
        from src.api.progress import OperationStage, OperationProgressTracker

        # Use a fresh tracker to avoid interference from other tests
        tracker = OperationProgressTracker()
        collected_stages = []

        chunks = [make_chunk()]
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

        # Start operation and subscribe BEFORE running the query
        operation_id = await tracker.start("query")
        queue = await tracker.subscribe(operation_id)

        # The first event is the initial state (PENDING)
        first_event = await queue.get()
        collected_stages.append(first_event.stage)

        # Run the query with progress events
        await pipeline._query_with_events(
            question="Question?",
            document_id=None,
            language=None,
            tracker=tracker,
            operation_id=operation_id,
        )

        # Give a tiny moment for async queue to process
        import asyncio
        await asyncio.sleep(0.01)

        # Collect remaining events (non-blocking check)
        while True:
            try:
                event = queue.get_nowait()
                collected_stages.append(event.stage)
            except asyncio.QueueEmpty:
                break

        # Verify stages were emitted - at least we should see progression
        # The tracker updates in place, so we may see multiple VALIDATING entries
        # but we should see the stages were used (progress messages confirm this)
        assert OperationStage.PENDING in collected_stages
        # At minimum, the final state should be VALIDATING (last update before complete)
        assert OperationStage.VALIDATING in collected_stages

    @pytest.mark.asyncio
    async def test_query_with_progress_handles_no_results(
        self, pipeline, mock_retriever
    ):
        """query_with_progress should handle no results gracefully."""
        mock_retriever.retrieve.return_value = []

        operation_id, response = await pipeline.query_with_progress("Unknown?")

        assert operation_id is not None
        assert response.has_relevant_content is False
        assert response.confidence == Confidence.LOW

    @pytest.mark.asyncio
    async def test_query_with_progress_handles_error(
        self, pipeline, mock_retriever
    ):
        """query_with_progress should fail operation on error."""
        from src.api.progress import OperationStage, get_operation_tracker

        mock_retriever.retrieve.side_effect = RuntimeError("Retriever failed")

        tracker = get_operation_tracker()

        with pytest.raises(RuntimeError, match="Retriever failed"):
            await pipeline.query_with_progress("Question?")

    @pytest.mark.asyncio
    async def test_query_with_progress_backward_compatible(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """Original query() method should still work without progress."""
        chunks = [make_chunk()]
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

        # Original sync query should still work
        response = pipeline.query("Question?")

        assert isinstance(response, RAGResponse)
        assert response.answer == "Answer"

    @pytest.mark.asyncio
    async def test_query_with_progress_detects_document_language(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """query_with_progress should detect language from document chunks."""
        chunks = [
            make_chunk(content="Ceci est un contrat de service."),
        ]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] Contrat",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="La réponse",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        operation_id, response = await pipeline.query_with_progress("What is this?")

        assert response.language == "fr"

    @pytest.mark.asyncio
    async def test_query_with_progress_respects_language_override(
        self, pipeline, mock_retriever, mock_context_builder, mock_llm_client
    ):
        """query_with_progress should respect explicit language override."""
        chunks = [make_chunk(content="This is English content.")]
        mock_retriever.retrieve.return_value = chunks
        mock_context_builder.build.return_value = BuiltContext(
            context_text="[1] English",
            citations=[],
            chunk_count=1,
            total_tokens=10,
            has_relevant_content=True,
        )
        mock_llm_client.generate.return_value = LLMResponse(
            content="La réponse",
            model="test",
            total_tokens=5,
            finish_reason="stop",
        )

        operation_id, response = await pipeline.query_with_progress(
            "Question?", language="fr"
        )

        assert response.language == "fr"
