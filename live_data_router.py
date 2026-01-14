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
# JARVIS SAVANT ENGINE v7.3 - FULL INTEGRATION
# Philosophy: Competition + variance. Gematria dominant + exoteric inefficiencies.
# YTD Record: +94.40u (as of January 8, 2026)
# ============================================================================

JARVIS_CONFIG = {
    "version": "v7.3",
    "straight_betting_only": True,

    # Core RS Weights (Boss approved gematria boost)
    "rs_weights": {
        "gematria": 0.52,      # 52% - dominant factor
        "numerology": 0.20,
        "astro": 0.13,
        "vedic": 0.10,
        "sacred": 0.05,
        "fib_phi": 0.05,
        "vortex": 0.05,
    },

    # Public Fade (Exoteric King) - CRUSH THE CHALK
    "public_fade_threshold": 65,  # ≥65% public on chalk = fade
    "public_fade_penalty": -0.13,  # -13% probability adjustment

    # Mid-Spread Priority (Boss zone +4 to +9)
    "mid_spread_range": (4, 9),
    "mid_spread_amplifier": 0.20,  # +20% boost

    # Large Spread Trap Gate (Kings 41-pt, Rice 31-pt lessons)
    "large_spread_threshold": 14,
    "large_spread_penalty": -0.20,  # -20% trap gate

    # NHL ML Dog Protocol v5.9
    "nhl_ml_dog": {
        "enabled": True,
        "rs_threshold": 9.3,
        "public_chalk_threshold": 65,
        "outright_threshold": 35,
        "units": 0.5
    },

    # Betting Tiers
    "gold_star_threshold": 72,    # 2u bet
    "edge_lean_threshold": 68,    # 1u bet
    "ml_dog_lotto_units": 0.5,

    # Blended Probability Formula
    "rs_weight": 0.67,    # 67% Ritual Score
    "quant_weight": 0.33  # 33% Quantitative
}

# Gematria Cipher Values (English Ordinal - most common)
GEMATRIA_ORDINAL = {
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9,
    'j': 10, 'k': 11, 'l': 12, 'm': 13, 'n': 14, 'o': 15, 'p': 16, 'q': 17,
    'r': 18, 's': 19, 't': 20, 'u': 21, 'v': 22, 'w': 23, 'x': 24, 'y': 25, 'z': 26
}

def calculate_gematria(text: str) -> Dict[str, int]:
    """Calculate gematria values for text using multiple ciphers."""
    text = text.lower().replace(" ", "")

    # English Ordinal
    ordinal = sum(GEMATRIA_ORDINAL.get(c, 0) for c in text)

    # Reverse Ordinal
    reverse = sum(27 - GEMATRIA_ORDINAL.get(c, 0) for c in text if c in GEMATRIA_ORDINAL)

    # Reduction (sum digits until single digit)
    reduction = ordinal
    while reduction > 9:
        reduction = sum(int(d) for d in str(reduction))

    return {
        "ordinal": ordinal,
        "reverse": reverse,
        "reduction": reduction,
        "mod9": ordinal % 9 if ordinal % 9 != 0 else 9
    }

def check_gematria_triggers(home_team: str, away_team: str, line: float = None, total: float = None) -> Dict:
    """
    Check gematria triggers for a matchup.
    Returns hits on sacred numbers and total gematria score.
    """
    hits = []
    score = 0.0

    # Calculate gematria for teams
    home_gem = calculate_gematria(home_team)
    away_gem = calculate_gematria(away_team)
    combined = home_gem["ordinal"] + away_gem["ordinal"]

    # Check for sacred number hits
    sacred_numbers = [33, 93, 201, 322, 2178, 666, 777, 888, 111, 222, 333]

    for gem_type, gem_val in [("home_ordinal", home_gem["ordinal"]),
                               ("away_ordinal", away_gem["ordinal"]),
                               ("combined", combined),
                               ("home_reverse", home_gem["reverse"]),
                               ("away_reverse", away_gem["reverse"])]:
        for sacred in sacred_numbers:
            if gem_val == sacred or abs(gem_val - sacred) <= 2:
                hits.append({"type": gem_type, "value": gem_val, "sacred": sacred})
                # Weight by trigger importance
                if sacred in [201, 33, 93]:
                    score += 2.0
                elif sacred in [322, 2178]:
                    score += 3.0
                else:
                    score += 1.0

    # Check line and total for sacred numbers
    if line is not None:
        line_str = str(abs(line)).replace(".", "")
        for sacred in [33, 93, 7, 11, 22]:
            if str(sacred) in line_str:
                hits.append({"type": "line", "value": line, "sacred": sacred})
                score += 1.5

    if total is not None:
        for sacred in [201, 222, 333, 211, 220]:
            if abs(total - sacred) <= 3:
                hits.append({"type": "total", "value": total, "sacred": sacred})
                score += 2.0

    # Date numerology bonus
    today = datetime.now()
    date_sum = sum(int(d) for d in f"{today.year}{today.month:02d}{today.day:02d}")
    if date_sum in sacred_numbers or date_sum % 33 == 0:
        hits.append({"type": "date", "value": date_sum, "sacred": date_sum})
        score += 1.5

    return {
        "hits": hits,
        "hit_count": len(hits),
        "gematria_score": min(10.0, score),  # Cap at 10
        "home_gematria": home_gem,
        "away_gematria": away_gem
    }

