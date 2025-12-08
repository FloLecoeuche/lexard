"""Tests for async progress-tracking API endpoints."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.progress import OperationProgressTracker, OperationStage, get_operation_tracker
from src.api.schemas import AsyncOperationResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_tracker():
    """Create a mock operation tracker."""
    tracker = AsyncMock(spec=OperationProgressTracker)
    tracker.start = AsyncMock(return_value="test-operation-id")
    tracker.get = MagicMock(return_value=None)
    return tracker


class TestAsyncQueryEndpoint:
    """Tests for /query/async endpoint."""

    @patch("src.api.routes.query.get_document_registry")
    @patch("src.api.routes.query.get_operation_tracker")
    def test_query_async_returns_operation_id(
        self, mock_get_tracker, mock_get_registry, client
    ):
        """Test that /query/async returns operation_id immediately."""
        # Mock document registry
        mock_doc = MagicMock()
        mock_doc.status = "processed"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_doc
        mock_get_registry.return_value = mock_registry

        # Mock tracker
        mock_tracker = AsyncMock()
        mock_tracker.start = AsyncMock(return_value="test-op-123")
        mock_get_tracker.return_value = mock_tracker

        response = client.post(
            "/query/async",
            json={
                "document_id": "test-doc-id",
                "question": "What is the contract about?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] == "processing"
        assert "progress" in data["message"].lower()

    @patch("src.api.routes.query.get_document_registry")
    def test_query_async_document_not_found(self, mock_get_registry, client):
        """Test /query/async returns 404 for non-existent document."""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        mock_get_registry.return_value = mock_registry

        response = client.post(
            "/query/async",
            json={
                "document_id": "nonexistent-doc",
                "question": "What is the contract about?",
            },
        )

        assert response.status_code == 404
        assert "DOCUMENT_NOT_FOUND" in response.json()["detail"]["error"]["code"]

    @patch("src.api.routes.query.get_document_registry")
    def test_query_async_document_not_processed(self, mock_get_registry, client):
        """Test /query/async returns 400 for unprocessed document."""
        mock_doc = MagicMock()
        mock_doc.status = "processing"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_doc
        mock_get_registry.return_value = mock_registry

        response = client.post(
            "/query/async",
            json={
                "document_id": "test-doc-id",
                "question": "What is the contract about?",
            },
        )

        assert response.status_code == 400


class TestAsyncSummarizeEndpoint:
    """Tests for /summarize/async endpoint."""

    @patch("src.api.routes.analysis.get_document_registry")
    @patch("src.api.routes.analysis.get_operation_tracker")
    def test_summarize_async_returns_operation_id(
        self, mock_get_tracker, mock_get_registry, client
    ):
        """Test that /summarize/async returns operation_id immediately."""
        # Mock document registry
        mock_doc = MagicMock()
        mock_doc.status = "processed"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_doc
        mock_get_registry.return_value = mock_registry

        # Mock tracker
        mock_tracker = AsyncMock()
        mock_tracker.start = AsyncMock(return_value="test-op-456")
        mock_get_tracker.return_value = mock_tracker

        response = client.post(
            "/summarize/async",
            json={"document_id": "test-doc-id", "style": "executive"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] == "processing"

    @patch("src.api.routes.analysis.get_document_registry")
    def test_summarize_async_document_not_found(self, mock_get_registry, client):
        """Test /summarize/async returns 404 for non-existent document."""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        mock_get_registry.return_value = mock_registry

        response = client.post(
            "/summarize/async",
            json={"document_id": "nonexistent-doc"},
        )

        assert response.status_code == 404


class TestAsyncRisksEndpoint:
    """Tests for /risks/async endpoint."""

    @patch("src.api.routes.analysis.get_document_registry")
    @patch("src.api.routes.analysis.get_operation_tracker")
    def test_risks_async_returns_operation_id(
        self, mock_get_tracker, mock_get_registry, client
    ):
        """Test that /risks/async returns operation_id immediately."""
        # Mock document registry
        mock_doc = MagicMock()
        mock_doc.status = "processed"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_doc
        mock_get_registry.return_value = mock_registry

        # Mock tracker
        mock_tracker = AsyncMock()
        mock_tracker.start = AsyncMock(return_value="test-op-789")
        mock_get_tracker.return_value = mock_tracker

        response = client.post(
            "/risks/async",
            json={"document_id": "test-doc-id"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] == "processing"

    @patch("src.api.routes.analysis.get_document_registry")
    def test_risks_async_document_not_found(self, mock_get_registry, client):
        """Test /risks/async returns 404 for non-existent document."""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        mock_get_registry.return_value = mock_registry

        response = client.post(
            "/risks/async",
            json={"document_id": "nonexistent-doc"},
        )

        assert response.status_code == 404


class TestOperationsProgressEndpoint:
    """Tests for /operations/{operation_id}/progress SSE endpoint."""

    @patch("src.api.routes.operations.get_operation_tracker")
    def test_progress_not_found(self, mock_get_tracker, client):
        """Test /operations/{id}/progress returns 404 for non-existent operation."""
        mock_tracker = MagicMock()
        mock_tracker.get.return_value = None
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/operations/nonexistent-id/progress")

        assert response.status_code == 404


class TestOperationsResultEndpoint:
    """Tests for /operations/{operation_id}/result endpoint."""

    @patch("src.api.routes.operations.get_operation_tracker")
    def test_result_not_found(self, mock_get_tracker, client):
        """Test /operations/{id}/result returns 404 for non-existent operation."""
        mock_tracker = MagicMock()
        mock_tracker.get.return_value = None
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/operations/nonexistent-id/result")

        assert response.status_code == 404

    @patch("src.api.routes.operations.get_operation_tracker")
    def test_result_processing(self, mock_get_tracker, client):
        """Test /operations/{id}/result returns processing status."""
        mock_operation = MagicMock()
        mock_operation.stage = OperationStage.GENERATING
        mock_operation.progress = 0.5
        mock_operation.message = "Generating..."

        mock_tracker = MagicMock()
        mock_tracker.get.return_value = mock_operation
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/operations/test-op-id/result")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["stage"] == "generating"
        assert data["progress"] == 0.5

    @patch("src.api.routes.operations.get_operation_tracker")
    def test_result_complete(self, mock_get_tracker, client):
        """Test /operations/{id}/result returns complete result."""
        mock_operation = MagicMock()
        mock_operation.stage = OperationStage.COMPLETE
        mock_operation.result = {"answer": "Test answer", "language": "en"}

        mock_tracker = MagicMock()
        mock_tracker.get.return_value = mock_operation
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/operations/test-op-id/result")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "complete"
        assert data["result"]["answer"] == "Test answer"

    @patch("src.api.routes.operations.get_operation_tracker")
    def test_result_failed(self, mock_get_tracker, client):
        """Test /operations/{id}/result returns error for failed operation."""
        mock_operation = MagicMock()
        mock_operation.stage = OperationStage.FAILED
        mock_operation.error = "LLM timeout"

        mock_tracker = MagicMock()
        mock_tracker.get.return_value = mock_operation
        mock_get_tracker.return_value = mock_tracker

        response = client.get("/operations/test-op-id/result")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "LLM timeout"


class TestAsyncOperationResponseSchema:
    """Tests for AsyncOperationResponse schema."""

    def test_schema_fields(self):
        """Test schema has required fields."""
        response = AsyncOperationResponse(
            operation_id="test-123",
            status="processing",
            message="Query started",
        )

        assert response.operation_id == "test-123"
        assert response.status == "processing"
        assert response.message == "Query started"

    def test_schema_json_serialization(self):
        """Test schema serializes to JSON correctly."""
        response = AsyncOperationResponse(
            operation_id="test-456",
            status="processing",
            message="Summarization started",
        )

        json_data = response.model_dump()
        assert json_data["operation_id"] == "test-456"
        assert json_data["status"] == "processing"


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with sync endpoints."""

    @patch("src.api.routes.query.get_document_registry")
    @patch("src.api.routes.query.get_rag_pipeline")
    def test_sync_query_still_works(
        self, mock_get_pipeline, mock_get_registry, client
    ):
        """Test that the original /query endpoint still works."""
        # Mock document registry
        mock_doc = MagicMock()
        mock_doc.status = "processed"
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_doc
        mock_get_registry.return_value = mock_registry

        # Mock pipeline
        mock_result = MagicMock()
        mock_result.answer = "Test answer"
        mock_result.citation_chunks = []
        mock_result.confidence = MagicMock(value="high")
        mock_result.language = "en"
        mock_pipeline = MagicMock()
        mock_pipeline.query.return_value = mock_result
        mock_get_pipeline.return_value = mock_pipeline

        response = client.post(
            "/query",
            json={
                "document_id": "test-doc-id",
                "question": "What is the contract about?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["answer"] == "Test answer"
