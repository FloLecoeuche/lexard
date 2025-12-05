"""Document management routes for Lexard API."""

import hashlib
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.api.exceptions import DocumentParseError
from src.api.schemas import (
    DeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    ErrorResponse,
)

# Router for /documents/* endpoints
router = APIRouter(prefix="/documents", tags=["documents"])

# Separate router for /upload at root level
upload_router = APIRouter(tags=["documents"])

# Maximum file size in bytes (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def get_document_registry():
    """Get document registry instance (lazy import to avoid circular imports)."""
    from src.db.sqlite import DocumentRegistry

    return DocumentRegistry()


def get_qdrant_service():
    """Get Qdrant service instance (lazy import to avoid circular imports)."""
    from src.db.qdrant import QdrantService

    return QdrantService()


def get_embedding_service():
    """Get embedding service instance (lazy import to avoid circular imports)."""
    from src.rag.embeddings import EmbeddingService
    from src.config import get_settings

    settings = get_settings()
    return EmbeddingService(
        model_name=settings.embeddings.model,
        device=settings.embeddings.device,
        query_prefix=settings.embeddings.query_prefix,
        document_prefix=settings.embeddings.document_prefix,
    )


def _compute_file_hash(content: bytes) -> str:
    """Compute SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def _validate_file(file: UploadFile) -> None:
    """Validate uploaded file format."""
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Filename is required",
                    "trace_id": "",
                }
            },
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={
                "error": {
                    "code": "UNSUPPORTED_FORMAT",
                    "message": f"Unsupported file format: {suffix}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
                    "trace_id": "",
                }
            },
        )


@upload_router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    responses={
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "Unsupported file format"},
        422: {"model": ErrorResponse, "description": "Failed to parse document"},
    },
    summary="Upload a document",
    description="Upload a PDF, DOCX, or TXT document for analysis. The document is processed, chunked, and indexed.",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file (PDF, DOCX, or TXT)"),
) -> DocumentUploadResponse:
    """Upload and process a new document."""
    from src.config import get_settings
    from src.rag.chunking import Chunker
    from src.rag.extractors.factory import get_extractor

    trace_id = getattr(request.state, "trace_id", "")

    # Validate file format
    _validate_file(file)

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB",
                    "trace_id": trace_id,
                }
            },
        )

    # Compute file hash
    file_hash = _compute_file_hash(content)

    # Get file extension
    suffix = Path(file.filename).suffix.lower()  # type: ignore[union-attr]

    # Save to temp file for extraction
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_path = Path(tmp_file.name)

    # Extract text from document
    try:
        extractor = get_extractor(tmp_path)
        extraction_result = extractor.extract(tmp_path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise DocumentParseError(f"Failed to extract text from document: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # Get title from filename
    title = Path(file.filename).stem  # type: ignore[union-attr]

    # Initialize services
    registry = get_document_registry()
    qdrant = get_qdrant_service()
    embedding_service = get_embedding_service()
    settings = get_settings()

    # Create document record
    doc = registry.create(
        title=title,
        filename=file.filename,  # type: ignore[arg-type]
        file_hash=file_hash,
    )

    try:
        # Chunk the text using Chunker class
        chunker = Chunker(
            chunk_size=settings.chunking.size,
            overlap=settings.chunking.overlap,
        )
        chunks = chunker.chunk(extraction_result.pages)

        # Generate embeddings
        embeddings = embedding_service.embed_chunks(chunks)

        # Ensure collection exists
        qdrant.ensure_collection()

        # Store in Qdrant
        qdrant.upsert_chunks(
            chunks=chunks,
            embeddings=embeddings,
            document_id=doc.id,
            source_title=title,
        )

        # Update document status
        registry.update_status(
            doc.id,
            status="processed",
            page_count=extraction_result.total_pages,
            chunk_count=len(chunks),
        )

        # Refresh document from registry
        doc = registry.get(doc.id)  # type: ignore[assignment]

    except Exception as e:
        # Mark as failed on error
        registry.update_status(doc.id, status="failed")
        raise DocumentParseError(f"Failed to process document: {e}")

    return DocumentUploadResponse(
        document_id=doc.id,
        title=doc.title,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        version=doc.version,
        uploaded_at=doc.uploaded_at,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all documents",
    description="Get a list of all uploaded documents with metadata.",
)
async def list_documents(
    limit: int = 100,
    offset: int = 0,
) -> DocumentListResponse:
    """List all documents."""
    registry = get_document_registry()
    documents = registry.list_all(limit=limit, offset=offset)
    total = registry.count()

    return DocumentListResponse(
        documents=[
            DocumentMetadata(
                id=doc.id,
                title=doc.title,
                filename=doc.filename,
                page_count=doc.page_count,
                chunk_count=doc.chunk_count,
                version=doc.version,
                uploaded_at=doc.uploaded_at,
                status=doc.status,
            )
            for doc in documents
        ],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
    summary="Get document details",
    description="Get detailed information about a specific document.",
)
async def get_document(
    document_id: str,
    request: Request,
) -> DocumentDetailResponse:
    """Get document details by ID."""
    trace_id = getattr(request.state, "trace_id", "")
    registry = get_document_registry()
    doc = registry.get(document_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document with ID {document_id} not found",
                    "trace_id": trace_id,
                }
            },
        )

    return DocumentDetailResponse(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_hash=doc.file_hash,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        version=doc.version,
        parent_document_id=doc.parent_document_id,
        uploaded_at=doc.uploaded_at,
        status=doc.status,
    )


@router.delete(
    "/{document_id}",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
    summary="Delete a document",
    description="Delete a document and all associated chunks from the system.",
)
async def delete_document(
    document_id: str,
    request: Request,
) -> DeleteResponse:
    """Delete document by ID."""
    trace_id = getattr(request.state, "trace_id", "")
    registry = get_document_registry()
    qdrant = get_qdrant_service()

    # Check if document exists
    doc = registry.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document with ID {document_id} not found",
                    "trace_id": trace_id,
                }
            },
        )

    # Delete from Qdrant
    try:
        qdrant.delete_by_document(document_id)
    except Exception:
        pass  # Continue even if Qdrant deletion fails

    # Delete from registry
    registry.delete(document_id)

    return DeleteResponse(success=True, message="Document deleted successfully")
