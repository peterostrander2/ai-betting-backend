"""
NOAA Space Weather Client - Real-time Kp-Index Data

GLITCH Protocol integration for geomagnetic activity signals.
Fetches real Kp-Index from NOAA Space Weather Prediction Center.

API: https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
Cost: FREE (public API, no key needed)
Rate limit: None specified, but cache for 3 hours (Kp updates every 3h)

Semantic Audit (v20.18):
- Request-scoped proof via contextvars (not contaminated by concurrent requests)
- auth_type: "none" (public API, no key required)
- Call proof derived from request-local counters
"""

import os
import time
import logging
import contextvars
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Import httpx at module level to avoid NameError in except clauses
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

logger = logging.getLogger("noaa")


# =============================================================================
# REQUEST-SCOPED PROOF (v20.18 - Semantic Audit)
# =============================================================================

@dataclass
class NOAARequestProof:
    """
    Request-local NOAA call proof - NOT contaminated by other requests.

    Used to prove that NOAA API calls actually happened on THIS request,
    not on some other concurrent request. This is critical for semantic
    truthfulness verification.
    """
    calls: int = 0
    http_2xx: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    timeouts: int = 0
    cache_hits: int = 0
    errors: int = 0

    def record_call(
        self,
        status_code: int = 0,
        cache_hit: bool = False,
        timeout: bool = False,
        error: bool = False
    ) -> None:
        """Record a NOAA call to request-local proof."""
        self.calls += 1
        if cache_hit:
            self.cache_hits += 1
        elif timeout:
            self.timeouts += 1
        elif error:
            self.errors += 1
        elif 200 <= status_code < 300:
            self.http_2xx += 1
        elif 400 <= status_code < 500:
            self.http_4xx += 1
        elif 500 <= status_code < 600:
            self.http_5xx += 1

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for JSON serialization."""
        return {
            "noaa_calls": self.calls,
            "noaa_2xx": self.http_2xx,
            "noaa_4xx": self.http_4xx,
            "noaa_5xx": self.http_5xx,
            "noaa_timeouts": self.timeouts,
            "noaa_cache_hits": self.cache_hits,
            "noaa_errors": self.errors,
        }


# Request-local proof via ContextVar (not contaminated by concurrent requests)
_noaa_request_proof: contextvars.ContextVar[Optional[NOAARequestProof]] = \
    contextvars.ContextVar("noaa_request_proof", default=None)


def init_noaa_request_proof() -> NOAARequestProof:
    """
    Initialize request-local proof. Call at start of debug endpoint.

    Returns the proof object so it can be read after scoring completes.
    """
    proof = NOAARequestProof()
    _noaa_request_proof.set(proof)
    return proof


def get_noaa_request_proof() -> Optional[NOAARequestProof]:
    """
    Get current request's proof (None if not initialized).

    Returns None if called outside of a request context where
    init_noaa_request_proof() was called.
    """
    return _noaa_request_proof.get()


def _record_noaa_call(
    status_code: int = 0,
    cache_hit: bool = False,
    timeout: bool = False,
    error: bool = False
) -> None:
    """
    Record call to request-local proof (if active).

    This is called internally by fetch functions to record
    whether a call was made, and what the outcome was.
    """
    proof = _noaa_request_proof.get()
    if proof:
        proof.record_call(
            status_code=status_code,
            cache_hit=cache_hit,
            timeout=timeout,
            error=error
        )


def get_noaa_auth_context() -> Dict[str, Any]:
    """
    Get NOAA auth context for semantic audit.

    NOAA is a FREE public API with NO API key required.
    This returns auth_type: "none" (not key_present).
    """
    base_url = os.getenv("NOAA_BASE_URL")
    return {
        "auth_type": "none",  # Public API, no key required
        "enabled": NOAA_ENABLED,
        "base_url_source": "env:NOAA_BASE_URL" if base_url else "default",
    }

# Feature flag
NOAA_ENABLED = os.getenv("NOAA_ENABLED", "true").lower() == "true"

# Cache settings (Kp-Index updates every 3 hours)
_kp_cache: Dict[str, Any] = {}
_kp_cache_time: float = 0
KP_CACHE_TTL = 3 * 60 * 60  # 3 hours in seconds

# NOAA API endpoint
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

def _mark_noaa_used() -> None:
    try:
        from integration_registry import mark_integration_used
        mark_integration_used("noaa_space_weather")
    except Exception as e:
        logger.debug("noaa mark_integration_used failed: %s", str(e))


def fetch_kp_index_live() -> Dict[str, Any]:
    """
    Fetch real-time Kp-Index from NOAA Space Weather API.

    Returns latest Kp value and storm level assessment.
    Caches for 3 hours since Kp-Index updates every 3 hours.

    Returns:
        Dict with kp_value, storm_level, timestamp, source
    """
    global _kp_cache, _kp_cache_time

    if not NOAA_ENABLED:
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "disabled",
            "reason": "NOAA_DISABLED"
        }

    # Check cache
    now = time.time()
    if _kp_cache and (now - _kp_cache_time) < KP_CACHE_TTL:
        _mark_noaa_used()
        _record_noaa_call(cache_hit=True)  # v20.18: Record cache hit
        return {**_kp_cache, "source": "cache", "from_cache": True}

    if not HTTPX_AVAILABLE:
        _record_noaa_call(error=True)
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "fallback",
            "error": "httpx not installed",
            "from_cache": False,
            "from_live": False,
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(NOAA_KP_URL)
            _record_noaa_call(status_code=response.status_code)  # v20.18: Record HTTP call
            response.raise_for_status()
            data = response.json()

        # NOAA returns array of arrays:
        # [["time_tag", "Kp", "Kp_fraction", "a_running", "station_count"], ...]
        # First row is header, last row is most recent
        if not data or len(data) < 2:
            raise ValueError("Invalid NOAA response format")

        # Get most recent reading (last row)
        latest = data[-1]
        # Kp value is in index 1
        kp_value = float(latest[1])
        timestamp = latest[0]

        # Determine storm level
        if kp_value >= 8:
            storm_level = "EXTREME"
        elif kp_value >= 7:
            storm_level = "SEVERE"
        elif kp_value >= 6:
            storm_level = "STRONG"
        elif kp_value >= 5:
            storm_level = "MODERATE"
        elif kp_value >= 4:
            storm_level = "MINOR"
        elif kp_value >= 3:
            storm_level = "UNSETTLED"
        else:
            storm_level = "QUIET"

        result = {
            "kp_value": round(kp_value, 1),
            "storm_level": storm_level,
            "timestamp": timestamp,
            "source": "noaa_live",
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "from_cache": False,
            "from_live": True,
        }

        # Update cache
        _kp_cache = result
        _kp_cache_time = now

        _mark_noaa_used()
        logger.info("NOAA Kp-Index fetched: %.1f (%s)", kp_value, storm_level)
        return result

    except httpx.TimeoutException as e:
        _record_noaa_call(timeout=True)  # v20.18: Record timeout
        logger.warning("NOAA API timeout, using fallback: %s", e)
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "fallback",
            "error": str(e),
            "from_cache": False,
            "from_live": False,
        }
    except Exception as e:
        _record_noaa_call(error=True)  # v20.18: Record error
        logger.warning("NOAA API error, using fallback: %s", e)
        # Return fallback (average quiet conditions)
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "fallback",
            "error": str(e),
            "from_cache": False,
            "from_live": False,
        }


def get_kp_betting_signal(game_time: datetime = None) -> Dict[str, Any]:
    """
    Get Kp-Index with betting signal interpretation.

    Geomagnetic storms may affect human behavior and decision-making.
    - Quiet (Kp 0-2): Stable conditions, normal analysis
    - Unsettled (Kp 3-4): Slight volatility increase
    - Storm (Kp 5+): Increased emotional betting, potential value in contrarian plays

    Args:
        game_time: Game start time (for logging)

    Returns:
        Dict with score (0-1), reason, triggered, kp_value, storm_level, recommendation
    """
    kp_data = fetch_kp_index_live()
    kp_value = kp_data.get("kp_value", 3.0)
    storm_level = kp_data.get("storm_level", "QUIET")

    # Score interpretation for betting
    # Quiet conditions = stable = good for analysis (high score)
    # Storm conditions = volatile = reduce confidence (lower score)
    if kp_value <= 2:
        score = 0.8
        reason = f"KP_QUIET_{kp_value}"
        triggered = True
        recommendation = "Optimal conditions for analytical betting"
    elif kp_value <= 3:
        score = 0.7
        reason = f"KP_CALM_{kp_value}"
        triggered = False
        recommendation = "Normal conditions"
    elif kp_value <= 4:
        score = 0.5
        reason = f"KP_UNSETTLED_{kp_value}"
        triggered = False
        recommendation = "Slightly elevated volatility"
    elif kp_value <= 5:
        score = 0.4
        reason = f"KP_ACTIVE_{kp_value}"
        triggered = True
        recommendation = "Consider reducing position sizes"
    else:
        score = 0.3
        reason = f"KP_STORM_{kp_value}"
        triggered = True
        recommendation = "Geomagnetic storm - public may bet emotionally, contrarian value possible"

    return {
        "score": score,
        "reason": reason,
        "triggered": triggered,
        "kp_value": kp_value,
        "storm_level": storm_level,
        "recommendation": recommendation,
        "source": kp_data.get("source", "unknown"),
        "timestamp": kp_data.get("timestamp")
    }


def get_space_weather_summary() -> Dict[str, Any]:
    """
    Get comprehensive space weather summary for daily esoteric reading.

    Returns:
        Dict with kp_index, storm_activity, betting_outlook
    """
    kp_signal = get_kp_betting_signal()

    # Determine overall outlook
    if kp_signal["score"] >= 0.7:
        outlook = "FAVORABLE"
        outlook_reason = "Quiet geomagnetic conditions support clear analysis"
    elif kp_signal["score"] >= 0.5:
        outlook = "NEUTRAL"
        outlook_reason = "Normal space weather conditions"
    else:
        outlook = "CAUTION"
        outlook_reason = f"Elevated geomagnetic activity (Kp={kp_signal['kp_value']})"

    return {
        "kp_index": kp_signal,
        "betting_outlook": outlook,
        "outlook_reason": outlook_reason,
        "recommendations": [kp_signal["recommendation"]]
    }


# =============================================================================
# SOLAR X-RAY FLUX (v18.2) - Solar Flare Detection
# =============================================================================

# NOAA X-ray Flux API (GOES satellite data)
NOAA_XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"

# Cache for X-ray flux (updates every minute, cache for 1 hour)
_xray_cache: Dict[str, Any] = {}
_xray_cache_time: float = 0
XRAY_CACHE_TTL = 60 * 60  # 1 hour


def get_solar_xray_flux() -> Dict[str, Any]:
    """
    Fetch real-time solar X-ray flux from NOAA GOES satellite (v18.2).

    X-ray flux indicates solar flare activity:
    - X-class: flux >= 1e-4 W/m² (major flare)
    - M-class: flux >= 1e-5 W/m² (moderate flare)
    - C-class: flux >= 1e-6 W/m² (minor flare)
    - B-class: flux >= 1e-7 W/m² (background)
    - A-class: flux < 1e-7 W/m² (quiet)

    Returns:
        Dict with current_flux, flare_class, source
    """
    global _xray_cache, _xray_cache_time

    if not NOAA_ENABLED:
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "disabled"
        }

    # Check cache
    now = time.time()
    if _xray_cache and (now - _xray_cache_time) < XRAY_CACHE_TTL:
        _record_noaa_call(cache_hit=True)  # v20.18: Record cache hit
        return {**_xray_cache, "source": "cache", "from_cache": True}

    if not HTTPX_AVAILABLE:
        _record_noaa_call(error=True)
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "fallback",
            "error": "httpx not installed",
            "from_cache": False,
            "from_live": False,
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(NOAA_XRAY_URL)
            _record_noaa_call(status_code=response.status_code)  # v20.18: Record HTTP call
            response.raise_for_status()
            data = response.json()

        if not data or len(data) < 1:
            raise ValueError("Invalid NOAA X-ray response")

        # Get most recent reading (last item)
        # Format: {"time_tag": "...", "flux": 2.53e-07, "energy": "0.1-0.8nm", ...}
        latest = data[-1]
        current_flux = float(latest.get("flux", 0))
        timestamp = latest.get("time_tag", "")

        # Determine flare class
        if current_flux >= 1e-4:
            flare_class = "X"
        elif current_flux >= 1e-5:
            flare_class = "M"
        elif current_flux >= 1e-6:
            flare_class = "C"
        elif current_flux >= 1e-7:
            flare_class = "B"
        else:
            flare_class = "A"

        result = {
            "current_flux": current_flux,
            "flare_class": flare_class,
            "timestamp": timestamp,
            "source": "noaa_live",
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "from_cache": False,
            "from_live": True,
        }

        # Update cache
        _xray_cache = result
        _xray_cache_time = now

        logger.info("NOAA X-ray flux fetched: %.2e (%s-class)", current_flux, flare_class)
        return result

    except httpx.TimeoutException as e:
        _record_noaa_call(timeout=True)  # v20.18: Record timeout
        logger.warning("NOAA X-ray API timeout: %s", e)
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "fallback",
            "error": str(e),
            "from_cache": False,
            "from_live": False,
        }
    except Exception as e:
        _record_noaa_call(error=True)  # v20.18: Record error
        logger.warning("NOAA X-ray API error: %s", e)
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "fallback",
            "error": str(e),
            "from_cache": False,
            "from_live": False,
        }


# Export for integration
__all__ = [
    "fetch_kp_index_live",
    "get_kp_betting_signal",
    "get_space_weather_summary",
    "get_solar_xray_flux",
    "NOAA_ENABLED",
    # v20.18: Request-scoped proof for semantic audit
    "NOAARequestProof",
    "init_noaa_request_proof",
    "get_noaa_request_proof",
    "get_noaa_auth_context",
]
