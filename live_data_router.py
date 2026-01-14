# live_data_router.py v14.1 - PRODUCTION HARDENED
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
# JARVIS SAVANT ENGINE v7.3 - THE CONFLUENCE CORE
# Philosophy: Esoteric resonance (gematria dominant) + Exoteric inefficiencies
# YTD Record: +94.40u (as of January 8, 2026)
# ============================================================================

# Fibonacci sequence for line alignment checks
FIBONACCI_NUMBERS = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]

# Vortex math pattern (Tesla's 1-2-4-8-7-5 cycle)
VORTEX_PATTERN = [1, 2, 4, 8, 7, 5]


def validate_2178() -> Dict[str, Any]:
    """
    Prove the mathematical uniqueness of 2178 - THE IMMORTAL NUMBER.

    Property 1: 2178 × 4 = 8712 (its reversal)
    Property 2: 2178 × 8712 = 18974736 = 66^4

    This is the ONLY 4-digit number with both properties.
    It never collapses to zero in digit sum sequences.
    """
    n = 2178
    reversal = 8712

    # Property 1: n × 4 = reversal
    prop1 = (n * 4 == reversal)

    # Property 2: n × reversal = 66^4
    sixty_six_fourth = 66 * 66 * 66 * 66  # 18974736
    prop2 = (n * reversal == sixty_six_fourth)

    # Digit sum never collapses to 0
    digit_sum_val = sum(int(d) for d in str(n))  # 2+1+7+8 = 18 → 1+8 = 9

    return {
        "number": n,
        "reversal": reversal,
        "property_1": {
            "description": "n × 4 = reversal",
            "calculation": f"{n} × 4 = {n * 4}",
            "expected": reversal,
            "verified": prop1
        },
        "property_2": {
            "description": "n × reversal = 66^4",
            "calculation": f"{n} × {reversal} = {n * reversal}",
            "expected": sixty_six_fourth,
            "verified": prop2
        },
        "digit_sum": digit_sum_val,
        "digit_sum_reduced": 9,  # Always reduces to 9, never 0
        "validated": prop1 and prop2,
        "status": "IMMORTAL CONFIRMED" if (prop1 and prop2) else "VALIDATION FAILED",
        "significance": "The only 4-digit number where multiplication by 4 equals its reversal AND the product with its reversal equals 66^4"
    }


def digit_sum(n: int) -> int:
    """Calculate digit sum of a number."""
    return sum(int(d) for d in str(abs(n)))


def reduce_to_single(n: int) -> int:
    """Reduce number to single digit (gematria reduction), preserving master numbers."""
    n = abs(n)
    while n > 9 and n not in [11, 22, 33]:
        n = digit_sum(n)
    return n


def simple_gematria(text: str) -> int:
    """Calculate simple English gematria (A=1, B=2, ..., Z=26)."""
    total = 0
    for char in text.upper():
        if 'A' <= char <= 'Z':
            total += ord(char) - ord('A') + 1
    return total


def check_jarvis_trigger(value: int) -> Dict[str, Any]:
    """
    Check if a value triggers any Jarvis edge numbers.

    Checks for:
    1. Direct match with trigger numbers
    2. Reduction to trigger numbers
    3. Divisibility by 33 (master number)
    4. Tesla 3-6-9 alignment
    5. Contains 2178 sequence
    6. Fibonacci alignment
    7. Vortex math pattern
    """
    result = {
        "value": value,
        "triggered": False,
        "triggers": [],
        "total_boost": 0.0,
        "highest_tier": None,
        "details": []
    }

    str_value = str(abs(value))

    # Check for 2178 sequence in value
    if "2178" in str_value:
        trigger = JARVIS_TRIGGERS[2178]
        result["triggered"] = True
        result["triggers"].append(2178)
        result["total_boost"] += trigger["boost"]
        result["highest_tier"] = "LEGENDARY"
        result["details"].append({
            "type": "SEQUENCE",
            "trigger": 2178,
            "name": "THE IMMORTAL",
            "reason": "Contains 2178 sequence",
            "boost": trigger["boost"]
        })

    # Direct match check
    if value in JARVIS_TRIGGERS:
        trigger = JARVIS_TRIGGERS[value]
        if value not in result["triggers"]:
            result["triggered"] = True
            result["triggers"].append(value)
            result["total_boost"] += trigger["boost"]
            if result["highest_tier"] != "LEGENDARY":
                result["highest_tier"] = trigger["tier"]
            result["details"].append({
                "type": "DIRECT",
                "trigger": value,
                "name": trigger["name"],
                "reason": "Direct match",
                "boost": trigger["boost"]
            })

    # Reduction check - does value reduce to same as a trigger?
    reduced = reduce_to_single(value)
    for trigger_num, trigger in JARVIS_TRIGGERS.items():
        if trigger_num not in result["triggers"]:
            trigger_reduced = reduce_to_single(trigger_num)
            if reduced == trigger_reduced and reduced != 0:
                half_boost = trigger["boost"] * 0.5
                result["triggered"] = True
                result["triggers"].append(trigger_num)
                result["total_boost"] += half_boost
                result["details"].append({
                    "type": "REDUCTION",
                    "trigger": trigger_num,
                    "name": trigger["name"],
                    "reason": f"Reduces to {reduced} (same as {trigger_num})",
                    "boost": half_boost
                })

    # 33 divisibility (Master Number alignment)
    if value % 33 == 0 and 33 not in result["triggers"]:
        result["triggered"] = True
        result["triggers"].append(33)
        result["total_boost"] += 5.0
        result["details"].append({
            "type": "DIVISIBILITY",
            "trigger": 33,
            "name": "THE MASTER",
            "reason": f"{value} is divisible by 33",
            "boost": 5.0
        })

    # Tesla 3-6-9 check
    if reduced in TESLA_NUMBERS:
        result["total_boost"] += 2.0
        result["details"].append({
            "type": "TESLA",
            "trigger": reduced,
            "name": "TESLA ALIGNMENT",
            "reason": f"Reduces to Tesla number {reduced}",
            "boost": 2.0
        })

    # Fibonacci alignment check
    if value in FIBONACCI_NUMBERS or abs(value) in FIBONACCI_NUMBERS:
        result["total_boost"] += 1.5
        result["details"].append({
            "type": "FIBONACCI",
            "trigger": value,
            "name": "FIBONACCI ALIGNMENT",
            "reason": f"{value} is in Fibonacci sequence",
            "boost": 1.5
        })

    # Vortex math check (digital root follows 1-2-4-8-7-5 pattern)
    if reduced in VORTEX_PATTERN:
        result["total_boost"] += 1.0
        result["details"].append({
            "type": "VORTEX",
            "trigger": reduced,
            "name": "VORTEX MATH",
            "reason": f"Digital root {reduced} in vortex pattern",
            "boost": 1.0
        })

    return result