def calculate_jarvis_rs(
    gematria_data: Dict,
    public_pct: float = 50,
    line_value: float = None,
    sport: str = "NBA"
) -> Dict:
    """
    Calculate JARVIS Ritual Score (RS) with all fused upgrades.

    RS = Gematria (52%) + Numerology (20%) + Astro (13%) + Vedic (10%) + Sacred (5%)

    Plus:
    - Public Fade: -13% when public ≥65% on chalk
    - Mid-Spread Amplifier: +20% for lines +4 to +9
    - Large Spread Trap: -20% for lines ≥14
    """
    config = JARVIS_CONFIG
    base_rs = 5.0  # Neutral base

    # ===== GEMATRIA COMPONENT (52%) =====
    gematria_score = gematria_data.get("gematria_score", 0)
    gematria_contrib = (gematria_score / 10) * 5.2  # Max 5.2 points from gematria

    # ===== NUMEROLOGY + OTHER COMPONENTS (48%) =====
    # Date numerology
    numerology = calculate_date_numerology()
    numerology_score = 2.0 if numerology.get("is_master_number_day") else 1.0
    if numerology.get("tesla_energy"):
        numerology_score += 0.5

    other_contrib = numerology_score * 0.48  # Max ~2.4 points

    # Calculate base RS
    rs = base_rs + gematria_contrib + other_contrib

    # ===== PUBLIC FADE ADJUSTMENT =====
    public_fade_applied = False
    if public_pct >= config["public_fade_threshold"]:
        # Public is heavy on chalk - FADE IT
        rs_adjustment = config["public_fade_penalty"] * 10  # -1.3 points
        rs += rs_adjustment
        public_fade_applied = True

    # ===== MID-SPREAD AMPLIFIER =====
    mid_spread_boost = False
    if line_value is not None:
        abs_line = abs(line_value)
        min_spread, max_spread = config["mid_spread_range"]
        if min_spread <= abs_line <= max_spread:
            rs *= (1 + config["mid_spread_amplifier"])  # +20%
            mid_spread_boost = True

    # ===== LARGE SPREAD TRAP GATE =====
    large_spread_trap = False
    if line_value is not None:
        if abs(line_value) >= config["large_spread_threshold"]:
            rs *= (1 + config["large_spread_penalty"])  # -20%
            large_spread_trap = True

    # Cap RS at 10
    rs = min(10.0, max(0.0, rs))

    return {
        "rs": round(rs, 2),
        "gematria_contrib": round(gematria_contrib, 2),
        "public_fade_applied": public_fade_applied,
        "public_pct": public_pct,
        "mid_spread_boost": mid_spread_boost,
        "large_spread_trap": large_spread_trap,
        "gematria_hits": gematria_data.get("hit_count", 0)
    }

def get_jarvis_bet_recommendation(blended_prob: float, sport: str, is_dog: bool, rs: float, public_chalk: float) -> Dict:
    """
    Get JARVIS betting recommendation based on blended probability.

    Tiers:
    - Gold Star (2u): blended ≥72%
    - Edge Lean (1u): blended ≥68%
    - ML Dog Lotto (0.5u): NHL dog with RS ≥9.3 and public chalk ≥65%
    """
    config = JARVIS_CONFIG
    recommendation = {"units": 0, "tier": "NO_BET", "reasoning": []}

    # Gold Star
    if blended_prob >= config["gold_star_threshold"]:
        recommendation["units"] = 2.0
        recommendation["tier"] = "GOLD_STAR"
        recommendation["reasoning"].append(f"Blended {blended_prob:.1f}% ≥ 72% threshold")

    # Edge Lean
    elif blended_prob >= config["edge_lean_threshold"]:
        recommendation["units"] = 1.0
        recommendation["tier"] = "EDGE_LEAN"
        recommendation["reasoning"].append(f"Blended {blended_prob:.1f}% ≥ 68% threshold")

    # NHL ML Dog Protocol
    if sport.upper() == "NHL" and is_dog:
        nhl_config = config["nhl_ml_dog"]
        if (rs >= nhl_config["rs_threshold"] and
            public_chalk >= nhl_config["public_chalk_threshold"]):
            recommendation["ml_dog_lotto"] = True
            recommendation["ml_dog_units"] = nhl_config["units"]
            recommendation["reasoning"].append(
                f"NHL ML Dog: RS {rs:.1f} ≥ {nhl_config['rs_threshold']}, "
                f"Public {public_chalk:.0f}% ≥ {nhl_config['public_chalk_threshold']}%"
            )

    return recommendation

# ============================================================================
# CONFLUENCE SYSTEM v10.1 - Alignment between Research & Esoteric
# ============================================================================

CONFLUENCE_LEVELS = {
    "IMMORTAL": {"boost": 10, "color": "#FFD700", "desc": "2178 THE IMMORTAL detected"},
    "JARVIS_PERFECT": {"boost": 7, "color": "#9333EA", "desc": "JARVIS + Perfect alignment"},
    "PERFECT": {"boost": 5, "color": "#10B981", "desc": "Both research & esoteric ≥80%"},
    "STRONG": {"boost": 3, "color": "#3B82F6", "desc": "Both scores ≥70%"},
    "MODERATE": {"boost": 1, "color": "#F59E0B", "desc": "Both scores ≥50%"},
    "DIVERGENT": {"boost": 0, "color": "#6B7280", "desc": "Scores diverge - proceed with caution"}
}

def check_tesla_alignment(value: float) -> Dict[str, Any]:
    """
    Check for Tesla 3-6-9 alignment in a numeric value.
    Tesla believed 3, 6, 9 held the keys to the universe.
    """
    if value is None:
        return {"aligned": False, "pattern": None, "strength": 0}

    val_str = str(abs(float(value))).replace(".", "")
    digits = [int(d) for d in val_str if d.isdigit()]

    # Check digit sum
    digit_sum = sum(digits)
    reduced = digit_sum
    while reduced > 9:
        reduced = sum(int(d) for d in str(reduced))

    # Tesla alignment: reduced to 3, 6, or 9
    if reduced in [3, 6, 9]:
        strength = 3 if reduced == 9 else 2 if reduced == 6 else 1
        return {
            "aligned": True,
            "pattern": f"Reduces to {reduced}",
            "digit_sum": digit_sum,
            "reduced": reduced,
            "strength": strength
        }

    # Also check if value itself contains 369 pattern
    if "369" in val_str or "396" in val_str or "693" in val_str:
        return {
            "aligned": True,
            "pattern": "Contains 369 sequence",
            "digit_sum": digit_sum,
            "reduced": reduced,
            "strength": 2
        }

    return {"aligned": False, "pattern": None, "digit_sum": digit_sum, "reduced": reduced, "strength": 0}


