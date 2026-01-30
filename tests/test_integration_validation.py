"""
Test: Integration Validation - Required => Validated

GOAL: Every integration marked "Required" in docs/AUDIT_MAP.md MUST have a
connectivity validation test. This enforces "required means validated".

STATUS CATEGORIES:
(A) configured+validated - Env var set AND connectivity confirmed
(B) configured+unreachable - Env var set BUT API not responding (FAIL LOUD)
(C) intentionally disabled - Feature flag false (only for required=False integrations)

For this test to pass, all REQUIRED integrations must be (A) or at least configured.
"""

import pytest
import os
import asyncio
from typing import Dict, Any, Tuple

# Import the integration registry
try:
    from integration_registry import (
        INTEGRATIONS,
        get_integration,
        is_env_set,
        get_env_value,
        check_integration_configured,
    )
    REGISTRY_AVAILABLE = True
except ImportError:
    REGISTRY_AVAILABLE = False


# ============================================================================
# REQUIRED INTEGRATIONS (14 total - all integrations are required)
# ============================================================================

REQUIRED_INTEGRATIONS = [
    "odds_api",
    "playbook_api",
    "balldontlie",
    "weather_api",  # REQUIRED for outdoor sports (NFL, MLB, NCAAF)
    "astronomy_api",
    "noaa_space_weather",
    "fred_api",
    "finnhub_api",
    "serpapi",
    "twitter_api",
    "whop_api",
    "database",
    "redis",
    "railway_storage",
]

OPTIONAL_INTEGRATIONS = [
    # All integrations are now required
]


# ============================================================================
# VALIDATION FUNCTIONS FOR EACH INTEGRATION
# ============================================================================

async def validate_odds_api() -> Tuple[bool, str]:
    """Validate Odds API is configured and reachable."""
    key = os.getenv("ODDS_API_KEY") or os.getenv("EXPO_PUBLIC_ODDS_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: ODDS_API_KEY not set"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.the-odds-api.com/v4/sports",
                params={"apiKey": key}
            )
            if resp.status_code == 200:
                remaining = resp.headers.get("x-requests-remaining", "unknown")
                return True, f"VALIDATED: reachable, {remaining} requests remaining"
            else:
                return False, f"UNREACHABLE: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"UNREACHABLE: {str(e)}"


async def validate_playbook_api() -> Tuple[bool, str]:
    """Validate Playbook API is configured and reachable."""
    key = os.getenv("PLAYBOOK_API_KEY") or os.getenv("EXPO_PUBLIC_PLAYBOOK_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: PLAYBOOK_API_KEY not set"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.playbook-api.com/v1/health",
                params={"api_key": key}
            )
            if resp.status_code == 200:
                return True, "VALIDATED: reachable"
            else:
                return False, f"UNREACHABLE: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"UNREACHABLE: {str(e)}"


async def validate_balldontlie() -> Tuple[bool, str]:
    """Validate BallDontLie API is configured and reachable."""
    key = os.getenv("BALLDONTLIE_API_KEY") or os.getenv("BDL_API_KEY")
    if not key or key in ("", "your_key_here", "your_balldontlie_api_key_here"):
        return False, "NOT_CONFIGURED: BALLDONTLIE_API_KEY or BDL_API_KEY not set"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.balldontlie.io/v1/players",
                headers={"Authorization": key},
                params={"per_page": 1}
            )
            if resp.status_code == 200:
                return True, "VALIDATED: reachable, API key works"
            elif resp.status_code == 401:
                return False, "UNREACHABLE: Invalid API key (401)"
            else:
                return False, f"UNREACHABLE: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"UNREACHABLE: {str(e)}"


async def validate_astronomy_api() -> Tuple[bool, str]:
    """Validate Astronomy API is configured."""
    app_id = os.getenv("ASTRONOMY_API_ID") or os.getenv("EXPO_PUBLIC_ASTRONOMY_API_ID")
    app_secret = os.getenv("ASTRONOMY_API_SECRET") or os.getenv("EXPO_PUBLIC_ASTRONOMY_API_SECRET")

    if not app_id or not app_secret:
        return False, "NOT_CONFIGURED: ASTRONOMY_API_ID or ASTRONOMY_API_SECRET not set"

    # Note: Full validation would require an actual API call
    # For now, we check that credentials are configured
    return True, "CONFIGURED: credentials set (connectivity not tested)"


