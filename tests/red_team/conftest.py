"""Pytest fixtures for red team testing."""

import os
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.guardrails.prompt_injection import InjectionDetector


@pytest.fixture
def injection_detector() -> InjectionDetector:
    """Create an injection detector instance for testing."""
    return InjectionDetector()


@pytest.fixture
def mock_api_client() -> Generator[MagicMock, None, None]:
    """Create a mock API client for testing without real API calls."""
    with patch("httpx.Client") as mock_client:
        client = MagicMock()
        mock_client.return_value = client
        yield client


@pytest.fixture
def api_url() -> str:
    """Get API URL from environment or use default."""
    return os.environ.get("LEXARD_API_URL", "http://localhost:8000")


@pytest.fixture
def api_client(api_url: str) -> Generator[httpx.Client, None, None]:
    """Create a real HTTP client for integration tests."""
    client = httpx.Client(base_url=api_url, timeout=60.0)
    yield client
    client.close()


@pytest.fixture
def test_document_id() -> str:
    """Get test document ID from environment."""
    return os.environ.get("TEST_DOCUMENT_ID", "test_doc")


def make_query_response(
    answer: str = "Test answer based on [1].",
    citations: list[dict[str, Any]] | None = None,
    confidence: str = "high",
    hallucination_flagged: bool = False,
) -> dict[str, Any]:
    """Helper to create mock query responses."""
    if citations is None:
        citations = [
            {
                "content": "Test citation content",
                "page": 1,
                "chunk_index": 0,
                "score": 0.85,
            }
        ]
    return {
        "answer": answer,
        "citations": citations,
        "confidence": confidence,
        "hallucination_flagged": hallucination_flagged,
    }


def make_error_response(
    code: str = "VALIDATION_ERROR",
    message: str = "Validation failed",
    trace_id: str = "test-trace-id",
) -> dict[str, Any]:
    """Helper to create mock error responses."""
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
        }
    }
