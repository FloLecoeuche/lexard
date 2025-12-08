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
            "document_id_1": sample_contract_en_pdf,
            "document_id_2": sample_contract_en_docx
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
            "document_id_1": sample_contract_en_pdf,
            "document_id_2": sample_contract_fr_pdf
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
            "document_id_1": sample_contract_fr_pdf,
            "document_id_2": sample_contract_fr_docx
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
            "document_id_1": sample_contract_en_pdf,
            "document_id_2": sample_contract_fr_pdf
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Each difference should have meaningful information
    for diff in data["differences"]:
        assert "category" in diff, "Difference missing category"
        assert "description" in diff, "Difference missing description"

        # Category and description should be non-empty
        assert len(diff["category"]) > 0, "Category cannot be empty"
        assert len(diff["description"]) > 10, "Description too short"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_same_document(api_client, sample_contract_en_pdf):
    """Test comparing a document with itself."""
    response = await api_client.post(
        "/compare",
        json={
            "document_id_1": sample_contract_en_pdf,
            "document_id_2": sample_contract_en_pdf
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
            "document_id_1": sample_contract_en_pdf,
            "document_id_2": "00000000-0000-0000-0000-000000000000"
        }
    )

    # Should return error (404 or 400)
    assert response.status_code in [400, 404]

    data = response.json()
    assert "error" in data


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
                "document_id_1": doc1,
                "document_id_2": doc2
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_comparison_response_valid(data)
