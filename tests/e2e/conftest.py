"""Pytest fixtures for E2E tests."""
import asyncio
import os
import re
from pathlib import Path
from typing import AsyncGenerator

import pytest
import httpx

from src.api.main import app
from src.config import get_settings


# Service availability checking
def check_api_available() -> bool:
    """Check if API server is available."""
    try:
        # Use sync client for checking
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://localhost:8000/health")
            return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


def check_ollama_available() -> bool:
    """Check if Ollama service is available."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://localhost:11434/api/version")
            return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


def check_qdrant_available() -> bool:
    """Check if Qdrant service is available."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://localhost:6333/healthz")
            return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


# Pytest skip markers based on service availability
requires_api = pytest.mark.skipif(
    not check_api_available(),
    reason="API server not available at localhost:8000"
)

requires_ollama = pytest.mark.skipif(
    not check_ollama_available(),
    reason="Ollama not available at localhost:11434"
)

requires_qdrant = pytest.mark.skipif(
    not check_qdrant_available(),
    reason="Qdrant not available at localhost:6333"
)

requires_all_services = pytest.mark.skipif(
    not (check_api_available() and check_ollama_available() and check_qdrant_available()),
    reason="One or more services not available (API, Ollama, Qdrant)"
)


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_environment():
    """Configure environment for E2E tests."""
    # Set longer timeout for Ollama (CPU inference is slow)
    os.environ["LEXARD_LLM__TIMEOUT_SECONDS"] = "180"
    yield
    # Cleanup
    if "LEXARD_LLM__TIMEOUT_SECONDS" in os.environ:
        del os.environ["LEXARD_LLM__TIMEOUT_SECONDS"]


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture(scope="session")
def test_data_dir():
    """Get test data directory."""
    return Path(__file__).parent.parent.parent / "data" / "test"


@pytest.fixture(scope="session")
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API."""
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        timeout=120.0  # Long timeout for E2E tests
    ) as client:
        yield client


async def wait_for_upload_completion(
    client: httpx.AsyncClient,
    task_id: str,
    timeout: int = 120
) -> dict:
    """Wait for upload to complete by polling status.

    Args:
        client: HTTP client
        task_id: Upload task ID
        timeout: Maximum wait time in seconds

    Returns:
        Final status data with document ID

    Raises:
        TimeoutError: If upload doesn't complete in time
        RuntimeError: If upload fails
    """
    import time
    start = time.time()

    while time.time() - start < timeout:
        response = await client.get(f"/upload/status/{task_id}")
        data = response.json()

        if data["stage"] == "complete":
            return data
        elif data["stage"] == "failed":
            raise RuntimeError(f"Upload failed: {data.get('error')}")

        await asyncio.sleep(1)

    raise TimeoutError(f"Upload did not complete within {timeout}s")


async def upload_document(
    client: httpx.AsyncClient,
    file_path: Path
) -> str:
    """Upload a document and wait for completion.

    Args:
        client: HTTP client
        file_path: Path to document file

    Returns:
        Document ID

    Raises:
        AssertionError: If upload fails
    """
    # Determine MIME type based on file extension
    mime_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }
    mime_type = mime_types.get(file_path.suffix.lower(), "application/octet-stream")

    with open(file_path, "rb") as f:
        response = await client.post(
            "/upload",
            files={"file": (file_path.name, f, mime_type)}
        )

    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()

    # Wait for processing to complete
    task_id = data["task_id"]
    status_data = await wait_for_upload_completion(client, task_id)

    # Extract document ID from message
    match = re.search(r"Document ID: ([a-f0-9-]+)", status_data["message"])
    assert match, f"Could not extract document ID from message: {status_data['message']}"

    return match.group(1)


@pytest.fixture
async def sample_contract_en_pdf(api_client, test_data_dir):
    """Upload sample English contract (PDF) and return document ID."""
    file_path = test_data_dir / "contract_nda_en.pdf"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_en_docx(api_client, test_data_dir):
    """Upload sample English contract (DOCX) and return document ID."""
    file_path = test_data_dir / "contract_nda_en.docx"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_fr_pdf(api_client, test_data_dir):
    """Upload sample French contract (PDF) and return document ID."""
    file_path = test_data_dir / "contrat_nda_fr.pdf"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_fr_docx(api_client, test_data_dir):
    """Upload sample French contract (DOCX) and return document ID."""
    file_path = test_data_dir / "contrat_nda_fr.docx"
    return await upload_document(api_client, file_path)