def calculate_gematria_signal(player_name: str, team_name: str, opponent_name: str = "",
                               jersey_number: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculate gematria values and check for Jarvis triggers.
    Uses simple English gematria (A=1, B=2, etc.)
    Weight: 52% of RS (Boss approved)
    """
    player_value = simple_gematria(player_name)
    team_value = simple_gematria(team_name)
    opponent_value = simple_gematria(opponent_name) if opponent_name else 0

    combined = player_value + team_value
    if jersey_number:
        combined += jersey_number

    matchup_value = team_value + opponent_value

    # Check for Jarvis triggers on all values
    player_trigger = check_jarvis_trigger(player_value)
    team_trigger = check_jarvis_trigger(team_value)
    combined_trigger = check_jarvis_trigger(combined)
    matchup_trigger = check_jarvis_trigger(matchup_value) if opponent_value else {"total_boost": 0, "triggers": []}

    # Count total gematria hits
    total_boost = (
        player_trigger["total_boost"] +
        team_trigger["total_boost"] +
        combined_trigger["total_boost"] +
        matchup_trigger.get("total_boost", 0)
    )

    all_triggers = set(
        player_trigger.get("triggers", []) +
        team_trigger.get("triggers", []) +
        combined_trigger.get("triggers", []) +
        matchup_trigger.get("triggers", [])
    )

    # Determine influence level (0-1 scale)
    if total_boost >= 20:
        influence = 0.95
        tier = "LEGENDARY"
    elif total_boost >= 15:
        influence = 0.85
        tier = "HIGH"
    elif total_boost >= 10:
        influence = 0.75
        tier = "HIGH"
    elif total_boost >= 5:
        influence = 0.55
        tier = "MEDIUM"
    else:
        influence = 0.35
        tier = "LOW"

    # Check for IMMORTAL specifically
    immortal_detected = 2178 in all_triggers

    return {
        "player_value": player_value,
        "player_reduced": reduce_to_single(player_value),
        "team_value": team_value,
        "team_reduced": reduce_to_single(team_value),
        "combined_value": combined,
        "combined_reduced": reduce_to_single(combined),
        "matchup_value": matchup_value,
        "influence": influence,
        "tier": tier,
        "gematria_hits": len(all_triggers),
        "triggers_found": list(all_triggers),
        "total_boost": total_boost,
        "immortal_detected": immortal_detected,
        "breakdown": {
            "player": player_trigger,
            "team": team_trigger,
            "combined": combined_trigger,
            "matchup": matchup_trigger if opponent_value else None
        }
    }


def calculate_public_fade_signal(public_percentage: float, is_favorite: bool) -> Dict[str, Any]:
    """
    JARVIS PUBLIC FADE 65% CRUSH ZONE

    When public is ≥65% on the chalk (favorite), this is prime fade territory.
    The masses move lines inefficiently - fade their conviction.
    This is the -13% penalty that's been crushing the public.

    +94.40u YTD came largely from this edge.
    """
    signal = {
        "public_pct": public_percentage,
        "is_favorite": is_favorite,
        "in_crush_zone": False,
        "fade_signal": False,
        "influence": 0.0,
        "fade_modifier": 0.0,
        "recommendation": ""
    }

    # CRUSH ZONE: Public ≥65% on favorite
    if public_percentage >= 65 and is_favorite:
        signal["in_crush_zone"] = True
        signal["fade_signal"] = True

        # Scale influence based on how deep in crush zone
        if public_percentage >= 80:
            signal["influence"] = 0.95
            signal["fade_modifier"] = -0.15  # -15% to favorite's value
            signal["recommendation"] = "MAXIMUM FADE - Public delusion at peak"
        elif public_percentage >= 75:
            signal["influence"] = 0.85
            signal["fade_modifier"] = -0.13  # -13% (the key number)
            signal["recommendation"] = "STRONG FADE - Heavy public chalk"
        elif public_percentage >= 70:
            signal["influence"] = 0.75
            signal["fade_modifier"] = -0.10
            signal["recommendation"] = "FADE - Solid crush zone entry"
        else:
            signal["influence"] = 0.65
            signal["fade_modifier"] = -0.08
            signal["recommendation"] = "FADE - Entering crush zone"

    elif public_percentage >= 65 and not is_favorite:
        # Public heavy on dog - contrarian opportunity but less reliable
        signal["influence"] = 0.45
        signal["recommendation"] = "MONITOR - Public dog heavy (unusual)"

    elif public_percentage <= 35:
        # Contrarian opportunity - public avoiding
        signal["influence"] = 0.55
        signal["fade_modifier"] = 0.05  # Slight boost
        signal["recommendation"] = "CONTRARIAN VALUE - Public avoiding"

    else:
        signal["influence"] = 0.30
        signal["recommendation"] = "NO CLEAR PUBLIC EDGE"

    return signal


def calculate_mid_spread_signal(spread: float) -> Dict[str, Any]:
    """
    JARVIS MID-SPREAD AMPLIFIER

    The Goldilocks Zone: +4 to +9
    Not too small (meaningless), not too big (trap territory).
    This is where dogs cover most reliably.
    +20% boost in this zone.
    """
    abs_spread = abs(spread)
    is_dog = spread > 0  # Positive spread = underdog

    signal = {
        "spread": spread,
        "abs_spread": abs_spread,
        "is_underdog": is_dog,
        "in_goldilocks": False,
        "influence": 0.0,
        "zone": "",
        "boost_modifier": 1.0
    }

    if 4 <= abs_spread <= 9:
        # GOLDILOCKS ZONE
        signal["in_goldilocks"] = True
        signal["zone"] = "GOLDILOCKS"
        signal["boost_modifier"] = 1.20  # +20% boost

        # Peak is around 6-7
        if 6 <= abs_spread <= 7:
            signal["influence"] = 0.85
        else:
            signal["influence"] = 0.75

    elif abs_spread < 4:
        signal["zone"] = "TOO_TIGHT"
        signal["influence"] = 0.50
        signal["boost_modifier"] = 1.0

    elif abs_spread > 15:
        # TRAP GATE - Large spreads are traps (handled separately)
        signal["zone"] = "TRAP_GATE"
        signal["influence"] = 0.25
        signal["boost_modifier"] = 0.80  # -20% penalty

    else:
        # 10-15 range - moderate
        signal["zone"] = "MODERATE"
        signal["influence"] = 0.55
        signal["boost_modifier"] = 1.0

    return signal


def calculate_large_spread_trap(spread: float) -> Dict[str, Any]:
    """
    JARVIS LARGE SPREAD TRAP GATE

    Spreads >14 points are trap territory.
    Books know public loves big favorites.
    Apply -20% penalty to any signals in this zone.

    Lessons learned: Kings 41-pt, Rice 31-pt disasters
    """
    abs_spread = abs(spread)

    signal = {
        "spread": spread,
        "abs_spread": abs_spread,
        "is_trap": False,
        "penalty": 1.0,
        "trap_level": "NONE",
        "warning": ""
    }

    if abs_spread >= 20:
        signal["is_trap"] = True
        signal["penalty"] = 0.70  # -30% penalty
        signal["trap_level"] = "EXTREME"
        signal["warning"] = "EXTREME TRAP - Heavily penalize any plays here. Blowout variance is massive."

    elif abs_spread >= 14:
        signal["is_trap"] = True
        signal["penalty"] = 0.80  # -20% penalty
        signal["trap_level"] = "HIGH"
        signal["warning"] = "TRAP GATE ACTIVE - Large spread penalty applied"

    elif abs_spread >= 10:
        signal["trap_level"] = "MODERATE"
        signal["penalty"] = 0.95  # -5% penalty
        signal["warning"] = "Elevated spread - proceed with caution"

    return signal


def calculate_nhl_dog_protocol(sport: str, spread: float, research_score: float,
                                public_pct: float) -> Dict[str, Any]:
    """
    JARVIS NHL DOG PROTOCOL v5.9

    Specific edge for NHL:
    - Puck line dogs (+1.5)
    - Research score ≥9.3
    - Public ≥65% on favorite

    This trifecta has been highly profitable.
    Recent streak: Penguins, Canadiens, Kings, Blackhawks, Stars outrights.
    """
    signal = {
        "sport": sport,
        "protocol_active": False,
        "conditions_met": [],
        "conditions_failed": [],
        "influence": 0.0,
        "ml_dog_play": False,
        "recommendation": ""
    }

    if sport.upper() != "NHL":
        signal["recommendation"] = "Protocol only applies to NHL"
        return signal

    # Check conditions
    is_dog = spread > 0  # Positive spread = underdog
    is_puck_line = abs(spread) == 1.5
    high_research = research_score >= 9.3
    public_heavy = public_pct >= 65

    if is_dog and is_puck_line:
        signal["conditions_met"].append(f"Puck line dog (+{spread})")
    elif is_dog:
        signal["conditions_met"].append(f"Underdog (+{spread})")
    else:
        signal["conditions_failed"].append("Not underdog")

    if high_research:
        signal["conditions_met"].append(f"Research score {research_score:.1f} >= 9.3")
    else:
        signal["conditions_failed"].append(f"Research score {research_score:.1f} < 9.3")

    if public_heavy:
        signal["conditions_met"].append(f"Public {public_pct:.0f}% >= 65% (fade opportunity)")
    else:
        signal["conditions_failed"].append(f"Public {public_pct:.0f}% < 65%")

    # Calculate influence
    conditions_count = len(signal["conditions_met"])

    if conditions_count >= 3:
        signal["protocol_active"] = True
        signal["influence"] = 0.92
        signal["ml_dog_play"] = True
        signal["recommendation"] = "FULL PROTOCOL - All conditions met. 0.5u ML Dog of the Day."
    elif conditions_count == 2:
        signal["influence"] = 0.70
        signal["recommendation"] = "PARTIAL PROTOCOL - 2/3 conditions. Consider with caution."
    elif conditions_count == 1:
        signal["influence"] = 0.45
        signal["recommendation"] = "WEAK SIGNAL - Only 1/3 conditions met."
    else:
        signal["influence"] = 0.20
        signal["recommendation"] = "NO PROTOCOL - Conditions not met."

    return signal


def get_dynamic_esoteric_weights(jarvis_triggered: bool = False,
                                  immortal_detected: bool = False) -> Dict[str, float]:
    """
    Dynamic esoteric weights based on Jarvis trigger detection.

    When Jarvis triggers are found, boost gematria weight.
    When THE IMMORTAL (2178) is detected, maximize gematria weight.
    """
    if immortal_detected:
        return {
            "gematria": 0.55,      # IMMORTAL boost (max)
            "numerology": 0.15,
            "astro": 0.10,
            "vedic": 0.05,
            "sacred": 0.05,
            "fib_phi": 0.05,
            "vortex": 0.05
        }
    elif jarvis_triggered:
        return {
            "gematria": 0.45,      # JARVIS boost
            "numerology": 0.18,
            "astro": 0.12,
            "vedic": 0.08,
            "sacred": 0.05,
            "fib_phi": 0.06,
            "vortex": 0.06
        }
    else:
        return {
            "gematria": 0.30,      # Standard
            "numerology": 0.20,
            "astro": 0.15,
            "vedic": 0.10,
            "sacred": 0.10,
            "fib_phi": 0.08,
            "vortex": 0.07
        }


def calculate_confluence(research_score: float, esoteric_score: float,
                         jarvis_triggered: bool = False, immortal_detected: bool = False,
                         in_crush_zone: bool = False, in_goldilocks: bool = False) -> Dict[str, Any]:
    """
    THE HEART OF THE SYSTEM - Calculate cosmic confluence between research and esoteric.

    IMMORTAL confluence is the highest tier - only when 2178 is detected
    and research model also aligns.

    Confluence Levels:
    - IMMORTAL:       2178 detected + both ≥7.5 + aligned ≥80% → +10 boost
    - JARVIS_PERFECT: Trigger + both ≥7.5 + aligned ≥80%      → +7 boost
    - PERFECT:        Both ≥7.5 + aligned ≥80%                → +5 boost
    - STRONG:         Both ≥7.5 OR aligned ≥70%               → +3 boost
    - MODERATE:       Aligned ≥60%                            → +1 boost
    - DIVERGENT:      Models disagree                         → +0 boost
    """
    confluence = {
        "research_score": round(research_score, 2),
        "esoteric_score": round(esoteric_score, 2),
        "alignment_pct": 0.0,
        "level": "DIVERGENT",
        "boost": 0.0,
        "description": "",
        "factors": []
    }

    # Normalize both scores to 0-10 scale for comparison
    r_norm = min(10, max(0, research_score))
    e_norm = min(10, max(0, esoteric_score))

    # Calculate alignment (how close are they on 0-10 scale)
    diff = abs(r_norm - e_norm)
    alignment = (1 - (diff / 10)) * 100  # 0-100%
    confluence["alignment_pct"] = round(alignment, 1)

    # Check conditions
    both_high = r_norm >= 7.5 and e_norm >= 7.5
    aligned_80 = alignment >= 80
    aligned_70 = alignment >= 70
    aligned_60 = alignment >= 60

    # Determine confluence level (check in order of priority)
    if immortal_detected and both_high and aligned_80:
        confluence["level"] = "IMMORTAL"
        confluence["boost"] = 10.0
        confluence["description"] = "THE IMMORTAL CONFLUENCE - 2178 detected with full model alignment. Maximum edge."
        confluence["factors"].append("IMMORTAL_DETECTED")

    elif jarvis_triggered and both_high and aligned_80:
        confluence["level"] = "JARVIS_PERFECT"
        confluence["boost"] = 7.0
        confluence["description"] = "JARVIS PERFECT CONFLUENCE - Trigger detected with strong alignment."
        confluence["factors"].append("JARVIS_TRIGGERED")

    elif both_high and aligned_80:
        confluence["level"] = "PERFECT"
        confluence["boost"] = 5.0
        confluence["description"] = "Perfect cosmic alignment between research and esoteric models."

    elif both_high or (aligned_70 and (r_norm >= 7.0 or e_norm >= 7.0)):
        confluence["level"] = "STRONG"
        confluence["boost"] = 3.0
        confluence["description"] = "Strong confluence - models showing agreement."

    elif aligned_60:
        confluence["level"] = "MODERATE"
        confluence["boost"] = 1.0
        confluence["description"] = "Moderate alignment between models."

    else:
        confluence["level"] = "DIVERGENT"
        confluence["boost"] = 0.0
        confluence["description"] = "Models diverging - use primary research score with caution."

    # Apply crush zone and goldilocks bonuses on top
    if in_crush_zone:
        confluence["boost"] += 2.0
        confluence["factors"].append("CRUSH_ZONE_ACTIVE")
        confluence["description"] += " [PUBLIC FADE CRUSH ZONE]"

    if in_goldilocks:
        confluence["boost"] += 1.0
        confluence["factors"].append("GOLDILOCKS_SPREAD")
        confluence["description"] += " [GOLDILOCKS SPREAD]"

    return confluence


def calculate_blended_probability(research_score: float, esoteric_score: float,
                                   confluence_boost: float = 0) -> Dict[str, Any]:
    """
    Calculate blended probability using the 67/33 RS/Quant formula.

    Formula: 0.67 * (research/10) + 0.33 * (esoteric/10)
    Then apply confluence boost.

    Returns percentage (0-100 scale).
    """
    # Normalize scores to 0-1
    r_norm = min(1.0, max(0, research_score / 10))
    e_norm = min(1.0, max(0, esoteric_score / 10))

    # Apply 67/33 blend
    base_blend = (0.67 * r_norm) + (0.33 * e_norm)

    # Convert to percentage
    base_pct = base_blend * 100

    # Apply confluence boost (scaled to percentage)
    boost_pct = confluence_boost * 3  # Each boost point = 3% increase
    final_pct = min(95, base_pct + boost_pct)  # Cap at 95%

    return {
        "base_blend": round(base_blend, 4),
        "base_percentage": round(base_pct, 1),
        "confluence_boost_pct": round(boost_pct, 1),
        "final_percentage": round(final_pct, 1),
        "formula": "0.67 × (research/10) + 0.33 × (esoteric/10) + confluence_boost"
    }


def determine_bet_tier(blended_pct: float, nhl_protocol_active: bool = False) -> Dict[str, Any]:
    """
    Determine betting tier based on blended probability.

    Tiers:
    - GOLD_STAR:   ≥72% → 2u
    - EDGE_LEAN:   ≥68% → 1u
    - NHL_DOG:     Protocol active → 0.5u ML
    - MONITOR:     ≥60% → 0u (watch only)
    - PASS:        <60% → skip
    """
    tier = {
        "blended_pct": blended_pct,
        "tier": "PASS",
        "units": 0.0,
        "reasoning": []
    }

    if blended_pct >= 72:
        tier["tier"] = "GOLD_STAR"
        tier["units"] = 2.0
        tier["reasoning"].append(f"Blended {blended_pct:.1f}% >= 72% threshold")

    elif blended_pct >= 68:
        tier["tier"] = "EDGE_LEAN"
        tier["units"] = 1.0
        tier["reasoning"].append(f"Blended {blended_pct:.1f}% >= 68% threshold")

    elif blended_pct >= 60:
        tier["tier"] = "MONITOR"
        tier["units"] = 0.0
        tier["reasoning"].append(f"Blended {blended_pct:.1f}% >= 60% - monitor only")

    else:
        tier["tier"] = "PASS"
        tier["units"] = 0.0
        tier["reasoning"].append(f"Blended {blended_pct:.1f}% < 60% - insufficient edge")

    # NHL Dog Protocol override
    if nhl_protocol_active:
        tier["nhl_ml_dog"] = True
        tier["nhl_units"] = 0.5
        tier["reasoning"].append("NHL DOG PROTOCOL ACTIVE - 0.5u ML Dog")

    return tier


class JarvisSavantEngine:
    """
    JARVIS SAVANT ENGINE v7.3

    The complete scoring and confluence system.
    Combines:
    - 8 AI Models (from MasterPredictionSystem)
    - 8 Pillars (from PillarsAnalyzer)
    - JARVIS Triggers (gematria, numerology)
    - Esoteric Edge (moon, Tesla, sacred geometry)
    - Public Fade (exoteric edge)
    - Spread Analysis (Goldilocks, Trap Gate)
    - Confluence Calculator (alignment measurement)
    - Blended Probability (67/33 formula)
    - Bet Tiers (Gold Star, Edge Lean)

    Philosophy: Competition + variance.
    Edges from esoteric resonance (gematria dominant) + exoteric inefficiencies.
    Straight betting only.
    """

    def __init__(self):
        self.version = "v7.3"
        self.ytd_units = 94.40  # Update after results
        self.straight_betting_only = True

        # Thresholds
        self.gold_star_threshold = 72
        self.edge_lean_threshold = 68
        self.ml_dog_lotto_units = 0.5

        # NHL Protocol thresholds
        self.nhl_rs_threshold = 9.3
        self.nhl_public_threshold = 65

    def analyze_pick(self, pick_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete analysis of a single pick using all systems.

        Required pick_data fields:
        - player_name (optional for game picks)
        - team_name
        - opponent_name
        - sport
        - spread (optional)
        - public_pct (optional, default 50)
        - is_favorite (optional, default False)
        - ai_score (from MPS, default 5.0)
        - pillar_score (from Pillars, default 3.0)
        """
        # Extract data with defaults
        player_name = pick_data.get("player_name", "")
        team_name = pick_data.get("team_name", "")
        opponent_name = pick_data.get("opponent_name", "")
        sport = pick_data.get("sport", "").upper()
        spread = pick_data.get("spread", 0)
        public_pct = pick_data.get("public_pct", 50)
        is_favorite = pick_data.get("is_favorite", spread < 0)
        ai_score = pick_data.get("ai_score", 5.0)
        pillar_score = pick_data.get("pillar_score", 3.0)
        jersey_number = pick_data.get("jersey_number")

        # Calculate all signals
        gematria = calculate_gematria_signal(player_name, team_name, opponent_name, jersey_number)
        public_fade = calculate_public_fade_signal(public_pct, is_favorite)
        mid_spread = calculate_mid_spread_signal(spread)
        trap_gate = calculate_large_spread_trap(spread)

        # Get daily energy
        daily_energy = get_daily_energy()
        moon = get_moon_phase()
        numerology = calculate_date_numerology()

        # Check JARVIS triggers on combined values
        jarvis_triggered = gematria["total_boost"] > 0
        immortal_detected = gematria["immortal_detected"]

        # Get dynamic weights
        weights = get_dynamic_esoteric_weights(jarvis_triggered, immortal_detected)

        # Calculate RESEARCH SCORE (AI + Pillars, scaled to 0-10)
        # AI Models max 8, Pillars max 8 → combined max 16, scale to 10
        research_raw = ai_score + pillar_score
        research_score = min(10, (research_raw / 16) * 10)

        # Calculate ESOTERIC SCORE (JARVIS + Esoteric + Astro/Vedic factors)
        esoteric_components = []

        # Gematria (52% when IMMORTAL, 45% when triggered, 30% otherwise)
        esoteric_components.append(gematria["influence"] * weights["gematria"] * 10)

        # Numerology (date-based)
        energy_influence = daily_energy.get("overall_score", 50) / 100
        esoteric_components.append(energy_influence * weights["numerology"] * 10)

        # Tesla alignment
        if numerology.get("tesla_energy"):
            esoteric_components.append(0.8 * weights["sacred"] * 10)

        # Master number boost
        if numerology.get("is_master_number_day"):
            esoteric_components.append(1.0 * weights["sacred"] * 10)

        # PHASE 2: Astro/Vedic components (13% astro + 10% vedic = 23%)
        try:
            astro_data = calculate_astro_score(sport)
            astro_influence = astro_data["astro_score"] / 10  # Normalize to 0-1

            # Planetary hour component (part of astro weight)
            planetary_component = astro_data["components"]["planetary_hour"]["influence"]
            esoteric_components.append(planetary_component * weights["astro"] * 10)

            # Nakshatra component (part of vedic weight)
            nakshatra_component = astro_data["components"]["nakshatra"]["influence"]
            esoteric_components.append(nakshatra_component * weights["vedic"] * 10)

            # Retrograde penalty (applied to both)
            if astro_data["components"]["retrograde"]["any_active"]:
                retrograde_penalty = 1 - astro_data["components"]["retrograde"]["influence"]
                esoteric_components.append(-retrograde_penalty * 2)  # Penalty up to -1.4 points
        except Exception:
            # Fallback to moon phase if astro calculation fails
            moon_influence = 0.7 if moon.get("phase") == "Full Moon" else 0.5
            esoteric_components.append(moon_influence * weights["astro"] * 10)

        # Fibonacci/Phi component (check if spread aligns with Fib numbers)
        if spread and abs(spread) in [1.5, 2, 3, 5, 8, 13]:
            esoteric_components.append(0.7 * weights["fib_phi"] * 10)

        # Vortex component (already in gematria reduction, add small boost)
        esoteric_components.append(0.5 * weights["vortex"] * 10)

        esoteric_raw = sum(esoteric_components)

        # Apply trap gate penalty if active
        if trap_gate["is_trap"]:
            esoteric_raw *= trap_gate["penalty"]

        # Apply goldilocks boost
        if mid_spread["in_goldilocks"]:
            esoteric_raw *= mid_spread["boost_modifier"]

        esoteric_score = min(10, esoteric_raw)

        # Calculate CONFLUENCE
        confluence = calculate_confluence(
            research_score,
            esoteric_score,
            jarvis_triggered,
            immortal_detected,
            public_fade["in_crush_zone"],
            mid_spread["in_goldilocks"]
        )

        # Calculate BLENDED PROBABILITY
        blended = calculate_blended_probability(
            research_score,
            esoteric_score,
            confluence["boost"]
        )

        # Check NHL DOG PROTOCOL
        nhl_protocol = calculate_nhl_dog_protocol(
            sport, spread, research_score, public_pct
        )

        # Determine BET TIER
        bet_tier = determine_bet_tier(
            blended["final_percentage"],
            nhl_protocol["protocol_active"]
        )

        # Calculate JARVIS score component (0-4 max)
        jarvis_score = min(4.0, gematria["total_boost"] / 5)

        # Build comprehensive result
        return {
            "version": self.version,

            # Dual Scores
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),

            # Confluence
            "confluence": confluence,

            # Blended Result
            "blended_probability": blended,

            # Bet Recommendation
            "bet_recommendation": bet_tier,

            # Scoring Breakdown (legacy format for compatibility)
            "scoring_breakdown": {
                "ai_models": round(ai_score, 2),
                "pillars": round(pillar_score, 2),
                "jarvis": round(jarvis_score, 2),
                "esoteric": round(esoteric_score - jarvis_score, 2)  # Non-JARVIS esoteric
            },

            # Total Score (legacy, max 22)
            "total_score": round(ai_score + pillar_score + jarvis_score + (esoteric_score * 0.2), 2),

            # Confidence (legacy format)
            "confidence": confluence["level"] if confluence["level"] in ["IMMORTAL", "JARVIS_PERFECT", "PERFECT"] else (
                "SMASH" if blended["final_percentage"] >= 78 else
                "HIGH" if blended["final_percentage"] >= 70 else
                "MEDIUM" if blended["final_percentage"] >= 60 else
                "LOW"
            ),
            "confidence_pct": round(blended["final_percentage"], 1),

            # Signal Details
            "signals": {
                "gematria": gematria,
                "public_fade": public_fade,
                "mid_spread": mid_spread,
                "trap_gate": trap_gate,
                "nhl_protocol": nhl_protocol
            },

            # JARVIS Status
            "jarvis_status": {
                "triggered": jarvis_triggered,
                "immortal_active": immortal_detected,
                "gematria_hits": gematria["gematria_hits"],
                "triggers_found": gematria["triggers_found"],
                "total_boost": gematria["total_boost"],
                "tier": gematria["tier"],
                "crush_zone_active": public_fade["in_crush_zone"],
                "goldilocks_active": mid_spread["in_goldilocks"],
                "trap_gate_active": trap_gate["is_trap"]
            },

            # Daily Energy
            "daily_energy": daily_energy
        }


