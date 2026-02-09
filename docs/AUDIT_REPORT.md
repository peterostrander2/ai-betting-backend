# Backend Audit Report — Option A / Integrations / Persistence / Live Betting

Date: 2026-02-09
Git SHA: (pending commit)

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
