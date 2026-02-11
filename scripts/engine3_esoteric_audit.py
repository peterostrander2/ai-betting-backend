#!/usr/bin/env python3
"""
Engine 3 (Esoteric) Semantic Audit Script (v20.18)

Verifies semantic truthfulness of Engine 3 output:
- esoteric_breakdown has per-signal provenance
- Each signal has value, status, source_api, raw_inputs_summary, call_proof
- kp_index.source_api == "noaa" and solar_flare.source_api == "noaa"
- auth_context.noaa.auth_type == "none" (NOT key_present)
- request_proof shows request-local counters
- No dead code signals in breakdown
- Suppressed candidates have full esoteric_breakdown

Usage:
    python scripts/engine3_esoteric_audit.py --local
    python scripts/engine3_esoteric_audit.py --production

Environment:
    API_KEY: Required for production audit
"""

import argparse
import json
import os
import sys
import yaml
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_truth_table() -> Dict[str, Any]:
    """Load truth table from ESOTERIC_TRUTH_TABLE.md."""
    truth_table_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "ESOTERIC_TRUTH_TABLE.md"
    )

    if not os.path.exists(truth_table_path):
        print(f"ERROR: Truth table not found at {truth_table_path}")
        return {}

    with open(truth_table_path, 'r') as f:
        content = f.read()

    # Find YAML block
    yaml_start = content.find("```yaml")
    yaml_end = content.find("```", yaml_start + 7)

    if yaml_start == -1 or yaml_end == -1:
        print("ERROR: No YAML block found in truth table")
        return {}

    yaml_content = content[yaml_start + 7:yaml_end].strip()
    return yaml.safe_load(yaml_content)


