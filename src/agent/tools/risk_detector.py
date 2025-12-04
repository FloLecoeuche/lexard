"""Risk detection tool for contract documents.

Identifies potential risks in contracts including:
- Legal liability risks
- Financial penalty risks
- Data protection/GDPR issues
- Unfavorable termination conditions
- Ambiguous language
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from qdrant_client.http import models

if TYPE_CHECKING:
    from src.db.qdrant import QdrantService
    from src.rag.llm import OllamaClient

logger = logging.getLogger(__name__)


class RiskSeverity(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskCategory(str, Enum):
    """Categories of contract risks."""

    LEGAL_LIABILITY = "legal_liability"
    FINANCIAL_PENALTY = "financial_penalty"
    DATA_PROTECTION = "data_protection"
    TERMINATION = "termination"
    AMBIGUOUS_LANGUAGE = "ambiguous_language"
    OTHER = "other"


@dataclass
class Risk:
    """A single identified risk.

    Attributes:
        category: Type of risk
        severity: Risk severity level
        description: Explanation of the risk
        clause_excerpt: Relevant text from the document
        page: Page number where risk was found
        recommendation: Suggested mitigation (optional)
    """

    category: RiskCategory
    severity: RiskSeverity
    description: str
    clause_excerpt: str
    page: int
    recommendation: str | None = None


@dataclass
class RiskAnalysisResult:
    """Result from risk analysis.

    Attributes:
        risks: List of identified risks
        overall_risk_level: Aggregated risk severity
        summary: Human-readable summary
        document_id: Analyzed document ID
    """

    risks: list[Risk] = field(default_factory=list)
    overall_risk_level: RiskSeverity = RiskSeverity.LOW
    summary: str = ""
    document_id: str = ""


class RiskDetectorTool:
    """Identify risks in contract documents.

    Analyzes document chunks to detect potential legal, financial,
    and operational risks in contracts.

    Args:
        llm_client: Ollama client for LLM generation
        qdrant_service: Qdrant service for retrieving document chunks
    """

    RISK_ANALYSIS_PROMPT = """Analyze the following contract excerpt for potential risks.

EXCERPT (Page {page}):
{content}

Identify any risks in these categories:
1. Legal liability risks (indemnification, warranties, liability caps)
2. Financial penalty risks (late fees, liquidated damages, penalties)
3. Data protection/GDPR compliance issues (data handling, privacy)
4. Unfavorable termination conditions (notice periods, termination for convenience)
5. Ambiguous language that could be exploited (vague terms, undefined obligations)

For each risk found, provide:
- Category: one of [legal_liability, financial_penalty, data_protection, termination, ambiguous_language, other]
- Severity: low/medium/high
- Description: Brief explanation of the risk
- Clause: Quote the relevant text exactly
- Recommendation: How to mitigate (optional)

If no risks are found, respond with exactly: NO_RISKS_FOUND

