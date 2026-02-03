from core.scoring_contract import GOLD_STAR_GATES


def test_gold_star_gates_exclude_context():
    assert "context_score" not in GOLD_STAR_GATES
    assert set(GOLD_STAR_GATES.keys()) == {"ai_score", "research_score", "jarvis_score", "esoteric_score"}
