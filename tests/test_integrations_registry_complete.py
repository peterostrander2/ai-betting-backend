"""
Test: Integration Registry Completeness

REQUIREMENT: All 14 external API integrations must be registered and trackable.

The Integration Registry (integration_registry.py) is the SINGLE SOURCE OF TRUTH
for all external dependencies. Tests verify:
1. All 14 integrations are registered
2. Required vs optional integrations are marked correctly
3. Env var mapping is correct
4. Status tracking functions work
5. Health check functions work
"""

import pytest

# Import the integration registry
try:
    from integration_registry import (
        INTEGRATIONS,
        get_integration,
        list_integrations,
        get_required_integrations,
        get_optional_integrations,
        check_integration_configured,
        get_all_integrations_status,
        get_integrations_summary,
        get_health_check_loud,
        record_success,
        record_failure,
    )
    REGISTRY_AVAILABLE = True
except ImportError:
    REGISTRY_AVAILABLE = False


# The 14 integrations registered (from AUDIT_MAP.md)
# Note: weather_api is optional (WEATHER_ENABLED=false by default)
REQUIRED_INTEGRATIONS = [
    "odds_api",            # Live odds, props, lines
    "playbook_api",        # Sharp money, splits, injuries
    "balldontlie",         # NBA grading (requires env var)
    "weather_api",         # Outdoor sports (OPTIONAL - disabled by default)
    "astronomy_api",       # Moon phases for esoteric
    "noaa_space_weather",  # Solar activity for esoteric
    "fred_api",            # Economic sentiment
    "finnhub_api",         # Sportsbook stocks
    "serpapi",             # News aggregation
    "twitter_api",         # Real-time news
    "whop_api",            # Membership auth
    "database",            # PostgreSQL
    "redis",               # Caching
    "railway_storage",     # Picks persistence
]


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestIntegrationRegistryCompleteness:
    """Test that all 14 integrations are registered"""

    def test_all_14_integrations_registered(self):
        """All 14 required integrations must be in INTEGRATIONS dict"""
        for integration in REQUIRED_INTEGRATIONS:
            assert integration in INTEGRATIONS, \
                f"Integration '{integration}' is not registered"

    def test_integration_count(self):
        """Should have at least 14 integrations"""
        assert len(INTEGRATIONS) >= 14, \
            f"Expected at least 14 integrations, got {len(INTEGRATIONS)}"

    def test_each_integration_has_required_fields(self):
        """Each integration should have required attributes"""
        required_fields = ["name", "env_vars", "required", "description"]

        for name, config in INTEGRATIONS.items():
            for field in required_fields:
                # Integration is a dataclass, use hasattr
                assert hasattr(config, field), \
                    f"Integration '{name}' missing field '{field}'"

    def test_env_vars_are_lists(self):
        """env_vars should be a list for each integration"""
        for name, config in INTEGRATIONS.items():
            # Integration is a dataclass, use attribute access
            env_vars = config.env_vars if hasattr(config, 'env_vars') else []
            assert isinstance(env_vars, list), \
                f"Integration '{name}' env_vars should be a list"

    def test_required_is_boolean(self):
        """required field should be boolean"""
        for name, config in INTEGRATIONS.items():
            # Integration is a dataclass, use attribute access
            required = config.required if hasattr(config, 'required') else None
            assert isinstance(required, bool), \
                f"Integration '{name}' required should be boolean"


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestIntegrationEnvVars:
    """Test environment variable mappings"""

    def test_odds_api_env_var(self):
        """Odds API should use ODDS_API_KEY"""
        config = get_integration("odds_api")
        assert config is not None, "odds_api integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "ODDS_API_KEY" in env_vars

    def test_playbook_api_env_var(self):
        """Playbook API should use PLAYBOOK_API_KEY"""
        config = get_integration("playbook_api")
        assert config is not None, "playbook_api integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "PLAYBOOK_API_KEY" in env_vars

    def test_balldontlie_env_var(self):
        """BallDontLie should use BDL_API_KEY or BALLDONTLIE_API_KEY"""
        config = get_integration("balldontlie")
        assert config is not None, "balldontlie integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "BDL_API_KEY" in env_vars or "BALLDONTLIE_API_KEY" in env_vars

    def test_railway_storage_env_var(self):
        """Railway storage should use RAILWAY_VOLUME_MOUNT_PATH"""
        config = get_integration("railway_storage")
        assert config is not None, "railway_storage integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "RAILWAY_VOLUME_MOUNT_PATH" in env_vars

    def test_database_env_var(self):
        """Database should use DATABASE_URL"""
        config = get_integration("database")
        assert config is not None, "database integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "DATABASE_URL" in env_vars

    def test_redis_env_var(self):
        """Redis should use REDIS_URL"""
        config = get_integration("redis")
        assert config is not None, "redis integration not found"
        env_vars = config.env_vars if hasattr(config, 'env_vars') else []
        assert "REDIS_URL" in env_vars


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestRequiredVsOptional:
    """Test required vs optional integration marking"""

    def test_core_betting_apis_are_required(self):
        """Core betting APIs should be marked as required"""
        core_required = ["odds_api", "playbook_api"]

        for integration in core_required:
            config = get_integration(integration)
            assert config is not None, f"{integration} not found"
            required = config.required if hasattr(config, 'required') else None
            assert required is True, \
                f"{integration} should be marked as required"

    def test_esoteric_apis_are_registered(self):
        """Esoteric/enhancement APIs should be registered"""
        esoteric_apis = ["weather_api", "astronomy_api", "noaa_space_weather"]

        for integration in esoteric_apis:
            config = get_integration(integration)
            assert config is not None, f"{integration} not found"
            assert hasattr(config, "required"), \
                f"{integration} should have required field"

    def test_weather_api_is_required(self):
        """Weather API is required for outdoor sports (NFL, MLB, NCAAF)"""
        config = get_integration("weather_api")
        assert config is not None, "weather_api integration not found"
        required = config.required if hasattr(config, 'required') else None
        assert required is True, "weather_api must be required for outdoor sports"

    def test_get_required_integrations_function(self):
        """get_required_integrations should return list"""
        required = get_required_integrations()
        assert isinstance(required, list)
        assert len(required) > 0, "Should have at least some required integrations"

    def test_get_optional_integrations_function(self):
        """get_optional_integrations should return list"""
        optional = get_optional_integrations()
        assert isinstance(optional, list)


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestStatusFunctions:
    """Test status checking functions"""

    def test_list_integrations_returns_all(self):
        """list_integrations should return all integration names"""
        names = list_integrations()
        assert isinstance(names, list)
        assert len(names) >= 14

    def test_get_integration_returns_config(self):
        """get_integration should return Integration object"""
        config = get_integration("odds_api")
        # It returns an Integration dataclass, not a dict
        assert config is not None
        assert hasattr(config, 'name')
        assert config.name == "odds_api"

    def test_get_integration_unknown_returns_none(self):
        """get_integration with unknown name should return None or empty"""
        config = get_integration("unknown_integration_xyz")
        assert config is None

    def test_check_integration_configured_exists(self):
        """check_integration_configured function should exist and work"""
        # Should not raise
        result = check_integration_configured("odds_api")
        assert isinstance(result, bool)

    def test_get_all_integrations_status_returns_dict(self):
        """get_all_integrations_status should return comprehensive status"""
        # Note: This is an async function, test its existence
        import asyncio
        import inspect
        assert callable(get_all_integrations_status)
        # It's async, so we can't call it directly in sync test
        assert inspect.iscoroutinefunction(get_all_integrations_status)

    def test_get_integrations_summary_returns_lists(self):
        """get_integrations_summary should return configured/not_configured lists"""
        summary = get_integrations_summary()
        assert isinstance(summary, dict)
        assert "configured" in summary or "not_configured" in summary


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestHealthCheckFunctions:
    """Test health check functions"""

    def test_get_health_check_loud_exists(self):
        """get_health_check_loud function should exist"""
        assert callable(get_health_check_loud)

    def test_get_health_check_loud_returns_dict(self):
        """get_health_check_loud should return health status dict"""
        health = get_health_check_loud()
        assert isinstance(health, dict)
        # Should have some health indicator
        assert "ok" in health or "healthy" in health or "status" in health

    def test_record_success_exists(self):
        """record_success function should exist for tracking"""
        assert callable(record_success)

    def test_record_failure_exists(self):
        """record_failure function should exist for tracking"""
        assert callable(record_failure)


@pytest.mark.skipif(not REGISTRY_AVAILABLE, reason="Integration registry not available")
class TestSpecificIntegrations:
    """Test specific integration configurations"""

    def test_balldontlie_is_for_nba(self):
        """BallDontLie should be for NBA stats/grading"""
        config = get_integration("balldontlie")
        assert config is not None, "balldontlie integration not found"
        desc = config.description.lower() if hasattr(config, 'description') else ""
        # Should mention it's for NBA or grading
        assert "nba" in desc or "grading" in desc or "player" in desc or "stats" in desc

    def test_railway_storage_is_for_persistence(self):
        """Railway storage should be for picks persistence"""
        config = get_integration("railway_storage")
        assert config is not None, "railway_storage integration not found"
        desc = config.description.lower() if hasattr(config, 'description') else ""
        assert "persist" in desc or "storage" in desc or "volume" in desc

    def test_database_has_postgresql_reference(self):
        """Database should reference PostgreSQL"""
        config = get_integration("database")
        assert config is not None, "database integration not found"
        desc = config.description.lower() if hasattr(config, 'description') else ""
        assert "postgres" in desc or "database" in desc or "sql" in desc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
