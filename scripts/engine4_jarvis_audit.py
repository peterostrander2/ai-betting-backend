#!/usr/bin/env python3
"""
Engine 4 Jarvis Audit Script
============================
Runtime audit for Jarvis-Ophis Hybrid Engine v1.1.

Usage:
    python scripts/engine4_jarvis_audit.py --local
    python scripts/engine4_jarvis_audit.py --url https://web-production-7b2a.up.railway.app --sport nba
    python scripts/engine4_jarvis_audit.py --local --output docs/engine4_audit_report.json

Checks:
    1. jarvis_score present and in range [0, 10]
    2. msrf_status == "IN_JARVIS" (not post-base)
    3. jarvis_msrf_component present and <= JARVIS_MSRF_COMPONENT_CAP
    4. jarvis_msrf_component <= jarvis_msrf_component_raw (clamp works)
    5. final_score reconciles within 0.02
    6. msrf_boost == 0.0 in all picks (post-base disabled)
    7. serp_boost == 0.0 and serp_status == "DISABLED"
    8. Engine weights are correct (25/35/20/20)
"""

import argparse
import json
import sys
import os
from datetime import date, datetime
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# LOCAL AUDIT (Synthetic Picks)
# =============================================================================

def run_local_audit() -> Dict[str, Any]:
    """Run audit against local synthetic picks."""
    from core.compute_final_score import (
        compute_final_score_option_a,
        ENGINE_WEIGHTS,
        JARVIS_MSRF_COMPONENT_CAP,
        MSRF_BOOST_CAP,
        SERP_BOOST_CAP_TOTAL,
    )
    from core.jarvis_ophis_hybrid import calculate_hybrid_jarvis_score

    results = {
        "mode": "local",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "errors": [],
        "warnings": [],
        "pass": True,
    }

    # Generate synthetic test picks
    test_cases = [
        {"home_team": "Los Angeles Lakers", "away_team": "Boston Celtics", "sport": "NBA"},
        {"home_team": "New York Rangers", "away_team": "Pittsburgh Penguins", "sport": "NHL"},
        {"home_team": "Dallas Cowboys", "away_team": "Philadelphia Eagles", "sport": "NFL"},
        {"home_team": "Boston Red Sox", "away_team": "New York Yankees", "sport": "MLB"},
        {"home_team": "Duke Blue Devils", "away_team": "North Carolina Tar Heels", "sport": "NCAAB"},
    ]

    # =========================================================================
    # CHECK 1: Jarvis score present and in range
    # =========================================================================
    check1_pass = True
    check1_details = []
    for tc in test_cases:
        jarvis_result = calculate_hybrid_jarvis_score(
            home_team=tc["home_team"],
            away_team=tc["away_team"],
            sport=tc["sport"],
            matchup_date=date.today(),
        )
        js = jarvis_result.get("jarvis_rs")
        if js is None:
            check1_pass = False
            check1_details.append(f"FAIL: {tc['sport']} jarvis_rs is None")
        elif not (0.0 <= js <= 10.0):
            check1_pass = False
            check1_details.append(f"FAIL: {tc['sport']} jarvis_rs={js} out of range")
        else:
            check1_details.append(f"PASS: {tc['sport']} jarvis_rs={js}")

    results["checks"]["jarvis_score_range"] = {
        "pass": check1_pass,
        "details": check1_details,
    }
    if not check1_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 2: msrf_status == "IN_JARVIS"
    # =========================================================================
    check2_pass = True
    check2_details = []
    for tc in test_cases:
        jarvis_result = calculate_hybrid_jarvis_score(
            home_team=tc["home_team"],
            away_team=tc["away_team"],
            sport=tc["sport"],
            matchup_date=date.today(),
        )
        status = jarvis_result.get("msrf_status")
        if status != "IN_JARVIS":
            check2_pass = False
            check2_details.append(f"FAIL: {tc['sport']} msrf_status={status}")
        else:
            check2_details.append(f"PASS: {tc['sport']} msrf_status=IN_JARVIS")

    results["checks"]["msrf_status_in_jarvis"] = {
        "pass": check2_pass,
        "details": check2_details,
    }
    if not check2_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 3: jarvis_msrf_component <= cap
    # =========================================================================
    check3_pass = True
    check3_details = []
    for tc in test_cases:
        jarvis_result = calculate_hybrid_jarvis_score(
            home_team=tc["home_team"],
            away_team=tc["away_team"],
            sport=tc["sport"],
            matchup_date=date.today(),
        )
        msrf_comp = jarvis_result.get("jarvis_msrf_component", 0)
        if msrf_comp > JARVIS_MSRF_COMPONENT_CAP:
            check3_pass = False
            check3_details.append(f"FAIL: {tc['sport']} msrf_component={msrf_comp} > cap={JARVIS_MSRF_COMPONENT_CAP}")
        else:
            check3_details.append(f"PASS: {tc['sport']} msrf_component={msrf_comp}")

    results["checks"]["msrf_component_capped"] = {
        "pass": check3_pass,
        "cap": JARVIS_MSRF_COMPONENT_CAP,
        "details": check3_details,
    }
    if not check3_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 4: jarvis_msrf_component <= jarvis_msrf_component_raw
    # =========================================================================
    check4_pass = True
    check4_details = []
    for tc in test_cases:
        jarvis_result = calculate_hybrid_jarvis_score(
            home_team=tc["home_team"],
            away_team=tc["away_team"],
            sport=tc["sport"],
            matchup_date=date.today(),
        )
        clamped = jarvis_result.get("jarvis_msrf_component", 0)
        raw = jarvis_result.get("jarvis_msrf_component_raw", 0)
        if clamped > raw + 0.001:  # Small tolerance for floating point
            check4_pass = False
            check4_details.append(f"FAIL: {tc['sport']} clamped={clamped} > raw={raw}")
        else:
            check4_details.append(f"PASS: {tc['sport']} clamped={clamped} <= raw={raw}")

    results["checks"]["msrf_clamp_correct"] = {
        "pass": check4_pass,
        "details": check4_details,
    }
    if not check4_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 5: Final score reconciliation
    # =========================================================================
    check5_pass = True
    check5_details = []
    test_scores = [
        (7.0, 7.5, 6.0, 6.5, 0.15, 1.0, 0.5),
        (8.5, 8.2, 8.0, 8.5, 0.3, 3.0, 1.5),
        (5.0, 5.0, 4.0, 4.5, -0.2, 0.0, -1.0),
    ]
    for ai, res, eso, jar, ctx, conf, jason in test_scores:
        r = compute_final_score_option_a(
            ai_score=ai, research_score=res, esoteric_score=eso, jarvis_score=jar,
            context_modifier=ctx, confluence_boost=conf, jason_sim_boost=jason,
        )
        if not r["reconciliation_pass"]:
            check5_pass = False
            check5_details.append(f"FAIL: delta={r['reconciliation_delta']}")
        else:
            check5_details.append(f"PASS: final={r['final_score']} delta={r['reconciliation_delta']}")

    results["checks"]["reconciliation"] = {
        "pass": check5_pass,
        "details": check5_details,
    }
    if not check5_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 6: msrf_boost forced to 0.0
    # =========================================================================
    check6_pass = True
    check6_details = []
    for msrf_input in [0.0, 0.5, 1.0, 999.0]:
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=6.5,
            msrf_boost=msrf_input,
        )
        if r["terms"]["msrf_boost"] != 0.0:
            check6_pass = False
            check6_details.append(f"FAIL: input={msrf_input} → output={r['terms']['msrf_boost']}")
        else:
            check6_details.append(f"PASS: input={msrf_input} → forced to 0.0")

    results["checks"]["msrf_postbase_disabled"] = {
        "pass": check6_pass,
        "cap": MSRF_BOOST_CAP,
        "details": check6_details,
    }
    if not check6_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 7: serp_boost forced to 0.0 and serp_status == "DISABLED"
    # =========================================================================
    check7_pass = True
    check7_details = []
    for serp_input in [0.0, 1.0, 4.3, 100.0]:
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=6.5,
            serp_boost=serp_input,
        )
        if r["terms"]["serp_boost"] != 0.0:
            check7_pass = False
            check7_details.append(f"FAIL: input={serp_input} → output={r['terms']['serp_boost']}")
        elif r["serp_status"] != "DISABLED":
            check7_pass = False
            check7_details.append(f"FAIL: serp_status={r['serp_status']} (expected DISABLED)")
        else:
            check7_details.append(f"PASS: input={serp_input} → forced to 0.0, status=DISABLED")

    results["checks"]["serp_disabled"] = {
        "pass": check7_pass,
        "cap": SERP_BOOST_CAP_TOTAL,
        "details": check7_details,
    }
    if not check7_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK 8: Engine weights correct
    # =========================================================================
    check8_pass = True
    check8_details = []
    expected = {"ai": 0.25, "research": 0.35, "esoteric": 0.20, "jarvis": 0.20}
    for engine, expected_weight in expected.items():
        actual = ENGINE_WEIGHTS.get(engine)
        if actual != expected_weight:
            check8_pass = False
            check8_details.append(f"FAIL: {engine}={actual} (expected {expected_weight})")
        else:
            check8_details.append(f"PASS: {engine}={actual}")

    weight_sum = sum(ENGINE_WEIGHTS.values())
    if abs(weight_sum - 1.0) >= 0.001:
        check8_pass = False
        check8_details.append(f"FAIL: weights sum to {weight_sum} (expected 1.0)")
    else:
        check8_details.append(f"PASS: weights sum to {weight_sum}")

    results["checks"]["engine_weights"] = {
        "pass": check8_pass,
        "weights": ENGINE_WEIGHTS,
        "details": check8_details,
    }
    if not check8_pass:
        results["pass"] = False

    # Summary
    passed = sum(1 for c in results["checks"].values() if c["pass"])
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} checks passed"

    return results


