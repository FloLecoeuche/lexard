"""Dense retriever for semantic search over Qdrant.

Retrieves relevant document chunks based on embedding similarity
with configurable score thresholds, document filtering, and result caching.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

from qdrant_client.http import models

from src.config import Settings, get_settings
from src.db.qdrant import QdrantService
from src.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class ResultCache:
    """LRU cache for retrieval results with TTL support."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 300.0):
        """Initialize result cache.

        Args:
            max_size: Maximum number of results to cache
            ttl_seconds: Time-to-live for cached results in seconds
        """
        self._cache: OrderedDict[str, tuple[list, float]] = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str, document_id: str | None) -> str:
        """Create cache key from query and document_id."""
        key_str = f"{query}|{document_id or ''}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, document_id: str | None) -> list | None:
        """Get cached results.

        Args:
            query: Search query
            document_id: Optional document filter

        Returns:
            Cached results or None if not found/expired
        """
        key = self._make_key(query, document_id)
        if key in self._cache:
            results, timestamp = self._cache[key]
            # Check TTL
            if time.time() - timestamp < self.ttl_seconds:
                self._cache.move_to_end(key)
                self.hits += 1
                return results
            else:
                # Expired - remove
                del self._cache[key]
        self.misses += 1
        return None

    def put(self, query: str, document_id: str | None, results: list) -> None:
        """Store results in cache.

        Args:
            query: Search query
            document_id: Optional document filter
            results: List of RetrievedChunk to cache
        """
        key = self._make_key(query, document_id)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
        self._cache[key] = (results, time.time())

    def invalidate_document(self, document_id: str) -> int:
        """Invalidate all cached results for a document.

        Args:
            document_id: Document ID to invalidate

        Returns:
            Number of cache entries invalidated
        """
        keys_to_remove = []
        for key, (results, _) in self._cache.items():
            if results and results[0].document_id == document_id:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def __len__(self) -> int:
        return len(self._cache)


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
    using embedding similarity. Supports score thresholding,
    document filtering, and result caching.

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
        enable_cache: bool = True,
        cache_ttl: float = 300.0,
    ):
        """Initialize retriever.

        Args:
            embedding_service: Service for generating query embeddings
            qdrant_service: Service for Qdrant operations
            top_k: Maximum chunks to retrieve. Defaults to config value (8).
            score_threshold: Minimum score. Defaults to config value (0.7).
            settings: Settings instance. If None, uses get_settings().
            enable_cache: Whether to enable result caching
            cache_ttl: Time-to-live for cached results in seconds
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
        self.enable_cache = enable_cache
        self._cache = ResultCache(ttl_seconds=cache_ttl) if enable_cache else None

    def retrieve(
        self,
        query: str,
        document_id: str | None = None,
        use_cache: bool = True,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for a query.

        Generates an embedding for the query, searches Qdrant for
        similar chunks, filters by score threshold, and returns
        results sorted by relevance. Results are cached for repeated queries.

        Args:
            query: User's question or search query
            document_id: Optional filter to specific document
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of RetrievedChunk sorted by score (descending).
            Empty list if no chunks meet the score threshold.
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retriever")
            return []

        # Check cache first
        if use_cache and self._cache is not None:
            cached = self._cache.get(query, document_id)
            if cached is not None:
                logger.debug("Cache hit for query: %s", query[:50])
                return cached

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

        # Cache results
        if use_cache and self._cache is not None:
            self._cache.put(query, document_id, chunks)

        logger.info(
            "Retrieved %d chunks (query: '%s...', threshold: %.2f)",
            len(chunks),
            query[:30],
            self.score_threshold,
        )

        # Results are already sorted by score (descending) from Qdrant
        return chunks

    @property
    def cache_stats(self) -> dict[str, float | int] | None:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, size, and hit_rate, or None if caching disabled
        """
        if self._cache is None:
            return None
        return {
            "hits": self._cache.hits,
            "misses": self._cache.misses,
            "size": len(self._cache),
            "hit_rate": self._cache.hit_rate,
        }

    def clear_cache(self) -> None:
        """Clear the retrieval result cache."""
        if self._cache is not None:
            self._cache.clear()
            logger.info("Retrieval cache cleared")

    def invalidate_document_cache(self, document_id: str) -> int:
        """Invalidate cached results for a specific document.

        Args:
            document_id: Document ID to invalidate

        Returns:
            Number of cache entries invalidated
        """
        if self._cache is not None:
            count = self._cache.invalidate_document(document_id)
            if count > 0:
                logger.info(
                    "Invalidated %d cache entries for document %s",
                    count,
                    document_id,
                )
            return count
        return 0
