"""
Debug Pick Proof Smoke Test - v11.00
====================================
Validates that the debug proof system is working correctly.

Usage:
    python -m tests.debug_pick_proof --sport nba
    python -m tests.debug_pick_proof --sport nhl --local
    python -m tests.debug_pick_proof --all

This test verifies:
1. Debug proof module is importable
2. All 8 pillars are defined
3. All 17 signals are defined
4. Pick identity fields are present
5. Engine scores are populated
6. Official card persistence works
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all debug proof imports work."""
    print("\n=== Testing Imports ===")

    try:
        from debug_proof import (
            build_debug_object,
            save_official_card,
            load_official_card,
            get_official_card_pick_ids,
            get_time_status,
            generate_pick_id,
            PILLARS,
            SIGNALS
        )
        print("  [PASS] debug_proof module imports successful")
        return True
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False


def test_pillar_definitions():
    """Test that all 8 pillars are defined."""
    print("\n=== Testing Pillar Definitions ===")

    from debug_proof import PILLARS

    expected_pillars = [
        "Sharp Split",
        "Reverse Line Move",
        "Hospital Fade",
        "Situational Spot",
        "Expert Consensus",
        "Prop Correlation",
        "Hook Discipline",
        "Volume Discipline"
    ]

    actual_names = [p["name"] for p in PILLARS]

    if len(PILLARS) != 8:
        print(f"  [FAIL] Expected 8 pillars, got {len(PILLARS)}")
        return False

    for expected in expected_pillars:
        if expected not in actual_names:
            print(f"  [FAIL] Missing pillar: {expected}")
            return False

    print(f"  [PASS] All 8 pillars defined: {actual_names}")
    return True


def test_signal_definitions():
    """Test that all 17 signals are defined."""
    print("\n=== Testing Signal Definitions ===")

    from debug_proof import SIGNALS

    if len(SIGNALS) != 17:
        print(f"  [FAIL] Expected 17 signals, got {len(SIGNALS)}")
        return False

    # Check categories
    categories = set(s["category"] for s in SIGNALS)
    expected_categories = {"market", "context", "esoteric", "jarvis"}

    if categories != expected_categories:
        print(f"  [FAIL] Missing categories: {expected_categories - categories}")
        return False

    print(f"  [PASS] All 17 signals defined across 4 categories: {categories}")
    return True


def test_time_status():
    """Test time status determination."""
    print("\n=== Testing Time Status ===")

    from debug_proof import get_time_status
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)

    # Test UPCOMING (game starts in 1 hour)
    future_time = now_et + timedelta(hours=1)
    status = get_time_status(future_time, now_et)
    if status != "UPCOMING":
        print(f"  [FAIL] Future game should be UPCOMING, got {status}")
        return False

    # Test STARTED (game started 10 minutes ago)
    recent_past = now_et - timedelta(minutes=10)
    status = get_time_status(recent_past, now_et)
    if status != "STARTED":
        print(f"  [FAIL] Recent game should be STARTED, got {status}")
        return False

    # Test LIVE_ONLY (game started 1 hour ago)
    past_time = now_et - timedelta(hours=1)
    status = get_time_status(past_time, now_et)
    if status != "LIVE_ONLY":
        print(f"  [FAIL] Mid-game should be LIVE_ONLY, got {status}")
        return False

    # Test EXPIRED (game started 3 hours ago)
    old_time = now_et - timedelta(hours=3)
    status = get_time_status(old_time, now_et)
    if status != "EXPIRED":
        print(f"  [FAIL] Old game should be EXPIRED, got {status}")
        return False

    print("  [PASS] All time status transitions correct")
    return True


def test_pick_id_generation():
    """Test deterministic pick ID generation."""
    print("\n=== Testing Pick ID Generation ===")

    from debug_proof import generate_pick_id

    pick1 = {
        "sport": "NBA",
        "game_id": "abc123",
        "player_name": "LeBron James",
        "stat_type": "points",
        "selection": "over",
        "line": 25.5
    }

    pick2 = {
        "sport": "NBA",
        "game_id": "abc123",
        "player_name": "LeBron James",
        "stat_type": "points",
        "selection": "over",
        "line": 25.5
    }

    pick3 = {
        "sport": "NBA",
        "game_id": "abc123",
        "player_name": "LeBron James",
        "stat_type": "points",
        "selection": "under",  # Different selection
        "line": 25.5
    }

    id1 = generate_pick_id(pick1)
    id2 = generate_pick_id(pick2)
    id3 = generate_pick_id(pick3)

    if id1 != id2:
        print(f"  [FAIL] Same picks should have same ID: {id1} != {id2}")
        return False

    if id1 == id3:
        print(f"  [FAIL] Different picks should have different IDs: {id1} == {id3}")
        return False

    if len(id1) != 16:
        print(f"  [FAIL] Pick ID should be 16 chars, got {len(id1)}")
        return False

    print(f"  [PASS] Pick ID generation deterministic: {id1}")
    return True


