from datetime import date

from jarvis_savant_engine import JarvisSavantEngine
from jason_sim_confluence import JasonSimConfluence
import signals.msrf_resonance as msrf


def test_confluence_levels_strong_and_moderate():
    jarvis = JarvisSavantEngine()

    # STRONG: alignment >= 80 and at least one active signal, but not both_high
    strong = jarvis.calculate_confluence(
        research_score=7.0,
        esoteric_score=7.0,
        jarvis_active=True,
        research_sharp_present=False,
        jason_sim_boost=0.0,
    )
    assert strong["level"] == "STRONG"
    assert strong["boost"] == 3

    # MODERATE: alignment >= 70 but no active signals
    moderate = jarvis.calculate_confluence(
        research_score=7.0,
        esoteric_score=7.0,
        jarvis_active=False,
        research_sharp_present=False,
        jason_sim_boost=0.0,
    )
    assert moderate["level"] == "MODERATE"
    assert moderate["boost"] == 1


def test_jason_sim_positive_and_negative_paths():
    jason = JasonSimConfluence()

    sim_results = {
        "home_win_pct": 65.0,
        "away_win_pct": 35.0,
        "home_cover_pct": 60.0,
        "away_cover_pct": 40.0,
        "projected_total": 220.0,
        "projected_pace": "NEUTRAL",
        "variance_flag": "MED",
        "total_std": 15.0,
        "num_sims": 1000,
    }
    boost = jason.evaluate_spread_ml(
        base_score=7.5,
        pick_side="Home",
        home_team="Home",
        away_team="Away",
        sim_results=sim_results,
    )
    assert boost["boost"] > 0

    sim_results_low = sim_results | {"home_win_pct": 50.0, "away_win_pct": 50.0}
    downgrade = jason.evaluate_spread_ml(
        base_score=7.5,
        pick_side="Home",
        home_team="Home",
        away_team="Away",
        sim_results=sim_results_low,
    )
    assert downgrade["boost"] < 0 or downgrade["boost"] == 0.0


def test_msrf_positive_boost_fixture():
    # Deterministic MSRF positive path: patch operations to force multiple hits
    original_ops = msrf.OPERATIONS
    original_enabled = msrf.MSRF_ENABLED
    try:
        msrf.MSRF_ENABLED = True
        msrf.OPERATIONS = [
            ("T1", lambda y: y, "X3", 0),
            ("T2", lambda y: y, "X3", 0),
            ("T3", lambda y: y, "X3", 0),
        ]
        # Significant dates with 12-day interval, target_date = X3 + 12
        sig_dates = [date(2024, 1, 1), date(2024, 1, 13), date(2024, 1, 25)]
        target = date(2024, 2, 6)
        result = msrf.calculate_msrf_resonance(sig_dates, target)
        assert result["boost"] >= 0.25
        assert result["triggered"] is True
    finally:
        msrf.OPERATIONS = original_ops
        msrf.MSRF_ENABLED = original_enabled
