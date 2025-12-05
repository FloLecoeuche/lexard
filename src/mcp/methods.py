"""MCP method implementations.

Provides methods for:
- list_documents: List all available documents
- analyze_document: Analyze a document (summary, risks, metadata)
- ask_question: Query a document with RAG
- compare: Compare two documents
"""

import logging
from typing import Any, Dict, List

from src.mcp.errors import ANALYSIS_FAILED, DOCUMENT_NOT_FOUND, make_error
from src.mcp.schemas import (
    AnalyzeDocumentParams,
    AnalyzeDocumentResult,
    AskQuestionParams,
    AskQuestionResult,
    CompareParams,
    CompareResult,
    DifferenceInfo,
    DocumentInfo,
    ListDocumentsResult,
)

logger = logging.getLogger(__name__)


def get_document_registry():
    """Get document registry instance (lazy import to avoid circular imports)."""
    from src.db.sqlite import DocumentRegistry

    return DocumentRegistry()


def get_qdrant_service():
    """Get Qdrant service instance (lazy import to avoid circular imports)."""
    from src.db.qdrant import QdrantService

    return QdrantService()


def get_llm_client():
    """Get Ollama LLM client instance (lazy import to avoid circular imports)."""
    from src.config import get_settings
    from src.rag.llm import OllamaClient

    settings = get_settings()
    return OllamaClient(config=settings.llm)


def get_rag_pipeline():
    """Get RAG pipeline instance (lazy import to avoid circular imports)."""
    from src.config import get_settings
    from src.db.qdrant import QdrantService
    from src.rag.context import ContextBuilder
    from src.rag.embeddings import EmbeddingService
    from src.rag.llm import OllamaClient
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
    llm_client = OllamaClient(config=settings.llm)

    return RAGPipeline(
        retriever=retriever,
        context_builder=context_builder,
        llm_client=llm_client,
        settings=settings,
    )


async def list_documents(params: Dict[str, Any] | None = None) -> ListDocumentsResult:
    """List all available documents.

    Args:
        params: Optional parameters (none required)

    Returns:
        ListDocumentsResult with list of documents
    """
    registry = get_document_registry()
    documents = registry.list_all(limit=100, offset=0)

    return ListDocumentsResult(
        documents=[
            DocumentInfo(
                id=doc.id,
                title=doc.title,
                uploaded_at=doc.uploaded_at,
                page_count=doc.page_count,
                version=doc.version,
            )
            for doc in documents
        ]
    )


async def analyze_document(params: AnalyzeDocumentParams) -> AnalyzeDocumentResult:
    """Analyze a document based on analysis type.

    Args:
        params: Analysis parameters with document_id and analysis_type

    Returns:
        AnalyzeDocumentResult with analysis text and optional citations

    Raises:
        Exception with DOCUMENT_NOT_FOUND error if document doesn't exist
        Exception with ANALYSIS_FAILED error if analysis fails
    """
    registry = get_document_registry()
    doc = registry.get(params.document_id)

    if not doc:
        error = make_error(
            DOCUMENT_NOT_FOUND, f"Document {params.document_id} not found"
        )
        raise ValueError(error.to_dict())

    if doc.status != "processed":
        error = make_error(
            ANALYSIS_FAILED, f"Document not ready (status: {doc.status})"
        )
        raise ValueError(error.to_dict())

    qdrant = get_qdrant_service()
    llm = get_llm_client()

    if params.analysis_type == "summary":
        from src.agent.tools.summarizer import SummarizerTool

        summarizer = SummarizerTool(llm_client=llm, qdrant_service=qdrant)

        try:
            result = await summarizer.summarize(
                document_id=params.document_id, style="executive"
            )
            return AnalyzeDocumentResult(
                analysis=result.executive_summary,
                risk_level=None,
                citations=result.key_points[:5],
            )
        except Exception as e:
            error = make_error(ANALYSIS_FAILED, str(e))
            raise ValueError(error.to_dict())

    elif params.analysis_type == "risks":
        from src.agent.tools.risk_detector import RiskDetectorTool

        risk_detector = RiskDetectorTool(llm_client=llm, qdrant_service=qdrant)

        try:
            result = await risk_detector.analyze(document_id=params.document_id)
            risk_descriptions = [r.description for r in result.risks[:5]]
            return AnalyzeDocumentResult(
                analysis=f"Found {len(result.risks)} risks. "
                + "; ".join(risk_descriptions),
                risk_level=result.overall_risk_level.value,
                citations=[r.clause_excerpt for r in result.risks[:5]],
            )
        except Exception as e:
            error = make_error(ANALYSIS_FAILED, str(e))
            raise ValueError(error.to_dict())

    elif params.analysis_type == "metadata":
        return AnalyzeDocumentResult(
            analysis=f"Document '{doc.title}' ({doc.filename}): "
            f"{doc.page_count or 'unknown'} pages, "
            f"{doc.chunk_count or 'unknown'} chunks, "
            f"version {doc.version}, status: {doc.status}",
            risk_level=None,
            citations=[],
        )

    else:
        error = make_error(
            ANALYSIS_FAILED, f"Unknown analysis type: {params.analysis_type}"
        )
        raise ValueError(error.to_dict())


