"""End-to-end tests for document upload and query."""
import pytest

from tests.e2e.utils import (
    assert_query_response_valid,
    assert_summary_response_valid,
)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_query_english_pdf(api_client, sample_contract_en_pdf):
    """Test complete workflow: upload English PDF document and query it."""
    doc_id = sample_contract_en_pdf

    # Query the document
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "What is the termination notice period?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Validate response structure and content
    assert_query_response_valid(data)

    # Verify answer is substantial
    assert len(data["answer"]) > 20, "Answer too short"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_query_english_docx(api_client, sample_contract_en_docx):
    """Test complete workflow: upload English DOCX document and query it."""
    doc_id = sample_contract_en_docx

    # Query the document
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "What are the payment terms?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Validate response structure and content
    assert_query_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_summarize_pdf(api_client, sample_contract_en_pdf):
    """Test document summarization for PDF."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "executive"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_summary_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_and_summarize_docx(api_client, sample_contract_en_docx):
    """Test document summarization for DOCX."""
    doc_id = sample_contract_en_docx

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "detailed"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert_summary_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_multiple_queries_same_document(api_client, sample_contract_en_pdf):
    """Test multiple queries on the same document."""
    doc_id = sample_contract_en_pdf

    questions = [
        "What is the termination notice period?",
        "What are the payment terms?",
        "Who are the parties to this contract?",
    ]

    for question in questions:
        response = await api_client.post(
            "/query",
            json={
                "document_id": doc_id,
                "question": question
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_query_response_valid(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_query_confidence_levels(api_client, sample_contract_en_pdf):
    """Test that confidence levels are assigned appropriately."""
    doc_id = sample_contract_en_pdf

    # Query about contract topic
    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "What is mentioned about termination?"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert_query_response_valid(data)

    # Should return a valid confidence level
    # Note: Confidence can vary based on LLM response and chunk retrieval
    assert data["confidence"] in ["low", "medium", "high"], \
        f"Invalid confidence level: {data['confidence']}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_citation_quality(api_client, sample_contract_en_pdf):
    """Test that citations are relevant and above threshold."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": "What are the key obligations?"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # All citations should have score >= 0.7
    for citation in data["citation_chunks"]:
        assert citation["score"] >= 0.7, \
            f"Citation score {citation['score']} below threshold"

        # Citations should have substantial content
        assert len(citation["content"]) > 50, \
            "Citation content too short"

        # Page numbers should be valid
        assert citation["page"] >= 1, "Invalid page number"
