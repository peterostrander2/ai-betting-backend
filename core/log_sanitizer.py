"""
Centralized Log Sanitizer
=========================

Provides functions to redact sensitive data from logs, including:
- API keys and tokens
- Authorization headers
- Cookies
- Environment variable values
- Any token-like strings

Usage:
    from core.log_sanitizer import sanitize, sanitize_headers, sanitize_url

    # Sanitize a dictionary (headers, params, etc.)
    safe_headers = sanitize_headers(request.headers)

    # Sanitize a URL that may contain API keys
    safe_url = sanitize_url(url)

    # Sanitize arbitrary text
    safe_text = sanitize(some_string)
"""

import re
import os
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Headers that should always be redacted
SENSITIVE_HEADERS = frozenset({
    "x-api-key",
    "authorization",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "x-access-token",
    "bearer",
    "api-key",
    "apikey",
    "x-csrf-token",
    "x-xsrf-token",
})

# Query parameter names that should be redacted
SENSITIVE_PARAMS = frozenset({
    "apikey",
    "api_key",
    "key",
    "token",
    "access_token",
    "auth_token",
    "secret",
    "password",
    "pwd",
})

# Environment variable names that contain secrets (values should never be logged)
SENSITIVE_ENV_VARS = frozenset({
    "ODDS_API_KEY",
    "PLAYBOOK_API_KEY",
    "BALLDONTLIE_API_KEY",
    "BDL_API_KEY",
    "WEATHER_API_KEY",
    "OPENWEATHERMAP_API_KEY",
    "SERPAPI_KEY",
    "NEWSAPI_KEY",
    "TWITTER_BEARER",
    "WHOP_API_KEY",
    "API_AUTH_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "FRED_API_KEY",
    "FINNHUB_KEY",
    "ASTRONOMY_API_ID",
    "ASTRONOMY_API_SECRET",
})

# Redaction placeholder
REDACTED = "[REDACTED]"

