"""Document comparison tool for identifying differences between versions.

Compares two documents by:
1. Retrieving chunks from both documents
2. Computing semantic similarity between sections
3. Identifying added, removed, and modified content
4. Calculating overall document similarity

Supports multilingual documents (English and French) with language
auto-detection from document content.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

import numpy as np
from qdrant_client.http import models

from src.rag.llm import detect_language

if TYPE_CHECKING:
    from src.db.qdrant import QdrantService

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Type of change detected between document versions."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class Difference:
    """A difference between two document sections.

    Attributes:
        section: Section identifier (page/chunk reference)
        doc_a_excerpt: Text excerpt from document A
        doc_b_excerpt: Text excerpt from document B
        change_type: Type of change detected
        similarity_score: Semantic similarity score (0-1)
    """

    section: str
    doc_a_excerpt: str
    doc_b_excerpt: str
    change_type: ChangeType
    similarity_score: float


@dataclass
class ComparisonResult:
    """Result from document comparison.

    Attributes:
        differences: List of detected differences
        overall_similarity: Overall document similarity score (0-1)
        doc_a_id: First document ID
        doc_b_id: Second document ID
        summary: Human-readable summary of changes
        doc_a_chunk_count: Number of chunks in document A
        doc_b_chunk_count: Number of chunks in document B
        language: Detected/used language for the comparison ('en' or 'fr')
    """

    differences: list[Difference]
    overall_similarity: float
    doc_a_id: str
    doc_b_id: str
    summary: str
    doc_a_chunk_count: int = 0
    doc_b_chunk_count: int = 0
    language: Literal["en", "fr"] = "en"


class DiffTool:
    """Compare two documents for differences.

    Uses semantic similarity between document chunks to identify:
    - Unchanged sections (high similarity)
    - Modified sections (medium similarity)
    - Added sections (in B but not A)
    - Removed sections (in A but not B)

    Supports multilingual documents with automatic language detection from
    document content. The language of the first document (doc_a) determines
    the language used for the comparison summary.

    Args:
        qdrant_service: Qdrant service for retrieving document chunks
    """

    # Similarity thresholds
    SIMILARITY_THRESHOLD = 0.85  # Above this = unchanged
    MODIFIED_THRESHOLD = 0.5  # Above this = modified, below = added/removed

    # Maximum excerpt length for differences
    EXCERPT_MAX_LENGTH = 200

    def __init__(self, qdrant_service: "QdrantService"):
        """Initialize diff tool.

        Args:
            qdrant_service: Qdrant service for chunk retrieval
        """
        self.qdrant_service = qdrant_service

    async def compare(
        self, doc_a_id: str, doc_b_id: str, language: str | None = None
    ) -> ComparisonResult:
        """Compare two documents.

        Args:
            doc_a_id: First document ID
            doc_b_id: Second document ID
            language: Output language ('en' or 'fr'). If None, auto-detected
                     from first document's content.

        Returns:
            ComparisonResult with differences and similarity

        Raises:
            ValueError: If one or both documents have no chunks

        Note:
            Language is detected from the FIRST DOCUMENT's content (doc_a),
            ensuring comparisons of French documents produce French summaries.
        """
        logger.info(f"Comparing documents: {doc_a_id} vs {doc_b_id}")

        # 1. Get chunks from both documents (in parallel)
        chunks_a, chunks_b = await asyncio.gather(
            self._get_document_chunks(doc_a_id),
            self._get_document_chunks(doc_b_id),
        )

        if not chunks_a:
            raise ValueError(f"No chunks found for document {doc_a_id}")
        if not chunks_b:
            raise ValueError(f"No chunks found for document {doc_b_id}")

        logger.info(
            f"Retrieved {len(chunks_a)} chunks from doc A, {len(chunks_b)} from doc B"
        )

        # 2. Detect language from first document's content if not provided
        if language is None:
            language = self._detect_language_from_chunks(chunks_a)

        logger.info(f"Using language '{language}' for comparison")

        # 3. Extract embeddings from chunks
        embeddings_a = self._get_embeddings(chunks_a)
        embeddings_b = self._get_embeddings(chunks_b)

        # 4. Compute pairwise similarities
        similarity_matrix = self._compute_similarity_matrix(embeddings_a, embeddings_b)

        # 5. Find differences
        differences = self._find_differences(chunks_a, chunks_b, similarity_matrix)

        # 6. Calculate overall similarity
        overall = self._calculate_overall_similarity(similarity_matrix)

        # 7. Generate summary in detected language
        summary = self._generate_summary(differences, overall, language)

        logger.info(
            f"Comparison complete: {overall:.1%} similar, {len(differences)} differences, language={language}"
        )

        return ComparisonResult(
            differences=differences,
            overall_similarity=overall,
            doc_a_id=doc_a_id,
            doc_b_id=doc_b_id,
            summary=summary,
            doc_a_chunk_count=len(chunks_a),
            doc_b_chunk_count=len(chunks_b),
            language=language,
        )

    def _detect_language_from_chunks(self, chunks: list) -> str:
        """Detect language from document chunks.

        Samples text from multiple chunks for reliable detection.

        Args:
            chunks: List of Qdrant points with content payload

        Returns:
            'fr' for French, 'en' for English (default)
        """
        if not chunks:
            return "en"

        # Sample text from first few chunks
        sample_texts = []
        for chunk in chunks[:3]:
            content = chunk.payload.get("content", "")
            if content:
                sample_texts.append(content)

        combined_sample = " ".join(sample_texts)[:1000]
        return detect_language(combined_sample)

    async def _get_document_chunks(self, doc_id: str) -> list:
        """Get all chunks for a document from Qdrant.

        Args:
            doc_id: Document ID to retrieve chunks for

        Returns:
            List of chunk points with payload and vectors
        """

        def _scroll():
            return self.qdrant_service.client.scroll(
                collection_name=self.qdrant_service.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=True,
            )

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        results, _ = await loop.run_in_executor(None, _scroll)

        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.payload.get("chunk_index", 0))

        return results

    def _get_embeddings(self, chunks: list) -> np.ndarray:
        """Extract embeddings from chunks.

        Args:
            chunks: List of Qdrant points with vectors

        Returns:
            numpy array of embeddings
        """
        return np.array([c.vector for c in chunks])

    def _compute_similarity_matrix(
        self,
        embeddings_a: np.ndarray,
        embeddings_b: np.ndarray,
    ) -> np.ndarray:
        """Compute cosine similarity between all pairs of embeddings.

        Args:
            embeddings_a: Embeddings from document A (shape: [n_a, dim])
            embeddings_b: Embeddings from document B (shape: [n_b, dim])

        Returns:
            Similarity matrix of shape [n_a, n_b]
        """
        # Normalize embeddings (should already be normalized, but ensure)
        a_norm = embeddings_a / np.linalg.norm(embeddings_a, axis=1, keepdims=True)
        b_norm = embeddings_b / np.linalg.norm(embeddings_b, axis=1, keepdims=True)

        # Cosine similarity = dot product of normalized vectors
        return np.dot(a_norm, b_norm.T)

    def _find_differences(
        self,
        chunks_a: list,
        chunks_b: list,
        similarity_matrix: np.ndarray,
    ) -> list[Difference]:
        """Find differences between documents based on similarity matrix.

        Args:
            chunks_a: Chunks from document A
            chunks_b: Chunks from document B
            similarity_matrix: Pairwise similarity scores

        Returns:
            List of Difference objects
        """
        differences = []
        matched_b_indices: set[int] = set()

        # For each chunk in A, find best match in B
        for i, chunk_a in enumerate(chunks_a):
            best_match_idx = int(np.argmax(similarity_matrix[i]))
            best_score = float(similarity_matrix[i, best_match_idx])
            chunk_b = chunks_b[best_match_idx]

            if best_score >= self.SIMILARITY_THRESHOLD:
                # Unchanged - mark as matched
                matched_b_indices.add(best_match_idx)
            elif best_score >= self.MODIFIED_THRESHOLD:
                # Modified - record difference
                matched_b_indices.add(best_match_idx)
                differences.append(
                    Difference(
                        section=self._format_section(chunk_a.payload),
                        doc_a_excerpt=self._truncate(
                            chunk_a.payload.get("content", "")
                        ),
                        doc_b_excerpt=self._truncate(
                            chunk_b.payload.get("content", "")
                        ),
                        change_type=ChangeType.MODIFIED,
                        similarity_score=best_score,
                    )
                )
            else:
                # Removed - chunk in A has no good match in B
                differences.append(
                    Difference(
                        section=self._format_section(chunk_a.payload),
                        doc_a_excerpt=self._truncate(
                            chunk_a.payload.get("content", "")
                        ),
                        doc_b_excerpt="",
                        change_type=ChangeType.REMOVED,
                        similarity_score=best_score,
                    )
                )

        # Check for chunks in B with no match in A (added)
        for j, chunk_b in enumerate(chunks_b):
            if j in matched_b_indices:
                continue

            # Find best match score from A to this B chunk
            best_score = float(np.max(similarity_matrix[:, j]))

            if best_score < self.MODIFIED_THRESHOLD:
                # Added - chunk in B has no good match in A
                differences.append(
                    Difference(
                        section=self._format_section(chunk_b.payload),
                        doc_a_excerpt="",
                        doc_b_excerpt=self._truncate(
                            chunk_b.payload.get("content", "")
                        ),
                        change_type=ChangeType.ADDED,
                        similarity_score=best_score,
                    )
                )

        return differences

    def _format_section(self, payload: dict) -> str:
        """Format section identifier from chunk payload.

        Args:
            payload: Chunk payload dictionary

        Returns:
            Formatted section string
        """
        page = payload.get("page", 0)
        chunk_index = payload.get("chunk_index", 0)
        return f"Page {page}, Chunk {chunk_index}"

    def _truncate(self, text: str) -> str:
        """Truncate text to maximum excerpt length.

        Args:
            text: Text to truncate

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= self.EXCERPT_MAX_LENGTH:
            return text
        return text[: self.EXCERPT_MAX_LENGTH - 3] + "..."

    def _calculate_overall_similarity(self, similarity_matrix: np.ndarray) -> float:
        """Calculate overall document similarity.

        Uses the average of best matches for each chunk in A.

        Args:
            similarity_matrix: Pairwise similarity scores

        Returns:
            Overall similarity score (0-1)
        """
        if similarity_matrix.size == 0:
            return 0.0

        # Average of best matches for each chunk in A
        best_matches = np.max(similarity_matrix, axis=1)
        return float(np.mean(best_matches))

    def _generate_summary(
        self,
        differences: list[Difference],
        overall: float,
        language: str = "en",
    ) -> str:
        """Generate human-readable comparison summary.

        Args:
            differences: List of detected differences
            overall: Overall similarity score
            language: Language for summary ('en' or 'fr')

        Returns:
            Summary string
        """
        added = sum(1 for d in differences if d.change_type == ChangeType.ADDED)
        removed = sum(1 for d in differences if d.change_type == ChangeType.REMOVED)
        modified = sum(1 for d in differences if d.change_type == ChangeType.MODIFIED)

        if not differences:
            if language == "fr":
                return f"Les documents sont similaires à {overall:.0%} sans différences significatives détectées."
            return f"Documents are {overall:.0%} similar with no significant differences detected."

        if language == "fr":
            parts = []
            if added:
                parts.append(f"{added} ajouté(s)")
            if removed:
                parts.append(f"{removed} supprimé(s)")
            if modified:
                parts.append(f"{modified} modifié(s)")

            changes_str = ", ".join(parts)
            return (
                f"Les documents sont similaires à {overall:.0%}. "
                f"{len(differences)} différences trouvées: {changes_str} sections."
            )

        parts = []
        if added:
            parts.append(f"{added} added")
        if removed:
            parts.append(f"{removed} removed")
        if modified:
            parts.append(f"{modified} modified")

        changes_str = ", ".join(parts)
        return (
            f"Documents are {overall:.0%} similar. "
            f"Found {len(differences)} differences: {changes_str} sections."
        )
