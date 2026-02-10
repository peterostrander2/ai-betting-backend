# Backend Audit Report — Option A / Integrations / Persistence / Live Betting

Date: 2026-02-10
Git SHA: (pending commit)

---

## Engine 2 Research Semantic Audit (v20.16+) — February 10, 2026

### Summary

The Research Engine (Engine 2) has been audited for anti-conflation compliance. The core issue was that both `sharp_boost` (should be Playbook-only) and `line_boost` (should be Odds API-only) were reading from the same `sharp_signal` dict, allowing line variance to incorrectly upgrade sharp signal strength.

### Problem Statement

**The Conflation Bug (Fixed in v20.16):**

```python
# OLD CODE (lines 2030-2033) - BUG!
if lv >= 2.0 and signal["signal_strength"] in ("NONE", "MILD"):
    signal["signal_strength"] = "STRONG"  # Odds API data contaminating Playbook field!
```

**Symptom:** "Sharp signal STRONG" appeared when it was actually line variance triggering it.

### Fix Applied

1. **Separate Objects:** Created distinct `playbook_sharp` and `odds_line` objects
2. **Exclusive Reading:** `sharp_boost` reads ONLY from `playbook_sharp`, `line_boost` reads ONLY from `odds_line`
3. **Independent Strength Fields:** Added `sharp_strength` (Playbook) and `lv_strength` (Odds API) as separate fields

### Anti-Conflation Invariants

| Invariant | Description | Verification |
|-----------|-------------|--------------|
| Source Attribution | `sharp_boost.source_api == "playbook_api"` | `/debug/research-candidates` |
| Source Attribution | `line_boost.source_api == "odds_api"` | `/debug/research-candidates` |
| Sharp Reason Gate | If `playbook_sharp.status != SUCCESS`, reasons MUST NOT contain "Sharp" | `test_research_truthfulness.py` |
| Usage Counter Proof | If `sharp_boost.status == SUCCESS`, `playbook_calls_delta >= 1` | Runtime audit |
| Usage Counter Proof | If `line_boost.status == SUCCESS`, `odds_api_calls_delta >= 1` | Runtime audit |

### New Files

| File | Purpose |
|------|---------|
| `core/research_types.py` | ComponentStatus enum, type definitions, validation helpers |
| `docs/RESEARCH_TRUTH_TABLE.md` | Complete Research engine contract documentation |
| `tests/test_research_truthfulness.py` | 12 anti-conflation tests |
| `scripts/engine2_research_audit.py` | Python runtime audit script |
| `scripts/engine2_research_audit.sh` | Shell wrapper for full audit |

### New Debug Endpoint

**GET /debug/research-candidates/{sport}**

Returns pre-filter candidates with full research breakdown:

```json
{
  "candidates_pre_filter": [
    {
      "pick_id": "abc123",
      "final_score": 7.5,
      "research_breakdown": {
        "sharp_boost": {
          "value": 1.5,
          "status": "SUCCESS",
          "source_api": "playbook_api",
          "raw_inputs_summary": {"ticket_pct": 45, "money_pct": 62}
        },
        "line_boost": {
          "value": 3.0,
          "status": "SUCCESS",
          "source_api": "odds_api",
          "raw_inputs_summary": {"line_variance": 2.5}
        }
      }
    }
  ],
  "auth_context": {
    "playbook_api": {"key_present": true},
    "odds_api": {"key_present": true}
  },
  "usage_counters_delta": {"playbook_calls": 1, "odds_api_calls": 1}
}
```

### Verification Commands

```bash
# Run unit tests
pytest tests/test_research_truthfulness.py tests/test_sharp_lv_separation.py -v

# Run static + runtime audit
API_KEY=xxx ./scripts/engine2_research_audit.sh --sport NBA

# Check debug endpoint manually
curl "https://web-production-7b2a.up.railway.app/debug/research-candidates/NBA?limit=5" \
  -H "X-API-Key: YOUR_KEY" | jq '.candidates_pre_filter[0].research_breakdown'
```

### Component Status Values

