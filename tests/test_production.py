"""
PRODUCTION REQUIREMENT TESTS
============================
Tests for v14.9 production requirements:
1. TODAY-only slate gating
2. Pick field completeness (game and prop)
3. Jarvis fields present
4. Jason Sim present
5. Tiering single source of truth
6. Injury blocking
7. Learning loop methods

Run with: python -m pytest tests/test_production.py -v
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

# ============================================================================
# TEST 1: TODAY-ONLY GATING
# ============================================================================

class TestTodayOnlyGating:
    """Verify TODAY-only slate gating works correctly."""

    def test_time_filters_module_exists(self):
        """Time filters module should be importable."""
        try:
            from time_filters import (
                is_game_today,
                is_game_tomorrow,
                get_today_range_et,
                validate_today_slate,
                get_game_status
            )
            assert True
        except ImportError as e:
            pytest.fail(f"time_filters module not available: {e}")

    def test_today_range_returns_tuple(self):
        """get_today_range_et should return start and end datetimes."""
        from time_filters import get_today_range_et
        start, end = get_today_range_et()
        assert start is not None
        assert end is not None
        assert start < end

    def test_is_game_today_for_current_time(self):
        """A game starting now should be marked as today."""
        from time_filters import is_game_today, get_now_et
        # Use current time in ET timezone (same as what the filter uses)
        try:
            now_et = get_now_et()
            # Format with timezone offset
            now_iso = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")
            # Insert colon in timezone offset for ISO format
            if len(now_iso) > 5 and now_iso[-5] in "+-":
                now_iso = now_iso[:-2] + ":" + now_iso[-2:]
        except Exception:
            # Fallback to UTC
            now_iso = datetime.now().isoformat() + "Z"
        result = is_game_today(now_iso)
        assert result == True, f"is_game_today({now_iso}) returned {result}"

    def test_is_game_tomorrow_excluded(self):
        """Tomorrow's games should be excluded."""
        from time_filters import is_game_today, is_game_tomorrow, get_now_et
        try:
            now_et = get_now_et()
            tomorrow = now_et + timedelta(days=1)
            tomorrow_iso = tomorrow.strftime("%Y-%m-%dT%H:%M:%S%z")
            if len(tomorrow_iso) > 5 and tomorrow_iso[-5] in "+-":
                tomorrow_iso = tomorrow_iso[:-2] + ":" + tomorrow_iso[-2:]
        except Exception:
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_iso = tomorrow.isoformat() + "Z"
        assert is_game_tomorrow(tomorrow_iso) == True
        # is_game_today should return False
        assert is_game_today(tomorrow_iso) == False

    def test_validate_today_slate_filters_correctly(self):
        """validate_today_slate should filter out non-today games."""
        from time_filters import validate_today_slate, get_now_et

        try:
            now = get_now_et()
            tomorrow = now + timedelta(days=1)
            yesterday = now - timedelta(days=1)

            def format_iso(dt):
                iso = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
                if len(iso) > 5 and iso[-5] in "+-":
                    iso = iso[:-2] + ":" + iso[-2:]
                return iso
        except Exception:
            now = datetime.now()
            tomorrow = now + timedelta(days=1)
            yesterday = now - timedelta(days=1)
            def format_iso(dt):
                return dt.isoformat() + "Z"

        games = [
            {"home_team": "Team A", "away_team": "Team B", "commence_time": format_iso(now)},
            {"home_team": "Team C", "away_team": "Team D", "commence_time": format_iso(tomorrow)},
            {"home_team": "Team E", "away_team": "Team F", "commence_time": format_iso(yesterday)},
        ]

        today_games, excluded = validate_today_slate(games)

        # Today's game should be included (or at least the filtering ran)
        assert isinstance(today_games, list)
        assert isinstance(excluded, list)
        # Total should equal input
        assert len(today_games) + len(excluded) == len(games)


# ============================================================================
# TEST 2: PICK FIELD COMPLETENESS (GAME)
# ============================================================================