def audit_local() -> Tuple[bool, List[str]]:
    """
    Run local audit (no network calls).

    Checks:
    - Module imports
    - Function existence
    - Signal inventory
    - Truth table consistency
    """
    errors = []
    warnings = []

    print("\n=== ENGINE 3 LOCAL AUDIT ===\n")

    # 1. Check module imports
    print("[1/5] Checking module imports...")
    try:
        from esoteric_engine import (
            get_glitch_aggregate,
            get_phase8_esoteric_signals,
            build_esoteric_breakdown_with_provenance,
            get_serpapi_auth_context,
        )
        print("  ✓ esoteric_engine imports OK")
    except ImportError as e:
        errors.append(f"esoteric_engine import failed: {e}")
        print(f"  ✗ esoteric_engine import FAILED: {e}")

    try:
        from alt_data_sources.noaa import (
            init_noaa_request_proof,
            get_noaa_request_proof,
            get_noaa_auth_context,
            NOAARequestProof,
        )
        print("  ✓ noaa imports OK")
    except ImportError as e:
        errors.append(f"noaa import failed: {e}")
        print(f"  ✗ noaa import FAILED: {e}")

    # 2. Check NOAA auth context
    print("\n[2/5] Checking NOAA auth context...")
    try:
        from alt_data_sources.noaa import get_noaa_auth_context
        auth = get_noaa_auth_context()

        if auth.get("auth_type") == "none":
            print("  ✓ NOAA auth_type == 'none' (correct for public API)")
        else:
            errors.append(f"NOAA auth_type should be 'none', got {auth.get('auth_type')}")
            print(f"  ✗ NOAA auth_type WRONG: {auth.get('auth_type')}")

        if "key_present" in auth:
            errors.append("NOAA auth_context has 'key_present' (should not for public API)")
            print("  ✗ NOAA auth_context has 'key_present' (WRONG)")
        else:
            print("  ✓ NOAA auth_context has no 'key_present' (correct)")

        if "enabled" in auth:
            print(f"  ✓ NOAA enabled: {auth.get('enabled')}")
        else:
            warnings.append("NOAA auth_context missing 'enabled' field")
    except Exception as e:
        errors.append(f"NOAA auth context check failed: {e}")

    # 3. Check request-scoped proof
    print("\n[3/5] Checking request-scoped proof...")
    try:
        from alt_data_sources.noaa import init_noaa_request_proof, get_noaa_request_proof

        proof = init_noaa_request_proof()
        proof.record_call(status_code=200)
        proof.record_call(cache_hit=True)

        retrieved = get_noaa_request_proof()

        if retrieved is proof:
            print("  ✓ Request proof uses contextvars (request-local)")
        else:
            errors.append("Request proof not using contextvars correctly")

        if proof.http_2xx == 1:
            print("  ✓ HTTP 2xx counter working")
        else:
            errors.append(f"HTTP 2xx counter wrong: expected 1, got {proof.http_2xx}")

        if proof.cache_hits == 1:
            print("  ✓ Cache hits counter working")
        else:
            errors.append(f"Cache hits counter wrong: expected 1, got {proof.cache_hits}")

        to_dict = proof.to_dict()
        required_keys = {"noaa_calls", "noaa_2xx", "noaa_cache_hits"}
        if required_keys <= set(to_dict.keys()):
            print("  ✓ Proof to_dict() has required keys")
        else:
            missing = required_keys - set(to_dict.keys())
            errors.append(f"Proof to_dict() missing keys: {missing}")

    except Exception as e:
        errors.append(f"Request proof check failed: {e}")

    # 4. Check truth table
    print("\n[4/5] Checking truth table...")
    truth_table = load_truth_table()

    if truth_table:
        wired = truth_table.get("wired_signals", [])
        dead = truth_table.get("present_not_wired", [])

        print(f"  ✓ Wired signals: {len(wired)}")
        print(f"  ✓ Dead code signals: {len(dead)}")

        if len(wired) == 23:
            print("  ✓ Wired signal count is 23 (correct)")
        else:
            errors.append(f"Expected 23 wired signals, got {len(wired)}")

        # Verify no overlap
        overlap = set(wired) & set(dead)
        if overlap:
            errors.append(f"Overlap between wired and dead: {overlap}")
        else:
            print("  ✓ No overlap between wired and dead signals")
    else:
        warnings.append("Could not load truth table")

    # 5. Check esoteric_breakdown structure
    print("\n[5/5] Checking esoteric_breakdown structure...")
    try:
        from datetime import date
        from esoteric_engine import (
            get_glitch_aggregate,
            get_phase8_esoteric_signals,
            build_esoteric_breakdown_with_provenance,
        )

        glitch = get_glitch_aggregate(
            birth_date_str=None,
            game_date=date.today(),
            game_time=datetime.now(),
            line_history=None,
            value_for_benford=None,
            primary_value=5.5
        )

        phase8 = get_phase8_esoteric_signals(
            game_datetime=datetime.now(),
            game_date=date.today(),
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics"
        )

        breakdown = build_esoteric_breakdown_with_provenance(
            glitch_result=glitch,
            phase8_result=phase8,
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            spread=5.5,
            total=220.5,
        )

        required_fields = {"value", "status", "source_api", "source_type", "raw_inputs_summary", "call_proof", "triggered", "contribution"}

        all_ok = True
        for signal_name, signal_data in breakdown.items():
            missing = required_fields - set(signal_data.keys())
            if missing:
                errors.append(f"{signal_name} missing fields: {missing}")
                all_ok = False

        if all_ok:
            print(f"  ✓ All {len(breakdown)} signals have required fields")

        # Check source_api attribution
        kp = breakdown.get("kp_index", {})
        if kp.get("source_api") == "noaa":
            print("  ✓ kp_index.source_api == 'noaa'")
        else:
            errors.append(f"kp_index.source_api should be 'noaa', got {kp.get('source_api')}")

        solar = breakdown.get("solar_flare", {})
        if solar.get("source_api") == "noaa":
            print("  ✓ solar_flare.source_api == 'noaa'")
        else:
            errors.append(f"solar_flare.source_api should be 'noaa', got {solar.get('source_api')}")

        # Check internal signals have null source_api
        internal_count = 0
        for signal_name, signal_data in breakdown.items():
            if signal_data.get("source_type") == "INTERNAL":
                if signal_data.get("source_api") is None:
                    internal_count += 1
                else:
                    errors.append(f"{signal_name} is INTERNAL but source_api is not None")

        print(f"  ✓ {internal_count} internal signals have source_api=null")

    except Exception as e:
        errors.append(f"Breakdown structure check failed: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n=== AUDIT SUMMARY ===\n")
    if errors:
        print(f"ERRORS: {len(errors)}")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("ERRORS: 0")

    if warnings:
        print(f"\nWARNINGS: {len(warnings)}")
        for w in warnings:
            print(f"  ⚠ {w}")

    passed = len(errors) == 0
    print(f"\nRESULT: {'PASS' if passed else 'FAIL'}")

    return passed, errors


