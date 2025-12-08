"""Qdrant vector database service for document storage and retrieval."""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.config import Settings, get_settings
from src.rag.chunking import Chunk

logger = logging.getLogger(__name__)


class QdrantConnectionError(Exception):
    """Raised when Qdrant connection fails."""

    pass


class QdrantService:
    """Service for managing document vectors in Qdrant.

    Handles collection creation, vector upsert with metadata,
    deduplication, and document deletion.
    """

    # HNSW configuration from PRD
    HNSW_M = 16
    HNSW_EF_CONSTRUCT = 128

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
        settings: Settings | None = None,
    ):
        """Initialize Qdrant service.

        Args:
            host: Qdrant host. Defaults to config value.
            port: Qdrant port. Defaults to config value.
            collection_name: Collection name. Defaults to config value.
            settings: Settings instance. If None, uses get_settings().
        """
        if settings is None:
            settings = get_settings()

        self.host = host or settings.qdrant.host
        self.port = port or settings.qdrant.port
        self.collection_name = collection_name or settings.qdrant.collection
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Lazy-initialize Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(host=self.host, port=self.port)
        return self._client

    def health_check(self) -> bool:
        """Check if Qdrant is accessible.

        Returns:
            True if Qdrant is reachable, False otherwise.
        """
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            return False

    def ensure_collection(self, vector_size: int = 768) -> None:
        """Create collection if it doesn't exist.

        Args:
            vector_size: Dimension of vectors. Defaults to 768 (multilingual-e5-base).

        Raises:
            QdrantConnectionError: If unable to connect to Qdrant.
        """
        try:
            collections = self.client.get_collections().collections
            if any(c.name == self.collection_name for c in collections):
                logger.debug(f"Collection '{self.collection_name}' already exists")
                return

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=self.HNSW_M,
                    ef_construct=self.HNSW_EF_CONSTRUCT,
                ),
            )
            logger.info(
                f"Created collection '{self.collection_name}' with "
                f"vector_size={vector_size}, HNSW m={self.HNSW_M}, "
                f"ef_construct={self.HNSW_EF_CONSTRUCT}"
            )
        except UnexpectedResponse as e:
            raise QdrantConnectionError(f"Failed to create collection: {e}")
        except Exception as e:
            raise QdrantConnectionError(f"Qdrant connection error: {e}")

    def get_existing_hashes(self, document_id: str) -> set[str]:
        """Get content hashes of existing chunks for a document.

        Args:
            document_id: Document ID to check.

        Returns:
            Set of content hashes already stored for this document.
        """
        try:
            # Scroll through all points for this document
            existing_hashes: set[str] = set()
            offset = None

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    ),
                    limit=100,
                    offset=offset,
                    with_payload=["content_hash"],
                )

                for point in results:
                    if point.payload and "content_hash" in point.payload:
                        existing_hashes.add(point.payload["content_hash"])

                if offset is None:
                    break

            return existing_hashes
        except Exception as e:
            logger.warning(f"Failed to get existing hashes: {e}")
            return set()

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        document_id: str,
        source_title: str | None = None,
        deduplicate: bool = True,
    ) -> int:
        """Upsert chunks with embeddings.

        Args:
            chunks: List of Chunk objects.
            embeddings: Numpy array of embeddings (shape: [n_chunks, dim]).
            document_id: Document ID for grouping.
            source_title: Optional document title for payload.
            deduplicate: If True, skip chunks with existing content_hash.

        Returns:
            Number of chunks actually inserted.

        Raises:
            QdrantConnectionError: If upsert fails.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch"
            )

        if not chunks:
            return 0

        # Get existing hashes for deduplication
        existing_hashes: set[str] = set()
        if deduplicate:
            existing_hashes = self.get_existing_hashes(document_id)
            if existing_hashes:
                logger.debug(
                    f"Found {len(existing_hashes)} existing chunks for document {document_id}"
                )

        # Build points, skipping duplicates
        points: list[models.PointStruct] = []
        uploaded_at = datetime.now(timezone.utc).isoformat()

        for chunk, embedding in zip(chunks, embeddings):
            # Skip if content hash already exists
            if deduplicate and chunk.content_hash in existing_hashes:
                logger.debug(f"Skipping duplicate chunk {chunk.chunk_index}")
                continue

            point_id = str(uuid.uuid4())
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={
                        "document_id": document_id,
                        "content": chunk.content,
                        "page": chunk.page,
                        "pages": chunk.pages,
                        "chunk_index": chunk.chunk_index,
                        "content_hash": chunk.content_hash,
                        "source_title": source_title or "",
                        "uploaded_at": uploaded_at,
                    },
                )
            )

        if not points:
            logger.info("No new chunks to insert (all duplicates)")
            return 0

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(
                f"Upserted {len(points)} chunks for document {document_id}"
            )
            return len(points)
        except Exception as e:
            raise QdrantConnectionError(f"Failed to upsert chunks: {e}")

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID to delete.

        Returns:
            Number of points deleted (approximate).

        Raises:
            QdrantConnectionError: If deletion fails.
        """
        try:
            # First count how many we're deleting
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
            )
            count = count_result.count

            if count == 0:
                logger.debug(f"No chunks found for document {document_id}")
                return 0

            # Delete all points matching the document_id
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )
            logger.info(f"Deleted {count} chunks for document {document_id}")
            return count
        except Exception as e:
            raise QdrantConnectionError(f"Failed to delete document chunks: {e}")

    def get_collection_info(self) -> dict | None:
        """Get collection information.

        Returns:
            Dictionary with collection info, or None if collection doesn't exist.
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "status": info.status.value if hasattr(info.status, "value") else str(info.status),
            }
        except Exception:
            return None
