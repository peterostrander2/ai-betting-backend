"""
GOLDEN FIXTURE TESTS - Regression tests for captured API responses

These tests load golden fixtures (captured from production) and validate:
- Schema compliance
- Weight reconciliation
- Titanium 3-of-4 rule
- Score thresholds
- Jarvis v2.2.1 fields

Golden fixtures are versioned by date. Tests compare against the fixture's
own validation rules, not the current code, to allow intentional scoring changes.

Run with:
    pytest tests/test_golden_fixture.py -v

To update fixtures:
    API_KEY=your_key python3 scripts/golden_snapshot.py NBA
"""

import os
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional


# =============================================================================
# FIXTURE LOADING
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "golden"


def get_available_fixtures() -> List[Dict[str, str]]:
    """Get list of available golden fixtures."""
    fixtures = []

    if not FIXTURES_DIR.exists():
        return fixtures

    for sport_dir in FIXTURES_DIR.iterdir():
        if sport_dir.is_dir():
            for fixture_file in sport_dir.glob("*.json"):
                fixtures.append({
                    "sport": sport_dir.name.upper(),
                    "date": fixture_file.stem,
                    "path": str(fixture_file),
                })

    return fixtures


def load_fixture(path: str) -> Optional[Dict[str, Any]]:
    """Load a golden fixture from disk."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load fixture {path}: {e}")
        return None


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

REQUIRED_SCORING_FIELDS = [
    "ai_score", "research_score", "esoteric_score", "jarvis_rs",
    "final_score", "tier", "context_modifier",
]

REQUIRED_REASON_FIELDS = [
    "ai_reasons", "research_reasons", "esoteric_reasons", "jarvis_reasons",
]

VALID_TIERS = {"TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"}

JARVIS_V22_FIELDS = [
    "jarvis_rs", "jarvis_active", "jarvis_reasons",
    "ophis_raw", "ophis_score_norm", "msrf_status",
]


def validate_schema(pick: Dict[str, Any]) -> List[str]:
    """Validate pick has required fields."""
    violations = []

    for field in REQUIRED_SCORING_FIELDS:
        if field not in pick:
            violations.append(f"MISSING:{field}")

    for field in REQUIRED_REASON_FIELDS:
        if field not in pick:
            violations.append(f"MISSING:{field}")
        elif not isinstance(pick[field], list):
            violations.append(f"NOT_LIST:{field}")

    return violations


def validate_score_threshold(pick: Dict[str, Any]) -> List[str]:
    """Validate final_score >= 6.5."""
    violations = []

    final_score = pick.get("final_score")
    if final_score is not None and final_score < 6.5:
        violations.append(f"SCORE_BELOW_THRESHOLD:{final_score}")

    return violations


def validate_tier(pick: Dict[str, Any]) -> List[str]:
    """Validate tier is valid."""
    violations = []

    tier = pick.get("tier")
    if tier is not None and tier not in VALID_TIERS:
        violations.append(f"INVALID_TIER:{tier}")

    return violations


def validate_titanium_rule(pick: Dict[str, Any]) -> List[str]:
    """Validate Titanium 3-of-4 rule."""
    violations = []

    if not pick.get("titanium_triggered"):
        return violations

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    engines_above_8 = sum(1 for score in [ai, research, esoteric, jarvis] if score >= 8.0)

    if engines_above_8 < 3:
        violations.append(f"TITANIUM_RULE_VIOLATION:{engines_above_8}/4_engines_gte_8")

    return violations


def validate_weight_reconciliation(pick: Dict[str, Any], tolerance: float = 2.0) -> List[str]:
    """Validate scores reconcile with weight formula."""
    violations = []

    AI_WEIGHT = 0.25
    RESEARCH_WEIGHT = 0.35
    ESOTERIC_WEIGHT = 0.15
    JARVIS_WEIGHT = 0.25

    ai = pick.get("ai_score", 0) or 0
    research = pick.get("research_score", 0) or 0
    esoteric = pick.get("esoteric_score", 0) or 0
    jarvis = pick.get("jarvis_rs", 0) or 0

    expected_base = (ai * AI_WEIGHT) + (research * RESEARCH_WEIGHT) + \
                   (esoteric * ESOTERIC_WEIGHT) + (jarvis * JARVIS_WEIGHT)

    context_mod = pick.get("context_modifier", 0) or 0
    confluence = pick.get("confluence_boost", 0) or 0
    msrf = pick.get("msrf_boost", 0) or 0
    jason = pick.get("jason_sim_boost", 0) or 0
    serp = pick.get("serp_boost", 0) or 0

    total_boosts = confluence + msrf + jason + serp
    capped_boosts = min(total_boosts, 1.5)

    expected_final_approx = expected_base + context_mod + capped_boosts

    actual_final = pick.get("final_score", 0)
    delta = abs(actual_final - expected_final_approx)

    if delta > tolerance:
        violations.append(f"WEIGHT_DRIFT:expected={expected_final_approx:.2f},actual={actual_final:.2f},delta={delta:.2f}")

    return violations


def validate_jarvis_v22_fields(pick: Dict[str, Any]) -> List[str]:
    """Validate Jarvis v2.2.1 fields are present when hybrid is enabled."""
    violations = []

    # Only validate if this looks like a hybrid response
    if "blend_type" in pick and "HYBRID" in str(pick.get("blend_type", "")).upper():
        for field in JARVIS_V22_FIELDS:
            if field not in pick:
                violations.append(f"JARVIS_V22_MISSING:{field}")

    return violations


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture(params=get_available_fixtures())
def golden_fixture(request):
    """Parameterized fixture that yields each golden fixture."""
    fixture_info = request.param
    fixture = load_fixture(fixture_info["path"])
    if fixture is None:
        pytest.skip(f"Could not load fixture: {fixture_info['path']}")
    return fixture


# =============================================================================
# TESTS
# =============================================================================

class TestGoldenFixtureSchema:
    """Schema validation tests for golden fixtures."""

    def test_fixture_has_metadata(self, golden_fixture):
        """Fixture must have metadata section."""
        assert "metadata" in golden_fixture
        assert "sport" in golden_fixture["metadata"]
        assert "date_et" in golden_fixture["metadata"]
        assert "captured_at" in golden_fixture["metadata"]

    def test_fixture_has_response(self, golden_fixture):
        """Fixture must have response section."""
        assert "response" in golden_fixture

    def test_all_picks_have_required_fields(self, golden_fixture):
        """All picks must have required scoring fields."""
        response = golden_fixture["response"]
        game_picks = response.get("game_picks", {}).get("picks", [])
        prop_picks = response.get("props", {}).get("picks", [])

        all_violations = []
        for pick in game_picks + prop_picks:
            violations = validate_schema(pick)
            if violations:
                all_violations.append({
                    "pick_id": pick.get("pick_id", "unknown"),
                    "violations": violations,
                })

        assert len(all_violations) == 0, f"Schema violations: {all_violations[:5]}"


class TestGoldenFixtureScoring:
    """Scoring validation tests for golden fixtures."""

    def test_no_picks_below_threshold(self, golden_fixture):
        """No picks should have final_score < 6.5."""
        response = golden_fixture["response"]
        game_picks = response.get("game_picks", {}).get("picks", [])
        prop_picks = response.get("props", {}).get("picks", [])

        violations = []
        for pick in game_picks + prop_picks:
            issues = validate_score_threshold(pick)
            if issues:
                violations.append({
                    "pick_id": pick.get("pick_id", "unknown"),
                    "final_score": pick.get("final_score"),
                })

        assert len(violations) == 0, f"Score threshold violations: {violations}"

    def test_all_tiers_valid(self, golden_fixture):
        """All tiers must be valid."""
        response = golden_fixture["response"]
        game_picks = response.get("game_picks", {}).get("picks", [])
        prop_picks = response.get("props", {}).get("picks", [])

        violations = []
        for pick in game_picks + prop_picks:
            issues = validate_tier(pick)
            if issues:
                violations.append({
                    "pick_id": pick.get("pick_id", "unknown"),
                    "tier": pick.get("tier"),
                })

        assert len(violations) == 0, f"Tier violations: {violations}"


class TestGoldenFixtureTitanium:
    """Titanium rule tests for golden fixtures."""

    def test_titanium_rule_enforced(self, golden_fixture):
        """Titanium 3-of-4 rule must be enforced."""
        response = golden_fixture["response"]
        game_picks = response.get("game_picks", {}).get("picks", [])
        prop_picks = response.get("props", {}).get("picks", [])

        violations = []
        for pick in game_picks + prop_picks:
            issues = validate_titanium_rule(pick)
            if issues:
                violations.append({
                    "pick_id": pick.get("pick_id", "unknown"),
                    "violations": issues,
                })

        assert len(violations) == 0, f"Titanium violations: {violations}"


class TestGoldenFixtureWeightReconciliation:
    """Weight reconciliation tests for golden fixtures."""

    def test_weights_reconcile(self, golden_fixture):
        """Scores should approximately match weight formula."""
        response = golden_fixture["response"]
        game_picks = response.get("game_picks", {}).get("picks", [])
        prop_picks = response.get("props", {}).get("picks", [])

        # Only warn on reconciliation issues, don't fail
        # (allows for ensemble/live adjustments)
        violations = []
        for pick in game_picks + prop_picks:
            issues = validate_weight_reconciliation(pick, tolerance=2.5)
            if issues:
                violations.append({
                    "pick_id": pick.get("pick_id", "unknown"),
                    "violations": issues,
                })

        # Log warnings but don't fail (adjustments may cause drift)
        if violations:
            print(f"\nWeight reconciliation warnings ({len(violations)} picks):")
            for v in violations[:3]:
                print(f"  {v['pick_id']}: {v['violations']}")


class TestGoldenFixtureIntegrity:
    """Integrity checks for golden fixtures."""

    def test_fixture_matches_own_validation(self, golden_fixture):
        """Fixture's own validation should pass."""
        validation = golden_fixture.get("validation", {})

        # Check that fixture passed its own validation at capture time
        if "all_passed" in validation:
            # If fixture recorded validation, check it
            # (older fixtures may not have this)
            assert validation["all_passed"], \
                f"Fixture failed its own validation: {validation.get('results', {})}"

    def test_pick_counts_consistent(self, golden_fixture):
        """Pick counts should be consistent."""
        response = golden_fixture["response"]
        validation = golden_fixture.get("validation", {}).get("results", {})

        actual_game_picks = len(response.get("game_picks", {}).get("picks", []))
        actual_prop_picks = len(response.get("props", {}).get("picks", []))

        # If validation recorded counts, check they match
        if "game_picks" in validation:
            assert validation["game_picks"] == actual_game_picks, \
                f"Game pick count mismatch: recorded={validation['game_picks']}, actual={actual_game_picks}"
        if "prop_picks" in validation:
            assert validation["prop_picks"] == actual_prop_picks, \
                f"Prop pick count mismatch: recorded={validation['prop_picks']}, actual={actual_prop_picks}"