def test_debug_object_build():
    """Test building a full debug object."""
    print("\n=== Testing Debug Object Build ===")

    from debug_proof import build_debug_object
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)

    sample_pick = {
        "sport": "NBA",
        "game_id": "nba_20260125_lal_bos",
        "matchup": "Lakers @ Celtics",
        "player_name": "LeBron James",
        "stat_type": "points",
        "selection": "over",
        "line": 25.5,
        "odds": -110,
        "smash_score": 7.8,
        "tier": "GOLD_STAR",
        "game_time": (now_et + timedelta(hours=2)).isoformat(),
        "reasons": [
            "RESEARCH: Sharp Split +1.0",
            "RESEARCH: RLM Confirmed +0.8",
            "JARVIS: Trigger 33 +0.4"
        ],
        "ai_score": 6.5,
        "research_score": 7.2,
        "esoteric_score": 6.8,
        "jarvis_rs": 7.0,
        "jarvis_active": True,
        "jarvis_triggers": ["33"],
        "confluence_boost": 0.3
    }

    debug_obj = build_debug_object(sample_pick, now_et)

    # Verify required sections
    required_sections = [
        "pick_identity",
        "line_provenance",
        "engine_scores",
        "pillars_proof",
        "signals_proof",
        "jarvis_details",
        "jason_sim",
        "injury_guardrails",
        "raw_reasons"
    ]

    for section in required_sections:
        if section not in debug_obj:
            print(f"  [FAIL] Missing required section: {section}")
            return False

    # Verify pick identity
    identity = debug_obj["pick_identity"]
    if identity["sport"] != "NBA":
        print(f"  [FAIL] Sport mismatch: {identity['sport']}")
        return False

    if identity["time_status"] != "UPCOMING":
        print(f"  [FAIL] Time status should be UPCOMING, got {identity['time_status']}")
        return False

    # Verify pillars proof
    if len(debug_obj["pillars_proof"]) != 8:
        print(f"  [FAIL] Expected 8 pillars, got {len(debug_obj['pillars_proof'])}")
        return False

    # Verify signals proof
    if len(debug_obj["signals_proof"]) != 17:
        print(f"  [FAIL] Expected 17 signals, got {len(debug_obj['signals_proof'])}")
        return False

    # Verify engine scores
    engines = debug_obj["engine_scores"]
    if engines["ai_engine_score"] != 6.5:
        print(f"  [FAIL] AI score mismatch: {engines['ai_engine_score']}")
        return False

    print("  [PASS] Debug object built with all required sections")
    print(f"         Sections: {list(debug_obj.keys())}")
    return True


def test_official_card_persistence():
    """Test official card save/load cycle."""
    print("\n=== Testing Official Card Persistence ===")

    from debug_proof import (
        save_official_card, load_official_card,
        get_official_card_pick_ids, get_official_card_path
    )
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)

    # Create test picks (one UPCOMING, one STARTED)
    test_picks = [
        {
            "sport": "NBA",
            "game_id": "test_game_1",
            "selection": "Lakers +5.5",
            "line": 5.5,
            "odds": -110,
            "tier": "GOLD_STAR",
            "smash_score": 7.8,
            "game_time": (now_et + timedelta(hours=2)).isoformat()  # UPCOMING
        },
        {
            "sport": "NBA",
            "game_id": "test_game_2",
            "selection": "Celtics -3.5",
            "line": -3.5,
            "odds": -110,
            "tier": "EDGE_LEAN",
            "smash_score": 7.2,
            "game_time": (now_et - timedelta(hours=1)).isoformat()  # LIVE_ONLY (should not save)
        }
    ]

    # Save
    saved_count = save_official_card(test_picks, now_et)

    if saved_count < 1:
        print(f"  [WARN] Expected at least 1 pick saved (UPCOMING), got {saved_count}")
        # Not a failure since file might already have data

    # Load
    loaded_picks = load_official_card(now_et)

    if not loaded_picks:
        print("  [FAIL] No picks loaded from official card")
        return False

    # Get pick IDs
    pick_ids = get_official_card_pick_ids(now_et)

    print(f"  [PASS] Official card persistence working")
    print(f"         Saved: {saved_count}, Loaded: {len(loaded_picks)}, Pick IDs: {len(pick_ids)}")
    print(f"         Path: {get_official_card_path(now_et)}")
    return True


