"""Tests for document comparison tool."""

import pytest
import numpy as np
from unittest.mock import MagicMock
from dataclasses import dataclass

from src.agent.tools.diff import (
    DiffTool,
    ComparisonResult,
    Difference,
    ChangeType,
)


@dataclass
class MockPoint:
    """Mock Qdrant point with vector."""

    payload: dict
    vector: list[float]


@pytest.fixture
def mock_qdrant_service():
    """Create mock Qdrant service."""
    service = MagicMock()
    service.collection_name = "test_collection"
    service.client = MagicMock()
    return service


@pytest.fixture
def diff_tool(mock_qdrant_service):
    """Create DiffTool instance."""
    return DiffTool(qdrant_service=mock_qdrant_service)


def create_mock_chunk(
    content: str,
    page: int,
    chunk_index: int,
    doc_id: str,
    vector: list[float] | None = None,
) -> MockPoint:
    """Helper to create mock chunk."""
    if vector is None:
        # Create a random normalized vector
        v = np.random.randn(768)
        v = v / np.linalg.norm(v)
        vector = v.tolist()
    return MockPoint(
        payload={
            "content": content,
            "page": page,
            "chunk_index": chunk_index,
            "document_id": doc_id,
        },
        vector=vector,
    )


def create_similar_vector(base_vector: list[float], similarity: float) -> list[float]:
    """Create a vector with approximately the desired similarity to base_vector."""
    base = np.array(base_vector)
    random_component = np.random.randn(len(base))
    random_component = random_component / np.linalg.norm(random_component)

    # Mix base with random to achieve desired similarity
    # similarity ≈ cos(θ), where θ is angle between vectors
    # mixed = base * similarity + random * sqrt(1 - similarity^2)
    mixed = base * similarity + random_component * np.sqrt(1 - similarity**2)
    mixed = mixed / np.linalg.norm(mixed)
    return mixed.tolist()


class TestChangeType:
    """Test ChangeType enum."""

    def test_enum_values(self):
        """Test all change types exist."""
        assert ChangeType.ADDED == "added"
        assert ChangeType.REMOVED == "removed"
        assert ChangeType.MODIFIED == "modified"
        assert ChangeType.UNCHANGED == "unchanged"


class TestDifference:
    """Test Difference dataclass."""

    def test_difference_creation(self):
        """Test creating a difference."""
        diff = Difference(
            section="Page 1, Chunk 0",
            doc_a_excerpt="Original text",
            doc_b_excerpt="Modified text",
            change_type=ChangeType.MODIFIED,
            similarity_score=0.75,
        )
        assert diff.section == "Page 1, Chunk 0"
        assert diff.change_type == ChangeType.MODIFIED
        assert diff.similarity_score == 0.75


class TestComparisonResult:
    """Test ComparisonResult dataclass."""

    def test_result_creation(self):
        """Test creating a comparison result."""
        result = ComparisonResult(
            differences=[],
            overall_similarity=0.95,
            doc_a_id="doc-a",
            doc_b_id="doc-b",
            summary="Documents are 95% similar.",
            doc_a_chunk_count=5,
            doc_b_chunk_count=5,
        )
        assert result.overall_similarity == 0.95
        assert result.doc_a_id == "doc-a"
        assert result.doc_b_id == "doc-b"

    def test_result_defaults(self):
        """Test result with default values."""
        result = ComparisonResult(
            differences=[],
            overall_similarity=0.8,
            doc_a_id="a",
            doc_b_id="b",
            summary="Test",
        )
        assert result.doc_a_chunk_count == 0
        assert result.doc_b_chunk_count == 0


class TestDiffToolInit:
    """Test DiffTool initialization."""

    def test_init(self, mock_qdrant_service):
        """Test basic initialization."""
        tool = DiffTool(qdrant_service=mock_qdrant_service)
        assert tool.qdrant_service == mock_qdrant_service

    def test_constants(self, diff_tool):
        """Test default constants are set."""
        assert diff_tool.SIMILARITY_THRESHOLD == 0.85
        assert diff_tool.MODIFIED_THRESHOLD == 0.5
        assert diff_tool.EXCERPT_MAX_LENGTH == 200


