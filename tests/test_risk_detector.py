"""Tests for risk detection tool."""

import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock

from src.agent.tools.risk_detector import (
    Risk,
    RiskAnalysisResult,
    RiskCategory,
    RiskDetectorTool,
    RiskSeverity,
)
from src.rag.llm import LLMResponse


@dataclass
class MockPoint:
    """Mock Qdrant point."""

    payload: dict


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.generate = MagicMock(
        return_value=LLMResponse(
            content="NO_RISKS_FOUND",
            model="test-model",
            total_tokens=50,
            finish_reason="stop",
        )
    )
    return client


@pytest.fixture
def mock_qdrant_service():
    """Create mock Qdrant service."""
    service = MagicMock()
    service.collection_name = "test_collection"
    service.client = MagicMock()
    return service


@pytest.fixture
def risk_detector(mock_llm_client, mock_qdrant_service):
    """Create RiskDetectorTool instance."""
    return RiskDetectorTool(
        llm_client=mock_llm_client, qdrant_service=mock_qdrant_service
    )


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        MockPoint(
            payload={
                "content": "The contractor shall indemnify and hold harmless the client from any claims.",
                "page": 1,
                "chunk_index": 0,
                "document_id": "doc-123",
            }
        ),
        MockPoint(
            payload={
                "content": "Late payments shall incur a penalty of 5% per month.",
                "page": 2,
                "chunk_index": 1,
                "document_id": "doc-123",
            }
        ),
        MockPoint(
            payload={
                "content": "Either party may terminate this agreement with 30 days written notice.",
                "page": 3,
                "chunk_index": 2,
                "document_id": "doc-123",
            }
        ),
    ]


class TestRiskEnums:
    """Test Risk-related enums."""

    def test_risk_severity_values(self):
        """Test RiskSeverity enum values."""
        assert RiskSeverity.LOW.value == "low"
        assert RiskSeverity.MEDIUM.value == "medium"
        assert RiskSeverity.HIGH.value == "high"

    def test_risk_category_values(self):
        """Test RiskCategory enum values."""
        assert RiskCategory.LEGAL_LIABILITY.value == "legal_liability"
        assert RiskCategory.FINANCIAL_PENALTY.value == "financial_penalty"
        assert RiskCategory.DATA_PROTECTION.value == "data_protection"
        assert RiskCategory.TERMINATION.value == "termination"
        assert RiskCategory.AMBIGUOUS_LANGUAGE.value == "ambiguous_language"
        assert RiskCategory.OTHER.value == "other"


class TestRisk:
    """Test Risk dataclass."""

    def test_risk_creation(self):
        """Test creating a Risk object."""
        risk = Risk(
            category=RiskCategory.FINANCIAL_PENALTY,
            severity=RiskSeverity.HIGH,
            description="Late payment penalty of 5% per month is excessive.",
            clause_excerpt="Late payments shall incur a penalty of 5% per month.",
            page=2,
            recommendation="Negotiate penalty down to 1.5% per month.",
        )
        assert risk.category == RiskCategory.FINANCIAL_PENALTY
        assert risk.severity == RiskSeverity.HIGH
        assert "5%" in risk.clause_excerpt
        assert risk.page == 2
        assert risk.recommendation is not None

    def test_risk_without_recommendation(self):
        """Test Risk with optional recommendation."""
        risk = Risk(
            category=RiskCategory.LEGAL_LIABILITY,
            severity=RiskSeverity.MEDIUM,
            description="Broad indemnification clause.",
            clause_excerpt="shall indemnify and hold harmless",
            page=1,
        )
        assert risk.recommendation is None


