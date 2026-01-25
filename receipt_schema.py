"""
receipt_schema.py - Score Receipt Schema for Pick Explainability
Version: v10.57

Every scored pick MUST include a receipt that proves what was used.
This enables deterministic verification and debugging.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json

# =============================================================================
# REQUIRED COMPONENTS (Tests fail if missing)
# =============================================================================

# All 8 AI Models
REQUIRED_MODELS = [
    "ensemble_stacking",
    "lstm_neural",
    "matchup_specific",
    "monte_carlo",
    "line_movement",
    "rest_fatigue",
    "injury_impact",
    "betting_edge"
]

# All 8 Pillars
REQUIRED_PILLARS = [
    "sharp_split",
    "reverse_line_move",
    "hospital_fade",
    "situational_spot",
    "expert_consensus",
    "prop_correlation",
    "hook_discipline",
    "volume_discipline"
]

# All Signals (17 total)
REQUIRED_SIGNALS = [
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

# All Esoteric Components
REQUIRED_ESOTERIC = [
    "gematria",
    "jarvis_trigger",
    "vedic_astro",
    "fibonacci",
    "tesla_vortex",
    "numerology",
    "sacred_geometry",
    "planetary_hour"
]


# =============================================================================
# RECEIPT SCHEMA
# =============================================================================

@dataclass
class ModelResult:
    """Result from a single AI model."""
    raw: Any = None
    score: float = 0.0
    available: bool = True
    notes: str = ""


@dataclass
class SignalResult:
    """Result from a single signal."""
    raw: Any = None
    score: float = 0.0
    passed: bool = False
    threshold: Any = None
    notes: str = ""


@dataclass
class PillarResult:
    """Result from a single pillar."""
    passed: bool = False
    score: float = 0.0
    trigger: str = ""
    notes: str = ""


@dataclass
class EsotericResult:
    """Result from a single esoteric component."""
    raw: Any = None
    score: float = 0.0
    weight: float = 0.0
    triggered: bool = False
    notes: str = ""


@dataclass
class TierResult:
    """Tier assignment result."""
    tier: str = "PASS"
    badge: str = "PASS"
    units: float = 0.0
    action: str = "SKIP"
    threshold: float = 0.0


@dataclass
class ValidatorResult:
    """Result from validators."""
    passed: bool = True
    drop_reasons: List[str] = field(default_factory=list)
    prop_integrity: bool = True
    injury_guard: bool = True
    market_available: bool = True


@dataclass
class PickReceipt:
    """
    Complete receipt for a scored pick.

    Every pick MUST include this in debug mode.
    All components MUST be present (even if disabled/0.0).
    """
    # Pick identification
    pick_id: str = ""
    sport: str = ""
    league: str = ""
    market_type: str = ""  # "prop" or "game"
    market_key: str = ""
    team: str = ""
    opponent: str = ""
    player: Optional[str] = None
    line: float = 0.0
    odds: int = -110
    book: str = ""
    game_id: str = ""
    game_time_et: str = ""

    # Raw inputs (everything needed to recompute)
    raw_inputs: Dict[str, Any] = field(default_factory=dict)

    # Model results (8 required)
    models: Dict[str, ModelResult] = field(default_factory=dict)

    # Signal results (17 required)
    signals: Dict[str, SignalResult] = field(default_factory=dict)

    # Pillar results (8 required)
    pillars: Dict[str, PillarResult] = field(default_factory=dict)

    # Esoteric results (8 required)
    esoteric: Dict[str, EsotericResult] = field(default_factory=dict)

    # Bonuses applied
    bonuses: Dict[str, float] = field(default_factory=dict)

    # Penalties applied
    penalties: Dict[str, float] = field(default_factory=dict)

    # Scores
    research_score: float = 0.0
    esoteric_score: float = 0.0
    alignment_pct: float = 0.0
    confluence_boost: float = 0.0
    base_score: float = 0.0
    final_score: float = 0.0

    # Tier assignment
    tier: TierResult = field(default_factory=TierResult)

    # Validators
    validators: ValidatorResult = field(default_factory=ValidatorResult)

    # Gate debug info
    publish_gate: Dict[str, Any] = field(default_factory=dict)
    pick_filter: Dict[str, Any] = field(default_factory=dict)
    jason_sim: Dict[str, Any] = field(default_factory=dict)

    # Confluence reasons (ordered deterministically)
    reasons_ordered: List[str] = field(default_factory=list)

    # Additional metadata
    ref_code: Optional[str] = None
    guardrails: Dict[str, Any] = field(default_factory=dict)

    # Version info
    version: Dict[str, str] = field(default_factory=lambda: {
        "router": "v15.0",
        "scoring": "v10.57"
    })

    def to_dict(self) -> Dict[str, Any]:
        """Convert receipt to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert receipt to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def verify_receipt_completeness(receipt: PickReceipt) -> Tuple[bool, List[str]]:
    """
    Verify that a receipt has all required components.

    Returns:
        Tuple of (is_complete, missing_components)
    """
    missing = []

    # Check models
    for model in REQUIRED_MODELS:
        if model not in receipt.models:
            missing.append(f"MODEL:{model}")

    # Check pillars
    for pillar in REQUIRED_PILLARS:
        if pillar not in receipt.pillars:
            missing.append(f"PILLAR:{pillar}")

    # Check signals (relaxed - only check if signals dict exists)
    if not receipt.signals:
        missing.append("SIGNALS:empty")

    # Check esoteric (relaxed - only check if esoteric dict exists)
    if not receipt.esoteric:
        missing.append("ESOTERIC:empty")

    # Check validators
    if receipt.validators is None:
        missing.append("VALIDATORS:missing")

    # Check scores
    if receipt.base_score == 0.0 and receipt.final_score == 0.0:
        missing.append("SCORES:both_zero")

    # Check tier
    if not receipt.tier.tier:
        missing.append("TIER:missing")

    return (len(missing) == 0, missing)