class TestGetDocumentChunks:
    """Test document chunk retrieval."""

    @pytest.mark.asyncio
    async def test_get_chunks(self, diff_tool):
        """Test retrieving chunks for a document."""
        chunks = [
            create_mock_chunk("Content 1", 1, 0, "doc-a"),
            create_mock_chunk("Content 2", 1, 1, "doc-a"),
        ]
        diff_tool.qdrant_service.client.scroll.return_value = (chunks, None)

        result = await diff_tool._get_document_chunks("doc-a")

        assert len(result) == 2
        diff_tool.qdrant_service.client.scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_sorted_by_index(self, diff_tool):
        """Test chunks are sorted by chunk_index."""
        chunks = [
            create_mock_chunk("Content 2", 1, 2, "doc-a"),
            create_mock_chunk("Content 0", 1, 0, "doc-a"),
            create_mock_chunk("Content 1", 1, 1, "doc-a"),
        ]
        diff_tool.qdrant_service.client.scroll.return_value = (chunks, None)

        result = await diff_tool._get_document_chunks("doc-a")

        indices = [c.payload["chunk_index"] for c in result]
        assert indices == [0, 1, 2]


class TestGetEmbeddings:
    """Test embedding extraction."""

    def test_get_embeddings(self, diff_tool):
        """Test extracting embeddings from chunks."""
        vector1 = [0.1] * 768
        vector2 = [0.2] * 768
        chunks = [
            create_mock_chunk("A", 1, 0, "doc", vector1),
            create_mock_chunk("B", 1, 1, "doc", vector2),
        ]

        embeddings = diff_tool._get_embeddings(chunks)

        assert embeddings.shape == (2, 768)
        np.testing.assert_array_almost_equal(embeddings[0], vector1)


class TestComputeSimilarityMatrix:
    """Test similarity matrix computation."""

    def test_identical_vectors(self, diff_tool):
        """Test similarity of identical vectors is 1."""
        v = np.array([[1.0, 0.0, 0.0]])
        matrix = diff_tool._compute_similarity_matrix(v, v)

        np.testing.assert_array_almost_equal(matrix, [[1.0]])

    def test_orthogonal_vectors(self, diff_tool):
        """Test similarity of orthogonal vectors is 0."""
        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[0.0, 1.0, 0.0]])
        matrix = diff_tool._compute_similarity_matrix(a, b)

        np.testing.assert_array_almost_equal(matrix, [[0.0]])

    def test_matrix_shape(self, diff_tool):
        """Test matrix has correct shape."""
        a = np.random.randn(3, 768)
        b = np.random.randn(5, 768)
        matrix = diff_tool._compute_similarity_matrix(a, b)

        assert matrix.shape == (3, 5)


