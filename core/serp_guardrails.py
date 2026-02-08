"""
SERP Guardrails - Central Enforcement for SerpAPI Betting Intelligence

Manages:
- Shadow mode (logs signals, applies 0 boost when enabled)
- Daily/monthly quota tracking (166/day, 5000/month)
- Boost caps per engine
- Cache hit/miss tracking
- Status reporting for /debug/integrations

Environment Variables:
- SERP_SHADOW_MODE: bool (default: false) - When true, boosts are zeroed; false = LIVE MODE
- SERP_INTEL_ENABLED: bool (default: true) - Feature flag
- SERP_DAILY_QUOTA: int (default: 166) - Daily API calls (5000/30)
- SERP_MONTHLY_QUOTA: int (default: 5000) - Monthly API calls
- SERP_TIMEOUT: float (default: 2.0) - API timeout seconds
- SERP_CACHE_TTL: int (default: 5400) - Cache TTL in seconds (90 min)
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger("serp_guardrails")

# =============================================================================
# CONFIGURATION
# =============================================================================

def _env_bool(key: str, default: bool = True) -> bool:
    """Parse boolean environment variable."""
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")

def _env_int(key: str, default: int) -> int:
    """Parse integer environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default

def _env_float(key: str, default: float) -> float:
    """Parse float environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default

# Shadow mode - when True, all boosts are zeroed (safe observation mode)
# Default: False (LIVE MODE - boosts are applied to scoring)
SERP_SHADOW_MODE = _env_bool("SERP_SHADOW_MODE", False)

# Feature flag - master enable/disable
SERP_INTEL_ENABLED = _env_bool("SERP_INTEL_ENABLED", True)

# Quota limits
SERP_DAILY_QUOTA = _env_int("SERP_DAILY_QUOTA", 166)  # 5000/30 days
SERP_MONTHLY_QUOTA = _env_int("SERP_MONTHLY_QUOTA", 5000)

# API settings
SERP_TIMEOUT = _env_float("SERP_TIMEOUT", 2.0)  # Strict 2s timeout
SERP_CACHE_TTL = _env_int("SERP_CACHE_TTL", 5400)  # 90 minutes

# v20.9: Props SERP - disabled by default to save quota (~60% of daily calls)
# Props consume ~220 unique per-player queries with near-zero cache hit rate.
# Disabling saves quota for game SERP (high cache hit rate, higher impact signals).
# Set SERP_PROPS_ENABLED=true to re-enable without code changes.
SERP_PROPS_ENABLED = _env_bool("SERP_PROPS_ENABLED", False)

# =============================================================================
# BOOST CAPS (Engine-Specific Limits)
# =============================================================================

# Max boost each engine can receive from SERP signals
SERP_BOOST_CAPS = {
    "ai": 0.8,           # Silent Spike detection
    "research": 1.3,     # Sharp Chatter, RLM, Public sentiment
    "esoteric": 0.6,     # Noosphere, Trends
    "jarvis": 0.7,       # Narratives
    "context": 0.9,      # Situational (B2B, rest, weather)
}

# Total max boost across all engines
SERP_TOTAL_CAP = 4.3

# =============================================================================
# QUOTA TRACKING (In-Memory - Resets on Restart)
# =============================================================================

@dataclass
class QuotaTracker:
    """Tracks API quota usage."""
    daily_used: int = 0
    monthly_used: int = 0
    daily_date: str = ""  # YYYY-MM-DD
    monthly_date: str = ""  # YYYY-MM
    last_reset: Optional[str] = None

    def check_daily(self) -> tuple[bool, int]:
        """Check if daily quota available. Returns (available, remaining)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.daily_date != today:
            self.daily_used = 0
            self.daily_date = today
            self.last_reset = datetime.now(timezone.utc).isoformat()
        remaining = SERP_DAILY_QUOTA - self.daily_used
        return remaining > 0, remaining

    def check_monthly(self) -> tuple[bool, int]:
        """Check if monthly quota available. Returns (available, remaining)."""
        this_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if self.monthly_date != this_month:
            self.monthly_used = 0
            self.monthly_date = this_month
            self.last_reset = datetime.now(timezone.utc).isoformat()
        remaining = SERP_MONTHLY_QUOTA - self.monthly_used
        return remaining > 0, remaining

    def increment(self, count: int = 1):
        """Increment quota counters."""
        self.daily_used += count
        self.monthly_used += count

    def to_dict(self) -> Dict[str, Any]:
        """Export tracker state."""
        daily_ok, daily_rem = self.check_daily()
        monthly_ok, monthly_rem = self.check_monthly()
        return {
            "daily_used": self.daily_used,
            "daily_limit": SERP_DAILY_QUOTA,
            "daily_remaining": daily_rem,
            "daily_available": daily_ok,
            "monthly_used": self.monthly_used,
            "monthly_limit": SERP_MONTHLY_QUOTA,
            "monthly_remaining": monthly_rem,
            "monthly_available": monthly_ok,
            "last_reset": self.last_reset,
        }


