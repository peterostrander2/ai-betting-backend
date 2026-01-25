"""
Debug Proof Module v11.00
=========================
Production-ready debug output for pick verification.
Provides auditable, deterministic proof per pick.

Every pick MUST show:
- Pick Identity (game, time, status)
- Sportsbook + Line Provenance
- 4-Engine Scores (AI, Research, Esoteric, Jarvis)
- All 8 Pillars (fired status, delta, evidence)
- All 17 Signals (fired status, delta, evidence)
- Jarvis Details
- Jason Sim Confluence
- Injury + Availability Guardrails
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

from time_filters import get_now_et, parse_to_et, get_today_et

ET = ZoneInfo("America/New_York")

# =============================================================================
# PILLAR DEFINITIONS - All 8 Pillars
# =============================================================================

PILLARS = [
    {"id": 1, "name": "Sharp Split", "key": "sharp_split"},
    {"id": 2, "name": "Reverse Line Move", "key": "rlm"},
    {"id": 3, "name": "Hospital Fade", "key": "hospital_fade"},
    {"id": 4, "name": "Situational Spot", "key": "situational_spot"},
    {"id": 5, "name": "Expert Consensus", "key": "expert_consensus"},
    {"id": 6, "name": "Prop Correlation", "key": "prop_correlation"},
    {"id": 7, "name": "Hook Discipline", "key": "hook_discipline"},
    {"id": 8, "name": "Volume Discipline", "key": "volume_discipline"},
]

# =============================================================================
# SIGNAL DEFINITIONS - All 17 Signals
# =============================================================================

SIGNALS = [
    # Market Signals (1-6)
    {"id": 1, "name": "Sharp Money Flow", "category": "market"},
    {"id": 2, "name": "Reverse Line Movement", "category": "market"},
    {"id": 3, "name": "Public Fade Opportunity", "category": "market"},
    {"id": 4, "name": "Steam Move Detected", "category": "market"},
    {"id": 5, "name": "Line Value Edge", "category": "market"},
    {"id": 6, "name": "Book Disagreement", "category": "market"},
    # Context Signals (7-11)
    {"id": 7, "name": "Home Court Advantage", "category": "context"},
    {"id": 8, "name": "Rest Advantage", "category": "context"},
    {"id": 9, "name": "Injury Impact", "category": "context"},
    {"id": 10, "name": "Pace Mismatch", "category": "context"},
    {"id": 11, "name": "Defensive Matchup", "category": "context"},
    # Esoteric Signals (12-15)
    {"id": 12, "name": "Vedic Astrology Alignment", "category": "esoteric"},
    {"id": 13, "name": "Fibonacci Pattern", "category": "esoteric"},
    {"id": 14, "name": "Vortex Energy", "category": "esoteric"},
    {"id": 15, "name": "Daily Energy Flow", "category": "esoteric"},
    # Jarvis Signals (16-17)
    {"id": 16, "name": "Gematria Trigger", "category": "jarvis"},
    {"id": 17, "name": "Sacred Number Hit", "category": "jarvis"},
]

# =============================================================================
# TIME STATUS HELPERS
# =============================================================================

def get_time_status(start_time_et: Optional[datetime], now_et: Optional[datetime] = None) -> str:
    """
    Determine time status for a pick.

    Returns:
        UPCOMING: Game hasn't started (can be on Official Card)
        STARTED: Game started within last 30 min (Live-only)
        LIVE_ONLY: Game in progress but still bettable live
        EXPIRED: Game too far along or finished
    """
    if now_et is None:
        now_et = get_now_et()

    if start_time_et is None:
        return "UNKNOWN"

    # Ensure both are timezone-aware
    if start_time_et.tzinfo is None:
        start_time_et = start_time_et.replace(tzinfo=ET)

    diff_minutes = (now_et - start_time_et).total_seconds() / 60

    if diff_minutes < -5:
        return "UPCOMING"
    elif diff_minutes < 30:
        return "STARTED"
    elif diff_minutes < 120:  # Within 2 hours
        return "LIVE_ONLY"
    else:
        return "EXPIRED"


def generate_pick_id(pick: Dict[str, Any]) -> str:
    """Generate stable hash ID for a pick."""
    # Create deterministic string from key fields
    key_parts = [
        str(pick.get("sport", "")),
        str(pick.get("game_id", "")),
        str(pick.get("player_name", "") or ""),
        str(pick.get("stat_type", "") or pick.get("market", "")),
        str(pick.get("selection", "") or pick.get("pick", "")),
        str(pick.get("line", "")),
    ]
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]


# =============================================================================
# PILLAR PROOF BUILDER
# =============================================================================

def build_pillar_proof(
    pick: Dict[str, Any],
    reasons: List[str],
    sharp_data: Optional[Dict] = None,
    injuries_data: Optional[List] = None
) -> List[Dict[str, Any]]:
    """
    Build proof for all 8 pillars.

    Returns list of pillar objects with:
    - name: Pillar name
    - fired: bool (did this pillar contribute?)
    - delta: float (how much did it add/subtract?)
    - evidence_string: Human-readable evidence
    """
    pillars_proof = []
    reasons_lower = [r.lower() for r in reasons]
    reasons_text = " ".join(reasons)

    # 1. Sharp Split
    sharp_fired = any("sharp split" in r or "sharp money" in r for r in reasons_lower)
    sharp_delta = 0.0
    sharp_evidence = "No sharp divergence detected"
    if sharp_fired:
        for r in reasons:
            if "Sharp" in r and "+" in r:
                try:
                    sharp_delta = float(r.split("+")[-1])
                except:
                    sharp_delta = 1.0
                sharp_evidence = r
                break
    pillars_proof.append({
        "name": "Sharp Split",
        "fired": sharp_fired,
        "delta": sharp_delta,
        "evidence_string": sharp_evidence
    })

    # 2. Reverse Line Move
    rlm_fired = any("rlm" in r or "reverse line" in r for r in reasons_lower)
    rlm_delta = 0.0
    rlm_evidence = "No reverse line movement detected"
    if rlm_fired:
        for r in reasons:
            if "RLM" in r or "Reverse Line" in r:
                if "+" in r:
                    try:
                        rlm_delta = float(r.split("+")[-1])
                    except:
                        rlm_delta = 1.0
                rlm_evidence = r
                break
    pillars_proof.append({
        "name": "Reverse Line Move",
        "fired": rlm_fired,
        "delta": rlm_delta,
        "evidence_string": rlm_evidence
    })

    # 3. Hospital Fade
    hospital_fired = any("hospital" in r or "injury" in r for r in reasons_lower)
    hospital_delta = 0.0
    hospital_evidence = "No significant opponent injuries"
    if hospital_fired:
        for r in reasons:
            if "Hospital" in r or "Injury" in r:
                if "+" in r:
                    try:
                        hospital_delta = float(r.split("+")[-1])
                    except:
                        hospital_delta = 0.25
                hospital_evidence = r
                break
    pillars_proof.append({
        "name": "Hospital Fade",
        "fired": hospital_fired,
        "delta": hospital_delta,
        "evidence_string": hospital_evidence
    })

    # 4. Situational Spot
    spot_fired = any("situational" in r or "rest" in r or "b2b" in r or "home court" in r for r in reasons_lower)
    spot_delta = 0.0
    spot_evidence = "No situational advantage"
    for r in reasons:
        if "Rest" in r or "Home Court" in r or "Situational" in r or "B2B" in r:
            if "+" in r:
                try:
                    spot_delta += float(r.split("+")[-1])
                except:
                    spot_delta += 0.2
            elif "-" in r:
                try:
                    spot_delta -= float(r.split("-")[-1])
                except:
                    spot_delta -= 0.2
            spot_evidence = r
            spot_fired = True
    pillars_proof.append({
        "name": "Situational Spot",
        "fired": spot_fired,
        "delta": round(spot_delta, 2),
        "evidence_string": spot_evidence
    })

    # 5. Expert Consensus
    expert_fired = any("expert" in r or "consensus" in r or "institutional" in r for r in reasons_lower)
    expert_delta = 0.0
    expert_evidence = "No expert consensus signal"
    if expert_fired:
        for r in reasons:
            if "Expert" in r or "Consensus" in r or "Institutional" in r:
                if "+" in r:
                    try:
                        expert_delta = float(r.split("+")[-1])
                    except:
                        expert_delta = 0.5
                expert_evidence = r
                break
    pillars_proof.append({
        "name": "Expert Consensus",
        "fired": expert_fired,
        "delta": expert_delta,
        "evidence_string": expert_evidence
    })

    # 6. Prop Correlation
    corr_fired = any("correlation" in r or "correlated" in r for r in reasons_lower)
    corr_delta = 0.0
    corr_evidence = "No prop correlation detected"
    if corr_fired:
        for r in reasons:
            if "Correlation" in r or "Correlated" in r:
                if "+" in r:
                    try:
                        corr_delta = float(r.split("+")[-1])
                    except:
                        corr_delta = 0.15
                corr_evidence = r
                break
    pillars_proof.append({
        "name": "Prop Correlation",
        "fired": corr_fired,
        "delta": corr_delta,
        "evidence_string": corr_evidence
    })

    # 7. Hook Discipline
    hook_fired = any("hook" in r or "key number" in r for r in reasons_lower)
    hook_delta = 0.0
    hook_evidence = "Standard line (no hook impact)"
    for r in reasons:
        if "Hook" in r or "Key Number" in r:
            if "+" in r:
                try:
                    hook_delta = float(r.split("+")[-1])
                except:
                    hook_delta = 0.15
            elif "-" in r:
                try:
                    hook_delta = -float(r.split("-")[-1])
                except:
                    hook_delta = -0.3
            hook_evidence = r
            hook_fired = True
    pillars_proof.append({
        "name": "Hook Discipline",
        "fired": hook_fired,
        "delta": round(hook_delta, 2),
        "evidence_string": hook_evidence
    })

    # 8. Volume Discipline
    vol_fired = any("volume" in r or "public" in r for r in reasons_lower)
    vol_delta = 0.0
    vol_evidence = "Normal betting volume"
    for r in reasons:
        if "Volume" in r or "Public" in r:
            if "+" in r:
                try:
                    vol_delta = float(r.split("+")[-1])
                except:
                    vol_delta = 0.5
            elif "-" in r:
                try:
                    vol_delta = -float(r.split("-")[-1])
                except:
                    vol_delta = -0.15
            vol_evidence = r
            vol_fired = True
    pillars_proof.append({
        "name": "Volume Discipline",
        "fired": vol_fired,
        "delta": round(vol_delta, 2),
        "evidence_string": vol_evidence
    })

    return pillars_proof


# =============================================================================
# SIGNAL PROOF BUILDER
# =============================================================================

def build_signal_proof(
    pick: Dict[str, Any],
    reasons: List[str],
    engine_breakdown: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    Build proof for all 17 signals.

    Returns list of signal objects with:
    - name: Signal name
    - category: market/context/esoteric/jarvis
    - fired: bool
    - delta: float
    - evidence_string: Human-readable evidence
    """
    signals_proof = []
    reasons_text = " ".join(reasons).lower()

    # Market Signals (1-6)
    # 1. Sharp Money Flow
    sharp_fired = "sharp" in reasons_text and ("money" in reasons_text or "split" in reasons_text)
    signals_proof.append({
        "name": "Sharp Money Flow",
        "category": "market",
        "fired": sharp_fired,
        "delta": _extract_delta(reasons, ["Sharp"]),
        "evidence_string": _extract_evidence(reasons, ["Sharp"]) or "No sharp money signal"
    })

    # 2. Reverse Line Movement
    rlm_fired = "rlm" in reasons_text or "reverse line" in reasons_text
    signals_proof.append({
        "name": "Reverse Line Movement",
        "category": "market",
        "fired": rlm_fired,
        "delta": _extract_delta(reasons, ["RLM", "Reverse Line"]),
        "evidence_string": _extract_evidence(reasons, ["RLM", "Reverse Line"]) or "No RLM detected"
    })

    # 3. Public Fade Opportunity
    fade_fired = "fade" in reasons_text or "public" in reasons_text
    signals_proof.append({
        "name": "Public Fade Opportunity",
        "category": "market",
        "fired": fade_fired,
        "delta": _extract_delta(reasons, ["Fade", "Public"]),
        "evidence_string": _extract_evidence(reasons, ["Fade", "Public"]) or "No public fade"
    })

    # 4. Steam Move Detected
    steam_fired = "steam" in reasons_text
    signals_proof.append({
        "name": "Steam Move Detected",
        "category": "market",
        "fired": steam_fired,
        "delta": _extract_delta(reasons, ["Steam"]),
        "evidence_string": _extract_evidence(reasons, ["Steam"]) or "No steam move"
    })

    # 5. Line Value Edge
    value_fired = "value" in reasons_text or "edge" in reasons_text
    signals_proof.append({
        "name": "Line Value Edge",
        "category": "market",
        "fired": value_fired,
        "delta": _extract_delta(reasons, ["Value", "Edge"]),
        "evidence_string": _extract_evidence(reasons, ["Value", "Edge"]) or "No line value edge"
    })

    # 6. Book Disagreement
    book_fired = "book" in reasons_text and "disagree" in reasons_text
    signals_proof.append({
        "name": "Book Disagreement",
        "category": "market",
        "fired": book_fired,
        "delta": _extract_delta(reasons, ["Book"]),
        "evidence_string": _extract_evidence(reasons, ["Book"]) or "Books in agreement"
    })

    # Context Signals (7-11)
    # 7. Home Court Advantage
    home_fired = "home" in reasons_text
    signals_proof.append({
        "name": "Home Court Advantage",
        "category": "context",
        "fired": home_fired,
        "delta": _extract_delta(reasons, ["Home"]),
        "evidence_string": _extract_evidence(reasons, ["Home"]) or "Away/neutral"
    })

    # 8. Rest Advantage
    rest_fired = "rest" in reasons_text or "fatigue" in reasons_text or "b2b" in reasons_text
    signals_proof.append({
        "name": "Rest Advantage",
        "category": "context",
        "fired": rest_fired,
        "delta": _extract_delta(reasons, ["Rest", "Fatigue", "B2B"]),
        "evidence_string": _extract_evidence(reasons, ["Rest", "Fatigue", "B2B"]) or "Equal rest"
    })

    # 9. Injury Impact
    injury_fired = "injury" in reasons_text or "hospital" in reasons_text
    signals_proof.append({
        "name": "Injury Impact",
        "category": "context",
        "fired": injury_fired,
        "delta": _extract_delta(reasons, ["Injury", "Hospital"]),
        "evidence_string": _extract_evidence(reasons, ["Injury", "Hospital"]) or "No significant injuries"
    })

    # 10. Pace Mismatch
    pace_fired = "pace" in reasons_text
    signals_proof.append({
        "name": "Pace Mismatch",
        "category": "context",
        "fired": pace_fired,
        "delta": _extract_delta(reasons, ["Pace"]),
        "evidence_string": _extract_evidence(reasons, ["Pace"]) or "Similar pace teams"
    })

    # 11. Defensive Matchup
    def_fired = "defense" in reasons_text or "matchup" in reasons_text
    signals_proof.append({
        "name": "Defensive Matchup",
        "category": "context",
        "fired": def_fired,
        "delta": _extract_delta(reasons, ["Defense", "Matchup"]),
        "evidence_string": _extract_evidence(reasons, ["Defense", "Matchup"]) or "Neutral matchup"
    })

    # Esoteric Signals (12-15)
    # 12. Vedic Astrology Alignment
    vedic_fired = "vedic" in reasons_text or "astro" in reasons_text
    signals_proof.append({
        "name": "Vedic Astrology Alignment",
        "category": "esoteric",
        "fired": vedic_fired,
        "delta": _extract_delta(reasons, ["Vedic", "Astro"]),
        "evidence_string": _extract_evidence(reasons, ["Vedic", "Astro"]) or "No vedic signal"
    })

    # 13. Fibonacci Pattern
    fib_fired = "fibonacci" in reasons_text or "fib" in reasons_text
    signals_proof.append({
        "name": "Fibonacci Pattern",
        "category": "esoteric",
        "fired": fib_fired,
        "delta": _extract_delta(reasons, ["Fibonacci", "Fib"]),
        "evidence_string": _extract_evidence(reasons, ["Fibonacci", "Fib"]) or "No Fibonacci pattern"
    })

    # 14. Vortex Energy
    vortex_fired = "vortex" in reasons_text
    signals_proof.append({
        "name": "Vortex Energy",
        "category": "esoteric",
        "fired": vortex_fired,
        "delta": _extract_delta(reasons, ["Vortex"]),
        "evidence_string": _extract_evidence(reasons, ["Vortex"]) or "No vortex pattern"
    })

    # 15. Daily Energy Flow
    energy_fired = "energy" in reasons_text or "ritual" in reasons_text or "daily" in reasons_text
    signals_proof.append({
        "name": "Daily Energy Flow",
        "category": "esoteric",
        "fired": energy_fired,
        "delta": _extract_delta(reasons, ["Energy", "Ritual", "Daily"]),
        "evidence_string": _extract_evidence(reasons, ["Energy", "Ritual"]) or "Neutral daily energy"
    })

    # Jarvis Signals (16-17)
    # 16. Gematria Trigger
    gematria_fired = "gematria" in reasons_text
    signals_proof.append({
        "name": "Gematria Trigger",
        "category": "jarvis",
        "fired": gematria_fired,
        "delta": _extract_delta(reasons, ["Gematria"]),
        "evidence_string": _extract_evidence(reasons, ["Gematria"]) or "No gematria hit"
    })

    # 17. Sacred Number Hit
    sacred_fired = "trigger" in reasons_text and any(str(n) in reasons_text for n in [33, 47, 88, 93, 201, 322, 2178])
    signals_proof.append({
        "name": "Sacred Number Hit",
        "category": "jarvis",
        "fired": sacred_fired,
        "delta": _extract_delta(reasons, ["Trigger"]),
        "evidence_string": _extract_evidence(reasons, ["Trigger"]) or "No sacred number hit"
    })

    return signals_proof


