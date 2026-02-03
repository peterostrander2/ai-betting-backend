"""Tests for HTTP retry wrapper"""
import pytest
from unittest.mock import Mock, patch
import requests
from core.http_retry import (
    request_json_with_retry,
    get_json_with_retry,
    RETRYABLE_STATUS_CODES
)


def test_successful_request_first_try():
    """Test successful request on first attempt"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "success"}
    
    with patch('requests.request', return_value=mock_response) as mock_req:
        ok, status, data, error = get_json_with_retry("https://example.com/api")
        
        assert ok is True
        assert status == 200
        assert data == {"data": "success"}
        assert error is None
        assert mock_req.call_count == 1


def test_retry_on_502_then_success():
    """Test retry on 502, then success"""
    mock_fail = Mock()
    mock_fail.status_code = 502
    
    mock_success = Mock()
    mock_success.status_code = 200
    mock_success.json.return_value = {"data": "success"}
    
    with patch('requests.request', side_effect=[mock_fail, mock_fail, mock_success]) as mock_req:
        ok, status, data, error = get_json_with_retry("https://example.com/api")
        
        assert ok is True
        assert status == 200
        assert data == {"data": "success"}
        assert mock_req.call_count == 3


def test_no_retry_on_400():
    """Test no retry on 400 (hard error)"""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    
    with patch('requests.request', return_value=mock_response) as mock_req:
        ok, status, data, error = get_json_with_retry("https://example.com/api")
        
        assert ok is False
        assert status == 400
        assert data is None
        assert "400" in error
        assert mock_req.call_count == 1


def test_retry_on_timeout():
    """Test retry on timeout"""
    with patch('requests.request', side_effect=requests.exceptions.Timeout("Timeout")) as mock_req:
        ok, status, data, error = get_json_with_retry(
            "https://example.com/api",
            max_attempts=3
        )
        
        assert ok is False
        assert status is None
        assert data is None
        assert "Timeout" in error
        assert mock_req.call_count == 3


def test_max_elapsed_time():
    """Test max elapsed time limit"""
    mock_response = Mock()
    mock_response.status_code = 503
    
    with patch('requests.request', return_value=mock_response):
        ok, status, data, error = get_json_with_retry(
            "https://example.com/api",
            max_elapsed=0.1,  # Very short timeout
            max_attempts=100
        )
        
        assert ok is False
        assert "Max elapsed time" in error


def test_all_retryable_status_codes():
    """Test all retryable status codes"""
    for status_code in RETRYABLE_STATUS_CODES:
        mock_response = Mock()
        mock_response.status_code = status_code
        
        with patch('requests.request', return_value=mock_response) as mock_req:
            ok, status, data, error = get_json_with_retry(
                "https://example.com/api",
                max_attempts=2
            )
            
            assert ok is False
            assert mock_req.call_count == 2


def test_invalid_json_response():
    """Test handling of invalid JSON"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    
    with patch('requests.request', return_value=mock_response):
        ok, status, data, error = get_json_with_retry("https://example.com/api")
        
        assert ok is False
        assert status == 200
        assert data is None
        assert "Invalid JSON" in error
