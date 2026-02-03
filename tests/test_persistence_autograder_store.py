"""
Test: Persistence to autograder store.

REQUIREMENT: Picks must persist to grader_store so autograder can load and grade them.
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch
import grader_store


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        predictions_file = os.path.join(tmpdir, "predictions.jsonl")
        with patch.object(grader_store, 'STORAGE_ROOT', tmpdir):
            with patch.object(grader_store, 'PREDICTIONS_FILE', predictions_file):
                with patch.object(grader_store, 'AUDIT_DIR', os.path.join(tmpdir, "audits")):
                    yield predictions_file


def test_persist_pick_creates_file(temp_storage):
    """Persisting a pick creates the predictions file."""
    pick = {
        "sport": "NBA",
        "event_id": "game123",
        "market": "SPREAD",
        "side": "Lakers",
        "line": -3.5,
        "book_key": "fanduel",
        "final_score": 8.2
    }

    result = grader_store.persist_pick(pick, "2026-01-28")

    assert result is True
    assert os.path.exists(temp_storage)


def test_persist_pick_idempotent(temp_storage):
    """Persisting same pick twice returns False (duplicate)."""
    pick = {
        "sport": "NBA",
        "event_id": "game123",
        "market": "SPREAD",
        "side": "Lakers",
        "line": -3.5,
        "book_key": "fanduel",
        "final_score": 8.2
    }

    result1 = grader_store.persist_pick(pick, "2026-01-28")
    result2 = grader_store.persist_pick(pick, "2026-01-28")

    assert result1 is True
    assert result2 is False  # Duplicate


def test_load_predictions_returns_persisted_picks(temp_storage):
    """Loading predictions returns all persisted picks."""
    picks = [
        {
            "sport": "NBA",
            "event_id": "game1",
            "market": "SPREAD",
            "side": "Lakers",
            "line": -3.5,
            "book_key": "fanduel",
            "final_score": 8.2
        },
        {
            "sport": "NHL",
            "event_id": "game2",
            "market": "TOTAL",
            "side": "Over",
            "line": 6.5,
            "book_key": "draftkings",
            "final_score": 7.8
        }
    ]

    for pick in picks:
        grader_store.persist_pick(pick, "2026-01-28")

    loaded = grader_store.load_predictions("2026-01-28")

    assert len(loaded) == 2
    assert all("pick_id" in p for p in loaded)
    assert all(p["date_et"] == "2026-01-28" for p in loaded)


def test_load_predictions_filters_by_date(temp_storage):
    """Loading predictions can filter by date_et."""
    grader_store.persist_pick({"sport": "NBA", "event_id": "1", "market": "SPREAD", "side": "A", "line": 0, "book_key": "b", "final_score": 7}, "2026-01-27")
    grader_store.persist_pick({"sport": "NBA", "event_id": "2", "market": "SPREAD", "side": "B", "line": 0, "book_key": "b", "final_score": 7}, "2026-01-28")

    loaded = grader_store.load_predictions("2026-01-28")

    assert len(loaded) == 1
    assert loaded[0]["event_id"] == "2"


def test_get_storage_stats_returns_count(temp_storage):
    """Storage stats returns correct prediction count."""
    grader_store.persist_pick({"sport": "NBA", "event_id": "1", "market": "SPREAD", "side": "A", "line": 0, "book_key": "b", "final_score": 7}, "2026-01-28")
    grader_store.persist_pick({"sport": "NBA", "event_id": "2", "market": "SPREAD", "side": "B", "line": 0, "book_key": "b", "final_score": 7}, "2026-01-28")

    stats = grader_store.get_storage_stats()

    assert stats["predictions_file_exists"] is True
    assert stats["storage_root_writable"] is True
    assert stats["predictions_loaded_count"] == 2


def test_load_predictions_parses_jsonl_format(temp_storage):
    """Loading predictions correctly parses JSONL format (one JSON per line)."""
    # Write 2 JSONL lines directly to file
    jsonl_content = (
        '{"pick_id": "abc123", "sport": "NBA", "event_id": "game1", "date_et": "2026-01-28", "final_score": 8.0}\n'
        '{"pick_id": "def456", "sport": "NHL", "event_id": "game2", "date_et": "2026-01-28", "final_score": 7.5}\n'
    )

    with open(temp_storage, 'w') as f:
        f.write(jsonl_content)

    # Load predictions
    loaded = grader_store.load_predictions()

    assert len(loaded) == 2
    assert loaded[0]["pick_id"] == "abc123"
    assert loaded[1]["pick_id"] == "def456"
    assert all(p["date_et"] == "2026-01-28" for p in loaded)


def test_load_predictions_skips_corrupted_lines(temp_storage):
    """Loading predictions skips corrupted lines and logs errors without crashing."""
    # Write JSONL with one corrupted line
    jsonl_content = (
        '{"pick_id": "abc123", "sport": "NBA", "event_id": "game1", "date_et": "2026-01-28", "final_score": 8.0}\n'
        '{"pick_id": "CORRUPTED_LINE", invalid json here\n'  # Corrupted
        '{"pick_id": "def456", "sport": "NHL", "event_id": "game2", "date_et": "2026-01-28", "final_score": 7.5}\n'
    )

    with open(temp_storage, 'w') as f:
        f.write(jsonl_content)

    # Load predictions - should skip corrupted line
    loaded = grader_store.load_predictions()

    # Should load 2 valid lines, skip 1 corrupted
    assert len(loaded) == 2
    assert loaded[0]["pick_id"] == "abc123"
    assert loaded[1]["pick_id"] == "def456"