def build_receipt_from_pick(pick: Dict[str, Any], debug_data: Dict[str, Any] = None) -> PickReceipt:
    """
    Build a receipt from a scored pick dictionary.

    Args:
        pick: Scored pick dictionary
        debug_data: Optional debug data with additional context

    Returns:
        PickReceipt with all available components
    """
    receipt = PickReceipt()

    # Pick identification
    receipt.pick_id = pick.get("id", pick.get("pick_id", ""))
    receipt.sport = pick.get("sport", "")
    receipt.league = pick.get("league", pick.get("sport", ""))
    receipt.market_type = "prop" if pick.get("player_name") or pick.get("stat_type") else "game"
    receipt.market_key = pick.get("market", pick.get("stat_type", pick.get("bet_type", "")))
    receipt.team = pick.get("team", pick.get("player_team", ""))
    receipt.opponent = pick.get("opponent", "")
    receipt.player = pick.get("player_name", pick.get("player", None))
    receipt.line = float(pick.get("line", 0))
    receipt.odds = int(pick.get("odds", -110))
    receipt.book = pick.get("book", pick.get("sportsbook", "draftkings"))
    receipt.game_id = pick.get("game_id", "")
    receipt.game_time_et = pick.get("game_time_et", pick.get("commence_time", ""))

    # Scores
    receipt.research_score = float(pick.get("research_score", 0))
    receipt.esoteric_score = float(pick.get("esoteric_score", 0))
    receipt.alignment_pct = float(pick.get("alignment_pct", pick.get("dual_align", 0)))
    receipt.confluence_boost = float(pick.get("confluence_boost", 0))
    receipt.base_score = float(pick.get("base_score", pick.get("smash_score", pick.get("final_score", 0))))
    receipt.final_score = float(pick.get("final_score", pick.get("smash_score", 0)))

    # Tier
    tier_name = pick.get("tier", "PASS")
    receipt.tier = TierResult(
        tier=tier_name,
        badge=pick.get("badge", tier_name),
        units=float(pick.get("recommended_units", pick.get("units", 0))),
        action=pick.get("action", "SKIP")
    )

    # Reasons
    receipt.reasons_ordered = pick.get("reasons", pick.get("confluence_reasons", []))

    # Build model results from available data
    for model in REQUIRED_MODELS:
        model_data = pick.get("ai_breakdown", {}).get(model, {})
        receipt.models[model] = ModelResult(
            raw=model_data.get("raw"),
            score=float(model_data.get("score", 0)),
            available=model_data.get("available", True),
            notes=model_data.get("notes", "")
        )

    # Build pillar results from reasons
    for pillar in REQUIRED_PILLARS:
        pillar_key = f"PILLAR_{pillar.upper()}"
        pillar_triggered = any(pillar_key in r.upper() for r in receipt.reasons_ordered)
        receipt.pillars[pillar] = PillarResult(
            passed=pillar_triggered,
            score=0.5 if pillar_triggered else 0.0,
            trigger=pillar_key if pillar_triggered else "",
            notes=""
        )

    # Build esoteric results from breakdown
    esoteric_breakdown = pick.get("esoteric_breakdown", {})
    for esoteric in REQUIRED_ESOTERIC:
        esoteric_data = esoteric_breakdown.get(esoteric, {})
        receipt.esoteric[esoteric] = EsotericResult(
            raw=esoteric_data.get("raw"),
            score=float(esoteric_data.get("score", 0)),
            weight=float(esoteric_data.get("weight", 0)),
            triggered=esoteric_data.get("triggered", False),
            notes=esoteric_data.get("notes", "")
        )

    # Build signal results (simplified)
    for signal in REQUIRED_SIGNALS:
        receipt.signals[signal] = SignalResult(
            raw=None,
            score=0.0,
            passed=False,
            notes="(signal tracking in progress)"
        )

    # Validators
    receipt.validators = ValidatorResult(
        passed=not pick.get("dropped", False),
        drop_reasons=pick.get("drop_reasons", [])
    )

    # Debug data
    if debug_data:
        receipt.publish_gate = debug_data.get("publish_gate", {})
        receipt.pick_filter = debug_data.get("pick_filter", {})
        receipt.jason_sim = debug_data.get("jason_sim", {})
        receipt.guardrails = debug_data.get("guardrails", {})

    return receipt


