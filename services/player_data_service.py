"""
PlayerDataService - Unified NBA Player Data Service
====================================================
v1.0 - February 2026

Provides player context (season averages, birth dates, player ID) for ALL engines.
Uses BallDontLie API with fallback to static player_birth_data.py.

Integration Points:
- Engine 1 (AI/LSTM): Season averages for normalization baseline
- Engine 2 (Research): Line difficulty assessment vs player average
- Engine 3 (Esoteric): Birth dates for biorhythm/chrome resonance
- MSRF: Player history for significant dates

Features:
- Async-safe methods (no asyncio.run() nesting issues)
- In-memory LRU cache (1hr TTL, 500 player limit)
- Graceful fallback to static data
- Request-scoped telemetry
"""

import os
import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import OrderedDict

logger = logging.getLogger("player_data_service")

# Import BallDontLie functions
try:
    from alt_data_sources.balldontlie import (
        is_balldontlie_configured,
        search_player,
        get_player_season_averages,
        get_player_by_id,
        BDL_ENABLED,
    )
    BDL_AVAILABLE = True
except ImportError:
    BDL_AVAILABLE = False
    BDL_ENABLED = False
    logger.warning("BallDontLie module not available - using static data only")

# Import static fallback data
try:
    from player_birth_data import get_player_data, get_all_players
    STATIC_DATA_AVAILABLE = True
except ImportError:
    STATIC_DATA_AVAILABLE = False
    logger.warning("player_birth_data not available - limited fallback")


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class PlayerContext:
    """
    Player context data for use across all engines.

    Provides season averages, birth date, and player identification.
    """
    player_name: str
    player_id: Optional[int] = None
    birth_date: Optional[str] = None  # YYYY-MM-DD format
    position: Optional[str] = None
    team: Optional[str] = None
    team_abbreviation: Optional[str] = None

    # Season averages (for props line assessment)
    season_pts: Optional[float] = None
    season_reb: Optional[float] = None
    season_ast: Optional[float] = None
    season_stl: Optional[float] = None
    season_blk: Optional[float] = None
    season_fg_pct: Optional[float] = None
    season_fg3_pct: Optional[float] = None
    season_pra: Optional[float] = None  # Points + Rebounds + Assists
    season_pr: Optional[float] = None   # Points + Rebounds
    season_pa: Optional[float] = None   # Points + Assists
    season_threes: Optional[float] = None  # 3-pointers made per game
    games_played: Optional[int] = None

    # Metadata
    data_source: str = "unknown"  # "balldontlie", "static", "fallback"
    cached_at: Optional[str] = None

    @property
    def has_season_data(self) -> bool:
        """Check if season average data is available."""
        return self.season_pts is not None and self.season_pts > 0

    @property
    def has_birth_date(self) -> bool:
        """Check if birth date is available."""
        return self.birth_date is not None and self.birth_date != "1990-01-01"

    def get_stat_average(self, stat_type: str) -> Optional[float]:
        """Get season average for a specific stat type."""
        stat_map = {
            "points": self.season_pts,
            "pts": self.season_pts,
            "rebounds": self.season_reb,
            "reb": self.season_reb,
            "assists": self.season_ast,
            "ast": self.season_ast,
            "steals": self.season_stl,
            "stl": self.season_stl,
            "blocks": self.season_blk,
            "blk": self.season_blk,
            "threes": self.season_threes,
            "three_pointers": self.season_threes,
            "3pm": self.season_threes,
            "pra": self.season_pra,
            "pts_reb_ast": self.season_pra,
            "pr": self.season_pr,
            "pts_reb": self.season_pr,
            "pa": self.season_pa,
            "pts_ast": self.season_pa,
        }
        return stat_map.get(stat_type.lower())

    @classmethod
    def empty(cls, player_name: str = "Unknown") -> "PlayerContext":
        """Return an empty PlayerContext for non-NBA or unavailable players."""
        return cls(
            player_name=player_name,
            data_source="empty",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "player_name": self.player_name,
            "player_id": self.player_id,
            "birth_date": self.birth_date,
            "position": self.position,
            "team": self.team,
            "team_abbreviation": self.team_abbreviation,
            "season_pts": self.season_pts,
            "season_reb": self.season_reb,
            "season_ast": self.season_ast,
            "season_stl": self.season_stl,
            "season_blk": self.season_blk,
            "season_pra": self.season_pra,
            "season_threes": self.season_threes,
            "games_played": self.games_played,
            "has_season_data": self.has_season_data,
            "has_birth_date": self.has_birth_date,
            "data_source": self.data_source,
            "cached_at": self.cached_at,
        }


