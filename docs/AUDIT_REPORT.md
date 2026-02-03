# Audit Report — ai-betting-backend

Date: 2026-02-03

## Executive Summary (Pass/Fail by Requirement)

1) **Option A only runtime scoring model:** **PASS (with noted additive term visibility gap)**
   - Option A weights and bounded context modifier are the only base model in runtime scoring paths. Evidence below.
   - **Exception:** an extra post-base `ensemble_adjustment` modifies `final_score` after the Option A sum and is not surfaced as a dedicated field.

2) **Every boost/modifier bounded + visible + documented + included in math check:** **PARTIAL PASS**
   - Bounded caps exist for context, MSRF, SERP, Jason, and final clamp in code.
   - **Gap:** `ensemble_adjustment` is bounded (+/-0.5) but not exposed as a top-level field in debug payloads; it only appears in `ai_reasons`.

3) **Engine separation & responsibilities (4 engines + context):** **PASS (with duplication/drift risk noted)**
   - Main runtime scoring in `live_data_router.py` computes AI/Research/Esoteric/Jarvis and context separately.
   - There is a separate research engine module (`research_engine.py`) that is not used in the main best-bets path (drift risk).

4) **Paid API usage is real + observable:** **PARTIAL PASS**
   - Odds API, Playbook API, BallDontLie, SerpAPI have call sites with telemetry (`mark_integration_used`).
   - **Gap:** integration contract `owner_modules` references non-existent filenames (e.g., `noaa_api.py`, `weather_api.py`, `serpapi.py`, `twitter_api.py`, `whop_integration.py`, `fred_api.py`, `finnhub_api.py`).

5) **Contract drift checks for BASE_5/context weighting/etc:** **PASS**
   - No runtime usage of `BASE_5` or `ENGINE_WEIGHTS["context"]` found; occurrences are in docs/tests only.

6) **Endpoint output consistency:** **PARTIAL PASS**
   - `/live/best-bets/{sport}?debug=1` exposes all required fields listed below.
   - **Gap:** `ensemble_adjustment` not exposed as a field despite affecting `final_score`.

---

## Audit Procedure Results

### A) Static Scan (rg summary)
Command:
```
rg -n "BASE_4|BASE_5|final_score\s*=|compute_final_score|context_modifier|CONTEXT_MODIFIER_CAP|ENGINE_WEIGHTS|context_weight|\+\s*0\.5|\-\s*0\.5|min\(10|max\(0|ensemble|pillars|harmonic|gematria|glitch_adjustment" .
```
Summary:
- `BASE_5` and `ENGINE_WEIGHTS["context"]` only appear in **docs/tests**, not runtime code.
  - `CLAUDE.md:5525`, `tests/test_option_a_scoring_guard.py:83`, `scripts/option_a_drift_scan.sh:14`.
- `compute_final_score_option_a` is defined once and used in runtime scoring paths.
  - `core/scoring_pipeline.py:59-83`, `live_data_router.py:4569-4576`, `live_data_router.py:7430-7437`, `live_data_router.py:11355-11362`.
- `ensemble_adjustment` is applied after `compute_final_score_option_a` in the game-pick path.
  - `live_data_router.py:4748-4758`, `utils/ensemble_adjustment.py:6-22`.

Single source of truth constants:
- **Scoring contract:** `core/scoring_contract.py:9-83` defines weights + caps.
- **Final score math:** `core/scoring_pipeline.py:59-83` defines Option A sum + clamping.

### B) End-to-End Scoring Path (Best-Bets runtime)

**Entry / scoring path:** `/live/best-bets/{sport}` uses `calculate_pick_score`.
- AI scoring + LSTM/heuristics in `live_data_router.py:3182-3463`.
- Research scoring in `live_data_router.py:3464-3650` (market pillars, sharp, line variance, public fade, etc.).
- Esoteric + Jarvis scoring in `live_data_router.py:3820-4240` (signals), with harmonic boost folded into confluence at `live_data_router.py:4273-4289`.
- Base score weights (Option A) and context modifier calculation at `live_data_router.py:4501-4523`.
- Final score formula uses `compute_final_score_option_a` at `live_data_router.py:4567-4576`.
- Post-base ensemble adjustment at `live_data_router.py:4746-4758` (applies +/-0.5 based on hit_prob).

