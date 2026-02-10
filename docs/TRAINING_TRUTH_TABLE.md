# Engine 1 Training Truth Table

**v20.17.2** - Mechanically Verifiable Training Pipeline Documentation

This document defines what the Engine 1 daily training pipeline **actually does** in code. Every claim is backed by a code pointer.

---

## Overview

The training pipeline runs daily at **7:00 AM ET** via `daily_scheduler.py`. It trains three ML models from graded picks stored in `/data/grader/predictions.jsonl`.

### Key Files

| File | Purpose | Line References |
|------|---------|-----------------|
| `scripts/train_team_models.py` | Main training script | Entry point |
| `team_ml_models.py` | Model classes (LSTM, Matchup, Ensemble) | Model implementations |
| `grader_store.py` | Pick persistence (predictions.jsonl) | Data source |
| `scripts/audit_training_store.py` | Store audit utility | Verification |
| `daily_scheduler.py:174` | Scheduler config (7 AM ET job) | Automation |

---

## Data Source Contract

### Store Location
```
Path: ${RAILWAY_VOLUME_MOUNT_PATH}/grader/predictions.jsonl
Default: /data/grader/predictions.jsonl
Format: JSONL (one JSON record per line)
Schema Version: 1.0
```

### Required Record Fields for Training

| Field | Type | Required For | Missing Behavior |
|-------|------|--------------|------------------|
| `grade_status` | string | All models | Dropped (no_grade) |
| `result` | string | All models | Dropped (no_result) |
| `pick_type` | string | Market filtering | Dropped (wrong_market) |
| `sport` | string | Sport filtering | Dropped (missing_field) |
| `home_team` | string | Team models | Dropped (missing_field) |
| `away_team` | string | Team models | Dropped (missing_field) |
| `date_et` | string | Time window | Dropped (outside_window) |
| `ai_breakdown.raw_inputs.model_preds.values` | array[4] | Ensemble only | Dropped (no_model_preds) |

---

## Filter Pipeline (Mechanically Checkable)

### Filter Order (Mutually Exclusive)
Picks are filtered in this exact order. Each pick counts in **exactly one** drop bucket.

```
1. drop_no_grade          - grade_status != "GRADED"
2. drop_no_result         - result not in ("WIN", "LOSS", "PUSH")
3. drop_wrong_market      - pick_type not in SUPPORTED_GAME_MARKETS
4. drop_missing_required  - home_team, away_team, sport, date_et empty
5. drop_outside_window    - date_et outside training window (default: 7 days)
6. drop_wrong_sport       - sport filter applied and doesn't match
```

**Code Reference:** `scripts/train_team_models.py:load_graded_picks()`

### Filter Math Assertion
```python
# INVARIANT: Must hold true for every training run
assert eligible_total + sum_of_drops == loaded_total
```

Where:
- `loaded_total` = total records read from predictions.jsonl
- `sum_of_drops` = drop_no_grade + drop_no_result + drop_wrong_market + drop_missing_required + drop_outside_window + drop_wrong_sport
- `eligible_total` = records that passed all filters

---

## Model Training Contracts

### 1. Team LSTM Model

**Purpose:** Learn team-level patterns from historical picks.

**Training Source:** Graded picks with valid team names.

**Features Used:**
- Team name (home/away)
- Sport
- Result (WIN/LOSS)

**Output:**
```python
{
    "games_processed": int,
    "teams_cached_total": int,
    "feature_schema_hash": str,  # SHA256 of sorted feature names
    "sports_included": List[str],
}
```

**Code Reference:** `scripts/train_team_models.py:update_team_cache()`

### 2. Team Matchup Model

**Purpose:** Track historical head-to-head matchup outcomes.

**Training Source:** Graded picks with valid team names.

**Features Used:**
- Home team vs Away team pairing
- Sport
- Result (WIN/LOSS)

**Output:**
```python
{
    "games_processed": int,
    "matchups_tracked_total": int,
    "feature_schema_hash": str,
    "sports_included": List[str],
}
```

**Code Reference:** `scripts/train_team_models.py:update_matchup_matrix()`

### 3. Game Ensemble Model

**Purpose:** Combine predictions from multiple models into calibrated hit probability.

**Training Source:** Graded picks with `ai_breakdown.raw_inputs.model_preds.values` array.

#### Label Definition (CRITICAL)

```python
# Binary hit classification
label_type: "binary_hit"
label_definition: "hit = 1.0 if result == WIN, hit = 0.0 if result == LOSS, PUSH excluded"
```

**INVARIANT:** The ensemble ONLY uses binary classification:
- WIN = 1.0 (hit)
- LOSS = 0.0 (miss)
- PUSH = excluded (not trained on)

**Feature Requirements:**
```python
REQUIRED_MODEL_PREDS_LENGTH = 4  # Must have exactly 4 model prediction values
```

**Per-Model Filter Telemetry:**
```python
{
    "eligible_from_upstream": int,     # Picks passed upstream filters
    "drop_no_model_preds": int,        # Missing ai_breakdown.raw_inputs.model_preds
    "drop_insufficient_values": int,   # len(values) < 4
    "drop_no_result": int,             # Result not WIN/LOSS
    "drop_push_excluded": int,         # PUSH results (excluded by design)
    "used_for_training": int,          # Actually used for sklearn fit()
    "assertion_passed": bool,          # Math reconciles
}
```

**Schema Match Verification:**
```python
{
    "training_feature_schema_hash": str,   # Hash of features used in training
    "inference_feature_schema_hash": str,  # Hash of features used at runtime
    "schema_match": bool,                  # MUST be True for valid deployment
}
```

**Code Reference:** `scripts/train_team_models.py:update_ensemble_weights()`

---

## Training Signatures

