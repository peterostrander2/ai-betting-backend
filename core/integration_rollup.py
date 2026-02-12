"""
INTEGRATION ROLLUP - Daily metrics aggregation for integration health monitoring

Records every integration event (success/failure/not_relevant) and aggregates
into daily rollups for trending and alerting.

Usage:
    from core.integration_rollup import record_integration_event, get_rollup, get_alerts

    # On every integration call
    record_integration_event("odds_api", "SUCCESS", latency_ms=234)
    record_integration_event("weather_api", "NOT_RELEVANT", latency_ms=5)
    record_integration_event("playbook_api", "ERROR", latency_ms=1500, error_code="TIMEOUT")

    # Query rollups
    rollup = get_rollup(days=7)
    alerts = get_alerts()
"""

import os
import json
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from threading import Lock
from pathlib import Path

from core.integration_contract import (
    INTEGRATIONS,
    CRITICAL_INTEGRATIONS,
    DEGRADED_OK_INTEGRATIONS,
    OPTIONAL_INTEGRATIONS,
    RELEVANCE_GATED_INTEGRATIONS,
    HEALTH_POLICY,
)

logger = logging.getLogger("integration_rollup")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Staleness thresholds (seconds)
STALENESS_THRESHOLDS = {
    "odds_api": 300,          # 5 minutes - odds move fast
    "playbook_api": 1800,     # 30 minutes - splits update less frequently
    "balldontlie": 3600,      # 1 hour - stats don't change mid-game
    "weather_api": 3600,      # 1 hour - weather updates hourly
    "default": 21600,         # 6 hours for other integrations
}

# Alert thresholds
ALERT_THRESHOLDS = {
    "critical_down_minutes": 60,      # Alert if CRITICAL down for 60 min
    "success_rate_drop_pct": 20,      # Alert if success rate drops 20%
    "unused_hours": 24,               # Alert if configured but unused for 24h
    "min_samples_for_rate": 10,       # Need 10+ samples to compute rate
}

# Storage path
ROLLUP_DIR = os.path.join(
    os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "./grader_data"),
    "integration_rollups"
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class IntegrationEvent:
    """Single integration call event."""
    timestamp: str
    status: str  # SUCCESS, ERROR, NOT_RELEVANT, CACHE_HIT
    latency_ms: int
    error_code: Optional[str] = None


@dataclass
class IntegrationDayStats:
    """Aggregated stats for one integration for one day."""
    integration: str
    date_et: str

    # Counts
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    not_relevant_count: int = 0
    cache_hit_count: int = 0

    # Timestamps
    first_call_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_error: Optional[str] = None

    # Latency stats (ms)
    latencies: List[int] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        denominator = self.success_count + self.error_count
        if denominator == 0:
            return 100.0  # No errors = 100%
        return (self.success_count / denominator) * 100

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in ms."""
        if not self.latencies:
            return 0.0
        return statistics.mean(self.latencies)

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency in ms."""
        if len(self.latencies) < 2:
            return self.avg_latency_ms
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "integration": self.integration,
            "date_et": self.date_et,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "not_relevant_count": self.not_relevant_count,
            "cache_hit_count": self.cache_hit_count,
            "success_rate": round(self.success_rate, 2),
            "first_call_at": self.first_call_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "sample_count": len(self.latencies),
        }


@dataclass
class DailyRollup:
    """Full rollup for one day across all integrations."""
    date_et: str
    generated_at: str
    integrations: Dict[str, IntegrationDayStats] = field(default_factory=dict)

    # Summary counts
    total_calls: int = 0
    total_errors: int = 0
    critical_errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "date_et": self.date_et,
            "generated_at": self.generated_at,
            "summary": {
                "total_calls": self.total_calls,
                "total_errors": self.total_errors,
                "critical_errors": self.critical_errors,
                "integrations_active": len([i for i in self.integrations.values() if i.total_calls > 0]),
                "integrations_total": len(INTEGRATIONS),
            },
            "integrations": {
                name: stats.to_dict()
                for name, stats in self.integrations.items()
            },
        }


# =============================================================================
# IN-MEMORY STATE (thread-safe)
# =============================================================================

_lock = Lock()
_current_day_stats: Dict[str, IntegrationDayStats] = {}
_current_date_et: Optional[str] = None


