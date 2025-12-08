"""Multi-step document summarization tool.

Implements a two-phase summarization approach:
1. Chunk-level summaries: Summarize each chunk individually
2. Aggregation: Combine chunk summaries into a coherent executive summary

Supports multilingual documents (English and French) with language
auto-detection from document content.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from qdrant_client.http import models

from src.agent.prompts import get_prompt
from src.rag.llm import detect_language

if TYPE_CHECKING:
    from src.db.qdrant import QdrantService
    from src.rag.llm import OllamaClient

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """Result from document summarization.

    Attributes:
        executive_summary: Cohesive summary of the entire document
        key_points: List of extracted key points
        section_summaries: Per-chunk summaries (for detailed style)
        word_count: Word count of executive summary
        chunk_count: Number of chunks processed
        language: Detected/used language for the summary ('en' or 'fr')
    """

    executive_summary: str
    key_points: list[str]
    section_summaries: list[dict] = field(default_factory=list)
    word_count: int = 0
    chunk_count: int = 0
    language: Literal["en", "fr"] = "en"


class SummarizerTool:
    """Multi-step document summarization.

    Generates summaries through a two-phase process:
    1. Chunk-level: Each document chunk is summarized individually
    2. Aggregation: Chunk summaries are combined into an executive summary

    Supports multilingual documents with automatic language detection from
    document content. French documents receive French summaries, English
    documents receive English summaries.

    Args:
        llm_client: Ollama client for LLM generation
        qdrant_service: Qdrant service for retrieving document chunks
    """

    # Intermediate aggregation prompts (for hierarchical summarization)
    INTERMEDIATE_AGGREGATION_PROMPTS = {
        "en": """Combine these summaries into a single consolidated summary.
Keep all important details, obligations, and key facts.

SUMMARIES:
{summaries}

Write a comprehensive summary (3-5 sentences):""",
        "fr": """Combinez ces résumés en un seul résumé consolidé.
Conservez tous les détails importants, obligations et faits clés.

RÉSUMÉS:
{summaries}