Every model training produces a **training signature** that is recorded for auditability.

```python
{
    "training_run_id": str,                 # Unique ID for this training run
    "training_timestamp": str,              # ISO timestamp
    "samples_used": int,                    # Actual samples in sklearn fit()
    "feature_schema_hash": str,             # Deterministic hash of feature names
    "label_type": str,                      # "binary_hit" for ensemble
    "label_definition": str,                # Human-readable label definition
    "schema_match": bool,                   # Training vs inference features match
    "filter_telemetry": dict,               # Per-model drop counts
}
```

---

## Store Audit Utility

### Purpose
Mechanically verify training store contents without loading into memory.

### Usage
```bash
# CLI usage
python scripts/audit_training_store.py --json

# API usage (from training-status endpoint)
from scripts.audit_training_store import get_store_audit_summary
audit = get_store_audit_summary()
```

### Output Fields

```python
{
    "store_provenance": {
        "path": str,                    # File path
        "volume_mount_path": str,       # Railway volume root
        "exists": bool,                 # File exists
        "mtime_iso": str,               # Last modified time
        "line_count": int,              # Total lines
        "size_bytes": int,              # File size
        "store_schema_version": str,    # "1.0"
    },
    "data_quality": {
        "total_records": int,           # Successfully parsed records
        "graded_count": int,            # Records with grade_status=GRADED
        "ungraded_count": int,          # Records without GRADED status
        "missing_grade_status": int,    # Records missing grade_status field
        "missing_result": int,          # Records missing result field
        "missing_model_preds_total": int,  # Records missing model_preds
        "missing_model_preds_attribution": {
            "old_schema": int,          # Before model_preds was added
            "non_game_market": int,     # Props don't use ensemble
            "error_path": int,          # Error/timeout during scoring
            "unknown": int,             # Cannot determine reason
        },
        "missing_model_preds_by_market": {
            "game": int,                # Game picks missing model_preds
            "prop": int,                # Prop picks (expected to be missing)
        },
        "insufficient_model_preds": int,  # len(values) < 4
    },
    "distribution": {
        "by_sport": dict,               # {NBA: N, NFL: M, ...}
        "by_market": dict,              # {game: N, prop: M, other: K}
        "by_pick_type_top5": dict,      # Top 5 pick types by count
    },
    "eligible_timestamp_range": {
        "earliest": str,                # ISO timestamp of oldest eligible pick
        "latest": str,                  # ISO timestamp of newest eligible pick
    },
    "reconciliation": {
        "total_lines": int,             # Total lines in file
        "parsed_ok": int,               # Successfully parsed
        "parse_errors": int,            # Failed to parse
        "reconciled": bool,             # parsed_ok + parse_errors == total_lines
    },
}
```

### Attribution Buckets for Missing model_preds

| Bucket | Meaning | Expected? |
|--------|---------|-----------|
| `old_schema` | Record predates model_preds introduction (before 2026-02-01) | Yes |
| `non_game_market` | Prop/other market (not scored by game ensemble) | Yes |
| `error_path` | Error/timeout/fallback during scoring | Investigate if high |
| `unknown` | Cannot determine reason | Investigate if high |

---

## Verification Commands

### Check Training Health
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.training_health'
# Expected: "HEALTHY"
```

### Check Store Audit
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.store_audit'
```

### Run Store Audit Locally
```bash
python scripts/audit_training_store.py --json --path /data/grader/predictions.jsonl
```

### Verify Filter Math
```bash
# The assertion_passed field must be true
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.training_telemetry.filter_telemetry.assertion_passed'
# Expected: true
```

### Check Ensemble Schema Match
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.model_status.ensemble_training_signature.schema_match'
# Expected: true
```

---

## Anti-Patterns (NEVER DO)

1. **NEVER** train on PUSH results - they are excluded by design
2. **NEVER** use regression labels (e.g., "line ± 5") - use binary_hit only
3. **NEVER** skip filter telemetry assertions
4. **NEVER** merge graded and ungraded counts
5. **NEVER** assume all records have model_preds (props don't)
6. **NEVER** call predict() on unfitted sklearn models

---

## Scheduler Contract

### Training Job
```python
Job ID: "team_model_train"
Schedule: 7:00 AM ET daily
Script: scripts/train_team_models.py
Timeout: 10 minutes
```

### Training Verification Job
```python
Job ID: "training_verification"
Schedule: 7:30 AM ET daily (30 min after training)
Purpose: Verify 7 AM training executed successfully
On Failure: Logs ERROR, writes alert to /data/audit_logs/training_alert_{date}.json
```

---

## Test Coverage

Tests in `tests/test_training_telemetry.py`:

1. `test_filter_counts_sum_correctly` - Verify filter math assertion
2. `test_used_for_training_never_exceeds_eligible` - Sanity check
3. `test_drop_counts_are_mutually_exclusive` - Each pick in exactly one bucket
4. `test_filter_version_present` - Schema tracking
5. `test_schema_hash_consistency` - Same features = same hash
6. `test_schema_hash_differs_for_different_features` - Different features = different hash
7. `test_team_cache_returns_training_signature` - LSTM training signature
8. `test_matchup_matrix_returns_training_signature` - Matchup training signature
9. `test_ensemble_returns_training_signature` - Ensemble with label_definition
10. `test_model_status_includes_training_telemetry` - Status endpoint integration
11. `test_model_status_includes_per_model_signatures` - Per-model signatures present

---

## Changelog

- **v20.17.2** - Added store audit utility, attribution buckets, enhanced training-status endpoint
- **v20.17.1** - Fixed label definition (binary_hit), renamed telemetry fields
- **v20.17.0** - Added mechanically checkable filter telemetry
- **v20.16.3** - Added training-status endpoint