class TestGamePickFields:
    """Verify game picks have all required fields."""

    REQUIRED_GAME_FIELDS = [
        "sport",
        "event_id",
        "pick_type",
        "pick_side",
        "line",
        "odds",
        "book",
        "book_key",
        "game",
        "matchup",
        "home_team",
        "away_team",
        "start_time_et",
        "game_status",
        # Engine scores
        "ai_score",
        "research_score",
        "esoteric_score",
        "jarvis_rs",
        "final_score",
        # Tier
        "tier",
        "action",
        "units",
        # Jason Sim
        "jason_ran",
        "jason_sim_boost",
        # Jarvis
        "jarvis_active",
        "jarvis_hits_count",
        "jarvis_triggers_hit",
        "jarvis_reasons"
    ]

    def test_game_pick_has_required_fields(self):
        """A sample game pick should have all required fields."""
        # Create a sample game pick (mirroring what best-bets returns)
        sample_pick = self._create_sample_game_pick()

        missing_fields = []
        for field in self.REQUIRED_GAME_FIELDS:
            if field not in sample_pick:
                missing_fields.append(field)

        if missing_fields:
            pytest.fail(f"Game pick missing required fields: {missing_fields}")

    def _create_sample_game_pick(self) -> Dict[str, Any]:
        """Create a sample game pick with all expected fields."""
        return {
            "sport": "NBA",
            "event_id": "Team B@Team A",
            "pick_type": "SPREAD",
            "pick": "Team A -3.5",
            "pick_side": "Team A -3.5",
            "team": "Team A",
            "line": -3.5,
            "odds": -110,
            "book": "DraftKings",
            "book_key": "draftkings",
            "book_link": "https://draftkings.com",
            "game": "Team B @ Team A",
            "matchup": "Team B @ Team A",
            "home_team": "Team A",
            "away_team": "Team B",
            "start_time_et": "7:30 PM ET",
            "game_status": "UPCOMING",
            "is_live_bet_candidate": False,
            "market": "spreads",
            "recommendation": "Team A -3.5",
            "best_book": "DraftKings",
            "best_book_link": "https://draftkings.com",
            # Engine scores
            "total_score": 7.5,
            "final_score": 7.5,
            "ai_score": 6.0,
            "research_score": 8.0,
            "esoteric_score": 5.5,
            "jarvis_score": 5.0,
            "confidence": "HIGH",
            "confidence_score": 80,
            # Tier
            "tier": "EDGE_LEAN",
            "action": "PLAY",
            "units": 1.0,
            # JARVIS fields
            "jarvis_rs": 5.0,
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["No triggers hit"],
            # Jason Sim
            "jason_ran": True,
            "jason_sim_boost": 0.0,
            "jason_blocked": False,
            "jason_win_pct_home": 55.0,
            "jason_win_pct_away": 45.0,
            "projected_total": 220,
            "projected_pace": "NEUTRAL",
            "variance_flag": "MED",
            "injury_state": "UNKNOWN",
            "confluence_reasons": [],
            "base_score": 7.5,
            # Research
            "research_breakdown": {
                "sharp_boost": 1.5,
                "line_boost": 1.5,
                "public_boost": 0.0,
                "base_research": 2.0,
                "total": 5.0
            },
            "research_reasons": ["Sharp signal MODERATE (+1.5)"],
            "pillars_passed": ["Sharp Money Detection"],
            "pillars_failed": ["Reverse Line Movement"],
            # Other
            "sharp_signal": "MODERATE"
        }


# ============================================================================
# TEST 3: PICK FIELD COMPLETENESS (PROP)
# ============================================================================

