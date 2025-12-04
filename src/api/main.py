"""Main FastAPI application for Lexard."""

from typing import Literal

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.logging import get_logger, setup_logging
from src.api.middleware import ErrorHandlerMiddleware, RequestIDMiddleware
from src.api.schemas import HealthResponse

# Initialize logging
setup_logging(level="info")
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Lexard",
    description="AI Contract Analyst - Sovereign B2B RAG Solution",
    version="0.1.0",
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


async def check_qdrant() -> Literal["connected", "disconnected"]:
    """Check if Qdrant is accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Qdrant uses root endpoint for health check
            response = await client.get("http://localhost:6333/")
            if response.status_code == 200:
                return "connected"
    except Exception:
        pass
    return "disconnected"


async def check_ollama() -> Literal["connected", "disconnected"]:
    """Check if Ollama is accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                return "connected"
    except Exception:
        pass
    return "disconnected"


@app.get("/health", response_model=HealthResponse)
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