**Proof of Option A base weights:**
- Contract weights: `core/scoring_contract.py:9-14`.
- Base score usage: `live_data_router.py:4506-4512` and `live_data_router.py:7424-7429`.

**Context modifier bounds:**
- Cap definition: `core/scoring_contract.py:16-18`.
- Clamp in scoring function: `core/scoring_pipeline.py:48-56` and `core/scoring_pipeline.py:72-83`.
- Runtime context_modifier computed and clamped: `live_data_router.py:4514-4523`.

### C) Integration Usage Audit (Paid APIs + telemetry)

**Telemetry registry:** `integration_registry.py:872-892` defines `mark_integration_used` with `used_count` + `last_used_at`.

**Odds API**
- Module: `odds_api.py`
- Call site: `odds_api.py:47-67`
- Telemetry: `odds_api.py:61-63` → `mark_integration_used("odds_api")`
- Caching: none in module

**Playbook API**
- Module: `playbook_api.py`
- Call site: `playbook_api.py:211-224`
- Telemetry: `playbook_api.py:220-221`
- Caching: none in module

**BallDontLie API**
- Module: `alt_data_sources/balldontlie.py`
- Cache TTL: `alt_data_sources/balldontlie.py:45-47` (120s)
- Call site: `alt_data_sources/balldontlie.py:101-114`
- Telemetry: `alt_data_sources/balldontlie.py:109-111`

**SerpAPI**
- Module: `alt_data_sources/serpapi.py`
- Cache TTL: `alt_data_sources/serpapi.py:35-38` (90m default or guardrails)
- Quota/guardrails: `alt_data_sources/serpapi.py:20-79`
- Telemetry: `alt_data_sources/serpapi.py:154-157`

**Weather API (context)**
- Module: `alt_data_sources/weather.py`
- Telemetry on successful fetch: `alt_data_sources/weather.py:558-562`

**NOAA (esoteric)**
- Module: `alt_data_sources/noaa.py`
- Telemetry on cache and live fetch: `alt_data_sources/noaa.py:31-63` and `alt_data_sources/noaa.py:113-114`

**Integration contract naming mismatches (drift):**
- `core/integration_contract.py` references files not present in repo:
  - `weather_api.py`, `serpapi.py`, `noaa_api.py`, `twitter_api.py`, `whop_integration.py`, `fred_api.py`, `finnhub_api.py`.
- `rg --files | rg -n "fred_api.py|finnhub_api.py|twitter_api.py|whop_integration.py|noaa_api.py|weather_api.py|serpapi.py"` only returns `alt_data_sources/serpapi.py`.

### D) Tests + Script Gates

- `python3 -m pytest -q` → **494 passed, 42 skipped** (see test run logs).
- `bash scripts/prod_sanity_check.sh` → **skipped** with `SKIP_NETWORK=1` (network-dependent). This is now explicitly supported.
- Guard test for Option A exists and blocks BASE_5/context weighting:
  - `tests/test_option_a_scoring_guard.py:32-122`.

---

## Confirmed Scoring Formula (with Evidence)

**Option A formula (runtime):**
- Base weights: `core/scoring_contract.py:9-14`.
- Base score calc: `live_data_router.py:4506-4512`.
- Context modifier (bounded): `live_data_router.py:4514-4523`.
- Final score (Option A): `live_data_router.py:4567-4576` using `core/scoring_pipeline.py:59-83`.

**Post-base additive terms:**
- `confluence_boost` (includes harmonic boost) → `live_data_router.py:4273-4289` + `live_data_router.py:4567-4576`.
- `msrf_boost` → `live_data_router.py:4291-4319` + `live_data_router.py:4567-4576`.
- `jason_sim_boost` → `live_data_router.py:4526-4568` + `live_data_router.py:4567-4576`.
- `serp_boost` → `live_data_router.py:5059-5063` + `live_data_router.py:4567-4576`.
- **Ensemble adjustment** (+/-0.5): `live_data_router.py:4746-4758`, bounded in `utils/ensemble_adjustment.py:6-22`.

---

