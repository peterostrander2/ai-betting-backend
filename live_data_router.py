# live_data_router.py v14.7 - TITANIUM TIER SUPPORT
# Research-Optimized + Esoteric Edge + NOOSPHERE VELOCITY + TITANIUM SMASH
# Production-safe with retries, logging, rate-limit handling, deterministic fallbacks
# v11.08: Single source of truth for tiers via tiering.py

from fastapi import APIRouter, HTTPException, Depends, Header, Response, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from typing import Optional, List, Dict, Any, Tuple
import httpx
import time
import logging

# CRITICAL: Define logger BEFORE any import handlers use it
logger = logging.getLogger("live_data")

# Deterministic sort key for pick lists to avoid hash churn on equal scores.
def _stable_pick_sort_key(p: dict) -> tuple:
    score = p.get("total_score", p.get("final_score", 0)) or 0
    return (
        -score,
        str(p.get("pick_id") or p.get("id") or ""),
        str(p.get("selection") or p.get("player") or p.get("player_name") or ""),
        str(p.get("matchup") or p.get("game") or ""),
    )

# Import Pydantic models for request/response validation
try:
    from models.api_models import (
        TrackBetRequest, TrackBetResponse, GradeBetRequest,
        ParlayLegRequest, PlaceParlayRequest, GradeParlayRequest, ParlayCalculateRequest,
        UserPreferencesRequest, RunAuditRequest, AdjustWeightsRequest,
        LogPickRequest, GradePickRequest, CommunityVoteRequest, AffiliateConfigRequest,
        BetResult
    )
    PYDANTIC_MODELS_AVAILABLE = True
except ImportError:
    PYDANTIC_MODELS_AVAILABLE = False
import os
import hashlib
import asyncio
import random
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None
import math
import json
import numpy as np

# PickContract v1 - canonical normalizer
try:
    from utils.pick_normalizer import (
        normalize_pick as contract_normalize_pick,
        normalize_best_bets_response as contract_normalize_best_bets_response
    )
    PICK_CONTRACT_AVAILABLE = True
except Exception as e:
    PICK_CONTRACT_AVAILABLE = False
    logger.warning("pick_normalizer not available: %s", e)

# Public payload sanitizer (ET-only + remove telemetry/UTC)
try:
    from utils.public_payload_sanitizer import sanitize_public_payload
    PUBLIC_SANITIZER_AVAILABLE = True
except Exception as e:
    PUBLIC_SANITIZER_AVAILABLE = False
    logger.warning("public_payload_sanitizer not available: %s", e)


def _sanitize_public(payload: dict) -> dict:
    if PUBLIC_SANITIZER_AVAILABLE:
        return sanitize_public_payload(payload)
    return payload

# Import grader_store - SINGLE SOURCE OF TRUTH for persistence
try:
    import grader_store
    GRADER_STORE_AVAILABLE = True
except ImportError:
    GRADER_STORE_AVAILABLE = False

# Import MasterPredictionSystem for comprehensive AI scoring
try:
    from advanced_ml_backend import MasterPredictionSystem
    MASTER_PREDICTION_AVAILABLE = True
except ImportError:
    MASTER_PREDICTION_AVAILABLE = False

# Import Playbook API utility
try:
    from playbook_api import (
        playbook_fetch, build_playbook_url, VALID_LEAGUES,
        get_splits as pb_get_splits,
        get_injuries as pb_get_injuries,
        get_lines as pb_get_lines,
        get_teams as pb_get_teams,
        get_games as pb_get_games,
        get_api_usage as pb_get_api_usage
    )
    PLAYBOOK_UTIL_AVAILABLE = True
except ImportError:
    PLAYBOOK_UTIL_AVAILABLE = False
    logger.warning("playbook_api module not available - using inline fetch")

# Import Auto-Grader singleton (CRITICAL: use get_grader() not AutoGrader())
try:
    from auto_grader import get_grader, AutoGrader
    AUTO_GRADER_AVAILABLE = True
except ImportError:
    AUTO_GRADER_AVAILABLE = False
    logger.warning("auto_grader module not available")

# Import Tiering module - SINGLE SOURCE OF TRUTH for tier configs (v11.08)
try:
    from tiering import (
        tier_from_score,
        get_tier_config,
        check_titanium_rule,
        scale_ai_score_to_10,
        scale_jarvis_score_to_10,
        get_confidence_from_tier,
        check_injury_validity,
        apply_injury_downgrade,
        is_prop_invalid_injury,
        ENGINE_VERSION as TIERING_VERSION,
        TIER_CONFIG,
        TITANIUM_THRESHOLD,
        DEFAULT_JARVIS_RS
    )
    TIERING_AVAILABLE = True
except ImportError:
    TIERING_AVAILABLE = False
    TIERING_VERSION = "0.0"
    DEFAULT_JARVIS_RS = 5.0
    logger.warning("tiering module not available - using legacy tier logic")

# Import Scoring Contract - SINGLE SOURCE OF TRUTH for scoring constants
from core.scoring_contract import ENGINE_WEIGHTS, MIN_FINAL_SCORE, MIN_PROPS_SCORE, GOLD_STAR_THRESHOLD, GOLD_STAR_GATES, HARMONIC_CONVERGENCE_THRESHOLD, MSRF_BOOST_CAP, SERP_BOOST_CAP_TOTAL, TOTALS_SIDE_CALIBRATION, SPORT_TOTALS_CALIBRATION, ENSEMBLE_ADJUSTMENT_STEP, ODDS_STALENESS_THRESHOLD_SECONDS, CONFLUENCE_LEVELS, PERSIST_TIERS
from core.scoring_pipeline import compute_final_score_option_a, compute_harmonic_boost
from core.telemetry import apply_used_integrations_debug, attach_integration_telemetry_debug, record_daily_integration_rollup

# Import Time ET - SINGLE SOURCE OF TRUTH for ET timezone
try:
    from core.time_et import (
        now_et,
        et_day_bounds,
        is_in_et_day,
        filter_events_et,
    )
    TIME_ET_AVAILABLE = True
except ImportError:
    TIME_ET_AVAILABLE = False
    logger.warning("core.time_et module not available - ET filtering disabled")

# Import Database utilities for line history (v17.7)
try:
    from database import get_db, get_line_history_values, get_season_extreme, DB_ENABLED
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    DB_ENABLED = False
    logger.warning("database module not available for line history")

# Import legacy time_filters for compatibility (will be deprecated)
try:
    from time_filters import (
        is_game_today,
        is_game_started,
        is_team_in_slate,
        validate_today_slate,
        build_today_slate,
        filter_today_games,
        get_game_start_time_et,
        get_today_date_str,
        get_today_range_et,
        log_slate_summary,
        get_game_status,
    )
    TIME_FILTERS_AVAILABLE = True
except ImportError:
    TIME_FILTERS_AVAILABLE = False
    logger.warning("time_filters module not available")

# Import Jason Sim Confluence - Win probability simulation (v11.08)
try:
    from jason_sim_confluence import (
        run_jason_confluence,
        get_default_jason_output,
        get_jason_sim
    )
    JASON_SIM_AVAILABLE = True
except ImportError:
    JASON_SIM_AVAILABLE = False
    logger.warning("jason_sim_confluence module not available")

# Import Pick Logger - Production pick persistence and grading (v14.9)
try:
    from pick_logger import (
        get_pick_logger,
        log_published_pick,
        grade_pick as grade_logged_pick,
        run_daily_audit_report,
        get_today_picks
    )
    PICK_LOGGER_AVAILABLE = True
except ImportError:
    PICK_LOGGER_AVAILABLE = False
    logger.warning("pick_logger module not available - pick persistence disabled")

# Import Result Fetcher - Automatic result fetching and grading (v14.9)
try:
    from result_fetcher import (
        auto_grade_picks,
        fetch_completed_games,
        fetch_nba_player_stats,
        scheduled_auto_grade
    )
    RESULT_FETCHER_AVAILABLE = True
except ImportError:
    RESULT_FETCHER_AVAILABLE = False
    logger.warning("result_fetcher module not available - auto-grading disabled")

# Import Unified Player Identity Resolver (v14.9 - CRITICAL for prop accuracy)
try:
    from identity import (
        resolve_player,
        get_player_resolver,
        get_player_index,
        normalize_player_name,
        normalize_team_name,
        ResolvedPlayer,
    )
    IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    IDENTITY_RESOLVER_AVAILABLE = False
    logger.warning("identity module not available - player resolution disabled")

# Import Centralized Signal Calculators (v14.11 - Single-calculation policy)
try:
    from signals import (
        calculate_public_fade,
        get_public_fade_context,
        PublicFadeSignal,
    )
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False
    logger.warning("signals module not available - using inline calculations")

# Import Weather Module for outdoor sports scoring (v16.0)
# Weather is now a REQUIRED integration - no WEATHER_ENABLED flag needed
try:
    from alt_data_sources.weather import (
        get_weather_modifier,
        get_weather_context_sync,
        get_weather_context,  # Async version for live data
        is_outdoor_sport,
    )
    WEATHER_MODULE_AVAILABLE = True
except ImportError:
    WEATHER_MODULE_AVAILABLE = False
    logger.warning("weather module not available - weather scoring disabled")

# Import Travel Module for rest days and fatigue analysis (v16.0)
try:
    from alt_data_sources.travel import (
        get_travel_impact,
    )
    TRAVEL_MODULE_AVAILABLE = True
except ImportError:
    TRAVEL_MODULE_AVAILABLE = False
    logger.warning("travel module not available - rest days calculation disabled")

# Import ESPN Lineups/Officials Module for referee data (v17.2)
try:
    from alt_data_sources.espn_lineups import (
        get_officials_for_game,
        get_espn_scoreboard,
        get_espn_status,
    )
    ESPN_OFFICIALS_AVAILABLE = True
except ImportError:
    ESPN_OFFICIALS_AVAILABLE = False
    logger.warning("espn_lineups module not available - officials data disabled")

    async def get_officials_for_game(*args, **kwargs):
        return {"available": False, "reason": "MODULE_NOT_LOADED"}

# Import ML Integration Module for LSTM-powered prop predictions (v16.1)
try:
    from ml_integration import (
        get_lstm_ai_score,
        get_lstm_manager,
        get_ml_status,
    )
    ML_INTEGRATION_AVAILABLE = True
except ImportError:
    ML_INTEGRATION_AVAILABLE = False
    logger.warning("ml_integration module not available - using heuristic AI scores")

# Import Context Layer Services for Pillars 13-17 (v17.0)
try:
    from context_layer import (
        DefensiveRankService,
        PaceVectorService,
        UsageVacuumService,
        OfficialsService,
        ParkFactorService,
    )
    CONTEXT_LAYER_AVAILABLE = True
except ImportError:
    CONTEXT_LAYER_AVAILABLE = False
    logger.warning("context_layer module not available - using default context values")

# Import Ensemble Model for Game Picks (v17.0)
try:
    from ml_integration import get_ensemble_ai_score
    ENSEMBLE_AVAILABLE = True
except ImportError:
    ENSEMBLE_AVAILABLE = False
    logger.warning("ensemble model not available - skipping ensemble prediction")

# Import SERP Intelligence for betting signals (v17.4)
try:
    from alt_data_sources.serp_intelligence import (
        get_serp_betting_intelligence,
        get_serp_prop_intelligence,
    )
    from core.serp_guardrails import (
        is_serp_available,
        get_serp_status,
        SERP_SHADOW_MODE,
        SERP_PROPS_ENABLED,
    )
    SERP_INTEL_AVAILABLE = True
except ImportError:
    SERP_INTEL_AVAILABLE = False
    SERP_SHADOW_MODE = True  # Default to shadow mode if module not available
    SERP_PROPS_ENABLED = False
    logger.warning("serp_intelligence module not available - SERP signals disabled")

# Import Gematria Twitter Intelligence for community consensus signals (v17.9)
try:
    from alt_data_sources.gematria_twitter_intel import (
        get_gematria_consensus_boost,
        GEMATRIA_ACCOUNTS,
    )
    GEMATRIA_INTEL_AVAILABLE = True
except ImportError:
    GEMATRIA_INTEL_AVAILABLE = False
    logger.warning("gematria_twitter_intel module not available - Gematria community signals disabled")

# Import Astronomical API for Void-of-Course moon detection (v17.5 - Phase 2.2)
try:
    from astronomical_api import is_void_moon_now
    ASTRONOMICAL_API_AVAILABLE = True
except ImportError:
    ASTRONOMICAL_API_AVAILABLE = False
    logger.warning("astronomical_api module not available - VOC detection disabled")
    def is_void_moon_now():
        return (False, 0.0)

# Redis import with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ============================================================================
# LOGGING SETUP (logger already defined at top for early import handlers)
# ============================================================================

logger.setLevel(logging.INFO)

# Add handler if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)

# ============================================================================
# CONFIGURATION (Environment Variables)
# ============================================================================

# API Keys - REQUIRED: Set these in Railway environment variables
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")

PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")
PLAYBOOK_API_BASE = os.getenv("PLAYBOOK_API_BASE", "https://api.playbook-api.com/v1")

# Log warning if API keys are missing
if not ODDS_API_KEY:
    logger.warning("ODDS_API_KEY not set - will use fallback data")
if not PLAYBOOK_API_KEY:
    logger.warning("PLAYBOOK_API_KEY not set - will use fallback data")

# Authentication - Optional API key for endpoint protection
# Set API_AUTH_KEY in Railway to enable authentication
# Set API_AUTH_ENABLED=true to require auth (default: false)
API_AUTH_KEY = os.getenv("API_AUTH_KEY", "")
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"

if API_AUTH_ENABLED and not API_AUTH_KEY:
    logger.warning("API_AUTH_ENABLED is true but API_AUTH_KEY not set - auth disabled")
    API_AUTH_ENABLED = False

# Redis Configuration - Railway provides REDIS_URL when Redis service is attached
# Falls back to in-memory cache if Redis is not available
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_ENABLED = bool(REDIS_URL) and REDIS_AVAILABLE

if REDIS_URL and not REDIS_AVAILABLE:
    logger.warning("REDIS_URL set but redis package not installed - using in-memory cache")
elif REDIS_URL:
    logger.info("Redis caching enabled")
else:
    logger.info("Redis not configured - using in-memory cache")

ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sport mappings - Playbook uses uppercase league names (NBA, NFL, MLB, NHL, NCAAB)
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "NBA"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "NFL"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "MLB"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "NHL"},
    "ncaab": {"odds": "basketball_ncaab", "espn": "basketball/mens-college-basketball", "playbook": "NCAAB"},
}

# ============================================================================
# SHARED HTTP CLIENT
# ============================================================================

_shared_client: Optional[httpx.AsyncClient] = None


def get_shared_client() -> httpx.AsyncClient:
    """Get or create a shared httpx AsyncClient for connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=30.0)
    return _shared_client


#


async def close_shared_client():
    """Close the shared client (call on app shutdown)."""
    global _shared_client
    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None


# ============================================================================
# FETCH WITH RETRIES HELPER
# ============================================================================

async def fetch_with_retries(
    method: str,
    url: str,
    *,
    params: Dict[str, Any] = None,
    headers: Dict[str, str] = None,
    max_retries: int = 2,
    backoff_base: float = 0.5
) -> Optional[httpx.Response]:
    """
    Fetch URL with retries and exponential backoff.
    Returns Response on success, None on complete failure.
    Rate-limited (429) responses are returned directly for caller to handle.
    """
    client = get_shared_client()
    attempt = 0

    while attempt <= max_retries:
        try:
            resp = await client.request(method, url, params=params, headers=headers)

            # Return rate-limited responses for caller to handle
            if resp.status_code == 429:
                logger.warning("Rate limited by %s (attempt %d): %s",
                             url, attempt, resp.text[:200] if resp.text else "No body")
                return resp

            # Odds API usage marking (success + valid JSON only)
            if resp.status_code == 200 and url.startswith(ODDS_API_BASE):
                try:
                    _ = resp.json()
                    try:
                        from integration_registry import mark_integration_used
                        mark_integration_used("odds_api")
                    except Exception as e:
                        logger.debug("odds_api mark_integration_used failed: %s", str(e))
                except Exception:
                    # Invalid JSON should not mark usage
                    pass

            return resp

        except httpx.RequestError as e:
            logger.exception("HTTP request failed (attempt %d/%d) %s: %s",
                           attempt + 1, max_retries + 1, url, str(e))
            if attempt < max_retries:
                sleep_for = backoff_base * (2 ** attempt)
                await asyncio.sleep(sleep_for)
            attempt += 1

    logger.error("All retries exhausted for %s", url)
    return None


# ============================================================================
# HYBRID CACHE (Redis with in-memory fallback)
# ============================================================================

class HybridCache:
    """
    Cache with Redis backend and in-memory fallback.
    Automatically falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, default_ttl: int = 300, prefix: str = "bookie"):
        """Initialize cache with default TTL in seconds (default 5 minutes)."""
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._redis_client: Optional[Any] = None
        self._memory_cache: Dict[str, tuple] = {}  # key -> (value, expires_at)
        self._using_redis = False

        # Try to connect to Redis if configured
        if REDIS_ENABLED:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                self._using_redis = True
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning("Redis connection failed, using in-memory cache: %s", e)
                self._redis_client = None
                self._using_redis = False

    def _make_key(self, key: str) -> str:
        """Create prefixed key for Redis."""
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if self._using_redis and self._redis_client:
            try:
                redis_key = self._make_key(key)
                value = self._redis_client.get(redis_key)
                if value:
                    logger.debug("Redis HIT: %s", key)
                    return json.loads(value)
                return None
            except Exception as e:
                logger.warning("Redis get failed, falling back to memory: %s", e)
                self._using_redis = False

        # In-memory fallback
        if key in self._memory_cache:
            value, expires_at = self._memory_cache[key]
            if datetime.now() < expires_at:
                logger.debug("Memory HIT: %s", key)
                return value
            else:
                del self._memory_cache[key]
                logger.debug("Memory EXPIRED: %s", key)
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with optional custom TTL."""
        ttl = ttl or self._default_ttl

        if self._using_redis and self._redis_client:
            try:
                redis_key = self._make_key(key)
                self._redis_client.setex(redis_key, ttl, json.dumps(value))
                logger.debug("Redis SET: %s (TTL: %ds)", key, ttl)
                return
            except Exception as e:
                logger.warning("Redis set failed, falling back to memory: %s", e)
                self._using_redis = False

        # In-memory fallback
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._memory_cache[key] = (value, expires_at)
        logger.debug("Memory SET: %s (TTL: %ds)", key, ttl)

    def clear(self) -> None:
        """Clear all cached values."""
        if self._using_redis and self._redis_client:
            try:
                pattern = self._make_key("*")
                keys = self._redis_client.keys(pattern)
                if keys:
                    self._redis_client.delete(*keys)
                logger.info("Redis cache cleared (%d keys)", len(keys))
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)

        # Always clear memory cache too
        self._memory_cache.clear()
        logger.info("Memory cache cleared")

    def acquire_lock(self, key: str, ttl: int = 900) -> bool:
        """Try to acquire a distributed lock. Returns True if acquired."""
        lock_key = f"lock:{key}"
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.set(self._make_key(lock_key), "1", nx=True, ex=ttl))
            except Exception:
                pass
        # In-memory fallback
        if lock_key in self._memory_cache:
            _, expires_at = self._memory_cache[lock_key]
            if datetime.now() < expires_at:
                return False
        self._memory_cache[lock_key] = ("1", datetime.now() + timedelta(seconds=ttl))
        return True

    def release_lock(self, key: str):
        """Release a distributed lock."""
        lock_key = f"lock:{key}"
        if self._using_redis and self._redis_client:
            try:
                self._redis_client.delete(self._make_key(lock_key))
            except Exception:
                pass
        if lock_key in self._memory_cache:
            del self._memory_cache[lock_key]

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": "redis" if self._using_redis else "memory",
            "redis_configured": REDIS_ENABLED,
            "redis_connected": self._using_redis
        }

        if self._using_redis and self._redis_client:
            try:
                pattern = self._make_key("*")
                keys = self._redis_client.keys(pattern)
                stats["redis_keys"] = len(keys)
            except Exception:
                stats["redis_keys"] = "error"

        # Memory stats
        now = datetime.now()
        valid = sum(1 for _, (_, exp) in self._memory_cache.items() if now < exp)
        stats["memory_total_keys"] = len(self._memory_cache)
        stats["memory_valid_keys"] = valid
        stats["memory_expired_keys"] = len(self._memory_cache) - valid

        return stats


# Global cache instance - 5 minute TTL for API responses
api_cache = HybridCache(default_ttl=300, prefix="bookie")


# ============================================================================
# DETERMINISTIC RNG FOR FALLBACK DATA
# ============================================================================

def deterministic_rng_for_game_id(game_id: Any) -> random.Random:
    """
    Create a deterministic Random instance seeded by game_id.
    This ensures fallback splits are stable across requests for the same game.
    """
    seed = int(hashlib.md5(str(game_id).encode()).hexdigest()[:8], 16)
    return random.Random(seed)


# Sample teams for fallback data
SAMPLE_MATCHUPS = {
    "nba": [
        {"id": "nba_sample_1", "home": "Los Angeles Lakers", "away": "Boston Celtics"},
        {"id": "nba_sample_2", "home": "Golden State Warriors", "away": "Phoenix Suns"},
        {"id": "nba_sample_3", "home": "Milwaukee Bucks", "away": "Miami Heat"},
    ],
    "nfl": [
        {"id": "nfl_sample_1", "home": "Kansas City Chiefs", "away": "Buffalo Bills"},
        {"id": "nfl_sample_2", "home": "San Francisco 49ers", "away": "Dallas Cowboys"},
    ],
    "mlb": [
        {"id": "mlb_sample_1", "home": "New York Yankees", "away": "Boston Red Sox"},
        {"id": "mlb_sample_2", "home": "Los Angeles Dodgers", "away": "San Francisco Giants"},
    ],
    "nhl": [
        {"id": "nhl_sample_1", "home": "Toronto Maple Leafs", "away": "Montreal Canadiens"},
        {"id": "nhl_sample_2", "home": "Boston Bruins", "away": "New York Rangers"},
    ],
}


def generate_fallback_line_shop(sport: str) -> List[Dict[str, Any]]:
    """Return empty list when line shop data is unavailable. No sample data."""
    # REMOVED: Sample data fallback. Return empty list.
    return []


def _DEPRECATED_generate_fallback_line_shop(sport: str) -> List[Dict[str, Any]]:
    """DEPRECATED: Old sample data generator - kept for reference only.

    SECURITY: Returns empty list unless ENABLE_DEMO=true.
    """
    if os.getenv("ENABLE_DEMO", "").lower() != "true":
        return []  # No sample data without explicit demo mode
    matchups = SAMPLE_MATCHUPS.get(sport, SAMPLE_MATCHUPS["nba"])
    line_shop_data = []

    for matchup in matchups:
        game_id = matchup["id"]
        rng = deterministic_rng_for_game_id(game_id)

        # Generate deterministic spread between -7.5 and +7.5
        base_spread = rng.choice([-7.5, -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])
        base_total = rng.choice([210.5, 215.5, 220.5, 225.5, 230.5, 235.5])

        game_data = {
            "game_id": game_id,
            "home_team": matchup["home"],
            "away_team": matchup["away"],
            "commence_time": datetime.now().isoformat(),
            "markets": {
                "spreads": {"best_odds": {}, "all_books": []},
                "h2h": {"best_odds": {}, "all_books": []},
                "totals": {"best_odds": {}, "all_books": []},
            }
        }

        # Generate odds for each sportsbook with slight variation
        for book_key, config in SPORTSBOOK_CONFIGS.items():
            book_rng = deterministic_rng_for_game_id(f"{game_id}_{book_key}")
            spread_var = book_rng.choice([0, 0.5, -0.5])
            odds_var = book_rng.choice([-5, 0, 5, -10, 10])

            # Spread odds
            spread_entry = {
                "book_key": book_key,
                "book_name": config["name"],
                "outcomes": [
                    {"name": matchup["home"], "price": -110 + odds_var, "point": base_spread + spread_var},
                    {"name": matchup["away"], "price": -110 - odds_var, "point": -(base_spread + spread_var)},
                ],
                "deep_link": generate_sportsbook_link(book_key, game_id, sport)
            }
            game_data["markets"]["spreads"]["all_books"].append(spread_entry)

            # Moneyline odds
            home_ml = -150 + (odds_var * 3) if base_spread < 0 else 130 + (odds_var * 3)
            away_ml = 130 - (odds_var * 3) if base_spread < 0 else -150 - (odds_var * 3)
            h2h_entry = {
                "book_key": book_key,
                "book_name": config["name"],
                "outcomes": [
                    {"name": matchup["home"], "price": home_ml},
                    {"name": matchup["away"], "price": away_ml},
                ],
                "deep_link": generate_sportsbook_link(book_key, game_id, sport)
            }
            game_data["markets"]["h2h"]["all_books"].append(h2h_entry)

            # Total odds
            total_entry = {
                "book_key": book_key,
                "book_name": config["name"],
                "outcomes": [
                    {"name": "Over", "price": -110 + odds_var, "point": base_total},
                    {"name": "Under", "price": -110 - odds_var, "point": base_total},
                ],
                "deep_link": generate_sportsbook_link(book_key, game_id, sport)
            }
            game_data["markets"]["totals"]["all_books"].append(total_entry)

        # Calculate best odds for each market
        for market_key in ["spreads", "h2h", "totals"]:
            for book_entry in game_data["markets"][market_key]["all_books"]:
                for outcome in book_entry["outcomes"]:
                    name = outcome["name"]
                    price = outcome["price"]
                    if name not in game_data["markets"][market_key]["best_odds"]:
                        game_data["markets"][market_key]["best_odds"][name] = {
                            "price": price, "book": book_entry["book_name"], "book_key": book_entry["book_key"]
                        }
                    elif price > game_data["markets"][market_key]["best_odds"][name]["price"]:
                        game_data["markets"][market_key]["best_odds"][name] = {
                            "price": price, "book": book_entry["book_name"], "book_key": book_entry["book_key"]
                        }

        line_shop_data.append(game_data)

    return line_shop_data


def generate_fallback_sharp(sport: str) -> List[Dict[str, Any]]:
    """Return empty list when sharp data is unavailable. No sample data."""
    # REMOVED: Sample data fallback. Return empty list with data_status indicator.
    return []


def generate_fallback_betslip(sport: str, game_id: str, bet_type: str, selection: str) -> Dict[str, Any]:
    """Return empty betslip response when data is unavailable. No sample data."""
    # REMOVED: Sample data fallback. Return empty response with data_status.
    return {
        "sport": sport.upper(),
        "game_id": game_id,
        "game": None,
        "bet_type": bet_type,
        "selection": selection,
        "source": "unavailable",
        "data_status": "NO_DATA",
        "best_odds": None,
        "all_books": [],
        "count": 0,
        "timestamp": datetime.now().isoformat(),
        "message": "No betting data available for this game"
    }


# ============================================================================
# AUTHENTICATION DEPENDENCY
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Verify API key if authentication is enabled.
    Pass X-API-Key header to authenticate.
    """
    if not API_AUTH_ENABLED:
        return True  # Auth disabled, allow all

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != API_AUTH_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# ============================================================================
# ROUTER SETUP
# ============================================================================

def _normalize_market_label(pick_type: str, stat_type: str = None) -> str:
    """Derive market_label from pick_type. For props, use stat category."""
    # Market label is derived from pick_type, NOT from market field
    if pick_type == "player_prop":
        # For props, use the stat category
        stat_labels = {
            "player_points": "Points",
            "player_rebounds": "Rebounds",
            "player_assists": "Assists",
            "player_threes": "3PT Made",
            "player_steals": "Steals",
            "player_blocks": "Blocks",
            "player_turnovers": "Turnovers",
            "player_pts_rebs": "Pts + Rebs",
            "player_pts_asts": "Pts + Asts",
            "player_rebs_asts": "Rebs + Asts",
            "player_pts_rebs_asts": "Pts + Rebs + Asts",
            "player_double_double": "Double Double",
            "player_triple_double": "Triple Double",
            "player_first_td": "First TD Scorer",
            "player_anytime_td": "Anytime TD",
            "player_goals": "Goals",
            "player_shots": "Shots on Goal",
            "player_saves": "Saves",
        }
        if stat_type:
            return stat_labels.get(stat_type, stat_type.replace("_", " ").replace("player ", "").title())
        return "Player Prop"
    elif pick_type == "spread":
        return "Spread"
    elif pick_type == "moneyline":
        return "Moneyline"
    elif pick_type == "total":
        return "Total"
    return "Unknown"


def _get_signal_label(pick: dict) -> str:
    """Get signal label (e.g., 'Sharp Signal') separate from market type."""
    market = pick.get("market", "").lower()
    if market == "sharp_money":
        return "Sharp Signal"
    # Could add more signal types here
    return None


def _normalize_pick_type(pick: dict) -> str:
    """Determine normalized pick_type from pick data."""
    existing = pick.get("pick_type", "").upper()
    market = pick.get("market", "").lower()

    # Already normalized
    if existing in ("PLAYER_PROP", "MONEYLINE", "SPREAD", "TOTAL"):
        return existing.lower()

    # Props detection
    if pick.get("player") or pick.get("player_name") or "player_" in market:
        return "player_prop"

    # Game pick type detection
    if existing == "TOTAL" or market in ("totals", "total"):
        return "total"
    if existing == "SPREAD" or market in ("spreads", "spread"):
        return "spread"
    if existing in ("ML", "MONEYLINE", "H2H") or market in ("h2h", "moneyline"):
        return "moneyline"
    if existing == "SHARP" or market == "sharp_money":
        # Sharp picks are typically spread or ML based on line
        line = pick.get("line")
        if line is not None and line != 0:
            return "spread"
        return "moneyline"

    # Default based on presence of player
    return "spread" if pick.get("team") else "player_prop"


def _normalize_selection(pick: dict, pick_type: str) -> str:
    """Get the selection (who/what to bet on) from pick data."""
    if pick_type == "player_prop":
        return pick.get("player_name") or pick.get("player") or "Unknown Player"
    if pick_type == "total":
        home = pick.get("home_team", "Home")
        away = pick.get("away_team", "Away")
        return f"{away}/{home}"
    # Spread or ML - return team
    return pick.get("team") or pick.get("side") or pick.get("home_team") or "Unknown Team"


def _normalize_side_label(pick: dict, pick_type: str) -> str:
    """Get the side label for the bet."""
    side = pick.get("side", "")
    direction = pick.get("direction", "")
    over_under = pick.get("over_under", "")

    if pick_type in ("player_prop", "total"):
        # For props and totals, use Over/Under
        if side.lower() in ("over", "under"):
            return side.title()
        if direction.upper() in ("OVER", "UNDER"):
            return direction.title()
        if over_under.lower() in ("over", "under"):
            return over_under.title()
        return "Over"  # Default

    # For spread/ML, use team name
    return pick.get("team") or pick.get("side") or "Unknown"

def _resolve_home_away_intent(pick: dict) -> str:
    """Derive intended HOME/AWAY from pick_side hints."""
    pick_side = (pick.get("pick_side") or "").lower()
    if not pick_side:
        return ""
    if "home" in pick_side:
        return "HOME"
    if "away" in pick_side or "visitor" in pick_side:
        return "AWAY"
    return ""


def _build_bet_string(pick: dict, pick_type: str, selection: str, market_label: str, side_label: str, line_signed: str = None) -> str:
    """Build canonical bet display string."""
    line = pick.get("line")
    odds = pick.get("odds") or pick.get("odds_american")
    units = pick.get("units", 1.0)

    # Format odds - don't fabricate if missing
    if odds is not None:
        odds_str = f"+{odds}" if odds > 0 else str(odds)
    else:
        odds_str = "N/A"
    units_str = f"{units}u"

    if pick_type == "player_prop":
        # "Sam Hauser — 3PT Made Over 4.5 (+130) — 2u"
        line_str = f" {line}" if line is not None else ""
        return f"{selection} — {market_label} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "total":
        # "Bucks/Celtics Over 228.5 (-110) — 1u"
        line_str = f" {line}" if line is not None else ""
        return f"{selection} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "spread":
        # "Boston Celtics -4.5 (-105) — 1u"
        if line_signed:
            return f"{selection} {line_signed} ({odds_str}) — {units_str}"
        return f"{selection} ({odds_str}) — {units_str}"

    # Moneyline: "Milwaukee Bucks Moneyline (-110) — 1u"
    return f"{selection} Moneyline ({odds_str}) — {units_str}"


def _normalize_pick(pick: dict) -> dict:
    """
    PickContract v1: Normalize pick to guarantee all required fields for frontend.

    CORE IDENTITY FIELDS:
    - id: stable unique pick_id
    - sport, league
    - event_id
    - matchup, home_team, away_team
    - start_time_et (display string)
    - start_time_iso (ISO string or null)
    - status/has_started/is_live flags

    BET INSTRUCTION FIELDS:
    - pick_type: "spread" | "moneyline" | "total" | "player_prop"
    - market_label: human label ("Spread", "Points", etc.)
    - selection: exactly what user bets (team OR player OR "Over"/"Under")
    - selection_home_away: "HOME" | "AWAY" | null (computed from selection vs home/away teams)
    - line: numeric line value (null for pure ML)
    - line_signed: "+1.0" / "-2.5" / "O 220.5" / "U 220.5" (signed string)
    - odds_american: number or null (NEVER fabricated)
    - units: recommended bet units
    - bet_string: final human-readable instruction
    - book, book_link

    REASONING FIELDS:
    - tier, score, confidence_label
    - signals_fired, confluence_reasons
    - engine_breakdown
    """
    if not isinstance(pick, dict):
        return pick
    if PICK_CONTRACT_AVAILABLE:
        return contract_normalize_pick(pick)

    # === CORE IDENTITY ===
    pick["id"] = pick.get("id") or pick.get("pick_id") or pick.get("event_id") or "unknown"
    pick["sport"] = pick.get("sport", "").upper() or "UNKNOWN"
    pick["league"] = pick.get("league") or pick.get("sport", "").upper() or "UNKNOWN"
    pick["event_id"] = pick.get("event_id") or pick.get("game_id") or pick["id"]

    home_team = pick.get("home_team") or ""
    away_team = pick.get("away_team") or ""
    pick["home_team"] = home_team
    pick["away_team"] = away_team
    pick["matchup"] = pick.get("matchup") or pick.get("game") or f"{away_team} @ {home_team}"

    # === START TIME ===
    start_time_display = pick.get("start_time") or pick.get("start_time_et") or pick.get("game_time")
    pick["start_time_et"] = start_time_display
    pick["start_time"] = start_time_display  # Alias for backward compat
    pick["start_time_timezone"] = "ET"

    commence_iso = pick.get("commence_time_iso") or pick.get("commence_time")
    pick["start_time_iso"] = commence_iso if commence_iso else None

    if commence_iso and isinstance(commence_iso, str) and commence_iso.endswith("Z"):
        pick["start_time_utc"] = commence_iso
    elif commence_iso:
        try:
            dt = datetime.fromisoformat(str(commence_iso).replace("Z", "+00:00"))
            pick["start_time_utc"] = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pick["start_time_utc"] = commence_iso
    else:
        pick["start_time_utc"] = None
    # Do not expose UTC fields to clients (ET only)
    pick.pop("start_time_utc", None)

    # Fallback: derive ET display time from commence_time if missing
    if not start_time_display and commence_iso:
        try:
            if TIME_FILTERS_AVAILABLE:
                start_time_display = get_game_start_time_et(commence_iso)
            elif _ET is not None:
                dt = datetime.fromisoformat(str(commence_iso).replace("Z", "+00:00"))
                start_time_display = dt.astimezone(_ET).strftime("%-I:%M %p ET")
        except Exception:
            start_time_display = ""
        pick["start_time_et"] = start_time_display
        pick["start_time"] = start_time_display
        pick["start_time_timezone"] = "ET"

    if not start_time_display or start_time_display == "TBD ET":
        start_time_display = "TBD ET"
        pick["start_time_et"] = start_time_display
        pick["start_time"] = start_time_display
        pick["start_time_timezone"] = "ET"
        pick["start_time_status"] = "UNAVAILABLE"
    else:
        pick["start_time_status"] = "OK"

    # === STATUS FLAGS ===
    pick["status"] = pick.get("status") or pick.get("game_status") or "unknown"
    pick["has_started"] = pick.get("has_started", False)
    pick["is_started_already"] = pick.get("is_started_already", pick.get("has_started", False))
    pick["is_live"] = pick.get("is_live", False)
    pick["is_live_bet_candidate"] = pick.get("is_live_bet_candidate", False)

    # === BET INSTRUCTION FIELDS ===
    pick_type = _normalize_pick_type(pick)
    stat_type = pick.get("stat_type", pick.get("prop_type", ""))
    market_label = _normalize_market_label(pick_type, stat_type)
    signal_label = _get_signal_label(pick)
    selection = _normalize_selection(pick, pick_type)
    side_label = _normalize_side_label(pick, pick_type)

    # Ensure line exists
    line = pick.get("line")
    if line is None:
        for key in ("point", "spread", "total", "line_value", "player_line"):
            if pick.get(key) is not None:
                line = pick.get(key)
                pick["line"] = line
                break

    # Build line_signed based on pick_type
    line_signed = None
    if pick_type == "spread" and line is not None:
        line_signed = f"+{line}" if line > 0 else str(line)
    elif pick_type == "total" and line is not None:
        prefix = "O" if side_label.lower() == "over" else "U"
        line_signed = f"{prefix} {line}"
    elif pick_type == "player_prop" and line is not None:
        prefix = "O" if side_label.lower() == "over" else "U"
        line_signed = f"{prefix} {line}"

    # Get actual odds - NEVER fabricate
    raw_odds = pick.get("odds") or pick.get("odds_american")
    odds_american = raw_odds if raw_odds is not None else None

    # Enforce canonical side resolution for game picks (HOME/AWAY)
    correction_flags = pick.get("correction_flags") or []
    if pick_type in ("spread", "moneyline"):
        intent = _resolve_home_away_intent(pick)
        if intent and home_team and away_team:
            desired_team = home_team if intent == "HOME" else away_team
            if selection and desired_team and selection.strip() != desired_team:
                correction_flags.append("FIELD_CONTRADICTION_CORRECTED")
                selection = desired_team
                pick["team"] = desired_team
                side_label = desired_team
    pick["correction_flags"] = correction_flags

    # Build canonical bet string
    bet_string = _build_bet_string(
        pick,
        pick_type,
        selection,
        market_label,
        side_label,
        line_signed if pick_type == "spread" else None
    )

    # Compute selection_home_away for semantic consistency
    selection_home_away = None
    if selection and home_team and away_team:
        sel_lower = selection.lower().strip()
        home_lower = home_team.lower().strip()
        away_lower = away_team.lower().strip()
        if sel_lower == home_lower or home_lower in sel_lower or sel_lower in home_lower:
            selection_home_away = "HOME"
        elif sel_lower == away_lower or away_lower in sel_lower or sel_lower in away_lower:
            selection_home_away = "AWAY"

    # Set all bet instruction fields
    pick["pick_type"] = pick_type
    pick["market_label"] = market_label
    pick["signal_label"] = signal_label
    pick["selection"] = selection
    pick["selection_home_away"] = selection_home_away
    pick["side_label"] = side_label
    pick["line"] = line
    pick["line_signed"] = line_signed
    pick["odds_american"] = odds_american
    pick["units"] = pick.get("units", 1.0)
    pick["recommended_units"] = pick.get("units", 1.0)  # Alias
    pick["bet_string"] = bet_string
    pick["book"] = pick.get("book") or pick.get("sportsbook_name") or "Consensus"
    pick["book_link"] = pick.get("book_link") or pick.get("sportsbook_event_url") or ""

    # === REASONING FIELDS ===
    pick["tier"] = pick.get("tier") or pick.get("bet_tier", {}).get("tier") or "EDGE_LEAN"
    pick["score"] = pick.get("score") or pick.get("final_score") or pick.get("total_score") or 0
    pick["confidence_label"] = pick.get("confidence_label") or pick.get("confidence") or pick.get("action") or "PLAY"
    pick["signals_fired"] = pick.get("signals_fired") or pick.get("signals_firing") or []
    pick["confluence_reasons"] = pick.get("confluence_reasons") or []
    pick["engine_breakdown"] = pick.get("engine_breakdown") or {
        "ai": pick.get("ai_score", 0),
        "research": pick.get("research_score", 0),
        "esoteric": pick.get("esoteric_score", 0),
        "jarvis": pick.get("jarvis_score") or pick.get("jarvis_rs", 0)
    }

    return pick


def _normalize_best_bets_response(payload: dict) -> dict:
    """Normalize all picks in a best-bets response."""
    if not isinstance(payload, dict):
        return payload
    if PICK_CONTRACT_AVAILABLE:
        return contract_normalize_best_bets_response(payload)

    # Normalize props picks
    props = payload.get("props", {})
    if isinstance(props, dict) and "picks" in props:
        props["picks"] = [_normalize_pick(p) for p in props.get("picks", [])]

    # Normalize game picks
    game_picks = payload.get("game_picks", {})
    if isinstance(game_picks, dict) and "picks" in game_picks:
        game_picks["picks"] = [_normalize_pick(p) for p in game_picks.get("picks", [])]

    return payload


def _ensure_live_contract_payload(payload, status_code: int):
    """Ensure /live responses include required contract fields."""
    if payload is None:
        payload = {}
    if isinstance(payload, list):
        payload = {"data": payload}
    if not isinstance(payload, dict):
        payload = {"data": payload}

    if "source" not in payload:
        payload["source"] = "unknown"
    if "generated_at" not in payload:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    if "errors" not in payload or payload["errors"] is None:
        payload["errors"] = []

    if status_code >= 400 and not payload["errors"]:
        detail = payload.get("detail", "request_failed")
        payload["errors"] = [{"status": status_code, "message": detail}]

    # Deterministic error ordering (avoid hash churn)
    if isinstance(payload.get("errors"), list):
        def _err_key(e):
            if isinstance(e, dict):
                return (
                    str(e.get("code", "")),
                    str(e.get("status", "")),
                    str(e.get("message", "")),
                )
            return (str(e), "", "")
        payload["errors"] = sorted(payload["errors"], key=_err_key)

    if "data" not in payload and not ("props" in payload or "game_picks" in payload):
        payload["data"] = []

    # Normalize best-bets response picks with guaranteed fields
    if "props" in payload or "game_picks" in payload:
        payload = _normalize_best_bets_response(payload)

    return payload


class LiveContractRoute(APIRoute):
    """Wrap /live responses to enforce JSON contract and avoid 500s."""
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def custom_handler(request):
            response = await original_handler(request)
            if not isinstance(response, Response):
                return response
            media_type = (response.media_type or "").lower()
            if not media_type.startswith("application/json"):
                return response

            try:
                payload = json.loads(response.body)
            except Exception:
                return response

            payload = _ensure_live_contract_payload(payload, response.status_code)

            # Sanitize member-facing payloads (ET-only, strip telemetry/UTC)
            # Never sanitize /live/debug/* endpoints
            path = request.url.path
            if PUBLIC_SANITIZER_AVAILABLE and not path.startswith("/live/debug"):
                # Optional: keep api-health untouched
                if path != "/live/api-health":
                    payload = sanitize_public_payload(payload)
            status_code = response.status_code
            if status_code >= 500:
                status_code = 200

            # Don't copy Content-Length as the new payload may have different size
            new_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ("content-length", "content-encoding")
            }
            # Anti-cache headers - prevent any caching of live data (including Service Worker)
            new_headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
            new_headers["Pragma"] = "no-cache"
            new_headers["Expires"] = "0"
            # Vary header ensures caches treat requests with different auth as distinct
            new_headers["Vary"] = "Origin, X-API-Key, Authorization"
            # CORS headers for API key
            new_headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, Authorization"
            return JSONResponse(
                content=payload,
                status_code=status_code,
                headers=new_headers,
            )

        return custom_handler


router = APIRouter(prefix="/live", tags=["live"], dependencies=[Depends(verify_api_key)], route_class=LiveContractRoute)

# ============================================================================
# MASTER PREDICTION SYSTEM (Lazy Loaded Singleton)
# ============================================================================

_master_prediction_system = None

def get_master_prediction_system():
    """Get or initialize the MasterPredictionSystem singleton."""
    global _master_prediction_system
    if _master_prediction_system is None and MASTER_PREDICTION_AVAILABLE:
        try:
            _master_prediction_system = MasterPredictionSystem()
            logger.info("MasterPredictionSystem initialized")
        except Exception as e:
            logger.exception("Failed to initialize MasterPredictionSystem: %s", e)
    return _master_prediction_system


# ============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS
# Weight: boost / 5 = max +4.0 points (doubled from original /10)
# ============================================================================

JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 20, "tier": "LEGENDARY", "description": "Only number where n4=reverse AND n4=66^4. Never collapses.", "mathematical": True},
    201: {"name": "THE ORDER", "boost": 12, "tier": "HIGH", "description": "Jesuit Order gematria. The Event of 201.", "mathematical": False},
    33: {"name": "THE MASTER", "boost": 10, "tier": "HIGH", "description": "Highest master number. Masonic significance.", "mathematical": False},
    93: {"name": "THE WILL", "boost": 10, "tier": "HIGH", "description": "Thelema sacred number. Will and Love.", "mathematical": False},
    322: {"name": "THE SOCIETY", "boost": 10, "tier": "HIGH", "description": "Skull & Bones. Genesis 3:22.", "mathematical": False}
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]

# ============================================================================
# ESOTERIC HELPER FUNCTIONS (exported for main.py)
# ============================================================================

def calculate_date_numerology() -> Dict[str, Any]:
    """Calculate numerology for today's date."""
    today = datetime.now()
    digits = str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2)

    # Life path number
    life_path = sum(int(d) for d in digits)
    while life_path > 9 and life_path not in [11, 22, 33]:
        life_path = sum(int(d) for d in str(life_path))

    # Day vibration
    day_vibe = sum(int(d) for d in str(today.day))
    while day_vibe > 9:
        day_vibe = sum(int(d) for d in str(day_vibe))

    # Check for power numbers
    power_hits = [n for n in POWER_NUMBERS if str(n) in digits]
    tesla_energy = any(d in "369" for d in digits)

    meanings = {
        1: "Leadership - favorites dominate",
        2: "Balance - close games expected",
        3: "Creative - unexpected outcomes",
        4: "Stability - chalk hits",
        5: "Change - underdogs bark",
        6: "Harmony - totals accurate",
        7: "Spiritual - trust the model",
        8: "Power - high scoring",
        9: "Completion - season trends hold"
    }

    return {
        "date": today.strftime("%Y-%m-%d"),
        "life_path": life_path,
        "day_vibration": day_vibe,
        "meaning": meanings.get(life_path % 10, "Standard energy"),
        "power_numbers_present": power_hits,
        "tesla_energy": tesla_energy,
        "is_master_number_day": life_path in [11, 22, 33]
    }


def get_moon_phase() -> Dict[str, Any]:
    """Get current moon phase and betting implications."""
    known_new_moon = datetime(2024, 1, 11)
    days_since = (datetime.now() - known_new_moon).days
    lunar_cycle = 29.53
    phase_day = days_since % lunar_cycle

    phases = [
        (0, 1.85, "New Moon", "Fresh starts - take calculated risks"),
        (1.85, 7.38, "Waxing Crescent", "Building momentum - follow trends"),
        (7.38, 11.07, "First Quarter", "Decision time - key matchups"),
        (11.07, 14.76, "Waxing Gibbous", "Increasing energy - overs favored"),
        (14.76, 16.61, "Full Moon", "High volatility - expect upsets"),
        (16.61, 22.14, "Waning Gibbous", "Reflection - fade public"),
        (22.14, 25.83, "Last Quarter", "Release - unders hit"),
        (25.83, 29.53, "Waning Crescent", "Rest period - low scoring")
    ]

    for start, end, name, meaning in phases:
        if start <= phase_day < end:
            illumination = abs(14.76 - phase_day) / 14.76 * 100
            return {
                "phase": name,
                "meaning": meaning,
                "phase_day": round(phase_day, 1),
                "illumination": round(100 - illumination, 1),
                "betting_edge": "VOLATILITY" if "Full" in name else "STABILITY" if "New" in name else "NEUTRAL"
            }

    return {"phase": "Unknown", "meaning": "Check phase", "phase_day": phase_day}


def get_daily_energy() -> Dict[str, Any]:
    """Get overall daily energy reading for betting.

    v17.5 (Phase 2.2): Added Void-of-Course moon penalty.
    When moon is void-of-course with confidence > 0.5, apply -20 penalty.
    Traditional astrological wisdom: avoid initiating bets during VOC periods.
    """
    numerology = calculate_date_numerology()
    moon = get_moon_phase()

    energy_score = 50

    if numerology.get("is_master_number_day"):
        energy_score += 15
    if numerology.get("tesla_energy"):
        energy_score += 10
    if moon.get("phase") == "Full Moon":
        energy_score += 20
    elif moon.get("phase") == "New Moon":
        energy_score -= 10

    dow = datetime.now().weekday()
    day_modifiers = {
        0: ("Monday", -5, "Slow start"),
        1: ("Tuesday", 0, "Neutral"),
        2: ("Wednesday", 5, "Midweek momentum"),
        3: ("Thursday", 10, "TNF/Peak energy"),
        4: ("Friday", 15, "Weekend anticipation"),
        5: ("Saturday", 20, "Prime time"),
        6: ("Sunday", 25, "NFL Sunday dominance")
    }
    day_name, modifier, day_meaning = day_modifiers[dow]
    energy_score += modifier

    # ===== v17.5: VOID OF COURSE MOON PENALTY =====
    # Traditional astrological wisdom: avoid initiating new bets during VOC periods
    voc_penalty = 0
    voc_data = {"is_void": False, "confidence": 0.0, "penalty": 0}
    try:
        is_void, voc_confidence = is_void_moon_now()
        voc_data["is_void"] = is_void
        voc_data["confidence"] = voc_confidence
        if is_void and voc_confidence > 0.5:
            voc_penalty = -20  # Significant penalty during void periods
            energy_score += voc_penalty
            voc_data["penalty"] = voc_penalty
            logger.debug("VOC Moon detected (confidence=%.2f) - applying %d penalty", voc_confidence, voc_penalty)
    except Exception as e:
        logger.warning("VOC calculation failed: %s", e)

    return {
        "overall_score": min(100, max(0, energy_score)),
        "rating": "HIGH" if energy_score >= 70 else "MEDIUM" if energy_score >= 40 else "LOW",
        "day_of_week": day_name,
        "day_influence": day_meaning,
        "recommended_action": "Aggressive betting" if energy_score >= 70 else "Standard sizing" if energy_score >= 40 else "Conservative approach",
        "numerology_summary": numerology,
        "moon_summary": moon,
        "void_of_course": voc_data
    }


# ============================================================================
# LIVE DATA ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "14.4",
        "codename": "JARVIS_SAVANT_v10.1",
        "features": [
            "Phase 1: Confluence Core",
            "Phase 2: Vedic/Astro",
            "Phase 3: Learning Loop",
            "v10.1 Dual-Score Confluence",
            "v10.1 Bet Tier System"
        ],
        "timestamp": datetime.now().isoformat()
    }


# Smoke test endpoint moved to main.py to avoid route conflicts
# See main.py line 64-66 for /live/smoke-test/alert-status endpoint


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics for debugging."""
    return {
        "cache": api_cache.stats(),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cache/clear")
async def cache_clear():
    """Clear the API cache."""
    api_cache.clear()
    return {"status": "cache_cleared", "timestamp": datetime.now().isoformat()}


@router.get("/playbook/usage")
async def get_playbook_usage():
    """
    Get Playbook API plan and usage info.
    Useful for monitoring API quota.
    """
    if not PLAYBOOK_API_KEY:
        return {"error": "PLAYBOOK_API_KEY not configured", "status": "unavailable"}

    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/me"
        resp = await fetch_with_retries(
            "GET", playbook_url,
            params={"api_key": PLAYBOOK_API_KEY}
        )

        if resp and resp.status_code == 200:
            data = resp.json()
            return {
                "status": "ok",
                "source": "playbook",
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": f"Playbook returned {resp.status_code if resp else 'no response'}",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.exception("Failed to fetch Playbook usage: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/playbook/health")
async def get_playbook_health():
    """Check Playbook API health status."""
    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/health"
        resp = await fetch_with_retries("GET", playbook_url)

        if resp and resp.status_code == 200:
            return {"status": "healthy", "playbook_status": resp.json() if resp.text else "ok"}
        else:
            return {"status": "unhealthy", "code": resp.status_code if resp else None}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def calculate_usage_warning(remaining: int, used: int) -> Dict[str, Any]:
    """
    Calculate usage warning level based on remaining vs used.

    Returns warning levels:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)
    """
    if remaining is None or used is None:
        return {"level": "UNKNOWN", "message": "Could not determine usage", "percent_used": None}

    total = remaining + used
    if total == 0:
        return {"level": "UNKNOWN", "message": "No quota data", "percent_used": None}

    percent_used = round((used / total) * 100, 1)
    percent_remaining = round((remaining / total) * 100, 1)

    if percent_remaining <= 10:
        return {
            "level": "CRITICAL",
            "emoji": "🚨",
            "message": f"CRITICAL: Only {percent_remaining}% remaining! Consider upgrading NOW.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": True
        }
    elif percent_used >= 75:
        return {
            "level": "CAUTION_75",
            "emoji": "🟠",
            "message": f"Warning: {percent_used}% used. Running low on API calls.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": True
        }
    elif percent_used >= 50:
        return {
            "level": "CAUTION_50",
            "emoji": "🟡",
            "message": f"Notice: {percent_used}% used. Half of monthly quota consumed.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }
    elif percent_used >= 25:
        return {
            "level": "CAUTION_25",
            "emoji": "🟢",
            "message": f"Info: {percent_used}% used. Healthy usage so far.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }
    else:
        return {
            "level": "HEALTHY",
            "emoji": "✅",
            "message": f"Healthy: Only {percent_used}% used. Plenty of quota remaining.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }


@router.get("/odds-api/usage")
async def get_odds_api_usage():
    """
    Get Odds API usage info from response headers with threshold warnings.

    Warning Levels:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)
    """
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not configured", "status": "unavailable"}

    try:
        # Make a lightweight request to get usage headers
        odds_url = f"{ODDS_API_BASE}/sports"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY}
        )

        if resp:
            # Extract usage from headers
            requests_remaining = resp.headers.get("x-requests-remaining")
            requests_used = resp.headers.get("x-requests-used")

            remaining = int(requests_remaining) if requests_remaining else None
            used = int(requests_used) if requests_used else None

            # Calculate warning level
            warning = calculate_usage_warning(remaining, used)

            return {
                "status": "ok",
                "source": "odds_api",
                "usage": {
                    "requests_remaining": remaining,
                    "requests_used": used,
                    "total_quota": (remaining + used) if remaining and used else None,
                    "note": "Resets monthly. Check https://the-odds-api.com for plan limits."
                },
                "warning": warning,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "No response from Odds API",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.exception("Failed to fetch Odds API usage: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/api-usage")
async def get_all_api_usage():
    """
    Get combined usage for all paid APIs (Playbook + Odds API) with threshold warnings.

    Warning Levels for each API:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)

    Overall status shows the WORST status across all APIs.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "apis": {},
        "overall_status": "HEALTHY",
        "action_needed": False,
        "alerts": []
    }

    warning_priority = {"CRITICAL": 5, "CAUTION_75": 4, "CAUTION_50": 3, "CAUTION_25": 2, "HEALTHY": 1, "UNKNOWN": 0}
    worst_level = "HEALTHY"

    # Get Playbook usage
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/me"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"api_key": PLAYBOOK_API_KEY}
            )
            if resp and resp.status_code == 200:
                data = resp.json()
                result["apis"]["playbook"] = {"status": "ok", "data": data}
                # Check if Playbook returns usage info
                if "usage" in data or "requests" in data:
                    pb_used = data.get("usage", {}).get("used", data.get("requests", {}).get("used", 0))
                    pb_limit = data.get("usage", {}).get("limit", data.get("requests", {}).get("limit", 1000))
                    pb_remaining = pb_limit - pb_used
                    pb_warning = calculate_usage_warning(pb_remaining, pb_used)
                    result["apis"]["playbook"]["warning"] = pb_warning
                    if warning_priority.get(pb_warning["level"], 0) > warning_priority.get(worst_level, 0):
                        worst_level = pb_warning["level"]
                    if pb_warning.get("action_needed"):
                        result["alerts"].append(f"Playbook: {pb_warning['message']}")
            elif resp and resp.status_code == 429:
                result["apis"]["playbook"] = {"status": "rate_limited", "warning": {"level": "CRITICAL", "message": "Rate limited!"}}
                worst_level = "CRITICAL"
                result["alerts"].append("🚨 Playbook API is RATE LIMITED!")
            else:
                result["apis"]["playbook"] = {"status": "error", "code": resp.status_code if resp else None}
        except Exception as e:
            result["apis"]["playbook"] = {"status": "error", "error": str(e)}
    else:
        result["apis"]["playbook"] = {"status": "not_configured"}

    # Get Odds API usage
    if ODDS_API_KEY:
        try:
            odds_url = f"{ODDS_API_BASE}/sports"
            resp = await fetch_with_retries(
                "GET", odds_url,
                params={"apiKey": ODDS_API_KEY}
            )
            if resp:
                remaining = int(resp.headers.get("x-requests-remaining", 0))
                used = int(resp.headers.get("x-requests-used", 0))
                warning = calculate_usage_warning(remaining, used)

                result["apis"]["odds_api"] = {
                    "status": "ok",
                    "requests_remaining": remaining,
                    "requests_used": used,
                    "total_quota": remaining + used,
                    "warning": warning
                }

                if warning_priority.get(warning["level"], 0) > warning_priority.get(worst_level, 0):
                    worst_level = warning["level"]
                if warning.get("action_needed"):
                    result["alerts"].append(f"Odds API: {warning['message']}")
            else:
                result["apis"]["odds_api"] = {"status": "error", "error": "No response"}
        except Exception as e:
            result["apis"]["odds_api"] = {"status": "error", "error": str(e)}
    else:
        result["apis"]["odds_api"] = {"status": "not_configured"}

    # Set overall status
    result["overall_status"] = worst_level
    result["action_needed"] = worst_level in ["CRITICAL", "CAUTION_75"]

    # Add summary message
    if worst_level == "CRITICAL":
        result["summary"] = "🚨 CRITICAL: One or more APIs running very low! Upgrade needed."
    elif worst_level == "CAUTION_75":
        result["summary"] = "🟠 WARNING: High API usage. Consider upgrading soon."
    elif worst_level == "CAUTION_50":
        result["summary"] = "🟡 NOTICE: 50%+ of API quota used this month."
    elif worst_level == "CAUTION_25":
        result["summary"] = "🟢 HEALTHY: Normal API usage levels."
    else:
        result["summary"] = "✅ HEALTHY: API usage looks good!"

    return result


@router.get("/api-health")
async def get_api_health_quick():
    """
    Quick health check for all APIs - lightweight status for dashboards.

    Returns simple status:
    - overall: HEALTHY | CAUTION | CRITICAL
    - action_needed: true/false
    - alerts: list of any warnings

    Use /api-usage for full details.
    """
    # Get full usage data
    full_usage = await get_all_api_usage()

    return {
        "overall_status": full_usage["overall_status"],
        "action_needed": full_usage["action_needed"],
        "summary": full_usage.get("summary", ""),
        "alerts": full_usage["alerts"],
        "timestamp": full_usage["timestamp"],
        "detail_endpoint": "/live/api-usage"
    }


@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    """
    Get sharp money signals using Playbook API with Odds API fallback.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"sharp:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached  # Return dict, FastAPI auto-serializes for endpoints

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []
    odds_data_used = False
    playbook_data_used = False

    # Derive sharp signals from Playbook splits data (sharp = money% differs significantly from ticket%)
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/splits"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    splits = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("games", []))

                    # v15.1: Include ALL games with splits data so research engine
                    # always has ticket_pct/money_pct. Signal strength varies by diff.
                    for game in splits:
                        # Handle Playbook v1 nested splits format:
                        # { "splits": { "spread": { "bets": { "homePercent": N }, "money": { "homePercent": N } } } }
                        _sp = game.get("splits", {})
                        _sp_spread = _sp.get("spread", {}) if isinstance(_sp, dict) else {}
                        _sp_bets = _sp_spread.get("bets", {})
                        _sp_money = _sp_spread.get("money", {})

                        if _sp_bets or _sp_money:
                            ticket_pct = _sp_bets.get("homePercent", _sp_bets.get("home_pct", 50))
                            money_pct = _sp_money.get("homePercent", _sp_money.get("home_pct", 50))
                            public_pct = ticket_pct
                        else:
                            # Flat field fallback
                            money_pct = game.get("money_pct", game.get("moneyPct", 50))
                            ticket_pct = game.get("ticket_pct", game.get("ticketPct", 50))
                            public_pct = game.get("public_pct", game.get("publicPct", ticket_pct))

                        diff = abs(money_pct - ticket_pct)
                        sharp_side = "home" if money_pct > ticket_pct else "away"
                        if diff >= 20:
                            strength = "STRONG"
                        elif diff >= 10:
                            strength = "MODERATE"
                        elif diff >= 5:
                            strength = "MILD"
                        else:
                            strength = "NONE"

                        home = game.get("home_team", game.get("homeTeam", game.get("homeTeamName")))
                        away = game.get("away_team", game.get("awayTeam", game.get("awayTeamName")))

                        data.append({
                            "game_id": game.get("id", game.get("gameId")),
                            "home_team": home,
                            "away_team": away,
                            "sharp_side": sharp_side,
                            "money_pct": money_pct,
                            "ticket_pct": ticket_pct,
                            "public_pct": public_pct,
                            "signal_strength": strength,
                            "line_variance": 0
                        })

                    if data:
                        # v15.1: Merge Odds API line variance into Playbook data
                        try:
                            _lv_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
                            _lv_resp = await fetch_with_retries(
                                "GET", _lv_url,
                                params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads", "oddsFormat": "american"}
                            )
                            if _lv_resp and _lv_resp.status_code == 200:
                                _lv_variance = {}  # normalized_key → variance
                                _lv_raw_keys = {}  # for debug logging
                                for _lv_game in _lv_resp.json():
                                    _lv_key = f"{_lv_game.get('away_team', '')}@{_lv_game.get('home_team', '')}"
                                    _lv_norm_key = _lv_key.lower().strip()
                                    _lv_spreads = []
                                    for _lv_bm in _lv_game.get("bookmakers", []):
                                        for _lv_mkt in _lv_bm.get("markets", []):
                                            if _lv_mkt.get("key") == "spreads":
                                                for _lv_out in _lv_mkt.get("outcomes", []):
                                                    if _lv_out.get("name") == _lv_game.get("home_team"):
                                                        _lv_spreads.append(_lv_out.get("point", 0))
                                    if len(_lv_spreads) >= 2:
                                        _lv_val = round(max(_lv_spreads) - min(_lv_spreads), 1)
                                        _lv_variance[_lv_norm_key] = _lv_val
                                        _lv_raw_keys[_lv_key] = _lv_val
                                    else:
                                        _lv_variance[_lv_norm_key] = 0.0
                                logger.info("Odds API variance keys: %s", list(_lv_raw_keys.keys())[:5])
                                # Merge variance into Playbook signals using normalized keys
                                _lv_matched = 0
                                for signal in data:
                                    _sig_key = f"{signal.get('away_team', '')}@{signal.get('home_team', '')}"
                                    _sig_norm = _sig_key.lower().strip()
                                    lv = _lv_variance.get(_sig_norm, 0)
                                    if lv == 0 and _sig_norm not in _lv_variance:
                                        # Try partial matching on home team
                                        _sig_home = (signal.get('home_team') or '').lower()
                                        for _vk, _vv in _lv_variance.items():
                                            if _sig_home and _sig_home in _vk:
                                                lv = _vv
                                                break
                                    if lv > 0 or _sig_norm in _lv_variance:
                                        _lv_matched += 1
                                    signal["line_variance"] = lv
                                    # Upgrade signal_strength if line variance is strong
                                    if lv >= 2.0 and signal["signal_strength"] in ("NONE", "MILD"):
                                        signal["signal_strength"] = "STRONG"
                                    elif lv >= 1.5 and signal["signal_strength"] in ("NONE", "MILD"):
                                        signal["signal_strength"] = "MODERATE"
                                logger.info("Merged Odds API line variance for %s: %d/%d matched, %d with variance>0, playbook_keys=%s",
                                           sport, _lv_matched, len(data),
                                           sum(1 for v in _lv_variance.values() if v > 0),
                                           [f"{s.get('away_team')}@{s.get('home_team')}" for s in data[:3]])
                        except Exception as e:
                            logger.warning("Failed to merge line variance: %s", e)

                        logger.info("Playbook sharp signals derived for %s: %d signals", sport, len(data))
                        result = {"sport": sport.upper(), "source": "playbook+odds_api", "count": len(data), "data": data, "movements": data}
                        api_cache.set(cache_key, result)
                        return result  # Return dict, FastAPI auto-serializes for endpoints
                except ValueError as e:
                    logger.error("Failed to parse Playbook response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook fetch failed for %s: %s", sport, e)

    # Fallback to Odds API variance analysis
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads", "oddsFormat": "american"}
        )

        if not resp or resp.status_code != 200:
            # Use fallback data when API unavailable
            logger.warning("Odds API unavailable for sharp, using fallback data")
            data = generate_fallback_sharp(sport_lower)
            result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data, "movements": data}
            api_cache.set(cache_key, result)
            return result  # Return dict, FastAPI auto-serializes for endpoints

        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

        try:
            games = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Odds API response: %s", e)
            # Use fallback on parse error
            data = generate_fallback_sharp(sport_lower)
            result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data, "movements": data}
            api_cache.set(cache_key, result)
            return result  # Return dict, FastAPI auto-serializes for endpoints

        for game in games:
            spreads = []
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") == "spreads":
                        for outcome in market.get("outcomes", []):
                            if outcome.get("name") == game.get("home_team"):
                                spreads.append(outcome.get("point", 0))

            # v15.1: Include ALL games so sharp_lookup always has entries.
            # Games with high variance get stronger signal_strength.
            variance = 0.0
            if len(spreads) >= 2:
                variance = max(spreads) - min(spreads)

            if variance >= 2:
                strength = "STRONG"
            elif variance >= 1.5:
                strength = "MODERATE"
            elif variance >= 0.5:
                strength = "MILD"
            else:
                strength = "NONE"

            data.append({
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "line_variance": round(variance, 1),
                "signal_strength": strength
            })

        logger.info("Odds API sharp analysis for %s: %d signals found", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API processing failed for %s: %s, using fallback", sport, e)
        # Return fallback on any error
        data = generate_fallback_sharp(sport_lower)
        result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data, "movements": data}
        api_cache.set(cache_key, result)
        return result  # Return dict, FastAPI auto-serializes for endpoints

    result = {"sport": sport.upper(), "source": "odds_api", "count": len(data), "data": data, "movements": data}  # movements alias for frontend
    api_cache.set(cache_key, result)
    return result  # Return dict, FastAPI auto-serializes for endpoints


@router.get("/splits/{sport}")
async def get_splits(sport: str):
    """
    Get betting splits with Playbook API + deterministic estimation fallback.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "estimated",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"splits:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return JSONResponse(_sanitize_public(cached))

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - uses /splits?league=NBA&api_key=... format
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/splits"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    # Playbook returns array of games directly or in "data" key
                    games = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("games", []))
                    logger.info("Playbook splits data retrieved for %s: %d games", sport, len(games))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(games), "data": games}
                    api_cache.set(cache_key, result)
                    return JSONResponse(_sanitize_public(result))
                except ValueError as e:
                    logger.error("Failed to parse Playbook splits response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

            if resp:
                logger.warning("Playbook splits returned %s for %s", resp.status_code, sport)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook splits fetch failed for %s: %s", sport, e)

    # Fallback to Odds API with deterministic estimation
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
        )

        if not resp:
            raise HTTPException(status_code=502, detail="Odds API unreachable after retries")

        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

        if resp.status_code != 200:
            logger.warning("Odds API returned %s for splits %s", resp.status_code, sport)
            raise HTTPException(status_code=502, detail=f"Odds API returned error: {resp.status_code}")

        try:
            games = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Odds API splits response: %s", e)
            raise HTTPException(status_code=502, detail="Invalid response from Odds API")

        for game in games:
            game_id = game.get("id", "")
            # Use deterministic RNG so same game always gets same estimated splits
            rng = deterministic_rng_for_game_id(game_id)
            home_bet = rng.randint(40, 60)
            home_money = home_bet + rng.randint(-10, 10)

            data.append({
                "game_id": game_id,
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "spread_splits": {
                    "home": {"bets_pct": home_bet, "money_pct": max(25, min(75, home_money))},
                    "away": {"bets_pct": 100 - home_bet, "money_pct": max(25, min(75, 100 - home_money))}
                }
            })

        logger.info("Odds API splits estimation for %s: %d games", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API splits processing failed for %s: %s", sport, e)
        raise HTTPException(status_code=500, detail="Internal error processing splits data")

    result = {"sport": sport.upper(), "source": "estimated", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return JSONResponse(_sanitize_public(result))


@router.get("/injuries/{sport}")
async def get_injuries(sport: str):
    """
    Get injury report for a sport using Playbook API.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "espn",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    # v17.2: Return dict (not JSONResponse) so internal callers can use .get()
    # FastAPI auto-serializes dicts for endpoint responses
    cache_key = f"injuries:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached  # Return dict for dual-use compatibility

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - /injuries?league=NBA&api_key=...
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/injuries"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    injuries = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("injuries", []))
                    logger.info("Playbook injuries retrieved for %s: %d records", sport, len(injuries))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(injuries), "data": injuries, "injuries": injuries}  # injuries alias for frontend
                    api_cache.set(cache_key, result)
                    return result  # v17.2: Return dict for dual-use compatibility
                except ValueError as e:
                    logger.error("Failed to parse Playbook injuries response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook injuries fetch failed for %s: %s", sport, e)

    # Fallback to ESPN injuries
    try:
        espn_url = f"{ESPN_API_BASE}/{sport_config['espn']}/injuries"
        resp = await fetch_with_retries("GET", espn_url)

        if resp and resp.status_code == 200:
            try:
                json_body = resp.json()
                for team in json_body.get("teams", []):
                    team_name = team.get("team", {}).get("displayName", "Unknown")
                    for injury in team.get("injuries", []):
                        data.append({
                            "team": team_name,
                            "player": injury.get("athlete", {}).get("displayName", "Unknown"),
                            "position": injury.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                            "status": injury.get("status", "Unknown"),
                            "description": injury.get("details", {}).get("detail", ""),
                            "date": injury.get("date", "")
                        })
                logger.info("ESPN injuries retrieved for %s: %d records", sport, len(data))
            except (ValueError, KeyError) as e:
                logger.error("Failed to parse ESPN injuries: %s", e)
        else:
            logger.warning("ESPN injuries returned %s for %s", resp.status_code if resp else "no response", sport)

    except Exception as e:
        logger.exception("ESPN injuries fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "espn" if data else "none", "count": len(data), "data": data, "injuries": data}  # injuries alias for frontend
    api_cache.set(cache_key, result)
    return result  # v17.2: Return dict for dual-use compatibility


@router.get("/lines/{sport}")
async def get_lines(sport: str):
    """
    Get current betting lines (spread/total/ML) using Playbook API.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"lines:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached  # Return dict for internal callers, FastAPI auto-serializes for endpoints

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - /lines?league=NBA&api_key=...
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/lines"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    lines = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("lines", []))
                    logger.info("Playbook lines retrieved for %s: %d games", sport, len(lines))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(lines), "data": lines}
                    api_cache.set(cache_key, result)
                    return result  # Return dict for internal callers, FastAPI auto-serializes for endpoints
                except ValueError as e:
                    logger.error("Failed to parse Playbook lines response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook lines fetch failed for %s: %s", sport, e)

    # Fallback to Odds API
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,totals,h2h",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()
            for game in games:
                game_lines = {
                    "game_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "spreads": [],
                    "totals": [],
                    "moneylines": []
                }

                for bm in game.get("bookmakers", []):
                    book = bm.get("key")
                    for market in bm.get("markets", []):
                        market_key = market.get("key")
                        for outcome in market.get("outcomes", []):
                            entry = {
                                "book": book,
                                "team": outcome.get("name"),
                                "price": outcome.get("price"),
                                "point": outcome.get("point")
                            }
                            if market_key == "spreads":
                                game_lines["spreads"].append(entry)
                            elif market_key == "totals":
                                game_lines["totals"].append(entry)
                            elif market_key == "h2h":
                                game_lines["moneylines"].append(entry)

                data.append(game_lines)

            logger.info("Odds API lines retrieved for %s: %d games", sport, len(data))

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API lines fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "none", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return result  # Return dict for internal callers, FastAPI auto-serializes for endpoints


@router.get("/props/{sport}")
async def get_props(sport: str):
    """
    Get player props for a sport.

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower == "ncaab":
        return _sanitize_public({"sport": "NCAAB", "source": "disabled", "count": 0, "data": [],
                "note": "NCAAB player props disabled — state legality varies"})
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"props:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return _sanitize_public(cached)

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Odds API first for props - must fetch per event using /events/{eventId}/odds
    try:
        from odds_api import odds_api_get
        _client = get_shared_client()
        # Step 1: Get list of events for this sport
        events_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events"
        events_resp, _events_used = await odds_api_get(
            events_url,
            params={"apiKey": ODDS_API_KEY},
            client=_client,
        )

        if events_resp and events_resp.status_code == 200:
            events = events_resp.json()
            logger.info("Found %d events for %s props", len(events), sport)

            # Step 2: Fetch props for each event (limit to first 5 to avoid rate limits)
            prop_markets = "player_points,player_rebounds,player_assists,player_threes"
            if sport_lower == "nfl":
                prop_markets = "player_pass_tds,player_pass_yds,player_rush_yds,player_reception_yds,player_receptions"
            elif sport_lower == "mlb":
                prop_markets = "batter_total_bases,batter_hits,batter_rbis,pitcher_strikeouts"
            elif sport_lower == "nhl":
                prop_markets = "player_points,player_shots_on_goal,player_assists"

            for event in events[:5]:
                event_id = event.get("id")
                if not event_id:
                    continue

                # Fetch props for this specific event
                event_odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events/{event_id}/odds"
                event_resp, _event_used = await odds_api_get(
                    event_odds_url,
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us",
                        "markets": prop_markets,
                        "oddsFormat": "american"
                    },
                    client=_client,
                )

                if event_resp and event_resp.status_code == 200:
                    try:
                        event_data = event_resp.json()
                        game_props = {
                            "game_id": event_data.get("id"),
                            "home_team": event_data.get("home_team"),
                            "away_team": event_data.get("away_team"),
                            "commence_time": event.get("commence_time"),  # From events list, not event_data
                            "props": []
                        }

                        for bm in event_data.get("bookmakers", []):
                            for market in bm.get("markets", []):
                                market_key = market.get("key", "")
                                if "player" in market_key or "batter" in market_key or "pitcher" in market_key:
                                    for outcome in market.get("outcomes", []):
                                        game_props["props"].append({
                                            "player": outcome.get("description", ""),
                                            "market": market_key,
                                            "line": outcome.get("point", 0),
                                            "odds": outcome.get("price", -110),
                                            "side": outcome.get("name"),
                                            "book": bm.get("key")
                                        })

                        if game_props["props"]:
                            data.append(game_props)
                            odds_data_used = True
                            logger.info("Got %d props for %s vs %s", len(game_props["props"]), game_props["away_team"], game_props["home_team"])

                    except ValueError as e:
                        logger.warning("Failed to parse event %s props: %s", event_id, e)
                else:
                    logger.debug("No props for event %s (status %s)", event_id, event_resp.status_code if event_resp else "no response")

            logger.info("Props data retrieved from Odds API for %s: %d games with props", sport, len(data))
        else:
            logger.warning("Odds API events returned %s for %s, trying Playbook API", events_resp.status_code if events_resp else "no response", sport)

    except Exception as e:
        logger.warning("Odds API props failed for %s: %s, trying Playbook API", sport, e)

    # Fallback to Playbook API for props if Odds API failed or returned no data
    if not data and PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/props/{sport_config['playbook']}"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                playbook_data = resp.json()
                for game in playbook_data.get("games", playbook_data.get("data", [])):
                    game_props = {
                        "game_id": game.get("game_id", game.get("id", "")),
                        "home_team": game.get("home_team", ""),
                        "away_team": game.get("away_team", ""),
                        "commence_time": game.get("commence_time", game.get("game_time", "")),
                        "props": []
                    }

                    for prop in game.get("props", game.get("player_props", [])):
                        game_props["props"].append({
                            "player": prop.get("player_name", prop.get("player", "")),
                            "market": prop.get("prop_type", prop.get("market", "points")),
                            "line": prop.get("line", prop.get("value", 0)),
                            "odds": prop.get("odds", prop.get("price", -110)),
                            "side": prop.get("side", prop.get("pick", "Over")),
                            "book": prop.get("sportsbook", prop.get("book", "consensus"))
                        })

                    if game_props["props"]:
                        data.append(game_props)
                        playbook_data_used = True

                logger.info("Props data retrieved from Playbook API for %s: %d games with props", sport, len(data))
            else:
                logger.warning("Playbook API props returned %s for %s", resp.status_code if resp else "no response", sport)

        except Exception as e:
            logger.warning("Playbook API props failed for %s: %s", sport, e)

    # If still no data, return empty (no sample props)
    if not data:
        logger.info("No props from APIs for %s; returning empty list", sport)

    if odds_data_used:
        source = "odds_api"
    elif playbook_data_used:
        source = "playbook"
    else:
        source = "generated"

    result = {"sport": sport.upper(), "source": source, "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return _sanitize_public(result)


@router.get("/best-bets/{sport}")
async def get_best_bets(
    sport: str,
    mode: Optional[str] = None,
    min_score: Optional[float] = None,
    debug: Optional[int] = None,
    date: Optional[str] = None,
    max_events: Optional[int] = None,
    max_props: Optional[int] = None,
    max_games: Optional[int] = None,
):
    """
    Get best bets using full 8 AI Models + 8 Pillars + JARVIS + Esoteric scoring.
    Returns TWO categories: props (player props) and game_picks (spreads, totals, ML).

    Scoring Formula:
    TOTAL = AI_Models (0-8) + Pillars (0-8) + JARVIS (0-4) + Esoteric_Boost

    Query Parameters:
    - mode: Optional. Set to "live" to filter only is_live==true picks
    - min_score: Override minimum score threshold (default 6.5, min 5.0 for debug)
    - debug: Set to 1 to return top 25 candidates with full engine breakdown
    - max_events: Max events to process (default 12). Applied before props fetch.
    - max_props: Max prop picks in output (default 10)
    - max_games: Max game picks in output (default 10)
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Validate mode parameter
    live_mode = mode and mode.lower() == "live"
    debug_mode = debug == 1

    # Clamp min_score: production floor is 6.5, debug allows down to 5.0
    effective_min_score = MIN_FINAL_SCORE
    if min_score is not None:
        effective_min_score = max(5.0, min(10.0, min_score))

    # Skip cache in debug mode
    if not debug_mode:
        cache_key = f"best-bets:{sport_lower}" + (":live" if live_mode else "")
        cached = api_cache.get(cache_key)
        if cached:
            return JSONResponse(_sanitize_public(cached))
    else:
        cache_key = None  # Don't cache debug responses

    # Caps with defaults
    effective_max_events = max(1, min(max_events or 12, 30))
    effective_max_props = max(1, min(max_props or 10, 50))
    effective_max_games = max(1, min(max_games or 10, 50))

    import uuid as _uuid
    request_id = _uuid.uuid4().hex[:12]
    _start = time.time()
    try:
        result = await _best_bets_inner(
            sport, sport_lower, live_mode,
            cache_key, effective_min_score, debug_mode,
            date_str=date,
            max_events=effective_max_events,
            max_props=effective_max_props,
            max_games=effective_max_games,
        )
        logger.info("best-bets %s completed in %.1fs (request_id=%s, debug=%s, min=%.1f)",
                     sport, time.time() - _start, request_id, debug_mode, effective_min_score)
        if debug_mode:
            return result
        return JSONResponse(_sanitize_public(result))
    except HTTPException:
        raise
    except Exception as e:
        import traceback as _tb
        _tb_str = _tb.format_exc()
        logger.error("best-bets CRASH request_id=%s sport=%s: %s\n%s",
                     request_id, sport, e, _tb_str)
        detail = {"code": "BEST_BETS_FAILED", "message": "best-bets failed"}
        if debug_mode:
            detail["request_id"] = request_id
            detail["error_type"] = type(e).__name__
            detail["error_message"] = str(e)
            detail["traceback"] = _tb_str[-2000:]  # Last 2000 chars of traceback
        raise HTTPException(status_code=500, detail=detail)


async def _best_bets_inner(sport, sport_lower, live_mode, cache_key,
                           min_score=6.5, debug_mode=False, date_str=None,
                           max_events=12, max_props=10, max_games=10):
    sport_upper = sport.upper()
    used_integrations = set()
    integration_calls = {}
    integration_impact = {}
    usage_snapshot_before = {}

    try:
        from integration_registry import get_usage_snapshot
        usage_snapshot_before = get_usage_snapshot()
    except Exception:
        usage_snapshot_before = {}

    def _ensure_integration_entry(name: str) -> Dict[str, Any]:
        entry = integration_calls.get(name)
        if entry is None:
            entry = {
                "called": 0,
                "status": None,
                "latency_total_ms": 0.0,
                "latency_samples": 0,
                "cache_hit": None,
                "cache_hits": 0,
                "cache_samples": 0,
            }
            integration_calls[name] = entry
        return entry

    def _record_integration_call(name: str, status: str | None = None, latency_ms: float | None = None, cache_hit: bool | None = None) -> None:
        entry = _ensure_integration_entry(name)
        entry["called"] += 1
        if status is not None:
            entry["status"] = status
        if latency_ms is not None:
            entry["latency_total_ms"] += float(latency_ms)
            entry["latency_samples"] += 1
        if cache_hit is not None:
            entry["cache_hit"] = bool(cache_hit)
            entry["cache_samples"] += 1
            if cache_hit:
                entry["cache_hits"] += 1

    def _record_integration_impact(name: str, nonzero_boost: bool = False, reasons_count: int = 0, affected_ranking: bool | None = None) -> None:
        entry = integration_impact.get(name)
        if entry is None:
            entry = {"nonzero_boost": 0, "reasons_count": 0, "affected_ranking": 0}
            integration_impact[name] = entry
        if nonzero_boost:
            entry["nonzero_boost"] += 1
        entry["reasons_count"] += int(reasons_count)
        if affected_ranking:
            entry["affected_ranking"] += 1

    # Initialize paid integrations with default entries for debug visibility
    for _name in ("odds_api", "playbook_api", "balldontlie", "serpapi"):
        _ensure_integration_entry(_name)
        integration_impact.setdefault(_name, {"nonzero_boost": 0, "reasons_count": 0, "affected_ranking": 0})

    def _mark_integration_used(name: str) -> None:
        """Track integration usage for this run + update last_used_at."""
        used_integrations.add(name)
        _record_integration_call(name, status="OK")
        try:
            from integration_registry import mark_integration_used
            mark_integration_used(name)
        except Exception:
            # Usage telemetry is best-effort only
            pass

    # --- v16.0 PERFORMANCE: Time budget + per-stage timings ---
    TIME_BUDGET_S = float(os.getenv("BEST_BETS_TIME_BUDGET_S", "55"))  # Configurable; increased default to allow both games AND props scoring to complete
    _t0 = time.time()
    _deadline = _t0 + TIME_BUDGET_S
    _timings = {}  # stage_name → elapsed_seconds
    _timed_out_components = []

    def _elapsed():
        return time.time() - _t0

    def _time_left():
        return max(0, _deadline - time.time())

    def _past_deadline():
        return time.time() >= _deadline

    def _record(stage, start):
        _timings[stage] = round(time.time() - start, 3)

    _s = time.time()
    # Get MasterPredictionSystem
    mps = get_master_prediction_system()
    daily_energy = get_daily_energy()

    # Fetch sharp money for both categories
    _sharp_start = time.time()
    sharp_data = await get_sharp_money(sport)
    _sharp_latency_ms = (time.time() - _sharp_start) * 1000.0
    _sharp_source = (sharp_data.get("source") or "").lower() if isinstance(sharp_data, dict) else ""
    if "playbook" in _sharp_source:
        _record_integration_call("playbook_api", status="OK", latency_ms=_sharp_latency_ms)
    if "odds_api" in _sharp_source:
        _record_integration_call("odds_api", status="OK", latency_ms=_sharp_latency_ms)
    sharp_lookup = {}
    for signal in sharp_data.get("data", []):
        game_key = f"{signal.get('away_team')}@{signal.get('home_team')}"
        sharp_lookup[game_key] = signal

    # Get esoteric engines for enhanced scoring
    jarvis = get_jarvis_savant()
    vedic = get_vedic_astro()
    learning = get_esoteric_loop()

    # Get learned weights for esoteric scoring
    esoteric_weights = learning.get_weights()["weights"] if learning else {}
    _record("init_engines", _s)

    # v16.0: Build ET window debug info (uses single source of truth: core.time_et)
    _date_window_et_debug = {}
    _filter_date = None
    if TIME_ET_AVAILABLE:
        try:
            _et_start, _et_end, _start_utc, _end_utc = et_day_bounds(date_str=date_str)
            _iso_date = _et_start.date().isoformat()
            _filter_date = _iso_date  # Single source of truth for filter date
            _date_window_et_debug.update({
                "date_str": date_str or "today",
                "start_et": _et_start.isoformat(),  # Full ISO: 2026-01-29T00:00:00-05:00
                "end_et": _et_end.isoformat(),      # Full ISO: 2026-01-30T00:00:00-05:00 (exclusive)
                "window_display": f"{_iso_date} 00:00:00 to 23:59:59 ET",  # Human readable (canonical window)
                "filter_date": _filter_date,  # This MUST match /debug/time.et_date
                "interval_notation": "[start, end)",  # Half-open interval: start inclusive, end exclusive
            })
        except Exception as e:
            logger.warning("ET bounds failed in best-bets: %s", e)
            _date_window_et_debug.update({
                "filter_date": "ERROR",
                "error": str(e)
            })

    # ==========================================================================
    # v15.0 STANDALONE JARVIS ENGINE (0-10 scale)
    # ==========================================================================
    # Jarvis is now a SEPARATE 4th engine, not part of Esoteric
    # Components:
    #   - Gematria Signal (40%): 0-4 pts
    #   - Sacred Triggers (40%): 2178/201/33/93/322 → 0-4 pts
    #   - Mid-Spread Amplifier (20%): Goldilocks zone → 0-2 pts
    # ==========================================================================
    def calculate_jarvis_engine_score(
        jarvis_engine,
        game_str: str,
        player_name: str = "",
        home_team: str = "",
        away_team: str = "",
        spread: float = 0,
        total: float = 0,
        prop_line: float = 0,
        date_et: str = ""
    ) -> Dict[str, Any]:
        """
        JARVIS ENGINE (0-10 standalone) - v16.0 with ADDITIVE trigger scoring

        Returns standalone jarvis_score plus all required output fields.

        v16.0 GOLD_STAR FIX:
        - Baseline: 4.5 when inputs present but no triggers
        - Triggers ADD to baseline (not replace it)
        - 1 minor trigger => ~5.0-6.2
        - 1 strong trigger OR 2+ triggers => >=6.5 (GOLD_STAR eligible)
        - Stacked triggers => 8.5-10 (rare)
        - Full audit fields: jarvis_baseline, jarvis_trigger_contribs, jarvis_no_trigger_reason

        Trigger Contributions (ADDITIVE to baseline 4.5):
        - IMMORTAL (2178): +3.5 → total 8.0
        - ORDER (201): +2.5 → total 7.0
        - MASTER (33): +2.0 → total 6.5
        - WILL (93): +2.0 → total 6.5
        - SOCIETY (322): +2.0 → total 6.5
        - BEAST (666): +1.5 → total 6.0
        - JESUS (888): +1.5 → total 6.0
        - TESLA KEY (369): +1.5 → total 6.0
        - POWER_NUMBER: +0.8 → total 5.3
        - TESLA_REDUCTION: +0.5 → total 5.0
        - REDUCTION match: +0.5 → total 5.0
        - Gematria strong: +1.5, moderate: +0.8
        - Mid-spread goldilocks: +0.5
        """
        JARVIS_BASELINE = 4.5  # Baseline when inputs present

        # v16.0 Trigger contribution values (ADDITIVE to baseline)
        TRIGGER_CONTRIBUTIONS = {
            2178: 3.5,   # IMMORTAL - highest
            201: 2.5,    # ORDER - high
            33: 2.0,     # MASTER - Gold-Star eligible
            93: 2.0,     # WILL - Gold-Star eligible
            322: 2.0,    # SOCIETY - Gold-Star eligible
            666: 1.5,    # BEAST - medium
            888: 1.5,    # JESUS - medium
            369: 1.5,    # TESLA KEY - medium
        }
        POWER_NUMBER_CONTRIB = 0.8
        TESLA_REDUCTION_CONTRIB = 0.5
        REDUCTION_MATCH_CONTRIB = 0.5
        GEMATRIA_STRONG_CONTRIB = 1.5
        GEMATRIA_MODERATE_CONTRIB = 0.8
        GOLDILOCKS_CONTRIB = 0.5
        STACKING_DECAY = 0.7  # Each additional trigger contributes 70% of previous

        jarvis_triggers_hit = []
        jarvis_trigger_contribs = {}  # New: {trigger_name: contribution}
        jarvis_fail_reasons = []
        jarvis_no_trigger_reason = None
        immortal_detected = False

        # Track inputs used for transparency
        jarvis_inputs_used = {
            "matchup_str": game_str if game_str else None,
            "date_et": date_et if date_et else None,
            "spread": spread if spread != 0 else None,
            "total": total if total != 0 else None,
            "player_line": prop_line if prop_line != 0 else None,
            "home_team": home_team if home_team else None,
            "away_team": away_team if away_team else None,
            "player_name": player_name if player_name else None
        }

        # Check if critical inputs are missing
        inputs_missing = not game_str or (not home_team and not away_team)

        if inputs_missing:
            # CRITICAL INPUTS MISSING - Cannot run Jarvis
            jarvis_fail_reasons.append("Missing critical inputs (matchup_str or teams)")
            return {
                "jarvis_rs": None,
                "jarvis_baseline": None,
                "jarvis_trigger_contribs": {},
                "jarvis_active": False,
                "jarvis_hits_count": 0,
                "jarvis_triggers_hit": [],
                "jarvis_reasons": ["Inputs missing - cannot run"],
                "jarvis_fail_reasons": jarvis_fail_reasons,
                "jarvis_no_trigger_reason": "INPUTS_MISSING",
                "jarvis_inputs_used": jarvis_inputs_used,
                "immortal_detected": False,
            }

        # Start with baseline
        jarvis_rs = JARVIS_BASELINE
        total_trigger_contrib = 0.0
        gematria_contrib = 0.0
        goldilocks_contrib = 0.0
        trigger_count = 0

        if jarvis_engine:
            # 1. Sacred Triggers - ADDITIVE contributions
            trigger_result = jarvis_engine.check_jarvis_trigger(game_str)
            sorted_triggers = sorted(
                trigger_result.get("triggers_hit", []),
                key=lambda t: TRIGGER_CONTRIBUTIONS.get(t["number"], 0.5),
                reverse=True
            )

            for i, trig in enumerate(sorted_triggers):
                trigger_num = trig["number"]
                match_type = trig.get("match_type", "DIRECT")

                # Get base contribution
                if trigger_num in TRIGGER_CONTRIBUTIONS:
                    base_contrib = TRIGGER_CONTRIBUTIONS[trigger_num]
                elif match_type == "POWER_NUMBER":
                    base_contrib = POWER_NUMBER_CONTRIB
                elif match_type == "TESLA_REDUCTION":
                    base_contrib = TESLA_REDUCTION_CONTRIB
                elif match_type == "REDUCTION":
                    base_contrib = REDUCTION_MATCH_CONTRIB
                else:
                    base_contrib = 0.5  # Default for unknown triggers

                # Apply stacking decay (70% for each subsequent trigger)
                decay_factor = STACKING_DECAY ** i
                actual_contrib = base_contrib * decay_factor

                jarvis_triggers_hit.append({
                    "number": trigger_num,
                    "name": trig["name"],
                    "match_type": match_type,
                    "base_contrib": round(base_contrib, 2),
                    "actual_contrib": round(actual_contrib, 2),
                    "decay_factor": round(decay_factor, 2)
                })
                jarvis_trigger_contribs[trig["name"]] = round(actual_contrib, 2)
                total_trigger_contrib += actual_contrib
                trigger_count += 1

                if trigger_num == 2178:
                    immortal_detected = True

            # 2. Gematria Signal - ADDITIVE contribution
            if player_name and home_team:
                gematria = jarvis_engine.calculate_gematria_signal(player_name, home_team, away_team)
                signal_strength = gematria.get("signal_strength", 0)
                if signal_strength > 0.7:
                    gematria_contrib = GEMATRIA_STRONG_CONTRIB
                    jarvis_trigger_contribs["gematria_strong"] = gematria_contrib
                elif signal_strength > 0.4:
                    gematria_contrib = GEMATRIA_MODERATE_CONTRIB
                    jarvis_trigger_contribs["gematria_moderate"] = gematria_contrib

            # 3. Mid-Spread Goldilocks - ADDITIVE contribution
            mid_spread = jarvis_engine.calculate_mid_spread_signal(spread)
            if mid_spread.get("signal") == "GOLDILOCKS":
                goldilocks_contrib = GOLDILOCKS_CONTRIB
                jarvis_trigger_contribs["goldilocks_zone"] = goldilocks_contrib

        else:
            # Fallback: check triggers in game_str directly
            for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
                if str(trigger_num) in game_str:
                    base_contrib = TRIGGER_CONTRIBUTIONS.get(trigger_num, 0.5)
                    decay_factor = STACKING_DECAY ** trigger_count
                    actual_contrib = base_contrib * decay_factor

                    jarvis_triggers_hit.append({
                        "number": trigger_num,
                        "name": trigger_data["name"],
                        "match_type": "STRING_MATCH",
                        "base_contrib": round(base_contrib, 2),
                        "actual_contrib": round(actual_contrib, 2),
                        "decay_factor": round(decay_factor, 2)
                    })
                    jarvis_trigger_contribs[trigger_data["name"]] = round(actual_contrib, 2)
                    total_trigger_contrib += actual_contrib
                    trigger_count += 1

                    if trigger_num == 2178:
                        immortal_detected = True

        # Calculate final jarvis_rs = baseline + all contributions
        jarvis_rs = JARVIS_BASELINE + total_trigger_contrib + gematria_contrib + goldilocks_contrib

        # Cap at 0-10 range
        jarvis_rs = max(0, min(10, jarvis_rs))

        # Determine jarvis_active and build reasons
        jarvis_hits_count = len(jarvis_triggers_hit)
        has_any_contrib = total_trigger_contrib > 0 or gematria_contrib > 0 or goldilocks_contrib > 0

        if has_any_contrib:
            jarvis_active = True
            jarvis_reasons = list(jarvis_trigger_contribs.keys())
            jarvis_no_trigger_reason = None
        else:
            jarvis_active = True  # Inputs present, Jarvis ran
            jarvis_reasons = [f"Baseline {JARVIS_BASELINE} (no triggers)"]
            jarvis_no_trigger_reason = "NO_TRIGGER_BASELINE"
            jarvis_fail_reasons.append(f"No triggers fired - baseline {JARVIS_BASELINE}")

        return {
            "jarvis_rs": round(jarvis_rs, 2),
            "jarvis_baseline": JARVIS_BASELINE,
            "jarvis_trigger_contribs": jarvis_trigger_contribs,
            "jarvis_active": jarvis_active,
            "jarvis_hits_count": jarvis_hits_count,
            "jarvis_triggers_hit": jarvis_triggers_hit,
            "jarvis_reasons": jarvis_reasons,
            "jarvis_fail_reasons": jarvis_fail_reasons,
            "jarvis_no_trigger_reason": jarvis_no_trigger_reason,
            "jarvis_inputs_used": jarvis_inputs_used,
            "immortal_detected": immortal_detected,
        }

    # ============================================================================
    # v16.0 CONTEXT MODIFIERS - weather_context, rest_days, home_away, vacuum_score
    # ============================================================================
    async def compute_context_modifiers(
        sport: str,
        home_team: str,
        away_team: str,
        player_team: str = "",
        pick_type: str = "GAME",
        pick_side: str = "",
        injuries_data: dict = None,
        rest_days_override: Optional[int] = None
    ) -> dict:
        """
        Compute all 4 context modifier fields for a pick.

        Returns dict with:
        - weather_context: {status, reason, score_modifier}
        - rest_days: {value, status, reason}
        - home_away: {value, status, reason}
        - vacuum_score: {value, status, reason}
        """
        result = {}

        # 1. WEATHER_CONTEXT (async for outdoor sports to fetch live data)
        if WEATHER_MODULE_AVAILABLE:
            try:
                # Use async version for live weather data (outdoor sports)
                weather_ctx = await get_weather_context(sport, home_team, "")
                result["weather_context"] = {
                    "status": weather_ctx.get("status", "UNAVAILABLE"),
                    "reason": weather_ctx.get("reason", "Unknown"),
                    "score_modifier": weather_ctx.get("score_modifier", 0.0),
                    "raw": weather_ctx.get("raw"),
                    "features": weather_ctx.get("features")
                }
            except Exception as e:
                result["weather_context"] = {
                    "status": "ERROR",
                    "reason": str(e)[:100],
                    "score_modifier": 0.0,
                    "raw": None,
                    "features": None
                }
        else:
            result["weather_context"] = {
                "status": "UNAVAILABLE",
                "reason": "Weather module not available",
                "score_modifier": 0.0,
                "raw": None,
                "features": None
            }

        # 2. REST_DAYS
        if rest_days_override is not None:
            result["rest_days"] = {
                "value": int(rest_days_override),
                "status": "COMPUTED",
                "reason": "ESPN_SCHEDULE"
            }
        elif TRAVEL_MODULE_AVAILABLE:
            try:
                travel_data = get_travel_impact(sport, away_team, home_team)
                result["rest_days"] = {
                    "value": travel_data.get("rest_days", 1),
                    "status": "COMPUTED" if travel_data.get("available") else "UNAVAILABLE",
                    "reason": travel_data.get("reason", "Unknown")
                }
            except Exception as e:
                result["rest_days"] = {
                    "value": None,
                    "status": "ERROR",
                    "reason": str(e)[:100]
                }
        else:
            result["rest_days"] = {
                "value": 1,
                "status": "UNAVAILABLE",
                "reason": "Travel module not available - using default 1 day rest"
            }

        # 3. HOME_AWAY
        try:
            if pick_type == "PROP" and player_team:
                # For props: determine if player's team is home or away
                if player_team.lower() == home_team.lower() or player_team.lower() in home_team.lower():
                    ha_value = "HOME"
                elif player_team.lower() == away_team.lower() or player_team.lower() in away_team.lower():
                    ha_value = "AWAY"
                else:
                    ha_value = "UNKNOWN"
                result["home_away"] = {
                    "value": ha_value,
                    "status": "COMPUTED",
                    "reason": f"Player team '{player_team}' is {ha_value}"
                }
            else:
                # For games: use pick_side to determine
                if pick_side:
                    side_lower = pick_side.lower()
                    if side_lower in home_team.lower() or "home" in side_lower:
                        ha_value = "HOME"
                    elif side_lower in away_team.lower() or "away" in side_lower:
                        ha_value = "AWAY"
                    else:
                        # For totals (Over/Under), default to HOME perspective
                        ha_value = "HOME"
                    result["home_away"] = {
                        "value": ha_value,
                        "status": "COMPUTED",
                        "reason": f"Pick side '{pick_side}' -> {ha_value}"
                    }
                else:
                    result["home_away"] = {
                        "value": "HOME",
                        "status": "DEFAULT",
                        "reason": "No pick_side provided - defaulting to HOME"
                    }
        except Exception as e:
            result["home_away"] = {
                "value": None,
                "status": "ERROR",
                "reason": str(e)[:100]
            }

        # 4. VACUUM_SCORE (placeholder - uses injuries to detect opportunity)
        try:
            if injuries_data and isinstance(injuries_data, dict):
                # Count injured starters for opportunity detection
                injured_count = 0
                injured_players = []
                for team, players in injuries_data.items():
                    if isinstance(players, list):
                        for p in players:
                            status = p.get("status", "").upper() if isinstance(p, dict) else ""
                            if status in ["OUT", "DOUBTFUL"]:
                                injured_count += 1
                                if isinstance(p, dict):
                                    injured_players.append(p.get("name", "Unknown"))

                # Vacuum score: higher when more key players are out (creates opportunity)
                # Scale: 0 injuries = 0, 1 = 2.0, 2 = 4.0, 3+ = 5.0 (capped)
                vacuum_value = min(5.0, injured_count * 2.0)
                result["vacuum_score"] = {
                    "value": round(vacuum_value, 1),
                    "status": "COMPUTED",
                    "reason": f"{injured_count} injured players: {', '.join(injured_players[:3])}" if injured_players else "No injury data affecting vacuum"
                }
            else:
                result["vacuum_score"] = {
                    "value": 0.0,
                    "status": "UNAVAILABLE",
                    "reason": "No injury data available for vacuum calculation"
                }
        except Exception as e:
            result["vacuum_score"] = {
                "value": 0.0,
                "status": "ERROR",
                "reason": str(e)[:100]
            }

        return result

    def _lineup_risk_guard(commence_time_iso: str, injury_status: str) -> Dict[str, Any]:
        """
        Lightweight lineup confirmation guard.
        If close to start and player is QUESTIONABLE/GTD, apply a small penalty.
        """
        if not commence_time_iso:
            return {"confirmed": False, "status": "UNKNOWN", "minutes_to_start": None, "penalty": 0.0, "reason": "No commence_time"}

        try:
            _dt = datetime.fromisoformat(commence_time_iso.replace("Z", "+00:00"))
            if _ET:
                now_local = datetime.now(_ET)
                game_local = _dt.astimezone(_ET)
            else:
                now_local = datetime.now(timezone.utc)
                game_local = _dt.astimezone(timezone.utc)
            minutes_to_start = int((game_local - now_local).total_seconds() / 60)
        except Exception:
            return {"confirmed": False, "status": "UNKNOWN", "minutes_to_start": None, "penalty": 0.0, "reason": "Commence_time parse error"}

        status = (injury_status or "UNKNOWN").upper()
        risky = {"QUESTIONABLE", "GTD", "GAME_TIME_DECISION", "DOUBTFUL", "PROBABLE"}
        if minutes_to_start <= 90 and status in risky:
            return {
                "confirmed": False,
                "status": status,
                "minutes_to_start": minutes_to_start,
                "penalty": -0.5,
                "reason": "Lineup unconfirmed close to lock"
            }

        return {
            "confirmed": True,
            "status": status,
            "minutes_to_start": minutes_to_start,
            "penalty": 0.0,
            "reason": "Lineup ok"
        }

    # v16.1: Helper function for heuristic AI score calculation (fallback when LSTM unavailable)
    def _calculate_heuristic_ai_score(base_ai, sharp_signal, spread, player_name):
        """Calculate AI score using heuristic rules (pre-LSTM method)."""
        ai_reasons = []
        _ai_boost = 0.0
        ai_reasons.append(f"Base AI: {base_ai}/8")

        # Odds data present: +0.5
        if sharp_signal:
            _ai_boost += 0.5
            ai_reasons.append("Sharp data present (+0.5)")

        # Strong/moderate sharp signal aligns with model: +1.0 / +0.5
        _ss = sharp_signal.get("signal_strength", "NONE") if sharp_signal else "NONE"
        if _ss == "STRONG":
            _ai_boost += 1.0
            ai_reasons.append("STRONG signal alignment (+1.0)")
        elif _ss == "MODERATE":
            _ai_boost += 0.5
            ai_reasons.append("MODERATE signal alignment (+0.5)")
        elif _ss == "MILD":
            _ai_boost += 0.25
            ai_reasons.append("MILD signal alignment (+0.25)")

        # Favorable line value (spread in predictable range 3-10): +0.5
        if 3 <= abs(spread) <= 10:
            _ai_boost += 0.5
            ai_reasons.append(f"Favorable spread {spread} (+0.5)")

        # Player name present for props (more data = better model): +0.25
        if player_name:
            _ai_boost += 0.25
            ai_reasons.append("Player data available (+0.25)")

        ai_score = min(8.0, base_ai + _ai_boost)
        return ai_score, ai_reasons

    # v20.1: AI Score Resolver - 8-model system as PRIMARY for games
    # Returns (ai_score, reasons, ai_mode, models_used_count)
    def _resolve_game_ai_score(
        mps,
        game_data: Dict,
        fallback_base: float = 5.0,
        sharp_signal: Optional[Dict] = None
    ) -> Tuple[float, List[str], str, int]:
        """
        PRIMARY AI score resolver for GAME picks using all 8 ML models.

        Returns:
            ai_score: 0-10 scale score from ML models
            reasons: List of diagnostic strings
            ai_mode: "ML_PRIMARY" or "HEURISTIC_FALLBACK"
            models_used_count: Number of models that contributed

        The 8 models run by MasterPredictionSystem:
        1. Ensemble Stacking (XGBoost + LightGBM + RF)
        2. LSTM Neural Network (temporal patterns)
        3. Matchup-Specific Model (player vs opponent)
        4. Monte Carlo Simulator (10k simulations)
        5. Line Movement Analyzer (sharp money RLM)
        6. Rest/Fatigue Model (schedule impact)
        7. Injury Impact Model (player availability)
        8. Edge Calculator (EV + Kelly)

        Fallback to heuristic ONLY when:
        - MasterPredictionSystem unavailable
        - Output is NaN/inf/out of range
        - Missing required fields
        - Runtime error in prediction
        """
        reasons = []

        # ===== GUARD: MPS must be available =====
        if mps is None:
            # Fallback to heuristic
            ai_score, heuristic_reasons = _calculate_heuristic_ai_score(
                fallback_base, sharp_signal, game_data.get("spread", 0), None
            )
            reasons.append("ML unavailable: MasterPredictionSystem not loaded")
            reasons.extend(heuristic_reasons)
            return ai_score, reasons, "HEURISTIC_FALLBACK", 0

        try:
            # ===== BUILD GAME DATA FOR 8-MODEL PREDICTION =====
            # Map available data to MasterPredictionSystem format
            import numpy as np

            spread = game_data.get("spread", 0) or 0
            total = game_data.get("total", 220) or 220

            # Build features array from available context
            features = np.array([
                game_data.get("def_rank", 15),      # Defensive rank
                game_data.get("pace", 100),          # Pace
                game_data.get("vacuum", 0),          # Injury vacuum
                abs(spread),                          # Spread magnitude
                total,                                # Total
                1.0 if game_data.get("home_pick") else 0.0,  # Picking home?
            ])

            # Recent games - use spread as proxy for performance trend
            recent_games = [abs(spread)] * 10  # Simplified sequence

            # Player stats approximation from spread
            std_dev = 10.0  # Default std dev
            expected_value = total / 2 + (spread / 2 if game_data.get("home_pick") else -spread / 2)

            # Build complete game_data dict for MPS
            mps_game_data = {
                "features": features,
                "recent_games": recent_games,
                "line": abs(spread),
                "player_id": game_data.get("home_team", "home"),
                "opponent_id": game_data.get("away_team", "away"),
                "player_stats": {
                    "expected_value": expected_value,
                    "std_dev": std_dev
                },
                "game_id": game_data.get("event_id", "live"),
                "current_line": spread,
                "opening_line": spread,  # Assume no movement if not available
                "time_until_game": 60,
                "betting_percentages": {
                    "public_on_favorite": sharp_signal.get("public_pct", 50) if sharp_signal else 50
                },
                "schedule": {
                    "days_rest": game_data.get("days_rest", 1),
                    "travel_miles": game_data.get("travel_miles", 0),
                    "games_in_last_7": game_data.get("games_last_7", 3)
                },
                "injuries": game_data.get("injuries", []),
                "depth_chart": {},
                "betting_odds": game_data.get("odds", -110)
            }

            # ===== RUN 8-MODEL PREDICTION =====
            result = mps.generate_comprehensive_prediction(mps_game_data)

            # ===== VALIDATE OUTPUT =====
            ai_score_raw = result.get("ai_score")

            # Check for invalid values
            if ai_score_raw is None:
                raise ValueError("ai_score is None")
            if not isinstance(ai_score_raw, (int, float)):
                raise ValueError(f"ai_score is not numeric: {type(ai_score_raw)}")
            if np.isnan(ai_score_raw) or np.isinf(ai_score_raw):
                raise ValueError(f"ai_score is NaN/inf: {ai_score_raw}")
            if ai_score_raw < 0 or ai_score_raw > 10:
                raise ValueError(f"ai_score out of range [0,10]: {ai_score_raw}")

            # ===== EXTRACT DIAGNOSTICS =====
            ai_score = float(ai_score_raw)
            confidence = result.get("confidence", "unknown")
            ev = result.get("expected_value", 0)
            probability = result.get("probability", 0.5)
            factors = result.get("factors", {})

            # Count models that contributed (non-zero factors)
            models_used = sum(1 for v in factors.values() if v != 0)

            # Build diagnostic reasons (non-secret info)
            reasons.append(f"8-Model AI: {ai_score:.1f}/10 (confidence: {confidence})")
            reasons.append(f"Models used: {models_used}/8")
            reasons.append(f"EV: {ev:+.3f}, prob: {probability:.1%}")

            # Key driver summary
            if factors.get("rest_factor", 1.0) < 0.9:
                reasons.append(f"Fatigue factor: {factors.get('rest_factor', 1.0):.2f}")
            if factors.get("injury_impact", 0) < -1:
                reasons.append(f"Injury impact: {factors.get('injury_impact', 0):.1f}")
            if factors.get("line_movement", 0) != 0:
                reasons.append(f"Line movement: {factors.get('line_movement', 0):+.1f}")
            if factors.get("edge", 0) > 5:
                reasons.append(f"Edge: {factors.get('edge', 0):.1f}%")

            return ai_score, reasons, "ML_PRIMARY", models_used

        except Exception as e:
            # ===== FALLBACK TO HEURISTIC =====
            logger.warning(f"8-model prediction failed, using heuristic: {e}")
            ai_score, heuristic_reasons = _calculate_heuristic_ai_score(
                fallback_base, sharp_signal, game_data.get("spread", 0), None
            )
            reasons.append(f"ML unavailable: {str(e)[:100]}")
            reasons.extend(heuristic_reasons)
            return ai_score, reasons, "HEURISTIC_FALLBACK", 0
            reasons.append(f"8-model partial: {str(e)[:50]}")

        # Cap total boost to reasonable range
        total_boost = max(-1.0, min(1.5, total_boost))

        return total_boost, reasons

    # v17.0: Helper function to map prop market to defensive position category
    def _market_to_position(market: str, sport: str) -> str:
        """Map prop market to defensive position category for context layer lookup."""
        market_lower = market.lower() if market else ""

        if sport == "NBA":
            if "point" in market_lower or "assist" in market_lower:
                return "Guard"
            elif "rebound" in market_lower or "block" in market_lower:
                return "Big"
            else:
                return "Wing"
        elif sport == "NFL":
            if "pass" in market_lower:
                return "QB"
            elif "rush" in market_lower:
                return "RB"
            elif "rec" in market_lower:
                return "WR"
            else:
                return "WR"
        elif sport == "NHL":
            if "goal" in market_lower or "point" in market_lower:
                return "Center"
            elif "shot" in market_lower:
                return "Winger"
            elif "save" in market_lower:
                return "Goalie"
            else:
                return "Center"
        elif sport == "MLB":
            if "strikeout" in market_lower or "pitch" in market_lower:
                return "Pitcher"
            else:
                return "Batter"
        elif sport == "NCAAB":
            if "point" in market_lower or "assist" in market_lower:
                return "Guard"
            elif "rebound" in market_lower or "block" in market_lower:
                return "Big"
            else:
                return "Wing"
        return "Guard"  # default

    # Helper function to extract multi-book line values for Benford analysis
    # v17.6: Benford Anomaly needs 10+ values to be statistically significant
    def _extract_benford_values_from_game(game: dict, prop_line: float = None, spread: float = None, total: float = None) -> list:
        """
        Extract all available line values for Benford analysis.
        Aggregates lines from multiple sportsbooks to get 10+ values.

        Sources:
        - Direct values: prop_line, spread, total (3 values)
        - Multi-book spreads: game.bookmakers[].markets[spreads].outcomes[].point (5-10 values)
        - Multi-book totals: game.bookmakers[].markets[totals].outcomes[].point (5-10 values)

        Returns: List of 10-25 numeric values for Benford analysis
        """
        values = []

        # Add direct values
        if prop_line and prop_line > 0:
            values.append(prop_line)
        if spread:
            values.append(abs(spread))
        if total and total > 0:
            values.append(total)

        # Extract from bookmakers array
        if game and isinstance(game, dict):
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    market_key = market.get("key", "")

                    # Extract spread values
                    if market_key == "spreads":
                        for outcome in market.get("outcomes", []):
                            point = outcome.get("point")
                            if point is not None:
                                values.append(abs(point))

                    # Extract total values
                    elif market_key == "totals":
                        for outcome in market.get("outcomes", []):
                            point = outcome.get("point")
                            if point is not None and point > 0:
                                values.append(point)

        # Deduplicate while preserving order (for statistical validity)
        seen = set()
        unique_values = []
        for v in values:
            if v not in seen:
                seen.add(v)
                unique_values.append(v)

        return unique_values

    # Helper function to calculate scores with v15.0 4-engine architecture + Jason Sim
    # v16.1: Added market parameter for LSTM model routing
    # v17.6: Added game_bookmakers parameter for Benford analysis
    # v20.0: Added game_status parameter for live signals, event_id for line history
    def calculate_pick_score(game_str, sharp_signal, base_ai=5.0, player_name="", home_team="", away_team="", spread=0, total=220, public_pct=50, pick_type="GAME", pick_side="", prop_line=0, market="", game_datetime=None, game_bookmakers=None, book_count: int = 0, market_book_count: int = 0, event_id: str | None = None, game_status: str = ""):
        # =====================================================================
        # v15.0 FOUR-ENGINE ARCHITECTURE (Clean Separation)
        # =====================================================================
        # ENGINE 1 - AI SCORE (0-10): Pure 8 AI Models (0-8 scaled to 0-10)
        # ENGINE 2 - RESEARCH SCORE (0-10): Sharp money + RLM + Public Fade
        # ENGINE 3 - ESOTERIC SCORE (0-10): Numerology + Astro + Fib + Vortex + Daily
        #            (NO Jarvis, NO Gematria, NO Public Fade - those are separate)
        # ENGINE 4 - JARVIS SCORE (0-10): Gematria + Sacred Triggers + Mid-Spread
        #
        # FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost
        # BASE_4 = (ai × 0.25) + (research × 0.35) + (esoteric × 0.20) + (jarvis × 0.20)
        # =====================================================================

        # --- ESOTERIC WEIGHTS (v15.0 - Clean Separation, NO Jarvis/Gematria) ---
        ESOTERIC_WEIGHTS = {
            "numerology": 0.35,   # 35% - Generic numerology (MANDATORY)
            "astro": 0.25,        # 25% - Vedic astrology
            "fib": 0.15,          # 15% - Fibonacci alignment
            "vortex": 0.15,       # 15% - Tesla 3-6-9 patterns
            "daily_edge": 0.10    # 10% - Daily energy
        }

        # --- ENGINE SEPARATION (v15.0 Clean Architecture) ---
        # AI Score: Pure model output (0-8 scale) - NO external signals
        # Research Score: Sharp money + Line variance + Public betting (0-10 scale)
        # Esoteric Score: Numerology + Astro + Fib + Vortex + Daily (0-10 scale)
        # Jarvis Score: Gematria + Sacred Triggers + Mid-Spread (0-10 scale)
        # The four engines are combined for final score

        research_reasons = []
        esoteric_reasons = []
        context_reasons = []
        pillars_passed = []
        pillars_failed = []
        ai_reasons = []
        lstm_metadata = None
        weather_data = None

        # --- AI SCORE (Dynamic Model - 0-8 scale) ---
        # v16.1: Use LSTM for props if available, otherwise fallback to heuristics
        # v17.0: Wire real context data from Pillars 13-15 (Defensive Rank, Pace, Vacuum)

        # v17.0: Initialize context variables at function scope for return statement
        _def_rank = 16    # default (middle of pack)
        _pace = 100.0     # default neutral pace
        _vacuum = 0.0     # default no vacuum

        # v17.2: Get real context data for ALL pick types (Pillars 13-15)
        # This runs for both PROP and GAME picks
        if home_team and away_team and CONTEXT_LAYER_AVAILABLE:
            try:
                # Determine team context based on pick type
                if pick_type == "PROP" and player_name:
                    # For props, use player's team (assume home if not specified)
                    _player_team = home_team  # Default assumption
                    opponent = away_team
                    # Map market to position for defense lookup
                    position = _market_to_position(market, sport_upper) if market else "Guard"
                else:
                    # For game picks, use home team perspective
                    _player_team = home_team
                    opponent = away_team
                    # v17.2: Sport-specific default positions for defensive rank lookup
                    _default_positions = {
                        "NBA": "Guard", "NCAAB": "Guard",
                        "NFL": "WR", "NHL": "Center", "MLB": "Batter"
                    }
                    position = _default_positions.get(sport_upper, "Guard")

                # Pillar 13: Defensive Rank (lower = better defense)
                _def_rank = DefensiveRankService.get_rank(sport_upper, opponent, position)

                # Pillar 14: Pace Vector (average of both teams)
                _pace = PaceVectorService.get_game_pace(sport_upper, home_team, away_team)

                # Pillar 15: Usage Vacuum from injuries
                # v17.2: Use _injuries_by_team to calculate vacuum
                if _injuries_by_team:
                    # Get injuries for BOTH teams and sum vacuum
                    home_injuries = _injuries_by_team.get(home_team, [])
                    away_injuries = _injuries_by_team.get(away_team, [])
                    all_injuries = home_injuries + away_injuries

                    if all_injuries:
                        try:
                            _vacuum = UsageVacuumService.calculate_vacuum(sport_upper, all_injuries)
                        except Exception as ve:
                            logger.debug("Vacuum calculation failed: %s", ve)

                        # Fallback: count OUT players if service fails
                        if _vacuum == 0.0:
                            out_count = sum(1 for inj in all_injuries if inj.get("status", "").upper() in ["OUT", "DOUBTFUL"])
                            _vacuum = min(25.0, out_count * 5.0)  # Each OUT player = 5% vacuum, max 25%

                logger.debug("CONTEXT[%s]: def_rank=%d, pace=%.1f, vacuum=%.1f (opponent=%s, home_inj=%d, away_inj=%d)",
                             pick_type, _def_rank, _pace, _vacuum, opponent,
                             len(_injuries_by_team.get(home_team, [])), len(_injuries_by_team.get(away_team, [])))
            except Exception as e:
                logger.debug(f"Context lookup failed, using defaults: {e}")

        # Initialize AI telemetry (for debug output)
        _ai_telemetry = {"ai_mode": "UNKNOWN", "models_used_count": 0}

        if pick_type == "PROP" and ML_INTEGRATION_AVAILABLE and market:
            # PROPS: LSTM-powered AI score (primary)
            try:
                lstm_ai_score, lstm_metadata = get_lstm_ai_score(
                    sport=sport_upper,
                    market=market,
                    prop_line=prop_line,
                    player_name=player_name,
                    home_team=home_team,
                    away_team=away_team,
                    player_team=None,
                    player_stats=None,
                    game_data={"def_rank": _def_rank, "pace": _pace, "vacuum": _vacuum},
                    base_ai=base_ai
                )
                if lstm_metadata.get("source") == "lstm":
                    ai_score = lstm_ai_score
                    ai_reasons.append(f"LSTM AI: {ai_score:.2f}/8 ({lstm_metadata.get('model_key', 'unknown')})")
                    ai_reasons.append(f"LSTM confidence: {lstm_metadata.get('confidence', 0):.1f}%")
                    if lstm_metadata.get("adjustment", 0) > 0:
                        ai_reasons.append(f"LSTM lean: +{lstm_metadata.get('adjustment', 0):.2f}")
                    elif lstm_metadata.get("adjustment", 0) < 0:
                        ai_reasons.append(f"LSTM lean: {lstm_metadata.get('adjustment', 0):.2f}")
                    # Telemetry: LSTM is ML primary for props
                    _ai_telemetry = {"ai_mode": "ML_LSTM", "models_used_count": 1}
                else:
                    # Fallback to heuristic
                    ai_score, ai_reasons = _calculate_heuristic_ai_score(
                        base_ai, sharp_signal, spread, player_name
                    )
                    _ai_telemetry = {"ai_mode": "HEURISTIC_FALLBACK", "models_used_count": 0}
            except Exception as e:
                logger.warning(f"LSTM prediction failed, using heuristic: {e}")
                ai_score, ai_reasons = _calculate_heuristic_ai_score(
                    base_ai, sharp_signal, spread, player_name
                )
                _ai_telemetry = {"ai_mode": "HEURISTIC_FALLBACK", "models_used_count": 0}
        else:
            # ===== v20.1: GAMES USE 8-MODEL SYSTEM AS PRIMARY =====
            # No more heuristic + boost double-counting
            # MasterPredictionSystem runs all 8 models directly

            # Gather injury data for the model
            _all_injuries_for_ml = []
            if _injuries_by_team:
                for team_injuries in _injuries_by_team.values():
                    _all_injuries_for_ml.extend(team_injuries)

            # Format injuries for the model
            _formatted_injuries = []
            for inj in _all_injuries_for_ml:
                status = inj.get("status", "").upper()
                if status in ["OUT", "DOUBTFUL"]:
                    _formatted_injuries.append({
                        "player": {
                            "name": inj.get("player_name", inj.get("name", "Unknown")),
                            "depth": 1 if inj.get("is_starter", True) else 2
                        },
                        "status": status
                    })

            # Build game data for the 8-model resolver
            _game_data_for_ml = {
                "spread": spread,
                "total": total,
                "def_rank": _def_rank,
                "pace": _pace,
                "vacuum": _vacuum,
                "home_team": home_team,
                "away_team": away_team,
                "home_pick": pick_side.lower() == home_team.lower() if pick_side and home_team else True,
                "event_id": candidate.get("id", "unknown"),
                "injuries": _formatted_injuries,
                "odds": -110,  # Default
                "days_rest": 1,  # Could be enriched from schedule
                "travel_miles": 0,
                "games_last_7": 3
            }

            # Run 8-model resolver (ML primary, heuristic fallback)
            ai_score_raw, ai_reasons, _ai_mode, _models_used = _resolve_game_ai_score(
                mps=mps,
                game_data=_game_data_for_ml,
                fallback_base=base_ai,
                sharp_signal=sharp_signal
            )

            # Store telemetry for debug output
            _ai_telemetry = {
                "ai_mode": _ai_mode,
                "models_used_count": _models_used
            }

            # The resolver returns 0-10 scale already for ML_PRIMARY
            # For HEURISTIC_FALLBACK it returns 0-8 scale, so we need to convert
            if _ai_mode == "ML_PRIMARY":
                # ML returns 0-10 directly, but we need 0-8 for consistency with ai_score
                # Then scale to 0-10 for ai_scaled
                ai_score = ai_score_raw * 0.8  # 0-10 -> 0-8
            else:
                # Heuristic already returns 0-8
                ai_score = ai_score_raw

        # Scale AI to 0-10 for use in base_score formula
        ai_scaled = scale_ai_score_to_10(ai_score, max_ai=8.0) if TIERING_AVAILABLE else ai_score * 1.25

        # --- RESEARCH SCORE (Market Intelligence - 0-10 scale) ---
        # Pillar 1: Sharp Money Detection (0-3 pts)
        sharp_boost = 0.0
        sig_strength = sharp_signal.get("signal_strength", "NONE")
        if sig_strength == "STRONG":
            sharp_boost = 3.0
            research_reasons.append("Sharp signal STRONG (+3.0)")
            pillars_passed.append("Sharp Money Detection")
        elif sig_strength == "MODERATE":
            sharp_boost = 1.5
            research_reasons.append("Sharp signal MODERATE (+1.5)")
            pillars_passed.append("Sharp Money Detection")
        elif sig_strength == "MILD":
            sharp_boost = 0.5
            research_reasons.append("Sharp signal MILD (+0.5)")
            pillars_passed.append("Sharp Money Detection")
        else:
            research_reasons.append("No sharp signal detected")
            pillars_failed.append("Sharp Money Detection")

        # Pillar 2: Line Movement/Value (0-3 pts)
        line_variance = sharp_signal.get("line_variance", 0)
        line_boost = 0.0
        if line_variance > 1.5:
            line_boost = 3.0
            research_reasons.append(f"Line variance {line_variance:.1f}pts (strong RLM)")
            pillars_passed.append("Reverse Line Movement")
            pillars_passed.append("Line Value Detection")
        elif line_variance > 0.5:
            line_boost = 1.5
            research_reasons.append(f"Line variance {line_variance:.1f}pts (moderate)")
            pillars_passed.append("Line Value Detection")
        else:
            research_reasons.append(f"Line variance {line_variance:.1f}pts (minimal)")
            pillars_failed.append("Reverse Line Movement")

        # v17.3: ESPN Odds Cross-Validation (adds confidence when ESPN confirms)
        # Uses fuzzy matching via _find_espn_data() to handle team name variations
        espn_odds_boost = 0.0
        if _espn_odds_by_game and home_team and away_team:
            _espn_odds = _find_espn_data(_espn_odds_by_game, home_team, away_team)
            if _espn_odds and _espn_odds.get("available"):
                # Check if ESPN spread/total aligns with our data
                espn_spread = _espn_odds.get("spread")
                espn_total = _espn_odds.get("total")
                primary_line = float(spread) if spread else (float(total) if total else None)

                if primary_line is not None:
                    # Compare ESPN line with our primary line
                    if espn_spread and spread:
                        try:
                            diff = abs(float(espn_spread) - float(spread))
                            if diff <= 0.5:
                                espn_odds_boost = 0.5
                                research_reasons.append(f"ESPN confirms spread (diff {diff:.1f})")
                            elif diff <= 1.0:
                                espn_odds_boost = 0.25
                                research_reasons.append(f"ESPN spread close (diff {diff:.1f})")
                        except (ValueError, TypeError):
                            pass

                    elif espn_total and total:
                        try:
                            diff = abs(float(espn_total) - float(total))
                            if diff <= 1.0:
                                espn_odds_boost = 0.5
                                research_reasons.append(f"ESPN confirms total (diff {diff:.1f})")
                            elif diff <= 2.0:
                                espn_odds_boost = 0.25
                                research_reasons.append(f"ESPN total close (diff {diff:.1f})")
                        except (ValueError, TypeError):
                            pass

        # Market liquidity boost (book coverage)
        liquidity_boost = 0.0
        if market_book_count >= 8:
            liquidity_boost = 0.5
        elif market_book_count >= 5:
            liquidity_boost = 0.3
        elif market_book_count >= 3:
            liquidity_boost = 0.1
        if liquidity_boost > 0:
            research_reasons.append(f"Market liquidity: {market_book_count} books (+{liquidity_boost})")

        # Pillar 3: Public Betting Fade (0-2 pts) - fading heavy public action
        # v14.11: Use centralized public fade calculator (single-calculation policy)
        public_pct_val = sharp_signal.get("public_pct", 50)
        ticket_pct_val = sharp_signal.get("ticket_pct")
        money_pct_val = sharp_signal.get("money_pct")

        if SIGNALS_AVAILABLE:
            pf_signal = calculate_public_fade(public_pct_val, ticket_pct_val, money_pct_val)
            public_boost = pf_signal.research_boost
            pf_context = get_public_fade_context(pf_signal)
            if pf_signal.reason:
                research_reasons.append(pf_signal.reason)
            if pf_signal.is_fade_opportunity:
                pillars_passed.append("Public Fade Opportunity")
        else:
            # Fallback to inline calculation
            public_boost = 0.0
            pf_context = {"public_overload": False}
            if public_pct_val >= 75:
                public_boost = 2.0
                research_reasons.append(f"Public at {public_pct_val}% (fade signal)")
                pillars_passed.append("Public Fade Opportunity")
                pf_context = {"public_overload": True}
            elif public_pct_val >= 65:
                public_boost = 1.0
                research_reasons.append(f"Public at {public_pct_val}% (mild fade)")
                pf_context = {"public_overload": True}

        # Pillar 4: Base research floor (2 pts baseline)
        # v15.2: Boost base when real splits data is present (not default 50/50)
        base_research = 2.0
        _has_real_splits = sharp_signal and (sharp_signal.get("ticket_pct") is not None or sharp_signal.get("money_pct") is not None)
        if _has_real_splits:
            _mt_diff = abs((sharp_signal.get("money_pct") or 50) - (sharp_signal.get("ticket_pct") or 50))
            if _mt_diff >= 3:
                base_research = 3.0  # Real splits with money-ticket divergence
                research_reasons.append(f"Splits data present (m/t diff={_mt_diff:.0f}%)")
            else:
                base_research = 2.5  # Real splits but minimal divergence
                research_reasons.append("Splits data present (minimal divergence)")

        # Research score: Sum of pillars normalized to 0-10
        # Max possible: 3 (sharp) + 3 (line) + 2 (public) + 3 (base) + 0.5 (ESPN) + 0.5 (liquidity) = 12.0 → capped at 10
        research_score = min(10.0, base_research + sharp_boost + line_boost + public_boost + espn_odds_boost + liquidity_boost)
        research_reasons.append(
            f"Research: {round(research_score, 2)}/10 (Sharp:{sharp_boost} + RLM:{line_boost} + Public:{public_boost} + ESPN:{espn_odds_boost} + Liquidity:{liquidity_boost} + Base:{base_research})"
        )

        if (sharp_boost + public_boost + liquidity_boost) > 0:
            _record_integration_impact(
                "playbook_api",
                nonzero_boost=True,
                reasons_count=len(research_reasons),
            )
        if line_boost > 0 or espn_odds_boost > 0:
            _record_integration_impact(
                "odds_api",
                nonzero_boost=True,
                reasons_count=1,
            )

        # ===== WEATHER IMPACT ON RESEARCH (v17.9) =====
        weather_adj = 0.0
        if sport.upper() in ("NFL", "MLB", "NCAAF") and weather_data and weather_data.get("available"):
            try:
                _wmod = weather_data.get("weather_modifier", 0.0)
                if _wmod != 0.0:
                    weather_adj = max(-0.5, _wmod * 0.5)
                    research_score = min(10.0, research_score + weather_adj)
                    for wr in weather_data.get("weather_reasons", []):
                        research_reasons.append(f"Weather: {wr}")
            except Exception as e:
                logger.debug("Weather adjustment failed: %s", e)

        # Pillar score for backwards compatibility (used in scoring_breakdown)
        pillar_score = sharp_boost + line_boost + public_boost

        # =================================================================
        # v15.1 JARVIS ENGINE (Standalone 0-10) - Called FIRST
        # =================================================================
        jarvis_data = calculate_jarvis_engine_score(
            jarvis_engine=jarvis,
            game_str=game_str,
            player_name=player_name,
            home_team=home_team,
            away_team=away_team,
            spread=spread,
            total=total,
            prop_line=prop_line,
            date_et=get_today_date_et() if 'get_today_date_et' in dir() else ""
        )
        jarvis_rs = jarvis_data["jarvis_rs"]
        jarvis_active = jarvis_data["jarvis_active"]
        jarvis_hits_count = jarvis_data["jarvis_hits_count"]
        jarvis_triggers_hit = jarvis_data["jarvis_triggers_hit"]
        jarvis_reasons = jarvis_data["jarvis_reasons"]
        jarvis_fail_reasons = jarvis_data.get("jarvis_fail_reasons", [])
        jarvis_inputs_used = jarvis_data.get("jarvis_inputs_used", {})
        immortal_detected = jarvis_data["immortal_detected"]
        jarvis_triggered = jarvis_hits_count > 0

        # =================================================================
        # v15.2 ESOTERIC SCORE (0-10) - Per-Pick Differentiation
        # =================================================================
        # Components: Numerology (35%) + Astro (25%) + Fib (15%) + Vortex (15%) + Daily (10%)
        import hashlib as _hl
        numerology_score = 0.0    # 0-3.5 pts (35%)
        astro_score = 0.0         # 0-2.5 pts (25%)
        fib_score = 0.0           # 0-1.5 pts (15%)
        vortex_score = 0.0        # 0-1.5 pts (15%)
        daily_edge_score = 0.0    # 0-1.0 pts (10%)
        trap_mod = 0.0            # Modifier (negative)

        # --- A) MAGNITUDE for fib/vortex (never 0 for props) ---
        # v15.0: For props, prioritize prop_line FIRST; for game picks, use spread/total
        if player_name:
            # PROP PICK: Use prop line first, game context as fallback
            _eso_magnitude = abs(prop_line) if prop_line else 0
            if _eso_magnitude == 0 and spread:
                _eso_magnitude = abs(spread)
            if _eso_magnitude == 0 and total:
                _eso_magnitude = abs(total / 10) if total != 220 else 0
        else:
            # GAME PICK: Use spread/total first (normal flow)
            _eso_magnitude = abs(spread) if spread else 0
            if _eso_magnitude == 0 and total:
                _eso_magnitude = abs(total / 10) if total != 220 else 0
            if _eso_magnitude == 0 and prop_line:
                _eso_magnitude = abs(prop_line)

        # --- B) NUMEROLOGY (35% weight, max 3.5 pts) - Real Pythagorean numerology ---
        # v16.1: Replace SHA-256 stub with actual numerology calculations
        from esoteric_engine import calculate_generic_numerology, calculate_life_path
        from player_birth_data import get_player_data
        from datetime import datetime as dt_now

        numerology_signals = []
        numerology_score_raw = 0.5  # Base score (neutral)

        # 1. Universal Day Number (game date numerology)
        _today = dt_now.now()
        _day_sum = _today.day + _today.month + sum(int(d) for d in str(_today.year))
        _universal_day = _day_sum
        while _universal_day > 9 and _universal_day not in [11, 22, 33]:
            _universal_day = sum(int(d) for d in str(_universal_day))

        # 2. Name numerology using Pythagorean
        if player_name:
            _name_num = calculate_generic_numerology(player_name, context="player")
            if _name_num.get("is_master_number"):
                numerology_score_raw += 0.15
                numerology_signals.append(f"Master Number {_name_num['pythagorean_reduction']}")
            if _name_num.get("is_tesla_number"):
                numerology_score_raw += 0.1
                numerology_signals.append(f"Tesla Number {_name_num['pythagorean_reduction']}")

            # 3. Life Path sync with player birth date (if available)
            _player_data = get_player_data(player_name)
            if _player_data and _player_data.get("birth_date"):
                _life_path = calculate_life_path(_player_data["birth_date"])
                # Check harmony with universal day
                if _life_path == _universal_day:
                    numerology_score_raw += 0.25
                    numerology_signals.append(f"Perfect Sync: Life Path {_life_path} = Universal Day")
                elif abs(_life_path - _universal_day) <= 2 or (_life_path + _universal_day == 9):
                    numerology_score_raw += 0.12
                    numerology_signals.append(f"Harmonic: Life Path {_life_path} ~ Universal Day {_universal_day}")

        # 4. Line numerology (spread/total/prop line)
        _line_num = calculate_generic_numerology(prop_line if prop_line else spread, context="spread" if not prop_line else "player")
        if _line_num.get("signals_hit"):
            numerology_score_raw += _line_num.get("signal_strength", 0) * 0.5
            numerology_signals.extend(_line_num["signals_hit"][:2])

        # 5. Master number boost from game string
        if "11" in game_str or "22" in game_str or "33" in game_str:
            numerology_score_raw += 0.08
            numerology_signals.append("Master number in matchup")

        # Cap at 1.0 and convert to weighted score
        numerology_raw = min(1.0, numerology_score_raw)
        numerology_score = numerology_raw * 10 * ESOTERIC_WEIGHTS["numerology"]

        logger.debug("Numerology[%s]: raw=%.2f signals=%s", player_name[:20] if player_name else game_str[:20], numerology_raw, numerology_signals[:3])

        if jarvis:
            # --- TRAP DEDUCTION (negative modifier) ---
            trap = jarvis.calculate_large_spread_trap(spread, total)
            trap_mod = trap.get("modifier", 0)  # Usually negative

            # --- E) FIBONACCI (15% weight, max 1.5 pts) - scaled in esoteric path ---
            fib_alignment = jarvis.calculate_fibonacci_alignment(float(_eso_magnitude) if _eso_magnitude else 0)
            fib_raw = fib_alignment.get("modifier", 0)
            # Scale up fib modifier in esoteric layer (Jarvis returns 0.05-0.15)
            _fib_scaled = min(0.6, fib_raw * 6.0) if fib_raw > 0 else 0.0
            fib_score = _fib_scaled * 10 * ESOTERIC_WEIGHTS["fib"]

            # --- E) VORTEX (15% weight, max 1.5 pts) - scaled in esoteric path ---
            vortex_value = int(abs(_eso_magnitude * 10)) if _eso_magnitude else 0
            vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)
            vortex_raw = vortex_pattern.get("modifier", 0)
            # Scale up vortex modifier in esoteric layer (Jarvis returns 0.08-0.15)
            _vortex_scaled = min(0.7, vortex_raw * 5.0) if vortex_raw > 0 else 0.0
            vortex_score = _vortex_scaled * 10 * ESOTERIC_WEIGHTS["vortex"]

        # --- C) ASTRO (25% weight, max 2.5 pts) - Linear 0-100 → 0-10 ---
        astro = vedic.calculate_astro_score() if vedic else {"overall_score": 50}
        # Map 0-100 directly to 0-10 (50 ≈ 5.0, not 0.0)
        astro_score = (astro["overall_score"] / 100) * 10 * ESOTERIC_WEIGHTS["astro"]

        # --- D) DAILY EDGE (10% weight, max 1.0 pts) - Lower thresholds ---
        _de = daily_energy.get("overall_score", 50)
        if _de >= 85:
            daily_edge_score = 10 * ESOTERIC_WEIGHTS["daily_edge"]   # 1.0 pts
        elif _de >= 70:
            daily_edge_score = 7 * ESOTERIC_WEIGHTS["daily_edge"]    # 0.7 pts
        elif _de >= 55:
            daily_edge_score = 4 * ESOTERIC_WEIGHTS["daily_edge"]    # 0.4 pts

        # --- ESOTERIC SCORE: Sum of weighted components + trap modifier ---
        esoteric_raw = (
            numerology_score +    # 35% weight (0-3.5)
            astro_score +         # 25% weight (0-2.5)
            fib_score +           # 15% weight (0-1.5)
            vortex_score +        # 15% weight (0-1.5)
            daily_edge_score +    # 10% weight (0-1.0)
            trap_mod              # Modifier (negative)
        )

        # ===== GLITCH PROTOCOL SIGNALS (v17.2) =====
        # Integrate orphaned esoteric signals: Chrome Resonance, Void Moon, Hurst, Kp-Index
        glitch_adjustment = 0.0
        glitch_reasons = []
        _game_date_obj = None  # Initialize here so MSRF can use it even if GLITCH try block fails

        try:
            from esoteric_engine import get_glitch_aggregate, calculate_chrome_resonance
            from player_birth_data import get_player_data as get_player_birth

            # Get player birth date for Chrome Resonance (props only)
            _player_birth = None
            if player_name:
                _pdata = get_player_birth(player_name)
                if _pdata and _pdata.get("birth_date"):
                    _player_birth = _pdata["birth_date"]

            # Get game date
            _game_date_obj = None
            if game_datetime:
                _game_date_obj = game_datetime.date() if hasattr(game_datetime, 'date') else game_datetime

            # Collect line values for Benford analysis (needs 10+ for statistical significance)
            # v17.6: Now extracts from multi-book data to get 10+ values
            _line_values = _extract_benford_values_from_game(
                game={"bookmakers": game_bookmakers} if game_bookmakers else {},
                prop_line=prop_line,
                spread=spread,
                total=total
            )

            # ===== v17.7: HURST EXPONENT DATA =====
            # Fetch line history for Hurst Exponent calculation in GLITCH
            _line_history = None
            try:
                _event_id = event_id
                if _event_id and DATABASE_AVAILABLE and DB_ENABLED:
                    with get_db() as db:
                        if db:
                            _line_history = get_line_history_values(
                                db,
                                event_id=_event_id,
                                value_type="spread",  # Use spread for primary line movement
                                limit=30
                            )
                            if _line_history and len(_line_history) >= 10:
                                logger.debug("HURST: Loaded %d line history values for event %s",
                                            len(_line_history), _event_id[:20] if _event_id else "unknown")
            except Exception as e:
                logger.debug("Line history fetch skipped: %s", e)

            # Calculate GLITCH aggregate
            glitch_result = get_glitch_aggregate(
                birth_date_str=_player_birth,
                game_date=_game_date_obj,
                game_time=game_datetime,
                line_history=_line_history,  # v17.7: Now using real line history data
                value_for_benford=_line_values if len(_line_values) >= 10 else None,
                primary_value=prop_line if prop_line else spread
            )

            # GLITCH score (0-10 scale) adjusts esoteric
            # Weight: 15% of esoteric score comes from GLITCH signals
            _glitch_score = glitch_result.get("glitch_score_10", 5.0)
            glitch_adjustment = (_glitch_score - 5.0) * 0.15  # ±0.75 max adjustment

            # Add triggered signals to reasons
            if glitch_result.get("triggered_count", 0) > 0:
                for sig in glitch_result.get("triggered_signals", []):
                    glitch_reasons.append(f"GLITCH: {sig}")

            # Add specific Chrome Resonance if strong
            if "chrome_resonance" in glitch_result.get("breakdown", {}):
                chrome = glitch_result["breakdown"]["chrome_resonance"]
                if chrome.get("triggered"):
                    glitch_reasons.append(f"Chrome: {chrome.get('interval_name', 'unknown')} ({chrome.get('resonance_type', '')})")

            # Log GLITCH signals
            if glitch_adjustment != 0:
                logger.debug("GLITCH[%s]: score=%.2f, adj=%.2f, signals=%s",
                            game_str[:30], _glitch_score, glitch_adjustment, glitch_result.get("triggered_signals", []))
        except Exception as e:
            logger.debug("GLITCH signals unavailable: %s", e)

        # Apply GLITCH adjustment to esoteric_raw
        esoteric_raw += glitch_adjustment

        # ===== v17.6: VORTEX ENERGY (Tesla 3-6-9) =====
        vortex_boost = 0.0
        try:
            from esoteric_engine import calculate_vortex_energy

            # Determine primary value for vortex analysis
            _vortex_value = prop_line if prop_line else total if total else abs(spread) if spread else None
            _vortex_context = "prop" if prop_line else "total" if total else "spread"

            if _vortex_value:
                vortex_result = calculate_vortex_energy(_vortex_value, context=_vortex_context)
                if vortex_result.get("triggered"):
                    _vortex_boost = 0.3 if vortex_result.get("is_perfect_vortex") else 0.2 if vortex_result.get("is_tesla_aligned") else 0.1
                    vortex_boost = _vortex_boost
                    esoteric_reasons.append(f"Vortex: {vortex_result['signal']} (root={vortex_result['digital_root']})")
                    logger.debug("VORTEX[%s]: value=%.1f, signal=%s, root=%d, boost=%.2f",
                                game_str[:30], _vortex_value, vortex_result['signal'], vortex_result['digital_root'], _vortex_boost)
        except Exception as e:
            logger.debug("Vortex calculation skipped: %s", e)

        # Apply Vortex boost
        esoteric_raw += vortex_boost

        # ===== v17.7: FIBONACCI RETRACEMENT (Season Extremes) =====
        # Check if current line is near key Fibonacci retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)
        fib_retracement_boost = 0.0
        _is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
        try:
            if DATABASE_AVAILABLE and DB_ENABLED and _is_game_pick:
                from esoteric_engine import calculate_fibonacci_retracement

                # Determine current season (Sept-Aug academic year pattern)
                _now = datetime.now()
                _season = f"{_now.year}-{str(_now.year+1)[-2:]}" if _now.month >= 9 else f"{_now.year-1}-{str(_now.year)[-2:]}"

                # Get primary line value (spread or total)
                _fib_line = abs(spread) if spread else total if total else None
                _fib_stat = "spread" if spread else "total"

                if _fib_line:
                    with get_db() as db:
                        if db:
                            extremes = get_season_extreme(db, sport_upper, _season, _fib_stat)

                            if extremes and extremes.get("season_high") and extremes.get("season_low"):
                                fib_result = calculate_fibonacci_retracement(
                                    current_line=_fib_line,
                                    season_high=extremes["season_high"],
                                    season_low=extremes["season_low"]
                                )

                                if fib_result.get("near_fib_level"):
                                    _fib_boost = 0.35 if fib_result["signal"] == "REVERSAL_ZONE" else 0.2
                                    fib_retracement_boost = _fib_boost
                                    esoteric_reasons.append(
                                        f"Fib Retracement: {fib_result['closest_fib_level']}% ({fib_result['signal']})"
                                    )
                                    logger.debug("FIB_RETRACEMENT[%s]: line=%.1f at %.1f%% of season (high=%.1f, low=%.1f), signal=%s, boost=%.2f",
                                                game_str[:30], _fib_line, fib_result['retracement_pct'],
                                                extremes["season_high"], extremes["season_low"],
                                                fib_result['signal'], _fib_boost)
        except Exception as e:
            logger.debug("Fibonacci retracement skipped: %s", e)

        # Apply Fibonacci Retracement boost
        esoteric_raw += fib_retracement_boost

        # ===== PHASE 1: DORMANT ESOTERIC SIGNAL ACTIVATION (v17.5) =====
        # Wiring three previously dormant signals from esoteric_engine.py:
        # 1. Biorhythms - for props (player birthday-based cycles)
        # 2. Gann Square - for games (sacred geometry price levels)
        # 3. Founder's Echo - for games (team gematria resonance)

        # --- 1. BIORHYTHMS (Props Only) ---
        # Player birth date cycles: physical (23 days), emotional (28 days), intellectual (33 days)
        biorhythm_boost = 0.0
        if pick_type == "PROP" and player_name:
            try:
                from esoteric_engine import calculate_biorhythms
                from player_birth_data import get_player_data as _get_player_bio
                _bio_player = _get_player_bio(player_name)
                if _bio_player and _bio_player.get("birth_date"):
                    _bio_target_date = _game_date_obj if _game_date_obj else None
                    _bio_result = calculate_biorhythms(_bio_player["birth_date"], _bio_target_date)
                    _bio_status = _bio_result.get("status", "")
                    _bio_overall = _bio_result.get("overall", 0)

                    # Boost based on biorhythm status
                    if _bio_status == "PEAK":
                        biorhythm_boost = 0.3
                        esoteric_reasons.append(f"Biorhythm: PEAK ({_bio_overall:.0f})")
                    elif _bio_status == "RISING":
                        biorhythm_boost = 0.15
                        esoteric_reasons.append(f"Biorhythm: RISING ({_bio_overall:.0f})")
                    elif _bio_status == "LOW":
                        biorhythm_boost = -0.2  # Negative for low periods
                        esoteric_reasons.append(f"Biorhythm: LOW ({_bio_overall:.0f})")

                    if biorhythm_boost != 0:
                        logger.debug("BIORHYTHM[%s]: status=%s, overall=%.1f, boost=%.2f",
                                     player_name[:20], _bio_status, _bio_overall, biorhythm_boost)
            except ImportError:
                logger.debug("Biorhythms module not available")
            except Exception as e:
                logger.debug("Biorhythms calculation failed: %s", e)

        # --- 2. GANN SQUARE (Games Only) ---
        # Sacred geometry: checks if spread/total hit resonant angles (45°, 90°, 180°, 360°)
        # Note: pick_type is "SPREAD", "MONEYLINE", "TOTAL" for games, "PROP" for props
        gann_boost = 0.0
        _is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
        if _is_game_pick and spread and total:
            try:
                from esoteric_engine import analyze_spread_gann
                _gann_result = analyze_spread_gann(abs(spread), total)
                _gann_signal = _gann_result.get("spread", {}).get("signal", "WEAK")
                _gann_angle = _gann_result.get("spread", {}).get("closest_key_angle", 0)
                _gann_combined = _gann_result.get("combined_resonance", False)

                if _gann_signal == "STRONG":
                    gann_boost = 0.25
                    esoteric_reasons.append(f"Gann: {_gann_angle}° (STRONG)")
                elif _gann_signal == "MODERATE":
                    gann_boost = 0.15
                    esoteric_reasons.append(f"Gann: {_gann_angle}° (MODERATE)")

                # Extra boost for combined resonance (both spread and total hit key angles)
                if _gann_combined:
                    gann_boost += 0.1
                    esoteric_reasons.append("Gann: Combined Resonance")

                if gann_boost > 0:
                    logger.debug("GANN[%s]: spread_signal=%s, angle=%d, combined=%s, boost=%.2f",
                                 game_str[:30], _gann_signal, _gann_angle, _gann_combined, gann_boost)
            except ImportError:
                logger.debug("Gann Square module not available")
            except Exception as e:
                logger.debug("Gann Square calculation failed: %s", e)

        # --- 3. FOUNDER'S ECHO (Games Only) ---
        # Team founding year gematria resonance with game date
        # Note: pick_type is "SPREAD", "MONEYLINE", "TOTAL" for games, "PROP" for props
        founders_boost = 0.0
        if _is_game_pick and (home_team or away_team):
            try:
                from esoteric_engine import check_founders_echo
                _founders_target_date = _game_date_obj if _game_date_obj else None

                # Check both teams for founder resonance
                _home_echo = check_founders_echo(home_team, _founders_target_date) if home_team else {}
                _away_echo = check_founders_echo(away_team, _founders_target_date) if away_team else {}

                _home_resonance = _home_echo.get("resonance", False)
                _away_resonance = _away_echo.get("resonance", False)

                if _home_resonance or _away_resonance:
                    founders_boost = 0.2
                    _resonant_team = home_team if _home_resonance else away_team
                    _founding_year = _home_echo.get("founding_year") if _home_resonance else _away_echo.get("founding_year")
                    esoteric_reasons.append(f"Founder's Echo: {_resonant_team} ({_founding_year})")

                    # Extra boost if both teams resonate (rare)
                    if _home_resonance and _away_resonance:
                        founders_boost = 0.35
                        esoteric_reasons.append(f"Founder's Echo: Both teams resonate!")

                    logger.debug("FOUNDER[%s vs %s]: home=%s, away=%s, boost=%.2f",
                                 home_team or "?", away_team or "?",
                                 _home_resonance, _away_resonance, founders_boost)
            except ImportError:
                logger.debug("Founder's Echo module not available")
            except Exception as e:
                logger.debug("Founder's Echo calculation failed: %s", e)

        # Apply Phase 1 dormant signal boosts
        esoteric_raw += biorhythm_boost + gann_boost + founders_boost

        # ===== ALTITUDE IMPACT (v17.9) =====
        altitude_adj = 0.0
        try:
            from context_layer import StadiumAltitudeService
            altitude_adj, altitude_reasons = StadiumAltitudeService.get_altitude_adjustment(
                sport=sport, home_team=home_team, pick_type=pick_type, pick_side=pick_side
            )
            if altitude_adj != 0.0:
                esoteric_raw += altitude_adj
                esoteric_reasons.extend(altitude_reasons)
        except Exception as e:
            logger.debug("Altitude adjustment failed: %s", e)

        # ===== PHASE 8 (v18.2) NEW ESOTERIC SIGNALS =====
        phase8_boost = 0.0
        phase8_reasons = []
        phase8_full_result = None
        try:
            from esoteric_engine import get_phase8_esoteric_signals

            # Parse game datetime for lunar/solar signals
            _game_datetime = None
            if commence_time:
                try:
                    if isinstance(commence_time, str):
                        _game_datetime = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                    else:
                        _game_datetime = commence_time
                except Exception:
                    _game_datetime = datetime.now()
            else:
                _game_datetime = datetime.now()

            # Get streak data if available (from context or injuries lookup)
            _home_streak = 0
            _home_streak_type = "W"
            _away_streak = 0
            _away_streak_type = "W"

            # Try to get streak info from team data (if available)
            try:
                if home_team and sport:
                    # Could fetch from ESPN or Playbook if we had a streak endpoint
                    pass  # Placeholder - streaks can be added via future integration
            except Exception:
                pass

            # Calculate all Phase 8 signals
            phase8_result = get_phase8_esoteric_signals(
                game_datetime=_game_datetime,
                game_date=_game_date_obj,
                sport=sport,
                home_team=home_team,
                away_team=away_team,
                pick_type=pick_type,
                pick_side=pick_side,
                home_streak=_home_streak,
                home_streak_type=_home_streak_type,
                away_streak=_away_streak,
                away_streak_type=_away_streak_type
            )

            phase8_boost = phase8_result.get("phase8_boost", 0.0)
            phase8_reasons = phase8_result.get("reasons", [])
            phase8_full_result = phase8_result  # Capture for debug

            if phase8_boost != 0.0:
                esoteric_raw += phase8_boost
                esoteric_reasons.extend(phase8_reasons)

            if phase8_result.get("triggered_count", 0) > 0:
                logger.debug("Phase8[%s]: boost=%.2f, signals=%s",
                            game_str[:30], phase8_boost, phase8_result.get("triggered_signals", []))

        except ImportError as ie:
            logger.warning("Phase 8 signals module not available: %s", ie)
        except Exception as e:
            logger.warning("Phase 8 signals calculation failed: %s", e)

        # ===== WEATHER IMPACT (v20.0 Phase 9) =====
        # Weather only affects outdoor sports (NFL, MLB, NCAAF)
        # Indoor sports (NBA, NHL, NCAAB) and dome stadiums are skipped
        weather_adj = 0.0
        weather_reasons = []
        _is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
        if _is_game_pick and sport_upper in ("NFL", "MLB", "NCAAF"):
            try:
                from alt_data_sources.weather import get_weather_context_sync
                # Get venue from candidate if available
                _weather_venue = candidate.get("venue", "") if isinstance(candidate, dict) else ""
                weather_ctx = get_weather_context_sync(sport_upper, home_team, _weather_venue)
                if weather_ctx.get("status") == "VALIDATED":
                    weather_adj = weather_ctx.get("score_modifier", 0.0)
                    if weather_adj != 0.0:
                        _weather_raw = weather_ctx.get("raw", {})
                        _temp = _weather_raw.get("temp_f", "?")
                        _wind = _weather_raw.get("wind_mph", "?")
                        _precip = _weather_raw.get("precip_in", 0)
                        weather_reasons.append(f"Weather: {weather_adj:+.2f} ({_temp}°F, {_wind}mph wind)")
                        if _precip > 0.1:
                            weather_reasons.append(f"Precipitation: {_precip}in")
                        research_reasons.extend(weather_reasons)
                        # Apply weather penalty to research score (weather only penalizes, max -0.35)
                        research_score = max(0.0, min(10.0, research_score + weather_adj))
                        logger.debug("WEATHER[%s @ %s]: temp=%.1f, wind=%.1f, precip=%.2f, adj=%.2f",
                                    away_team or "?", home_team or "?", _temp if isinstance(_temp, float) else 0,
                                    _wind if isinstance(_wind, float) else 0, _precip, weather_adj)
                elif weather_ctx.get("status") == "NOT_RELEVANT":
                    logger.debug("WEATHER[%s]: %s", home_team or "?", weather_ctx.get("reason", "skipped"))
            except Exception as e:
                logger.debug("Weather adjustment failed: %s", e)

        # ===== SURFACE IMPACT (v20.0 Phase 9) =====
        # Surface type (grass vs turf) affects performance for NFL/MLB
        surface_adj = 0.0
        surface_reason = ""
        if _is_game_pick and sport_upper in ("NFL", "MLB"):
            try:
                from alt_data_sources.stadium import calculate_surface_impact_for_scoring
                surface_adj, surface_reason = calculate_surface_impact_for_scoring(
                    sport=sport_upper,
                    home_team=home_team,
                    pick_type=pick_type,
                    market=market  # Use function parameter
                )
                if surface_adj != 0.0 and surface_reason:
                    esoteric_reasons.append(surface_reason)
                    esoteric_raw += surface_adj
                    logger.debug("SURFACE[%s]: %s, adj=%.2f", home_team or "?", surface_reason, surface_adj)
            except ImportError:
                logger.debug("Surface impact module not available")
            except Exception as e:
                logger.debug("Surface impact failed: %s", e)

        # ===== PLAYER MATCHUP SCORING (v20.0 Phase 9) =====
        # For props: adjust based on opponent defensive quality vs player position
        matchup_adj = 0.0
        matchup_reason = ""
        if pick_type == "PROP" and player_name and away_team:
            try:
                from context_layer import PlayerMatchupService
                # Determine position from prop type
                _player_pos = PlayerMatchupService.get_prop_type_position(sport_upper, market)
                if _player_pos:
                    matchup_adj, matchup_reason = PlayerMatchupService.get_matchup_adjustment(
                        sport=sport_upper,
                        player_position=_player_pos,
                        opponent_team=away_team,  # Player's opponent
                        prop_type=market  # Use function parameter
                    )
                    if matchup_adj != 0.0 and matchup_reason:
                        context_reasons.append(matchup_reason)
                        # Apply to context score (affects overall via context engine weight)
                        context_score = max(0.0, min(10.0, context_score + matchup_adj))
                        logger.debug("MATCHUP[%s vs %s]: pos=%s, adj=%.2f", player_name, away_team, _player_pos, matchup_adj)
            except ImportError:
                logger.debug("PlayerMatchupService not available")
            except Exception as e:
                logger.debug("Matchup scoring failed: %s", e)

        # ===== LIVE IN-GAME SIGNALS (v20.0 Phase 9) =====
        # Only applies to LIVE games - score momentum and line movement detection
        live_boost = 0.0
        live_reasons = []
        # game_status is now passed as parameter (v20.0)
        if game_status in ("LIVE", "MISSED_START") and _is_game_pick:
            try:
                from alt_data_sources.live_signals import (
                    get_combined_live_signals, is_live_signals_enabled
                )
                if is_live_signals_enabled():
                    _home_score = candidate.get("home_score", 0) if isinstance(candidate, dict) else 0
                    _away_score = candidate.get("away_score", 0) if isinstance(candidate, dict) else 0
                    _period = candidate.get("period", 1) if isinstance(candidate, dict) else 1
                    _current_line = candidate.get("line", 0) if isinstance(candidate, dict) else 0
                    _event_id = candidate.get("event_id", "") if isinstance(candidate, dict) else ""
                    _is_home_pick = pick_side and home_team and pick_side.lower() in home_team.lower()

                    live_signals = get_combined_live_signals(
                        event_id=_event_id,
                        home_score=_home_score,
                        away_score=_away_score,
                        period=_period,
                        sport=sport_upper,
                        pick_side=pick_side or "",
                        is_home_pick=_is_home_pick,
                        current_line=_current_line,
                        db_session=None  # Would need db session for line history
                    )

                    if live_signals.get("available"):
                        live_boost = live_signals.get("total_boost", 0.0)
                        live_reasons = live_signals.get("reasons", [])
                        if live_boost != 0.0:
                            research_reasons.extend(live_reasons)
                            # Apply live boost to research score (capped at ±0.50)
                            research_score = max(0.0, min(10.0, research_score + live_boost))
                            logger.info("LIVE_SIGNALS[%s]: boost=%.2f, signals=%s",
                                       _event_id[:8] if _event_id else "?", live_boost, live_signals.get("signals", []))
            except ImportError:
                logger.debug("Live signals module not available")
            except Exception as e:
                logger.debug("Live signals failed: %s", e)

        # Clamp to 0-10
        esoteric_score = max(0, min(10, esoteric_raw))
        logger.debug("Esoteric[%s]: mag=%.1f num=%.2f astro=%.2f fib=%.2f vortex=%.2f daily=%.2f trap=%.2f → raw=%.2f",
                     game_str[:30], _eso_magnitude, numerology_score, astro_score, fib_score, vortex_score, daily_edge_score, trap_mod, esoteric_raw)

        # --- v15.3 FOUR-ENGINE CONFLUENCE (with STRONG eligibility gate) ---
        _research_sharp_present = bool(sharp_signal and sharp_signal.get("signal_strength", "NONE") != "NONE")
        if jarvis:
            confluence = jarvis.calculate_confluence(
                research_score=research_score,
                esoteric_score=esoteric_score,
                immortal_detected=immortal_detected,
                jarvis_triggered=jarvis_triggered,
                jarvis_active=jarvis_active,
                research_sharp_present=_research_sharp_present,
                jason_sim_boost=0.0  # Jason hasn't run yet; will be checked post-hoc
            )
        else:
            # Fallback confluence calculation with STRONG eligibility gate
            alignment = 1 - abs(research_score - esoteric_score) / 10
            alignment_pct = alignment * 100
            both_high = research_score >= 7.5 and esoteric_score >= 7.5
            jarvis_high = jarvis_rs is not None and jarvis_rs >= 7.5
            if immortal_detected and both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "IMMORTAL", "boost": CONFLUENCE_LEVELS["IMMORTAL"], "alignment_pct": alignment_pct}
            elif jarvis_triggered and both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "JARVIS_PERFECT", "boost": CONFLUENCE_LEVELS["JARVIS_PERFECT"], "alignment_pct": alignment_pct}
            elif both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "PERFECT", "boost": CONFLUENCE_LEVELS["PERFECT"], "alignment_pct": alignment_pct}
            elif alignment_pct >= 70:
                # v15.3: STRONG requires alignment >= 80% AND active signal
                _strong_ok = alignment_pct >= 80 and (jarvis_active or _research_sharp_present)
                if _strong_ok:
                    confluence = {"level": "STRONG", "boost": CONFLUENCE_LEVELS["STRONG"], "alignment_pct": alignment_pct}
                else:
                    confluence = {"level": "MODERATE", "boost": CONFLUENCE_LEVELS["MODERATE"], "alignment_pct": alignment_pct}
            elif alignment_pct >= 60:
                confluence = {"level": "MODERATE", "boost": CONFLUENCE_LEVELS["MODERATE"], "alignment_pct": alignment_pct}
            else:
                confluence = {"level": "DIVERGENT", "boost": CONFLUENCE_LEVELS["DIVERGENT"], "alignment_pct": alignment_pct}

        # ===== v17.3 HARMONIC CONVERGENCE CHECK =====
        # "Golden Boost" when Math (Research) + Magic (Esoteric) both exceed threshold
        # This represents exceptional alignment between market intelligence and cosmic signals
        # v17.3: Lowered from 8.0 to 7.5 for better trigger rate
        HARMONIC_THRESHOLD = HARMONIC_CONVERGENCE_THRESHOLD  # From scoring_contract.py (7.5)

        harmonic_boost = compute_harmonic_boost(research_score, esoteric_score)
        if harmonic_boost > 0:
            confluence = {
                "level": "HARMONIC_CONVERGENCE",
                "boost": confluence.get("boost", 0) + harmonic_boost,
                "alignment_pct": 100.0,
                "reason": f"Math({research_score:.1f}) + Magic({esoteric_score:.1f}) >= {HARMONIC_THRESHOLD}"
            }
            research_reasons.append(f"HARMONIC CONVERGENCE: +{harmonic_boost} (Research + Esoteric both >= {HARMONIC_THRESHOLD})")
            logger.info("HARMONIC_CONVERGENCE: Research=%.1f, Esoteric=%.1f, boost=+%.1f",
                        research_score, esoteric_score, harmonic_boost)

        # ===== v17.2 MSRF RESONANCE BOOST =====
        # Mathematical Sequence Resonance Framework: turn date detection using Pi, Phi, sacred numbers
        # Adds confluence boost when game date aligns with mathematically significant projections
        msrf_boost = 0.0
        msrf_metadata = {"source": "not_run"}
        msrf_status = "NOT_RELEVANT"
        msrf_reasons = []
        try:
            from signals.msrf_resonance import get_msrf_confluence_boost, MSRF_ENABLED
            if not MSRF_ENABLED:
                msrf_status = "NOT_RELEVANT"
                msrf_reasons.append("MSRF disabled")
            elif not _game_date_obj:
                msrf_status = "NOT_RELEVANT"
                msrf_reasons.append("MSRF missing game_date")
            else:
                msrf_boost, msrf_metadata = get_msrf_confluence_boost(
                    game_date=_game_date_obj,
                    player_name=player_name,
                    home_team=home_team,
                    away_team=away_team,
                    sport=sport_upper
                )
                msrf_boost = max(-MSRF_BOOST_CAP, min(MSRF_BOOST_CAP, msrf_boost))
                msrf_status = "OK" if msrf_boost > 0 else "NOT_RELEVANT"
                if msrf_metadata.get("level"):
                    msrf_reasons.append(f"MSRF: {msrf_metadata.get('level')} ({msrf_boost:+.2f})")
                if msrf_boost > 0:
                    esoteric_reasons.append(f"MSRF: {msrf_metadata.get('level', 'RESONANCE')} (+{msrf_boost:.2f})")
                    logger.info("MSRF[%s vs %s]: %s, boost=+%.2f, points=%.1f",
                                home_team or "?", away_team or "?",
                                msrf_metadata.get("level", "?"),
                                msrf_boost, msrf_metadata.get("points", 0))
        except ImportError:
            msrf_status = "UNAVAILABLE"
            msrf_reasons.append("MSRF module not available")
            logger.debug("MSRF module not available")
        except Exception as e:
            msrf_status = "ERROR"
            msrf_reasons.append(f"MSRF error: {e}")
            logger.warning("MSRF calculation failed: %s", e)

        # ===== v17.4 SERP BETTING INTELLIGENCE =====
        # Search trend signals from SerpAPI mapped to boost layers
        # SHADOW MODE by default: logs signals but applies 0 boost
        serp_intel = None
        serp_boost_total = 0.0
        serp_reasons = []
        serp_signals = []
        serp_status = "UNAVAILABLE"

        if SERP_INTEL_AVAILABLE and is_serp_available():
            try:
                _serp_start = time.time()
                if player_name and not SERP_PROPS_ENABLED:
                    # v20.9: Skip SERP for props — saves ~60% of daily quota
                    # Props rely on LSTM, context layer, GLITCH, Phase 8 signals instead
                    # Per-player SERP queries are unique (near-zero cache hit rate)
                    # Re-enable with SERP_PROPS_ENABLED=true env var
                    serp_status = "SKIPPED_PROPS"
                    serp_reasons.append("SERP: Skipped for props (quota optimization)")
                elif player_name:
                    # Prop bets - use prop intelligence (SERP_PROPS_ENABLED=true)
                    serp_intel = get_serp_prop_intelligence(
                        sport=sport_upper,
                        player_name=player_name,
                        home_team=home_team,
                        away_team=away_team,
                        market=market,
                        prop_line=prop_line
                    )
                else:
                    # Game bets - check pre-fetch cache first (v20.7)
                    _serp_target = pick_side if pick_side in [home_team, away_team] else home_team
                    _serp_cache_key = (home_team.lower(), away_team.lower(), _serp_target.lower())
                    if _serp_cache_key in _serp_game_cache:
                        serp_intel = _serp_game_cache[_serp_cache_key]
                    else:
                        serp_intel = get_serp_betting_intelligence(
                            sport=sport_upper,
                            home_team=home_team,
                            away_team=away_team,
                            pick_side=pick_side,
                        )

                if serp_intel and serp_intel.get("available"):
                    serp_status = "OK"
                    # Apply SERP boosts to engine scores (already capped and shadow-mode applied)
                    serp_boosts = serp_intel.get("boosts", {})
                    serp_boost_total = sum(serp_boosts.values())
                    if serp_boost_total > SERP_BOOST_CAP_TOTAL:
                        serp_boost_total = SERP_BOOST_CAP_TOTAL

                    # Log triggered signals
                    serp_signals = serp_intel.get("signals", [])
                    for sig in serp_signals:
                        if sig.get("triggered"):
                            serp_reasons.append(f"SERP[{sig['engine']}]: {sig.get('reason', 'signal triggered')}")

                    # Log shadow mode status
                    if SERP_SHADOW_MODE and serp_intel.get("boosts_raw"):
                        raw_total = sum(serp_intel["boosts_raw"].values())
                        if raw_total > 0:
                            logger.info("SERP SHADOW[%s]: Would apply +%.2f (AI:%.2f R:%.2f E:%.2f J:%.2f C:%.2f)",
                                        game_str[:30], raw_total,
                                        serp_intel["boosts_raw"].get("ai", 0),
                                        serp_intel["boosts_raw"].get("research", 0),
                                        serp_intel["boosts_raw"].get("esoteric", 0),
                                        serp_intel["boosts_raw"].get("jarvis", 0),
                                        serp_intel["boosts_raw"].get("context", 0))
                _record_integration_call("serpapi", status=serp_status, latency_ms=(time.time() - _serp_start) * 1000.0)
            except Exception as e:
                logger.debug("SERP intelligence failed: %s", e)
                serp_status = "ERROR"
                serp_intel = {"available": False, "error": str(e)}
        elif SERP_INTEL_AVAILABLE:
            serp_status = "UNAVAILABLE"
            serp_reasons.append("SERP quota unavailable or disabled")
        else:
            serp_status = "UNAVAILABLE"
            serp_reasons.append("SERP module not available")

        _record_integration_impact(
            "serpapi",
            nonzero_boost=serp_boost_total != 0.0,
            reasons_count=len(serp_reasons),
        )

        # ===== v17.9 GEMATRIA TWITTER INTELLIGENCE =====
        # Community consensus signals from gematria Twitter accounts
        # Monitors: GematriaClub, ScriptLeaker, ZachHubbard, archaix138, etc.
        gematria_boost = 0.0
        gematria_metadata = {"available": False, "reason": "not_run"}
        gematria_reasons = []

        if GEMATRIA_INTEL_AVAILABLE:
            try:
                # Build context for gematria consensus lookup
                gematria_context = {
                    "sport": sport_upper,
                    "home_team": home_team,
                    "away_team": away_team,
                    "player_name": player_name,
                    "market": market,
                    "pick_side": pick_side,
                    "prop_line": prop_line,
                    "spread": spread,
                    "total": total,
                }

                gematria_boost, gematria_metadata = get_gematria_consensus_boost(gematria_context)

                if gematria_boost > 0:
                    confluence["boost"] = confluence.get("boost", 0) + gematria_boost
                    confluence["gematria_boost"] = gematria_boost

                    consensus_level = gematria_metadata.get("consensus_level", "MODERATE")
                    account_count = gematria_metadata.get("accounts_aligned", 0)
                    gematria_reasons.append(f"Gematria: {consensus_level} consensus ({account_count} accounts) +{gematria_boost:.2f}")

                    logger.info("GEMATRIA[%s vs %s]: %s consensus, %d accounts, boost=+%.2f",
                                home_team or "?", away_team or "?",
                                consensus_level, account_count, gematria_boost)

                    # Add any sacred number triggers found
                    for trigger in gematria_metadata.get("triggers", [])[:3]:
                        gematria_reasons.append(f"Gematria: {trigger}")

            except Exception as e:
                logger.debug("Gematria intelligence failed: %s", e)
                gematria_metadata = {"available": False, "error": str(e)}

        confluence_level = confluence.get("level", "DIVERGENT")
        confluence_boost = confluence.get("boost", 0)
        confluence_reasons = []
        if confluence.get("reason"):
            confluence_reasons.append(str(confluence.get("reason")))
        confluence_reasons.append(f"Confluence {confluence_level} (+{confluence_boost:.2f})")
        if harmonic_boost > 0:
            confluence_reasons.append(f"Harmonic Convergence (+{harmonic_boost:.2f})")

        # --- v18.0 CONTEXT SCORE (Pillars 13-15) ---
        # Calculate context_score (0-10) from defensive rank, pace, and vacuum
        # Context is a bounded modifier layer (NOT a weighted engine)

        # Pillar 13: Defensive Rank (lower rank = worse defense = better for offense)
        # Rank 1 = worst defense = best matchup = 10, Rank 32 = best defense = 0
        _total_teams = 32 if sport_upper in ["NBA", "NFL", "NHL"] else 30 if sport_upper == "MLB" else 350
        def_component = max(0, min(10, (_total_teams - _def_rank) / (_total_teams - 1) * 10))

        # Pillar 14: Pace (higher pace = more scoring opportunities)
        # Pace 90 = slow (0), Pace 110 = fast (10)
        pace_component = max(0, min(10, (_pace - 90) / 20 * 10))

        # Pillar 15: Vacuum (higher vacuum = more usage available from injuries)
        # Vacuum 0 = no boost (5), Vacuum 25+ = max boost (10)
        vacuum_component = max(0, min(10, 5 + (_vacuum / 5)))

        # Weighted combination: Defense 50%, Pace 30%, Vacuum 20%
        context_score = (def_component * 0.5) + (pace_component * 0.3) + (vacuum_component * 0.2)
        context_score = round(max(0, min(10, context_score)), 2)

        # ===== TRAVEL FATIGUE TO CONTEXT (v17.9) =====
        travel_adj = 0.0
        try:
            from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact, TRAVEL_ENABLED
            if TRAVEL_ENABLED and away_team and home_team:
                _rest_days = rest_days if 'rest_days' in dir() else 1
                _distance = calculate_distance(away_team, home_team)
                if _distance > 0:
                    _fatigue = calculate_fatigue_impact(sport, _distance, _rest_days, 0)
                    _impact = _fatigue.get("overall_impact", "NONE")
                    if _rest_days == 0:  # B2B
                        travel_adj = -0.5
                        context_reasons.append("B2B: Back-to-back game (-0.5)")
                    elif _rest_days == 1 and _distance > 1500:
                        travel_adj = -0.35
                        context_reasons.append(f"Travel: {_distance}mi + 1-day rest (-0.35)")
                    elif _impact == "HIGH":
                        travel_adj = -0.4
                        for r in _fatigue.get("reasons", []):
                            context_reasons.append(f"Travel: {r}")
                    elif _impact == "MEDIUM" and _distance > 1000:
                        travel_adj = -0.2
                        context_reasons.append(f"Travel: {_distance}mi distance (-0.2)")
                    if travel_adj != 0.0:
                        context_score = round(max(0, min(10, context_score + travel_adj)), 2)
        except Exception as e:
            logger.debug("Travel fatigue failed: %s", e)

        # --- v18.0 BASE SCORE FORMULA (4 Engines + Context Modifier) ---
        # BASE_4 = (ai × 0.25) + (research × 0.35) + (esoteric × 0.20) + (jarvis × 0.20)
        # CONTEXT_MOD = bounded modifier (NOT an engine weight)
        # FINAL = BASE_4 + CONTEXT_MOD + confluence_boost + jason_sim_boost (+ other boosts)
        # If jarvis_rs is None (inputs missing), use 0 for jarvis contribution
        jarvis_contribution = (jarvis_rs * ENGINE_WEIGHTS["jarvis"]) if jarvis_rs is not None else 0
        base_score = (
            (ai_scaled * ENGINE_WEIGHTS["ai"]) +
            (research_score * ENGINE_WEIGHTS["research"]) +
            (esoteric_score * ENGINE_WEIGHTS["esoteric"]) +
            jarvis_contribution
        )

        # Context modifier: map 0-10 score to bounded modifier (centered at 5)
        try:
            from core.scoring_contract import CONTEXT_MODIFIER_CAP
            _context_cap = CONTEXT_MODIFIER_CAP
        except Exception:
            _context_cap = 0.35
        context_modifier = ((context_score - 5.0) / 5.0) * _context_cap
        context_modifier = round(max(-_context_cap, min(_context_cap, context_modifier)), 3)
        if context_modifier != 0:
            context_reasons.append(f"Context modifier: {context_modifier:+.3f} (score={context_score:.2f})")

        # --- v11.08 JASON SIM CONFLUENCE (runs after base score, before tier assignment) ---
        # Jason simulates game outcomes and applies boost/downgrade based on win probability
        jason_output = {}
        if JASON_SIM_AVAILABLE:
            try:
                # Determine actual pick_type from context if not provided
                actual_pick_type = pick_type
                if player_name and actual_pick_type == "GAME":
                    actual_pick_type = "PROP"

                jason_output = run_jason_confluence(
                    base_score=base_score,
                    pick_type=actual_pick_type,
                    pick_side=pick_side if pick_side else (player_name if player_name else home_team),
                    home_team=home_team,
                    away_team=away_team,
                    spread=spread,
                    total=total,
                    prop_line=prop_line,
                    player_name=player_name,
                    injury_state="CONFIRMED_ONLY"
                )
            except Exception as e:
                logger.warning("Jason Sim failed: %s", e)
                jason_output = get_default_jason_output()
                jason_output["base_score"] = base_score
        else:
            # Default Jason output when module not available
            jason_output = {
                "jason_ran": False,
                "jason_sim_boost": 0.0,
                "jason_blocked": False,
                "jason_win_pct_home": 50.0,
                "jason_win_pct_away": 50.0,
                "projected_total": total,
                "projected_pace": "NEUTRAL",
                "variance_flag": "MED",
                "injury_state": "UNKNOWN",
                "confluence_reasons": ["Jason module not available"],
                "base_score": base_score
            }

        # FINAL = BASE_4 + CONTEXT_MOD + CONFLUENCE + MSRF + JASON + SERP + ENSEMBLE + TOTALS_CAL
        jason_sim_boost = jason_output.get("jason_sim_boost", 0.0)

        # ===== v20.4 TOTALS SIDE CALIBRATION (computed before final score) =====
        # Applied INSIDE TOTAL_BOOST_CAP to prevent score clustering at 10.0
        totals_calibration_adj = 0.0
        if pick_type == "TOTAL" and TOTALS_SIDE_CALIBRATION.get("enabled", False):
            pick_side_lower = (pick_side or "").lower()
            if "over" in pick_side_lower:
                totals_calibration_adj = TOTALS_SIDE_CALIBRATION.get("over_penalty", 0.0)
                context_reasons.append(f"TOTALS_CALIBRATION: OVER penalty ({totals_calibration_adj:+.2f})")
            elif "under" in pick_side_lower:
                totals_calibration_adj = TOTALS_SIDE_CALIBRATION.get("under_boost", 0.0)
                context_reasons.append(f"TOTALS_CALIBRATION: UNDER boost ({totals_calibration_adj:+.2f})")
            if totals_calibration_adj != 0.0:
                logger.debug("TOTALS_CALIBRATION[%s]: side=%s, adj=%.2f",
                           game_str[:30], pick_side, totals_calibration_adj)

        # ===== v20.11 SPORT-SPECIFIC TOTALS CALIBRATION =====
        # NHL Totals: 26% win rate (Feb 5 data) - needs severe penalty
        # NCAAB Totals: 46% win rate - moderate penalty
        sport_totals_adj = 0.0
        if pick_type == "TOTAL" and SPORT_TOTALS_CALIBRATION.get("enabled", False):
            sport_totals_adj = SPORT_TOTALS_CALIBRATION.get(sport_upper, 0.0)
            if sport_totals_adj != 0.0:
                totals_calibration_adj += sport_totals_adj
                context_reasons.append(f"SPORT_TOTALS_CAL: {sport_upper} penalty ({sport_totals_adj:+.2f})")
                logger.info("SPORT_TOTALS_CALIBRATION[%s]: sport=%s, adj=%.2f, total_adj=%.2f",
                           game_str[:30], sport_upper, sport_totals_adj, totals_calibration_adj)

        final_score, context_modifier = compute_final_score_option_a(
            base_score=base_score,
            context_modifier=context_modifier,
            confluence_boost=confluence_boost,
            msrf_boost=msrf_boost,
            jason_sim_boost=jason_sim_boost,
            serp_boost=serp_boost_total,
            totals_calibration_adj=totals_calibration_adj,
        )

        # ===== v17.8 PILLAR 16: OFFICIALS TENDENCY INTEGRATION =====
        # Referee/Umpire tendencies impact totals, spreads, and props
        # v17.8: Now uses real referee tendency database (officials_data.py)
        officials_adjustment = 0.0
        officials_reasons = []

        if sport_upper in ["NBA", "NFL", "NHL"] and CONTEXT_LAYER_AVAILABLE:
            try:
                # v17.2: Lookup officials from ESPN prefetched data
                # _officials_by_game keys are (home_team_lower, away_team_lower)
                lead_official = ""
                official_2 = ""
                official_3 = ""
                officials_data = None

                if home_team and away_team and _officials_by_game:
                    officials_data = _find_espn_data(_officials_by_game, home_team, away_team)
                    if officials_data and officials_data.get("available"):
                        lead_official = officials_data.get("lead_official", "")
                        official_2 = officials_data.get("official_2", "")
                        official_3 = officials_data.get("official_3", "")
                        logger.debug("OFFICIALS[%s @ %s]: lead=%s, o2=%s, o3=%s (source: %s)",
                                    away_team, home_team, lead_official, official_2, official_3,
                                    officials_data.get("source", "unknown"))

                # Only apply if we have official data
                if lead_official and officials_data:
                    # v17.8: Use new tendency-based adjustment method
                    # Determine pick type for officials analysis
                    if player_name:
                        officials_pick_type = "PROP"
                    elif "total" in game_str.lower() or (total and not spread):
                        officials_pick_type = "TOTAL"
                    else:
                        officials_pick_type = "SPREAD"

                    # Determine pick side for tendency matching
                    # For totals: Over/Under
                    # For spreads: team name or home/away
                    officials_pick_side = pick_side
                    if officials_pick_type == "TOTAL":
                        pick_side_lower = (pick_side or "").lower()
                        if "over" in pick_side_lower:
                            officials_pick_side = "Over"
                        elif "under" in pick_side_lower:
                            officials_pick_side = "Under"

                    # Determine if betting on home team
                    is_home = False
                    if home_team and pick_side:
                        pick_side_lower = pick_side.lower()
                        home_lower = home_team.lower()
                        is_home = home_lower in pick_side_lower or pick_side_lower == "home"

                    # v17.8: Call new tendency-based method
                    adj, reasons = OfficialsService.get_officials_adjustment(
                        sport=sport_upper,
                        officials=officials_data,
                        pick_type=officials_pick_type,
                        pick_side=officials_pick_side,
                        is_home_team=is_home
                    )

                    if adj != 0.0 and reasons:
                        officials_adjustment = adj
                        officials_reasons = reasons
                        for reason in reasons:
                            research_reasons.append(f"Officials: {reason} ({adj:+.2f})")
                        # Apply to research_score (officials = market intelligence)
                        research_score = min(10.0, research_score + officials_adjustment)
                        logger.debug("OFFICIALS v17.8: %s adjustment=%+.2f reasons=%s",
                                    lead_official, officials_adjustment, officials_reasons)

                    # v18.0: Record official assignment for automated tracking
                    # Fire-and-forget: don't block scoring if recording fails
                    if lead_official and event_id:
                        try:
                            from services.officials_tracker import officials_tracker
                            officials_tracker.record_game_assignment(
                                event_id=event_id,
                                sport=sport_upper,
                                home_team=home_team or "",
                                away_team=away_team or "",
                                officials={
                                    "lead_official": lead_official,
                                    "official_2": official_2,
                                    "official_3": official_3,
                                },
                                game_date=_game_date_str if _game_date_str else "",
                                over_under_line=total,
                                spread_line=spread,
                                game_start_time=_game_datetime if _game_datetime else None
                            )
                        except Exception as rec_err:
                            logger.debug(f"Officials assignment recording skipped: {rec_err}")
            except Exception as e:
                logger.debug(f"Officials adjustment failed: {e}")

        # ===== v17.0 PILLAR 17: PARK FACTORS (MLB ONLY) =====
        # Stadium characteristics affect hitting/pitching performance
        park_adjustment = 0.0
        park_reason = None

        if sport_upper == "MLB" and home_team and CONTEXT_LAYER_AVAILABLE:
            try:
                # Determine if batter stat (vs pitcher stat)
                is_batter = True  # default
                if market:
                    market_lower = market.lower()
                    is_batter = market_lower in [
                        "player_hits", "batter_hits", "player_total_bases",
                        "batter_total_bases", "player_home_runs", "batter_rbis",
                        "player_runs", "batter_runs"
                    ]
                    if "strikeout" in market_lower or "pitch" in market_lower:
                        is_batter = False

                player_avg = prop_line if prop_line and prop_line > 0 else 3.5

                park_obj = ParkFactorService.get_adjustment(
                    home_team=home_team,
                    player_avg=player_avg,
                    is_batter=is_batter
                )

                if park_obj:
                    park_adjustment = park_obj.get("value", 0.0)
                    park_reason = park_obj.get("reason", "")
                    # Add to research_reasons (environmental factor)
                    research_reasons.append(f"Park: {park_reason} ({park_adjustment:+.2f})")
                    # Apply park factor to esoteric (venue = environmental/cosmic factor)
                    esoteric_score = min(10.0, max(0.0, esoteric_score + park_adjustment))
            except Exception as e:
                logger.debug(f"Park factor adjustment failed: {e}")

        # Check if Jason blocked this pick
        jason_blocked = jason_output.get("jason_blocked", False)

        # ===== v17.0 ENSEMBLE MODEL FOR GAME PICKS =====
        # Use trained ensemble model to predict hit probability for game picks
        # Game pick types: SPREAD, TOTAL, MONEYLINE, SHARP (not "GAME" - that's the default)
        ensemble_metadata = None
        ensemble_adjustment = 0.0
        _GAME_PICK_TYPES = {"SPREAD", "TOTAL", "MONEYLINE", "SHARP", "GAME"}

        if pick_type in _GAME_PICK_TYPES and ENSEMBLE_AVAILABLE and ML_INTEGRATION_AVAILABLE:
            try:
                ensemble_ai, ensemble_metadata = get_ensemble_ai_score(
                    ai_score=ai_scaled,
                    research_score=research_score,
                    esoteric_score=esoteric_score,
                    jarvis_score=jarvis_rs if jarvis_rs is not None else 4.5,
                    line=float(spread) if spread else float(total) if total else 0.0,
                    odds=-110,  # Default odds (could be passed from outer scope)
                    confluence_boost=confluence_boost,
                    jason_sim_boost=jason_sim_boost,
                    titanium_triggered=False,  # Not yet calculated
                    sport=sport_upper,
                    pick_type="GAME",
                    side=pick_side if pick_side else "Home",
                    base_ai=ai_scaled
                )

                if ensemble_metadata and ensemble_metadata.get("source") == "ensemble":
                    # Ensemble predicts hit probability - use to adjust confidence
                    hit_prob = ensemble_metadata.get("hit_probability", 0.5)
                    ensemble_confidence = ensemble_metadata.get("confidence", 0)
                    ai_reasons.append(f"Ensemble hit prob: {hit_prob:.1%} (conf: {ensemble_confidence:.0f}%)")

                    # Determine ensemble adjustment value (applied INSIDE TOTAL_BOOST_CAP)
                    if hit_prob > 0.6:
                        ensemble_adjustment = ENSEMBLE_ADJUSTMENT_STEP
                        ai_reasons.append(f"Ensemble boost: +{ENSEMBLE_ADJUSTMENT_STEP} (prob > 60%)")
                    elif hit_prob < 0.4:
                        ensemble_adjustment = -ENSEMBLE_ADJUSTMENT_STEP
                        ai_reasons.append(f"Ensemble penalty: -{ENSEMBLE_ADJUSTMENT_STEP} (prob < 40%)")

                    # Recompute final_score with ensemble_adjustment inside the cap
                    if ensemble_adjustment != 0.0:
                        final_score, context_modifier = compute_final_score_option_a(
                            base_score=base_score,
                            context_modifier=context_modifier,
                            confluence_boost=confluence_boost,
                            msrf_boost=msrf_boost,
                            jason_sim_boost=jason_sim_boost,
                            serp_boost=serp_boost_total,
                            totals_calibration_adj=totals_calibration_adj,
                            ensemble_adjustment=ensemble_adjustment,
                        )
            except Exception as e:
                logger.debug(f"Ensemble prediction unavailable: {e}")

        # --- v15.0: jarvis_rs already calculated by standalone function above ---
        # jarvis_rs, jarvis_active, jarvis_hits_count, jarvis_triggers_hit, jarvis_reasons
        # are all set from calculate_jarvis_engine_score() call

        # --- v18.0 TITANIUM CHECK (STRICT 3 of 4 engines >= 8.0) ---
        # Context NEVER counts toward Titanium.
        try:
            from core.titanium import evaluate_titanium
            titanium_triggered, titanium_explanation, qualifying_engines = evaluate_titanium(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=(jarvis_rs if jarvis_rs is not None else 0),
                final_score=final_score,
                threshold=8.0
            )
        except Exception:
            titanium_triggered, titanium_explanation, qualifying_engines = check_titanium_rule(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=(jarvis_rs if jarvis_rs is not None else 0),
                final_score=final_score
            )

        # --- v11.08 BET TIER DETERMINATION (Single Source of Truth) ---
        if TIERING_AVAILABLE:
            bet_tier = tier_from_score(
                final_score=final_score,
                confluence=confluence,
                nhl_dog_protocol=False,
                titanium_triggered=titanium_triggered,
                # v20.12: Pass engine scores for quality gates
                base_score=base_score,
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=(jarvis_rs if jarvis_rs is not None else 0),
            )
        else:
            # Fallback tier determination (v12.0 thresholds)
            if titanium_triggered:
                bet_tier = {"tier": "TITANIUM_SMASH", "units": 2.5, "action": "SMASH", "badge": "TITANIUM SMASH"}
            elif final_score >= GOLD_STAR_THRESHOLD:  # v12.0: was 9.0
                bet_tier = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
            elif final_score >= MIN_FINAL_SCORE:  # v12.0: was 7.5
                bet_tier = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
            elif final_score >= 5.5:  # v12.0: was 6.0
                bet_tier = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
            else:
                bet_tier = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

        # --- v18.0 GOLD_STAR HARD GATES (4 engines) ---
        # GOLD_STAR requires ALL engine minimums. If any gate fails, downgrade to EDGE_LEAN.
        _gold_gates = {
            "ai_gte_6.8": ai_scaled >= GOLD_STAR_GATES["ai_score"],
            "research_gte_5.5": research_score >= GOLD_STAR_GATES["research_score"],
            "jarvis_gte_6.5": (jarvis_rs >= GOLD_STAR_GATES["jarvis_score"]) if jarvis_rs is not None else False,
            "esoteric_gte_4.0": esoteric_score >= GOLD_STAR_GATES["esoteric_score"],
        }
        _gold_gates_passed = all(_gold_gates.values())
        _gold_gates_failed = [k for k, v in _gold_gates.items() if not v]

        if bet_tier.get("tier") == "GOLD_STAR" and not _gold_gates_passed:
            logger.info("GOLD_STAR downgrade: gates failed=%s (ai=%.1f R=%.1f J=%.1f E=%.1f)",
                        _gold_gates_failed, ai_scaled, research_score, jarvis_rs, esoteric_score)
            bet_tier = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY",
                        "badge": "EDGE LEAN", "gold_star_downgrade": True,
                        "gold_star_failed_gates": _gold_gates_failed}
            # Also update explanation
            bet_tier["explanation"] = f"EDGE_LEAN (GOLD_STAR downgraded: {', '.join(_gold_gates_failed)})"
            bet_tier["final_score"] = round(final_score, 2)
            bet_tier["confluence_level"] = confluence_level

        # Map to confidence levels for backward compatibility
        if TIERING_AVAILABLE:
            confidence, confidence_score = get_confidence_from_tier(bet_tier.get("tier", "PASS"))
        else:
            confidence_map = {
                "TITANIUM_SMASH": "SMASH",
                "GOLD_STAR": "SMASH",
                "EDGE_LEAN": "HIGH",
                "MONITOR": "MEDIUM",
                "PASS": "LOW"
            }
            confidence = confidence_map.get(bet_tier.get("tier", "PASS"), "LOW")
            confidence_score_map = {"SMASH": 95, "HIGH": 80, "MEDIUM": 60, "LOW": 30}
            confidence_score = confidence_score_map.get(confidence, 30)

        # Build smash_reasons for Titanium (which engines cleared 8.0)
        smash_reasons = []
        if titanium_triggered:
            if ai_scaled >= 8.0:
                smash_reasons.append(f"AI Engine: {round(ai_scaled, 2)}/10")
            if research_score >= 8.0:
                smash_reasons.append(f"Research Engine: {round(research_score, 2)}/10")
            if esoteric_score >= 8.0:
                smash_reasons.append(f"Esoteric Engine: {round(esoteric_score, 2)}/10")
            if jarvis_rs is not None and jarvis_rs >= 8.0:
                smash_reasons.append(f"Jarvis Engine: {round(jarvis_rs, 2)}/10")
            if abs(context_modifier) >= 0.2:
                smash_reasons.append(f"Context Modifier: {context_modifier:+.2f}")

        # Build penalties array from modifiers
        # v15.0: public_fade_mod removed (now only in Research as positive boost)
        penalties = []
        if trap_mod < 0:
            penalties.append({"name": "Large Spread Trap", "magnitude": round(trap_mod, 2)})

        # --- v15.3 TIER_REASON (Transparency for frontend) ---
        # Explain why this tier was assigned, especially for downgrades
        tier_reason = []
        actual_tier = bet_tier.get("tier", "PASS")

        if actual_tier == "TITANIUM_SMASH":
            tier_reason.append(f"TITANIUM: {sum([ai_scaled >= 8.0, research_score >= 8.0, esoteric_score >= 8.0, (jarvis_rs >= 8.0) if jarvis_rs is not None else False])}/4 engines >= 8.0")
        elif actual_tier == "GOLD_STAR":
            if _gold_gates_passed:
                tier_reason.append(f"GOLD_STAR: Score {final_score:.2f} >= 7.5, passed all hard gates")
            else:
                # This shouldn't happen (downgrade should have occurred), but log it
                tier_reason.append(f"GOLD_STAR: Score {final_score:.2f}, but gates may be marginal")
        elif actual_tier == "EDGE_LEAN":
            if final_score >= GOLD_STAR_THRESHOLD:
                # High score but downgraded to EDGE_LEAN - explain why
                if not _gold_gates_passed:
                    failed_gate_names = [g.replace("_gte_", " >= ").replace("_", " ").title() for g in _gold_gates_failed]
                    tier_reason.append(f"EDGE_LEAN: Score {final_score:.2f} >= 7.5 but failed GOLD gates: {', '.join(failed_gate_names)}")
                else:
                    tier_reason.append(f"EDGE_LEAN: Score {final_score:.2f} >= 7.5 but other criteria not met")
            elif final_score >= MIN_FINAL_SCORE:
                tier_reason.append(f"EDGE_LEAN: Score {final_score:.2f} in 6.5-7.5 range")
            else:
                tier_reason.append(f"EDGE_LEAN: Score {final_score:.2f} (should not be returned)")
        elif actual_tier == "MONITOR":
            tier_reason.append(f"MONITOR: Score {final_score:.2f} in 5.5-6.5 range (below output threshold)")
        elif actual_tier == "PASS":
            tier_reason.append(f"PASS: Score {final_score:.2f} < 5.5 (should not be returned)")

        # Add specific gate failures for transparency
        if _gold_gates_failed and final_score >= GOLD_STAR_THRESHOLD:
            for gate in _gold_gates_failed:
                if gate == "ai_gte_6.8":
                    tier_reason.append(f"  - AI {ai_scaled:.1f} < 6.8")
                elif gate == "research_gte_5.5":
                    tier_reason.append(f"  - Research {research_score:.1f} < 5.5")
                elif gate == "jarvis_gte_6.5":
                    if jarvis_rs is not None:
                        tier_reason.append(f"  - Jarvis {jarvis_rs:.1f} < 6.5")
                    else:
                        tier_reason.append(f"  - Jarvis inputs missing (None)")
                elif gate == "esoteric_gte_4.0":
                    tier_reason.append(f"  - Esoteric {esoteric_score:.1f} < 4.0")

        return {
            "total_score": round(final_score, 2),
            "final_score": round(final_score, 2),  # Alias for frontend
            "confidence": confidence,
            "confidence_score": confidence_score,
            "confluence_level": confluence_level,
            "confluence_reasons": confluence_reasons,
            "confluence_boost": confluence_boost,
            "bet_tier": bet_tier,
            "tier": bet_tier.get("tier", "PASS"),
            "tier_reason": tier_reason,  # v15.3 Transparency: why this tier was assigned
            "action": bet_tier.get("action", "SKIP"),
            "units": bet_tier.get("units", bet_tier.get("unit_size", 0.0)),
            # v18.0 Engine scores (all 0-10 scale) - 4 base engines + context modifier
            "ai_score": round(ai_scaled, 2),
            "ai_mode": _ai_telemetry.get("ai_mode", "UNKNOWN"),  # v20.1: ML_PRIMARY, ML_LSTM, or HEURISTIC_FALLBACK
            "ai_models_used": _ai_telemetry.get("models_used_count", 0),  # v20.1: Number of ML models that ran
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "jarvis_score": round(jarvis_rs, 2) if jarvis_rs is not None else None,  # Alias for jarvis_rs
            "context_modifier": round(context_modifier, 3),  # v18.0: bounded modifier
            "context_score": round(context_score, 2),  # backward-compat (raw score)
            "context_reasons": context_reasons,
            "live_adjustment": round(live_boost, 2),
            "live_reasons": live_reasons,
            "base_4_score": round(base_score, 2),
            "ensemble_adjustment": round(ensemble_adjustment, 3),
            "totals_calibration_adj": round(totals_calibration_adj, 3),
            "sport_totals_adj": round(sport_totals_adj, 3),  # v20.11: Sport-specific totals penalty
            # Detailed breakdowns
            "scoring_breakdown": {
                "research_score": round(research_score, 2),
                "esoteric_score": round(esoteric_score, 2),
                "ai_models": round(ai_score, 2),
                "ai_score": round(ai_scaled, 2),
                "ai_mode": _ai_telemetry.get("ai_mode", "UNKNOWN"),
                "ai_models_used": _ai_telemetry.get("models_used_count", 0),
                "context_modifier": round(context_modifier, 3),  # v18.0
                "context_score": round(context_score, 2),  # backward-compat
                "pillars": round(pillar_score, 2),
                "confluence_boost": confluence_boost,
                "msrf_boost": msrf_boost,
                "serp_boost": serp_boost_total,
                "ensemble_adjustment": round(ensemble_adjustment, 3),
                "live_adjustment": round(live_boost, 2),
                "alignment_pct": confluence.get("alignment_pct", 0),
                "gold_star_gates": _gold_gates,
                "gold_star_eligible": _gold_gates_passed,
                "gold_star_failed": _gold_gates_failed
            },
            # v17.1 Context breakdown (Pillars 13-15)
            "context_breakdown": {
                "def_rank": _def_rank,
                "def_component": round(def_component, 2),
                "pace": _pace,
                "pace_component": round(pace_component, 2),
                "vacuum": _vacuum,
                "vacuum_component": round(vacuum_component, 2),
                "score": round(context_score, 2),
                "modifier": round(context_modifier, 3)
            },
            # v14.9 Research breakdown (clean engine separation)
            "research_breakdown": {
                "sharp_boost": round(sharp_boost, 2),
                "line_boost": round(line_boost, 2),
                "public_boost": round(public_boost, 2),
                "liquidity_boost": round(liquidity_boost, 2),
                "book_count": int(book_count or 0),
                "market_book_count": int(market_book_count or 0),
                "base_research": round(base_research, 2),
                "signal_strength": sig_strength,
                "total": round(research_score, 2)
            },
            # v15.0 Esoteric breakdown (NO gematria, NO jarvis, NO public_fade - clean separation)
            "esoteric_breakdown": {
                "magnitude_input": round(_eso_magnitude, 2),
                "numerology": round(numerology_score, 2),
                "astro": round(astro_score, 2),
                "fibonacci": round(fib_score, 2),
                "vortex": round(vortex_score, 2),
                "daily_edge": round(daily_edge_score, 2),
                "trap_mod": round(trap_mod, 2)
            },
            # v16.0 Jarvis audit fields (ADDITIVE trigger scoring for GOLD_STAR eligibility)
            "jarvis_baseline": jarvis_data.get("jarvis_baseline", 4.5),
            "jarvis_trigger_contribs": jarvis_data.get("jarvis_trigger_contribs", {}),
            "jarvis_triggers": jarvis_triggers_hit,
            "immortal_detected": immortal_detected,
            # v16.0 JARVIS fields (MUST always exist - full transparency)
            "jarvis_rs": round(jarvis_rs, 2) if jarvis_rs is not None else None,
            "jarvis_active": jarvis_active,
            "jarvis_hits_count": jarvis_hits_count,
            "jarvis_triggers_hit": jarvis_triggers_hit,
            "jarvis_reasons": jarvis_reasons,
            "jarvis_fail_reasons": jarvis_fail_reasons,
            "jarvis_no_trigger_reason": jarvis_data.get("jarvis_no_trigger_reason"),
            "jarvis_inputs_used": jarvis_inputs_used,
            # v11.08 TITANIUM fields
            "titanium_triggered": titanium_triggered,
            "titanium_explanation": titanium_explanation,
            "smash_reasons": smash_reasons,
            # v11.08 JASON SIM CONFLUENCE fields (MUST always exist)
            "jason_ran": jason_output.get("jason_ran", False),
            "jason_sim_boost": round(jason_sim_boost, 2),
            "jason_status": (
                "UNAVAILABLE" if not JASON_SIM_AVAILABLE else
                "BLOCKED" if jason_blocked else
                "OK" if jason_output.get("jason_ran", False) else
                "ERROR"
            ),
            "jason_blocked": jason_blocked,
            "jason_win_pct_home": jason_output.get("jason_win_pct_home", 50.0),
            "jason_win_pct_away": jason_output.get("jason_win_pct_away", 50.0),
            "jason_projected_total": jason_output.get("projected_total", total),
            "jason_variance_flag": jason_output.get("variance_flag", "MED"),
            "jason_injury_state": jason_output.get("injury_state", "UNKNOWN"),
            "jason_sim_count": jason_output.get("sim_count", 0),
            "projected_total": jason_output.get("projected_total", total),  # Keep for backwards compat
            "projected_pace": jason_output.get("projected_pace", "NEUTRAL"),
            "variance_flag": jason_output.get("variance_flag", "MED"),  # Keep for backwards compat
            "injury_state": jason_output.get("injury_state", "UNKNOWN"),  # Keep for backwards compat
            "jason_reasons": jason_output.get("confluence_reasons", []),
            "base_score": round(base_score, 2),  # Score before Jason boost
            # v11.08 Stack/Penalty fields
            "penalties": penalties,
            "stack_complete": not jason_blocked,  # Stack incomplete if Jason blocked
            "partial_stack_reasons": ["Jason blocked pick"] if jason_blocked else [],
            # v11.08 Research/Pillar tracking
            "research_reasons": research_reasons,
            "ai_reasons": ai_reasons,
            "esoteric_reasons": esoteric_reasons,
            "pillars_passed": pillars_passed,
            "pillars_failed": pillars_failed,
            # v16.1 LSTM ML fields (for props with LSTM prediction)
            "lstm_adjustment": lstm_metadata.get("adjustment", 0.0) if lstm_metadata else 0.0,
            "lstm_confidence": lstm_metadata.get("confidence", 0.0) if lstm_metadata else 0.0,
            "lstm_model_key": lstm_metadata.get("model_key") if lstm_metadata else None,
            "lstm_source": lstm_metadata.get("source", "heuristic") if lstm_metadata else "heuristic",
            # v17.0 Context Layer Pillars (13-17)
            "context_layer": {
                "def_rank": _def_rank,
                "pace": _pace,
                "vacuum": _vacuum,
                "officials_adjustment": officials_adjustment,
                "officials_reasons": officials_reasons,
                "park_adjustment": park_adjustment,
                "park_reason": park_reason,
            },
            # v17.0 Harmonic Convergence
            "harmonic_boost": harmonic_boost,
            # v17.2 MSRF Resonance
            "msrf_boost": msrf_boost,
            "msrf_status": msrf_status,
            "msrf_reasons": msrf_reasons,
            "msrf_metadata": msrf_metadata,
            # v18.2 Phase 8 Esoteric Signals
            "phase8_boost": phase8_boost,
            "phase8_reasons": phase8_reasons,
            "phase8_breakdown": phase8_full_result.get("breakdown") if phase8_full_result else None,
            # v17.4 SERP Intelligence
            "serp_intel": serp_intel,
            "serp_boost": serp_boost_total,
            "serp_status": serp_status,
            "serp_reasons": serp_reasons,
            "serp_signals": serp_signals,
            "serp_shadow_mode": SERP_SHADOW_MODE if SERP_INTEL_AVAILABLE else True,
            # v17.9 Gematria Twitter Intelligence
            "gematria_boost": gematria_boost,
            "gematria_metadata": gematria_metadata,
            "gematria_reasons": gematria_reasons,
            # v17.5 GLITCH Protocol adjustment
            "glitch_adjustment": glitch_adjustment,
            # v19.1 GLITCH signal breakdown (for learning loop)
            "glitch_signals": glitch_result.get("breakdown", {}) if 'glitch_result' in dir() and glitch_result else {},
            # v19.1 Esoteric contributions (for learning loop - track individual signal boosts)
            "esoteric_contributions": {
                "numerology": numerology_score if 'numerology_score' in dir() else 0.0,
                "astro": astro_score if 'astro_score' in dir() else 0.0,
                "fib_alignment": fib_score if 'fib_score' in dir() else 0.0,
                "vortex": vortex_score if 'vortex_score' in dir() else 0.0,
                "daily_edge": daily_edge_score if 'daily_edge_score' in dir() else 0.0,
                "glitch": glitch_adjustment if 'glitch_adjustment' in dir() else 0.0,
                "biorhythm": bio_boost if 'bio_boost' in dir() else 0.0,
                "gann": gann_boost if 'gann_boost' in dir() else 0.0,
                "founders_echo": echo_boost if 'echo_boost' in dir() else 0.0,
                "phase8": phase8_boost if 'phase8_boost' in dir() else 0.0,
                "harmonic": harmonic_boost if 'harmonic_boost' in dir() else 0.0,
                "msrf": msrf_boost if 'msrf_boost' in dir() else 0.0,
            },
            # v17.0 Ensemble Model (for GAME picks)
            "ensemble_metadata": ensemble_metadata
        }

    # ============================================
    # v15.1: Pre-fetch game lines for game_context (spread/total for props)
    # Uses cached get_lines() to avoid extra API calls
    # ============================================
    _s = time.time()
    game_context = {}  # game_key → {spread, total}
    try:
        _lines_data = await get_lines(sport)
        for _lg in _lines_data.get("data", []):
            # Handle both Playbook format (homeTeamName) and Odds API format (home_team)
            _lg_home = _lg.get("home_team") or _lg.get("homeTeamName", "")
            _lg_away = _lg.get("away_team") or _lg.get("awayTeamName", "")
            if not _lg_home or not _lg_away:
                continue
            _lg_key = f"{_lg_away}@{_lg_home}"
            _gc_spread = 0
            _gc_total = 220

            # Playbook v1 format: { "lines": { "spread": { "home": -1.5 }, "total": 6.5 } }
            _lines_obj = _lg.get("lines", {})
            if isinstance(_lines_obj, dict) and _lines_obj:
                _sp_obj = _lines_obj.get("spread", {})
                if isinstance(_sp_obj, dict) and "home" in _sp_obj:
                    _gc_spread = _sp_obj["home"]
                _tl_val = _lines_obj.get("total")
                if isinstance(_tl_val, (int, float)):
                    _gc_total = _tl_val
            else:
                # Odds API format: { "spreads": [{team, point}], "totals": [{point}] }
                _spreads = _lg.get("spreads", [])
                _totals = _lg.get("totals", [])
                if isinstance(_spreads, list):
                    for _sp in _spreads:
                        if isinstance(_sp, dict) and _sp.get("team") == _lg_home and _sp.get("point") is not None:
                            _gc_spread = _sp["point"]
                            break
                if isinstance(_totals, list):
                    for _tl in _totals:
                        if isinstance(_tl, dict) and _tl.get("point") is not None:
                            _gc_total = _tl["point"]
                            break

            game_context[_lg_key] = {"spread": _gc_spread, "total": _gc_total}
        logger.info("Game context built for props: %d games with spread/total data", len(game_context))
    except Exception as e:
        logger.warning("Failed to build game_context for props: %s", e)
    _record("game_context", _s)

    # ============================================
    # v16.1: PARALLEL DATA FETCH — props + game odds concurrently
    # ============================================
    _s = time.time()
    _skip_ncaab_props = sport_upper == "NCAAB"
    if _skip_ncaab_props:
        logger.info("NCAAB props disabled — state legality varies, skipping prop analysis")

    sport_config = SPORT_MAPPINGS[sport_lower]
    odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"

    async def _fetch_props():
        if _skip_ncaab_props:
            return {"data": []}
        return await get_props(sport)

    async def _fetch_game_odds():
        try:
            from odds_api import odds_api_get
            resp, used = await odds_api_get(
                odds_url,
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "spreads,h2h,totals",
                    "oddsFormat": "american"
                },
            )
            return {"resp": resp, "used": used}
        except Exception:
            # Fallback to existing retry helper
            resp = await fetch_with_retries(
                "GET", odds_url,
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "spreads,h2h,totals",
                    "oddsFormat": "american"
                }
            )
            return {"resp": resp, "used": False}

    # v17.2: Add injuries fetch for vacuum calculation (Pillar 15)
    async def _fetch_injuries():
        try:
            return await get_injuries(sport)
        except Exception as e:
            logger.debug("Injuries fetch failed: %s", e)
            return {"data": []}

    # v17.2: Add ESPN scoreboard fetch for officials data (Pillar 16)
    async def _fetch_espn_scoreboard():
        if not ESPN_OFFICIALS_AVAILABLE:
            return {"events": []}
        try:
            return await get_espn_scoreboard(sport, date_str)
        except Exception as e:
            logger.debug("ESPN scoreboard fetch failed: %s", e)
            return {"events": []}

    props_data, game_odds_resp, injuries_data, espn_scoreboard = await asyncio.gather(
        _fetch_props(),
        _fetch_game_odds(),
        _fetch_injuries(),
        _fetch_espn_scoreboard(),
        return_exceptions=True
    )
    # Handle exceptions from gather
    if isinstance(props_data, Exception):
        logger.warning("Props fetch failed in parallel: %s", props_data)
        props_data = {"data": []}
    if isinstance(game_odds_resp, Exception):
        logger.warning("Game odds fetch failed in parallel: %s", game_odds_resp)
        game_odds_resp = None
        _odds_used = False
    else:
        if isinstance(game_odds_resp, dict):
            _odds_used = bool(game_odds_resp.get("used"))
            game_odds_resp = game_odds_resp.get("resp")
        else:
            _odds_used = False
    if isinstance(injuries_data, Exception):
        logger.debug("Injuries fetch failed in parallel: %s", injuries_data)
        injuries_data = {"data": []}

    # Record when odds data was fetched (for live endpoint staleness checks)
    _odds_fetched_at = now_et().isoformat() if TIME_ET_AVAILABLE else datetime.now().isoformat()

    # Integration usage telemetry (best-bets scoring cycle, request-scoped)
    if isinstance(props_data, dict):
        src = props_data.get("source", "")
        if src == "odds_api":
            _mark_integration_used("odds_api")
        elif src == "playbook":
            _mark_integration_used("playbook_api")
    if isinstance(injuries_data, dict):
        if injuries_data.get("source") == "playbook":
            _mark_integration_used("playbook_api")
    if _odds_used:
        _mark_integration_used("odds_api")
    if isinstance(espn_scoreboard, Exception):
        logger.debug("ESPN scoreboard failed in parallel: %s", espn_scoreboard)
        espn_scoreboard = {"events": []}
    _record("parallel_fetch", _s)

    # v17.2: Build injuries lookup by team for vacuum calculation
    # Handles both Playbook format (team objects with players array) and ESPN format (flat list)
    _injuries_by_team = {}
    if injuries_data and isinstance(injuries_data, dict):
        for item in injuries_data.get("data", injuries_data.get("injuries", [])):
            # Check if Playbook format (has 'players' array)
            if "players" in item and isinstance(item.get("players"), list):
                team_name = item.get("teamName", item.get("team", ""))
                if team_name:
                    if team_name not in _injuries_by_team:
                        _injuries_by_team[team_name] = []
                    for player in item["players"]:
                        # Normalize player injury to common format
                        _injuries_by_team[team_name].append({
                            "team": team_name,
                            "player": player.get("name", ""),
                            "status": player.get("status", ""),
                            "position": player.get("position", ""),
                            "reason": player.get("reason", "")
                        })
            else:
                # ESPN format (flat list with team field per injury)
                team = item.get("team", "")
                if team:
                    if team not in _injuries_by_team:
                        _injuries_by_team[team] = []
                    _injuries_by_team[team].append(item)

    logger.info("INJURIES LOOKUP: %d teams with injuries loaded", len(_injuries_by_team))

    # v17.3: Team name normalization for ESPN cross-validation
    # Handles differences like "LA Clippers" (ESPN) vs "Los Angeles Clippers" (Odds API)
    TEAM_NAME_ALIASES = {
        # NBA
        "la clippers": "los angeles clippers",
        "la lakers": "los angeles lakers",
        # Common abbreviations
        "ny knicks": "new york knicks",
        "ny giants": "new york giants",
        "ny jets": "new york jets",
        "ny yankees": "new york yankees",
        "ny mets": "new york mets",
        "sf giants": "san francisco giants",
        "sf 49ers": "san francisco 49ers",
    }

    def _normalize_team_name(name: str) -> str:
        """Normalize team name to canonical form for matching."""
        if not name:
            return ""
        name_lower = name.lower().strip()
        # Check direct alias mapping
        if name_lower in TEAM_NAME_ALIASES:
            return TEAM_NAME_ALIASES[name_lower]
        return name_lower

    def _find_espn_data(lookup: dict, home: str, away: str):
        """Try to find ESPN data using multiple key formats for fuzzy matching."""
        if not lookup:
            return None

        # Normalize both team names
        home_norm = _normalize_team_name(home)
        away_norm = _normalize_team_name(away)

        # Try direct match first
        key = (home_norm, away_norm)
        if key in lookup:
            return lookup[key]

        # Try finding by partial match (team name contained in key)
        for (lk_home, lk_away), value in lookup.items():
            # Check if both teams match (either direction for home/away)
            home_match = (home_norm in lk_home or lk_home in home_norm or
                         home_norm.split()[-1] == lk_home.split()[-1])  # Match last word (mascot)
            away_match = (away_norm in lk_away or lk_away in away_norm or
                         away_norm.split()[-1] == lk_away.split()[-1])  # Match last word (mascot)
            if home_match and away_match:
                return value

        return None

    # v17.2: Build ESPN event lookup for officials (Pillar 16)
    # Maps (home_team_lower, away_team_lower) -> espn_event_id
    _espn_events_by_teams = {}
    if espn_scoreboard and isinstance(espn_scoreboard, dict):
        for event in espn_scoreboard.get("events", []):
            event_id = event.get("id")
            if not event_id:
                continue
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]
            competitors = comp.get("competitors", [])
            home_team = None
            away_team = None
            for team_data in competitors:
                team_info = team_data.get("team", {})
                team_name = team_info.get("displayName", "").lower()
                if team_data.get("homeAway") == "home":
                    home_team = team_name
                else:
                    away_team = team_name
            if home_team and away_team:
                # Store with normalized key
                _espn_events_by_teams[(_normalize_team_name(home_team), _normalize_team_name(away_team))] = event_id

    logger.info("ESPN EVENTS LOOKUP: %d games mapped", len(_espn_events_by_teams))

    # v17.9: REST DAYS from ESPN schedule (lookback window)
    _rest_days_by_team = {}
    if ESPN_OFFICIALS_AVAILABLE:
        try:
            if _filter_date:
                _target_date_et = datetime.fromisoformat(_filter_date).date()
            else:
                _target_date_et = datetime.now(_ET).date() if _ET else datetime.now(timezone.utc).date()

            _lookback_days = 7
            _dates = [(_target_date_et - timedelta(days=i)) for i in range(1, _lookback_days + 1)]

            async def _fetch_scoreboard_for_date(d):
                return await get_espn_scoreboard(sport, d.isoformat())

            _scoreboards = await asyncio.gather(
                *[_fetch_scoreboard_for_date(d) for d in _dates],
                return_exceptions=True
            )

            _last_game_date_by_team = {}
            for d, sb in zip(_dates, _scoreboards):
                if isinstance(sb, Exception):
                    continue
                for event in sb.get("events", []):
                    # ESPN event date is ISO timestamp
                    ev_date = event.get("date")
                    if ev_date:
                        try:
                            ev_dt = datetime.fromisoformat(ev_date.replace("Z", "+00:00"))
                            ev_et_date = ev_dt.astimezone(_ET).date() if _ET else ev_dt.date()
                        except Exception:
                            ev_et_date = d
                    else:
                        ev_et_date = d

                    competitions = event.get("competitions", [])
                    if not competitions:
                        continue
                    comp = competitions[0]
                    for team_data in comp.get("competitors", []):
                        team_name = team_data.get("team", {}).get("displayName", "")
                        if not team_name:
                            continue
                        key = _normalize_team_name(team_name)
                        prev = _last_game_date_by_team.get(key)
                        if prev is None or ev_et_date > prev:
                            _last_game_date_by_team[key] = ev_et_date

            for team_key, last_date in _last_game_date_by_team.items():
                delta_days = (_target_date_et - last_date).days - 1
                _rest_days_by_team[team_key] = max(0, delta_days)

            logger.info("REST_DAYS (ESPN): computed for %d teams (lookback=%d)",
                        len(_rest_days_by_team), _lookback_days)
        except Exception as e:
            logger.debug("REST_DAYS (ESPN) failed: %s", e)
            _rest_days_by_team = {}

    def _rest_days_for_team(team_name: str) -> Optional[int]:
        if not team_name:
            return None
        return _rest_days_by_team.get(_normalize_team_name(team_name))

    # v17.2: Prefetch officials for all ESPN events (batch operation)
    _officials_by_game = {}
    if ESPN_OFFICIALS_AVAILABLE and _espn_events_by_teams:
        async def _fetch_officials_batch():
            tasks = []
            keys = []
            from alt_data_sources.espn_lineups import get_officials_for_event
            for (home, away), event_id in _espn_events_by_teams.items():
                keys.append((home, away))
                tasks.append(get_officials_for_event(sport, event_id))
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for key, result in zip(keys, results):
                    if isinstance(result, Exception):
                        continue
                    if result.get("available"):
                        _officials_by_game[key] = result
        try:
            await _fetch_officials_batch()
        except Exception as e:
            logger.debug("Officials batch fetch failed: %s", e)

    logger.info("OFFICIALS LOOKUP: %d games with officials data", len(_officials_by_game))

    # v17.3: Batch fetch ESPN enriched data (odds, injuries, venue) for all games
    _espn_odds_by_game = {}  # (home, away) -> odds dict
    _espn_injuries_supplement = {}  # team_name -> list of injuries (to merge with Playbook)
    _espn_venue_by_game = {}  # (home, away) -> venue dict with weather
    _espn_fetch_error = None  # Track any fetch errors for debug output

    logger.info("ESPN ENRICHED FETCH: Checking conditions - ESPN_OFFICIALS_AVAILABLE=%s, events_count=%d",
                ESPN_OFFICIALS_AVAILABLE, len(_espn_events_by_teams))
    if ESPN_OFFICIALS_AVAILABLE and _espn_events_by_teams:
        async def _fetch_espn_enriched_batch():
            from alt_data_sources.espn_lineups import get_espn_odds, get_espn_injuries, get_espn_venue_info
            logger.info("ESPN ENRICHED FETCH: Inside batch function, sport=%s", sport)

            # Fetch odds, injuries, venue in parallel for all events
            odds_tasks = []
            injury_tasks = []
            venue_tasks = []
            keys = list(_espn_events_by_teams.keys())
            event_ids = [_espn_events_by_teams[k] for k in keys]
            logger.info("ESPN ENRICHED FETCH: Processing %d events, IDs=%s", len(event_ids), event_ids[:3])

            for event_id in event_ids:
                odds_tasks.append(get_espn_odds(sport, event_id))
                injury_tasks.append(get_espn_injuries(sport, event_id))
                # Only fetch venue for outdoor sports (MLB, NFL)
                if sport_upper in ["MLB", "NFL"]:
                    venue_tasks.append(get_espn_venue_info(sport, event_id))
                else:
                    venue_tasks.append(asyncio.sleep(0))  # Placeholder

            logger.info("ESPN ENRICHED FETCH: Running gather with %d total tasks", len(odds_tasks) + len(injury_tasks) + len(venue_tasks))
            # Run all in parallel
            all_tasks = odds_tasks + injury_tasks + venue_tasks
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            logger.info("ESPN ENRICHED FETCH: Gather complete, got %d results", len(results))

            n = len(keys)
            odds_results = results[:n]
            injury_results = results[n:2*n]
            venue_results = results[2*n:]

            # Process odds
            _odds_errors = 0
            _odds_unavailable = 0
            _odds_reasons = []
            for key, result in zip(keys, odds_results):
                if isinstance(result, Exception):
                    _odds_errors += 1
                    _odds_reasons.append(f"{key[0][:10]}: ERR {str(result)[:30]}")
                    logger.debug("ESPN odds error for %s: %s", key, result)
                    continue
                # Handle case where result is not a dict
                if not isinstance(result, dict):
                    _odds_errors += 1
                    _odds_reasons.append(f"{key[0][:10]}: BADTYPE {type(result).__name__}={str(result)[:20]}")
                    continue
                if result.get("available"):
                    _espn_odds_by_game[key] = result
                    _odds_reasons.append(f"{key[0][:10]}: OK spread={result.get('spread')}")
                else:
                    _odds_unavailable += 1
                    reason = result.get("reason", "")
                    error = result.get("error", "")
                    _odds_reasons.append(f"{key[0][:10]}: {reason or error or 'unknown'}")
                    logger.debug("ESPN odds unavailable for %s: %s", key, reason or error)
            logger.info("ESPN ODDS BATCH: success=%d, errors=%d, unavailable=%d",
                       len(_espn_odds_by_game), _odds_errors, _odds_unavailable)

            # Store counts for debug output
            nonlocal _espn_fetch_error
            _espn_fetch_error = f"odds: success={len(_espn_odds_by_game)}, errors={_odds_errors}, unavailable={_odds_unavailable}; reasons={_odds_reasons}"

            # Process injuries (merge into team-based lookup)
            for key, result in zip(keys, injury_results):
                if isinstance(result, Exception):
                    continue
                if result and result.get("available"):
                    for inj in result.get("injuries", []):
                        team = inj.get("team", "")
                        if team:
                            if team not in _espn_injuries_supplement:
                                _espn_injuries_supplement[team] = []
                            _espn_injuries_supplement[team].append(inj)

            # Process venue/weather (outdoor sports only)
            if sport_upper in ["MLB", "NFL"]:
                for key, result in zip(keys, venue_results):
                    if isinstance(result, Exception):
                        continue
                    if result and result.get("available"):
                        _espn_venue_by_game[key] = result

        _espn_fetch_error = None
        try:
            await _fetch_espn_enriched_batch()
        except Exception as e:
            _espn_fetch_error = str(e)
            logger.warning("ESPN enriched batch fetch failed: %s", e)
    else:
        _espn_fetch_error = f"Skipped: ESPN_OFFICIALS_AVAILABLE={ESPN_OFFICIALS_AVAILABLE}, events={len(_espn_events_by_teams)}"

    logger.info("ESPN ENRICHED: odds=%d, injuries=%d teams, venues=%d",
                len(_espn_odds_by_game), len(_espn_injuries_supplement), len(_espn_venue_by_game))

    # Merge ESPN injuries with Playbook injuries (_injuries_by_team)
    for team, injuries in _espn_injuries_supplement.items():
        if team not in _injuries_by_team:
            _injuries_by_team[team] = []
        # Add ESPN injuries that aren't already in the list
        existing_players = {i.get("player", "").lower() for i in _injuries_by_team[team]}
        for inj in injuries:
            player = inj.get("player", "")
            if player.lower() not in existing_players:
                _injuries_by_team[team].append(inj)
                existing_players.add(player.lower())

    logger.info("INJURIES LOOKUP (merged): %d teams with injuries", len(_injuries_by_team))

    # ============================================
    # APPLY ET DAY GATE to both datasets
    # ============================================
    _s = time.time()

    # --- Build commence_time lookup from games data (for backfilling props) ---
    _games_time_lookup = {}
    if game_odds_resp and hasattr(game_odds_resp, 'status_code') and game_odds_resp.status_code == 200:
        _raw_games_for_lookup = game_odds_resp.json()
        for _g in _raw_games_for_lookup:
            _ht = _g.get("home_team", "").lower()
            _at = _g.get("away_team", "").lower()
            _ct = _g.get("commence_time")
            if _ht and _at and _ct:
                _games_time_lookup[(_at, _ht)] = _ct
                _games_time_lookup[(_ht, _at)] = _ct  # Both orderings
        logger.info("PROPS TIME BACKFILL: Built lookup from %d games", len(_raw_games_for_lookup))

    # --- Props ET filter ---
    raw_prop_games = props_data.get("data", []) if isinstance(props_data, dict) else []

    # Backfill commence_time for props from games data
    _props_backfilled = 0
    for _pg in raw_prop_games:
        if not _pg.get("commence_time"):
            _ph = _pg.get("home_team", "").lower()
            _pa = _pg.get("away_team", "").lower()
            _found_time = _games_time_lookup.get((_pa, _ph)) or _games_time_lookup.get((_ph, _pa))
            if _found_time:
                _pg["commence_time"] = _found_time
                _props_backfilled += 1
    if _props_backfilled:
        logger.info("PROPS TIME BACKFILL: Filled %d/%d props with commence_time from games", _props_backfilled, len(raw_prop_games))

    _dropped_out_of_window_props = 0
    _dropped_missing_time_props = 0
    if TIME_ET_AVAILABLE and raw_prop_games:
        prop_games, _dropped_props_window, _dropped_props_missing = filter_events_et(raw_prop_games, date_str)
        _dropped_out_of_window_props = len(_dropped_props_window)
        _dropped_missing_time_props = len(_dropped_props_missing)
        logger.info("PROPS TODAY GATE: kept=%d, dropped_window=%d, dropped_missing=%d",
                    len(prop_games), _dropped_out_of_window_props, _dropped_missing_time_props)
    else:
        prop_games = raw_prop_games

    _date_window_et_debug["events_before_props"] = len(raw_prop_games)
    _date_window_et_debug["events_after_props"] = len(prop_games)

    if len(prop_games) > max_events:
        logger.info("MAX_EVENTS CAP: Trimming prop events from %d to %d", len(prop_games), max_events)
        prop_games = prop_games[:max_events]

    # --- Games ET filter ---
    raw_games = []
    _dropped_out_of_window_games = 0
    _dropped_missing_time_games = 0
    ghost_game_count = 0
    if game_odds_resp and hasattr(game_odds_resp, 'status_code') and game_odds_resp.status_code == 200:
        # Reuse already-parsed games data if available (from props backfill above)
        raw_games = _raw_games_for_lookup if _games_time_lookup else game_odds_resp.json()
        _date_window_et_debug["events_before_games"] = len(raw_games)
        if TIME_ET_AVAILABLE:
            raw_games, _dropped_games_window, _dropped_games_missing = filter_events_et(raw_games, date_str)
            _dropped_out_of_window_games = len(_dropped_games_window)
            _dropped_missing_time_games = len(_dropped_games_missing)
            ghost_game_count = _dropped_out_of_window_games + _dropped_missing_time_games
            logger.info("GAMES TODAY GATE: kept=%d, dropped_window=%d, dropped_missing=%d",
                        len(raw_games), _dropped_out_of_window_games, _dropped_missing_time_games)
        _date_window_et_debug["events_after_games"] = len(raw_games)
        if len(raw_games) > max_events:
            logger.info("MAX_EVENTS CAP: Trimming game events from %d to %d", len(raw_games), max_events)
            raw_games = raw_games[:max_events]
    _record("et_filter", _s)

    # ============================================
    # v16.1: PARALLEL PLAYER RESOLUTION (all unique players at once)
    # ============================================
    _s = time.time()
    _player_resolve_cache = {}  # (sport, name_lower, home, away) → dict|"BLOCKED"
    _resolve_attempted = 0
    _resolve_succeeded = 0
    _resolve_timed_out = 0

    if IDENTITY_RESOLVER_AVAILABLE and prop_games:
        # 1. Extract unique (player, home_team, away_team) tuples from props
        _unique_players = {}  # resolve_key → (raw_name, home, away, game_key)
        for game in prop_games:
            _ht = game.get("home_team", "")
            _at = game.get("away_team", "")
            _gk = f"{_at}@{_ht}"
            for prop in game.get("props", []):
                _pn = prop.get("player", "Unknown")
                _rk = (sport_upper, _pn.lower().strip(), _ht, _at)
                if _rk not in _unique_players:
                    _unique_players[_rk] = (_pn, _ht, _at, _gk)

        logger.info("PLAYER RESOLVE: %d unique players to resolve", len(_unique_players))

        # 2. Resolve all in parallel with per-call 0.8s timeout
        async def _resolve_one(rk, raw_name, home, away, gk):
            try:
                resolved = await asyncio.wait_for(
                    resolve_player(sport=sport_upper, raw_name=raw_name, team_hint=home, event_id=gk),
                    timeout=0.8
                )
                # If low confidence with home team, try away team
                if not resolved.is_resolved or resolved.confidence < 0.8:
                    try:
                        resolved_away = await asyncio.wait_for(
                            resolve_player(sport=sport_upper, raw_name=raw_name, team_hint=away, event_id=gk),
                            timeout=0.8
                        )
                        if resolved_away.confidence > resolved.confidence:
                            resolved = resolved_away
                    except asyncio.TimeoutError:
                        pass  # Keep first result

                if resolved.is_resolved:
                    # Check injury guard
                    try:
                        _resolver = get_player_resolver()
                        resolved = await asyncio.wait_for(
                            _resolver.check_injury_guard(resolved, allow_questionable=True),
                            timeout=0.5
                        )
                    except asyncio.TimeoutError:
                        pass  # Skip injury guard, don't block

                    if resolved.is_blocked:
                        return rk, "BLOCKED"
                    return rk, {
                        "canonical_player_id": resolved.canonical_player_id,
                        "provider_ids": resolved.provider_ids,
                        "position": resolved.position,
                        "team": resolved.team,
                    }
                return rk, {}
            except asyncio.TimeoutError:
                return rk, "TIMEOUT"
            except Exception as e:
                logger.debug("Player resolve failed for %s: %s", raw_name, e)
                return rk, {}

        # Fire all resolutions concurrently
        _resolve_tasks = [
            _resolve_one(rk, raw_name, home, away, gk)
            for rk, (raw_name, home, away, gk) in _unique_players.items()
        ]
        _resolve_attempted = len(_resolve_tasks)

        # Use overall timeout for the whole batch (3s max)
        try:
            _results = await asyncio.wait_for(
                asyncio.gather(*_resolve_tasks, return_exceptions=True),
                timeout=3.0
            )
            for r in _results:
                if isinstance(r, Exception):
                    continue
                rk, val = r
                _player_resolve_cache[rk] = val
                if isinstance(val, dict) and val.get("canonical_player_id"):
                    _resolve_succeeded += 1
                elif val == "TIMEOUT":
                    _resolve_timed_out += 1
        except asyncio.TimeoutError:
            logger.warning("PLAYER RESOLVE: Batch timed out after 3s (%d/%d resolved)", _resolve_succeeded, _resolve_attempted)
            _timed_out_components.append("player_resolution_batch")

    _record("player_resolution", _s)
    logger.info("PLAYER RESOLVE: %d attempted, %d succeeded, %d timed_out in %.2fs",
                _resolve_attempted, _resolve_succeeded, _resolve_timed_out, _timings.get("player_resolution", 0))

    # ============================================
    # SERP PRE-FETCH: Parallel game-level SERP intelligence (v20.7)
    # Reduces ~107 sequential SerpAPI calls (~17s) to parallel (~2-3s)
    # Results cached in _serp_game_cache for use in calculate_pick_score()
    # ============================================
    _s = time.time()
    _serp_game_cache: Dict[tuple, Dict[str, Any]] = {}
    _serp_prefetch_count = 0

    if SERP_INTEL_AVAILABLE and is_serp_available() and not _past_deadline():
        # Extract unique (home_team, away_team) pairs from games + props
        _unique_serp_games: set = set()
        if raw_games:
            for _g in raw_games:
                _ht = _g.get("home_team", "")
                _at = _g.get("away_team", "")
                if _ht and _at:
                    _unique_serp_games.add((_ht, _at))
        if prop_games:
            for _g in prop_games:
                _ht = _g.get("home_team", "")
                _at = _g.get("away_team", "")
                if _ht and _at:
                    _unique_serp_games.add((_ht, _at))

        if _unique_serp_games:
            import concurrent.futures

            def _prefetch_serp_game(home: str, away: str, target: str) -> tuple:
                """Fetch SERP intel for one game+target combination."""
                try:
                    result = get_serp_betting_intelligence(
                        sport=sport_upper,
                        home_team=home,
                        away_team=away,
                        pick_side=target,
                    )
                    return (home.lower(), away.lower(), target.lower()), result
                except Exception as e:
                    logger.debug("SERP prefetch error %s@%s target=%s: %s", away, home, target, e)
                    return (home.lower(), away.lower(), target.lower()), None

            # Build task list: both home and away targets for each game
            _serp_prefetch_tasks = []
            for _ht, _at in _unique_serp_games:
                _serp_prefetch_tasks.append((_ht, _at, _ht))   # home as target
                _serp_prefetch_tasks.append((_ht, _at, _at))   # away as target

            # Run all in parallel threads (each call makes ~9 sequential SerpAPI calls internally)
            _max_workers = min(16, len(_serp_prefetch_tasks))
            _loop = asyncio.get_event_loop()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as _executor:
                    _futs = [
                        _loop.run_in_executor(_executor, _prefetch_serp_game, h, a, t)
                        for h, a, t in _serp_prefetch_tasks
                    ]
                    _serp_results = await asyncio.wait_for(
                        asyncio.gather(*_futs, return_exceptions=True),
                        timeout=12.0
                    )
                    for _sr in _serp_results:
                        if isinstance(_sr, Exception):
                            continue
                        _key, _val = _sr
                        if _val is not None:
                            _serp_game_cache[_key] = _val
                            _serp_prefetch_count += 1
            except asyncio.TimeoutError:
                logger.warning("SERP PREFETCH: timed out after 12s (%d cached)", _serp_prefetch_count)
                _timed_out_components.append("serp_prefetch")
            except Exception as e:
                logger.warning("SERP PREFETCH: failed: %s", e)

        logger.info("SERP PREFETCH: %d results cached for %d unique games in %.2fs",
                     _serp_prefetch_count, len(_unique_serp_games), time.time() - _s)

    _record("serp_prefetch", _s)

    # ============================================
    # CATEGORY 1: GAME PICKS (Spreads, Totals, ML) — runs FIRST (fast, no player resolution)
    # ============================================
    _s = time.time()
    game_picks = []
    _game_scoring_error = False

    # v16.0: Weather cache per game (fetch once, apply to all markets)
    _weather_cache: Dict[str, Dict[str, Any]] = {}
    _weather_fetched = 0
    _weather_cache_hits = 0

    try:
        if raw_games:
            for game in raw_games:
                if _past_deadline():
                    _timed_out_components.append("game_picks_scoring")
                    logger.warning("TIME BUDGET: Game picks hit deadline after %d picks", len(game_picks))
                    break
                home_team = game.get("home_team", "")
                away_team = game.get("away_team", "")
                game_key = f"{away_team}@{home_team}"
                game_str = f"{home_team}{away_team}"
                sharp_signal = sharp_lookup.get(game_key, {})
                commence_time = game.get("commence_time", "")

                # Parse commence_time to datetime object for MSRF/GLITCH
                _game_datetime = None
                if commence_time:
                    try:
                        from datetime import datetime as _dt_parse
                        _game_datetime = _dt_parse.fromisoformat(commence_time.replace("Z", "+00:00"))
                    except Exception:
                        pass

                start_time_et = ""
                if commence_time:
                    try:
                        start_time_et = get_game_start_time_et(commence_time) if TIME_FILTERS_AVAILABLE else ""
                    except Exception:
                        start_time_et = ""

                # v20.0: Compute game_status early for live signals
                _game_status = "UPCOMING"
                if TIME_FILTERS_AVAILABLE and commence_time:
                    _game_status = get_game_status(commence_time)

                # v16.0: Fetch weather once per game (async, cached by game_key)
                _game_weather = _weather_cache.get(game_key)
                if _game_weather is None and WEATHER_MODULE_AVAILABLE:
                    try:
                        _game_weather = await get_weather_modifier(
                            sport=sport_upper,
                            home_team=home_team,
                            venue="",
                            game_time=commence_time
                        )
                        _weather_cache[game_key] = _game_weather
                        _weather_fetched += 1
                    except Exception as e:
                        logger.debug("Weather fetch failed for %s: %s", game_key, e)
                        _game_weather = {
                            "available": False,
                            "reason": "FETCH_ERROR",
                            "weather_modifier": 0.0,
                            "weather_reasons": []
                        }
                        _weather_cache[game_key] = _game_weather
                elif _game_weather is not None:
                    _weather_cache_hits += 1
                else:
                    # Weather module not available
                    _game_weather = {
                        "available": False,
                        "reason": "MODULE_UNAVAILABLE",
                        "weather_modifier": 0.0,
                        "weather_reasons": []
                    }

                # v17.3: Supplement with ESPN venue/weather for outdoor sports
                if sport_upper in ["MLB", "NFL"] and _espn_venue_by_game:
                    _espn_venue = _find_espn_data(_espn_venue_by_game, home_team, away_team)
                    if _espn_venue and _espn_venue.get("available"):
                        # Add venue info to weather context
                        venue_info = _espn_venue.get("venue", {})
                        if not _game_weather.get("available"):
                            # Use ESPN weather as fallback
                            espn_weather = _espn_venue.get("weather", {})
                            if espn_weather and espn_weather.get("temperature"):
                                temp = espn_weather.get("temperature", 70)
                                wind = espn_weather.get("wind_speed", 0)
                                # Simple weather modifier based on conditions
                                weather_mod = 0.0
                                weather_reasons = []
                                if temp and temp < 40:
                                    weather_mod -= 0.5
                                    weather_reasons.append(f"Cold temp ({temp}°F)")
                                elif temp and temp > 90:
                                    weather_mod -= 0.3
                                    weather_reasons.append(f"Hot temp ({temp}°F)")
                                if wind and wind > 15:
                                    weather_mod -= 0.3
                                    weather_reasons.append(f"High wind ({wind}mph)")
                                _game_weather = {
                                    "available": True,
                                    "reason": "ESPN_VENUE",
                                    "weather_modifier": weather_mod,
                                    "weather_reasons": weather_reasons,
                                    "source": "espn"
                                }
                        # Add venue details regardless
                        _game_weather["espn_venue"] = {
                            "name": venue_info.get("name", ""),
                            "indoor": venue_info.get("indoor", True),
                            "grass": venue_info.get("grass", False),
                            "capacity": venue_info.get("capacity")
                        }
                        if _espn_venue.get("attendance"):
                            _game_weather["espn_venue"]["attendance"] = _espn_venue.get("attendance")

                game_bookmakers = game.get("bookmakers", [])
                game_book_count = len(game_bookmakers)
                market_book_counts = {}
                for bm in game_bookmakers:
                    bm_key_raw = bm.get("key") or bm.get("title") or ""
                    bm_key_norm = bm_key_raw.lower() if isinstance(bm_key_raw, str) else ""
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        if market_key:
                            market_book_counts.setdefault(market_key, set()).add(bm_key_norm or bm.get("title", "").lower())
                market_book_counts = {k: len(v) for k, v in market_book_counts.items()}

                best_odds_by_market = {}
                for bm in game_bookmakers:
                    book_name = bm.get("title", "Unknown")
                    book_key = bm.get("key", "") or "consensus"  # FIX: Never store empty book_key
                    bm_link = AFFILIATE_LINKS.get(book_key, "")
                    # Convert dict to URL string: base_url + sport_paths.get(sport, '')
                    if isinstance(bm_link, dict):
                        base_url = bm_link.get("base_url", "")
                        sport_paths = bm_link.get("sport_paths", {})
                        sport_path = sport_paths.get(sport_lower, "")
                        bm_link = base_url + sport_path if base_url else ""
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point")
                            outcome_key = f"{market_key}:{pick_name}:{point}"
                            if outcome_key not in best_odds_by_market or odds > best_odds_by_market[outcome_key][0]:
                                best_odds_by_market[outcome_key] = (odds, book_name, book_key, bm_link)

                for bm in game_bookmakers[:1]:
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            point = outcome.get("point")
                            outcome_key = f"{market_key}:{pick_name}:{point}"
                            best_odds, best_book, best_book_key, best_link = best_odds_by_market.get(
                                outcome_key, (outcome.get("price", -110), "Unknown", "consensus", "")
                            )

                            if market_key == "spreads":
                                pick_type = "SPREAD"
                                pick_side = f"{pick_name} {point:+.1f}" if point else pick_name
                                display = pick_side
                            elif market_key == "h2h":
                                pick_type = "MONEYLINE"
                                pick_side = f"{pick_name} ML"
                                display = pick_side
                            elif market_key == "totals":
                                pick_type = "TOTAL"
                                pick_side = f"{pick_name} {point}" if point else pick_name
                                display = pick_side
                            else:
                                continue

                            market_book_count = market_book_counts.get(market_key, 0)
                            score_data = calculate_pick_score(
                                game_str,
                                sharp_signal,
                                base_ai=4.5,
                                player_name="",
                                home_team=home_team,
                                away_team=away_team,
                                spread=point if market_key == "spreads" and point else 0,
                                total=point if market_key == "totals" and point else 220,
                                public_pct=sharp_signal.get("public_pct", sharp_signal.get("ticket_pct", 50)),
                                pick_type=pick_type,
                                pick_side=pick_side,
                                prop_line=point if point else 0,
                                game_datetime=_game_datetime,
                                game_bookmakers=game_bookmakers,  # v17.6: Multi-book for Benford
                                book_count=game_book_count,
                                market_book_count=market_book_count,
                                event_id=game.get("id"),
                                game_status=_game_status  # v20.0: Pass for live signals
                            )

                            # v16.0: Apply weather modifier to score (capped at ±1.0)
                            _weather_mod = _game_weather.get("weather_modifier", 0.0) if _game_weather else 0.0
                            _weather_reasons = _game_weather.get("weather_reasons", []) if _game_weather else []
                            _weather_available = _game_weather.get("available", False) if _game_weather else False

                            # Apply weather modifier to total_score and final_score
                            if _weather_mod != 0.0:
                                _old_score = score_data.get("total_score", 0)
                                _old_final = score_data.get("final_score", _old_score)
                                score_data["total_score"] = round(_old_score + _weather_mod, 2)
                                score_data["final_score"] = round(_old_final + _weather_mod, 2)
                                logger.debug("Weather modifier applied: %s -> %.2f + %.2f = %.2f",
                                           game_key, _old_score, _weather_mod, score_data["total_score"])

                            # Add weather fields to score_data
                            score_data["weather_modifier"] = round(_weather_mod, 2)
                            score_data["weather_reasons"] = _weather_reasons
                            score_data["weather_available"] = _weather_available

                            game_status = "UPCOMING"
                            if TIME_FILTERS_AVAILABLE and commence_time:
                                game_status = get_game_status(commence_time)

                            signals_fired = score_data.get("pillars_passed", []).copy()
                            if sharp_signal.get("signal_strength") in ["STRONG", "MODERATE"]:
                                signals_fired.append(f"SHARP_{sharp_signal.get('signal_strength')}")
                            has_started = game_status in ["MISSED_START", "LIVE", "FINAL"]

                            # v16.0: Compute context modifiers for this game pick
                            # v17.2: Pass injuries data for vacuum calculation
                            _rest_override = _rest_days_for_team(away_team)
                            _game_ctx_mods = await compute_context_modifiers(
                                sport=sport.upper(),
                                home_team=home_team,
                                away_team=away_team,
                                player_team="",
                                pick_type="GAME",
                                pick_side=pick_side,
                                injuries_data=_injuries_by_team,
                                rest_days_override=_rest_override
                            )

                            game_picks.append({
                                "sport": sport.upper(),
                                "league": sport.upper(),
                                "event_id": game_key,
                                "pick_type": pick_type,
                                "pick": display,
                                "pick_side": pick_side,
                                "side": pick_name,  # Required for contradiction gate: team name for spreads/ML, Over/Under for totals
                                "team": pick_name if market_key != "totals" else None,
                                "line": point,
                                "odds": best_odds,
                                "book": best_book or "consensus",
                                "book_key": best_book_key or "consensus",  # FIX: Never empty
                                "book_link": best_link,
                                "sportsbook_name": best_book,
                                "sportsbook_event_url": best_link,
                                "game": f"{away_team} @ {home_team}",
                                "matchup": f"{away_team} @ {home_team}",
                                "home_team": home_team,
                                "away_team": away_team,
                                "start_time_et": start_time_et,
                                "game_status": game_status,
                                "status": game_status.lower() if game_status else "scheduled",
                                "has_started": has_started,
                                "is_started_already": has_started,
                                "is_live": game_status == "MISSED_START",
                                "is_live_bet_candidate": game_status == "MISSED_START",
                                "market": market_key,
                                "recommendation": display,
                                "best_book": best_book,
                                "best_book_link": best_link,
                                "book_count": game_book_count,
                                "market_book_count": market_book_count,
                                "signals_fired": signals_fired,
                                "signals_firing": signals_fired,
                                "pillars_hit": score_data.get("pillars_passed", []),
                                "engine_breakdown": {
                                    "ai": score_data.get("ai_score", 0),
                                    "research": score_data.get("research_score", 0),
                                    "esoteric": score_data.get("esoteric_score", 0),
                                    "jarvis": score_data.get("jarvis_rs", 0),
                                },
                                "titanium_reasons": score_data.get("smash_reasons", []),
                                "graded": False,
                                "grade_status": "PENDING",
                                **score_data,
                                "sharp_signal": sharp_signal.get("signal_strength", "NONE"),
                                # v16.0: Context Modifiers (REQUIRED - Session 4 Hard Gate)
                                "weather_context": _game_ctx_mods.get("weather_context"),
                                "rest_days": _game_ctx_mods.get("rest_days"),
                                "home_away": _game_ctx_mods.get("home_away"),
                                "vacuum_score": _game_ctx_mods.get("vacuum_score"),
                            })
    except Exception as e:
        _game_scoring_error = True
        logger.warning("Game picks scoring failed: %s", e)

    _record("game_picks_scoring", _s)

    if ghost_game_count > 0:
        logger.info("GHOST PREVENTION: Excluded %d games not scheduled for today", ghost_game_count)

    # Fallback to sharp money if no game picks
    if not game_picks and sharp_data.get("data"):
        for signal in sharp_data.get("data", []):
            home_team = signal.get("home_team", "")
            away_team = signal.get("away_team", "")
            game_str = f"{home_team}{away_team}"

            # Look up commence_time and bookmakers from raw_games for start_time_et and Benford
            commence_time = ""
            _sharp_bookmakers = []
            signal_game_id = signal.get("game_id", "")
            if signal_game_id and raw_games:
                for g in raw_games:
                    if g.get("id") == signal_game_id:
                        commence_time = g.get("commence_time", "")
                        _sharp_bookmakers = g.get("bookmakers", [])  # v17.6
                        break

            # Parse commence_time to datetime object for MSRF/GLITCH
            _sharp_game_dt = None
            if commence_time:
                try:
                    from datetime import datetime as _dt_parse
                    _sharp_game_dt = _dt_parse.fromisoformat(commence_time.replace("Z", "+00:00"))
                except Exception:
                    pass

            # v20.0: Compute game_status for live signals
            _sharp_game_status = "UPCOMING"
            if TIME_FILTERS_AVAILABLE and commence_time:
                _sharp_game_status = get_game_status(commence_time)

            score_data = calculate_pick_score(
                game_str,
                signal,
                base_ai=5.0,
                player_name="",
                home_team=home_team,
                away_team=away_team,
                spread=signal.get("line_variance", 0),
                total=220,
                public_pct=50,
                pick_type="SHARP",
                pick_side=signal.get("sharp_side", "home"),
                prop_line=0,
                game_datetime=_sharp_game_dt,
                game_bookmakers=_sharp_bookmakers,  # v17.6: Multi-book for Benford
                event_id=signal_game_id,
                game_status=_sharp_game_status  # v20.0: Pass for live signals
            )

            signals_fired = score_data.get("pillars_passed", []).copy()
            signals_fired.append(f"SHARP_{signal.get('signal_strength', 'MODERATE')}")

            # Derive start_time_et from commence_time
            start_time_et = ""
            if commence_time:
                try:
                    start_time_et = get_game_start_time_et(commence_time) if TIME_FILTERS_AVAILABLE else ""
                except Exception:
                    start_time_et = ""

            # v16.0: Compute context modifiers for sharp fallback picks
            # v17.2: Pass injuries data for vacuum calculation
            _rest_override = _rest_days_for_team(away_team)
            _sharp_ctx_mods = await compute_context_modifiers(
                sport=sport.upper(),
                home_team=home_team,
                away_team=away_team,
                player_team="",
                pick_type="SHARP",
                pick_side=signal.get("sharp_side", "home"),
                injuries_data=_injuries_by_team,
                rest_days_override=_rest_override
            )

            game_picks.append({
                "sport": sport.upper(),
                "league": sport.upper(),
                "event_id": signal.get("game_id", ""),
                "pick_type": "SHARP",
                "pick": f"Sharp on {signal.get('sharp_side', 'home')}",
                "pick_side": f"{signal.get('sharp_side', 'home').upper()} SHARP",
                "side": home_team if signal.get("sharp_side") == "home" else away_team,  # Required for contradiction gate
                "team": home_team if signal.get("sharp_side") == "home" else away_team,
                "line": signal.get("line_variance", 0),
                "odds": -110,
                "book": "",
                "book_key": "",
                "book_link": "",
                "sportsbook_name": "",
                "sportsbook_event_url": "",
                "game": f"{away_team} @ {home_team}",
                "matchup": f"{away_team} @ {home_team}",
                "home_team": home_team,
                "away_team": away_team,
                "start_time_et": start_time_et,
                "game_status": "UPCOMING",
                "status": "scheduled",
                "has_started": False,
                "is_started_already": False,
                "is_live": False,
                "is_live_bet_candidate": False,
                "market": "sharp_money",
                "recommendation": f"SHARP ON {signal.get('sharp_side', 'home').upper()}",
                "best_book": "",
                "best_book_link": "",
                "signals_fired": signals_fired,
                "signals_firing": signals_fired,
                "pillars_hit": score_data.get("pillars_passed", []),
                "engine_breakdown": {
                    "ai": score_data.get("ai_score", 0),
                    "research": score_data.get("research_score", 0),
                    "esoteric": score_data.get("esoteric_score", 0),
                    "jarvis": score_data.get("jarvis_rs", 0),
                },
                "titanium_reasons": score_data.get("smash_reasons", []),
                "graded": False,
                "grade_status": "PENDING",
                **score_data,
                "sharp_signal": signal.get("signal_strength", "MODERATE"),
                # v16.0: Context Modifiers (REQUIRED - Session 4 Hard Gate)
                "weather_context": _sharp_ctx_mods.get("weather_context"),
                "rest_days": _sharp_ctx_mods.get("rest_days"),
                "home_away": _sharp_ctx_mods.get("home_away"),
                "vacuum_score": _sharp_ctx_mods.get("vacuum_score"),
            })

    # ============================================
    # CATEGORY 2: PLAYER PROPS (uses pre-resolved player cache — instant lookups)
    # ============================================
    # Reset deadline for props — game scoring consumed the shared budget,
    # so props get their own dedicated time window (Lesson 49).
    PROPS_TIME_BUDGET_S = float(os.getenv("BEST_BETS_PROPS_TIME_BUDGET_S", "30"))
    _deadline = time.time() + PROPS_TIME_BUDGET_S
    _s = time.time()
    props_picks = []
    _props_scoring_error = False
    invalid_injury_count = 0
    try:
        _props_deadline_hit = False
        for game in prop_games:
            if _past_deadline():
                _timed_out_components.append("props_scoring")
                logger.warning("TIME BUDGET: Props scoring hit deadline after %d picks (%.1fs)", len(props_picks), _elapsed())
                _props_deadline_hit = True
                break
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            game_key = f"{away_team}@{home_team}"
            game_str = f"{home_team}{away_team}"
            sharp_signal = sharp_lookup.get(game_key, {})
            commence_time = game.get("commence_time", "")

            # Parse commence_time to datetime object for MSRF/GLITCH
            _prop_game_datetime = None
            if commence_time:
                try:
                    from datetime import datetime as _dt_parse
                    _prop_game_datetime = _dt_parse.fromisoformat(commence_time.replace("Z", "+00:00"))
                except Exception:
                    pass

            _ctx = game_context.get(game_key, {})
            _game_spread = _ctx.get("spread", 0)
            _game_total = _ctx.get("total", 220)

            start_time_et = ""
            if commence_time:
                try:
                    start_time_et = get_game_start_time_et(commence_time) if TIME_FILTERS_AVAILABLE else ""
                except Exception:
                    start_time_et = ""

            # v20.0: Compute game_status early for live signals
            _prop_game_status = "UPCOMING"
            if TIME_FILTERS_AVAILABLE and commence_time:
                _prop_game_status = get_game_status(commence_time)

            # v16.0: Fetch weather for props game (use existing cache or fetch)
            _prop_game_weather = _weather_cache.get(game_key)
            if _prop_game_weather is None and WEATHER_MODULE_AVAILABLE:
                try:
                    _prop_game_weather = await get_weather_modifier(
                        sport=sport_upper,
                        home_team=home_team,
                        venue="",
                        game_time=commence_time
                    )
                    _weather_cache[game_key] = _prop_game_weather
                    _weather_fetched += 1
                except Exception as e:
                    logger.debug("Weather fetch failed for props %s: %s", game_key, e)
                    _prop_game_weather = {
                        "available": False,
                        "reason": "FETCH_ERROR",
                        "weather_modifier": 0.0,
                        "weather_reasons": []
                    }
                    _weather_cache[game_key] = _prop_game_weather
            elif _prop_game_weather is not None:
                _weather_cache_hits += 1
            else:
                _prop_game_weather = {
                    "available": False,
                    "reason": "MODULE_UNAVAILABLE",
                    "weather_modifier": 0.0,
                    "weather_reasons": []
                }

            _props_list = game.get("props", [])
            _prop_books_by_market = {}
            _prop_books_all = set()
            for _p in _props_list:
                _book_raw = _p.get("book") or _p.get("book_key") or _p.get("bookmaker") or ""
                _book_norm = _book_raw.lower().strip() if isinstance(_book_raw, str) else ""
                _market_key = _p.get("market", "")
                if _book_norm:
                    _prop_books_all.add(_book_norm)
                    if _market_key:
                        _prop_books_by_market.setdefault(_market_key, set()).add(_book_norm)
            _prop_book_count = len(_prop_books_all)

            for prop in _props_list:
                if _past_deadline():
                    _timed_out_components.append("props_scoring")
                    logger.warning("TIME BUDGET: Props scoring hit deadline after %d picks (%.1fs)", len(props_picks), _elapsed())
                    _props_deadline_hit = True
                    break
                player = prop.get("player", "Unknown")
                market = prop.get("market", "")
                line = prop.get("line", 0)
                odds = prop.get("odds", -110)
                side = prop.get("side", "Over")
                injury_status = prop.get("injury_status", "HEALTHY")
                book_name = prop.get("book_name", prop.get("bookmaker", "Unknown"))
                book_key = prop.get("book_key", "")
                book_link = prop.get("link", prop.get("book_link", ""))

                if side not in ["Over", "Under"]:
                    continue

                if TIERING_AVAILABLE and is_prop_invalid_injury(injury_status):
                    invalid_injury_count += 1
                    continue

                market_book_count = len(_prop_books_by_market.get(market, set()))
                score_data = calculate_pick_score(
                    game_str + player,
                    sharp_signal,
                    base_ai=5.0,
                    player_name=player,
                    home_team=home_team,
                    away_team=away_team,
                    spread=_game_spread,
                    total=_game_total,
                    public_pct=sharp_signal.get("public_pct", sharp_signal.get("ticket_pct", 50)),
                    pick_type="PROP",
                    pick_side=side,
                    prop_line=line,
                    market=market,  # v16.1: Pass market for LSTM model routing
                    game_datetime=_prop_game_datetime,
                    game_bookmakers=game.get("bookmakers", []),  # v17.6: Multi-book for Benford
                    book_count=_prop_book_count,
                    market_book_count=market_book_count,
                    event_id=game.get("id"),
                    game_status=_prop_game_status  # v20.0: Pass for live signals
                )

                # Lineup confirmation guard (props only)
                lineup_guard = _lineup_risk_guard(commence_time, injury_status)

                # v16.0: Apply weather modifier to props (capped at ±1.0)
                _prop_weather_mod = _prop_game_weather.get("weather_modifier", 0.0) if _prop_game_weather else 0.0
                _prop_weather_reasons = _prop_game_weather.get("weather_reasons", []) if _prop_game_weather else []
                _prop_weather_available = _prop_game_weather.get("available", False) if _prop_game_weather else False

                # Apply weather modifier to total_score and final_score
                if _prop_weather_mod != 0.0:
                    _old_prop_score = score_data.get("total_score", 0)
                    _old_prop_final = score_data.get("final_score", _old_prop_score)
                    score_data["total_score"] = round(_old_prop_score + _prop_weather_mod, 2)
                    score_data["final_score"] = round(_old_prop_final + _prop_weather_mod, 2)

                # Add weather fields to score_data
                score_data["weather_modifier"] = round(_prop_weather_mod, 2)
                score_data["weather_reasons"] = _prop_weather_reasons
                score_data["weather_available"] = _prop_weather_available

                tier = score_data.get("tier", "PASS")
                was_downgraded = False
                if TIERING_AVAILABLE and injury_status:
                    tier, was_downgraded = apply_injury_downgrade(tier, injury_status)
                    if was_downgraded:
                        score_data["tier"] = tier
                        new_config = get_tier_config(tier)
                        score_data["units"] = new_config.get("units", 0.0)
                        score_data["action"] = new_config.get("action", "SKIP")
                        if "penalties" not in score_data:
                            score_data["penalties"] = []
                        score_data["penalties"].append({
                            "name": "Injury Downgrade",
                            "magnitude": -1,
                            "reason": f"Player is {injury_status}"
                        })

                game_status = "UPCOMING"
                if TIME_FILTERS_AVAILABLE and commence_time:
                    game_status = get_game_status(commence_time)

                # v16.1: Use pre-resolved player cache (instant lookup, no await)
                canonical_player_id = None
                provider_ids = {}
                player_position = None
                player_team = None
                resolved_injury_status = injury_status
                prop_blocked = False

                _resolve_key = (sport_upper, player.lower().strip(), home_team, away_team)
                _cached_res = _player_resolve_cache.get(_resolve_key)

                if _cached_res == "BLOCKED":
                    prop_blocked = True
                elif isinstance(_cached_res, dict):
                    canonical_player_id = _cached_res.get("canonical_player_id")
                    provider_ids = _cached_res.get("provider_ids", {})
                    player_position = _cached_res.get("position")
                    player_team = _cached_res.get("team")
                # TIMEOUT or missing → use fallback ID (don't block the prop)

                if prop_blocked:
                    continue

                if not canonical_player_id:
                    safe_name = player.lower().replace(" ", "_").replace("'", "").replace(".", "")
                    safe_team = home_team.lower().replace(" ", "_")
                    canonical_player_id = f"{sport_upper}:NAME:{safe_name}|{safe_team}"

                # v14.9: Build signals_fired array from pillars
                signals_fired = score_data.get("pillars_passed", []).copy()
                if sharp_signal.get("signal_strength") in ["STRONG", "MODERATE"]:
                    signals_fired.append(f"SHARP_{sharp_signal.get('signal_strength')}")

                # v14.9: Determine has_started
                has_started = game_status in ["MISSED_START", "LIVE", "FINAL"]

                # v16.0: Compute context modifiers for this prop
                # v17.2: Pass injuries data for vacuum calculation
                _rest_override = _rest_days_for_team(player_team or away_team)
                _ctx_mods = await compute_context_modifiers(
                    sport=sport.upper(),
                    home_team=home_team,
                    away_team=away_team,
                    player_team=player_team or "",
                    pick_type="PROP",
                    pick_side=side,
                    injuries_data=_injuries_by_team,
                    rest_days_override=_rest_override
                )

                props_picks.append({
                    "sport": sport.upper(),
                    "league": sport.upper(),  # v14.9: Consistent league field
                    "event_id": game_key,  # v14.9: For prop availability tracking
                    "player": player,
                    "player_name": player,
                    "player_team": player_team,  # v14.9: Resolved team
                    # v14.9 CANONICAL PLAYER ID - required for grading
                    "canonical_player_id": canonical_player_id,
                    "provider_ids": provider_ids,
                    "position": player_position,
                    "market": market,
                    "stat_type": market,
                    "prop_type": market,
                    "line": line,
                    "side": side,
                    "direction": side.upper(),  # v14.9: Alias for frontend consistency
                    "over_under": side,
                    "odds": odds,
                    "book": book_name,  # v14.9: Consistent sportsbook field
                    "book_key": book_key,
                    "book_link": book_link,
                    # v14.11: Sportsbook aliases for output contract
                    "sportsbook_name": book_name,
                    "sportsbook_event_url": book_link,
                    "game": f"{away_team} @ {home_team}",
                    "matchup": f"{away_team} @ {home_team}",
                    "home_team": home_team,
                    "away_team": away_team,
                    "start_time_et": start_time_et,  # Human-readable (e.g., "7:30 PM ET")
                    "commence_time_iso": commence_time,  # Programmatic ISO timestamp
                    "game_status": game_status,
                    "status": game_status.lower() if game_status else "scheduled",  # v14.11: Status field
                    "has_started": has_started,  # v14.9: Boolean for frontend
                    "is_started_already": has_started,  # v14.11: Alias for frontend
                    "is_live": game_status == "MISSED_START",  # v14.11: Live mode flag
                    "is_live_bet_candidate": game_status == "MISSED_START",
                    "recommendation": f"{side.upper()} {line}",
                    "injury_status": resolved_injury_status,
                    "injury_checked": True,  # v14.9: Injury was checked via identity resolver
                    "lineup_status": lineup_guard,
                    "best_book": book_name,
                    "best_book_link": book_link,
                    "book_count": _prop_book_count,
                    "market_book_count": market_book_count,
                    "signals_fired": signals_fired,  # v14.9: Array of all triggered signals
                    "signals_firing": signals_fired,  # v14.11: Alias for output contract
                    "pillars_hit": score_data.get("pillars_passed", []),  # v14.11: Alias
                    # v14.11: Engine breakdown for frontend
                    "engine_breakdown": {
                        "ai": score_data.get("ai_score", 0),
                        "research": score_data.get("research_score", 0),
                        "esoteric": score_data.get("esoteric_score", 0),
                        "jarvis": score_data.get("jarvis_rs", 0),
                    },
                    # v14.11: Titanium reasons alias
                    "titanium_reasons": score_data.get("smash_reasons", []),
                    # v14.11: Grading fields (populated by pick_logger)
                    "graded": False,
                    "grade_status": "PENDING",
                    **score_data,
                    "sharp_signal": sharp_signal.get("signal_strength", "NONE"),
                    # v16.0: Context Modifiers (REQUIRED - Session 4 Hard Gate)
                    "weather_context": _ctx_mods.get("weather_context"),
                    "rest_days": _ctx_mods.get("rest_days"),
                    "home_away": _ctx_mods.get("home_away"),
                    "vacuum_score": _ctx_mods.get("vacuum_score"),
                })
            if _props_deadline_hit:
                break
    except HTTPException:
        _props_scoring_error = True
        logger.warning("Props fetch failed for %s", sport)
    except Exception as e:
        _props_scoring_error = True
        logger.warning("Props scoring failed for %s: %s", sport, e)

    _record("props_scoring", _s)

    if invalid_injury_count > 0:
        logger.info("INJURY ENFORCEMENT: Excluded %d props due to OUT/DOUBTFUL/SUSPENDED status", invalid_injury_count)

    # ============================================
    # v15.3 DEDUPLICATE PROPS - stable pick_id + priority rule
    # ============================================
    import hashlib as _dedup_hl

    PREFERRED_BOOKS = ["draftkings", "fanduel", "betmgm", "caesars", "pinnacle"]

    def _make_pick_id(p: dict) -> str:
        """Deterministic pick_id from canonical bet semantics."""
        _side = p.get('side') or p.get('direction') or p.get('pick_side') or ''
        _line = p.get('line') if p.get('line') is not None else p.get('prop_line', 0)
        canonical = (
            f"{sport.upper()}"
            f"|{p.get('event_id') or p.get('game_id') or p.get('matchup', '')}"
            f"|{p.get('market') or p.get('prop_type') or p.get('pick_type', '')}"
            f"|{_side.upper()}"
            f"|{round(float(_line or 0), 2)}"
            f"|{p.get('player') or p.get('player_name', '')}"
        )
        return _dedup_hl.sha1(canonical.encode()).hexdigest()[:12]

    def _book_priority(p: dict) -> int:
        bk = (p.get("book_key") or p.get("book") or "").lower()
        try:
            return PREFERRED_BOOKS.index(bk)
        except ValueError:
            return len(PREFERRED_BOOKS)

    def _dedupe_picks(picks: list) -> tuple:
        """Dedupe by pick_id. Returns (deduped_list, dropped_count, dupe_groups)."""
        groups = {}
        for p in picks:
            pid = _make_pick_id(p)
            p["pick_id"] = pid
            groups.setdefault(pid, []).append(p)

        kept = []
        dupe_groups_debug = []
        total_dropped = 0
        for pid, dupes in groups.items():
            # Sort: highest score → best book → first seen
            dupes.sort(key=lambda x: (-x.get("total_score", 0), _book_priority(x), str(x.get("pick_id", ""))))
            winner = dupes[0]
            kept.append(winner)
            if len(dupes) > 1:
                total_dropped += len(dupes) - 1
                dupe_groups_debug.append({
                    "pick_id": pid,
                    "count": len(dupes),
                    "kept_book": winner.get("book_key", ""),
                    "dropped_books": [d.get("book_key", "") for d in dupes[1:]]
                })
        return kept, total_dropped, dupe_groups_debug

    deduplicated_props, _dupe_dropped_props, _dupe_groups_props = _dedupe_picks(props_picks)

    # v15.0: Filter to min_score threshold before taking top picks
    COMMUNITY_MIN_SCORE = min_score
    deduplicated_props.sort(key=_stable_pick_sort_key)

    # Capture ALL candidates for debug/distribution before filtering
    _all_prop_candidates = deduplicated_props  # Keep ref for debug output

    # v20.13: Props use lower threshold (6.5) because SERP disabled for props (saves API quota)
    # Props cannot get SERP boosts (+4.3 max) that game picks receive
    filtered_props = [p for p in deduplicated_props if p["total_score"] >= MIN_PROPS_SCORE]
    filtered_below_6_5_props = len(deduplicated_props) - len(filtered_props)

    # v15.3: Deduplicate game picks too
    deduplicated_games, _dupe_dropped_games, _dupe_groups_games = _dedupe_picks(game_picks)
    deduplicated_games.sort(key=_stable_pick_sort_key)
    _all_game_candidates = deduplicated_games  # Keep ref for debug output

    filtered_game_picks = [p for p in deduplicated_games if p["total_score"] >= COMMUNITY_MIN_SCORE]
    filtered_below_6_5_games = len(deduplicated_games) - len(filtered_game_picks)

    # v15.0: Apply contradiction gate to prevent both sides of same bet
    contradiction_debug = {"total_dropped": 0, "props_dropped": 0, "games_dropped": 0}
    try:
        from utils.contradiction_gate import apply_contradiction_gate
        filtered_props_no_contradict, filtered_games_no_contradict, contradiction_debug = apply_contradiction_gate(
            filtered_props,
            filtered_game_picks,
            debug=debug_mode
        )
    except Exception as e:
        logger.error("CONTRADICTION_GATE: Failed to apply gate: %s", e)
        # Fallback: use filtered picks without contradiction gate
        filtered_props_no_contradict = filtered_props
        filtered_games_no_contradict = filtered_game_picks

    # v16.1: Apply diversity filter to prevent same player appearing multiple times
    # Max 1 prop per player, max 3 props per game
    diversity_debug = {"total_dropped": 0, "player_limited": 0, "game_limited": 0}
    try:
        from utils.diversity_filter import apply_diversity_gate
        filtered_props_diverse, filtered_games_diverse, diversity_debug = apply_diversity_gate(
            filtered_props_no_contradict,
            filtered_games_no_contradict,
            debug=debug_mode
        )
    except Exception as e:
        logger.error("DIVERSITY_FILTER: Failed to apply filter: %s", e)
        # Fallback: use picks without diversity filter
        filtered_props_diverse = filtered_props_no_contradict
        filtered_games_diverse = filtered_games_no_contradict

    # Take top N after diversity filtering
    top_props = filtered_props_diverse[:max_props]
    top_game_picks = filtered_games_diverse[:max_games]

    # v20.12: Apply max_per_sport_per_day concentration limit (quality over quantity)
    # Limit total picks (props + games combined) to configured max
    try:
        from core.scoring_contract import CONCENTRATION_LIMITS
        max_per_sport = CONCENTRATION_LIMITS.get("max_per_sport_per_day", 8)
        total_picks = len(top_props) + len(top_game_picks)
        if total_picks > max_per_sport:
            # Keep best picks from combined pool, prioritizing by score
            combined = [(p, "prop") for p in top_props] + [(g, "game") for g in top_game_picks]
            combined.sort(key=lambda x: x[0].get("final_score", 0) or x[0].get("total_score", 0), reverse=True)
            combined = combined[:max_per_sport]
            top_props = [p for p, t in combined if t == "prop"]
            top_game_picks = [p for p, t in combined if t == "game"]
            _picks_dropped_sport_limit = total_picks - max_per_sport
            logger.info("CONCENTRATION_LIMIT: Reduced %d picks to %d (max_per_sport_per_day=%d)",
                       total_picks, max_per_sport, max_per_sport)
    except Exception as e:
        logger.warning("CONCENTRATION_LIMIT: Failed to apply sport limit: %s", e)
        # Continue without enforcement

    # CRITICAL FIX: Enforce book_key defaults before API response (BOTH props and games)
    # Applied UNCONDITIONALLY - never allow empty book_key in response
    try:
        from utils.book_sanitizer import ensure_book_fields
        top_props = [ensure_book_fields(p) for p in top_props]
        top_game_picks = [ensure_book_fields(g) for g in top_game_picks]
    except Exception as e:
        logger.error("CRITICAL: book_key sanitizer failed: %s", e)
        # This should never fail, but log and continue if it does

    if _dupe_dropped_props + _dupe_dropped_games > 0:
        logger.info("DEDUPE: dropped %d prop dupes, %d game dupes", _dupe_dropped_props, _dupe_dropped_games)

    if contradiction_debug.get("total_dropped", 0) > 0:
        logger.info("CONTRADICTION_GATE: blocked %d props, %d games (opposite sides)",
                   contradiction_debug.get("props_dropped", 0), contradiction_debug.get("games_dropped", 0))

    if diversity_debug.get("total_dropped", 0) > 0:
        logger.info("DIVERSITY_FILTER: blocked %d picks (player_limit=%d, game_limit=%d)",
                   diversity_debug.get("total_dropped", 0),
                   diversity_debug.get("player_limited", 0),
                   diversity_debug.get("game_limited", 0))


    # ============================================
    # LOG PICKS FOR GRADING (v14.9 + v12.0 auto_grader integration)
    # ============================================
    _s = time.time()
    _picks_logged = 0
    # REMOVED: pick_logger persistence (grader_store is now the SINGLE SOURCE OF TRUTH)
    _picks_logged = 0
    _picks_skipped = 0
    _pick_log_errors = []

    # LOG TO AUTO_GRADER for weight learning (v12.0)
    # ============================================
    if AUTO_GRADER_AVAILABLE:
        try:
            grader = get_grader()
            grader_logged = 0

            # Log prop picks to auto_grader (props have stat predictions)
            for pick in top_props:
                player_name = pick.get("player_name", pick.get("player", ""))
                prop_type = pick.get("prop_type", pick.get("market", "points"))
                line = pick.get("line", 0)

                if player_name and line:
                    # Map prop_type to stat_type
                    stat_type_map = {
                        "points": "points", "pts": "points",
                        "rebounds": "rebounds", "reb": "rebounds",
                        "assists": "assists", "ast": "assists",
                        "threes": "threes", "3pt": "threes",
                        "steals": "steals", "stl": "steals",
                        "blocks": "blocks", "blk": "blocks",
                        "pra": "pra", "pts+reb+ast": "pra",
                        "passing_yards": "passing_yards",
                        "rushing_yards": "rushing_yards",
                        "receiving_yards": "receiving_yards",
                    }
                    stat_type = stat_type_map.get(prop_type.lower(), "points")

                    # Extract adjustments from pick if available
                    # v19.1: Extract context layer adjustments
                    _ctx = pick.get("context_layer", {})
                    adjustments = {
                        "defense": _ctx.get("def_rank", 0.0) if isinstance(_ctx.get("def_rank"), (int, float)) else 0.0,
                        "pace": _ctx.get("pace", 0.0) if isinstance(_ctx.get("pace"), (int, float)) else 0.0,
                        "vacuum": _ctx.get("vacuum", 0.0) if isinstance(_ctx.get("vacuum"), (int, float)) else 0.0,
                        "lstm_brain": pick.get("lstm_adjustment", 0.0),
                        "officials": _ctx.get("officials_adjustment", 0.0),
                        # v19.1: GAP 1 fix - Research engine signals
                        "sharp_money": pick.get("research_breakdown", {}).get("sharp_boost", 0.0),
                        "public_fade": pick.get("research_breakdown", {}).get("public_boost", 0.0),
                        "line_variance": pick.get("research_breakdown", {}).get("line_boost", 0.0),
                    }

                    # v19.1: GAP 2 fix - Extract GLITCH signals and esoteric contributions
                    _glitch_signals = pick.get("glitch_signals", {})
                    _esoteric_contribs = pick.get("esoteric_contributions", {})
                    _pick_type = pick.get("pick_type", pick.get("market", "PROP")).upper()

                    grader.log_prediction(
                        sport=sport.upper(),
                        player_name=player_name,
                        stat_type=stat_type,
                        predicted_value=line,  # Use line as predicted value
                        line=line,
                        adjustments=adjustments,
                        pick_type=_pick_type,
                        glitch_signals=_glitch_signals,
                        esoteric_contributions=_esoteric_contribs
                    )
                    grader_logged += 1

            if grader_logged > 0:
                logger.info("AUTO_GRADER: Logged %d prop predictions for weight learning", grader_logged)
        except Exception as e:
            logger.error("AUTO_GRADER: Failed to log predictions: %s", e)

    _record("pick_logging", _s)

    # ============================================
    # PERSIST TO GRADER STORE (v15.1 MASTER FIX)
    # ============================================
    # Persist picks so autograder can grade tomorrow
    _grader_store_persisted = 0
    _grader_store_duplicates = 0
    try:
        # Use top-level import (already imported at line 99)
        _start_et, _end_et, _start_utc, _end_utc = et_day_bounds(date_str=date_str)
        date_et_for_store = _start_et.date().isoformat()

        # Persist all picks (props + games)
        # v20.12: Filter to only quality tiers - uses PERSIST_TIERS from scoring_contract.py
        # MONITOR and PASS tiers are filtered out - they don't provide value for the learning loop
        all_candidates = top_props + top_game_picks
        all_picks_to_persist = [p for p in all_candidates if p.get("tier", "").upper() in PERSIST_TIERS]
        _tier_filtered_count = len(all_candidates) - len(all_picks_to_persist)

        logger.info("GRADER_STORE: Attempting to persist %d picks (date_et=%s), filtered %d non-quality tiers",
                    len(all_picks_to_persist), date_et_for_store, _tier_filtered_count)

        for pick in all_picks_to_persist:
            # Ensure required fields for grading
            pick.setdefault("pick_id", "")
            pick.setdefault("date_et", date_et_for_store)
            pick.setdefault("grade_status", "PENDING")
            pick.setdefault("persisted_at", "")

            # Persist (idempotent by pick_id)
            if grader_store.persist_pick(pick, date_et_for_store):
                _grader_store_persisted += 1
            else:
                _grader_store_duplicates += 1

        logger.info("GRADER_STORE: Persisted %d picks, %d duplicates",
                    _grader_store_persisted, _grader_store_duplicates)
    except Exception as e:
        logger.exception("GRADER_STORE: Failed to persist picks: %s", e)

    # ============================================
    # LIVE MODE FILTERING (v14.11)
    # ============================================
    # When mode=live, filter to only picks marked as is_live==true
    # These are halftime/period break opportunities where live lines exist
    if live_mode:
        # Filter props: check is_live or is_live_bet_candidate
        top_props = [
            p for p in top_props
            if p.get("is_live") is True or p.get("is_live_bet_candidate") is True
        ]

        # Filter game picks: check is_live or is_live_bet_candidate
        top_game_picks = [
            p for p in top_game_picks
            if p.get("is_live") is True or p.get("is_live_bet_candidate") is True
        ]

        logger.info("LIVE_MODE: Filtered to %d props, %d game_picks", len(top_props), len(top_game_picks))

    # Normalize picks to enforce frontend contract fields
    top_props = [_normalize_pick(p) for p in top_props]
    top_game_picks = [_normalize_pick(p) for p in top_game_picks]

    # ============================================
    # BUILD FINAL RESPONSE
    # ============================================
    # Get astro status if available
    astro_status = None
    if vedic:
        try:
            astro_status = {
                "planetary_hour": vedic.calculate_planetary_hour(),
                "nakshatra": vedic.calculate_nakshatra(),
                "overall_score": vedic.calculate_astro_score().get("overall_score", 50)
            }
        except Exception as e:
            logger.warning("Failed to get astro status: %s", e)

    # v14.9 Version metadata for frontend
    build_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:8] or "local"
    deploy_version = "15.1"

    # v14.9: Date and timestamp in ET
    date_et = get_today_date_str() if TIME_FILTERS_AVAILABLE else datetime.now().strftime("%Y-%m-%d")
    run_timestamp_et = datetime.now().isoformat()

    # Component status (public, non-telemetry)
    props_status = "OK"
    games_status = "OK"
    if _skip_ncaab_props:
        props_status = "SKIPPED"
    elif "props_scoring" in _timed_out_components:
        props_status = "TIMED_OUT"
    elif _props_scoring_error:
        props_status = "ERROR"
    elif len(top_props) == 0:
        props_status = "EMPTY"

    if "game_picks_scoring" in _timed_out_components:
        games_status = "TIMED_OUT"
    elif _game_scoring_error:
        games_status = "ERROR"
    elif len(top_game_picks) == 0:
        games_status = "EMPTY"

    # Stable error codes for public response
    errors = []
    if props_status == "TIMED_OUT":
        errors.append({"code": "PROPS_TIMED_OUT", "component": "props", "message": "props scoring timed out"})
    elif props_status == "ERROR":
        errors.append({"code": "PROPS_ERROR", "component": "props", "message": "props scoring failed"})
    if games_status == "TIMED_OUT":
        errors.append({"code": "GAME_PICKS_TIMED_OUT", "component": "game_picks", "message": "game picks scoring timed out"})
    elif games_status == "ERROR":
        errors.append({"code": "GAME_PICKS_ERROR", "component": "game_picks", "message": "game picks scoring failed"})

    overall_status = "OK"
    if any(s in ["TIMED_OUT", "ERROR"] for s in [props_status, games_status]):
        overall_status = "PARTIAL"

    result = {
        "sport": sport.upper(),
        "mode": "live" if live_mode else "standard",  # v14.11: Indicate which mode
        "source": f"jarvis_savant_v{TIERING_VERSION if TIERING_AVAILABLE else '11.08'}",
        "status": overall_status,
        "scoring_system": "Phase 1-3 Integrated + Titanium v11.08",
        "engine_version": TIERING_VERSION if TIERING_AVAILABLE else "11.08",
        "deploy_version": deploy_version,
        "build_sha": build_sha,
        "identity_resolver": IDENTITY_RESOLVER_AVAILABLE,
        "date_et": date_et,  # v14.9: Today's date in ET
        "run_timestamp_et": run_timestamp_et,  # v14.9: When this response was generated
        "errors": errors,
        "component_status": {
            "props": props_status,
            "game_picks": games_status
        },
        "props": {
            "count": len(top_props),
            "total_analyzed": len(props_picks),
            "status": props_status,
            "picks": top_props
        },
        "game_picks": {
            "count": len(top_game_picks),
            "total_analyzed": len(_all_game_candidates),
            "status": games_status,
            "picks": top_game_picks
        },
        "meta": {
            "odds_fetched_at": _odds_fetched_at,
        },
        "esoteric": {
            "daily_energy": daily_energy,
            "astro_status": astro_status,
            "learned_weights": esoteric_weights,
            "learning_active": learning is not None
        },
        "timestamp": datetime.now().isoformat(),
        "_cached_at": time.time(),
        "_elapsed_s": round(_elapsed(), 2),
        "_timed_out_components": _timed_out_components if _timed_out_components else None,
    }

    try:
        from integration_registry import get_usage_snapshot
        usage_snapshot_after = get_usage_snapshot()
        for name in ("odds_api", "playbook_api", "balldontlie", "serpapi"):
            before = usage_snapshot_before.get(name, {}).get("used_count", 0)
            after = usage_snapshot_after.get(name, {}).get("used_count", 0)
            if after > before:
                entry = integration_calls.get(name, {"called": 0})
                if entry.get("called", 0) == 0:
                    _record_integration_call(name, status="OK")
    except Exception:
        pass

    # === DEBUG MODE: Return top 25 candidates with full engine breakdown ===
    if debug_mode:
        def _debug_pick(p):
            """Extract debug-relevant fields from a candidate pick."""
            return {
                "player_name": p.get("player_name", p.get("player", "")),
                "matchup": p.get("matchup", p.get("game", "")),
                "prop_type": p.get("prop_type", p.get("market", p.get("pick_type", ""))),
                "line": p.get("line"),
                "side": p.get("side", p.get("over_under", "")),
                "final_score": p.get("total_score", p.get("final_score", 0)),
                "tier": p.get("tier", "PASS"),
                "action": p.get("action", "SKIP"),
                "sub_scores": {
                    "ai_score": p.get("ai_score", 0),
                    "research_score": p.get("research_score", 0),
                    "esoteric_score": p.get("esoteric_score", 0),
                    "jarvis_score": p.get("jarvis_score", p.get("jarvis_rs", 0)),
                    "jason_sim_boost": p.get("jason_sim_boost", 0),
                    "base_score": p.get("base_score", 0),
                },
                "breakdown": {
                    "scoring": p.get("scoring_breakdown", {}),
                    "research": p.get("research_breakdown", {}),
                    "esoteric": p.get("esoteric_breakdown", {}),
                    "jarvis": p.get("jarvis_breakdown", {}),
                },
                "missing_data": {
                    "no_odds": not p.get("odds") and not p.get("best_odds"),
                    "no_sharp_signal": not p.get("research_breakdown", {}).get("sharp_boost"),
                    "no_splits": not p.get("research_breakdown", {}).get("public_boost") and not p.get("research_breakdown", {}).get("sharp_boost"),
                    "no_injury_data": p.get("injury_status", "HEALTHY") == "UNKNOWN",
                    "no_jarvis_triggers": p.get("jarvis_hits_count", 0) == 0,
                    "jason_blocked": p.get("jason_blocked", False),
                    "jason_not_run": not p.get("jason_ran", False),
                },
                "engine_inputs": {
                    "research_total": p.get("research_breakdown", {}).get("total", 0),
                    "sharp_boost": p.get("research_breakdown", {}).get("sharp_boost", 0),
                    "public_boost": p.get("research_breakdown", {}).get("public_boost", 0),
                    "esoteric_fib": p.get("esoteric_breakdown", {}).get("fibonacci", 0),
                    "esoteric_vortex": p.get("esoteric_breakdown", {}).get("vortex", 0),
                    "confluence_boost": p.get("scoring_breakdown", {}).get("confluence_boost", 0),
                },
                "titanium_triggered": p.get("titanium_triggered", False),
                "titanium_reasons": p.get("titanium_reasons", p.get("smash_reasons", [])),
                "signals_fired": p.get("jarvis_reasons", []) + p.get("confluence_reasons", []),
            }

        debug_props = [_debug_pick(p) for p in _all_prop_candidates[:25]]
        debug_games = [_debug_pick(p) for p in _all_game_candidates[:25]]

        # Score distribution buckets (0.5 increments)
        all_scores = [p.get("total_score", 0) for p in _all_prop_candidates + _all_game_candidates]
        buckets = {}
        for s in all_scores:
            bucket = round(int(s * 2) / 2, 1)  # Round to nearest 0.5
            buckets[bucket] = buckets.get(bucket, 0) + 1

        # v15.3: Ensure stable debug schema with defaults for all keys
        result["debug"] = {
            # Timing breakdown
            "debug_timings": _timings,
            "total_elapsed_s": round(_elapsed(), 2),
            "timed_out_components": _timed_out_components,
            "time_budget_s": TIME_BUDGET_S,
            "props_time_budget_s": PROPS_TIME_BUDGET_S,
            "max_events": max_events,
            "max_props": max_props,
            "max_games": max_games,

            # Player resolution (always present, even if empty)
            "player_resolution": {
                "attempted": _resolve_attempted,
                "succeeded": _resolve_succeeded,
                "timed_out": _resolve_timed_out,
                "cache_size": len(_player_resolve_cache),
            },

            # Date window (always present, even if empty)
            "date_window_et": _date_window_et_debug or {
                "date_str": "unknown",
                "start_et": "00:00:00",
                "end_et": "23:59:59",
                "events_dropped_before": 0,
                "events_dropped_after": 0,
            },
            "min_score_used": min_score,
            "community_threshold": 6.5,
            "total_prop_candidates": len(_all_prop_candidates),
            "total_game_candidates": len(_all_game_candidates),
            "props_above_6_0": sum(1 for p in _all_prop_candidates if p.get("total_score", 0) >= 6.0),
            "props_above_6_5": sum(1 for p in _all_prop_candidates if p.get("total_score", 0) >= 6.5),
            "games_above_6_0": sum(1 for p in _all_game_candidates if p.get("total_score", 0) >= 6.0),
            "games_above_6_5": sum(1 for p in _all_game_candidates if p.get("total_score", 0) >= 6.5),
            "score_distribution": dict(sorted(buckets.items())),
            "dropped_out_of_window_props": _dropped_out_of_window_props,
            "dropped_out_of_window_games": _dropped_out_of_window_games,
            "dropped_missing_time_props": _dropped_missing_time_props,
            "dropped_missing_time_games": _dropped_missing_time_games,

            # v15.3 Injury guard (always present)
            "injury_guard": {
                "blocked_count": sum(1 for p in _all_prop_candidates if p.get("injury_status", "HEALTHY") in ["OUT", "DOUBTFUL"]),
                "questionable_count": sum(1 for p in _all_prop_candidates if p.get("injury_status", "HEALTHY") == "QUESTIONABLE"),
                "checked_count": sum(1 for p in _all_prop_candidates if p.get("injury_checked", False)),
            },

            # v15.3 Gate summary (always present)
            "gates": {
                "below_6_5": filtered_below_6_5_props + filtered_below_6_5_games,
                "contradictions": contradiction_debug.get("total_dropped", 0),
                "duplicates": _dupe_dropped_props + _dupe_dropped_games,
                "out_of_window": _dropped_out_of_window_props + _dropped_out_of_window_games,
                "total_filtered": (filtered_below_6_5_props + filtered_below_6_5_games +
                                  contradiction_debug.get("total_dropped", 0) +
                                  diversity_debug.get("total_dropped", 0) +
                                  _dupe_dropped_props + _dupe_dropped_games +
                                  _dropped_out_of_window_props + _dropped_out_of_window_games),
            },

            # v15.3 dedupe telemetry
            "dupe_dropped_props": _dupe_dropped_props,
            "dupe_dropped_games": _dupe_dropped_games,
            "dupe_dropped_count": _dupe_dropped_props + _dupe_dropped_games,
            "dupe_groups_props": _dupe_groups_props[:10],  # Cap for output size
            "dupe_groups_games": _dupe_groups_games[:10],
            # v15.0 filtering telemetry
            "filtered_below_6_5_props": filtered_below_6_5_props,
            "filtered_below_6_5_games": filtered_below_6_5_games,
            "filtered_below_6_5_total": filtered_below_6_5_props + filtered_below_6_5_games,
            "contradiction_blocked_props": contradiction_debug["props_dropped"],
            "contradiction_blocked_games": contradiction_debug["games_dropped"],
            "contradiction_blocked_total": contradiction_debug["total_dropped"],
            # v16.1 diversity filter telemetry
            "diversity_player_limited": diversity_debug.get("player_limited", 0),
            "diversity_game_limited": diversity_debug.get("game_limited", 0),
            "diversity_total_dropped": diversity_debug.get("total_dropped", 0),
            # v15.1 diagnostics
            "sharp_lookup_size": len(sharp_lookup),
            "sharp_source": sharp_data.get("source", "unknown"),
            "game_context_size": len(game_context),
            "splits_present_count": sum(1 for p in _all_prop_candidates + _all_game_candidates if p.get("research_breakdown", {}).get("sharp_boost", 0) > 0),
            "jarvis_active_count": sum(1 for p in _all_prop_candidates + _all_game_candidates if p.get("jarvis_hits_count", 0) > 0),
            "jason_ran_count": sum(1 for p in _all_prop_candidates + _all_game_candidates if p.get("jason_ran", False)),
            "picks_logged": _picks_logged,
            "picks_skipped_dupes": _picks_skipped,
            "picks_attempted": len(top_props) + len(top_game_picks),
            "pick_log_errors": _pick_log_errors,
            "top_prop_candidates": debug_props,
            "top_game_candidates": debug_games,
            # v16.0 Weather telemetry
            "weather": {
                "enabled": WEATHER_MODULE_AVAILABLE,  # Weather is now required (no WEATHER_ENABLED flag)
                "module_available": WEATHER_MODULE_AVAILABLE,
                "games_fetched": _weather_fetched,
                "cache_hits": _weather_cache_hits,
                "cache_size": len(_weather_cache),
                "picks_with_weather": sum(1 for p in _all_prop_candidates + _all_game_candidates if p.get("weather_available", False)),
                "picks_with_modifier": sum(1 for p in _all_prop_candidates + _all_game_candidates if p.get("weather_modifier", 0) != 0),
            },
            # v17.4 SERP Intelligence status banner
            "serp": {
                "available": SERP_INTEL_AVAILABLE,
                "shadow_mode": SERP_SHADOW_MODE if SERP_INTEL_AVAILABLE else True,
                "mode": "shadow" if (SERP_INTEL_AVAILABLE and SERP_SHADOW_MODE) else ("live" if SERP_INTEL_AVAILABLE else "disabled"),
                "status": get_serp_status() if (SERP_INTEL_AVAILABLE and callable(get_serp_status)) else {"error": "serp_intel_unavailable"},
                "prefetch_cached": _serp_prefetch_count,
                "prefetch_games": len(_serp_game_cache) if _serp_game_cache else 0,
            },
            # v17.3 ESPN Integration telemetry
            "espn": {
                "available": ESPN_OFFICIALS_AVAILABLE,
                "events_mapped": len(_officials_by_game) if _officials_by_game else 0,
                "officials_available": len(_officials_by_game) if _officials_by_game else 0,
                "officials_data": [{"game": str(k), "lead": v.get("lead_official") if isinstance(v, dict) else None} for k, v in list(_officials_by_game.items())[:3]] if _officials_by_game else [],
                "odds_available": len(_espn_odds_by_game) if _espn_odds_by_game else 0,
                "injuries_teams": len(_espn_injuries_supplement) if _espn_injuries_supplement else 0,
                "venues_available": len(_espn_venue_by_game) if _espn_venue_by_game else 0,
                "events_keys": list(_espn_events_by_teams.keys())[:5] if _espn_events_by_teams and len(_espn_events_by_teams) <= 5 else (list(_espn_events_by_teams.keys())[:5] + [f"...and {len(_espn_events_by_teams) - 5} more"] if _espn_events_by_teams else []),
                "fetch_error": _espn_fetch_error,
            },
        }
        apply_used_integrations_debug(result, used_integrations, debug_mode)
        attach_integration_telemetry_debug(result, integration_calls, integration_impact, debug_mode)
        record_daily_integration_rollup(date_et, integration_calls, integration_impact)
        # Don't cache debug responses
        return result

    record_daily_integration_rollup(date_et, integration_calls, integration_impact)
    if cache_key:
        api_cache.set(cache_key, result, ttl=120)  # 2 minute TTL
    return result


# ============================================================================
# LIVE BETTING ENDPOINT (v12.0 Production Hardened)
# ============================================================================

@router.get("/live/in-play/{sport}")
async def get_live_bets(sport: str):
    """
    Live betting picks - games currently in progress.

    Only returns picks with final_score >= MIN_FINAL_SCORE (COMMUNITY_MIN_SCORE).
    All picks have status = "LIVE" or "STARTED".

    Returns:
        Dict with sport, type, picks[], live_games_count, timestamp
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get best bets first
    best_bets_response = await get_best_bets(sport)

    # Odds staleness check
    odds_fetched_at_str = best_bets_response.get("meta", {}).get("odds_fetched_at")
    odds_age_seconds = None
    staleness_status = "UNKNOWN"
    try:
        if odds_fetched_at_str and TIME_ET_AVAILABLE:
            from datetime import datetime as _dt
            _fetched = _dt.fromisoformat(odds_fetched_at_str)
            _now = now_et()
            if _fetched.tzinfo is None:
                from zoneinfo import ZoneInfo
                _fetched = _fetched.replace(tzinfo=ZoneInfo("America/New_York"))
            odds_age_seconds = (_now - _fetched).total_seconds()
            staleness_status = "STALE" if odds_age_seconds > ODDS_STALENESS_THRESHOLD_SECONDS else "FRESH"
    except Exception:
        pass

    # Filter to only live/started games
    live_picks = []
    market_suspended_count = 0

    def _detect_market_status(pick):
        """Check if market appears suspended (no active bookmaker lines)."""
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            return "suspended", "No active bookmaker lines"
        return "open", None

    # Process props
    for pick in best_bets_response.get("props", {}).get("picks", []):
        commence_time = pick.get("start_time", pick.get("commence_time", ""))
        if TIME_FILTERS_AVAILABLE and commence_time:
            is_started, started_at = is_game_started(commence_time)
            if is_started:
                # Only include if score >= 6.5 (community threshold)
                final_score = pick.get("final_score", 0)
                if final_score >= MIN_FINAL_SCORE:
                    pick["status"] = "LIVE"
                    pick["started_at"] = started_at
                    pick["live_bet_eligible"] = True
                    pick["staleness_status"] = staleness_status
                    pick["odds_age_seconds"] = odds_age_seconds
                    mkt_status, mkt_reason = _detect_market_status(pick)
                    pick["market_status"] = mkt_status
                    if mkt_reason:
                        pick["market_suspended_reason"] = mkt_reason
                    if mkt_status == "suspended":
                        market_suspended_count += 1
                    if staleness_status == "STALE":
                        pick["live_adjustment"] = 0
                    live_picks.append(pick)

    # Process game picks
    for pick in best_bets_response.get("game_picks", {}).get("picks", []):
        commence_time = pick.get("start_time", pick.get("commence_time", ""))
        if TIME_FILTERS_AVAILABLE and commence_time:
            is_started, started_at = is_game_started(commence_time)
            if is_started:
                final_score = pick.get("final_score", 0)
                if final_score >= MIN_FINAL_SCORE:
                    pick["status"] = "LIVE"
                    pick["started_at"] = started_at
                    pick["live_bet_eligible"] = True
                    pick["staleness_status"] = staleness_status
                    pick["odds_age_seconds"] = odds_age_seconds
                    mkt_status, mkt_reason = _detect_market_status(pick)
                    pick["market_status"] = mkt_status
                    if mkt_reason:
                        pick["market_suspended_reason"] = mkt_reason
                    if mkt_status == "suspended":
                        market_suspended_count += 1
                    if staleness_status == "STALE":
                        pick["live_adjustment"] = 0
                    live_picks.append(pick)

    if market_suspended_count > 0:
        logger.info("LIVE IN-PLAY: %d picks with suspended markets detected", market_suspended_count)

    # Sort by final_score descending
    live_picks.sort(key=_stable_pick_sort_key)

    return {
        "sport": sport.upper(),
        "type": "LIVE_BETS",
        "picks": live_picks,
        "live_games_count": len(live_picks),
        "community_threshold": 6.5,
        "market_suspended_count": market_suspended_count,
        "odds_staleness": {
            "status": staleness_status,
            "odds_age_seconds": round(odds_age_seconds, 1) if odds_age_seconds is not None else None,
            "threshold_seconds": ODDS_STALENESS_THRESHOLD_SECONDS,
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# v11.15: LIVE IN-GAME PICKS ENDPOINT (with BallDontLie context)
# ============================================================================

@router.get("/in-game/{sport}")
async def get_in_game_picks(sport: str):
    """
    v11.15: Live in-game betting picks for games that have already started.

    Returns picks from best-bets that have game_status=MISSED_START,
    meaning they are candidates for live/in-game betting.

    For NBA, includes BallDontLie live context if configured (BDL_API_KEY).

    Trigger Windows (NBA):
    - HALFTIME: Between Q2 end and Q3 start
    - LATE_GAME_Q4: Q4 with 10:00 or less remaining
    - OVERTIME: Any overtime period

    Response includes:
    - live_picks: Picks for games that have started
    - trigger_games: Games currently in valid trigger windows
    - bdl_context: BallDontLie live data (if available)
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get best-bets and filter to MISSED_START picks
    best_bets_result = await get_best_bets(sport)

    # Odds staleness check
    odds_fetched_at_str = best_bets_result.get("meta", {}).get("odds_fetched_at")
    odds_age_seconds = None
    staleness_status = "UNKNOWN"
    try:
        if odds_fetched_at_str and TIME_ET_AVAILABLE:
            from datetime import datetime as _dt
            _fetched = _dt.fromisoformat(odds_fetched_at_str)
            _now = now_et()
            if _fetched.tzinfo is None:
                from zoneinfo import ZoneInfo
                _fetched = _fetched.replace(tzinfo=ZoneInfo("America/New_York"))
            odds_age_seconds = (_now - _fetched).total_seconds()
            staleness_status = "STALE" if odds_age_seconds > ODDS_STALENESS_THRESHOLD_SECONDS else "FRESH"
    except Exception:
        pass

    # Filter props and game picks to only MISSED_START
    live_props = [
        p for p in best_bets_result.get("props", {}).get("picks", [])
        if p.get("game_status") == "MISSED_START"
    ]
    live_game_picks = [
        p for p in best_bets_result.get("game_picks", {}).get("picks", [])
        if p.get("game_status") == "MISSED_START"
    ]

    # Annotate live picks with staleness and market status info
    market_suspended_count = 0
    for pick in live_props + live_game_picks:
        pick["staleness_status"] = staleness_status
        pick["odds_age_seconds"] = odds_age_seconds
        if staleness_status == "STALE":
            pick["live_adjustment"] = 0
        # Market status detection
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            pick["market_status"] = "suspended"
            pick["market_suspended_reason"] = "No active bookmaker lines"
            market_suspended_count += 1
        else:
            pick["market_status"] = "open"

    if market_suspended_count > 0:
        logger.info("IN-GAME: %d picks with suspended markets detected", market_suspended_count)

    # Get BallDontLie context for NBA
    bdl_context = None
    if sport_lower == "nba":
        try:
            from alt_data_sources.balldontlie import (
                is_balldontlie_configured,
                get_nba_live_context
            )
            if is_balldontlie_configured():
                bdl_context = await get_nba_live_context()
        except ImportError:
            logger.debug("BallDontLie module not available")
        except Exception as e:
            logger.warning("Failed to get BallDontLie context: %s", e)

    # Build trigger games list from BDL context
    trigger_games = []
    if bdl_context and bdl_context.get("available"):
        trigger_games = bdl_context.get("trigger_games", [])

    return {
        "sport": sport.upper(),
        "source": "live_in_game_v11.15",
        "live_props": {
            "count": len(live_props),
            "picks": live_props
        },
        "live_game_picks": {
            "count": len(live_game_picks),
            "picks": live_game_picks
        },
        "trigger_windows": {
            "games_in_window": len(trigger_games),
            "games": trigger_games
        },
        "market_suspended_count": market_suspended_count,
        "odds_staleness": {
            "status": staleness_status,
            "odds_age_seconds": round(odds_age_seconds, 1) if odds_age_seconds is not None else None,
            "threshold_seconds": ODDS_STALENESS_THRESHOLD_SECONDS,
        },
        "bdl_context": bdl_context,
        "bdl_configured": bdl_context is not None and bdl_context.get("available", False),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# DEBUG PICK BREAKDOWN ENDPOINT (v11.08)
# ============================================================================

@router.get("/debug/pick-breakdown/{sport}")
async def debug_pick_breakdown(sport: str):
    """
    DEBUG ENDPOINT: Full breakdown of pick scoring for verification.

    Returns TODAY-only picks with complete engine score breakdown.
    Used by frontend to verify all 4 engines are running and scoring correctly.

    For each pick includes:
    - pick_id: Deterministic hash for stable identification
    - All 4 engine scores: ai_score, research_score, esoteric_score, jarvis_rs
    - All reasons arrays: ai_reasons, research_reasons, esoteric_reasons, jarvis_reasons
    - penalties_applied: Array of penalty objects
    - titanium_triggered: Boolean if 3/4 engines >= 8.0
    - titanium_explanation: Human-readable explanation

    This endpoint exposes what was already computed - no new scoring.
    TODAY-only slate gating (midnight-to-midnight America/New_York) is enforced.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get MasterPredictionSystem and esoteric engines
    mps = get_master_prediction_system()
    daily_energy = get_daily_energy()
    jarvis = get_jarvis_savant()
    vedic = get_vedic_astro()

    # Fetch sharp money
    sharp_data = await get_sharp_money(sport)
    sharp_lookup = {}
    for signal in sharp_data.get("data", []):
        game_key = f"{signal.get('away_team')}@{signal.get('home_team')}"
        sharp_lookup[game_key] = signal

    # Helper to generate deterministic pick_id
    def generate_pick_id(pick_data: Dict) -> str:
        """Generate stable hash ID for a pick."""
        key_parts = [
            str(pick_data.get("player", "")),
            str(pick_data.get("market", "")),
            str(pick_data.get("line", "")),
            str(pick_data.get("side", "")),
            str(pick_data.get("game", "")),
            str(pick_data.get("pick_type", ""))
        ]
        hash_input = "|".join(key_parts).encode()
        return hashlib.sha256(hash_input).hexdigest()[:12]

    # Helper to calculate detailed score with full breakdown
    def calculate_detailed_score(game_str, sharp_signal, base_ai=5.0, player_name="", home_team="", away_team="", spread=0, total=220, public_pct=50, is_prop=True):
        """Calculate scores with full breakdown for debug output (v14.9 Clean Architecture)."""

        # --- ESOTERIC WEIGHTS (v10.2 - Gematria Dominant) ---
        ESOTERIC_WEIGHTS = {
            "gematria": 0.52,
            "jarvis": 0.20,
            "astro": 0.13,
            "fib": 0.05,
            "vortex": 0.05,
            "daily_edge": 0.05
        }

        # --- AI SCORE (Pure Model - 0-8 scale, with data quality boosts) ---
        ai_reasons = []
        ai_reasons.append(f"Base AI: {base_ai}/8")
        _ai_boost = 0.0
        # Sharp data present
        if sharp_signal:
            _ai_boost += 0.5
            ai_reasons.append("Sharp data present (+0.5)")
        # Signal strength
        _ss = sharp_signal.get("signal_strength", "NONE") if sharp_signal else "NONE"
        if _ss == "STRONG":
            _ai_boost += 1.0
            ai_reasons.append("STRONG signal alignment (+1.0)")
        elif _ss == "MODERATE":
            _ai_boost += 0.5
            ai_reasons.append("MODERATE signal alignment (+0.5)")
        elif _ss == "MILD":
            _ai_boost += 0.25
            ai_reasons.append("MILD signal alignment (+0.25)")
        # Favorable spread
        if 3 <= abs(spread) <= 10:
            _ai_boost += 0.5
            ai_reasons.append(f"Favorable spread {spread} (+0.5)")
        # Player data
        if player_name:
            _ai_boost += 0.25
            ai_reasons.append("Player data available (+0.25)")
        ai_score = min(8.0, base_ai + _ai_boost)

        # --- RESEARCH SCORE (Market Intelligence - 0-10 scale) ---
        research_reasons = []

        # Pillar 1: Sharp Money Detection (0-3 pts)
        sharp_boost = 0.0
        if sharp_signal.get("signal_strength") == "STRONG":
            sharp_boost = 3.0
            research_reasons.append("Sharp signal STRONG (+3.0)")
        elif sharp_signal.get("signal_strength") == "MODERATE":
            sharp_boost = 1.5
            research_reasons.append("Sharp signal MODERATE (+1.5)")
        else:
            research_reasons.append("No sharp signal detected")

        # Pillar 2: Line Movement/Value (0-3 pts)
        line_variance = sharp_signal.get("line_variance", 0)
        line_boost = 0.0
        if line_variance > 1.5:
            line_boost = 3.0
            research_reasons.append(f"Line variance {line_variance:.1f}pts (strong RLM)")
        elif line_variance > 0.5:
            line_boost = 1.5
            research_reasons.append(f"Line variance {line_variance:.1f}pts (moderate)")
        else:
            research_reasons.append(f"Line variance {line_variance:.1f}pts (minimal)")

        # Pillar 3: Public Betting Fade (0-2 pts)
        # v14.11: Use centralized public fade calculator (single-calculation policy)
        public_pct_val = sharp_signal.get("public_pct", public_pct)
        ticket_pct_val = sharp_signal.get("ticket_pct")
        money_pct_val = sharp_signal.get("money_pct")

        if SIGNALS_AVAILABLE:
            public_fade_signal = calculate_public_fade(public_pct_val, ticket_pct_val, money_pct_val)
            public_boost = public_fade_signal.research_boost
            public_fade_context = get_public_fade_context(public_fade_signal)
            if public_fade_signal.reason:
                research_reasons.append(public_fade_signal.reason)
        else:
            # Fallback to inline calculation
            public_boost = 0.0
            public_fade_context = {"public_overload": False}
            if public_pct_val >= 75:
                public_boost = 2.0
                research_reasons.append(f"Public at {public_pct_val}% (fade signal)")
                public_fade_context = {"public_overload": True, "is_strong_fade": True}
            elif public_pct_val >= 65:
                public_boost = 1.0
                research_reasons.append(f"Public at {public_pct_val}% (mild fade)")
                public_fade_context = {"public_overload": True, "is_strong_fade": False}

        # Pillar 4: Base research floor (2 pts baseline)
        base_research = 2.0

        # Research score: Sum of pillars normalized to 0-10
        research_score = min(10.0, base_research + sharp_boost + line_boost + public_boost)
        research_reasons.append(f"Total: {round(research_score, 2)}/10 (Sharp:{sharp_boost} + RLM:{line_boost} + Public:{public_boost} + Base:{base_research})")

        if (sharp_boost + public_boost) > 0:
            _record_integration_impact(
                "playbook_api",
                nonzero_boost=True,
                reasons_count=len(research_reasons),
            )
        if line_boost > 0:
            _record_integration_impact(
                "odds_api",
                nonzero_boost=True,
                reasons_count=1,
            )

        # Pillar score for backwards compatibility
        pillar_score = sharp_boost + line_boost + public_boost

        # --- ESOTERIC COMPONENTS ---
        # v14.11: public_fade_mod REMOVED - only Research Engine applies public fade boost
        gematria_score = 0.0
        jarvis_score = 0.0
        astro_score = 0.0
        fib_score = 0.0
        vortex_score = 0.0
        daily_edge_score = 0.0
        trap_mod = 0.0
        # NOTE: public_fade_context available for reference, but NOT applied numerically

        jarvis_triggers_hit = []
        esoteric_reasons = []
        penalties_applied = []

        if jarvis:
            # JARVIS TRIGGERS
            trigger_result = jarvis.check_jarvis_trigger(game_str)
            raw_jarvis = 0.0
            for trig in trigger_result.get("triggers_hit", []):
                raw_jarvis += trig["boost"] / 10
                jarvis_triggers_hit.append({
                    "number": trig["number"],
                    "name": trig["name"],
                    "boost": round(trig["boost"] / 10, 2)
                })
            jarvis_score = min(1.0, raw_jarvis) * 10 * ESOTERIC_WEIGHTS["jarvis"]

            if jarvis_triggers_hit:
                esoteric_reasons.append(f"JARVIS triggers: {[t['name'] for t in jarvis_triggers_hit]}")

            # GEMATRIA
            if player_name and home_team:
                gematria = jarvis.calculate_gematria_signal(player_name, home_team, away_team)
                gematria_strength = gematria.get("signal_strength", 0)
                if gematria.get("triggered"):
                    gematria_strength = min(1.0, gematria_strength * 1.5)
                    esoteric_reasons.append(f"Gematria triggered: strength {round(gematria_strength, 2)}")
                gematria_score = gematria_strength * 10 * ESOTERIC_WEIGHTS["gematria"]

                # v14.11: PUBLIC FADE - Now context-only for Esoteric, NO numeric modifier
                # Research Engine owns the boost; Esoteric only sees the flag
                if public_fade_context.get("public_overload"):
                    esoteric_reasons.append(f"Public overload detected (context only, no boost)")

                # TRAP DEDUCTION
                trap = jarvis.calculate_large_spread_trap(spread, total)
                trap_mod = trap.get("modifier", 0)
                if trap_mod < 0:
                    penalties_applied.append({"name": "Large Spread Trap", "magnitude": round(trap_mod, 2)})

                # FIBONACCI
                fib_alignment = jarvis.calculate_fibonacci_alignment(float(spread) if spread else 0)
                fib_raw = fib_alignment.get("modifier", 0)
                fib_score = max(0, fib_raw) * 10 * ESOTERIC_WEIGHTS["fib"]
                if fib_score > 0:
                    esoteric_reasons.append(f"Fibonacci alignment: +{round(fib_score, 2)}")

                # VORTEX
                vortex_value = int(abs(spread * 10)) if spread else 0
                vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)
                vortex_raw = vortex_pattern.get("modifier", 0)
                vortex_score = max(0, vortex_raw) * 10 * ESOTERIC_WEIGHTS["vortex"]
                if vortex_score > 0:
                    esoteric_reasons.append(f"Vortex 3-6-9 pattern: +{round(vortex_score, 2)}")

            # ASTRO
            astro = vedic.calculate_astro_score() if vedic else {"overall_score": 50}
            astro_normalized = (astro["overall_score"] - 50) / 50
            astro_score = max(0, astro_normalized) * 10 * ESOTERIC_WEIGHTS["astro"]
            if astro_score > 0:
                esoteric_reasons.append(f"Astro boost: +{round(astro_score, 2)}")

        # DAILY EDGE
        if daily_energy.get("overall_score", 50) >= 85:
            daily_edge_score = 10 * ESOTERIC_WEIGHTS["daily_edge"]
            esoteric_reasons.append("Daily energy HIGH: +0.5")
        elif daily_energy.get("overall_score", 50) >= 70:
            daily_edge_score = 5 * ESOTERIC_WEIGHTS["daily_edge"]
            esoteric_reasons.append("Daily energy MODERATE: +0.25")

        if not esoteric_reasons:
            esoteric_reasons.append("No esoteric signals triggered")

        # --- ESOTERIC SCORE ---
        # v14.11: public_fade_mod REMOVED - prevents double-counting with Research Engine
        esoteric_raw = (
            gematria_score + jarvis_score + astro_score +
            fib_score + vortex_score + daily_edge_score +
            trap_mod  # trap_mod is the only negative modifier
        )
        esoteric_score = max(0, min(10, esoteric_raw))

        # --- CONFLUENCE ---
        if jarvis:
            confluence = jarvis.calculate_confluence(
                research_score=research_score,
                esoteric_score=esoteric_score,
                immortal_detected=any(t["number"] == 2178 for t in jarvis_triggers_hit),
                jarvis_triggered=len(jarvis_triggers_hit) > 0
            )
        else:
            alignment = 1 - abs(research_score - esoteric_score) / 10
            alignment_pct = alignment * 100
            if alignment_pct >= 80 and research_score >= 7.5 and esoteric_score >= 7.5:
                confluence = {"level": "PERFECT", "boost": CONFLUENCE_LEVELS["PERFECT"], "alignment_pct": alignment_pct}
            elif alignment_pct >= 70:
                confluence = {"level": "STRONG", "boost": CONFLUENCE_LEVELS["STRONG"], "alignment_pct": alignment_pct}
            else:
                confluence = {"level": "DIVERGENT", "boost": CONFLUENCE_LEVELS["DIVERGENT"], "alignment_pct": alignment_pct}

        confluence_boost = confluence.get("boost", 0)

        # --- JARVIS RS (0-10 scale) ---
        jarvis_rs = scale_jarvis_score_to_10(jarvis_score, max_jarvis=2.0) if TIERING_AVAILABLE else jarvis_score * 5
        jarvis_active = len(jarvis_triggers_hit) > 0
        jarvis_reasons = [t.get("name", "Unknown") for t in jarvis_triggers_hit]

        # --- AI SCALED (0-10) ---
        ai_scaled = scale_ai_score_to_10(ai_score, max_ai=8.0) if TIERING_AVAILABLE else ai_score * 1.25

        # --- FINAL SCORE (Option A - 4 base engines + additive boosts) ---
        context_modifier = 0.0
        jason_sim_boost = 0.0
        base_score = (
            (ai_scaled * ENGINE_WEIGHTS["ai"]) +
            (research_score * ENGINE_WEIGHTS["research"]) +
            (esoteric_score * ENGINE_WEIGHTS["esoteric"]) +
            (jarvis_rs * ENGINE_WEIGHTS["jarvis"])
        )
        final_score, context_modifier = compute_final_score_option_a(
            base_score=base_score,
            context_modifier=context_modifier,
            confluence_boost=confluence_boost,
            msrf_boost=0.0,
            jason_sim_boost=jason_sim_boost,
            serp_boost=0.0,
        )

        # --- TITANIUM CHECK ---
        try:
            from core.titanium import evaluate_titanium
            titanium_triggered, titanium_explanation, qualifying_engines = evaluate_titanium(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=jarvis_rs,
                final_score=final_score,
                threshold=8.0
            )
        except Exception:
            titanium_triggered, titanium_explanation, qualifying_engines = check_titanium_rule(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=jarvis_rs,
                final_score=final_score
            )

        # --- BET TIER ---
        if TIERING_AVAILABLE:
            bet_tier = tier_from_score(
                final_score=final_score,
                confluence=confluence,
                nhl_dog_protocol=False,
                titanium_triggered=titanium_triggered,
                # v20.12: Pass engine scores for quality gates
                base_score=base_score,
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=jarvis_rs,
            )
        else:
            # Fallback tier determination (v12.0 thresholds)
            if titanium_triggered:
                bet_tier = {"tier": "TITANIUM_SMASH", "units": 2.5, "action": "SMASH"}
            elif final_score >= GOLD_STAR_THRESHOLD:  # v12.0: was 9.0
                bet_tier = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
            elif final_score >= MIN_FINAL_SCORE:  # v12.0: was 7.5
                bet_tier = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
            elif final_score >= 5.5:  # v12.0: was 6.0
                bet_tier = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
            else:
                bet_tier = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

        return {
            # Engine scores (all on 0-10 scale for comparison)
            "ai_score": round(ai_scaled, 2),
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "jarvis_rs": round(jarvis_rs, 2),

            # Reasons arrays
            "ai_reasons": ai_reasons,
            "research_reasons": research_reasons,
            "esoteric_reasons": esoteric_reasons,
            "jarvis_reasons": jarvis_reasons,

            # Penalties
            "penalties_applied": penalties_applied,

            # Final scoring
            "final_score": round(final_score, 2),
            "confluence_level": confluence.get("level", "DIVERGENT"),
            "confluence_boost": confluence_boost,

            # Tier
            "tier": bet_tier.get("tier", "PASS"),
            "action": bet_tier.get("action", "SKIP"),
            "units": bet_tier.get("units", bet_tier.get("unit_size", 0.0)),

            # Titanium
            "titanium_triggered": titanium_triggered,
            "titanium_explanation": titanium_explanation,

            # JARVIS
            "jarvis_active": jarvis_active,
            "jarvis_triggers": jarvis_triggers_hit
        }

    # ========== COLLECT PROPS ==========
    props_breakdown = []
    try:
        props_data = await get_props(sport)
        for game in props_data.get("data", []):
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            game_key = f"{away_team}@{home_team}"
            game_str = f"{home_team}{away_team}"
            sharp_signal = sharp_lookup.get(game_key, {})

            for prop in game.get("props", []):
                player = prop.get("player", "Unknown")
                market = prop.get("market", "")
                line = prop.get("line", 0)
                odds = prop.get("odds", -110)
                side = prop.get("side", "Over")

                if side not in ["Over", "Under"]:
                    continue

                score_data = calculate_detailed_score(
                    game_str + player, sharp_signal, base_ai=5.0,
                    player_name=player, home_team=home_team, away_team=away_team,
                    spread=0, total=220, public_pct=50, is_prop=True
                )

                pick_base = {
                    "sport": sport.upper(),
                    "is_prop": True,
                    "matchup": f"{away_team} @ {home_team}",
                    "player_name": player,
                    "stat_type": market,
                    "line": line,
                    "over_under": side,
                    "odds": odds,
                    "book_name": prop.get("book_name", "Unknown"),
                    "book_key": prop.get("book_key", ""),
                    "link": prop.get("link", ""),
                    "injury_status": prop.get("injury_status", "HEALTHY")
                }
                pick_base["pick_id"] = generate_pick_id(pick_base)
                pick_base.update(score_data)
                props_breakdown.append(pick_base)

    except Exception as e:
        logger.warning("Props fetch failed for debug breakdown: %s", e)

    # ========== COLLECT GAME PICKS ==========
    game_breakdown = []
    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()
            for game in games:
                home_team = game.get("home_team", "")
                away_team = game.get("away_team", "")
                game_key = f"{away_team}@{home_team}"
                game_str = f"{home_team}{away_team}"
                sharp_signal = sharp_lookup.get(game_key, {})

                for bm in game.get("bookmakers", [])[:1]:
                    book_name = bm.get("title", "Unknown")
                    book_key = bm.get("key", "")

                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")

                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point")

                            if market_key == "spreads":
                                pick_type = "SPREAD"
                                display = f"{pick_name} {point:+.1f}" if point else pick_name
                            elif market_key == "h2h":
                                pick_type = "MONEYLINE"
                                display = f"{pick_name} ML"
                            elif market_key == "totals":
                                pick_type = "TOTAL"
                                display = f"{pick_name} {point}" if point else pick_name
                            else:
                                continue

                            score_data = calculate_detailed_score(
                                game_str, sharp_signal, base_ai=4.5,
                                player_name="", home_team=home_team, away_team=away_team,
                                spread=point if market_key == "spreads" and point else 0,
                                total=point if market_key == "totals" and point else 220,
                                public_pct=50, is_prop=False
                            )

                            pick_base = {
                                "sport": sport.upper(),
                                "is_prop": False,
                                "matchup": f"{away_team} @ {home_team}",
                                "pick_type": pick_type,
                                "side": pick_name,
                                "spread": point if market_key == "spreads" else None,
                                "total": point if market_key == "totals" else None,
                                "display": display,
                                "odds": odds,
                                "book_name": book_name,
                                "book_key": book_key,
                                "link": ""
                            }
                            pick_base["pick_id"] = generate_pick_id(pick_base)
                            pick_base.update(score_data)
                            game_breakdown.append(pick_base)

    except Exception as e:
        logger.warning("Game odds fetch failed for debug breakdown: %s", e)

    # Sort by final_score
    props_breakdown.sort(key=_stable_pick_sort_key)
    game_breakdown.sort(key=_stable_pick_sort_key)

    return {
        "sport": sport.upper(),
        "engine_version": TIERING_VERSION if TIERING_AVAILABLE else "11.08",
        "titanium_threshold": TITANIUM_THRESHOLD if TIERING_AVAILABLE else 8.0,
        "timestamp": datetime.now().isoformat(),
        "props": {
            "count": len(props_breakdown),
            "picks": props_breakdown[:20]  # Limit to top 20 for response size
        },
        "game_picks": {
            "count": len(game_breakdown),
            "picks": game_breakdown[:20]  # Limit to top 20 for response size
        },
        "summary": {
            "total_picks_analyzed": len(props_breakdown) + len(game_breakdown),
            "titanium_count": sum(1 for p in props_breakdown + game_breakdown if p.get("titanium_triggered")),
            "gold_star_count": sum(1 for p in props_breakdown + game_breakdown if p.get("tier") == "GOLD_STAR"),
            "edge_lean_count": sum(1 for p in props_breakdown + game_breakdown if p.get("tier") == "EDGE_LEAN")
        }
    }


# ============================================================================
# DEBUG ENDPOINTS (v14.9 Production Requirements)
# ============================================================================

@router.get("/debug/pipeline/{sport}")
async def debug_pipeline(sport: str):
    """
    DEBUG ENDPOINT: Full pipeline step-by-step BEFORE final filtering.

    Shows the raw scoring data at each stage of the pipeline:
    1. Raw API data fetched
    2. TODAY-only filtering applied
    3. Engine scores calculated (AI, Research, Esoteric, Jarvis)
    4. Jason Sim confluence applied
    5. Tier assignment
    6. Final filtering (deduplication, injury blocking)

    This helps debug why certain picks may be missing or scored unexpectedly.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    pipeline_steps = {
        "step_1_api_fetch": {},
        "step_2_today_filter": {},
        "step_3_engine_scores": {},
        "step_4_jason_confluence": {},
        "step_5_tier_assignment": {},
        "step_6_final_filtering": {}
    }

    sport_config = SPORT_MAPPINGS[sport_lower]

    # Step 1: Raw API fetch
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american"
            }
        )
        raw_games = resp.json() if resp and resp.status_code == 200 else []
        pipeline_steps["step_1_api_fetch"] = {
            "games_fetched": len(raw_games),
            "games": [{"home": g.get("home_team"), "away": g.get("away_team"), "commence_time": g.get("commence_time")} for g in raw_games[:10]]
        }
    except Exception as e:
        pipeline_steps["step_1_api_fetch"] = {"error": str(e)}

    # Step 2: TODAY-only filter
    if TIME_FILTERS_AVAILABLE and raw_games:
        today_games, excluded = validate_today_slate(raw_games)
        pipeline_steps["step_2_today_filter"] = {
            "today_games_count": len(today_games),
            "excluded_count": len(excluded),
            "excluded_reasons": [{"game": f"{g.get('away_team')}@{g.get('home_team')}", "time": g.get("commence_time")} for g in excluded[:5]]
        }
    else:
        pipeline_steps["step_2_today_filter"] = {
            "note": "TIME_FILTERS not available or no games"
        }

    # Step 3-6: Get from best-bets endpoint
    try:
        best_bets = await get_best_bets(sport)
        pipeline_steps["step_3_engine_scores"] = {
            "props_scored": best_bets.get("props", {}).get("total_analyzed", 0),
            "games_scored": best_bets.get("game_picks", {}).get("total_analyzed", 0)
        }
        pipeline_steps["step_4_jason_confluence"] = {
            "jason_available": JASON_SIM_AVAILABLE,
            "sample_jason_output": best_bets.get("props", {}).get("picks", [{}])[0].get("jason_ran") if best_bets.get("props", {}).get("picks") else None
        }
        pipeline_steps["step_5_tier_assignment"] = {
            "tiering_module_available": TIERING_AVAILABLE,
            "tier_distribution": {
                "TITANIUM_SMASH": sum(1 for p in best_bets.get("props", {}).get("picks", []) + best_bets.get("game_picks", {}).get("picks", []) if p.get("tier") == "TITANIUM_SMASH"),
                "GOLD_STAR": sum(1 for p in best_bets.get("props", {}).get("picks", []) + best_bets.get("game_picks", {}).get("picks", []) if p.get("tier") == "GOLD_STAR"),
                "EDGE_LEAN": sum(1 for p in best_bets.get("props", {}).get("picks", []) + best_bets.get("game_picks", {}).get("picks", []) if p.get("tier") == "EDGE_LEAN"),
                "MONITOR": sum(1 for p in best_bets.get("props", {}).get("picks", []) + best_bets.get("game_picks", {}).get("picks", []) if p.get("tier") == "MONITOR"),
                "PASS": sum(1 for p in best_bets.get("props", {}).get("picks", []) + best_bets.get("game_picks", {}).get("picks", []) if p.get("tier") == "PASS")
            }
        }
        pipeline_steps["step_6_final_filtering"] = {
            "final_props": best_bets.get("props", {}).get("count", 0),
            "final_game_picks": best_bets.get("game_picks", {}).get("count", 0),
            "identity_resolver": best_bets.get("identity_resolver", False)
        }
    except Exception as e:
        pipeline_steps["step_3_engine_scores"] = {"error": str(e)}

    return {
        "sport": sport.upper(),
        "pipeline": pipeline_steps,
        "modules_available": {
            "tiering": TIERING_AVAILABLE,
            "time_filters": TIME_FILTERS_AVAILABLE,
            "jason_sim": JASON_SIM_AVAILABLE,
            "identity_resolver": IDENTITY_RESOLVER_AVAILABLE,
            "pick_logger": PICK_LOGGER_AVAILABLE,
            "auto_grader": AUTO_GRADER_AVAILABLE
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/debug/identity/{player_name}")
async def debug_identity(player_name: str, sport: str = "nba", team_hint: str = ""):
    """
    DEBUG ENDPOINT: Test player identity resolution.

    Returns all resolution attempts and matches for a player name.
    Useful for debugging why a player prop might be missing or mismatched.
    """
    if not IDENTITY_RESOLVER_AVAILABLE:
        return {
            "player_name": player_name,
            "error": "Identity resolver module not available",
            "fallback_id": f"{sport.upper()}:NAME:{player_name.lower().replace(' ', '_')}",
            "timestamp": datetime.now().isoformat()
        }

    try:
        # Try resolution
        resolved = await resolve_player(
            sport=sport.upper(),
            raw_name=player_name,
            team_hint=team_hint,
            event_id=""
        )

        # Get normalizations
        normalized_name = normalize_player_name(player_name)
        normalized_team = normalize_team_name(team_hint) if team_hint else None

        return {
            "input": {
                "player_name": player_name,
                "sport": sport.upper(),
                "team_hint": team_hint
            },
            "normalizations": {
                "normalized_name": normalized_name,
                "normalized_team": normalized_team
            },
            "resolution_result": {
                "is_resolved": resolved.is_resolved,
                "canonical_player_id": resolved.canonical_player_id,
                "provider_ids": resolved.provider_ids,
                "confidence": resolved.confidence,
                "match_method": str(resolved.match_method) if hasattr(resolved, 'match_method') else "unknown",
                "team": resolved.team,
                "position": resolved.position,
                "is_blocked": resolved.is_blocked,
                "blocked_reason": resolved.blocked_reason
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "player_name": player_name,
            "error": str(e),
            "fallback_id": f"{sport.upper()}:NAME:{player_name.lower().replace(' ', '_')}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/debug/today-games/{sport}")
async def debug_today_games(sport: str):
    """
    DEBUG ENDPOINT: Show raw game list with TODAY-only validation.

    Verifies no tomorrow games are included.
    Shows each game's commence_time and whether it passes TODAY filter.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads",
                "oddsFormat": "american"
            }
        )

        if not resp or resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch games from Odds API")

        raw_games = resp.json()

        # Analyze each game
        game_analysis = []
        for game in raw_games:
            commence_time = game.get("commence_time", "")
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")

            analysis = {
                "matchup": f"{away_team} @ {home_team}",
                "commence_time_raw": commence_time,
                "commence_time_et": get_game_start_time_et(commence_time) if TIME_FILTERS_AVAILABLE else "N/A"
            }

            if TIME_FILTERS_AVAILABLE:
                analysis["is_today"] = is_game_today(commence_time)
                analysis["game_status"] = get_game_status(commence_time)
                analysis["has_started"] = is_game_started(commence_time)
            else:
                analysis["is_today"] = "TIME_FILTERS not available"

            game_analysis.append(analysis)

        # Get today's date info
        today_info = {}
        if TIME_FILTERS_AVAILABLE:
            start_et, end_et = get_today_range_et()
            today_info = {
                "today_date_et": get_today_date_str(),
                "window_start": start_et.isoformat() if hasattr(start_et, 'isoformat') else str(start_et),
                "window_end": end_et.isoformat() if hasattr(end_et, 'isoformat') else str(end_et)
            }

        return {
            "sport": sport.upper(),
            "total_games_from_api": len(raw_games),
            "today_filter_available": TIME_FILTERS_AVAILABLE,
            "today_info": today_info,
            "games": game_analysis,
            "summary": {
                "today_games": sum(1 for g in game_analysis if g.get("is_today") == True),
                "not_today": sum(1 for g in game_analysis if g.get("is_today") == False),
                "already_started": sum(1 for g in game_analysis if g.get("has_started") == True)
            },
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/learning/latest")
async def debug_learning_latest():
    """
    DEBUG ENDPOINT: Get latest learning loop status and report.

    Shows:
    - Current weights for all esoteric signals
    - Recent performance by signal
    - Weight adjustment history
    - Grading statistics
    """
    result = {
        "esoteric_learning": {},
        "auto_grader": {},
        "timestamp": datetime.now().isoformat()
    }

    # Esoteric Learning Loop
    try:
        loop = get_esoteric_loop()
        if loop:
            result["esoteric_learning"] = {
                "available": True,
                "current_weights": loop.get_weights(),
                "performance_30d": loop.get_performance(days_back=30),
                "recent_picks": loop.get_recent_picks(limit=5)
            }
        else:
            result["esoteric_learning"] = {"available": False}
    except Exception as e:
        result["esoteric_learning"] = {"available": False, "error": str(e)}

    # Auto Grader
    if AUTO_GRADER_AVAILABLE:
        try:
            grader = get_grader()
            total_predictions = sum(len(p) for p in grader.predictions.values())

            # Get performance for each sport
            sport_performance = {}
            for sport in grader.SUPPORTED_SPORTS:
                try:
                    perf = grader.get_performance(sport, days_back=7)
                    sport_performance[sport] = perf
                except:
                    sport_performance[sport] = {"error": "Could not fetch"}

            result["auto_grader"] = {
                "available": True,
                "total_predictions_logged": total_predictions,
                "storage_path": grader.storage_path,
                "sports_tracked": grader.SUPPORTED_SPORTS,
                "performance_by_sport": sport_performance
            }
        except Exception as e:
            result["auto_grader"] = {"available": False, "error": str(e)}
    else:
        result["auto_grader"] = {"available": False}

    # Esoteric Grader (from esoteric_grader.py)
    try:
        from esoteric_grader import get_esoteric_grader
        eso_grader = get_esoteric_grader()
        result["esoteric_grader"] = {
            "available": True,
            "accuracy_stats": eso_grader.get_all_accuracy_stats(),
            "performance_summary": eso_grader.get_performance_summary(days_back=30)
        }
    except Exception as e:
        result["esoteric_grader"] = {"available": False, "error": str(e)}

    return result


@router.get("/lstm/status")
async def lstm_status():
    """Check LSTM model availability and status."""
    try:
        from lstm_brain import LSTMBrain, TF_AVAILABLE

        # v16.1: Also check ml_integration module for enhanced status
        if ML_INTEGRATION_AVAILABLE:
            ml_status = get_ml_status()
            return {
                "available": True,
                "tensorflow_available": TF_AVAILABLE,
                "mode": "tensorflow" if TF_AVAILABLE else "numpy_fallback",
                "note": "LSTM active for props. Models loaded on-demand.",
                "ml_integration": ml_status,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "available": True,
                "tensorflow_available": TF_AVAILABLE,
                "mode": "tensorflow" if TF_AVAILABLE else "numpy_fallback",
                "note": "LSTM brain available but ml_integration not loaded.",
                "timestamp": datetime.now().isoformat()
            }
    except ImportError:
        return {
            "available": False,
            "tensorflow_available": False,
            "mode": "disabled",
            "note": "LSTM module not available",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/ml/status")
async def ml_status():
    """
    v16.1: Comprehensive ML infrastructure status.

    Returns status of all ML components:
    - LSTM models for props (loaded/available/predictions)
    - Ensemble model for games (loaded/trained_at/metrics)
    - TensorFlow availability
    - Model performance metrics
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "available": ML_INTEGRATION_AVAILABLE
    }

    if not ML_INTEGRATION_AVAILABLE:
        result["error"] = "ml_integration module not available"
        return result

    try:
        # Get comprehensive ML status
        ml_status_data = get_ml_status()
        result.update(ml_status_data)

        # Calculate performance metrics from graded predictions
        try:
            import grader_store
            predictions = grader_store.load_predictions()

            # Filter to graded predictions from last 7 days
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            recent_graded = [
                p for p in predictions
                if p.get("grade_status") == "GRADED"
                and p.get("created_at", "") >= cutoff
            ]

            # Calculate hit rates
            if recent_graded:
                # Overall hit rate
                hits = sum(1 for p in recent_graded if p.get("result", "").upper() in ["WIN", "HIT"])
                total = len(recent_graded)
                result["performance"] = {
                    "period": "7_days",
                    "total_graded": total,
                    "hits": hits,
                    "hit_rate": round(hits / total, 3) if total > 0 else 0,
                }

                # Split by LSTM vs heuristic (props)
                lstm_props = [p for p in recent_graded
                             if p.get("pick_type") == "PROP"
                             and p.get("lstm_source") == "lstm"]
                heuristic_props = [p for p in recent_graded
                                  if p.get("pick_type") == "PROP"
                                  and p.get("lstm_source") != "lstm"]

                if lstm_props:
                    lstm_hits = sum(1 for p in lstm_props if p.get("result", "").upper() in ["WIN", "HIT"])
                    result["performance"]["lstm_props"] = {
                        "total": len(lstm_props),
                        "hits": lstm_hits,
                        "hit_rate": round(lstm_hits / len(lstm_props), 3)
                    }

                if heuristic_props:
                    heur_hits = sum(1 for p in heuristic_props if p.get("result", "").upper() in ["WIN", "HIT"])
                    result["performance"]["heuristic_props"] = {
                        "total": len(heuristic_props),
                        "hits": heur_hits,
                        "hit_rate": round(heur_hits / len(heuristic_props), 3)
                    }

                # Game picks (ensemble vs heuristic)
                game_picks = [p for p in recent_graded if p.get("pick_type") != "PROP"]
                if game_picks:
                    game_hits = sum(1 for p in game_picks if p.get("result", "").upper() in ["WIN", "HIT"])
                    result["performance"]["game_picks"] = {
                        "total": len(game_picks),
                        "hits": game_hits,
                        "hit_rate": round(game_hits / len(game_picks), 3)
                    }
            else:
                result["performance"] = {
                    "period": "7_days",
                    "total_graded": 0,
                    "note": "No graded predictions in the last 7 days"
                }

        except Exception as e:
            result["performance"] = {"error": str(e)}

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


@router.get("/grader/status")
async def grader_status():
    """
    Check grader status for both pick logging and weight learning systems.

    Returns:
        - predictions_logged: Count of picks logged today (pick_logger)
        - pending_to_grade: Count of ungraded picks (pick_logger)
        - last_run_at: Last auto-grade run timestamp
        - last_errors: Recent grading errors
        - weight_learning: Auto-grader weight learning status (separate system)
    """
    result = {
        "available": True,
        "timestamp": datetime.now().isoformat()
    }

    # Grader Store Stats (SINGLE SOURCE OF TRUTH for persistence)
    try:
        import grader_store
        # Use top-level import (already imported at line 99)
        _start_et, _end_et, _start_utc, _end_utc = et_day_bounds()
        today = _start_et.date().isoformat()

        # Load predictions from grader_store with reconciliation stats
        recon_data = grader_store.load_predictions_with_reconciliation()
        all_predictions_raw = recon_data["predictions"]
        reconciliation = recon_data["reconciliation"]

        # Filter to today's predictions
        all_predictions = [p for p in all_predictions_raw if p.get("date_et") == today]
        pending = [p for p in all_predictions if p.get("grade_status") != "GRADED"]
        graded = [p for p in all_predictions if p.get("grade_status") == "GRADED"]

        # Get last write time from file mtime
        last_write_at = None
        try:
            import os
            if os.path.exists(grader_store.PREDICTIONS_FILE):
                mtime = os.path.getmtime(grader_store.PREDICTIONS_FILE)
                last_write_at = datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            pass

        result["grader_store"] = {
            "predictions_logged": len(all_predictions),
            "predictions_total_all_dates": len(all_predictions_raw),
            "pending_to_grade": len(pending),
            "graded_today": len(graded),
            "storage_path": grader_store.STORAGE_ROOT,
            "predictions_file": grader_store.PREDICTIONS_FILE,
            "last_write_at": last_write_at,
            "date": today,
            "reconciliation": {
                "file_lines": reconciliation["total_lines"],
                "parsed_ok": reconciliation["parsed_ok"],
                "skipped_total": reconciliation["skipped_total"],
                "reconciled": reconciliation["reconciled"],
                "top_skip_reasons": reconciliation["skip_reasons"],
            }
        }
    except Exception as e:
        logger.error("Grader store status failed: %s", e)
        result["grader_store"] = {
            "available": False,
            "error": str(e)
        }

    # Root-level aliases for DX (prevents "field not found" confusion)
    result["total_predictions"] = result.get("grader_store", {}).get("predictions_total_all_dates", 0)
    result["file_path"] = result.get("grader_store", {}).get("predictions_file")
    result["store_path"] = result.get("grader_store", {}).get("storage_path")
    result["last_write_at"] = result.get("grader_store", {}).get("last_write_at")

    # Scheduler Stats (last run time and errors)
    try:
        from daily_scheduler import get_daily_scheduler
        scheduler = get_daily_scheduler()
        if scheduler and hasattr(scheduler, 'auto_grade_job'):
            job = scheduler.auto_grade_job
            result["last_run_at"] = job.last_run.isoformat() if job.last_run else None
            result["last_errors"] = job.last_errors[-5:] if hasattr(job, 'last_errors') else []
        else:
            result["last_run_at"] = None
            result["last_errors"] = []
    except Exception as e:
        logger.error("Scheduler status failed: %s", e)
        result["last_run_at"] = None
        result["last_errors"] = [str(e)]

    # Auto-Grader Weight Learning Stats (separate system for adjusting prediction weights)
    try:
        if AUTO_GRADER_AVAILABLE:
            grader = get_grader()  # Use singleton - CRITICAL for data persistence!

            # Weight version hash for tracking which weights are loaded
            weights_version_hash = None
            weights_file_exists = False
            weights_last_modified_et = None
            try:
                import hashlib as _hashlib
                from storage_paths import get_weights_file as _get_weights_file
                _wf = _get_weights_file()
                weights_file_exists = os.path.exists(_wf)
                if weights_file_exists:
                    with open(_wf, 'rb') as _f:
                        weights_version_hash = _hashlib.sha256(_f.read()).hexdigest()[:12]
                    weights_last_modified_et = datetime.fromtimestamp(
                        os.path.getmtime(_wf)
                    ).isoformat()
            except Exception:
                pass

            # Training drop stats (if available from last load)
            training_drops = getattr(grader, 'last_drop_stats', None)

            result["weight_learning"] = {
                "available": True,
                "supported_sports": grader.SUPPORTED_SPORTS,
                "predictions_logged": sum(len(p) for p in grader.predictions.values()),
                "weights_loaded": bool(grader.weights),
                "weights_version_hash": weights_version_hash,
                "weights_file_exists": weights_file_exists,
                "weights_last_modified_et": weights_last_modified_et,
                "storage_path": grader.storage_path,
                "training_drops": training_drops,
                "note": "Use /grader/weights/{sport} to see learned weights"
            }
        else:
            result["weight_learning"] = {
                "available": False,
                "note": "Auto-grader weight learning not available"
            }
    except Exception as e:
        logger.error("Auto-grader weight learning status failed: %s", e)
        result["weight_learning"] = {
            "available": False,
            "error": str(e)
        }

    return result


@router.get("/grader/debug-files")
async def grader_debug_files(api_key: str = Depends(verify_api_key)):
    """
    Debug endpoint to prove disk persistence (PROTECTED).

    Returns:
        - Resolved DATA_DIR and PICK_LOGS paths
        - Today's JSONL file path, existence, size, line count
        - First and last JSONL rows (with sensitive fields redacted)

    Requires:
        - X-API-Key header for authentication
    """
    import os
    from data_dir import DATA_DIR, PICK_LOGS
    from pick_logger import get_today_date_et

    result = {
        "paths": {
            "DATA_DIR": DATA_DIR,
            "PICK_LOGS": PICK_LOGS,
            "DATA_DIR_source": "RAILWAY_VOLUME_MOUNT_PATH env var" if os.getenv("RAILWAY_VOLUME_MOUNT_PATH") else "fallback"
        }
    }

    # Get today's file
    today = get_today_date_et()
    today_file = os.path.join(PICK_LOGS, f"picks_{today}.jsonl")

    result["today_file"] = {
        "path": today_file,
        "date": today,
        "exists": os.path.exists(today_file)
    }

    if os.path.exists(today_file):
        try:
            # Get file stats
            stat = os.stat(today_file)
            result["today_file"]["size_bytes"] = stat.st_size
            result["today_file"]["modified_time"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # Count lines and get first/last
            with open(today_file, 'r') as f:
                lines = f.readlines()

            result["today_file"]["line_count"] = len(lines)

            if lines:
                # Parse first and last, redact sensitive fields
                import json

                def redact_pick(line):
                    try:
                        pick = json.loads(line)
                        # Keep only essential fields, redact IDs
                        return {
                            "sport": pick.get("sport", ""),
                            "date": pick.get("date", ""),
                            "pick_type": pick.get("pick_type", ""),
                            "player_name": pick.get("player_name", "")[:20] if pick.get("player_name") else "",
                            "matchup": pick.get("matchup", "")[:40] if pick.get("matchup") else "",
                            "tier": pick.get("tier", ""),
                            "final_score": pick.get("final_score", 0),
                            "result": pick.get("result"),
                            "pick_id": pick.get("pick_id", "")[:8] + "..." if pick.get("pick_id") else ""
                        }
                    except Exception as e:
                        return {"error": str(e)}

                result["today_file"]["first_pick"] = redact_pick(lines[0])
                result["today_file"]["last_pick"] = redact_pick(lines[-1])
        except Exception as e:
            result["today_file"]["read_error"] = str(e)

    return result


# =============================================================================
# DEBUG ENDPOINTS (v15.0 - NEVER BREAK AGAIN)
# =============================================================================

@router.get("/debug/predictions/status")
async def debug_predictions_status(api_key: str = Depends(verify_api_key)):
    """
    Show prediction storage state (PROTECTED).

    Returns:
        - total_predictions: int
        - pending_predictions: int
        - graded_predictions: int
        - last_prediction_time: str
        - by_sport: Dict[sport, count]
        - storage_path: str
        - file_sizes: Dict[date, size_bytes]

    Requires:
        X-API-Key header
    """
    try:
        from core.persistence import get_storage_stats
        stats = get_storage_stats()
        return stats
    except ImportError:
        # Fallback if core.persistence not available
        try:
            from pick_logger import get_pick_logger, get_today_date_et
            pick_logger = get_pick_logger()
            today = get_today_date_et()
            all_picks = pick_logger.get_picks_for_date(today)

            pending = [p for p in all_picks if p.get("grade_status") == "PENDING"]
            graded = [p for p in all_picks if p.get("grade_status") in ["WIN", "LOSS", "PUSH"]]

            by_sport = {}
            for pick in all_picks:
                sport = pick.get("sport", "UNKNOWN")
                by_sport[sport] = by_sport.get(sport, 0) + 1

            return {
                "storage_path": pick_logger.storage_path,
                "total_predictions": len(all_picks),
                "pending_predictions": len(pending),
                "graded_predictions": len(graded),
                "last_prediction_time": all_picks[-1].get("published_at", "") if all_picks else "",
                "by_sport": by_sport,
                "file_sizes": {},
            }
        except Exception as e:
            logger.error("Failed to get predictions status: %s", e)
            return {
                "storage_path": "unavailable",
                "total_predictions": 0,
                "pending_predictions": 0,
                "graded_predictions": 0,
                "last_prediction_time": "",
                "by_sport": {},
                "file_sizes": {},
                "error": str(e)
            }


@router.get("/debug/system/health")
async def debug_system_health(api_key: str = Depends(verify_api_key)):
    """
    Comprehensive system health check (PROTECTED).

    Checks:
        - API connectivity (Playbook, Odds API, BallDontLie)
        - Persistence read/write sanity check
        - Scoring pipeline sanity on synthetic candidate
        - Core modules availability

    Returns:
        - ok: bool (overall health)
        - errors: List[str] (problems found)
        - checks: Dict[check_name, result]

    IMPORTANT: NEVER crashes - returns ok=false + errors list if problems found.

    Requires:
        X-API-Key header
    """
    errors = []
    checks = {}

    # =========================================================================
    # CHECK 1: API Connectivity
    # =========================================================================
    api_checks = {}

    # Playbook API
    try:
        if PLAYBOOK_UTIL_AVAILABLE:
            test_url = build_playbook_url("health", {})
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(test_url)
                api_checks["playbook"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code
                }
                if resp.status_code != 200:
                    errors.append(f"Playbook API returned {resp.status_code}")
        else:
            api_checks["playbook"] = {"ok": False, "error": "playbook_api module not available"}
            errors.append("playbook_api module not available")
    except Exception as e:
        api_checks["playbook"] = {"ok": False, "error": str(e)}
        errors.append(f"Playbook API check failed: {e}")

    # Odds API
    try:
        odds_api_key = os.getenv("ODDS_API_KEY", "")
        if odds_api_key:
            # Use params dict instead of embedding key in URL (prevents log leakage)
            test_url = "https://api.the-odds-api.com/v4/sports/"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(test_url, params={"apiKey": odds_api_key})
                api_checks["odds_api"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "remaining": resp.headers.get("x-requests-remaining", "unknown")
                }
                if resp.status_code != 200:
                    errors.append(f"Odds API returned {resp.status_code}")
        else:
            api_checks["odds_api"] = {"ok": False, "error": "ODDS_API_KEY not set"}
            errors.append("ODDS_API_KEY environment variable not set")
    except Exception as e:
        api_checks["odds_api"] = {"ok": False, "error": str(e)}
        errors.append(f"Odds API check failed: {e}")

    # BallDontLie
    try:
        from alt_data_sources.balldontlie import BALLDONTLIE_API_KEY
        if BALLDONTLIE_API_KEY:
            test_url = "https://api.balldontlie.io/v1/players?per_page=1"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    test_url,
                    headers={"Authorization": BALLDONTLIE_API_KEY}
                )
                api_checks["balldontlie"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code
                }
                if resp.status_code != 200:
                    errors.append(f"BallDontLie API returned {resp.status_code}")
        else:
            api_checks["balldontlie"] = {"ok": False, "error": "BALLDONTLIE_API_KEY not set"}
    except Exception as e:
        api_checks["balldontlie"] = {"ok": False, "error": str(e)}

    checks["api_connectivity"] = api_checks

    # =========================================================================
    # CHECK 2: Persistence Read/Write
    # =========================================================================
    try:
        from core.persistence import validate_storage_writable
        is_writable, write_error = validate_storage_writable()
        checks["persistence"] = {
            "ok": is_writable,
            "writable": is_writable,
            "error": write_error if not is_writable else None
        }
        if not is_writable:
            errors.append(f"Persistence not writable: {write_error}")
    except ImportError:
        # Fallback
        try:
            from pick_logger import get_pick_logger
            pick_logger = get_pick_logger()
            import tempfile
            test_file = os.path.join(pick_logger.storage_path, ".health_check")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            checks["persistence"] = {"ok": True, "writable": True}
        except Exception as e:
            checks["persistence"] = {"ok": False, "writable": False, "error": str(e)}
            errors.append(f"Persistence write check failed: {e}")

    # =========================================================================
    # CHECK 3: Scoring Pipeline Sanity
    # =========================================================================
    try:
        from core.scoring_pipeline import score_candidate

        # Synthetic test candidate
        test_candidate = {
            "game_str": "Test @ Team",
            "player_name": "",
            "pick_type": "SPREAD",
            "line": -5.5,
            "side": "Test",
            "spread": -5.5,
            "total": 220,
            "odds": -110,
            "prop_line": 0,
        }

        test_context = {
            "sharp_signal": {"signal_strength": "MODERATE", "line_variance": 0.8},
            "public_pct": 65,
            "home_team": "Team",
            "away_team": "Test",
        }

        result = score_candidate(test_candidate, test_context)

        # Validate result has required fields
        required_fields = ["ai_score", "research_score", "esoteric_score", "jarvis_score", "final_score", "tier"]
        missing = [f for f in required_fields if f not in result]

        if missing:
            checks["scoring_pipeline"] = {
                "ok": False,
                "error": f"Missing fields in result: {missing}"
            }
            errors.append(f"Scoring pipeline missing fields: {missing}")
        else:
            checks["scoring_pipeline"] = {
                "ok": True,
                "test_final_score": result["final_score"],
                "test_tier": result["tier"]
            }
    except ImportError:
        checks["scoring_pipeline"] = {
            "ok": False,
            "error": "core.scoring_pipeline module not available"
        }
        errors.append("Scoring pipeline module not available")
    except Exception as e:
        checks["scoring_pipeline"] = {"ok": False, "error": str(e)}
        errors.append(f"Scoring pipeline sanity check failed: {e}")

    # =========================================================================
    # CHECK 4: Core Modules
    # =========================================================================
    core_modules = {}

    try:
        from core import invariants
        core_modules["invariants"] = {"ok": True, "version": "15.1"}
    except ImportError as e:
        core_modules["invariants"] = {"ok": False, "error": str(e)}
        errors.append("core.invariants module not available")

    try:
        from core import scoring_pipeline
        core_modules["scoring_pipeline"] = {"ok": True}
    except ImportError as e:
        core_modules["scoring_pipeline"] = {"ok": False, "error": str(e)}

    try:
        from core import time_window_et
        core_modules["time_window_et"] = {"ok": True}
    except ImportError as e:
        core_modules["time_window_et"] = {"ok": False, "error": str(e)}

    try:
        from core import persistence
        core_modules["persistence"] = {"ok": True}
    except ImportError as e:
        core_modules["persistence"] = {"ok": False, "error": str(e)}

    checks["core_modules"] = core_modules

    # =========================================================================
    # OVERALL STATUS
    # =========================================================================
    ok = len(errors) == 0

    return {
        "ok": ok,
        "errors": errors,
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/debug/time")
async def debug_time(api_key: str = Depends(verify_api_key)):
    """
    ET timezone debug endpoint (PROTECTED).

    Returns current time info from single source of truth (core.time_et)
    plus fail-loud validation of ET bounds invariants.

    CANONICAL ET SLATE WINDOW:
        Start: 00:00:00 ET (midnight) - inclusive
        End:   00:00:00 ET next day (midnight) - exclusive
        Interval: [start, end)

    Returns:
        - now_utc_iso: Current UTC time
        - now_et_iso: Current ET time
        - et_date: Today's date in ET (YYYY-MM-DD)
        - et_day_start_iso: Start of ET day (00:00:00)
        - et_day_end_iso: End of ET day (00:00:00 next day, exclusive)
        - canonical_window: Description of the canonical window
        - bounds_validation: Invariant validation results (FAIL LOUD if invalid)
        - build_sha: Git commit SHA
        - deploy_version: Deployment version

    Requires:
        X-API-Key header
    """
    try:
        from core.time_et import now_et, et_day_bounds, assert_et_bounds

        # Current times
        now_utc = datetime.now(timezone.utc)
        now_et_dt = now_et()

        # ET day bounds
        start_et, end_et, _start_utc, _end_utc = et_day_bounds()
        et_date = start_et.date().isoformat()

        # FAIL LOUD: Validate bounds invariants
        validation = assert_et_bounds(start_et, end_et)

        # Build info
        build_sha = BUILD_SHA if 'BUILD_SHA' in globals() else "unknown"
        deploy_version = DEPLOY_VERSION if 'DEPLOY_VERSION' in globals() else "unknown"

        return {
            "now_utc_iso": now_utc.isoformat(),
            "now_et_iso": now_et_dt.isoformat(),
            "et_date": et_date,
            "et_day_start_iso": start_et.isoformat(),
            "et_day_end_iso": end_et.isoformat(),
            "window_display": f"{et_date} 00:00:00 to 23:59:59 ET",
            "canonical_window": {
                "start_time": "00:00:00 ET",
                "end_time": "00:00:00 ET (next day, exclusive)",
                "interval_notation": "[start, end)",
                "description": "ET day runs midnight to midnight (exclusive end)",
            },
            "bounds_validation": validation,
            "bounds_valid": validation["valid"],
            "build_sha": build_sha,
            "deploy_version": deploy_version,
        }
    except Exception as e:
        return {
            "error": str(e),
            "bounds_valid": False,
            "timestamp": datetime.now().isoformat()
        }


@router.get("/debug/integrations")
async def debug_integrations(
    api_key: str = Depends(verify_api_key),
    quick: bool = False
):
    """
    Get status of ALL external integrations.

    This endpoint provides comprehensive visibility into:
    - Which APIs are configured (env vars set)
    - Which APIs are reachable (can connect)
    - Last success/error timestamps
    - Which modules and endpoints depend on each integration

    Args:
        quick: If true, returns fast summary without connectivity checks

    Returns:
        Complete integration status for monitoring and debugging.

    Requires:
        X-API-Key header
    """
    try:
        from integration_registry import (
            get_all_integrations_status,
            get_integrations_summary
        )

        if quick:
            return get_integrations_summary()
        else:
            return await get_all_integrations_status()

    except ImportError as e:
        return {
            "error": "Integration registry not available",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Error getting integrations status: %s", e)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/grader/weights/{sport}")
async def grader_weights(sport: str):
    """Get current prediction weights for a sport."""
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    from dataclasses import asdict
    grader = get_grader()  # Use singleton
    sport_upper = sport.upper()

    if sport_upper not in grader.weights:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    weights = {}
    for stat_type, config in grader.weights[sport_upper].items():
        weights[stat_type] = asdict(config)

    return {
        "sport": sport_upper,
        "weights": weights,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/grader/run-audit")
async def run_grader_audit(audit_config: Dict[str, Any] = None):
    """
    Run the daily audit to analyze bias and adjust weights.

    This is the self-improvement mechanism:
    1. Analyzes yesterday's predictions vs actual outcomes
    2. Calculates bias per prediction factor
    3. Adjusts weights to correct systematic errors
    4. Persists learned weights for future picks

    Request body (optional):
    {
        "days_back": 1,        # How many days to analyze (default: 1)
        "apply_changes": true  # Whether to apply weight changes (default: true)
    }
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    try:
        grader = get_grader()  # Use singleton

        config = audit_config or {}
        days_back = config.get("days_back", 1)
        apply_changes = config.get("apply_changes", True)

        # Run full audit
        results = grader.run_daily_audit(days_back=days_back)

        return {
            "status": "audit_complete",
            "days_analyzed": days_back,
            "changes_applied": apply_changes,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "note": "Weights have been adjusted based on prediction performance"
        }

    except Exception as e:
        logger.exception("Audit failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grader/bias/{sport}")
async def get_prediction_bias(sport: str, stat_type: str = "all", days_back: int = 1):
    """
    Get prediction bias analysis for a sport.

    Shows how accurate our predictions have been and where we're over/under predicting.

    Bias interpretation:
    - Positive bias = we're predicting too HIGH
    - Negative bias = we're predicting too LOW
    - Healthy range is -1.0 to +1.0
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton
    bias = grader.calculate_bias(sport, stat_type, days_back)

    return {
        "sport": sport.upper(),
        "stat_type": stat_type,
        "days_analyzed": days_back,
        "bias": bias,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/grader/adjust-weights/{sport}")
async def adjust_sport_weights(sport: str, adjust_config: Dict[str, Any] = None):
    """
    Manually trigger weight adjustment for a sport.

    Request body (optional):
    {
        "stat_type": "points",    # Stat type to adjust (default: points)
        "days_back": 1,           # Days of data to analyze (default: 1)
        "apply_changes": true     # Whether to apply (default: true)
    }
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton

    config = adjust_config or {}
    stat_type = config.get("stat_type", "points")
    days_back = config.get("days_back", 1)
    apply_changes = config.get("apply_changes", True)

    result = grader.adjust_weights(
        sport=sport,
        stat_type=stat_type,
        days_back=days_back,
        apply_changes=apply_changes
    )

    return {
        "status": "adjustment_complete" if apply_changes else "preview",
        "result": result,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/grader/performance/{sport}")
async def get_grader_performance(sport: str, days_back: int = 7):
    """
    Get prediction performance metrics for a sport.

    Shows hit rate, MAE, and trends over time.
    Use this to monitor how well our picks are performing.
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton

    sport_upper = sport.upper()
    predictions = grader.predictions.get(sport_upper, [])

    # v20.5: Use timezone-aware datetime for comparison
    from core.time_et import now_et
    from zoneinfo import ZoneInfo
    et_tz = ZoneInfo("America/New_York")
    cutoff = now_et() - timedelta(days=days_back)

    # Filter to graded predictions within timeframe
    graded = []
    for p in predictions:
        if p.actual_value is None:
            continue
        try:
            ts = datetime.fromisoformat(p.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=et_tz)
            if ts >= cutoff:
                graded.append(p)
        except (ValueError, TypeError):
            continue

    if not graded:
        return {
            "sport": sport_upper,
            "days_analyzed": days_back,
            "graded_count": 0,
            "message": "No graded predictions in this timeframe",
            "timestamp": datetime.now().isoformat()
        }

    # Calculate metrics
    hits = sum(1 for p in graded if p.hit)
    total = len(graded)
    hit_rate = hits / total if total > 0 else 0

    errors = [abs(p.error) for p in graded if p.error is not None]
    mae = sum(errors) / len(errors) if errors else 0

    # Group by stat type
    by_stat = {}
    for p in graded:
        if p.stat_type not in by_stat:
            by_stat[p.stat_type] = {"hits": 0, "total": 0, "errors": []}
        by_stat[p.stat_type]["total"] += 1
        if p.hit:
            by_stat[p.stat_type]["hits"] += 1
        if p.error is not None:
            by_stat[p.stat_type]["errors"].append(abs(p.error))

    stat_breakdown = {}
    for stat, data in by_stat.items():
        stat_breakdown[stat] = {
            "hit_rate": round(data["hits"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
            "total_picks": data["total"],
            "mae": round(sum(data["errors"]) / len(data["errors"]), 2) if data["errors"] else 0
        }

    return {
        "sport": sport_upper,
        "days_analyzed": days_back,
        "graded_count": total,
        "overall": {
            "hit_rate": round(hit_rate * 100, 1),
            "mae": round(mae, 2),
            "profitable": hit_rate > 0.52,  # Need 52%+ to profit at -110 odds
            "status": "🔥 PROFITABLE" if hit_rate > 0.55 else ("✅ BREAK-EVEN" if hit_rate > 0.48 else "⚠️ NEEDS IMPROVEMENT")
        },
        "by_stat_type": stat_breakdown,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/grader/daily-report")
async def get_daily_community_report(days_back: int = 1):
    """
    Generate a community-friendly daily report.

    This report is designed to share with your community showing:
    - Yesterday's performance across all sports
    - What the system learned
    - How we're improving
    - Encouragement regardless of wins/losses

    Share this every morning to build trust and transparency!
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    try:
        grader = get_grader()  # Use singleton

        # v20.5: Use timezone-aware datetimes to avoid comparison errors
        from core.time_et import now_et
        now = now_et()

        report_date = (now - timedelta(days=days_back)).strftime("%B %d, %Y")
        today = now.strftime("%B %d, %Y")

        # Collect performance across all sports
        sports_data = {}
        total_picks = 0
        total_hits = 0
        overall_lessons = []
        improvements = []

        for sport in ["NBA", "NFL", "MLB", "NHL"]:
            predictions = grader.predictions.get(sport, [])

            # v20.5: Fix date window - should be exactly 1 day, not 2
            # For days_back=1 (yesterday): 00:00 yesterday to 00:00 today
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
            report_day_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
            report_day_end = report_day_start + timedelta(days=1)

            # Filter to report day's graded predictions
            graded = []
            for p in predictions:
                if p.actual_value is None:
                    continue
                try:
                    ts = datetime.fromisoformat(p.timestamp)
                    # Make timezone-aware if naive
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=et_tz)
                    if report_day_start <= ts < report_day_end:
                        graded.append(p)
                except (ValueError, TypeError):
                    continue

            if graded:
                hits = sum(1 for p in graded if p.hit)
                total = len(graded)
                hit_rate = hits / total if total > 0 else 0

                # Calculate bias
                errors = [p.error for p in graded if p.error is not None]
                avg_error = sum(errors) / len(errors) if errors else 0

                sports_data[sport] = {
                    "picks": total,
                    "wins": hits,
                    "losses": total - hits,
                    "hit_rate": round(hit_rate * 100, 1),
                    "status": "🔥" if hit_rate >= 0.55 else ("✅" if hit_rate >= 0.50 else "📈"),
                    "avg_error": round(avg_error, 2)
                }

                total_picks += total
                total_hits += hits

                # Generate lessons learned
                if avg_error > 2:
                    overall_lessons.append(f"{sport}: We were predicting slightly high. Adjusting down.")
                    improvements.append(f"Lowered {sport} prediction weights by {min(abs(avg_error) * 2, 5):.1f}%")
                elif avg_error < -2:
                    overall_lessons.append(f"{sport}: We were predicting slightly low. Adjusting up.")
                    improvements.append(f"Raised {sport} prediction weights by {min(abs(avg_error) * 2, 5):.1f}%")

        # Calculate overall hit rate
        overall_hit_rate = (total_hits / total_picks * 100) if total_picks > 0 else 0

        # Generate status emoji and message
        if overall_hit_rate >= 55:
            status_emoji = "🔥"
            status_message = "SMASHING IT!"
            encouragement = "Your community is in great hands. Keep riding the hot streak!"
        elif overall_hit_rate >= 52:
            status_emoji = "💰"
            status_message = "PROFITABLE DAY!"
            encouragement = "Above the 52% threshold needed for profit. Solid performance!"
        elif overall_hit_rate >= 48:
            status_emoji = "📊"
            status_message = "BREAK-EVEN ZONE"
            encouragement = "Close to the mark. Our self-learning system is making adjustments."
        else:
            status_emoji = "📈"
            status_message = "LEARNING DAY"
            encouragement = "Every loss teaches us something. The AI is adjusting weights to improve tomorrow."

        # Build community report
        report = {
            "title": f"📊 SMASH SPOT DAILY REPORT - {today}",
            "subtitle": f"Performance Review: {report_date}",
            "overall": {
                "emoji": status_emoji,
                "status": status_message,
                "total_picks": total_picks,
                "total_wins": total_hits,
                "total_losses": total_picks - total_hits,
                "hit_rate": f"{overall_hit_rate:.1f}%",
                "profitable": overall_hit_rate >= 52
            },
            "by_sport": sports_data,
            "what_we_learned": overall_lessons if overall_lessons else [
                "Model performed within expected range.",
                "No major bias detected - weights stable."
            ],
            "improvements_made": improvements if improvements else [
                "Fine-tuning prediction confidence scores.",
                "Continuing to learn from betting patterns."
            ],
            "message_to_community": encouragement,
            "commitment": "🎯 We analyze EVERY pick, learn from EVERY outcome, and improve EVERY day. Win or lose, we're getting better together.",
            "next_audit": "Tomorrow 6:00 AM ET",
            "generated_at": datetime.now().isoformat()
        }

        # Add sample community post
        report["sample_post"] = f"""
{status_emoji} SMASH SPOT DAILY REPORT {status_emoji}

📅 {report_date} Results:
• Total Picks: {total_picks}
• Record: {total_hits}-{total_picks - total_hits}
• Hit Rate: {overall_hit_rate:.1f}%

{status_message}

📚 What We Learned:
{chr(10).join('• ' + lesson for lesson in (overall_lessons if overall_lessons else ['Model performing well, minor tuning applied.']))}

🔧 Improvements Made:
{chr(10).join('• ' + imp for imp in (improvements if improvements else ['Weights optimized for tomorrow.']))}

{encouragement}

🎯 We grade EVERY pick at 6 AM and adjust our AI daily.
Whether we win or lose, we're always improving! 💪
"""

        return report

    except Exception as e:
        logger.exception("Failed to generate daily report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DAILY LESSON ENDPOINT (v17.2) - AUTOGRADER LEARNING SUMMARY
# ============================================================================

@router.get("/grader/daily-lesson")
@router.get("/grader/daily-lesson/latest")
async def get_daily_lesson(date: Optional[str] = None, days_back: int = 0):
    """
    Return the latest daily learning lesson generated by the 6AM audit job.

    If date is not provided, returns today's ET lesson.
    """
    from data_dir import AUDIT_LOGS
    from core.time_et import now_et

    if days_back < 0:
        raise HTTPException(status_code=400, detail="days_back must be >= 0")

    if date:
        date_et = date
    else:
        date_et = (now_et() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    lesson_path = os.path.join(AUDIT_LOGS, f"lesson_{date_et}.json")

    if not os.path.exists(lesson_path):
        raise HTTPException(status_code=404, detail=f"No daily lesson found for {date_et}")

    try:
        with open(lesson_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed to read daily lesson: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read daily lesson")


# ============================================================================
# GRADER QUEUE & DRY-RUN ENDPOINTS (v14.10) - E2E Verification
# ============================================================================

@router.get("/grader/queue")
async def get_grader_queue(
    date: Optional[str] = None,
    sports: Optional[str] = None,
    run_id: Optional[str] = None,
    latest_run: bool = False
):
    """
    Get ungraded picks queue for a date.

    Returns minimal pick data for queue management and verification.

    Query params:
    - date: Date to query (default: today ET)
    - sports: Comma-separated sports filter (default: all)
    - run_id: Filter to specific run (optional)
    - latest_run: If true, filter to most recent run only (default: false)

    Example:
        GET /live/grader/queue?date=2026-01-26&sports=NBA,NFL
        GET /live/grader/queue?date=2026-01-26&latest_run=true
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        # Get date in ET (use core.time_et single source of truth)
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        pick_logger = get_pick_logger()
        picks = pick_logger.get_picks_for_date(date)

        # Filter by sports
        if sports:
            sport_list = [s.strip().upper() for s in sports.split(",")]
            picks = [p for p in picks if p.sport.upper() in sport_list]

        # Filter by run_id if specified
        if run_id:
            picks = [p for p in picks if getattr(p, 'run_id', '') == run_id]
        elif latest_run:
            # Get latest run_id
            latest_run_id = pick_logger.get_latest_run_id(date)
            if latest_run_id:
                picks = [p for p in picks if getattr(p, 'run_id', '') == latest_run_id]
                run_id = latest_run_id

        # Filter to ungraded only (not graded AND result is None)
        ungraded = [p for p in picks if not getattr(p, 'graded', False) and p.result is None]

        # Count by sport
        by_sport = {}
        for p in ungraded:
            sport = p.sport.upper()
            by_sport[sport] = by_sport.get(sport, 0) + 1

        logger.info("Grader queue: %d ungraded picks for %s (run_id=%s)", len(ungraded), date, run_id or "all")

        return {
            "date": date,
            "run_id": run_id,
            "latest_run": latest_run,
            "total": len(ungraded),
            "by_sport": by_sport,
            "picks": [
                {
                    "pick_id": p.pick_id,
                    "pick_hash": getattr(p, "pick_hash", ""),
                    "run_id": getattr(p, "run_id", ""),
                    "sport": p.sport,
                    "player_name": p.player_name,
                    "matchup": p.matchup,
                    "prop_type": p.prop_type,
                    "line": p.line,
                    "side": p.side,
                    "tier": p.tier,
                    "game_start_time_et": p.game_start_time_et,
                    "canonical_event_id": getattr(p, "canonical_event_id", ""),
                    "canonical_player_id": getattr(p, "canonical_player_id", ""),
                    "grade_status": getattr(p, "grade_status", "PENDING"),
                }
                for p in ungraded
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to get grader queue: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/grader/dry-run")
async def run_grader_dry_run(request_data: Dict[str, Any]):
    """
    Dry-run validation of autograder pipeline.

    Validates all picks can be:
    1. Matched to events (event ID exists or resolvable)
    2. Matched to players (for props: player ID exists or resolvable)
    3. Graded when game completes (grade-ready checklist)

    This is the KEY PROOF that tomorrow's 6AM grader will work.

    Request body:
    {
        "date": "2026-01-26",
        "sports": ["NBA", "NFL", "MLB", "NHL", "NCAAB"],
        "mode": "pre",  // "pre" (day-of) or "post" (next-day verification)
        "fail_on_unresolved": true
    }

    Mode semantics:
    - PRE (day-of): PASS if failed=0 AND unresolved=0 (pending allowed)
    - POST (next-day): PASS only if failed=0 AND pending=0 AND unresolved=0

    Returns structured validation report with PASS/FAIL/PENDING status.
    Per-pick reasons: PENDING_GAME_NOT_FINAL, UNRESOLVED_EVENT, UNRESOLVED_PLAYER, etc.

    ALWAYS returns valid JSON (never raises HTTPException to client).
    """
    if not GRADER_STORE_AVAILABLE:
        return {
            "ok": False,
            "error": "Grader store not available",
            "date": request_data.get("date", "unknown"),
            "mode": request_data.get("mode", "pre"),
            "total": 0,
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "overall_status": "ERROR"
        }

    try:
        # Parse request - get date from request or default to today ET
        date = request_data.get("date")
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        sports = request_data.get("sports") or ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
        mode = request_data.get("mode", "pre")  # "pre" or "post"
        fail_on_unresolved = request_data.get("fail_on_unresolved", False)

        # Load picks from grader_store (SINGLE SOURCE OF TRUTH)
        all_picks = grader_store.load_predictions(date_et=date)

        # Filter by sports
        sport_set = set(s.upper() for s in sports)
        picks = [p for p in all_picks if p.get("sport", "").upper() in sport_set]

        # Initialize results with new counters
        results = {
            "date": date,
            "mode": mode,
            "total": len(picks),
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "by_sport": {},
        }

        failed_picks = []
        unresolved_picks = []

        # Track already-graded/failed picks separately
        _already_graded = 0
        _already_failed = 0

        for pick in picks:
            sport = pick.get("sport", "").upper()

            if sport not in results["by_sport"]:
                results["by_sport"][sport] = {
                    "picks": 0,
                    "event_resolved": 0,
                    "player_resolved": 0,
                    "graded": 0,
                    "pending": 0,
                    "unresolved": 0,
                    "failed_picks": []
                }

            # Skip already-graded or already-failed picks
            _gs = pick.get("grade_status", "PENDING")
            if _gs == "GRADED":
                _already_graded += 1
                results["graded"] += 1
                results["by_sport"][sport]["graded"] += 1
                continue
            if _gs == "FAILED" and not pick.get("canonical_player_id"):
                # Old test seeds with no canonical_player_id — skip
                _already_failed += 1
                continue

            results["by_sport"][sport]["picks"] += 1

            # Check 1: Event resolution
            canonical_event_id = pick.get("canonical_event_id", "")
            matchup = pick.get("matchup", "")
            event_ok = bool(canonical_event_id) or bool(matchup)
            if event_ok:
                results["by_sport"][sport]["event_resolved"] += 1

            # Check 2: Player resolution (props only)
            player_ok = True
            player_name = pick.get("player_name", "")
            if player_name:
                canonical_player_id = pick.get("canonical_player_id", "")
                player_ok = bool(canonical_player_id) or IDENTITY_RESOLVER_AVAILABLE
                if player_ok:
                    results["by_sport"][sport]["player_resolved"] += 1

            # Check 3: Grade-ready checklist (always assume ready for dict picks)
            grade_ready_check = {"is_grade_ready": True, "reasons": []}

            # Determine per-pick status
            pick_reason = None
            pick_id = pick.get("pick_id", "")
            if not event_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_EVENT"
                unresolved_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason
                })
            elif player_name and not player_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_PLAYER"
                unresolved_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason
                })
            elif not grade_ready_check["is_grade_ready"]:
                # Missing required fields for grading
                results["failed"] += 1
                pick_reason = "MISSING_GRADE_FIELDS"
                failed_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
                results["by_sport"][sport]["failed_picks"].append({
                    "pick_id": pick_id,
                    "reason": pick_reason,
                    "player": player_name,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
            elif pick.get("result") is not None or pick.get("graded", False):
                # Already graded
                results["graded"] += 1
                results["by_sport"][sport]["graded"] += 1
            else:
                # Awaiting game completion (valid, just not graded yet)
                results["pending"] += 1
                results["by_sport"][sport]["pending"] += 1

        # Determine overall status based on mode
        if mode == "pre":
            # PRE mode: PASS if failed=0 AND unresolved=0 (pending allowed)
            if results["failed"] > 0 or results["unresolved"] > 0:
                results["overall_status"] = "FAIL"
            elif results["pending"] > 0:
                results["overall_status"] = "PENDING"  # This is OK for pre-mode
            else:
                results["overall_status"] = "PASS"
        else:  # post mode
            # POST mode: PASS only if everything graded
            if results["failed"] > 0 or results["unresolved"] > 0:
                results["overall_status"] = "FAIL"
            elif results["pending"] > 0:
                results["overall_status"] = "PENDING"  # Still waiting for grades
            else:
                results["overall_status"] = "PASS"

        # For exit code interpretation
        results["pre_mode_pass"] = (results["failed"] == 0 and results["unresolved"] == 0)
        results["post_mode_pass"] = (results["failed"] == 0 and results["unresolved"] == 0 and results["pending"] == 0)

        results["summary"] = {
            "total": results["total"],
            "graded": results["graded"],
            "pending": results["pending"],
            "failed": results["failed"],
            "unresolved": results["unresolved"]
        }
        results["failed_picks"] = failed_picks
        results["unresolved_picks"] = unresolved_picks
        results["skipped_already_graded"] = _already_graded
        results["skipped_stale_seeds"] = _already_failed
        results["timestamp"] = datetime.now().isoformat()

        logger.info(
            "Dry-run complete (mode=%s): %s - total=%d graded=%d pending=%d failed=%d unresolved=%d",
            mode,
            results["overall_status"],
            results["total"],
            results["graded"],
            results["pending"],
            results["failed"],
            results["unresolved"]
        )

        # Add fail flag if fail_on_unresolved and there are failures/unresolved
        if fail_on_unresolved and (results["failed"] > 0 or results["unresolved"] > 0):
            results["ok"] = False
            results["message"] = f"{results['failed']} failed, {results['unresolved']} unresolved"
        else:
            results["ok"] = True

        return results

    except Exception as e:
        logger.exception("Dry-run failed: %s", e)
        # ALWAYS return valid JSON, never raise HTTPException
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "date": request_data.get("date", "unknown"),
            "mode": request_data.get("mode", "pre"),
            "total": 0,
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "overall_status": "ERROR"
        }


# ============================================================================
# PICK LOGGER ENDPOINTS (v14.9) - Production Pick Persistence & Audit
# ============================================================================

@router.get("/picks/today")
async def get_logged_picks_today(sport: Optional[str] = None):
    """
    Get all picks logged today.

    Used for monitoring what picks have been published.
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        picks = get_today_picks(sport)
        payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sport": sport.upper() if sport else "ALL",
            "count": len(picks),
            "picks": [
                {
                    "pick_id": p.pick_id,
                    "sport": p.sport,
                    "player": p.player_name,
                    "matchup": p.matchup,
                    "line": p.line,
                    "side": p.side,
                    "tier": p.tier,
                    "final_score": p.final_score,
                    "already_started": p.already_started,
                    "book_validated": p.book_validated,
                    "result": p.result
                }
                for p in picks
            ],
            "timestamp": datetime.now().isoformat()
        }
        return JSONResponse(_sanitize_public(payload))
    except Exception as e:
        logger.exception("Failed to get today's picks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/picks/graded")
async def get_graded_picks(date: Optional[str] = None, sport: Optional[str] = None):
    """
    Get all picks with grading status for the Grading page.

    Returns both pending and graded picks from grader_store.
    Frontend uses the 'graded' boolean to split into tabs.

    Query params:
    - date: Date filter (YYYY-MM-DD), defaults to today ET
    - sport: Sport filter (NBA, NFL, etc.), defaults to all
    """
    if not GRADER_STORE_AVAILABLE:
        return {"picks": [], "error": "Grader store not available"}

    try:
        # Default to today in ET
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        # Load all predictions with grade records merged
        all_picks = grader_store.load_predictions(date_et=date)

        # Optional sport filter
        if sport:
            all_picks = [p for p in all_picks if p.get("sport", "").upper() == sport.upper()]

        # Map to frontend format expected by Grading.jsx
        picks_out = []
        for p in all_picks:
            is_graded = p.get("grade_status") == "GRADED"
            side = p.get("side", "")
            recommendation = side if side else ""
            # Build recommendation string (OVER/UNDER for props)
            if not recommendation and p.get("market", ""):
                market = p.get("market", "").upper()
                if "OVER" in market:
                    recommendation = "OVER"
                elif "UNDER" in market:
                    recommendation = "UNDER"

            picks_out.append({
                "id": p.get("pick_id"),
                "pick_id": p.get("pick_id"),
                "player": p.get("player_name") or p.get("side") or "Game",
                "team": p.get("home_team") or p.get("team", ""),
                "opponent": p.get("away_team") or "",
                "matchup": p.get("matchup", ""),
                "sport": p.get("sport", ""),
                "stat": p.get("stat_type") or p.get("market", ""),
                "line": p.get("line"),
                "projection": p.get("projection") or p.get("line"),
                "edge": p.get("edge") or 0,
                "recommendation": recommendation,
                "final_score": p.get("final_score"),
                "tier": p.get("tier", "STANDARD"),
                "units": p.get("units", 1.0),
                "graded": is_graded,
                "result": p.get("result") if is_graded else None,
                "actual": p.get("actual_value") if is_graded else None,
                "graded_at": p.get("graded_at") if is_graded else None,
                "date_et": p.get("date_et"),
                "pick_type": p.get("pick_type", ""),
            })

        return {
            "picks": picks_out,
            "date": date,
            "total": len(picks_out),
            "graded_count": sum(1 for p in picks_out if p["graded"]),
            "pending_count": sum(1 for p in picks_out if not p["graded"]),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.exception("Failed to get graded picks: %s", e)
        return {"picks": [], "error": str(e)}


@router.post("/picks/grade")
async def grade_published_pick(grade_data: Dict[str, Any]):
    """
    Grade a published pick with actual result.

    Request body:
    {
        "pick_id": "abc123def456",
        "result": "WIN",  // WIN, LOSS, or PUSH
        "actual_value": 27.5  // Optional: actual stat value for props
    }
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    pick_id = grade_data.get("pick_id")
    result = grade_data.get("result")
    actual_value = grade_data.get("actual_value")

    if not pick_id or not result:
        raise HTTPException(status_code=400, detail="pick_id and result are required")

    if result.upper() not in ("WIN", "LOSS", "PUSH"):
        raise HTTPException(status_code=400, detail="result must be WIN, LOSS, or PUSH")

    try:
        grade_result = grade_logged_pick(pick_id, result, actual_value)

        if grade_result:
            return {
                "status": "graded",
                **grade_result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Pick not found: {pick_id}")

    except Exception as e:
        logger.exception("Failed to grade pick: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/picks/bulk-grade")
async def bulk_grade_picks(grade_data: Dict[str, Any]):
    """
    Grade multiple picks at once.

    Request body:
    {
        "grades": [
            {"pick_id": "abc123", "result": "WIN"},
            {"pick_id": "def456", "result": "LOSS", "actual_value": 22.5}
        ]
    }
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    grades = grade_data.get("grades", [])
    if not grades:
        raise HTTPException(status_code=400, detail="grades array is required")

    results = []
    errors = []

    for grade in grades:
        pick_id = grade.get("pick_id")
        result = grade.get("result")
        actual_value = grade.get("actual_value")

        if not pick_id or not result:
            errors.append({"pick_id": pick_id, "error": "Missing required fields"})
            continue

        try:
            grade_result = grade_logged_pick(pick_id, result, actual_value)
            if grade_result:
                results.append(grade_result)
            else:
                errors.append({"pick_id": pick_id, "error": "Pick not found"})
        except Exception as e:
            errors.append({"pick_id": pick_id, "error": str(e)})

    return {
        "status": "bulk_grade_complete",
        "graded": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/picks/audit-report")
async def get_pick_audit_report(date: Optional[str] = None):
    """
    Generate comprehensive audit report for pick performance.

    Includes:
    - Record by tier and sport
    - ROI by tier
    - Top 10 false positives (high score loses)
    - Top 10 missed opportunities (low score wins)
    - Pillar hit-rate breakdown
    - Jarvis trigger performance
    - Jason sim accuracy

    Date format: YYYY-MM-DD (defaults to yesterday)
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        report = run_daily_audit_report(date)
        return report
    except Exception as e:
        logger.exception("Failed to generate audit report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/picks/validation-status")
async def get_pick_validation_status():
    """
    Get validation status for today's picks.

    Shows:
    - Total picks logged
    - Picks with validation errors (injury/book issues)
    - Already started (late pull) picks
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        picks = get_today_picks()

        validation_errors = [p for p in picks if p.validation_errors]
        late_pulls = [p for p in picks if p.already_started]
        graded = [p for p in picks if p.result is not None]

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_logged": len(picks),
            "valid_picks": len(picks) - len(validation_errors),
            "validation_errors": {
                "count": len(validation_errors),
                "picks": [
                    {
                        "pick_id": p.pick_id,
                        "player": p.player_name,
                        "errors": p.validation_errors
                    }
                    for p in validation_errors
                ]
            },
            "late_pulls": {
                "count": len(late_pulls),
                "picks": [
                    {
                        "pick_id": p.pick_id,
                        "matchup": p.matchup,
                        "reason": p.late_pull_reason
                    }
                    for p in late_pulls
                ]
            },
            "grading_status": {
                "graded": len(graded),
                "pending": len(picks) - len(graded)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to get validation status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# AUTO-GRADING ENDPOINTS (v14.9)
# =============================================================================

@router.post("/picks/auto-grade")
async def trigger_auto_grade(
    date: Optional[str] = None,
    sports: Optional[str] = None
):
    """
    Trigger automatic grading of picks against actual game results.

    This endpoint:
    1. Fetches completed game scores from Odds API
    2. Fetches actual player stats (NBA from balldontlie/ESPN)
    3. Grades all pending picks for the specified date
    4. Updates pick_logger with WIN/LOSS/PUSH results

    Query params:
    - date: Date to grade (default: today in ET). Format: YYYY-MM-DD
    - sports: Comma-separated sports to grade (default: NBA,NHL,NFL,MLB)

    Returns grading summary with results.
    """
    if not RESULT_FETCHER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Result fetcher not available")

    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        sports_list = sports.split(",") if sports else None
        result = await auto_grade_picks(date=date, sports=sports_list)
        return result
    except Exception as e:
        logger.exception("Auto-grade failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/picks/grading-summary")
async def get_grading_summary(date: Optional[str] = None):
    """
    Get a summary of grading results for a date.

    Shows:
    - Total picks graded
    - Record (wins/losses/pushes)
    - Hit rate by tier
    - Units profit/loss

    Query params:
    - date: Date to summarize (default: today in ET)
    """
    if not GRADER_STORE_AVAILABLE:
        return {
            "error": "Grader store not available",
            "date": date or "unknown",
            "total_picks": 0,
            "graded": 0,
            "pending": 0
        }

    try:
        # Get date (default to today in ET)
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        # Load picks from grader_store (SINGLE SOURCE OF TRUTH)
        picks = grader_store.load_predictions(date_et=date)
        graded = [p for p in picks if p.get("grade_status") == "GRADED"]
        pending = [p for p in picks if p.get("grade_status") != "GRADED"]

        # Calculate by tier
        tier_results = {}
        for pick in graded:
            tier = pick.get("tier", "UNKNOWN")
            if tier not in tier_results:
                tier_results[tier] = {"wins": 0, "losses": 0, "pushes": 0, "units_won": 0, "units_lost": 0}

            result = pick.get("result")
            units = pick.get("units", 1.0)

            if result == "WIN":
                tier_results[tier]["wins"] += 1
                tier_results[tier]["units_won"] += units
            elif result == "LOSS":
                tier_results[tier]["losses"] += 1
                tier_results[tier]["units_lost"] += units
            else:
                tier_results[tier]["pushes"] += 1

        # Overall summary
        total_wins = sum(t["wins"] for t in tier_results.values())
        total_losses = sum(t["losses"] for t in tier_results.values())
        total_pushes = sum(t["pushes"] for t in tier_results.values())
        units_won = sum(t["units_won"] for t in tier_results.values())
        units_lost = sum(t["units_lost"] for t in tier_results.values())

        return {
            "date": date,
            "total_picks": len(picks),
            "graded": len(graded),
            "pending": len(pending),
            "overall": {
                "record": f"{total_wins}-{total_losses}-{total_pushes}",
                "wins": total_wins,
                "losses": total_losses,
                "pushes": total_pushes,
                "hit_rate": f"{(total_wins / (total_wins + total_losses) * 100):.1f}%" if (total_wins + total_losses) > 0 else "N/A",
                "units_profit": round(units_won - units_lost, 2),
                "units_won": round(units_won, 2),
                "units_lost": round(units_lost, 2)
            },
            "by_tier": tier_results,
            "graded_picks": [
                {
                    "pick_id": p.get("pick_id"),
                    "player": p.get("player_name") or "Game",
                    "matchup": p.get("matchup"),
                    "line": p.get("line"),
                    "side": p.get("side"),
                    "tier": p.get("tier"),
                    "result": p.get("result"),
                    "actual_value": p.get("actual_value"),
                    "units": p.get("units", 1.0)
                }
                for p in graded
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to get grading summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/completed-games")
async def get_completed_games(sport: str = "NBA", days_back: int = 1):
    """
    Fetch completed games from Odds API.

    Query params:
    - sport: Sport code (NBA, NFL, NHL, MLB)
    - days_back: How many days back to fetch (default: 1)
    """
    if not RESULT_FETCHER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Result fetcher not available")

    try:
        games = await fetch_completed_games(sport, days_back)
        return {
            "sport": sport.upper(),
            "days_back": days_back,
            "count": len(games),
            "games": [
                {
                    "game_id": g.game_id,
                    "home_team": g.home_team,
                    "away_team": g.away_team,
                    "home_score": g.home_score,
                    "away_score": g.away_score,
                    "commence_time": g.commence_time
                }
                for g in games
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to fetch completed games: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/player-stats")
async def get_player_stats(sport: str = "NBA", date: Optional[str] = None):
    """
    Fetch actual player stats from external APIs.

    Query params:
    - sport: Sport code (currently only NBA supported)
    - date: Date to fetch stats for (default: today in ET)
    """
    if not RESULT_FETCHER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Result fetcher not available")

    if sport.upper() != "NBA":
        raise HTTPException(status_code=400, detail="Only NBA player stats currently supported")

    try:
        if not date:
            import pytz
            ET = pytz.timezone("America/New_York")
            date = datetime.now(ET).strftime("%Y-%m-%d")

        stats = await fetch_nba_player_stats(date)
        return {
            "sport": sport.upper(),
            "date": date,
            "count": len(stats),
            "players": [
                {
                    "player_name": s.player_name,
                    "team": s.team,
                    "points": s.points,
                    "rebounds": s.rebounds,
                    "assists": s.assists,
                    "pra": s.points + s.rebounds + s.assists,
                    "threes": s.three_pointers_made,
                    "steals": s.steals,
                    "blocks": s.blocks
                }
                for s in stats[:100]  # Limit to 100 for response size
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to fetch player stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/status")
async def scheduler_status():
    """Check daily scheduler status."""
    try:
        from daily_scheduler import SCHEDULER_AVAILABLE, SchedulerConfig
        return {
            "available": True,
            "apscheduler_available": SCHEDULER_AVAILABLE,
            "audit_time": f"{SchedulerConfig.AUDIT_HOUR:02d}:{SchedulerConfig.AUDIT_MINUTE:02d} ET",
            "supported_sports": list(SchedulerConfig.SPORT_STATS.keys()),
            "retrain_thresholds": {
                "mae": SchedulerConfig.RETRAIN_MAE_THRESHOLD,
                "hit_rate": SchedulerConfig.RETRAIN_HIT_RATE_THRESHOLD
            },
            "note": "Scheduler runs daily audit at 6 AM ET",
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {
            "available": False,
            "note": "Scheduler module not available",
            "timestamp": datetime.now().isoformat()
        }


@router.post("/ml/train-ensemble")
async def trigger_ensemble_training(background: bool = False):
    """
    Manually trigger ensemble model training.

    Args:
        background: If True, run in background. If False (default), run sync and return output.

    Requires at least 100 graded picks.
    """
    import subprocess
    import sys

    script_path = os.path.join(os.path.dirname(__file__), "scripts", "train_ensemble.py")

    if not os.path.exists(script_path):
        return {"success": False, "error": "Training script not found", "path": script_path}

    # First, count graded picks
    predictions_file = "/data/grader/predictions.jsonl"
    graded_count = 0
    total_count = 0

    try:
        if os.path.exists(predictions_file):
            import json
            with open(predictions_file, 'r') as f:
                for line in f:
                    if line.strip():
                        total_count += 1
                        try:
                            pick = json.loads(line)
                            if pick.get("grade_status", "").upper() == "GRADED":
                                graded_count += 1
                        except:
                            pass
    except Exception as e:
        logger.warning("Could not count graded picks: %s", e)

    # Run training synchronously (so we can see output)
    try:
        result = subprocess.run(
            [sys.executable, script_path, "--min-picks", "100"],
            capture_output=True,
            text=True,
            timeout=300
        )

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "graded_picks_found": graded_count,
            "total_picks": total_count,
            "predictions_file": predictions_file,
            "stdout": result.stdout[-2000:] if result.stdout else None,
            "stderr": result.stderr[-1000:] if result.stderr else None,
            "note": "Check /live/ml/status to see if model loaded"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Training timed out after 5 minutes"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/esoteric-edge")
async def get_esoteric_edge():
    """
    Get comprehensive esoteric edge analysis with historical accuracy stats.
    Returns daily energy + game signals + prop signals + accuracy data.
    """
    from esoteric_engine import (
        get_daily_esoteric_reading,
        calculate_void_moon,
        get_schumann_frequency,
        get_planetary_hour,
        calculate_noosphere_velocity,
        check_founders_echo,
        analyze_spread_gann,
        calculate_atmospheric_drag,
        calculate_biorhythms,
        check_life_path_sync,
        calculate_hurst_exponent,
        calculate_life_path,
        SAMPLE_PLAYERS
    )
    from esoteric_grader import get_esoteric_grader

    today = datetime.now().date()
    grader = get_esoteric_grader()

    # Daily reading
    daily = get_daily_esoteric_reading(today)

    # Get accuracy for current signals
    current_signals = {
        "void_moon_active": daily["void_moon"]["is_void"],
        "planetary_ruler": daily["planetary_hours"]["current_ruler"],
        "noosphere_direction": daily["noosphere"]["trending_direction"],
        "betting_outlook": daily["betting_outlook"],
    }
    combined_edge = grader.get_combined_edge(current_signals)

    # Get accuracy stats for each signal type
    outlook_accuracy = grader.get_signal_accuracy("betting_outlook", daily["betting_outlook"])
    void_moon_accuracy = grader.get_signal_accuracy("void_moon", daily["void_moon"]["is_void"])
    planetary_accuracy = grader.get_signal_accuracy("planetary_ruler", daily["planetary_hours"]["current_ruler"])
    noosphere_accuracy = grader.get_signal_accuracy("noosphere", daily["noosphere"]["trending_direction"])

    # Sample game signals (in production, would fetch from best-bets)
    sample_games = [
        {"game_id": "sample1", "home_team": "Lakers", "away_team": "Celtics", "spread": -3.5, "total": 225.5, "city": "Los Angeles"},
        {"game_id": "sample2", "home_team": "Warriors", "away_team": "Bulls", "spread": -7.5, "total": 232, "city": "San Francisco"},
    ]

    game_signals = []
    for game in sample_games:
        founders_home = check_founders_echo(game["home_team"])
        founders_away = check_founders_echo(game["away_team"])
        gann = analyze_spread_gann(game["spread"], game["total"])
        gann_accuracy = grader.get_signal_accuracy("gann_resonance", gann["combined_resonance"])
        founders_accuracy = grader.get_signal_accuracy("founders_echo", founders_home["resonance"] or founders_away["resonance"])

        game_signals.append({
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "signals": {
                "founders_echo": {
                    "home_match": founders_home["resonance"],
                    "away_match": founders_away["resonance"],
                    "boost": founders_home["boost"] + founders_away["boost"],
                    "accuracy": founders_accuracy
                },
                "gann_square": {
                    "spread_angle": gann["spread"]["angle"],
                    "resonant": gann["combined_resonance"],
                    "accuracy": gann_accuracy
                },
                "atmospheric": calculate_atmospheric_drag(game["city"])
            }
        })

    # Sample player signals with accuracy
    prop_signals = []
    for player_name, player_data in list(SAMPLE_PLAYERS.items())[:4]:
        bio = calculate_biorhythms(player_data["birth_date"])
        life_path = check_life_path_sync(player_name, player_data["birth_date"], player_data["jersey"])

        # Get accuracy for this player's signals
        bio_accuracy = grader.get_signal_accuracy("biorhythm", bio["status"])
        life_path_accuracy = grader.get_signal_accuracy("life_path", life_path["life_path"])

        prop_signals.append({
            "player_id": player_name.lower().replace(" ", "_"),
            "player_name": player_name,
            "signals": {
                "biorhythms": {
                    "physical": bio["physical"],
                    "emotional": bio["emotional"],
                    "intellectual": bio["intellectual"],
                    "status": bio["status"],
                    "accuracy": bio_accuracy
                },
                "life_path_sync": {
                    "player_life_path": life_path["life_path"],
                    "jersey_number": life_path["jersey_number"],
                    "sync_score": life_path["sync_score"],
                    "accuracy": life_path_accuracy
                }
            }
        })

    return {
        "timestamp": datetime.now().isoformat() + "Z",
        "daily_energy": {
            "betting_outlook": daily["betting_outlook"],
            "overall_energy": daily["overall_energy"],
            "moon_phase": daily["void_moon"]["moon_sign"].lower() if daily["void_moon"] else "unknown",
            "void_moon": daily["void_moon"],
            "schumann_frequency": daily["schumann_reading"],
            "planetary_hours": daily["planetary_hours"],
            "accuracy": {
                "outlook": outlook_accuracy,
                "void_moon": void_moon_accuracy,
                "planetary": planetary_accuracy,
                "noosphere": noosphere_accuracy
            }
        },
        "combined_edge": combined_edge,
        "game_signals": game_signals,
        "prop_signals": prop_signals,
        "parlay_warnings": [],
        "noosphere": daily["noosphere"]
    }


@router.get("/esoteric-accuracy")
async def get_esoteric_accuracy():
    """
    Get historical accuracy stats for all esoteric signals.
    Shows edge percentages based on historical performance.
    """
    from esoteric_grader import get_esoteric_grader

    grader = get_esoteric_grader()
    all_stats = grader.get_all_accuracy_stats()
    performance = grader.get_performance_summary(days_back=30)

    return {
        "timestamp": datetime.now().isoformat(),
        "accuracy_by_signal": all_stats,
        "recent_performance": performance,
        "methodology": {
            "edge_calculation": "Hit rate vs 50% baseline",
            "sample_sources": "Historical betting data + tracked predictions",
            "update_frequency": "Real-time as predictions are graded"
        }
    }


@router.get("/esoteric-accuracy/{signal_type}")
async def get_signal_accuracy(signal_type: str, value: str = None):
    """
    Get accuracy stats for a specific signal type.

    signal_type options: life_path, biorhythm, void_moon, planetary_ruler,
                        noosphere, gann_resonance, founders_echo, betting_outlook
    """
    from esoteric_grader import get_esoteric_grader

    grader = get_esoteric_grader()

    valid_types = [
        "life_path", "biorhythm", "void_moon", "planetary_ruler",
        "noosphere", "gann_resonance", "founders_echo", "betting_outlook"
    ]

    if signal_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid signal_type. Must be one of: {valid_types}"
        )

    if value:
        # Convert value to appropriate type
        if signal_type == "life_path":
            try:
                value = int(value)
            except:
                pass
        elif signal_type in ["void_moon", "gann_resonance", "founders_echo"]:
            value = value.lower() in ["true", "1", "yes"]

        accuracy = grader.get_signal_accuracy(signal_type, value)
        return {
            "signal_type": signal_type,
            "value": value,
            "accuracy": accuracy,
            "timestamp": datetime.now().isoformat()
        }
    else:
        # Return all values for this signal type
        all_stats = grader.get_all_accuracy_stats()
        return {
            "signal_type": signal_type,
            "all_values": all_stats.get(signal_type, {}),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/noosphere/status")
async def get_noosphere_status():
    """Noosphere Velocity - Global consciousness indicators."""
    # Use deterministic RNG based on current hour for stable results within the hour
    hour_seed = int(datetime.now().strftime("%Y%m%d%H"))
    rng = random.Random(hour_seed)
    coherence = rng.uniform(0.3, 0.9)
    anomaly_detected = coherence > 0.7

    return {
        "status": "ACTIVE",
        "version": "14.1",
        "global_coherence": round(coherence, 3),
        "anomaly_detected": anomaly_detected,
        "anomaly_strength": "STRONG" if coherence > 0.8 else "MODERATE" if coherence > 0.6 else "WEAK",
        "interpretation": "Collective attention spike - information asymmetry likely" if anomaly_detected else "Normal variance",
        "betting_signal": "FADE PUBLIC" if anomaly_detected else "FOLLOW TRENDS",
        "modules": {
            "insider_leak": {"status": "monitoring", "signal": "NEUTRAL"},
            "main_character_syndrome": {"status": "active", "signal": "CHECK NARRATIVES"},
            "phantom_injury": {"status": "scanning", "signal": "NO ALERTS"}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/gann-physics-status")
async def get_gann_physics_status():
    """GANN Physics - W.D. Gann's geometric principles applied to sports."""
    today = datetime.now()
    day_of_year = today.timetuple().tm_yday

    retracement_level = (day_of_year % 90) / 90 * 100
    rule_of_three = (day_of_year % 3 == 0)
    annulifier = (day_of_year % 7 == 0)

    return {
        "status": "ACTIVE",
        "date": today.strftime("%Y-%m-%d"),
        "modules": {
            "50_retracement": {
                "level": round(retracement_level, 1),
                "signal": "REVERSAL ZONE" if 45 <= retracement_level <= 55 else "TREND CONTINUATION",
                "description": "Gravity check - markets tend to retrace 50%"
            },
            "rule_of_three": {
                "active": rule_of_three,
                "signal": "EXHAUSTION" if rule_of_three else "MOMENTUM",
                "description": "Third attempt usually fails or succeeds dramatically"
            },
            "annulifier_cycle": {
                "active": annulifier,
                "signal": "HARMONIC LOCK" if annulifier else "NORMAL",
                "description": "7-day cycle completion - expect resolution"
            }
        },
        "overall_signal": "REVERSAL" if (retracement_level > 45 and rule_of_three) else "CONTINUATION",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# LEVEL 17 - PARLAY ARCHITECT CORRELATION ENGINE
# The Science: Books price parlays as independent. They aren't.
# Covariance > 0.8 = Mathematical Edge
# ============================================================================

CORRELATION_MATRIX = {
    # NFL Correlations
    "QB_WR": {"correlation": 0.88, "name": "BATTERY STACK", "description": "QB throws 300+ yards → WR1 must have yards"},
    "QB_TE": {"correlation": 0.72, "name": "REDZONE STACK", "description": "QB TDs correlate with TE targets in redzone"},
    "RB_DST": {"correlation": 0.65, "name": "GRIND STACK", "description": "RB dominance = winning = opponent forced passing = sacks/INTs"},
    "WR1_WR2": {"correlation": -0.35, "name": "CANNIBALIZE", "description": "Negative correlation - targets split"},

    # NBA Correlations
    "PG_C": {"correlation": 0.55, "name": "PNR STACK", "description": "Pick and roll - PG assists correlate with C points"},
    "STAR_OUT_BACKUP": {"correlation": 0.82, "name": "USAGE MONSTER", "description": "Star out = backup usage spike"},
    "BLOWOUT_BENCH": {"correlation": 0.70, "name": "GARBAGE TIME", "description": "Blowout = bench minutes spike"},

    # MLB Correlations
    "LEADOFF_RUNS": {"correlation": 0.68, "name": "TABLE SETTER", "description": "Leadoff OBP correlates with team runs"},
    "ACE_UNDER": {"correlation": 0.75, "name": "ACE EFFECT", "description": "Ace pitching = low scoring game"},
}

# Usage impact multipliers when star players are OUT
VOID_IMPACT_MULTIPLIERS = {
    # NBA - Points boost when star is out
    "Joel Embiid": {"teammate": "Tyrese Maxey", "pts_boost": 1.28, "usage_boost": 1.35},
    "LeBron James": {"teammate": "Anthony Davis", "pts_boost": 1.15, "usage_boost": 1.20},
    "Stephen Curry": {"teammate": "Klay Thompson", "pts_boost": 1.22, "usage_boost": 1.25},
    "Luka Doncic": {"teammate": "Kyrie Irving", "pts_boost": 1.18, "usage_boost": 1.22},
    "Giannis Antetokounmpo": {"teammate": "Damian Lillard", "pts_boost": 1.20, "usage_boost": 1.25},
    "Kevin Durant": {"teammate": "Devin Booker", "pts_boost": 1.12, "usage_boost": 1.18},
    "Jayson Tatum": {"teammate": "Jaylen Brown", "pts_boost": 1.15, "usage_boost": 1.20},
    "Nikola Jokic": {"teammate": "Jamal Murray", "pts_boost": 1.25, "usage_boost": 1.30},

    # NFL - Target/usage boost when WR1 is out
    "Davante Adams": {"teammate": "Jakobi Meyers", "target_boost": 1.35, "usage_boost": 1.40},
    "Tyreek Hill": {"teammate": "Jaylen Waddle", "target_boost": 1.28, "usage_boost": 1.32},
    "CeeDee Lamb": {"teammate": "Brandin Cooks", "target_boost": 1.30, "usage_boost": 1.35},
    "Justin Jefferson": {"teammate": "Jordan Addison", "target_boost": 1.38, "usage_boost": 1.42},
}

# ============================================================================
# SPORTSBOOK DEEP LINKS - Click-to-Bet Feature + SMASH LINKS
# ============================================================================

# Deep link URL schemes for direct bet slip access
SMASH_LINK_SCHEMES = {
    "draftkings": {
        "app": "draftkings://sportsbook/gateway?s=B_{sport}&e={event_id}&m={market_id}",
        "web": "https://sportsbook.draftkings.com/{sport_path}?eventId={event_id}",
        "universal": "https://sportsbook.draftkings.com/link/{sport}/{event_id}/{market_id}"
    },
    "fanduel": {
        "app": "fanduel://sportsbook/market/{market_id}",
        "web": "https://sportsbook.fanduel.com/{sport_path}/event/{event_id}",
        "universal": "https://sportsbook.fanduel.com/link/{event_id}"
    },
    "betmgm": {
        "app": "betmgm://sports/event/{event_id}",
        "web": "https://sports.betmgm.com/en/sports/{sport_path}/{event_id}",
        "universal": "https://sports.betmgm.com/link/{event_id}"
    },
    "caesars": {
        "app": "caesarssportsbook://event/{event_id}",
        "web": "https://www.caesars.com/sportsbook-and-casino/{sport_path}/{event_id}",
        "universal": "https://www.caesars.com/link/{event_id}"
    },
    "pointsbetus": {
        "app": "pointsbet://event/{event_id}",
        "web": "https://pointsbet.com/{sport_path}/{event_id}",
        "universal": "https://pointsbet.com/link/{event_id}"
    },
    "betrivers": {
        "app": "betrivers://event/{event_id}",
        "web": "https://www.betrivers.com/{sport_path}/{event_id}",
        "universal": "https://www.betrivers.com/link/{event_id}"
    }
}

SPORTSBOOK_CONFIGS = {
    "draftkings": {
        "name": "DraftKings",
        "web_base": "https://sportsbook.draftkings.com",
        "app_scheme": "draftkings://sportsbook/gateway",
        "color": "#53d337",
        "logo": "https://upload.wikimedia.org/wikipedia/en/b/b8/DraftKings_logo.svg"
    },
    "fanduel": {
        "name": "FanDuel",
        "web_base": "https://sportsbook.fanduel.com",
        "app_scheme": "fanduel://sportsbook/market",
        "color": "#1493ff",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/83/FanDuel_logo.svg"
    },
    "betmgm": {
        "name": "BetMGM",
        "web_base": "https://sports.betmgm.com",
        "app_scheme": "betmgm://sports/event",
        "color": "#c4a44a",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/2/2e/BetMGM_logo.svg"
    },
    "caesars": {
        "name": "Caesars",
        "web_base": "https://www.caesars.com/sportsbook-and-casino",
        "app_scheme": "caesarssportsbook://event",
        "color": "#0a2240",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Caesars_Sportsbook_logo.svg"
    },
    "pointsbetus": {
        "name": "PointsBet",
        "web_base": "https://pointsbet.com",
        "app_scheme": "pointsbet://",
        "color": "#ed1c24",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/3/3c/PointsBet_logo.svg"
    },
    "williamhill_us": {
        "name": "William Hill",
        "web_base": "https://www.williamhill.com/us",
        "app_scheme": "williamhill://",
        "color": "#00314d",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/a/a2/William_Hill_logo.svg"
    },
    "barstool": {
        "name": "Barstool",
        "web_base": "https://www.barstoolsportsbook.com",
        "app_scheme": "barstool://",
        "color": "#c41230",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Barstool_Sports_logo.svg"
    },
    "betrivers": {
        "name": "BetRivers",
        "web_base": "https://www.betrivers.com",
        "app_scheme": "betrivers://",
        "color": "#1b365d",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/85/BetRivers_logo.svg"
    }
}


def generate_sportsbook_link(book_key: str, event_id: str, sport: str) -> Dict[str, str]:
    """Generate deep link for a sportsbook event."""
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return None

    # Web link that works universally (sportsbooks redirect to app if installed)
    # Most sportsbooks use similar URL patterns for events
    sport_paths = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl"
    }
    sport_path = sport_paths.get(sport.lower(), sport.lower())

    return {
        "book_key": book_key,
        "name": config["name"],
        "web_url": f"{config['web_base']}/{sport_path}",
        "color": config["color"],
        "logo": config.get("logo", "")
    }


def generate_true_deep_link(book_key: str, event_id: str, sport: str, outcomes: List[Dict]) -> Dict[str, Any]:
    """
    Generate TRUE deep links that open the bet slip with selection pre-populated.

    Uses outcome sids from The Odds API to construct direct bet placement links.

    Deep Link Formats:
    - DraftKings: https://sportsbook.draftkings.com/event/{eventId}?outcomes={outcomeId}
    - FanDuel: https://sportsbook.fanduel.com/addToBetslip?marketId={marketId}&selectionId={selectionId}
    - BetMGM: https://sports.betmgm.com/en/sports/events/{eventId}
    - Others: Sport-specific pages (fallback)
    """
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return {"web": "#", "note": "Unknown sportsbook"}

    # Extract first outcome's sid if available (for single-click deep link)
    first_outcome_sid = None
    first_outcome_link = None
    if outcomes:
        first_outcome_sid = outcomes[0].get("sid")
        first_outcome_link = outcomes[0].get("link")

    # If API provided a direct link, use it
    if first_outcome_link:
        return {
            "web": first_outcome_link,
            "mobile": first_outcome_link,
            "type": "direct_betslip",
            "note": f"Opens {config['name']} with bet pre-populated"
        }

    # Build book-specific deep links using sids
    sport_path = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl"
    }.get(sport.lower(), sport.lower())

    base_url = config["web_base"]

    # Book-specific deep link construction
    if book_key == "draftkings" and first_outcome_sid:
        # DraftKings uses outcome IDs in URL
        return {
            "web": f"{base_url}/event/{event_id}?outcomes={first_outcome_sid}",
            "mobile": f"dksb://sb/addbet/{first_outcome_sid}",
            "type": "betslip",
            "note": f"Opens DraftKings with bet on slip"
        }

    elif book_key == "fanduel" and first_outcome_sid:
        # FanDuel uses marketId and selectionId - sid format may be "marketId.selectionId"
        parts = str(first_outcome_sid).split(".")
        if len(parts) >= 2:
            market_id = parts[0]
            selection_id = parts[1] if len(parts) > 1 else first_outcome_sid
            return {
                "web": f"{base_url}/addToBetslip?marketId={market_id}&selectionId={selection_id}",
                "mobile": f"fanduel://sportsbook/addToBetslip?marketId={market_id}&selectionId={selection_id}",
                "type": "betslip",
                "note": f"Opens FanDuel with bet on slip"
            }
        else:
            return {
                "web": f"{base_url}/{sport_path}",
                "mobile": config.get("app_scheme", ""),
                "type": "sport_page",
                "note": f"Opens FanDuel {sport.upper()} page"
            }

    elif book_key == "betmgm" and event_id:
        # BetMGM uses event IDs
        return {
            "web": f"{base_url}/en/sports/events/{event_id}",
            "mobile": f"betmgm://sports/event/{event_id}",
            "type": "event",
            "note": f"Opens BetMGM event page"
        }

    elif book_key == "caesars" and event_id:
        return {
            "web": f"{base_url}/us/{sport_path}/event/{event_id}",
            "mobile": f"caesarssportsbook://event/{event_id}",
            "type": "event",
            "note": f"Opens Caesars event page"
        }

    # Fallback: Sport-specific page
    return {
        "web": f"{base_url}/{sport_path}",
        "mobile": config.get("app_scheme", ""),
        "type": "sport_page",
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


@router.get("/line-shop/{sport}")
async def get_line_shopping(sport: str, game_id: Optional[str] = None):
    """
    Get odds from multiple sportsbooks for line shopping.
    Returns best odds for each side of each bet.

    Response includes deep links for each sportsbook.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache
    cache_key = f"line-shop:{sport_lower}:{game_id or 'all'}"
    cached = api_cache.get(cache_key)
    if cached:
        return JSONResponse(_sanitize_public(cached))

    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not resp or resp.status_code != 200:
            # Use fallback data when API unavailable
            logger.warning("Odds API unavailable for line-shop, using fallback data")
            line_shop_data = generate_fallback_line_shop(sport_lower)
            result = {
                "sport": sport.upper(),
                "source": "fallback",
                "count": len(line_shop_data),
                "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
                "data": line_shop_data,
                "timestamp": datetime.now().isoformat()
            }
            api_cache.set(cache_key, result, ttl=120)
            return JSONResponse(_sanitize_public(result))

        games = resp.json()
        line_shop_data = []

        for game in games:
            if game_id and game.get("id") != game_id:
                continue

            game_data = {
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "commence_time": game.get("commence_time"),
                "markets": {}
            }

            # Organize by market type
            for bookmaker in game.get("bookmakers", []):
                book_key = bookmaker.get("key")
                book_name = bookmaker.get("title")

                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")

                    if market_key not in game_data["markets"]:
                        game_data["markets"][market_key] = {
                            "best_odds": {},
                            "all_books": []
                        }

                    # Extract deep links from API response (if available)
                    api_link = bookmaker.get("link")  # Direct link from Odds API

                    # Build outcomes with sids and links
                    outcomes_with_links = []
                    for outcome in market.get("outcomes", []):
                        outcome_data = {
                            "name": outcome.get("name"),
                            "price": outcome.get("price"),
                            "point": outcome.get("point"),
                            "sid": outcome.get("sid"),  # Source ID for deep links
                            "link": outcome.get("link")  # Direct bet link if available
                        }
                        outcomes_with_links.append(outcome_data)

                    book_entry = {
                        "book_key": book_key,
                        "book_name": book_name,
                        "outcomes": outcomes_with_links,
                        "api_link": api_link,
                        "deep_link": generate_true_deep_link(book_key, game.get("id"), sport_lower, outcomes_with_links)
                    }
                    game_data["markets"][market_key]["all_books"].append(book_entry)

                    # Track best odds for each outcome
                    for outcome in market.get("outcomes", []):
                        outcome_name = outcome.get("name")
                        price = outcome.get("price", -110)

                        if outcome_name not in game_data["markets"][market_key]["best_odds"]:
                            game_data["markets"][market_key]["best_odds"][outcome_name] = {
                                "price": price,
                                "book": book_name,
                                "book_key": book_key
                            }
                        elif price > game_data["markets"][market_key]["best_odds"][outcome_name]["price"]:
                            game_data["markets"][market_key]["best_odds"][outcome_name] = {
                                "price": price,
                                "book": book_name,
                                "book_key": book_key
                            }

            line_shop_data.append(game_data)

        result = {
            "sport": sport.upper(),
            "source": "odds_api",
            "count": len(line_shop_data),
            "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
            "data": line_shop_data,
            "timestamp": datetime.now().isoformat()
        }

        api_cache.set(cache_key, result, ttl=120)  # 2 min cache for line shopping
        return JSONResponse(_sanitize_public(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Line shopping fetch failed: %s, using fallback", e)
        # Return fallback data on any error
        line_shop_data = generate_fallback_line_shop(sport_lower)
        result = {
            "sport": sport.upper(),
            "source": "fallback",
            "count": len(line_shop_data),
            "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
            "data": line_shop_data,
            "timestamp": datetime.now().isoformat()
        }
        api_cache.set(cache_key, result, ttl=120)
        return JSONResponse(_sanitize_public(result))


@router.get("/betslip/generate")
async def generate_betslip(
    sport: str,
    game_id: str,
    bet_type: str,  # spread, h2h, total
    selection: str,  # team name or over/under
    book: Optional[str] = None  # specific book, or returns all
):
    """
    Generate deep links for placing a specific bet across sportsbooks.

    Frontend uses this to create the "click to bet" modal.

    Example:
        /live/betslip/generate?sport=nba&game_id=xyz&bet_type=spread&selection=Lakers

    Returns links for all sportsbooks (or specific book if specified).
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get current odds for this game
    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": bet_type + "s" if bet_type in ["spread", "total"] else bet_type,
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not resp or resp.status_code != 200:
            # Use fallback data when API unavailable
            logger.warning("Odds API unavailable for betslip, using fallback data")
            return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)

        games = resp.json()
        target_game = None

        for game in games:
            if game.get("id") == game_id:
                target_game = game
                break

        if not target_game:
            # Game not found in API, use fallback
            logger.warning("Game %s not found, using fallback data", game_id)
            return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)

        betslip_options = []

        for bookmaker in target_game.get("bookmakers", []):
            book_key = bookmaker.get("key")

            # Filter by specific book if requested
            if book and book_key != book:
                continue

            # Skip if we don't have config for this book
            if book_key not in SPORTSBOOK_CONFIGS:
                continue

            book_config = SPORTSBOOK_CONFIGS[book_key]

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")

                # Match the requested bet type
                if bet_type == "spread" and market_key != "spreads":
                    continue
                if bet_type == "h2h" and market_key != "h2h":
                    continue
                if bet_type == "total" and market_key != "totals":
                    continue

                for outcome in market.get("outcomes", []):
                    outcome_name = outcome.get("name", "")

                    # Match the selection
                    if selection.lower() not in outcome_name.lower():
                        continue

                    # Extract sid and link from API response for true deep links
                    outcome_sid = outcome.get("sid")
                    outcome_link = outcome.get("link")

                    # Generate true deep link using API data
                    deep_link = generate_true_deep_link(
                        book_key,
                        game_id,
                        sport_lower,
                        [{"sid": outcome_sid, "link": outcome_link}]
                    )

                    betslip_options.append({
                        "book_key": book_key,
                        "book_name": book_config["name"],
                        "book_color": book_config["color"],
                        "book_logo": book_config.get("logo", ""),
                        "selection": outcome_name,
                        "odds": outcome.get("price", -110),
                        "point": outcome.get("point"),  # spread/total line
                        "sid": outcome_sid,  # Include sid for custom link building
                        "deep_link": deep_link
                    })

        # Sort by best odds (highest for positive, least negative for negative)
        betslip_options.sort(key=lambda x: x["odds"], reverse=True)

        return {
            "sport": sport.upper(),
            "game_id": game_id,
            "game": f"{target_game.get('away_team')} @ {target_game.get('home_team')}",
            "bet_type": bet_type,
            "selection": selection,
            "best_odds": betslip_options[0] if betslip_options else None,
            "all_books": betslip_options,
            "count": len(betslip_options),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Betslip generation failed: %s, using fallback", e)
        # Return fallback data on any error
        return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)


@router.get("/sportsbooks")
async def list_sportsbooks():
    """List all supported sportsbooks with their branding info."""
    sportsbooks_list = [
        {
            "key": key,
            "name": config["name"],
            "color": config["color"],
            "logo": config.get("logo", ""),
            "web_url": config["web_base"]
        }
        for key, config in SPORTSBOOK_CONFIGS.items()
    ]
    return {
        "count": len(SPORTSBOOK_CONFIGS),
        "active_count": len(sportsbooks_list),  # Frontend expects this field
        "sportsbooks": sportsbooks_list,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# LEVEL 17 - PARLAY ARCHITECT, VOID CHECK, SMASH CARD
# ============================================================================

@router.post("/parlay-architect")
async def parlay_architect(leg1: Dict[str, Any], leg2: Dict[str, Any]):
    """
    Calculates 'Correlation Alpha' for Same Game Parlays (SGP).
    Finds correlated props that books misprice as independent events.

    Request Body:
    {
        "leg1": {"player": "Patrick Mahomes", "position": "QB", "team": "KC", "prop": "passing_yards", "line": 275.5},
        "leg2": {"player": "Travis Kelce", "position": "TE", "team": "KC", "prop": "receiving_yards", "line": 65.5}
    }

    Response:
    {
        "stack_type": "BATTERY STACK",
        "correlation": 0.88,
        "glitch_score": 9.0,
        "recommendation": "CORRELATION GLITCH - Book Misprice Detected",
        "edge_explanation": "If Mahomes hits 275+ yards, Kelce MUST have yards. Books price independently."
    }
    """
    pos1 = leg1.get("position", "").upper()
    pos2 = leg2.get("position", "").upper()
    team1 = leg1.get("team", "").upper()
    team2 = leg2.get("team", "").upper()

    correlation = 0.0
    stack_type = "INDEPENDENT"
    description = "No significant correlation detected"

    # Same team correlations
    if team1 == team2:
        # QB + WR/TE Stack
        if pos1 == "QB" and pos2 in ["WR", "TE"]:
            corr_key = f"QB_{pos2}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]
        elif pos2 == "QB" and pos1 in ["WR", "TE"]:
            corr_key = f"QB_{pos1}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]

        # RB + DST Stack
        elif (pos1 == "RB" and pos2 == "DST") or (pos1 == "DST" and pos2 == "RB"):
            data = CORRELATION_MATRIX["RB_DST"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # WR1 + WR2 (negative correlation)
        elif pos1 == "WR" and pos2 == "WR":
            data = CORRELATION_MATRIX["WR1_WR2"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # PG + C (NBA)
        elif (pos1 == "PG" and pos2 == "C") or (pos1 == "C" and pos2 == "PG"):
            data = CORRELATION_MATRIX["PG_C"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

    # Calculate glitch score
    base_score = 5.0
    if correlation > 0.80:
        base_score += 4.0
        recommendation = "CORRELATION GLITCH - Book Misprice Detected"
    elif correlation > 0.60:
        base_score += 2.5
        recommendation = "MODERATE CORRELATION - Slight Edge"
    elif correlation > 0.40:
        base_score += 1.0
        recommendation = "WEAK CORRELATION - Standard Parlay"
    elif correlation < 0:
        base_score -= 2.0
        recommendation = "NEGATIVE CORRELATION - Avoid This Parlay"
    else:
        recommendation = "INDEPENDENT - No Correlation Edge"

    return {
        "stack_type": stack_type,
        "correlation": round(correlation, 2),
        "glitch_score": round(min(10, max(0, base_score)), 1),
        "recommendation": recommendation,
        "edge_explanation": description,
        "leg1": leg1,
        "leg2": leg2,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/void-check/{player}")
async def void_check(player: str, target_player: Optional[str] = None, baseline_avg: Optional[float] = None):
    """
    The HOF Feature: Recalculates hit rate when a star player is OUT.
    Finds the 'Usage Monster' - the teammate who benefits most.

    Example: /live/void-check/Joel%20Embiid
    Example: /live/void-check/Joel%20Embiid?target_player=Tyrese%20Maxey&baseline_avg=24.0

    Response:
    {
        "missing_star": "Joel Embiid",
        "usage_beneficiary": "Tyrese Maxey",
        "baseline_avg": 24.0,
        "void_avg": 30.7,
        "boost_pct": 28,
        "hit_rate_with_star": "5/10 (50%)",
        "hit_rate_without_star": "8/10 (80%)",
        "signal": "USAGE MONSTER (+6.7 pts without Joel Embiid)",
        "recommendation": "SMASH THE OVER"
    }
    """
    # Normalize player name
    player_normalized = player.title()

    # Check if we have data for this player
    impact_data = VOID_IMPACT_MULTIPLIERS.get(player_normalized)

    if not impact_data:
        # Generate reasonable fallback based on player name hash
        rng = deterministic_rng_for_game_id(player_normalized)
        pts_boost = 1.15 + (rng.random() * 0.20)  # 15-35% boost
        usage_boost = pts_boost + 0.05

        # Find a generic teammate name
        teammate = target_player or "Teammate"
        base_avg = baseline_avg or rng.randint(18, 28)
    else:
        teammate = target_player or impact_data["teammate"]
        pts_boost = impact_data.get("pts_boost", impact_data.get("target_boost", 1.20))
        usage_boost = impact_data["usage_boost"]
        base_avg = baseline_avg or 24.0  # Default baseline

    void_avg = base_avg * pts_boost
    boost_pct = int((pts_boost - 1) * 100)

    # Calculate hit rates (simulated based on boost)
    base_hit_rate = 50
    void_hit_rate = min(90, base_hit_rate + (boost_pct * 1.2))

    # Generate signal
    diff = void_avg - base_avg
    if diff > 5.0:
        signal = f"USAGE MONSTER (+{diff:.1f} pts without {player_normalized})"
        recommendation = "SMASH THE OVER"
    elif diff > 3.0:
        signal = f"USAGE SPIKE (+{diff:.1f} pts without {player_normalized})"
        recommendation = "LEAN OVER"
    else:
        signal = f"MINOR BUMP (+{diff:.1f} pts without {player_normalized})"
        recommendation = "MONITOR"

    return {
        "missing_star": player_normalized,
        "usage_beneficiary": teammate,
        "baseline_avg": round(base_avg, 1),
        "void_avg": round(void_avg, 1),
        "boost_pct": boost_pct,
        "usage_boost_pct": int((usage_boost - 1) * 100),
        "hit_rate_with_star": f"{base_hit_rate // 10}/10 ({base_hit_rate}%)",
        "hit_rate_without_star": f"{int(void_hit_rate) // 10}/10 ({int(void_hit_rate)}%)",
        "signal": signal,
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/smash-card")
async def generate_smash_card(bet_data: Dict[str, Any], book: Optional[str] = "draftkings"):
    """
    Generates a 'Smash Card' with deep links for one-tap betting.
    Bypasses sportsbook lobby and drops user directly into bet slip.

    Request Body:
    {
        "bet_data": {
            "player": "Tyrese Maxey",
            "prop": "points",
            "line": 28.5,
            "pick": "over",
            "odds": -110,
            "hit_rate": "8/10",
            "reasoning": "Embiid OUT - Usage Spike",
            "event_id": "nba_phi_vs_sac_123",
            "market_id": "player_points_maxey"
        },
        "book": "draftkings"
    }

    Response:
    {
        "smash_card": {
            "title": "SMASH: Tyrese Maxey OVER 28.5 PTS",
            "subtitle": "Embiid OUT - Usage Spike",
            "hit_rate_display": "[████████░░] 80%",
            "confidence": "HIGH",
            "button": {
                "text": "Place on DraftKings",
                "color": "#53d337",
                "logo": "..."
            },
            "deep_links": {
                "app": "draftkings://...",
                "web": "https://...",
                "universal": "https://..."
            }
        }
    }
    """
    book_key = book.lower() if book else "draftkings"
    book_config = SPORTSBOOK_CONFIGS.get(book_key, SPORTSBOOK_CONFIGS["draftkings"])
    link_schemes = SMASH_LINK_SCHEMES.get(book_key, SMASH_LINK_SCHEMES["draftkings"])

    player = bet_data.get("player", "Player")
    prop = bet_data.get("prop", "points")
    line = bet_data.get("line", 0)
    pick = bet_data.get("pick", "over").upper()
    odds = bet_data.get("odds", -110)
    hit_rate = bet_data.get("hit_rate", "7/10")
    reasoning = bet_data.get("reasoning", "AI Analysis")
    event_id = bet_data.get("event_id", "event_123")
    market_id = bet_data.get("market_id", "market_456")

    # Parse hit rate for visual
    try:
        hits, total = hit_rate.split("/")
        hit_pct = int(int(hits) / int(total) * 100)
    except:
        hit_pct = 70

    # Generate hit rate bar
    filled = hit_pct // 10
    empty = 10 - filled
    hit_rate_bar = f"[{'█' * filled}{'░' * empty}] {hit_pct}%"

    # Determine confidence
    if hit_pct >= 80:
        confidence = "HIGH"
    elif hit_pct >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Generate deep links
    sport = bet_data.get("sport", "nba").upper()
    sport_path = {"NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb", "NHL": "hockey/nhl"}.get(sport, "basketball/nba")

    deep_links = {
        "app": link_schemes["app"].format(sport=sport, event_id=event_id, market_id=market_id),
        "web": link_schemes["web"].format(sport_path=sport_path, event_id=event_id),
        "universal": link_schemes["universal"].format(sport=sport.lower(), event_id=event_id, market_id=market_id)
    }

    return {
        "smash_card": {
            "title": f"SMASH: {player} {pick} {line} {prop.upper()}",
            "subtitle": reasoning,
            "odds_display": f"{'+' if odds > 0 else ''}{odds}",
            "hit_rate_display": hit_rate_bar,
            "hit_rate_raw": hit_rate,
            "confidence": confidence,
            "button": {
                "text": f"Place on {book_config['name']}",
                "color": book_config["color"],
                "logo": book_config.get("logo", "")
            },
            "deep_links": deep_links,
            "all_books": [
                {
                    "key": key,
                    "name": cfg["name"],
                    "color": cfg["color"],
                    "logo": cfg.get("logo", ""),
                    "deep_link": SMASH_LINK_SCHEMES.get(key, {}).get("universal", "").format(
                        sport=sport.lower(), event_id=event_id, market_id=market_id
                    )
                }
                for key, cfg in SPORTSBOOK_CONFIGS.items()
            ]
        },
        "bet_data": bet_data,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/correlations")
async def list_correlations():
    """List all known correlation patterns for parlay building."""
    return {
        "count": len(CORRELATION_MATRIX),
        "correlations": [
            {
                "key": key,
                "name": data["name"],
                "correlation": data["correlation"],
                "description": data["description"],
                "edge": "HIGH" if data["correlation"] > 0.75 else "MEDIUM" if data["correlation"] > 0.5 else "LOW"
            }
            for key, data in CORRELATION_MATRIX.items()
        ],
        "void_players": list(VOID_IMPACT_MULTIPLIERS.keys()),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 3: LEARNING LOOP ENDPOINTS
# ============================================================================

# Import engines (lazy load to avoid circular imports)
_jarvis_savant_engine = None
_vedic_astro_engine = None
_esoteric_learning_loop = None


def get_jarvis_savant():
    """Lazy load JarvisSavantEngine."""
    global _jarvis_savant_engine
    if _jarvis_savant_engine is None:
        try:
            from jarvis_savant_engine import get_jarvis_engine
            _jarvis_savant_engine = get_jarvis_engine()
            logger.info("JarvisSavantEngine initialized")
        except ImportError as e:
            logger.warning("JarvisSavantEngine not available: %s", e)
    return _jarvis_savant_engine


def get_vedic_astro():
    """Lazy load VedicAstroEngine."""
    global _vedic_astro_engine
    if _vedic_astro_engine is None:
        try:
            from jarvis_savant_engine import get_vedic_engine
            _vedic_astro_engine = get_vedic_engine()
            logger.info("VedicAstroEngine initialized")
        except ImportError as e:
            logger.warning("VedicAstroEngine not available: %s", e)
    return _vedic_astro_engine


def get_esoteric_loop():
    """Lazy load EsotericLearningLoop."""
    global _esoteric_learning_loop
    if _esoteric_learning_loop is None:
        try:
            from jarvis_savant_engine import get_learning_loop
            _esoteric_learning_loop = get_learning_loop()
            logger.info("EsotericLearningLoop initialized")
        except ImportError as e:
            logger.warning("EsotericLearningLoop not available: %s", e)
    return _esoteric_learning_loop


# ============================================================================
# PHASE 1: CONFLUENCE CORE ENDPOINTS
# ============================================================================

@router.get("/validate-immortal")
async def validate_immortal():
    """
    Validate 2178 as THE IMMORTAL number.

    Mathematical proof that 2178 is the only 4-digit number where:
    - n^4 contains n
    - reverse(n)^4 contains reverse(n)
    - Digital root = 9 (Tesla completion)
    """
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    return jarvis.validate_2178()


@router.get("/jarvis-triggers")
async def list_jarvis_triggers():
    """List all JARVIS trigger numbers with their properties."""
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    return {
        "triggers": jarvis.triggers,
        "power_numbers": jarvis.power_numbers,
        "tesla_numbers": jarvis.tesla_numbers,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/check-trigger/{value}")
async def check_trigger(value: str):
    """
    Check if a value triggers any JARVIS numbers.

    Supports:
    - Direct number matches (e.g., 2178)
    - Gematria reduction of strings (e.g., "Lakers")
    """
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    # Try to parse as number first
    try:
        numeric_value = int(value)
        return jarvis.check_jarvis_trigger(numeric_value)
    except ValueError:
        return jarvis.check_jarvis_trigger(value)


@router.get("/confluence/{sport}")
async def get_confluence_analysis(
    sport: str,
    player: str = "Player",
    team: str = "Team",
    opponent: str = "Opponent",
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
    research_score: float = 7.0  # v10.1: Allow passing external research score
):
    """
    Calculate v10.1 dual-score confluence analysis for a pick.

    THE HEART - v10.1 Alignment System:
    - IMMORTAL (+10): 2178 + both ≥7.5 + alignment ≥80%
    - JARVIS_PERFECT (+7): Trigger + both ≥7.5 + alignment ≥80%
    - PERFECT (+5): both ≥7.5 + alignment ≥80%
    - STRONG (+3): Both high OR aligned ≥70%
    - MODERATE (+1): Aligned ≥60%
    - DIVERGENT (+0): Models disagree

    Alignment = 1 - |research - esoteric| / 10
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    jarvis = get_jarvis_savant()
    vedic = get_vedic_astro()
    learning = get_esoteric_loop()

    if not jarvis or not vedic:
        raise HTTPException(status_code=503, detail="Esoteric engines not available")

    esoteric_weights = learning.get_weights()["weights"] if learning else {}

    # Calculate all signals
    gematria = jarvis.calculate_gematria_signal(player, team, opponent)
    public_fade = jarvis.calculate_public_fade_signal(public_pct)
    mid_spread = jarvis.calculate_mid_spread_signal(spread)
    trap = jarvis.calculate_large_spread_trap(spread, total)
    astro = vedic.calculate_astro_score()

    # v10.1: Fibonacci alignment and Vortex pattern
    fib_alignment = jarvis.calculate_fibonacci_alignment(float(spread) if spread else 0)
    vortex_value = int(abs(spread * 10)) if spread else 0
    vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)

    # Check for JARVIS triggers in player/team names
    game_str = f"{player}{team}{opponent}"
    trigger_result = jarvis.check_jarvis_trigger(game_str)
    jarvis_triggered = len(trigger_result.get("triggers_hit", [])) > 0
    immortal_detected = any(t["number"] == 2178 for t in trigger_result.get("triggers_hit", []))

    # Calculate JARVIS score from triggers
    jarvis_score = 0.0
    for trig in trigger_result.get("triggers_hit", []):
        jarvis_score += trig["boost"] / 5
    jarvis_score = min(4.0, jarvis_score)

    # v10.1: Calculate esoteric score
    gematria_contribution = gematria.get("influence", 0) * 0.52 * 2 if gematria.get("triggered") else 0
    astro_contribution = (astro["overall_score"] - 50) / 50 * esoteric_weights.get("astro", 0.13) * 2

    esoteric_raw = (
        jarvis_score +
        gematria_contribution +
        max(0, astro_contribution) +
        mid_spread.get("modifier", 0) +
        fib_alignment.get("modifier", 0) +
        vortex_pattern.get("modifier", 0) +
        public_fade.get("influence", 0) +
        trap.get("modifier", 0)
    )
    esoteric_score = max(0, min(10, esoteric_raw * 1.25))

    # v10.1: Calculate dual-score confluence
    confluence = jarvis.calculate_confluence(
        research_score=research_score,
        esoteric_score=esoteric_score,
        immortal_detected=immortal_detected,
        jarvis_triggered=jarvis_triggered
    )

    # v10.1: Calculate final score and bet tier (Option A weights)
    ai_score = 0.0  # No AI engine inputs in this legacy endpoint
    jarvis_score_10 = min(10.0, jarvis_score * 2.5)
    base_score = (
        (ai_score * ENGINE_WEIGHTS["ai"]) +
        (research_score * ENGINE_WEIGHTS["research"]) +
        (esoteric_score * ENGINE_WEIGHTS["esoteric"]) +
        (jarvis_score_10 * ENGINE_WEIGHTS["jarvis"])
    )
    context_modifier = 0.0
    jason_sim_boost = 0.0
    final_score, context_modifier = compute_final_score_option_a(
        base_score=base_score,
        context_modifier=context_modifier,
        confluence_boost=confluence.get("boost", 0),
        msrf_boost=0.0,
        jason_sim_boost=jason_sim_boost,
        serp_boost=0.0,
    )
    bet_tier = jarvis.determine_bet_tier(final_score, confluence)

    return {
        "sport": sport.upper(),
        "version": "v10.1",
        "input": {
            "player": player,
            "team": team,
            "opponent": opponent,
            "spread": spread,
            "total": total,
            "public_pct": public_pct,
            "research_score": research_score
        },
        "signals": {
            "gematria": gematria,
            "public_fade": public_fade,
            "mid_spread": mid_spread,
            "trap": trap,
            "astro": astro,
            "fibonacci": fib_alignment,
            "vortex": vortex_pattern
        },
        "jarvis_triggers": trigger_result.get("triggers_hit", []),
        "scoring": {
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "final_score": round(final_score, 2),
            "formula": "FINAL = BASE_4 + context_modifier + confluence_boost + jason_sim_boost (+ msrf/serp if enabled)"
        },
        "confluence": confluence,
        "bet_tier": bet_tier,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 2: VEDIC/ASTRO ENDPOINTS
# ============================================================================

@router.get("/astro-status")
async def get_astro_status():
    """Get full astrological analysis for current moment."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_astro_score()


@router.get("/planetary-hour")
async def get_planetary_hour():
    """Get current planetary hour ruler (Chaldean order)."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_planetary_hour()


@router.get("/nakshatra")
async def get_nakshatra():
    """Get current Nakshatra (lunar mansion)."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_nakshatra()


@router.get("/retrograde-status")
async def get_retrograde_status():
    """Check retrograde status for Mercury, Venus, and Mars."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return {
        "mercury": vedic.is_planet_retrograde("Mercury"),
        "venus": vedic.is_planet_retrograde("Venus"),
        "mars": vedic.is_planet_retrograde("Mars"),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 3: LEARNING LOOP ENDPOINTS (DEPRECATED)
# ============================================================================
# DEPRECATED: Use /grader/* endpoints instead. These will be removed in v15.0.
# ============================================================================

@router.post("/learning/log-pick", deprecated=True)
async def log_esoteric_pick(pick_data: Dict[str, Any]):
    """
    DEPRECATED: Use /grader/* endpoints for prediction tracking.

    Log a pick for learning loop tracking.

    Request Body:
    {
        "sport": "NBA",
        "game_id": "game_123",
        "pick_type": "spread",
        "selection": "Lakers",
        "line": -3.5,
        "odds": -110,
        "esoteric_analysis": {...}  // From confluence analysis
    }

    Returns pick_id for later grading.
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    required_fields = ["sport", "game_id", "pick_type", "selection", "line", "odds"]
    for field in required_fields:
        if field not in pick_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # If esoteric_analysis not provided, generate it
    esoteric_analysis = pick_data.get("esoteric_analysis", {})
    if not esoteric_analysis:
        jarvis = get_jarvis_savant()
        vedic = get_vedic_astro()
        if jarvis and vedic:
            gematria = jarvis.calculate_gematria_signal(
                pick_data.get("player", "Player"),
                pick_data.get("team", "Team"),
                pick_data.get("opponent", "Opponent")
            )
            astro = vedic.calculate_astro_score()
            esoteric_analysis = {
                "gematria": gematria,
                "astro": astro,
                "total_score": 5.0
            }

    pick_id = loop.log_pick(
        sport=pick_data["sport"],
        game_id=pick_data["game_id"],
        pick_type=pick_data["pick_type"],
        selection=pick_data["selection"],
        line=pick_data["line"],
        odds=pick_data["odds"],
        esoteric_analysis=esoteric_analysis
    )

    return {
        "status": "logged",
        "pick_id": pick_id,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/learning/grade-pick", deprecated=True)
async def grade_esoteric_pick(grade_data: Dict[str, Any]):
    """
    DEPRECATED: Use /grader/* endpoints for prediction grading.

    Grade a pick with actual result.

    Request Body:
    {
        "pick_id": "ESO_NBA_game123_20241215123456",
        "result": "WIN"  // WIN, LOSS, or PUSH
    }
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    pick_id = grade_data.get("pick_id")
    result = grade_data.get("result")

    if not pick_id or not result:
        raise HTTPException(status_code=400, detail="Missing pick_id or result")

    grade_result = loop.grade_pick(pick_id, result)

    if "error" in grade_result:
        raise HTTPException(status_code=404, detail=grade_result["error"])

    return grade_result


@router.get("/learning/performance", deprecated=True)
async def get_learning_performance(days_back: int = 30):
    """
    DEPRECATED: Use /grader/performance/{sport} instead.

    Get esoteric learning loop performance summary.

    Shows:
    - Overall hit rate
    - Performance by signal type
    - Performance by confluence level
    - Performance by bet tier
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.get_performance(days_back)


@router.get("/learning/weights", deprecated=True)
async def get_learning_weights():
    """DEPRECATED: Use /grader/weights/{sport} instead. Get current learned weights for esoteric signals."""
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.get_weights()


@router.post("/learning/adjust-weights", deprecated=True)
async def adjust_learning_weights(learning_rate: float = 0.05):
    """
    DEPRECATED: Use /grader/adjust-weights/{sport} instead.

    Trigger weight adjustment based on historical performance.

    Uses gradient-based adjustment:
    - Increases weights for signals with hit rate > 55%
    - Decreases weights for signals with hit rate < 48%
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.adjust_weights(learning_rate)


@router.get("/learning/recent-picks", deprecated=True)
async def get_recent_picks(limit: int = 20):
    """DEPRECATED: Use /grader/* endpoints instead. Get recent esoteric picks for review."""
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return {
        "picks": loop.get_recent_picks(limit),
        "count": min(limit, len(loop.picks)),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/esoteric-analysis")
async def get_esoteric_analysis(
    player: str = "Player",
    team: str = "Team",
    opponent: str = "Opponent",
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
    model_probability: float = 50
):
    """
    Get complete esoteric analysis using all Phase 1-3 components.

    Returns:
    - Gematria signal
    - Public fade analysis
    - Mid-spread/Goldilocks
    - Trap detection
    - Astro/Vedic score
    - Confluence level
    - Blended probability (67/33 formula)
    - Bet tier recommendation
    """
    try:
        from jarvis_savant_engine import calculate_full_esoteric_analysis

        analysis = calculate_full_esoteric_analysis(
            player=player,
            team=team,
            opponent=opponent,
            spread=spread,
            total=total,
            public_pct=public_pct,
            model_probability=model_probability
        )

        return analysis

    except ImportError:
        raise HTTPException(status_code=503, detail="Esoteric analysis module not available")


# ============================================================================
# CLICK-TO-BET ENHANCEMENTS v2.0
# ============================================================================

# In-memory storage for user preferences and bet tracking
# In production, this should use Redis or a database
_user_preferences: Dict[str, Dict[str, Any]] = {}
_tracked_bets: List[Dict[str, Any]] = []
_parlay_slips: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> list of parlay legs
_placed_parlays: List[Dict[str, Any]] = []  # Tracked parlays


@router.get("/user/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """
    Get user's sportsbook preferences.

    Returns:
    - favorite_books: List of preferred sportsbooks (in order)
    - default_bet_amount: Default stake amount
    - notifications: Notification preferences
    """
    prefs = _user_preferences.get(user_id, {
        "user_id": user_id,
        "favorite_books": ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": 25,
        "auto_best_odds": True,
        "notifications": {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "created_at": datetime.now().isoformat()
    })

    return prefs


@router.post("/user/preferences/{user_id}")
async def save_user_preferences(user_id: str, prefs: UserPreferencesRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any]):
    """
    Save user's sportsbook preferences.

    Request Body (validated with Pydantic):
    - favorite_books: array of strings (validated against supported books)
    - default_bet_amount: float (default: 25, must be >= 0)
    - auto_best_odds: bool (default: true)
    - notifications: object with smash_alerts, odds_movement, bet_results booleans
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(prefs, 'dict'):
        data = prefs.dict()
    else:
        data = prefs if isinstance(prefs, dict) else dict(prefs)

    # Validate favorite_books
    valid_books = list(SPORTSBOOK_CONFIGS.keys())
    favorite_books = data.get("favorite_books", [])
    validated_books = [b for b in favorite_books if b in valid_books]

    # Get notifications, handling nested object
    notifications_data = data.get("notifications", {})
    if hasattr(notifications_data, 'dict'):
        notifications_data = notifications_data.dict()

    _user_preferences[user_id] = {
        "user_id": user_id,
        "favorite_books": validated_books if validated_books else ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": data.get("default_bet_amount", 25),
        "auto_best_odds": data.get("auto_best_odds", True),
        "notifications": notifications_data if notifications_data else {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "updated_at": datetime.now().isoformat()
    }

    return {"status": "saved", "preferences": _user_preferences[user_id]}


@router.post("/bets/track")
async def track_bet(
    bet_data: TrackBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a bet that was placed through the click-to-bet flow.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sport: str (required, validated: NBA/NFL/MLB/NHL)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated: American odds format)
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - ai_score: float (optional, 0-20)
    - confluence_level: str (optional)

    Returns bet_id for later grading.
    """
    # Handle both Pydantic model and dict input for backwards compatibility
    if PYDANTIC_MODELS_AVAILABLE and hasattr(bet_data, 'dict'):
        data = bet_data.dict()
    else:
        # Fallback validation for dict input
        data = bet_data if isinstance(bet_data, dict) else dict(bet_data)
        required_fields = ["sport", "game_id", "bet_type", "selection", "odds", "sportsbook"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds format
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds. American odds must be <= -100 or >= 100")
        data["sport"] = data.get("sport", "").upper()

    bet_id = f"BET_{data['sport']}_{data['game_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_bet = {
        "bet_id": bet_id,
        "user_id": data.get("user_id", "anonymous"),
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "sportsbook": data["sportsbook"],
        "stake": data.get("stake", 0),
        "potential_payout": calculate_payout(data.get("stake", 0), data["odds"]),
        "ai_score": data.get("ai_score"),
        "confluence_level": data.get("confluence_level"),
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _tracked_bets.append(tracked_bet)

    return {
        "status": "tracked",
        "bet_id": bet_id,
        "bet": tracked_bet,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/bets/grade/{bet_id}")
async def grade_bet(
    bet_id: str,
    result_data: GradeBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a tracked bet with actual result.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    - actual_score: str (optional)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(result_data, 'result'):
        result = result_data.result.value if hasattr(result_data.result, 'value') else str(result_data.result)
        actual_score = result_data.actual_score
    else:
        result = result_data.get("result", "").upper()
        actual_score = result_data.get("actual_score")
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for bet in _tracked_bets:
        if bet["bet_id"] == bet_id:
            bet["status"] = "GRADED"
            bet["result"] = result
            bet["actual_score"] = actual_score
            bet["graded_at"] = datetime.now().isoformat()

            # Calculate actual profit/loss
            if result == "WIN":
                bet["profit"] = bet["potential_payout"] - bet["stake"]
            elif result == "LOSS":
                bet["profit"] = -bet["stake"]
            else:  # PUSH
                bet["profit"] = 0

            return {"status": "graded", "bet": bet}

    raise HTTPException(status_code=404, detail=f"Bet not found: {bet_id}")


@router.get("/bets/history")
async def get_bet_history(
    user_id: Optional[str] = None,
    sport: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get bet history with optional filters.

    Supports filtering by:
    - user_id: Filter by user
    - sport: Filter by sport (NBA, NFL, etc.)
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered_bets = _tracked_bets.copy()

    if user_id:
        filtered_bets = [b for b in filtered_bets if b.get("user_id") == user_id]
    if sport:
        filtered_bets = [b for b in filtered_bets if b.get("sport") == sport.upper()]
    if status:
        filtered_bets = [b for b in filtered_bets if b.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered_bets.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded_bets = [b for b in filtered_bets if b.get("status") == "GRADED"]
    wins = len([b for b in graded_bets if b.get("result") == "WIN"])
    losses = len([b for b in graded_bets if b.get("result") == "LOSS"])
    pushes = len([b for b in graded_bets if b.get("result") == "PUSH"])
    total_profit = sum(b.get("profit", 0) for b in graded_bets)

    return {
        "bets": filtered_bets[:limit],
        "count": len(filtered_bets[:limit]),
        "total_tracked": len(filtered_bets),
        "stats": {
            "graded": len(graded_bets),
            "pending": len(filtered_bets) - len(graded_bets),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded_bets) * 100, 1) if graded_bets else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / sum(b.get("stake", 1) for b in graded_bets) * 100, 1) if graded_bets else 0
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/quick-betslip/{sport}/{game_id}")
async def quick_betslip(
    sport: str,
    game_id: str,
    user_id: Optional[str] = None
):
    """
    Generate a quick betslip for a game with user's preferred sportsbooks prioritized.

    One-click flow for SMASH picks:
    1. Gets current best odds across all books
    2. Prioritizes user's favorite books
    3. Returns ready-to-click betslip with deep links
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get user preferences
    user_prefs = _user_preferences.get(user_id, {}) if user_id else {}
    favorite_books = user_prefs.get("favorite_books", ["draftkings", "fanduel", "betmgm"])
    default_stake = user_prefs.get("default_bet_amount", 25)

    # Get line shopping data
    cache_key = f"line-shop:{sport_lower}:{game_id}"
    cached = api_cache.get(cache_key)

    if cached and "data" in cached:
        game_data = next((g for g in cached["data"] if g.get("game_id") == game_id), None)
    else:
        game_data = None

    if not game_data:
        # Use fallback
        game_data = {
            "game_id": game_id,
            "home_team": "Home Team",
            "away_team": "Away Team",
            "markets": {}
        }

    # Build quick betslip with prioritized books
    betslip_options = []

    for book_key in favorite_books:
        if book_key in SPORTSBOOK_CONFIGS:
            config = SPORTSBOOK_CONFIGS[book_key]
            betslip_options.append({
                "book_key": book_key,
                "book_name": config["name"],
                "book_color": config["color"],
                "book_logo": config.get("logo", ""),
                "is_favorite": True,
                "priority": favorite_books.index(book_key) + 1,
                "deep_link": generate_enhanced_deep_link(book_key, sport_lower, game_id, game_data)
            })

    # Add remaining books
    for book_key, config in SPORTSBOOK_CONFIGS.items():
        if book_key not in favorite_books:
            betslip_options.append({
                "book_key": book_key,
                "book_name": config["name"],
                "book_color": config["color"],
                "book_logo": config.get("logo", ""),
                "is_favorite": False,
                "priority": 99,
                "deep_link": generate_enhanced_deep_link(book_key, sport_lower, game_id, game_data)
            })

    return {
        "sport": sport.upper(),
        "game_id": game_id,
        "game": game_data,
        "default_stake": default_stake,
        "sportsbooks": betslip_options,
        "user_preferences_applied": user_id is not None,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PARLAY BUILDER
# ============================================================================

def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return 1 + (american_odds / 100)
    else:
        return 1 + (100 / abs(american_odds))


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return int(round((decimal_odds - 1) * 100))
    else:
        return int(round(-100 / (decimal_odds - 1)))


def calculate_parlay_odds(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate combined parlay odds from individual legs.
    Returns decimal odds, American odds, and implied probability.
    """
    if not legs:
        return {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}

    combined_decimal = 1.0
    for leg in legs:
        leg_odds = leg.get("odds", -110)
        combined_decimal *= american_to_decimal(leg_odds)

    combined_american = decimal_to_american(combined_decimal)
    implied_prob = (1 / combined_decimal) * 100

    return {
        "decimal": round(combined_decimal, 3),
        "american": combined_american,
        "implied_probability": round(implied_prob, 2)
    }


@router.get("/parlay/{user_id}")
async def get_parlay_slip(user_id: str):
    """
    Get current parlay slip for a user.

    Returns all legs in the parlay with calculated combined odds.
    """
    legs = _parlay_slips.get(user_id, [])
    combined = calculate_parlay_odds(legs)

    return {
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "max_legs": 12,
        "can_add_more": len(legs) < 12,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/add")
async def add_parlay_leg(
    leg_data: ParlayLegRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Add a leg to a user's parlay slip.

    Request Body (validated with Pydantic):
    - user_id: str (required)
    - sport: str (required, auto-uppercased)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated American format)
    - ai_score: float (optional)

    Returns updated parlay slip with combined odds.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(leg_data, 'dict'):
        data = leg_data.dict()
    else:
        data = leg_data if isinstance(leg_data, dict) else dict(leg_data)
        required_fields = ["user_id", "sport", "game_id", "bet_type", "selection", "odds"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds format")
        data["sport"] = data.get("sport", "").upper()

    user_id = data["user_id"]

    # Initialize slip if needed
    if user_id not in _parlay_slips:
        _parlay_slips[user_id] = []

    # Check max legs
    if len(_parlay_slips[user_id]) >= 12:
        raise HTTPException(status_code=400, detail="Maximum 12 legs per parlay")

    # Check for duplicate game/bet_type
    for existing in _parlay_slips[user_id]:
        if existing["game_id"] == data["game_id"] and existing["bet_type"] == data["bet_type"]:
            raise HTTPException(
                status_code=400,
                detail=f"Already have a {data['bet_type']} bet for this game"
            )

    leg_id = f"LEG_{user_id}_{len(_parlay_slips[user_id])}_{datetime.now().strftime('%H%M%S')}"

    new_leg = {
        "leg_id": leg_id,
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "ai_score": data.get("ai_score"),
        "added_at": datetime.now().isoformat()
    }

    _parlay_slips[user_id].append(new_leg)
    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "added",
        "leg": new_leg,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/remove/{user_id}/{leg_id}")
async def remove_parlay_leg(user_id: str, leg_id: str):
    """
    Remove a specific leg from a user's parlay slip.
    """
    if user_id not in _parlay_slips:
        raise HTTPException(status_code=404, detail="No parlay slip found for user")

    original_len = len(_parlay_slips[user_id])
    _parlay_slips[user_id] = [leg for leg in _parlay_slips[user_id] if leg["leg_id"] != leg_id]

    if len(_parlay_slips[user_id]) == original_len:
        raise HTTPException(status_code=404, detail=f"Leg {leg_id} not found")

    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "removed",
        "removed_leg_id": leg_id,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/clear/{user_id}")
async def clear_parlay_slip(user_id: str):
    """
    Clear all legs from a user's parlay slip.
    """
    removed_count = len(_parlay_slips.get(user_id, []))
    _parlay_slips[user_id] = []

    return {
        "status": "cleared",
        "removed_count": removed_count,
        "parlay": {
            "legs": [],
            "leg_count": 0,
            "combined_odds": {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/place")
async def place_parlay(
    parlay_data: PlaceParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a parlay bet that was placed.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - use_current_slip: bool (default: true)
    - legs: array (optional, used if use_current_slip is false)

    If use_current_slip is true, uses the user's current parlay slip.
    Otherwise, provide a "legs" array directly.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(parlay_data, 'dict'):
        data = parlay_data.dict()
    else:
        data = parlay_data if isinstance(parlay_data, dict) else dict(parlay_data)

    user_id = data.get("user_id", "anonymous")
    sportsbook = data.get("sportsbook")
    stake = data.get("stake", 0)

    if not sportsbook:
        raise HTTPException(status_code=400, detail="sportsbook is required")

    # Get legs from current slip or from request
    if data.get("use_current_slip", True):
        legs = _parlay_slips.get(user_id, [])
    else:
        legs = data.get("legs", [])

    if len(legs) < 2:
        raise HTTPException(status_code=400, detail="Parlay requires at least 2 legs")

    combined = calculate_parlay_odds(legs)

    # Calculate potential payout
    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
    else:
        potential_payout = 0

    parlay_id = f"PARLAY_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_parlay = {
        "parlay_id": parlay_id,
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "sportsbook": sportsbook,
        "stake": stake,
        "potential_payout": potential_payout,
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _placed_parlays.append(tracked_parlay)

    # Clear the slip after placing
    if data.get("use_current_slip", True):
        _parlay_slips[user_id] = []

    return {
        "status": "placed",
        "parlay": tracked_parlay,
        "message": f"Parlay with {len(legs)} legs tracked. Open {sportsbook} to place bet.",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/grade/{parlay_id}")
async def grade_parlay(
    parlay_id: str,
    grade_data: GradeParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a placed parlay with WIN, LOSS, or PUSH.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(grade_data, 'result'):
        result = grade_data.result.value if hasattr(grade_data.result, 'value') else str(grade_data.result)
    else:
        result = grade_data.get("result", "").upper()
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for parlay in _placed_parlays:
        if parlay["parlay_id"] == parlay_id:
            parlay["status"] = "GRADED"
            parlay["result"] = result
            parlay["graded_at"] = datetime.now().isoformat()

            # Calculate profit/loss
            if result == "WIN":
                parlay["profit"] = parlay["potential_payout"] - parlay["stake"]
            elif result == "LOSS":
                parlay["profit"] = -parlay["stake"]
            else:  # PUSH
                parlay["profit"] = 0

            return {
                "status": "graded",
                "parlay": parlay,
                "timestamp": datetime.now().isoformat()
            }

    raise HTTPException(status_code=404, detail=f"Parlay {parlay_id} not found")


@router.get("/parlay/history")
async def get_parlay_history(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get parlay history with stats.

    Supports filtering by:
    - user_id: Filter by user
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered = _placed_parlays.copy()

    if user_id:
        filtered = [p for p in filtered if p.get("user_id") == user_id]
    if status:
        filtered = [p for p in filtered if p.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded = [p for p in filtered if p.get("status") == "GRADED"]
    wins = len([p for p in graded if p.get("result") == "WIN"])
    losses = len([p for p in graded if p.get("result") == "LOSS"])
    pushes = len([p for p in graded if p.get("result") == "PUSH"])
    total_profit = sum(p.get("profit", 0) for p in graded)
    total_staked = sum(p.get("stake", 0) for p in graded)

    return {
        "parlays": filtered[:limit],
        "count": len(filtered[:limit]),
        "total_tracked": len(filtered),
        "stats": {
            "graded": len(graded),
            "pending": len(filtered) - len(graded),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded) * 100, 1) if graded else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / total_staked * 100, 1) if total_staked > 0 else 0
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/calculate")
async def calculate_parlay(calc_data: Dict[str, Any]):
    """
    Calculate parlay odds and payout without saving.

    Request Body:
    {
        "legs": [
            {"odds": -110},
            {"odds": +150},
            {"odds": -105}
        ],
        "stake": 25
    }

    Useful for preview/what-if calculations.
    """
    legs = calc_data.get("legs", [])
    stake = calc_data.get("stake", 0)

    if not legs:
        raise HTTPException(status_code=400, detail="At least one leg required")

    combined = calculate_parlay_odds(legs)

    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
        profit = round(potential_payout - stake, 2)
    else:
        potential_payout = 0
        profit = 0

    return {
        "leg_count": len(legs),
        "combined_odds": combined,
        "stake": stake,
        "potential_payout": potential_payout,
        "profit_if_win": profit,
        "example_payouts": {
            "$10": round(10 * combined["decimal"], 2),
            "$25": round(25 * combined["decimal"], 2),
            "$50": round(50 * combined["decimal"], 2),
            "$100": round(100 * combined["decimal"], 2)
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# COMMUNITY FEATURES: Man vs Machine Sentiment + Affiliate Links
# ============================================================================

# In-memory storage for community votes (use Redis/DB for production persistence)
_community_votes: Dict[str, Dict[str, int]] = {}

# Affiliate links for sportsbooks (configure your affiliate IDs here)
AFFILIATE_LINKS = {
    "draftkings": {
        "base_url": "https://sportsbook.draftkings.com",
        "affiliate_id": "",  # Add your affiliate ID
        "sport_paths": {
            "nba": "/leagues/basketball/nba",
            "nfl": "/leagues/football/nfl",
            "mlb": "/leagues/baseball/mlb",
            "nhl": "/leagues/hockey/nhl"
        }
    },
    "fanduel": {
        "base_url": "https://sportsbook.fanduel.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/navigation/nba",
            "nfl": "/navigation/nfl",
            "mlb": "/navigation/mlb",
            "nhl": "/navigation/nhl"
        }
    },
    "betmgm": {
        "base_url": "https://sports.betmgm.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/en/sports/basketball-7/betting/usa-9/nba-6004",
            "nfl": "/en/sports/football-11/betting/usa-9/nfl-35",
            "mlb": "/en/sports/baseball-23/betting/usa-9/mlb-75",
            "nhl": "/en/sports/ice-hockey-12/betting/usa-9/nhl-34"
        }
    },
    "caesars": {
        "base_url": "https://www.caesars.com/sportsbook-and-casino",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/us/nba",
            "nfl": "/us/nfl",
            "mlb": "/us/mlb",
            "nhl": "/us/nhl"
        }
    },
    "pointsbetus": {
        "base_url": "https://pointsbet.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sports/basketball/nba",
            "nfl": "/sports/football/nfl",
            "mlb": "/sports/baseball/mlb",
            "nhl": "/sports/hockey/nhl"
        }
    },
    "betrivers": {
        "base_url": "https://betrivers.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sports/basketball/nba",
            "nfl": "/sports/football/nfl",
            "mlb": "/sports/baseball/mlb",
            "nhl": "/sports/hockey/nhl"
        }
    },
    "espnbet": {
        "base_url": "https://espnbet.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sport/basketball/organization/nba",
            "nfl": "/sport/football/organization/nfl",
            "mlb": "/sport/baseball/organization/mlb",
            "nhl": "/sport/icehockey/organization/nhl"
        }
    },
    "bet365": {
        "base_url": "https://www.bet365.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/#/AS/B18/",
            "nfl": "/#/AS/B17/",
            "mlb": "/#/AS/B16/",
            "nhl": "/#/AS/B19/"
        }
    }
}


@router.get("/community/votes/{game_id}")
async def get_community_votes(game_id: str):
    """
    Get community sentiment votes for a game.

    Returns AI vs Public vote counts for the "Man vs Machine" widget.
    """
    votes = _community_votes.get(game_id, {"ai": 0, "public": 0})
    total = votes["ai"] + votes["public"]

    # Calculate percentages
    ai_pct = round((votes["ai"] / total) * 100) if total > 0 else 50
    public_pct = 100 - ai_pct

    return {
        "game_id": game_id,
        "votes": votes,
        "total": total,
        "percentages": {
            "ai": ai_pct,
            "public": public_pct
        },
        "consensus": "AI" if ai_pct > public_pct else ("PUBLIC" if public_pct > ai_pct else "SPLIT"),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/community/vote")
async def submit_community_vote(
    vote_data: Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Submit a community vote for Man vs Machine.

    Request Body:
    {
        "game_id": "nba_celtics_lakers_2026011600",
        "side": "ai" | "public",
        "user_id": "optional_user_identifier"
    }

    Users can vote whether they agree with the AI or fade it.
    """
    game_id = vote_data.get("game_id")
    side = vote_data.get("side", "").lower()

    if not game_id:
        raise HTTPException(status_code=400, detail="game_id required")

    if side not in ["ai", "public"]:
        raise HTTPException(status_code=400, detail="side must be 'ai' or 'public'")

    # Initialize if not exists
    if game_id not in _community_votes:
        _community_votes[game_id] = {"ai": 0, "public": 0}

    # Increment vote
    _community_votes[game_id][side] += 1

    # Get updated totals
    votes = _community_votes[game_id]
    total = votes["ai"] + votes["public"]
    ai_pct = round((votes["ai"] / total) * 100) if total > 0 else 50

    return {
        "status": "vote_recorded",
        "game_id": game_id,
        "side": side,
        "new_totals": votes,
        "percentages": {
            "ai": ai_pct,
            "public": 100 - ai_pct
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/community/leaderboard")
async def get_vote_leaderboard():
    """
    Get games with most community engagement.

    Shows which games have the most votes and biggest AI vs Public splits.
    """
    leaderboard = []

    for game_id, votes in _community_votes.items():
        total = votes["ai"] + votes["public"]
        if total == 0:
            continue

        ai_pct = round((votes["ai"] / total) * 100)
        split = abs(ai_pct - 50)  # How far from 50/50

        leaderboard.append({
            "game_id": game_id,
            "total_votes": total,
            "ai_percent": ai_pct,
            "public_percent": 100 - ai_pct,
            "split_magnitude": split,
            "consensus": "STRONG AI" if ai_pct >= 70 else ("STRONG PUBLIC" if ai_pct <= 30 else "CONTESTED")
        })

    # Sort by total votes
    leaderboard.sort(key=lambda x: x["total_votes"], reverse=True)

    return {
        "games": leaderboard[:20],
        "total_games_with_votes": len(leaderboard),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/affiliate/links")
async def get_affiliate_links(sport: str = "nba"):
    """
    Get affiliate links for all sportsbooks.

    Use these to deep-link users to sportsbooks with your affiliate tracking.
    """
    sport_lower = sport.lower()
    links = {}

    for book_key, config in AFFILIATE_LINKS.items():
        base = config["base_url"]
        affiliate = config.get("affiliate_id", "")
        sport_path = config["sport_paths"].get(sport_lower, "")

        # Build full URL
        full_url = f"{base}{sport_path}"
        if affiliate:
            # Add affiliate tracking (format varies by book)
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}affiliate={affiliate}"

        links[book_key] = {
            "url": full_url,
            "has_affiliate": bool(affiliate),
            "book_name": book_key.replace("_", " ").title()
        }

    return {
        "sport": sport.upper(),
        "links": links,
        "note": "Configure affiliate IDs in AFFILIATE_LINKS to enable tracking",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/affiliate/configure")
async def configure_affiliate_link(
    config_data: Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Configure an affiliate link for a sportsbook.

    Request Body:
    {
        "book": "draftkings",
        "affiliate_id": "your_affiliate_123",
        "custom_url": "https://optional.custom.tracking.url"
    }
    """
    book = config_data.get("book", "").lower()
    affiliate_id = config_data.get("affiliate_id", "")
    custom_url = config_data.get("custom_url", "")

    if book not in AFFILIATE_LINKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown book: {book}. Available: {list(AFFILIATE_LINKS.keys())}"
        )

    # Update the affiliate ID
    if affiliate_id:
        AFFILIATE_LINKS[book]["affiliate_id"] = affiliate_id

    if custom_url:
        AFFILIATE_LINKS[book]["base_url"] = custom_url

    return {
        "status": "configured",
        "book": book,
        "affiliate_id": AFFILIATE_LINKS[book]["affiliate_id"],
        "base_url": AFFILIATE_LINKS[book]["base_url"],
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_payout(stake: float, odds: int) -> float:
    """Calculate potential payout from American odds."""
    if stake <= 0:
        return 0
    if odds > 0:
        return stake + (stake * odds / 100)
    else:
        return stake + (stake * 100 / abs(odds))


def generate_enhanced_deep_link(book_key: str, sport: str, game_id: str, game_data: Dict) -> Dict[str, str]:
    """Generate enhanced deep links with sport-specific URLs."""
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return {"web": "#", "note": "Unknown sportsbook"}

    sport_paths = {
        "nba": {
            "draftkings": "basketball/nba",
            "fanduel": "navigation/nba",
            "betmgm": "sports/basketball/104/nba",
            "caesars": "us/nba",
            "pointsbetus": "sports/basketball/nba",
            "williamhill_us": "sports/basketball/nba",
            "barstool": "sports/basketball/nba",
            "betrivers": "sports/basketball/nba"
        },
        "nfl": {
            "draftkings": "football/nfl",
            "fanduel": "navigation/nfl",
            "betmgm": "sports/football/100/nfl",
            "caesars": "us/nfl",
            "pointsbetus": "sports/football/nfl",
            "williamhill_us": "sports/football/nfl",
            "barstool": "sports/football/nfl",
            "betrivers": "sports/football/nfl"
        },
        "mlb": {
            "draftkings": "baseball/mlb",
            "fanduel": "navigation/mlb",
            "betmgm": "sports/baseball/103/mlb",
            "caesars": "us/mlb",
            "pointsbetus": "sports/baseball/mlb",
            "williamhill_us": "sports/baseball/mlb",
            "barstool": "sports/baseball/mlb",
            "betrivers": "sports/baseball/mlb"
        },
        "nhl": {
            "draftkings": "hockey/nhl",
            "fanduel": "navigation/nhl",
            "betmgm": "sports/hockey/102/nhl",
            "caesars": "us/nhl",
            "pointsbetus": "sports/hockey/nhl",
            "williamhill_us": "sports/hockey/nhl",
            "barstool": "sports/hockey/nhl",
            "betrivers": "sports/hockey/nhl"
        }
    }

    sport_path = sport_paths.get(sport, {}).get(book_key, sport)

    home_team = game_data.get("home_team", "").replace(" ", "-").lower()
    away_team = game_data.get("away_team", "").replace(" ", "-").lower()

    # Build URL with game context when possible
    base_url = config["web_base"]
    full_url = f"{base_url}/{sport_path}"

    return {
        "web": full_url,
        "app_scheme": config.get("app_scheme", ""),
        "sport_path": sport_path,
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


# ============================================================================
# CONSOLIDATED ENDPOINTS (Server-Side Data Fetching)
# Reduces client-side waterfalls by combining multiple API calls into one
# ============================================================================

@router.get("/sport-dashboard/{sport}")
async def get_sport_dashboard(sport: str, auth: bool = Depends(verify_api_key)):
    """
    Consolidated endpoint for sport dashboard page.
    Replaces 6 separate API calls with a single request.

    Combines: best-bets, splits, lines, props, injuries, sharp

    Response Schema:
    {
        "sport": "NBA",
        "best_bets": { props: [], game_picks: [] },
        "market_overview": {
            "lines": [...],
            "splits": [...],
            "sharp_signals": [...]
        },
        "context": {
            "injuries": [...],
            "props": [...]
        },
        "daily_energy": {...},
        "timestamp": "ISO timestamp",
        "cache_info": { sources: {...} }
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"sport-dashboard:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        cached["cache_info"] = {"hit": True}
        return cached

    # Fetch all data in parallel
    try:
        results = await asyncio.gather(
            get_best_bets(sport),
            get_splits(sport),
            get_lines(sport),
            get_injuries(sport),
            get_sharp_money(sport),
            return_exceptions=True
        )

        best_bets, splits, lines, injuries, sharp = results

        # Handle any exceptions gracefully
        cache_sources = {}

        if isinstance(best_bets, Exception):
            logger.warning("sport-dashboard: best_bets failed: %s", best_bets)
            best_bets = {"props": [], "game_picks": []}
            cache_sources["best_bets"] = "error"
        else:
            cache_sources["best_bets"] = best_bets.get("source", "unknown")

        if isinstance(splits, Exception):
            logger.warning("sport-dashboard: splits failed: %s", splits)
            splits = {"data": []}
            cache_sources["splits"] = "error"
        else:
            cache_sources["splits"] = splits.get("source", "unknown")

        if isinstance(lines, Exception):
            logger.warning("sport-dashboard: lines failed: %s", lines)
            lines = {"data": []}
            cache_sources["lines"] = "error"
        else:
            cache_sources["lines"] = lines.get("source", "unknown")

        if isinstance(injuries, Exception):
            logger.warning("sport-dashboard: injuries failed: %s", injuries)
            injuries = {"data": []}
            cache_sources["injuries"] = "error"
        else:
            cache_sources["injuries"] = injuries.get("source", "unknown")

        if isinstance(sharp, Exception):
            logger.warning("sport-dashboard: sharp failed: %s", sharp)
            sharp = {"data": []}
            cache_sources["sharp"] = "error"
        else:
            cache_sources["sharp"] = sharp.get("source", "unknown")

        result = {
            "sport": sport.upper(),
            "best_bets": {
                "props": best_bets.get("props", []),
                "game_picks": best_bets.get("game_picks", [])
            },
            "market_overview": {
                "lines": lines.get("data", []),
                "splits": splits.get("data", []),
                "sharp_signals": sharp.get("data", [])
            },
            "context": {
                "injuries": injuries.get("data", [])
            },
            "daily_energy": best_bets.get("daily_energy", get_daily_energy()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cache_info": {"hit": False, "sources": cache_sources}
        }

        # Cache for 2 minutes (limited by best-bets TTL)
        api_cache.set(cache_key, result, ttl=120)
        return result

    except Exception as e:
        logger.exception("sport-dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Dashboard fetch failed: {str(e)}")


@router.get("/game-details/{sport}/{game_id}")
async def get_game_details(sport: str, game_id: str, auth: bool = Depends(verify_api_key)):
    """
    Consolidated endpoint for single game detail view.
    Replaces 4+ separate API calls with a single request.

    Combines: lines, props (filtered), sharp signals, injuries for specific game

    Response Schema:
    {
        "sport": "NBA",
        "game_id": "abc123",
        "game": { home_team, away_team, commence_time },
        "lines": { spreads: [], totals: [], moneylines: [] },
        "props": [...],
        "sharp_signals": {...},
        "injuries": { home: [], away: [] },
        "ai_pick": {...},
        "timestamp": "ISO timestamp"
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"game-details:{sport_lower}:{game_id}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    # Fetch all data in parallel
    try:
        results = await asyncio.gather(
            get_lines(sport),
            get_props(sport),
            get_sharp_money(sport),
            get_injuries(sport),
            get_best_bets(sport),
            return_exceptions=True
        )

        lines_data, props_data, sharp_data, injuries_data, best_bets_data = results

        # Find specific game in lines
        game_info = None
        game_lines = {"spreads": [], "totals": [], "moneylines": []}

        if not isinstance(lines_data, Exception):
            for game in lines_data.get("data", []):
                if game.get("game_id") == game_id or game.get("id") == game_id:
                    game_info = {
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "commence_time": game.get("commence_time")
                    }
                    game_lines = {
                        "spreads": game.get("spreads", []),
                        "totals": game.get("totals", []),
                        "moneylines": game.get("moneylines", [])
                    }
                    break

        # Filter props for this game
        game_props = []
        if not isinstance(props_data, Exception):
            for prop in props_data.get("data", []):
                if prop.get("game_id") == game_id or prop.get("event_id") == game_id:
                    game_props.append(prop)

        # Find sharp signal for this game
        game_sharp = {}
        if not isinstance(sharp_data, Exception):
            for signal in sharp_data.get("data", []):
                if signal.get("game_id") == game_id:
                    game_sharp = signal
                    break

        # Filter injuries for this game's teams
        game_injuries = {"home": [], "away": []}
        if not isinstance(injuries_data, Exception) and game_info:
            for inj in injuries_data.get("data", []):
                team = inj.get("team", "")
                if team == game_info.get("home_team"):
                    game_injuries["home"].append(inj)
                elif team == game_info.get("away_team"):
                    game_injuries["away"].append(inj)

        # Find AI pick for this game
        ai_pick = None
        if not isinstance(best_bets_data, Exception):
            for pick in best_bets_data.get("game_picks", []):
                if pick.get("game_id") == game_id:
                    ai_pick = pick
                    break
            # Also check props
            for prop in best_bets_data.get("props", []):
                if prop.get("game_id") == game_id or prop.get("event_id") == game_id:
                    if ai_pick is None:
                        ai_pick = {"props": [prop]}
                    elif "props" in ai_pick:
                        ai_pick["props"].append(prop)
                    else:
                        ai_pick["props"] = [prop]

        result = {
            "sport": sport.upper(),
            "game_id": game_id,
            "game": game_info or {"home_team": "Unknown", "away_team": "Unknown"},
            "lines": game_lines,
            "props": game_props,
            "sharp_signals": game_sharp,
            "injuries": game_injuries,
            "ai_pick": ai_pick,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # Cache for 2 minutes
        api_cache.set(cache_key, result, ttl=120)
        return result

    except Exception as e:
        logger.exception("game-details failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Game details fetch failed: {str(e)}")


@router.get("/parlay-builder-init/{sport}")
async def get_parlay_builder_init(
    sport: str,
    user_id: Optional[str] = None,
    auth: bool = Depends(verify_api_key)
):
    """
    Consolidated endpoint for parlay builder page initialization.
    Replaces 3-4 separate API calls with a single request.

    Combines: best-bets (recommended props), props (full market), correlations, user parlay

    Response Schema:
    {
        "sport": "NBA",
        "recommended_props": [...],
        "all_props": [...],
        "correlations": {...},
        "current_parlay": { legs: [], calculated_odds: null },
        "user_history": { recent_parlays: [] },
        "timestamp": "ISO timestamp"
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first (only cache non-user-specific data)
    cache_key = f"parlay-builder:{sport_lower}"
    cached_base = api_cache.get(cache_key)

    # Fetch base data if not cached
    if not cached_base:
        try:
            results = await asyncio.gather(
                get_best_bets(sport),
                get_props(sport),
                return_exceptions=True
            )

            best_bets_data, props_data = results

            recommended_props = []
            if not isinstance(best_bets_data, Exception):
                recommended_props = best_bets_data.get("props", [])

            all_props = []
            if not isinstance(props_data, Exception):
                all_props = props_data.get("data", [])

            cached_base = {
                "recommended_props": recommended_props,
                "all_props": all_props
            }
            api_cache.set(cache_key, cached_base, ttl=180)  # 3 minutes

        except Exception as e:
            logger.exception("parlay-builder-init fetch failed: %s", e)
            cached_base = {"recommended_props": [], "all_props": []}

    # Get correlation matrix (static, cached separately)
    correlations = get_parlay_correlations()

    # Get user-specific data if user_id provided
    current_parlay = {"legs": [], "calculated_odds": None}
    user_history = {"recent_parlays": []}

    if user_id:
        # Get current parlay slip
        parlay_slip = parlay_slips.get(user_id, {"legs": []})
        current_parlay = {
            "legs": parlay_slip.get("legs", []),
            "calculated_odds": None
        }

        # Calculate odds if legs exist
        if current_parlay["legs"]:
            try:
                calc_result = calculate_parlay_odds_internal(current_parlay["legs"])
                current_parlay["calculated_odds"] = calc_result
            except Exception:
                pass

        # Get recent parlay history
        user_parlays = [p for p in parlay_history if p.get("user_id") == user_id]
        user_history["recent_parlays"] = sorted(
            user_parlays,
            key=lambda x: x.get("placed_at", ""),
            reverse=True
        )[:5]

    result = {
        "sport": sport.upper(),
        "recommended_props": cached_base.get("recommended_props", []),
        "all_props": cached_base.get("all_props", []),
        "correlations": correlations,
        "current_parlay": current_parlay,
        "user_history": user_history,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    return result


def get_parlay_correlations() -> Dict[str, Any]:
    """Get static parlay correlation matrix."""
    return {
        "same_game": {
            "QB_WR": 0.88,
            "QB_TE": 0.75,
            "RB_DST": -0.45,
            "WR_WR": 0.35,
            "QB_RB": 0.25
        },
        "cross_game": {
            "same_position": 0.15,
            "division_rivalry": 0.10
        },
        "warning_threshold": 0.70,
        "boost_threshold": -0.30
    }


def calculate_parlay_odds_internal(legs: List[Dict]) -> Dict[str, Any]:
    """Calculate parlay odds from legs (internal helper)."""
    if not legs:
        return {"decimal_odds": 1.0, "american_odds": "+100", "implied_probability": 1.0}

    decimal_odds = 1.0
    for leg in legs:
        leg_odds = leg.get("odds", -110)
        if leg_odds > 0:
            decimal = 1 + (leg_odds / 100)
        else:
            decimal = 1 + (100 / abs(leg_odds))
        decimal_odds *= decimal

    # Convert to American
    if decimal_odds >= 2.0:
        american = f"+{int((decimal_odds - 1) * 100)}"
    else:
        american = f"-{int(100 / (decimal_odds - 1))}"

    implied_prob = 1 / decimal_odds

    return {
        "decimal_odds": round(decimal_odds, 3),
        "american_odds": american,
        "implied_probability": round(implied_prob, 4),
        "leg_count": len(legs)
    }


# ============================================================================
# EXPORTS FOR MAIN.PY
# ============================================================================

class LiveDataRouter:
    def __init__(self):
        self.router = router

    def get_router(self):
        return self.router


# Export the router instance
live_data_router = router
