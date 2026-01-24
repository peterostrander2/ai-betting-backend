#!/usr/bin/env python3
"""
debug_scorecards.py - Full Scoring Audit Tool
Version: v10.57

Generates itemized SCORECARD for every pick showing exactly how scores were computed,
including JARVIS trace, 8 Pillars, 17 Signals, and 8 AI Models.

Usage:
    python tools/debug_scorecards.py --sport nba
    python tools/debug_scorecards.py --sport all
    python tools/debug_scorecards.py --sport nba --json
"""

import argparse
import asyncio
import json
import os
import sys
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# CONSTANTS
# ============================================================================

SPORTS = ["nba", "nhl", "ncaab"]

# 8 Pillars of Execution
PILLARS = [
    "sharp_split",
    "reverse_line_move",
    "hospital_fade",
    "situational_spot",
    "expert_consensus",
    "prop_correlation",
    "hook_discipline",
    "volume_discipline"
]

# 17 Signals
SIGNALS = [
    "sharp_money",
    "public_fade",
    "reverse_line",
    "line_value",
    "goldilocks_zone",
    "trap_gate",
    "key_number",
    "steam_move",
    "contrarian",
    "closing_line_value",
    "market_efficiency",
    "volume_spike",
    "injury_news",
    "weather_impact",
    "rest_advantage",
    "travel_factor",
    "historical_trend"
]

# 8 AI Models
AI_MODELS = [
    "ensemble_stacking",
    "lstm_neural",
    "matchup_specific",
    "monte_carlo",
    "line_movement",
    "rest_fatigue",
    "injury_impact",
    "betting_edge"
]

# JARVIS Components
JARVIS_COMPONENTS = [
    "gematria",
    "jarvis_triggers",
    "numerology",
    "sacred_geometry",
    "fibonacci",
    "vortex",
    "vedic_astro",
    "planetary_hour"
]

# ============================================================================
# FETCH DATA
# ============================================================================

async def fetch_picks(sport: str) -> Dict[str, Any]:
    """Fetch picks from production API with debug=1."""
    import httpx

    api_key = os.environ.get("API_AUTH_KEY", "")
    base_url = os.environ.get("API_BASE_URL", "https://web-production-7b2a.up.railway.app")

    url = f"{base_url}/live/best-bets/{sport}?debug=1"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers={"X-API-Key": api_key})
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"API Error: {resp.status_code}")
            return {}


