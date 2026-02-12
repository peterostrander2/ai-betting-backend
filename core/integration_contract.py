"""
INTEGRATION CONTRACT - Single Source of Truth for API Integrations
Similar pattern to core/scoring_contract.py

All integrations must be defined here with complete metadata.
integration_registry.py imports from this file.

CRITICALITY TIERS (v20.19):
- CRITICAL: /health.ok = false if missing/unreachable. System cannot function.
- DEGRADED_OK: /health.status = degraded but ok = true. System continues with reduced functionality.
- OPTIONAL: No health impact. Log warning only.
- RELEVANCE_GATED: Required for specific contexts (e.g., weather for outdoor sports only).
"""

from enum import Enum


class CriticalityTier(str, Enum):
    """Integration criticality level for health check policy."""
    CRITICAL = "CRITICAL"          # /health fails if unreachable
    DEGRADED_OK = "DEGRADED_OK"    # /health degrades but ok=true
    OPTIONAL = "OPTIONAL"          # No health impact
    RELEVANCE_GATED = "RELEVANCE_GATED"  # Context-dependent


# Integration definitions - CANONICAL SOURCE
INTEGRATIONS = {
    "odds_api": {
        "required": True,
        "criticality": "CRITICAL",  # No betting without odds
        "env_vars": ["ODDS_API_KEY"],
        "owner_modules": ["odds_api.py", "live_data_router.py"],
        "debug_name": "The Odds API",
        "description": "Sports betting odds data provider",
        "feeds_engine": "research",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": {
            "endpoint": "https://api.the-odds-api.com/v4/sports",
            "method": "GET",
            "expected_status": [200]
        }
    },
    
    "playbook_api": {
        "required": True,
        "criticality": "CRITICAL",  # Core research engine - sharp money, splits
        "env_vars": ["PLAYBOOK_API_KEY"],
        "owner_modules": ["playbook_api.py", "live_data_router.py"],
        "debug_name": "Playbook API",
        "description": "Advanced sports analytics and insights",
        "feeds_engine": "research",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": {
            "endpoint": "https://api.playbook.com/v1/health",
            "method": "GET",
            "expected_status": [200]
        }
    },
    
    "balldontlie": {
        "required": True,
        "criticality": "CRITICAL",  # NBA grading system requires this
        "env_vars": ["BALLDONTLIE_API_KEY"],  # Primary key only (BDL_API_KEY is fallback in code)
        "owner_modules": ["balldontlie.py", "auto_grader.py"],
        "debug_name": "BallDontLie API",
        "description": "NBA stats and player data for grading",
        "feeds_engine": "grader",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": {
            "endpoint": "https://api.balldontlie.io/v1/players",
            "method": "GET",
            "expected_status": [200]
        }
    },
    
    "weather_api": {
        "required": True,  # Required but relevance-gated
        "criticality": "RELEVANCE_GATED",  # Only outdoor sports (NFL, MLB, NCAAF)
        "env_vars": ["WEATHER_API_KEY"],
        "owner_modules": ["weather_api.py", "live_data_router.py"],
        "debug_name": "Weather API",
        "description": "Weather data for outdoor sports context",
        "feeds_engine": "context_modifiers",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "NOT_RELEVANT", "UNAVAILABLE", "ERROR", "MISSING"],
        "banned_status_categories": ["FEATURE_DISABLED", "DISABLED"],  # Hard ban
        "relevance_gated": True,
        "relevance_sports": ["NFL", "MLB", "NCAAF"],  # Only these sports need weather
        "connectivity_test": {
            "endpoint": "https://api.openweathermap.org/data/2.5/weather",
            "method": "GET",
            "expected_status": [200]
        }
    },
    
    "railway_storage": {
        "required": True,
        "criticality": "CRITICAL",  # All picks lost without persistent storage
        "env_vars": ["RAILWAY_VOLUME_MOUNT_PATH"],
        "owner_modules": ["storage_paths.py", "data_dir.py", "grader_store.py"],
        "debug_name": "Railway Volume Storage",
        "description": "Persistent storage for picks and predictions",
        "feeds_engine": "persistence",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None  # File system check, not HTTP
    },

    "database": {
        "required": True,
        "criticality": "CRITICAL",  # Core data persistence
        "env_vars": ["DATABASE_URL"],
        "owner_modules": ["database.py"],
        "debug_name": "Supabase Database",
        "description": "Primary database for application data",
        "feeds_engine": "persistence",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },

    "redis": {
        "required": True,
        "criticality": "DEGRADED_OK",  # Performance only, not correctness
        "env_vars": ["REDIS_URL"],
        "owner_modules": ["cache.py"],
        "debug_name": "Redis Cache",
        "description": "In-memory cache for performance",
        "feeds_engine": "performance",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },
    
    "whop_api": {
        "required": True,
        "criticality": "DEGRADED_OK",  # Auth fails gracefully, system continues
        "env_vars": ["WHOP_API_KEY"],
        "owner_modules": ["whop_integration.py"],
        "debug_name": "Whop Payments",
        "description": "Payment and membership management",
        "feeds_engine": "none",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },

    "serpapi": {
        "required": False,  # v20.12: SERP disabled by default (Lesson 65)
        "criticality": "OPTIONAL",  # Disabled by default to conserve quota
        "env_vars": ["SERPAPI_KEY", "SERP_API_KEY"],
        "owner_modules": ["serpapi.py"],
        "debug_name": "SerpAPI",
        "description": "Search engine results for research",
        "feeds_engine": "research",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None,
        "default_disabled": True,  # SERP_INTEL_ENABLED=false by default
        "quota_sensitive": True
    },

    "twitter_api": {
        "required": False,
        "criticality": "OPTIONAL",  # Social signals are supplementary
        "env_vars": ["TWITTER_BEARER"],
        "owner_modules": ["twitter_api.py"],
        "debug_name": "Twitter/X API",
        "description": "Social sentiment analysis",
        "feeds_engine": "research",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },
    
    "astronomy_api": {
        "required": False,  # Esoteric feature, not critical for core betting
        "criticality": "OPTIONAL",  # Esoteric only, graceful fallback
        "env_vars": ["ASTRONOMY_API_ID", "ASTRONOMY_API_SECRET"],
        "owner_modules": ["astronomy_api.py"],
        "debug_name": "Astronomy API",
        "description": "Lunar phases and celestial data",
        "feeds_engine": "esoteric",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },

    "noaa_space_weather": {
        "required": False,  # Esoteric feature, not critical for core betting
        "criticality": "OPTIONAL",  # Esoteric only, graceful fallback
        "env_vars": ["NOAA_BASE_URL"],
        "owner_modules": ["noaa_api.py"],
        "debug_name": "NOAA Space Weather",
        "description": "Space weather and geomagnetic data",
        "feeds_engine": "esoteric",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": {
            "endpoint": "https://services.swpc.noaa.gov/products/",
            "method": "GET",
            "expected_status": [200]
        }
    },

    "fred_api": {
        "required": False,  # Changed: esoteric only
        "criticality": "OPTIONAL",  # Economic sentiment is supplementary
        "env_vars": ["FRED_API_KEY"],
        "owner_modules": ["fred_api.py"],
        "debug_name": "FRED Economic Data",
        "description": "Federal Reserve economic indicators",
        "feeds_engine": "esoteric",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    },

    "finnhub_api": {
        "required": False,  # Changed: esoteric only
        "criticality": "OPTIONAL",  # Market sentiment is supplementary
        "env_vars": ["FINNHUB_KEY"],
        "owner_modules": ["finnhub_api.py"],
        "debug_name": "Finnhub Market Data",
        "description": "Financial market sentiment",
        "feeds_engine": "esoteric",
        "allowed_status_categories": ["VALIDATED", "CONFIGURED", "ERROR", "MISSING"],
        "connectivity_test": None
    }
}

# =============================================================================
# DERIVED LISTS BY CRITICALITY TIER
# =============================================================================

# All integrations marked as required
REQUIRED_INTEGRATIONS = [k for k, v in INTEGRATIONS.items() if v["required"]]

# By criticality tier (for health check policy)
CRITICAL_INTEGRATIONS = [k for k, v in INTEGRATIONS.items() if v.get("criticality") == "CRITICAL"]
DEGRADED_OK_INTEGRATIONS = [k for k, v in INTEGRATIONS.items() if v.get("criticality") == "DEGRADED_OK"]
OPTIONAL_INTEGRATIONS = [k for k, v in INTEGRATIONS.items() if v.get("criticality") == "OPTIONAL"]
RELEVANCE_GATED_INTEGRATIONS = [k for k, v in INTEGRATIONS.items() if v.get("criticality") == "RELEVANCE_GATED"]

# All env vars across all integrations
ALL_ENV_VARS = set()
for integration in INTEGRATIONS.values():
    ALL_ENV_VARS.update(integration["env_vars"])

# Weather-specific rules
WEATHER_ALLOWED_STATUSES = ["VALIDATED", "CONFIGURED", "NOT_RELEVANT", "UNAVAILABLE", "ERROR", "MISSING"]
WEATHER_BANNED_STATUSES = ["FEATURE_DISABLED", "DISABLED"]

# =============================================================================
# HEALTH CHECK POLICY
# =============================================================================
# Defines how /health endpoint should respond based on integration status

HEALTH_POLICY = {
    "CRITICAL": {
        "on_missing": {"ok": False, "status": "critical"},
        "on_unreachable": {"ok": False, "status": "critical"},
    },
    "DEGRADED_OK": {
        "on_missing": {"ok": True, "status": "degraded"},
        "on_unreachable": {"ok": True, "status": "degraded"},
    },
    "OPTIONAL": {
        "on_missing": {"ok": True, "status": "healthy"},  # Just log warning
        "on_unreachable": {"ok": True, "status": "healthy"},
    },
    "RELEVANCE_GATED": {
        "on_missing": {"ok": True, "status": "healthy"},  # Unless sport requires it
        "on_unreachable": {"ok": True, "status": "degraded"},
    },
}

# Export canonical contract for validation
INTEGRATION_CONTRACT = {
    "integrations": INTEGRATIONS,
    "required_integrations": REQUIRED_INTEGRATIONS,
    "critical_integrations": CRITICAL_INTEGRATIONS,
    "degraded_ok_integrations": DEGRADED_OK_INTEGRATIONS,
    "optional_integrations": OPTIONAL_INTEGRATIONS,
    "relevance_gated_integrations": RELEVANCE_GATED_INTEGRATIONS,
    "all_env_vars": sorted(list(ALL_ENV_VARS)),
    "health_policy": HEALTH_POLICY,
    "weather_rules": {
        "allowed_statuses": WEATHER_ALLOWED_STATUSES,
        "banned_statuses": WEATHER_BANNED_STATUSES,
        "relevance_gated": True
    },
    "version": "2.0.0"  # v2.0.0: Added criticality tiers (v20.19)
}
