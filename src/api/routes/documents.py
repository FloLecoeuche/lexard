"""Document management routes for Lexard API."""

import asyncio
import hashlib
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from src.api.exceptions import DocumentParseError
from src.api.progress import ProcessingStage, progress_tracker
from src.api.schemas import (
    DeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

# Router for /documents/* endpoints
router = APIRouter(prefix="/documents", tags=["documents"])

# Separate router for /upload at root level
upload_router = APIRouter(tags=["documents"])

# Maximum file size in bytes (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# MIME type mapping for document preview
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}


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


async def _process_document_with_progress(
    content: bytes,
    filename: str,
    file_hash: str,
    task_id: str,
) -> None:
    """Process document and emit progress updates.

    Args:
        content: File content
        filename: Original filename
        file_hash: SHA256 hash of file
        task_id: Progress task ID
    """
    from src.config import get_settings
    from src.rag.chunking import Chunker
    from src.rag.extractors.factory import get_extractor

    try:
        # Stage 1: Parsing (0-20%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.PARSING,
            0.0,
            f"Parsing {filename}...",
        )

        # Run blocking extraction in thread to not block event loop
        def do_extraction():
            suffix = Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)
            try:
                extractor = get_extractor(tmp_path)
                return extractor.extract(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)

        extraction_result = await asyncio.to_thread(do_extraction)

        await progress_tracker.update(
            task_id,
            ProcessingStage.PARSING,
            0.2,
            f"Extracted {len(extraction_result.full_text)} characters from {extraction_result.total_pages} pages",
        )

        # Get title from filename
        title = Path(filename).stem

        # Initialize services
        registry = get_document_registry()
        qdrant = get_qdrant_service()
        embedding_service = get_embedding_service()
        settings = get_settings()

        # Create document record (DB operations in thread)
        def do_db_setup():
            doc = registry.create(
                title=title,
                filename=filename,
                file_hash=file_hash,
            )
            registry.store_file_content(doc.id, content)
            return doc

        doc = await asyncio.to_thread(do_db_setup)

        # Stage 2: Chunking (20-40%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.CHUNKING,
            0.2,
            "Splitting into chunks...",
        )

        def do_chunking():
            chunker = Chunker(
                chunk_size=settings.chunking.size,
                overlap=settings.chunking.overlap,
            )
            return chunker.chunk(extraction_result.pages)

        chunks = await asyncio.to_thread(do_chunking)

        await progress_tracker.update(
            task_id,
            ProcessingStage.CHUNKING,
            0.4,
            f"Created {len(chunks)} chunks",
        )

        # Stage 3: Embedding (40-80%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.EMBEDDING,
            0.4,
            f"Generating embeddings for {len(chunks)} chunks...",
        )

        # Generate embeddings (CPU-bound, run in thread)
        embeddings = await asyncio.to_thread(embedding_service.embed_chunks, chunks)

        await progress_tracker.update(
            task_id,
            ProcessingStage.EMBEDDING,
            0.8,
            f"Generated {len(embeddings)} embeddings",
        )

        # Stage 4: Indexing (80-100%)
        await progress_tracker.update(
            task_id,
            ProcessingStage.INDEXING,
            0.8,
            "Indexing in vector database...",
        )

        # Run Qdrant operations in thread
        def do_indexing():
            qdrant.ensure_collection()
            qdrant.upsert_chunks(
                chunks=chunks,
                embeddings=embeddings,
                document_id=doc.id,
                source_title=title,
            )
            registry.update_status(
                doc.id,
                status="processed",
                page_count=extraction_result.total_pages,
                chunk_count=len(chunks),
            )

        await asyncio.to_thread(do_indexing)

        # Mark complete
        await progress_tracker.mark_complete(
            task_id,
            "Document uploaded successfully!",
            document_id=doc.id,
        )

        # Schedule cleanup
        asyncio.create_task(progress_tracker.cleanup(task_id))

    except Exception as e:
        logger.error(f"Upload failed for task {task_id}: {e}")
        await progress_tracker.mark_failed(task_id, str(e))


@upload_router.post(
    "/upload",
    responses={
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "Unsupported file format"},
    },
    summary="Upload a document with progress tracking",
    description="Upload a PDF, DOCX, or TXT document for analysis. Returns task_id for progress tracking.",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file (PDF, DOCX, or TXT)"),
) -> dict:
    """Upload and process a new document with progress tracking."""
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

    # Create progress task
    task_id = progress_tracker.create_task(f"Uploading {file.filename}...")

    # Use asyncio.create_task for true concurrent execution
    # This allows SSE to stream progress updates in real-time
    # (BackgroundTasks runs AFTER response, blocking the event loop)
    asyncio.create_task(
        _process_document_with_progress(
            content,
            file.filename,  # type: ignore[arg-type]
            file_hash,
            task_id,
        )
    )

    return {
        "task_id": task_id,
        "filename": file.filename,
        "progress_url": f"/upload/progress/{task_id}",
        "status_url": f"/upload/status/{task_id}",
    }


@upload_router.get(
    "/upload/progress/{task_id}",
    summary="Stream upload progress via SSE",
    description="Stream real-time progress updates for a document upload via Server-Sent Events.",
)
async def stream_upload_progress(task_id: str):
    """Stream real-time progress updates via Server-Sent Events.

    Args:
        task_id: Progress task identifier

    Returns:
        SSE stream of progress updates
    """

    async def event_generator():
        """Generate SSE events from progress updates."""
        async for update in progress_tracker.subscribe(task_id):
            yield {
                "event": "progress",
                "data": json.dumps(update.to_dict()),
            }

    return EventSourceResponse(event_generator())


@upload_router.get(
    "/upload/status/{task_id}",
    responses={404: {"model": ErrorResponse, "description": "Task not found"}},
    summary="Get upload status",
    description="Get current upload status (polling alternative to SSE).",
)
async def get_upload_status(task_id: str, request: Request) -> dict:
    """Get current upload status (polling alternative to SSE).

    Args:
        task_id: Progress task identifier

    Returns:
        Current progress status

    Raises:
        HTTPException: If task not found
    """
    trace_id = getattr(request.state, "trace_id", "")
    status = progress_tracker.get_status(task_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": f"Task {task_id} not found",
                    "trace_id": trace_id,
                }
            },
        )
    return status.to_dict()


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


@router.get(
    "/{document_id}/file",
    responses={404: {"model": ErrorResponse, "description": "Document or file not found"}},
    summary="Get document file",
    description="Serve the original document file for preview.",
)
async def get_document_file(
    document_id: str,
    request: Request,
) -> Response:
    """Serve original document file for preview.

    Args:
        document_id: Document UUID

    Returns:
        Original file with appropriate Content-Type

    Raises:
        HTTPException: If document or file not found
    """
    trace_id = getattr(request.state, "trace_id", "")
    registry = get_document_registry()

    # Get document metadata
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

    # Get file content from database
    content = registry.get_file_content(document_id)
    if not content:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": "File content not available for this document",
                    "trace_id": trace_id,
                }
            },
        )

    # Determine MIME type from filename
    suffix = Path(doc.filename).suffix.lower()
    media_type = MIME_TYPES.get(suffix, "application/octet-stream")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )
