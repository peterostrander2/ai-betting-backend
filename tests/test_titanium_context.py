from core.titanium import evaluate_titanium


def test_titanium_ignores_context():
    """
    Titanium is STRICT 3-of-4 engines >= 8.0.
    Context is a modifier and must not influence Titanium.
    """
    triggered, reason, engines = evaluate_titanium(
        ai_score=8.2,
        research_score=8.1,
        esoteric_score=7.9,
        jarvis_score=7.8,
        final_score=9.0,
        threshold=8.0,
    )
    assert triggered is False
    assert "need 3" in reason or "Only" in reason
    assert engines == ["ai", "research"]
