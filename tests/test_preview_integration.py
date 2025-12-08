"""Integration tests for document preview feature (US 11.3).

Tests the full workflow: upload → preview → delete
for PDF, DOCX, and TXT files.
"""

import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.db.sqlite import DocumentRegistry


class TestPreviewIntegration:
    """Integration tests for document preview workflow."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def registry(self):
        """Create in-memory test registry."""
        return DocumentRegistry(":memory:")

    # --- PDF Tests ---

    def test_pdf_upload_stores_blob(self, registry):
        """Test that PDF upload stores file content as BLOB."""
        # Create document
        doc = registry.create(
            title="Test PDF",
            filename="test.pdf",
            file_hash="pdf123",
        )

        # Simulate PDF content (minimal PDF header)
        pdf_content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\ntrailer\n<</Root 1 0 R>>\n%%EOF"

        # Store content
        result = registry.store_file_content(doc.id, pdf_content)
        assert result is True

        # Retrieve and verify
        retrieved = registry.get_file_content(doc.id)
        assert retrieved == pdf_content

    def test_pdf_mime_type(self):
        """Test PDF MIME type mapping."""
        from src.api.routes.documents import MIME_TYPES

        assert MIME_TYPES[".pdf"] == "application/pdf"

    def test_pdf_multipage_blob_storage(self, registry):
        """Test storage of multi-page PDF (larger file)."""
        doc = registry.create(
            title="Multi-page PDF",
            filename="multipage.pdf",
            file_hash="multi123",
        )

        # Simulate larger PDF content (5KB)
        pdf_content = b"%PDF-1.4\n" + b"x" * 5000 + b"\n%%EOF"

        result = registry.store_file_content(doc.id, pdf_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert len(retrieved) == len(pdf_content)

    # --- DOCX Tests ---

    def test_docx_upload_stores_blob(self, registry):
        """Test that DOCX upload stores file content as BLOB."""
        doc = registry.create(
            title="Test DOCX",
            filename="test.docx",
            file_hash="docx123",
        )

        # DOCX files are ZIP archives - start with PK signature
        docx_content = b"PK\x03\x04" + b"\x00" * 100

        result = registry.store_file_content(doc.id, docx_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert retrieved == docx_content

    def test_docx_mime_type(self):
        """Test DOCX MIME type mapping."""
        from src.api.routes.documents import MIME_TYPES

        expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert MIME_TYPES[".docx"] == expected

    # --- TXT Tests ---

    def test_txt_upload_stores_blob(self, registry):
        """Test that TXT upload stores file content as BLOB."""
        doc = registry.create(
            title="Test TXT",
            filename="test.txt",
            file_hash="txt123",
        )

        txt_content = b"This is a test text file.\nWith multiple lines.\n"

        result = registry.store_file_content(doc.id, txt_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert retrieved == txt_content

    def test_txt_mime_type(self):
        """Test TXT MIME type mapping."""
        from src.api.routes.documents import MIME_TYPES

        assert MIME_TYPES[".txt"] == "text/plain; charset=utf-8"

    def test_txt_unicode_content(self, registry):
        """Test TXT file with Unicode content (French, Chinese, emoji)."""
        doc = registry.create(
            title="Unicode TXT",
            filename="unicode.txt",
            file_hash="unicode123",
        )

        # French, Chinese, and emoji content
        unicode_content = "Bonjour le monde! 你好世界! 🎉🚀".encode("utf-8")

        result = registry.store_file_content(doc.id, unicode_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert retrieved == unicode_content
        # Verify it decodes correctly
        decoded = retrieved.decode("utf-8")
        assert "Bonjour" in decoded
        assert "你好" in decoded
        assert "🎉" in decoded

    # --- Large File Tests ---

    def test_large_file_storage(self, registry):
        """Test storing large file content (10MB)."""
        doc = registry.create(
            title="Large File",
            filename="large.pdf",
            file_hash="large123",
        )

        # 10MB of content
        large_content = b"x" * (10 * 1024 * 1024)

        result = registry.store_file_content(doc.id, large_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert len(retrieved) == 10 * 1024 * 1024

    def test_very_large_file_storage(self, registry):
        """Test storing very large file content (25MB)."""
        doc = registry.create(
            title="Very Large File",
            filename="very_large.pdf",
            file_hash="verylarge123",
        )

        # 25MB of content
        large_content = b"x" * (25 * 1024 * 1024)

        result = registry.store_file_content(doc.id, large_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert len(retrieved) == 25 * 1024 * 1024

    # --- Legacy Document Tests (Migration) ---

    def test_legacy_document_no_blob(self, registry):
        """Test that documents without BLOB return None gracefully."""
        doc = registry.create(
            title="Legacy Document",
            filename="legacy.pdf",
            file_hash="legacy123",
        )

        # Don't store any file content (simulating pre-BLOB document)
        retrieved = registry.get_file_content(doc.id)
        assert retrieved is None

    def test_legacy_document_endpoint_returns_404(self, client):
        """Test that file endpoint returns 404 for legacy documents without BLOB."""
        # This test needs to mock the registry to return a document without file content
        with patch("src.api.routes.documents.get_document_registry") as mock_get_registry:
            mock_registry = MagicMock()

            # Mock document exists but no file content
            mock_doc = MagicMock()
            mock_doc.id = "legacy-doc-id"
            mock_doc.filename = "legacy.pdf"
            mock_registry.get.return_value = mock_doc
            mock_registry.get_file_content.return_value = None

            mock_get_registry.return_value = mock_registry

            response = client.get("/documents/legacy-doc-id/file")

            assert response.status_code == 404
            data = response.json()
            assert data["detail"]["error"]["code"] == "FILE_NOT_FOUND"

    # --- Error Handling Tests ---

    def test_file_endpoint_nonexistent_document(self, client):
        """Test 404 for non-existent document."""
        response = client.get("/documents/nonexistent-doc-id/file")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_file_endpoint_response_headers(self):
        """Test that file endpoint returns correct headers."""
        with patch("src.api.routes.documents.get_document_registry") as mock_get_registry:
            mock_registry = MagicMock()

            mock_doc = MagicMock()
            mock_doc.id = "test-id"
            mock_doc.filename = "contract.pdf"
            mock_registry.get.return_value = mock_doc
            mock_registry.get_file_content.return_value = b"%PDF-1.4\n%%EOF"

            mock_get_registry.return_value = mock_registry

            client = TestClient(app)
            response = client.get("/documents/test-id/file")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert 'filename="contract.pdf"' in response.headers["content-disposition"]

    def test_file_endpoint_inline_disposition(self):
        """Test that Content-Disposition is 'inline' for browser display."""
        with patch("src.api.routes.documents.get_document_registry") as mock_get_registry:
            mock_registry = MagicMock()

            mock_doc = MagicMock()
            mock_doc.id = "test-id"
            mock_doc.filename = "document.txt"
            mock_registry.get.return_value = mock_doc
            mock_registry.get_file_content.return_value = b"Hello World"

            mock_get_registry.return_value = mock_registry

            client = TestClient(app)
            response = client.get("/documents/test-id/file")

            assert response.status_code == 200
            assert "inline" in response.headers["content-disposition"]

    # --- Delete Workflow Tests ---

    def test_delete_removes_blob(self, registry):
        """Test that deleting document removes BLOB content."""
        doc = registry.create(
            title="To Delete",
            filename="delete.pdf",
            file_hash="delete123",
        )

        # Store content
        registry.store_file_content(doc.id, b"content to delete")
        assert registry.get_file_content(doc.id) is not None

        # Delete document
        registry.delete(doc.id)

        # Verify document and content are gone
        assert registry.get(doc.id) is None
        assert registry.get_file_content(doc.id) is None

    # --- Binary Content Tests ---

    def test_binary_pdf_content_preserved(self, registry):
        """Test that binary PDF content is preserved exactly."""
        doc = registry.create(
            title="Binary PDF",
            filename="binary.pdf",
            file_hash="binary123",
        )

        # Real PDF-like binary content with all byte values
        binary_content = bytes(range(256)) + b"%PDF-1.4\x00\x01\x02\xff\xfe\xfd"

        result = registry.store_file_content(doc.id, binary_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert retrieved == binary_content

    def test_binary_docx_content_preserved(self, registry):
        """Test that binary DOCX content is preserved exactly."""
        doc = registry.create(
            title="Binary DOCX",
            filename="binary.docx",
            file_hash="bindocx123",
        )

        # DOCX ZIP archive header + binary data
        binary_content = b"PK\x03\x04" + bytes(range(256))

        result = registry.store_file_content(doc.id, binary_content)
        assert result is True

        retrieved = registry.get_file_content(doc.id)
        assert retrieved == binary_content

    # --- Concurrent Access Tests ---

    def test_multiple_documents_isolated(self, registry):
        """Test that multiple documents have isolated content."""
        doc1 = registry.create(
            title="Doc 1",
            filename="doc1.pdf",
            file_hash="hash1",
        )
        doc2 = registry.create(
            title="Doc 2",
            filename="doc2.pdf",
            file_hash="hash2",
        )

        content1 = b"Content for document 1"
        content2 = b"Content for document 2"

        registry.store_file_content(doc1.id, content1)
        registry.store_file_content(doc2.id, content2)

        # Verify isolation
        assert registry.get_file_content(doc1.id) == content1
        assert registry.get_file_content(doc2.id) == content2

        # Delete one, other unaffected
        registry.delete(doc1.id)
        assert registry.get_file_content(doc1.id) is None
        assert registry.get_file_content(doc2.id) == content2


class TestPreviewEndpointSecurity:
    """Security tests for document file endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_path_traversal_blocked(self, client):
        """Test that path traversal attempts are blocked."""
        malicious_ids = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
            "/etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f",
        ]

        for malicious_id in malicious_ids:
            response = client.get(f"/documents/{malicious_id}/file")
            # Should be 404 (document not found), not a server error
            assert response.status_code == 404

    def test_null_byte_injection_blocked(self, client):
        """Test that null byte injection is blocked."""
        response = client.get("/documents/valid-id%00.pdf/file")
        assert response.status_code in (404, 400)

    def test_very_long_id_handled(self, client):
        """Test that very long document IDs are handled gracefully."""
        long_id = "a" * 10000
        response = client.get(f"/documents/{long_id}/file")
        assert response.status_code in (404, 400, 422)