def extract_picks_from_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all picks (props + game_picks) from response."""
    picks = []

    # Props
    props = response.get("props", {}).get("picks", [])
    for p in props:
        p["_pick_type"] = "prop"
    picks.extend(props)

    # Game picks
    game_picks = response.get("game_picks", {}).get("picks", [])
    for p in game_picks:
        p["_pick_type"] = "game"
    picks.extend(game_picks)

    return picks


# ============================================================================
# SCORECARD BUILDER
# ============================================================================

def build_scorecard(pick: Dict[str, Any], debug_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build complete scorecard for a single pick."""

    is_prop = pick.get("_pick_type") == "prop"

    # A) Pick Identity
    identity = {
        "sport": pick.get("sport", "?"),
        "matchup": pick.get("matchup", pick.get("game", "?")),
        "market_type": "prop" if is_prop else "game",
        "bet_type": pick.get("stat_type", pick.get("market", "?")),
        "player_name": pick.get("player_name", pick.get("player")) if is_prop else None,
        "stat_type": pick.get("stat_type") if is_prop else None,
        "side": pick.get("over_under", pick.get("side", pick.get("selection", "?"))),
        "line": pick.get("line"),
        "odds": pick.get("odds", -110),
        "book": pick.get("book", pick.get("sportsbook", "draftkings")),
        "pick_id": pick.get("pick_id", pick.get("id", f"{pick.get('player_name', pick.get('team', 'unknown'))}_{pick.get('stat_type', pick.get('market', 'unknown'))}"))
    }

    # B) Raw Inputs
    raw_inputs = {
        "sharp_signal": pick.get("sharp_signal", "NONE"),
        "public_pct": pick.get("public_pct"),
        "line_movement": {
            "open": pick.get("open_line"),
            "current": pick.get("line"),
            "movement": pick.get("line_movement")
        },
        "rest_days": {
            "team": pick.get("team_rest_days"),
            "opponent": pick.get("opp_rest_days")
        },
        "game_total": pick.get("game_total", pick.get("total")),
        "spread": pick.get("spread"),
        "missing_data_flags": []
    }

    # Check for missing data
    if not raw_inputs["sharp_signal"] or raw_inputs["sharp_signal"] == "NONE":
        raw_inputs["missing_data_flags"].append("sharp_signal_missing")
    if raw_inputs["public_pct"] is None:
        raw_inputs["missing_data_flags"].append("public_pct_missing")

    # C) 8 Pillars of Execution
    pillars = {}
    reasons = pick.get("reasons", [])
    scoring_breakdown = pick.get("scoring_breakdown", {})

    for pillar in PILLARS:
        pillar_data = {
            "raw_value": None,
            "passed": False,
            "score": 0.0,
            "contribution": 0.0,
            "source": "reasons"
        }

        # Check if pillar mentioned in reasons
        pillar_pattern = pillar.replace("_", "[ _]")
        for reason in reasons:
            if re.search(pillar_pattern, reason, re.IGNORECASE):
                pillar_data["passed"] = True
                # Try to extract score from reason
                match = re.search(r'[+\-]?(\d+\.?\d*)', reason)
                if match:
                    pillar_data["contribution"] = float(match.group(1))
                break

        pillars[pillar] = pillar_data

    # D) 17 Signals
    signals = {}
    fired_signals = pick.get("fired_signals", [])

    for signal in SIGNALS:
        signal_data = {
            "raw_value": None,
            "normalized": None,
            "weight": None,
            "contribution": 0.0,
            "fired": signal in [s.lower().replace(" ", "_") for s in fired_signals]
        }

        # Check reasons for signal mentions
        signal_pattern = signal.replace("_", "[ _]")
        for reason in reasons:
            if re.search(signal_pattern, reason, re.IGNORECASE):
                signal_data["fired"] = True
                match = re.search(r'[+\-]?(\d+\.?\d*)', reason)
                if match:
                    signal_data["contribution"] = float(match.group(1))
                break

        signals[signal] = signal_data

    # E) 8 AI Models
    ai_models = {}
    ai_breakdown = pick.get("ai_breakdown", {})

    for model in AI_MODELS:
        model_data = {
            "output": None,
            "weight": None,
            "contribution": 0.0,
            "available": True
        }

        # Check ai_breakdown
        if model in ai_breakdown:
            val = ai_breakdown[model]
            if isinstance(val, dict):
                model_data["output"] = val.get("score", val.get("raw"))
                model_data["contribution"] = val.get("contribution", 0)
            else:
                model_data["output"] = val
                model_data["contribution"] = float(val) if val else 0

        # Check reasons for model mentions
        model_pattern = model.replace("_", "[ _]")
        for reason in reasons:
            if re.search(model_pattern, reason, re.IGNORECASE) or "AI ENGINE" in reason:
                match = re.search(r'[+\-]?(\d+\.?\d*)', reason)
                if match:
                    model_data["contribution"] = float(match.group(1))
                break

        ai_models[model] = model_data

    # F) JARVIS SAVANT ENGINE TRACE
    jarvis_trace = build_jarvis_trace(pick)

    # G) Penalties / Adjustments
    penalties = {
        "under_penalty": {
            "applied": pick.get("under_penalty_applied", False),
            "amount": -0.15 if pick.get("under_penalty_applied") else 0,
            "skipped_reason": "game_pick" if not is_prop else None
        },
        "correlation_penalty": pick.get("correlation_penalty", 0),
        "volatility_penalty": 0,
        "missing_data_penalty": 0,
        "dk_board_status": "listed"  # Assume listed if we got this far
    }

    # H) Gate + Filtering Trace
    gates = {
        "publish_gate": {
            "passed": pick.get("publish_gate_passed", True),
            "threshold_used": debug_data.get("publish_gate", {}).get("publish_threshold_edge_lean", 7.05),
            "pick_score": pick.get("smash_score", pick.get("final_score", 0))
        },
        "pick_filter": {
            "passed": True,  # If we're seeing this pick, it passed
            "tier_from_score": pick.get("tier", "?")
        },
        "final_publish_decision": True
    }

    # Build final scorecard
    scorecard = {
        "pick_identity": identity,
        "raw_inputs": raw_inputs,
        "pillars_8": pillars,
        "signals_17": signals,
        "ai_models_8": ai_models,
        "jarvis_trace": jarvis_trace,
        "penalties": penalties,
        "gates": gates,
        "score_summary": {
            "research_score": pick.get("research_score", pick.get("ai_score", 0)),
            "esoteric_score": pick.get("esoteric_score", 0),
            "jarvis_rs": pick.get("jarvis_rs", 0),
            "alignment_pct": pick.get("alignment_pct", 0),
            "confluence_boost": pick.get("confluence_boost", 0),
            "final_score": pick.get("smash_score", pick.get("final_score", 0)),
            "tier": pick.get("tier", "?"),
            "published": True
        },
        "reasons_trace": reasons[:15]  # First 15 reasons for context
    }

    return scorecard


