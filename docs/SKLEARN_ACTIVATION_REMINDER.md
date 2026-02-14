# Sklearn Ensemble Activation Reminder

**Created:** 2026-02-14
**Target Activation Date:** 2026-02-21 (7 days of shadow data)
**Status:** ⏳ SHADOW MODE (waiting for data accumulation)

---

## What's Running Now

The sklearn ensemble regressors (XGBoost, LightGBM, RandomForest) are:
- ✅ Training daily at 7:15 AM ET
- ✅ Saving models to `/data/models/ensemble_sklearn_regressors.joblib`
- ✅ Loading on startup (for telemetry)
- ⏸️ NOT affecting predictions (shadow mode)

---

## 7-Day Verification Checklist

Run this on **February 21, 2026** or later:

```bash
API_KEY=your_key ./scripts/verify_sklearn_shadow.sh
```

### Manual Verification Commands

**1. Check training status:**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '{
    sklearn_mode: .sklearn_status.sklearn_mode,
    sklearn_trained: .sklearn_status.sklearn_trained,
    models_exist: .sklearn_status.models_exist,
    last_train_time: .sklearn_status.last_train_time,
    training_samples: .sklearn_status.training_samples
  }'
```

**Expected output:**
```json
{
  "sklearn_mode": "SHADOW",
  "sklearn_trained": false,
  "models_exist": true,
  "last_train_time": "2026-02-XX...",
  "training_samples": 50+
}
```

**2. Check score capture working:**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/picks/graded?limit=10" \
  -H "X-API-Key: YOUR_KEY" | jq '[.[] | {
    pick_id, result, actual_home_score, actual_away_score
  }]'
```

**3. Check training health:**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.training_health'
# Should be: "HEALTHY"
```

---

## How to Enable Live Mode

**Only do this after verification passes:**

1. Go to Railway Dashboard
2. Navigate to your project → Variables
3. Add new variable:
   ```
   ENSEMBLE_SKLEARN_ENABLED=true
   ```
4. Railway will auto-redeploy

### What Changes

| Aspect | Shadow Mode | Live Mode |
|--------|-------------|-----------|
| `sklearn_mode` | SHADOW | LIVE |
| `_ensemble_pipeline_trained` | False | True |
| Scoring impact | None | Uses trained models |

---

## Post-Activation Monitoring

After enabling, monitor for 24-48 hours:

1. **Score Distribution:**
   ```bash
   curl -s "https://web-production-7b2a.up.railway.app/ops/score-distribution?sport=NBA" \
     -H "X-API-Key: YOUR_KEY" | jq '.distribution'
   ```

2. **Pick Quality:**
   - Watch for unusual score inflation/deflation
   - Compare before/after pick distributions

3. **Training Status:**
   ```bash
   curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
     -H "X-API-Key: YOUR_KEY" | jq '.sklearn_status.sklearn_mode'
   # Should now show: "LIVE"
   ```

---

## Rollback (If Needed)

If scores drift unexpectedly:

1. Remove the environment variable:
   ```
   ENSEMBLE_SKLEARN_ENABLED  (delete it)
   ```
2. Or set to false:
   ```
   ENSEMBLE_SKLEARN_ENABLED=false
   ```
3. Redeploy - models return to shadow mode immediately

---

## Files Involved

| File | Purpose |
|------|---------|
| `advanced_ml_backend.py` | EnsembleStackingModel with save/load |
| `scripts/train_ensemble_regressors.py` | Training pipeline |
| `daily_scheduler.py` | 7:15 AM training job |
| `team_ml_models.py` | `_get_sklearn_status()` for telemetry |
| `live_data_router.py` | `/debug/training-status` endpoint |

---

## Contact

Questions about this activation? Check:
- `docs/ML_REFERENCE.md` - Full ML documentation
- `CLAUDE.md` - System invariants
- Railway logs for training job output
