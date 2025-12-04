"""Embedding generation service using sentence-transformers.

Provides lazy-loaded embedding model with batch processing,
retry logic, and progress tracking for large documents.
"""

import logging
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


class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers.

    Features:
    - Lazy model loading to avoid slow startup
    - Batch processing for efficiency
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
    ):
        """Initialize embedding service.

        Args:
            model_name: Sentence-transformers model name
            device: Device to run model on ('cpu' or 'cuda')
        """
        self._model: "SentenceTransformer | None" = None
        self.model_name = model_name
        self.device = device

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
        """Embed a single query string.

        Args:
            query: Query text to embed

        Returns:
            numpy array of shape (dimension,)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not query or not query.strip():
            raise EmbeddingError("Query cannot be empty")

        embeddings = self.embed([query], batch_size=1, show_progress=False)
        return embeddings[0]

    def embed_chunks(
        self,
        chunks: list,
        batch_size: int = 32,
    ) -> np.ndarray:
        """Embed a list of Chunk objects.

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
        return self.embed(texts, batch_size=batch_size)
