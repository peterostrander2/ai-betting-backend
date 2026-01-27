"""
Tests for Grader Queue and Dry-Run Endpoints (v14.10)
====================================================

Tests the queue selector and dry-run validation functionality.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

# Mock PublishedPick for testing
@dataclass
class MockPublishedPick:
    """Mock pick for testing queue and dry-run."""
    pick_id: str
    sport: str
    player_name: str = ""
    matchup: str = ""
    prop_type: str = ""
    line: float = 0.0
    side: str = ""
    tier: str = "MONITOR"
    game_start_time_et: str = ""
    canonical_event_id: str = ""
    canonical_player_id: str = ""
    graded: bool = False
    result: Optional[str] = None


# Sample test data
MOCK_PICKS = [
    MockPublishedPick(
        pick_id="pick1",
        sport="NBA",
        player_name="LeBron James",
        matchup="Lakers vs Celtics",
        prop_type="points",
        line=25.5,
        side="Over",
        tier="GOLD_STAR",
        game_start_time_et="2026-01-26 19:00",
        canonical_event_id="NBA:ODDS:abc123",
        canonical_player_id="NBA:BDL:237",
        graded=False,
        result=None
    ),
    MockPublishedPick(
        pick_id="pick2",
        sport="NBA",
        player_name="Stephen Curry",
        matchup="Warriors vs Suns",
        prop_type="threes",
        line=4.5,
        side="Over",
        tier="EDGE_LEAN",
        game_start_time_et="2026-01-26 22:00",
        canonical_event_id="NBA:ODDS:def456",
        canonical_player_id="NBA:BDL:115",
        graded=False,
        result=None
    ),
    MockPublishedPick(
        pick_id="pick3",
        sport="NFL",
        player_name="Patrick Mahomes",
        matchup="Chiefs vs Bills",
        prop_type="passing_yards",
        line=285.5,
        side="Over",
        tier="GOLD_STAR",
        game_start_time_et="2026-01-26 18:30",
        canonical_event_id="NFL:ODDS:ghi789",
        canonical_player_id="NFL:NAME:patrick_mahomes|kc",
        graded=False,
        result=None
    ),
    MockPublishedPick(
        pick_id="pick4_unresolved",
        sport="NBA",
        player_name="Unknown Player",
        matchup="Lakers vs Celtics",
        prop_type="rebounds",
        line=8.5,
        side="Under",
        tier="MONITOR",
        game_start_time_et="2026-01-26 19:00",
        canonical_event_id="",  # Missing event ID
        canonical_player_id="",  # Missing player ID
        graded=False,
        result=None
    ),
    MockPublishedPick(
        pick_id="pick5_graded",
        sport="NBA",
        player_name="Anthony Davis",
        matchup="Lakers vs Celtics",
        prop_type="points",
        line=28.5,
        side="Under",
        tier="EDGE_LEAN",
        game_start_time_et="2026-01-26 19:00",
        canonical_event_id="NBA:ODDS:abc123",
        canonical_player_id="NBA:BDL:203",
        graded=True,
        result="WIN"
    ),
]


class TestQueueSelector:
    """Tests for the grader queue selector."""

    def test_filter_ungraded_picks(self):
        """Test that only ungraded picks are returned."""
        picks = MOCK_PICKS.copy()

        # Filter to ungraded only (same logic as endpoint)
        ungraded = [p for p in picks if not getattr(p, 'graded', False) and p.result is None]

        assert len(ungraded) == 4  # Excludes pick5_graded
        assert all(not p.graded for p in ungraded)
        assert all(p.result is None for p in ungraded)

    def test_filter_by_sport(self):
        """Test filtering by sport."""
        picks = MOCK_PICKS.copy()
        sport_filter = ["NBA"]

        filtered = [p for p in picks if p.sport.upper() in sport_filter]

        # Should include all NBA picks (4 total)
        assert len(filtered) == 4
        assert all(p.sport == "NBA" for p in filtered)

    def test_filter_by_multiple_sports(self):
        """Test filtering by multiple sports."""
        picks = MOCK_PICKS.copy()
        sport_filter = ["NBA", "NFL"]

        filtered = [p for p in picks if p.sport.upper() in sport_filter]

        # All 5 picks are NBA or NFL
        assert len(filtered) == 5

    def test_count_by_sport(self):
        """Test counting picks by sport."""
        picks = [p for p in MOCK_PICKS if not p.graded and p.result is None]

        by_sport = {}
        for p in picks:
            sport = p.sport.upper()
            by_sport[sport] = by_sport.get(sport, 0) + 1

        assert by_sport.get("NBA", 0) == 3  # pick1, pick2, pick4
        assert by_sport.get("NFL", 0) == 1  # pick3

    def test_queue_response_structure(self):
        """Test the structure of queue response."""
        picks = [p for p in MOCK_PICKS if not p.graded and p.result is None]

        # Simulate response building
        response = {
            "date": "2026-01-26",
            "total": len(picks),
            "by_sport": {},
            "picks": []
        }

        for p in picks:
            sport = p.sport.upper()
            response["by_sport"][sport] = response["by_sport"].get(sport, 0) + 1
            response["picks"].append({
                "pick_id": p.pick_id,
                "sport": p.sport,
                "player_name": p.player_name,
                "matchup": p.matchup,
                "canonical_event_id": p.canonical_event_id,
                "canonical_player_id": p.canonical_player_id,
            })

        assert response["total"] == 4
        assert "NBA" in response["by_sport"]
        assert len(response["picks"]) == 4


class TestDryRunValidation:
    """Tests for the dry-run validation endpoint."""

    def test_all_picks_resolved(self):
        """Test dry-run passes when all picks are resolved."""
        # Use only fully resolved picks
        picks = [MOCK_PICKS[0], MOCK_PICKS[1], MOCK_PICKS[2]]  # All have IDs

        results = {
            "total": len(picks),
            "passed": 0,
            "failed": 0,
            "pending": 0,
        }

        for pick in picks:
            event_ok = bool(pick.canonical_event_id) or bool(pick.matchup)
            player_ok = bool(pick.canonical_player_id) if pick.player_name else True

            if not event_ok or not player_ok:
                results["failed"] += 1
            elif pick.result is not None:
                results["passed"] += 1
            else:
                results["pending"] += 1

        # All should be pending (not yet graded, but valid)
        assert results["failed"] == 0
        assert results["pending"] == 3
        assert results["passed"] == 0

    def test_unresolved_picks_fail(self):
        """Test dry-run identifies unresolved picks."""
        # Include the unresolved pick
        picks = [MOCK_PICKS[0], MOCK_PICKS[3]]  # pick1 OK, pick4 unresolved

        failed_picks = []

        for pick in picks:
            event_ok = bool(getattr(pick, "canonical_event_id", "")) or bool(pick.matchup)
            player_ok = bool(getattr(pick, "canonical_player_id", "")) if pick.player_name else True

            if not event_ok:
                failed_picks.append({
                    "pick_id": pick.pick_id,
                    "reason": "EVENT_NOT_FOUND",
                    "player": pick.player_name
                })
            elif pick.player_name and not player_ok:
                failed_picks.append({
                    "pick_id": pick.pick_id,
                    "reason": "PLAYER_NOT_FOUND",
                    "player": pick.player_name
                })

        # pick4 should fail (no event_id, but has matchup so event_ok might be True)
        # Actually pick4 has matchup so event_ok=True, but no player_id so player fails
        assert len(failed_picks) == 1
        assert failed_picks[0]["pick_id"] == "pick4_unresolved"
        assert failed_picks[0]["reason"] == "PLAYER_NOT_FOUND"

    def test_overall_status_pass(self):
        """Test overall status is PASS when no failures and all graded."""
        results = {"failed": 0, "pending": 0, "passed": 5}

        if results["failed"] > 0:
            status = "FAIL"
        elif results["pending"] > 0:
            status = "PENDING"
        else:
            status = "PASS"

        assert status == "PASS"

    def test_overall_status_fail(self):
        """Test overall status is FAIL when failures exist."""
        results = {"failed": 2, "pending": 3, "passed": 0}

        if results["failed"] > 0:
            status = "FAIL"
        elif results["pending"] > 0:
            status = "PENDING"
        else:
            status = "PASS"

        assert status == "FAIL"

    def test_overall_status_pending(self):
        """Test overall status is PENDING when games not complete."""
        results = {"failed": 0, "pending": 3, "passed": 2}

        if results["failed"] > 0:
            status = "FAIL"
        elif results["pending"] > 0:
            status = "PENDING"
        else:
            status = "PASS"

        assert status == "PENDING"

    def test_dry_run_response_structure(self):
        """Test the structure of dry-run response."""
        picks = MOCK_PICKS[:3]  # All resolved picks

        results = {
            "date": "2026-01-26",
            "total": len(picks),
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "by_sport": {},
            "summary": {},
        }

        for pick in picks:
            sport = pick.sport.upper()
            if sport not in results["by_sport"]:
                results["by_sport"][sport] = {
                    "picks": 0,
                    "event_resolved": 0,
                    "player_resolved": 0,
                    "failed_picks": []
                }

            results["by_sport"][sport]["picks"] += 1

            if pick.canonical_event_id:
                results["by_sport"][sport]["event_resolved"] += 1
            if pick.canonical_player_id:
                results["by_sport"][sport]["player_resolved"] += 1

            results["pending"] += 1

        results["overall_status"] = "PENDING"
        results["summary"] = {
            "total": results["total"],
            "passed": results["passed"],
            "failed": results["failed"],
            "pending": results["pending"]
        }

        # Verify structure
        assert "overall_status" in results
        assert "summary" in results
        assert "by_sport" in results
        assert results["by_sport"]["NBA"]["picks"] == 2
        assert results["by_sport"]["NFL"]["picks"] == 1


class TestGradedFieldBehavior:
    """Tests for the new graded field behavior."""

    def test_graded_false_initially(self):
        """Test that graded is False for new picks."""
        pick = MockPublishedPick(
            pick_id="new_pick",
            sport="NBA",
            graded=False,
            result=None
        )

        assert pick.graded is False
        assert pick.result is None

    def test_graded_true_after_grading(self):
        """Test that graded is True after setting result."""
        pick = MockPublishedPick(
            pick_id="graded_pick",
            sport="NBA",
            graded=True,
            result="WIN"
        )

        assert pick.graded is True
        assert pick.result == "WIN"

    def test_queue_excludes_graded(self):
        """Test that queue excludes picks with graded=True."""
        picks = MOCK_PICKS.copy()

        ungraded = [p for p in picks if not p.graded and p.result is None]

        # pick5_graded should be excluded
        assert not any(p.pick_id == "pick5_graded" for p in ungraded)

    def test_queue_includes_ungraded_with_no_result(self):
        """Test that queue includes picks with graded=False and result=None."""
        picks = MOCK_PICKS.copy()

        ungraded = [p for p in picks if not p.graded and p.result is None]

        # Should include all ungraded picks
        assert any(p.pick_id == "pick1" for p in ungraded)
        assert any(p.pick_id == "pick2" for p in ungraded)
        assert any(p.pick_id == "pick3" for p in ungraded)
        assert any(p.pick_id == "pick4_unresolved" for p in ungraded)


class TestEventResolutionLogic:
    """Tests for event resolution in dry-run."""

    def test_event_resolved_with_canonical_id(self):
        """Test event is resolved when canonical_event_id exists."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            canonical_event_id="NBA:ODDS:abc123",
            matchup=""
        )

        event_ok = bool(pick.canonical_event_id) or bool(pick.matchup)
        assert event_ok is True

    def test_event_resolved_with_matchup_only(self):
        """Test event is resolved when matchup exists (fallback)."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            canonical_event_id="",
            matchup="Lakers vs Celtics"
        )

        event_ok = bool(pick.canonical_event_id) or bool(pick.matchup)
        assert event_ok is True

    def test_event_not_resolved(self):
        """Test event is not resolved when both missing."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            canonical_event_id="",
            matchup=""
        )

        event_ok = bool(pick.canonical_event_id) or bool(pick.matchup)
        assert event_ok is False


class TestPlayerResolutionLogic:
    """Tests for player resolution in dry-run."""

    def test_player_resolved_with_canonical_id(self):
        """Test player is resolved when canonical_player_id exists."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            player_name="LeBron James",
            canonical_player_id="NBA:BDL:237"
        )

        player_ok = bool(pick.canonical_player_id) if pick.player_name else True
        assert player_ok is True

    def test_player_not_resolved(self):
        """Test player is not resolved when ID missing."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            player_name="Unknown Player",
            canonical_player_id=""
        )

        # Without identity resolver, this should fail
        player_ok = bool(pick.canonical_player_id)
        assert player_ok is False

    def test_game_pick_no_player_check(self):
        """Test game picks (no player) don't require player resolution."""
        pick = MockPublishedPick(
            pick_id="test",
            sport="NBA",
            player_name="",  # Game pick, no player
            canonical_player_id=""
        )

        # Game picks don't need player resolution
        player_ok = bool(pick.canonical_player_id) if pick.player_name else True
        assert player_ok is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
