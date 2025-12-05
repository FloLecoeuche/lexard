"""Hallucination detection for RAG responses.

Validates that LLM responses are grounded in the provided citation chunks
using semantic similarity checks.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Module-level executor for CPU-bound embedding work
_executor = ThreadPoolExecutor(max_workers=2)


@dataclass
class GroundingResult:
    """Result of hallucination check.

    Attributes:
        is_grounded: Whether the answer is sufficiently grounded in citations
        grounding_score: Similarity score between answer and citations (0.0-1.0)
        best_chunk_index: Index of the most relevant citation chunk
        details: Additional details about the grounding check
    """

    is_grounded: bool
    grounding_score: float
    best_chunk_index: int | None
    details: str


@lru_cache(maxsize=1)
def _get_embedding_model() -> "SentenceTransformer":
    """Lazily load the embedding model.

    Returns:
        Loaded SentenceTransformer model
    """
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model for hallucination detection")
    return SentenceTransformer("all-mpnet-base-v2")


class HallucinationDetector:
    """Detects hallucinated content in RAG responses.

    Uses semantic similarity to verify that the LLM's answer is grounded
    in the provided citation chunks. If the answer is semantically too
    different from all citations, it's flagged as potentially hallucinated.

    Attributes:
        threshold: Minimum similarity score for grounding (0.0-1.0)
    """

    def __init__(self, threshold: float = 0.8):
        """Initialize HallucinationDetector.

        Args:
            threshold: Minimum similarity score to consider grounded.
                       Higher values are stricter. Default 0.8.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self.threshold = threshold
        self._model: "SentenceTransformer | None" = None

    @property
    def model(self) -> "SentenceTransformer":
        """Get the embedding model, loading it lazily."""
        if self._model is None:
            self._model = _get_embedding_model()
        return self._model

    def check_grounding(
        self,
        answer: str,
        citation_chunks: list[str],
    ) -> GroundingResult:
        """Check if answer is grounded in citations.

        Computes semantic similarity between the answer and each citation
        chunk. The answer is considered grounded if the maximum similarity
        exceeds the threshold.

        Args:
            answer: The LLM-generated answer to validate
            citation_chunks: List of citation text chunks

        Returns:
            GroundingResult with grounding status and score
        """
        if not answer or not answer.strip():
            logger.warning("Empty answer provided for grounding check")
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                best_chunk_index=None,
                details="Answer is empty",
            )

        if not citation_chunks:
            logger.warning("No citation chunks provided for grounding check")
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                best_chunk_index=None,
                details="No citations to ground against",
            )

        # Filter empty chunks
        valid_chunks = [c for c in citation_chunks if c and c.strip()]
        if not valid_chunks:
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                best_chunk_index=None,
                details="All citation chunks are empty",
            )

        try:
            # Compute embeddings
            answer_embedding = self.model.encode(answer, normalize_embeddings=True)
            chunk_embeddings = self.model.encode(valid_chunks, normalize_embeddings=True)

            # Calculate cosine similarities (embeddings are normalized)
            similarities = np.dot(chunk_embeddings, answer_embedding)

            # Get best match
            best_idx = int(np.argmax(similarities))
            max_similarity = float(similarities[best_idx])

            is_grounded = max_similarity >= self.threshold

            logger.info(
                "Grounding check complete",
                extra={
                    "is_grounded": is_grounded,
                    "grounding_score": max_similarity,
                    "threshold": self.threshold,
                    "num_chunks": len(valid_chunks),
                },
            )

            return GroundingResult(
                is_grounded=is_grounded,
                grounding_score=max_similarity,
                best_chunk_index=best_idx,
                details=f"Max similarity {max_similarity:.3f} vs threshold {self.threshold}",
            )

        except Exception as e:
            logger.error(f"Grounding check failed: {e}")
            # On error, be conservative and assume not grounded
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                best_chunk_index=None,
                details=f"Grounding check error: {e}",
            )

    async def check_grounding_async(
        self,
        answer: str,
        citation_chunks: list[str],
    ) -> GroundingResult:
        """Async version of check_grounding.

        Runs the CPU-bound embedding computation in a thread pool
        to avoid blocking the event loop.

        Args:
            answer: The LLM-generated answer to validate
            citation_chunks: List of citation text chunks

        Returns:
            GroundingResult with grounding status and score
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self.check_grounding,
            answer,
            citation_chunks,
        )

    def check_claims_grounding(
        self,
        answer: str,
        citation_chunks: list[str],
        sentence_threshold: float | None = None,
    ) -> tuple[bool, float, list[tuple[str, float]]]:
        """Advanced grounding check at sentence level.

        Splits the answer into sentences and checks each one against
        citations. Useful for detecting partial hallucinations.

        Args:
            answer: The LLM-generated answer to validate
            citation_chunks: List of citation text chunks
            sentence_threshold: Per-sentence threshold (uses self.threshold if None)

        Returns:
            Tuple of:
                - Overall is_grounded status
                - Overall grounding score (average of sentence scores)
                - List of (sentence, score) tuples for details
        """
        import re

        threshold = sentence_threshold if sentence_threshold is not None else self.threshold

        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return False, 0.0, []

        if not citation_chunks:
            return False, 0.0, [(s, 0.0) for s in sentences]

        valid_chunks = [c for c in citation_chunks if c and c.strip()]
        if not valid_chunks:
            return False, 0.0, [(s, 0.0) for s in sentences]

        try:
            # Encode all sentences and chunks
            sentence_embeddings = self.model.encode(sentences, normalize_embeddings=True)
            chunk_embeddings = self.model.encode(valid_chunks, normalize_embeddings=True)

            sentence_scores = []
            for i, sent in enumerate(sentences):
                # Max similarity for this sentence
                similarities = np.dot(chunk_embeddings, sentence_embeddings[i])
                max_sim = float(np.max(similarities))
                sentence_scores.append((sent, max_sim))

            # Calculate overall grounding
            scores = [s[1] for s in sentence_scores]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            grounded_count = sum(1 for s in scores if s >= threshold)
            overall_grounded = grounded_count / len(scores) >= 0.8  # 80% of sentences grounded

            return overall_grounded, avg_score, sentence_scores

        except Exception as e:
            logger.error(f"Sentence-level grounding check failed: {e}")
            return False, 0.0, [(s, 0.0) for s in sentences]
