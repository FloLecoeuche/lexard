"""Main FastAPI application for Lexard."""

from functools import lru_cache
from typing import Literal

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.logging import get_logger, get_metrics, setup_logging
from src.api.middleware import ErrorHandlerMiddleware, RequestIDMiddleware
from src.api.routes import api_router
from src.api.routes.static import router as static_router
from src.api.schemas import GuardrailsMetricsResponse, HealthResponse
from src.config import get_settings
from src.guardrails import GuardrailsPipeline
from src.mcp import mcp_router

# Initialize logging
setup_logging(level="info")
logger = get_logger(__name__)

# Create FastAPI app with OpenAPI metadata
app = FastAPI(
    title="Lexard",
    description="""
**Lexard** is a sovereign, self-hosted B2B RAG solution for contract analysis.

## Features

- **Document Ingestion**: Upload PDF, DOCX, or TXT documents for analysis
- **RAG Queries**: Ask questions about documents with cited sources
- **Summarization**: Generate executive or detailed summaries
- **Risk Analysis**: Identify legal, financial, and operational risks
- **Document Comparison**: Compare two documents for differences

## API Sections

- **Documents**: Upload, list, view, and delete documents
- **Query**: Ask questions about specific documents
- **Analysis**: Summarize, analyze risks, and compare documents
""",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Service health and status endpoints",
        },
        {
            "name": "documents",
            "description": "Document upload, listing, and management",
        },
        {
            "name": "query",
            "description": "RAG-powered question answering with citations",
        },
        {
            "name": "analysis",
            "description": "Document summarization, risk analysis, and comparison",
        },
        {
            "name": "mcp",
            "description": "Model Context Protocol JSON-RPC 2.0 endpoint",
        },
    ],
)

# Add middleware (order matters: first added = outermost)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)
app.include_router(mcp_router)
app.include_router(static_router)


async def check_qdrant() -> Literal["connected", "disconnected"]:
    """Check if Qdrant is accessible."""
    try:
        settings = get_settings()
        qdrant_url = f"http://{settings.qdrant.host}:{settings.qdrant.port}/"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(qdrant_url)
            if response.status_code == 200:
                return "connected"
    except Exception:
        pass
    return "disconnected"


async def check_ollama() -> Literal["connected", "disconnected"]:
    """Check if Ollama is accessible."""
    try:
        settings = get_settings()
        ollama_url = f"{settings.llm.base_url}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_url)
            if response.status_code == 200:
                return "connected"
    except Exception:
        pass
    return "disconnected"


# Global guardrails pipeline instance for metrics tracking
_guardrails_pipeline: GuardrailsPipeline | None = None


def get_guardrails_pipeline() -> GuardrailsPipeline:
    """Get the global guardrails pipeline instance.

    Creates a new instance on first call.
    """
    global _guardrails_pipeline
    if _guardrails_pipeline is None:
        _guardrails_pipeline = GuardrailsPipeline()
    return _guardrails_pipeline


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Check service health and status of external dependencies (Qdrant, Ollama).",
)
async def health() -> HealthResponse:
    """Check service health and dependencies."""
    qdrant_status = await check_qdrant()
    ollama_status = await check_ollama()

    # Determine overall status
    services = {
        "qdrant": qdrant_status,
        "ollama": ollama_status,
    }

    all_connected = all(s == "connected" for s in services.values())
    any_connected = any(s == "connected" for s in services.values())

    if all_connected:
        status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    elif any_connected:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version="0.1.0",
        services=services,
    )


@app.get(
    "/guardrails/metrics",
    response_model=GuardrailsMetricsResponse,
    tags=["health"],
    summary="Guardrails metrics",
    description="Get guardrails pipeline metrics including rejection counts by type.",
)
async def guardrails_metrics() -> GuardrailsMetricsResponse:
    """Get guardrails metrics for monitoring."""
    pipeline = get_guardrails_pipeline()
    metrics = pipeline.metrics

    return GuardrailsMetricsResponse(
        total_inputs=metrics.total_inputs,
        total_outputs=metrics.total_outputs,
        injection_blocks=metrics.injection_blocks,
        hallucination_blocks=metrics.hallucination_blocks,
        schema_failures=metrics.schema_failures,
        pii_redactions=metrics.pii_redactions,
        input_block_rate=metrics.input_block_rate,
        output_block_rate=metrics.output_block_rate,
    )


@app.get(
    "/performance/metrics",
    tags=["health"],
    summary="Performance metrics",
    description="Get performance metrics including operation timings and error rates.",
)
async def performance_metrics() -> dict:
    """Get performance metrics for monitoring.

    Returns metrics for all tracked operations including:
    - count: Total number of operations
    - avg_time_ms: Average execution time
    - min_time_ms: Minimum execution time
    - max_time_ms: Maximum execution time
    - error_rate: Fraction of operations that resulted in errors
    """
    metrics = get_metrics()
    return {
        "metrics": metrics.get_all_metrics(),
    }
