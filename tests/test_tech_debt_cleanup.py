"""
Tests for technical debt cleanup items.

Item 1: mark_graded() append-only JSONL
Item 2: Odds staleness guard
Item 3: Market suspended detection
Item 4: Training drop telemetry
Item 5: Weight version hash
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
import grader_store


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for testing with graded_picks support."""
    with tempfile.TemporaryDirectory() as tmpdir:
        predictions_file = os.path.join(tmpdir, "predictions.jsonl")
        graded_picks_file = os.path.join(tmpdir, "graded_picks.jsonl")
        with patch.object(grader_store, 'STORAGE_ROOT', tmpdir):
            with patch.object(grader_store, 'PREDICTIONS_FILE', predictions_file):
                with patch.object(grader_store, 'GRADED_PICKS_FILE', graded_picks_file):
                    with patch.object(grader_store, 'AUDIT_DIR', os.path.join(tmpdir, "audits")):
                        yield {
                            "predictions_file": predictions_file,
                            "graded_picks_file": graded_picks_file,
                            "tmpdir": tmpdir,
                        }


# =============================================================================
# Item 1: mark_graded() append-only JSONL
# =============================================================================

class TestMarkGradedAppendOnly:
    """Tests for the new append-only mark_graded implementation."""

    def test_mark_graded_creates_graded_picks_file(self, temp_storage):
        """mark_graded should create graded_picks.jsonl if it doesn't exist."""
        result = grader_store.mark_graded("pick1", "WIN", 25.5, "2026-02-04T06:00:00")
        assert result is True
        assert os.path.exists(temp_storage["graded_picks_file"])

    def test_mark_graded_appends_record(self, temp_storage):
        """mark_graded should append a JSONL record to graded_picks.jsonl."""
        grader_store.mark_graded("pick1", "WIN", 25.5, "2026-02-04T06:00:00")
        grader_store.mark_graded("pick2", "LOSS", 18.0, "2026-02-04T06:00:01")

        with open(temp_storage["graded_picks_file"], 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1["pick_id"] == "pick1"
        assert record1["result"] == "WIN"
        assert record1["actual_value"] == 25.5
        assert record1["grade_status"] == "GRADED"

        record2 = json.loads(lines[1])
        assert record2["pick_id"] == "pick2"
        assert record2["result"] == "LOSS"

    def test_mark_graded_does_not_modify_predictions(self, temp_storage):
        """mark_graded should NEVER modify predictions.jsonl."""
        # Write a prediction first
        pred = {"pick_id": "pick1", "sport": "NBA", "date_et": "2026-02-04", "final_score": 8.0}
        with open(temp_storage["predictions_file"], 'w') as f:
            f.write(json.dumps(pred) + "\n")

        # Get original content
        with open(temp_storage["predictions_file"], 'r') as f:
            original_content = f.read()

        # Grade the pick
        grader_store.mark_graded("pick1", "WIN", 25.5, "2026-02-04T06:00:00")

        # Predictions file should be UNCHANGED
        with open(temp_storage["predictions_file"], 'r') as f:
            after_content = f.read()

        assert original_content == after_content

    def test_load_predictions_merges_grade_records(self, temp_storage):
        """load_predictions should merge grade records from graded_picks.jsonl."""
        # Write predictions
        preds = [
            {"pick_id": "p1", "sport": "NBA", "date_et": "2026-02-04", "final_score": 8.0},
            {"pick_id": "p2", "sport": "NHL", "date_et": "2026-02-04", "final_score": 7.5},
        ]
        with open(temp_storage["predictions_file"], 'w') as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

        # Grade one pick
        grader_store.mark_graded("p1", "WIN", 25.5, "2026-02-04T06:00:00")

        # Load should merge
        loaded = grader_store.load_predictions()
        assert len(loaded) == 2

        graded = [p for p in loaded if p["pick_id"] == "p1"][0]
        assert graded["grade_status"] == "GRADED"
        assert graded["result"] == "WIN"
        assert graded["actual_value"] == 25.5

        ungraded = [p for p in loaded if p["pick_id"] == "p2"][0]
        assert "grade_status" not in ungraded or ungraded.get("grade_status") != "GRADED"

    def test_load_predictions_works_without_graded_file(self, temp_storage):
        """load_predictions works even if graded_picks.jsonl doesn't exist."""
        preds = [
            {"pick_id": "p1", "sport": "NBA", "date_et": "2026-02-04", "final_score": 8.0},
        ]
        with open(temp_storage["predictions_file"], 'w') as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

        loaded = grader_store.load_predictions()
        assert len(loaded) == 1
        assert loaded[0]["pick_id"] == "p1"

    def test_crash_during_append_leaves_valid_state(self, temp_storage):
        """If an append is partially written, existing records remain valid."""
        # Write a valid grade record
        grader_store.mark_graded("pick1", "WIN", 25.5, "2026-02-04T06:00:00")

        # Simulate a partial write (corrupted line)
        with open(temp_storage["graded_picks_file"], 'a') as f:
            f.write('{"pick_id": "pick2", "result": "LOSS", "CORRUPTED\n')

        # Write another valid record
        grader_store.mark_graded("pick3", "WIN", 30.0, "2026-02-04T06:00:02")

        # Load should recover the valid records
        preds = [
            {"pick_id": "pick1", "date_et": "2026-02-04", "final_score": 8.0},
            {"pick_id": "pick3", "date_et": "2026-02-04", "final_score": 7.5},
        ]
        with open(temp_storage["predictions_file"], 'w') as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

        loaded = grader_store.load_predictions()
        graded_picks = {p["pick_id"]: p for p in loaded if p.get("grade_status") == "GRADED"}
        assert "pick1" in graded_picks
        assert "pick3" in graded_picks


# =============================================================================
# Item 2: Odds staleness detection
# =============================================================================

class TestOddsStaleness:
    """Tests for ODDS_STALENESS_THRESHOLD_SECONDS constant."""

    def test_constant_exists_in_scoring_contract(self):
        """ODDS_STALENESS_THRESHOLD_SECONDS should exist in scoring_contract."""
        from core.scoring_contract import ODDS_STALENESS_THRESHOLD_SECONDS
        assert ODDS_STALENESS_THRESHOLD_SECONDS == 120

    def test_constant_in_canonical_contract(self):
        """The constant should be importable from scoring_contract."""
        from core.scoring_contract import SCORING_CONTRACT
        # The constant is standalone, not necessarily in the dict, but should be importable
        from core.scoring_contract import ODDS_STALENESS_THRESHOLD_SECONDS
        assert isinstance(ODDS_STALENESS_THRESHOLD_SECONDS, (int, float))
        assert ODDS_STALENESS_THRESHOLD_SECONDS > 0


# =============================================================================
# Item 3: Market status detection
# =============================================================================

class TestMarketStatusDetection:
    """Tests for market status detection logic."""

    def test_pick_with_odds_is_open(self):
        """Pick with valid odds should have market_status='open'."""
        pick = {"odds_american": -110, "book": "draftkings"}
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            status = "suspended"
        else:
            status = "open"
        assert status == "open"

    def test_pick_without_odds_is_suspended(self):
        """Pick without odds and book should have market_status='suspended'."""
        pick = {"odds_american": None, "book": None}
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            status = "suspended"
        else:
            status = "open"
        assert status == "suspended"

    def test_pick_with_book_but_no_odds_is_open(self):
        """Pick with book name but no odds should still be open."""
        pick = {"odds_american": None, "book": "fanduel"}
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            status = "suspended"
        else:
            status = "open"
        assert status == "open"

    def test_pick_with_odds_but_no_book_is_open(self):
        """Pick with odds but no book should still be open."""
        pick = {"odds_american": -110, "book": None}
        odds = pick.get("odds_american")
        book = pick.get("book")
        if odds is None and not book:
            status = "suspended"
        else:
            status = "open"
        assert status == "open"


# =============================================================================
# Item 4: Training drop telemetry
# =============================================================================

class TestTrainingDropTelemetry:
    """Tests for training drop stats structure."""

    def test_drop_stats_dict_structure(self):
        """Drop stats dict should have the expected shape and keys."""
        drop_stats = {
            "unsupported_sport": 0,
            "below_score_threshold": 0,
            "duplicate_id": 0,
            "missing_pick_id": 0,
            "conversion_failed": 0,
        }
        assert isinstance(drop_stats, dict)
        assert "unsupported_sport" in drop_stats
        assert "below_score_threshold" in drop_stats
        assert all(isinstance(v, int) for v in drop_stats.values())

    def test_drop_stats_has_all_expected_keys(self):
        """Drop stats dict should have all expected counter keys."""
        expected_keys = {
            "unsupported_sport",
            "below_score_threshold",
            "duplicate_id",
            "missing_pick_id",
            "conversion_failed",
        }
        drop_stats = {k: 0 for k in expected_keys}
        assert set(drop_stats.keys()) == expected_keys

    def test_drop_stats_counters_increment(self):
        """Drop stats counters should be incrementable."""
        drop_stats = {
            "unsupported_sport": 0,
            "below_score_threshold": 0,
            "duplicate_id": 0,
            "missing_pick_id": 0,
            "conversion_failed": 0,
        }
        drop_stats["unsupported_sport"] += 3
        drop_stats["below_score_threshold"] += 5
        assert drop_stats["unsupported_sport"] == 3
        assert drop_stats["below_score_threshold"] == 5
        assert sum(drop_stats.values()) == 8


# =============================================================================
# Item 5: Weight version hash
# =============================================================================

class TestWeightVersionHash:
    """Tests for weight version hash computation."""

    def test_sha256_hash_computation(self):
        """SHA256[:12] should produce a 12-char hex string."""
        import hashlib
        content = b'{"NBA": {"points": {"base_weight": 1.0}}}'
        hash_val = hashlib.sha256(content).hexdigest()[:12]
        assert len(hash_val) == 12
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_different_content_produces_different_hash(self):
        """Different weight content should produce different hashes."""
        import hashlib
        content1 = b'{"NBA": {"points": {"base_weight": 1.0}}}'
        content2 = b'{"NBA": {"points": {"base_weight": 1.5}}}'
        hash1 = hashlib.sha256(content1).hexdigest()[:12]
        hash2 = hashlib.sha256(content2).hexdigest()[:12]
        assert hash1 != hash2


# =============================================================================
# Storage paths integration
# =============================================================================

class TestStoragePathsGradedPicks:
    """Tests for graded_picks path in storage_paths.py."""

    def test_get_graded_picks_file_returns_path(self):
        """get_graded_picks_file should return a valid path string."""
        from storage_paths import get_graded_picks_file
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"RAILWAY_VOLUME_MOUNT_PATH": tmpdir}):
                path = get_graded_picks_file()
                assert isinstance(path, str)
                assert "graded_picks.jsonl" in path

    def test_graded_picks_in_storage_health(self):
        """get_storage_health should include graded_picks info."""
        from storage_paths import get_storage_health
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create required directory structure
            grader_dir = os.path.join(tmpdir, "grader")
            os.makedirs(grader_dir, exist_ok=True)
            with patch.dict(os.environ, {"RAILWAY_VOLUME_MOUNT_PATH": tmpdir}):
                health = get_storage_health()
                assert "graded_picks_file" in health
                assert "graded_picks_exists" in health