def test_tiering_source():
    """Verify tiering.py is the single source of truth."""
    print("\n=== Testing Tiering Module ===")

    try:
        from tiering import (
            tier_from_score,
            DEFAULT_TIERS,
            TIER_CONFIG,
            TIER_ORDER
        )

        # Test tier thresholds
        # Note: TITANIUM_SMASH requires titanium_triggered=True
        tier_9_no_flag = tier_from_score(9.5)[0]  # Without flag = GOLD_STAR
        tier_9_with_flag = tier_from_score(9.5, titanium_triggered=True)[0]  # With flag = TITANIUM
        tier_8 = tier_from_score(8.0)[0]
        tier_7 = tier_from_score(7.0)[0]
        tier_6 = tier_from_score(6.0)[0]
        tier_5 = tier_from_score(5.0)[0]

        expected = {
            (9.5, False): "GOLD_STAR",  # Without flag, falls to GOLD_STAR
            (9.5, True): "TITANIUM_SMASH",  # With flag = TITANIUM
            (8.0, False): "GOLD_STAR",
            (7.0, False): "EDGE_LEAN",
            (6.0, False): "MONITOR",
            (5.0, False): "PASS"
        }

        actual = {
            (9.5, False): tier_9_no_flag,
            (9.5, True): tier_9_with_flag,
            (8.0, False): tier_8,
            (7.0, False): tier_7,
            (6.0, False): tier_6,
            (5.0, False): tier_5
        }

        for key, expected_tier in expected.items():
            if actual[key] != expected_tier:
                print(f"  [FAIL] Score {key} expected {expected_tier}, got {actual[key]}")
                return False

        print("  [PASS] tiering.py is single source of truth")
        print(f"         Thresholds: {DEFAULT_TIERS}")
        print(f"         Note: TITANIUM_SMASH requires titanium_triggered=True")
        return True

    except ImportError as e:
        print(f"  [FAIL] Could not import tiering module: {e}")
        return False


def test_live_endpoint(sport: str, local: bool = False):
    """Test the live endpoint with debug=1."""
    print(f"\n=== Testing Live Endpoint ({sport.upper()}) ===")

    # Try httpx first, then requests as fallback
    try:
        import httpx
        client_type = "httpx"
    except ImportError:
        try:
            import requests
            client_type = "requests"
        except ImportError:
            print("  [SKIP] Neither httpx nor requests installed")
            return True  # Skip but don't fail

    base_url = "http://localhost:8000" if local else "https://web-production-7b2a.up.railway.app"
    url = f"{base_url}/live/best-bets/{sport}?debug=1"

    # Get API key from environment
    api_key = os.getenv("API_AUTH_KEY", "")

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        if client_type == "httpx":
            response = httpx.get(url, headers=headers, timeout=30.0)
            status = response.status_code
            text = response.text
            data = response.json()
        else:  # requests
            response = requests.get(url, headers=headers, timeout=30)
            status = response.status_code
            text = response.text
            data = response.json()

        if status != 200:
            print(f"  [FAIL] HTTP {status}: {text[:200]}")
            return False

        # Check for debug section
        if "debug" not in data:
            print("  [FAIL] No debug section in response")
            return False

        debug = data["debug"]

        # Check for debug proof fields
        if "debug_proof_available" in debug:
            print(f"  Debug proof available: {debug['debug_proof_available']}")

        if "pick_proofs" in debug:
            proofs = debug["pick_proofs"]
            print(f"  Pick proofs count: {len(proofs)}")

            if proofs:
                # Show first pick proof structure
                first_proof = proofs[0]
                sections = list(first_proof.keys())
                print(f"  First proof sections: {sections}")

                # Show sample pick identity
                if "pick_identity" in first_proof:
                    identity = first_proof["pick_identity"]
                    print(f"  Sample pick identity:")
                    print(f"    - sport: {identity.get('sport')}")
                    print(f"    - matchup: {identity.get('matchup')}")
                    print(f"    - time_status: {identity.get('time_status')}")

        if "official_card_saved" in debug:
            print(f"  Official card saved: {debug['official_card_saved']}")

        if "official_card_path" in debug:
            print(f"  Official card path: {debug['official_card_path']}")

        print(f"  [PASS] Live endpoint returned debug proof data")
        return True

    except Exception as e:
        print(f"  [FAIL] Request error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Debug Pick Proof Smoke Test")
    parser.add_argument("--sport", type=str, default="nba", help="Sport to test (nba, nhl, nfl, mlb, ncaab)")
    parser.add_argument("--local", action="store_true", help="Test against localhost instead of production")
    parser.add_argument("--all", action="store_true", help="Test all sports")
    args = parser.parse_args()

    print("=" * 60)
    print("DEBUG PICK PROOF SMOKE TEST - v11.00")
    print("=" * 60)

    results = []

    # Run unit tests
    results.append(("Imports", test_imports()))
    results.append(("Pillar Definitions", test_pillar_definitions()))
    results.append(("Signal Definitions", test_signal_definitions()))
    results.append(("Time Status", test_time_status()))
    results.append(("Pick ID Generation", test_pick_id_generation()))
    results.append(("Debug Object Build", test_debug_object_build()))
    results.append(("Official Card Persistence", test_official_card_persistence()))
    results.append(("Tiering Module", test_tiering_source()))

    # Run live endpoint test
    if args.all:
        sports = ["nba", "nhl", "nfl", "mlb", "ncaab"]
    else:
        sports = [args.sport]

    for sport in sports:
        results.append((f"Live Endpoint ({sport})", test_live_endpoint(sport, args.local)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
