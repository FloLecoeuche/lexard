"""Middleware for Lexard API."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.exceptions import LexardError
from src.api.logging import get_logger, log_with_context, trace_id_var

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that adds a unique trace_id to each request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract trace_id
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

        # Set trace_id in context var for logging
        token = trace_id_var.set(trace_id)

        # Store trace_id in request state for access in handlers
        request.state.trace_id = trace_id

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request completion
            log_with_context(
                logger,
                "info",
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id
            return response

        finally:
            trace_id_var.reset(token)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware that catches exceptions and returns consistent error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except LexardError as exc:
            trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

            log_with_context(
                logger,
                "error",
                f"handled_error: {exc.message}",
                error_code=exc.code,
                status_code=exc.status_code,
            )

            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "trace_id": trace_id,
                    }
                },
                headers={"X-Trace-ID": trace_id},
            )
        except Exception as exc:
            trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

            log_with_context(
                logger,
                "error",
                f"unhandled_error: {str(exc)}",
                error_type=type(exc).__name__,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An internal error occurred",
                        "trace_id": trace_id,
                    }
                },
                headers={"X-Trace-ID": trace_id},
            )