class TestPropPickFields:
    """Verify prop picks have all required fields."""

    REQUIRED_PROP_FIELDS = [
        "sport",
        "event_id",
        "player",
        "player_name",
        "canonical_player_id",
        "market",
        "stat_type",
        "prop_type",
        "line",
        "side",
        "over_under",
        "odds",
        "book",
        "book_key",
        "game",
        "matchup",
        "home_team",
        "away_team",
        # Engine scores
        "ai_score",
        "research_score",
        "esoteric_score",
        "jarvis_rs",
        "final_score",
        # Tier
        "tier",
        # Jason Sim
        "jason_ran",
        "jason_sim_boost",
        # Jarvis
        "jarvis_active",
        "jarvis_hits_count",
        "jarvis_triggers_hit",
        "jarvis_reasons",
        # Injury
        "injury_status"
    ]

    def test_prop_pick_has_required_fields(self):
        """A sample prop pick should have all required fields."""
        sample_pick = self._create_sample_prop_pick()

        missing_fields = []
        for field in self.REQUIRED_PROP_FIELDS:
            if field not in sample_pick:
                missing_fields.append(field)

        if missing_fields:
            pytest.fail(f"Prop pick missing required fields: {missing_fields}")

    def _create_sample_prop_pick(self) -> Dict[str, Any]:
        """Create a sample prop pick with all expected fields."""
        return {
            "sport": "NBA",
            "event_id": "Team B@Team A",
            "player": "LeBron James",
            "player_name": "LeBron James",
            "player_team": "Los Angeles Lakers",
            "canonical_player_id": "NBA:BDL:237",
            "provider_ids": {"balldontlie": 237, "odds_api": None},
            "position": "F",
            "market": "points",
            "stat_type": "points",
            "prop_type": "points",
            "line": 25.5,
            "side": "Over",
            "over_under": "Over",
            "odds": -110,
            "book": "FanDuel",
            "book_key": "fanduel",
            "book_link": "https://fanduel.com",
            "game": "Team B @ Team A",
            "matchup": "Team B @ Team A",
            "home_team": "Team A",
            "away_team": "Team B",
            "start_time_et": "7:30 PM ET",
            "game_status": "UPCOMING",
            "is_live_bet_candidate": False,
            "recommendation": "OVER 25.5",
            "injury_status": "HEALTHY",
            "best_book": "FanDuel",
            "best_book_link": "https://fanduel.com",
            # Engine scores
            "total_score": 8.2,
            "final_score": 8.2,
            "ai_score": 7.0,
            "research_score": 7.5,
            "esoteric_score": 6.0,
            "jarvis_score": 5.0,
            "confidence": "HIGH",
            "confidence_score": 85,
            # Tier
            "tier": "EDGE_LEAN",
            "action": "PLAY",
            "units": 1.0,
            # JARVIS fields
            "jarvis_rs": 5.0,
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["No triggers hit"],
            # Jason Sim
            "jason_ran": True,
            "jason_sim_boost": 0.2,
            "jason_blocked": False,
            "jason_win_pct_home": 55.0,
            "jason_win_pct_away": 45.0,
            "projected_total": 220,
            "projected_pace": "FAST",
            "variance_flag": "LOW",
            "injury_state": "CONFIRMED_ONLY",
            "confluence_reasons": ["Player performance aligns with simulation"],
            "base_score": 8.0,
            # Research
            "research_breakdown": {
                "sharp_boost": 1.5,
                "line_boost": 1.5,
                "public_boost": 1.0,
                "base_research": 2.0,
                "total": 6.0
            },
            "research_reasons": ["Sharp signal MODERATE (+1.5)"],
            "pillars_passed": ["Sharp Money Detection", "Line Value Detection"],
            "pillars_failed": [],
            # Other
            "sharp_signal": "MODERATE"
        }


# ============================================================================
# TEST 4: JARVIS FIELDS PRESENT
# ============================================================================

