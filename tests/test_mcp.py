"""Tests for MCP JSON-RPC 2.0 server."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestMCPEndpoint:
    """Tests for /mcp JSON-RPC endpoint."""

    def test_list_documents_success(self, client):
        """Test list_documents method returns valid JSON-RPC response."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "list_documents",
                "params": {},
                "id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert data["id"] == 1
        assert "documents" in data["result"]

    def test_method_not_found(self, client):
        """Test unknown method returns -32601."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "invalid_method",
                "params": {},
                "id": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32601
        assert "not found" in data["error"]["message"].lower()
        assert data["id"] == 2

    def test_invalid_params(self, client):
        """Test invalid params returns -32602."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "analyze_document",
                "params": {},  # Missing required params
                "id": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32602
        assert data["id"] == 3

    def test_invalid_request_no_jsonrpc(self, client):
        """Test missing jsonrpc field returns -32600."""
        response = client.post(
            "/mcp",
            json={
                "method": "list_documents",
                "id": 4,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600

    def test_invalid_request_wrong_jsonrpc_version(self, client):
        """Test wrong jsonrpc version returns -32600."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "1.0",
                "method": "list_documents",
                "id": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32600

    def test_parse_error_invalid_json(self, client):
        """Test invalid JSON returns -32700."""
        response = client.post(
            "/mcp",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32700

    def test_document_not_found_analyze(self, client):
        """Test document not found returns -32000."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "analyze_document",
                "params": {
                    "document_id": "nonexistent-uuid",
                    "analysis_type": "summary",
                },
                "id": 6,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32000
        assert data["id"] == 6

    def test_document_not_found_ask_question(self, client):
        """Test document not found in ask_question returns -32000."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "ask_question",
                "params": {
                    "document_id": "nonexistent-uuid",
                    "question": "What is this document about?",
                },
                "id": 7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32000
        assert data["id"] == 7

    def test_document_not_found_compare(self, client):
        """Test document not found in compare returns -32000."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "compare",
                "params": {
                    "doc_a": "nonexistent-uuid-1",
                    "doc_b": "nonexistent-uuid-2",
                },
                "id": 8,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"]["code"] == -32000
        assert data["id"] == 8

    def test_notification_no_id(self, client):
        """Test notification (no id) returns response with null id."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "list_documents",
                "params": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] is None

    def test_string_id_preserved(self, client):
        """Test string request ID is preserved in response."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "list_documents",
                "params": {},
                "id": "request-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "request-123"


class TestMCPSchemas:
    """Tests for MCP schema validation."""

    def test_analyze_document_valid_types(self, client):
        """Test analyze_document accepts all valid analysis types."""
        for analysis_type in ["summary", "risks", "metadata"]:
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "analyze_document",
                    "params": {
                        "document_id": "test-doc",
                        "analysis_type": analysis_type,
                    },
                    "id": 1,
                },
            )

            # Should get document not found, not invalid params
            data = response.json()
            assert data["error"]["code"] == -32000  # Document not found

    def test_analyze_document_invalid_type(self, client):
        """Test analyze_document rejects invalid analysis type."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "analyze_document",
                "params": {
                    "document_id": "test-doc",
                    "analysis_type": "invalid_type",
                },
                "id": 1,
            },
        )

        data = response.json()
        assert data["error"]["code"] == -32602  # Invalid params
