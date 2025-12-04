"""RAG pipeline for end-to-end query processing.

Combines retrieval, context building, and LLM generation to produce
grounded answers with citations.
"""

import logging
from dataclasses import dataclass
from enum import Enum

from src.config import Settings, get_settings
from src.rag.context import BuiltContext, ContextBuilder
from src.rag.llm import OllamaClient, QA_SYSTEM_PROMPT, build_qa_prompt
from src.rag.retriever import Retriever, RetrievedChunk

logger = logging.getLogger(__name__)


class Confidence(str, Enum):
    """Confidence level based on retrieval quality."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CitationChunk:
    """Citation reference with source information.

    Attributes:
        content: Text content of the cited chunk
        page: Page number in source document
        chunk_index: Index of chunk within document
        score: Relevance score from retrieval
    """

    content: str
    page: int
    chunk_index: int
    score: float


@dataclass
class RAGResponse:
    """Response from RAG pipeline.

    Attributes:
        answer: Generated answer text
        citation_chunks: List of cited source chunks
        confidence: Confidence level based on retrieval scores
        has_relevant_content: Whether relevant content was found
    """

    answer: str
    citation_chunks: list[CitationChunk]
    confidence: Confidence
    has_relevant_content: bool


class RAGPipeline:
    """End-to-end RAG pipeline for question answering.

    Orchestrates retrieval, context building, and LLM generation
    to produce grounded answers with citations.

    Attributes:
        retriever: Dense retriever for semantic search
        context_builder: Builder for LLM context window
        llm_client: Ollama client for generation
    """

    # Confidence score thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.75

    def __init__(
        self,
        retriever: Retriever,
        context_builder: ContextBuilder,
        llm_client: OllamaClient,
        settings: Settings | None = None,
    ):
        """Initialize RAG pipeline.

        Args:
            retriever: Dense retriever for semantic search
            context_builder: Builder for formatting context
            llm_client: Ollama client for LLM generation
            settings: Settings instance. If None, uses get_settings().
        """
        if settings is None:
            settings = get_settings()

        self.retriever = retriever
        self.context_builder = context_builder
        self.llm_client = llm_client
        self._settings = settings

    def query(
        self,
        question: str,
        document_id: str | None = None,
    ) -> RAGResponse:
        """Execute RAG query and return grounded answer.

        Retrieves relevant chunks, builds context, generates LLM response,
        and formats the answer with citations.

        Args:
            question: User's question
            document_id: Optional document filter

        Returns:
            RAGResponse with answer and citations
        """
        logger.info(
            "Processing RAG query",
            extra={
                "question_length": len(question),
                "document_id": document_id,
            },
        )

        # 1. Retrieve relevant chunks
        chunks = self.retriever.retrieve(question, document_id)

        # 2. Handle no results
        if not chunks:
            logger.info("No relevant chunks found for query")
            return RAGResponse(
                answer="I could not find relevant information in the provided documents to answer this question.",
                citation_chunks=[],
                confidence=Confidence.LOW,
                has_relevant_content=False,
            )

        # 3. Build context
        context = self.context_builder.build(chunks)

        # 4. Generate LLM response
        answer = self._generate_answer(question, context)

        # 5. Calculate confidence from retrieval scores
        confidence = self._calculate_confidence(chunks)

        # 6. Build citation chunks
        citation_chunks = self._build_citation_chunks(chunks, context)

        logger.info(
            "RAG query complete",
            extra={
                "chunk_count": len(citation_chunks),
                "confidence": confidence.value,
                "answer_length": len(answer),
            },
        )

        return RAGResponse(
            answer=answer,
            citation_chunks=citation_chunks,
            confidence=confidence,
            has_relevant_content=True,
        )

    def _generate_answer(self, question: str, context: BuiltContext) -> str:
        """Generate answer using LLM.

        Args:
            question: User's question
            context: Built context with chunks

        Returns:
            Generated answer text
        """
        prompt = build_qa_prompt(question, context.context_text)

        logger.debug(
            "Generating answer",
            extra={
                "prompt_length": len(prompt),
                "context_tokens": context.total_tokens,
            },
        )

        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT,
        )

        return response.content

    def _calculate_confidence(self, chunks: list[RetrievedChunk]) -> Confidence:
        """Calculate confidence level from chunk scores.

        Uses average retrieval score to determine confidence:
        - HIGH: avg_score >= 0.85
        - MEDIUM: avg_score >= 0.75
        - LOW: avg_score < 0.75

        Args:
            chunks: Retrieved chunks with scores

        Returns:
            Confidence level
        """
        if not chunks:
            return Confidence.LOW

        avg_score = sum(c.score for c in chunks) / len(chunks)

        if avg_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return Confidence.HIGH
        elif avg_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return Confidence.MEDIUM
        else:
            return Confidence.LOW

    def _build_citation_chunks(
        self,
        chunks: list[RetrievedChunk],
        context: BuiltContext,
    ) -> list[CitationChunk]:
        """Build citation chunks from retrieved chunks.

        Only includes chunks that were actually used in context.

        Args:
            chunks: All retrieved chunks
            context: Built context (determines which chunks were used)

        Returns:
            List of CitationChunk objects
        """
        # Only include chunks that fit in context
        used_chunk_count = context.chunk_count

        return [
            CitationChunk(
                content=chunk.content,
                page=chunk.page,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
            )
            for chunk in chunks[:used_chunk_count]
        ]
