"""
ERROR_RESPONSES.PY - Standardized Error Response Utilities

This module provides consistent error response formats across all API endpoints.

Usage:
    from core.error_responses import make_error, ErrorCode

    # Create error response
    return JSONResponse(
        status_code=400,
        content=make_error(
            code=ErrorCode.INVALID_SPORT,
            message="Sport 'soccer' is not supported",
            field="sport"
        )
    )

Response Format:
    {
        "status": "error",
        "error": "Sport 'soccer' is not supported",  # Legacy single error
        "errors": [
            {
                "code": "INVALID_SPORT",
                "message": "Sport 'soccer' is not supported",
                "field": "sport"
            }
        ],
        "timestamp": "2026-02-14T13:00:00-05:00"
    }
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class ErrorDetail:
    """Single error detail."""
    code: str
    message: str
    field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None fields."""
        result = {"code": self.code, "message": self.message}
        if self.field is not None:
            result["field"] = self.field
        return result


@dataclass
class ErrorResponse:
    """Standardized error response."""
    status: str = "error"
    error: Optional[str] = None  # Legacy single error (for backward compat)
    errors: List[ErrorDetail] = field(default_factory=list)
    request_id: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON response."""
        result: Dict[str, Any] = {"status": self.status}

        if self.error is not None:
            result["error"] = self.error

        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]

        if self.request_id is not None:
            result["request_id"] = self.request_id

        if self.timestamp is not None:
            result["timestamp"] = self.timestamp

        return result


class ErrorCode:
    """Standard error codes for consistent API responses."""

    # Authentication
    API_KEY_MISSING = "API_KEY_MISSING"
    API_KEY_INVALID = "API_KEY_INVALID"

    # Validation
    INVALID_SPORT = "INVALID_SPORT"
    INVALID_MARKET = "INVALID_MARKET"
    INVALID_DATE = "INVALID_DATE"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Resource
    NOT_FOUND = "NOT_FOUND"
    NO_DATA_AVAILABLE = "NO_DATA_AVAILABLE"

    # Rate Limiting
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # External APIs
    API_UNAVAILABLE = "API_UNAVAILABLE"
    API_TIMEOUT = "API_TIMEOUT"
    API_ERROR = "API_ERROR"

    # Internal
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def make_error(
    code: str,
    message: str,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
    include_timestamp: bool = True,
) -> Dict[str, Any]:
    """
    Create standardized error response dict.

    Args:
        code: Error code from ErrorCode class
        message: Human-readable error message
        field: Optional field name that caused the error
        request_id: Optional request correlation ID
        include_timestamp: Whether to include timestamp (default True)

    Returns:
        Dict suitable for JSONResponse content

    Example:
        >>> make_error(ErrorCode.INVALID_SPORT, "Unknown sport: soccer", field="sport")
        {
            "status": "error",
            "error": "Unknown sport: soccer",
            "errors": [{"code": "INVALID_SPORT", "message": "Unknown sport: soccer", "field": "sport"}],
            "timestamp": "2026-02-14T13:00:00-05:00"
        }
    """
    from core.time_et import format_as_of_et

    timestamp = format_as_of_et() if include_timestamp else None

    error_detail = ErrorDetail(code=code, message=message, field=field)

    response = ErrorResponse(
        error=message,  # Legacy compatibility
        errors=[error_detail],
        request_id=request_id,
        timestamp=timestamp,
    )

    return response.to_dict()


def make_errors(
    errors: List[Dict[str, str]],
    request_id: Optional[str] = None,
    include_timestamp: bool = True,
) -> Dict[str, Any]:
    """
    Create error response with multiple errors.

    Args:
        errors: List of error dicts with 'code', 'message', and optional 'field'
        request_id: Optional request correlation ID
        include_timestamp: Whether to include timestamp (default True)

    Returns:
        Dict suitable for JSONResponse content

    Example:
        >>> make_errors([
        ...     {"code": "INVALID_SPORT", "message": "Unknown sport", "field": "sport"},
        ...     {"code": "INVALID_DATE", "message": "Invalid date format", "field": "date"}
        ... ])
    """
    from core.time_et import format_as_of_et

    timestamp = format_as_of_et() if include_timestamp else None

    error_details = [
        ErrorDetail(
            code=e["code"],
            message=e["message"],
            field=e.get("field")
        )
        for e in errors
    ]

    # Use first error message for legacy 'error' field
    legacy_error = errors[0]["message"] if errors else None

    response = ErrorResponse(
        error=legacy_error,
        errors=error_details,
        request_id=request_id,
        timestamp=timestamp,
    )

    return response.to_dict()


# Export list
__all__ = [
    'ErrorDetail',
    'ErrorResponse',
    'ErrorCode',
    'make_error',
    'make_errors',
]