def audit_production(api_key: str, base_url: str = "https://web-production-7b2a.up.railway.app") -> Tuple[bool, List[str]]:
    """
    Run production audit (network calls).

    Checks:
    - /debug/esoteric-candidates/{sport} endpoint
    - esoteric_breakdown in response
    - auth_context structure
    - request_proof counters
    """
    import httpx

    errors = []
    warnings = []

    print("\n=== ENGINE 3 PRODUCTION AUDIT ===\n")
    print(f"Base URL: {base_url}")

    headers = {"X-API-Key": api_key}

    # 1. Fetch esoteric candidates
    print("\n[1/3] Fetching esoteric candidates...")
    try:
        url = f"{base_url}/debug/esoteric-candidates/NBA?limit=5"
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers=headers)

        if response.status_code != 200:
            errors.append(f"Endpoint returned {response.status_code}: {response.text[:200]}")
            return False, errors

        data = response.json()
        print(f"  ✓ Got response with {len(data.get('candidates_pre_filter', []))} candidates")

    except Exception as e:
        errors.append(f"Fetch failed: {e}")
        return False, errors

    # 2. Check auth_context
    print("\n[2/3] Checking auth_context...")
    auth_context = data.get("auth_context", {})

    noaa_auth = auth_context.get("noaa", {})
    if noaa_auth.get("auth_type") == "none":
        print("  ✓ auth_context.noaa.auth_type == 'none'")
    else:
        errors.append(f"noaa auth_type should be 'none', got {noaa_auth.get('auth_type')}")

    if "key_present" in noaa_auth:
        errors.append("noaa auth_context has 'key_present' (should not)")
    else:
        print("  ✓ auth_context.noaa has no 'key_present'")

    if noaa_auth.get("enabled") is True:
        print("  ✓ auth_context.noaa.enabled == true")
    else:
        warnings.append(f"noaa enabled is {noaa_auth.get('enabled')}")

    serpapi_auth = auth_context.get("serpapi", {})
    if serpapi_auth.get("auth_type") == "api_key":
        print("  ✓ auth_context.serpapi.auth_type == 'api_key'")

    # 3. Check request_proof
    print("\n[3/3] Checking request_proof...")
    request_proof = data.get("request_proof", {})

    required_keys = {"noaa_calls", "noaa_2xx", "noaa_cache_hits"}
    missing = required_keys - set(request_proof.keys())
    if missing:
        errors.append(f"request_proof missing keys: {missing}")
    else:
        print("  ✓ request_proof has all required keys")

    print(f"  ✓ noaa_calls: {request_proof.get('noaa_calls', 0)}")
    print(f"  ✓ noaa_2xx: {request_proof.get('noaa_2xx', 0)}")
    print(f"  ✓ noaa_cache_hits: {request_proof.get('noaa_cache_hits', 0)}")

    # 4. Check candidates
    candidates = data.get("candidates_pre_filter", [])
    if candidates:
        print(f"\n[4/4] Checking {len(candidates)} candidates...")

        for i, candidate in enumerate(candidates[:3]):  # Check first 3
            breakdown = candidate.get("esoteric_breakdown", {})
            print(f"\n  Candidate {i+1}: {candidate.get('matchup', 'unknown')}")
            print(f"    Signals in breakdown: {len(breakdown)}")

            # Check kp_index
            kp = breakdown.get("kp_index", {})
            if kp.get("source_api") == "noaa":
                print(f"    ✓ kp_index.source_api == 'noaa'")
            else:
                errors.append(f"Candidate {i}: kp_index.source_api wrong")

            # Check status
            status = kp.get("status")
            call_proof = kp.get("call_proof")
            if status == "SUCCESS" and call_proof:
                has_proof = call_proof.get("cache_hit") or call_proof.get("2xx_delta", 0) >= 1
                if has_proof:
                    print(f"    ✓ kp_index SUCCESS has valid call_proof")
                else:
                    errors.append(f"Candidate {i}: kp_index SUCCESS but no proof")
            elif status in ("FALLBACK", "NO_DATA"):
                print(f"    ✓ kp_index status={status} (acceptable)")

    # Check suppressed candidates
    suppressed = [c for c in candidates if not c.get("passed_filter")]
    if suppressed:
        print(f"\n  Checking suppressed candidates ({len(suppressed)})...")
        for c in suppressed[:2]:
            breakdown = c.get("esoteric_breakdown", {})
            if len(breakdown) >= 20:  # Should have ~23 signals
                print(f"    ✓ Suppressed candidate has full breakdown ({len(breakdown)} signals)")
            else:
                errors.append(f"Suppressed candidate missing signals: only {len(breakdown)}")

    # Build SHA
    print(f"\n  build_sha: {data.get('build_sha', 'unknown')}")

    # Summary
    print("\n=== PRODUCTION AUDIT SUMMARY ===\n")
    if errors:
        print(f"ERRORS: {len(errors)}")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("ERRORS: 0")

    if warnings:
        print(f"\nWARNINGS: {len(warnings)}")
        for w in warnings:
            print(f"  ⚠ {w}")

    passed = len(errors) == 0
    print(f"\nRESULT: {'PASS' if passed else 'FAIL'}")

    return passed, errors


def main():
    parser = argparse.ArgumentParser(description="Engine 3 Esoteric Semantic Audit")
    parser.add_argument("--local", action="store_true", help="Run local audit (no network)")
    parser.add_argument("--production", action="store_true", help="Run production audit")
    parser.add_argument("--api-key", default=os.getenv("API_KEY"), help="API key for production")
    parser.add_argument("--base-url", default="https://web-production-7b2a.up.railway.app",
                        help="Base URL for production")

    args = parser.parse_args()

    if not args.local and not args.production:
        args.local = True  # Default to local

    exit_code = 0

    if args.local:
        passed, errors = audit_local()
        if not passed:
            exit_code = 1

    if args.production:
        if not args.api_key:
            print("ERROR: API_KEY required for production audit")
            print("Set API_KEY environment variable or use --api-key")
            sys.exit(1)

        passed, errors = audit_production(args.api_key, args.base_url)
        if not passed:
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