def check_33_divisibility(value: float) -> Dict[str, Any]:
    """
    Check if a value is divisible by 33 or contains 33.
    33 = THE MASTER NUMBER in esoteric numerology.
    """
    if value is None:
        return {"triggered": False, "pattern": None}

    val = abs(float(value))
    val_int = int(val)
    val_str = str(val).replace(".", "")

    # Check divisibility
    if val_int > 0 and val_int % 33 == 0:
        return {
            "triggered": True,
            "pattern": f"{val_int} divisible by 33",
            "type": "divisibility"
        }

    # Check if contains 33
    if "33" in val_str:
        return {
            "triggered": True,
            "pattern": f"{val} contains 33",
            "type": "contains"
        }

    return {"triggered": False, "pattern": None}


def reduce_to_trigger(value: float) -> Dict[str, Any]:
    """
    Check if a value reduces to a sacred trigger number.
    Reduction: sum digits repeatedly until single/double digit.
    """
    if value is None:
        return {"triggered": False, "reduces_to": None}

    val = abs(float(value))
    val_str = str(val).replace(".", "")
    digit_sum = sum(int(d) for d in val_str if d.isdigit())

    # Reduce to single or recognized double digit
    reduced = digit_sum
    reduction_path = [digit_sum]

    while reduced > 99:
        reduced = sum(int(d) for d in str(reduced))
        reduction_path.append(reduced)

    # Check against sacred numbers
    sacred_reductions = {
        33: "THE MASTER",
        93: "THE WILL",
        11: "ILLUMINATION",
        22: "MASTER BUILDER",
        7: "DIVINE",
        9: "COMPLETION"
    }

    for sacred, name in sacred_reductions.items():
        if reduced == sacred or digit_sum == sacred:
            return {
                "triggered": True,
                "reduces_to": sacred,
                "name": name,
                "original": val,
                "path": reduction_path
            }

    # Final single-digit reduction
    final = reduced
    while final > 9:
        final = sum(int(d) for d in str(final))

    if final in [3, 6, 9]:  # Tesla numbers
        return {
            "triggered": True,
            "reduces_to": final,
            "name": f"TESLA_{final}",
            "original": val,
            "path": reduction_path + [final]
        }

    return {"triggered": False, "reduces_to": final, "path": reduction_path}


def check_immortal_2178(home_team: str, away_team: str, line: float = None, total: float = None) -> Dict[str, Any]:
    """
    Check for 2178 THE IMMORTAL trigger - the most powerful sacred number.
    2178 appears in team gematria, lines, totals, or combinations.
    """
    result = {"detected": False, "sources": [], "strength": 0}

    # Calculate gematria
    home_gem = calculate_gematria(home_team or "")
    away_gem = calculate_gematria(away_team or "")
    combined = home_gem["ordinal"] + away_gem["ordinal"]

    # Check for 2178
    checks = [
        ("combined_gematria", combined),
        ("home_gematria", home_gem["ordinal"]),
        ("away_gematria", away_gem["ordinal"]),
    ]

    if line is not None:
        # Check line * some factor
        checks.append(("line_factor", abs(line) * 66))
        checks.append(("line_raw", abs(line)))

    if total is not None:
        checks.append(("total", total))
        checks.append(("total_factor", total * 10))

    for source, val in checks:
        # Direct 2178 or very close
        if abs(val - 2178) < 5:
            result["detected"] = True
            result["sources"].append({"source": source, "value": val, "match": "DIRECT"})
            result["strength"] += 10
        # Contains 2178
        elif "2178" in str(int(val)):
            result["detected"] = True
            result["sources"].append({"source": source, "value": val, "match": "CONTAINS"})
            result["strength"] += 5
        # Digits sum to 18 (2+1+7+8)
        elif sum(int(d) for d in str(int(val))) == 18:
            result["sources"].append({"source": source, "value": val, "match": "SUM_18"})
            result["strength"] += 2

    return result


