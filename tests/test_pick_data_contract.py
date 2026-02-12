"""
PICK DATA CONTRACT TESTS - Boundary Validation for API Payloads

These tests validate that pick payloads from /live/best-bets/{sport} conform
to the data contract. They catch "engine is correct but output is missing fields"
problems before they reach the frontend.

Run with:
    pytest tests/test_pick_data_contract.py -v

For live endpoint testing:
    API_KEY=your_key pytest tests/test_pick_data_contract.py -v --live
"""

import pytest
from typing import Dict, Any, List
from datetime import datetime


# =============================================================================
# PICK CONTRACT SCHEMA
# =============================================================================

REQUIRED_PICK_FIELDS = {
    # Identity
    "pick_id": str,
    "sport": str,
    "market": str,

    # Scoring (ALL 4 engines + final)
    "ai_score": (int, float),
    "research_score": (int, float),
    "esoteric_score": (int, float),
    "jarvis_rs": (int, float, type(None)),  # Can be None when inputs missing
    "final_score": (int, float),
    "tier": str,

    # Context (modifier, not engine)
    "context_modifier": (int, float),

    # Boosts (each must be present even if 0)
    "confluence_boost": (int, float),

    # Reasons (all must be lists)
    "ai_reasons": list,
    "research_reasons": list,
    "esoteric_reasons": list,
    "jarvis_reasons": list,
    "context_reasons": list,
}

REQUIRED_GAME_PICK_FIELDS = {
    **REQUIRED_PICK_FIELDS,
    "matchup": str,
    "home_team": str,
    "away_team": str,
}

REQUIRED_PROP_FIELDS = {
    **REQUIRED_PICK_FIELDS,
    "player_name": str,
    "stat_type": str,
    "line": (int, float),
    "side": str,  # Over/Under
}

# Titanium fields (required when titanium_triggered=True)
TITANIUM_FIELDS = {
    "titanium_triggered": bool,
    "titanium_count": int,
    "titanium_qualified_engines": list,
}

# Allowed tier values
VALID_TIERS = {"TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"}

# Minimum score threshold
MIN_FINAL_SCORE = 6.5


# =============================================================================
# CONTRACT VALIDATION FUNCTIONS
# =============================================================================

def validate_pick_schema(pick: Dict[str, Any], pick_type: str = "game") -> List[str]:
    """
    Validate a pick against the data contract.
    Returns list of violations (empty = valid).
    """
    violations = []

    # Select schema based on pick type
    schema = REQUIRED_PROP_FIELDS if pick_type == "prop" else REQUIRED_GAME_PICK_FIELDS

    # Check required fields
    for field, expected_type in schema.items():
        if field not in pick:
            violations.append(f"MISSING: {field}")
            continue

        value = pick[field]
        if not isinstance(value, expected_type):
            violations.append(f"TYPE_ERROR: {field} expected {expected_type}, got {type(value)}")

    # Check titanium fields when triggered
    if pick.get("titanium_triggered"):
        for field, expected_type in TITANIUM_FIELDS.items():
            if field not in pick:
                violations.append(f"TITANIUM_MISSING: {field}")
            elif not isinstance(pick[field], expected_type):
                violations.append(f"TITANIUM_TYPE_ERROR: {field}")

    # Check final_score threshold
    if "final_score" in pick:
        if pick["final_score"] < MIN_FINAL_SCORE:
            violations.append(f"SCORE_THRESHOLD: final_score={pick['final_score']} < {MIN_FINAL_SCORE}")

    # Check tier validity
    if "tier" in pick and pick["tier"] not in VALID_TIERS:
        violations.append(f"INVALID_TIER: {pick['tier']} not in {VALID_TIERS}")

    return violations


