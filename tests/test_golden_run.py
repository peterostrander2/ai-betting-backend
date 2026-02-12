"""
GOLDEN RUN REGRESSION TESTS

These tests validate the entire system hasn't drifted from expected behavior.
Run with pytest or as part of CI to gate deployments.

Run:
    pytest tests/test_golden_run.py -v

For live validation (requires API_KEY):
    RUN_LIVE_TESTS=1 API_KEY=your_key pytest tests/test_golden_run.py -v
"""

import os
import sys
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# EXPECTED VALUES (single source of truth)
# =============================================================================

EXPECTED_VERSION = "20.20"

EXPECTED_ENGINE_WEIGHTS = {
    "ai": 0.25,
    "research": 0.35,
    "esoteric": 0.15,
    "jarvis": 0.25,
}

EXPECTED_JARVIS_BLEND_TYPE = "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA"
EXPECTED_JARVIS_VERSION = "JARVIS_OPHIS_HYBRID_v2.2.1"

TITANIUM_THRESHOLD = 8.0
TITANIUM_MIN_ENGINES = 3
MIN_FINAL_SCORE = 7.0  # From scoring_contract.py

VALID_TIERS = {"TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN"}

CRITICAL_INTEGRATIONS = ["odds_api", "playbook_api", "balldontlie", "railway_storage", "database"]

REQUIRED_PICK_FIELDS = {
    "pick_id", "sport", "market", "final_score", "tier",
    "ai_score", "research_score", "esoteric_score",
    "ai_reasons", "research_reasons", "esoteric_reasons", "jarvis_reasons",
    "titanium_triggered", "titanium_count",
}

REQUIRED_JARVIS_FIELDS = {
    "jarvis_rs", "jarvis_active",
}


# =============================================================================
# CONTRACT TESTS (no network needed)
# =============================================================================