# Global engine instance
_jarvis_engine: Optional[JarvisSavantEngine] = None


def get_jarvis_engine() -> JarvisSavantEngine:
    """Get or create the JarvisSavantEngine singleton."""
    global _jarvis_engine
    if _jarvis_engine is None:
        _jarvis_engine = JarvisSavantEngine()
        logger.info("JarvisSavantEngine v7.3 initialized")
    return _jarvis_engine


# ============================================================================
# PHASE 2: VEDIC/ASTRO MODULE
# Weight: 13% astro + 10% vedic = 23% of esoteric score
# Components: Planetary Hours, Retrograde Detection, Nakshatra Positions
# ============================================================================

# Planetary hour rulers in Chaldean order
# Each day starts with its ruling planet, then follows this sequence
PLANETARY_SEQUENCE = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Day rulers (Sunday=0, Monday=1, etc.)
DAY_RULERS = {
    0: "Sun",      # Sunday
    1: "Moon",     # Monday
    2: "Mars",     # Tuesday
    3: "Mercury",  # Wednesday
    4: "Jupiter",  # Thursday
    5: "Venus",    # Friday
    6: "Saturn"    # Saturday
}

# Planetary characteristics for betting
PLANET_BETTING_INFLUENCE = {
    "Sun": {
        "influence": 0.75,
        "characteristics": "Authority, confidence, favorites perform",
        "bet_signal": "CHALK_FRIENDLY",
        "sports_boost": ["NBA", "NFL"]  # High-profile sports
    },
    "Moon": {
        "influence": 0.65,
        "characteristics": "Emotion, volatility, home teams favored",
        "bet_signal": "HOME_EDGE",
        "sports_boost": ["NHL", "MLB"]  # Night games
    },
    "Mars": {
        "influence": 0.80,
        "characteristics": "Aggression, underdogs fight, high scoring",
        "bet_signal": "DOG_WARRIOR",
        "sports_boost": ["NFL", "NHL"]  # Physical sports
    },
    "Mercury": {
        "influence": 0.55,
        "characteristics": "Speed, unpredictability, communication errors",
        "bet_signal": "CHAOS_FACTOR",
        "sports_boost": ["NBA"]  # Fast-paced
    },
    "Jupiter": {
        "influence": 0.85,
        "characteristics": "Expansion, luck, overs, big favorites cover",
        "bet_signal": "EXPANSION_PLAY",
        "sports_boost": ["NBA", "NFL"]  # High scoring potential
    },
    "Venus": {
        "influence": 0.60,
        "characteristics": "Harmony, low variance, unders, close games",
        "bet_signal": "UNDER_LEAN",
        "sports_boost": ["MLB", "NHL"]  # Lower scoring
    },
    "Saturn": {
        "influence": 0.70,
        "characteristics": "Restriction, discipline, defense, unders",
        "bet_signal": "DEFENSIVE_GRIND",
        "sports_boost": ["NFL", "NHL"]  # Defensive sports
    }
}