async def ask_question(params: AskQuestionParams) -> AskQuestionResult:
    """Ask a question about a document using RAG.

    Args:
        params: Question parameters with document_id and question

    Returns:
        AskQuestionResult with answer, citations, and confidence

    Raises:
        Exception with DOCUMENT_NOT_FOUND error if document doesn't exist
        Exception with ANALYSIS_FAILED error if query fails
    """
    registry = get_document_registry()
    doc = registry.get(params.document_id)

    if not doc:
        error = make_error(
            DOCUMENT_NOT_FOUND, f"Document {params.document_id} not found"
        )
        raise ValueError(error.to_dict())

    if doc.status != "processed":
        error = make_error(
            ANALYSIS_FAILED, f"Document not ready (status: {doc.status})"
        )
        raise ValueError(error.to_dict())

    try:
        pipeline = get_rag_pipeline()
        result = pipeline.query(
            question=params.question,
            document_id=params.document_id,
        )
    except Exception as e:
        error = make_error(ANALYSIS_FAILED, f"Query failed: {e}")
        raise ValueError(error.to_dict())

    return AskQuestionResult(
        answer=result.answer,
        citation_chunks=[c.content for c in result.citation_chunks],
        confidence=result.confidence.value,
    )


async def compare(params: CompareParams) -> CompareResult:
    """Compare two documents.

    Args:
        params: Compare parameters with doc_a and doc_b IDs

    Returns:
        CompareResult with differences between documents

    Raises:
        Exception with DOCUMENT_NOT_FOUND error if document doesn't exist
        Exception with ANALYSIS_FAILED error if comparison fails
    """
    registry = get_document_registry()

    # Verify both documents exist
    for doc_id in [params.doc_a, params.doc_b]:
        doc = registry.get(doc_id)
        if not doc:
            error = make_error(DOCUMENT_NOT_FOUND, f"Document {doc_id} not found")
            raise ValueError(error.to_dict())
        if doc.status != "processed":
            error = make_error(
                ANALYSIS_FAILED, f"Document {doc_id} not ready (status: {doc.status})"
            )
            raise ValueError(error.to_dict())

    from src.agent.tools.diff import DiffTool

    qdrant = get_qdrant_service()
    diff_tool = DiffTool(qdrant_service=qdrant)

    try:
        result = await diff_tool.compare(doc_a_id=params.doc_a, doc_b_id=params.doc_b)
    except Exception as e:
        error = make_error(ANALYSIS_FAILED, f"Comparison failed: {e}")
        raise ValueError(error.to_dict())

    return CompareResult(
        differences=[
            DifferenceInfo(
                section=d.section,
                doc_a_content=d.doc_a_excerpt,
                doc_b_content=d.doc_b_excerpt,
                similarity_score=d.similarity_score,
            )
            for d in result.differences
        ]
    )


# Method registry for dispatch
MCP_METHODS = {
    "list_documents": list_documents,
    "analyze_document": analyze_document,
    "ask_question": ask_question,
    "compare": compare,
}
