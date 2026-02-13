"""
Structured Logging with Request Correlation - v20.21
=====================================================

Provides JSON-structured logging with request correlation for tracing.

Features:
1. JSON log format for production (parseable by log aggregators)
2. Request correlation via X-Request-ID header
3. Automatic request_id generation if not provided
4. Integration with log sanitizer for secret redaction
5. Thread-safe context management

Usage:
    from core.structured_logging import (
        configure_structured_logging,
        get_request_id,
        set_request_id,
        log_with_context,
        RequestCorrelationMiddleware,
    )

    # In main.py startup:
    configure_structured_logging()
    app.add_middleware(RequestCorrelationMiddleware)

    # In any module:
    logger = logging.getLogger(__name__)
    logger.info("Processing pick", extra={"pick_id": "abc123", "sport": "NBA"})
    # Output: {"timestamp": "...", "level": "INFO", "message": "Processing pick",
    #          "request_id": "req-xxx", "pick_id": "abc123", "sport": "NBA"}
"""

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Thread-safe context variable for request correlation
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Environment configuration
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    _request_id_ctx.set(request_id)


def clear_request_id() -> None:
    """Clear the request ID from context."""
    _request_id_ctx.set(None)


def generate_request_id() -> str:
    """Generate a new request ID."""
    return f"req-{uuid.uuid4().hex[:12]}"


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter with request correlation and secret redaction.

    Output format:
    {
        "timestamp": "2026-02-13T10:30:45.123456+00:00",
        "level": "INFO",
        "logger": "live_data_router",
        "message": "Processing request",
        "request_id": "req-abc123def456",
        "module": "live_data_router",
        "function": "get_best_bets",
        "line": 1234,
        ... extra fields ...
    }
    """

    # Fields to exclude from extra (already handled or internal)
    EXCLUDE_FIELDS = {
        "name", "msg", "args", "created", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs",
        "pathname", "process", "processName", "relativeCreated",
        "stack_info", "exc_info", "exc_text", "thread", "threadName",
        "message", "taskName",
    }

    def __init__(self, include_build_sha: bool = True):
        super().__init__()
        self.include_build_sha = include_build_sha
        self._build_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:8] or "local"

    def format(self, record: logging.LogRecord) -> str:
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request correlation if available
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id

        # Add location info
        log_entry["module"] = record.module
        log_entry["function"] = record.funcName
        log_entry["line"] = record.lineno

        # Add build SHA for tracing deployed version
        if self.include_build_sha:
            log_entry["build_sha"] = self._build_sha

        # Add extra fields (excluding internal logging fields)
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in self.EXCLUDE_FIELDS and not key.startswith("_"):
                    # Sanitize sensitive values
                    log_entry[key] = self._sanitize_value(key, value)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str, ensure_ascii=False)

    def _sanitize_value(self, key: str, value: Any) -> Any:
        """Sanitize sensitive values before logging."""
        # Import here to avoid circular imports
        try:
            from core.log_sanitizer import _is_sensitive_key, REDACTED

            if _is_sensitive_key(key):
                return REDACTED

            # Check nested dicts
            if isinstance(value, dict):
                return {
                    k: REDACTED if _is_sensitive_key(k) else v
                    for k, v in value.items()
                }
        except ImportError:
            pass

        return value


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter with request correlation.

    Output format:
    2026-02-13 10:30:45.123 [INFO] [req-abc123] live_data_router:get_best_bets:1234 - Processing request
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        request_id = get_request_id() or "-"

        # Build base message
        base = f"{timestamp} [{record.levelname}] [{request_id}] {record.name}:{record.funcName}:{record.lineno} - {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract or generate request IDs for correlation.

    - Extracts X-Request-ID from incoming request headers
    - Generates a new request ID if not present
    - Sets the request ID in response headers
    - Stores request ID in context for logging
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate request ID
        request_id = request.headers.get(self.HEADER_NAME)
        if not request_id:
            request_id = generate_request_id()

        # Set in context for logging
        set_request_id(request_id)

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response headers
            response.headers[self.HEADER_NAME] = request_id

            return response
        finally:
            # Clear context after request
            clear_request_id()


def configure_structured_logging(
    level: str = None,
    format_type: str = None,
    include_build_sha: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var.
        format_type: "json" or "text". Defaults to LOG_FORMAT env var.
        include_build_sha: Include build SHA in JSON logs.

    This should be called once at application startup, before any logging occurs.
    """
    level = level or LOG_LEVEL
    format_type = format_type or LOG_FORMAT

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler with appropriate formatter
    handler = logging.StreamHandler(sys.stdout)

    if format_type.lower() == "json":
        handler.setFormatter(JSONFormatter(include_build_sha=include_build_sha))
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy_logger in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra: Any,
) -> None:
    """
    Log a message with additional context fields.

    Args:
        logger: The logger to use
        level: Log level (e.g., logging.INFO)
        message: Log message
        **extra: Additional fields to include in the log entry

    Example:
        log_with_context(logger, logging.INFO, "Pick scored",
                        pick_id="abc123", sport="NBA", score=8.5)
    """
    logger.log(level, message, extra=extra)


# Convenience functions for common log levels
def log_info(logger: logging.Logger, message: str, **extra: Any) -> None:
    """Log an INFO message with context."""
    log_with_context(logger, logging.INFO, message, **extra)


def log_warning(logger: logging.Logger, message: str, **extra: Any) -> None:
    """Log a WARNING message with context."""
    log_with_context(logger, logging.WARNING, message, **extra)


def log_error(logger: logging.Logger, message: str, **extra: Any) -> None:
    """Log an ERROR message with context."""
    log_with_context(logger, logging.ERROR, message, **extra)


def log_debug(logger: logging.Logger, message: str, **extra: Any) -> None:
    """Log a DEBUG message with context."""
    log_with_context(logger, logging.DEBUG, message, **extra)
