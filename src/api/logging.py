"""JSON structured logging for Lexard API."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for trace_id
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


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