class TestRiskAnalysisResult:
    """Test RiskAnalysisResult dataclass."""

    def test_result_creation(self):
        """Test creating a RiskAnalysisResult."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Test risk",
                clause_excerpt="test clause",
                page=1,
            )
        ]
        result = RiskAnalysisResult(
            risks=risks,
            overall_risk_level=RiskSeverity.HIGH,
            summary="1 high risk identified.",
            document_id="doc-123",
        )
        assert len(result.risks) == 1
        assert result.overall_risk_level == RiskSeverity.HIGH
        assert result.document_id == "doc-123"

    def test_result_defaults(self):
        """Test RiskAnalysisResult default values."""
        result = RiskAnalysisResult()
        assert result.risks == []
        assert result.overall_risk_level == RiskSeverity.LOW
        assert result.summary == ""
        assert result.document_id == ""


class TestRiskDetectorInit:
    """Test RiskDetectorTool initialization."""

    def test_init(self, mock_llm_client, mock_qdrant_service):
        """Test basic initialization."""
        detector = RiskDetectorTool(
            llm_client=mock_llm_client, qdrant_service=mock_qdrant_service
        )
        assert detector.llm == mock_llm_client
        assert detector.qdrant_service == mock_qdrant_service

    def test_constants(self, risk_detector):
        """Test default constants are set."""
        assert risk_detector.CHUNK_BATCH_SIZE == 3
        assert risk_detector.MAX_CHUNKS == 50


class TestGetAllChunks:
    """Test chunk retrieval."""

    @pytest.mark.asyncio
    async def test_get_all_chunks(self, risk_detector, sample_chunks):
        """Test retrieving all chunks for a document."""
        risk_detector.qdrant_service.client.scroll.return_value = (sample_chunks, None)

        chunks = await risk_detector._get_all_chunks("doc-123")

        assert len(chunks) == 3
        risk_detector.qdrant_service.client.scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_sorted_by_index(self, risk_detector, sample_chunks):
        """Test chunks are sorted by chunk_index."""
        shuffled = [sample_chunks[2], sample_chunks[0], sample_chunks[1]]
        risk_detector.qdrant_service.client.scroll.return_value = (shuffled, None)

        chunks = await risk_detector._get_all_chunks("doc-123")

        indices = [c.payload["chunk_index"] for c in chunks]
        assert indices == [0, 1, 2]


class TestAnalyzeChunk:
    """Test single chunk analysis."""

    @pytest.mark.asyncio
    async def test_analyze_chunk_no_risks(self, risk_detector, sample_chunks):
        """Test analyzing a chunk with no risks."""
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        risks = await risk_detector._analyze_chunk(sample_chunks[0])

        assert risks == []

    @pytest.mark.asyncio
    async def test_analyze_chunk_with_risks(self, risk_detector, sample_chunks):
        """Test analyzing a chunk that contains risks."""
        risk_detector.llm.generate.return_value = LLMResponse(
            content="""{"risks": [
                {
                    "category": "financial_penalty",
                    "severity": "high",
                    "description": "Excessive late payment penalty.",
                    "clause": "penalty of 5% per month",
                    "recommendation": "Negotiate lower penalty."
                }
            ]}""",
            model="test",
            total_tokens=100,
            finish_reason="stop",
        )

        risks = await risk_detector._analyze_chunk(sample_chunks[1])

        assert len(risks) == 1
        assert risks[0].category == RiskCategory.FINANCIAL_PENALTY
        assert risks[0].severity == RiskSeverity.HIGH

    @pytest.mark.asyncio
    async def test_analyze_empty_chunk(self, risk_detector):
        """Test handling empty chunk."""
        empty_chunk = MockPoint(payload={"content": "", "page": 1, "chunk_index": 0})

        risks = await risk_detector._analyze_chunk(empty_chunk)

        assert risks == []


class TestParseRisks:
    """Test risk parsing from LLM response."""

    def test_parse_valid_json(self, risk_detector):
        """Test parsing valid JSON response."""
        response = """{"risks": [
            {
                "category": "legal_liability",
                "severity": "medium",
                "description": "Broad indemnification.",
                "clause": "indemnify and hold harmless"
            }
        ]}"""

        risks = risk_detector._parse_risks(response, page=1)

        assert len(risks) == 1
        assert risks[0].category == RiskCategory.LEGAL_LIABILITY
        assert risks[0].severity == RiskSeverity.MEDIUM
        assert risks[0].page == 1

    def test_parse_json_in_code_block(self, risk_detector):
        """Test parsing JSON wrapped in markdown code block."""
        response = """Here are the risks:

```json
{"risks": [
    {
        "category": "termination",
        "severity": "low",
        "description": "Short notice period.",
        "clause": "30 days written notice"
    }
]}
```"""

        risks = risk_detector._parse_risks(response, page=3)

        assert len(risks) == 1
        assert risks[0].category == RiskCategory.TERMINATION

    def test_parse_unknown_category_fallback(self, risk_detector):
        """Test unknown category falls back to OTHER."""
        response = """{"risks": [
            {
                "category": "unknown_category",
                "severity": "low",
                "description": "Some risk",
                "clause": "some clause"
            }
        ]}"""

        risks = risk_detector._parse_risks(response, page=1)

        assert len(risks) == 1
        assert risks[0].category == RiskCategory.OTHER

    def test_parse_unknown_severity_fallback(self, risk_detector):
        """Test unknown severity falls back to LOW."""
        response = """{"risks": [
            {
                "category": "legal_liability",
                "severity": "critical",
                "description": "Some risk",
                "clause": "some clause"
            }
        ]}"""

        risks = risk_detector._parse_risks(response, page=1)

        assert len(risks) == 1
        assert risks[0].severity == RiskSeverity.LOW

    def test_parse_invalid_json(self, risk_detector):
        """Test handling invalid JSON gracefully."""
        response = "This is not JSON at all."

        risks = risk_detector._parse_risks(response, page=1)

        assert risks == []

    def test_parse_empty_risks_array(self, risk_detector):
        """Test handling empty risks array."""
        response = """{"risks": []}"""

        risks = risk_detector._parse_risks(response, page=1)

        assert risks == []

    def test_parse_multiple_risks(self, risk_detector):
        """Test parsing multiple risks."""
        response = """{"risks": [
            {
                "category": "financial_penalty",
                "severity": "high",
                "description": "Risk 1",
                "clause": "clause 1"
            },
            {
                "category": "data_protection",
                "severity": "medium",
                "description": "Risk 2",
                "clause": "clause 2"
            }
        ]}"""

        risks = risk_detector._parse_risks(response, page=2)

        assert len(risks) == 2
        assert risks[0].category == RiskCategory.FINANCIAL_PENALTY
        assert risks[1].category == RiskCategory.DATA_PROTECTION


class TestDeduplicateRisks:
    """Test risk deduplication."""

    def test_deduplicate_identical_descriptions(self, risk_detector):
        """Test removing risks with identical descriptions."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Broad indemnification clause requires attention.",
                clause_excerpt="clause 1",
                page=1,
            ),
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Broad indemnification clause requires attention.",
                clause_excerpt="clause 2",
                page=2,
            ),
        ]

        unique = risk_detector._deduplicate_risks(risks)

        assert len(unique) == 1

    def test_keep_different_descriptions(self, risk_detector):
        """Test keeping risks with different descriptions."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="First unique risk description here.",
                clause_excerpt="clause 1",
                page=1,
            ),
            Risk(
                category=RiskCategory.FINANCIAL_PENALTY,
                severity=RiskSeverity.MEDIUM,
                description="Second completely different risk.",
                clause_excerpt="clause 2",
                page=2,
            ),
        ]

        unique = risk_detector._deduplicate_risks(risks)

        assert len(unique) == 2

    def test_deduplicate_empty_list(self, risk_detector):
        """Test deduplicating empty list."""
        unique = risk_detector._deduplicate_risks([])
        assert unique == []


class TestCalculateOverallRisk:
    """Test overall risk calculation."""

    def test_no_risks_is_low(self, risk_detector):
        """Test no risks results in LOW overall."""
        overall = risk_detector._calculate_overall_risk([])
        assert overall == RiskSeverity.LOW

    def test_all_low_is_low(self, risk_detector):
        """Test all LOW risks result in LOW overall."""
        risks = [
            Risk(
                category=RiskCategory.AMBIGUOUS_LANGUAGE,
                severity=RiskSeverity.LOW,
                description="Minor issue",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.OTHER,
                severity=RiskSeverity.LOW,
                description="Another minor issue",
                clause_excerpt="clause",
                page=2,
            ),
        ]

        overall = risk_detector._calculate_overall_risk(risks)
        assert overall == RiskSeverity.LOW

    def test_any_medium_is_medium(self, risk_detector):
        """Test any MEDIUM risk results in MEDIUM overall."""
        risks = [
            Risk(
                category=RiskCategory.AMBIGUOUS_LANGUAGE,
                severity=RiskSeverity.LOW,
                description="Minor issue",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.TERMINATION,
                severity=RiskSeverity.MEDIUM,
                description="Moderate issue",
                clause_excerpt="clause",
                page=2,
            ),
        ]

        overall = risk_detector._calculate_overall_risk(risks)
        assert overall == RiskSeverity.MEDIUM

    def test_any_high_is_high(self, risk_detector):
        """Test any HIGH risk results in HIGH overall."""
        risks = [
            Risk(
                category=RiskCategory.AMBIGUOUS_LANGUAGE,
                severity=RiskSeverity.LOW,
                description="Minor issue",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Major issue",
                clause_excerpt="clause",
                page=2,
            ),
        ]

        overall = risk_detector._calculate_overall_risk(risks)
        assert overall == RiskSeverity.HIGH


class TestGenerateSummary:
    """Test summary generation."""

    def test_no_risks_summary(self, risk_detector):
        """Test summary for no risks."""
        summary = risk_detector._generate_summary([])
        assert "No significant risks" in summary

    def test_summary_with_risks(self, risk_detector):
        """Test summary includes risk counts."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="High risk",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.FINANCIAL_PENALTY,
                severity=RiskSeverity.MEDIUM,
                description="Medium risk",
                clause_excerpt="clause",
                page=2,
            ),
            Risk(
                category=RiskCategory.AMBIGUOUS_LANGUAGE,
                severity=RiskSeverity.LOW,
                description="Low risk",
                clause_excerpt="clause",
                page=3,
            ),
        ]

        summary = risk_detector._generate_summary(risks)

        assert "3 risks" in summary
        assert "1 high" in summary
        assert "1 medium" in summary
        assert "1 low" in summary

    def test_summary_includes_categories(self, risk_detector):
        """Test summary includes category breakdown."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Legal risk",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.MEDIUM,
                description="Another legal risk",
                clause_excerpt="clause",
                page=2,
            ),
        ]

        summary = risk_detector._generate_summary(risks)

        assert "Legal Liability" in summary


class TestAnalyze:
    """Test main analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_document_no_risks(self, risk_detector, sample_chunks):
        """Test analyzing document with no risks."""
        risk_detector.qdrant_service.client.scroll.return_value = (sample_chunks, None)
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        result = await risk_detector.analyze("doc-123")

        assert isinstance(result, RiskAnalysisResult)
        assert result.risks == []
        assert result.overall_risk_level == RiskSeverity.LOW
        assert result.document_id == "doc-123"

    @pytest.mark.asyncio
    async def test_analyze_document_with_risks(self, risk_detector, sample_chunks):
        """Test analyzing document that contains risks."""
        risk_detector.qdrant_service.client.scroll.return_value = (sample_chunks, None)

        # Return risks for each chunk
        call_count = [0]

        def mock_generate(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResponse(
                    content="""{"risks": [{"category": "legal_liability", "severity": "high", "description": "Indemnification risk", "clause": "indemnify"}]}""",
                    model="test",
                    total_tokens=50,
                    finish_reason="stop",
                )
            return LLMResponse(
                content="NO_RISKS_FOUND",
                model="test",
                total_tokens=10,
                finish_reason="stop",
            )

        risk_detector.llm.generate = mock_generate

        result = await risk_detector.analyze("doc-123")

        assert len(result.risks) >= 1
        assert result.overall_risk_level == RiskSeverity.HIGH

    @pytest.mark.asyncio
    async def test_analyze_no_chunks_raises(self, risk_detector):
        """Test analyzing document with no chunks raises error."""
        risk_detector.qdrant_service.client.scroll.return_value = ([], None)

        with pytest.raises(ValueError, match="No chunks found"):
            await risk_detector.analyze("nonexistent-doc")

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_errors(self, risk_detector, sample_chunks):
        """Test analyze handles individual LLM errors gracefully."""
        risk_detector.qdrant_service.client.scroll.return_value = (sample_chunks, None)

        call_count = [0]

        def mock_generate(prompt):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("LLM error")
            return LLMResponse(
                content="NO_RISKS_FOUND",
                model="test",
                total_tokens=10,
                finish_reason="stop",
            )

        risk_detector.llm.generate = mock_generate

        # Should not raise, should handle error gracefully
        result = await risk_detector.analyze("doc-123")

        assert isinstance(result, RiskAnalysisResult)


class TestLongDocuments:
    """Test handling of long documents."""

    @pytest.mark.asyncio
    async def test_max_chunks_limit(self, risk_detector):
        """Test long documents are limited to MAX_CHUNKS."""
        many_chunks = [
            MockPoint(
                payload={
                    "content": f"Chunk {i} content here.",
                    "page": i // 10,
                    "chunk_index": i,
                    "document_id": "doc-123",
                }
            )
            for i in range(60)
        ]

        risk_detector.qdrant_service.client.scroll.return_value = (many_chunks, None)
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        result = await risk_detector.analyze("doc-123")

        # Should process at most MAX_CHUNKS (50)
        # Each chunk calls generate once
        assert risk_detector.llm.generate.call_count == 50


class TestLanguageSupport:
    """Test multilingual support for risk detection."""

    @pytest.fixture
    def french_chunks(self):
        """Create French language chunks for testing."""
        return [
            MockPoint(
                payload={
                    "content": "Le prestataire s'engage à indemniser le client de tout préjudice.",
                    "page": 1,
                    "chunk_index": 0,
                    "document_id": "doc-fr",
                }
            ),
            MockPoint(
                payload={
                    "content": "Les pénalités de retard s'élèvent à 5% par mois de retard.",
                    "page": 2,
                    "chunk_index": 1,
                    "document_id": "doc-fr",
                }
            ),
        ]

    def test_result_includes_language_field(self):
        """Test RiskAnalysisResult includes language field."""
        result = RiskAnalysisResult(
            risks=[],
            overall_risk_level=RiskSeverity.LOW,
            summary="No risks",
            document_id="doc-123",
            language="fr",
        )
        assert result.language == "fr"

    def test_result_default_language_is_english(self):
        """Test RiskAnalysisResult defaults to English."""
        result = RiskAnalysisResult(
            risks=[],
            overall_risk_level=RiskSeverity.LOW,
            summary="No risks",
            document_id="doc-123",
        )
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_analyze_with_explicit_language(self, risk_detector, sample_chunks):
        """Test analysis with explicit language parameter."""
        risk_detector.qdrant_service.client.scroll.return_value = (sample_chunks, None)
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        result = await risk_detector.analyze("doc-123", language="fr")

        assert result.language == "fr"

    @pytest.mark.asyncio
    async def test_auto_detect_french_language(self, risk_detector, french_chunks):
        """Test language auto-detection from French chunks."""
        risk_detector.qdrant_service.client.scroll.return_value = (french_chunks, None)
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        result = await risk_detector.analyze("doc-fr")

        assert result.language == "fr"

    def test_french_summary_no_risks(self, risk_detector):
        """Test French summary when no risks found."""
        summary = risk_detector._generate_summary([], language="fr")
        assert "Aucun risque significatif" in summary

    def test_french_summary_with_risks(self, risk_detector):
        """Test French summary with risks."""
        risks = [
            Risk(
                category=RiskCategory.LEGAL_LIABILITY,
                severity=RiskSeverity.HIGH,
                description="Risque élevé",
                clause_excerpt="clause",
                page=1,
            ),
            Risk(
                category=RiskCategory.FINANCIAL_PENALTY,
                severity=RiskSeverity.MEDIUM,
                description="Risque moyen",
                clause_excerpt="clause",
                page=2,
            ),
        ]

        summary = risk_detector._generate_summary(risks, language="fr")

        assert "2 risques identifiés" in summary
        assert "1 élevé" in summary
        assert "1 moyen" in summary

    def test_detect_language_from_chunks(self, risk_detector, french_chunks):
        """Test language detection from chunks."""
        language = risk_detector._detect_language_from_chunks(french_chunks)
        assert language == "fr"

    def test_detect_language_empty_chunks(self, risk_detector):
        """Test language detection defaults to English for empty chunks."""
        language = risk_detector._detect_language_from_chunks([])
        assert language == "en"

    @pytest.mark.asyncio
    async def test_french_prompt_used(self, risk_detector, french_chunks):
        """Test French prompt is used when language is French."""
        risk_detector.qdrant_service.client.scroll.return_value = (french_chunks, None)
        risk_detector.llm.generate.return_value = LLMResponse(
            content="NO_RISKS_FOUND",
            model="test",
            total_tokens=10,
            finish_reason="stop",
        )

        await risk_detector.analyze("doc-fr", language="fr")

        # Verify French prompt was used (check for French keywords in call)
        call_args = risk_detector.llm.generate.call_args[0][0]
        assert "Analysez" in call_args or "EXTRAIT" in call_args