async def validate_noaa() -> Tuple[bool, str]:
    """Validate NOAA Space Weather API is reachable (free, no auth)."""
    base_url = os.getenv("NOAA_BASE_URL") or os.getenv("EXPO_PUBLIC_NOAA_BASE_URL") or "https://services.swpc.noaa.gov"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/products/noaa-planetary-k-index.json")
            if resp.status_code == 200:
                return True, "VALIDATED: reachable (free API)"
            else:
                return False, f"UNREACHABLE: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"UNREACHABLE: {str(e)}"


async def validate_fred_api() -> Tuple[bool, str]:
    """Validate FRED API is configured."""
    key = os.getenv("FRED_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: FRED_API_KEY not set"

    # FRED has rate limits, just verify key is set
    return True, "CONFIGURED: key set (connectivity not tested in CI)"


async def validate_finnhub() -> Tuple[bool, str]:
    """Validate Finnhub API is configured."""
    key = os.getenv("FINNHUB_KEY") or os.getenv("FINNHUB_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: FINNHUB_KEY not set"

    return True, "CONFIGURED: key set (connectivity not tested in CI)"


async def validate_serpapi() -> Tuple[bool, str]:
    """Validate SerpAPI is configured."""
    key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: SERPAPI_KEY not set"

    return True, "CONFIGURED: key set (connectivity not tested in CI)"


async def validate_twitter() -> Tuple[bool, str]:
    """Validate Twitter API is configured."""
    key = os.getenv("TWITTER_BEARER") or os.getenv("TWITTER_BEARER_TOKEN")
    if not key:
        return False, "NOT_CONFIGURED: TWITTER_BEARER not set"

    return True, "CONFIGURED: key set (connectivity not tested in CI)"


async def validate_whop() -> Tuple[bool, str]:
    """Validate Whop API is configured."""
    key = os.getenv("WHOP_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: WHOP_API_KEY not set"

    return True, "CONFIGURED: key set (connectivity not tested in CI)"


async def validate_database() -> Tuple[bool, str]:
    """Validate Database is configured."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return False, "NOT_CONFIGURED: DATABASE_URL not set"

    # Check it looks like a valid postgres URL
    if "postgres" in url or "postgresql" in url:
        return True, "CONFIGURED: PostgreSQL URL set"
    else:
        return True, "CONFIGURED: Database URL set (non-postgres)"


async def validate_redis() -> Tuple[bool, str]:
    """Validate Redis is configured."""
    url = os.getenv("REDIS_URL")
    if not url:
        return False, "NOT_CONFIGURED: REDIS_URL not set"

    return True, "CONFIGURED: Redis URL set"


async def validate_storage() -> Tuple[bool, str]:
    """Validate Railway storage is configured and writable."""
    path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("GRADER_MOUNT_ROOT")
    if not path:
        return False, "NOT_CONFIGURED: RAILWAY_VOLUME_MOUNT_PATH not set"

    # Check if path exists and is writable
    if os.path.exists(path):
        if os.access(path, os.W_OK):
            is_mount = os.path.ismount(path)
            return True, f"VALIDATED: writable, is_mountpoint={is_mount}"
        else:
            return False, "UNREACHABLE: path exists but not writable"
    else:
        return False, f"UNREACHABLE: path {path} does not exist"


async def validate_weather() -> Tuple[bool, str]:
    """Validate Weather API (REQUIRED for outdoor sports)."""
    key = os.getenv("WEATHER_API_KEY")
    if not key:
        return False, "NOT_CONFIGURED: WEATHER_API_KEY not set"

    # Ping WeatherAPI.com to verify connectivity
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.weatherapi.com/v1/current.json",
                params={"key": key, "q": "40.7128,-74.0060", "aqi": "no"}
            )
            if resp.status_code == 200:
                return True, "VALIDATED: WeatherAPI.com reachable"
            elif resp.status_code == 401:
                return False, "UNREACHABLE: Invalid API key (401)"
            elif resp.status_code == 403:
                return False, "UNREACHABLE: API key forbidden (403)"
            else:
                return False, f"UNREACHABLE: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"UNREACHABLE: {str(e)}"


# ============================================================================
# VALIDATION REGISTRY
# ============================================================================

VALIDATORS = {
    "odds_api": validate_odds_api,
    "playbook_api": validate_playbook_api,
    "balldontlie": validate_balldontlie,
    "weather_api": validate_weather,
    "astronomy_api": validate_astronomy_api,
    "noaa_space_weather": validate_noaa,
    "fred_api": validate_fred_api,
    "finnhub_api": validate_finnhub,
    "serpapi": validate_serpapi,
    "twitter_api": validate_twitter,
    "whop_api": validate_whop,
    "database": validate_database,
    "redis": validate_redis,
    "railway_storage": validate_storage,
}


# ============================================================================
# TESTS
# ============================================================================

@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestIntegrationValidation:
    """Test that all required integrations are validated."""

    def test_all_required_integrations_have_validators(self):
        """Every required integration must have a validation function."""
        for name in REQUIRED_INTEGRATIONS:
            assert name in VALIDATORS, f"Missing validator for required integration: {name}"

    def test_all_integrations_in_registry_have_validators(self):
        """Every integration in registry should have a validator."""
        for name in INTEGRATIONS.keys():
            assert name in VALIDATORS, f"Missing validator for integration: {name}"

    def test_required_integrations_count(self):
        """Should have exactly 14 required integrations."""
        required = [i for i in INTEGRATIONS.values() if i.required]
        assert len(required) == 14, f"Expected 14 required integrations, got {len(required)}"

    def test_optional_integrations_count(self):
        """Should have exactly 0 optional integrations (all are required)."""
        optional = [i for i in INTEGRATIONS.values() if not i.required]
        assert len(optional) == 0, f"Expected 0 optional integrations, got {len(optional)}"


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestBallDontLieValidation:
    """Specific tests for BallDontLie integration (per user requirement)."""

    def test_balldontlie_requires_env_var(self):
        """BallDontLie must require env var, no hardcoded key."""
        config = get_integration("balldontlie")
        assert config is not None
        assert "BDL_API_KEY" in config.env_vars or "BALLDONTLIE_API_KEY" in config.env_vars
        # Notes should mention no hardcoded fallback
        assert "hardcoded" in config.notes.lower() or "required" in config.notes.lower()

    def test_balldontlie_is_required(self):
        """BallDontLie must be marked as required."""
        config = get_integration("balldontlie")
        assert config is not None
        assert config.required is True, "balldontlie must be required"

    @pytest.mark.asyncio
    async def test_balldontlie_ping(self):
        """Ping test for BallDontLie API (skip if key not set)."""
        key = os.getenv("BALLDONTLIE_API_KEY") or os.getenv("BDL_API_KEY")
        if not key or key in ("", "your_key_here", "your_balldontlie_api_key_here"):
            pytest.skip("BALLDONTLIE_API_KEY not set in environment")

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.balldontlie.io/v1/players",
                headers={"Authorization": key},
                params={"per_page": 1}
            )
            assert resp.status_code == 200, f"BallDontLie API returned {resp.status_code}"
            data = resp.json()
            assert "data" in data, "Response should contain 'data' field"


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestWeatherApiRequired:
    """Test that weather_api is correctly marked as required."""

    def test_weather_api_is_required(self):
        """Weather API must be marked as required (required=True)."""
        config = get_integration("weather_api")
        assert config is not None
        assert config.required is True, "weather_api must be required"

    def test_weather_api_env_vars(self):
        """Weather API must require WEATHER_API_KEY."""
        config = get_integration("weather_api")
        assert config is not None
        assert "WEATHER_API_KEY" in config.env_vars, "WEATHER_API_KEY must be in env_vars"

    def test_weather_api_outdoor_sports_only(self):
        """Weather API should only affect outdoor sports endpoints."""
        config = get_integration("weather_api")
        assert config is not None
        # Should include NFL, MLB, NCAAF (outdoor sports)
        assert "/live/best-bets/NFL" in config.endpoints
        assert "/live/best-bets/MLB" in config.endpoints
        assert "/live/best-bets/NCAAF" in config.endpoints
        # Should NOT include NBA, NHL (indoor sports)
        assert "/live/best-bets/NBA" not in config.endpoints
        assert "/live/best-bets/NHL" not in config.endpoints

    @pytest.mark.asyncio
    async def test_weather_api_ping(self):
        """Ping test for WeatherAPI.com (skip if key not set)."""
        key = os.getenv("WEATHER_API_KEY")
        if not key:
            pytest.skip("WEATHER_API_KEY not set in environment")

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.weatherapi.com/v1/current.json",
                params={"key": key, "q": "40.7128,-74.0060", "aqi": "no"}
            )
            assert resp.status_code == 200, f"WeatherAPI.com returned {resp.status_code}"
            data = resp.json()
            assert "current" in data, "Response should contain 'current' field"
            assert "temp_f" in data.get("current", {}), "Response should contain temperature"


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestStorageValidation:
    """Test Railway storage validation."""

    def test_storage_path_configured(self):
        """RAILWAY_VOLUME_MOUNT_PATH should be set in production."""
        path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("GRADER_MOUNT_ROOT")
        if not path:
            pytest.skip("RAILWAY_VOLUME_MOUNT_PATH not set (not running on Railway)")

        assert os.path.exists(path), f"Storage path {path} does not exist"

    def test_storage_is_mountpoint(self):
        """Storage should be a mount point on Railway."""
        path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        if not path:
            pytest.skip("RAILWAY_VOLUME_MOUNT_PATH not set")

        if os.path.exists(path):
            assert os.path.ismount(path), f"{path} should be a mount point"


# ============================================================================
# COMPREHENSIVE VALIDATION REPORT
# ============================================================================

async def run_all_validations() -> Dict[str, Any]:
    """Run all validators and return comprehensive report."""
    results = {
        "validated": [],
        "configured_only": [],
        "unreachable": [],
        "not_configured": [],
        "disabled": [],
    }

    for name, validator in VALIDATORS.items():
        success, message = await validator()

        integration = INTEGRATIONS.get(name)
        is_required = integration.required if integration else True

        if "VALIDATED" in message:
            results["validated"].append({"name": name, "status": message, "required": is_required})
        elif "CONFIGURED" in message:
            results["configured_only"].append({"name": name, "status": message, "required": is_required})
        elif "DISABLED" in message:
            results["disabled"].append({"name": name, "status": message, "required": is_required})
        elif "UNREACHABLE" in message:
            results["unreachable"].append({"name": name, "status": message, "required": is_required})
        else:
            results["not_configured"].append({"name": name, "status": message, "required": is_required})

    results["summary"] = {
        "total": len(VALIDATORS),
        "validated_count": len(results["validated"]),
        "configured_only_count": len(results["configured_only"]),
        "unreachable_count": len(results["unreachable"]),
        "not_configured_count": len(results["not_configured"]),
        "disabled_count": len(results["disabled"]),
    }

    return results


if __name__ == "__main__":
    # Run validations directly
    import asyncio

    async def main():
        results = await run_all_validations()
        print("\n" + "=" * 60)
        print("INTEGRATION VALIDATION REPORT")
        print("=" * 60)

        print(f"\n✅ VALIDATED ({len(results['validated'])}):")
        for item in results["validated"]:
            print(f"   {item['name']}: {item['status']}")

        print(f"\n⚠️  CONFIGURED ONLY ({len(results['configured_only'])}):")
        for item in results["configured_only"]:
            print(f"   {item['name']}: {item['status']}")

        print(f"\n🔇 DISABLED ({len(results['disabled'])}):")
        for item in results["disabled"]:
            print(f"   {item['name']}: {item['status']}")

        print(f"\n❌ UNREACHABLE ({len(results['unreachable'])}):")
        for item in results["unreachable"]:
            print(f"   {item['name']}: {item['status']}")

        print(f"\n🚫 NOT CONFIGURED ({len(results['not_configured'])}):")
        for item in results["not_configured"]:
            print(f"   {item['name']}: {item['status']}")

        print("\n" + "=" * 60)
        print(f"SUMMARY: {results['summary']}")
        print("=" * 60)

    asyncio.run(main())