| Status | Meaning |
|--------|---------|
| `SUCCESS` | API call succeeded, data present |
| `NO_DATA` | API call succeeded but no relevant data |
| `ERROR` | API call failed (timeout, 4xx, 5xx) |
| `DISABLED` | Feature flag disabled |

### Source Attribution Matrix

| Component | Source API | Status Key | Boost Range |
|-----------|------------|------------|-------------|
| `sharp_boost` | `playbook_api` | `sharp_strength` | 0.0 - 3.0 |
| `line_boost` | `odds_api` | `lv_strength` | 0.0 - 3.0 |
| `public_boost` | `playbook_api` | `public_pct` | 0.0 - 2.0 |
| `espn_odds_boost` | `espn_api` | n/a | 0.0 - 0.5 |
| `liquidity_boost` | `odds_api` | n/a | 0.0 - 0.5 |

### Test Coverage

| Test | Purpose |
|------|---------|
| `test_line_variance_cannot_set_sharp_strength` | Verify lv can never escalate sharp |
| `test_sharp_strength_only_from_playbook_sharp` | Verify sharp reads from Playbook only |
| `test_line_boost_only_from_odds_line` | Verify line reads from Odds API only |
| `test_source_api_tags_present` | Verify source attribution |
| `test_no_sharp_reason_when_playbook_not_success` | Verify reason string invariant |
| `test_network_proof_2xx_delta` | Verify network proof matches status |

---

## Training Pipeline Visibility (v20.16.3) — February 10, 2026

### Summary

Enhanced scheduler and training status endpoints to provide decisive proof that the training pipeline is executing and persisting correctly.

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/scheduler/status` | GET | **Enhanced** - Now shows all jobs with next_run_time_et, trigger, misfire_grace_time |
| `/live/debug/training-status` | GET | **NEW** - Comprehensive training status with artifact proof and health status |
| `/live/grader/train-team-models` | POST | **Exists** - Manual trigger for training pipeline |

### GET /live/scheduler/status

Enhanced to return detailed job information:

```json
{
  "available": true,
  "scheduler_running": true,
  "jobs": [
    {
      "id": "daily_audit",
      "name": "Daily Audit",
      "next_run_time_et": "2026-02-10T06:00:00-05:00",
      "trigger_type": "CronTrigger",
      "trigger": "cron[hour='6', minute='0']"
    },
    {
      "id": "team_model_train",
      "name": "Daily Team Model Training",
      "next_run_time_et": "2026-02-10T07:00:00-05:00",
      "trigger_type": "CronTrigger",
      "trigger": "cron[hour='7', minute='0']"
    }
  ],
  "training_job_registered": true
}
```

### GET /live/debug/training-status

Returns comprehensive training status:

```json
{
  "model_status": {
    "ensemble": "TRAINED",
    "ensemble_samples_trained": 21,
    "ensemble_is_trained": true,
    "lstm": "TRAINED",
    "lstm_teams_cached": 205,
    "matchup": "TRAINED",
    "matchup_tracked": 135
  },
  "training_telemetry": {
    "last_train_run_at": "2026-02-10T03:54:07",
    "graded_samples_seen": 866,
    "samples_used_for_training": 21,
    "volume_mount_path": "/data"
  },
  "artifact_proof": {
    "team_data_cache.json": {
      "exists": true,
      "size_bytes": 45678,
      "mtime_iso": "2026-02-10T03:54:07-05:00"
    },
    "matchup_matrix.json": {
      "exists": true,
      "size_bytes": 12345,
      "mtime_iso": "2026-02-10T03:54:07-05:00"
    },
    "ensemble_weights.json": {
      "exists": true,
      "size_bytes": 1024,
      "mtime_iso": "2026-02-10T03:54:07-05:00"
    }
  },
  "scheduler_proof": {
    "job_registered": true,
    "next_run_time_et": "2026-02-10T07:00:00-05:00"
  },
  "training_health": "HEALTHY",
  "graded_picks_count": 866,
  "errors": null
}
```

### Training Health States

| State | Condition | Meaning |
|-------|-----------|---------|
| **HEALTHY** | Training ran within 24h OR no graded picks exist | Normal operation |
| **STALE** | Training older than 24h AND graded picks > 0 | Training should have run |
| **NEVER_RAN** | last_train_run_at is null AND graded picks > 0 | Training pipeline never executed |

### Non-Negotiable Proof Fields

| Field | Required In | Purpose |
|-------|-------------|---------|
| `training_job_registered` | scheduler/status | Confirms 7 AM ET job exists |
| `next_run_time_et` | scheduler/status, debug/training-status | Proves next scheduled run |
| `artifact_proof[file].exists` | debug/training-status | Proves artifacts written to disk |
| `artifact_proof[file].mtime_iso` | debug/training-status | Proves when artifacts updated |
| `training_health` | debug/training-status | Overall health classification |
| `graded_picks_count` | debug/training-status | Shows data available for training |

### Verification Commands

```bash
# Check scheduler status and training job
curl "https://web-production-7b2a.up.railway.app/live/scheduler/status" \
  -H "X-API-Key: YOUR_KEY" | jq '.jobs[] | select(.id == "team_model_train")'

