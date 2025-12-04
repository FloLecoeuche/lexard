"""Database layer - Qdrant and SQLite.

Note: Direct imports from submodules are preferred to avoid circular imports.
Use `from src.db.sqlite import DocumentRegistry` or `from src.db.qdrant import QdrantService`.
"""


def __getattr__(name: str):
    """Lazy import to avoid circular imports."""
    if name in ("QdrantService", "QdrantConnectionError"):
        from src.db.qdrant import QdrantConnectionError, QdrantService

        if name == "QdrantService":
            return QdrantService
        return QdrantConnectionError
    if name in ("Document", "DocumentRegistry"):
        from src.db.sqlite import Document, DocumentRegistry

        if name == "Document":
            return Document
        return DocumentRegistry
    raise AttributeError(f"module 'src.db' has no attribute '{name}'")


__all__ = ["QdrantService", "QdrantConnectionError", "Document", "DocumentRegistry"]
