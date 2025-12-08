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


class TestAnalyticsSchema:
    """Tests for analytics database schema."""

    @pytest.fixture
    def registry(self):
        """Create an in-memory registry for testing."""
        return DocumentRegistry(":memory:")

    def test_analytics_events_table_created(self, registry):
        """analytics_events table should be created on initialization."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_events'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "analytics_events"

    def test_analytics_sessions_table_created(self, registry):
        """analytics_sessions table should be created on initialization."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_sessions'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "analytics_sessions"

    def test_analytics_browsers_table_created(self, registry):
        """analytics_browsers table should be created on initialization."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_browsers'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "analytics_browsers"

    def test_analytics_events_table_columns(self, registry):
        """analytics_events table should have correct columns."""
        conn = registry._get_connection()
        cursor = conn.execute("PRAGMA table_info(analytics_events)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "event_name" in columns
        assert "browser_id" in columns
        assert "session_id" in columns
        assert "properties" in columns
        assert "created_at" in columns

    def test_analytics_sessions_table_columns(self, registry):
        """analytics_sessions table should have correct columns."""
        conn = registry._get_connection()
        cursor = conn.execute("PRAGMA table_info(analytics_sessions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "session_id" in columns
        assert "browser_id" in columns
        assert "started_at" in columns
        assert "ended_at" in columns
        assert "is_returning_user" in columns
        assert "event_count" in columns
        assert "query_count" in columns
        assert "docs_uploaded" in columns

    def test_analytics_browsers_table_columns(self, registry):
        """analytics_browsers table should have correct columns."""
        conn = registry._get_connection()
        cursor = conn.execute("PRAGMA table_info(analytics_browsers)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "browser_id" in columns
        assert "first_seen_at" in columns
        assert "last_seen_at" in columns
        assert "total_sessions" in columns

    def test_analytics_events_indexes_created(self, registry):
        """analytics_events indexes should be created."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_events_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_events_browser" in indexes
        assert "idx_events_session" in indexes
        assert "idx_events_name" in indexes
        assert "idx_events_created" in indexes

    def test_analytics_sessions_indexes_created(self, registry):
        """analytics_sessions indexes should be created."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_sessions_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_sessions_browser" in indexes
        assert "idx_sessions_started" in indexes

    def test_analytics_browsers_indexes_created(self, registry):
        """analytics_browsers indexes should be created."""
        conn = registry._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_browsers_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_browsers_first_seen" in indexes

    def test_analytics_schema_idempotent(self, registry):
        """Running schema initialization multiple times should not fail."""
        conn = registry._get_connection()

        # Call init again - should not raise
        registry._init_analytics_schema(conn)
        registry._init_analytics_schema(conn)

        # Tables should still exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'analytics_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert len(tables) == 3

    def test_documents_table_unaffected(self, registry):
        """analytics schema should not affect existing documents table."""
        # Create a document
        doc = registry.create("Test Doc", "test.pdf", "hash123")
        assert doc is not None
        assert doc.title == "Test Doc"

        # Verify document retrieval still works
        retrieved = registry.get(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id

    def test_can_insert_analytics_event(self, registry):
        """Should be able to insert into analytics_events table."""
        conn = registry._get_connection()
        conn.execute(
            """INSERT INTO analytics_events
               (event_name, browser_id, session_id, properties)
               VALUES (?, ?, ?, ?)""",
            ("test_event", "browser123", "session456", '{"key": "value"}'),
        )
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM analytics_events")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_can_insert_analytics_session(self, registry):
        """Should be able to insert into analytics_sessions table."""
        conn = registry._get_connection()
        conn.execute(
            """INSERT INTO analytics_sessions
               (session_id, browser_id, is_returning_user)
               VALUES (?, ?, ?)""",
            ("session123", "browser456", False),
        )
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM analytics_sessions")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_can_insert_analytics_browser(self, registry):
        """Should be able to insert into analytics_browsers table."""
        conn = registry._get_connection()
        conn.execute(
            """INSERT INTO analytics_browsers (browser_id) VALUES (?)""",
            ("browser789",),
        )
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM analytics_browsers")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_session_id_unique_constraint(self, registry):
        """analytics_sessions.session_id should be unique."""
        import sqlite3

        conn = registry._get_connection()
        conn.execute(
            """INSERT INTO analytics_sessions (session_id, browser_id, is_returning_user)
               VALUES (?, ?, ?)""",
            ("unique_session", "browser1", False),
        )
        conn.commit()

        # Attempting to insert duplicate session_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO analytics_sessions (session_id, browser_id, is_returning_user)
                   VALUES (?, ?, ?)""",
                ("unique_session", "browser2", True),
            )

    def test_browser_id_primary_key(self, registry):
        """analytics_browsers.browser_id should be primary key."""
        import sqlite3

        conn = registry._get_connection()
        conn.execute(
            "INSERT INTO analytics_browsers (browser_id) VALUES (?)",
            ("pk_browser",),
        )
        conn.commit()

        # Attempting to insert duplicate browser_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO analytics_browsers (browser_id) VALUES (?)",
                ("pk_browser",),
            )
