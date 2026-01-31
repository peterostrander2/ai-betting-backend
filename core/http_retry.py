"""
HTTP Retry Wrapper - Eliminates transient failures
Single source of truth for all external API calls
"""
import time
import random
import requests
from typing import Tuple, Optional, Dict, Any

# Transient errors that should be retried
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    ConnectionResetError,
)

# Configuration
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_MAX_ELAPSED_SECONDS = 8.0
DEFAULT_BASE_DELAY = 0.25  # seconds
DEFAULT_MAX_DELAY = 2.5    # seconds
DEFAULT_TIMEOUT = 10       # seconds


def _calculate_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate exponential backoff with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter


def request_json_with_retry(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_elapsed: float = DEFAULT_MAX_ELAPSED_SECONDS,
    allowed_retry_statuses: Optional[set] = None,
) -> Tuple[bool, Optional[int], Optional[dict], Optional[str]]:
    """
    Make HTTP request with retry logic for transient failures
    
    Returns:
        (ok, status_code, json_data, error_msg)
        - ok: True if successful, False otherwise
        - status_code: HTTP status code or None
        - json_data: Parsed JSON response or None
        - error_msg: Error message or None
    """
    if allowed_retry_statuses is None:
        allowed_retry_statuses = RETRYABLE_STATUS_CODES
    
    start_time = time.time()
    last_error = None
    
    for attempt in range(max_attempts):
        # Check elapsed time
        elapsed = time.time() - start_time
        if elapsed >= max_elapsed:
            return (
                False,
                None,
                None,
                f"Max elapsed time ({max_elapsed}s) exceeded after {attempt} attempts"
            )
        
        try:
            # Make request
            response = requests.request(
                method=method.upper(),
                url=url,
                params=params,
                headers=headers,
                json=json_body,
                timeout=timeout
            )
            
            # Success
            if response.status_code < 400:
                try:
                    json_data = response.json()
                    return (True, response.status_code, json_data, None)
                except Exception as e:
                    return (False, response.status_code, None, f"Invalid JSON: {e}")
            
            # Hard error - don't retry
            if response.status_code not in allowed_retry_statuses:
                return (
                    False,
                    response.status_code,
                    None,
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            
            # Retryable error
            last_error = f"HTTP {response.status_code}"
            
        except RETRYABLE_EXCEPTIONS as e:
            last_error = f"{type(e).__name__}: {str(e)}"
        
        except Exception as e:
            # Unexpected error - don't retry
            return (False, None, None, f"Unexpected error: {type(e).__name__}: {e}")
        
        # Backoff before retry (unless last attempt)
        if attempt < max_attempts - 1:
            backoff = _calculate_backoff(attempt, DEFAULT_BASE_DELAY, DEFAULT_MAX_DELAY)
            time.sleep(backoff)
    
    # All retries exhausted
    return (
        False,
        None,
        None,
        f"All {max_attempts} attempts failed. Last error: {last_error}"
    )


# Convenience methods
def get_json_with_retry(url: str, **kwargs) -> Tuple[bool, Optional[int], Optional[dict], Optional[str]]:
    """GET request with retry"""
    return request_json_with_retry("GET", url, **kwargs)


def post_json_with_retry(url: str, **kwargs) -> Tuple[bool, Optional[int], Optional[dict], Optional[str]]:
    """POST request with retry"""
    return request_json_with_retry("POST", url, **kwargs)