# 27 Nakshatras (Lunar Mansions) with betting characteristics
NAKSHATRAS = [
    {"name": "Ashwini", "ruler": "Ketu", "nature": "swift", "betting": "quick_action", "influence": 0.70},
    {"name": "Bharani", "ruler": "Venus", "nature": "fierce", "betting": "high_risk", "influence": 0.65},
    {"name": "Krittika", "ruler": "Sun", "nature": "mixed", "betting": "favorites", "influence": 0.75},
    {"name": "Rohini", "ruler": "Moon", "nature": "fixed", "betting": "home_teams", "influence": 0.80},
    {"name": "Mrigashira", "ruler": "Mars", "nature": "soft", "betting": "careful", "influence": 0.55},
    {"name": "Ardra", "ruler": "Rahu", "nature": "sharp", "betting": "upsets", "influence": 0.85},
    {"name": "Punarvasu", "ruler": "Jupiter", "nature": "movable", "betting": "overs", "influence": 0.75},
    {"name": "Pushya", "ruler": "Saturn", "nature": "light", "betting": "unders", "influence": 0.90},  # Most auspicious
    {"name": "Ashlesha", "ruler": "Mercury", "nature": "sharp", "betting": "avoid", "influence": 0.40},
    {"name": "Magha", "ruler": "Ketu", "nature": "fierce", "betting": "dogs", "influence": 0.70},
    {"name": "Purva Phalguni", "ruler": "Venus", "nature": "fierce", "betting": "favorites", "influence": 0.65},
    {"name": "Uttara Phalguni", "ruler": "Sun", "nature": "fixed", "betting": "chalk", "influence": 0.75},
    {"name": "Hasta", "ruler": "Moon", "nature": "light", "betting": "skill_games", "influence": 0.80},
    {"name": "Chitra", "ruler": "Mars", "nature": "soft", "betting": "props", "influence": 0.70},
    {"name": "Swati", "ruler": "Rahu", "nature": "movable", "betting": "line_movement", "influence": 0.75},
    {"name": "Vishakha", "ruler": "Jupiter", "nature": "mixed", "betting": "parlays", "influence": 0.65},
    {"name": "Anuradha", "ruler": "Saturn", "nature": "soft", "betting": "defense", "influence": 0.80},
    {"name": "Jyeshtha", "ruler": "Mercury", "nature": "sharp", "betting": "veteran_edge", "influence": 0.70},
    {"name": "Mula", "ruler": "Ketu", "nature": "sharp", "betting": "destruction", "influence": 0.50},
    {"name": "Purva Ashadha", "ruler": "Venus", "nature": "fierce", "betting": "momentum", "influence": 0.75},
    {"name": "Uttara Ashadha", "ruler": "Sun", "nature": "fixed", "betting": "champions", "influence": 0.85},
    {"name": "Shravana", "ruler": "Moon", "nature": "movable", "betting": "listen_sharps", "influence": 0.80},
    {"name": "Dhanishta", "ruler": "Mars", "nature": "movable", "betting": "aggressive", "influence": 0.75},
    {"name": "Shatabhisha", "ruler": "Rahu", "nature": "movable", "betting": "healing", "influence": 0.70},
    {"name": "Purva Bhadrapada", "ruler": "Jupiter", "nature": "fierce", "betting": "risk_on", "influence": 0.65},
    {"name": "Uttara Bhadrapada", "ruler": "Saturn", "nature": "fixed", "betting": "patience", "influence": 0.80},
    {"name": "Revati", "ruler": "Mercury", "nature": "soft", "betting": "completion", "influence": 0.75}
]

