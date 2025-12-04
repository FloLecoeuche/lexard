"""Context builder for RAG pipeline.

Formats retrieved chunks into a context window for LLM consumption
with citation markers and token limits.
"""

import logging
from dataclasses import dataclass

import tiktoken

from src.config import Settings, get_settings
from src.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Reference to a source chunk.

    Attributes:
        index: Citation number (1-based, e.g., [1], [2])
        page: Page number in source document
        chunk_index: Index of chunk within document
        document_id: UUID of source document
        excerpt: First N characters of chunk content for reference
    """

    index: int
    page: int
    chunk_index: int
    document_id: str
    excerpt: str


@dataclass
class BuiltContext:
    """Result of building context from chunks.

    Attributes:
        context_text: Formatted context string with citation markers
        citations: List of citation metadata
        chunk_count: Number of chunks included
        total_tokens: Approximate token count of context
        has_relevant_content: Whether any relevant content was found
    """

    context_text: str
    citations: list[Citation]
    chunk_count: int
    total_tokens: int
    has_relevant_content: bool


class ContextBuilder:
    """Builds formatted context from retrieved chunks.

    Formats chunks with citation markers for LLM consumption,
    respecting token limits and generating citation metadata.

    Attributes:
        max_chunks: Maximum number of chunks to include
        max_tokens: Maximum token count for context
        excerpt_length: Length of excerpt in citations
    """

    def __init__(
        self,
        max_chunks: int | None = None,
        max_tokens: int | None = None,
        excerpt_length: int | None = None,
        settings: Settings | None = None,
    ):
        """Initialize context builder.

        Args:
            max_chunks: Maximum chunks to include. Defaults to config value (8).
            max_tokens: Maximum tokens. Defaults to config value (3000).
            excerpt_length: Excerpt length for citations. Defaults to config value (100).
            settings: Settings instance. If None, uses get_settings().
        """
        if settings is None:
            settings = get_settings()

        self.max_chunks = max_chunks if max_chunks is not None else settings.context.max_chunks
        self.max_tokens = max_tokens if max_tokens is not None else settings.context.max_tokens
        self.excerpt_length = (
            excerpt_length if excerpt_length is not None else settings.context.excerpt_length
        )

        # Use cl100k_base encoding (GPT-4/ChatGPT compatible, works for most models)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to tokenize

        Returns:
            Number of tokens
        """
        return len(self._tokenizer.encode(text))

    def _create_excerpt(self, content: str) -> str:
        """Create excerpt from chunk content.

        Args:
            content: Full chunk content

        Returns:
            Truncated excerpt with ellipsis if needed
        """
        if len(content) <= self.excerpt_length:
            return content
        return content[: self.excerpt_length] + "..."

    def build(self, chunks: list[RetrievedChunk]) -> BuiltContext:
        """Build context from retrieved chunks.

        Formats chunks with citation markers [1], [2], etc., respecting
        token limits and generating citation metadata.

        Args:
            chunks: List of retrieved chunks (sorted by relevance)

        Returns:
            BuiltContext with formatted text and citations
        """
        # Handle empty chunks case
        if not chunks:
            logger.debug("No chunks provided to context builder")
            return BuiltContext(
                context_text="",
                citations=[],
                chunk_count=0,
                total_tokens=0,
                has_relevant_content=False,
            )

        context_parts = []
        citations = []
        total_tokens = 0

        for i, chunk in enumerate(chunks[: self.max_chunks]):
            # Check token limit before adding
            chunk_tokens = self._count_tokens(chunk.content)

            if total_tokens + chunk_tokens > self.max_tokens:
                logger.debug(
                    "Token limit reached after %d chunks (total: %d tokens)",
                    len(citations),
                    total_tokens,
                )
                break

            # Create citation marker and formatted chunk
            citation_index = i + 1
            citation_marker = f"[{citation_index}]"
            context_parts.append(f"{citation_marker} {chunk.content}")

            # Record citation metadata
            citations.append(
                Citation(
                    index=citation_index,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    document_id=chunk.document_id,
                    excerpt=self._create_excerpt(chunk.content),
                )
            )

            total_tokens += chunk_tokens

        # Join chunks with double newlines for readability
        context_text = "\n\n".join(context_parts)

        logger.info(
            "Built context: %d chunks, %d tokens",
            len(citations),
            total_tokens,
        )

        return BuiltContext(
            context_text=context_text,
            citations=citations,
            chunk_count=len(citations),
            total_tokens=total_tokens,
            has_relevant_content=True,
        )
