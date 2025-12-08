"""End-to-end tests for document comparison."""
import pytest

from tests.e2e.utils import assert_comparison_response_valid


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_two_english_documents(
    api_client,
    sample_contract_en_pdf,
    sample_contract_en_docx
):
    """Test comparing two English documents (PDF vs DOCX)."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": sample_contract_en_docx
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_comparison_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_english_and_french_documents(
    api_client,
    sample_contract_en_pdf,
    sample_contract_fr_pdf
):
    """Test comparing English and French documents."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": sample_contract_fr_pdf
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_comparison_response_valid(data)

    # Should identify differences (different language is a difference)
    assert isinstance(data["differences"], list)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_two_french_documents(
    api_client,
    sample_contract_fr_pdf,
    sample_contract_fr_docx
):
    """Test comparing two French documents (PDF vs DOCX)."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_fr_pdf,
            "doc_b": sample_contract_fr_docx
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_comparison_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_comparison_difference_details(
    api_client,
    sample_contract_en_pdf,
    sample_contract_fr_pdf
):
    """Test that comparison provides detailed difference information."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": sample_contract_fr_pdf
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Each difference should have meaningful information
    for diff in data["differences"]:
        assert "section" in diff, "Difference missing section"
        assert "change_type" in diff, "Difference missing change_type"
        assert "similarity" in diff, "Difference missing similarity"

        # Section should be non-empty
        assert len(diff["section"]) > 0, "Section cannot be empty"
        # Change type should be valid
        assert diff["change_type"] in ["added", "removed", "modified"], \
            f"Invalid change_type: {diff['change_type']}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_same_document(api_client, sample_contract_en_pdf):
    """Test comparing a document with itself."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": sample_contract_en_pdf
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_comparison_response_valid(data)

    # Comparing same document should show minimal or no differences
    # (implementation may vary - some systems might show "identical")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_comparison_invalid_document_id(api_client, sample_contract_en_pdf):
    """Test comparison with invalid document ID."""
    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": "00000000-0000-0000-0000-000000000000"
        }
    )

    # Should return error (404, 400, or 422)
    assert response.status_code in [400, 404, 422], \
        f"Expected error status, got {response.status_code}"

    data = response.json()
    # Error response can be in various formats
    assert "error" in data or "detail" in data or "message" in data, \
        f"Expected error response, got: {data}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_multi_document_comparison_workflow(
    api_client,
    sample_contract_en_pdf,
    sample_contract_en_docx,
    sample_contract_fr_pdf
):
    """Test comparing multiple document pairs."""

    comparisons = [
        (sample_contract_en_pdf, sample_contract_en_docx),
        (sample_contract_en_pdf, sample_contract_fr_pdf),
        (sample_contract_en_docx, sample_contract_fr_pdf),
    ]

    for doc1, doc2 in comparisons:
        response = await api_client.post(
            "/compare",
            json={
                "doc_a": doc1,
                "doc_b": doc2
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_comparison_response_valid(data)
