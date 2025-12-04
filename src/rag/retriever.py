"""Dense retriever for semantic search over Qdrant.

Retrieves relevant document chunks based on embedding similarity
with configurable score thresholds and document filtering.
"""

import logging
from dataclasses import dataclass

from qdrant_client.http import models

from src.config import Settings, get_settings
from src.db.qdrant import QdrantService
from src.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved chunk with relevance score and metadata.

    Attributes:
        content: Text content of the chunk
        score: Cosine similarity score (0.0 to 1.0)
        page: Primary page number where chunk appears
        chunk_index: Index of chunk within document
        document_id: UUID of source document
        content_hash: Hash for deduplication
    """

    content: str
    score: float
    page: int
    chunk_index: int
    document_id: str
    content_hash: str


class Retriever:
    """Dense retriever using embedding similarity search.

    Retrieves the most relevant chunks from Qdrant for a query
    using embedding similarity. Supports score thresholding and
    document filtering.

    Attributes:
        embedding_service: Service for generating query embeddings
        qdrant_service: Service for vector database operations
        top_k: Maximum number of chunks to retrieve
        score_threshold: Minimum similarity score (chunks below are discarded)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
        top_k: int | None = None,
        score_threshold: float | None = None,
        settings: Settings | None = None,
    ):
        """Initialize retriever.

        Args:
            embedding_service: Service for generating query embeddings
            qdrant_service: Service for Qdrant operations
            top_k: Maximum chunks to retrieve. Defaults to config value (8).
            score_threshold: Minimum score. Defaults to config value (0.7).
            settings: Settings instance. If None, uses get_settings().
        """
        if settings is None:
            settings = get_settings()

        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service
        self.top_k = top_k if top_k is not None else settings.retrieval.top_k
        self.score_threshold = (
            score_threshold
            if score_threshold is not None
            else settings.retrieval.score_threshold
        )

    def retrieve(
        self,
        query: str,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for a query.

        Generates an embedding for the query, searches Qdrant for
        similar chunks, filters by score threshold, and returns
        results sorted by relevance.

        Args:
            query: User's question or search query
            document_id: Optional filter to specific document

        Returns:
            List of RetrievedChunk sorted by score (descending).
            Empty list if no chunks meet the score threshold.
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retriever")
            return []

        # 1. Embed query
        logger.debug("Generating embedding for query: %s", query[:50])
        query_vector = self.embedding_service.embed_query(query)

        # 2. Build filter conditions
        filter_conditions = None
        if document_id:
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
            logger.debug("Filtering by document_id: %s", document_id)

        # 3. Search Qdrant with score threshold
        logger.debug(
            "Searching Qdrant: top_k=%d, score_threshold=%.2f",
            self.top_k,
            self.score_threshold,
        )

        results = self.qdrant_service.client.search(
            collection_name=self.qdrant_service.collection_name,
            query_vector=query_vector.tolist(),
            limit=self.top_k,
            query_filter=filter_conditions,
            with_payload=True,
            score_threshold=self.score_threshold,
        )

        # 4. Convert to RetrievedChunk objects
        chunks = []
        for result in results:
            payload = result.payload or {}
            chunks.append(
                RetrievedChunk(
                    content=payload.get("content", ""),
                    score=result.score,
                    page=payload.get("page", 0),
                    chunk_index=payload.get("chunk_index", 0),
                    document_id=payload.get("document_id", ""),
                    content_hash=payload.get("content_hash", ""),
                )
            )

        logger.info(
            "Retrieved %d chunks (query: '%s...', threshold: %.2f)",
            len(chunks),
            query[:30],
            self.score_threshold,
        )

        # Results are already sorted by score (descending) from Qdrant
        return chunks