# Global quota tracker instance
_quota_tracker = QuotaTracker()

# =============================================================================
# CACHE TRACKING
# =============================================================================

@dataclass
class RateLimitTracker:
    """Tracks rate-limit state to avoid wasting time on 429 errors."""
    is_rate_limited: bool = False
    rate_limited_until: float = 0.0  # Unix timestamp
    consecutive_429s: int = 0
    cooldown_seconds: int = 300  # 5 minute default cooldown

    def record_429(self):
        """Record a 429 error and activate cooldown."""
        self.consecutive_429s += 1
        self.is_rate_limited = True
        # Exponential backoff: 5min, 10min, 20min, max 1 hour
        backoff = min(3600, self.cooldown_seconds * (2 ** min(self.consecutive_429s - 1, 3)))
        self.rate_limited_until = time.time() + backoff
        logger.warning("SERP rate-limited (429). Cooldown for %d seconds.", backoff)

    def record_success(self):
        """Record a successful call - reset rate limit state."""
        if self.is_rate_limited:
            logger.info("SERP rate limit cleared - API responding normally")
        self.is_rate_limited = False
        self.consecutive_429s = 0

    def is_in_cooldown(self) -> tuple[bool, str]:
        """Check if we're in rate-limit cooldown. Returns (in_cooldown, reason)."""
        if not self.is_rate_limited:
            return False, ""
        if time.time() >= self.rate_limited_until:
            # Cooldown expired, allow retry
            return False, ""
        remaining = int(self.rate_limited_until - time.time())
        return True, f"RATE_LIMITED_COOLDOWN_{remaining}s"

    def to_dict(self) -> Dict[str, Any]:
        """Export tracker state."""
        in_cooldown, reason = self.is_in_cooldown()
        return {
            "is_rate_limited": self.is_rate_limited,
            "in_cooldown": in_cooldown,
            "cooldown_reason": reason,
            "consecutive_429s": self.consecutive_429s,
            "cooldown_expires_at": datetime.fromtimestamp(self.rate_limited_until, tz=timezone.utc).isoformat() if self.rate_limited_until > 0 else None,
        }


# Global rate limit tracker
_rate_limit_tracker = RateLimitTracker()


@dataclass
class CacheStats:
    """Tracks cache performance."""
    hits: int = 0
    misses: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    def record_error(self):
        self.errors += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate_pct": round(self.hit_rate, 1),
            "total_requests": self.hits + self.misses,
        }


# Global cache stats instance
_cache_stats = CacheStats()

# =============================================================================
# GUARDRAIL FUNCTIONS
# =============================================================================

def check_quota_available() -> tuple[bool, Dict[str, Any]]:
    """
    Check if SERP API quota is available.

    Returns:
        (available: bool, status: dict with quota details)
    """
    daily_ok, daily_rem = _quota_tracker.check_daily()
    monthly_ok, monthly_rem = _quota_tracker.check_monthly()

    available = daily_ok and monthly_ok
    status = {
        "available": available,
        "daily_remaining": daily_rem,
        "monthly_remaining": monthly_rem,
        "reason": None if available else (
            "Daily quota exceeded" if not daily_ok else "Monthly quota exceeded"
        )
    }

    if not available:
        logger.warning("SERP quota exhausted: %s", status["reason"])

    return available, status


def increment_quota(count: int = 1):
    """Increment quota after successful API call."""
    _quota_tracker.increment(count)
    logger.debug("SERP quota incremented by %d (daily: %d/%d, monthly: %d/%d)",
                 count, _quota_tracker.daily_used, SERP_DAILY_QUOTA,
                 _quota_tracker.monthly_used, SERP_MONTHLY_QUOTA)


# =============================================================================
# RATE LIMIT API
# =============================================================================

def check_rate_limit() -> tuple[bool, str]:
    """
    Check if SERP is rate-limited (429 cooldown).

    Returns:
        (is_available: bool, reason: str if not available)
    """
    in_cooldown, reason = _rate_limit_tracker.is_in_cooldown()
    if in_cooldown:
        return False, reason
    return True, ""


def record_rate_limit_error():
    """Record a 429 rate-limit error. Activates cooldown."""
    _rate_limit_tracker.record_429()


