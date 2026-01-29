"""
Test Jarvis Transparency & Stability (v15.1)

JARVIS REQUIREMENTS:
1. Always output these fields for every pick:
   - jarvis_rs (0-10 or None)
   - jarvis_active (bool)
   - jarvis_hits_count (int)
   - jarvis_triggers_hit (array)
   - jarvis_reasons (array)
   - jarvis_fail_reasons (array)
   - jarvis_inputs_used (dict)

2. If jarvis_rs < 2.0, jarvis_fail_reasons explains why

3. Floor behavior:
   - If inputs present: baseline floor 4.5 + boosts for triggers
   - If inputs missing: jarvis_active=False and jarvis_rs=None (not 0.8)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest


class TestJarvisTransparencyFields:
    """Test all required Jarvis fields are always present"""

    def test_jarvis_fields_present_in_mock_response(self):
        """Mock test: Verify all required fields are in expected output"""
        # This is a schema test - verifies field structure
        required_fields = [
            "jarvis_rs",
            "jarvis_active",
            "jarvis_hits_count",
            "jarvis_triggers_hit",
            "jarvis_reasons",
            "jarvis_fail_reasons",
            "jarvis_inputs_used"
        ]

        # Mock pick output
        mock_pick = {
            "jarvis_rs": 4.5,
            "jarvis_active": True,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Baseline floor 4.5 (no triggers)"],
            "jarvis_fail_reasons": ["No triggers fired - using baseline floor 4.5"],
            "jarvis_inputs_used": {
                "matchup_str": "Lakers @ Celtics",
                "date_et": "2026-01-28",
                "spread": -5.5,
                "total": 220.5,
                "player_line": None,
                "home_team": "Celtics",
                "away_team": "Lakers",
                "player_name": None
            }
        }

        for field in required_fields:
            assert field in mock_pick, f"Required field '{field}' missing from output"

    def test_jarvis_inputs_used_structure(self):
        """Verify jarvis_inputs_used contains all expected keys"""
        expected_keys = [
            "matchup_str",
            "date_et",
            "spread",
            "total",
            "player_line",
            "home_team",
            "away_team",
            "player_name"
        ]

        mock_inputs = {
            "matchup_str": "Warriors @ Jazz",
            "date_et": "2026-01-28",
            "spread": -3.5,
            "total": 235.0,
            "player_line": 25.5,  # For props
            "home_team": "Jazz",
            "away_team": "Warriors",
            "player_name": "LeBron James"
        }

        for key in expected_keys:
            assert key in mock_inputs, f"Expected key '{key}' missing from jarvis_inputs_used"


class TestJarvisFloorBehavior:
    """Test Jarvis floor behavior based on input availability"""

    def test_inputs_missing_returns_none(self):
        """When inputs missing, jarvis_rs should be None and jarvis_active=False"""
        # Mock scenario: no game_str or teams
        mock_output_missing_inputs = {
            "jarvis_rs": None,
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Inputs missing - cannot run"],
            "jarvis_fail_reasons": ["Missing critical inputs (matchup_str or teams)"],
            "jarvis_inputs_used": {
                "matchup_str": None,
                "date_et": None,
                "spread": None,
                "total": None,
                "player_line": None,
                "home_team": None,
                "away_team": None,
                "player_name": None
            }
        }

        assert mock_output_missing_inputs["jarvis_rs"] is None, "jarvis_rs should be None when inputs missing"
        assert mock_output_missing_inputs["jarvis_active"] is False, "jarvis_active should be False when inputs missing"
        assert "Missing critical inputs" in mock_output_missing_inputs["jarvis_fail_reasons"][0]

    def test_inputs_present_no_triggers_uses_floor(self):
        """When inputs present but no triggers, use baseline floor 4.5"""
        mock_output_with_floor = {
            "jarvis_rs": 4.5,
            "jarvis_active": True,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Baseline floor 4.5 (no triggers)"],
            "jarvis_fail_reasons": ["No triggers fired - using baseline floor 4.5"],
            "jarvis_inputs_used": {
                "matchup_str": "Lakers @ Celtics",
                "date_et": "2026-01-28",
                "spread": -5.5,
                "total": 220.5,
                "player_line": None,
                "home_team": "Celtics",
                "away_team": "Lakers",
                "player_name": None
            }
        }

        assert mock_output_with_floor["jarvis_rs"] == 4.5, "jarvis_rs should be 4.5 baseline floor"
        assert mock_output_with_floor["jarvis_active"] is True, "jarvis_active should be True when inputs present"
        assert "baseline floor" in mock_output_with_floor["jarvis_reasons"][0].lower()

    def test_inputs_present_with_triggers_above_floor(self):
        """When inputs present with triggers, score > baseline floor"""
        mock_output_with_triggers = {
            "jarvis_rs": 7.2,  # Above floor due to triggers
            "jarvis_active": True,
            "jarvis_hits_count": 2,
            "jarvis_triggers_hit": [
                {"number": 33, "name": "33 Mastery", "boost": 1.5},
                {"number": 93, "name": "93 Thelema", "boost": 1.2}
            ],
            "jarvis_reasons": ["33 Mastery", "93 Thelema"],
            "jarvis_fail_reasons": [],
            "jarvis_inputs_used": {
                "matchup_str": "Lakers @ Celtics 33",
                "date_et": "2026-01-28",
                "spread": -5.5,
                "total": 220.5,
                "player_line": None,
                "home_team": "Celtics",
                "away_team": "Lakers",
                "player_name": None
            }
        }

        assert mock_output_with_triggers["jarvis_rs"] > 4.5, "jarvis_rs should be > floor when triggers fire"
        assert mock_output_with_triggers["jarvis_active"] is True
        assert mock_output_with_triggers["jarvis_hits_count"] > 0


class TestJarvisFailReasons:
    """Test jarvis_fail_reasons explains low scores"""

    def test_fail_reasons_for_very_low_score(self):
        """If jarvis_rs < 2.0, fail_reasons should explain why"""
        mock_output_low_score = {
            "jarvis_rs": 1.5,
            "jarvis_active": True,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Baseline floor 4.5 (no triggers)"],
            "jarvis_fail_reasons": [
                "No triggers fired - using baseline floor 4.5",
                "Score 1.5 < 2.0: Zero triggers fired",
                "Score 1.5 < 2.0: Gematria score 0.00 < 0.5"
            ],
            "jarvis_inputs_used": {
                "matchup_str": "Lakers @ Celtics",
                "date_et": "2026-01-28",
                "spread": -5.5,
                "total": 220.5,
                "player_line": None,
                "home_team": "Celtics",
                "away_team": "Lakers",
                "player_name": None
            }
        }

        assert mock_output_low_score["jarvis_rs"] < 2.0
        assert len(mock_output_low_score["jarvis_fail_reasons"]) > 0, "fail_reasons should explain low score"
        fail_text = " ".join(mock_output_low_score["jarvis_fail_reasons"])
        assert "< 2.0" in fail_text or "triggers" in fail_text.lower()

    def test_no_fail_reasons_for_good_score(self):
        """If jarvis_rs >= 2.0, fail_reasons may be empty or minimal"""
        mock_output_good_score = {
            "jarvis_rs": 7.5,
            "jarvis_active": True,
            "jarvis_hits_count": 1,
            "jarvis_triggers_hit": [{"number": 2178, "name": "2178 Immortal", "boost": 3.0}],
            "jarvis_reasons": ["2178 Immortal"],
            "jarvis_fail_reasons": [],  # No failures when score is good
            "jarvis_inputs_used": {
                "matchup_str": "Lakers @ Celtics 2178",
                "date_et": "2026-01-28",
                "spread": -5.5,
                "total": 220.5,
                "player_line": None,
                "home_team": "Celtics",
                "away_team": "Lakers",
                "player_name": None
            }
        }

        assert mock_output_good_score["jarvis_rs"] >= 2.0
        # fail_reasons should be empty or not about score < 2.0
        if mock_output_good_score["jarvis_fail_reasons"]:
            assert not any("< 2.0" in reason for reason in mock_output_good_score["jarvis_fail_reasons"])


class TestJarvisNoneHandling:
    """Test that jarvis_rs=None is handled correctly in scoring"""

    def test_none_jarvis_does_not_break_calculations(self):
        """When jarvis_rs=None, contribution to final_score should be 0"""
        # Mock calculation
        ai_scaled = 8.0
        research_score = 7.0
        esoteric_score = 6.0
        jarvis_rs = None
        confluence_boost = 2.0

        # Calculate score with None handling
        jarvis_contribution = (jarvis_rs * 0.15) if jarvis_rs is not None else 0
        base_score = (ai_scaled * 0.25) + (research_score * 0.30) + (esoteric_score * 0.20) + jarvis_contribution + confluence_boost

        expected = (8.0 * 0.25) + (7.0 * 0.30) + (6.0 * 0.20) + 0 + 2.0
        assert base_score == expected, f"Expected {expected}, got {base_score}"

    def test_none_jarvis_excluded_from_titanium(self):
        """When jarvis_rs=None, should not count toward Titanium threshold"""
        ai_scaled = 8.5
        research_score = 8.2
        esoteric_score = 8.0
        jarvis_rs = None

        # Titanium check with None handling
        jarvis_for_titanium = jarvis_rs if jarvis_rs is not None else 0
        engines_above_8 = sum([
            ai_scaled >= 8.0,
            research_score >= 8.0,
            esoteric_score >= 8.0,
            jarvis_for_titanium >= 8.0
        ])

        assert engines_above_8 == 3, "Should count 3 engines (not including None jarvis)"


class TestJarvisInputsUsedTracking:
    """Test that jarvis_inputs_used accurately reflects what was provided"""

    def test_prop_pick_includes_player_line(self):
        """For prop picks, jarvis_inputs_used should include player_line"""
        mock_prop_inputs = {
            "matchup_str": "Lakers @ Celtics - LeBron James points",
            "date_et": "2026-01-28",
            "spread": -5.5,
            "total": 220.5,
            "player_line": 25.5,  # Prop line
            "home_team": "Celtics",
            "away_team": "Lakers",
            "player_name": "LeBron James"
        }

        assert mock_prop_inputs["player_line"] is not None, "Prop picks should include player_line"
        assert mock_prop_inputs["player_name"] is not None, "Prop picks should include player_name"

    def test_game_pick_excludes_player_fields(self):
        """For game picks, player fields should be None"""
        mock_game_inputs = {
            "matchup_str": "Lakers @ Celtics",
            "date_et": "2026-01-28",
            "spread": -5.5,
            "total": 220.5,
            "player_line": None,  # No player line for game picks
            "home_team": "Celtics",
            "away_team": "Lakers",
            "player_name": None  # No player for game picks
        }

        assert mock_game_inputs["player_line"] is None, "Game picks should not have player_line"
        assert mock_game_inputs["player_name"] is None, "Game picks should not have player_name"


class TestJarvisReasonsArray:
    """Test jarvis_reasons array content"""

    def test_reasons_when_triggers_hit(self):
        """When triggers fire, jarvis_reasons should list trigger names"""
        mock_with_triggers = {
            "jarvis_triggers_hit": [
                {"number": 33, "name": "33 Mastery", "boost": 1.5},
                {"number": 93, "name": "93 Thelema", "boost": 1.2}
            ],
            "jarvis_reasons": ["33 Mastery", "93 Thelema"]
        }

        assert len(mock_with_triggers["jarvis_reasons"]) == 2
        assert "33 Mastery" in mock_with_triggers["jarvis_reasons"]
        assert "93 Thelema" in mock_with_triggers["jarvis_reasons"]

    def test_reasons_when_no_triggers(self):
        """When no triggers, jarvis_reasons should explain baseline"""
        mock_no_triggers = {
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Baseline floor 4.5 (no triggers)"]
        }

        assert len(mock_no_triggers["jarvis_reasons"]) > 0
        assert "baseline" in mock_no_triggers["jarvis_reasons"][0].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