def build_jarvis_trace(pick: Dict[str, Any]) -> Dict[str, Any]:
    """Build detailed JARVIS trace for a pick."""

    esoteric_breakdown = pick.get("esoteric_breakdown", {})
    jarvis_triggers = pick.get("jarvis_triggers", [])
    jarvis_reasons = pick.get("jarvis_reasons", [])
    jarvis_active = pick.get("jarvis_active", False)
    jarvis_rs = pick.get("jarvis_rs", 0)

    # Determine if JARVIS was invoked
    jarvis_invoked = bool(esoteric_breakdown) or jarvis_active or jarvis_rs > 0

    trace = {
        "jarvis_invoked": jarvis_invoked,
        "jarvis_total_contribution": jarvis_rs,
        "jarvis_active": jarvis_active,
        "jarvis_triggers_hit": len(jarvis_triggers),
        "jarvis_turbo_boost": pick.get("jarvis_turbo_boost", 0),
        "jarvis_components": []
    }

    if not jarvis_invoked:
        trace["jarvis_skip_reason"] = determine_jarvis_skip_reason(pick)
        trace["jarvis_expected_path"] = "calculate_gematria_signal() -> calculate_ritual_score()"

    # Build component breakdown
    components = []

    # 1) Gematria
    gematria_score = esoteric_breakdown.get("gematria", 0)
    components.append({
        "name": "gematria",
        "function": "calculate_gematria_signal()",
        "raw_output": gematria_score,
        "normalized": gematria_score,
        "weight": 0.52,
        "contribution": round(gematria_score * 0.52, 3)
    })

    # 2) JARVIS Triggers
    trigger_score = esoteric_breakdown.get("jarvis_triggers", 0)
    trigger_details = []
    for t in jarvis_triggers:
        trigger_details.append({
            "number": t.get("number"),
            "name": t.get("name"),
            "boost": t.get("boost")
        })
    components.append({
        "name": "jarvis_triggers",
        "function": "JARVIS_TRIGGERS lookup",
        "raw_output": trigger_score,
        "triggers_fired": trigger_details,
        "weight": 0.20,
        "contribution": round(trigger_score * 0.20, 3)
    })

    # 3) Fibonacci Alignment
    fib_score = esoteric_breakdown.get("fibonacci", 0)
    components.append({
        "name": "fibonacci_alignment",
        "function": "calculate_fibonacci_alignment()",
        "raw_output": fib_score,
        "weight": 0.05,
        "contribution": round(fib_score * 0.05, 3)
    })

    # 4) Vortex Pattern
    vortex_score = esoteric_breakdown.get("vortex", 0)
    components.append({
        "name": "vortex_pattern",
        "function": "calculate_vortex_pattern()",
        "raw_output": vortex_score,
        "weight": 0.05,
        "contribution": round(vortex_score * 0.05, 3)
    })

    # 5) Vedic Astro
    astro_score = esoteric_breakdown.get("astro", 0)
    components.append({
        "name": "vedic_astro",
        "function": "calculate_astro_score()",
        "raw_output": astro_score,
        "includes": ["planetary_hour", "nakshatra", "moon_phase"],
        "weight": 0.13,
        "contribution": round(astro_score * 0.13, 3)
    })

    # 6) Daily Edge
    edge_score = esoteric_breakdown.get("daily_edge", 0)
    components.append({
        "name": "daily_edge",
        "function": "get_daily_energy()",
        "raw_output": edge_score,
        "weight": 0.05,
        "contribution": round(edge_score * 0.05, 3)
    })

    trace["jarvis_components"] = components
    trace["jarvis_reasons"] = jarvis_reasons

    # Feature flags and thresholds
    trace["jarvis_feature_flags"] = {
        "gematria_enabled": True,
        "vedic_enabled": True,
        "fibonacci_enabled": True,
        "vortex_enabled": True,
        "turbo_enabled": True
    }

    trace["jarvis_thresholds"] = {
        "turbo_gate": 6.50,
        "turbo_rs_min": 6.8,
        "turbo_cap": 0.55,
        "immortal_threshold": 2178
    }

    # Immortal detection
    trace["immortal_detected"] = pick.get("immortal_detected", False)

    return trace