## Table — Every Term that Changes `final_score`

| Term | Bound / Cap | Where Set | Exposed in API (debug=1) | Documented | Notes |
|---|---|---|---|---|---|
| `BASE_4` | weights sum 1.00 | `core/scoring_contract.py:9-14`, `live_data_router.py:4506-4512` | `base_4_score` at `live_data_router.py:4931` | `CLAUDE.md:169-171`, `SCORING_LOGIC.md:49-52` | Option A base only |
| `context_modifier` | ±0.35 | `core/scoring_contract.py:16-18`, `live_data_router.py:4514-4523`, clamp in `core/scoring_pipeline.py:48-56` | `context_modifier` + reasons at `live_data_router.py:4928-4931` | `CLAUDE.md:163-171`, `SCORING_LOGIC.md:49-63` | Bounded modifier only |
| `confluence_boost` | cap via `CONFLUENCE_BOOST_CAP` | `core/scoring_contract.py:59`, `live_data_router.py:4240-4272` | `confluence_boost` at `live_data_router.py:4917` | `SCORING_LOGIC.md` | Harmonic folded here |
| `harmonic_boost` | 1.5 | `core/scoring_contract.py:54-55`, `live_data_router.py:4273-4289` | `harmonic_boost` at `live_data_router.py:5048` | `SCORING_LOGIC.md` | Folded into confluence boost |
| `msrf_boost` | ±1.0 | `core/scoring_contract.py:60`, `live_data_router.py:4291-4319` | `msrf_boost`, `msrf_status` at `live_data_router.py:5050-5053` | `SCORING_LOGIC.md` | Separate from confluence |
| `jason_sim_boost` | ±1.5 | `core/scoring_contract.py:62`, `core/scoring_pipeline.py:74-78` | `jason_sim_boost`, `jason_status` at `live_data_router.py:5001-5007` | `SCORING_LOGIC.md` | Can be negative |
| `serp_boost` | ≤ 4.3 | `core/scoring_contract.py:61`, `core/scoring_pipeline.py:74-77` | `serp_boost`, `serp_status` at `live_data_router.py:5059-5063` | `SCORING_LOGIC.md` | Guardrails in `core/serp_guardrails.py` |
| `ensemble_adjustment` | ±0.5 | `utils/ensemble_adjustment.py:6-22`, applied at `live_data_router.py:4746-4758` | **No dedicated field** (only in `ai_reasons`) | `CLAUDE.md` + `SCORING_LOGIC.md` updated | **Visibility gap** |

Terms folded into engine scores (not post-base):
- `glitch_adjustment`, `gematria_boost`, `phase8_boost`, `officials_adjustment`, `park_adjustment` → applied inside esoteric or research components; exposed in breakdown fields at `live_data_router.py:5047-5072`.

---

## Engine Separation & Responsibilities (Evidence)

**AI Engine**
- Runtime scoring uses LSTM (props) or heuristic fallback:
  - `live_data_router.py:3182-3463` (LSTM via `get_lstm_ai_score`, heuristic fallback).
- Ensemble model used for post-base adjustment (not base weight): `live_data_router.py:4722-4758`.

**Research Engine**
- Runtime research scoring (sharp, RLM, public fade, etc.): `live_data_router.py:3464-3650`.
- Separate module exists (`research_engine.py:577-761`) but is not used by the live best-bets path → **drift risk**.

**Esoteric Engine**
- Runtime esoteric calculation + signals: `live_data_router.py:3820-4240`.
- Phase 8 + glitch + gematria are folded into esoteric breakdown and exposed in debug fields (`live_data_router.py:5055-5072`).

**Jarvis Engine**
- Runtime Jarvis scoring and triggers in `live_data_router.py:3820-4240` and `jarvis_savant_engine.py`.

**Context Modifier**
- Context services are sourced from `context_layer.py:1032-1160` (defense/pace/vacuum/park).
- Context modifier computed separately and clamped in `live_data_router.py:4514-4523`.

---

## Endpoint Output Consistency (Best-Bets)

**Required fields present in debug payload:**
- `base_4_score`, `context_modifier`, `confluence_boost`, `msrf_boost`, `jason_sim_boost`, `serp_boost`, `final_score`, statuses/reasons:
  - Fields present in `live_data_router.py:4910-5063`.