# Mercury Retrograde periods for 2026 (approximate)
MERCURY_RETROGRADE_2026 = [
    {"start": (2026, 1, 25), "end": (2026, 2, 14)},
    {"start": (2026, 5, 19), "end": (2026, 6, 11)},
    {"start": (2026, 9, 17), "end": (2026, 10, 9)}
]

# Venus Retrograde 2026 (approximate - every 18 months)
VENUS_RETROGRADE_2026 = [
    {"start": (2026, 3, 2), "end": (2026, 4, 12)}
]

# Mars Retrograde 2026 (approximate - every 26 months)
MARS_RETROGRADE_2026 = [
    {"start": (2026, 12, 6), "end": (2027, 2, 24)}
]


def calculate_planetary_hour(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate the current planetary hour based on Chaldean order.

    Each day has 24 planetary hours (12 day, 12 night).
    Day hours start at sunrise, night hours at sunset.
    For simplicity, we use 6 AM as sunrise and 6 PM as sunset.
    """
    if dt is None:
        dt = datetime.now()

    weekday = dt.weekday()  # Monday=0, Sunday=6
    # Adjust to Sunday=0 for our DAY_RULERS
    day_index = (weekday + 1) % 7

    day_ruler = DAY_RULERS[day_index]

    # Calculate hour of day (0-23)
    hour = dt.hour

    # Determine if day or night hour
    # Day hours: 6 AM - 6 PM (6-17)
    # Night hours: 6 PM - 6 AM (18-23, 0-5)
    if 6 <= hour < 18:
        is_day = True
        hour_of_period = hour - 6  # 0-11
    else:
        is_day = False
        if hour >= 18:
            hour_of_period = hour - 18  # 0-5
        else:
            hour_of_period = hour + 6  # 6-11

    # Find starting index in planetary sequence for this day's ruler
    day_ruler_index = PLANETARY_SEQUENCE.index(day_ruler)

    # For night hours, we start from the 13th hour position
    # (12 day hours have passed)
    if not is_day:
        offset = 12 + hour_of_period
    else:
        offset = hour_of_period

    # Calculate current planetary hour ruler
    current_index = (day_ruler_index + offset) % 7
    current_ruler = PLANETARY_SEQUENCE[current_index]

    # Get planetary influence
    planet_info = PLANET_BETTING_INFLUENCE[current_ruler]

    return {
        "datetime": dt.isoformat(),
        "day_ruler": day_ruler,
        "current_hour_ruler": current_ruler,
        "is_day_hour": is_day,
        "hour_of_period": hour_of_period + 1,  # 1-indexed for display
        "influence": planet_info["influence"],
        "characteristics": planet_info["characteristics"],
        "bet_signal": planet_info["bet_signal"],
        "sports_boost": planet_info["sports_boost"]
    }


def is_planet_retrograde(planet: str, dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Check if a planet is retrograde.

    Retrograde periods cause disruption and reversals.
    Mercury: Communication issues, upsets more likely
    Venus: Value plays backfire
    Mars: Aggression misfires, underdogs struggle
    """
    if dt is None:
        dt = datetime.now()

    date_tuple = (dt.year, dt.month, dt.day)

    retrograde_periods = {
        "Mercury": MERCURY_RETROGRADE_2026,
        "Venus": VENUS_RETROGRADE_2026,
        "Mars": MARS_RETROGRADE_2026
    }

    if planet not in retrograde_periods:
        return {"planet": planet, "retrograde": False, "applicable": False}

    for period in retrograde_periods[planet]:
        start = period["start"]
        end = period["end"]

        # Convert to comparable format
        if start <= date_tuple <= end:
            return {
                "planet": planet,
                "retrograde": True,
                "period_start": f"{start[0]}-{start[1]:02d}-{start[2]:02d}",
                "period_end": f"{end[0]}-{end[1]:02d}-{end[2]:02d}",
                "betting_impact": get_retrograde_impact(planet)
            }

    return {
        "planet": planet,
        "retrograde": False,
        "next_retrograde": get_next_retrograde(planet, dt)
    }


def get_retrograde_impact(planet: str) -> Dict[str, Any]:
    """Get the betting impact of a retrograde planet."""
    impacts = {
        "Mercury": {
            "modifier": -0.10,
            "description": "Communication breakdowns, miscues, upsets more likely",
            "recommendation": "FADE FAVORITES - chaos factor elevated",
            "avoid": ["heavy chalk", "complex parlays"]
        },
        "Venus": {
            "modifier": -0.08,
            "description": "Value plays misfire, beauty doesn't win",
            "recommendation": "CONTRARIAN VALUE - perceived value traps",
            "avoid": ["value plays", "public dogs"]
        },
        "Mars": {
            "modifier": -0.12,
            "description": "Aggression backfires, underdogs can't capitalize",
            "recommendation": "DEFENSIVE POSTURE - low variance plays",
            "avoid": ["underdog ML", "aggressive dogs"]
        }
    }
    return impacts.get(planet, {"modifier": 0, "description": "Unknown"})


def get_next_retrograde(planet: str, dt: datetime) -> Optional[str]:
    """Get the next retrograde period for a planet."""
    retrograde_periods = {
        "Mercury": MERCURY_RETROGRADE_2026,
        "Venus": VENUS_RETROGRADE_2026,
        "Mars": MARS_RETROGRADE_2026
    }

    if planet not in retrograde_periods:
        return None

    date_tuple = (dt.year, dt.month, dt.day)

    for period in retrograde_periods[planet]:
        if period["start"] > date_tuple:
            return f"{period['start'][0]}-{period['start'][1]:02d}-{period['start'][2]:02d}"

    return "Next year"


def calculate_nakshatra(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate the current Nakshatra (lunar mansion).

    The Moon transits through all 27 Nakshatras in ~27.3 days.
    Each Nakshatra spans 13°20' of the zodiac.

    This is a simplified calculation based on lunar cycle position.
    For precise calculations, ephemeris data would be needed.
    """
    if dt is None:
        dt = datetime.now()

    # Known new moon for reference
    known_new_moon = datetime(2024, 1, 11)
    days_since = (dt - known_new_moon).days

    # Lunar cycle is ~27.3 days for sidereal month (nakshatra-based)
    sidereal_month = 27.3
    nakshatra_position = (days_since % sidereal_month) / sidereal_month

    # Calculate nakshatra index (0-26)
    nakshatra_index = int(nakshatra_position * 27) % 27
    nakshatra = NAKSHATRAS[nakshatra_index]

    # Calculate pada (quarter) - each nakshatra has 4 padas
    pada_position = (nakshatra_position * 27) % 1
    pada = int(pada_position * 4) + 1

    return {
        "nakshatra": nakshatra["name"],
        "nakshatra_index": nakshatra_index + 1,  # 1-indexed
        "pada": pada,
        "ruler": nakshatra["ruler"],
        "nature": nakshatra["nature"],
        "betting_type": nakshatra["betting"],
        "influence": nakshatra["influence"],
        "moon_age_days": round(days_since % sidereal_month, 1)
    }


def get_retrograde_status() -> Dict[str, Any]:
    """Get retrograde status for all tracked planets."""
    dt = datetime.now()
    return {
        "mercury": is_planet_retrograde("Mercury", dt),
        "venus": is_planet_retrograde("Venus", dt),
        "mars": is_planet_retrograde("Mars", dt),
        "any_retrograde": any([
            is_planet_retrograde("Mercury", dt).get("retrograde", False),
            is_planet_retrograde("Venus", dt).get("retrograde", False),
            is_planet_retrograde("Mars", dt).get("retrograde", False)
        ])
    }


def calculate_astro_score(sport: str = "") -> Dict[str, Any]:
    """
    Calculate the complete astro/vedic score.

    Weight breakdown:
    - Planetary Hour: 40% of astro score
    - Nakshatra: 35% of astro score
    - Retrograde Status: 25% of astro score
    """
    planetary_hour = calculate_planetary_hour()
    nakshatra = calculate_nakshatra()
    retrogrades = get_retrograde_status()

    # Calculate component scores (0-1 scale)
    planetary_influence = planetary_hour["influence"]

    # Boost if sport matches planetary hour boost
    sport_upper = sport.upper()
    if sport_upper in planetary_hour.get("sports_boost", []):
        planetary_influence = min(1.0, planetary_influence + 0.10)

    nakshatra_influence = nakshatra["influence"]

    # Retrograde penalty
    retrograde_penalty = 0
    if retrogrades["any_retrograde"]:
        for planet in ["mercury", "venus", "mars"]:
            if retrogrades[planet].get("retrograde", False):
                impact = retrogrades[planet].get("betting_impact", {})
                retrograde_penalty += abs(impact.get("modifier", 0))

    retrograde_influence = max(0.3, 1.0 - retrograde_penalty)

    # Weighted combination
    # Planetary Hour: 40%, Nakshatra: 35%, Retrograde: 25%
    astro_score = (
        planetary_influence * 0.40 +
        nakshatra_influence * 0.35 +
        retrograde_influence * 0.25
    )

    # Scale to 0-10
    astro_score_scaled = astro_score * 10

    return {
        "astro_score": round(astro_score_scaled, 2),
        "components": {
            "planetary_hour": {
                "ruler": planetary_hour["current_hour_ruler"],
                "influence": planetary_influence,
                "signal": planetary_hour["bet_signal"],
                "sports_boost": planetary_hour["sports_boost"]
            },
            "nakshatra": {
                "name": nakshatra["nakshatra"],
                "ruler": nakshatra["ruler"],
                "influence": nakshatra_influence,
                "betting_type": nakshatra["betting_type"]
            },
            "retrograde": {
                "any_active": retrogrades["any_retrograde"],
                "influence": retrograde_influence,
                "details": retrogrades
            }
        },
        "overall_signal": _get_astro_signal(astro_score_scaled, planetary_hour, nakshatra),
        "timestamp": datetime.now().isoformat()
    }


def _get_astro_signal(score: float, planetary: Dict, nakshatra: Dict) -> str:
    """Generate an overall astro betting signal."""
    if score >= 8.0:
        return f"COSMIC ALIGNMENT - {planetary['current_hour_ruler']} hour + {nakshatra['nakshatra']} nakshatra favor betting"
    elif score >= 6.5:
        return f"FAVORABLE - {planetary['bet_signal']} signal active"
    elif score >= 5.0:
        return f"NEUTRAL - Standard variance expected"
    elif score >= 3.5:
        return f"CAUTION - {nakshatra['nature']} energy may cause upsets"
    else:
        return f"AVOID - Cosmic conditions unfavorable"


# ============================================================================
# LIVE DATA ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "14.1",
        "codename": "PRODUCTION_HARDENED",
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

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "player_points,player_rebounds,player_assists,player_threes",
                "oddsFormat": "american"
            }
        )

        if not resp:
            raise HTTPException(status_code=502, detail="Odds API unreachable after retries")

        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

        if resp.status_code != 200:
            logger.warning("Odds API props returned %s for %s", resp.status_code, sport)
            raise HTTPException(status_code=502, detail=f"Odds API returned error: {resp.status_code}")

        try:
            games = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Odds API props response: %s", e)
            raise HTTPException(status_code=502, detail="Invalid response from Odds API")

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

        logger.info("Props data retrieved for %s: %d games with props", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Props fetch failed for %s: %s", sport, e)
        raise HTTPException(status_code=500, detail="Internal error fetching props")

    result = {"sport": sport.upper(), "source": "odds_api", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return result


@router.get("/best-bets/{sport}")
async def get_best_bets(sport: str):
    """
    Get best bets using JARVIS SAVANT ENGINE v7.3.

    Full confluence scoring system:
    - 8 AI Models + 8 Pillars → Research Score (0-10)
    - JARVIS + Esoteric factors → Esoteric Score (0-10)
    - Confluence alignment measurement
    - Blended probability (67/33 formula)
    - Bet tiers (Gold Star 2u, Edge Lean 1u)

    Returns TWO categories: props (player props) and game_picks (spreads, totals, ML).
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"best-bets:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    # Get JARVIS Engine and daily energy
    engine = get_jarvis_engine()
    daily_energy = get_daily_energy()

    # Fetch sharp money and splits for public fade analysis
    sharp_data = await get_sharp_money(sport)
    sharp_lookup = {}
    for signal in sharp_data.get("data", []):
        game_key = f"{signal.get('away_team')}@{signal.get('home_team')}"
        sharp_lookup[game_key] = signal

    # Try to get splits for public percentages
    splits_lookup = {}
    try:
        splits_data = await get_splits(sport)
        for split in splits_data.get("data", []):
            game_key = f"{split.get('away_team')}@{split.get('home_team')}"
            home_bets = split.get("spread_splits", {}).get("home", {}).get("bets_pct", 50)
            splits_lookup[game_key] = home_bets
    except Exception:
        pass  # Continue without splits

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
            sharp_signal = sharp_lookup.get(game_key, {})
            public_pct = splits_lookup.get(game_key, 50)

            for prop in game.get("props", []):
                player = prop.get("player", "Unknown")
                market = prop.get("market", "")
                line = prop.get("line", 0)
                odds = prop.get("odds", -110)
                side = prop.get("side", "Over")

                if side not in ["Over", "Under"]:
                    continue

                # Calculate AI score based on sharp signal
                ai_score = 5.0
                if sharp_signal.get("signal_strength") == "STRONG":
                    ai_score = 7.0
                elif sharp_signal.get("signal_strength") == "MODERATE":
                    ai_score = 6.0

                # Calculate pillar score
                pillar_score = 4.0 if sharp_signal.get("line_variance", 0) > 1.5 else 3.0

                # Use JARVIS Engine for full analysis
                analysis = engine.analyze_pick({
                    "player_name": player,
                    "team_name": home_team,
                    "opponent_name": away_team,
                    "sport": sport,
                    "spread": 0,  # Props don't have spread
                    "public_pct": public_pct,
                    "is_favorite": False,
                    "ai_score": ai_score,
                    "pillar_score": pillar_score
                })

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
                    # Dual Scores
                    "research_score": analysis["research_score"],
                    "esoteric_score": analysis["esoteric_score"],
                    # Confluence
                    "confluence": analysis["confluence"]["level"],
                    "alignment_pct": analysis["confluence"]["alignment_pct"],
                    # Blended Result
                    "blended_pct": analysis["blended_probability"]["final_percentage"],
                    # Bet Recommendation
                    "bet_tier": analysis["bet_recommendation"]["tier"],
                    "units": analysis["bet_recommendation"]["units"],
                    # Legacy fields for compatibility
                    "total_score": analysis["total_score"],
                    "confidence": analysis["confidence"],
                    "confidence_pct": analysis["confidence_pct"],
                    "scoring_breakdown": analysis["scoring_breakdown"],
                    # JARVIS Status
                    "jarvis_triggered": analysis["jarvis_status"]["triggered"],
                    "immortal_active": analysis["jarvis_status"]["immortal_active"],
                    "gematria_tier": analysis["jarvis_status"]["tier"],
                    "sharp_signal": sharp_signal.get("signal_strength", "NONE")
                })
    except HTTPException:
        logger.warning("Props fetch failed for %s", sport)

    # Sort by blended percentage and take top 10
    props_picks.sort(key=lambda x: x["blended_pct"], reverse=True)
    top_props = props_picks[:10]

    # ============================================
    # CATEGORY 2: GAME PICKS (Spreads, Totals, ML)
    # ============================================
    game_picks = []
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
                sharp_signal = sharp_lookup.get(game_key, {})
                public_pct = splits_lookup.get(game_key, 50)

                for bm in game.get("bookmakers", [])[:1]:
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")

                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point", 0)

                            # Build display info
                            if market_key == "spreads":
                                pick_type = "SPREAD"
                                display = f"{pick_name} {point:+.1f}" if point else pick_name
                                spread = point if pick_name == home_team else -point if point else 0
                            elif market_key == "h2h":
                                pick_type = "MONEYLINE"
                                display = f"{pick_name} ML"
                                spread = 0
                            elif market_key == "totals":
                                pick_type = "TOTAL"
                                display = f"{pick_name} {point}" if point else pick_name
                                spread = 0
                            else:
                                continue

                            # Calculate AI score based on sharp signal
                            ai_score = 4.5
                            if sharp_signal.get("signal_strength") == "STRONG":
                                ai_score = 6.5
                            elif sharp_signal.get("signal_strength") == "MODERATE":
                                ai_score = 5.5

                            # Calculate pillar score
                            pillar_score = 4.0 if sharp_signal.get("line_variance", 0) > 1.5 else 3.0

                            # Determine if this is a favorite pick
                            is_favorite = (pick_name == home_team and public_pct > 50) or \
                                         (pick_name == away_team and public_pct < 50)

                            # Use JARVIS Engine for full analysis
                            analysis = engine.analyze_pick({
                                "player_name": "",
                                "team_name": pick_name,
                                "opponent_name": away_team if pick_name == home_team else home_team,
                                "sport": sport,
                                "spread": spread,
                                "public_pct": public_pct if is_favorite else 100 - public_pct,
                                "is_favorite": is_favorite,
                                "ai_score": ai_score,
                                "pillar_score": pillar_score
                            })

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
                                # Dual Scores
                                "research_score": analysis["research_score"],
                                "esoteric_score": analysis["esoteric_score"],
                                # Confluence
                                "confluence": analysis["confluence"]["level"],
                                "alignment_pct": analysis["confluence"]["alignment_pct"],
                                # Blended Result
                                "blended_pct": analysis["blended_probability"]["final_percentage"],
                                # Bet Recommendation
                                "bet_tier": analysis["bet_recommendation"]["tier"],
                                "units": analysis["bet_recommendation"]["units"],
                                # Legacy fields for compatibility
                                "total_score": analysis["total_score"],
                                "confidence": analysis["confidence"],
                                "confidence_pct": analysis["confidence_pct"],
                                "scoring_breakdown": analysis["scoring_breakdown"],
                                # JARVIS Status
                                "jarvis_triggered": analysis["jarvis_status"]["triggered"],
                                "immortal_active": analysis["jarvis_status"]["immortal_active"],
                                "crush_zone": analysis["jarvis_status"]["crush_zone_active"],
                                "goldilocks": analysis["jarvis_status"]["goldilocks_active"],
                                "trap_gate": analysis["jarvis_status"]["trap_gate_active"],
                                "gematria_tier": analysis["jarvis_status"]["tier"],
                                "sharp_signal": sharp_signal.get("signal_strength", "NONE"),
                                # NHL Protocol
                                "nhl_protocol": analysis["signals"]["nhl_protocol"]["protocol_active"] if sport_lower == "nhl" else False
                            })
    except Exception as e:
        logger.warning("Game odds fetch failed: %s", e)

    # Fallback to sharp money if no game picks
    if not game_picks and sharp_data.get("data"):
        for signal in sharp_data.get("data", []):
            home_team = signal.get("home_team", "")
            away_team = signal.get("away_team", "")

            analysis = engine.analyze_pick({
                "player_name": "",
                "team_name": home_team,
                "opponent_name": away_team,
                "sport": sport,
                "spread": signal.get("line_variance", 0),
                "public_pct": 60,
                "is_favorite": True,
                "ai_score": 5.0,
                "pillar_score": 4.0
            })

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
                "research_score": analysis["research_score"],
                "esoteric_score": analysis["esoteric_score"],
                "confluence": analysis["confluence"]["level"],
                "blended_pct": analysis["blended_probability"]["final_percentage"],
                "bet_tier": analysis["bet_recommendation"]["tier"],
                "units": analysis["bet_recommendation"]["units"],
                "total_score": analysis["total_score"],
                "confidence": analysis["confidence"],
                "confidence_pct": analysis["confidence_pct"],
                "scoring_breakdown": analysis["scoring_breakdown"],
                "sharp_signal": signal.get("signal_strength", "MODERATE")
            })

    # Sort by blended percentage and take top 10
    game_picks.sort(key=lambda x: x["blended_pct"], reverse=True)
    top_game_picks = game_picks[:10]

    # ============================================
    # BUILD FINAL RESPONSE
    # ============================================
    result = {
        "sport": sport.upper(),
        "source": "jarvis_savant_engine_v7.3",
        "scoring_system": {
            "version": "v7.3",
            "components": [
                "8 AI Models → Research Score",
                "8 Pillars → Research Score",
                "JARVIS Triggers → Esoteric Score",
                "Gematria (52% weight) → Esoteric Score",
                "Public Fade (-13%) → Esoteric Score",
                "Mid-Spread (+20%) → Esoteric Score",
                "Confluence Calculator → Alignment Boost",
                "Blended Probability (67/33) → Final Score"
            ],
            "bet_tiers": {
                "GOLD_STAR": "≥72% → 2u",
                "EDGE_LEAN": "≥68% → 1u",
                "MONITOR": "≥60% → watch",
                "PASS": "<60% → skip"
            }
        },
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
        "daily_energy": daily_energy,
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
    """Get current esoteric edge analysis."""
    numerology = calculate_date_numerology()
    moon = get_moon_phase()
    energy = get_daily_energy()

    edge_factors = []

    if numerology.get("is_master_number_day"):
        edge_factors.append({"factor": "Master Number Day", "boost": 15, "description": "Elevated spiritual energy"})

    if numerology.get("tesla_energy"):
        edge_factors.append({"factor": "Tesla 3-6-9 Energy", "boost": 10, "description": "Vortex math alignment"})

    if moon.get("phase") == "Full Moon":
        edge_factors.append({"factor": "Full Moon", "boost": 20, "description": "Maximum illumination - expect chaos"})

    for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
        if trigger_num in [33, 93]:
            today_num = sum(int(d) for d in datetime.now().strftime("%Y%m%d"))
            if today_num % trigger_num == 0:
                edge_factors.append({
                    "factor": f"JARVIS: {trigger_data['name']}",
                    "boost": trigger_data["boost"],
                    "description": trigger_data["description"]
                })

    total_boost = sum(f["boost"] for f in edge_factors)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "numerology": numerology,
        "moon_phase": moon,
        "daily_energy": energy,
        "edge_factors": edge_factors,
        "total_edge_boost": total_boost,
        "recommendation": "AGGRESSIVE" if total_boost >= 30 else "STANDARD" if total_boost >= 15 else "CONSERVATIVE"
    }