def _get_et_date() -> str:
    """Get current date in ET timezone."""
    try:
        from zoneinfo import ZoneInfo
        et_tz = ZoneInfo("America/New_York")
        return datetime.now(et_tz).strftime("%Y-%m-%d")
    except Exception:
        # Fallback to UTC-5
        return (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _ensure_day_initialized(date_et: str) -> None:
    """Initialize stats for a new day, flushing previous day if needed."""
    global _current_day_stats, _current_date_et

    if _current_date_et != date_et:
        # Flush previous day's data
        if _current_date_et and _current_day_stats:
            _flush_to_disk(_current_date_et)

        # Initialize new day
        _current_date_et = date_et
        _current_day_stats = {
            name: IntegrationDayStats(integration=name, date_et=date_et)
            for name in INTEGRATIONS.keys()
        }


def _flush_to_disk(date_et: str) -> None:
    """Persist day's rollup to disk."""
    try:
        os.makedirs(ROLLUP_DIR, exist_ok=True)

        rollup = DailyRollup(
            date_et=date_et,
            generated_at=_get_timestamp(),
            integrations=_current_day_stats.copy(),
        )

        # Compute summary stats
        for stats in rollup.integrations.values():
            rollup.total_calls += stats.total_calls
            rollup.total_errors += stats.error_count
            if stats.integration in CRITICAL_INTEGRATIONS:
                rollup.critical_errors += stats.error_count

        filepath = os.path.join(ROLLUP_DIR, f"rollup_{date_et}.json")
        with open(filepath, "w") as f:
            json.dump(rollup.to_dict(), f, indent=2)

        logger.info(f"Flushed integration rollup for {date_et} to {filepath}")
    except Exception as e:
        logger.error(f"Failed to flush rollup for {date_et}: {e}")


# =============================================================================
# PUBLIC API
# =============================================================================

def record_integration_event(
    name: str,
    status: str,
    latency_ms: int = 0,
    error_code: Optional[str] = None,
) -> None:
    """
    Record an integration event.

    Args:
        name: Integration name (e.g., "odds_api")
        status: One of SUCCESS, ERROR, NOT_RELEVANT, CACHE_HIT
        latency_ms: Response time in milliseconds
        error_code: Error code if status is ERROR
    """
    if name not in INTEGRATIONS:
        logger.warning(f"Unknown integration: {name}")
        return

    with _lock:
        date_et = _get_et_date()
        _ensure_day_initialized(date_et)

        stats = _current_day_stats.get(name)
        if not stats:
            stats = IntegrationDayStats(integration=name, date_et=date_et)
            _current_day_stats[name] = stats

        timestamp = _get_timestamp()

        # Update counts
        stats.total_calls += 1

        if not stats.first_call_at:
            stats.first_call_at = timestamp

        if status == "SUCCESS":
            stats.success_count += 1
            stats.last_success_at = timestamp
        elif status == "ERROR":
            stats.error_count += 1
            stats.last_error_at = timestamp
            stats.last_error = error_code or "UNKNOWN"
        elif status == "NOT_RELEVANT":
            stats.not_relevant_count += 1
        elif status == "CACHE_HIT":
            stats.cache_hit_count += 1
            stats.last_success_at = timestamp  # Cache hit counts as success

        # Record latency for non-cache calls
        if status != "CACHE_HIT" and latency_ms > 0:
            stats.latencies.append(latency_ms)
            # Keep only last 1000 samples to bound memory
            if len(stats.latencies) > 1000:
                stats.latencies = stats.latencies[-1000:]


def flush_daily_rollup(date_et: Optional[str] = None) -> Dict[str, Any]:
    """
    Force flush current day's rollup to disk.

    Args:
        date_et: Optional date to flush (defaults to current day)

    Returns:
        The flushed rollup data
    """
    with _lock:
        target_date = date_et or _get_et_date()
        _ensure_day_initialized(target_date)
        _flush_to_disk(target_date)

        rollup = DailyRollup(
            date_et=target_date,
            generated_at=_get_timestamp(),
            integrations=_current_day_stats.copy(),
        )
        for stats in rollup.integrations.values():
            rollup.total_calls += stats.total_calls
            rollup.total_errors += stats.error_count
            if stats.integration in CRITICAL_INTEGRATIONS:
                rollup.critical_errors += stats.error_count

        return rollup.to_dict()


def get_rollup(days: int = 7) -> Dict[str, Any]:
    """
    Get integration rollup data for the last N days.

    Args:
        days: Number of days to include (default 7)

    Returns:
        Dict with daily rollups and computed success rates
    """
    result = {
        "requested_days": days,
        "generated_at": _get_timestamp(),
        "daily_rollups": [],
        "integration_summary": {},
        "critical_failures_24h": [],
    }

    # Get current day's live data
    with _lock:
        date_et = _get_et_date()
        _ensure_day_initialized(date_et)

        current_rollup = DailyRollup(
            date_et=date_et,
            generated_at=_get_timestamp(),
            integrations=_current_day_stats.copy(),
        )
        for stats in current_rollup.integrations.values():
            current_rollup.total_calls += stats.total_calls
            current_rollup.total_errors += stats.error_count
            if stats.integration in CRITICAL_INTEGRATIONS:
                current_rollup.critical_errors += stats.error_count

        result["daily_rollups"].append(current_rollup.to_dict())

    # Load historical rollups from disk
    try:
        if os.path.exists(ROLLUP_DIR):
            for i in range(1, days):
                past_date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
                filepath = os.path.join(ROLLUP_DIR, f"rollup_{past_date}.json")
                if os.path.exists(filepath):
                    with open(filepath) as f:
                        result["daily_rollups"].append(json.load(f))
    except Exception as e:
        logger.error(f"Error loading historical rollups: {e}")

    # Compute per-integration summary across all days
    integration_totals: Dict[str, Dict[str, int]] = {}
    for rollup in result["daily_rollups"]:
        for name, stats in rollup.get("integrations", {}).items():
            if name not in integration_totals:
                integration_totals[name] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "not_relevant_count": 0,
                }
            integration_totals[name]["total_calls"] += stats.get("total_calls", 0)
            integration_totals[name]["success_count"] += stats.get("success_count", 0)
            integration_totals[name]["error_count"] += stats.get("error_count", 0)
            integration_totals[name]["not_relevant_count"] += stats.get("not_relevant_count", 0)

    for name, totals in integration_totals.items():
        denom = totals["success_count"] + totals["error_count"]
        success_rate = (totals["success_count"] / denom * 100) if denom > 0 else 100.0

        criticality = INTEGRATIONS.get(name, {}).get("criticality", "OPTIONAL")

        result["integration_summary"][name] = {
            "criticality": criticality,
            "total_calls": totals["total_calls"],
            "success_count": totals["success_count"],
            "error_count": totals["error_count"],
            "not_relevant_count": totals["not_relevant_count"],
            "success_rate_pct": round(success_rate, 2),
            "is_critical": name in CRITICAL_INTEGRATIONS,
        }

    # Find critical failures in last 24h
    if result["daily_rollups"]:
        today = result["daily_rollups"][0]
        for name in CRITICAL_INTEGRATIONS:
            stats = today.get("integrations", {}).get(name, {})
            if stats.get("error_count", 0) > 0:
                result["critical_failures_24h"].append({
                    "integration": name,
                    "error_count": stats["error_count"],
                    "last_error": stats.get("last_error"),
                    "last_error_at": stats.get("last_error_at"),
                })

    return result