If risks are found, respond with valid JSON only:
{{"risks": [
  {{
    "category": "category_name",
    "severity": "low|medium|high",
    "description": "...",
    "clause": "quoted text...",
    "recommendation": "..."
  }}
]}}"""

    # Batch size for chunk processing
    CHUNK_BATCH_SIZE = 3
    # Maximum chunks to analyze
    MAX_CHUNKS = 50

    def __init__(
        self,
        llm_client: "OllamaClient",
        qdrant_service: "QdrantService",
    ):
        """Initialize risk detector tool.

        Args:
            llm_client: Ollama client for LLM generation
            qdrant_service: Qdrant service for chunk retrieval
        """
        self.llm = llm_client
        self.qdrant_service = qdrant_service

    async def analyze(self, document_id: str) -> RiskAnalysisResult:
        """Analyze document for risks.

        Args:
            document_id: Document ID to analyze

        Returns:
            RiskAnalysisResult with identified risks

        Raises:
            ValueError: If no chunks found for document
        """
        logger.info(f"Starting risk analysis for document {document_id}")

        # 1. Get all chunks
        chunks = await self._get_all_chunks(document_id)

        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")

        # Limit chunks for very long documents
        if len(chunks) > self.MAX_CHUNKS:
            logger.warning(
                f"Document has {len(chunks)} chunks, limiting to {self.MAX_CHUNKS}"
            )
            chunks = chunks[: self.MAX_CHUNKS]

        # 2. Analyze each chunk for risks (in batches)
        all_risks = await self._analyze_chunks_batch(chunks)

        logger.info(f"Found {len(all_risks)} raw risks before deduplication")

        # 3. Deduplicate similar risks
        unique_risks = self._deduplicate_risks(all_risks)

        logger.info(f"Found {len(unique_risks)} unique risks after deduplication")

        # 4. Calculate overall risk level
        overall = self._calculate_overall_risk(unique_risks)

        # 5. Generate summary
        summary = self._generate_summary(unique_risks)

        result = RiskAnalysisResult(
            risks=unique_risks,
            overall_risk_level=overall,
            summary=summary,
            document_id=document_id,
        )

        logger.info(
            f"Risk analysis complete: {len(unique_risks)} risks, "
            f"overall level: {overall.value}"
        )

        return result

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

        loop = asyncio.get_event_loop()
        results, _ = await loop.run_in_executor(None, _scroll)

        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.payload.get("chunk_index", 0))

        return results

    async def _analyze_chunks_batch(self, chunks: list) -> list[Risk]:
        """Analyze chunks in batches for risks.

        Args:
            chunks: List of chunk points from Qdrant

        Returns:
            List of identified Risk objects
        """
        all_risks = []

        # Process in batches
        for i in range(0, len(chunks), self.CHUNK_BATCH_SIZE):
            batch = chunks[i : i + self.CHUNK_BATCH_SIZE]

            # Process batch concurrently
            tasks = [self._analyze_chunk(chunk) for chunk in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for chunk, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed to analyze chunk {chunk.payload.get('chunk_index', 0)}: {result}"
                    )
                else:
                    all_risks.extend(result)

        return all_risks

    async def _analyze_chunk(self, chunk) -> list[Risk]:
        """Analyze a single chunk for risks.

        Args:
            chunk: Qdrant point with payload

        Returns:
            List of risks found in this chunk
        """
        content = chunk.payload.get("content", "")
        page = chunk.payload.get("page", 0)

        if not content.strip():
            return []

        prompt = self.RISK_ANALYSIS_PROMPT.format(page=page, content=content)

        def _generate():
            return self.llm.generate(prompt)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _generate)

        if "NO_RISKS_FOUND" in response.content:
            return []

        return self._parse_risks(response.content, page)

    def _parse_risks(self, response: str, page: int) -> list[Risk]:
        """Parse LLM response into Risk objects.

        Args:
            response: Raw LLM response text
            page: Page number for context

        Returns:
            List of parsed Risk objects
        """
        try:
            # Try to extract JSON from response
            content = response.strip()

            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1]

            content = content.strip()

            # Try to find JSON object
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                logger.debug(f"No JSON found in response: {content[:100]}...")
                return []

            json_str = content[start_idx:end_idx]
            data = json.loads(json_str)

            risks = []
            for r in data.get("risks", []):
                try:
                    # Parse category with fallback
                    category_str = r.get("category", "other").lower().replace(" ", "_")
                    try:
                        category = RiskCategory(category_str)
                    except ValueError:
                        category = RiskCategory.OTHER

                    # Parse severity with fallback
                    severity_str = r.get("severity", "low").lower()
                    try:
                        severity = RiskSeverity(severity_str)
                    except ValueError:
                        severity = RiskSeverity.LOW

                    risks.append(
                        Risk(
                            category=category,
                            severity=severity,
                            description=r.get("description", ""),
                            clause_excerpt=r.get("clause", ""),
                            page=page,
                            recommendation=r.get("recommendation"),
                        )
                    )
                except (KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse individual risk: {e}")
                    continue

            return risks

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}, response: {response[:200]}...")
            return []
        except Exception as e:
            logger.debug(f"Unexpected error parsing risks: {e}")
            return []

    def _deduplicate_risks(self, risks: list[Risk]) -> list[Risk]:
        """Remove duplicate/similar risks.

        Uses description similarity to identify duplicates.

        Args:
            risks: List of all identified risks

        Returns:
            List of unique risks
        """
        unique = []
        seen_descriptions = set()

        for risk in risks:
            # Create a key from first 50 chars of description, normalized
            desc_key = risk.description[:50].lower().strip()

            if desc_key not in seen_descriptions:
                unique.append(risk)
                seen_descriptions.add(desc_key)

        return unique

    def _calculate_overall_risk(self, risks: list[Risk]) -> RiskSeverity:
        """Calculate overall risk level from individual risks.

        Logic:
        - Any HIGH severity risk = HIGH overall
        - Any MEDIUM severity risk = MEDIUM overall
        - Only LOW or no risks = LOW overall

        Args:
            risks: List of identified risks

        Returns:
            Aggregated risk severity
        """
        if not risks:
            return RiskSeverity.LOW

        if any(r.severity == RiskSeverity.HIGH for r in risks):
            return RiskSeverity.HIGH

        if any(r.severity == RiskSeverity.MEDIUM for r in risks):
            return RiskSeverity.MEDIUM

        return RiskSeverity.LOW

    def _generate_summary(self, risks: list[Risk]) -> str:
        """Generate human-readable risk summary.

        Args:
            risks: List of identified risks

        Returns:
            Summary string
        """
        if not risks:
            return "No significant risks identified in this document."

        high = sum(1 for r in risks if r.severity == RiskSeverity.HIGH)
        medium = sum(1 for r in risks if r.severity == RiskSeverity.MEDIUM)
        low = sum(1 for r in risks if r.severity == RiskSeverity.LOW)

        # Count by category
        categories = {}
        for r in risks:
            cat_name = r.category.value.replace("_", " ").title()
            categories[cat_name] = categories.get(cat_name, 0) + 1

        category_breakdown = ", ".join(
            f"{count} {cat}" for cat, count in sorted(categories.items())
        )

        return (
            f"Identified {len(risks)} risks: {high} high, {medium} medium, {low} low severity. "
            f"Categories: {category_breakdown}."
        )