# Regex patterns for token-like strings
TOKEN_PATTERNS = [
    # API keys (typically 20+ chars of alphanumeric)
    re.compile(r'\b[A-Za-z0-9]{20,}\b'),
    # Bearer tokens
    re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE),
    # JWT tokens (three base64 segments)
    re.compile(r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'),
    # Basic auth (base64 encoded)
    re.compile(r'Basic\s+[A-Za-z0-9+/=]+', re.IGNORECASE),
]


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates sensitive data."""
    key_lower = key.lower().replace("-", "_").replace(" ", "_")
    return (
        key_lower in SENSITIVE_HEADERS
        or key_lower in SENSITIVE_PARAMS
        or "key" in key_lower
        or "token" in key_lower
        or "secret" in key_lower
        or "password" in key_lower
        or "auth" in key_lower
        or "bearer" in key_lower
        or "cookie" in key_lower
    )


def _get_env_values_to_redact() -> set:
    """Get current values of sensitive environment variables."""
    values = set()
    for var_name in SENSITIVE_ENV_VARS:
        value = os.environ.get(var_name, "")
        if value and len(value) >= 8:  # Only redact non-trivial values
            values.add(value)
    return values


def sanitize_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    """
    Sanitize a headers dictionary, redacting sensitive values.

    Args:
        headers: Dictionary of headers (can be any Mapping-like object)

    Returns:
        New dictionary with sensitive values redacted
    """
    if not headers:
        return {}

    sanitized = {}
    for key, value in headers.items():
        key_str = str(key)
        if _is_sensitive_key(key_str):
            sanitized[key_str] = REDACTED
        else:
            sanitized[key_str] = str(value)

    return sanitized


def sanitize_dict(data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Recursively sanitize a dictionary, redacting sensitive values.

    Args:
        data: Dictionary to sanitize
        depth: Current recursion depth (max 5 to prevent infinite loops)

    Returns:
        New dictionary with sensitive values redacted
    """
    if not data or depth > 5:
        return data if data else {}

    sanitized = {}
    env_values = _get_env_values_to_redact()

    for key, value in data.items():
        key_str = str(key)

        if _is_sensitive_key(key_str):
            sanitized[key_str] = REDACTED
        elif isinstance(value, dict):
            sanitized[key_str] = sanitize_dict(value, depth + 1)
        elif isinstance(value, str):
            # Check if value matches a known secret
            if value in env_values:
                sanitized[key_str] = REDACTED
            else:
                sanitized[key_str] = value
        elif isinstance(value, (list, tuple)):
            sanitized[key_str] = [
                sanitize_dict(v, depth + 1) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            sanitized[key_str] = value

    return sanitized


def sanitize_url(url: str) -> str:
    """
    Sanitize a URL by redacting sensitive query parameters.

    Args:
        url: URL string that may contain API keys in query params

    Returns:
        URL with sensitive query params redacted
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # Parse query string
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Redact sensitive params
        sanitized_params = {}
        for key, values in params.items():
            if _is_sensitive_key(key):
                sanitized_params[key] = [REDACTED]
            else:
                sanitized_params[key] = values

        # Rebuild URL
        sanitized_query = urlencode(sanitized_params, doseq=True)
        sanitized_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            sanitized_query,
            parsed.fragment
        ))

        return sanitized_url

    except Exception:
        # If parsing fails, try basic redaction
        return _sanitize_text_basic(url)


def sanitize(text: str, redact_tokens: bool = True) -> str:
    """
    Sanitize arbitrary text by redacting sensitive patterns.

    Args:
        text: Text that may contain sensitive data
        redact_tokens: Whether to redact token-like strings (may have false positives)

    Returns:
        Text with sensitive data redacted
    """
    if not text:
        return text

    result = text

    # Redact known env var values
    env_values = _get_env_values_to_redact()
    for value in env_values:
        if value in result:
            result = result.replace(value, REDACTED)

    # Redact token patterns if requested
    if redact_tokens:
        for pattern in TOKEN_PATTERNS:
            result = pattern.sub(REDACTED, result)

    return result


def _sanitize_text_basic(text: str) -> str:
    """Basic text sanitization for when URL parsing fails."""
    result = text

    # Redact common API key patterns in URLs
    patterns = [
        (re.compile(r'apiKey=[^&\s]+', re.IGNORECASE), 'apiKey=' + REDACTED),
        (re.compile(r'api_key=[^&\s]+', re.IGNORECASE), 'api_key=' + REDACTED),
        (re.compile(r'key=[^&\s]+', re.IGNORECASE), 'key=' + REDACTED),
        (re.compile(r'token=[^&\s]+', re.IGNORECASE), 'token=' + REDACTED),
    ]

    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)

    return result


def safe_log_request(
    method: str,
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
) -> str:
    """
    Create a safe log string for an HTTP request.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        params: Query parameters (will be sanitized)
        headers: Request headers (will be sanitized)

    Returns:
        Safe string for logging
    """
    safe_url = sanitize_url(url)
    parts = [f"{method} {safe_url}"]

    if params:
        safe_params = sanitize_dict(params)
        # Only show non-redacted params
        visible_params = {k: v for k, v in safe_params.items() if v != REDACTED}
        if visible_params:
            parts.append(f"params={visible_params}")
        if any(v == REDACTED for v in safe_params.values()):
            parts.append("(some params redacted)")

    if headers:
        safe_headers = sanitize_headers(headers)
        # Don't log headers by default, just note if auth is present
        if any(v == REDACTED for v in safe_headers.values()):
            parts.append("(auth headers present)")

    return " ".join(parts)


def safe_log_response(
    status_code: int,
    url: str,
    response_text: Optional[str] = None,
    max_length: int = 200,
) -> str:
    """
    Create a safe log string for an HTTP response.

    Args:
        status_code: HTTP status code
        url: Request URL (will be sanitized)
        response_text: Response body text (will be truncated and sanitized)
        max_length: Maximum length of response text to include

    Returns:
        Safe string for logging
    """
    safe_url = sanitize_url(url)
    parts = [f"HTTP {status_code} from {safe_url}"]

    if response_text:
        truncated = response_text[:max_length]
        if len(response_text) > max_length:
            truncated += "..."
        # Sanitize the response text too
        safe_text = sanitize(truncated, redact_tokens=False)
        parts.append(f"response={safe_text}")

    return " ".join(parts)


# Convenience function for backward compatibility
def redact_sensitive(data: Union[str, Dict, None]) -> Union[str, Dict, None]:
    """
    Convenience function to sanitize either a string or dictionary.

    Args:
        data: String or dictionary to sanitize

    Returns:
        Sanitized data of the same type
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return sanitize_dict(data)
    if isinstance(data, str):
        return sanitize(data)
    return data