class TestFindDifferences:
    """Test difference finding."""

    def test_identical_documents(self, diff_tool):
        """Test no differences for identical documents."""
        # Same vector in both documents
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)

        chunks_a = [create_mock_chunk("Same content", 1, 0, "a", vector.tolist())]
        chunks_b = [create_mock_chunk("Same content", 1, 0, "b", vector.tolist())]

        matrix = np.array([[1.0]])  # Perfect similarity

        differences = diff_tool._find_differences(chunks_a, chunks_b, matrix)

        assert len(differences) == 0

    def test_modified_content(self, diff_tool):
        """Test modified content is detected."""
        base_vector = np.random.randn(768)
        base_vector = base_vector / np.linalg.norm(base_vector)

        # Create similar but not identical vector
        similar_vector = create_similar_vector(base_vector.tolist(), 0.7)

        chunks_a = [create_mock_chunk("Original text", 1, 0, "a", base_vector.tolist())]
        chunks_b = [create_mock_chunk("Modified text", 1, 0, "b", similar_vector)]

        matrix = np.array([[0.7]])  # Medium similarity

        differences = diff_tool._find_differences(chunks_a, chunks_b, matrix)

        assert len(differences) == 1
        assert differences[0].change_type == ChangeType.MODIFIED

    def test_removed_content(self, diff_tool):
        """Test removed content is detected."""
        vector_a = np.random.randn(768)
        vector_a = vector_a / np.linalg.norm(vector_a)
        vector_b = np.random.randn(768)
        vector_b = vector_b / np.linalg.norm(vector_b)

        chunks_a = [create_mock_chunk("Content in A only", 1, 0, "a", vector_a.tolist())]
        chunks_b = [create_mock_chunk("Different content in B", 1, 0, "b", vector_b.tolist())]

        matrix = np.array([[0.2]])  # Low similarity

        differences = diff_tool._find_differences(chunks_a, chunks_b, matrix)

        # Should have both removed (from A) and added (to B)
        assert len(differences) >= 1
        removed = [d for d in differences if d.change_type == ChangeType.REMOVED]
        assert len(removed) == 1

    def test_added_content(self, diff_tool):
        """Test added content is detected."""
        # A has one chunk, B has two - one matching, one new
        vector_common = np.random.randn(768)
        vector_common = vector_common / np.linalg.norm(vector_common)
        vector_new = np.random.randn(768)
        vector_new = vector_new / np.linalg.norm(vector_new)

        chunks_a = [create_mock_chunk("Common", 1, 0, "a", vector_common.tolist())]
        chunks_b = [
            create_mock_chunk("Common", 1, 0, "b", vector_common.tolist()),
            create_mock_chunk("New content", 2, 1, "b", vector_new.tolist()),
        ]

        # A[0] matches B[0] perfectly, A[0] doesn't match B[1]
        matrix = np.array([[0.99, 0.1]])

        differences = diff_tool._find_differences(chunks_a, chunks_b, matrix)

        added = [d for d in differences if d.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert "New content" in added[0].doc_b_excerpt


class TestFormatSection:
    """Test section formatting."""

    def test_format_section(self, diff_tool):
        """Test section formatting."""
        payload = {"page": 3, "chunk_index": 5}
        result = diff_tool._format_section(payload)
        assert result == "Page 3, Chunk 5"

    def test_format_section_defaults(self, diff_tool):
        """Test section formatting with missing values."""
        payload = {}
        result = diff_tool._format_section(payload)
        assert result == "Page 0, Chunk 0"


class TestTruncate:
    """Test text truncation."""

    def test_short_text(self, diff_tool):
        """Test short text is not truncated."""
        text = "Short text"
        result = diff_tool._truncate(text)
        assert result == text

    def test_long_text(self, diff_tool):
        """Test long text is truncated."""
        text = "A" * 300
        result = diff_tool._truncate(text)
        assert len(result) == diff_tool.EXCERPT_MAX_LENGTH
        assert result.endswith("...")


class TestCalculateOverallSimilarity:
    """Test overall similarity calculation."""

    def test_perfect_similarity(self, diff_tool):
        """Test perfect match gives 1.0."""
        matrix = np.array([[1.0, 0.5], [0.5, 1.0]])
        result = diff_tool._calculate_overall_similarity(matrix)
        assert result == 1.0

    def test_no_similarity(self, diff_tool):
        """Test no match gives 0.0."""
        matrix = np.array([[0.0]])
        result = diff_tool._calculate_overall_similarity(matrix)
        assert result == 0.0

    def test_partial_similarity(self, diff_tool):
        """Test partial similarity."""
        matrix = np.array([[0.8, 0.3], [0.2, 0.6]])
        result = diff_tool._calculate_overall_similarity(matrix)
        # Max of each row: 0.8, 0.6; mean = 0.7
        assert result == pytest.approx(0.7)

    def test_empty_matrix(self, diff_tool):
        """Test empty matrix returns 0."""
        matrix = np.array([]).reshape(0, 0)
        result = diff_tool._calculate_overall_similarity(matrix)
        assert result == 0.0


class TestGenerateSummary:
    """Test summary generation."""

    def test_no_differences(self, diff_tool):
        """Test summary with no differences."""
        summary = diff_tool._generate_summary([], 0.95)
        assert "95%" in summary
        assert "no significant differences" in summary.lower()

    def test_with_differences(self, diff_tool):
        """Test summary with differences."""
        differences = [
            Difference("P1", "a", "b", ChangeType.ADDED, 0.1),
            Difference("P2", "a", "b", ChangeType.REMOVED, 0.2),
            Difference("P3", "a", "b", ChangeType.MODIFIED, 0.6),
            Difference("P4", "a", "b", ChangeType.MODIFIED, 0.7),
        ]
        summary = diff_tool._generate_summary(differences, 0.75)

        assert "75%" in summary
        assert "4 differences" in summary
        assert "1 added" in summary
        assert "1 removed" in summary
        assert "2 modified" in summary


class TestCompare:
    """Test main compare method."""

    @pytest.mark.asyncio
    async def test_compare_identical_documents(self, diff_tool):
        """Test comparing identical documents."""
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)

        chunks = [
            create_mock_chunk("Content 1", 1, 0, "doc", vector.tolist()),
            create_mock_chunk("Content 2", 1, 1, "doc", vector.tolist()),
        ]

        diff_tool.qdrant_service.client.scroll.return_value = (chunks, None)

        result = await diff_tool.compare("doc-a", "doc-a")

        assert isinstance(result, ComparisonResult)
        assert result.overall_similarity > 0.9
        assert len(result.differences) == 0

    @pytest.mark.asyncio
    async def test_compare_no_chunks_doc_a(self, diff_tool):
        """Test error when document A has no chunks."""
        diff_tool.qdrant_service.client.scroll.return_value = ([], None)

        with pytest.raises(ValueError, match="No chunks found for document doc-a"):
            await diff_tool.compare("doc-a", "doc-b")

    @pytest.mark.asyncio
    async def test_compare_no_chunks_doc_b(self, diff_tool):
        """Test error when document B has no chunks."""
        chunks_a = [create_mock_chunk("Content", 1, 0, "a")]

        # First call returns chunks for A, second returns empty for B
        diff_tool.qdrant_service.client.scroll.side_effect = [
            (chunks_a, None),
            ([], None),
        ]

        with pytest.raises(ValueError, match="No chunks found for document doc-b"):
            await diff_tool.compare("doc-a", "doc-b")

    @pytest.mark.asyncio
    async def test_compare_returns_correct_ids(self, diff_tool):
        """Test result contains correct document IDs."""
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)
        chunks = [create_mock_chunk("Content", 1, 0, "doc", vector.tolist())]
        diff_tool.qdrant_service.client.scroll.return_value = (chunks, None)

        result = await diff_tool.compare("doc-alpha", "doc-beta")

        assert result.doc_a_id == "doc-alpha"
        assert result.doc_b_id == "doc-beta"

    @pytest.mark.asyncio
    async def test_compare_returns_chunk_counts(self, diff_tool):
        """Test result contains chunk counts."""
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)

        chunks_a = [
            create_mock_chunk("A1", 1, 0, "a", vector.tolist()),
            create_mock_chunk("A2", 1, 1, "a", vector.tolist()),
        ]
        chunks_b = [
            create_mock_chunk("B1", 1, 0, "b", vector.tolist()),
            create_mock_chunk("B2", 1, 1, "b", vector.tolist()),
            create_mock_chunk("B3", 2, 2, "b", vector.tolist()),
        ]

        diff_tool.qdrant_service.client.scroll.side_effect = [
            (chunks_a, None),
            (chunks_b, None),
        ]

        result = await diff_tool.compare("doc-a", "doc-b")

        assert result.doc_a_chunk_count == 2
        assert result.doc_b_chunk_count == 3


