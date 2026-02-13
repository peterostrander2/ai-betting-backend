"""
TEST_STRUCTURED_LOGGING.PY - Tests for Structured Logging
==========================================================
v20.21 - Request correlation and JSON logging

Tests verify:
1. Request ID generation and context
2. JSON log format structure
3. Secret redaction in logs
4. Middleware request correlation

Run with: python -m pytest tests/test_structured_logging.py -v
"""

import json
import logging
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.structured_logging import (
    get_request_id,
    set_request_id,
    clear_request_id,
    generate_request_id,
    JSONFormatter,
    TextFormatter,
    configure_structured_logging,
)


class TestRequestIdContext:
    """Tests for request ID context management."""

    def test_generate_request_id_format(self):
        """Request IDs should have req- prefix and 12 hex chars."""
        request_id = generate_request_id()
        assert request_id.startswith("req-")
        assert len(request_id) == 16  # "req-" + 12 chars

    def test_set_and_get_request_id(self):
        """Should be able to set and retrieve request ID."""
        test_id = "req-test123456"
        set_request_id(test_id)
        assert get_request_id() == test_id
        clear_request_id()

    def test_clear_request_id(self):
        """Clearing should set request ID to None."""
        set_request_id("req-test123456")
        clear_request_id()
        assert get_request_id() is None

    def test_default_request_id_is_none(self):
        """Default request ID should be None."""
        clear_request_id()
        assert get_request_id() is None


class TestJSONFormatter:
    """Tests for JSON log formatter."""

    def test_json_format_structure(self):
        """JSON log entries should have required fields."""
        formatter = JSONFormatter(include_build_sha=False)

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Test message"
        assert parsed["line"] == 42

    def test_json_includes_request_id_when_set(self):
        """JSON should include request_id when set in context."""
        formatter = JSONFormatter(include_build_sha=False)

        set_request_id("req-abc123def456")

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["request_id"] == "req-abc123def456"
        clear_request_id()

    def test_json_excludes_request_id_when_not_set(self):
        """JSON should not have request_id when not set."""
        clear_request_id()
        formatter = JSONFormatter(include_build_sha=False)

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "request_id" not in parsed

    def test_json_redacts_sensitive_keys(self):
        """JSON formatter should redact sensitive field values."""
        formatter = JSONFormatter(include_build_sha=False)

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.api_key = "secret_value_123"

        output = formatter.format(record)
        parsed = json.loads(output)

        # api_key should be redacted
        assert parsed.get("api_key") == "[REDACTED]"

    def test_json_includes_extra_fields(self):
        """JSON should include extra fields from record."""
        formatter = JSONFormatter(include_build_sha=False)

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Pick scored",
            args=(),
            exc_info=None,
        )
        record.pick_id = "abc123"
        record.sport = "NBA"
        record.score = 8.5

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["pick_id"] == "abc123"
        assert parsed["sport"] == "NBA"
        assert parsed["score"] == 8.5


class TestTextFormatter:
    """Tests for text log formatter."""

    def test_text_format_structure(self):
        """Text formatter should produce readable output."""
        formatter = TextFormatter()

        set_request_id("req-test123456")

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_func"

        output = formatter.format(record)

        assert "[INFO]" in output
        assert "[req-test123456]" in output
        assert "test_logger" in output
        assert "Test message" in output

        clear_request_id()

    def test_text_format_without_request_id(self):
        """Text formatter should show '-' when no request ID."""
        clear_request_id()
        formatter = TextFormatter()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_func"

        output = formatter.format(record)

        assert "[-]" in output


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_json_format(self):
        """Should configure JSON format when specified."""
        # This mainly tests that it doesn't crash
        configure_structured_logging(level="DEBUG", format_type="json")

        logger = logging.getLogger("test_config_json")
        # Should not raise
        logger.info("Test message")

    def test_configure_text_format(self):
        """Should configure text format when specified."""
        configure_structured_logging(level="DEBUG", format_type="text")

        logger = logging.getLogger("test_config_text")
        # Should not raise
        logger.info("Test message")

    def test_configure_is_idempotent(self):
        """Calling configure multiple times should not add duplicate handlers."""
        # Call configure multiple times
        configure_structured_logging(level="INFO", format_type="json")
        configure_structured_logging(level="INFO", format_type="json")
        configure_structured_logging(level="DEBUG", format_type="text")

        root_logger = logging.getLogger()

        # Should only have one handler (not three)
        assert len(root_logger.handlers) == 1, \
            f"Expected 1 handler, got {len(root_logger.handlers)} (duplicate handlers on reconfigure)"
