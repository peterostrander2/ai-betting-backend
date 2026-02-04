import importlib
import os
import pytest


def _build_pick(pick_id: str, score: float) -> dict:
    return {
        "pick_id": pick_id,
        "sport": "NBA",
        "event_id": pick_id,
        "market": "SPREAD",
        "side": "Home",
        "line": 1.5,
        "book_key": "test",
        "final_score": score,
        "date_et": "2026-02-03",
        "grade_status": "GRADED",
        "result": "WIN",
        "actual_value": 1.0,
        "persisted_at": "2026-02-03T00:00:00Z",
    }


def test_weights_file_under_mount_path(tmp_path, monkeypatch):
    mount = tmp_path / "mount"
    mount.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(mount))

    import data_dir
    try:
        import auto_grader
    except ModuleNotFoundError:
        pytest.skip("auto_grader requires numpy")

    importlib.reload(data_dir)
    importlib.reload(auto_grader)

    grader = auto_grader.AutoGrader()
    weights_file = os.path.join(grader.storage_path, "weights.json")

    assert str(mount) in weights_file
    assert "grader_data" in weights_file


def test_predictions_store_append_only(tmp_path, monkeypatch):
    import grader_store

    predictions_file = os.path.join(tmp_path, "predictions.jsonl")
    monkeypatch.setattr(grader_store, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(grader_store, "PREDICTIONS_FILE", predictions_file)
    monkeypatch.setattr(grader_store, "AUDIT_DIR", os.path.join(tmp_path, "audits"))

    pick1 = _build_pick("p1", 7.0)
    pick2 = _build_pick("p2", 7.2)

    assert grader_store.persist_pick(pick1, "2026-02-03") is True
    assert grader_store.persist_pick(pick2, "2026-02-03") is True

    with open(predictions_file, "r") as f:
        lines = [line for line in f.readlines() if line.strip()]

    assert len(lines) == 2


def test_training_ignores_picks_below_min_score(monkeypatch):
    try:
        import auto_grader
    except ModuleNotFoundError:
        pytest.skip("auto_grader requires numpy")

    def _load_predictions():
        return [
            _build_pick("low", 5.0),
            _build_pick("high", 7.0),
        ]

    monkeypatch.setattr(auto_grader, "grader_store_load_predictions", _load_predictions)
    monkeypatch.setattr(auto_grader, "GRADER_STORE_AVAILABLE", True)

    grader = auto_grader.AutoGrader(storage_path="./grader_data_test")
    total = sum(len(p) for p in grader.predictions.values())

    assert total == 1


def test_training_dedup_by_pick_id(monkeypatch):
    try:
        import auto_grader
    except ModuleNotFoundError:
        pytest.skip("auto_grader requires numpy")

    def _load_predictions():
        return [
            _build_pick("dup", 7.1),
            _build_pick("dup", 7.1),
        ]

    monkeypatch.setattr(auto_grader, "grader_store_load_predictions", _load_predictions)
    monkeypatch.setattr(auto_grader, "GRADER_STORE_AVAILABLE", True)

    grader = auto_grader.AutoGrader(storage_path="./grader_data_test")
    total = sum(len(p) for p in grader.predictions.values())

    assert total == 1


def test_weights_load_missing_is_safe(tmp_path):
    try:
        import auto_grader
    except ModuleNotFoundError:
        pytest.skip("auto_grader requires numpy")

    grader = auto_grader.AutoGrader(storage_path=str(tmp_path))
    weights = grader.get_all_weights()

    assert isinstance(weights, dict)
    assert "NBA" in weights


def test_predictions_roundtrip_survives_reload(tmp_path, monkeypatch):
    """Persist to grader_store then reload and ensure predictions load."""
    mount = tmp_path / "mount"
    mount.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(mount))

    import grader_store
    importlib.reload(grader_store)

    pick = _build_pick("roundtrip", 7.1)
    grader_store.ensure_storage_writable()
    assert grader_store.persist_pick(pick, "2026-02-03") is True

    loaded = grader_store.load_predictions("2026-02-03")
    assert any(p.get("pick_id") == pick["pick_id"] for p in loaded)


def test_auto_grader_uses_et_aware_comparisons():
    """Auto-grader should normalize timestamps to ET before comparisons."""
    with open("auto_grader.py", "r") as f:
        text = f.read()

    assert "now_et()" in text, "auto_grader must use now_et() for ET-aware comparisons"
    assert "fromisoformat" in text and "tzinfo is None" in text, "auto_grader must normalize naive timestamps"


def test_scoring_path_does_not_adjust_weights():
    with open("live_data_router.py", "r") as f:
        text = f.read()

    start = text.find("async def get_best_bets")
    assert start != -1
    remainder = text[start:]
    end = remainder.find("\nasync def ")
    block = remainder if end == -1 else remainder[:end]

    assert "adjust_weights" not in block
    assert "apply_updates" not in block
    assert "_save_state" not in block