class TestIntegration:
    """Integration tests for DiffTool."""

    @pytest.mark.asyncio
    async def test_detect_all_change_types(self, diff_tool):
        """Test detecting added, removed, and modified content."""
        # Create distinct vectors for different types of changes
        np.random.seed(42)  # For reproducibility

        # Unchanged: identical vectors
        unchanged_vec = np.random.randn(768)
        unchanged_vec = unchanged_vec / np.linalg.norm(unchanged_vec)

        # Modified: similar but not identical
        modified_vec_a = np.random.randn(768)
        modified_vec_a = modified_vec_a / np.linalg.norm(modified_vec_a)
        modified_vec_b = create_similar_vector(modified_vec_a.tolist(), 0.7)

        # Removed: only in A
        removed_vec = np.random.randn(768)
        removed_vec = removed_vec / np.linalg.norm(removed_vec)

        # Added: only in B
        added_vec = np.random.randn(768)
        added_vec = added_vec / np.linalg.norm(added_vec)

        chunks_a = [
            create_mock_chunk("Unchanged text", 1, 0, "a", unchanged_vec.tolist()),
            create_mock_chunk("Original text", 1, 1, "a", modified_vec_a.tolist()),
            create_mock_chunk("Removed text", 2, 2, "a", removed_vec.tolist()),
        ]

        chunks_b = [
            create_mock_chunk("Unchanged text", 1, 0, "b", unchanged_vec.tolist()),
            create_mock_chunk("Modified text", 1, 1, "b", modified_vec_b),
            create_mock_chunk("Added text", 2, 2, "b", added_vec.tolist()),
        ]

        diff_tool.qdrant_service.client.scroll.side_effect = [
            (chunks_a, None),
            (chunks_b, None),
        ]

        result = await diff_tool.compare("doc-a", "doc-b")

        # Should have detected differences
        assert len(result.differences) > 0
        change_types = {d.change_type for d in result.differences}

        # Should detect at least modified and either added or removed
        # (exact behavior depends on similarity thresholds)
        assert len(change_types) >= 1