Écrivez un résumé complet (3-5 phrases):""",
    }

    # Batch size for chunk processing to avoid overwhelming LLM
    CHUNK_BATCH_SIZE = 5
    # Maximum chunks to process (for very long documents)
    MAX_CHUNKS = 50
    # Conservative context budget for aggregation (tokens)
    # Leaves room for prompt template + response
    # Assuming ~4 tokens per word, 50 words per chunk summary = ~200 tokens/summary
    MAX_AGGREGATION_TOKENS = 6000
    TOKENS_PER_SUMMARY = 200  # Conservative estimate

    def __init__(
        self,
        llm_client: "OllamaClient",
        qdrant_service: "QdrantService",
    ):
        """Initialize summarizer tool.

        Args:
            llm_client: Ollama client for LLM generation
            qdrant_service: Qdrant service for chunk retrieval
        """
        self.llm = llm_client
        self.qdrant_service = qdrant_service

    async def summarize(
        self,
        document_id: str,
        style: str = "executive",
        language: str | None = None,
    ) -> SummaryResult:
        """Summarize a document.

        Args:
            document_id: Document ID to summarize
            style: Summary style - "executive" (default) or "detailed"
            language: Output language ('en' or 'fr'). If None, auto-detected
                     from document content.

        Returns:
            SummaryResult with summary and key points

        Raises:
            ValueError: If no chunks found for document

        Note:
            Language is detected from the DOCUMENT content (chunks),
            ensuring French documents always get French summaries.
        """
        logger.info(f"Starting summarization for document {document_id}, style={style}")

        # 1. Retrieve all chunks for document
        chunks = await self._get_all_chunks(document_id)

        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")

        # 2. Detect language from document content if not provided
        if language is None:
            language = self._detect_language_from_chunks(chunks)

        logger.info(f"Using language '{language}' for summarization")

        # Limit chunks for very long documents
        if len(chunks) > self.MAX_CHUNKS:
            logger.warning(
                f"Document has {len(chunks)} chunks, limiting to {self.MAX_CHUNKS}"
            )
            chunks = chunks[: self.MAX_CHUNKS]

        # 3. Generate chunk summaries (in batches for efficiency)
        chunk_summaries = await self._summarize_chunks_batch(chunks, language)

        # 4. Aggregate summaries
        aggregated = await self._aggregate_summaries(chunk_summaries, language)

        # 5. Build result
        result = SummaryResult(
            executive_summary=aggregated["executive_summary"],
            key_points=aggregated["key_points"],
            section_summaries=chunk_summaries if style == "detailed" else [],
            word_count=len(aggregated["executive_summary"].split()),
            chunk_count=len(chunks),
            language=language,
        )

        logger.info(
            f"Summarization complete: {result.word_count} words, "
            f"{len(result.key_points)} key points, language={language}"
        )

        return result

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

    async def _get_all_chunks(self, document_id: str) -> list:
        """Get all chunks for a document from Qdrant.

        Args:
            document_id: Document ID to retrieve chunks for

        Returns:
            List of chunk points with payload
        """

        def _scroll():
            return self.qdrant_service.client.scroll(
                collection_name=self.qdrant_service.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
            )

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        results, _ = await loop.run_in_executor(None, _scroll)

        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.payload.get("chunk_index", 0))

        return results

    async def _summarize_chunks_batch(
        self, chunks: list, language: str = "en"
    ) -> list[dict]:
        """Summarize chunks in batches.

        Args:
            chunks: List of chunk points from Qdrant
            language: Language for prompts ('en' or 'fr')

        Returns:
            List of dictionaries with page and summary
        """
        chunk_summaries = []

        # Process in batches
        for i in range(0, len(chunks), self.CHUNK_BATCH_SIZE):
            batch = chunks[i : i + self.CHUNK_BATCH_SIZE]

            # Process batch concurrently
            tasks = [self._summarize_chunk(chunk, language) for chunk in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for chunk, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed to summarize chunk {chunk.payload.get('chunk_index', 0)}: {result}"
                    )
                    summary = "[Summary unavailable]" if language == "en" else "[Résumé non disponible]"
                else:
                    summary = result

                chunk_summaries.append(
                    {
                        "page": chunk.payload.get("page", 0),
                        "chunk_index": chunk.payload.get("chunk_index", 0),
                        "summary": summary,
                    }
                )

        return chunk_summaries

    async def _summarize_chunk(self, chunk, language: str = "en") -> str:
        """Summarize a single chunk.

        Args:
            chunk: Qdrant point with payload containing content
            language: Language for prompts ('en' or 'fr')

        Returns:
            Summary string
        """
        content = chunk.payload.get("content", "")
        if not content.strip():
            return "[Empty chunk]" if language == "en" else "[Extrait vide]"

        # Use bilingual prompt from prompts module
        prompt = get_prompt("chunk_summary", language, content=content)

        def _generate():
            return self.llm.generate(prompt)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _generate)

        return response.content.strip()

    async def _aggregate_summaries(
        self, summaries: list[dict], language: str = "en"
    ) -> dict:
        """Aggregate chunk summaries into final summary.

        Uses hierarchical aggregation for large documents to stay within
        context limits. Groups summaries into batches, creates intermediate
        summaries, then produces the final summary.

        Args:
            summaries: List of chunk summary dictionaries
            language: Language for prompts ('en' or 'fr')

        Returns:
            Dictionary with executive_summary and key_points
        """
        # Filter and sort valid summaries (handle both EN and FR unavailable messages)
        invalid_summaries = {
            "[Summary unavailable]",
            "[Résumé non disponible]",
            "[Empty chunk]",
            "[Extrait vide]",
        }
        valid_summaries = [
            s for s in summaries
            if s["summary"] not in invalid_summaries
        ]

        if not valid_summaries:
            if language == "fr":
                return {
                    "executive_summary": "Impossible de générer le résumé - aucun résumé de section valide disponible.",
                    "key_points": [],
                }
            return {
                "executive_summary": "Unable to generate summary - no valid chunk summaries available.",
                "key_points": [],
            }

        sorted_summaries = sorted(
            valid_summaries, key=lambda s: (s.get("page", 0), s.get("chunk_index", 0))
        )

        # Calculate how many summaries fit in context
        max_summaries_per_batch = self.MAX_AGGREGATION_TOKENS // self.TOKENS_PER_SUMMARY

        logger.info(
            f"Aggregating {len(sorted_summaries)} summaries "
            f"(max {max_summaries_per_batch} per batch)"
        )

        # If summaries fit in one batch, do direct aggregation
        if len(sorted_summaries) <= max_summaries_per_batch:
            return await self._final_aggregation(sorted_summaries, language)

        # Hierarchical aggregation for large documents
        logger.info(
            f"Document too large for single aggregation, using hierarchical approach"
        )
        return await self._hierarchical_aggregation(
            sorted_summaries, max_summaries_per_batch, language
        )

    async def _hierarchical_aggregation(
        self, summaries: list[dict], batch_size: int, language: str = "en"
    ) -> dict:
        """Perform hierarchical aggregation for large documents.

        Groups summaries into batches, creates intermediate summaries,
        then combines those for the final summary.

        Args:
            summaries: Sorted list of chunk summary dictionaries
            batch_size: Maximum summaries per batch
            language: Language for prompts ('en' or 'fr')

        Returns:
            Dictionary with executive_summary and key_points
        """
        current_summaries = summaries
        level = 0

        # Get language-specific intermediate aggregation prompt
        intermediate_prompt_template = self.INTERMEDIATE_AGGREGATION_PROMPTS.get(
            language, self.INTERMEDIATE_AGGREGATION_PROMPTS["en"]
        )

        # Keep reducing until we fit in context
        while len(current_summaries) > batch_size:
            level += 1
            logger.info(
                f"Hierarchical aggregation level {level}: "
                f"{len(current_summaries)} -> ~{len(current_summaries) // batch_size + 1} summaries"
            )

            intermediate_summaries = []

            for i in range(0, len(current_summaries), batch_size):
                batch = current_summaries[i:i + batch_size]

                # Create intermediate summary for this batch
                batch_text = "\n\n".join(
                    f"- {s.get('summary', s) if isinstance(s, dict) else s}"
                    for s in batch
                )

                prompt = intermediate_prompt_template.format(summaries=batch_text)

                def _generate(p=prompt):
                    return self.llm.generate(p)

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, _generate)

                # Store as simple string for next level
                intermediate_summaries.append({
                    "page": batch[0].get("page", 0) if isinstance(batch[0], dict) else 0,
                    "chunk_index": i // batch_size,
                    "summary": response.content.strip(),
                })

            current_summaries = intermediate_summaries

        # Final aggregation with reduced summaries
        return await self._final_aggregation(current_summaries, language)

    async def _final_aggregation(
        self, summaries: list[dict], language: str = "en"
    ) -> dict:
        """Perform final aggregation to create executive summary.

        Args:
            summaries: List of summary dictionaries that fit in context
            language: Language for prompts ('en' or 'fr')

        Returns:
            Dictionary with executive_summary and key_points
        """
        summaries_text = "\n\n".join(
            f"Section {s.get('chunk_index', i)}: {s['summary']}"
            for i, s in enumerate(summaries)
        )

        # Use bilingual prompt from prompts module
        prompt = get_prompt("aggregation", language, summaries=summaries_text)

        def _generate():
            return self.llm.generate(prompt)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _generate)

        return self._parse_summary_response(response.content, language)

    def _parse_summary_response(self, text: str, language: str = "en") -> dict:
        """Parse the aggregated summary response.

        Args:
            text: Raw LLM response text
            language: Language code ('en' or 'fr')

        Returns:
            Dictionary with executive_summary and key_points
        """
        # Default values
        executive = text.strip()
        key_points = []

        # Headers for each language
        if language == "fr":
            key_points_headers = ["## Points Clés", "Points Clés", "## Key Points", "Key Points"]
            executive_headers = ["## Résumé Exécutif", "Résumé Exécutif", "## Executive Summary", "Executive Summary"]
        else:
            key_points_headers = ["## Key Points", "Key Points", "## Points Clés", "Points Clés"]
            executive_headers = ["## Executive Summary", "Executive Summary", "## Résumé Exécutif", "Résumé Exécutif"]

        # Try to parse structured response
        for kp_header in key_points_headers:
            if kp_header in text:
                parts = text.split(kp_header)
                # Remove executive summary header from first part
                first_part = parts[0]
                for exec_header in executive_headers:
                    first_part = first_part.replace(exec_header, "")
                executive = first_part.strip()

                if len(parts) > 1:
                    lines = parts[1].strip().split("\n")
                    key_points = [
                        line.lstrip("- *").rstrip("*").strip()
                        for line in lines
                        if line.strip().startswith("-") or line.strip().startswith("*")
                    ]
                break

        # Fallback: try basic "Key Points" or "Points Clés" detection
        if not key_points:
            for kp_marker in ["Key Points", "Points Clés"]:
                if kp_marker in text:
                    parts = text.split(kp_marker)
                    executive = parts[0].replace("Executive Summary", "").replace("Résumé Exécutif", "").strip()

                    if len(parts) > 1:
                        lines = parts[1].strip().split("\n")
                        key_points = [
                            line.lstrip("- *:").rstrip("*").strip()
                            for line in lines
                            if line.strip()
                            and (
                                line.strip().startswith("-")
                                or line.strip().startswith("*")
                                or (line.strip() and line.strip()[0].isdigit())
                            )
                        ]
                    break

        # Clean up executive summary
        executive = executive.strip()
        if executive.startswith(":"):
            executive = executive[1:].strip()

        # Ensure we have at least some key points
        if not key_points and executive:
            # Extract sentences as fallback key points
            sentences = [s.strip() for s in executive.split(".") if len(s.strip()) > 20]
            key_points = sentences[:5]

        return {
            "executive_summary": executive,
            "key_points": key_points,
        }