# =============================================================================
# PRODUCTION AUDIT (Live API)
# =============================================================================

def run_production_audit(url: str, sport: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Run audit against production API."""
    import urllib.request
    import urllib.error

    results = {
        "mode": "production",
        "url": url,
        "sport": sport,
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "errors": [],
        "warnings": [],
        "pass": True,
    }

    # Fetch best-bets with debug
    endpoint = f"{url.rstrip('/')}/live/best-bets/{sport}?debug=1"
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        req = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        results["errors"].append(f"HTTP Error {e.code}: {e.reason}")
        results["pass"] = False
        return results
    except Exception as e:
        results["errors"].append(f"Request failed: {str(e)}")
        results["pass"] = False
        return results

    # Collect all picks
    all_picks = []
    if "props" in data and "picks" in data["props"]:
        all_picks.extend(data["props"]["picks"])
    if "game_picks" in data and "picks" in data["game_picks"]:
        all_picks.extend(data["game_picks"]["picks"])

    if not all_picks:
        results["warnings"].append("No picks returned from API")
        results["summary"] = "No picks to audit"
        return results

    # =========================================================================
    # CHECK: jarvis_score present and in range
    # =========================================================================
    check_pass = True
    check_details = []
    for pick in all_picks[:10]:  # Sample first 10
        js = pick.get("jarvis_score") or pick.get("jarvis_rs")
        pick_id = pick.get("pick_id", "unknown")
        if js is None:
            check_pass = False
            check_details.append(f"FAIL: {pick_id} jarvis_score missing")
        elif not (0.0 <= js <= 10.0):
            check_pass = False
            check_details.append(f"FAIL: {pick_id} jarvis_score={js} out of range")
        else:
            check_details.append(f"PASS: {pick_id} jarvis_score={js}")

    results["checks"]["jarvis_score_range"] = {
        "pass": check_pass,
        "sample_size": len(all_picks[:10]),
        "details": check_details,
    }
    if not check_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK: msrf_boost == 0.0
    # =========================================================================
    check_pass = True
    check_details = []
    for pick in all_picks[:10]:
        msrf = pick.get("msrf_boost", 0.0)
        pick_id = pick.get("pick_id", "unknown")
        if msrf != 0.0:
            check_pass = False
            check_details.append(f"FAIL: {pick_id} msrf_boost={msrf} (expected 0.0)")
        else:
            check_details.append(f"PASS: {pick_id} msrf_boost=0.0")

    results["checks"]["msrf_postbase_zero"] = {
        "pass": check_pass,
        "details": check_details,
    }
    if not check_pass:
        results["pass"] = False

    # =========================================================================
    # CHECK: serp_boost == 0.0
    # =========================================================================
    check_pass = True
    check_details = []
    for pick in all_picks[:10]:
        serp = pick.get("serp_boost", 0.0)
        pick_id = pick.get("pick_id", "unknown")
        if serp != 0.0:
            check_pass = False
            check_details.append(f"FAIL: {pick_id} serp_boost={serp} (expected 0.0)")
        else:
            check_details.append(f"PASS: {pick_id} serp_boost=0.0")

    results["checks"]["serp_boost_zero"] = {
        "pass": check_pass,
        "details": check_details,
    }
    if not check_pass:
        results["pass"] = False

    # Summary
    passed = sum(1 for c in results["checks"].values() if c["pass"])
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} checks passed"
    results["picks_audited"] = len(all_picks)

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Engine 4 Jarvis Audit Script")
    parser.add_argument("--local", action="store_true", help="Run local audit with synthetic picks")
    parser.add_argument("--url", type=str, help="Production URL to audit")
    parser.add_argument("--sport", type=str, default="NBA", help="Sport to audit (default: NBA)")
    parser.add_argument("--api-key", type=str, help="API key for production")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    args = parser.parse_args()

    # Get API key from env if not provided
    api_key = args.api_key or os.environ.get("API_KEY")

    if args.local:
        print("Running LOCAL audit (synthetic picks)...")
        results = run_local_audit()
    elif args.url:
        print(f"Running PRODUCTION audit against {args.url} ({args.sport})...")
        results = run_production_audit(args.url, args.sport, api_key)
    else:
        # Default to local
        print("Running LOCAL audit (synthetic picks)...")
        results = run_local_audit()

    # Output results
    print("\n" + "=" * 60)
    print(f"ENGINE 4 JARVIS AUDIT - {results['mode'].upper()}")
    print("=" * 60)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Summary: {results['summary']}")
    print(f"Overall: {'PASS ✓' if results['pass'] else 'FAIL ✗'}")
    print("-" * 60)

    for check_name, check_data in results.get("checks", {}).items():
        status = "✓" if check_data["pass"] else "✗"
        print(f"  [{status}] {check_name}")
        for detail in check_data.get("details", [])[:3]:  # First 3 details
            print(f"      {detail}")

    if results.get("errors"):
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")

    if results.get("warnings"):
        print("\nWarnings:")
        for warning in results["warnings"]:
            print(f"  - {warning}")

    # Save to file if requested
    if args.output:
        output_path = args.output
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    # Exit with appropriate code
    sys.exit(0 if results["pass"] else 1)


if __name__ == "__main__":
    main()
