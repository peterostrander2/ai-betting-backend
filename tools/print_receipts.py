#!/usr/bin/env python3
"""
print_receipts.py - CLI tool to print score receipts for picks

Usage:
    python tools/print_receipts.py --limit 10
    python tools/print_receipts.py --latest
    python tools/print_receipts.py --sport nba --limit 5
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from receipt_schema import (
    build_receipt_from_pick, verify_receipt_completeness, PickReceipt
)


async def fetch_live_picks(sport: str = "nba", limit: int = 10):
    """
    Fetch live picks from the local router.
    Raises an error if the router is unavailable.
    """
    # Import and use the local router
    from live_data_router import get_best_bets
    result = await get_best_bets(sport, debug=1)

    picks = []
    # Extract props
    props = result.get("props", {}).get("picks", [])
    picks.extend(props[:limit])

    # Extract game picks
    game_picks = result.get("game_picks", {}).get("picks", [])
    picks.extend(game_picks[:max(0, limit - len(picks))])

    debug_data = result.get("debug", {})
    return picks[:limit], debug_data


def print_receipt(receipt: PickReceipt, verbose: bool = False):
    """Print a formatted receipt."""
    print("=" * 70)
    print(f"PICK ID: {receipt.pick_id or 'N/A'}")
    print(f"TYPE: {receipt.market_type.upper()} | MARKET: {receipt.market_key}")
    if receipt.player:
        print(f"PLAYER: {receipt.player}")
    print(f"TEAM: {receipt.team} vs {receipt.opponent}")
    print(f"LINE: {receipt.line} @ {receipt.odds}")
    print("-" * 70)

    # Scores
    print(f"RESEARCH SCORE: {receipt.research_score:.2f}")
    print(f"ESOTERIC SCORE: {receipt.esoteric_score:.2f}")
    print(f"ALIGNMENT: {receipt.alignment_pct:.1f}%")
    print(f"CONFLUENCE BOOST: +{receipt.confluence_boost:.2f}")
    print(f"FINAL SCORE: {receipt.final_score:.2f}")
    print("-" * 70)

    # Tier
    print(f"TIER: {receipt.tier.tier} | UNITS: {receipt.tier.units} | ACTION: {receipt.tier.action}")
    print("-" * 70)

    # Reasons
    print("REASONS:")
    for i, reason in enumerate(receipt.reasons_ordered[:10], 1):
        print(f"  {i}. {reason}")

    if verbose:
        print("-" * 70)
        print("VALIDATORS:")
        print(f"  Passed: {receipt.validators.passed}")
        if receipt.validators.drop_reasons:
            print(f"  Drop Reasons: {receipt.validators.drop_reasons}")

        # Models
        print("-" * 70)
        print("MODELS:")
        for name, model in receipt.models.items():
            status = "OK" if model.available else "N/A"
            print(f"  {name}: score={model.score:.2f} [{status}]")

        # Pillars
        print("-" * 70)
        print("PILLARS:")
        for name, pillar in receipt.pillars.items():
            status = "PASS" if pillar.passed else "----"
            print(f"  {name}: {status} (score={pillar.score:.2f})")

    print("=" * 70)
    print()


def verify_and_report(receipt: PickReceipt):
    """Verify receipt completeness and report."""
    is_complete, missing = verify_receipt_completeness(receipt)

    if is_complete:
        print("[PASS] Receipt is complete")
    else:
        print(f"[FAIL] Missing components:")
        for m in missing:
            print(f"  - {m}")

    return is_complete


async def main():
    parser = argparse.ArgumentParser(
        description="Print score receipts for picks"
    )
    parser.add_argument(
        "--sport", "-s",
        type=str,
        default="nba",
        choices=["nba", "nfl", "mlb", "nhl"],
        help="Sport to fetch picks for"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum number of picks to show"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed receipt info"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify receipt completeness"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Save receipts to file"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Show latest picks (same as --limit 10)"
    )

    args = parser.parse_args()

    if args.latest:
        args.limit = 10

    print(f"Fetching {args.limit} picks for {args.sport.upper()}...")
    print()

    picks, debug_data = await fetch_live_picks(args.sport, args.limit)

    if not picks:
        print("No picks found.")
        return

    print(f"Found {len(picks)} picks")
    print()

    receipts = []
    all_complete = True

    for pick in picks:
        receipt = build_receipt_from_pick(pick, debug_data)
        receipts.append(receipt)

        if args.json:
            print(receipt.to_json())
        else:
            print_receipt(receipt, verbose=args.verbose)

        if args.verify:
            if not verify_and_report(receipt):
                all_complete = False
            print()

    if args.save:
        save_path = args.save
        with open(save_path, 'w') as f:
            json.dump(
                [r.to_dict() for r in receipts],
                f,
                indent=2,
                default=str
            )
        print(f"Saved {len(receipts)} receipts to {save_path}")

    if args.verify:
        print()
        if all_complete:
            print("[SUMMARY] All receipts are complete")
        else:
            print("[SUMMARY] Some receipts have missing components")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
