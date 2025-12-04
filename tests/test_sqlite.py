"""Tests for SQLite document registry module."""

import pytest

from src.db.sqlite import Document, DocumentRegistry


class TestDocumentRegistry:
    """Tests for the DocumentRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create an in-memory registry for testing."""
        return DocumentRegistry(":memory:")

    def test_create_document(self, registry):
        """Creating a document should return a Document with correct fields."""
        doc = registry.create("Test Doc", "test.pdf", "abc123hash")

        assert doc.id is not None
        assert doc.title == "Test Doc"
        assert doc.filename == "test.pdf"
        assert doc.file_hash == "abc123hash"
        assert doc.version == 1
        assert doc.status == "processing"
        assert doc.parent_document_id is None
        assert doc.page_count is None
        assert doc.chunk_count is None
        assert doc.uploaded_at is not None

    def test_get_document(self, registry):
        """Getting a document by ID should return the correct document."""
        created = registry.create("Test Doc", "test.pdf", "abc123")
        retrieved = registry.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Test Doc"

    def test_get_nonexistent_document(self, registry):
        """Getting a nonexistent document should return None."""
        result = registry.get("nonexistent-uuid")
        assert result is None

    def test_get_by_hash(self, registry):
        """Getting document by hash should return a matching document."""
        doc1 = registry.create("Doc 1", "doc1.pdf", "samehash")

        existing = registry.get_by_hash("samehash")

        assert existing is not None
        assert existing.id == doc1.id
        assert existing.file_hash == "samehash"

    def test_get_by_hash_not_found(self, registry):
        """Getting by nonexistent hash should return None."""
        result = registry.get_by_hash("nonexistent-hash")
        assert result is None

    def test_update_status(self, registry):
        """Updating status should persist the changes."""
        doc = registry.create("Test Doc", "test.pdf", "abc123")

        result = registry.update_status(doc.id, "processed")
        assert result is True

        updated = registry.get(doc.id)
        assert updated is not None
        assert updated.status == "processed"

    def test_update_status_with_counts(self, registry):
        """Updating status with page and chunk counts should persist all values."""
        doc = registry.create("Test Doc", "test.pdf", "abc123")

        registry.update_status(doc.id, "processed", page_count=10, chunk_count=25)

        updated = registry.get(doc.id)
        assert updated is not None
        assert updated.status == "processed"
        assert updated.page_count == 10
        assert updated.chunk_count == 25

    def test_update_status_page_count_only(self, registry):
        """Updating with page_count only should work."""
        doc = registry.create("Test Doc", "test.pdf", "abc123")

        registry.update_status(doc.id, "processing", page_count=5)

        updated = registry.get(doc.id)
        assert updated is not None
        assert updated.page_count == 5
        assert updated.chunk_count is None

    def test_update_status_chunk_count_only(self, registry):
        """Updating with chunk_count only should work."""
        doc = registry.create("Test Doc", "test.pdf", "abc123")

        registry.update_status(doc.id, "processing", chunk_count=15)

        updated = registry.get(doc.id)
        assert updated is not None
        assert updated.chunk_count == 15
        assert updated.page_count is None

    def test_update_status_nonexistent(self, registry):
        """Updating nonexistent document should return False."""
        result = registry.update_status("nonexistent-uuid", "processed")
        assert result is False

    def test_version_increment(self, registry):
        """Creating a document with parent should increment version."""
        doc1 = registry.create("Doc", "doc.pdf", "hash1")
        doc2 = registry.create("Doc v2", "doc.pdf", "hash2", parent_document_id=doc1.id)
        doc3 = registry.create("Doc v3", "doc.pdf", "hash3", parent_document_id=doc2.id)

        assert doc1.version == 1
        assert doc2.version == 2
        assert doc2.parent_document_id == doc1.id
        assert doc3.version == 3
        assert doc3.parent_document_id == doc2.id

    def test_version_with_invalid_parent(self, registry):
        """Creating with invalid parent ID should default to version 1."""
        doc = registry.create("Doc", "doc.pdf", "hash1", parent_document_id="invalid-id")
        assert doc.version == 1

    def test_list_all_empty(self, registry):
        """Listing empty registry should return empty list."""
        docs = registry.list_all()
        assert docs == []

    def test_list_all(self, registry):
        """Listing should return all documents."""
        registry.create("Doc 1", "doc1.pdf", "hash1")
        registry.create("Doc 2", "doc2.pdf", "hash2")
        registry.create("Doc 3", "doc3.pdf", "hash3")

        docs = registry.list_all()
        assert len(docs) == 3

    def test_list_all_returns_all_documents(self, registry):
        """List should return all created documents."""
        doc1 = registry.create("Doc 1", "doc1.pdf", "hash1")
        doc2 = registry.create("Doc 2", "doc2.pdf", "hash2")
        doc3 = registry.create("Doc 3", "doc3.pdf", "hash3")

        docs = registry.list_all()

        # All documents should be returned
        doc_ids = {d.id for d in docs}
        assert doc1.id in doc_ids
        assert doc2.id in doc_ids
        assert doc3.id in doc_ids

    def test_list_all_pagination(self, registry):
        """Pagination should work correctly."""
        for i in range(10):
            registry.create(f"Doc {i}", f"doc{i}.pdf", f"hash{i}")

        page1 = registry.list_all(limit=3, offset=0)
        page2 = registry.list_all(limit=3, offset=3)
        page3 = registry.list_all(limit=3, offset=6)
        page4 = registry.list_all(limit=3, offset=9)

        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 3
        assert len(page4) == 1

        # Verify no duplicates
        all_ids = [d.id for d in page1 + page2 + page3 + page4]
        assert len(all_ids) == len(set(all_ids))

    def test_delete_document(self, registry):
        """Deleting a document should remove it from registry."""
        doc = registry.create("Test Doc", "test.pdf", "abc123")

        result = registry.delete(doc.id)
        assert result is True

        retrieved = registry.get(doc.id)
        assert retrieved is None

    def test_delete_nonexistent(self, registry):
        """Deleting nonexistent document should return False."""
        result = registry.delete("nonexistent-uuid")
        assert result is False

    def test_count_empty(self, registry):
        """Count on empty registry should return 0."""
        assert registry.count() == 0

    def test_count(self, registry):
        """Count should return correct number of documents."""
        registry.create("Doc 1", "doc1.pdf", "hash1")
        registry.create("Doc 2", "doc2.pdf", "hash2")
        registry.create("Doc 3", "doc3.pdf", "hash3")

        assert registry.count() == 3

    def test_count_after_delete(self, registry):
        """Count should update after deletion."""
        doc = registry.create("Doc", "doc.pdf", "hash")
        assert registry.count() == 1

        registry.delete(doc.id)
        assert registry.count() == 0


class TestDocumentRegistryFileSystem:
    """Tests for DocumentRegistry with actual file system."""

    def test_creates_data_directory(self, tmp_path):
        """Registry should create data directory if it doesn't exist."""
        db_path = tmp_path / "subdir" / "nested" / "lexard.db"
        registry = DocumentRegistry(str(db_path))

        assert db_path.parent.exists()
        doc = registry.create("Test", "test.pdf", "hash")
        assert doc is not None

    def test_persistence(self, tmp_path):
        """Data should persist across registry instances."""
        db_path = tmp_path / "lexard.db"

        # Create document with first instance
        registry1 = DocumentRegistry(str(db_path))
        doc = registry1.create("Test Doc", "test.pdf", "abc123")
        doc_id = doc.id

        # Retrieve with second instance
        registry2 = DocumentRegistry(str(db_path))
        retrieved = registry2.get(doc_id)

        assert retrieved is not None
        assert retrieved.title == "Test Doc"
