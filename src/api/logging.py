"""JSON structured logging for Lexard API with performance metrics."""

import functools
import json
import logging
import sys
import time
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TypeVar

# Context variable for trace_id
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

# Type variables for generic decorator
F = TypeVar("F", bound=Callable[..., Any])


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "logger": record.name,
        }

        # Add trace_id if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "info") -> None:
    """Configure JSON structured logging.

    Args:
        level: Log level (debug, info, warning, error)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **extra: Any,
) -> None:
    """Log a message with extra context fields.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error)
        message: Log message
        **extra: Additional fields to include in log
    """
    log_method = getattr(logger, level.lower(), logger.info)
    record_factory = logging.getLogRecordFactory()

    def custom_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = record_factory(*args, **kwargs)
        record.extra_fields = extra  # type: ignore
        return record

    logging.setLogRecordFactory(custom_factory)
    log_method(message)
    logging.setLogRecordFactory(record_factory)


# Performance Metrics


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""

    count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    errors: int = 0

    def record(self, duration_ms: float, error: bool = False) -> None:
        """Record a single operation.

        Args:
            duration_ms: Operation duration in milliseconds
            error: Whether the operation resulted in an error
        """
        self.count += 1
        self.total_time_ms += duration_ms
        self.min_time_ms = min(self.min_time_ms, duration_ms)
        self.max_time_ms = max(self.max_time_ms, duration_ms)
        if error:
            self.errors += 1

    @property
    def avg_time_ms(self) -> float:
        """Average operation time in milliseconds."""
        return self.total_time_ms / self.count if self.count > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Error rate as a fraction (0.0 to 1.0)."""
        return self.errors / self.count if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "count": self.count,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "min_time_ms": round(self.min_time_ms, 2) if self.count > 0 else 0,
            "max_time_ms": round(self.max_time_ms, 2),
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
        }


class PerformanceMetrics:
    """Global performance metrics collector.

    Thread-safe singleton for collecting operation timing metrics.
    """

    _instance: Optional["PerformanceMetrics"] = None
    _metrics: Dict[str, OperationMetrics]

    def __new__(cls) -> "PerformanceMetrics":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._metrics = defaultdict(OperationMetrics)
        return cls._instance

    def record(
        self,
        operation: str,
        duration_ms: float,
        error: bool = False,
    ) -> None:
        """Record an operation timing.

        Args:
            operation: Name of the operation (e.g., "rag_query", "embedding")
            duration_ms: Duration in milliseconds
            error: Whether the operation resulted in an error
        """
        self._metrics[operation].record(duration_ms, error)

    def get_metrics(self, operation: str) -> OperationMetrics:
        """Get metrics for a specific operation.

        Args:
            operation: Name of the operation

        Returns:
            OperationMetrics for the operation
        """
        return self._metrics[operation]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary mapping operation names to their metrics
        """
        return {
            name: metrics.to_dict()
            for name, metrics in self._metrics.items()
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()


# Global metrics instance
_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Get the global performance metrics instance.

    Returns:
        PerformanceMetrics singleton instance
    """
    return _metrics


def timed(operation: str, log_level: str = "debug") -> Callable[[F], F]:
    """Decorator to time function execution and record metrics.

    Args:
        operation: Name of the operation for metrics
        log_level: Log level for timing output (default: debug)

    Returns:
        Decorated function that records execution time

    Example:
        @timed("rag_query")
        def process_query(query: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(func.__module__)
            start = time.perf_counter()
            error = False

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                error = True
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _metrics.record(operation, elapsed_ms, error)

                log_method = getattr(logger, log_level, logger.debug)
                log_with_context(
                    logger,
                    log_level,
                    f"{operation} completed",
                    operation=operation,
                    duration_ms=round(elapsed_ms, 2),
                    error=error,
                )

        return wrapper  # type: ignore

    return decorator


async def timed_async(
    operation: str,
    log_level: str = "debug",
) -> Callable[[F], F]:
    """Async version of timed decorator.

    Args:
        operation: Name of the operation for metrics
        log_level: Log level for timing output (default: debug)

    Returns:
        Decorated async function that records execution time
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(func.__module__)
            start = time.perf_counter()
            error = False

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                error = True
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _metrics.record(operation, elapsed_ms, error)

                log_with_context(
                    logger,
                    log_level,
                    f"{operation} completed",
                    operation=operation,
                    duration_ms=round(elapsed_ms, 2),
                    error=error,
                )

        return wrapper  # type: ignore

    return decorator
