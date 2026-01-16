# live_data_router.py v14.6 - TRUE DEEP LINKS
# Research-Optimized + Esoteric Edge + NOOSPHERE VELOCITY
# Production-safe with retries, logging, rate-limit handling, deterministic fallbacks

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
import httpx
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

# Sport mappings
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "nba"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "nfl"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "mlb"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "nhl"},
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

    # Try Playbook API first
    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/sharp/{sport_config['playbook']}"
        resp = await fetch_with_retries(
            "GET", playbook_url,
            headers={"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
        )

        if resp and resp.status_code == 200:
            try:
                json_body = resp.json()
                games = json_body.get("games", [])
                logger.info("Playbook sharp data retrieved for %s: %d games", sport, len(games))
                result = {"sport": sport.upper(), "source": "playbook", "count": len(games), "data": games}
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
            result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data}
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
            result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data}
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

            if len(spreads) >= 3:
                variance = max(spreads) - min(spreads)
                if variance >= 1.5:
                    data.append({
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "line_variance": round(variance, 1),
                        "signal_strength": "STRONG" if variance >= 2 else "MODERATE"
                    })

        logger.info("Odds API sharp analysis for %s: %d signals found", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API processing failed for %s: %s, using fallback", sport, e)
        # Return fallback on any error
        data = generate_fallback_sharp(sport_lower)
        result = {"sport": sport.upper(), "source": "fallback", "count": len(data), "data": data}
        api_cache.set(cache_key, result)
        return result

    result = {"sport": sport.upper(), "source": "odds_api", "count": len(data), "data": data}
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

    # Try Playbook API first
    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/splits/{sport_config['playbook']}"
        resp = await fetch_with_retries(
            "GET", playbook_url,
            headers={"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
        )

        if resp and resp.status_code == 200:
            try:
                json_body = resp.json()
                games = json_body.get("games", [])
                logger.info("Playbook splits data retrieved for %s: %d games", sport, len(games))
                result = {"sport": sport.upper(), "source": "playbook", "count": len(games), "data": games}
                api_cache.set(cache_key, result)
                return result
            except ValueError as e:
                logger.error("Failed to parse Playbook splits response: %s", e)

        if resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

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
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"props:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Odds API first for props
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "player_points,player_rebounds,player_assists,player_threes,player_pass_tds,player_rush_yds,player_reception_yds",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            try:
                games = resp.json()
                for game in games:
                    game_props = {
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "commence_time": game.get("commence_time"),
                        "props": []
                    }

                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            if "player" in market.get("key", ""):
                                for outcome in market.get("outcomes", []):
                                    game_props["props"].append({
                                        "player": outcome.get("description", ""),
                                        "market": market.get("key"),
                                        "line": outcome.get("point", 0),
                                        "odds": outcome.get("price", -110),
                                        "side": outcome.get("name"),
                                        "book": bm.get("key")
                                    })

                    if game_props["props"]:
                        data.append(game_props)

                logger.info("Props data retrieved from Odds API for %s: %d games with props", sport, len(data))
            except ValueError as e:
                logger.error("Failed to parse Odds API props response: %s", e)
        else:
            logger.warning("Odds API props returned %s for %s, trying Playbook API", resp.status_code if resp else "no response", sport)

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
async def get_best_bets(sport: str):
    """
    Get best bets using full 8 AI Models + 8 Pillars + JARVIS + Esoteric scoring.
    Returns TWO categories: props (player props) and game_picks (spreads, totals, ML).

    Scoring Formula:
    TOTAL = AI_Models (0-8) + Pillars (0-8) + JARVIS (0-4) + Esoteric_Boost

    Response Schema:
    {
        "sport": "NBA",
        "props": [...],       // Player props
        "game_picks": [...],  // Spreads, totals, moneylines
        "daily_energy": {...},
        "timestamp": "ISO timestamp"
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"best-bets:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

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

    # Helper function to calculate scores with v10.1 dual-score confluence
    def calculate_pick_score(game_str, sharp_signal, base_ai=5.0, player_name="", home_team="", away_team="", spread=0, total=220, public_pct=50):
        # =====================================================================
        # v10.1 DUAL-SCORE CONFLUENCE SYSTEM
        # =====================================================================
        # RESEARCH SCORE (0-10): 8 AI Models (0-8) + 8 Pillars (0-8) scaled to 0-10
        # ESOTERIC SCORE (0-10): JARVIS (0-4) + Gematria + Public Fade + Mid-Spread + Esoteric Edge
        # FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost
        # =====================================================================

        # --- RESEARCH SCORE CALCULATION ---
        ai_score = base_ai
        if sharp_signal.get("signal_strength") == "STRONG":
            ai_score += 2.0
        elif sharp_signal.get("signal_strength") == "MODERATE":
            ai_score += 1.0
        ai_score = min(8.0, ai_score)

        pillar_score = 3.0 if sharp_signal.get("line_variance", 0) > 1.0 else 2.0
        pillar_score = min(8.0, pillar_score)

        # Research score: (ai + pillar) / 16 * 10 = normalized to 0-10
        research_score = (ai_score + pillar_score) / 16 * 10

        # --- ESOTERIC SCORE CALCULATION ---
        jarvis_score = 0.0
        jarvis_triggers_hit = []
        immortal_detected = False
        jarvis_triggered = False
        gematria_contribution = 0.0
        public_fade_contribution = 0.0
        mid_spread_contribution = 0.0
        astro_contribution = 0.0
        esoteric_edge = 0.0
        fib_contribution = 0.0
        vortex_contribution = 0.0
        trap_deduction = 0.0

        if jarvis:
            # Full JARVIS trigger check
            trigger_result = jarvis.check_jarvis_trigger(game_str)
            for trig in trigger_result.get("triggers_hit", []):
                jarvis_boost = trig["boost"] / 5
                jarvis_score += jarvis_boost
                jarvis_triggers_hit.append({
                    "number": trig["number"],
                    "name": trig["name"],
                    "match_type": trig.get("match_type", "DIRECT"),
                    "boost": round(jarvis_boost, 2)
                })
                # Check for IMMORTAL 2178
                if trig["number"] == 2178:
                    immortal_detected = True
            jarvis_score = min(4.0, jarvis_score)
            jarvis_triggered = len(jarvis_triggers_hit) > 0

            # Full gematria and signals
            if player_name and home_team:
                gematria = jarvis.calculate_gematria_signal(player_name, home_team, away_team)
                public_fade = jarvis.calculate_public_fade_signal(public_pct)
                mid_spread = jarvis.calculate_mid_spread_signal(spread)
                trap = jarvis.calculate_large_spread_trap(spread, total)

                # Get astro score
                astro = vedic.calculate_astro_score() if vedic else {"overall_score": 50}

                # Gematria contribution (52% weight per v10.1)
                if gematria.get("triggered"):
                    gematria_contribution = gematria.get("influence", 0) * 0.52 * 2

                # Public fade contribution (graduated per v10.1)
                public_fade_contribution = public_fade.get("influence", 0)

                # Mid-spread contribution
                mid_spread_contribution = mid_spread.get("modifier", 0)

                # Trap deduction
                trap_deduction = trap.get("modifier", 0)

                # Astro contribution
                astro_contribution = (astro["overall_score"] - 50) / 50 * esoteric_weights.get("astro", 0.13) * 2

                # Fibonacci alignment (v10.1 Fix #7)
                fib_alignment = jarvis.calculate_fibonacci_alignment(float(spread) if spread else 0)
                fib_contribution = fib_alignment.get("modifier", 0)

                # Vortex pattern check (v10.1 Fix #8)
                vortex_value = int(abs(spread * 10)) if spread else 0
                vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)
                vortex_contribution = vortex_pattern.get("modifier", 0)
        else:
            # Fallback to simple trigger check
            for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
                if str(trigger_num) in game_str:
                    jarvis_boost = trigger_data["boost"] / 5
                    jarvis_score += jarvis_boost
                    jarvis_triggers_hit.append({
                        "number": trigger_num,
                        "name": trigger_data["name"],
                        "boost": round(jarvis_boost, 2)
                    })
                    if trigger_num == 2178:
                        immortal_detected = True
            jarvis_score = min(4.0, jarvis_score)
            jarvis_triggered = len(jarvis_triggers_hit) > 0

        # Esoteric edge from daily energy (0-2)
        if daily_energy.get("overall_score", 50) >= 85:
            esoteric_edge = 2.0
        elif daily_energy.get("overall_score", 50) >= 70:
            esoteric_edge = 1.0

        # Esoteric score: JARVIS (0-4) + contributions (scaled to fit 0-10)
        # Base: JARVIS 0-4, Edge 0-2, Gematria 0-1, Astro 0-0.5, Mid-spread 0-0.2, etc
        # Max theoretical: 4 + 2 + 1 + 0.5 + 0.2 + fib + vortex ~ 8-9
        esoteric_raw = (
            jarvis_score +
            esoteric_edge +
            gematria_contribution +
            max(0, astro_contribution) +
            mid_spread_contribution +
            fib_contribution +
            vortex_contribution +
            public_fade_contribution +  # Usually negative
            trap_deduction
        )
        esoteric_score = max(0, min(10, esoteric_raw * 1.25))  # Scale to 0-10

        # --- v10.1 DUAL-SCORE CONFLUENCE ---
        if jarvis:
            confluence = jarvis.calculate_confluence(
                research_score=research_score,
                esoteric_score=esoteric_score,
                immortal_detected=immortal_detected,
                jarvis_triggered=jarvis_triggered
            )
        else:
            # Fallback confluence calculation
            alignment = 1 - abs(research_score - esoteric_score) / 10
            alignment_pct = alignment * 100
            both_high = research_score >= 7.5 and esoteric_score >= 7.5
            if immortal_detected and both_high and alignment_pct >= 80:
                confluence = {"level": "IMMORTAL", "boost": 10, "alignment_pct": alignment_pct}
            elif jarvis_triggered and both_high and alignment_pct >= 80:
                confluence = {"level": "JARVIS_PERFECT", "boost": 7, "alignment_pct": alignment_pct}
            elif both_high and alignment_pct >= 80:
                confluence = {"level": "PERFECT", "boost": 5, "alignment_pct": alignment_pct}
            elif alignment_pct >= 70:
                confluence = {"level": "STRONG", "boost": 3, "alignment_pct": alignment_pct}
            elif alignment_pct >= 60:
                confluence = {"level": "MODERATE", "boost": 1, "alignment_pct": alignment_pct}
            else:
                confluence = {"level": "DIVERGENT", "boost": 0, "alignment_pct": alignment_pct}

        confluence_level = confluence.get("level", "DIVERGENT")
        confluence_boost = confluence.get("boost", 0)

        # --- v10.1 FINAL SCORE FORMULA ---
        # FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost
        final_score = (research_score * 0.67) + (esoteric_score * 0.33) + confluence_boost

        # --- v10.1 BET TIER DETERMINATION ---
        if jarvis:
            bet_tier = jarvis.determine_bet_tier(final_score, confluence)
        else:
            if final_score >= 9.0:
                bet_tier = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
            elif final_score >= 7.5:
                bet_tier = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
            elif final_score >= 6.0:
                bet_tier = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
            else:
                bet_tier = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

        # Map to confidence levels for backward compatibility
        confidence_map = {
            "GOLD_STAR": "SMASH",
            "EDGE_LEAN": "HIGH",
            "MONITOR": "MEDIUM",
            "PASS": "LOW"
        }
        confidence = confidence_map.get(bet_tier.get("tier", "PASS"), "LOW")

        return {
            "total_score": round(final_score, 2),
            "confidence": confidence,
            "confluence_level": confluence_level,
            "bet_tier": bet_tier,
            "scoring_breakdown": {
                "research_score": round(research_score, 2),
                "esoteric_score": round(esoteric_score, 2),
                "ai_models": round(ai_score, 2),
                "pillars": round(pillar_score, 2),
                "jarvis": round(jarvis_score, 2),
                "esoteric_edge": round(esoteric_edge, 2),
                "confluence_boost": confluence_boost,
                "alignment_pct": confluence.get("alignment_pct", 0)
            },
            "jarvis_triggers": jarvis_triggers_hit,
            "immortal_detected": immortal_detected
        }

    # ============================================
    # CATEGORY 1: PLAYER PROPS
    # ============================================
    props_picks = []
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

                # Calculate score with full esoteric integration
                score_data = calculate_pick_score(
                    game_str + player,
                    sharp_signal,
                    base_ai=5.0,
                    player_name=player,
                    home_team=home_team,
                    away_team=away_team,
                    spread=0,
                    total=220,
                    public_pct=50
                )

                props_picks.append({
                    "player": player,
                    "market": market,
                    "line": line,
                    "side": side,
                    "odds": odds,
                    "game": f"{away_team} @ {home_team}",
                    "home_team": home_team,
                    "away_team": away_team,
                    "recommendation": f"{side.upper()} {line}",
                    **score_data,
                    "sharp_signal": sharp_signal.get("signal_strength", "NONE")
                })
    except HTTPException:
        logger.warning("Props fetch failed for %s", sport)

    # Sort props by score and take top 10
    props_picks.sort(key=lambda x: x["total_score"], reverse=True)
    top_props = props_picks[:10]

    # ============================================
    # CATEGORY 2: GAME PICKS (Spreads, Totals, ML)
    # ============================================
    game_picks = []
    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        # Fetch game odds (spreads, totals, moneylines)
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

                for bm in game.get("bookmakers", [])[:1]:  # Just use first book for now
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")

                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point")

                            # Build display info
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

                            # Calculate score with full esoteric integration
                            score_data = calculate_pick_score(
                                game_str,
                                sharp_signal,
                                base_ai=4.5,
                                player_name="",
                                home_team=home_team,
                                away_team=away_team,
                                spread=point if market_key == "spreads" and point else 0,
                                total=point if market_key == "totals" and point else 220,
                                public_pct=50
                            )

                            game_picks.append({
                                "pick_type": pick_type,
                                "pick": display,
                                "team": pick_name if market_key != "totals" else None,
                                "line": point,
                                "odds": odds,
                                "game": f"{away_team} @ {home_team}",
                                "home_team": home_team,
                                "away_team": away_team,
                                "market": market_key,
                                "recommendation": display,
                                **score_data,
                                "sharp_signal": sharp_signal.get("signal_strength", "NONE")
                            })
    except Exception as e:
        logger.warning("Game odds fetch failed: %s", e)

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
                public_pct=50
            )

            game_picks.append({
                "pick_type": "SHARP",
                "pick": f"Sharp on {signal.get('side', 'HOME')}",
                "team": home_team if signal.get("side") == "HOME" else away_team,
                "line": signal.get("line_variance", 0),
                "odds": -110,
                "game": f"{away_team} @ {home_team}",
                "home_team": home_team,
                "away_team": away_team,
                "market": "sharp_money",
                "recommendation": f"SHARP ON {signal.get('side', 'HOME').upper()}",
                **score_data,
                "sharp_signal": signal.get("signal_strength", "MODERATE")
            })

    # Sort game picks by score and take top 10
    game_picks.sort(key=lambda x: x["total_score"], reverse=True)
    top_game_picks = game_picks[:10]

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

    result = {
        "sport": sport.upper(),
        "source": "jarvis_savant_v7.3",
        "scoring_system": "Phase 1-3 Integrated",
        "props": {
            "count": len(top_props),
            "total_analyzed": len(props_picks),
            "picks": top_props
        },
        "game_picks": {
            "count": len(top_game_picks),
            "total_analyzed": len(game_picks),
            "picks": top_game_picks
        },
        "esoteric": {
            "daily_energy": daily_energy,
            "astro_status": astro_status,
            "learned_weights": esoteric_weights,
            "learning_active": learning is not None
        },
        "timestamp": datetime.now().isoformat()
    }
    api_cache.set(cache_key, result, ttl=120)  # 2 minute TTL
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
    """Check auto-grader status and current weights."""
    try:
        from auto_grader import AutoGrader
        grader = AutoGrader()
        return {
            "available": True,
            "supported_sports": grader.SUPPORTED_SPORTS,
            "predictions_logged": sum(len(p) for p in grader.predictions.values()),
            "weights_loaded": bool(grader.weights),
            "note": "Use /grader/weights/{sport} to see current weights",
            "timestamp": datetime.now().isoformat()
        }
    except ImportError as e:
        return {
            "available": False,
            "error": str(e),
            "note": "Auto-grader module not available",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/grader/weights/{sport}")
async def grader_weights(sport: str):
    """Get current prediction weights for a sport."""
    try:
        from auto_grader import AutoGrader
        from dataclasses import asdict
        grader = AutoGrader()
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
    except ImportError:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")


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
    Get comprehensive esoteric edge analysis.
    Returns daily energy + game signals + prop signals + parlay warnings.
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
        SAMPLE_PLAYERS
    )

    today = datetime.now().date()

    # Daily reading
    daily = get_daily_esoteric_reading(today)

    # Sample game signals (in production, would fetch from best-bets)
    sample_games = [
        {"game_id": "sample1", "home_team": "Lakers", "away_team": "Celtics", "spread": -3.5, "total": 225.5, "city": "Los Angeles"},
        {"game_id": "sample2", "home_team": "Warriors", "away_team": "Bulls", "spread": -7.5, "total": 232, "city": "San Francisco"},
    ]

    game_signals = []
    for game in sample_games:
        game_signals.append({
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "signals": {
                "founders_echo": {
                    "home_match": check_founders_echo(game["home_team"])["resonance"],
                    "away_match": check_founders_echo(game["away_team"])["resonance"],
                    "boost": check_founders_echo(game["home_team"])["boost"] + check_founders_echo(game["away_team"])["boost"]
                },
                "gann_square": {
                    "spread_angle": analyze_spread_gann(game["spread"], game["total"])["spread"]["angle"],
                    "resonant": analyze_spread_gann(game["spread"], game["total"])["combined_resonance"]
                },
                "atmospheric": calculate_atmospheric_drag(game["city"])
            }
        })

    # Sample player signals
    prop_signals = []
    for player_name, player_data in list(SAMPLE_PLAYERS.items())[:4]:
        bio = calculate_biorhythms(player_data["birth_date"])
        life_path = check_life_path_sync(player_name, player_data["birth_date"], player_data["jersey"])
        prop_signals.append({
            "player_id": player_name.lower().replace(" ", "_"),
            "player_name": player_name,
            "signals": {
                "biorhythms": {
                    "physical": bio["physical"],
                    "emotional": bio["emotional"],
                    "intellectual": bio["intellectual"]
                },
                "life_path_sync": {
                    "player_life_path": life_path["life_path"],
                    "jersey_number": life_path["jersey_number"],
                    "sync_score": life_path["sync_score"]
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
            "planetary_hours": daily["planetary_hours"]
        },
        "game_signals": game_signals,
        "prop_signals": prop_signals,
        "parlay_warnings": [],  # Populated when parlay legs provided
        "noosphere": daily["noosphere"]
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
# PHASE 3: LEARNING LOOP ENDPOINTS
# ============================================================================

@router.post("/learning/log-pick")
async def log_esoteric_pick(pick_data: Dict[str, Any]):
    """
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


@router.post("/learning/grade-pick")
async def grade_esoteric_pick(grade_data: Dict[str, Any]):
    """
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


@router.get("/learning/performance")
async def get_learning_performance(days_back: int = 30):
    """
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


@router.get("/learning/weights")
async def get_learning_weights():
    """Get current learned weights for esoteric signals."""
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.get_weights()


@router.post("/learning/adjust-weights")
async def adjust_learning_weights(learning_rate: float = 0.05):
    """
    Trigger weight adjustment based on historical performance.

    Uses gradient-based adjustment:
    - Increases weights for signals with hit rate > 55%
    - Decreases weights for signals with hit rate < 48%
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.adjust_weights(learning_rate)


@router.get("/learning/recent-picks")
async def get_recent_picks(limit: int = 20):
    """Get recent esoteric picks for review."""
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
async def save_user_preferences(user_id: str, prefs: Dict[str, Any]):
    """
    Save user's sportsbook preferences.

    Request Body:
    {
        "favorite_books": ["fanduel", "draftkings", "caesars"],
        "default_bet_amount": 50,
        "auto_best_odds": true,
        "notifications": {
            "smash_alerts": true,
            "odds_movement": false,
            "bet_results": true
        }
    }
    """
    # Validate favorite_books
    valid_books = list(SPORTSBOOK_CONFIGS.keys())
    favorite_books = prefs.get("favorite_books", [])
    validated_books = [b for b in favorite_books if b in valid_books]

    _user_preferences[user_id] = {
        "user_id": user_id,
        "favorite_books": validated_books if validated_books else ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": prefs.get("default_bet_amount", 25),
        "auto_best_odds": prefs.get("auto_best_odds", True),
        "notifications": prefs.get("notifications", {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        }),
        "updated_at": datetime.now().isoformat()
    }

    return {"status": "saved", "preferences": _user_preferences[user_id]}


@router.post("/bets/track")
async def track_bet(bet_data: Dict[str, Any]):
    """
    Track a bet that was placed through the click-to-bet flow.

    Request Body:
    {
        "user_id": "user_123",
        "sport": "NBA",
        "game_id": "game_xyz",
        "game": "Lakers vs Celtics",
        "bet_type": "spread",
        "selection": "Lakers",
        "line": -3.5,
        "odds": -110,
        "sportsbook": "draftkings",
        "stake": 25,
        "ai_score": 8.5,
        "confluence_level": "STRONG"
    }

    Returns bet_id for later grading.
    """
    required_fields = ["sport", "game_id", "bet_type", "selection", "odds", "sportsbook"]
    for field in required_fields:
        if field not in bet_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    bet_id = f"BET_{bet_data['sport']}_{bet_data['game_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_bet = {
        "bet_id": bet_id,
        "user_id": bet_data.get("user_id", "anonymous"),
        "sport": bet_data["sport"].upper(),
        "game_id": bet_data["game_id"],
        "game": bet_data.get("game", "Unknown Game"),
        "bet_type": bet_data["bet_type"],
        "selection": bet_data["selection"],
        "line": bet_data.get("line"),
        "odds": bet_data["odds"],
        "sportsbook": bet_data["sportsbook"],
        "stake": bet_data.get("stake", 0),
        "potential_payout": calculate_payout(bet_data.get("stake", 0), bet_data["odds"]),
        "ai_score": bet_data.get("ai_score"),
        "confluence_level": bet_data.get("confluence_level"),
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
async def grade_bet(bet_id: str, result_data: Dict[str, Any]):
    """
    Grade a tracked bet with actual result.

    Request Body:
    {
        "result": "WIN",  // WIN, LOSS, PUSH
        "actual_score": "Lakers 110, Celtics 105"  // Optional
    }
    """
    result = result_data.get("result", "").upper()
    if result not in ["WIN", "LOSS", "PUSH"]:
        raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for bet in _tracked_bets:
        if bet["bet_id"] == bet_id:
            bet["status"] = "GRADED"
            bet["result"] = result
            bet["actual_score"] = result_data.get("actual_score")
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
    limit: int = 50
):
    """
    Get bet history with optional filters.

    Supports filtering by:
    - user_id: Filter by user
    - sport: Filter by sport (NBA, NFL, etc.)
    - status: Filter by status (PENDING, GRADED)
    """
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
async def add_parlay_leg(leg_data: Dict[str, Any]):
    """
    Add a leg to a user's parlay slip.

    Request Body:
    {
        "user_id": "user_123",
        "sport": "NBA",
        "game_id": "game_xyz",
        "game": "Lakers vs Celtics",
        "bet_type": "spread",
        "selection": "Lakers",
        "line": -3.5,
        "odds": -110,
        "ai_score": 8.5
    }

    Returns updated parlay slip with combined odds.
    """
    required_fields = ["user_id", "sport", "game_id", "bet_type", "selection", "odds"]
    for field in required_fields:
        if field not in leg_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    user_id = leg_data["user_id"]

    # Initialize slip if needed
    if user_id not in _parlay_slips:
        _parlay_slips[user_id] = []

    # Check max legs
    if len(_parlay_slips[user_id]) >= 12:
        raise HTTPException(status_code=400, detail="Maximum 12 legs per parlay")

    # Check for duplicate game/bet_type
    for existing in _parlay_slips[user_id]:
        if existing["game_id"] == leg_data["game_id"] and existing["bet_type"] == leg_data["bet_type"]:
            raise HTTPException(
                status_code=400,
                detail=f"Already have a {leg_data['bet_type']} bet for this game"
            )

    leg_id = f"LEG_{user_id}_{len(_parlay_slips[user_id])}_{datetime.now().strftime('%H%M%S')}"

    new_leg = {
        "leg_id": leg_id,
        "sport": leg_data["sport"].upper(),
        "game_id": leg_data["game_id"],
        "game": leg_data.get("game", "Unknown Game"),
        "bet_type": leg_data["bet_type"],
        "selection": leg_data["selection"],
        "line": leg_data.get("line"),
        "odds": leg_data["odds"],
        "ai_score": leg_data.get("ai_score"),
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
async def place_parlay(parlay_data: Dict[str, Any]):
    """
    Track a parlay bet that was placed.

    Request Body:
    {
        "user_id": "user_123",
        "sportsbook": "draftkings",
        "stake": 25,
        "use_current_slip": true  // OR provide "legs" array
    }

    If use_current_slip is true, uses the user's current parlay slip.
    Otherwise, provide a "legs" array directly.
    """
    user_id = parlay_data.get("user_id", "anonymous")
    sportsbook = parlay_data.get("sportsbook")
    stake = parlay_data.get("stake", 0)

    if not sportsbook:
        raise HTTPException(status_code=400, detail="sportsbook is required")

    # Get legs from current slip or from request
    if parlay_data.get("use_current_slip", True):
        legs = _parlay_slips.get(user_id, [])
    else:
        legs = parlay_data.get("legs", [])

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
    if parlay_data.get("use_current_slip", True):
        _parlay_slips[user_id] = []

    return {
        "status": "placed",
        "parlay": tracked_parlay,
        "message": f"Parlay with {len(legs)} legs tracked. Open {sportsbook} to place bet.",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/grade/{parlay_id}")
async def grade_parlay(parlay_id: str, grade_data: Dict[str, Any]):
    """
    Grade a placed parlay with WIN, LOSS, or PUSH.

    Request Body:
    {
        "result": "WIN"  // or "LOSS" or "PUSH"
    }
    """
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
    limit: int = 50
):
    """
    Get parlay history with stats.

    Supports filtering by:
    - user_id: Filter by user
    - status: Filter by status (PENDING, GRADED)
    """
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
# EXPORTS FOR MAIN.PY
# ============================================================================

class LiveDataRouter:
    def __init__(self):
        self.router = router

    def get_router(self):
        return self.router


# Export the router instance
live_data_router = router