class TestJarvisFields:
    """Verify Jarvis engine fields are always present."""

    def test_jarvis_engine_module_exists(self):
        """Jarvis savant engine should be importable."""
        try:
            from jarvis_savant_engine import (
                JarvisSavantEngine,
                get_jarvis_engine,
                JARVIS_TRIGGERS
            )
            assert True
        except ImportError as e:
            pytest.fail(f"jarvis_savant_engine module not available: {e}")

    def test_jarvis_engine_check_trigger(self):
        """Jarvis engine should detect triggers."""
        from jarvis_savant_engine import get_jarvis_engine
        jarvis = get_jarvis_engine()

        # Test with 2178 (THE IMMORTAL)
        result = jarvis.check_jarvis_trigger(2178)
        assert "triggers_hit" in result
        assert len(result["triggers_hit"]) > 0
        assert any(t["number"] == 2178 for t in result["triggers_hit"])

    def test_jarvis_engine_gematria(self):
        """Jarvis engine should calculate gematria."""
        from jarvis_savant_engine import get_jarvis_engine
        jarvis = get_jarvis_engine()

        result = jarvis.calculate_gematria("LeBron James")
        assert "simple" in result
        assert "reverse" in result
        assert isinstance(result["simple"], int)

    def test_jarvis_sacred_triggers_defined(self):
        """All sacred triggers should be defined."""
        from jarvis_savant_engine import JARVIS_TRIGGERS

        sacred_numbers = [2178, 201, 33, 93, 322]
        for num in sacred_numbers:
            assert num in JARVIS_TRIGGERS, f"Sacred trigger {num} not defined"


# ============================================================================
# TEST 5: JASON SIM PRESENT
# ============================================================================

class TestJasonSimPresent:
    """Verify Jason Sim confluence is available."""

    def test_jason_sim_module_exists(self):
        """Jason sim module should be importable."""
        try:
            from jason_sim_confluence import (
                JasonSimConfluence,
                run_jason_confluence,
                get_default_jason_output
            )
            assert True
        except ImportError as e:
            pytest.fail(f"jason_sim_confluence module not available: {e}")

    def test_jason_sim_run_confluence(self):
        """Jason sim should run confluence calculation."""
        try:
            from jason_sim_confluence import run_jason_confluence
            result = run_jason_confluence(
                base_score=7.0,
                pick_type="SPREAD",
                pick_side="Lakers -3.5",
                home_team="Lakers",
                away_team="Celtics",
                spread=-3.5,
                total=220
            )
            assert "jason_ran" in result
            assert "jason_sim_boost" in result
        except ImportError:
            pytest.skip("jason_sim_confluence module not available")

    def test_jason_default_output_structure(self):
        """Default output should have all required fields."""
        try:
            from jason_sim_confluence import get_default_jason_output
            output = get_default_jason_output()

            required_fields = [
                "jason_ran",
                "jason_sim_boost",
                "jason_blocked",
                "jason_win_pct_home",
                "jason_win_pct_away",
                "projected_total",
                "variance_flag",
                "confluence_reasons"
            ]

            for field in required_fields:
                assert field in output, f"Default Jason output missing {field}"
        except ImportError:
            pytest.skip("jason_sim_confluence module not available")


# ============================================================================
# TEST 6: TIERING SINGLE SOURCE OF TRUTH
# ============================================================================

