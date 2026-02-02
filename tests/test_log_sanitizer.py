"""
Tests for core/log_sanitizer.py

Ensures sensitive data is properly redacted from logs.
"""

import os
import pytest
from core.log_sanitizer import (
    sanitize_headers,
    sanitize_dict,
    sanitize_url,
    sanitize,
    safe_log_request,
    safe_log_response,
    REDACTED,
)


class TestSanitizeHeaders:
    """Tests for header sanitization."""

    def test_redacts_x_api_key(self):
        """X-API-Key header should be redacted."""
        headers = {"X-API-Key": "secret-key-12345", "Content-Type": "application/json"}
        result = sanitize_headers(headers)
        assert result["X-API-Key"] == REDACTED
        assert result["Content-Type"] == "application/json"

    def test_redacts_authorization(self):
        """Authorization header should be redacted."""
        headers = {"Authorization": "Bearer abc123xyz", "Accept": "application/json"}
        result = sanitize_headers(headers)
        assert result["Authorization"] == REDACTED
        assert result["Accept"] == "application/json"

    def test_redacts_cookie(self):
        """Cookie headers should be redacted."""
        headers = {"Cookie": "session=abc123", "Set-Cookie": "token=xyz789"}
        result = sanitize_headers(headers)
        assert result["Cookie"] == REDACTED
        assert result["Set-Cookie"] == REDACTED

    def test_case_insensitive(self):
        """Header names should be matched case-insensitively."""
        headers = {"x-api-key": "secret", "AUTHORIZATION": "Bearer token"}
        result = sanitize_headers(headers)
        assert result["x-api-key"] == REDACTED
        assert result["AUTHORIZATION"] == REDACTED

    def test_empty_headers(self):
        """Empty headers should return empty dict."""
        assert sanitize_headers({}) == {}
        assert sanitize_headers(None) == {}


class TestSanitizeDict:
    """Tests for dictionary sanitization."""

    def test_redacts_api_key_in_params(self):
        """API key in query params should be redacted."""
        params = {"apiKey": "my-secret-key", "sport": "nba", "region": "us"}
        result = sanitize_dict(params)
        assert result["apiKey"] == REDACTED
        assert result["sport"] == "nba"
        assert result["region"] == "us"

    def test_redacts_nested_secrets(self):
        """Nested dictionaries should be sanitized recursively."""
        data = {
            "config": {
                "api_key": "secret123",
                "endpoint": "https://api.example.com"
            },
            "headers": {
                "Authorization": "Bearer token"
            }
        }
        result = sanitize_dict(data)
        assert result["config"]["api_key"] == REDACTED
        assert result["config"]["endpoint"] == "https://api.example.com"
        assert result["headers"]["Authorization"] == REDACTED

    def test_handles_lists(self):
        """Lists should be processed correctly."""
        data = {
            "items": [
                {"token": "secret1", "name": "item1"},
                {"token": "secret2", "name": "item2"},
            ]
        }
        result = sanitize_dict(data)
        assert result["items"][0]["token"] == REDACTED
        assert result["items"][0]["name"] == "item1"
        assert result["items"][1]["token"] == REDACTED


class TestSanitizeUrl:
    """Tests for URL sanitization."""

    def test_redacts_apikey_param(self):
        """apiKey query param should be redacted."""
        url = "https://api.example.com/data?apiKey=secret123&sport=nba"
        result = sanitize_url(url)
        # URL encoding may escape brackets: [REDACTED] -> %5BREDACTED%5D
        assert "secret123" not in result
        assert "REDACTED" in result  # May be URL-encoded
        assert "sport=nba" in result

    def test_redacts_api_key_param(self):
        """api_key query param should be redacted."""
        url = "https://api.example.com/data?api_key=secret456&region=us"
        result = sanitize_url(url)
        assert "secret456" not in result
        assert "REDACTED" in result  # May be URL-encoded

    def test_redacts_token_param(self):
        """token query param should be redacted."""
        url = "https://api.example.com/auth?token=jwt123xyz&user=test"
        result = sanitize_url(url)
        assert "jwt123xyz" not in result
        assert "REDACTED" in result  # May be URL-encoded

    def test_preserves_path(self):
        """URL path should be preserved."""
        url = "https://api.example.com/v1/sports/nba/odds?apiKey=secret"
        result = sanitize_url(url)
        assert "/v1/sports/nba/odds" in result

    def test_empty_url(self):
        """Empty URL should return empty."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) is None


class TestSanitizeText:
    """Tests for text sanitization."""

    def test_redacts_bearer_token(self):
        """Bearer tokens should be redacted."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        result = sanitize(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_redacts_basic_auth(self):
        """Basic auth tokens should be redacted."""
        text = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        result = sanitize(text)
        assert "dXNlcjpwYXNzd29yZA==" not in result

    def test_redacts_long_alphanumeric(self):
        """Long alphanumeric strings (API keys) should be redacted."""
        text = "Using API key: abc123def456ghi789jkl012mno345"
        result = sanitize(text, redact_tokens=True)
        assert "abc123def456ghi789jkl012mno345" not in result


class TestSafeLogRequest:
    """Tests for safe request logging."""

    def test_safe_log_request_redacts_params(self):
        """Request log should redact sensitive params."""
        log = safe_log_request(
            method="GET",
            url="https://api.example.com/data",
            params={"apiKey": "secret", "sport": "nba"},
            headers={"Authorization": "Bearer token"}
        )
        assert "secret" not in log
        assert "sport" in log or "nba" in log
        assert "(auth headers present)" in log
        assert "(some params redacted)" in log

    def test_safe_log_request_no_headers(self):
        """Request log without headers should work."""
        log = safe_log_request(
            method="GET",
            url="https://api.example.com/data?apiKey=secret",
            params=None,
            headers=None
        )
        assert "secret" not in log


class TestSafeLogResponse:
    """Tests for safe response logging."""

    def test_safe_log_response_truncates(self):
        """Response log should truncate long text."""
        long_text = "x" * 500
        log = safe_log_response(
            status_code=200,
            url="https://api.example.com/data?apiKey=secret",
            response_text=long_text,
            max_length=100
        )
        assert "secret" not in log
        assert "..." in log
        assert len(log) < 500


class TestEnvVarRedaction:
    """Tests for environment variable value redaction."""

    def test_redacts_env_var_values(self, monkeypatch):
        """Known env var values should be redacted from text."""
        # Set a test env var
        monkeypatch.setenv("ODDS_API_KEY", "test-odds-key-12345")

        # Force reload of env values
        from core.log_sanitizer import _get_env_values_to_redact
        env_values = _get_env_values_to_redact()

        assert "test-odds-key-12345" in env_values

        # Sanitize text containing the value
        text = "Fetching from API with key test-odds-key-12345 for NBA"
        result = sanitize(text)
        assert "test-odds-key-12345" not in result