def determine_jarvis_skip_reason(pick: Dict[str, Any]) -> str:
    """Determine why JARVIS might not have been invoked."""

    if not pick.get("player_name") and not pick.get("player"):
        return "game_pick_no_player_for_gematria"

    if pick.get("_pick_type") == "game":
        return "game_pick_limited_jarvis_signals"

    return "unknown_check_jarvis_engine_availability"


# ============================================================================
# OUTPUT FORMATTERS
# ============================================================================

def print_scorecard_text(scorecard: Dict[str, Any], pick_num: int):
    """Print scorecard in human-readable format."""

    identity = scorecard["pick_identity"]
    summary = scorecard["score_summary"]
    jarvis = scorecard["jarvis_trace"]

    print("=" * 80)
    print(f"SCORECARD #{pick_num}")
    print("=" * 80)

    # Identity
    print("\n[A] PICK IDENTITY")
    print("-" * 40)
    print(f"  Sport: {identity['sport']}")
    print(f"  Matchup: {identity['matchup']}")
    print(f"  Type: {identity['market_type'].upper()}")
    if identity['player_name']:
        print(f"  Player: {identity['player_name']}")
    print(f"  Bet: {identity['bet_type']} {identity['side']} {identity['line']}")
    print(f"  Odds: {identity['odds']}")

    # Score Summary
    print("\n[B] SCORE SUMMARY")
    print("-" * 40)
    print(f"  Research Score: {summary['research_score']:.2f}")
    print(f"  Esoteric Score: {summary['esoteric_score']:.2f}")
    print(f"  Jarvis RS: {summary['jarvis_rs']:.2f}")
    print(f"  Alignment: {summary['alignment_pct']:.1f}%")
    print(f"  Confluence Boost: +{summary['confluence_boost']:.2f}")
    print(f"  FINAL SCORE: {summary['final_score']:.2f}")
    print(f"  TIER: {summary['tier']}")

    # JARVIS Trace (REQUIRED)
    print("\n[F] JARVIS SAVANT ENGINE TRACE")
    print("-" * 40)
    print(f"  jarvis_invoked: {jarvis['jarvis_invoked']}")
    print(f"  jarvis_active: {jarvis['jarvis_active']}")
    print(f"  jarvis_total_contribution (jarvis_rs): {jarvis['jarvis_total_contribution']:.2f}")
    print(f"  jarvis_triggers_hit: {jarvis['jarvis_triggers_hit']}")
    print(f"  jarvis_turbo_boost: +{jarvis['jarvis_turbo_boost']:.2f}")
    print(f"  immortal_detected: {jarvis['immortal_detected']}")

    if not jarvis['jarvis_invoked']:
        print(f"  jarvis_skip_reason: {jarvis.get('jarvis_skip_reason', 'N/A')}")
        print(f"  jarvis_expected_path: {jarvis.get('jarvis_expected_path', 'N/A')}")

    print("\n  Components:")
    for comp in jarvis['jarvis_components']:
        contrib = comp.get('contribution', 0)
        raw = comp.get('raw_output', 0)
        print(f"    {comp['name']}: raw={raw:.2f}, weight={comp.get('weight', 0)}, contrib={contrib:.3f}")
        if comp.get('triggers_fired'):
            for t in comp['triggers_fired']:
                print(f"      -> Trigger {t['number']} ({t['name']}) boost={t['boost']}")

    if jarvis['jarvis_reasons']:
        print("\n  Jarvis Reasons:")
        for r in jarvis['jarvis_reasons'][:5]:
            print(f"    - {r}")

    # Pillars (condensed)
    print("\n[C] 8 PILLARS OF EXECUTION")
    print("-" * 40)
    pillars = scorecard["pillars_8"]
    for name, data in pillars.items():
        status = "PASS" if data['passed'] else "----"
        contrib = data['contribution']
        print(f"  {name}: [{status}] +{contrib:.2f}")

    # AI Models (condensed)
    print("\n[E] 8 AI MODELS")
    print("-" * 40)
    models = scorecard["ai_models_8"]
    for name, data in models.items():
        contrib = data['contribution']
        print(f"  {name}: +{contrib:.2f}")

    # Gates
    print("\n[H] GATE + FILTERING TRACE")
    print("-" * 40)
    gates = scorecard["gates"]
    pg = gates["publish_gate"]
    print(f"  publish_gate: {'PASS' if pg['passed'] else 'FAIL'} (threshold={pg['threshold_used']}, score={pg['pick_score']:.2f})")
    print(f"  pick_filter: {'PASS' if gates['pick_filter']['passed'] else 'FAIL'}")
    print(f"  tier_from_score: {gates['pick_filter']['tier_from_score']}")

    # Reasons trace
    print("\n[I] REASONS TRACE")
    print("-" * 40)
    for r in scorecard["reasons_trace"][:10]:
        print(f"  {r}")

    print()