def validate_no_contradictions(picks: List[Dict]) -> List[str]:
    """
    Validate no picks are contradictions (Over AND Under on same line).
    """
    violations = []
    seen = {}

    for pick in picks:
        # Build unique key (excluding side)
        sport = pick.get("sport", "")
        event_id = pick.get("event_id", "")
        market = pick.get("market", "")
        line = pick.get("line", 0)
        player = pick.get("player_name", "")

        key = f"{sport}|{event_id}|{market}|{line}|{player}"
        side = pick.get("side", "")

        if key in seen:
            if seen[key] != side:
                violations.append(f"CONTRADICTION: {key} has both {seen[key]} and {side}")
        else:
            seen[key] = side

    return violations


def validate_weights_reconcile(pick: Dict) -> List[str]:
    """
    Validate that engine scores + boosts mathematically reconcile to final_score.
    This catches scoring drift.
    """
    violations = []

    # Engine weights (from scoring_contract.py)
    AI_WEIGHT = 0.25
    RESEARCH_WEIGHT = 0.35
    ESOTERIC_WEIGHT = 0.15
    JARVIS_WEIGHT = 0.25

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    context_mod = pick.get("context_modifier", 0) or 0
    confluence = pick.get("confluence_boost", 0) or 0
    msrf = pick.get("msrf_boost", 0) or 0
    jason = pick.get("jason_sim_boost", 0) or 0
    serp = pick.get("serp_boost", 0) or 0

    # Compute expected base
    expected_base = (ai * AI_WEIGHT) + (research * RESEARCH_WEIGHT) + \
                   (esoteric * ESOTERIC_WEIGHT) + (jarvis * JARVIS_WEIGHT)

    # Total boost cap is 1.5
    TOTAL_BOOST_CAP = 1.5
    total_boosts = confluence + msrf + jason + serp
    capped_boosts = min(total_boosts, TOTAL_BOOST_CAP)

    # Expected final (before other adjustments)
    expected_final_approx = expected_base + context_mod + capped_boosts

    # Allow some tolerance for other adjustments (ensemble, live, etc.)
    final = pick.get("final_score", 0)
    tolerance = 2.0  # Allow for ensemble/live adjustments

    if abs(final - expected_final_approx) > tolerance:
        violations.append(
            f"SCORE_DRIFT: final={final:.2f} but expected ~{expected_final_approx:.2f} "
            f"(base={expected_base:.2f} + context={context_mod:.2f} + boosts={capped_boosts:.2f})"
        )

    return violations


def validate_titanium_rule(pick: Dict) -> List[str]:
    """
    Validate Titanium 3-of-4 rule is correctly applied.
    """
    violations = []

    if not pick.get("titanium_triggered"):
        return violations

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    engines_above_8 = sum(1 for score in [ai, research, esoteric, jarvis] if score >= 8.0)

    if engines_above_8 < 3:
        violations.append(
            f"TITANIUM_RULE_VIOLATED: titanium_triggered=True but only {engines_above_8}/4 engines >= 8.0"
        )

    return violations


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_game_pick():
    """Minimal valid game pick."""
    return {
        "pick_id": "test123456ab",
        "sport": "NBA",
        "market": "SPREAD",
        "matchup": "Lakers @ Celtics",
        "home_team": "Celtics",
        "away_team": "Lakers",
        "ai_score": 7.5,
        "research_score": 7.8,
        "esoteric_score": 6.0,
        "jarvis_rs": 6.5,
        "context_modifier": 0.15,
        "confluence_boost": 1.0,
        "final_score": 7.2,
        "tier": "GOLD_STAR",
        "ai_reasons": ["AI models aligned"],
        "research_reasons": ["Sharp money detected"],
        "esoteric_reasons": ["Lunar phase favorable"],
        "jarvis_reasons": ["Gematria trigger"],
        "context_reasons": ["Pace advantage"],
    }


@pytest.fixture
def sample_prop_pick():
    """Minimal valid prop pick."""
    return {
        "pick_id": "prop123456ab",
        "sport": "NBA",
        "market": "PLAYER_POINTS",
        "player_name": "LeBron James",
        "stat_type": "points",
        "line": 25.5,
        "side": "Over",
        "ai_score": 7.0,
        "research_score": 6.8,
        "esoteric_score": 5.5,
        "jarvis_rs": 6.0,
        "context_modifier": 0.1,
        "confluence_boost": 0.5,
        "final_score": 6.8,
        "tier": "EDGE_LEAN",
        "ai_reasons": ["Prop model confident"],
        "research_reasons": ["Line moved favorably"],
        "esoteric_reasons": [],
        "jarvis_reasons": [],
        "context_reasons": [],
    }


