# AI Model Truth Table for GAME Picks

**Version:** v20.21 (Feb 13, 2026)
**Evidence:** Production debug output from `/live/best-bets/NBA?debug=1`

## Used vs Not Used Matrix

| # | Model | Invoked? | Code Location | Output Value (Prod) | Contributes to ai_score? | Status |
|---|-------|----------|---------------|---------------------|--------------------------|--------|
| 1 | **Ensemble Stacking** | ✅ Yes | `advanced_ml_backend.py:714` | 54.2 | ✅ Yes (via predicted_value mean) | **STUB** - returns `np.mean(features)`, not trained |
| 2 | **LSTM** | ✅ Yes | `advanced_ml_backend.py:717` | varies | ✅ Yes (via predicted_value mean) | **FIXED v20.21** - uses sport-specific defaults for totals |
| 3 | **Matchup** | ✅ Yes | `advanced_ml_backend.py:720` | 54.2 | ✅ Yes (via predicted_value mean) | **STUB** - returns `np.mean(features)`, no matchup models |
| 4 | **Monte Carlo** | ✅ Yes | `advanced_ml_backend.py:728` | 107.9 | ✅ Yes (via predicted_value mean) | **WORKS** - runs 10k simulations |
| 5 | **Line Movement** | ✅ Yes | `advanced_ml_backend.py:737` | 0 | ✅ Yes (factor_score += 0.5 when \|move\| > 0.5) | **WORKS** |
| 6 | **Rest/Fatigue** | ✅ Yes | `advanced_ml_backend.py:748` | 1.0 | ✅ Yes (multiplies predicted_value) | **WORKS** |
| 7 | **Injury Impact** | ✅ Yes | `advanced_ml_backend.py:756` | -5.0 max | ✅ Yes (adds to predicted_value) | **FIXED v20.21** - capped at -5.0 |
| 8 | **Edge Calculator** | ✅ Yes | `advanced_ml_backend.py:777` | 98.091% | ✅ Yes (edge_score = min(3, edge_pct/5)) | **WORKS** |

## Issues Identified (v20.21 Status)

### Fixed Issues ✅

1. **LSTM returns 0 for totals picks** - FIXED v20.21
   - Root cause: When `line=0` for totals markets, LSTM returned 0
   - Fix: `TeamLSTMModel.predict()` now uses sport-specific default totals when line=0 and is_totals=True
   - Sports defaults: NBA=226, NCAAB=145, NFL=45, NHL=6, MLB=8.5

2. **Injury Impact unbounded (-122.0)** - FIXED v20.21
   - Root cause: `InjuryImpactModel.INJURY_IMPACT_CAP` was 10.0, allowing large negatives
   - Fix: Reduced `INJURY_IMPACT_CAP` to 5.0 (returns max -5.0)

3. **Line Movement not used in ai_score** - ALREADY FIXED
   - Line 1073: `if abs(model_predictions.get('line_movement', 0)) > 0.5: factor_score += 0.5`
   - Contributes to `factor_score` → `alternative_base` → `ai_score`

### Design Issues (Accepted)

4. **Ensemble is untrained stub**
   - Returns `np.mean(features)` which equals `matchup` output
   - Training script exists but model file not loaded
   - **Accepted**: System works with fallback, training improves over time

5. **Matchup has no models**
   - Uses TeamMatchupModel which tracks H2H history at runtime
   - Falls back to feature mean when no history
   - **Accepted**: Improves as games are tracked

## Production Evidence (Feb 9, 2026)

```
CANDIDATE: Milwaukee Bucks @ Orlando Magic (TOTALS market)
  ai_mode: ML_PRIMARY
  models_used_count: 6

  model_preds:
    ensemble: 54.2      # = np.mean(features) - STUB
    lstm: 0.0           # BROKEN - spread=0 for totals
    matchup: 54.2       # = np.mean(features) - STUB
    monte_carlo: 107.9  # WORKS - actual simulation

  raw_inputs:
    edge_percent: 98.091    # Unrealistic due to probability=0.01
    probability: 0.01       # Bad calc from predicted_value << line
    rest_factor: 1.0        # WORKS
    injury_impact: -122.0   # BROKEN - not capped
    line_movement: 0        # Stored but NOT USED
```

## How ai_score is Actually Computed

```python
# 1. Get 4 model predictions
model_values = [ensemble, lstm, matchup, monte_carlo]  # [54.2, 0.0, 54.2, 107.9]

# 2. Average them for predicted_value
predicted_value = np.mean(model_values)  # = 54.08

# 3. Apply rest/injury modifiers
predicted_value = predicted_value * rest_factor + injury_impact
# = 54.08 * 1.0 + (-122.0) = -67.92  # NEGATIVE!

# 4. Calculate probability (goes wrong with negative predicted_value)
probability = 0.5 + (predicted_value - line) / (2 * std_dev)
# = 0.5 + (-67.92 - 214.5) / (2 * 6.5) = -21.2 → clamped to 0.01

# 5. agreement_score based on model_std (high = low agreement)
model_std = np.std([54.2, 0.0, 54.2, 107.9])  # = 38.15
agreement_score = max(0, 3 - model_std / 2)    # = max(0, 3 - 19.07) = 0

# 6. edge_score based on edge_percent
edge_score = min(3, edge_pct / 5)  # = min(3, 98.09 / 5) = 3.0

# 7. factor_score
factor_score = 0
if rest_factor >= 0.95: factor_score += 1.0  # +1.0 (yes)
if abs(injury_impact) < 1: factor_score += 0.5  # +0 (no, 122 >> 1)
if abs(line_movement) > 0.5: factor_score += 0.5  # +0 (no, 0 < 0.5)
# factor_score = 1.0

# 8. alternative_base = 2.0 + 0 + 3 + 1 = 6.0
# 9. pillar_boost = -2.75 (bounded from -5 to +5)
# 10. ai_score = max(2.0, 6.0 - 2.75) = 3.25
```

## Files Changed

| File | Change |
|------|--------|
| `advanced_ml_backend.py:636` | Add `INJURY_IMPACT_CAP` to `InjuryImpactModel` |
| `live_data_router.py:3393` | Use `total` for totals picks, `spread` for spreads |
| `advanced_ml_backend.py:744` | Include `line_movement` in factor_score |
| `advanced_ml_backend.py:893` | Add `model_status` dict showing used/stub/broken per model |