def print_scorecard_json(scorecard: Dict[str, Any]):
    """Print scorecard as JSONL."""
    print(json.dumps(scorecard, indent=None, default=str))


# ============================================================================
# MAIN
# ============================================================================

async def audit_sport(sport: str, output_json: bool = False) -> List[Dict[str, Any]]:
    """Run full audit for a single sport."""

    print(f"\n{'='*80}")
    print(f"SCORING AUDIT: {sport.upper()}")
    print(f"{'='*80}")

    # Fetch data
    response = await fetch_picks(sport)
    picks = extract_picks_from_response(response)
    debug_data = response.get("debug", {})

    if not picks:
        print(f"No picks found for {sport}")
        return []

    print(f"Found {len(picks)} picks")

    # Build scorecards
    scorecards = []
    for i, pick in enumerate(picks, 1):
        scorecard = build_scorecard(pick, debug_data)
        scorecards.append(scorecard)

        if output_json:
            print_scorecard_json(scorecard)
        else:
            print_scorecard_text(scorecard, i)

    return scorecards


async def main():
    parser = argparse.ArgumentParser(description="Full Scoring Audit Tool")
    parser.add_argument(
        "--sport", "-s",
        type=str,
        default="all",
        help="Sport to audit (nba, nhl, ncaab, or all)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSONL"
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Save output to file"
    )

    args = parser.parse_args()

    sports = SPORTS if args.sport.lower() == "all" else [args.sport.lower()]

    all_scorecards = []

    for sport in sports:
        if sport not in SPORTS:
            print(f"Unknown sport: {sport}")
            continue

        scorecards = await audit_sport(sport, args.json)
        all_scorecards.extend(scorecards)

    # Summary
    if not args.json:
        print("\n" + "=" * 80)
        print("AUDIT SUMMARY")
        print("=" * 80)
        print(f"Total picks audited: {len(all_scorecards)}")

        # JARVIS stats
        jarvis_invoked = sum(1 for s in all_scorecards if s['jarvis_trace']['jarvis_invoked'])
        jarvis_active = sum(1 for s in all_scorecards if s['jarvis_trace']['jarvis_active'])
        immortal_count = sum(1 for s in all_scorecards if s['jarvis_trace']['immortal_detected'])

        print(f"JARVIS invoked: {jarvis_invoked}/{len(all_scorecards)}")
        print(f"JARVIS active (triggers hit): {jarvis_active}/{len(all_scorecards)}")
        print(f"Immortal (2178) detected: {immortal_count}")

        # Tier breakdown
        tiers = {}
        for s in all_scorecards:
            tier = s['score_summary']['tier']
            tiers[tier] = tiers.get(tier, 0) + 1
        print(f"Tiers: {tiers}")

    # Save if requested
    if args.save:
        with open(args.save, 'w') as f:
            for sc in all_scorecards:
                f.write(json.dumps(sc, default=str) + "\n")
        print(f"\nSaved {len(all_scorecards)} scorecards to {args.save}")


if __name__ == "__main__":
    asyncio.run(main())