def _extract_delta(reasons: List[str], keywords: List[str]) -> float:
    """Extract delta value from reasons containing keywords."""
    for r in reasons:
        for kw in keywords:
            if kw.lower() in r.lower():
                if "+" in r:
                    try:
                        parts = r.split("+")
                        return float(parts[-1].strip().rstrip(")"))
                    except:
                        pass
                elif "-" in r and r.count("-") > 0:
                    # Check for negative delta
                    try:
                        # Find the last number with minus sign
                        import re
                        matches = re.findall(r'-[\d.]+', r)
                        if matches:
                            return float(matches[-1])
                    except:
                        pass
    return 0.0


def _extract_evidence(reasons: List[str], keywords: List[str]) -> Optional[str]:
    """Extract evidence string from reasons containing keywords."""
    for r in reasons:
        for kw in keywords:
            if kw.lower() in r.lower():
                return r
    return None


# =============================================================================
# FULL DEBUG OBJECT BUILDER
# =============================================================================

def build_debug_object(
    pick: Dict[str, Any],
    now_et: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Build full debug object for a pick with all verification data.

    This is the main function that creates the complete audit trail.
    """
    if now_et is None:
        now_et = get_now_et()

    # Parse start time
    start_time_raw = pick.get("game_time") or pick.get("start_time") or pick.get("game_time_est")
    start_time_et = parse_to_et(start_time_raw) if start_time_raw else None

    # Get reasons array
    reasons = pick.get("reasons", [])
    if not reasons and pick.get("rationale"):
        reasons = [pick.get("rationale")]

    # Build engine breakdown
    engine_breakdown = pick.get("engine_breakdown", {})
    scoring_breakdown = pick.get("scoring_breakdown", {})

    debug_obj = {
        # =====================================================================
        # PICK IDENTITY
        # =====================================================================
        "pick_identity": {
            "pick_id": pick.get("pick_id") or generate_pick_id(pick),
            "sport": pick.get("sport", "").upper(),
            "league": pick.get("league") or pick.get("sport", "").upper(),
            "game_id": pick.get("game_id"),
            "matchup": pick.get("matchup") or pick.get("game"),
            "selection": pick.get("selection") or pick.get("pick"),
            "player_name": pick.get("player_name"),
            "stat_type": pick.get("stat_type") or pick.get("market"),
            "start_time_et": start_time_et.isoformat() if start_time_et else None,
            "now_et": now_et.isoformat(),
            "time_status": get_time_status(start_time_et, now_et),
        },

        # =====================================================================
        # SPORTSBOOK + LINE PROVENANCE
        # =====================================================================
        "line_provenance": {
            "provider_source": pick.get("source", "odds_api"),
            "sportsbook": pick.get("book") or pick.get("book_key") or "draftkings",
            "sportsbook_display": pick.get("book_display") or pick.get("book_name"),
            "odds": pick.get("odds") or pick.get("odds_american"),
            "market": pick.get("market") or pick.get("market_key"),
            "line": pick.get("line"),
            "last_updated": pick.get("odds_pulled_at"),
            "deep_link": pick.get("book_url") or pick.get("book_link"),
            "pulled_line": pick.get("line_at_pull"),
            "current_line": pick.get("line"),
        },

        # =====================================================================
        # ENGINE SCORES (4-Engine Separation)
        # =====================================================================
        "engine_scores": {
            "ai_engine_score": round(pick.get("ai_score") or scoring_breakdown.get("ai_score") or 5.0, 2),
            "research_engine_score": round(pick.get("research_score") or scoring_breakdown.get("research_score") or 5.0, 2),
            "esoteric_edge_score": round(pick.get("esoteric_score") or scoring_breakdown.get("esoteric_score") or 5.0, 2),
            "jarvis_engine_score": round(pick.get("jarvis_rs") or 5.0, 2),
            "final_score": round(pick.get("smash_score") or pick.get("final_score") or 5.0, 2),
            "scoring_formula": "FINAL = (AI × 0.35) + (Research × 0.35) + (Esoteric × 0.10) + (Jarvis × 0.20) + Confluence",
            "weights": {
                "ai": 0.35,
                "research": 0.35,
                "esoteric": 0.10,
                "jarvis": 0.20
            },
            "confluence_boost": pick.get("confluence_boost", 0.0),
            "tier": pick.get("tier", "MONITOR"),
            "tier_action": pick.get("action") or pick.get("bet_tier", {}).get("action", "WATCH"),
        },

        # =====================================================================
        # PILLARS PROOF (Research Engine - All 8)
        # =====================================================================
        "pillars_proof": build_pillar_proof(pick, reasons),

        # =====================================================================
        # SIGNALS PROOF (All 17)
        # =====================================================================
        "signals_proof": build_signal_proof(pick, reasons, engine_breakdown),

        # =====================================================================
        # JARVIS DETAILS
        # =====================================================================
        "jarvis_details": {
            "jarvis_active": pick.get("jarvis_active", False),
            "jarvis_rs": round(pick.get("jarvis_rs", 5.0), 2),
            "jarvis_hits_count": pick.get("jarvis_hits_count", 0),
            "jarvis_triggers_hit": pick.get("jarvis_triggers", []),
            "jarvis_reasons": pick.get("jarvis_reasons", []),
            "immortal_detected": pick.get("immortal_detected", False),
            "note": "Jarvis is STANDALONE - gematria + sacred triggers only"
        },

        # =====================================================================
        # JASON SIM CONFLUENCE
        # =====================================================================
        "jason_sim": {
            "jason_sim_used": pick.get("jason_sim_used", False),
            "jason_sim_boost": pick.get("jason_sim_boost", 0.0),
            "win_pct_home": pick.get("jason_sim_win_pct"),
            "win_pct_away": None,  # Complement if available
            "variance_flag": pick.get("jason_sim_variance_flag"),
            "confluence_reasons": pick.get("confluence_reasons", []),
            "note": "POST-PICK confluence layer only"
        },

        # =====================================================================
        # INJURY + AVAILABILITY GUARDRAILS
        # =====================================================================
        "injury_guardrails": {
            "injury_checked": pick.get("injury_verified", False),
            "injury_state": pick.get("injury_status", "UNKNOWN"),
            "player_available_in_book": pick.get("player_prop_listed", True),
            "block_reason": pick.get("block_reason"),
            "injury_warning": pick.get("injury_warning"),
        },

        # =====================================================================
        # RAW REASONS (for audit)
        # =====================================================================
        "raw_reasons": reasons,

        # =====================================================================
        # AI BREAKDOWN (if available)
        # =====================================================================
        "ai_breakdown": pick.get("ai_breakdown", {}),

        # =====================================================================
        # ESOTERIC BREAKDOWN (if available)
        # =====================================================================
        "esoteric_breakdown": pick.get("esoteric_breakdown", {}),
    }

    return debug_obj


# =============================================================================
# OFFICIAL CARD PERSISTENCE
# =============================================================================

OFFICIAL_CARD_DIR = os.path.join(os.path.dirname(__file__), "data", "official_cards")

def get_official_card_path(date_et: datetime) -> str:
    """Get path to official card file for a date."""
    os.makedirs(OFFICIAL_CARD_DIR, exist_ok=True)
    date_str = date_et.strftime("%Y-%m-%d")
    return os.path.join(OFFICIAL_CARD_DIR, f"official_card_{date_str}.jsonl")


def save_official_card(picks: List[Dict[str, Any]], date_et: Optional[datetime] = None):
    """
    Save official card picks to JSONL file.
    Only UPCOMING picks go on the official card.
    """
    if date_et is None:
        date_et = get_now_et()

    filepath = get_official_card_path(date_et)

    # Filter to UPCOMING only
    now_et = get_now_et()
    official_picks = []

    for pick in picks:
        start_time_raw = pick.get("game_time") or pick.get("start_time") or pick.get("game_time_est")
        start_time_et = parse_to_et(start_time_raw) if start_time_raw else None
        time_status = get_time_status(start_time_et, now_et)

        if time_status == "UPCOMING":
            pick_record = {
                "pick_id": pick.get("pick_id") or generate_pick_id(pick),
                "sport": pick.get("sport"),
                "game_id": pick.get("game_id"),
                "selection": pick.get("selection") or pick.get("pick"),
                "player_name": pick.get("player_name"),
                "line": pick.get("line"),
                "odds": pick.get("odds"),
                "tier": pick.get("tier"),
                "final_score": pick.get("smash_score") or pick.get("final_score"),
                "logged_at": now_et.isoformat(),
                "start_time_et": start_time_et.isoformat() if start_time_et else None,
            }
            official_picks.append(pick_record)

    # Append to file (don't overwrite - accumulate through the day)
    with open(filepath, "a") as f:
        for pick in official_picks:
            f.write(json.dumps(pick) + "\n")

    return len(official_picks)


def load_official_card(date_et: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Load official card picks for a date."""
    if date_et is None:
        date_et = get_now_et()

    filepath = get_official_card_path(date_et)

    if not os.path.exists(filepath):
        return []

    picks = []
    seen_ids = set()

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pick = json.loads(line)
                    # Dedupe by pick_id
                    pick_id = pick.get("pick_id")
                    if pick_id and pick_id not in seen_ids:
                        picks.append(pick)
                        seen_ids.add(pick_id)
                except json.JSONDecodeError:
                    continue

    return picks


def get_official_card_pick_ids(date_et: Optional[datetime] = None) -> set:
    """Get set of pick IDs from official card for grading."""
    picks = load_official_card(date_et)
    return {p.get("pick_id") for p in picks if p.get("pick_id")}
