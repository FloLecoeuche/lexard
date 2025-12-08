"""Tests for document file serving endpoint."""

import pytest

from src.db.sqlite import DocumentRegistry


class TestDocumentRegistry:
    """Tests for DocumentRegistry file content methods."""

    def test_store_and_get_file_content(self):
        """Test storing and retrieving file content."""
        registry = DocumentRegistry(":memory:")
        doc = registry.create(
            title="Test Document",
            filename="test.pdf",
            file_hash="abc123",
        )

        content = b"PDF file content bytes"
        result = registry.store_file_content(doc.id, content)

        assert result is True
        retrieved = registry.get_file_content(doc.id)
        assert retrieved == content

    def test_get_file_content_nonexistent_document(self):
        """Test getting file content for non-existent document."""
        registry = DocumentRegistry(":memory:")
        result = registry.get_file_content("nonexistent-id")
        assert result is None

    def test_get_file_content_no_content_stored(self):
        """Test getting file content when none was stored."""
        registry = DocumentRegistry(":memory:")
        doc = registry.create(
            title="Test Document",
            filename="test.pdf",
            file_hash="abc123",
        )

        result = registry.get_file_content(doc.id)
        assert result is None

    def test_store_file_content_nonexistent_document(self):
        """Test storing file content for non-existent document."""
        registry = DocumentRegistry(":memory:")
        result = registry.store_file_content("nonexistent-id", b"content")
        assert result is False

    def test_store_large_file_content(self):
        """Test storing large file content (simulating real documents)."""
        registry = DocumentRegistry(":memory:")
        doc = registry.create(
            title="Large Document",
            filename="large.pdf",
            file_hash="large123",
        )

        # 1MB of content
        large_content = b"x" * (1024 * 1024)
        result = registry.store_file_content(doc.id, large_content)

        assert result is True
        retrieved = registry.get_file_content(doc.id)
        assert retrieved == large_content
        assert len(retrieved) == 1024 * 1024

    def test_store_binary_file_content(self):
        """Test storing binary file content with various byte values."""
        registry = DocumentRegistry(":memory:")
        doc = registry.create(
            title="Binary Document",
            filename="binary.pdf",
            file_hash="binary123",
        )

        # PDF header followed by binary data
        binary_content = b"%PDF-1.4\x00\x01\x02\xff\xfe\xfd"
        result = registry.store_file_content(doc.id, binary_content)

        assert result is True
        retrieved = registry.get_file_content(doc.id)
        assert retrieved == binary_content

    def test_migration_adds_column(self):
        """Test that migration adds file_content column."""
        registry = DocumentRegistry(":memory:")
        conn = registry._get_connection()

        # Check column exists
        cursor = conn.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]

        assert "file_content" in columns


class TestDocumentFileEndpoint:
    """Tests for GET /documents/{doc_id}/file endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.api.main import app

        return TestClient(app)

    @pytest.fixture
    def registry(self):
        """Create test registry."""
        return DocumentRegistry(":memory:")

    def test_get_file_endpoint_document_not_found(self, client):
        """Test 404 when document doesn't exist."""
        response = client.get("/documents/nonexistent-id/file")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_mime_type_mapping(self):
        """Test MIME type mapping for supported formats."""
        from src.api.routes.documents import MIME_TYPES

        assert MIME_TYPES[".pdf"] == "application/pdf"
        assert (
            MIME_TYPES[".docx"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert MIME_TYPES[".txt"] == "text/plain; charset=utf-8"

    def test_path_traversal_protection(self, client):
        """Test that path traversal attempts are handled safely."""
        # These should all return 404, not expose files
        malicious_ids = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
            "/etc/passwd",
        ]

        for malicious_id in malicious_ids:
            response = client.get(f"/documents/{malicious_id}/file")
            # Should be 404 (not found) not 200 or 500
            assert response.status_code == 404