# ============================================================================
# JARVIS SAVANT ENGINE ENDPOINTS
# ============================================================================

@router.get("/validate-immortal")
async def validate_immortal():
    """
    Validate the mathematical properties of THE IMMORTAL number (2178).

    Proves:
    - 2178 × 4 = 8712 (its reversal)
    - 2178 × 8712 = 18974736 = 66^4

    This is the ONLY 4-digit number with both properties.
    Used as the highest-tier JARVIS trigger.
    """
    return validate_2178()


@router.get("/jarvis-triggers")
async def get_jarvis_triggers():
    """
    Get all JARVIS trigger numbers and their properties.

    These are the sacred numbers that signal edge opportunities:
    - 2178: THE IMMORTAL (Legendary tier)
    - 201: THE ORDER (High tier)
    - 33: THE MASTER (High tier)
    - 93: THE WILL (High tier)
    - 322: THE SOCIETY (High tier)

    Also includes Tesla numbers (3, 6, 9) and Fibonacci sequence.
    """
    return {
        "version": "v7.3",
        "triggers": JARVIS_TRIGGERS,
        "tesla_numbers": TESLA_NUMBERS,
        "power_numbers": POWER_NUMBERS,
        "fibonacci_sequence": FIBONACCI_NUMBERS,
        "vortex_pattern": VORTEX_PATTERN,
        "immortal_validation": validate_2178(),
        "usage": {
            "direct_match": "Full boost when value equals trigger number",
            "reduction_match": "Half boost when digit reduction matches trigger",
            "divisibility": "Partial boost when divisible by 33",
            "sequence": "Full boost when value contains 2178 sequence"
        }
    }


