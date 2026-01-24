#!/usr/bin/env python3
"""
Run Pull Cycle v10.73
=====================
Single command to run a complete pick pull cycle.

Usage:
    python3 scripts/run_pull_cycle.py --sport ncaab
    python3 scripts/run_pull_cycle.py --sport nba --force
    python3 scripts/run_pull_cycle.py --sport all

Behavior:
1. Checks readiness gates for the sport
2. Pulls picks via API (or directly if running locally)
3. Validates engine completeness on each pick
4. Outputs community-ready table
5. Saves snapshot for change monitoring
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from pull_readiness import (
    check_readiness,
    ReadinessStatus,
    GateStatus,
    validate_pick_pipeline,
    audit_pick_engines,
    REQUIRED_ENGINES
)
from change_monitor import check_for_changes, get_change_summary, save_snapshot
from pick_schema import normalize_picks, picks_to_table, PickCard

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://web-production-7b2a.up.railway.app")
API_KEY = os.getenv("API_AUTH_KEY", "")

SPORTS = ["nba", "ncaab", "nfl", "mlb", "nhl"]


async def fetch_best_bets(sport: str, debug: bool = True) -> Optional[Dict]:
    """Fetch best bets from the API."""
    url = f"{API_BASE_URL}/live/best-bets/{sport}"
    params = {"debug": 1} if debug else {}

    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"❌ API error: {resp.status_code} - {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None


async def fetch_readiness_data(sport: str) -> Dict:
    """Fetch data needed for readiness checks."""
    headers = {"X-API-Key": API_KEY} if API_KEY else {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch splits, injuries, and games in parallel
        tasks = [
            client.get(f"{API_BASE_URL}/live/splits/{sport}", headers=headers),
            client.get(f"{API_BASE_URL}/live/injuries/{sport}", headers=headers),
            client.get(f"{API_BASE_URL}/live/lines/{sport}", headers=headers),
        ]

        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            splits_data = None
            injury_data = None
            games_data = None

            if not isinstance(responses[0], Exception) and responses[0].status_code == 200:
                splits_resp = responses[0].json()
                splits_data = splits_resp.get("data") or splits_resp.get("splits", [])

            if not isinstance(responses[1], Exception) and responses[1].status_code == 200:
                injury_resp = responses[1].json()
                injury_data = injury_resp.get("data") or injury_resp.get("injuries", [])

            if not isinstance(responses[2], Exception) and responses[2].status_code == 200:
                lines_resp = responses[2].json()
                games_data = lines_resp.get("data") or lines_resp.get("lines", [])

            return {
                "splits_data": splits_data,
                "injury_data": injury_data,
                "games": games_data,
                "total_games": len(games_data) if games_data else 0
            }
        except Exception as e:
            print(f"⚠️ Failed to fetch readiness data: {e}")
            return {}


def print_readiness_report(readiness):
    """Print readiness gates status."""
    print("\n" + "=" * 60)
    print(f"📊 READINESS CHECK: {readiness.sport}")
    print("=" * 60)

    status_emoji = {
        ReadinessStatus.READY: "✅",
        ReadinessStatus.PARTIAL: "⚠️",
        ReadinessStatus.DEFERRED: "⏳",
        ReadinessStatus.NOT_READY: "❌"
    }

    print(f"\nStatus: {status_emoji.get(readiness.status, '?')} {readiness.status.value}")
    print(f"Pull Now: {'YES' if readiness.pull_now else 'NO'}")

    print("\nGates:")
    for gate in readiness.gates:
        gate_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}
        print(f"  {gate_emoji.get(gate.status.value, '?')} {gate.gate_name}: {gate.reason}")

    if readiness.recommended_windows:
        print("\nRecommended Pull Windows (EST):")
        for w in readiness.recommended_windows:
            print(f"  • {w.start_time} - {w.end_time} ({w.label})")

    if readiness.reason_codes:
        print(f"\nReason Codes: {', '.join(readiness.reason_codes)}")


def print_picks_table(picks: List[Dict], sport: str):
    """Print normalized picks table."""
    if not picks:
        print("\n⚠️ No picks to display")
        return

    normalized = normalize_picks(picks, sport)
    table = picks_to_table(normalized)

    print("\n" + "=" * 80)
    print(f"📋 COMMUNITY PICKS: {sport.upper()}")
    print("=" * 80)
    print(table)


def print_engine_audit(picks: List[Dict]):
    """Print engine completeness audit."""
    print("\n" + "-" * 60)
    print("🔧 ENGINE COMPLETENESS AUDIT")
    print("-" * 60)

    complete_count = 0
    incomplete_picks = []

    for pick in picks:
        valid, reason, audit = validate_pick_pipeline(pick)
        if audit.complete:
            complete_count += 1
        else:
            pick_name = pick.get("player_name") or pick.get("selection_name") or pick.get("game", "")[:30]
            incomplete_picks.append((pick_name, audit.engines_missing, audit.completeness_pct))

    total = len(picks)
    pct = (complete_count / max(1, total)) * 100

    print(f"\nComplete: {complete_count}/{total} ({pct:.0f}%)")
    print(f"Required Engines: {', '.join(REQUIRED_ENGINES)}")

    if incomplete_picks:
        print(f"\n⚠️ Incomplete Picks ({len(incomplete_picks)}):")
        for name, missing, pct in incomplete_picks[:5]:
            print(f"  • {name}: missing {', '.join(missing)} ({pct:.0f}% complete)")
        if len(incomplete_picks) > 5:
            print(f"  ... and {len(incomplete_picks) - 5} more")


def print_change_report(report):
    """Print change detection report."""
    if report is None:
        print("\n📝 First pull - no previous snapshot to compare")
        return

    if not report.changes:
        print("\n✅ No significant changes since last pull")
        return

    print("\n" + "-" * 60)
    print("🔄 CHANGES SINCE LAST PULL")
    print("-" * 60)
    print(get_change_summary(report))


async def run_pull_cycle(sport: str, force: bool = False, save: bool = True) -> Dict:
    """
    Run a complete pull cycle for a sport.

    Returns summary dict with results.
    """
    result = {
        "sport": sport.upper(),
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "picks_count": 0,
        "readiness": None,
        "engine_audit": None,
        "changes": None
    }

    # Step 1: Check readiness
    print(f"\n🔍 Checking readiness for {sport.upper()}...")
    readiness_data = await fetch_readiness_data(sport)

    readiness = check_readiness(
        sport=sport,
        injury_data=readiness_data.get("injury_data"),
        splits_data=readiness_data.get("splits_data"),
        games=readiness_data.get("games"),
        total_games=readiness_data.get("total_games", 0)
    )

    print_readiness_report(readiness)
    result["readiness"] = readiness.to_dict()

    # Step 2: Decide whether to pull
    if not readiness.pull_now and not force:
        print(f"\n⏳ Deferring pull. Use --force to override.")
        print(f"   Next check recommended in {readiness.next_check_minutes} minutes")
        return result

    if force and not readiness.pull_now:
        print(f"\n⚠️ Force flag set - pulling despite readiness gates")

    # Step 3: Fetch picks
    print(f"\n📡 Fetching best bets for {sport.upper()}...")
    data = await fetch_best_bets(sport, debug=True)

    if data is None:
        print("❌ Failed to fetch picks")
        return result

    # Combine props and game picks
    props = data.get("props", {}).get("picks", [])
    game_picks = data.get("game_picks", {}).get("picks", [])
    all_picks = props + game_picks

    result["picks_count"] = len(all_picks)

    if not all_picks:
        print("⚠️ No picks returned from API")
        return result

    # Step 4: Engine audit
    print_engine_audit(all_picks)

    complete_count = sum(1 for p in all_picks if validate_pick_pipeline(p)[0])
    result["engine_audit"] = {
        "total": len(all_picks),
        "complete": complete_count,
        "completeness_pct": round((complete_count / max(1, len(all_picks))) * 100, 1)
    }

    # Step 5: Print picks table
    print_picks_table(all_picks, sport)

    # Step 6: Check for changes
    if save:
        change_report = check_for_changes(sport, all_picks)
        print_change_report(change_report)
        if change_report:
            result["changes"] = change_report.to_dict()

    result["success"] = True

    # Step 7: Summary
    print("\n" + "=" * 60)
    print("✅ PULL CYCLE COMPLETE")
    print("=" * 60)
    print(f"Sport: {sport.upper()}")
    print(f"Picks: {len(all_picks)} ({len(props)} props, {len(game_picks)} games)")
    print(f"Engine Completeness: {result['engine_audit']['completeness_pct']}%")
    print(f"Timestamp: {result['timestamp']}")

    return result


async def main():
    parser = argparse.ArgumentParser(description="Run pick pull cycle")
    parser.add_argument("--sport", required=True, help="Sport to pull (nba, ncaab, nfl, mlb, nhl, all)")
    parser.add_argument("--force", action="store_true", help="Force pull even if readiness fails")
    parser.add_argument("--no-save", action="store_true", help="Don't save snapshot")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of formatted text")

    args = parser.parse_args()

    if args.sport.lower() == "all":
        sports = SPORTS
    else:
        sports = [args.sport.lower()]

    results = []
    for sport in sports:
        if sport not in SPORTS:
            print(f"❌ Unknown sport: {sport}")
            continue

        result = await run_pull_cycle(sport, force=args.force, save=not args.no_save)
        results.append(result)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