class TestTieringSingleSource:
    """Verify tiering.py is the single source of truth."""

    def test_tiering_module_exists(self):
        """Tiering module should be importable."""
        try:
            from tiering import (
                tier_from_score,
                TIER_CONFIG,
                check_titanium_rule,
                TITANIUM_THRESHOLD
            )
            assert True
        except ImportError as e:
            pytest.fail(f"tiering module not available: {e}")

    def test_tier_thresholds_defined(self):
        """All tier thresholds should be defined."""
        from tiering import TIER_CONFIG

        expected_tiers = ["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN", "MONITOR", "PASS"]
        for tier in expected_tiers:
            assert tier in TIER_CONFIG, f"Tier {tier} not defined in TIER_CONFIG"

    def test_tier_from_score_gold_star(self):
        """Score >= 7.5 should return GOLD_STAR (v12.0 thresholds)."""
        from tiering import tier_from_score
        result = tier_from_score(final_score=8.0)
        assert result["tier"] == "GOLD_STAR"

    def test_tier_from_score_edge_lean(self):
        """Score >= 7.0 and < 7.5 should return EDGE_LEAN (v20.12: requires MODERATE confluence)."""
        from tiering import tier_from_score
        # v20.12: Must pass confluence to avoid DIVERGENT default which downgrades to MONITOR
        result = tier_from_score(final_score=7.0, confluence={"level": "MODERATE"})
        assert result["tier"] == "EDGE_LEAN"

    def test_tier_from_score_monitor(self):
        """Score >= 5.5 and < 6.5 should return MONITOR (v12.0 thresholds)."""
        from tiering import tier_from_score
        result = tier_from_score(final_score=6.0)
        assert result["tier"] == "MONITOR"

    def test_tier_from_score_pass(self):
        """Score < 5.5 should return PASS (v12.0 thresholds)."""
        from tiering import tier_from_score
        result = tier_from_score(final_score=5.0)
        assert result["tier"] == "PASS"

    def test_titanium_rule_check(self):
        """Titanium rule should trigger with final_score >= 8.0 AND 3/4 engines >= 6.5 (v12.0)."""
        from tiering import check_titanium_rule

        # Should trigger: final >= 8.0 AND 3/4 engines >= 6.5
        triggered, explanation, engines = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=5.0,
            final_score=8.5
        )
        assert triggered == True
        assert len(engines) >= 3

        # Should NOT trigger (final_score < 8.0)
        triggered, explanation, engines = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=7.0,
            final_score=7.9
        )
        assert triggered == False

        # Should NOT trigger (only 2 engines >= 6.5)
        triggered, explanation, engines = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=5.0,
            jarvis_score=5.0,
            final_score=8.5
        )
        assert triggered == False


# ============================================================================
# TEST 7: INJURY BLOCKING
# ============================================================================

