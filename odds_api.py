"""
odds_api.py - Thin Odds API client wrapper

Responsibilities:
- Make Odds API requests with consistent timeout/retry
- Mark integration usage on successful JSON response
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


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
                except Exception:
                    used = False
            return resp, used
        except Exception as e:
            last_exc = e
            if attempt <= retries:
                await asyncio.sleep(backoff_s * attempt)
            else:
                break

    if last_exc:
        logger.debug("Odds API request failed: %s", last_exc)
    return None, used