# =============================================================================
# LRU CACHE IMPLEMENTATION
# =============================================================================

class LRUCache:
    """
    Simple LRU cache with TTL support.

    Features:
    - Max 500 players (configurable)
    - 1 hour TTL (configurable)
    - Thread-safe via OrderedDict
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[PlayerContext, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    def _normalize_key(self, player_name: str) -> str:
        """Normalize player name for consistent cache keys."""
        return player_name.lower().strip()

    async def get(self, player_name: str) -> Optional[PlayerContext]:
        """Get player from cache if not expired."""
        key = self._normalize_key(player_name)

        if key not in self._cache:
            return None

        context, cached_at = self._cache[key]

        # Check TTL
        if time.time() - cached_at > self.ttl_seconds:
            # Expired - remove from cache
            async with self._lock:
                self._cache.pop(key, None)
            return None

        # Move to end (most recently used)
        async with self._lock:
            self._cache.move_to_end(key)

        return context

    async def set(self, player_name: str, context: PlayerContext) -> None:
        """Add player to cache."""
        key = self._normalize_key(player_name)

        async with self._lock:
            # Remove if exists (to update position)
            self._cache.pop(key, None)

            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            # Add with current timestamp
            self._cache[key] = (context, time.time())

    def get_sync(self, player_name: str) -> Optional[PlayerContext]:
        """Synchronous get (for non-async contexts)."""
        key = self._normalize_key(player_name)

        if key not in self._cache:
            return None

        context, cached_at = self._cache[key]

        if time.time() - cached_at > self.ttl_seconds:
            self._cache.pop(key, None)
            return None

        self._cache.move_to_end(key)
        return context

    def set_sync(self, player_name: str, context: PlayerContext) -> None:
        """Synchronous set (for non-async contexts)."""
        key = self._normalize_key(player_name)

        self._cache.pop(key, None)

        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (context, time.time())

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()


# =============================================================================
# PLAYER DATA SERVICE
# =============================================================================

class PlayerDataService:
    """
    Unified player data service for NBA.

    Provides season averages, birth dates, and player context to ALL engines.
    Uses BallDontLie API with fallback to static data.

    Usage:
        # Async context (FastAPI endpoint)
        ctx = await PlayerDataService.get_player_context("LeBron James")

        # Sync context (background job)
        ctx = PlayerDataService.get_player_context_sync("LeBron James")
    """

    _cache = LRUCache(max_size=500, ttl_seconds=3600)
    _telemetry = {
        "bdl_calls": 0,
        "bdl_hits": 0,
        "bdl_errors": 0,
        "cache_hits": 0,
        "static_fallbacks": 0,
        "empty_returns": 0,
    }

    @classmethod
    async def get_player_context(
        cls,
        player_name: str,
        sport: str = "NBA"
    ) -> PlayerContext:
        """
        Get player context for any engine (async version).

        Args:
            player_name: Player's full name
            sport: Sport code (currently only NBA supported)

        Returns:
            PlayerContext with season averages, birth date, etc.
        """
        # Only NBA is supported currently
        if sport.upper() != "NBA":
            cls._telemetry["empty_returns"] += 1
            return PlayerContext.empty(player_name)

        if not player_name or len(player_name.strip()) < 2:
            cls._telemetry["empty_returns"] += 1
            return PlayerContext.empty(player_name or "Unknown")

        # Check cache first
        cached = await cls._cache.get(player_name)
        if cached:
            cls._telemetry["cache_hits"] += 1
            return cached

        # Try BallDontLie API
        if BDL_AVAILABLE and BDL_ENABLED:
            try:
                context = await cls._fetch_from_balldontlie(player_name)
                if context:
                    await cls._cache.set(player_name, context)
                    return context
            except Exception as e:
                logger.warning(f"BallDontLie lookup failed for {player_name}: {e}")
                cls._telemetry["bdl_errors"] += 1

        # Fallback to static data
        context = cls._fallback_to_static(player_name)
        await cls._cache.set(player_name, context)
        return context

    @classmethod
    def get_player_context_sync(
        cls,
        player_name: str,
        sport: str = "NBA"
    ) -> PlayerContext:
        """
        Get player context (sync version for non-async contexts).

        Note: This version only uses cache and static data.
        BallDontLie API calls require async context.
        """
        if sport.upper() != "NBA":
            cls._telemetry["empty_returns"] += 1
            return PlayerContext.empty(player_name)

        if not player_name or len(player_name.strip()) < 2:
            cls._telemetry["empty_returns"] += 1
            return PlayerContext.empty(player_name or "Unknown")

        # Check cache
        cached = cls._cache.get_sync(player_name)
        if cached:
            cls._telemetry["cache_hits"] += 1
            return cached

        # Fallback to static data (no async BDL calls in sync context)
        context = cls._fallback_to_static(player_name)
        cls._cache.set_sync(player_name, context)
        return context

    @classmethod
    async def _fetch_from_balldontlie(cls, player_name: str) -> Optional[PlayerContext]:
        """Fetch player data from BallDontLie API."""
        cls._telemetry["bdl_calls"] += 1

        # Search for player
        player = await search_player(player_name)
        if not player or not player.get("id"):
            logger.debug(f"Player not found in BallDontLie: {player_name}")
            return None

        player_id = player["id"]

        # Get season averages
        season_avg = await get_player_season_averages(player_id)

        cls._telemetry["bdl_hits"] += 1

        # Build context
        return cls._build_context_from_bdl(player, season_avg)

    @classmethod
    def _build_context_from_bdl(
        cls,
        player: Dict[str, Any],
        season_avg: Optional[Dict[str, Any]]
    ) -> PlayerContext:
        """Build PlayerContext from BallDontLie API response."""
        pts = season_avg.get("points", 0.0) if season_avg else 0.0
        reb = season_avg.get("rebounds", 0.0) if season_avg else 0.0
        ast = season_avg.get("assists", 0.0) if season_avg else 0.0

        return PlayerContext(
            player_name=player.get("full_name") or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            player_id=player.get("id"),
            birth_date=player.get("birth_date"),  # BDL provides this
            position=player.get("position"),
            team=player.get("team"),
            team_abbreviation=player.get("team_abbreviation"),
            season_pts=pts,
            season_reb=reb,
            season_ast=ast,
            season_stl=season_avg.get("steals", 0.0) if season_avg else None,
            season_blk=season_avg.get("blocks", 0.0) if season_avg else None,
            season_fg_pct=season_avg.get("fg_pct", 0.0) if season_avg else None,
            season_fg3_pct=season_avg.get("fg3_pct", 0.0) if season_avg else None,
            season_pra=pts + reb + ast if season_avg else None,
            season_pr=pts + reb if season_avg else None,
            season_pa=pts + ast if season_avg else None,
            season_threes=season_avg.get("fg3m", 0.0) if season_avg else None,
            games_played=season_avg.get("games_played") if season_avg else None,
            data_source="balldontlie",
            cached_at=datetime.now().isoformat(),
        )

    @classmethod
    def _fallback_to_static(cls, player_name: str) -> PlayerContext:
        """Fallback to static player_birth_data.py."""
        cls._telemetry["static_fallbacks"] += 1

        if not STATIC_DATA_AVAILABLE:
            return PlayerContext(
                player_name=player_name,
                birth_date="1990-01-01",  # Default fallback
                data_source="fallback",
                cached_at=datetime.now().isoformat(),
            )

        # Look up in static data
        static_data = get_player_data(player_name)

        if static_data:
            return PlayerContext(
                player_name=player_name,
                birth_date=static_data.get("birth_date", "1990-01-01"),
                position=static_data.get("position"),
                team=static_data.get("team"),
                data_source="static",
                cached_at=datetime.now().isoformat(),
            )

        # Not found in static data either
        return PlayerContext(
            player_name=player_name,
            birth_date="1990-01-01",  # Generic fallback
            data_source="fallback",
            cached_at=datetime.now().isoformat(),
        )

    @classmethod
    async def warm_cache_for_players(cls, player_names: List[str]) -> Dict[str, Any]:
        """
        Pre-fetch player data for a list of players.

        Used by daily_scheduler.py to warm cache before picks generation.
        """
        warmed = 0
        errors = 0

        for name in player_names[:50]:  # Limit to 50 players
            try:
                await cls.get_player_context(name, "NBA")
                warmed += 1
            except Exception as e:
                logger.warning(f"Failed to warm cache for {name}: {e}")
                errors += 1

        return {
            "warmed": warmed,
            "errors": errors,
            "cache_size": cls._cache.size(),
        }

    @classmethod
    def get_telemetry(cls) -> Dict[str, Any]:
        """Get service telemetry for debugging."""
        return {
            **cls._telemetry,
            "cache_size": cls._cache.size(),
            "bdl_enabled": BDL_ENABLED,
            "static_data_available": STATIC_DATA_AVAILABLE,
        }

    @classmethod
    def reset_telemetry(cls) -> None:
        """Reset telemetry counters."""
        cls._telemetry = {
            "bdl_calls": 0,
            "bdl_hits": 0,
            "bdl_errors": 0,
            "cache_hits": 0,
            "static_fallbacks": 0,
            "empty_returns": 0,
        }

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the player cache."""
        cls._cache.clear()


