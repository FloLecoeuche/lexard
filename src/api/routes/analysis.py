"""Analysis routes for Lexard API (summarize, compare, risks)."""

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import (
    CompareRequest,
    CompareResponse,
    DifferenceItem,
    ErrorResponse,
    RiskItem,
    RiskRequest,
    RiskResponse,
    SummarizeRequest,
    SummarizeResponse,
)

router = APIRouter(tags=["analysis"])


def get_document_registry():
    """Get document registry instance (lazy import to avoid circular imports)."""
    from src.db.sqlite import DocumentRegistry

    return DocumentRegistry()


def get_qdrant_service():
    """Get Qdrant service instance (lazy import to avoid circular imports)."""
    from src.db.qdrant import QdrantService

    return QdrantService()


def get_llm_client():
    """Get LLM client instance (lazy import to avoid circular imports)."""
    from src.config import get_settings
    from src.rag.llm import create_llm_client

    settings = get_settings()
    return create_llm_client(config=settings.llm)


def _verify_document_exists(registry, document_id: str, trace_id: str) -> None:
    """Verify that a document exists and is processed."""
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

    if doc.status != "processed":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Document is not ready for analysis (status: {doc.status})",
                    "trace_id": trace_id,
                }
            },
        )


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    },
    summary="Summarize a document",
    description="Generate a summary of a document with key points extracted.",
)
async def summarize_document(
    req: SummarizeRequest,
    request: Request,
) -> SummarizeResponse:
    """Generate document summary."""
    from src.agent.tools.summarizer import SummarizerTool

    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists
    registry = get_document_registry()
    _verify_document_exists(registry, req.document_id, trace_id)

    # Get services
    qdrant = get_qdrant_service()
    llm = get_llm_client()

    # Create summarizer tool
    summarizer = SummarizerTool(llm_client=llm, qdrant_service=qdrant)

    try:
        result = await summarizer.summarize(
            document_id=req.document_id,
            style=req.style,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": str(e),
                    "trace_id": trace_id,
                }
            },
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
                    "message": f"Summarization failed: {e}",
                    "trace_id": trace_id,
                }
            },
        )

    return SummarizeResponse(
        summary=result.executive_summary,
        key_points=result.key_points,
        word_count=result.word_count,
        language=result.language,
    )


@router.post(
    "/risks",
    response_model=RiskResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    },
    summary="Analyze document risks",
    description="Identify potential risks in a contract document.",
)
async def analyze_risks(
    req: RiskRequest,
    request: Request,
) -> RiskResponse:
    """Analyze document for risks."""
    from src.agent.tools.risk_detector import RiskDetectorTool

    trace_id = getattr(request.state, "trace_id", "")

    # Verify document exists
    registry = get_document_registry()
    _verify_document_exists(registry, req.document_id, trace_id)

    # Get services
    qdrant = get_qdrant_service()
    llm = get_llm_client()

    # Create risk detector tool
    risk_detector = RiskDetectorTool(llm_client=llm, qdrant_service=qdrant)

    try:
        result = await risk_detector.analyze(document_id=req.document_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": str(e),
                    "trace_id": trace_id,
                }
            },
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
                    "message": f"Risk analysis failed: {e}",
                    "trace_id": trace_id,
                }
            },
        )

    return RiskResponse(
        risks=[
            RiskItem(
                category=r.category.value,
                severity=r.severity.value,
                description=r.description,
                clause_excerpt=r.clause_excerpt,
                page=r.page,
                recommendation=r.recommendation,
            )
            for r in result.risks
        ],
        overall_risk_level=result.overall_risk_level.value,
        language=result.language,
    )


@router.post(
    "/compare",
    response_model=CompareResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
    summary="Compare two documents",
    description="Compare two documents and identify differences between them.",
)
async def compare_documents(
    req: CompareRequest,
    request: Request,
) -> CompareResponse:
    """Compare two documents."""
    from src.agent.tools.diff import DiffTool

    trace_id = getattr(request.state, "trace_id", "")

    # Verify both documents exist
    registry = get_document_registry()
    _verify_document_exists(registry, req.doc_a, trace_id)
    _verify_document_exists(registry, req.doc_b, trace_id)

    # Get Qdrant service
    qdrant = get_qdrant_service()

    # Create diff tool
    diff_tool = DiffTool(qdrant_service=qdrant)

    try:
        result = await diff_tool.compare(doc_a_id=req.doc_a, doc_b_id=req.doc_b)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": str(e),
                    "trace_id": trace_id,
                }
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Comparison failed: {e}",
                    "trace_id": trace_id,
                }
            },
        )

    return CompareResponse(
        differences=[
            DifferenceItem(
                section=d.section,
                doc_a_excerpt=d.doc_a_excerpt,
                doc_b_excerpt=d.doc_b_excerpt,
                change_type=d.change_type.value,
                similarity=d.similarity_score,
            )
            for d in result.differences
        ],
        overall_similarity=result.overall_similarity,
        language=result.language,
    )
