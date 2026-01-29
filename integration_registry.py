"""
INTEGRATION REGISTRY - Single Source of Truth for All External Integrations

This module declares EVERY external API/service integration with:
- Environment variable key(s)
- Required status (ALL integrations are REQUIRED)
- Validation function (is_configured, is_reachable)
- Code owners (modules that use it)
- Endpoints/jobs that depend on it
- Last success/error tracking

BEHAVIOR RULE: "No 500s"
- Endpoints: FAIL SOFT (graceful degradation, return partial data, never crash)
- Health checks: FAIL LOUD (clear error messages showing what's missing)

ENDPOINT: /debug/integrations
Returns comprehensive status of all 14 integrations for monitoring.

ENDPOINT: /debug/integrations?quick=true
Returns fast summary without API connectivity checks.

ALL 14 INTEGRATIONS ARE REQUIRED:
1. odds_api - Live odds, props (paid)
2. playbook_api - Sharp money, splits (paid)
3. balldontlie - NBA grading (GOAT key)
4. weather_api - Outdoor sports
5. astronomy_api - Esoteric moon phases
6. noaa_space_weather - Esoteric solar
7. fred_api - Economic sentiment
8. finnhub_api - Sportsbook stocks
9. serpapi - News aggregation
10. twitter_api - Real-time news
11. whop_api - Membership auth
12. database - PostgreSQL
13. redis - Caching
14. railway_storage - Picks persistence
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger("integration_registry")

# =============================================================================
# INTEGRATION STATUS TRACKING
# =============================================================================

class IntegrationStatus(Enum):
    """Status of an integration."""
    CONFIGURED = "configured"       # Env var set
    NOT_CONFIGURED = "not_configured"  # Env var missing
    REACHABLE = "reachable"        # API responded successfully
    UNREACHABLE = "unreachable"    # API failed to respond
    UNKNOWN = "unknown"            # Not yet tested


@dataclass
class IntegrationHealth:
    """Runtime health tracking for an integration."""
    last_check: Optional[str] = None
    last_ok: Optional[str] = None
    last_error: Optional[str] = None
    error_count: int = 0
    success_count: int = 0
    consecutive_failures: int = 0


# Global health tracking (in-memory)
_health_tracker: Dict[str, IntegrationHealth] = {}


def record_success(integration_name: str):
    """Record successful API call."""
    if integration_name not in _health_tracker:
        _health_tracker[integration_name] = IntegrationHealth()

    health = _health_tracker[integration_name]
    now = datetime.now(timezone.utc).isoformat()
    health.last_check = now
    health.last_ok = now
    health.success_count += 1
    health.consecutive_failures = 0


def record_failure(integration_name: str, error: str):
    """Record failed API call."""
    if integration_name not in _health_tracker:
        _health_tracker[integration_name] = IntegrationHealth()

    health = _health_tracker[integration_name]
    now = datetime.now(timezone.utc).isoformat()
    health.last_check = now
    health.last_error = f"{now}: {error}"
    health.error_count += 1
    health.consecutive_failures += 1


def get_health(integration_name: str) -> IntegrationHealth:
    """Get health status for an integration."""
    return _health_tracker.get(integration_name, IntegrationHealth())


# =============================================================================
# INTEGRATION DEFINITIONS
# =============================================================================

@dataclass
class Integration:
    """Definition of an external integration."""
    name: str
    description: str
    env_vars: List[str]  # Primary and fallback env var names
    required: bool  # True = app won't work without it
    modules: List[str]  # Python modules that use this
    endpoints: List[str]  # API endpoints that depend on this
    jobs: List[str]  # Scheduled jobs that use this
    validate_fn: Optional[str] = None  # Name of validation function
    notes: str = ""


# Master list of all integrations
INTEGRATIONS: Dict[str, Integration] = {}


def register_integration(
    name: str,
    description: str,
    env_vars: List[str],
    required: bool,
    modules: List[str],
    endpoints: List[str],
    jobs: List[str] = None,
    validate_fn: str = None,
    notes: str = ""
):
    """Register an integration in the registry."""
    INTEGRATIONS[name] = Integration(
        name=name,
        description=description,
        env_vars=env_vars,
        required=required,
        modules=modules,
        endpoints=endpoints,
        jobs=jobs or [],
        validate_fn=validate_fn,
        notes=notes
    )


# =============================================================================
# REGISTER ALL INTEGRATIONS
# =============================================================================

# --- PRIMARY PAID APIS (REQUIRED) ---

register_integration(
    name="odds_api",
    description="The Odds API - Live odds, lines, props for all sports",
    env_vars=["ODDS_API_KEY", "EXPO_PUBLIC_ODDS_API_KEY"],
    required=True,
    modules=["live_data_router.py", "odds_api.py"],
    endpoints=[
        "/live/best-bets/{sport}",
        "/live/props/{sport}",
        "/live/lines/{sport}",
        "/live/odds/{sport}",
        "/live/line-shop/{sport}",
    ],
    jobs=["scheduled_props_fetch", "scheduled_odds_update"],
    validate_fn="validate_odds_api",
    notes="Monthly quota limit. Check /live/odds-api/usage for remaining requests."
)

register_integration(
    name="playbook_api",
    description="Playbook Sports API - Sharp money, splits, injuries for all sports",
    env_vars=["PLAYBOOK_API_KEY", "EXPO_PUBLIC_PLAYBOOK_API_KEY"],
    required=True,
    modules=["live_data_router.py", "playbook_api.py"],
    endpoints=[
        "/live/sharp/{sport}",
        "/live/splits/{sport}",
        "/live/injuries/{sport}",
        "/live/best-bets/{sport}",
    ],
    jobs=["scheduled_splits_fetch", "scheduled_injury_update"],
    validate_fn="validate_playbook_api",
    notes="Provides research engine signals (sharp money, public splits)."
)

# --- NBA SPECIFIC (REQUIRED - GOAT TIER) ---

register_integration(
    name="balldontlie",
    description="BallDontLie GOAT API - NBA stats, box scores, player lookup, grading",
    env_vars=["BDL_API_KEY", "BALLDONTLIE_API_KEY"],
    required=True,  # REQUIRED - Key is hardcoded, essential for NBA grading
    modules=["alt_data_sources/balldontlie.py", "result_fetcher.py", "identity/player_resolver.py"],
    endpoints=[
        "/live/best-bets/NBA",
        "/live/grader/run-audit",
        "/live/picks/grading-summary",
    ],
    jobs=["daily_grading_6am", "nba_prop_grading"],
    validate_fn="validate_balldontlie",
    notes="GOAT tier key: 1cbb16a0-3060-4caf-ac17-ff11352540bc. REQUIRED for NBA prop grading."
)

# --- ESOTERIC ENGINE DATA (REQUIRED for 20% scoring weight) ---

register_integration(
    name="weather_api",
    description="OpenWeather API - Weather data for outdoor sports (NFL, MLB)",
    env_vars=["WEATHER_API_KEY", "EXPO_PUBLIC_WEATHER_API_KEY", "OPENWEATHER_API_KEY"],
    required=True,  # REQUIRED - Feeds esoteric engine for outdoor sports
    modules=["alt_data_sources/weather.py", "live_data_router.py"],
    endpoints=["/live/best-bets/NFL", "/live/best-bets/MLB"],
    jobs=["scheduled_weather_update"],
    validate_fn="validate_weather_api",
    notes="Feature flagged (WEATHER_ENABLED). Critical for NFL/MLB outdoor game analysis."
)

register_integration(
    name="astronomy_api",
    description="AstronomyAPI - Moon phases, astro data for esoteric engine (25% of esoteric)",
    env_vars=["ASTRONOMY_API_ID", "EXPO_PUBLIC_ASTRONOMY_API_ID",
              "ASTRONOMY_API_SECRET", "EXPO_PUBLIC_ASTRONOMY_API_SECRET"],
    required=True,  # REQUIRED - Feeds esoteric scoring engine (20% weight)
    modules=["esoteric_engine.py", "live_data_router.py"],
    endpoints=["/live/esoteric-edge", "/esoteric/today-energy", "/live/best-bets/{sport}"],
    jobs=["daily_astro_update"],
    validate_fn="validate_astronomy_api",
    notes="Moon phase alignment contributes to esoteric score."
)

register_integration(
    name="noaa_space_weather",
    description="NOAA Space Weather - Solar activity, geomagnetic data for esoteric",
    env_vars=["NOAA_BASE_URL", "EXPO_PUBLIC_NOAA_BASE_URL"],
    required=True,  # REQUIRED - Feeds esoteric engine
    modules=["esoteric_engine.py"],
    endpoints=["/live/esoteric-edge", "/esoteric/today-energy", "/live/best-bets/{sport}"],
    jobs=[],
    validate_fn="validate_noaa",
    notes="Free public API. Solar/geomagnetic data for esoteric scoring."
)

# --- FINANCIAL/SENTIMENT (REQUIRED - feeds research/esoteric engines) ---

register_integration(
    name="fred_api",
    description="Federal Reserve Economic Data - Economic indicators for sentiment",
    env_vars=["FRED_API_KEY"],
    required=True,  # REQUIRED - Feeds esoteric/research engines
    modules=["esoteric_engine.py"],
    endpoints=["/live/esoteric-edge", "/live/best-bets/{sport}"],
    jobs=[],
    validate_fn="validate_fred_api",
    notes="Economic sentiment signals. Fail soft on endpoints, loud on health check."
)

register_integration(
    name="finnhub_api",
    description="Finnhub - Stock/financial data, sportsbook stock prices",
    env_vars=["FINNHUB_KEY", "FINNHUB_API_KEY"],
    required=True,  # REQUIRED - Sportsbook sentiment tracking
    modules=["esoteric_engine.py"],
    endpoints=["/live/esoteric-edge"],
    jobs=[],
    validate_fn="validate_finnhub",
    notes="Tracks sportsbook company stock prices for sentiment."
)

# --- SOCIAL/NEWS (REQUIRED - real-time signals) ---

register_integration(
    name="serpapi",
    description="SerpAPI - Search engine results, news aggregation, trending topics",
    env_vars=["SERPAPI_KEY", "SERP_API_KEY"],
    required=True,  # REQUIRED - News sentiment signals
    modules=["esoteric_engine.py"],
    endpoints=["/live/esoteric-edge", "/live/best-bets/{sport}"],
    jobs=[],
    validate_fn="validate_serpapi",
    notes="News/trending analysis. Fail soft on endpoints, loud on health check."
)

register_integration(
    name="twitter_api",
    description="Twitter/X API - Breaking news, injury reports, real-time sentiment",
    env_vars=["TWITTER_BEARER", "TWITTER_BEARER_TOKEN"],
    required=True,  # REQUIRED - Real-time injury/news detection
    modules=["esoteric_engine.py"],
    endpoints=["/live/esoteric-edge", "/live/best-bets/{sport}"],
    jobs=[],
    validate_fn="validate_twitter",
    notes="Real-time injury news. Fail soft on endpoints, loud on health check."
)

# --- BUSINESS/AUTH (REQUIRED) ---

register_integration(
    name="whop_api",
    description="Whop API - Membership/payment platform, premium access control",
    env_vars=["WHOP_API_KEY"],
    required=True,  # REQUIRED - Membership verification
    modules=["auth.py"],
    endpoints=["/auth/verify", "/auth/webhook"],
    jobs=[],
    validate_fn="validate_whop",
    notes="Premium membership verification. Fail soft on endpoints, loud on health check."
)

# --- INFRASTRUCTURE (REQUIRED) ---

register_integration(
    name="database",
    description="PostgreSQL Database - Primary data store",
    env_vars=["DATABASE_URL"],
    required=True,  # REQUIRED - Primary storage (JSONL is fallback only)
    modules=["database.py", "models.py"],
    endpoints=["all"],
    jobs=["all"],
    validate_fn="validate_database",
    notes="Primary data store. Falls back to JSONL but DB is required for production."
)

register_integration(
    name="redis",
    description="Redis - Caching layer for performance",
    env_vars=["REDIS_URL"],
    required=True,  # REQUIRED - Production caching
    modules=["cache.py"],
    endpoints=["all"],
    jobs=[],
    validate_fn="validate_redis",
    notes="Production caching. Falls back to in-memory but Redis required for scale."
)

register_integration(
    name="railway_storage",
    description="Railway Persistent Volume - Picks and weights storage",
    env_vars=["RAILWAY_VOLUME_MOUNT_PATH", "GRADER_MOUNT_ROOT"],
    required=True,
    modules=["storage_paths.py", "data_dir.py", "grader_store.py", "pick_logger.py"],
    endpoints=[
        "/live/best-bets/{sport}",
        "/live/grader/status",
        "/live/grader/run-audit",
        "/internal/storage/health",
    ],
    jobs=["daily_grading_6am", "scheduled_props_fetch"],
    validate_fn="validate_storage",
    notes="CRITICAL: All picks persisted here. Fail-fast on startup if not writable."
)


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def is_env_set(*env_vars: str) -> bool:
    """Check if any of the given env vars are set and non-empty."""
    for var in env_vars:
        value = os.getenv(var, "")
        if value and value.strip() and value != "your_key_here":
            return True
    return False


def get_env_value(*env_vars: str) -> Optional[str]:
    """Get first non-empty env var value."""
    for var in env_vars:
        value = os.getenv(var, "")
        if value and value.strip() and value != "your_key_here":
            return value.strip()
    return None


async def validate_odds_api() -> Dict[str, Any]:
    """Validate Odds API connectivity."""
    key = get_env_value("ODDS_API_KEY", "EXPO_PUBLIC_ODDS_API_KEY")
    if not key:
        return {"configured": False, "reachable": False, "error": "API key not set"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.the-odds-api.com/v4/sports",
                params={"apiKey": key}
            )
            if resp.status_code == 200:
                record_success("odds_api")
                remaining = resp.headers.get("x-requests-remaining", "unknown")
                return {
                    "configured": True,
                    "reachable": True,
                    "requests_remaining": remaining
                }
            else:
                error = f"HTTP {resp.status_code}"
                record_failure("odds_api", error)
                return {"configured": True, "reachable": False, "error": error}
    except Exception as e:
        record_failure("odds_api", str(e))
        return {"configured": True, "reachable": False, "error": str(e)}


async def validate_playbook_api() -> Dict[str, Any]:
    """Validate Playbook API connectivity."""
    key = get_env_value("PLAYBOOK_API_KEY", "EXPO_PUBLIC_PLAYBOOK_API_KEY")
    if not key:
        return {"configured": False, "reachable": False, "error": "API key not set"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.playbook-api.com/v1/health",
                params={"api_key": key}
            )
            if resp.status_code == 200:
                record_success("playbook_api")
                return {"configured": True, "reachable": True}
            else:
                error = f"HTTP {resp.status_code}"
                record_failure("playbook_api", error)
                return {"configured": True, "reachable": False, "error": error}
    except Exception as e:
        record_failure("playbook_api", str(e))
        return {"configured": True, "reachable": False, "error": str(e)}


async def validate_balldontlie() -> Dict[str, Any]:
    """Validate BallDontLie API connectivity."""
    # BDL has hardcoded GOAT key
    try:
        from alt_data_sources.balldontlie import BDL_ENABLED, BDL_API_KEY
        if not BDL_ENABLED:
            return {"configured": False, "reachable": False, "error": "BDL not enabled"}

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.balldontlie.io/v1/players",
                headers={"Authorization": BDL_API_KEY},
                params={"per_page": 1}
            )
            if resp.status_code == 200:
                record_success("balldontlie")
                return {"configured": True, "reachable": True}
            else:
                error = f"HTTP {resp.status_code}"
                record_failure("balldontlie", error)
                return {"configured": True, "reachable": False, "error": error}
    except ImportError:
        return {"configured": False, "reachable": False, "error": "Module not available"}
    except Exception as e:
        record_failure("balldontlie", str(e))
        return {"configured": True, "reachable": False, "error": str(e)}


async def validate_weather_api() -> Dict[str, Any]:
    """Validate Weather API configuration."""
    try:
        from alt_data_sources.weather import WEATHER_ENABLED, OPENWEATHER_API_KEY
        if not WEATHER_ENABLED:
            return {"configured": False, "reachable": False, "reason": "WEATHER_ENABLED=false"}
        if not OPENWEATHER_API_KEY:
            return {"configured": False, "reachable": False, "error": "API key not set"}
        return {"configured": True, "reachable": None, "note": "Not tested (stub module)"}
    except ImportError:
        return {"configured": False, "reachable": False, "error": "Module not available"}


async def validate_storage() -> Dict[str, Any]:
    """Validate Railway storage is configured and writable."""
    try:
        from storage_paths import get_storage_health
        health = get_storage_health()
        return {
            "configured": health.get("ok", False),
            "reachable": health.get("writable", False),
            "is_mountpoint": health.get("is_mountpoint", False),
            "is_ephemeral": health.get("is_ephemeral", True),
            "predictions_count": health.get("predictions_line_count", 0),
            "resolved_base_dir": health.get("resolved_base_dir"),
        }
    except Exception as e:
        return {"configured": False, "reachable": False, "error": str(e)}


# Map of validation function names to actual functions
VALIDATORS: Dict[str, Callable] = {
    "validate_odds_api": validate_odds_api,
    "validate_playbook_api": validate_playbook_api,
    "validate_balldontlie": validate_balldontlie,
    "validate_weather_api": validate_weather_api,
    "validate_storage": validate_storage,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_integration(name: str) -> Optional[Integration]:
    """Get integration definition by name."""
    return INTEGRATIONS.get(name)


def list_integrations() -> List[str]:
    """List all registered integration names."""
    return list(INTEGRATIONS.keys())


def get_required_integrations() -> List[Integration]:
    """Get list of required integrations."""
    return [i for i in INTEGRATIONS.values() if i.required]


def get_optional_integrations() -> List[Integration]:
    """Get list of optional integrations."""
    return [i for i in INTEGRATIONS.values() if not i.required]


def check_integration_configured(name: str) -> bool:
    """Check if an integration is configured (env vars set)."""
    integration = INTEGRATIONS.get(name)
    if not integration:
        return False
    return is_env_set(*integration.env_vars)


async def check_integration_health(name: str) -> Dict[str, Any]:
    """Check full health of an integration."""
    integration = INTEGRATIONS.get(name)
    if not integration:
        return {"error": f"Unknown integration: {name}"}

    result = {
        "name": name,
        "description": integration.description,
        "required": integration.required,
        "is_configured": is_env_set(*integration.env_vars),
        "env_vars": integration.env_vars,
        "modules": integration.modules,
        "endpoints": integration.endpoints,
        "jobs": integration.jobs,
        "notes": integration.notes,
    }

    # Add runtime health tracking
    health = get_health(name)
    result["last_check"] = health.last_check
    result["last_ok"] = health.last_ok
    result["last_error"] = health.last_error
    result["success_count"] = health.success_count
    result["error_count"] = health.error_count
    result["consecutive_failures"] = health.consecutive_failures

    # Run validation if available
    if integration.validate_fn and integration.validate_fn in VALIDATORS:
        try:
            validation = await VALIDATORS[integration.validate_fn]()
            result["validation"] = validation
            result["is_reachable"] = validation.get("reachable", None)
        except Exception as e:
            result["validation"] = {"error": str(e)}
            result["is_reachable"] = False
    else:
        result["is_reachable"] = None  # Not tested

    return result


async def get_all_integrations_status() -> Dict[str, Any]:
    """
    Get status of ALL integrations.

    This is the main function called by /debug/integrations endpoint.
    """
    results = {}
    required_missing = []
    optional_missing = []

    for name, integration in INTEGRATIONS.items():
        status = await check_integration_health(name)
        results[name] = status

        # Track missing required integrations
        if not status["is_configured"]:
            if integration.required:
                required_missing.append(name)
            else:
                optional_missing.append(name)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_integrations": len(INTEGRATIONS),
        "required_count": len([i for i in INTEGRATIONS.values() if i.required]),
        "optional_count": len([i for i in INTEGRATIONS.values() if not i.required]),
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "all_required_configured": len(required_missing) == 0,
        "integrations": results,
    }


def get_integrations_summary() -> Dict[str, Any]:
    """
    Get quick summary without running validation checks.

    Faster than get_all_integrations_status() - doesn't make API calls.
    """
    configured = []
    not_configured = []

    for name, integration in INTEGRATIONS.items():
        if is_env_set(*integration.env_vars):
            configured.append(name)
        else:
            not_configured.append(name)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(INTEGRATIONS),
        "configured": configured,
        "not_configured": not_configured,
        "configured_count": len(configured),
        "not_configured_count": len(not_configured),
    }


def get_health_check_loud() -> Dict[str, Any]:
    """
    LOUD health check - clearly shows all failures.

    BEHAVIOR:
    - Endpoints: Fail SOFT (graceful degradation, no 500s)
    - Health check: Fail LOUD (clear error messages)

    Returns:
        {
            "status": "HEALTHY" | "DEGRADED" | "CRITICAL",
            "all_configured": bool,
            "missing_count": int,
            "missing_integrations": [...],
            "errors": [...],
            "message": "Clear human-readable status"
        }
    """
    missing = []
    errors = []

    for name, integration in INTEGRATIONS.items():
        if not is_env_set(*integration.env_vars):
            missing.append({
                "name": name,
                "env_vars": integration.env_vars,
                "description": integration.description,
                "affects": integration.endpoints[:3],  # First 3 endpoints
            })
            errors.append(f"MISSING: {name} - Set one of: {integration.env_vars}")

    # Determine status
    if len(missing) == 0:
        status = "HEALTHY"
        message = "All 14 integrations configured and ready"
    elif len(missing) <= 3:
        status = "DEGRADED"
        message = f"{len(missing)} integration(s) missing - system running with reduced functionality"
    else:
        status = "CRITICAL"
        message = f"{len(missing)} integrations missing - system severely degraded"

    return {
        "status": status,
        "all_configured": len(missing) == 0,
        "total_integrations": len(INTEGRATIONS),
        "configured_count": len(INTEGRATIONS) - len(missing),
        "missing_count": len(missing),
        "missing_integrations": missing,
        "errors": errors,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# STARTUP VALIDATION
# =============================================================================

def validate_required_on_startup() -> bool:
    """
    Validate all required integrations are configured.

    Call this during app startup to fail fast if critical integrations missing.

    Returns True if all required integrations are configured.
    """
    missing = []

    for name, integration in INTEGRATIONS.items():
        if integration.required and not is_env_set(*integration.env_vars):
            missing.append(name)
            logger.error("MISSING REQUIRED INTEGRATION: %s", name)
            logger.error("  Required env vars: %s", integration.env_vars)
            logger.error("  Used by: %s", integration.modules)

    if missing:
        logger.error("=" * 60)
        logger.error("STARTUP VALIDATION FAILED")
        logger.error("Missing required integrations: %s", missing)
        logger.error("=" * 60)
        return False

    logger.info("✓ All required integrations configured")
    return True


def log_integration_status():
    """Log status of all integrations at startup."""
    logger.info("=" * 60)
    logger.info("INTEGRATION REGISTRY STATUS")
    logger.info("=" * 60)

    for name, integration in INTEGRATIONS.items():
        configured = is_env_set(*integration.env_vars)
        status = "✓" if configured else "✗"
        req = "REQUIRED" if integration.required else "optional"
        logger.info("%s %s (%s): %s", status, name, req,
                   "configured" if configured else "NOT CONFIGURED")

    logger.info("=" * 60)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Registration
    "register_integration",
    "INTEGRATIONS",

    # Health tracking
    "record_success",
    "record_failure",
    "get_health",

    # Status checking
    "get_integration",
    "list_integrations",
    "get_required_integrations",
    "get_optional_integrations",
    "check_integration_configured",
    "check_integration_health",
    "get_all_integrations_status",
    "get_integrations_summary",
    "get_health_check_loud",

    # Startup
    "validate_required_on_startup",
    "log_integration_status",
]
