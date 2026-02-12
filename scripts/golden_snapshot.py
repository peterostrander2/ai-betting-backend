#!/usr/bin/env python3
"""
GOLDEN SNAPSHOT - Capture live slate for regression testing

Captures a deterministic snapshot of /live/best-bets/{sport}?debug=1 including:
- Full JSON response
- Metadata (timestamp, build SHA, sport)
- Computed validation checks

Usage:
    API_KEY=your_key python3 scripts/golden_snapshot.py NBA
    API_KEY=your_key API_BASE=https://... python3 scripts/golden_snapshot.py NHL

Saves to:
    tests/fixtures/golden/{sport}/{date_et}.json
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_et_date() -> str:
    """Get current date in ET timezone."""
    try:
        from zoneinfo import ZoneInfo
        et_tz = ZoneInfo("America/New_York")
        return datetime.now(et_tz).strftime("%Y-%m-%d")
    except Exception:
        # Fallback to UTC-5
        return (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")


def fetch_best_bets(sport: str, base_url: str, api_key: str) -> Dict[str, Any]:
    """Fetch best-bets from API with debug enabled."""
    import requests

    url = f"{base_url}/live/best-bets/{sport}"
    params = {"debug": "1"}
    headers = {"X-API-Key": api_key}

    response = requests.get(url, params=params, headers=headers, timeout=120)
    response.raise_for_status()

    return response.json()


def validate_pick_schema(pick: Dict[str, Any]) -> List[str]:
    """Validate a single pick has required fields."""
    violations = []

    # Required scoring fields
    required_fields = [
        "ai_score", "research_score", "esoteric_score", "jarvis_rs",
        "final_score", "tier", "context_modifier",
        "ai_reasons", "research_reasons", "esoteric_reasons", "jarvis_reasons",
    ]

    for field in required_fields:
        if field not in pick:
            violations.append(f"MISSING:{field}")

    # Numeric validation
    if "final_score" in pick:
        if pick["final_score"] < 6.5:
            violations.append(f"SCORE_TOO_LOW:{pick['final_score']}")

    # Tier validation
    valid_tiers = {"TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"}
    if "tier" in pick and pick["tier"] not in valid_tiers:
        violations.append(f"INVALID_TIER:{pick['tier']}")

    return violations


def validate_titanium_rule(pick: Dict[str, Any]) -> List[str]:
    """Validate Titanium 3-of-4 rule."""
    violations = []

    if not pick.get("titanium_triggered"):
        return violations

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    engines_above_8 = sum(1 for score in [ai, research, esoteric, jarvis] if score >= 8.0)

    if engines_above_8 < 3:
        violations.append(f"TITANIUM_RULE:only_{engines_above_8}_engines_gte_8")

    return violations


def reconcile_weights(pick: Dict[str, Any]) -> Dict[str, Any]:
    """Check if score reconciles with engine weights."""
    AI_WEIGHT = 0.25
    RESEARCH_WEIGHT = 0.35
    ESOTERIC_WEIGHT = 0.15
    JARVIS_WEIGHT = 0.25

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    expected_base = (ai * AI_WEIGHT) + (research * RESEARCH_WEIGHT) + \
                   (esoteric * ESOTERIC_WEIGHT) + (jarvis * JARVIS_WEIGHT)

    context_mod = pick.get("context_modifier", 0) or 0
    confluence = pick.get("confluence_boost", 0) or 0
    msrf = pick.get("msrf_boost", 0) or 0
    jason = pick.get("jason_sim_boost", 0) or 0
    serp = pick.get("serp_boost", 0) or 0

    # Total boost cap is 1.5
    total_boosts = confluence + msrf + jason + serp
    capped_boosts = min(total_boosts, 1.5)

    expected_final_approx = expected_base + context_mod + capped_boosts

    actual_final = pick.get("final_score", 0)
    delta = abs(actual_final - expected_final_approx)

    return {
        "expected_base": round(expected_base, 3),
        "context_modifier": round(context_mod, 3),
        "total_boosts": round(total_boosts, 3),
        "capped_boosts": round(capped_boosts, 3),
        "expected_final_approx": round(expected_final_approx, 3),
        "actual_final": round(actual_final, 3),
        "delta": round(delta, 3),
        "reconciles": delta < 2.0,  # Allow for ensemble/live adjustments
    }


def create_snapshot(sport: str, response: Dict[str, Any]) -> Dict[str, Any]:
    """Create a golden snapshot with validation checks."""
    date_et = get_et_date()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Extract metadata
    build_sha = response.get("debug", {}).get("build_sha") or response.get("meta", {}).get("build_sha", "unknown")

    # Get all picks
    game_picks = response.get("game_picks", {}).get("picks", [])
    prop_picks = response.get("props", {}).get("picks", [])
    all_picks = game_picks + prop_picks

    # Run validations
    validation_results = {
        "total_picks": len(all_picks),
        "game_picks": len(game_picks),
        "prop_picks": len(prop_picks),
        "schema_violations": [],
        "titanium_violations": [],
        "weight_reconciliation": [],
        "score_stats": {},
    }

    scores = []
    for pick in all_picks:
        # Schema check
        schema_issues = validate_pick_schema(pick)
        if schema_issues:
            validation_results["schema_violations"].append({
                "pick_id": pick.get("pick_id", "unknown"),
                "issues": schema_issues,
            })

        # Titanium check
        titanium_issues = validate_titanium_rule(pick)
        if titanium_issues:
            validation_results["titanium_violations"].append({
                "pick_id": pick.get("pick_id", "unknown"),
                "issues": titanium_issues,
            })

        # Weight reconciliation
        recon = reconcile_weights(pick)
        if not recon["reconciles"]:
            validation_results["weight_reconciliation"].append({
                "pick_id": pick.get("pick_id", "unknown"),
                "details": recon,
            })

        if pick.get("final_score"):
            scores.append(pick["final_score"])

    # Score stats
    if scores:
        validation_results["score_stats"] = {
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "avg": round(sum(scores) / len(scores), 2),
            "count": len(scores),
        }

    # Create snapshot
    snapshot = {
        "metadata": {
            "sport": sport,
            "date_et": date_et,
            "captured_at": timestamp,
            "build_sha": build_sha,
            "version": "20.20",
        },
        "validation": {
            "all_passed": (
                len(validation_results["schema_violations"]) == 0 and
                len(validation_results["titanium_violations"]) == 0
            ),
            "results": validation_results,
        },
        "response": response,
    }

    # Generate content hash for integrity
    content_hash = hashlib.md5(json.dumps(response, sort_keys=True).encode()).hexdigest()[:12]
    snapshot["metadata"]["content_hash"] = content_hash

    return snapshot


def save_snapshot(snapshot: Dict[str, Any], sport: str) -> str:
    """Save snapshot to fixtures directory."""
    date_et = snapshot["metadata"]["date_et"]

    # Create directory
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "golden" / sport.lower()
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    filepath = fixtures_dir / f"{date_et}.json"
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2)

    return str(filepath)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: API_KEY=your_key python3 scripts/golden_snapshot.py <sport>")
        print("Sports: NBA, NHL, NFL, MLB, NCAAB")
        sys.exit(1)

    sport = sys.argv[1].upper()
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app")

    if not api_key:
        print("ERROR: API_KEY environment variable required")
        sys.exit(1)

    valid_sports = {"NBA", "NHL", "NFL", "MLB", "NCAAB"}
    if sport not in valid_sports:
        print(f"ERROR: Invalid sport '{sport}'. Must be one of: {valid_sports}")
        sys.exit(1)

    print(f"Fetching best-bets for {sport}...")
    print(f"Base URL: {base_url}")

    try:
        response = fetch_best_bets(sport, base_url, api_key)
    except Exception as e:
        print(f"ERROR: Failed to fetch best-bets: {e}")
        sys.exit(1)

    print("Creating snapshot...")
    snapshot = create_snapshot(sport, response)

    print("Saving snapshot...")
    filepath = save_snapshot(snapshot, sport)

    # Print summary
    print("\n" + "=" * 60)
    print("GOLDEN SNAPSHOT CREATED")
    print("=" * 60)
    print(f"Sport: {sport}")
    print(f"Date: {snapshot['metadata']['date_et']}")
    print(f"Build SHA: {snapshot['metadata']['build_sha']}")
    print(f"Content Hash: {snapshot['metadata']['content_hash']}")
    print(f"File: {filepath}")
    print()
    print("Validation:")
    print(f"  Total Picks: {snapshot['validation']['results']['total_picks']}")
    print(f"  Game Picks: {snapshot['validation']['results']['game_picks']}")
    print(f"  Prop Picks: {snapshot['validation']['results']['prop_picks']}")
    print(f"  Schema Violations: {len(snapshot['validation']['results']['schema_violations'])}")
    print(f"  Titanium Violations: {len(snapshot['validation']['results']['titanium_violations'])}")
    print(f"  Weight Reconciliation Issues: {len(snapshot['validation']['results']['weight_reconciliation'])}")
    print()
    if snapshot["validation"]["all_passed"]:
        print("✅ ALL VALIDATIONS PASSED")
    else:
        print("❌ SOME VALIDATIONS FAILED")
        if snapshot['validation']['results']['schema_violations']:
            print("\nSchema violations:")
            for v in snapshot['validation']['results']['schema_violations'][:5]:
                print(f"  {v['pick_id']}: {v['issues']}")
        if snapshot['validation']['results']['titanium_violations']:
            print("\nTitanium violations:")
            for v in snapshot['validation']['results']['titanium_violations']:
                print(f"  {v['pick_id']}: {v['issues']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