def get_alerts() -> Dict[str, Any]:
    """
    Check for alert conditions and return active alerts.

    Returns:
        Dict with alerts list and summary
    """
    alerts = []
    now = datetime.now(timezone.utc)

    # Get current stats
    with _lock:
        date_et = _get_et_date()
        _ensure_day_initialized(date_et)
        current_stats = {k: v.to_dict() for k, v in _current_day_stats.items()}

    # Check each integration
    for name, config in INTEGRATIONS.items():
        criticality = config.get("criticality", "OPTIONAL")
        stats = current_stats.get(name, {})

        # 1. CRITICAL_INTEGRATION_DOWN: CRITICAL integration with recent errors
        if criticality == "CRITICAL":
            last_error_at = stats.get("last_error_at")
            if last_error_at:
                try:
                    error_time = datetime.fromisoformat(last_error_at.replace("Z", "+00:00"))
                    minutes_since_error = (now - error_time).total_seconds() / 60

                    if minutes_since_error <= ALERT_THRESHOLDS["critical_down_minutes"]:
                        # Check if there's been a success since the error
                        last_success_at = stats.get("last_success_at")
                        recovered = False
                        if last_success_at:
                            success_time = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
                            recovered = success_time > error_time

                        if not recovered:
                            alerts.append({
                                "code": "CRITICAL_INTEGRATION_DOWN",
                                "severity": "critical",
                                "integration": name,
                                "message": f"Critical integration {name} has errors in last {int(minutes_since_error)} minutes",
                                "last_error": stats.get("last_error"),
                                "last_error_at": last_error_at,
                            })
                except Exception:
                    pass

        # 2. UNUSED_INTEGRATION: Configured but not used
        total_calls = stats.get("total_calls", 0)
        if total_calls == 0 and criticality in ("CRITICAL", "DEGRADED_OK"):
            alerts.append({
                "code": "UNUSED_INTEGRATION",
                "severity": "warning",
                "integration": name,
                "message": f"Integration {name} is {criticality} but has 0 calls today",
            })

        # 3. SUCCESS_RATE_DROP: Significant drop vs expected
        success_rate = stats.get("success_rate", 100)
        if stats.get("total_calls", 0) >= ALERT_THRESHOLDS["min_samples_for_rate"]:
            if success_rate < (100 - ALERT_THRESHOLDS["success_rate_drop_pct"]):
                alerts.append({
                    "code": "SUCCESS_RATE_DROP",
                    "severity": "warning" if criticality != "CRITICAL" else "critical",
                    "integration": name,
                    "message": f"Integration {name} success rate is {success_rate:.1f}%",
                    "success_rate": success_rate,
                    "error_count": stats.get("error_count", 0),
                })

        # 4. CRITICAL_STALENESS: No recent success for critical integration
        if criticality == "CRITICAL":
            last_success_at = stats.get("last_success_at")
            staleness_threshold = STALENESS_THRESHOLDS.get(name, STALENESS_THRESHOLDS["default"])

            if last_success_at:
                try:
                    success_time = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
                    staleness_seconds = (now - success_time).total_seconds()

                    if staleness_seconds > staleness_threshold:
                        alerts.append({
                            "code": "CRITICAL_STALENESS",
                            "severity": "critical",
                            "integration": name,
                            "message": f"Critical integration {name} data is stale ({int(staleness_seconds)}s old, threshold {staleness_threshold}s)",
                            "staleness_seconds": int(staleness_seconds),
                            "threshold_seconds": staleness_threshold,
                            "last_success_at": last_success_at,
                        })
                except Exception:
                    pass

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 99))

    return {
        "generated_at": _get_timestamp(),
        "alert_count": len(alerts),
        "critical_count": len([a for a in alerts if a.get("severity") == "critical"]),
        "warning_count": len([a for a in alerts if a.get("severity") == "warning"]),
        "alerts": alerts,
        "thresholds": ALERT_THRESHOLDS,
    }


