# Backend Audit Report — Option A / Integrations / Persistence / Live Betting

Date: 2026-02-04
Git SHA: f590006a90dc66bf18909f2e4de4a4d055256c1a

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
- live_sanity_check: **PASS** (operator run 2026‑02‑04 ET)
- api_proof_check: **PASS** (operator run 2026‑02‑04 ET)
- perf_audit_best_bets: **PASS** (operator run 2026‑02‑04 ET)

**Ship/No‑Ship (local only):** PASS
**Ship/No‑Ship (prod network):** PASS (operator network checks confirmed)

## 2) Scoring Verification — Option A

**Canonical formula (Option A):**
- BASE_4 = AI*0.25 + Research*0.35 + Esoteric*0.20 + Jarvis*0.20
- CONTEXT_MODIFIER_CAP = 0.35 (context is a bounded modifier, not a weighted engine)
- FINAL = min(10, BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment)

**Proof (local):**
- `tests/test_option_a_scoring_guard.py` asserts no context engine weight, no BASE_5, and checks formula shape.
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

## 6) Performance Audit

**Script:** `scripts/perf_audit_best_bets.sh`
- Collects `debug_timings` (P50/P95) per sport.
- Flags high‑latency stages for investigation.

**Operator Result (2026‑02‑04 ET):**
- NBA p50 ≈ 45.9s (full pipeline)
- NHL p50 ≈ 53.2s (full pipeline)
- NFL/MLB/NCAAB: no games/off‑season

## 7) Persistence + Storage

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