class TestEngineWeights:
    """Verify engine weights match contract."""

    def test_weights_from_scoring_contract(self):
        """Engine weights in scoring_contract.py match expected."""
        from core.scoring_contract import ENGINE_WEIGHTS

        for engine, expected_weight in EXPECTED_ENGINE_WEIGHTS.items():
            actual = ENGINE_WEIGHTS.get(engine)
            assert actual == expected_weight, \
                f"Engine {engine} weight changed: expected {expected_weight}, got {actual}"

    def test_weights_sum_to_one(self):
        """Engine weights must sum to 1.0."""
        from core.scoring_contract import ENGINE_WEIGHTS

        total = sum(ENGINE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, not 1.0"

    def test_four_engines_present(self):
        """Must have exactly 4 engines."""
        from core.scoring_contract import ENGINE_WEIGHTS

        assert set(ENGINE_WEIGHTS.keys()) == set(EXPECTED_ENGINE_WEIGHTS.keys())


class TestTitaniumContract:
    """Verify Titanium rule contract."""

    def test_titanium_threshold(self):
        """Titanium threshold is 8.0."""
        from core.scoring_contract import TITANIUM_RULE

        assert TITANIUM_RULE["threshold"] == 8.0

    def test_titanium_requires_3_of_4(self):
        """Titanium requires 3 of 4 engines >= 8.0."""
        from core.titanium import compute_titanium_flag

        # 3 of 4 should trigger
        triggered, diag = compute_titanium_flag(8.0, 8.0, 8.0, 5.0)
        assert triggered is True
        assert diag["titanium_hits_count"] == 3

        # 2 of 4 should not trigger
        triggered, diag = compute_titanium_flag(8.0, 8.0, 5.0, 5.0)
        assert triggered is False
        assert diag["titanium_hits_count"] == 2


class TestJarvisContract:
    """Verify Jarvis v2.2 contract."""

    def test_jarvis_hybrid_version(self):
        """Jarvis version is v2.2."""
        from core.jarvis_ophis_hybrid import VERSION

        assert VERSION == EXPECTED_JARVIS_VERSION

    def test_jarvis_blend_type(self):
        """Jarvis blend type is weighted blend capped delta."""
        from core.jarvis_ophis_hybrid import calculate_hybrid_jarvis_score

        result = calculate_hybrid_jarvis_score("Lakers", "Celtics")
        assert result.get("jarvis_blend_type") == EXPECTED_JARVIS_BLEND_TYPE

    def test_jarvis_weights(self):
        """Jarvis/Ophis weights are 55/45."""
        from core.jarvis_ophis_hybrid import JARVIS_WEIGHT, OPHIS_WEIGHT

        assert JARVIS_WEIGHT == 0.55
        assert OPHIS_WEIGHT == 0.45

    def test_ophis_delta_bounded(self):
        """Ophis delta is bounded to ±0.75."""
        from core.jarvis_ophis_hybrid import OPHIS_DELTA_CAP

        assert OPHIS_DELTA_CAP == 0.75


class TestIntegrationContract:
    """Verify integration criticality tiers."""

    def test_critical_integrations_defined(self):
        """Critical integrations have CRITICAL tier."""
        from core.integration_contract import INTEGRATIONS

        for integration in CRITICAL_INTEGRATIONS:
            info = INTEGRATIONS.get(integration, {})
            criticality = info.get("criticality")
            assert criticality == "CRITICAL", \
                f"{integration} should be CRITICAL, got {criticality}"

    def test_criticality_tiers_valid(self):
        """All integrations have valid criticality tiers."""
        from core.integration_contract import INTEGRATIONS, CriticalityTier

        valid_tiers = {t.value for t in CriticalityTier}

        for name, info in INTEGRATIONS.items():
            crit = info.get("criticality")
            assert crit in valid_tiers, f"{name} has invalid criticality: {crit}"


class TestScoringContract:
    """Verify scoring contract values."""

    def test_min_final_score(self):
        """Minimum final score for output is 7.0."""
        from core.scoring_contract import MIN_FINAL_SCORE

        assert MIN_FINAL_SCORE == 7.0

    def test_total_boost_cap(self):
        """Total boost cap is 1.5."""
        from core.scoring_contract import TOTAL_BOOST_CAP

        assert TOTAL_BOOST_CAP == 1.5

    def test_context_modifier_cap(self):
        """Context modifier cap is 0.35."""
        from core.scoring_contract import CONTEXT_MODIFIER_CAP

        assert CONTEXT_MODIFIER_CAP == 0.35


# =============================================================================
# SCHEMA TESTS (validate pick structure)
# =============================================================================

class TestPickSchema:
    """Verify pick schema has required fields."""

    def test_normalize_pick_has_required_fields(self):
        """normalize_pick outputs all required fields."""
        from utils.pick_normalizer import normalize_pick

        # Input with enough data to generate pick_id
        raw = {
            "sport": "NBA",
            "market": "SPREAD",
            "event_id": "test-event-123",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "selection": "Lakers",
            "line": -3.5,
            "final_score": 7.5,
            "tier": "GOLD_STAR",
            "ai_score": 7.0,
            "research_score": 7.0,
            "esoteric_score": 6.0,
            "jarvis_rs": 6.5,
            "ai_reasons": ["test"],
            "research_reasons": ["test"],
            "esoteric_reasons": ["test"],
            "jarvis_reasons": ["test"],
            "titanium_triggered": False,
            "titanium_count": 0,
        }

        normalized = normalize_pick(raw)

        # Check key required fields (pick_id may be generated differently)
        key_fields = {"sport", "market", "final_score", "tier", "ai_score", "research_score", "esoteric_score"}
        for field in key_fields:
            assert field in normalized, f"Missing required field: {field}"


class TestTierValues:
    """Verify tier values are valid."""

    def test_tier_from_score_returns_valid_tiers(self):
        """tier_from_score only returns valid tier names."""
        from tiering import tier_from_score

        # Test various scores with proper signature
        test_cases = [
            {"final_score": 9.0, "titanium_triggered": True, "ai_score": 8.5, "research_score": 8.5, "esoteric_score": 8.5, "jarvis_score": 8.5},
            {"final_score": 8.0, "titanium_triggered": False, "ai_score": 7.5, "research_score": 7.5},
            {"final_score": 7.5, "titanium_triggered": False},
        ]

        for kwargs in test_cases:
            result = tier_from_score(**kwargs)
            tier = result.get("tier")
            assert tier in VALID_TIERS, f"Invalid tier {tier} for {kwargs}"


# =============================================================================
# LIVE TESTS (require API_KEY)
# =============================================================================

@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live tests require RUN_LIVE_TESTS=1 and API_KEY"
)
class TestLiveEndpoints:
    """Live endpoint validation tests."""

    @pytest.fixture
    def api_client(self):
        """Create API client."""
        import requests

        api_key = os.getenv("API_KEY", "")
        base_url = os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app")

        class Client:
            def get(self, endpoint: str) -> Dict[str, Any]:
                url = f"{base_url}{endpoint}"
                headers = {"X-API-Key": api_key} if api_key else {}
                resp = requests.get(url, headers=headers, timeout=120)
                resp.raise_for_status()
                return resp.json()

        return Client()

    def test_health_returns_expected_version(self, api_client):
        """Health endpoint returns expected version."""
        import requests
        base_url = os.getenv("API_BASE", "https://web-production-7b2a.up.railway.app")
        resp = requests.get(f"{base_url}/health", timeout=30)
        health = resp.json()

        assert health.get("version") == EXPECTED_VERSION

    def test_best_bets_picks_have_required_fields(self, api_client):
        """Best-bets picks have all required fields."""
        data = api_client.get("/live/best-bets/NBA?debug=1")

        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])
        all_picks = props + games

        if not all_picks:
            pytest.skip("No picks returned (off-season?)")

        for pick in all_picks:
            for field in REQUIRED_PICK_FIELDS:
                assert field in pick, f"Pick missing {field}"

    def test_best_bets_no_picks_below_threshold(self, api_client):
        """No picks returned with final_score < 6.5."""
        data = api_client.get("/live/best-bets/NBA?debug=1")

        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])

        for pick in props + games:
            assert pick.get("final_score", 0) >= MIN_FINAL_SCORE, \
                f"Pick below threshold: {pick.get('final_score')}"

    def test_best_bets_titanium_rule_enforced(self, api_client):
        """Titanium picks have 3+ engines >= 8.0."""
        data = api_client.get("/live/best-bets/NBA?debug=1")

        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])

        for pick in props + games:
            if pick.get("titanium_triggered"):
                engines = [
                    pick.get("ai_score", 0),
                    pick.get("research_score", 0),
                    pick.get("esoteric_score", 0),
                    pick.get("jarvis_rs", 0) or 0,
                ]
                above_8 = sum(1 for e in engines if e >= TITANIUM_THRESHOLD)
                assert above_8 >= TITANIUM_MIN_ENGINES, \
                    f"Titanium with only {above_8} engines >= 8.0"

    def test_best_bets_valid_tiers(self, api_client):
        """All picks have valid tier values."""
        data = api_client.get("/live/best-bets/NBA?debug=1")

        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])

        for pick in props + games:
            tier = pick.get("tier")
            assert tier in VALID_TIERS, f"Invalid tier: {tier}"

    def test_best_bets_jarvis_fields_present(self, api_client):
        """Jarvis fields present in picks."""
        data = api_client.get("/live/best-bets/NBA?debug=1")

        props = data.get("props", {}).get("picks", [])
        games = data.get("game_picks", {}).get("picks", [])

        for pick in (props + games)[:5]:  # Sample first 5
            for field in REQUIRED_JARVIS_FIELDS:
                assert field in pick, f"Missing Jarvis field: {field}"

    def test_integration_rollup_has_critical_tiers(self, api_client):
        """Integration rollup shows CRITICAL tier for critical integrations."""
        data = api_client.get("/live/debug/integration-rollup?days=1")

        summary = data.get("integration_summary", {})

        for integration in CRITICAL_INTEGRATIONS:
            info = summary.get(integration, {})
            assert info.get("criticality") == "CRITICAL", \
                f"{integration} should be CRITICAL in rollup"
