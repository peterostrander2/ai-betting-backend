from typing import Any, Dict, Set
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("telemetry")


def apply_used_integrations_debug(result: Dict[str, Any], used_integrations: Set[str], debug_mode: bool) -> None:
    """Attach used_integrations only in debug responses."""
    if not debug_mode:
        return
    result.setdefault("debug", {})
    result["debug"]["used_integrations"] = sorted(used_integrations)


def _build_integration_calls_view(integration_calls: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    view: Dict[str, Dict[str, Any]] = {}
    for name, entry in integration_calls.items():
        calls = int(entry.get("called", 0))
        latency_ms = None
        if entry.get("latency_samples", 0) > 0:
            latency_ms = round(entry.get("latency_total_ms", 0.0) / entry.get("latency_samples", 1), 1)
        cache_hit_rate = None
        if entry.get("cache_samples", 0) > 0:
            cache_hit_rate = round(entry.get("cache_hits", 0) / entry.get("cache_samples", 1), 3)
        view[name] = {
            "called": calls > 0,
            "call_count": calls,
            "status": entry.get("status"),
            "latency_ms": latency_ms,
            "cache_hit": entry.get("cache_hit"),
            "cache_hit_rate": cache_hit_rate,
        }
    return view


def attach_integration_telemetry_debug(
    result: Dict[str, Any],
    integration_calls: Dict[str, Dict[str, Any]],
    integration_impact: Dict[str, Dict[str, Any]],
    debug_mode: bool,
) -> None:
    """Attach integration telemetry only in debug responses."""
    if not debug_mode:
        return
    result.setdefault("debug", {})
    calls_view = _build_integration_calls_view(integration_calls)
    totals_calls = sum(v.get("call_count", 0) for v in calls_view.values())
    cache_samples = sum(integration_calls.get(k, {}).get("cache_samples", 0) for k in integration_calls)
    cache_hits = sum(integration_calls.get(k, {}).get("cache_hits", 0) for k in integration_calls)
    cache_hit_rate = round(cache_hits / cache_samples, 3) if cache_samples > 0 else None

    result["debug"]["integration_calls"] = calls_view
    result["debug"]["integration_impact"] = integration_impact
    result["debug"]["integration_totals"] = {
        "calls_made": totals_calls,
        "cache_hit_rate": cache_hit_rate,
    }

    # usage_counters: Real network calls only (called - cache_hits)
    # Format: {odds_api_calls, playbook_calls, serp_calls}
    def _real_calls(name: str) -> int:
        entry = integration_calls.get(name, {})
        called = int(entry.get("called", 0))
        cache_hits = int(entry.get("cache_hits", 0))
        return max(0, called - cache_hits)

    result["debug"]["usage_counters"] = {
        "odds_api_calls": _real_calls("odds_api"),
        "playbook_calls": _real_calls("playbook_api"),
        "serp_calls": _real_calls("serpapi"),
        "noaa_kp_calls": _real_calls("noaa_kp"),
        "noaa_solar_calls": _real_calls("noaa_solar"),
    }


def record_daily_integration_rollup(
    date_et: str,
    integration_calls: Dict[str, Dict[str, Any]],
    integration_impact: Dict[str, Dict[str, Any]],
) -> None:
    """Persist daily integration usage and impact to Railway volume."""
    try:
        from storage_paths import get_mount_root
    except Exception as e:
        logger.debug("telemetry rollup skipped (storage_paths unavailable): %s", e)
        return

    try:
        mount_root = get_mount_root()
        telemetry_dir = os.path.join(mount_root, "telemetry")
        os.makedirs(telemetry_dir, exist_ok=True)
        path = os.path.join(telemetry_dir, f"daily_{date_et}.json")

        existing = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    existing = json.load(f) or {}
            except Exception:
                existing = {}

        rollup = existing if isinstance(existing, dict) else {}
        rollup.setdefault("date_et", date_et)
        rollup.setdefault("integrations", {})
        rollup.setdefault("updated_at_utc", None)

        for name, entry in integration_calls.items():
            target = rollup["integrations"].setdefault(name, {
                "calls": 0,
                "cache_hits": 0,
                "cache_samples": 0,
                "latency_total_ms": 0.0,
                "latency_samples": 0,
                "impact_nonzero": 0,
                "impact_reasons": 0,
            })
            target["calls"] += int(entry.get("called", 0))
            target["cache_hits"] += int(entry.get("cache_hits", 0))
            target["cache_samples"] += int(entry.get("cache_samples", 0))
            target["latency_total_ms"] += float(entry.get("latency_total_ms", 0.0))
            target["latency_samples"] += int(entry.get("latency_samples", 0))

        for name, entry in integration_impact.items():
            target = rollup["integrations"].setdefault(name, {
                "calls": 0,
                "cache_hits": 0,
                "cache_samples": 0,
                "latency_total_ms": 0.0,
                "latency_samples": 0,
                "impact_nonzero": 0,
                "impact_reasons": 0,
            })
            target["impact_nonzero"] += int(entry.get("nonzero_boost", 0))
            target["impact_reasons"] += int(entry.get("reasons_count", 0))

        rollup["updated_at_utc"] = datetime.now(timezone.utc).isoformat()

        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(rollup, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.debug("telemetry rollup write failed: %s", e)
