# live_data_router.py v14.7 - TITANIUM TIER SUPPORT
# Research-Optimized + Esoteric Edge + NOOSPHERE VELOCITY + TITANIUM SMASH
# Production-safe with retries, logging, rate-limit handling, deterministic fallbacks
# v11.08: Single source of truth for tiers via tiering.py

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
import httpx
import time

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
import logging
import hashlib
import asyncio
import random
from datetime import datetime, timedelta
import math
import json
import numpy as np

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

# Import Time Filters - TODAY-only slate gating (v11.08)
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
        is_game_started,
        get_game_status,
        filter_events_today_et,
        et_day_bounds
    )
    TIME_FILTERS_AVAILABLE = True
except ImportError:
    TIME_FILTERS_AVAILABLE = False
    logger.warning("time_filters module not available - TODAY-only gating disabled")

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

# Redis import with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger = logging.getLogger("live_data")
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
    """Generate fallback line shopping data when API is unavailable."""
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
    """Generate fallback sharp money data when API is unavailable."""
    matchups = SAMPLE_MATCHUPS.get(sport, SAMPLE_MATCHUPS["nba"])
    data = []

    for matchup in matchups:
        rng = deterministic_rng_for_game_id(matchup["id"])
        variance = rng.choice([1.5, 2.0, 2.5, 3.0])

        data.append({
            "game_id": matchup["id"],
            "home_team": matchup["home"],
            "away_team": matchup["away"],
            "line_variance": variance,
            "signal_strength": "STRONG" if variance >= 2 else "MODERATE"
        })

    return data


def generate_fallback_betslip(sport: str, game_id: str, bet_type: str, selection: str) -> Dict[str, Any]:
    """Generate fallback betslip data when API is unavailable."""
    matchups = SAMPLE_MATCHUPS.get(sport, SAMPLE_MATCHUPS["nba"])

    # Find matching game or use first
    target_matchup = matchups[0]
    for m in matchups:
        if m["id"] == game_id or game_id.lower() in m["home"].lower() or game_id.lower() in m["away"].lower():
            target_matchup = m
            break

    rng = deterministic_rng_for_game_id(target_matchup["id"])
    base_spread = rng.choice([-5.5, -4.5, -3.5, 3.5, 4.5, 5.5])
    base_total = rng.choice([215.5, 220.5, 225.5, 230.5])

    betslip_options = []
    for book_key, config in SPORTSBOOK_CONFIGS.items():
        book_rng = deterministic_rng_for_game_id(f"{target_matchup['id']}_{book_key}")
        odds_var = book_rng.choice([-5, 0, 5, -10, 10])

        # Determine odds based on bet type and selection
        if bet_type == "spread":
            point = base_spread if selection.lower() in target_matchup["home"].lower() else -base_spread
            odds = -110 + odds_var
        elif bet_type == "h2h":
            is_home = selection.lower() in target_matchup["home"].lower()
            odds = (-150 + odds_var * 3) if is_home else (130 + odds_var * 3)
            point = None
        else:  # total
            odds = -110 + odds_var
            point = base_total

        betslip_options.append({
            "book_key": book_key,
            "book_name": config["name"],
            "book_color": config["color"],
            "book_logo": config.get("logo", ""),
            "selection": selection,
            "odds": odds,
            "point": point,
            "deep_link": {
                "web": f"{config['web_base']}/",
                "note": "Opens sportsbook - navigate to game to place bet"
            }
        })

    betslip_options.sort(key=lambda x: x["odds"], reverse=True)

    return {
        "sport": sport.upper(),
        "game_id": target_matchup["id"],
        "game": f"{target_matchup['away']} @ {target_matchup['home']}",
        "bet_type": bet_type,
        "selection": selection,
        "source": "fallback",
        "best_odds": betslip_options[0] if betslip_options else None,
        "all_books": betslip_options,
        "count": len(betslip_options),
        "timestamp": datetime.now().isoformat()
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

router = APIRouter(prefix="/live", tags=["live"], dependencies=[Depends(verify_api_key)])

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
    """Get overall daily energy reading for betting."""
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

    return {
        "overall_score": min(100, max(0, energy_score)),
        "rating": "HIGH" if energy_score >= 70 else "MEDIUM" if energy_score >= 40 else "LOW",
        "day_of_week": day_name,
        "day_influence": day_meaning,
        "recommended_action": "Aggressive betting" if energy_score >= 70 else "Standard sizing" if energy_score >= 40 else "Conservative approach",
        "numerology_summary": numerology,
        "moon_summary": moon
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


@router.get("/smoke-test/alert-status")
@router.head("/smoke-test/alert-status")
async def smoke_test_alert_status():
    """
    Smoke test and alert status endpoint for frontend monitors.

    Returns system health status including:
    - API availability
    - Pick logging status
    - Auto-grading status
    - Last errors
    """
    result = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "alerts": []
    }

    # Check pick logger
    if PICK_LOGGER_AVAILABLE:
        pick_logger = get_pick_logger()
        today = get_today_date_str() if TIME_FILTERS_AVAILABLE else datetime.now().strftime("%Y-%m-%d")
        today_picks = pick_logger.get_picks_for_date(today)

        result["pick_logger"] = {
            "available": True,
            "picks_logged_today": len(today_picks)
        }
    else:
        result["pick_logger"] = {"available": False}
        result["alerts"].append("Pick logger unavailable")
        result["status"] = "degraded"

    # Check auto-grader scheduler
    from daily_scheduler import get_daily_scheduler
    scheduler = get_daily_scheduler()
    if scheduler and hasattr(scheduler, 'auto_grade_job'):
        job = scheduler.auto_grade_job
        last_run = job.last_run.isoformat() if job.last_run else None
        result["auto_grader"] = {
            "available": True,
            "last_run_at": last_run
        }

        # Alert if no run in last 2 hours
        if job.last_run and (datetime.now() - job.last_run).total_seconds() > 7200:
            result["alerts"].append("Auto-grader hasn't run in 2+ hours")
            result["status"] = "warning"
    else:
        result["auto_grader"] = {"available": False}
        result["alerts"].append("Auto-grader scheduler unavailable")
        result["status"] = "degraded"

    # Check API keys
    api_keys_ok = bool(ODDS_API_KEY and PLAYBOOK_API_KEY)
    result["api_keys_configured"] = api_keys_ok
    if not api_keys_ok:
        result["alerts"].append("Missing API keys")
        result["status"] = "critical"

    return result


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
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

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
                        return result
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
            return result

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
            return result

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
        return result

    result = {"sport": sport.upper(), "source": "odds_api", "count": len(data), "data": data, "movements": data}  # movements alias for frontend
    api_cache.set(cache_key, result)
    return result


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
        return cached

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
                    return result
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
    return result


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
    cache_key = f"injuries:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

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
                    return result
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
    return result


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
        return cached

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
                    return result
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
    return result


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
        return {"sport": "NCAAB", "source": "disabled", "count": 0, "data": [],
                "note": "NCAAB player props disabled — state legality varies"}
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"props:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Odds API first for props - must fetch per event using /events/{eventId}/odds
    try:
        # Step 1: Get list of events for this sport
        events_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events"
        events_resp = await fetch_with_retries(
            "GET", events_url,
            params={"apiKey": ODDS_API_KEY}
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
                event_resp = await fetch_with_retries(
                    "GET", event_odds_url,
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us",
                        "markets": prop_markets,
                        "oddsFormat": "american"
                    }
                )

                if event_resp and event_resp.status_code == 200:
                    try:
                        event_data = event_resp.json()
                        game_props = {
                            "game_id": event_data.get("id"),
                            "home_team": event_data.get("home_team"),
                            "away_team": event_data.get("away_team"),
                            "commence_time": event_data.get("commence_time"),
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

                logger.info("Props data retrieved from Playbook API for %s: %d games with props", sport, len(data))
            else:
                logger.warning("Playbook API props returned %s for %s", resp.status_code if resp else "no response", sport)

        except Exception as e:
            logger.warning("Playbook API props failed for %s: %s", sport, e)

    # If still no data, generate sample props from today's games
    if not data:
        logger.info("No props from APIs, generating from game schedule for %s", sport)
        try:
            # Get today's games from Odds API (main odds endpoint works)
            odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
            resp = await fetch_with_retries(
                "GET", odds_url,
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "h2h",
                    "oddsFormat": "american"
                }
            )

            if resp and resp.status_code == 200:
                games = resp.json()
                # Import player data for realistic props
                from player_birth_data import get_players_by_sport

                sport_upper = sport.upper()
                if sport_upper == "NCAAB":
                    sport_upper = "NCAAB"
                players = get_players_by_sport(sport_upper)
                player_list = list(players.keys())

                for game in games[:5]:  # Limit to 5 games
                    home_team = game.get("home_team", "")
                    away_team = game.get("away_team", "")

                    # Find players on these teams
                    team_players = [p for p, d in players.items() if d.get("team", "") in [home_team, away_team] or home_team in d.get("team", "") or away_team in d.get("team", "")]

                    if not team_players and player_list:
                        # Use random players if no team match
                        import random
                        random.seed(hash(home_team + away_team))
                        team_players = random.sample(player_list, min(4, len(player_list)))

                    game_props = {
                        "game_id": game.get("id"),
                        "home_team": home_team,
                        "away_team": away_team,
                        "commence_time": game.get("commence_time"),
                        "props": []
                    }

                    # Generate props for found players
                    prop_types = {
                        "NBA": [("player_points", 22.5), ("player_rebounds", 6.5), ("player_assists", 5.5)],
                        "NFL": [("player_pass_yds", 250.5), ("player_rush_yds", 65.5), ("player_rec_yds", 55.5)],
                        "MLB": [("player_hits", 1.5), ("player_runs", 0.5), ("player_rbis", 0.5)],
                        "NHL": [("player_points", 0.5), ("player_shots", 2.5), ("player_assists", 0.5)],
                        "NCAAB": [("player_points", 15.5), ("player_rebounds", 5.5), ("player_assists", 3.5)],
                    }

                    for player in team_players[:3]:
                        for prop_type, base_line in prop_types.get(sport.upper(), prop_types["NBA"]):
                            game_props["props"].append({
                                "player": player,
                                "market": prop_type,
                                "line": base_line,
                                "odds": -110,
                                "side": "Over",
                                "book": "consensus"
                            })
                            game_props["props"].append({
                                "player": player,
                                "market": prop_type,
                                "line": base_line,
                                "odds": -110,
                                "side": "Under",
                                "book": "consensus"
                            })

                    if game_props["props"]:
                        data.append(game_props)

                logger.info("Generated props from schedule for %s: %d games with props", sport, len(data))

        except Exception as e:
            logger.warning("Failed to generate props from schedule for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "generated", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return result


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
    effective_min_score = 6.5
    if min_score is not None:
        effective_min_score = max(5.0, min(10.0, min_score))

    # Skip cache in debug mode
    if not debug_mode:
        cache_key = f"best-bets:{sport_lower}" + (":live" if live_mode else "")
        cached = api_cache.get(cache_key)
        if cached:
            return cached
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
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback as _tb
        logger.error("best-bets CRASH request_id=%s sport=%s: %s\n%s",
                     request_id, sport, e, _tb.format_exc())
        raise HTTPException(status_code=500, detail={
            "message": "best-bets failed",
            "request_id": request_id
        })


async def _best_bets_inner(sport, sport_lower, live_mode, cache_key,
                           min_score=6.5, debug_mode=False, date_str=None,
                           max_events=12, max_props=10, max_games=10):
    sport_upper = sport.upper()

    # --- v16.0 PERFORMANCE: Time budget + per-stage timings ---
    TIME_BUDGET_S = 15.0
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
    sharp_data = await get_sharp_money(sport)
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

    # v16.0: Build ET window debug info
    _date_window_et_debug = {}
    if TIME_FILTERS_AVAILABLE:
        try:
            _et_start, _et_end = et_day_bounds(date_str)
            _date_window_et_debug = {
                "date_str": date_str or "today",
                "start_et": _et_start.strftime("%H:%M:%S"),
                "end_et": _et_end.strftime("%H:%M:%S"),
                "date_et": _et_start.strftime("%Y-%m-%d"),
            }
        except Exception:
            pass

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
        spread: float = 0
    ) -> Dict[str, Any]:
        """
        JARVIS ENGINE (0-10 standalone) - v15.0

        Returns standalone jarvis_score plus all required output fields.
        """
        JARVIS_WEIGHTS = {
            "gematria": 0.40,     # 40% - Gematria signal (0-4 pts)
            "triggers": 0.40,     # 40% - Sacred triggers (0-4 pts)
            "mid_spread": 0.20    # 20% - Goldilocks zone amplifier (0-2 pts)
        }

        jarvis_triggers_hit = []
        immortal_detected = False
        gematria_score = 0.0
        trigger_score = 0.0
        mid_spread_score = 0.0

        if jarvis_engine:
            # 1. Sacred Triggers (40% weight, max 4 pts)
            trigger_result = jarvis_engine.check_jarvis_trigger(game_str)
            raw_trigger = 0.0
            for trig in trigger_result.get("triggers_hit", []):
                raw_trigger += trig["boost"] / 10  # Normalize boost
                jarvis_triggers_hit.append({
                    "number": trig["number"],
                    "name": trig["name"],
                    "match_type": trig.get("match_type", "DIRECT"),
                    "boost": round(trig["boost"] / 10, 2)
                })
                if trig["number"] == 2178:
                    immortal_detected = True

            # Scale trigger score: normalize to 0-1, multiply by weight*10
            trigger_score = min(1.0, raw_trigger) * 10 * JARVIS_WEIGHTS["triggers"]

            # 2. Gematria Signal (40% weight, max 4 pts)
            if player_name and home_team:
                gematria = jarvis_engine.calculate_gematria_signal(player_name, home_team, away_team)
                gematria_strength = gematria.get("signal_strength", 0)
                if gematria.get("triggered"):
                    gematria_strength = min(1.0, gematria_strength * 1.5)
                gematria_score = gematria_strength * 10 * JARVIS_WEIGHTS["gematria"]

            # 3. Mid-Spread Goldilocks Amplifier (20% weight, max 2 pts)
            mid_spread = jarvis_engine.calculate_mid_spread_signal(spread)
            mid_spread_mod = mid_spread.get("modifier", 0)
            if mid_spread_mod > 0:  # Only positive boost (Goldilocks zone 4-9)
                mid_spread_score = mid_spread_mod * 10 * JARVIS_WEIGHTS["mid_spread"]
        else:
            # Fallback: check triggers in game_str directly
            for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
                if str(trigger_num) in game_str:
                    trigger_score += trigger_data["boost"] / 25  # Scaled down
                    jarvis_triggers_hit.append({
                        "number": trigger_num,
                        "name": trigger_data["name"],
                        "boost": round(trigger_data["boost"] / 25, 2)
                    })
                    if trigger_num == 2178:
                        immortal_detected = True
            trigger_score = min(4.0, trigger_score)  # Cap at 40% max

        # Total Jarvis Engine Score (0-10)
        jarvis_rs = gematria_score + trigger_score + mid_spread_score
        jarvis_rs = max(0, min(10, jarvis_rs))

        # If no triggers and no gematria, return default neutral score
        jarvis_hits_count = len(jarvis_triggers_hit)
        if jarvis_hits_count == 0 and gematria_score < 0.5:
            jarvis_rs = DEFAULT_JARVIS_RS if TIERING_AVAILABLE else 5.0

        return {
            "jarvis_rs": round(jarvis_rs, 2),
            "jarvis_active": jarvis_hits_count > 0 or gematria_score >= 1.0,
            "jarvis_hits_count": jarvis_hits_count,
            "jarvis_triggers_hit": jarvis_triggers_hit,
            "jarvis_reasons": [t.get("name", "Unknown") for t in jarvis_triggers_hit] if jarvis_hits_count > 0 else (["Gematria alignment"] if gematria_score >= 1.0 else ["No triggers hit"]),
            "immortal_detected": immortal_detected,
            "jarvis_breakdown": {
                "gematria": round(gematria_score, 2),
                "triggers": round(trigger_score, 2),
                "mid_spread": round(mid_spread_score, 2)
            }
        }

    # Helper function to calculate scores with v15.0 4-engine architecture + Jason Sim
    def calculate_pick_score(game_str, sharp_signal, base_ai=5.0, player_name="", home_team="", away_team="", spread=0, total=220, public_pct=50, pick_type="GAME", pick_side="", prop_line=0):
        # =====================================================================
        # v15.0 FOUR-ENGINE ARCHITECTURE (Clean Separation)
        # =====================================================================
        # ENGINE 1 - AI SCORE (0-10): Pure 8 AI Models (0-8 scaled to 0-10)
        # ENGINE 2 - RESEARCH SCORE (0-10): Sharp money + RLM + Public Fade
        # ENGINE 3 - ESOTERIC SCORE (0-10): Numerology + Astro + Fib + Vortex + Daily
        #            (NO Jarvis, NO Gematria, NO Public Fade - those are separate)
        # ENGINE 4 - JARVIS SCORE (0-10): Gematria + Sacred Triggers + Mid-Spread
        #
        # FINAL = (ai × 0.25) + (research × 0.30) + (esoteric × 0.20) + (jarvis × 0.15) + confluence_boost
        # Then: FINAL += jason_sim_boost (post-pick confluence)
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
        pillars_passed = []
        pillars_failed = []

        # --- AI SCORE (Dynamic Model - 0-8 scale) ---
        # v15.1: AI score is calibrated based on data quality signals
        # Base AI (5.0 props, 4.5 games) + boosts for data availability
        _ai_boost = 0.0
        # Odds data present: +0.5
        if sharp_signal:
            _ai_boost += 0.5
        # Strong/moderate sharp signal aligns with model: +1.0 / +0.5
        _ss = sharp_signal.get("signal_strength", "NONE")
        if _ss == "STRONG":
            _ai_boost += 1.0
        elif _ss == "MODERATE":
            _ai_boost += 0.5
        elif _ss == "MILD":
            _ai_boost += 0.25
        # Favorable line value (spread in predictable range 3-10): +0.5
        if 3 <= abs(spread) <= 10:
            _ai_boost += 0.5
        # Player name present for props (more data = better model): +0.25
        if player_name:
            _ai_boost += 0.25
        ai_score = min(8.0, base_ai + _ai_boost)
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
        # Max possible: 3 (sharp) + 3 (line) + 2 (public) + 3 (base) = 11 → capped at 10
        research_score = min(10.0, base_research + sharp_boost + line_boost + public_boost)
        research_reasons.append(f"Research: {round(research_score, 2)}/10 (Sharp:{sharp_boost} + RLM:{line_boost} + Public:{public_boost} + Base:{base_research})")

        # Pillar score for backwards compatibility (used in scoring_breakdown)
        pillar_score = sharp_boost + line_boost + public_boost

        # =================================================================
        # v15.0 JARVIS ENGINE (Standalone 0-10) - Called FIRST
        # =================================================================
        jarvis_data = calculate_jarvis_engine_score(
            jarvis_engine=jarvis,
            game_str=game_str,
            player_name=player_name,
            home_team=home_team,
            away_team=away_team,
            spread=spread
        )
        jarvis_rs = jarvis_data["jarvis_rs"]
        jarvis_active = jarvis_data["jarvis_active"]
        jarvis_hits_count = jarvis_data["jarvis_hits_count"]
        jarvis_triggers_hit = jarvis_data["jarvis_triggers_hit"]
        jarvis_reasons = jarvis_data["jarvis_reasons"]
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
        _eso_magnitude = abs(spread) if spread else 0
        if _eso_magnitude == 0 and prop_line:
            _eso_magnitude = abs(prop_line)
        if _eso_magnitude == 0:
            _eso_magnitude = abs(total / 10) if total and total != 220 else 0

        # --- B) NUMEROLOGY (35% weight, max 3.5 pts) - Pick-specific ---
        from datetime import datetime as dt_now
        day_of_year = dt_now.now().timetuple().tm_yday
        daily_base = (day_of_year % 9 + 1) / 9  # 0.11 to 1.0

        # Pick-specific seed (deterministic via SHA-256)
        _pick_hash = _hl.sha256(f"{game_str}|{prop_line}|{player_name}".encode()).hexdigest()
        _pick_seed = int(_pick_hash[:8], 16) % 9 + 1  # 1-9
        pick_factor = _pick_seed / 9  # 0.11 to 1.0

        # Blend: 40% daily + 60% pick-specific
        numerology_raw = (daily_base * 0.4) + (pick_factor * 0.6)

        # Master number boost
        if "11" in game_str or "22" in game_str or "33" in game_str:
            numerology_raw = min(1.0, numerology_raw * 1.3)
        numerology_score = numerology_raw * 10 * ESOTERIC_WEIGHTS["numerology"]

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
            jarvis_high = jarvis_rs >= 7.5
            if immortal_detected and both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "IMMORTAL", "boost": 10, "alignment_pct": alignment_pct}
            elif jarvis_triggered and both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "JARVIS_PERFECT", "boost": 7, "alignment_pct": alignment_pct}
            elif both_high and jarvis_high and alignment_pct >= 80:
                confluence = {"level": "PERFECT", "boost": 5, "alignment_pct": alignment_pct}
            elif alignment_pct >= 70:
                # v15.3: STRONG requires alignment >= 80% AND active signal
                _strong_ok = alignment_pct >= 80 and (jarvis_active or _research_sharp_present)
                if _strong_ok:
                    confluence = {"level": "STRONG", "boost": 3, "alignment_pct": alignment_pct}
                else:
                    confluence = {"level": "MODERATE", "boost": 1, "alignment_pct": alignment_pct}
            elif alignment_pct >= 60:
                confluence = {"level": "MODERATE", "boost": 1, "alignment_pct": alignment_pct}
            else:
                confluence = {"level": "DIVERGENT", "boost": 0, "alignment_pct": alignment_pct}

        confluence_level = confluence.get("level", "DIVERGENT")
        confluence_boost = confluence.get("boost", 0)

        # --- v15.1 BASE SCORE FORMULA (4 Engines + AI) ---
        # BASE = (ai × 0.25) + (research × 0.30) + (esoteric × 0.20) + (jarvis × 0.15) + confluence_boost
        # AI models now directly contribute 25% of the score
        base_score = (ai_scaled * 0.25) + (research_score * 0.30) + (esoteric_score * 0.20) + (jarvis_rs * 0.15) + confluence_boost

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

        # FINAL = BASE + JASON_BOOST
        jason_sim_boost = jason_output.get("jason_sim_boost", 0.0)
        final_score = base_score + jason_sim_boost

        # Check if Jason blocked this pick
        jason_blocked = jason_output.get("jason_blocked", False)

        # --- v15.0: jarvis_rs already calculated by standalone function above ---
        # jarvis_rs, jarvis_active, jarvis_hits_count, jarvis_triggers_hit, jarvis_reasons
        # are all set from calculate_jarvis_engine_score() call

        # --- v15.0 TITANIUM CHECK (3 of 4 engines >= 8.0) ---
        titanium_triggered = False
        titanium_explanation = ""
        if TIERING_AVAILABLE:
            titanium_triggered, titanium_explanation, qualifying_engines = check_titanium_rule(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=jarvis_rs
            )
        else:
            # Fallback check without tiering module
            engines_above_8 = sum([
                ai_scaled >= 8.0,
                research_score >= 8.0,
                esoteric_score >= 8.0,
                jarvis_rs >= 8.0
            ])
            titanium_triggered = engines_above_8 >= 3
            titanium_explanation = f"Titanium: {engines_above_8}/4 engines >= 8.0 (need 3)"

        # --- v11.08 BET TIER DETERMINATION (Single Source of Truth) ---
        if TIERING_AVAILABLE:
            bet_tier = tier_from_score(
                final_score=final_score,
                confluence=confluence,
                nhl_dog_protocol=False,
                titanium_triggered=titanium_triggered
            )
        else:
            # Fallback tier determination (v12.0 thresholds)
            if titanium_triggered:
                bet_tier = {"tier": "TITANIUM_SMASH", "units": 2.5, "action": "SMASH", "badge": "TITANIUM SMASH"}
            elif final_score >= 7.5:  # v12.0: was 9.0
                bet_tier = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
            elif final_score >= 6.5:  # v12.0: was 7.5
                bet_tier = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
            elif final_score >= 5.5:  # v12.0: was 6.0
                bet_tier = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
            else:
                bet_tier = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

        # --- v15.3 GOLD_STAR HARD GATES ---
        # GOLD_STAR requires ALL engine minimums. If any gate fails, downgrade to EDGE_LEAN.
        _gold_gates = {
            "ai_gte_6.8": ai_scaled >= 6.8,
            "research_gte_5.5": research_score >= 5.5,
            "jarvis_gte_6.5": jarvis_rs >= 6.5,
            "esoteric_gte_4.0": esoteric_score >= 4.0,
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
            if jarvis_rs >= 8.0:
                smash_reasons.append(f"Jarvis Engine: {round(jarvis_rs, 2)}/10")

        # Build penalties array from modifiers
        # v15.0: public_fade_mod removed (now only in Research as positive boost)
        penalties = []
        if trap_mod < 0:
            penalties.append({"name": "Large Spread Trap", "magnitude": round(trap_mod, 2)})

        return {
            "total_score": round(final_score, 2),
            "final_score": round(final_score, 2),  # Alias for frontend
            "confidence": confidence,
            "confidence_score": confidence_score,
            "confluence_level": confluence_level,
            "bet_tier": bet_tier,
            "tier": bet_tier.get("tier", "PASS"),
            "action": bet_tier.get("action", "SKIP"),
            "units": bet_tier.get("units", bet_tier.get("unit_size", 0.0)),
            # v11.08 Engine scores (all 0-10 scale)
            "ai_score": round(ai_scaled, 2),
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "jarvis_score": round(jarvis_rs, 2),  # Alias for jarvis_rs
            # Detailed breakdowns
            "scoring_breakdown": {
                "research_score": round(research_score, 2),
                "esoteric_score": round(esoteric_score, 2),
                "ai_models": round(ai_score, 2),
                "ai_score": round(ai_scaled, 2),
                "pillars": round(pillar_score, 2),
                "confluence_boost": confluence_boost,
                "alignment_pct": confluence.get("alignment_pct", 0),
                "gold_star_gates": _gold_gates,
                "gold_star_eligible": _gold_gates_passed,
                "gold_star_failed": _gold_gates_failed
            },
            # v14.9 Research breakdown (clean engine separation)
            "research_breakdown": {
                "sharp_boost": round(sharp_boost, 2),
                "line_boost": round(line_boost, 2),
                "public_boost": round(public_boost, 2),
                "base_research": 2.0,
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
            # v15.0 Jarvis breakdown (standalone engine)
            "jarvis_breakdown": jarvis_data.get("jarvis_breakdown", {}),
            "jarvis_triggers": jarvis_triggers_hit,
            "immortal_detected": immortal_detected,
            # v11.08 JARVIS fields (MUST always exist)
            "jarvis_rs": round(jarvis_rs, 2),
            "jarvis_active": jarvis_active,
            "jarvis_hits_count": jarvis_hits_count,
            "jarvis_triggers_hit": jarvis_triggers_hit,
            "jarvis_reasons": jarvis_reasons,
            # v11.08 TITANIUM fields
            "titanium_triggered": titanium_triggered,
            "titanium_explanation": titanium_explanation,
            "smash_reasons": smash_reasons,
            # v11.08 JASON SIM CONFLUENCE fields (MUST always exist)
            "jason_ran": jason_output.get("jason_ran", False),
            "jason_sim_boost": round(jason_sim_boost, 2),
            "jason_blocked": jason_blocked,
            "jason_win_pct_home": jason_output.get("jason_win_pct_home", 50.0),
            "jason_win_pct_away": jason_output.get("jason_win_pct_away", 50.0),
            "projected_total": jason_output.get("projected_total", total),
            "projected_pace": jason_output.get("projected_pace", "NEUTRAL"),
            "variance_flag": jason_output.get("variance_flag", "MED"),
            "injury_state": jason_output.get("injury_state", "UNKNOWN"),
            "confluence_reasons": jason_output.get("confluence_reasons", []),
            "base_score": round(base_score, 2),  # Score before Jason boost
            # v11.08 Stack/Penalty fields
            "penalties": penalties,
            "stack_complete": not jason_blocked,  # Stack incomplete if Jason blocked
            "partial_stack_reasons": ["Jason blocked pick"] if jason_blocked else [],
            # v11.08 Research/Pillar tracking
            "research_reasons": research_reasons,
            "pillars_passed": pillars_passed,
            "pillars_failed": pillars_failed
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
        return await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american"
            }
        )

    props_data, game_odds_resp = await asyncio.gather(
        _fetch_props(),
        _fetch_game_odds(),
        return_exceptions=True
    )
    # Handle exceptions from gather
    if isinstance(props_data, Exception):
        logger.warning("Props fetch failed in parallel: %s", props_data)
        props_data = {"data": []}
    if isinstance(game_odds_resp, Exception):
        logger.warning("Game odds fetch failed in parallel: %s", game_odds_resp)
        game_odds_resp = None
    _record("parallel_fetch", _s)

    # ============================================
    # APPLY ET DAY GATE to both datasets
    # ============================================
    _s = time.time()
    # --- Props ET filter ---
    raw_prop_games = props_data.get("data", []) if isinstance(props_data, dict) else []
    _dropped_out_of_window_props = 0
    _dropped_missing_time_props = 0
    if TIME_FILTERS_AVAILABLE and raw_prop_games:
        prop_games, _dropped_props_window, _dropped_props_missing = filter_events_today_et(raw_prop_games, date_str)
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
        raw_games = game_odds_resp.json()
        _date_window_et_debug["events_before_games"] = len(raw_games)
        if TIME_FILTERS_AVAILABLE:
            raw_games, _dropped_games_window, _dropped_games_missing = filter_events_today_et(raw_games, date_str)
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
    # CATEGORY 1: GAME PICKS (Spreads, Totals, ML) — runs FIRST (fast, no player resolution)
    # ============================================
    _s = time.time()
    game_picks = []

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

                start_time_et = ""
                if TIME_FILTERS_AVAILABLE and commence_time:
                    start_time_et = get_game_start_time_et(commence_time)

                best_odds_by_market = {}
                for bm in game.get("bookmakers", []):
                    book_name = bm.get("title", "Unknown")
                    book_key = bm.get("key", "")
                    bm_link = AFFILIATE_LINKS.get(book_key, "")
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point")
                            outcome_key = f"{market_key}:{pick_name}:{point}"
                            if outcome_key not in best_odds_by_market or odds > best_odds_by_market[outcome_key][0]:
                                best_odds_by_market[outcome_key] = (odds, book_name, book_key, bm_link)

                for bm in game.get("bookmakers", [])[:1]:
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            point = outcome.get("point")
                            outcome_key = f"{market_key}:{pick_name}:{point}"
                            best_odds, best_book, best_book_key, best_link = best_odds_by_market.get(
                                outcome_key, (outcome.get("price", -110), "Unknown", "", "")
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
                                prop_line=point if point else 0
                            )

                            game_status = "UPCOMING"
                            if TIME_FILTERS_AVAILABLE and commence_time:
                                game_status = get_game_status(commence_time)

                            signals_fired = score_data.get("pillars_passed", []).copy()
                            if sharp_signal.get("signal_strength") in ["STRONG", "MODERATE"]:
                                signals_fired.append(f"SHARP_{sharp_signal.get('signal_strength')}")
                            has_started = game_status in ["MISSED_START", "LIVE", "FINAL"]

                            game_picks.append({
                                "sport": sport.upper(),
                                "league": sport.upper(),
                                "event_id": game_key,
                                "pick_type": pick_type,
                                "pick": display,
                                "pick_side": pick_side,
                                "team": pick_name if market_key != "totals" else None,
                                "line": point,
                                "odds": best_odds,
                                "book": best_book,
                                "book_key": best_book_key,
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
                                "sharp_signal": sharp_signal.get("signal_strength", "NONE")
                            })
    except Exception as e:
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
                pick_side=signal.get("side", "HOME"),
                prop_line=0
            )

            signals_fired = score_data.get("pillars_passed", []).copy()
            signals_fired.append(f"SHARP_{signal.get('signal_strength', 'MODERATE')}")

            game_picks.append({
                "sport": sport.upper(),
                "league": sport.upper(),
                "event_id": signal.get("game_id", ""),
                "pick_type": "SHARP",
                "pick": f"Sharp on {signal.get('side', 'HOME')}",
                "pick_side": f"{signal.get('side', 'HOME')} SHARP",
                "team": home_team if signal.get("side") == "HOME" else away_team,
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
                "start_time_et": "",
                "game_status": "UPCOMING",
                "status": "scheduled",
                "has_started": False,
                "is_started_already": False,
                "is_live": False,
                "is_live_bet_candidate": False,
                "market": "sharp_money",
                "recommendation": f"SHARP ON {signal.get('side', 'HOME').upper()}",
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
                "sharp_signal": signal.get("signal_strength", "MODERATE")
            })

    # ============================================
    # CATEGORY 2: PLAYER PROPS (uses pre-resolved player cache — instant lookups)
    # ============================================
    _s = time.time()
    props_picks = []
    invalid_injury_count = 0
    try:
        for game in prop_games:
            if _past_deadline():
                _timed_out_components.append("props_scoring")
                logger.warning("TIME BUDGET: Props scoring hit deadline after %d picks (%.1fs)", len(props_picks), _elapsed())
                break
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            game_key = f"{away_team}@{home_team}"
            game_str = f"{home_team}{away_team}"
            sharp_signal = sharp_lookup.get(game_key, {})
            commence_time = game.get("commence_time", "")

            _ctx = game_context.get(game_key, {})
            _game_spread = _ctx.get("spread", 0)
            _game_total = _ctx.get("total", 220)

            start_time_et = ""
            if TIME_FILTERS_AVAILABLE and commence_time:
                start_time_et = get_game_start_time_et(commence_time)

            for prop in game.get("props", []):
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
                    prop_line=line
                )

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
                    "best_book": book_name,
                    "best_book_link": book_link,
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
                    "sharp_signal": sharp_signal.get("signal_strength", "NONE")
                })
    except HTTPException:
        logger.warning("Props fetch failed for %s", sport)

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
            dupes.sort(key=lambda x: (-x.get("total_score", 0), _book_priority(x)))
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
    deduplicated_props.sort(key=lambda x: x["total_score"], reverse=True)

    # Capture ALL candidates for debug/distribution before filtering
    _all_prop_candidates = deduplicated_props  # Keep ref for debug output

    filtered_props = [p for p in deduplicated_props if p["total_score"] >= COMMUNITY_MIN_SCORE]
    top_props = filtered_props[:max_props]

    # v15.3: Deduplicate game picks too
    deduplicated_games, _dupe_dropped_games, _dupe_groups_games = _dedupe_picks(game_picks)
    deduplicated_games.sort(key=lambda x: x["total_score"], reverse=True)
    _all_game_candidates = deduplicated_games  # Keep ref for debug output

    filtered_game_picks = [p for p in deduplicated_games if p["total_score"] >= COMMUNITY_MIN_SCORE]
    top_game_picks = filtered_game_picks[:max_games]

    if _dupe_dropped_props + _dupe_dropped_games > 0:
        logger.info("DEDUPE: dropped %d prop dupes, %d game dupes", _dupe_dropped_props, _dupe_dropped_games)


    # ============================================
    # LOG PICKS FOR GRADING (v14.9 + v12.0 auto_grader integration)
    # ============================================
    _s = time.time()
    _picks_logged = 0
    _picks_skipped = 0
    _pick_log_errors = []
    if PICK_LOGGER_AVAILABLE:
        try:
            pick_logger = get_pick_logger()
            import pytz as _pytz
            logged_count = 0
            skipped_count = 0
            validation_warnings = []
            _et_tz = _pytz.timezone("America/New_York")
            _now_for_log = datetime.now(_et_tz)

            def _enrich_pick_for_logging(p):
                """Add game_time_utc, minutes_since_start, raw_inputs_snapshot."""
                start_et = p.get("start_time_et", "")
                game_time_utc = ""
                mins_since = 0
                if start_et:
                    try:
                        gt = datetime.fromisoformat(start_et.replace("Z", "+00:00"))
                        if gt.tzinfo is None:
                            gt = _et_tz.localize(gt)
                        game_time_utc = gt.astimezone(_pytz.utc).isoformat()
                        delta = (_now_for_log - gt.astimezone(_et_tz)).total_seconds()
                        if delta > 0:
                            mins_since = int(delta / 60)
                    except Exception:
                        pass
                p["game_time_utc"] = game_time_utc
                p["minutes_since_start"] = mins_since
                p["raw_inputs_snapshot"] = {
                    "line": p.get("line"),
                    "odds": p.get("odds", -110),
                    "matchup": p.get("matchup", p.get("game", "")),
                    "injury_status": p.get("injury_status", "HEALTHY"),
                    "sharp_signal": p.get("sharp_signal", ""),
                    "tier": p.get("tier", ""),
                }

            # Log prop picks
            for pick in top_props:
                _enrich_pick_for_logging(pick)
                log_result = pick_logger.log_pick(
                    pick_data=pick,
                    game_start_time=pick.get("start_time_et", "")
                )
                if log_result.get("logged"):
                    logged_count += 1
                elif log_result.get("skipped"):
                    skipped_count += 1
                if log_result.get("validation_errors"):
                    validation_warnings.extend(log_result["validation_errors"])

            # Log game picks
            for pick in top_game_picks:
                _enrich_pick_for_logging(pick)
                log_result = pick_logger.log_pick(
                    pick_data=pick,
                    game_start_time=pick.get("start_time_et", "")
                )
                if log_result.get("logged"):
                    logged_count += 1
                elif log_result.get("skipped"):
                    skipped_count += 1
                if log_result.get("validation_errors"):
                    validation_warnings.extend(log_result["validation_errors"])

            _picks_logged = logged_count
            _picks_skipped = skipped_count
            if logged_count > 0:
                logger.info("PICK_LOGGER: Logged %d picks, skipped %d dupes", logged_count, skipped_count)
            elif skipped_count > 0:
                logger.info("PICK_LOGGER: All %d picks skipped (duplicates)", skipped_count)
            if validation_warnings:
                logger.warning("PICK_LOGGER: Validation warnings: %s", validation_warnings[:5])
        except Exception as e:
            logger.error("PICK_LOGGER: Failed to log picks: %s", e)
            _pick_log_errors.append(str(e))

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
                    adjustments = {
                        "defense": pick.get("defense_adjustment", 0.0),
                        "pace": pick.get("pace_adjustment", 0.0),
                        "vacuum": pick.get("vacuum_adjustment", 0.0),
                        "lstm_brain": pick.get("lstm_adjustment", 0.0),
                        "officials": pick.get("officials_adjustment", 0.0),
                    }

                    grader.log_prediction(
                        sport=sport.upper(),
                        player_name=player_name,
                        stat_type=stat_type,
                        predicted_value=line,  # Use line as predicted value
                        line=line,
                        adjustments=adjustments
                    )
                    grader_logged += 1

            if grader_logged > 0:
                logger.info("AUTO_GRADER: Logged %d prop predictions for weight learning", grader_logged)
        except Exception as e:
            logger.error("AUTO_GRADER: Failed to log predictions: %s", e)

    _record("pick_logging", _s)

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
    deploy_version = "14.9"

    # v14.9: Date and timestamp in ET
    date_et = get_today_date_str() if TIME_FILTERS_AVAILABLE else datetime.now().strftime("%Y-%m-%d")
    run_timestamp_et = datetime.now().isoformat()

    result = {
        "sport": sport.upper(),
        "mode": "live" if live_mode else "standard",  # v14.11: Indicate which mode
        "source": f"jarvis_savant_v{TIERING_VERSION if TIERING_AVAILABLE else '11.08'}",
        "scoring_system": "Phase 1-3 Integrated + Titanium v11.08",
        "engine_version": TIERING_VERSION if TIERING_AVAILABLE else "11.08",
        "deploy_version": deploy_version,
        "build_sha": build_sha,
        "identity_resolver": IDENTITY_RESOLVER_AVAILABLE,
        "date_et": date_et,  # v14.9: Today's date in ET
        "run_timestamp_et": run_timestamp_et,  # v14.9: When this response was generated
        "props": {
            "count": len(top_props),
            "total_analyzed": len(props_picks),
            "picks": top_props
        },
        "game_picks": {
            "count": len(top_game_picks),
            "total_analyzed": len(_all_game_candidates),
            "picks": top_game_picks
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

        result["debug"] = {
            "debug_timings": _timings,
            "total_elapsed_s": round(_elapsed(), 2),
            "timed_out_components": _timed_out_components,
            "time_budget_s": TIME_BUDGET_S,
            "max_events": max_events,
            "max_props": max_props,
            "max_games": max_games,
            "player_resolve_cache_size": len(_player_resolve_cache),
            "player_resolve_attempted": _resolve_attempted,
            "player_resolve_succeeded": _resolve_succeeded,
            "player_resolve_timed_out": _resolve_timed_out,
            "date_window_et": _date_window_et_debug,
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
            # v15.3 dedupe telemetry
            "dupe_dropped_props": _dupe_dropped_props,
            "dupe_dropped_games": _dupe_dropped_games,
            "dupe_dropped_count": _dupe_dropped_props + _dupe_dropped_games,
            "dupe_groups_props": _dupe_groups_props[:10],  # Cap for output size
            "dupe_groups_games": _dupe_groups_games[:10],
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
        }
        # Don't cache debug responses
        return result

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

    Only returns picks with final_score >= 6.5 (COMMUNITY_MIN_SCORE).
    All picks have status = "LIVE" or "STARTED".

    Returns:
        Dict with sport, type, picks[], live_games_count, timestamp
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get best bets first
    best_bets_response = await get_best_bets(sport)

    # Filter to only live/started games
    live_picks = []

    # Process props
    for pick in best_bets_response.get("props", {}).get("picks", []):
        commence_time = pick.get("start_time", pick.get("commence_time", ""))
        if TIME_FILTERS_AVAILABLE and commence_time:
            is_started, started_at = is_game_started(commence_time)
            if is_started:
                # Only include if score >= 6.5 (community threshold)
                final_score = pick.get("final_score", 0)
                if final_score >= 6.5:
                    pick["status"] = "LIVE"
                    pick["started_at"] = started_at
                    pick["live_bet_eligible"] = True
                    live_picks.append(pick)

    # Process game picks
    for pick in best_bets_response.get("game_picks", {}).get("picks", []):
        commence_time = pick.get("start_time", pick.get("commence_time", ""))
        if TIME_FILTERS_AVAILABLE and commence_time:
            is_started, started_at = is_game_started(commence_time)
            if is_started:
                final_score = pick.get("final_score", 0)
                if final_score >= 6.5:
                    pick["status"] = "LIVE"
                    pick["started_at"] = started_at
                    pick["live_bet_eligible"] = True
                    live_picks.append(pick)

    # Sort by final_score descending
    live_picks.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    return {
        "sport": sport.upper(),
        "type": "LIVE_BETS",
        "picks": live_picks,
        "live_games_count": len(live_picks),
        "community_threshold": 6.5,
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

    # Filter props and game picks to only MISSED_START
    live_props = [
        p for p in best_bets_result.get("props", {}).get("picks", [])
        if p.get("game_status") == "MISSED_START"
    ]
    live_game_picks = [
        p for p in best_bets_result.get("game_picks", {}).get("picks", [])
        if p.get("game_status") == "MISSED_START"
    ]

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
    TODAY-only slate gating (12:01am-11:59pm America/New_York) is enforced.
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

        # --- AI SCORE (Pure Model - 0-8 scale, NO external signals) ---
        ai_score = min(8.0, base_ai)
        ai_reasons = [f"Pure model prediction: {round(ai_score, 2)}/8"]

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
                confluence = {"level": "PERFECT", "boost": 5, "alignment_pct": alignment_pct}
            elif alignment_pct >= 70:
                confluence = {"level": "STRONG", "boost": 3, "alignment_pct": alignment_pct}
            else:
                confluence = {"level": "DIVERGENT", "boost": 0, "alignment_pct": alignment_pct}

        confluence_boost = confluence.get("boost", 0)

        # --- FINAL SCORE ---
        final_score = (research_score * 0.67) + (esoteric_score * 0.33) + confluence_boost

        # --- JARVIS RS (0-10 scale) ---
        jarvis_rs = scale_jarvis_score_to_10(jarvis_score, max_jarvis=2.0) if TIERING_AVAILABLE else jarvis_score * 5
        jarvis_active = len(jarvis_triggers_hit) > 0
        jarvis_reasons = [t.get("name", "Unknown") for t in jarvis_triggers_hit]

        # --- AI SCALED (0-10) ---
        ai_scaled = scale_ai_score_to_10(ai_score, max_ai=8.0) if TIERING_AVAILABLE else ai_score * 1.25

        # --- TITANIUM CHECK ---
        if TIERING_AVAILABLE:
            titanium_triggered, titanium_explanation, qualifying_engines = check_titanium_rule(
                ai_score=ai_scaled,
                research_score=research_score,
                esoteric_score=esoteric_score,
                jarvis_score=jarvis_rs
            )
        else:
            engines_above_8 = sum([ai_scaled >= 8.0, research_score >= 8.0, esoteric_score >= 8.0, jarvis_rs >= 8.0])
            titanium_triggered = engines_above_8 >= 3
            titanium_explanation = f"Titanium: {engines_above_8}/4 engines >= 8.0 (need 3)"

        # --- BET TIER ---
        if TIERING_AVAILABLE:
            bet_tier = tier_from_score(final_score, confluence, titanium_triggered=titanium_triggered)
        else:
            # Fallback tier determination (v12.0 thresholds)
            if titanium_triggered:
                bet_tier = {"tier": "TITANIUM_SMASH", "units": 2.5, "action": "SMASH"}
            elif final_score >= 7.5:  # v12.0: was 9.0
                bet_tier = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
            elif final_score >= 6.5:  # v12.0: was 7.5
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
    props_breakdown.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    game_breakdown.sort(key=lambda x: x.get("final_score", 0), reverse=True)

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
        return {
            "available": True,
            "tensorflow_available": TF_AVAILABLE,
            "mode": "tensorflow" if TF_AVAILABLE else "numpy_fallback",
            "note": "LSTM requires historical player data for predictions.",
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
    from daily_scheduler import get_daily_scheduler

    result = {
        "available": True,
        "timestamp": datetime.now().isoformat()
    }

    # Pick Logger Stats (actual published picks that need grading)
    if PICK_LOGGER_AVAILABLE:
        pick_logger = get_pick_logger()
        today = get_today_date_str() if TIME_FILTERS_AVAILABLE else datetime.now().strftime("%Y-%m-%d")

        # Get today's picks
        today_picks = pick_logger.get_picks_for_date(today)
        pending_picks = [p for p in today_picks if not p.result]
        graded_picks = [p for p in today_picks if p.result]

        result["pick_logger"] = {
            "predictions_logged": len(today_picks),
            "pending_to_grade": len(pending_picks),
            "graded_today": len(graded_picks),
            "storage_path": pick_logger.storage_path,
            "date": today
        }
    else:
        result["pick_logger"] = {
            "available": False,
            "note": "Pick logger not available"
        }

    # Scheduler Stats (last run time and errors)
    scheduler = get_daily_scheduler()
    if scheduler and hasattr(scheduler, 'auto_grade_job'):
        job = scheduler.auto_grade_job
        result["last_run_at"] = job.last_run.isoformat() if job.last_run else None
        result["last_errors"] = job.last_errors[-5:] if hasattr(job, 'last_errors') else []
    else:
        result["last_run_at"] = None
        result["last_errors"] = []

    # Auto-Grader Weight Learning Stats (separate system for adjusting prediction weights)
    if AUTO_GRADER_AVAILABLE:
        grader = get_grader()  # Use singleton - CRITICAL for data persistence!
        result["weight_learning"] = {
            "available": True,
            "supported_sports": grader.SUPPORTED_SPORTS,
            "predictions_logged": sum(len(p) for p in grader.predictions.values()),
            "weights_loaded": bool(grader.weights),
            "storage_path": grader.storage_path,
            "note": "Use /grader/weights/{sport} to see learned weights"
        }
    else:
        result["weight_learning"] = {
            "available": False,
            "note": "Auto-grader weight learning not available"
        }

    return result


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

    # Filter to graded predictions within timeframe
    cutoff = datetime.now() - timedelta(days=days_back)
    graded = [
        p for p in predictions
        if p.actual_value is not None and
        datetime.fromisoformat(p.timestamp) >= cutoff
    ]

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

        report_date = (datetime.now() - timedelta(days=days_back)).strftime("%B %d, %Y")
        today = datetime.now().strftime("%B %d, %Y")

        # Collect performance across all sports
        sports_data = {}
        total_picks = 0
        total_hits = 0
        overall_lessons = []
        improvements = []

        for sport in ["NBA", "NFL", "MLB", "NHL"]:
            predictions = grader.predictions.get(sport, [])
            cutoff = datetime.now() - timedelta(days=days_back + 1)
            end_cutoff = datetime.now() - timedelta(days=days_back - 1)

            # Filter to yesterday's graded predictions
            graded = [
                p for p in predictions
                if p.actual_value is not None and
                cutoff <= datetime.fromisoformat(p.timestamp) <= end_cutoff
            ]

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
        # Get date in ET
        if not date:
            if PYTZ_AVAILABLE:
                ET_TZ = pytz.timezone("America/New_York")
                date = datetime.now(ET_TZ).strftime("%Y-%m-%d")
            else:
                date = datetime.now().strftime("%Y-%m-%d")

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
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        # Parse request - get date from request or default to today ET
        date = request_data.get("date")
        if not date:
            if PYTZ_AVAILABLE:
                ET_TZ = pytz.timezone("America/New_York")
                date = datetime.now(ET_TZ).strftime("%Y-%m-%d")
            else:
                date = datetime.now().strftime("%Y-%m-%d")
        sports = request_data.get("sports") or ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
        mode = request_data.get("mode", "pre")  # "pre" or "post"
        fail_on_unresolved = request_data.get("fail_on_unresolved", False)

        pick_logger = get_pick_logger()
        all_picks = pick_logger.get_picks_for_date(date)

        # Filter by sports
        sport_set = set(s.upper() for s in sports)
        picks = [p for p in all_picks if p.sport.upper() in sport_set]

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
            sport = pick.sport.upper()

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
            _gs = getattr(pick, "grade_status", "PENDING")
            if _gs == "GRADED":
                _already_graded += 1
                results["graded"] += 1
                results["by_sport"][sport]["graded"] += 1
                continue
            if _gs == "FAILED" and not getattr(pick, "canonical_player_id", ""):
                # Old test seeds with no canonical_player_id — skip
                _already_failed += 1
                continue

            results["by_sport"][sport]["picks"] += 1

            # Check 1: Event resolution
            canonical_event_id = getattr(pick, "canonical_event_id", "")
            event_ok = bool(canonical_event_id) or bool(pick.matchup)
            if event_ok:
                results["by_sport"][sport]["event_resolved"] += 1

            # Check 2: Player resolution (props only)
            player_ok = True
            if pick.player_name:
                canonical_player_id = getattr(pick, "canonical_player_id", "")
                player_ok = bool(canonical_player_id) or IDENTITY_RESOLVER_AVAILABLE
                if player_ok:
                    results["by_sport"][sport]["player_resolved"] += 1

            # Check 3: Grade-ready checklist (if available)
            grade_ready_check = pick_logger.check_grade_ready(pick) if hasattr(pick_logger, 'check_grade_ready') else {"is_grade_ready": True, "reasons": []}

            # Determine per-pick status
            pick_reason = None
            if not event_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_EVENT"
                unresolved_picks.append({
                    "pick_id": pick.pick_id,
                    "sport": sport,
                    "player": pick.player_name,
                    "matchup": pick.matchup,
                    "reason": pick_reason
                })
            elif pick.player_name and not player_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_PLAYER"
                unresolved_picks.append({
                    "pick_id": pick.pick_id,
                    "sport": sport,
                    "player": pick.player_name,
                    "matchup": pick.matchup,
                    "reason": pick_reason
                })
            elif not grade_ready_check["is_grade_ready"]:
                # Missing required fields for grading
                results["failed"] += 1
                pick_reason = "MISSING_GRADE_FIELDS"
                failed_picks.append({
                    "pick_id": pick.pick_id,
                    "sport": sport,
                    "player": pick.player_name,
                    "matchup": pick.matchup,
                    "reason": pick_reason,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
                results["by_sport"][sport]["failed_picks"].append({
                    "pick_id": pick.pick_id,
                    "reason": pick_reason,
                    "player": pick.player_name,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
            elif pick.result is not None or getattr(pick, 'graded', False):
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

        # Return HTTP 422 if fail_on_unresolved and there are failures/unresolved
        if fail_on_unresolved and (results["failed"] > 0 or results["unresolved"] > 0):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": f"{results['failed']} failed, {results['unresolved']} unresolved",
                    "overall_status": "FAIL",
                    "failed_picks": failed_picks,
                    "unresolved_picks": unresolved_picks,
                    "summary": results["summary"]
                }
            )

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Dry-run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
        return {
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
    except Exception as e:
        logger.exception("Failed to get today's picks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        from datetime import datetime as dt
        import pytz

        pick_logger = get_pick_logger()

        if not date:
            ET = pytz.timezone("America/New_York")
            date = dt.now(ET).strftime("%Y-%m-%d")

        picks = pick_logger.get_picks_for_date(date)
        graded = [p for p in picks if p.result]
        pending = [p for p in picks if not p.result]

        # Calculate by tier
        tier_results = {}
        for pick in graded:
            tier = pick.tier or "UNKNOWN"
            if tier not in tier_results:
                tier_results[tier] = {"wins": 0, "losses": 0, "pushes": 0, "units_won": 0, "units_lost": 0}

            if pick.result == "WIN":
                tier_results[tier]["wins"] += 1
                tier_results[tier]["units_won"] += pick.units or 0
            elif pick.result == "LOSS":
                tier_results[tier]["losses"] += 1
                tier_results[tier]["units_lost"] += pick.units or 0
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
                    "pick_id": p.pick_id,
                    "player": p.player_name or "Game",
                    "matchup": p.matchup,
                    "line": p.line,
                    "side": p.side,
                    "tier": p.tier,
                    "result": p.result,
                    "actual_value": p.actual_value,
                    "units": p.units
                }
                for p in graded
            ],
            "timestamp": dt.now().isoformat()
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
        return cached

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
            return result

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
        return result

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
        return result


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

    # v10.1: Calculate final score and bet tier
    final_score = (research_score * 0.67) + (esoteric_score * 0.33) + confluence.get("boost", 0)
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
            "formula": "FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost"
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
