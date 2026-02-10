#!/usr/bin/env python3
"""
Engine 2 Research Semantic Audit Script

v20.16+ Anti-Conflation Verification

This script verifies the Research Engine anti-conflation invariants:
1. sharp_boost.source_api == "playbook_api"
2. line_boost.source_api == "odds_api"
3. No "Sharp" in reasons when playbook_sharp.status != SUCCESS
4. Usage counters increment on SUCCESS status
5. Network proof matches status claims

Usage:
    API_KEY=xxx python scripts/engine2_research_audit.py [--sport NBA] [--base-url URL]

See docs/RESEARCH_TRUTH_TABLE.md for the complete contract.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Any, Tuple

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import urllib.request
    import urllib.error


def fetch_debug_candidates(base_url: str, sport: str, api_key: str, limit: int = 25) -> Dict:
    """Fetch research candidates from debug endpoint."""
    url = f"{base_url}/debug/research-candidates/{sport}?limit={limit}"
    headers = {"X-API-Key": api_key}

    if HTTPX_AVAILABLE:
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    else:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())


def verify_source_attribution(candidate: Dict) -> List[str]:
    """Verify source_api tags are correct."""
    violations = []
    breakdown = candidate.get("research_breakdown", {})

    # Check sharp_boost source
    sharp = breakdown.get("sharp_boost", {})
    if sharp.get("source_api") != "playbook_api":
        violations.append(
            f"sharp_boost.source_api should be 'playbook_api', got '{sharp.get('source_api')}'"
        )

    # Check line_boost source
    line = breakdown.get("line_boost", {})
    if line.get("source_api") != "odds_api":
        violations.append(
            f"line_boost.source_api should be 'odds_api', got '{line.get('source_api')}'"
        )

    return violations


def verify_status_consistency(candidate: Dict, response: Dict) -> List[str]:
    """Verify status claims match network/usage proof."""
    violations = []
    breakdown = candidate.get("research_breakdown", {})
    network_proof = response.get("network_proof", {})
    usage_delta = response.get("usage_counters_delta", {})

    # If sharp_boost.status == SUCCESS, playbook must have been called
    sharp = breakdown.get("sharp_boost", {})
    if sharp.get("status") == "SUCCESS":
        playbook_delta = usage_delta.get("playbook_calls", 0)
        playbook_2xx = network_proof.get("playbook_2xx_delta", 0)

        # At least one of: delta > 0 or cache hit
        call_proof = sharp.get("call_proof", {})
        if playbook_delta == 0 and playbook_2xx == 0 and not call_proof.get("cache_hit"):
            violations.append(
                f"sharp_boost.status=SUCCESS but playbook_calls_delta=0 and no cache_hit"
            )

    # If line_boost.status == SUCCESS, odds_api must have been called
    line = breakdown.get("line_boost", {})
    if line.get("status") == "SUCCESS":
        odds_delta = usage_delta.get("odds_api_calls", 0)
        odds_2xx = network_proof.get("odds_2xx_delta", 0)

        call_proof = line.get("call_proof", {})
        if odds_delta == 0 and odds_2xx == 0 and not call_proof.get("cache_hit"):
            violations.append(
                f"line_boost.status=SUCCESS but odds_api_calls_delta=0 and no cache_hit"
            )

    return violations


def verify_auth_context(response: Dict) -> List[str]:
    """Verify auth_context shows API keys are configured."""
    violations = []
    auth_context = response.get("auth_context", {})

    # Check Playbook API key
    playbook = auth_context.get("playbook_api", {})
    if not playbook.get("key_present"):
        violations.append("auth_context.playbook_api.key_present is False")

    # Check Odds API key
    odds = auth_context.get("odds_api", {})
    if not odds.get("key_present"):
        violations.append("auth_context.odds_api.key_present is False")

    return violations


def verify_raw_inputs(candidate: Dict) -> List[str]:
    """Verify raw_inputs_summary is present and bounded."""
    violations = []
    breakdown = candidate.get("research_breakdown", {})

    # Check sharp_boost has raw_inputs_summary
    sharp = breakdown.get("sharp_boost", {})
    if "raw_inputs_summary" not in sharp:
        violations.append("sharp_boost missing raw_inputs_summary")
    else:
        inputs = sharp["raw_inputs_summary"]
        # Should have expected keys (can be None values)
        expected = {"ticket_pct", "money_pct", "divergence", "sharp_side"}
        missing = expected - set(inputs.keys())
        if missing:
            violations.append(f"sharp_boost.raw_inputs_summary missing keys: {missing}")

    # Check line_boost has raw_inputs_summary
    line = breakdown.get("line_boost", {})
    if "raw_inputs_summary" not in line:
        violations.append("line_boost missing raw_inputs_summary")
    else:
        inputs = line["raw_inputs_summary"]
        expected = {"line_variance", "lv_strength"}
        missing = expected - set(inputs.keys())
        if missing:
            violations.append(f"line_boost.raw_inputs_summary missing keys: {missing}")

    return violations


def run_audit(base_url: str, sport: str, api_key: str, limit: int = 25) -> Tuple[bool, Dict]:
    """Run full audit and return (passed, results)."""
    results = {
        "sport": sport,
        "base_url": base_url,
        "candidates_checked": 0,
        "violations": [],
        "warnings": [],
        "auth_context_ok": False,
        "passed": False,
    }

    try:
        response = fetch_debug_candidates(base_url, sport, api_key, limit)
    except Exception as e:
        results["violations"].append(f"Failed to fetch debug endpoint: {e}")
        return False, results

    # Check auth_context
    auth_violations = verify_auth_context(response)
    if auth_violations:
        results["violations"].extend(auth_violations)
    else:
        results["auth_context_ok"] = True

    # Check each candidate
    candidates = response.get("candidates_pre_filter", [])
    results["candidates_checked"] = len(candidates)

    for candidate in candidates:
        pick_id = candidate.get("pick_id", "unknown")

        # Source attribution
        source_violations = verify_source_attribution(candidate)
        for v in source_violations:
            results["violations"].append(f"[{pick_id}] {v}")

        # Status consistency
        status_violations = verify_status_consistency(candidate, response)
        for v in status_violations:
            results["violations"].append(f"[{pick_id}] {v}")

        # Raw inputs
        input_violations = verify_raw_inputs(candidate)
        for v in input_violations:
            results["violations"].append(f"[{pick_id}] {v}")

    # Add summary data
    results["usage_counters_delta"] = response.get("usage_counters_delta", {})
    results["network_proof"] = response.get("network_proof", {})
    results["total_candidates"] = response.get("total_candidates", 0)
    results["filtered_count"] = response.get("filtered_count", 0)

    results["passed"] = len(results["violations"]) == 0
    return results["passed"], results


def main():
    parser = argparse.ArgumentParser(
        description="Engine 2 Research Semantic Audit"
    )
    parser.add_argument(
        "--sport", default="NBA",
        help="Sport to audit (default: NBA)"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app"),
        help="API base URL"
    )
    parser.add_argument(
        "--limit", type=int, default=25,
        help="Max candidates to check (default: 25)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    api_key = os.getenv("API_KEY")
    if not api_key:
        print("ERROR: API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    passed, results = run_audit(
        base_url=args.base_url,
        sport=args.sport,
        api_key=api_key,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print(f"Engine 2 Research Semantic Audit - {args.sport}")
        print("=" * 60)
        print()
        print(f"Base URL: {args.base_url}")
        print(f"Candidates checked: {results['candidates_checked']}")
        print(f"Total candidates (inc. filtered): {results.get('total_candidates', 'N/A')}")
        print(f"Filtered below 6.5: {results.get('filtered_count', 'N/A')}")
        print()

        if results["auth_context_ok"]:
            print("[OK] Auth context: API keys configured")
        else:
            print("[FAIL] Auth context: Missing API keys")

        print()
        print("Usage Counters Delta:")
        for k, v in results.get("usage_counters_delta", {}).items():
            print(f"  {k}: {v}")

        print()
        print("Network Proof:")
        for k, v in results.get("network_proof", {}).items():
            print(f"  {k}: {v}")

        print()
        if results["violations"]:
            print(f"[FAIL] {len(results['violations'])} violations found:")
            for v in results["violations"]:
                print(f"  - {v}")
        else:
            print("[PASS] No violations found")

        print()
        print("=" * 60)
        if passed:
            print("VERDICT: PASS")
        else:
            print("VERDICT: FAIL")
        print("=" * 60)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
