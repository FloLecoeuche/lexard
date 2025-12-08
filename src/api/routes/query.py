"""Query routes for Lexard API."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.api.progress import get_operation_tracker
from src.api.schemas import (
    AsyncOperationResponse,
    CitationChunk,
    ErrorResponse,
    QueryRequest,
    QueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


def get_document_registry():
    """Get document registry instance (lazy import to avoid circular imports)."""
    from src.db.sqlite import DocumentRegistry

    return DocumentRegistry()


def get_rag_pipeline():
    """Get RAG pipeline instance (lazy import to avoid circular imports)."""
    from src.config import get_settings
    from src.db.qdrant import QdrantService
    from src.rag.context import ContextBuilder
    from src.rag.embeddings import EmbeddingService
    from src.rag.llm import create_llm_client
    from src.rag.pipeline import RAGPipeline
    from src.rag.retriever import Retriever

    settings = get_settings()
    embedding_service = EmbeddingService(
        model_name=settings.embeddings.model,
        device=settings.embeddings.device,
        query_prefix=settings.embeddings.query_prefix,
        document_prefix=settings.embeddings.document_prefix,
    )
    qdrant_service = QdrantService()
    retriever = Retriever(
        embedding_service=embedding_service,
        qdrant_service=qdrant_service
    )
    context_builder = ContextBuilder()
    llm_client = create_llm_client(config=settings.llm)

    return RAGPipeline(
        retriever=retriever,
        context_builder=context_builder,
        llm_client=llm_client,
        settings=settings,
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    },
    summary="Query a document",
    description="Ask a question about a specific document and receive an answer with citations.",
)
async def query_document(
    query: QueryRequest,
    request: Request,
) -> QueryResponse:
    """Query a document using RAG."""
    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists
    registry = get_document_registry()
    doc = registry.get(query.document_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document with ID {query.document_id} not found",
                    "trace_id": trace_id,
                }
            },
        )

    if doc.status != "processed":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Document is not ready for queries (status: {doc.status})",
                    "trace_id": trace_id,
                }
            },
        )

    # Execute RAG query
    try:
        pipeline = get_rag_pipeline()
        result = pipeline.query(
            question=query.question,
            document_id=query.document_id,
        )
    except Exception as e:
        if "Ollama" in str(e) or "connection" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "LLM service is unavailable",
                        "trace_id": trace_id,
                    }
                },
            )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Query failed: {e}",
                    "trace_id": trace_id,
                }
            },
        )

    return QueryResponse(
        answer=result.answer,
        citation_chunks=[
            CitationChunk(
                content=c.content,
                page=c.page,
                chunk_index=c.chunk_index,
                score=c.score,
            )
            for c in result.citation_chunks
        ],
        confidence=result.confidence.value,
        language=result.language,
    )


async def _execute_query_with_progress(
    operation_id: str,
    question: str,
    document_id: str,
) -> None:
    """Background task to execute query with progress tracking.

    Args:
        operation_id: Operation ID for progress tracking
        question: User's question
        document_id: Document to query
    """
    tracker = get_operation_tracker()
    pipeline = get_rag_pipeline()

    try:
        # Use the progress-aware query method
        result = await pipeline._query_with_events(
            question=question,
            document_id=document_id,
            language=None,  # Auto-detect
            tracker=tracker,
            operation_id=operation_id,
        )
        # Convert to dict for storage
        result_dict = {
            "answer": result.answer,
            "citation_chunks": [
                {
                    "content": c.content,
                    "page": c.page,
                    "chunk_index": c.chunk_index,
                    "score": c.score,
                }
                for c in result.citation_chunks
            ],
            "confidence": result.confidence.value,
            "language": result.language,
        }
        await tracker.complete(operation_id, result_dict)
    except Exception as e:
        logger.error(f"Query failed for operation {operation_id}: {e}")
        await tracker.fail(operation_id, str(e))


@router.post(
    "/query/async",
    response_model=AsyncOperationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
    summary="Query a document (async with progress)",
    description="""
Start an async query operation with progress tracking.

Returns an operation_id immediately. Subscribe to `/operations/{operation_id}/progress`
for real-time progress updates via Server-Sent Events.

Get the final result from `/operations/{operation_id}/result` after completion.
""",
)
async def query_document_async(
    query: QueryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> AsyncOperationResponse:
    """Query a document using RAG with async progress tracking."""
    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists (fast check before starting operation)
    registry = get_document_registry()
    doc = registry.get(query.document_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document with ID {query.document_id} not found",
                    "trace_id": trace_id,
                }
            },
        )

    if doc.status != "processed":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Document is not ready for queries (status: {doc.status})",
                    "trace_id": trace_id,
                }
            },
        )

    # Start operation and get ID
    tracker = get_operation_tracker()
    operation_id = await tracker.start("query")

    logger.info(
        f"Starting async query operation {operation_id}",
        extra={
            "operation_id": operation_id,
            "document_id": query.document_id,
            "trace_id": trace_id,
        },
    )

    # Start background processing
    background_tasks.add_task(
        _execute_query_with_progress,
        operation_id=operation_id,
        question=query.question,
        document_id=query.document_id,
    )

    return AsyncOperationResponse(
        operation_id=operation_id,
        status="processing",
        message="Query started. Subscribe to /operations/{operation_id}/progress for updates.",
    )
