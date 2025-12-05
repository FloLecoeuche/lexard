"""Pytest fixtures for E2E tests."""
import asyncio
import re
from pathlib import Path
from typing import AsyncGenerator

import pytest
import httpx

from src.api.main import app
from src.config import get_settings


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
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="session")
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API."""
    async with httpx.AsyncClient(
        app=app,
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
    with open(file_path, "rb") as f:
        response = await client.post(
            "/upload",
            files={"file": (file_path.name, f, "application/pdf" if file_path.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
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
    file_path = test_data_dir / "sample_contract_en.pdf"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_en_docx(api_client, test_data_dir):
    """Upload sample English contract (DOCX) and return document ID."""
    file_path = test_data_dir / "sample_contract_en.docx"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_fr_pdf(api_client, test_data_dir):
    """Upload sample French contract (PDF) and return document ID."""
    file_path = test_data_dir / "sample_contract_fr.pdf"
    return await upload_document(api_client, file_path)


@pytest.fixture
async def sample_contract_fr_docx(api_client, test_data_dir):
    """Upload sample French contract (DOCX) and return document ID."""
    file_path = test_data_dir / "sample_contract_fr.docx"
    return await upload_document(api_client, file_path)
