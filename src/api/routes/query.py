"""Query routes for Lexard API."""

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import (
    CitationChunk,
    ErrorResponse,
    QueryRequest,
    QueryResponse,
)

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
