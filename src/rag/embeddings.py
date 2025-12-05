"""Embedding generation service using sentence-transformers.

Provides lazy-loaded embedding model with batch processing,
retry logic, caching, and progress tracking for large documents.
"""

import hashlib
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""

    pass


class LRUCache:
    """Simple LRU cache for embeddings using OrderedDict."""

    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of entries to cache
        """
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def _make_key(self, text: str) -> str:
        """Create cache key from text using MD5 hash."""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> np.ndarray | None:
        """Get embedding from cache.

        Args:
            text: Text to look up

        Returns:
            Cached embedding or None if not found
        """
        key = self._make_key(text)
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, text: str, embedding: np.ndarray) -> None:
        """Store embedding in cache.

        Args:
            text: Text key
            embedding: Embedding vector to store
        """
        key = self._make_key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                # Remove oldest entry
                self._cache.popitem(last=False)
            self._cache[key] = embedding

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


class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers.

    Features:
    - Lazy model loading to avoid slow startup
    - Batch processing for efficiency
    - LRU caching for repeated queries
    - Retry logic with exponential backoff
    - Progress tracking for large documents

    Attributes:
        model_name: Name of the sentence-transformers model
        device: Device to run model on ('cpu' or 'cuda')
        dimension: Output embedding dimension (768 for all-mpnet-base-v2)
    """

    # Model output dimension for all-mpnet-base-v2
    DIMENSION = 768

    def __init__(
        self,
        model_name: str = "all-mpnet-base-v2",
        device: str = "cpu",
        cache_size: int = 1000,
        enable_cache: bool = True,
        query_prefix: str = "",
        document_prefix: str = "",
    ):
        """Initialize embedding service.

        Args:
            model_name: Sentence-transformers model name
            device: Device to run model on ('cpu' or 'cuda')
            cache_size: Maximum number of embeddings to cache
            enable_cache: Whether to enable embedding caching
            query_prefix: Prefix to add to queries (e.g., 'query: ' for E5 models)
            document_prefix: Prefix to add to documents (e.g., 'passage: ' for E5 models)
        """
        self._model: "SentenceTransformer | None" = None
        self.model_name = model_name
        self.device = device
        self.enable_cache = enable_cache
        self._cache = LRUCache(max_size=cache_size) if enable_cache else None

        # Auto-detect E5 models and apply prefixes
        self.use_prefixes = "e5" in model_name.lower()
        self.query_prefix = query_prefix if self.use_prefixes else ""
        self.document_prefix = document_prefix if self.use_prefixes else ""

    @property
    def model(self) -> "SentenceTransformer":
        """Lazy load the sentence-transformers model.

        Returns:
            Loaded SentenceTransformer model

        Raises:
            EmbeddingError: If model loading fails
        """
        if self._model is None:
            try:
                logger.info(
                    "Loading embedding model: %s on device: %s",
                    self.model_name,
                    self.device,
                )
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device=self.device)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                raise EmbeddingError(f"Failed to load embedding model: {e}") from e
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Embedding vector dimension (768 for all-mpnet-base-v2)
        """
        return self.DIMENSION

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RuntimeError, MemoryError)),
        reraise=True,
    )
    def embed(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool | None = None,
    ) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process per batch
            show_progress: Show progress bar. If None, auto-enables for >100 texts.

        Returns:
            numpy array of shape (len(texts), dimension)

        Raises:
            EmbeddingError: If embedding generation fails after retries
        """
        if not texts:
            return np.array([]).reshape(0, self.dimension)

        # Auto-enable progress bar for large batches
        if show_progress is None:
            show_progress = len(texts) > 100

        try:
            logger.debug(
                "Generating embeddings for %d texts (batch_size=%d)",
                len(texts),
                batch_size,
            )

            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=True,  # L2 normalize for cosine similarity
            )

            logger.debug("Generated %d embeddings", len(embeddings))
            return embeddings

        except (RuntimeError, MemoryError):
            # Let tenacity handle retry for these
            raise
        except Exception as e:
            logger.error("Embedding generation failed: %s", e)
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string with caching and E5 prefix.

        Args:
            query: Query text to embed

        Returns:
            numpy array of shape (dimension,)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not query or not query.strip():
            raise EmbeddingError("Query cannot be empty")

        # Apply E5 query prefix if needed
        text = f"{self.query_prefix}{query}" if self.use_prefixes else query

        # Check cache first (using original query as key)
        if self._cache is not None:
            cached = self._cache.get(query)
            if cached is not None:
                logger.debug("Cache hit for query embedding")
                return cached

        embeddings = self.embed([text], batch_size=1, show_progress=False)
        result = embeddings[0]

        # Cache the result (using original query as key)
        if self._cache is not None:
            self._cache.put(query, result)

        return result

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
        """Clear the embedding cache."""
        if self._cache is not None:
            self._cache.clear()
            logger.info("Embedding cache cleared")

    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool | None = None,
    ) -> np.ndarray:
        """Embed a list of documents with E5 document prefix.

        Args:
            texts: List of document texts to embed
            batch_size: Number of texts to process per batch
            show_progress: Show progress bar. If None, auto-enables for >100 texts.

        Returns:
            numpy array of shape (len(texts), dimension)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        # Apply E5 document prefix if needed
        if self.use_prefixes:
            texts = [f"{self.document_prefix}{t}" for t in texts]

        return self.embed(texts, batch_size=batch_size, show_progress=show_progress)

    def embed_chunks(
        self,
        chunks: list,
        batch_size: int = 32,
    ) -> np.ndarray:
        """Embed a list of Chunk objects with E5 document prefix.

        Convenience method that extracts content from Chunk objects.

        Args:
            chunks: List of Chunk objects with 'content' attribute
            batch_size: Number of chunks to process per batch

        Returns:
            numpy array of shape (len(chunks), dimension)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        texts = [chunk.content for chunk in chunks]
        return self.embed_documents(texts, batch_size=batch_size)


# Alias for backward compatibility
EmbeddingsService = EmbeddingService