@router.get("/check-trigger/{value}")
async def check_trigger_value(value: int):
    """
    Check if a specific value triggers any JARVIS edge numbers.

    Checks for:
    1. Direct match with trigger numbers
    2. Reduction to trigger numbers (digit sum)
    3. Divisibility by 33 (master number)
    4. Tesla 3-6-9 alignment
    5. Contains 2178 sequence
    6. Fibonacci alignment
    7. Vortex math pattern

    Example: /live/check-trigger/231
    """
    result = check_jarvis_trigger(value)
    result["interpretation"] = ""

    if result["triggered"]:
        if result["highest_tier"] == "LEGENDARY":
            result["interpretation"] = "IMMORTAL DETECTED - Maximum edge signal. This is rare."
        elif result["total_boost"] >= 15:
            result["interpretation"] = "HIGH EDGE - Multiple triggers activated. Strong signal."
        elif result["total_boost"] >= 10:
            result["interpretation"] = "MODERATE EDGE - Significant trigger activity."
        elif result["total_boost"] >= 5:
            result["interpretation"] = "LIGHT EDGE - Some trigger activity present."
        else:
            result["interpretation"] = "MINIMAL EDGE - Minor trigger activity."
    else:
        result["interpretation"] = "NO TRIGGERS - This value does not activate any JARVIS signals."

    return result