# =============================================================================
# LINE DIFFICULTY ASSESSMENT
# =============================================================================

def calculate_line_difficulty(
    prop_line: float,
    season_average: float,
    stat_type: str = "points"
) -> Dict[str, Any]:
    """
    Calculate how difficult a prop line is relative to player's season average.

    Returns:
        {
            "difficulty": float (-1 to +1, negative = soft, positive = hard),
            "difficulty_pct": float (percentage difference from average),
            "assessment": str ("SOFT", "FAIR", "HARD"),
            "adjustment": float (scoring adjustment to apply)
        }
    """
    if season_average <= 0:
        return {
            "difficulty": 0.0,
            "difficulty_pct": 0.0,
            "assessment": "UNKNOWN",
            "adjustment": 0.0,
            "reason": "No season average available"
        }

    # Calculate percentage difference: (line - average) / average
    difficulty_pct = (prop_line - season_average) / season_average

    # Determine assessment and adjustment
    if difficulty_pct < -0.15:
        # Line is 15%+ below average - SOFT (easy to hit over)
        assessment = "SOFT"
        adjustment = 0.3  # Boost for soft lines
    elif difficulty_pct > 0.15:
        # Line is 15%+ above average - HARD (difficult to hit over)
        assessment = "HARD"
        adjustment = -0.2  # Penalty for hard lines
    else:
        assessment = "FAIR"
        adjustment = 0.0

    return {
        "difficulty": round(difficulty_pct, 3),
        "difficulty_pct": round(difficulty_pct * 100, 1),
        "assessment": assessment,
        "adjustment": adjustment,
        "season_average": season_average,
        "prop_line": prop_line,
        "reason": f"Line {prop_line} vs avg {season_average:.1f} ({difficulty_pct*100:+.1f}%)"
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PlayerDataService",
    "PlayerContext",
    "calculate_line_difficulty",
    "LRUCache",
]