# =============================================================================
# TESTS
# =============================================================================

class TestPickSchema:
    """Test pick schema validation."""

    def test_valid_game_pick(self, sample_game_pick):
        """Valid game pick passes all checks."""
        violations = validate_pick_schema(sample_game_pick, "game")
        assert violations == [], f"Unexpected violations: {violations}"

    def test_valid_prop_pick(self, sample_prop_pick):
        """Valid prop pick passes all checks."""
        violations = validate_pick_schema(sample_prop_pick, "prop")
        assert violations == [], f"Unexpected violations: {violations}"

    def test_missing_ai_score(self, sample_game_pick):
        """Detect missing ai_score."""
        del sample_game_pick["ai_score"]
        violations = validate_pick_schema(sample_game_pick, "game")
        assert any("MISSING: ai_score" in v for v in violations)

    def test_missing_research_score(self, sample_game_pick):
        """Detect missing research_score."""
        del sample_game_pick["research_score"]
        violations = validate_pick_schema(sample_game_pick, "game")
        assert any("MISSING: research_score" in v for v in violations)

    def test_wrong_type_ai_score(self, sample_game_pick):
        """Detect wrong type for ai_score."""
        sample_game_pick["ai_score"] = "high"
        violations = validate_pick_schema(sample_game_pick, "game")
        assert any("TYPE_ERROR: ai_score" in v for v in violations)

    def test_score_below_threshold(self, sample_game_pick):
        """Detect score below minimum threshold."""
        sample_game_pick["final_score"] = 5.5
        violations = validate_pick_schema(sample_game_pick, "game")
        assert any("SCORE_THRESHOLD" in v for v in violations)

    def test_invalid_tier(self, sample_game_pick):
        """Detect invalid tier value."""
        sample_game_pick["tier"] = "SUPER_PICK"
        violations = validate_pick_schema(sample_game_pick, "game")
        assert any("INVALID_TIER" in v for v in violations)


class TestContradictionGate:
    """Test contradiction detection."""

    def test_no_contradictions(self, sample_prop_pick):
        """No violations when picks don't contradict."""
        pick1 = {**sample_prop_pick, "side": "Over"}
        pick2 = {**sample_prop_pick, "player_name": "Steph Curry", "side": "Under"}
        violations = validate_no_contradictions([pick1, pick2])
        assert violations == []

    def test_detect_contradiction(self, sample_prop_pick):
        """Detect Over/Under contradiction on same line."""
        pick1 = {**sample_prop_pick, "side": "Over"}
        pick2 = {**sample_prop_pick, "side": "Under"}  # Same player, same line
        violations = validate_no_contradictions([pick1, pick2])
        assert any("CONTRADICTION" in v for v in violations)


class TestTitaniumRule:
    """Test Titanium 3-of-4 rule validation."""

    def test_valid_titanium(self, sample_game_pick):
        """Valid Titanium with 3/4 engines >= 8.0."""
        sample_game_pick["titanium_triggered"] = True
        sample_game_pick["titanium_count"] = 3
        sample_game_pick["titanium_qualified_engines"] = ["ai", "research", "jarvis"]
        sample_game_pick["ai_score"] = 8.5
        sample_game_pick["research_score"] = 8.2
        sample_game_pick["jarvis_rs"] = 8.0
        violations = validate_titanium_rule(sample_game_pick)
        assert violations == []

    def test_invalid_titanium_only_2_engines(self, sample_game_pick):
        """Detect Titanium violation with only 2/4 engines >= 8.0."""
        sample_game_pick["titanium_triggered"] = True
        sample_game_pick["ai_score"] = 8.5
        sample_game_pick["research_score"] = 8.2
        sample_game_pick["esoteric_score"] = 6.0  # Below 8.0
        sample_game_pick["jarvis_rs"] = 6.5       # Below 8.0
        violations = validate_titanium_rule(sample_game_pick)
        assert any("TITANIUM_RULE_VIOLATED" in v for v in violations)