def get_staleness_seconds(name: str) -> Optional[int]:
    """
    Get staleness in seconds for an integration.

    Returns None if no success recorded, otherwise seconds since last success.
    """
    with _lock:
        date_et = _get_et_date()
        _ensure_day_initialized(date_et)

        stats = _current_day_stats.get(name)
        if not stats or not stats.last_success_at:
            return None

        try:
            success_time = datetime.fromisoformat(stats.last_success_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return int((now - success_time).total_seconds())
        except Exception:
            return None


def get_integration_health_for_health_endpoint() -> Dict[str, Any]:
    """
    Get integration health summary for /health endpoint.

    Applies criticality tiers correctly:
    - CRITICAL: missing/unreachable → ok=false
    - DEGRADED_OK: missing/unreachable → ok=true, status=degraded
    - OPTIONAL: no health impact
    - RELEVANCE_GATED: context-dependent

    Returns:
        Dict with ok, status, and per-integration status
    """
    result = {
        "ok": True,
        "status": "healthy",
        "integrations": {},
        "degraded_reasons": [],
        "critical_errors": [],
    }

    with _lock:
        date_et = _get_et_date()
        _ensure_day_initialized(date_et)

        for name, config in INTEGRATIONS.items():
            criticality = config.get("criticality", "OPTIONAL")
            stats = _current_day_stats.get(name, IntegrationDayStats(integration=name, date_et=date_et))

            # Determine current status
            has_recent_success = stats.last_success_at is not None
            has_recent_error = stats.last_error_at is not None

            # If we have both, check which is more recent
            integration_ok = True
            if has_recent_error and has_recent_success:
                try:
                    success_time = datetime.fromisoformat(stats.last_success_at.replace("Z", "+00:00"))
                    error_time = datetime.fromisoformat(stats.last_error_at.replace("Z", "+00:00"))
                    integration_ok = success_time > error_time
                except Exception:
                    integration_ok = True
            elif has_recent_error and not has_recent_success:
                integration_ok = False

            # Apply criticality policy
            if not integration_ok:
                if criticality == "CRITICAL":
                    result["ok"] = False
                    result["status"] = "critical"
                    result["critical_errors"].append({
                        "integration": name,
                        "last_error": stats.last_error,
                    })
                elif criticality == "DEGRADED_OK":
                    if result["status"] == "healthy":
                        result["status"] = "degraded"
                    result["degraded_reasons"].append(f"{name} has errors")
                # OPTIONAL and RELEVANCE_GATED don't affect health

            result["integrations"][name] = {
                "criticality": criticality,
                "ok": integration_ok,
                "total_calls": stats.total_calls,
                "success_count": stats.success_count,
                "error_count": stats.error_count,
                "last_success_at": stats.last_success_at,
                "last_error_at": stats.last_error_at,
            }

    return result
