#!/usr/bin/env python3
"""
v10.82: Production Schema Integration Tests

Tests the canonical API contract for /live/best-bets/* endpoints.

Run: python3 test_production_schema.py [--prod]
"""

import sys
import json
import subprocess
from typing import Dict, Any, List, Optional

# Configuration
LOCAL_URL = "http://localhost:8000"
PROD_URL = "https://web-production-7b2a.up.railway.app"
API_KEY = "bookie-prod-2026-xK9mP2nQ7vR4"

# Required fields per pick (MUST ALWAYS EXIST)
PICK_REQUIRED_FIELDS = {
    "pick_id",
    "sport",
    "league",
    "tier",
    "tier_badge",
    "action",
    "final_score",
    "display_title",
    "display_pick",
    "game_time_est",
    "has_started",
    "book_key",
    "book_name",
    "engines",
    "reasons",
}

# Required response-level fields
RESPONSE_REQUIRED_FIELDS = {
    "sport",
    "league",
    "engine_version",
    "api_version",
    "timezone",
    "generated_at_est",
    "today_only_enforced",
    "source",
    "game_picks",
    "props",
}


def curl_json(url: str, headers: Dict[str, str] = None) -> Optional[Dict]:
    """Fetch JSON from URL using curl."""
    cmd = ["curl", "-s", url]
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAIL: curl failed with code {result.returncode}")
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"  FAIL: Invalid JSON - {e}")
        print(f"  Response: {result.stdout[:500]}")
        return None


def check_version_consistency(base_url: str) -> bool:
    """Check that /version and /best-bets return consistent versions."""
    print("\n[1] Version Consistency Check")

    # Get /version
    version_data = curl_json(f"{base_url}/version")
    if not version_data:
        print("  FAIL: Could not fetch /version")
        return False

    version_engine = version_data.get("engine_version")
    version_api = version_data.get("api_version")
    print(f"  /version: engine={version_engine}, api={version_api}")

    # Get /best-bets/nba
    headers = {"X-API-Key": API_KEY}
    bets_data = curl_json(f"{base_url}/live/best-bets/nba", headers)
    if not bets_data:
        print("  FAIL: Could not fetch /best-bets/nba")
        return False

    bets_engine = bets_data.get("engine_version")
    bets_api = bets_data.get("api_version")
    print(f"  /best-bets: engine={bets_engine}, api={bets_api}")

    if version_engine != bets_engine:
        print(f"  FAIL: engine_version mismatch: {version_engine} vs {bets_engine}")
        return False

    if version_api != bets_api:
        print(f"  FAIL: api_version mismatch: {version_api} vs {bets_api}")
        return False

    print("  PASS: Version consistency OK")
    return True


def check_response_fields(data: Dict, sport: str) -> List[str]:
    """Check response-level required fields."""
    missing = []
    for field in RESPONSE_REQUIRED_FIELDS:
        if field not in data:
            missing.append(f"response.{field}")
    return missing


def check_pick_fields(pick: Dict, pick_type: str, idx: int) -> List[str]:
    """Check pick-level required fields."""
    missing = []
    for field in PICK_REQUIRED_FIELDS:
        if field not in pick:
            missing.append(f"{pick_type}[{idx}].{field}")

    # Check book_url exists (can be null but must exist)
    if "book_url" not in pick and "book_link" not in pick:
        missing.append(f"{pick_type}[{idx}].book_url/book_link")

    # Check engines structure
    engines = pick.get("engines", {})
    for eng in ["ai", "research", "esoteric", "jarvis"]:
        if eng not in engines:
            missing.append(f"{pick_type}[{idx}].engines.{eng}")

    return missing


def check_today_only_gate(data: Dict) -> bool:
    """Check today-only filter is enforced."""
    print("\n[3] TODAY-ONLY Gate Check")

    if not data.get("today_only_enforced"):
        print("  FAIL: today_only_enforced is not True")
        return False

    debug = data.get("debug", {})
    time_gate = debug.get("time_gate", {})

    if time_gate:
        print(f"  time_gate: {json.dumps(time_gate)}")
    else:
        print("  WARN: time_gate debug info not present (run with ?debug=1)")

    print("  PASS: today_only_enforced=True")
    return True


def check_no_null_display(data: Dict) -> bool:
    """Check no picks have null display fields."""
    print("\n[4] Display Fields Check")

    null_display = []

    for i, pick in enumerate(data.get("game_picks", {}).get("picks", [])):
        if not pick.get("display_title"):
            null_display.append(f"game_picks[{i}].display_title")
        if not pick.get("display_pick"):
            null_display.append(f"game_picks[{i}].display_pick")

    for i, pick in enumerate(data.get("props", {}).get("picks", [])):
        if not pick.get("display_title"):
            null_display.append(f"props[{i}].display_title")
        if not pick.get("display_pick"):
            null_display.append(f"props[{i}].display_pick")

    if null_display:
        print(f"  FAIL: Null display fields: {null_display[:5]}...")
        return False

    print("  PASS: All picks have display_title and display_pick")
    return True


