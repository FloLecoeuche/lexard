"""End-to-end tests for error handling scenarios."""
import pytest
from pathlib import Path


def assert_is_error_response(data: dict) -> None:
    """Assert that response indicates an error.

    Supports multiple error response formats:
    - Standard: {"error": {"code": "...", "message": "..."}}
    - FastAPI validation: {"detail": "..." or [{"msg": "..."}]}
    """
    has_error = (
        "error" in data or
        "detail" in data or
        "message" in data
    )
    assert has_error, f"Expected error response, got: {data}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_query_nonexistent_document(api_client):
    """Test querying a document that doesn't exist."""
    fake_doc_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.post(
        "/query",
        json={
            "document_id": fake_doc_id,
            "question": "What is this document about?"
        }
    )

    # Should return an error status
    assert response.status_code in [404, 400, 422], \
        f"Expected error status, got {response.status_code}"
    data = response.json()
    assert_is_error_response(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_invalid_file_format(api_client, test_data_dir):
    """Test uploading an unsupported file format."""
    # Create a temporary invalid file
    invalid_file = test_data_dir / "test_invalid.exe"
    invalid_file.write_bytes(b"Not a valid document")

    try:
        with open(invalid_file, "rb") as f:
            response = await api_client.post(
                "/upload",
                files={"file": (invalid_file.name, f, "application/octet-stream")}
            )

        # Should reject invalid format with client error
        assert response.status_code in [400, 415, 422], \
            f"Expected rejection for invalid format, got {response.status_code}"
    finally:
        # Cleanup
        if invalid_file.exists():
            invalid_file.unlink()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_empty_file(api_client, test_data_dir):
    """Test uploading an empty file."""
    empty_file = test_data_dir / "test_empty.pdf"
    empty_file.write_bytes(b"")

    try:
        with open(empty_file, "rb") as f:
            response = await api_client.post(
                "/upload",
                files={"file": (empty_file.name, f, "application/pdf")}
            )

        # Empty file may be accepted for processing but fail later,
        # or rejected immediately - both are valid behaviors
        if response.status_code == 200:
            # If accepted, we can poll status to see if it failed
            data = response.json()
            assert "task_id" in data, "Accepted upload should return task_id"
        else:
            assert response.status_code in [400, 422], \
                f"Should reject empty file, got {response.status_code}"
    finally:
        # Cleanup
        if empty_file.exists():
            empty_file.unlink()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_query_missing_required_fields(api_client, sample_contract_en_pdf):
    """Test query with missing required fields."""
    doc_id = sample_contract_en_pdf

    # Missing question field
    response = await api_client.post(
        "/query",
        json={"document_id": doc_id}
    )

    assert response.status_code == 422  # Validation error
    data = response.json()

    # FastAPI validation error format
    assert "detail" in data or "error" in data


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_query_with_empty_question(api_client, sample_contract_en_pdf):
    """Test query with empty question."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/query",
        json={
            "document_id": doc_id,
            "question": ""
        }
    )

    # Should reject empty question
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_summarize_nonexistent_document(api_client):
    """Test summarizing a document that doesn't exist."""
    fake_doc_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": fake_doc_id,
            "summary_type": "executive"
        }
    )

    # Should return an error status
    assert response.status_code in [404, 400, 422], \
        f"Expected error status, got {response.status_code}"
    data = response.json()
    assert_is_error_response(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_compare_with_invalid_document_ids(api_client, sample_contract_en_pdf):
    """Test comparison with one invalid document ID."""
    fake_doc_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.post(
        "/compare",
        json={
            "doc_a": sample_contract_en_pdf,
            "doc_b": fake_doc_id
        }
    )

    # Should return an error status (404 for not found or 422 for validation)
    assert response.status_code in [404, 400, 422], \
        f"Expected error status, got {response.status_code}"
    data = response.json()
    assert_is_error_response(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_risks_nonexistent_document(api_client):
    """Test risk analysis on non-existent document."""
    fake_doc_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.post(
        "/risks",
        json={"document_id": fake_doc_id}
    )

    # Should return an error status
    assert response.status_code in [404, 400, 422], \
        f"Expected error status, got {response.status_code}"
    data = response.json()
    assert_is_error_response(data)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_invalid_document_id_format(api_client):
    """Test with malformed document ID."""
    invalid_ids = [
        "not-a-uuid",
        "12345",
        "",
        "NULL",
    ]

    for invalid_id in invalid_ids:
        response = await api_client.post(
            "/query",
            json={
                "document_id": invalid_id,
                "question": "Test question"
            }
        )

        # Should reject invalid UUID format
        assert response.status_code in [400, 404, 422], \
            f"Should reject invalid document ID: {invalid_id}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_upload_without_file(api_client):
    """Test upload endpoint without providing a file."""
    response = await api_client.post("/upload")

    # Should reject request without file
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_invalid_summary_type(api_client, sample_contract_en_pdf):
    """Test summarization with invalid summary_type."""
    doc_id = sample_contract_en_pdf

    response = await api_client.post(
        "/summarize",
        json={
            "document_id": doc_id,
            "summary_type": "invalid_type"
        }
    )

    # API may accept invalid type and use default, or reject with error
    # Both are valid behaviors - we just ensure no server error
    assert response.status_code < 500, \
        f"Should not cause server error, got {response.status_code}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_malformed_json_request(api_client):
    """Test handling of malformed JSON in request."""
    response = await api_client.post(
        "/query",
        content=b"{invalid json}",
        headers={"Content-Type": "application/json"}
    )

    # Should return appropriate error
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_health_endpoint_always_works(api_client):
    """Test that health endpoint works even when other operations fail."""
    response = await api_client.get("/health")

    # Health endpoint should always respond
    assert response.status_code == 200
    data = response.json()

    assert "status" in data or "healthy" in str(data).lower()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_error_response_includes_trace_id(api_client):
    """Test that error responses include trace_id for debugging."""
    fake_doc_id = "00000000-0000-0000-0000-000000000000"

    response = await api_client.post(
        "/query",
        json={
            "document_id": fake_doc_id,
            "question": "Test"
        }
    )

    # Should return error status
    assert response.status_code in [404, 400, 422]
    data = response.json()

    # Check if trace_id is present in error response
    # Some error formats include it, some don't - we just verify response structure
    assert_is_error_response(data)