def calculate_confluence(
    research_score: float,
    esoteric_score: float,
    research_max: float = 16.0,
    esoteric_max: float = 6.0,
    jarvis_triggered: bool = False,
    immortal_detected: bool = False,
    gematria_hits: int = 0,
    tesla_aligned: bool = False
) -> Dict[str, Any]:
    """
    Calculate confluence between Research Model and Esoteric Edge.

    This measures how aligned the quantitative signals are with esoteric patterns.
    High confluence = SMASH territory. Low confluence = proceed with caution.

    Returns:
        level: IMMORTAL, JARVIS_PERFECT, PERFECT, STRONG, MODERATE, DIVERGENT
        boost: Points to add (0-10)
        alignment_pct: How aligned the two scores are
        research_pct: Research score as percentage
        esoteric_pct: Esoteric score as percentage
    """
    # Calculate percentages
    research_pct = (research_score / research_max) * 100 if research_max > 0 else 0
    esoteric_pct = (esoteric_score / esoteric_max) * 100 if esoteric_max > 0 else 0

    # Alignment = how close the two percentages are (inverse of difference)
    diff = abs(research_pct - esoteric_pct)
    alignment_pct = max(0, 100 - diff)

    # Average of both scores (as percentage)
    avg_pct = (research_pct + esoteric_pct) / 2

    # Determine confluence level
    level = "DIVERGENT"
    boost = 0
    reasoning = []

    # IMMORTAL: The highest tier - 2178 detected with strong signals
    if immortal_detected and research_pct >= 75 and esoteric_pct >= 75:
        level = "IMMORTAL"
        boost = CONFLUENCE_LEVELS["IMMORTAL"]["boost"]
        reasoning.append("2178 THE IMMORTAL detected with strong alignment")

    # JARVIS_PERFECT: JARVIS triggered + both scores high
    elif jarvis_triggered and research_pct >= 70 and esoteric_pct >= 70:
        level = "JARVIS_PERFECT"
        boost = CONFLUENCE_LEVELS["JARVIS_PERFECT"]["boost"]
        reasoning.append(f"JARVIS triggered with {alignment_pct:.0f}% alignment")

    # PERFECT: Both scores ≥80% with good alignment
    elif research_pct >= 80 and esoteric_pct >= 80 and alignment_pct >= 70:
        level = "PERFECT"
        boost = CONFLUENCE_LEVELS["PERFECT"]["boost"]
        reasoning.append(f"Perfect confluence: Research {research_pct:.0f}%, Esoteric {esoteric_pct:.0f}%")

    # STRONG: Both scores ≥70%
    elif research_pct >= 70 and esoteric_pct >= 70:
        level = "STRONG"
        boost = CONFLUENCE_LEVELS["STRONG"]["boost"]
        reasoning.append(f"Strong confluence: Research {research_pct:.0f}%, Esoteric {esoteric_pct:.0f}%")

    # MODERATE: Both scores ≥50%
    elif research_pct >= 50 and esoteric_pct >= 50:
        level = "MODERATE"
        boost = CONFLUENCE_LEVELS["MODERATE"]["boost"]
        reasoning.append(f"Moderate confluence: Research {research_pct:.0f}%, Esoteric {esoteric_pct:.0f}%")

    # DIVERGENT: Scores don't align
    else:
        level = "DIVERGENT"
        boost = 0
        if research_pct > esoteric_pct + 20:
            reasoning.append(f"Research strong ({research_pct:.0f}%) but esoteric weak ({esoteric_pct:.0f}%)")
        elif esoteric_pct > research_pct + 20:
            reasoning.append(f"Esoteric strong ({esoteric_pct:.0f}%) but research weak ({research_pct:.0f}%)")
        else:
            reasoning.append(f"Both signals below threshold")

    # Bonus for Tesla alignment
    if tesla_aligned and level != "DIVERGENT":
        boost += 0.5
        reasoning.append("Tesla 3-6-9 aligned (+0.5)")

    # Bonus for multiple gematria hits
    if gematria_hits >= 3 and level != "DIVERGENT":
        boost += 0.5
        reasoning.append(f"{gematria_hits} gematria hits (+0.5)")

    return {
        "level": level,
        "boost": round(boost, 2),
        "color": CONFLUENCE_LEVELS[level]["color"],
        "description": CONFLUENCE_LEVELS[level]["desc"],
        "alignment_pct": round(alignment_pct, 1),
        "research_pct": round(research_pct, 1),
        "esoteric_pct": round(esoteric_pct, 1),
        "avg_strength": round(avg_pct, 1),
        "reasoning": reasoning,
        "jarvis_triggered": jarvis_triggered,
        "immortal_detected": immortal_detected,
        "tesla_aligned": tesla_aligned
    }


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

    # ============================================
    # FETCH ALL DATA SOURCES IN PARALLEL
    # ============================================
    sharp_data, splits_data = await asyncio.gather(
        get_sharp_money(sport),
        get_splits(sport),
        return_exceptions=True
    )

    # Handle any fetch errors gracefully
    if isinstance(sharp_data, Exception):
        logger.warning("Sharp data fetch failed: %s", sharp_data)
        sharp_data = {"data": []}
    if isinstance(splits_data, Exception):
        logger.warning("Splits data fetch failed: %s", splits_data)
        splits_data = {"data": []}

    # Build lookup dictionaries for fast access
    sharp_lookup = {}
    for signal in sharp_data.get("data", []):
        game_key = f"{signal.get('away_team')}@{signal.get('home_team')}"
        sharp_lookup[game_key] = signal

    splits_lookup = {}
    for split in splits_data.get("data", []):
        game_key = f"{split.get('away_team')}@{split.get('home_team')}"
        splits_lookup[game_key] = split

    # Helper function to check JARVIS triggers against numeric values
    def check_jarvis_triggers(line_value=None, total_value=None, prop_line=None, odds_value=None):
        """
        Check JARVIS sacred numbers against actual betting values.

        JARVIS triggers fire when:
        - Line/spread contains trigger (e.g., -3.0 for 33, spread of 3.3)
        - Total is a trigger number (e.g., 201, 220 contains 22)
        - Prop line matches (e.g., 33.5 points)
        - Date numerology aligns
        """
        jarvis_score = 0.0
        triggers_hit = []

        # Collect all numeric values to check
        values_to_check = []
        if line_value is not None:
            values_to_check.append(("line", abs(float(line_value))))
        if total_value is not None:
            values_to_check.append(("total", float(total_value)))
        if prop_line is not None:
            values_to_check.append(("prop", float(prop_line)))
        if odds_value is not None:
            values_to_check.append(("odds", abs(int(odds_value))))

        # Check date numerology
        today = datetime.now()
        date_sum = sum(int(d) for d in f"{today.year}{today.month:02d}{today.day:02d}")
        date_reduced = date_sum
        while date_reduced > 99:
            date_reduced = sum(int(d) for d in str(date_reduced))
        values_to_check.append(("date", date_reduced))
        values_to_check.append(("date_sum", date_sum))

        for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
            triggered = False
            trigger_source = None

            for source, value in values_to_check:
                # Direct match (33 in 33.5, 201 total)
                if trigger_num <= 100:
                    # For small triggers, check if value starts with or contains trigger
                    value_str = str(value).replace(".", "")
                    if str(trigger_num) in value_str:
                        triggered = True
                        trigger_source = source
                        break
                    # Also check if value rounds to trigger
                    if abs(value - trigger_num) < 1:
                        triggered = True
                        trigger_source = source
                        break
                else:
                    # For large triggers (201, 322, 2178), check totals and sums
                    if source in ["total", "date_sum"] and abs(value - trigger_num) < 2:
                        triggered = True
                        trigger_source = source
                        break

            if triggered:
                boost = trigger_data["boost"] / 5  # Max 4 points
                jarvis_score += boost
                triggers_hit.append({
                    "number": trigger_num,
                    "name": trigger_data["name"],
                    "source": trigger_source,
                    "boost": round(boost, 2)
                })

        return min(4.0, jarvis_score), triggers_hit

    # Helper function to calculate esoteric boost
    def calculate_esoteric_boost(line_value=None, prop_line=None):
        """
        Calculate esoteric boost based on daily energy and pick alignment.

        Factors:
        - Daily energy score (base)
        - Power numbers in lines (11, 22, 33, etc.)
        - Tesla numbers (3, 6, 9)
        - Moon phase alignment
        """
        boost = 0.0
        factors = []

        # Base boost from daily energy
        energy_score = daily_energy.get("overall_score", 50)
        if energy_score >= 85:
            boost += 1.5
            factors.append("HIGH_ENERGY_DAY")
        elif energy_score >= 70:
            boost += 1.0
            factors.append("GOOD_ENERGY_DAY")
        elif energy_score >= 55:
            boost += 0.5
            factors.append("NEUTRAL_ENERGY")

        # Check for power numbers in lines
        check_values = []
        if line_value is not None:
            check_values.append(abs(float(line_value)))
        if prop_line is not None:
            check_values.append(float(prop_line))

        for val in check_values:
            val_int = int(val)
            val_decimal = int((val % 1) * 10)

            # Power number check (11, 22, 33, etc.)
            if val_int in POWER_NUMBERS or val_decimal in [1, 2, 3, 4, 5, 6, 7, 8, 9] and val_int % 11 == 0:
                boost += 0.5
                factors.append(f"POWER_NUMBER_{val_int}")
                break

            # Tesla number check (3, 6, 9)
            if val_int % 3 == 0 or val_decimal in [3, 6, 9]:
                boost += 0.3
                factors.append(f"TESLA_ALIGNMENT_{val}")
                break

        # Moon phase bonus
        moon_data = daily_energy.get("moon_summary", {})
        moon_phase = moon_data.get("phase", "")
        if moon_phase == "Full Moon":
            boost += 0.5
            factors.append("FULL_MOON")
        elif moon_phase in ["Waxing Gibbous", "First Quarter"]:
            boost += 0.2
            factors.append("WAXING_MOON")

        return min(2.0, boost), factors

    # ============================================
    # COMPREHENSIVE SCORING FUNCTION
    # Uses: 8 AI Models + 8 Pillars + JARVIS + Esoteric
    # ============================================
    def calculate_comprehensive_score(
        sharp_signal: Dict,
        splits_signal: Dict,
        line_value: float = None,
        total_value: float = None,
        prop_line: float = None,
        odds_value: int = None,
        player_name: str = None,
        home_team: str = None,
        away_team: str = None,
        market_type: str = "spread"  # spread, total, prop, ml
    ) -> Dict:
        """
        MASTER SCORING FUNCTION - Combines ALL signals:

        1. 8 AI Models (via MasterPredictionSystem or signal-based fallback)
        2. 8 Pillars of Execution
        3. JARVIS Triggers (sacred numbers in lines/totals/dates)
        4. Esoteric Edge (daily energy, power numbers, moon phase)

        Returns comprehensive scoring with full breakdown.
        """
        ai_models_detail = {}
        pillars_detail = {}

        # ========================================
        # SECTION 1: 8 AI MODELS (0-8 points)
        # ========================================
        ai_score = 0.0

        if mps and MASTER_PREDICTION_AVAILABLE:
            # Build game_data for MasterPredictionSystem
            try:
                game_data = {
                    'features': np.array([
                        sharp_signal.get("line_variance", 0),
                        splits_signal.get("spread_splits", {}).get("home", {}).get("money_pct", 50) / 100,
                        odds_value / 100 if odds_value else -1.1,
                        line_value or prop_line or 0,
                    ]),
                    'recent_games': [],  # Would need historical data
                    'line': line_value or prop_line or 0,
                    'player_stats': {
                        'expected_value': prop_line or line_value or 0,
                        'std_dev': 6.5
                    },
                    'current_line': line_value or prop_line or 0,
                    'opening_line': (line_value or prop_line or 0) * 0.95,  # Estimate
                    'betting_odds': odds_value or -110,
                    'betting_percentages': splits_signal.get("spread_splits", {}),
                    'schedule': {'days_rest': 2, 'travel_miles': 0, 'games_in_last_7': 3},
                    'injuries': [],
                    'depth_chart': {}
                }

                # Call MasterPredictionSystem
                mps_result = mps.generate_comprehensive_prediction(game_data)

                # Extract AI score (0-10 from MPS, scale to 0-8)
                raw_ai = mps_result.get('ai_score', 5.0)
                ai_score = min(8.0, raw_ai * 0.8)

                # Extract individual model factors
                ai_models_detail = {
                    "ensemble": mps_result.get('factors', {}).get('ensemble', 0),
                    "lstm": mps_result.get('factors', {}).get('lstm', 0),
                    "matchup": mps_result.get('factors', {}).get('matchup', 0),
                    "monte_carlo": mps_result.get('factors', {}).get('monte_carlo', 0),
                    "line_movement": mps_result.get('factors', {}).get('line_movement', 0),
                    "rest_factor": mps_result.get('factors', {}).get('rest_factor', 1.0),
                    "injury_impact": mps_result.get('factors', {}).get('injury_impact', 0),
                    "edge_calc": mps_result.get('factors', {}).get('edge', 0)
                }

                # Extract pillar scores
                pillars_detail = mps_result.get('pillars', {}).get('scores', {})

            except Exception as e:
                logger.warning("MasterPredictionSystem failed, using signal-based fallback: %s", e)
                mps_result = None
        else:
            mps_result = None

        # Signal-based AI scoring (fallback or enhancement)
        if not mps_result or ai_score < 4.0:
            signal_ai = 4.0  # Base score

            # Model 1: Sharp Money Signal (Line Movement proxy)
            if sharp_signal.get("signal_strength") == "STRONG":
                signal_ai += 1.5
                ai_models_detail["sharp_signal"] = "STRONG (+1.5)"
            elif sharp_signal.get("signal_strength") == "MODERATE":
                signal_ai += 0.75
                ai_models_detail["sharp_signal"] = "MODERATE (+0.75)"

            # Model 2: Line Variance (indicates sharp action)
            line_var = sharp_signal.get("line_variance", 0)
            if line_var >= 2.0:
                signal_ai += 1.0
                ai_models_detail["line_variance"] = f"{line_var} (LARGE +1.0)"
            elif line_var >= 1.0:
                signal_ai += 0.5
                ai_models_detail["line_variance"] = f"{line_var} (MODERATE +0.5)"

            # Model 3: Betting Splits (Sharp vs Public)
            home_money = splits_signal.get("spread_splits", {}).get("home", {}).get("money_pct", 50)
            home_bets = splits_signal.get("spread_splits", {}).get("home", {}).get("bets_pct", 50)

            # Reverse line movement: Money disagrees with bets = sharp action
            if abs(home_money - home_bets) >= 15:
                signal_ai += 1.0
                ai_models_detail["reverse_line"] = f"Money {home_money}% vs Bets {home_bets}% (+1.0)"
            elif abs(home_money - home_bets) >= 8:
                signal_ai += 0.5
                ai_models_detail["reverse_line"] = f"Money {home_money}% vs Bets {home_bets}% (+0.5)"

            # Use higher of MPS or signal-based
            ai_score = max(ai_score, min(8.0, signal_ai))

        # ========================================
        # SECTION 2: 8 PILLARS (0-8 points)
        # ========================================
        pillar_score = 0.0
        pillars_triggered = []

        # Pillar 1: Sharp Split (money vs bets divergence)
        home_money = splits_signal.get("spread_splits", {}).get("home", {}).get("money_pct", 50)
        home_bets = splits_signal.get("spread_splits", {}).get("home", {}).get("bets_pct", 50)
        split_diff = abs(home_money - home_bets)
        if split_diff >= 20:
            pillar_score += 1.0
            pillars_triggered.append({"pillar": "SHARP_SPLIT", "value": split_diff, "points": 1.0})
        elif split_diff >= 10:
            pillar_score += 0.5
            pillars_triggered.append({"pillar": "SHARP_SPLIT", "value": split_diff, "points": 0.5})

        # Pillar 2: Reverse Line Movement
        line_var = sharp_signal.get("line_variance", 0)
        if line_var >= 2.0:
            pillar_score += 1.0
            pillars_triggered.append({"pillar": "REVERSE_LINE", "value": line_var, "points": 1.0})
        elif line_var >= 1.5:
            pillar_score += 0.5
            pillars_triggered.append({"pillar": "REVERSE_LINE", "value": line_var, "points": 0.5})

        # Pillar 3: Hook Discipline (key numbers in spreads)
        if line_value is not None:
            abs_line = abs(line_value)
            key_numbers = [3, 7, 10, 14]  # Football key numbers
            if sport_lower in ["nba", "ncaab"]:
                key_numbers = [1, 2, 3, 4, 5, 6, 7]  # Basketball key numbers

            if any(abs(abs_line - kn) < 0.5 for kn in key_numbers):
                pillar_score += 1.0
                pillars_triggered.append({"pillar": "HOOK_DISCIPLINE", "value": line_value, "points": 1.0})

        # Pillar 4: Volume Discipline (confidence-based sizing)
        # Higher AI score = higher volume discipline
        if ai_score >= 7.0:
            pillar_score += 1.0
            pillars_triggered.append({"pillar": "VOLUME_DISCIPLINE", "value": "HIGH_CONFIDENCE", "points": 1.0})
        elif ai_score >= 5.5:
            pillar_score += 0.5
            pillars_triggered.append({"pillar": "VOLUME_DISCIPLINE", "value": "MODERATE_CONFIDENCE", "points": 0.5})

        # Pillar 5: Situational Spot (rest advantage, travel, etc.)
        # Would need more data, using day of week as proxy
        dow = datetime.now().weekday()
        if dow in [4, 5, 6]:  # Fri-Sun = prime time
            pillar_score += 0.5
            pillars_triggered.append({"pillar": "SITUATIONAL_SPOT", "value": "PRIME_TIME", "points": 0.5})

        # Pillar 6: Expert Consensus (sharp signal strength)
        if sharp_signal.get("signal_strength") == "STRONG":
            pillar_score += 1.0
            pillars_triggered.append({"pillar": "EXPERT_CONSENSUS", "value": "STRONG", "points": 1.0})
        elif sharp_signal.get("signal_strength") == "MODERATE":
            pillar_score += 0.5
            pillars_triggered.append({"pillar": "EXPERT_CONSENSUS", "value": "MODERATE", "points": 0.5})

        # Pillar 7: Prop Correlation (for props only)
        if market_type == "prop" and prop_line:
            # Props that correlate with team performance
            if prop_line >= 25:  # High-usage player
                pillar_score += 0.5
                pillars_triggered.append({"pillar": "PROP_CORRELATION", "value": prop_line, "points": 0.5})

        # Pillar 8: Hospital Fade (injury-based opportunities)
        # Would need injury data, placeholder for now

        pillar_score = min(8.0, pillar_score)
        pillars_detail["triggered"] = pillars_triggered
        pillars_detail["total"] = round(pillar_score, 2)

        # ========================================
        # SECTION 3: JARVIS SAVANT ENGINE (0-4 points)
        # Full gematria + public fade + mid-spread amplifier
        # ========================================

        # Get public betting percentage
        public_pct = splits_signal.get("spread_splits", {}).get("home", {}).get("bets_pct", 50)

        # Run full gematria analysis on team names
        gematria_data = check_gematria_triggers(
            home_team=home_team or "",
            away_team=away_team or "",
            line=line_value or prop_line,
            total=total_value
        )

        # Calculate JARVIS Ritual Score with all fused upgrades
        jarvis_rs_data = calculate_jarvis_rs(
            gematria_data=gematria_data,
            public_pct=public_pct,
            line_value=line_value or prop_line,
            sport=sport_lower
        )

        # Scale RS (0-10) to JARVIS points (0-4)
        jarvis_score = (jarvis_rs_data["rs"] / 10) * 4.0

        # Also run basic numeric triggers
        basic_jarvis_score, jarvis_triggers_hit = check_jarvis_triggers(
            line_value=line_value,
            total_value=total_value,
            prop_line=prop_line,
            odds_value=odds_value
        )

        # Combine: take higher of RS-based or numeric triggers
        if basic_jarvis_score > jarvis_score:
            jarvis_score = basic_jarvis_score

        jarvis_detail = {
            "rs": jarvis_rs_data["rs"],
            "gematria_hits": gematria_data.get("hit_count", 0),
            "gematria_score": gematria_data.get("gematria_score", 0),
            "public_fade_applied": jarvis_rs_data.get("public_fade_applied", False),
            "mid_spread_boost": jarvis_rs_data.get("mid_spread_boost", False),
            "large_spread_trap": jarvis_rs_data.get("large_spread_trap", False),
            "numeric_triggers": jarvis_triggers_hit
        }

        # ========================================
        # SECTION 4: ESOTERIC EDGE (0-2 points)
        # ========================================
        esoteric_boost, esoteric_factors = calculate_esoteric_boost(
            line_value=line_value,
            prop_line=prop_line
        )

        # ========================================
        # SECTION 5: CONFLUENCE SYSTEM v10.1
        # Measures alignment between Research & Esoteric
        # ========================================

        # Check for Tesla 3-6-9 alignment
        check_val = line_value or prop_line or total_value
        tesla_data = check_tesla_alignment(check_val)

        # Check for 33 divisibility
        master_33_data = check_33_divisibility(check_val)
        if master_33_data["triggered"]:
            esoteric_factors.append(f"MASTER_33: {master_33_data['pattern']}")

        # Check for 2178 THE IMMORTAL
        immortal_data = check_immortal_2178(
            home_team=home_team or "",
            away_team=away_team or "",
            line=line_value or prop_line,
            total=total_value
        )

        # Determine if JARVIS was triggered (any triggers hit)
        jarvis_was_triggered = len(jarvis_triggers_hit) > 0 or gematria_data.get("hit_count", 0) >= 2

        # Calculate Research Score (AI + Pillars)
        research_score = ai_score + pillar_score  # Max 16

        # Calculate Esoteric Score (JARVIS + Esoteric boost)
        esoteric_total = jarvis_score + esoteric_boost  # Max 6

        # Calculate confluence
        confluence_data = calculate_confluence(
            research_score=research_score,
            esoteric_score=esoteric_total,
            research_max=16.0,
            esoteric_max=6.0,
            jarvis_triggered=jarvis_was_triggered,
            immortal_detected=immortal_data["detected"],
            gematria_hits=gematria_data.get("hit_count", 0),
            tesla_aligned=tesla_data["aligned"]
        )

        # ========================================
        # FINAL SCORE CALCULATION
        # ========================================
        # Base: 8 + 8 + 4 + 2 = 22 points
        # Plus confluence boost (0-10)
        # Max possible with IMMORTAL: 32 points
        base_score = ai_score + pillar_score + jarvis_score + esoteric_boost
        confluence_boost = confluence_data["boost"]
        total_score = base_score + confluence_boost

        # ========================================
        # BLENDED PROBABILITY (JARVIS Formula)
        # 67% Ritual Score + 33% Quantitative
        # ========================================
        quant_prob = min(100, (ai_score / 8) * 50 + (pillar_score / 8) * 30 + 20)
        blended_prob = (JARVIS_CONFIG["rs_weight"] * (jarvis_rs_data["rs"] * 10)) + \
                       (JARVIS_CONFIG["quant_weight"] * quant_prob)

        # Boost blended probability based on confluence level
        if confluence_data["level"] == "IMMORTAL":
            blended_prob += 15
        elif confluence_data["level"] == "JARVIS_PERFECT":
            blended_prob += 10
        elif confluence_data["level"] == "PERFECT":
            blended_prob += 7
        elif confluence_data["level"] == "STRONG":
            blended_prob += 4

        blended_prob = min(100, max(0, blended_prob))

        # ========================================
        # BET RECOMMENDATION (Gold Star, Edge Lean, NHL Dog)
        # ========================================
        is_dog = (line_value and line_value > 0) or (odds_value and odds_value > 100)
        bet_rec = get_jarvis_bet_recommendation(
            blended_prob=blended_prob,
            sport=sport_lower,
            is_dog=is_dog,
            rs=jarvis_rs_data["rs"],
            public_chalk=public_pct
        )

        # Add confluence tier to recommendation
        bet_rec["confluence_tier"] = confluence_data["level"]
        if confluence_data["level"] == "IMMORTAL":
            bet_rec["tier"] = "IMMORTAL_LOCK"
            bet_rec["units"] = max(bet_rec.get("units", 0), 3.0)
            bet_rec["reasoning"].append("IMMORTAL confluence - maximum confidence")

        # Confidence tiers based on total score (with confluence)
        if confluence_data["level"] == "IMMORTAL" or total_score >= 25:
            confidence = "IMMORTAL"
            confidence_pct = min(98, 90 + (total_score - 25) * 2)
        elif total_score >= 20:
            confidence = "SMASH"
            confidence_pct = min(95, 82 + (total_score - 20) * 2.5)
        elif total_score >= 16:
            confidence = "HIGH"
            confidence_pct = min(85, 72 + (total_score - 16) * 3)
        elif total_score >= 12:
            confidence = "MEDIUM"
            confidence_pct = min(72, 58 + (total_score - 12) * 3.5)
        else:
            confidence = "LOW"
            confidence_pct = max(35, 40 + total_score * 1.5)

        return {
            "total_score": round(total_score, 2),
            "base_score": round(base_score, 2),
            "confidence": confidence,
            "confidence_pct": round(confidence_pct),
            "blended_probability": round(blended_prob, 1),
            "scoring_breakdown": {
                "ai_models": round(ai_score, 2),
                "pillars": round(pillar_score, 2),
                "jarvis": round(jarvis_score, 2),
                "esoteric": round(esoteric_boost, 2),
                "confluence_boost": round(confluence_boost, 2)
            },
            "dual_scores": {
                "research": round(research_score, 2),
                "research_max": 16.0,
                "esoteric": round(esoteric_total, 2),
                "esoteric_max": 6.0
            },
            "confluence": confluence_data,
            "ai_models_detail": ai_models_detail,
            "pillars_detail": pillars_detail,
            "jarvis_detail": jarvis_detail,
            "jarvis_triggers": jarvis_triggers_hit,
            "esoteric_factors": esoteric_factors,
            "tesla_alignment": tesla_data,
            "immortal_2178": immortal_data,
            "bet_recommendation": bet_rec,
            "max_possible": 32.0  # With IMMORTAL confluence
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
            sharp_signal = sharp_lookup.get(game_key, {})

            splits_signal = splits_lookup.get(game_key, {})

            for prop in game.get("props", []):
                player = prop.get("player", "Unknown")
                market = prop.get("market", "")
                line = prop.get("line", 0)
                odds = prop.get("odds", -110)
                side = prop.get("side", "Over")

                if side not in ["Over", "Under"]:
                    continue

                # COMPREHENSIVE SCORING: AI + Pillars + JARVIS + Esoteric
                score_data = calculate_comprehensive_score(
                    sharp_signal=sharp_signal,
                    splits_signal=splits_signal,
                    prop_line=line,
                    odds_value=odds,
                    player_name=player,
                    home_team=home_team,
                    away_team=away_team,
                    market_type="prop"
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
                    **score_data
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
                sharp_signal = sharp_lookup.get(game_key, {})
                splits_signal = splits_lookup.get(game_key, {})

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
                                mkt_type = "spread"
                            elif market_key == "h2h":
                                pick_type = "MONEYLINE"
                                display = f"{pick_name} ML"
                                mkt_type = "ml"
                            elif market_key == "totals":
                                pick_type = "TOTAL"
                                display = f"{pick_name} {point}" if point else pick_name
                                mkt_type = "total"
                            else:
                                continue

                            # COMPREHENSIVE SCORING: AI + Pillars + JARVIS + Esoteric
                            score_data = calculate_comprehensive_score(
                                sharp_signal=sharp_signal,
                                splits_signal=splits_signal,
                                line_value=point if market_key == "spreads" else None,
                                total_value=point if market_key == "totals" else None,
                                odds_value=odds,
                                home_team=home_team,
                                away_team=away_team,
                                market_type=mkt_type
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
                                **score_data
                            })
    except Exception as e:
        logger.warning("Game odds fetch failed: %s", e)

    # Fallback to sharp money if no game picks
    if not game_picks and sharp_data.get("data"):
        for signal in sharp_data.get("data", []):
            home_team = signal.get("home_team", "")
            away_team = signal.get("away_team", "")
            game_key = f"{away_team}@{home_team}"
            line_variance = signal.get("line_variance", 0)
            splits_signal = splits_lookup.get(game_key, {})

            # COMPREHENSIVE SCORING for sharp money signals
            score_data = calculate_comprehensive_score(
                sharp_signal=signal,
                splits_signal=splits_signal,
                line_value=line_variance,
                home_team=home_team,
                away_team=away_team,
                market_type="spread"
            )

            game_picks.append({
                "pick_type": "SHARP",
                "pick": f"Sharp on {signal.get('side', 'HOME')}",
                "team": home_team if signal.get("side") == "HOME" else away_team,
                "line": line_variance,
                "odds": -110,
                "game": f"{away_team} @ {home_team}",
                "home_team": home_team,
                "away_team": away_team,
                "market": "sharp_money",
                "recommendation": f"SHARP ON {signal.get('side', 'HOME').upper()}",
                **score_data
            })

    # Sort game picks by score and take top 10
    game_picks.sort(key=lambda x: x["total_score"], reverse=True)
    top_game_picks = game_picks[:10]

    # ============================================
    # BUILD FINAL RESPONSE
    # ============================================
    result = {
        "sport": sport.upper(),
        "source": "master_prediction_system",
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