# Check training status with artifact proof
curl "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '{health: .training_health, artifacts: .artifact_proof}'

# Manual training trigger (optional)
curl -X POST "https://web-production-7b2a.up.railway.app/live/grader/train-team-models" \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"days": 7}'
```

### Tests Added

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `tests/test_training_status.py` | 12 | Scheduler job visibility, artifact proof shape, training health logic |

---

## Engine 4 Jarvis Overhaul (v20.1) — February 9, 2026

### Summary

Engine 4 (Jarvis) has been overhauled to integrate MSRF as an internal component rather than a post-base boost. SERP has been deterministically disabled (no paid API).

### Changes

| Component | Before | After | Reason |
|-----------|--------|-------|--------|
| MSRF post-base boost | 0..1.0 | **forced 0.0** | Now inside Jarvis engine (no double-count) |
| SERP boost | 0..4.3 | **forced 0.0** | No paid SERP API |
| Jason Sim cap | ±1.5 | **±2.0** | Monte Carlo earned more budget |
| JARVIS_MSRF_COMPONENT_CAP | n/a | **2.0** | New: bounds MSRF inside Jarvis |
| SERP_ENABLED | n/a | **False** | New: deterministic status flag |
| MSRF_ENABLED | n/a | **False** | New: deterministic status flag |

### Scoring Formula (v20.1)

```
final_score = clamp(
    base_4
  + context_modifier           (cap: ±0.35)
  + confluence_boost            (cap: 0..10)
  + jason_sim_boost             (cap: ±2.0)
  + ensemble_boost              (cap: 0..1.0)
  + hook_penalty                (cap: -0.5..0)
  + expert_consensus_boost      (cap: 0..0.75)
  + prop_correlation_adjustment (cap: ±0.5)
  + totals_calibration_adj      (cap: ±0.5)
  , 0.0, 10.0
)

base_4 = ai_score       × 0.25   (FROZEN)
       + research_score  × 0.35   (FROZEN)
       + esoteric_score  × 0.20   (FROZEN)
       + jarvis_score    × 0.20   (FROZEN)
```

### Jarvis-Ophis Hybrid (Engine 4)

**Blend:** 53% Ophis / 47% Jarvis ("TITAN BLEND")

**MSRF Integration:**
- Ophis Z-scan produces Z-values from win-date temporal analysis
- Jarvis scores those Z-values against MSRF sacred number sets
- MSRF contribution is clamped to `JARVIS_MSRF_COMPONENT_CAP` (2.0)
- Jarvis returns `jarvis_msrf_component` and `jarvis_msrf_component_raw` in payload
- `msrf_status` is always `"IN_JARVIS"` in normal operation

### Payload Fields (Engine 4)

| Field | Type | Description |
|-------|------|-------------|
| `jarvis_rs` | float | Jarvis score (0-10) |
| `jarvis_msrf_component` | float | MSRF contribution (clamped) |
| `jarvis_msrf_component_raw` | float | MSRF contribution (raw) |
| `msrf_status` | string | Always "IN_JARVIS" |
| `jarvis_triggers_hit` | list | Sacred number triggers hit |
| `jarvis_reasons` | list | Scoring reasons |

### Files Added/Modified

| File | Purpose |
|------|---------|
| `core/compute_final_score.py` | **NEW** - Single source of truth for final_score |
| `core/jarvis_ophis_hybrid.py` | **NEW** - Engine 4 implementation with MSRF |
| `tests/test_reconciliation.py` | **NEW** - 35 unit tests for v20.1 |
| `scripts/engine4_jarvis_audit.py` | **NEW** - Runtime audit script |
| `scripts/engine4_jarvis_audit.sh` | **NEW** - Shell wrapper |
| `docs/AUDIT_REPORT.md` | Updated with v20.1 changes |

### Verification Commands

```bash
# Unit tests (35 tests)
cd /Users/apple/ai-betting-backend && python -m pytest tests/test_reconciliation.py -v