def check_book_urls(data: Dict) -> bool:
    """Check all picks have book URLs."""
    print("\n[5] Book URL Check")

    missing_book_url = []

    for i, pick in enumerate(data.get("game_picks", {}).get("picks", [])):
        if not pick.get("book_url") and not pick.get("book_link"):
            missing_book_url.append(f"game_picks[{i}]")

    for i, pick in enumerate(data.get("props", {}).get("picks", [])):
        if not pick.get("book_url") and not pick.get("book_link"):
            missing_book_url.append(f"props[{i}]")

    if missing_book_url:
        print(f"  WARN: Missing book URLs: {missing_book_url[:5]}...")
        # Not a hard failure - URLs may be null if not available

    print("  PASS: Book URL check complete")
    return True


def check_has_started(data: Dict) -> bool:
    """Check has_started field exists and is boolean."""
    print("\n[6] has_started Field Check")

    invalid = []

    for i, pick in enumerate(data.get("game_picks", {}).get("picks", [])):
        hs = pick.get("has_started")
        if hs is None or not isinstance(hs, bool):
            invalid.append(f"game_picks[{i}]: {hs}")

    for i, pick in enumerate(data.get("props", {}).get("picks", [])):
        hs = pick.get("has_started")
        if hs is None or not isinstance(hs, bool):
            invalid.append(f"props[{i}]: {hs}")

    if invalid:
        print(f"  FAIL: Invalid has_started values: {invalid[:5]}")
        return False

    print("  PASS: All picks have valid has_started boolean")
    return True


def run_sport_test(base_url: str, sport: str) -> bool:
    """Run full schema test for a sport."""
    print(f"\n{'='*60}")
    print(f"Testing /live/best-bets/{sport}")
    print(f"{'='*60}")

    headers = {"X-API-Key": API_KEY}
    data = curl_json(f"{base_url}/live/best-bets/{sport}?debug=1", headers)

    if not data:
        print(f"FAIL: Could not fetch /best-bets/{sport}")
        return False

    all_passed = True

    # Check response fields
    print("\n[2] Response Fields Check")
    missing = check_response_fields(data, sport)
    if missing:
        print(f"  FAIL: Missing response fields: {missing}")
        all_passed = False
    else:
        print("  PASS: All response fields present")

    # Check pick fields
    print("\n[2b] Pick Fields Check")
    all_missing = []

    for i, pick in enumerate(data.get("game_picks", {}).get("picks", [])[:3]):
        all_missing.extend(check_pick_fields(pick, "game_picks", i))

    for i, pick in enumerate(data.get("props", {}).get("picks", [])[:3]):
        all_missing.extend(check_pick_fields(pick, "props", i))

    if all_missing:
        print(f"  FAIL: Missing pick fields: {all_missing[:10]}")
        all_passed = False
    else:
        print("  PASS: All pick fields present (sampled first 3)")

    # Check today-only gate
    if not check_today_only_gate(data):
        all_passed = False

    # Check display fields
    if not check_no_null_display(data):
        all_passed = False

    # Check book URLs
    if not check_book_urls(data):
        all_passed = False

    # Check has_started
    if not check_has_started(data):
        all_passed = False

    # Print sample picks
    print("\n[7] Sample Output")
    game_picks = data.get("game_picks", {}).get("picks", [])
    if game_picks:
        pick = game_picks[0]
        print(f"  Game Pick Sample:")
        print(f"    pick_id: {pick.get('pick_id')}")
        print(f"    display_title: {pick.get('display_title')}")
        print(f"    display_pick: {pick.get('display_pick')}")
        print(f"    book_url: {pick.get('book_url') or pick.get('book_link')}")
        print(f"    has_started: {pick.get('has_started')}")
        print(f"    action: {pick.get('action')}")
        print(f"    engines: {pick.get('engines')}")

    prop_picks = data.get("props", {}).get("picks", [])
    if prop_picks:
        pick = prop_picks[0]
        print(f"  Prop Pick Sample:")
        print(f"    pick_id: {pick.get('pick_id')}")
        print(f"    display_title: {pick.get('display_title')}")
        print(f"    display_pick: {pick.get('display_pick')}")
        print(f"    prop_stat: {pick.get('prop_stat')}")
        print(f"    direction: {pick.get('direction')}")
        print(f"    book_url: {pick.get('book_url') or pick.get('book_link')}")
        print(f"    has_started: {pick.get('has_started')}")

    return all_passed


def main():
    use_prod = "--prod" in sys.argv
    base_url = PROD_URL if use_prod else LOCAL_URL

    print(f"Production Schema Integration Tests")
    print(f"Target: {base_url}")
    print(f"{'='*60}")

    all_passed = True

    # Version consistency
    if not check_version_consistency(base_url):
        all_passed = False

    # Test NBA
    if not run_sport_test(base_url, "nba"):
        all_passed = False

    # Test NHL
    if not run_sport_test(base_url, "nhl"):
        all_passed = False

    # Summary
    print(f"\n{'='*60}")
    if all_passed:
        print("RESULT: ALL TESTS PASSED")
        return 0
    else:
        print("RESULT: SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