class TestWeightReconciliation:
    """Test that scores mathematically reconcile."""

    def test_weights_reconcile(self, sample_game_pick):
        """Scores should approximately match weight formula."""
        # Set up a pick where math should work out
        sample_game_pick["ai_score"] = 8.0
        sample_game_pick["research_score"] = 7.0
        sample_game_pick["esoteric_score"] = 6.0
        sample_game_pick["jarvis_rs"] = 7.0
        sample_game_pick["context_modifier"] = 0.2
        sample_game_pick["confluence_boost"] = 0.5
        sample_game_pick["msrf_boost"] = 0.0
        sample_game_pick["jason_sim_boost"] = 0.0
        sample_game_pick["serp_boost"] = 0.0

        # Expected: (8*0.25 + 7*0.35 + 6*0.15 + 7*0.25) + 0.2 + 0.5
        # = (2.0 + 2.45 + 0.9 + 1.75) + 0.7 = 7.1 + 0.7 = 7.8
        sample_game_pick["final_score"] = 7.8

        violations = validate_weights_reconcile(sample_game_pick)
        assert violations == [], f"Unexpected violations: {violations}"

    def test_detect_large_drift(self, sample_game_pick):
        """Detect when final_score doesn't match calculation."""
        sample_game_pick["ai_score"] = 5.0
        sample_game_pick["research_score"] = 5.0
        sample_game_pick["esoteric_score"] = 5.0
        sample_game_pick["jarvis_rs"] = 5.0
        sample_game_pick["context_modifier"] = 0.0
        sample_game_pick["confluence_boost"] = 0.0
        sample_game_pick["final_score"] = 9.5  # Way too high

        violations = validate_weights_reconcile(sample_game_pick)
        assert any("SCORE_DRIFT" in v for v in violations)


# =============================================================================
# INTEGRATION TEST (requires --live flag)
# =============================================================================

import os

@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run live endpoint tests"
)
class TestLiveEndpoint:
    """Tests against live production endpoint (requires API_KEY env var)."""

    @pytest.fixture
    def api_response(self):
        """Fetch live best-bets response."""
        import os
        import requests

        base_url = os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app")
        api_key = os.getenv("API_KEY")

        if not api_key:
            pytest.skip("API_KEY env var required for live tests")

        response = requests.get(
            f"{base_url}/live/best-bets/NBA?debug=1",
            headers={"X-API-Key": api_key},
            timeout=60
        )
        response.raise_for_status()
        return response.json()

    def test_all_game_picks_valid(self, api_response):
        """All game picks must pass schema validation."""
        game_picks = api_response.get("game_picks", {}).get("picks", [])

        for pick in game_picks:
            violations = validate_pick_schema(pick, "game")
            assert violations == [], f"Pick {pick.get('pick_id')}: {violations}"

    def test_all_prop_picks_valid(self, api_response):
        """All prop picks must pass schema validation."""
        prop_picks = api_response.get("props", {}).get("picks", [])

        for pick in prop_picks:
            violations = validate_pick_schema(pick, "prop")
            assert violations == [], f"Pick {pick.get('pick_id')}: {violations}"

    def test_no_contradictions_in_response(self, api_response):
        """No contradictions in response."""
        all_picks = (
            api_response.get("game_picks", {}).get("picks", []) +
            api_response.get("props", {}).get("picks", [])
        )
        violations = validate_no_contradictions(all_picks)
        assert violations == [], f"Contradictions found: {violations}"

    def test_titanium_rules_enforced(self, api_response):
        """Titanium 3-of-4 rule enforced for all picks."""
        all_picks = (
            api_response.get("game_picks", {}).get("picks", []) +
            api_response.get("props", {}).get("picks", [])
        )

        for pick in all_picks:
            violations = validate_titanium_rule(pick)
            assert violations == [], f"Pick {pick.get('pick_id')}: {violations}"