# Runtime audit (local)
python scripts/engine4_jarvis_audit.py --local

# Runtime audit (production)
API_KEY=xxx python scripts/engine4_jarvis_audit.py --url https://web-production-7b2a.up.railway.app --sport nba

# Full test suite
python -m pytest -q
```

### Non-Negotiable Invariants

1. **BASE_4 uses exactly 4 engines** with frozen weights (25/35/20/20)
2. **msrf_boost is forced to 0.0** everywhere (router, scoring pipeline, payload, tests)
3. **serp_boost is forced to 0.0** with `serp_status="DISABLED"`
4. **Final score reconciles** within `abs(delta) <= 0.02`
5. **Engine scores are NEVER mutated** after base_score is computed

---

## Previous Audit (2026-02-04)

## 1) Executive Summary (PASS/FAIL Matrix)

Local checks (run here):
- pytest -q: **PASS** (501 passed, 46 skipped)
- option_a_drift_scan: **PASS**
- audit_drift_scan (local-only): **PASS** (payload checks skipped; network unavailable)
- docs_contract_scan: **PASS**
- env_drift_scan: **PASS**
- learning_sanity_check: **PASS** (warnings due to missing local files)
- learning_loop_sanity: **PASS** (warnings due to missing local files)
- endpoint_matrix_sanity: **PASS** (operator run 2026‑02‑04 ET)
- prod_endpoint_matrix: **PASS** (operator run 2026‑02‑04 ET)
- signal_coverage_report: **PASS** (operator run 2026‑02‑04 ET)
- live_sanity_check: **PASS** (operator run 2026‑02‑04 ET)
- api_proof_check: **PASS** (operator run 2026‑02‑04 ET)
- perf_audit_best_bets: **PASS** (operator run 2026‑02‑04 ET)

**Ship/No‑Ship (local only):** PASS
**Ship/No‑Ship (prod network):** PASS (operator network checks confirmed)

## 2) Scoring Verification — Option A

**Canonical formula (Option A):**
- BASE_4 = AI*0.25 + Research*0.35 + Esoteric*0.20 + Jarvis*0.20
- CONTEXT_MODIFIER_CAP = 0.35 (context is a bounded modifier, not a weighted engine)
- FINAL = min(10, BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment + live_adjustment)

**Proof (local):**
- `tests/test_option_a_scoring_guard.py` asserts no context engine weight, no BASE_5, and checks formula shape.
- `tests/test_scoring_invariants_phase1.py` asserts Option A math with explicit post-base adjustments.
- `scripts/option_a_drift_scan.sh` checks runtime paths for forbidden patterns.
- `core/scoring_contract.py` defines ENGINE_WEIGHTS (4 engines only) and caps.

**Forbidden patterns search (local):**
- `BASE_5`, `ENGINE_WEIGHTS["context"]`, and context weights **not found** in scoring paths.

## 3) Boost Inventory + Caps

| Boost / Term | Where computed | Cap | Included in final_score | Notes |
|---|---|---|---|---|
| confluence_boost | `live_data_router.py` | `CONFLUENCE_BOOST_CAP` | Yes | Confluence level boosts | 
| msrf_boost | `signals/msrf_resonance.py` | `MSRF_BOOST_CAP` | Yes | 0.0/0.25/0.5/1.0 | 
| jason_sim_boost | `jason_sim_confluence.py` | `JASON_SIM_BOOST_CAP` | Yes | Can be negative | 
| serp_boost | `alt_data_sources/serp_intelligence.py` | `SERP_BOOST_CAP_TOTAL` | Yes | Total SERP cap | 
| ensemble_adjustment | `utils/ensemble_adjustment.py` | `ENSEMBLE_ADJUSTMENT_STEP` | Yes | +0.5/-0.5 step | 
| live_adjustment | `alt_data_sources/live_signals.py` (applied to research_score) | `LIVE_ADJUSTMENT_CAP` (internal) | Yes | Applied when in-play | 
| harmonic_boost | `live_data_router.py` | (internal) | No (folded into confluence) | Not additive to final | 
| glitch_adjustment | `live_data_router.py` | (internal) | No (folded into esoteric) | Not additive to final | 

## 4) Integration Validation (Local View)

**Expected required integrations:**
- Odds API, Playbook API, BallDontLie, SerpAPI, Weather (relevance‑gated), NOAA, Astronomy, FRED, Finnhub, Twitter, Whop, Database, Redis, Railway storage.

**Runtime validation (requires network):**
- Use `/live/debug/integrations` to confirm VALIDATED vs CONFIGURED and `last_used_at` telemetry.
- `scripts/api_proof_check.sh` enforces required paid APIs are VALIDATED and that status fields appear in payloads.

## 5) Endpoint Matrix (Network Required)

Required fields in `/live/best-bets/{sport}?debug=1`:
- `base_4_score`, `context_modifier`, `confluence_boost`, `msrf_boost`, `jason_sim_boost`, `serp_boost`, `ensemble_adjustment`, `final_score`
- status fields: `msrf_status`, `serp_status`, `jason_status`

**Local run:** SKIPPED due to network/DNS in this environment.
**Report:** `docs/ENDPOINT_MATRIX_REPORT.md`

## 6) Paid API Telemetry (Debug-Only)

**Debug telemetry added:**
- `debug.integration_calls` includes called/status/latency/cache_hit (best-effort).
- `debug.integration_impact` includes nonzero boost counts + reasons counts.
- `debug.integration_totals` includes calls_made + cache_hit_rate.

**Daily rollup (Railway volume):**
- `RAILWAY_VOLUME_MOUNT_PATH/telemetry/daily_YYYY-MM-DD.json`

## 7) Signal Coverage

**Script:** `scripts/signal_coverage_report.py`  
**Outputs:** `docs/SIGNAL_COVERAGE_REPORT.md`, `artifacts/signal_coverage.json`

## 8) Performance Audit

**Script:** `scripts/perf_audit_best_bets.sh`
- Collects `debug_timings` (P50/P95) per sport.
- Flags high‑latency stages for investigation.

**Operator Result (2026‑02‑04 ET):**
- NBA p50 ≈ 45.9s (full pipeline)
- NHL p50 ≈ 53.2s (full pipeline)
- NFL/MLB/NCAAB: no games/off‑season

## 9) Persistence + Storage

**Requirements:** All persistent data must be under `RAILWAY_VOLUME_MOUNT_PATH`.

**Local checks:**
- `scripts/learning_sanity_check.sh` and `scripts/learning_loop_sanity.sh` PASS (warnings due to missing local files).

**Paths:**
- Predictions: `${RAILWAY_VOLUME_MOUNT_PATH}/grader/predictions.jsonl`
- Weights: `${RAILWAY_VOLUME_MOUNT_PATH}/grader_data/weights.json`

## 8) Autograder + Learning Loop

**Schedule (ET):** 6:00 AM ET (autograder) / 6:15 AM ET (trap loop)
**Validated by:**
- `tests/test_learning_system_audit.py`
- `scripts/learning_loop_sanity.sh`

## 9) Frontend Contract Drift

**Reference:** `docs/PICK_CONTRACT_V1.md` + `docs/ENDPOINT_CONTRACT.md`
**Local check:** `tests/test_contract_docs_guard.py`

## 10) Action Items (Ranked)

1) Monitor best‑bets performance; consider precompute/caching if p95 grows.
2) Monitor best-bets performance (P95 timings) and tune time budget if needed.
3) Confirm integration `last_used_at` updates on cache hits for paid APIs.

## 11) Commands to Run Locally (Networked)

```
API_KEY="YOUR_KEY" bash scripts/endpoint_matrix_sanity.sh
API_KEY="YOUR_KEY" bash scripts/live_sanity_check.sh
API_KEY="YOUR_KEY" bash scripts/api_proof_check.sh
API_KEY="YOUR_KEY" bash scripts/perf_audit_best_bets.sh
```

## 12) Commands to Reproduce Local Audit

```
python3 -m pytest -q
bash scripts/option_a_drift_scan.sh
SKIP_NETWORK=1 bash scripts/audit_drift_scan.sh
bash scripts/docs_contract_scan.sh
bash scripts/env_drift_scan.sh
ALLOW_EMPTY=1 bash scripts/learning_sanity_check.sh
ALLOW_EMPTY=1 bash scripts/learning_loop_sanity.sh
```
## 10) Learning Loop Audit

**Report:** `docs/LEARNING_LOOP_AUDIT.md`

---

## NFL Props LSTM Status (v20.2 - February 8, 2026)

### Issue Summary

**Issue:** NFL props were using heuristic fallback instead of LSTM models, despite LSTM model files existing.

**Root Cause:** Missing market name mapping in `MARKET_TO_STAT`. The Odds API returns `player_reception_yds` but the mapping only had `player_rec_yds`.

**Fix Applied:** Added `player_reception_yds` to the mapping and improved fallback messaging.

**Status:** ✅ FIXED

### NFL LSTM Model Availability

| Stat Type | Model File | Status |
|-----------|------------|--------|
| passing_yards | `models/lstm_nfl_passing_yards.weights.h5` | ✅ Exists |
| rushing_yards | `models/lstm_nfl_rushing_yards.weights.h5` | ✅ Exists |
| receiving_yards | `models/lstm_nfl_receiving_yards.weights.h5` | ✅ Exists |

### Market → Stat Mapping (After Fix)

| Odds API Market | Stat Type | LSTM Model | Status |
|-----------------|-----------|------------|--------|
| `player_pass_yds` | passing_yards | nfl_passing_yards | ✅ Mapped |
| `player_passing_yards` | passing_yards | nfl_passing_yards | ✅ Mapped |
| `player_rush_yds` | rushing_yards | nfl_rushing_yards | ✅ Mapped |
| `player_rushing_yards` | rushing_yards | nfl_rushing_yards | ✅ Mapped |
| `player_rec_yds` | receiving_yards | nfl_receiving_yards | ✅ Mapped |
| `player_reception_yds` | receiving_yards | nfl_receiving_yards | ✅ **ADDED** |
| `player_receiving_yards` | receiving_yards | nfl_receiving_yards | ✅ Mapped |
| `player_pass_tds` | passing_yards | nfl_passing_yards | ✅ Proxy |
| `player_rush_tds` | rushing_yards | nfl_rushing_yards | ✅ Proxy |
| `player_receptions` | receiving_yards | nfl_receiving_yards | ✅ Proxy |

### Changes Made

1. **ml_integration.py** - Added `player_reception_yds` to MARKET_TO_STAT
2. **live_data_router.py** - Improved fallback messaging with clear reasons
3. **scripts/verify_lstm_props.sh** - New verification script

### Verification

```bash
./scripts/verify_lstm_props.sh NFL
API_KEY=your_key ./scripts/verify_lstm_props.sh NFL
```

### Contract: "LSTM Primary for Props When Available"

This contract is now enforced:

1. **When LSTM model exists:** Props use LSTM prediction, `ai_mode=ML_LSTM`
2. **When LSTM unavailable:** Props use heuristic, `ai_mode=HEURISTIC_FALLBACK`, ai_reasons explains why
3. **No silent fallbacks:** Every fallback includes a reason