**Shape stability for zero-game sports:**
- `scripts/prod_sanity_check.sh` now enforces shape for all sports and MLB empty payload allowed.

**Fail-soft / fail-loud:**
- `integration_registry.get_health_check_loud()` defines loud error behavior: `integration_registry.py:894-940`.

---

## Contract Drift Checks

- `BASE_5`, `ENGINE_WEIGHTS["context"]` appear only in docs/tests:
  - `CLAUDE.md:5525-5526`, `tests/test_option_a_scoring_guard.py:83`, `scripts/option_a_drift_scan.sh:14-16`.
- No runtime matches for context-weighted engine usage.

---

## Prioritized Bug List

### 1) **Hidden additive term: `ensemble_adjustment` not exposed as a field** (Severity: HIGH)
- **Evidence:** applied after final score at `live_data_router.py:4746-4758` and bounded in `utils/ensemble_adjustment.py:6-22`.
- **Impact:** violates requirement that every term affecting `final_score` is visible in debug payload and math check formula.
- **Fix suggestion:** add `ensemble_adjustment` (or `ensemble_delta`) to pick payload and scoring breakdown; include in debug math check.

### 2) **Integration contract owner_modules mismatch / missing files** (Severity: MEDIUM)
- **Evidence:** `core/integration_contract.py:56-185` references `weather_api.py`, `serpapi.py`, `noaa_api.py`, `twitter_api.py`, `whop_integration.py`, `fred_api.py`, `finnhub_api.py` but repo only contains `alt_data_sources/serpapi.py` for those names.
- **Impact:** audit tooling and doc generation may point to non-existent modules; drift risk for telemetry/audit.
- **Fix suggestion:** update `owner_modules` to actual file paths (e.g., `alt_data_sources/weather.py`, `alt_data_sources/serpapi.py`, `alt_data_sources/noaa.py`).

### 3) **Hardcoded production API key in prod sanity script** (Severity: LOW)
- **Evidence:** `scripts/prod_sanity_check.sh` sets default `API_KEY` in file header (now bypassable with `SKIP_NETWORK=1`).
- **Impact:** risk of accidental disclosure or use in logs.
- **Fix suggestion:** remove hardcoded key and require `API_KEY` env var for network checks.

---

## Claude Handoff (Minimal Changes Needed)

1) **Expose `ensemble_adjustment` in debug pick payload**
   - Add field next to other boost fields in the pick payload and scoring_breakdown.
   - Include in “math sum check” (debug) and docs.

2) **Fix integration contract module paths**
   - Update `core/integration_contract.py` `owner_modules` to actual filenames (e.g., `alt_data_sources/weather.py`, `alt_data_sources/noaa.py`, `alt_data_sources/serpapi.py`).

3) **Remove hardcoded API key from `scripts/prod_sanity_check.sh`**
   - Require `API_KEY` env var or `SKIP_NETWORK=1` for local runs.

---

## Changes Made During Audit (Docs + Scripts)

- `SCORING_LOGIC.md`: updated formula to include `ensemble_adjustment` and documented its behavior.
- `CLAUDE.md`: updated formula lines and added ensemble adjustment note.
- `scripts/prod_sanity_check.sh`: added `SKIP_NETWORK=1` early exit for local/offline audit.

---

## Commands Run

- Static scan: `rg -n "BASE_4|BASE_5|final_score\s*=|compute_final_score|context_modifier|CONTEXT_MODIFIER_CAP|ENGINE_WEIGHTS|context_weight|\+\s*0\.5|\-\s*0\.5|min\(10|max\(0|ensemble|pillars|harmonic|gematria|glitch_adjustment" .`
- Tests: `python3 -m pytest -q` (494 passed, 42 skipped)
- Sanity script (offline): `SKIP_NETWORK=1 bash scripts/prod_sanity_check.sh`
- Audit drift scan: `bash scripts/audit_drift_scan.sh` (set `SKIP_NETWORK=1` to skip payload checks)

## CI Wiring

The audit drift scan is wired into `scripts/ci_sanity_check.sh` as a pre-flight gate.
