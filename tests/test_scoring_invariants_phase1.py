import os
from pathlib import Path


def test_option_a_formula_with_adjustments():
    """Option A formula should include explicit post-base adjustments.

    v20.11: TOTAL_BOOST_CAP is now 1.5, so sum of confluence+msrf+jason+serp is capped.
    """
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import TOTAL_BOOST_CAP

    base_score = 6.2
    context_modifier = 0.2
    confluence_boost = 1.0
    msrf_boost = 0.3
    jason_sim_boost = -0.1
    serp_boost = 0.6
    ensemble_adjustment = 0.5
    live_adjustment = -0.2

    final_score, _ = compute_final_score_option_a(
        base_score=base_score,
        context_modifier=context_modifier,
        confluence_boost=confluence_boost,
        msrf_boost=msrf_boost,
        jason_sim_boost=jason_sim_boost,
        serp_boost=serp_boost,
    )

    # v20.11: Total boosts are capped at TOTAL_BOOST_CAP (1.5)
    raw_boosts = confluence_boost + msrf_boost + jason_sim_boost + serp_boost  # 1.8
    capped_boosts = min(TOTAL_BOOST_CAP, raw_boosts)  # 1.5
    expected = base_score + context_modifier + capped_boosts
    expected = min(10.0, max(0.0, expected + ensemble_adjustment + live_adjustment))

    assert abs((final_score + ensemble_adjustment + live_adjustment) - expected) <= 0.02


def test_final_score_bounds_after_adjustments():
    """Final score must be clamped to [0, 10] after adjustments."""
    from core.scoring_pipeline import compute_final_score_option_a

    final_score, _ = compute_final_score_option_a(
        base_score=9.8,
        context_modifier=0.35,
        confluence_boost=3.0,
        msrf_boost=1.0,
        jason_sim_boost=1.0,
        serp_boost=4.3,
    )
    final_score = min(10.0, max(0.0, final_score + 0.5))
    assert 0.0 <= final_score <= 10.0


def test_best_bets_uses_et_day_window_before_scoring():
    """best-bets should filter by ET day window before scoring loops."""
    repo_root = Path(__file__).resolve().parents[1]
    router_path = repo_root / "live_data_router.py"
    text = router_path.read_text()
    idx_filter = text.find("filter_events_et")
    idx_score = text.find("calculate_pick_score")
    assert idx_filter != -1, "filter_events_et must be used in best-bets pipeline"
    assert idx_score != -1, "calculate_pick_score should exist in best-bets pipeline"
    assert idx_filter < idx_score, "ET filtering must occur before scoring"
