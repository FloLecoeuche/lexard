"""API routes aggregation for Lexard."""

from fastapi import APIRouter

from src.api.routes.analysis import router as analysis_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.documents import router as documents_router
from src.api.routes.documents import upload_router
from src.api.routes.operations import router as operations_router
from src.api.routes.query import router as query_router

# Create main API router
api_router = APIRouter()

# Include all sub-routers
# Upload at root level (/upload)
api_router.include_router(upload_router)
# Documents management (/documents/*)
api_router.include_router(documents_router)
# Query (/query)
api_router.include_router(query_router)
# Analysis (/summarize, /compare, /risks)
api_router.include_router(analysis_router)
# Operations progress tracking (/operations/*)
api_router.include_router(operations_router)
# Analytics tracking (/analytics/*)
api_router.include_router(analytics_router)

__all__ = ["api_router"]
