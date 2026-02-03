from utils.ensemble_adjustment import apply_ensemble_adjustment


def test_ensemble_adjustment_boost():
    final, reasons = apply_ensemble_adjustment(7.0, 0.61)
    assert final == 7.5
    assert reasons


def test_ensemble_adjustment_penalty():
    final, reasons = apply_ensemble_adjustment(7.0, 0.39)
    assert final == 6.5
    assert reasons


def test_ensemble_adjustment_neutral():
    final, reasons = apply_ensemble_adjustment(7.0, 0.50)
    assert final == 7.0
    assert reasons == []