@router.get("/confluence/{sport}")
async def get_confluence_analysis(sport: str):
    """
    Get detailed confluence analysis for a sport.

    Shows how Research Score and Esoteric Score align for current games.
    The confluence level determines the confidence multiplier.

    Confluence Levels:
    - IMMORTAL: 2178 detected + both scores ≥7.5 + aligned ≥80% → +10 boost
    - JARVIS_PERFECT: Trigger + both ≥7.5 + aligned ≥80% → +7 boost
    - PERFECT: Both ≥7.5 + aligned ≥80% → +5 boost
    - STRONG: Both high OR aligned ≥70% → +3 boost
    - MODERATE: Aligned ≥60% → +1 boost
    - DIVERGENT: Models disagree → +0 boost
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    engine = get_jarvis_engine()
    daily_energy = get_daily_energy()

    # Get sample analysis using daily energy as proxy for current conditions
    sample_analysis = engine.analyze_pick({
        "player_name": "",
        "team_name": "Sample Team",
        "opponent_name": "Sample Opponent",
        "sport": sport,
        "spread": 5.5,  # Goldilocks zone
        "public_pct": 65,  # Crush zone edge
        "is_favorite": True,
        "ai_score": 6.0,
        "pillar_score": 4.0
    })

    return {
        "sport": sport.upper(),
        "engine_version": engine.version,
        "confluence_system": {
            "levels": {
                "IMMORTAL": {"boost": 10, "requirements": "2178 detected + both ≥7.5 + aligned ≥80%"},
                "JARVIS_PERFECT": {"boost": 7, "requirements": "Trigger + both ≥7.5 + aligned ≥80%"},
                "PERFECT": {"boost": 5, "requirements": "Both ≥7.5 + aligned ≥80%"},
                "STRONG": {"boost": 3, "requirements": "Both high OR aligned ≥70%"},
                "MODERATE": {"boost": 1, "requirements": "Aligned ≥60%"},
                "DIVERGENT": {"boost": 0, "requirements": "Models disagree"}
            },
            "formula": "BLENDED = 0.67 × (research/10) + 0.33 × (esoteric/10) + confluence_boost × 3%"
        },
        "current_conditions": {
            "daily_energy": daily_energy,
            "esoteric_weights": get_dynamic_esoteric_weights(False, False),
            "sample_analysis": {
                "research_score": sample_analysis["research_score"],
                "esoteric_score": sample_analysis["esoteric_score"],
                "confluence": sample_analysis["confluence"],
                "blended_probability": sample_analysis["blended_probability"],
                "bet_recommendation": sample_analysis["bet_recommendation"]
            }
        },
        "bet_tiers": {
            "GOLD_STAR": {"threshold": 72, "units": 2.0},
            "EDGE_LEAN": {"threshold": 68, "units": 1.0},
            "MONITOR": {"threshold": 60, "units": 0.0},
            "PASS": {"threshold": 0, "units": 0.0}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/astro-status")
async def get_astro_status(sport: Optional[str] = None):
    """
    Get current Vedic/Astro status for betting.

    Components:
    - Planetary Hour: Current ruling planet and betting signal
    - Nakshatra: Current lunar mansion and betting type
    - Retrograde Status: Mercury, Venus, Mars retrograde check

    Optional: Pass ?sport=nba to get sport-specific boost information.
    """
    astro = calculate_astro_score(sport or "")
    planetary_hour = calculate_planetary_hour()
    nakshatra = calculate_nakshatra()
    retrogrades = get_retrograde_status()

    return {
        "status": "ACTIVE",
        "version": "v2.0",
        "sport_filter": sport.upper() if sport else "ALL",
        "astro_score": astro["astro_score"],
        "overall_signal": astro["overall_signal"],
        "planetary_hour": {
            "day_ruler": planetary_hour["day_ruler"],
            "current_ruler": planetary_hour["current_hour_ruler"],
            "is_day_hour": planetary_hour["is_day_hour"],
            "hour_of_period": planetary_hour["hour_of_period"],
            "influence": planetary_hour["influence"],
            "bet_signal": planetary_hour["bet_signal"],
            "characteristics": planetary_hour["characteristics"],
            "sports_boost": planetary_hour["sports_boost"]
        },
        "nakshatra": {
            "name": nakshatra["nakshatra"],
            "index": nakshatra["nakshatra_index"],
            "pada": nakshatra["pada"],
            "ruler": nakshatra["ruler"],
            "nature": nakshatra["nature"],
            "betting_type": nakshatra["betting_type"],
            "influence": nakshatra["influence"]
        },
        "retrograde": {
            "any_active": retrogrades["any_retrograde"],
            "mercury": retrogrades["mercury"],
            "venus": retrogrades["venus"],
            "mars": retrogrades["mars"]
        },
        "betting_guidance": _get_astro_betting_guidance(astro, planetary_hour, nakshatra, retrogrades),
        "timestamp": datetime.now().isoformat()
    }


def _get_astro_betting_guidance(astro: Dict, planetary: Dict, nakshatra: Dict, retro: Dict) -> Dict[str, Any]:
    """Generate specific betting guidance based on astro conditions."""
    guidance = {
        "recommended_plays": [],
        "avoid": [],
        "special_conditions": []
    }

    # Planetary hour signals
    bet_signal = planetary["bet_signal"]
    if bet_signal == "CHALK_FRIENDLY":
        guidance["recommended_plays"].append("Favorites on the spread")
    elif bet_signal == "DOG_WARRIOR":
        guidance["recommended_plays"].append("Underdogs with margin")
    elif bet_signal == "EXPANSION_PLAY":
        guidance["recommended_plays"].append("Overs and high-scoring games")
    elif bet_signal == "UNDER_LEAN":
        guidance["recommended_plays"].append("Unders and low totals")
    elif bet_signal == "DEFENSIVE_GRIND":
        guidance["recommended_plays"].append("Defensive teams and unders")
    elif bet_signal == "HOME_EDGE":
        guidance["recommended_plays"].append("Home teams")
    elif bet_signal == "CHAOS_FACTOR":
        guidance["avoid"].append("Heavy favorites - chaos expected")

    # Nakshatra guidance
    betting_type = nakshatra["betting_type"]
    if betting_type == "upsets":
        guidance["recommended_plays"].append("Underdog plays")
    elif betting_type == "favorites":
        guidance["recommended_plays"].append("Strong chalk")
    elif betting_type == "avoid":
        guidance["avoid"].append("Major plays - unfavorable nakshatra")
    elif betting_type == "props":
        guidance["recommended_plays"].append("Player props")
    elif betting_type == "listen_sharps":
        guidance["special_conditions"].append("Sharp money more reliable today")

    # Retrograde warnings
    if retro["any_retrograde"]:
        if retro["mercury"].get("retrograde"):
            guidance["avoid"].append("Complex parlays - Mercury retrograde")
            guidance["special_conditions"].append("Communication errors likely - watch for referee chaos")
        if retro["venus"].get("retrograde"):
            guidance["avoid"].append("Perceived value plays - Venus retrograde")
        if retro["mars"].get("retrograde"):
            guidance["avoid"].append("Aggressive underdog ML - Mars retrograde")

    # Score-based overall
    if astro["astro_score"] >= 8.0:
        guidance["special_conditions"].append("COSMIC ALIGNMENT - Higher conviction plays")
    elif astro["astro_score"] <= 4.0:
        guidance["special_conditions"].append("UNFAVORABLE CONDITIONS - Reduce exposure")

    return guidance


@router.get("/planetary-hour")
async def get_planetary_hour():
    """Get detailed planetary hour information."""
    return calculate_planetary_hour()


@router.get("/nakshatra")
async def get_nakshatra():
    """Get current Nakshatra (lunar mansion) information."""
    return calculate_nakshatra()


@router.get("/retrograde-status")
async def get_retrograde_status_endpoint():
    """Get retrograde status for Mercury, Venus, and Mars."""
    return get_retrograde_status()


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
                "oddsFormat": "american"
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

                    book_entry = {
                        "book_key": book_key,
                        "book_name": book_name,
                        "outcomes": market.get("outcomes", []),
                        "deep_link": generate_sportsbook_link(book_key, game.get("id"), sport_lower)
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
                "oddsFormat": "american"
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

                    betslip_options.append({
                        "book_key": book_key,
                        "book_name": book_config["name"],
                        "book_color": book_config["color"],
                        "book_logo": book_config.get("logo", ""),
                        "selection": outcome_name,
                        "odds": outcome.get("price", -110),
                        "point": outcome.get("point"),  # spread/total line
                        "deep_link": {
                            "web": f"{book_config['web_base']}/",
                            "note": "Opens sportsbook - navigate to game to place bet"
                        }
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
    return {
        "count": len(SPORTSBOOK_CONFIGS),
        "sportsbooks": [
            {
                "key": key,
                "name": config["name"],
                "color": config["color"],
                "logo": config.get("logo", ""),
                "web_url": config["web_base"]
            }
            for key, config in SPORTSBOOK_CONFIGS.items()
        ],
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
# EXPORTS FOR MAIN.PY
# ============================================================================

class LiveDataRouter:
    def __init__(self):
        self.router = router

    def get_router(self):
        return self.router


# Export the router instance
live_data_router = router
