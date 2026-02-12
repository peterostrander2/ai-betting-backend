"""
odds_api.py - Thin Odds API client wrapper

Responsibilities:
- Make Odds API requests with consistent timeout/retry
- Mark integration usage on successful JSON response
- Record events to integration rollup for monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _record_rollup_event(status: str, latency_ms: int, error_code: Optional[str] = None):
    """Record integration event to rollup (fail-soft)."""
    try:
        from core.integration_rollup import record_integration_event
        record_integration_event("odds_api", status, latency_ms, error_code)
    except Exception:
        pass  # Fail-soft - don't break API calls if rollup fails


async def odds_api_get(
    url: str,
    params: Dict[str, Any],
    client: Optional[httpx.AsyncClient] = None,
    timeout_s: float = 10.0,
    retries: int = 2,
    backoff_s: float = 0.5,
) -> Tuple[Optional[httpx.Response], bool]:
    """
    Fetch Odds API endpoint with retry + usage telemetry.

    Returns:
        (resp, used)
        - resp: httpx.Response or None on hard failure
        - used: True only if response is HTTP 200 and JSON parses
    """
    attempt = 0
    used = False
    last_exc: Optional[Exception] = None
    start_time = time.time()

    while attempt <= retries:
        attempt += 1
        try:
            try:
                import httpx
            except ImportError:
                logger.debug("httpx not available for odds_api_get")
                return None, used
            if client is None:
                async with httpx.AsyncClient(timeout=timeout_s) as local_client:
                    resp = await local_client.get(url, params=params)
            else:
                resp = await client.get(url, params=params, timeout=timeout_s)

            if resp is None:
                continue

            latency_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                try:
                    # Validate JSON to avoid false positives
                    _ = resp.json()
                    used = True
                    try:
                        from integration_registry import mark_integration_used
                        mark_integration_used("odds_api")
                    except Exception:
                        pass
                    # v20.20: Record success to rollup
                    _record_rollup_event("SUCCESS", latency_ms)
                except Exception:
                    used = False
                    _record_rollup_event("ERROR", latency_ms, "JSON_PARSE_ERROR")
            else:
                # Non-200 status
                _record_rollup_event("ERROR", latency_ms, f"HTTP_{resp.status_code}")
            return resp, used
        except Exception as e:
            last_exc = e
            if attempt <= retries:
                await asyncio.sleep(backoff_s * attempt)
            else:
                break

    # All retries exhausted
    latency_ms = int((time.time() - start_time) * 1000)
    if last_exc:
        logger.debug("Odds API request failed: %s", last_exc)
        error_type = type(last_exc).__name__
        _record_rollup_event("ERROR", latency_ms, error_type)
    return None, used