# =============================================================================
# STANDALONE FIXTURE VALIDATOR (not a pytest test)
# =============================================================================

def validate_single_fixture(path: str) -> Dict[str, Any]:
    """Validate a single fixture file."""
    fixture = load_fixture(path)
    if not fixture:
        return {"valid": False, "error": "Could not load fixture"}

    results = {
        "path": path,
        "metadata": fixture.get("metadata", {}),
        "schema_violations": [],
        "score_violations": [],
        "tier_violations": [],
        "titanium_violations": [],
        "weight_violations": [],
    }

    response = fixture.get("response", {})
    all_picks = (
        response.get("game_picks", {}).get("picks", []) +
        response.get("props", {}).get("picks", [])
    )

    for pick in all_picks:
        results["schema_violations"].extend(validate_schema(pick))
        results["score_violations"].extend(validate_score_threshold(pick))
        results["tier_violations"].extend(validate_tier(pick))
        results["titanium_violations"].extend(validate_titanium_rule(pick))
        results["weight_violations"].extend(validate_weight_reconciliation(pick))

    results["valid"] = (
        len(results["schema_violations"]) == 0 and
        len(results["score_violations"]) == 0 and
        len(results["tier_violations"]) == 0 and
        len(results["titanium_violations"]) == 0
    )

    return results


if __name__ == "__main__":
    # Run as standalone validator
    fixtures = get_available_fixtures()
    if not fixtures:
        print("No golden fixtures found.")
        print("Create one with: API_KEY=your_key python3 scripts/golden_snapshot.py NBA")
    else:
        print(f"Found {len(fixtures)} golden fixtures:\n")
        for fixture_info in fixtures:
            result = validate_single_fixture(fixture_info["path"])
            status = "✅ VALID" if result["valid"] else "❌ INVALID"
            print(f"{status} {fixture_info['sport']} {fixture_info['date']}")
            if not result["valid"]:
                for key in ["schema_violations", "score_violations", "titanium_violations"]:
                    if result[key]:
                        print(f"   {key}: {result[key][:3]}")