class TestPreviewMIMETypes:
    """Tests for MIME type handling in preview."""

    def test_all_supported_types_mapped(self):
        """Test that all supported file types have MIME mappings."""
        from src.api.routes.documents import MIME_TYPES, ALLOWED_EXTENSIONS

        for ext in ALLOWED_EXTENSIONS:
            assert ext in MIME_TYPES, f"Missing MIME type for {ext}"

    def test_unknown_extension_fallback(self):
        """Test fallback MIME type for unknown extensions."""
        from src.api.routes.documents import MIME_TYPES

        # Unknown extension should not be in mapping
        assert ".xyz" not in MIME_TYPES

        # The endpoint uses .get() with fallback to application/octet-stream
        fallback = MIME_TYPES.get(".xyz", "application/octet-stream")
        assert fallback == "application/octet-stream"

    def test_case_insensitive_extension(self):
        """Test that file extensions are handled case-insensitively."""
        with patch("src.api.routes.documents.get_document_registry") as mock_get_registry:
            mock_registry = MagicMock()

            # Test uppercase extension
            mock_doc = MagicMock()
            mock_doc.id = "test-id"
            mock_doc.filename = "DOCUMENT.PDF"  # Uppercase
            mock_registry.get.return_value = mock_doc
            mock_registry.get_file_content.return_value = b"%PDF-1.4"

            mock_get_registry.return_value = mock_registry

            client = TestClient(app)
            response = client.get("/documents/test-id/file")

            # Should still return PDF MIME type
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
