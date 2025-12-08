"""Risk detection tool for contract documents.

Identifies potential risks in contracts including:
- Legal liability risks
- Financial penalty risks
- Data protection/GDPR issues
- Unfavorable termination conditions
- Ambiguous language

Supports multilingual documents (English and French) with language
auto-detection from document content.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

from qdrant_client.http import models

from src.rag.llm import detect_language

if TYPE_CHECKING:
    from src.api.progress import OperationProgressTracker
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
        language: Detected/used language for the analysis ('en' or 'fr')
    """

    risks: list[Risk] = field(default_factory=list)
    overall_risk_level: RiskSeverity = RiskSeverity.LOW
    summary: str = ""
    document_id: str = ""
    language: Literal["en", "fr"] = "en"


class RiskDetectorTool:
    """Identify risks in contract documents.

    Analyzes document chunks to detect potential legal, financial,
    and operational risks in contracts.

    Supports multilingual documents with automatic language detection from
    document content. French documents receive French risk analysis, English
    documents receive English risk analysis.

    Args:
        llm_client: Ollama client for LLM generation
        qdrant_service: Qdrant service for retrieving document chunks
    """

    RISK_ANALYSIS_PROMPTS = {
        "en": """You are analyzing a contract in English. You MUST respond entirely in English.

Analyze the following contract excerpt for potential risks.

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
- Description: Brief explanation of the risk (MUST be in English)
- Clause: Quote the relevant text exactly
- Recommendation: How to mitigate (MUST be in English)

If no risks are found, respond with exactly: NO_RISKS_FOUND

IMPORTANT: All description and recommendation fields MUST be written in English.

If risks are found, respond with valid JSON only:
{{"risks": [
  {{
    "category": "category_name",
    "severity": "low|medium|high",
    "description": "English description here",
    "clause": "quoted text...",
    "recommendation": "English recommendation here"
  }}
]}}""",
        "fr": """Vous analysez un contrat en français. Vous DEVEZ répondre entièrement en français.

Analysez l'extrait de contrat suivant pour identifier les risques potentiels.

EXTRAIT (Page {page}):
{content}

Identifiez les risques dans ces catégories:
1. Risques de responsabilité juridique (indemnisation, garanties, plafonds de responsabilité)
2. Risques de pénalités financières (pénalités de retard, dommages-intérêts, amendes)
3. Problèmes de protection des données/RGPD (traitement des données, vie privée)
4. Conditions de résiliation défavorables (préavis, résiliation pour convenance)
5. Langage ambigu pouvant être exploité (termes vagues, obligations non définies)

Pour chaque risque trouvé, fournissez:
- Catégorie: une parmi [legal_liability, financial_penalty, data_protection, termination, ambiguous_language, other]
- Gravité: low/medium/high
- Description: Brève explication du risque (DOIT être en français)
- Clause: Citation exacte du texte concerné
- Recommandation: Comment atténuer (DOIT être en français)

Si aucun risque n'est trouvé, répondez exactement: NO_RISKS_FOUND

IMPORTANT: Tous les champs description et recommendation DOIVENT être rédigés en français.

Si des risques sont trouvés, répondez uniquement avec du JSON valide:
{{"risks": [
  {{
    "category": "nom_categorie",
    "severity": "low|medium|high",
    "description": "Description en français ici",
    "clause": "texte cité...",
    "recommendation": "Recommandation en français ici"
  }}
]}}""",
    }

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

    async def analyze(
        self, document_id: str, language: str | None = None
    ) -> RiskAnalysisResult:
        """Analyze document for risks.

        Args:
            document_id: Document ID to analyze
            language: Output language ('en' or 'fr'). If None, auto-detected
                     from document content.

        Returns:
            RiskAnalysisResult with identified risks

        Raises:
            ValueError: If no chunks found for document

        Note:
            Language is detected from the DOCUMENT content (chunks),
            ensuring French documents always get French risk analysis.
        """
        logger.info(f"Starting risk analysis for document {document_id}")

        # 1. Get all chunks
        chunks = await self._get_all_chunks(document_id)

        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")

        # 2. Detect language from document content if not provided
        if language is None:
            language = self._detect_language_from_chunks(chunks)

        logger.info(f"Using language '{language}' for risk analysis")

        # Limit chunks for very long documents
        if len(chunks) > self.MAX_CHUNKS:
            logger.warning(
                f"Document has {len(chunks)} chunks, limiting to {self.MAX_CHUNKS}"
            )
            chunks = chunks[: self.MAX_CHUNKS]

        # 3. Analyze each chunk for risks (in batches)
        all_risks = await self._analyze_chunks_batch(chunks, language)

        logger.info(f"Found {len(all_risks)} raw risks before deduplication")

        # 4. Deduplicate similar risks
        unique_risks = self._deduplicate_risks(all_risks)

        logger.info(f"Found {len(unique_risks)} unique risks after deduplication")

        # 5. Calculate overall risk level
        overall = self._calculate_overall_risk(unique_risks)

        # 6. Generate summary
        summary = self._generate_summary(unique_risks, language)

        result = RiskAnalysisResult(
            risks=unique_risks,
            overall_risk_level=overall,
            summary=summary,
            document_id=document_id,
            language=language,
        )

        logger.info(
            f"Risk analysis complete: {len(unique_risks)} risks, "
            f"overall level: {overall.value}, language={language}"
        )

        return result

    async def analyze_with_progress(
        self,
        document_id: str,
        language: str | None = None,
        tracker: "OperationProgressTracker | None" = None,
        operation_id: str | None = None,
    ) -> RiskAnalysisResult:
        """Analyze document for risks with progress tracking.

        Args:
            document_id: Document ID to analyze
            language: Output language ('en' or 'fr'). If None, auto-detected
            tracker: Progress tracker instance
            operation_id: Operation ID for tracking

        Returns:
            RiskAnalysisResult with identified risks

        Raises:
            ValueError: If no chunks found for document
        """
        import asyncio
        from src.api.progress import OperationStage

        logger.info(f"Starting risk analysis with progress for document {document_id}")

        # Wait for SSE client to connect before starting heavy work
        if tracker and operation_id:
            await tracker.wait_for_subscriber(operation_id, timeout=0.5)

        # Stage 1: Loading (0-15%)
        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.RETRIEVING,
                0.05,
                "Loading document...",
            )
            await asyncio.sleep(0)  # Yield to let SSE send the update

        # Get all chunks
        chunks = await self._get_all_chunks(document_id)

        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.RETRIEVING,
                0.15,
                f"Loaded {len(chunks)} sections",
            )
            await asyncio.sleep(0)

        logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")

        # Detect language from document content if not provided
        if language is None:
            language = self._detect_language_from_chunks(chunks)

        logger.info(f"Using language '{language}' for risk analysis")

        # Limit chunks for very long documents
        if len(chunks) > self.MAX_CHUNKS:
            logger.warning(
                f"Document has {len(chunks)} chunks, limiting to {self.MAX_CHUNKS}"
            )
            chunks = chunks[: self.MAX_CHUNKS]

        # Stage 2: Analyzing chunks (15-70%)
        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.GENERATING,
                0.20,
                "Analyzing clauses...",
            )
            await asyncio.sleep(0)

        all_risks = await self._analyze_chunks_batch_with_progress(
            chunks, language, tracker, operation_id
        )

        logger.info(f"Found {len(all_risks)} raw risks before deduplication")

        # Stage 3: Evaluating (70-85%)
        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.GENERATING,
                0.70,
                "Evaluating risks...",
            )
            await asyncio.sleep(0)

        # Deduplicate similar risks
        unique_risks = self._deduplicate_risks(all_risks)

        logger.info(f"Found {len(unique_risks)} unique risks after deduplication")

        # Calculate overall risk level
        overall = self._calculate_overall_risk(unique_risks)

        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.GENERATING,
                0.85,
                "Risk evaluation complete",
            )
            await asyncio.sleep(0)

        # Stage 4: Validation (85-100%)
        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.VALIDATING,
                0.90,
                "Validating response...",
            )
            await asyncio.sleep(0)

        # Generate summary
        summary = self._generate_summary(unique_risks, language)

        result = RiskAnalysisResult(
            risks=unique_risks,
            overall_risk_level=overall,
            summary=summary,
            document_id=document_id,
            language=language,
        )

        if tracker and operation_id:
            await tracker.update(
                operation_id,
                OperationStage.VALIDATING,
                0.95,
                "Building result...",
            )
            await asyncio.sleep(0)

        logger.info(
            f"Risk analysis with progress complete: {len(unique_risks)} risks, "
            f"overall level: {overall.value}, language={language}"
        )

        return result

    async def _analyze_chunks_batch_with_progress(
        self,
        chunks: list,
        language: str = "en",
        tracker: "OperationProgressTracker | None" = None,
        operation_id: str | None = None,
    ) -> list[Risk]:
        """Analyze chunks in batches for risks with progress updates.

        Args:
            chunks: List of chunk points from Qdrant
            language: Language for prompts ('en' or 'fr')
            tracker: Progress tracker instance
            operation_id: Operation ID for tracking

        Returns:
            List of identified Risk objects
        """
        from src.api.progress import OperationStage

        all_risks = []
        total_chunks = len(chunks)

        # Process in batches
        for i in range(0, len(chunks), self.CHUNK_BATCH_SIZE):
            batch = chunks[i : i + self.CHUNK_BATCH_SIZE]

            # Update progress (20% to 70% range)
            if tracker and operation_id:
                progress = 0.20 + (0.50 * (i / total_chunks))
                await tracker.update(
                    operation_id,
                    OperationStage.GENERATING,
                    progress,
                    f"Analyzing section {i + 1} of {total_chunks}...",
                )

            # Process batch concurrently
            tasks = [self._analyze_chunk(chunk, language) for chunk in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for chunk, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed to analyze chunk {chunk.payload.get('chunk_index', 0)}: {result}"
                    )
                else:
                    all_risks.extend(result)

        return all_risks

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

        loop = asyncio.get_event_loop()
        results, _ = await loop.run_in_executor(None, _scroll)

        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.payload.get("chunk_index", 0))

        return results

    async def _analyze_chunks_batch(
        self, chunks: list, language: str = "en"
    ) -> list[Risk]:
        """Analyze chunks in batches for risks.

        Args:
            chunks: List of chunk points from Qdrant
            language: Language for prompts ('en' or 'fr')

        Returns:
            List of identified Risk objects
        """
        all_risks = []

        # Process in batches
        for i in range(0, len(chunks), self.CHUNK_BATCH_SIZE):
            batch = chunks[i : i + self.CHUNK_BATCH_SIZE]

            # Process batch concurrently
            tasks = [self._analyze_chunk(chunk, language) for chunk in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for chunk, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed to analyze chunk {chunk.payload.get('chunk_index', 0)}: {result}"
                    )
                else:
                    all_risks.extend(result)

        return all_risks

    async def _analyze_chunk(self, chunk, language: str = "en") -> list[Risk]:
        """Analyze a single chunk for risks.

        Args:
            chunk: Qdrant point with payload
            language: Language for prompts ('en' or 'fr')

        Returns:
            List of risks found in this chunk
        """
        content = chunk.payload.get("content", "")
        page = chunk.payload.get("page", 0)

        if not content.strip():
            return []

        # Get language-specific prompt
        prompt_template = self.RISK_ANALYSIS_PROMPTS.get(
            language, self.RISK_ANALYSIS_PROMPTS["en"]
        )
        prompt = prompt_template.format(page=page, content=content)

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

                    # Ensure clause_excerpt is never None (required field)
                    clause = r.get("clause") or r.get("clause_excerpt") or ""
                    description = r.get("description") or ""

                    # Skip if no meaningful content
                    if not description and not clause:
                        continue

                    risks.append(
                        Risk(
                            category=category,
                            severity=severity,
                            description=description,
                            clause_excerpt=clause if clause else "[No specific clause cited]",
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

    def _generate_summary(self, risks: list[Risk], language: str = "en") -> str:
        """Generate human-readable risk summary.

        Args:
            risks: List of identified risks
            language: Language for summary ('en' or 'fr')

        Returns:
            Summary string
        """
        if not risks:
            if language == "fr":
                return "Aucun risque significatif identifié dans ce document."
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

        if language == "fr":
            return (
                f"{len(risks)} risques identifiés: {high} élevé(s), {medium} moyen(s), {low} faible(s). "
                f"Catégories: {category_breakdown}."
            )

        return (
            f"Identified {len(risks)} risks: {high} high, {medium} medium, {low} low severity. "
            f"Categories: {category_breakdown}."
        )
