"""
Environment Configuration Helper - v10.32
=========================================
Centralized env var loading with fallbacks for Railway compatibility.
Handles both server-side vars and EXPO_PUBLIC_ prefixed vars.
"""

import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def get_env(*names: str, default: Any = None) -> Optional[str]:
    """
    Get environment variable with fallback names.

    Tries each name in order, returns first non-empty value.

    Example:
        get_env("ODDS_API_KEY", "EXPO_PUBLIC_ODDS_API_KEY")

    Args:
        *names: Variable names to try in order
        default: Default value if none found

    Returns:
        First non-empty value found, or default
    """
    for name in names:
        value = os.getenv(name)
        if value and str(value).strip():
            return value.strip()
    return default


def get_env_bool(name: str, default: bool = False) -> bool:
    """Get boolean env var (true/false/1/0)."""
    value = os.getenv(name, "").lower().strip()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


# ============================================================================
# CENTRALIZED CONFIG (loaded once at import)
# ============================================================================

class Config:
    """Centralized configuration from Railway env vars."""

    # ============================================================================
    # VERSION CONSTANTS - Single source of truth for API versioning
    # ============================================================================
    ENGINE_VERSION = "v10.91"  # v10.91: Lower sharp threshold 10%→7% to detect more signals
    API_VERSION = "14.9"
    TIMEZONE = "America/New_York"

    # ============================================================================
    # v10.83: Production hardening toggles
    # ============================================================================
    ALLOW_PARTIAL_STACK_BUMP = get_env_bool("ALLOW_PARTIAL_STACK_BUMP", False)
    ENABLE_MOVEMENT_MONITOR = get_env_bool("ENABLE_MOVEMENT_MONITOR", True)

    # Database
    DATABASE_URL = get_env("DATABASE_URL")

    # Redis
    REDIS_URL = get_env("REDIS_URL")

    # API Keys - Primary paid APIs
    ODDS_API_KEY = get_env("ODDS_API_KEY", "EXPO_PUBLIC_ODDS_API_KEY")
    PLAYBOOK_API_KEY = get_env("PLAYBOOK_API_KEY", "EXPO_PUBLIC_PLAYBOOK_API_KEY")

    # Weather API
    WEATHER_API_KEY = get_env("WEATHER_API_KEY", "EXPO_PUBLIC_WEATHER_API_KEY")

    # Astronomy API
    ASTRONOMY_API_ID = get_env("EXPO_PUBLIC_ASTRONOMY_API_ID", "ASTRONOMY_API_ID")
    ASTRONOMY_API_SECRET = get_env("EXPO_PUBLIC_ASTRONOMY_API_SECRET", "ASTRONOMY_API_SECRET")

    # NOAA Space Weather
    NOAA_BASE_URL = get_env("EXPO_PUBLIC_NOAA_BASE_URL", "NOAA_BASE_URL", default="https://services.swpc.noaa.gov")

    # Planetary Hours
    PLANETARY_HOURS_API_URL = get_env("EXPO_PUBLIC_PLANETARY_HOURS_API_URL", "PLANETARY_HOURS_API_URL")

    # FRED API (Federal Reserve Economic Data - economic indicators, sentiment)
    FRED_API_KEY = get_env("FRED_API_KEY")

    # Finnhub API (Stock/financial data - sportsbook stocks, market sentiment)
    FINNHUB_KEY = get_env("FINNHUB_KEY", "FINNHUB_API_KEY")

    # SerpAPI (Search engine results - news aggregation, trending topics)
    SERPAPI_KEY = get_env("SERPAPI_KEY", "SERP_API_KEY")

    # Whop API (Membership/payment platform - user management)
    WHOP_API_KEY = get_env("WHOP_API_KEY")

    # Twitter/X API (Breaking news, injury reports, sentiment)
    TWITTER_BEARER = get_env("TWITTER_BEARER", "TWITTER_BEARER_TOKEN")

    # Auth
    API_AUTH_ENABLED = get_env_bool("API_AUTH_ENABLED", False)
    API_AUTH_KEY = get_env("API_AUTH_KEY")

    @classmethod
    def log_status(cls):
        """Log config status at boot (no secrets, just availability)."""
        status = {
            "db": bool(cls.DATABASE_URL),
            "redis": bool(cls.REDIS_URL),
            "odds": bool(cls.ODDS_API_KEY),
            "playbook": bool(cls.PLAYBOOK_API_KEY),
            "weather": bool(cls.WEATHER_API_KEY),
            "astro": bool(cls.ASTRONOMY_API_ID and cls.ASTRONOMY_API_SECRET),
            "noaa": bool(cls.NOAA_BASE_URL),
            "planetary": bool(cls.PLANETARY_HOURS_API_URL),
            "espn": True,  # ESPN is free, always available
            "fred": bool(cls.FRED_API_KEY),
            "finnhub": bool(cls.FINNHUB_KEY),
            "serpapi": bool(cls.SERPAPI_KEY),
            "whop": bool(cls.WHOP_API_KEY),
            "twitter": bool(cls.TWITTER_BEARER),
            "auth": cls.API_AUTH_ENABLED
        }

        status_str = " ".join(f"{k}={v}" for k, v in status.items())
        logger.info(f"ENV OK: {status_str}")

        return status

    @classmethod
    def validate_required(cls):
        """Check required vars are set."""
        missing = []

        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not cls.ODDS_API_KEY:
            missing.append("ODDS_API_KEY")
        if not cls.PLAYBOOK_API_KEY:
            missing.append("PLAYBOOK_API_KEY")

        if missing:
            logger.warning(f"Missing recommended env vars: {missing}")

        return len(missing) == 0


# Log status on import
Config.log_status()
