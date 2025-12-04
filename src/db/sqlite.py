"""SQLite document registry for tracking uploaded documents.

Stores document metadata (not vectors) including:
- Document ID, title, filename
- File hash for deduplication
- Page count, chunk count
- Version tracking for updates
- Processing status
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER,
    version INTEGER DEFAULT 1,
    parent_document_id TEXT REFERENCES documents(id),
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'processing'  -- processing | processed | failed
);

CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_parent_document ON documents(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_status ON documents(status);
"""


@dataclass
class Document:
    """Document metadata record."""

    id: str
    title: str
    filename: str
    file_hash: str
    page_count: int | None
    chunk_count: int | None
    version: int
    parent_document_id: str | None
    uploaded_at: datetime
    status: str  # processing | processed | failed


class DocumentRegistry:
    """SQLite-based document metadata storage."""

    def __init__(self, db_path: str = "data/lexard.db"):
        """Initialize the document registry.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for testing.
        """
        self._is_memory = db_path == ":memory:"
        self.db_path = Path(db_path) if not self._is_memory else db_path
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # For in-memory databases, keep a persistent connection
        self._connection: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory configured.

        For in-memory databases, returns a persistent connection.
        For file-based databases, creates new connections as needed.
        """
        if self._is_memory:
            if self._connection is None:
                self._connection = sqlite3.connect(":memory:")
                self._connection.row_factory = sqlite3.Row
            return self._connection

        db_path = str(self.db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        """Convert database row to Document dataclass."""
        uploaded_at = datetime.fromisoformat(row["uploaded_at"])
        return Document(
            id=row["id"],
            title=row["title"],
            filename=row["filename"],
            file_hash=row["file_hash"],
            page_count=row["page_count"],
            chunk_count=row["chunk_count"],
            version=row["version"],
            parent_document_id=row["parent_document_id"],
            uploaded_at=uploaded_at,
            status=row["status"],
        )

    def create(
        self,
        title: str,
        filename: str,
        file_hash: str,
        parent_document_id: str | None = None,
    ) -> Document:
        """Create new document record.

        Args:
            title: Document title
            filename: Original filename
            file_hash: SHA256 hash of file contents for deduplication
            parent_document_id: Optional parent document ID for versioning

        Returns:
            Created Document record
        """
        doc_id = str(uuid.uuid4())
        version = 1

        if parent_document_id:
            parent = self.get(parent_document_id)
            if parent:
                version = parent.version + 1

        conn = self._get_connection()
        conn.execute(
            """INSERT INTO documents
               (id, title, filename, file_hash, version, parent_document_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_id, title, filename, file_hash, version, parent_document_id),
        )
        conn.commit()

        return self.get(doc_id)  # type: ignore[return-value]

    def get(self, doc_id: str) -> Document | None:
        """Get document by ID.

        Args:
            doc_id: Document UUID

        Returns:
            Document if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_document(row)
        return None

    def get_by_hash(self, file_hash: str) -> Document | None:
        """Get document by file hash for deduplication.

        Args:
            file_hash: SHA256 hash of file contents

        Returns:
            Most recent Document with matching hash, None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT * FROM documents
               WHERE file_hash = ?
               ORDER BY uploaded_at DESC
               LIMIT 1""",
            (file_hash,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_document(row)
        return None

    def update_status(
        self,
        doc_id: str,
        status: str,
        page_count: int | None = None,
        chunk_count: int | None = None,
    ) -> bool:
        """Update document processing status.

        Args:
            doc_id: Document UUID
            status: New status (processing | processed | failed)
            page_count: Optional page count to set
            chunk_count: Optional chunk count to set

        Returns:
            True if document was updated, False if not found
        """
        conn = self._get_connection()
        if page_count is not None and chunk_count is not None:
            cursor = conn.execute(
                """UPDATE documents
                   SET status = ?, page_count = ?, chunk_count = ?
                   WHERE id = ?""",
                (status, page_count, chunk_count, doc_id),
            )
        elif page_count is not None:
            cursor = conn.execute(
                """UPDATE documents
                   SET status = ?, page_count = ?
                   WHERE id = ?""",
                (status, page_count, doc_id),
            )
        elif chunk_count is not None:
            cursor = conn.execute(
                """UPDATE documents
                   SET status = ?, chunk_count = ?
                   WHERE id = ?""",
                (status, chunk_count, doc_id),
            )
        else:
            cursor = conn.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                (status, doc_id),
            )
        conn.commit()
        return cursor.rowcount > 0

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List all documents with pagination.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of Document records
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT * FROM documents
               ORDER BY uploaded_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [self._row_to_document(row) for row in rows]

    def delete(self, doc_id: str) -> bool:
        """Delete document record.

        Args:
            doc_id: Document UUID

        Returns:
            True if document was deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?",
            (doc_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Get total document count.

        Returns:
            Number of documents in registry
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM documents")
        row = cursor.fetchone()
        return row[0] if row else 0