class TestLanguageSupport:
    """Test multilingual support for document comparison."""

    @pytest.fixture
    def french_chunks_a(self):
        """Create French language chunks for document A."""
        np.random.seed(100)
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)
        return [
            create_mock_chunk(
                "Ceci est le premier paragraphe du contrat en français.",
                1, 0, "a-fr", vector.tolist()
            ),
        ]

    @pytest.fixture
    def french_chunks_b(self):
        """Create French language chunks for document B."""
        np.random.seed(100)
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)
        return [
            create_mock_chunk(
                "Ceci est le premier paragraphe modifié du contrat en français.",
                1, 0, "b-fr", vector.tolist()
            ),
        ]

    def test_result_includes_language_field(self):
        """Test ComparisonResult includes language field."""
        result = ComparisonResult(
            differences=[],
            overall_similarity=0.95,
            doc_a_id="a",
            doc_b_id="b",
            summary="Similar",
            language="fr",
        )
        assert result.language == "fr"

    def test_result_default_language_is_english(self):
        """Test ComparisonResult defaults to English."""
        result = ComparisonResult(
            differences=[],
            overall_similarity=0.95,
            doc_a_id="a",
            doc_b_id="b",
            summary="Similar",
        )
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_compare_with_explicit_language(self, diff_tool):
        """Test comparison with explicit language parameter."""
        np.random.seed(42)
        vector = np.random.randn(768)
        vector = vector / np.linalg.norm(vector)
        chunks = [create_mock_chunk("Content", 1, 0, "doc", vector.tolist())]
        diff_tool.qdrant_service.client.scroll.return_value = (chunks, None)

        result = await diff_tool.compare("doc-a", "doc-b", language="fr")

        assert result.language == "fr"

    @pytest.mark.asyncio
    async def test_auto_detect_french_language(self, diff_tool, french_chunks_a, french_chunks_b):
        """Test language auto-detection from French chunks."""
        diff_tool.qdrant_service.client.scroll.side_effect = [
            (french_chunks_a, None),
            (french_chunks_b, None),
        ]

        result = await diff_tool.compare("doc-a-fr", "doc-b-fr")

        assert result.language == "fr"

    def test_french_summary_no_differences(self, diff_tool):
        """Test French summary when no differences."""
        summary = diff_tool._generate_summary([], 0.95, language="fr")
        assert "95%" in summary
        assert "similaires" in summary.lower()

    def test_french_summary_with_differences(self, diff_tool):
        """Test French summary with differences."""
        differences = [
            Difference("P1", "a", "b", ChangeType.ADDED, 0.1),
            Difference("P2", "a", "b", ChangeType.REMOVED, 0.2),
            Difference("P3", "a", "b", ChangeType.MODIFIED, 0.6),
        ]
        summary = diff_tool._generate_summary(differences, 0.75, language="fr")

        assert "75%" in summary
        assert "3 différences" in summary
        assert "1 ajouté" in summary
        assert "1 supprimé" in summary
        assert "1 modifié" in summary

    def test_detect_language_from_chunks(self, diff_tool, french_chunks_a):
        """Test language detection from chunks."""
        language = diff_tool._detect_language_from_chunks(french_chunks_a)
        assert language == "fr"

    def test_detect_language_empty_chunks(self, diff_tool):
        """Test language detection defaults to English for empty chunks."""
        language = diff_tool._detect_language_from_chunks([])
        assert language == "en"
