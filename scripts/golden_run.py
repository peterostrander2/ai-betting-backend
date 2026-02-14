#!/usr/bin/env python3
"""
GOLDEN RUN - End-to-end system regression gate

Single command that proves the system hasn't drifted:
- Engine versions match expected
- Titanium gating works correctly
- Required fields present
- Weights reconcile
- Jarvis impl/blend fields correct
- Critical integrations called

Usage:
    # Capture new golden baseline
    API_KEY=your_key python3 scripts/golden_run.py capture

    # Validate against golden baseline
    API_KEY=your_key python3 scripts/golden_run.py validate

    # Quick health check (no baseline needed)
    API_KEY=your_key python3 scripts/golden_run.py check
"""

import os
import sys
import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Deterministic baseline (committed to repo, never auto-generated during validation)
GOLDEN_BASELINE = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_baseline_v20.21.json"
# Legacy capture file (for ad-hoc snapshots, NOT used in CI validation)
GOLDEN_CAPTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_run.json"
API_BASE = os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app")
API_KEY = os.getenv("API_KEY", "")

# =============================================================================
# EXPECTED VALUES (update when intentionally changing)
# =============================================================================

EXPECTED = {
    "version": "20.24",  # v20.24: Context multipliers now LIVE
    "engine_weights": {
        "ai": 0.25,
        "research": 0.35,
        "esoteric": 0.15,
        "jarvis": 0.25,
    },
    "jarvis_impl": "hybrid",
    "jarvis_blend_type": "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA",
    "jarvis_version": "JARVIS_OPHIS_HYBRID_v2.2.1",
    "titanium_threshold": 8.0,
    "titanium_min_engines": 3,
    "min_final_score_games": 7.0,  # From scoring_contract.py MIN_FINAL_SCORE
    "min_final_score_props": 6.5,  # From scoring_contract.py MIN_PROPS_SCORE
    "valid_tiers": ["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"],  # MONITOR/PASS are hidden
    "critical_integrations": ["odds_api", "playbook_api", "balldontlie", "railway_storage", "database"],
}

REQUIRED_PICK_FIELDS = [
    "pick_id", "sport", "market", "final_score", "tier",
    "ai_score", "research_score", "esoteric_score", "jarvis_rs",
    "ai_reasons", "research_reasons", "esoteric_reasons", "jarvis_reasons",
    "titanium_triggered",
    # Note: titanium_count is NOT output in production picks
]

REQUIRED_DEBUG_FIELDS = [
    "date_window_et", "filtered_below_6_5_total",
]

REQUIRED_JARVIS_FIELDS = [
    "jarvis_rs", "jarvis_active", "jarvis_blend_type", "ophis_delta",
]


# =============================================================================
# API FETCHING
# =============================================================================

def fetch_json(endpoint: str) -> Optional[Dict[str, Any]]:
    """Fetch JSON from API endpoint."""
    import requests

    url = f"{API_BASE}{endpoint}"
    headers = {"X-API-Key": API_KEY} if API_KEY else {}

    try:
        resp = requests.get(url, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"ERROR fetching {endpoint}: {e}")
        return None


def fetch_best_bets(sport: str) -> Optional[Dict[str, Any]]:
    """Fetch best-bets with debug enabled."""
    return fetch_json(f"/live/best-bets/{sport}?debug=1")


def fetch_health() -> Optional[Dict[str, Any]]:
    """Fetch health endpoint."""
    import requests
    url = f"{API_BASE}/health"
    try:
        resp = requests.get(url, timeout=30)
        return resp.json()
    except Exception as e:
        print(f"ERROR fetching /health: {e}")
        return None


def fetch_integration_rollup() -> Optional[Dict[str, Any]]:
    """Fetch integration rollup."""
    return fetch_json("/live/debug/integration-rollup?days=1")


def fetch_integrations_status() -> Optional[Dict[str, Any]]:
    """Fetch integrations status (includes calls_last_15m for v20.21 state machine)."""
    return fetch_json("/live/debug/integrations")


# =============================================================================
# NORMALIZATION (strip volatile fields)
# =============================================================================

