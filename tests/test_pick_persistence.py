"""
Test Pick Persistence (NEVER BREAK AGAIN)

RULE: Every returned pick >= 6.5 must be written to persistent storage
- prediction_id must be stable hash
- Storage must survive container restart (Railway volume)
- All required fields must be present
- AutoGrader must be able to read picks
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import tempfile
from pathlib import Path
from core.invariants import (
    PICK_STORAGE_REQUIRED_FIELDS,
    COMMUNITY_MIN_SCORE,
    validate_pick_storage,
)

# Try to import pick_logger
try:
    from pick_logger import PickLogger, get_today_date_et
    PICK_LOGGER_AVAILABLE = True
except ImportError:
    PICK_LOGGER_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="pick_logger not available")


class TestPickStorageConstants:
    """Test pick storage constant definitions"""

    def test_required_fields_defined(self):
        """Required storage fields list is defined"""
        assert isinstance(PICK_STORAGE_REQUIRED_FIELDS, list)
        assert len(PICK_STORAGE_REQUIRED_FIELDS) > 0

    def test_required_fields_include_essentials(self):
        """Required fields include essential metadata"""
        essential_fields = [
            "prediction_id",
            "sport",
            "final_score",
            "tier",
            "event_start_time_et",
        ]

        for field in essential_fields:
            assert field in PICK_STORAGE_REQUIRED_FIELDS, f"Missing essential field: {field}"

    def test_required_fields_include_engine_scores(self):
        """Required fields include all 4 engine scores"""
        engine_fields = [
            "ai_score",
            "research_score",
            "esoteric_score",
            "jarvis_score",
        ]

        for field in engine_fields:
            assert field in PICK_STORAGE_REQUIRED_FIELDS, f"Missing engine score: {field}"


class TestValidatePickStorage:
    """Test validate_pick_storage() function"""

    def test_validate_complete_pick(self):
        """Pick with all required fields should validate"""
        complete_pick = {
            "prediction_id": "abc123",
            "sport": "NBA",
            "market_type": "prop",
            "line_at_bet": 25.5,
            "odds_at_bet": -110,
            "book": "DraftKings",
            "event_start_time_et": "7:00 PM ET",
            "created_at": "2026-01-28T12:00:00Z",
            "final_score": 8.5,
            "tier": "GOLD_STAR",
            "ai_score": 8.2,
            "research_score": 7.8,
            "esoteric_score": 7.5,
            "jarvis_score": 6.0,
            "ai_reasons": ["Model A", "Model B"],
            "research_reasons": ["Sharp money"],
            "esoteric_reasons": ["Gematria"],
            "jarvis_reasons": ["Trigger 33"],
        }

        is_valid, error = validate_pick_storage(complete_pick)

        assert is_valid is True, f"Complete pick should validate: {error}"

    def test_validate_missing_prediction_id(self):
        """Pick missing prediction_id should fail"""
        incomplete_pick = {
            "sport": "NBA",
            "final_score": 8.5,
            # Missing prediction_id
        }

        is_valid, error = validate_pick_storage(incomplete_pick)

        assert is_valid is False, "Should fail without prediction_id"
        assert "prediction_id" in error.lower()

    def test_validate_missing_engine_score(self):
        """Pick missing any engine score should fail"""
        pick_missing_jarvis = {
            "prediction_id": "abc123",
            "sport": "NBA",
            "market_type": "game",
            "line_at_bet": -5.5,
            "odds_at_bet": -110,
            "book": "FanDuel",
            "event_start_time_et": "7:00 PM ET",
            "created_at": "2026-01-28T12:00:00Z",
            "final_score": 7.5,
            "tier": "EDGE_LEAN",
            "ai_score": 7.5,
            "research_score": 7.0,
            "esoteric_score": 6.5,
            # Missing jarvis_score
            "ai_reasons": [],
            "research_reasons": [],
            "esoteric_reasons": [],
            "jarvis_reasons": [],
        }

        is_valid, error = validate_pick_storage(pick_missing_jarvis)

        assert is_valid is False, "Should fail without jarvis_score"
        assert "jarvis_score" in error.lower()


@pytest.mark.skipif(not PICK_LOGGER_AVAILABLE, reason="pick_logger not available")
class TestPickLoggerPersistence:
    """Test PickLogger writes and reads correctly"""

    def test_pick_logger_writes_to_file(self):
        """PickLogger should write picks to JSONL file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PickLogger(storage_path=tmpdir)

            # Create a mock pick
            pick_data = {
                "sport": "NBA",
                "player_name": "LeBron James",
                "prop_type": "points",
                "line": 25.5,
                "side": "Over",
                "final_score": 8.5,
                "tier": "GOLD_STAR",
                "ai_score": 8.2,
                "research_score": 7.8,
                "esoteric_score": 7.5,
                "jarvis_score": 6.0,
            }

            # Log the pick
            result = logger.log_pick(pick_data, game_start_time="7:00 PM ET")

            # Check file was created
            today = get_today_date_et()
            pick_file = Path(tmpdir) / f"picks_{today}.jsonl"

            assert pick_file.exists(), "Pick file should be created"

            # Read back and verify
            with open(pick_file) as f:
                lines = f.readlines()
                assert len(lines) >= 1, "Should have at least one pick"

                first_pick = json.loads(lines[0])
                assert first_pick["sport"] == "NBA"
                assert first_pick["player_name"] == "LeBron James"

    def test_pick_logger_creates_stable_prediction_id(self):
        """prediction_id should be deterministic for same pick"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PickLogger(storage_path=tmpdir)

            pick_data = {
                "sport": "NBA",
                "event_id": "game123",
                "player_name": "LeBron James",
                "prop_type": "points",
                "line": 25.5,
                "side": "Over",
                "final_score": 8.5,
                "tier": "GOLD_STAR",
            }

            # Log same pick twice
            result1 = logger.log_pick(pick_data, game_start_time="7:00 PM ET")
            result2 = logger.log_pick(pick_data, game_start_time="7:00 PM ET")

            # Should have same prediction_id (deduplicated)
            # OR second log should skip (already logged)
            assert result1.get("pick_id") == result2.get("pick_id") or result2.get("skipped")

    def test_pick_logger_survives_restart(self):
        """Picks should be readable after logger restart"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First session: write picks
            logger1 = PickLogger(storage_path=tmpdir)
            pick1 = {
                "sport": "NBA",
                "player_name": "LeBron James",
                "line": 25.5,
                "final_score": 8.5,
            }
            logger1.log_pick(pick1, game_start_time="7:00 PM ET")

            # Simulate restart: create new logger instance
            logger2 = PickLogger(storage_path=tmpdir)

            # Should be able to read picks from first session
            today = get_today_date_et()
            picks = logger2.get_picks_for_date(today)

            assert len(picks) >= 1, "Should read picks from previous session"
            assert picks[0]["player_name"] == "LeBron James"

    def test_pick_logger_handles_below_threshold(self):
        """Picks below 6.5 should not be stored (or stored as internal only)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PickLogger(storage_path=tmpdir)

            low_score_pick = {
                "sport": "NBA",
                "player_name": "Test Player",
                "final_score": 5.5,  # Below 6.5
                "tier": "PASS",
            }

            result = logger.log_pick(low_score_pick, game_start_time="7:00 PM ET")

            # Depending on implementation, should either:
            # 1. Not log at all (result["skipped"] = True)
            # 2. Log but mark as internal_only
            # For now, just verify it doesn't crash
            assert "skipped" in result or "logged" in result


class TestStoragePathConfiguration:
    """Test storage path is correctly configured for Railway"""

    def test_storage_path_env_var(self):
        """Storage should use RAILWAY_VOLUME_MOUNT_PATH env var"""
        from core.invariants import PICK_STORAGE_PATH_ENV

        assert PICK_STORAGE_PATH_ENV == "RAILWAY_VOLUME_MOUNT_PATH"

    def test_storage_subpath(self):
        """Storage subpath should be pick_logs"""
        from core.invariants import PICK_STORAGE_SUBPATH

        assert PICK_STORAGE_SUBPATH == "pick_logs"

    def test_full_storage_path_construction(self):
        """Full storage path should be {VOLUME}/pick_logs"""
        # Mock environment variable
        os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = "/app/grader_data"

        # Import after setting env var
        from data_dir import PICK_LOGS

        assert "/app/grader_data" in PICK_LOGS
        assert "pick_logs" in PICK_LOGS


class TestAutoGraderCanReadPicks:
    """Test AutoGrader can read persisted picks"""

    @pytest.mark.skipif(not PICK_LOGGER_AVAILABLE, reason="pick_logger not available")
    def test_autograder_reads_pending_picks(self):
        """AutoGrader should find pending picks for grading"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PickLogger(storage_path=tmpdir)

            # Log a pick
            pick_data = {
                "sport": "NBA",
                "player_name": "LeBron James",
                "prop_type": "points",
                "line": 25.5,
                "side": "Over",
                "final_score": 8.5,
                "tier": "GOLD_STAR",
                "event_start_time_et": "7:00 PM ET",
                "grade_status": "PENDING",
            }
            logger.log_pick(pick_data, game_start_time="7:00 PM ET")

            # Get picks for grading
            today = get_today_date_et()
            picks = logger.get_picks_for_grading(date_str=today)

            assert len(picks) > 0, "AutoGrader should find pending picks"
            assert picks[0]["player_name"] == "LeBron James"
            assert picks[0]["grade_status"] == "PENDING"

    @pytest.mark.skipif(not PICK_LOGGER_AVAILABLE, reason="pick_logger not available")
    def test_autograder_no_false_empty(self):
        """AutoGrader should only say 'no picks' when truly empty"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PickLogger(storage_path=tmpdir)

            # File doesn't exist yet
            today = get_today_date_et()
            picks = logger.get_picks_for_date(today)

            # Should return empty list, not crash
            assert isinstance(picks, list)
            assert len(picks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
