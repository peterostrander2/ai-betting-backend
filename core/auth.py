"""
AUTH.PY - API Authentication Utilities

Single source of truth for API authentication across all routers.

Usage:
    from core.auth import verify_api_key

    @router.post("/protected")
    async def protected_endpoint(auth: bool = Depends(verify_api_key)):
        return {"status": "ok"}
"""

import os
import logging
from typing import Optional
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# API Authentication Configuration
# Set API_AUTH_KEY in Railway to enable authentication
# Set API_AUTH_ENABLED=true to require auth (default: false)
API_AUTH_KEY = os.getenv("API_AUTH_KEY", "")
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"

if API_AUTH_ENABLED and not API_AUTH_KEY:
    logger.warning("API_AUTH_ENABLED is true but API_AUTH_KEY not set - auth disabled")
    API_AUTH_ENABLED = False


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Verify API key if authentication is enabled.
    Pass X-API-Key header to authenticate.

    Returns:
        True if authentication passes

    Raises:
        HTTPException: 401 if missing key, 403 if invalid key
    """
    if not API_AUTH_ENABLED:
        return True  # Auth disabled, allow all

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != API_AUTH_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


__all__ = [
    'verify_api_key',
    'API_AUTH_ENABLED',
    'API_AUTH_KEY',
]