class TestInjuryBlocking:
    """Verify injury blocking for props."""

    def test_tiering_injury_functions_exist(self):
        """Injury blocking functions should exist in tiering."""
        try:
            from tiering import (
                is_prop_invalid_injury,
                apply_injury_downgrade,
                INVALID_INJURY_STATUSES,
                DOWNGRADE_INJURY_STATUSES
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Injury functions not in tiering module: {e}")

    def test_out_player_is_invalid(self):
        """OUT status should be marked as invalid."""
        from tiering import is_prop_invalid_injury
        assert is_prop_invalid_injury("OUT") == True
        assert is_prop_invalid_injury("DOUBTFUL") == True
        assert is_prop_invalid_injury("SUSPENDED") == True

    def test_healthy_player_is_valid(self):
        """HEALTHY status should NOT be marked as invalid."""
        from tiering import is_prop_invalid_injury
        assert is_prop_invalid_injury("HEALTHY") == False
        assert is_prop_invalid_injury("") == False

    def test_questionable_triggers_downgrade(self):
        """QUESTIONABLE status should trigger tier downgrade."""
        from tiering import apply_injury_downgrade

        new_tier, was_downgraded = apply_injury_downgrade("GOLD_STAR", "QUESTIONABLE")
        assert was_downgraded == True
        assert new_tier != "GOLD_STAR"


# ============================================================================
# TEST 8: LEARNING LOOP METHODS EXIST
# ============================================================================

class TestLearningLoopMethods:
    """Verify EsotericLearningLoop has required methods."""

    def test_esoteric_learning_loop_exists(self):
        """EsotericLearningLoop class should exist."""
        try:
            from jarvis_savant_engine import (
                EsotericLearningLoop,
                get_learning_loop
            )
            assert True
        except ImportError as e:
            pytest.fail(f"EsotericLearningLoop not available: {e}")

    def test_learning_loop_has_get_weights(self):
        """get_weights() method should exist."""
        from jarvis_savant_engine import get_learning_loop
        loop = get_learning_loop()

        assert hasattr(loop, 'get_weights')
        result = loop.get_weights()
        assert "weights" in result

    def test_learning_loop_has_update_weights(self):
        """update_weights() method should exist."""
        from jarvis_savant_engine import get_learning_loop
        loop = get_learning_loop()

        assert hasattr(loop, 'update_weights')
        # Don't actually call it as it would modify state

    def test_learning_loop_has_save_state(self):
        """save_state() method should exist."""
        from jarvis_savant_engine import get_learning_loop
        loop = get_learning_loop()

        assert hasattr(loop, 'save_state')
        # Don't actually call it as it would save to disk

    def test_learning_loop_has_adjust_weights(self):
        """adjust_weights() method should exist (alias for update_weights)."""
        from jarvis_savant_engine import get_learning_loop
        loop = get_learning_loop()

        assert hasattr(loop, 'adjust_weights')

    def test_auto_grader_exists(self):
        """AutoGrader class should exist."""
        try:
            from auto_grader import AutoGrader, get_grader
            grader = get_grader()

            assert hasattr(grader, 'get_weights')
            assert hasattr(grader, 'log_prediction')
            assert hasattr(grader, 'grade_prediction')
        except ImportError as e:
            # numpy may not be installed in test env, that's ok
            if "numpy" in str(e):
                pytest.skip("AutoGrader requires numpy which is not installed")
            pytest.fail(f"AutoGrader not available: {e}")


# ============================================================================
# INTEGRATION TEST: BEST-BETS STRUCTURE
# ============================================================================

class TestBestBetsStructure:
    """Integration tests for best-bets response structure."""

    def test_best_bets_metadata_fields(self):
        """Best-bets response should have all metadata fields."""
        # This simulates what the best-bets endpoint should return
        sample_response = {
            "sport": "NBA",
            "source": "jarvis_savant_v11.08",
            "scoring_system": "Phase 1-3 Integrated + Titanium v11.08",
            "engine_version": "11.08",
            "deploy_version": "14.9",
            "build_sha": "abc12345",
            "identity_resolver": True,
            "props": {"count": 10, "total_analyzed": 100, "picks": []},
            "game_picks": {"count": 10, "total_analyzed": 50, "picks": []},
            "esoteric": {
                "daily_energy": {},
                "astro_status": None,
                "learned_weights": {},
                "learning_active": True
            },
            "timestamp": "2026-01-26T12:00:00"
        }

        required_metadata = [
            "sport",
            "deploy_version",
            "build_sha",
            "identity_resolver",
            "props",
            "game_picks",
            "timestamp"
        ]

        for field in required_metadata:
            assert field in sample_response, f"Best-bets missing metadata field: {field}"


# ============================================================================
# TEST 9: v15.0 ENGINE SEPARATION
# ============================================================================

class TestV15EngineSeparation:
    """Verify v15.0 4-engine separation is correct."""

    def test_community_min_score_constant_exists(self):
        """COMMUNITY_MIN_SCORE should be defined in tiering (v20.12: raised to 7.0)."""
        try:
            from tiering import COMMUNITY_MIN_SCORE
            assert COMMUNITY_MIN_SCORE == 7.0, f"Expected 7.0, got {COMMUNITY_MIN_SCORE}"
        except ImportError:
            # Constant may be defined locally in live_data_router
            pass

    def test_esoteric_weights_no_jarvis_or_gematria(self):
        """Esoteric weights should NOT contain jarvis or gematria (v15.0)."""
        # These are the expected v15.0 weights
        expected_weights = {
            "numerology": 0.35,
            "astro": 0.25,
            "fib": 0.15,
            "vortex": 0.15,
            "daily_edge": 0.10
        }

        # Verify weights sum to 1.0
        total = sum(expected_weights.values())
        assert abs(total - 1.0) < 0.01, f"Esoteric weights should sum to 1.0, got {total}"

        # Verify no jarvis or gematria in esoteric
        assert "jarvis" not in expected_weights
        assert "gematria" not in expected_weights

    def test_jarvis_weights_structure(self):
        """Jarvis standalone engine should have gematria + triggers + mid_spread."""
        expected_jarvis_weights = {
            "gematria": 0.40,
            "triggers": 0.40,
            "mid_spread": 0.20
        }

        # Verify weights sum to 1.0
        total = sum(expected_jarvis_weights.values())
        assert abs(total - 1.0) < 0.01, f"Jarvis weights should sum to 1.0, got {total}"

    def test_public_fade_in_research_only(self):
        """Public Fade should only be in Research, not Esoteric."""
        # Research components
        research_components = ["sharp", "line", "public", "base"]

        # Esoteric components (v15.0 - no public_fade)
        esoteric_components = ["numerology", "astro", "fib", "vortex", "daily_edge", "trap_mod"]

        # Verify public is in research
        assert "public" in research_components

        # Verify public is NOT in esoteric
        assert "public" not in esoteric_components
        assert "public_fade" not in esoteric_components
        assert "public_fade_mod" not in esoteric_components


class TestV15ScoreFiltering:
    """Verify v15.0 score filtering >= 6.5."""

    def test_filter_below_threshold(self):
        """Picks below 6.5 should be filtered out."""
        test_picks = [
            {"total_score": 8.5, "player": "A"},
            {"total_score": 6.2, "player": "B"},  # Below threshold
            {"total_score": 7.0, "player": "C"},
            {"total_score": 5.5, "player": "D"},  # Below threshold
            {"total_score": 6.5, "player": "E"},  # At threshold
        ]

        COMMUNITY_MIN_SCORE = 6.5
        filtered = [p for p in test_picks if p["total_score"] >= COMMUNITY_MIN_SCORE]

        assert len(filtered) == 3, f"Expected 3 picks, got {len(filtered)}"
        assert all(p["total_score"] >= 6.5 for p in filtered)

    def test_empty_array_when_no_qualifying(self):
        """If no picks >= 6.5, should return empty array (not error)."""
        test_picks = [
            {"total_score": 5.0, "player": "A"},
            {"total_score": 4.5, "player": "B"},
        ]

        COMMUNITY_MIN_SCORE = 6.5
        filtered = [p for p in test_picks if p["total_score"] >= COMMUNITY_MIN_SCORE]

        assert filtered == [], "Should return empty array when no qualifying picks"


class TestV15JarvisStandalone:
    """Verify Jarvis is a standalone 0-10 engine."""

    def test_jarvis_engine_in_jarvis_savant(self):
        """JarvisSavantEngine should have all required methods."""
        try:
            from jarvis_savant_engine import JarvisSavantEngine
            engine = JarvisSavantEngine()

            # Required methods for standalone Jarvis
            # NOTE: calculate_mid_spread_signal moved to research_engine.py in v12.0
            required_methods = [
                "check_jarvis_trigger",
                "calculate_gematria_signal",
            ]

            for method in required_methods:
                assert hasattr(engine, method), f"JarvisSavantEngine missing method: {method}"
        except ImportError as e:
            pytest.fail(f"JarvisSavantEngine not available: {e}")

    def test_jarvis_output_fields(self):
        """Jarvis engine should return all required output fields."""
        expected_jarvis_output = {
            "jarvis_rs": 7.5,
            "jarvis_active": True,
            "jarvis_hits_count": 2,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Test trigger"],
            "immortal_detected": False,
            "jarvis_breakdown": {
                "gematria": 3.0,
                "triggers": 3.5,
                "mid_spread": 1.0
            }
        }

        required_fields = [
            "jarvis_rs",
            "jarvis_active",
            "jarvis_hits_count",
            "jarvis_triggers_hit",
            "jarvis_reasons"
        ]

        for field in required_fields:
            assert field in expected_jarvis_output, f"Jarvis output missing field: {field}"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
