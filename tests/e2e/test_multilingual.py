"""End-to-end tests for multilingual support."""
import pytest

from tests.e2e.utils import (
    assert_query_response_valid,
    assert_summary_response_valid,
    contains_french_text,
)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_pdf_upload_and_query(api_client, sample_contract_fr_pdf):
    """Test French PDF document processing end-to-end."""
    doc_id = sample_contract_fr_pdf

    # Query in French
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "Quelle est la période de préavis de résiliation?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert_query_response_valid(data)

    # Response should be in French
    assert contains_french_text(data["answer"]), \
        "Response should be in French for French query"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_docx_upload_and_query(api_client, sample_contract_fr_docx):
    """Test French DOCX document processing end-to-end."""
    doc_id = sample_contract_fr_docx

    # Query in French
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "Quelles sont les conditions de paiement?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert_query_response_valid(data)

    # Response should contain French
    assert contains_french_text(data["answer"]), \
        "Response should be in French"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_summarization(api_client, sample_contract_fr_pdf):
    """Test French document summarization."""
    doc_id = sample_contract_fr_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive",
            "language": "fr"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_summary_response_valid(data)

    # Summary should be in French
    assert contains_french_text(data["summary"]), \
        "Summary should be in French"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_cross_language_quality_comparison(
    api_client,
    sample_contract_en_pdf,
    sample_contract_fr_pdf
):
    """Verify both English and French documents work with similar quality."""

    # English query
    en_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_en_pdf,
            "question": "What are the payment terms?"
        }
    )

    # French query
    fr_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_fr_pdf,
            "question": "Quelles sont les conditions de paiement?"
        }
    )

    # Both should succeed
    assert en_response.status_code == 200
    assert fr_response.status_code == 200

    en_data = en_response.json()
    fr_data = fr_response.json()

    # Both should have valid responses
    assert_query_response_valid(en_data)
    assert_query_response_valid(fr_data)

    # Both should have citations
    assert len(en_data["citation_chunks"]) > 0
    assert len(fr_data["citation_chunks"]) > 0

    # Both should have reasonable confidence
    assert en_data["confidence"] in ["medium", "high"], \
        "English query should have medium/high confidence"
    assert fr_data["confidence"] in ["medium", "high"], \
        "French query should have medium/high confidence"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_french_citation_quality(api_client, sample_contract_fr_pdf):
    """Test that French document citations are relevant and above threshold."""
    doc_id = sample_contract_fr_pdf

    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "Quelles sont les obligations principales?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # All citations should meet threshold
    for citation in data["citation_chunks"]:
        assert citation["score"] >= 0.7, \
            f"French citation score {citation['score']} below threshold"

        # Citations should have substantial content
        assert len(citation["content"]) > 50, \
            "Citation content too short"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_mixed_language_documents(
    api_client,
    sample_contract_en_pdf,
    sample_contract_fr_pdf
):
    """Test querying different language documents in same session."""

    # Query English document in English
    en_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_en_pdf,
            "question": "What is the termination notice period?"
        }
    )

    # Query French document in French
    fr_response = await api_client.post(
        "/query",
        json={
            "document_id": sample_contract_fr_pdf,
            "question": "Quelle est la période de préavis?"
        }
    )

    # Both should succeed independently
    assert en_response.status_code == 200
    assert fr_response.status_code == 200

    # Both should have valid responses
    assert_query_response_valid(en_response.json())
    assert_query_response_valid(fr_response.json())


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_automatic_language_detection(api_client, sample_contract_fr_pdf):
    """Test that system detects French document and responds appropriately."""
    doc_id = sample_contract_fr_pdf

    # Query in French - system should detect and respond in French
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "Résumez les principales clauses."
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_query_response_valid(data)

    # Response should be in French based on query language
    assert contains_french_text(data["answer"]), \
        "System should respond in French for French query"