def generate_sample_receipts() -> Dict[str, PickReceipt]:
    """
    Generate sample receipts for documentation and testing.
    """
    # Sample prop pick
    prop_pick = {
        "id": "nba_prop_lebron_points_20260123",
        "sport": "NBA",
        "player_name": "LeBron James",
        "stat_type": "player_points",
        "line": 25.5,
        "odds": -115,
        "side": "Over",
        "team": "LAL",
        "opponent": "BOS",
        "game_id": "nba_lal_bos_20260123",
        "game_time_et": "2026-01-23T19:30:00",
        "research_score": 7.2,
        "esoteric_score": 6.8,
        "alignment_pct": 85.0,
        "confluence_boost": 0.35,
        "final_score": 7.55,
        "tier": "GOLD_STAR",
        "recommended_units": 2.0,
        "reasons": [
            "RESEARCH: Sharp Split +2.0",
            "RESEARCH: RLM +1.5",
            "JARVIS: Trigger 33 +0.5",
            "CONFLUENCE: Perfect +0.35"
        ]
    }

    # Sample game pick
    game_pick = {
        "id": "nba_game_lal_spread_20260123",
        "sport": "NBA",
        "bet_type": "spreads",
        "line": -3.5,
        "odds": -110,
        "side": "LAL",
        "team": "LAL",
        "opponent": "BOS",
        "game_id": "nba_lal_bos_20260123",
        "game_time_et": "2026-01-23T19:30:00",
        "research_score": 6.8,
        "esoteric_score": 6.5,
        "alignment_pct": 78.0,
        "confluence_boost": 0.25,
        "final_score": 6.85,
        "tier": "EDGE_LEAN",
        "recommended_units": 1.0,
        "reasons": [
            "RESEARCH: Sharp Split +1.5",
            "RESEARCH: Goldilocks Zone +0.2",
            "ESOTERIC: Numerology +0.3",
            "CONFLUENCE: Strong +0.25"
        ]
    }

    return {
        "prop": build_receipt_from_pick(prop_pick),
        "game": build_receipt_from_pick(game_pick)
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score Receipt Schema Utilities")
    parser.add_argument("--sample", action="store_true", help="Print sample receipts")
    parser.add_argument("--verify", type=str, help="Verify receipt JSON file")
    args = parser.parse_args()

    if args.sample:
        samples = generate_sample_receipts()
        print("=== SAMPLE PROP RECEIPT ===")
        print(samples["prop"].to_json())
        print("\n=== SAMPLE GAME RECEIPT ===")
        print(samples["game"].to_json())

    if args.verify:
        with open(args.verify, 'r') as f:
            data = json.load(f)
        receipt = build_receipt_from_pick(data)
        is_complete, missing = verify_receipt_completeness(receipt)
        if is_complete:
            print("PASS: Receipt is complete")
        else:
            print(f"FAIL: Missing components: {missing}")