def record_successful_call():
    """Record a successful API call. Clears rate-limit state."""
    _rate_limit_tracker.record_success()


def get_rate_limit_status() -> Dict[str, Any]:
    """Get current rate limit status."""
    return _rate_limit_tracker.to_dict()


def cap_boost(engine: str, value: float) -> float:
    """
    Cap boost value for an engine.

    Args:
        engine: Engine name (ai, research, esoteric, jarvis, context)
        value: Raw boost value

    Returns:
        Capped boost value
    """
    cap = SERP_BOOST_CAPS.get(engine, 0.5)
    capped = min(value, cap)
    if capped < value:
        logger.debug("SERP boost capped: %s %.2f -> %.2f", engine, value, capped)
    return capped


def cap_total_boost(boosts: Dict[str, float]) -> Dict[str, float]:
    """
    Cap total boost across all engines.

    Args:
        boosts: Dict of {engine: boost_value}

    Returns:
        Dict with scaled boosts if total exceeds cap
    """
    # First cap individual engines
    capped = {engine: cap_boost(engine, value) for engine, value in boosts.items()}

    # Check total
    total = sum(capped.values())
    if total > SERP_TOTAL_CAP:
        # Scale down proportionally
        scale = SERP_TOTAL_CAP / total
        capped = {engine: value * scale for engine, value in capped.items()}
        logger.info("SERP total boost scaled: %.2f -> %.2f (factor %.2f)",
                    total, sum(capped.values()), scale)

    return capped


def apply_shadow_mode(boosts: Dict[str, float]) -> Dict[str, float]:
    """
    Apply shadow mode - zero all boosts but preserve metadata for logging.

    Args:
        boosts: Dict of {engine: boost_value}

    Returns:
        Dict with zeroed boosts if shadow mode enabled, otherwise original
    """
    if SERP_SHADOW_MODE:
        # Zero all boosts but log what would have been applied
        original_total = sum(boosts.values())
        if original_total > 0:
            logger.info("SERP SHADOW MODE: Would have applied boosts: %s (total=%.2f)",
                       boosts, original_total)
        return {engine: 0.0 for engine in boosts}
    return boosts


def record_cache_hit():
    """Record a cache hit."""
    _cache_stats.record_hit()


def record_cache_miss():
    """Record a cache miss (API call made)."""
    _cache_stats.record_miss()


def record_cache_error():
    """Record a cache/API error."""
    _cache_stats.record_error()


# =============================================================================
# STATUS REPORTING
# =============================================================================

def get_serp_status() -> Dict[str, Any]:
    """
    Get comprehensive SERP integration status for /debug/integrations.

    Returns:
        Dict with shadow_mode, quota, cache stats, rate_limit, and config
    """
    rate_limit_status = _rate_limit_tracker.to_dict()
    return {
        "enabled": SERP_INTEL_ENABLED,
        "shadow_mode": SERP_SHADOW_MODE,
        "shadow_mode_reason": "Observation mode - signals logged but not applied" if SERP_SHADOW_MODE else "Live mode - boosts active",
        "props_enabled": SERP_PROPS_ENABLED,
        "rate_limited": rate_limit_status.get("in_cooldown", False),
        "rate_limit": rate_limit_status,
        "quota": _quota_tracker.to_dict(),
        "cache": _cache_stats.to_dict(),
        "config": {
            "timeout_s": SERP_TIMEOUT,
            "cache_ttl_s": SERP_CACHE_TTL,
            "boost_caps": SERP_BOOST_CAPS,
            "total_cap": SERP_TOTAL_CAP,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def is_serp_available() -> bool:
    """Check if SERP intelligence is available (enabled, within quota, not rate-limited)."""
    if not SERP_INTEL_ENABLED:
        return False
    # Check rate limit first (faster than quota check)
    rate_ok, _ = check_rate_limit()
    if not rate_ok:
        return False
    available, _ = check_quota_available()
    return available


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "SERP_SHADOW_MODE",
    "SERP_INTEL_ENABLED",
    "SERP_PROPS_ENABLED",
    "SERP_DAILY_QUOTA",
    "SERP_MONTHLY_QUOTA",
    "SERP_TIMEOUT",
    "SERP_CACHE_TTL",
    "SERP_BOOST_CAPS",
    "SERP_TOTAL_CAP",
    # Functions
    "check_quota_available",
    "increment_quota",
    "cap_boost",
    "cap_total_boost",
    "apply_shadow_mode",
    "record_cache_hit",
    "record_cache_miss",
    "record_cache_error",
    "get_serp_status",
    "is_serp_available",
]
