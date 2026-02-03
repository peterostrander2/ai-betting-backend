import importlib
import os


def test_live_signals_disabled_returns_unavailable(monkeypatch):
    monkeypatch.setenv("PHASE9_LIVE_SIGNALS_ENABLED", "false")
    import alt_data_sources.live_signals as live_signals
    importlib.reload(live_signals)

    result = live_signals.get_combined_live_signals(
        event_id="evt",
        home_score=10,
        away_score=5,
        period=3,
        sport="NBA",
        pick_side="Home",
        is_home_pick=True,
        current_line=-3.5,
        market_type="spread",
        db_session=None,
    )

    assert result["available"] is False
    assert result["total_boost"] == 0.0


def test_live_signals_cap(monkeypatch):
    monkeypatch.setenv("PHASE9_LIVE_SIGNALS_ENABLED", "true")
    import alt_data_sources.live_signals as live_signals
    importlib.reload(live_signals)

    def _fake_line_movement(*args, **kwargs):
        return {
            "boost": live_signals.MAX_LINE_MOVEMENT_BOOST,
            "signal": "MAJOR_STEAM",
            "reasons": ["fake"],
            "available": True,
            "movement": 3.0,
        }

    monkeypatch.setattr(live_signals, "detect_live_line_movement", _fake_line_movement)

    result = live_signals.get_combined_live_signals(
        event_id="evt",
        home_score=40,
        away_score=10,  # blowout
        period=4,
        sport="NBA",
        pick_side="Home",
        is_home_pick=True,
        current_line=-7.5,
        market_type="spread",
        db_session=None,
    )

    assert result["total_boost"] <= live_signals.MAX_COMBINED_LIVE_BOOST