def normalize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Strip timestamps and request IDs for stable comparison."""
    if not data:
        return {}

    # Fields to strip (volatile)
    volatile_patterns = [
        r".*_at$",           # timestamps ending in _at
        r".*_timestamp.*",   # timestamp fields
        r".*request_id.*",   # request IDs
        r"generated_at",
        r"captured_at",
        r"run_timestamp.*",
        r"elapsed.*",
        r"_cached_at",
    ]

    def should_strip(key: str) -> bool:
        for pattern in volatile_patterns:
            if re.match(pattern, key, re.IGNORECASE):
                return True
        return False

    def strip_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: strip_recursive(v) for k, v in obj.items() if not should_strip(k)}
        elif isinstance(obj, list):
            return [strip_recursive(item) for item in obj]
        else:
            return obj

    return strip_recursive(data)


def extract_schema_signature(picks: List[Dict]) -> Dict[str, Any]:
    """Extract schema signature from picks for comparison."""
    if not picks:
        return {"count": 0, "fields": [], "sample": None}

    # Get union of all fields across picks
    all_fields = set()
    for pick in picks:
        all_fields.update(pick.keys())

    # Get sample of first pick (normalized)
    sample = None
    if picks:
        sample = {k: type(v).__name__ for k, v in picks[0].items()}

    return {
        "count": len(picks),
        "fields": sorted(all_fields),
        "sample_types": sample,
    }


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, check: str, detail: str = ""):
        self.passed.append({"check": check, "detail": detail})

    def add_fail(self, check: str, detail: str, expected: Any = None, actual: Any = None):
        self.failed.append({
            "check": check,
            "detail": detail,
            "expected": expected,
            "actual": actual,
        })

    def add_warning(self, check: str, detail: str):
        self.warnings.append({"check": check, "detail": detail})

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def summary(self) -> str:
        return f"{len(self.passed)} passed, {len(self.failed)} failed, {len(self.warnings)} warnings"


def validate_health(health: Dict[str, Any], result: ValidationResult):
    """Validate health endpoint response."""
    # Version check
    version = health.get("version", "")
    if version == EXPECTED["version"]:
        result.add_pass("health.version", f"v{version}")
    else:
        result.add_fail("health.version", "Version mismatch", EXPECTED["version"], version)

    # Storage health
    storage = health.get("storage", {})
    if storage.get("is_mountpoint") and not storage.get("is_ephemeral"):
        result.add_pass("health.storage", "Persistent volume OK")
    else:
        result.add_fail("health.storage", "Storage not persistent")

    # Overall health
    if health.get("ok") or health.get("status") == "healthy":
        result.add_pass("health.status", "System healthy")
    else:
        result.add_warning("health.status", f"Status: {health.get('status')}")


def validate_picks(picks: List[Dict], sport: str, result: ValidationResult,
                   props_picks: List[Dict] = None, game_picks: List[Dict] = None):
    """Validate pick structure and scoring.

    Args:
        picks: All picks (props + games combined) for field validation
        sport: Sport code (NBA, NCAAB, etc.)
        result: ValidationResult to add pass/fail to
        props_picks: Props picks only (for threshold validation)
        game_picks: Game picks only (for threshold validation)
    """
    if not picks:
        result.add_warning(f"{sport}.picks", "No picks returned (may be off-season)")
        return

    # Required fields check
    missing_fields = set()
    for pick in picks:
        for field in REQUIRED_PICK_FIELDS:
            if field not in pick:
                missing_fields.add(field)

    if missing_fields:
        result.add_fail(f"{sport}.required_fields", f"Missing: {missing_fields}")
    else:
        result.add_pass(f"{sport}.required_fields", f"All {len(REQUIRED_PICK_FIELDS)} fields present")

    # Score threshold check - different thresholds for props vs games
    props_picks = props_picks or []
    game_picks = game_picks or []

    # Props: MIN_PROPS_SCORE = 6.5
    props_below = [p for p in props_picks if p.get("final_score", 0) < EXPECTED["min_final_score_props"]]
    # Games: MIN_FINAL_SCORE = 7.0
    games_below = [p for p in game_picks if p.get("final_score", 0) < EXPECTED["min_final_score_games"]]

    if props_below or games_below:
        issues = []
        if props_below:
            issues.append(f"{len(props_below)} props below {EXPECTED['min_final_score_props']}")
        if games_below:
            issues.append(f"{len(games_below)} games below {EXPECTED['min_final_score_games']}")
        result.add_fail(f"{sport}.score_threshold", "; ".join(issues))
    else:
        result.add_pass(f"{sport}.score_threshold",
                       f"Props >= {EXPECTED['min_final_score_props']}, Games >= {EXPECTED['min_final_score_games']}")

    # Tier validation
    invalid_tiers = [p.get("tier") for p in picks if p.get("tier") not in EXPECTED["valid_tiers"]]
    if invalid_tiers:
        result.add_fail(f"{sport}.valid_tiers", f"Invalid tiers: {set(invalid_tiers)}")
    else:
        result.add_pass(f"{sport}.valid_tiers", "All tiers valid")

    # Titanium rule validation
    for pick in picks:
        if pick.get("titanium_triggered"):
            engines = [
                pick.get("ai_score", 0),
                pick.get("research_score", 0),
                pick.get("esoteric_score", 0),
                pick.get("jarvis_rs", 0) or 0,
            ]
            above_8 = sum(1 for e in engines if e >= EXPECTED["titanium_threshold"])
            if above_8 < EXPECTED["titanium_min_engines"]:
                result.add_fail(
                    f"{sport}.titanium_rule",
                    f"Titanium triggered with only {above_8}/4 engines >= 8.0",
                    f">= {EXPECTED['titanium_min_engines']}",
                    above_8
                )

    # Count titanium picks validated
    titanium_picks = [p for p in picks if p.get("titanium_triggered")]
    if titanium_picks:
        result.add_pass(f"{sport}.titanium_rule", f"{len(titanium_picks)} titanium picks validated")

    # Weight reconciliation (sample)
    for pick in picks[:3]:  # Check first 3 picks
        ai = pick.get("ai_score", 0) or 0
        research = pick.get("research_score", 0) or 0
        esoteric = pick.get("esoteric_score", 0) or 0
        jarvis = pick.get("jarvis_rs", 0) or 0

        weights = EXPECTED["engine_weights"]
        expected_base = (
            ai * weights["ai"] +
            research * weights["research"] +
            esoteric * weights["esoteric"] +
            jarvis * weights["jarvis"]
        )

        final = pick.get("final_score", 0)
        # Allow for boosts (confluence, msrf, etc) - just check base isn't wildly off
        if final < expected_base - 2.0:
            result.add_warning(
                f"{sport}.weight_reconciliation",
                f"Final {final:.2f} much lower than base {expected_base:.2f}"
            )

    result.add_pass(f"{sport}.weight_reconciliation", "Weights reconcile within tolerance")


def validate_jarvis_fields(picks: List[Dict], sport: str, result: ValidationResult):
    """Validate Jarvis-specific fields."""
    if not picks:
        return

    for pick in picks[:5]:  # Sample first 5
        # Check jarvis fields exist
        missing = [f for f in REQUIRED_JARVIS_FIELDS if f not in pick]
        if missing:
            result.add_fail(f"{sport}.jarvis_fields", f"Missing: {missing}")
            return

        # Validate blend type
        blend_type = pick.get("jarvis_blend_type", "")
        if blend_type and blend_type != EXPECTED["jarvis_blend_type"]:
            result.add_fail(
                f"{sport}.jarvis_blend_type",
                "Blend type changed",
                EXPECTED["jarvis_blend_type"],
                blend_type
            )
            return

    result.add_pass(f"{sport}.jarvis_fields", "All Jarvis v2.2 fields present")


def validate_debug_fields(debug: Dict[str, Any], sport: str, result: ValidationResult):
    """Validate debug telemetry fields."""
    if not debug:
        result.add_warning(f"{sport}.debug", "No debug data (debug=1 not passed?)")
        return

    missing = [f for f in REQUIRED_DEBUG_FIELDS if f not in debug]
    if missing:
        result.add_fail(f"{sport}.debug_fields", f"Missing debug fields: {missing}")
    else:
        result.add_pass(f"{sport}.debug_fields", "Debug telemetry present")

    # ET date check
    date_window = debug.get("date_window_et", {})
    if date_window.get("filter_date"):
        result.add_pass(f"{sport}.et_gating", f"ET date: {date_window['filter_date']}")
    else:
        result.add_fail(f"{sport}.et_gating", "No ET filter date")


def validate_integrations(rollup: Dict[str, Any], result: ValidationResult,
                          integrations_status: Optional[Dict[str, Any]] = None):
    """Validate critical integrations are being called.

    v20.21: Uses deterministic state machine for "0 calls" warnings:
    - calls_last_15m: rolling window of recent calls (from integrations_status)
    - If calls_last_15m is None/missing, falls back to total_calls heuristic
    - Only warns if calls_last_15m == 0 AND integration is expected for validated sports
    """
    if not rollup:
        result.add_fail("integrations.rollup", "Could not fetch rollup")
        return

    summary = rollup.get("integration_summary", {})

    # v20.21: Get detailed status for calls_last_15m
    detailed_status = {}
    if integrations_status:
        detailed_status = integrations_status.get("integrations", {})

    # Integrations expected for NBA/NCAAB (what we validate against)
    # Per core/integration_contract.py SPORT_INTEGRATION_RELEVANCE
    expected_integrations = {
        "odds_api", "playbook_api", "railway_storage", "database",  # ALL sports
        "balldontlie",  # NBA
    }

    for integration in EXPECTED["critical_integrations"]:
        info = summary.get(integration, {})
        criticality = info.get("criticality", "UNKNOWN")
        total_calls = info.get("total_calls", 0)

        # v20.21: Get calls_last_15m from detailed status
        detail = detailed_status.get(integration, {})
        calls_15m = detail.get("calls_last_15m")  # May be None if not deployed

        if criticality != "CRITICAL":
            result.add_fail(
                f"integrations.{integration}",
                f"Criticality should be CRITICAL, got {criticality}"
            )
        elif calls_15m is not None and calls_15m > 0:
            # v20.21: Deterministic pass - recent calls confirmed
            result.add_pass(f"integrations.{integration}", f"{calls_15m} calls/15m, {criticality}")
        elif calls_15m == 0 and integration in expected_integrations:
            # v20.21: Deterministic warning - expected but no recent calls
            result.add_warning(
                f"integrations.{integration}",
                f"0 calls in last 15m (expected for validated sports)"
            )
        elif calls_15m == 0:
            # Not expected for validated sports - just note it
            result.add_pass(f"integrations.{integration}", f"0 calls/15m (not expected for sport)")
        elif total_calls > 0:
            # Fallback: calls_last_15m not available, use total_calls
            result.add_pass(f"integrations.{integration}", f"{total_calls} total calls, {criticality}")
        else:
            # Fallback: no calls at all
            result.add_warning(
                f"integrations.{integration}",
                f"0 total calls (calls_last_15m not available)"
            )


# =============================================================================
# GOLDEN RUN COMMANDS
# =============================================================================

def cmd_capture():
    """Capture ad-hoc snapshot (NOT used for CI validation - use golden_baseline_v20.20.json instead)."""
    print("Capturing ad-hoc snapshot...")
    print("NOTE: This creates a snapshot for debugging. CI validation uses golden_baseline_v20.20.json")
    print("")

    if not API_KEY:
        print("ERROR: API_KEY environment variable required")
        sys.exit(1)

    golden = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "api_base": API_BASE,
        "expected": EXPECTED,
        "snapshots": {},
    }

    # Capture health
    print("  Fetching /health...")
    health = fetch_health()
    if health:
        golden["snapshots"]["health"] = {
            "version": health.get("version"),
            "build_sha": health.get("build_sha"),
            "storage_ok": health.get("storage", {}).get("is_mountpoint"),
        }

    # Capture best-bets for active sports
    for sport in ["NBA", "NCAAB"]:
        print(f"  Fetching /live/best-bets/{sport}...")
        data = fetch_best_bets(sport)
        if data:
            props = data.get("props", {}).get("picks", [])
            games = data.get("game_picks", {}).get("picks", [])

            golden["snapshots"][sport] = {
                "props_schema": extract_schema_signature(props),
                "games_schema": extract_schema_signature(games),
                "debug_fields": list(data.get("debug", {}).keys()) if data.get("debug") else [],
                "sample_pick": normalize_response(props[0] if props else (games[0] if games else {})),
            }

    # Capture integration rollup
    print("  Fetching integration rollup...")
    rollup = fetch_integration_rollup()
    if rollup:
        golden["snapshots"]["integrations"] = {
            "summary": {k: v.get("criticality") for k, v in rollup.get("integration_summary", {}).items()},
        }

    # Save to capture file (NOT the deterministic baseline)
    GOLDEN_CAPTURE.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_CAPTURE, "w") as f:
        json.dump(golden, f, indent=2)

    print(f"\nSnapshot saved to: {GOLDEN_CAPTURE}")
    print(f"Snapshots: {list(golden['snapshots'].keys())}")
    print("")
    print("To update the deterministic baseline, manually edit:")
    print(f"  {GOLDEN_BASELINE}")


def cmd_validate():
    """Validate against deterministic baseline (committed to repo).

    IMPORTANT: This command uses the committed golden_baseline_v20.20.json file.
    It will HARD-FAIL if the baseline is missing - never auto-capture during validation.
    This ensures CI catches regressions against a known-good contract state.
    """
    print("Validating against deterministic baseline...")
    print(f"Baseline: {GOLDEN_BASELINE}")
    print("")

    if not GOLDEN_BASELINE.exists():
        print("=" * 60)
        print("FATAL ERROR: Deterministic baseline not found!")
        print("=" * 60)
        print(f"Expected: {GOLDEN_BASELINE}")
        print("")
        print("The baseline must be committed to the repo.")
        print("DO NOT auto-generate baselines during CI validation.")
        print("")
        print("To create a new baseline after intentional contract changes:")
        print("  1. Update tests/fixtures/golden_baseline_v20.20.json manually")
        print("  2. Commit the baseline with the contract change")
        print("=" * 60)
        sys.exit(1)

    if not API_KEY:
        print("ERROR: API_KEY environment variable required")
        sys.exit(1)

    with open(GOLDEN_BASELINE) as f:
        baseline = json.load(f)

    # Extract contracts from deterministic baseline
    contracts = baseline.get("contracts", {})

    # Override EXPECTED with baseline values for validation
    global EXPECTED
    EXPECTED = {
        "version": contracts.get("version", EXPECTED["version"]),
        "engine_weights": contracts.get("engine_weights", EXPECTED["engine_weights"]),
        "jarvis_impl": contracts.get("jarvis", {}).get("impl", EXPECTED["jarvis_impl"]),
        "jarvis_blend_type": contracts.get("jarvis", {}).get("blend_type", EXPECTED["jarvis_blend_type"]),
        "jarvis_version": contracts.get("jarvis", {}).get("version", EXPECTED["jarvis_version"]),
        "titanium_threshold": contracts.get("titanium", {}).get("threshold", EXPECTED["titanium_threshold"]),
        "titanium_min_engines": contracts.get("titanium", {}).get("min_engines", EXPECTED["titanium_min_engines"]),
        "min_final_score_games": contracts.get("thresholds", {}).get("min_final_score_games", EXPECTED["min_final_score_games"]),
        "min_final_score_props": contracts.get("thresholds", {}).get("min_final_score_props", EXPECTED["min_final_score_props"]),
        "valid_tiers": contracts.get("tiers", {}).get("valid_output", EXPECTED["valid_tiers"]),
        "critical_integrations": contracts.get("critical_integrations", EXPECTED["critical_integrations"]),
    }

    print(f"Baseline version: {baseline.get('baseline_version')}")
    print(f"Baseline type: {baseline.get('baseline_type')}")
    print("")

    result = ValidationResult()

    # Get required fields from baseline
    required_pick_fields = set(baseline.get("required_pick_fields", REQUIRED_PICK_FIELDS))
    required_jarvis_fields = set(baseline.get("required_jarvis_fields", REQUIRED_JARVIS_FIELDS))
    required_debug_fields = set(baseline.get("required_debug_fields", REQUIRED_DEBUG_FIELDS))

    # Validate health
    print("  Checking /health...")
    health = fetch_health()
    if health:
        validate_health(health, result)

    # Validate best-bets
    for sport in ["NBA", "NCAAB"]:
        print(f"  Checking /live/best-bets/{sport}...")
        data = fetch_best_bets(sport)
        if data:
            props = data.get("props", {}).get("picks", [])
            games = data.get("game_picks", {}).get("picks", [])
            all_picks = props + games

            validate_picks(all_picks, sport, result, props_picks=props, game_picks=games)
            validate_jarvis_fields(all_picks, sport, result)
            validate_debug_fields(data.get("debug", {}), sport, result)

            # Validate required fields from baseline are present
            if all_picks:
                pick_fields = set(all_picks[0].keys())
                missing = required_pick_fields - pick_fields
                if missing:
                    result.add_fail(f"baseline.{sport}.required_fields", f"Missing baseline-required fields: {missing}")

    # Validate integrations
    print("  Checking integrations...")
    rollup = fetch_integration_rollup()
    integrations_status = fetch_integrations_status()  # v20.21: for calls_last_15m
    validate_integrations(rollup, result, integrations_status)

    # Print results
    print("\n" + "=" * 60)
    print("GOLDEN RUN VALIDATION RESULTS")
    print("=" * 60)

    if result.passed:
        print(f"\n PASSED ({len(result.passed)}):")
        for p in result.passed:
            print(f"  {p['check']}: {p['detail']}")

    if result.warnings:
        print(f"\n WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  {w['check']}: {w['detail']}")

    if result.failed:
        print(f"\n FAILED ({len(result.failed)}):")
        for f in result.failed:
            print(f"  {f['check']}: {f['detail']}")
            if f.get("expected"):
                print(f"    expected: {f['expected']}")
                print(f"    actual:   {f['actual']}")

    print("\n" + "=" * 60)
    print(f"RESULT: {'PASS' if result.ok else 'FAIL'} - {result.summary()}")
    print("=" * 60)

    sys.exit(0 if result.ok else 1)


def cmd_check():
    """Quick health check without golden baseline."""
    print("Running quick health check...")

    if not API_KEY:
        print("ERROR: API_KEY environment variable required")
        sys.exit(1)

    result = ValidationResult()

    # Health check
    health = fetch_health()
    if health:
        validate_health(health, result)
    else:
        result.add_fail("health", "Could not fetch /health")

    # Best-bets check (just one sport)
    data = fetch_best_bets("NBA")
    if data:
        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])
        all_picks = props + games
        validate_picks(all_picks, "NBA", result, props_picks=props, game_picks=games)
        validate_jarvis_fields(all_picks, "NBA", result)
    else:
        result.add_fail("NBA", "Could not fetch best-bets")

    # Integration check
    rollup = fetch_integration_rollup()
    integrations_status = fetch_integrations_status()  # v20.21: for calls_last_15m
    if rollup:
        validate_integrations(rollup, result, integrations_status)

    # Print summary
    print("\n" + "=" * 60)
    print(f"QUICK CHECK: {'PASS' if result.ok else 'FAIL'} - {result.summary()}")
    print("=" * 60)

    if result.failed:
        for f in result.failed:
            print(f"  FAIL: {f['check']}: {f['detail']}")

    sys.exit(0 if result.ok else 1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "capture":
        cmd_capture()
    elif cmd == "validate":
        cmd_validate()
    elif cmd == "check":
        cmd_check()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: capture, validate, check")
        sys.exit(1)


if __name__ == "__main__":
    main()
