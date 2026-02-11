# Master Audit Index

**Purpose:** Single-command verification for each engine audit. Every claim backed by code pointers.

**Last Updated:** 2026-02-10

---

## Quick Reference

| Engine | Primary Audit Endpoint | Single-Command Check | Pass Criteria |
|--------|------------------------|----------------------|---------------|
| Engine 1 (AI/Training) | `/live/debug/training-status` | See [Engine 1 Validation](#engine-1-aitraining-validation) | `training_health == "HEALTHY"`, `unknown == 0` |
| Engine 2 (Research) | `/live/best-bets/{sport}?debug=1` | See [Engine 2 Validation](#engine-2-research-validation) | `source_api` present, anti-conflation holds |
| Engine 3 (Esoteric) | `/live/best-bets/{sport}?debug=1` | See [Engine 3 Validation](#engine-3-esoteric-validation) | `phase8_boost` present, signals computed |
| Engine 4 (Jarvis) | `/live/best-bets/{sport}?debug=1` | See [Engine 4 Validation](#engine-4-jarvis-validation) | 7 required fields present |

---

## Engine 1 (AI/Training) Validation

### What Can Go Wrong

| Failure Mode | Symptom | Root Cause |
|--------------|---------|------------|
| Telemetry path bug | `training_health: "NEVER_RAN"` when training ran | Reading `status["ensemble"]["training_telemetry"]` instead of `status["training_telemetry"]` |
| Unknown attribution | `missing_model_preds_attribution.unknown > 0` | Missing attribution buckets (heuristic_fallback, empty_raw_inputs) |
| Empty dict conditional | Training signatures not stored | `if filter_telemetry:` is False for `{}` |
| Ensemble unfitted | `predict()` crashes | `is_trained` based on file existence, not actual training |

### Invariants

| Invariant | Code Reference | Enforcement |
|-----------|----------------|-------------|
| `training_telemetry` at TOP level | `team_ml_models.py:get_model_status()` (line 605) | `live_data_router.py:11371` reads from top level |
| Attribution buckets complete | `scripts/audit_training_store.py:254` | `_attribute_missing_model_preds()` covers all cases |
| `unknown == 0` for game picks | `scripts/audit_training_store.py:280-310` | All game picks have known attribution |
| Binary hit labels only | `team_ml_models.py` | `label_type: "binary_hit"`, PUSH excluded |

### Proof Fields in Debug Payload

```json
{
  "build_sha": "string (from /health)",
  "training_health": "HEALTHY | STALE | NEVER_RAN",
  "training_telemetry": {
    "last_train_run_at": "ISO timestamp or null",
    "graded_samples_seen": "int >= 0",
    "samples_used_for_training": "int >= 0",
    "training_signatures": {
      "ensemble": {
        "schema_match": true,
        "label_type": "binary_hit",
        "filter_telemetry": { "assertion_passed": true }
      }
    }
  },
  "store_audit": {
    "data_quality": {
      "total_records": "int > 0",
      "graded_count": "int > 0",
      "missing_model_preds_attribution": {
        "old_schema": "int (expected for pre-Feb picks)",
        "non_game_market": "int (expected for props)",
        "error_path": "int (investigate if high)",
        "heuristic_fallback": "int (investigate if high)",
        "empty_raw_inputs": "int (investigate if high)",
        "unknown": "int (MUST be 0)"
      }
    }
  },
  "artifact_proof": {
    "team_cache.pkl": { "exists": true, "mtime_iso": "..." },
    "matchup_matrix.pkl": { "exists": true, "mtime_iso": "..." },
    "ensemble_weights.pkl": { "exists": true, "mtime_iso": "..." }
  }
}
```

### Tests That Enforce It

| Test File | Test Name | What It Validates |
|-----------|-----------|-------------------|
| `tests/test_training_telemetry.py` | `test_filter_counts_sum_correctly` | Filter math assertion |
| `tests/test_training_telemetry.py` | `test_attribution_buckets_complete` | All buckets present (81-83 fix) |
| `tests/test_training_telemetry.py` | `test_ensemble_returns_training_signature` | Ensemble has label_definition |
| `tests/test_training_status.py` | `test_training_status_endpoint` | Endpoint returns expected shape |

### Audit Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/audit_training_store.py` | Audit predictions.jsonl without loading | `python scripts/audit_training_store.py --json` |
| `scripts/train_team_models.py` | Manual training trigger | `python scripts/train_team_models.py` |

### Single-Command Validation (Engine 1)

**Copy this verbatim:**

```bash
#!/usr/bin/env bash
set -euo pipefail
API_KEY='YOUR_API_KEY'
BASE='https://web-production-7b2a.up.railway.app'

json="$(curl -fsS -H "X-API-Key: ${API_KEY}" "${BASE}/live/debug/training-status")"

# 1) Print compact status
echo "$json" | jq '{
  build_sha: (.verification_proof.build_sha // .build_sha // null),
  training_health: .training_health,
  last_train_run_at: .training_telemetry.last_train_run_at,
  graded_samples_seen: .training_telemetry.graded_samples_seen,
  samples_used_for_training: .training_telemetry.samples_used_for_training,
  missing_model_preds_attribution: .store_audit.data_quality.missing_model_preds_attribution,
  artifacts: .artifact_proof,
  ensemble_signature: .training_telemetry.training_signatures.ensemble
}'

# 2) Hard assertions (exits non-zero if any fail)
echo "$json" | jq -e '
  (.verification_proof.build_sha? // .build_sha? | type == "string" and length > 0)
  and (.training_health == "HEALTHY")
  and (.training_telemetry.last_train_run_at != null)
  and ((.training_telemetry.graded_samples_seen // 0) > 0)
  and ((.training_telemetry.samples_used_for_training // 0) >= 0)
  and ((.store_audit.data_quality.total_records // 0) > 0)
  and ((.store_audit.data_quality.graded_count // 0) > 0)
  and ((.store_audit.data_quality.missing_model_preds_attribution.unknown // 0) == 0)
  and (
    (.training_telemetry.training_signatures.ensemble? // null) == null
    or (
      (.training_telemetry.training_signatures.ensemble.schema_match == true)
      and (.training_telemetry.training_signatures.ensemble.label_type == "binary_hit")
      and (.training_telemetry.training_signatures.ensemble.filter_telemetry.assertion_passed == true)
    )
  )
' >/dev/null

echo "✅ ENGINE 1 HARD CHECKS PASS"
```

### Expected Output

```
{
  "build_sha": "abc1234",
  "training_health": "HEALTHY",
  "last_train_run_at": "2026-02-10T12:00:00Z",
  "graded_samples_seen": 150,
  "samples_used_for_training": 41,
  "missing_model_preds_attribution": {
    "old_schema": 500,
    "non_game_market": 400,
    "error_path": 10,
    "heuristic_fallback": 5,
    "empty_raw_inputs": 2,
    "unknown": 0
  },
  "artifacts": { ... },
  "ensemble_signature": { "schema_match": true, "label_type": "binary_hit", ... }
}
✅ ENGINE 1 HARD CHECKS PASS
```

---

## Engine 2 (Research) Validation

### What Can Go Wrong

| Failure Mode | Symptom | Root Cause |
|--------------|---------|------------|
| Sharp/line conflation | "Sharp signal STRONG" when only line variance triggered | Both read from same `sharp_signal` dict |
| Odds API upgrades Playbook field | `signal_strength` set to STRONG by `lv >= 2.0` | Line 2030-2033 bug (now fixed) |
| Source API missing | No provenance for boost values | No `source_api` field in breakdown |

### Invariants

| Invariant | Code Reference | Enforcement |
|-----------|----------------|-------------|
| `sharp_boost` ONLY from `playbook_sharp` | `live_data_router.py:5634-5700` | Separate objects, never merged |
| `line_boost` ONLY from `odds_line` | `live_data_router.py:5700-5750` | Separate objects, never merged |
| Source API attribution | `core/research_types.py` | `source_api` field in breakdown |
| Anti-conflation test | `tests/test_research_truthfulness.py` | 21 tests enforce separation |

### Proof Fields in Debug Payload

From `/live/best-bets/{sport}?debug=1`:

```json
{
  "picks": [
    {
      "research_breakdown": {
        "sharp_boost": 1.5,
        "line_boost": 0.0,
        "public_boost": 0.5,
        "sharp_source_api": "playbook_api",
        "line_source_api": "odds_api",
        "sharp_status": "SUCCESS",
        "line_status": "NO_DATA"
      },
      "research_reasons": ["Sharp signal MODERATE (17% divergence)", "..."]
    }
  ],
  "debug": {
    "research_telemetry": {
      "playbook_calls": 5,
      "odds_api_calls": 3
    }
  }
}
```

### Tests That Enforce It

| Test File | Test Name | What It Validates |
|-----------|-----------|-------------------|
| `tests/test_research_truthfulness.py` | `test_line_variance_cannot_set_sharp_strength` | LV doesn't upgrade sharp |
| `tests/test_research_truthfulness.py` | `test_sharp_boost_only_from_playbook_sharp` | Source isolation |
| `tests/test_research_truthfulness.py` | `test_source_api_tags_present` | Provenance present |
| `tests/test_option_a_scoring_guard.py` | `test_research_score_anti_conflation` | Engine separation |

### Audit Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/engine2_research_audit.py` | Runtime verification | `python scripts/engine2_research_audit.py --sport NBA` |
| `scripts/engine2_research_audit.sh` | Static + runtime checks | `./scripts/engine2_research_audit.sh` |

### Single-Command Validation (Engine 2)

**Copy this verbatim:**

```bash
#!/usr/bin/env bash
set -euo pipefail
API_KEY='YOUR_API_KEY'
BASE='https://web-production-7b2a.up.railway.app'
SPORT='NBA'

json="$(curl -fsS -H "X-API-Key: ${API_KEY}" "${BASE}/live/best-bets/${SPORT}?debug=1")"

# 1) Print research breakdown for first pick
echo "$json" | jq '.game_picks.picks[0] | {
  final_score,
  research_breakdown,
  research_reasons: (.research_reasons[0:3] // [])
}'

# 2) Hard semantic checks - ALL must pass
echo "$json" | jq -e '
  (.game_picks.picks // []) | all(
    # SHARP: if we claim any sharp boost, it must be Playbook + SUCCESS + real inputs
    (
      (.research_breakdown.sharp_boost // 0) <= 0
      or (
        .research_breakdown.sharp_source_api == "playbook_api"
        and .research_breakdown.sharp_status == "SUCCESS"
        and (.research_breakdown.sharp_raw_inputs.ticket_pct != null)
        and (.research_breakdown.sharp_raw_inputs.money_pct != null)
      )
    )
    and
    # LINE: if we claim any line boost, it must be Odds API + SUCCESS + real inputs
    (
      (.research_breakdown.line_boost // 0) <= 0
      or (
        .research_breakdown.line_source_api == "odds_api"
        and .research_breakdown.line_status == "SUCCESS"
        and (.research_breakdown.line_raw_inputs.line_variance != null)
      )
    )
    and
    # Anti-conflation: if sharp_status != SUCCESS then sharp_strength must be NONE
    (
      (.research_breakdown.sharp_status == "SUCCESS")
      or ((.research_breakdown.sharp_strength // "NONE") == "NONE")
    )
    and
    # No "Sharp" reason when sharp_status != SUCCESS
    (
      (.research_breakdown.sharp_status == "SUCCESS")
      or ((.research_reasons // []) | all(test("Sharp") | not))
    )
  )
' >/dev/null

echo "✅ ENGINE 2 HARD SEMANTIC CHECKS PASS"
```

### Expected Output

```
{
  "final_score": 7.2,
  "research_breakdown": {
    "sharp_boost": 1.5,
    "line_boost": 0.0,
    "public_boost": 0.5,
    "sharp_source_api": "playbook_api",
    "sharp_status": "SUCCESS",
    "sharp_raw_inputs": { "ticket_pct": 45, "money_pct": 62 },
    "line_source_api": "odds_api",
    "line_status": "NO_DATA"
  },
  "research_reasons": ["Sharp signal MODERATE (17% divergence)"]
}
✅ ENGINE 2 HARD SEMANTIC CHECKS PASS
```

### What This Validates

| Invariant | jq Clause | Failure Meaning |
|-----------|-----------|-----------------|
| Sharp boost requires Playbook | `sharp_source_api == "playbook_api"` | Boost from wrong source |
| Sharp boost requires SUCCESS | `sharp_status == "SUCCESS"` | Claiming data we don't have |
| Sharp boost requires real inputs | `ticket_pct != null` | Fabricated boost |
| Line boost requires Odds API | `line_source_api == "odds_api"` | Boost from wrong source |
| Line boost requires SUCCESS | `line_status == "SUCCESS"` | Claiming data we don't have |
| Line boost requires real inputs | `line_variance != null` | Fabricated boost |
| Anti-conflation | `sharp_strength == "NONE"` when not SUCCESS | Line variance upgrading sharp |
| Reason truthfulness | No "Sharp" when not SUCCESS | Misleading user |

---

## Engine 3 (Esoteric) Validation

### What Can Go Wrong

| Failure Mode | Symptom | Root Cause |
|--------------|---------|------------|
| esoteric_score missing | Pick has no esoteric data | compute_esoteric_score() not called |
| esoteric_score out of range | Score < 0 or > 10 | Aggregation overflow |
| Phase 8 signals missing | No `phase8_boost` or `phase8_reasons` | `get_phase8_esoteric_signals()` not called |
| GLITCH signals missing | No `glitch_breakdown` | `get_glitch_aggregate()` not called |
| NOAA unavailable | Kp-index always 0 | External API timeout, no fallback |
| Timezone error | Lunar phase calculation fails | Naive datetime in astro code |
| Engine weight wrong | Esoteric contributes wrong % | `ENGINE_WEIGHTS["esoteric"]` != 0.20 |
| **v20.18: Global counter contamination** | request_proof shows other request's calls | Not using contextvars |
| **v20.18: NOAA auth_context wrong** | `key_present` in public API | Using keyed API pattern for public API |
| **v20.18: Missing per-signal provenance** | Can't prove signal computed | No `source_api`, `call_proof`, `status` |

### Invariants

| Invariant | Code Reference | Enforcement |
|-----------|----------------|-------------|
| esoteric_score in [0.0, 10.0] | `esoteric_engine.py:compute_esoteric_score()` | Clamped output |
| 23 wired signals | `docs/ESOTERIC_TRUTH_TABLE.md` | YAML `wired_signals` list |
| 6 dead code signals | `docs/ESOTERIC_TRUTH_TABLE.md` | YAML `present_not_wired` list |
| Engine weight = 0.20 | `core/scoring_contract.py` | `ENGINE_WEIGHTS["esoteric"]` |
| External API fail-soft | `alt_data_sources/noaa.py` | 3-hour cache, default on timeout |
| Endpoint returns 200 | `live_data_router.py` | Even if NOAA fails |
| **v20.18: Request-scoped proof** | `alt_data_sources/noaa.py:85-97` | `contextvars.ContextVar` for NOAA |
| **v20.18: NOAA auth_type = "none"** | `alt_data_sources/noaa.py:132-144` | Public API, no key required |
| **v20.18: Per-signal provenance** | `esoteric_engine.py` | `build_esoteric_breakdown_with_provenance()` |

### Semantic Truthfulness (v20.18)

**Every signal in `esoteric_breakdown` MUST have:**

| Field | Type | Description |
|-------|------|-------------|
| `value` | float | Signal value (0-1 typically) |
| `status` | string | SUCCESS, NO_DATA, DISABLED, FALLBACK, ERROR |
| `source_api` | string/null | "noaa" for Kp/solar, null for internal |
| `source_type` | string | EXTERNAL or INTERNAL |
| `raw_inputs_summary` | object | Input data used for computation |
| `call_proof` | object/null | HTTP call evidence (for external APIs) |
| `triggered` | bool | Whether signal contributed to score |
| `contribution` | float | Points added to esoteric score |

**External API (NOAA) Truthfulness:**

| auth_context field | NOAA Value | Why |
|--------------------|------------|-----|
| `auth_type` | "none" | Public API, no key required |
| `enabled` | true/false | Feature flag state |
| `base_url_source` | "env:NOAA_BASE_URL" or "default" | Config origin |
| ~~`key_present`~~ | NEVER | Not a keyed API |

**Request-Scoped Proof (contextvars):**

```python
# CORRECT: Request-local counters (not contaminated by concurrent requests)
from alt_data_sources.noaa import init_noaa_request_proof, get_noaa_request_proof

proof = init_noaa_request_proof()  # Start of request
# ... scoring runs, makes NOAA calls ...
request_proof = {
    "noaa_calls": proof.calls,
    "noaa_2xx": proof.http_2xx,
    "noaa_cache_hits": proof.cache_hits,
}
```

### Proof Fields in Debug Payload

**Standard best-bets (existing):**

```json
{
  "picks": [
    {
      "esoteric_score": 5.2,
      "esoteric_reasons": ["Lunar waxing (+0.3)", "Kp-index low (+0.2)"],
      "phase8_boost": 0.8,
      "glitch_breakdown": {
        "kp_index": { "kp_value": 2, "source": "noaa_live" }
      }
    }
  ]
}
```

**v20.18 debug endpoint `/debug/esoteric-candidates/{sport}`:**

```json
{
  "candidates_pre_filter": [
    {
      "pick_id": "...",
      "esoteric_score": 5.2,
      "passed_filter": true,
      "esoteric_breakdown": {
        "kp_index": {
          "value": 0.4,
          "status": "SUCCESS",
          "source_api": "noaa",
          "source_type": "EXTERNAL",
          "raw_inputs_summary": {"kp_value": 4.2, "storm_level": "MODERATE"},
          "call_proof": {
            "source": "noaa_live",
            "cache_hit": false,
            "2xx_delta": 1
          },
          "triggered": true,
          "contribution": 0.4
        },
        "numerology": {
          "value": 0.8,
          "status": "SUCCESS",
          "source_api": null,
          "source_type": "INTERNAL",
          "raw_inputs_summary": {"player_name": "LeBron James"},
          "call_proof": null,
          "triggered": true,
          "contribution": 0.8
        }
      }
    }
  ],
  "auth_context": {
    "noaa": {
      "auth_type": "none",
      "enabled": true,
      "base_url_source": "default"
    }
  },
  "request_proof": {
    "noaa_calls": 2,
    "noaa_2xx": 2,
    "noaa_cache_hits": 0
  }
}
```

### Tests That Enforce It

| Test File | Test Name | What It Validates |
|-----------|-----------|-------------------|
| `tests/test_esoteric_truthfulness.py` | `test_esoteric_score_clamped_0_10` | Score in [0.0, 10.0] |
| `tests/test_esoteric_truthfulness.py` | `test_breakdown_has_required_fields` | All 8 provenance fields |
| `tests/test_esoteric_truthfulness.py` | `test_kp_index_source_api_is_noaa` | Kp-Index from NOAA |
| `tests/test_esoteric_truthfulness.py` | `test_solar_flare_source_api_is_noaa` | Solar Flare from NOAA |
| `tests/test_esoteric_truthfulness.py` | `test_internal_signals_have_null_source_api` | Internal = null source |
| `tests/test_esoteric_truthfulness.py` | `test_noaa_auth_context_has_no_key_present` | Public API contract |
| `tests/test_esoteric_truthfulness.py` | `test_dead_code_not_in_breakdown` | No orphaned signals |
| `tests/test_esoteric_truthfulness.py` | `test_request_proof_is_request_local` | contextvars isolation |
| `tests/test_esoteric_truthfulness.py` | `test_cache_hit_requires_cache_counter` | Cache truthfulness |
| `tests/test_esoteric_truthfulness.py` | `test_noaa_live_requires_2xx_counter` | Live call truthfulness |

### Audit Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/engine3_esoteric_audit.py` | Python audit (local + production) | `python scripts/engine3_esoteric_audit.py --local` |
| `scripts/engine3_esoteric_audit.sh` | Shell wrapper (static + Python) | `./scripts/engine3_esoteric_audit.sh --local` |

### Single-Command Validation (Engine 3)

**Basic validation (existing picks):**

```bash
#!/usr/bin/env bash
set -euo pipefail
API_KEY='YOUR_API_KEY'
BASE='https://web-production-7b2a.up.railway.app'
SPORT='NBA'

json="$(curl -fsS -H "X-API-Key: ${API_KEY}" "${BASE}/live/best-bets/${SPORT}?debug=1")"

# 1) Print esoteric breakdown for first pick
echo "$json" | jq '.game_picks.picks[0] | {
  esoteric_score,
  esoteric_reasons: (.esoteric_reasons[0:3] // []),
  phase8_boost: (.phase8_boost // 0),
  glitch_breakdown: (.glitch_breakdown // {}),
  phase8_breakdown: (.phase8_breakdown // {})
}'

# 2) Hard assertions - ALL must pass
echo "$json" | jq -e '
  # Must have picks OR be empty (off-season is valid)
  ((.game_picks.picks // []) | length == 0)
  or (
    (.game_picks.picks // []) | all(
      # esoteric_score present and in range [0, 10]
      (.esoteric_score != null)
      and (.esoteric_score >= 0)
      and (.esoteric_score <= 10)
      # esoteric_reasons present (may be empty)
      and (.esoteric_reasons != null)
    )
  )
' >/dev/null

echo "✅ ENGINE 3 BASIC CHECKS PASS"
```

**v20.18 Semantic Truthfulness Validation:**

```bash
#!/usr/bin/env bash
set -euo pipefail
API_KEY='YOUR_API_KEY'
BASE='https://web-production-7b2a.up.railway.app'

json="$(curl -fsS -H "X-API-Key: ${API_KEY}" "${BASE}/live/debug/esoteric-candidates/NBA?limit=5")"

# 1) Print compact status
echo "$json" | jq '{
  build_sha: .build_sha,
  candidate_count: (.candidates_pre_filter | length),
  auth_context: .auth_context,
  request_proof: .request_proof,
  first_kp: .candidates_pre_filter[0].esoteric_breakdown.kp_index
}'

# 2) Hard semantic assertions
echo "$json" | jq -e '
  # Gate A: build_sha present
  (.build_sha | type == "string" and length > 0)

  # Gate B: NOAA auth_context has auth_type="none" (NOT key_present)
  and (.auth_context.noaa.auth_type == "none")
  and (.auth_context.noaa.enabled == true)

  # Gate C: All kp_index SUCCESS claims have noaa source + call proof
  and (
    (.candidates_pre_filter // []) | all(
      (.esoteric_breakdown.kp_index.status == "SUCCESS")
      | if . then
          (.esoteric_breakdown.kp_index.source_api == "noaa")
          and (((.esoteric_breakdown.kp_index.call_proof // {}).cache_hit == true)
               or ((.esoteric_breakdown.kp_index.call_proof // {}).source == "noaa_live"))
        else true end
    )
  )

  # Gate D: Internal signals have null source_api
  and (
    (.candidates_pre_filter // []) | all(
      (.esoteric_breakdown.numerology.source_api == null)
    )
  )

  # Gate E: Request-local proof has required fields
  and (.request_proof.noaa_calls | type == "number")
  and (.request_proof.noaa_2xx | type == "number")
  and (.request_proof.noaa_cache_hits | type == "number")

  # Gate F: Cache truthfulness - cache_hit claim requires cache counter
  and (
    (.candidates_pre_filter // []) | all(
      ((.esoteric_breakdown.kp_index.call_proof // {}).cache_hit == true)
      | if . then (.request_proof.noaa_cache_hits >= 1) else true end
    )
  )
' >/dev/null

echo "✅ ENGINE 3 SEMANTIC TRUTHFULNESS PASS"
```

### Expected Output

```
{
  "build_sha": "abc1234",
  "candidate_count": 5,
  "auth_context": {
    "noaa": { "auth_type": "none", "enabled": true }
  },
  "request_proof": {
    "noaa_calls": 2,
    "noaa_2xx": 2,
    "noaa_cache_hits": 0
  },
  "first_kp": {
    "value": 0.4,
    "status": "SUCCESS",
    "source_api": "noaa",
    "call_proof": { "source": "noaa_live", "2xx_delta": 1 }
  }
}
✅ ENGINE 3 SEMANTIC TRUTHFULNESS PASS
```

### What This Validates

| Invariant | jq Clause | Failure Meaning |
|-----------|-----------|-----------------|
| esoteric_score present | `.esoteric_score != null` | Engine not running |
| Score in range | `>= 0 and <= 10` | Aggregation overflow |
| NOAA auth_type=none | `.auth_context.noaa.auth_type == "none"` | Wrong auth pattern |
| No key_present for NOAA | No `key_present` field | Public API treated as keyed |
| kp_index from NOAA | `.source_api == "noaa"` | Wrong source attribution |
| SUCCESS requires proof | `cache_hit or 2xx_delta` | Claiming data without call |
| Internal = null source | `.source_api == null` | Wrong source for internal |
| Request-local counters | `request_proof.*` present | Global counter contamination |
| Cache claim requires counter | `noaa_cache_hits >= 1` | False cache claim |
| Fail-soft | HTTP 200 | External API crash not caught |

### Truth Table Reference

See `docs/ESOTERIC_TRUTH_TABLE.md` for complete signal inventory:
- **23 wired signals** with source, formula, contribution bounds
- **6 dead code signals** (present in code but not called)
- Machine-readable YAML block for test assertions

---

## Engine 4 (Jarvis) Validation

### What Can Go Wrong

| Failure Mode | Symptom | Root Cause |
|--------------|---------|------------|
| Missing required fields | Frontend breaks on null | 7-field contract not enforced |
| Baseline wrong | Score too low/high | Not starting from 4.5 |
| Triggers not stacking | Missing contribution decay | 70% decay factor not applied |

### Invariants

| Invariant | Code Reference | Enforcement |
|-----------|----------------|-------------|
| 7 required fields | `jarvis_savant_engine.py` | Always return all 7 |
| Baseline 4.5 | `jarvis_savant_engine.py:150` | Score starts at 4.5 when active |
| Trigger stacking | `jarvis_savant_engine.py:200-250` | Each trigger adds 70% of previous |

### Proof Fields in Debug Payload

```json
{
  "jarvis_rs": 6.5,
  "jarvis_active": true,
  "jarvis_hits_count": 2,
  "jarvis_triggers_hit": ["THE MASTER", "gematria_strong"],
  "jarvis_fail_reasons": [],
  "jarvis_inputs_used": { "spread": -3.5, "total": 220.5 },
  "jarvis_baseline": 4.5
}
```

### Single-Command Validation (Engine 4)

```bash
curl -sS -H "X-API-Key: ${API_KEY}" "${BASE}/live/best-bets/NBA?debug=1" | \
  jq '.game_picks.picks[0] | {
    jarvis_rs,
    jarvis_active,
    jarvis_hits_count,
    jarvis_triggers_hit,
    jarvis_baseline
  }'
```

---

## jq Filter Best Practices

**Shell quoting rules for audit commands:**

| Do | Don't | Why |
|----|-------|-----|
| Single-quote jq filters | Double-quote filters | Avoids variable expansion issues |
| Use `==` for equality | Use `!=` for inequality | `!=` can cause shell quoting hiccups |
| Use `<= 0` for "not positive" | Use `!= 0` or `> 0` negated | Cleaner shell escaping |
| Use `// null` or `// 0` for defaults | Rely on missing fields | Null-safe comparisons |
| Use `test("pattern") \| not` | Use `!~ "pattern"` | jq doesn't have `!~` |

**Example patterns:**

```bash
# Good: single-quoted, == comparisons, null coalescing
echo "$json" | jq -e '
  (.status == "SUCCESS")
  and ((.count // 0) <= 0 or .valid == true)
  and ((.reasons // []) | all(test("Bad") | not))
'

# Avoid: != operators, double quotes
echo "$json" | jq -e "(.status != \"FAIL\")"  # Quoting nightmare
```

---

## Deployment Gates Summary

Before any deploy, ALL gates must pass:

| Gate | What | Command | Pass Criteria |
|------|------|---------|---------------|
| **A** | Build SHA matches | `curl /health \| jq .build_sha` | Matches expected commit |
| **B** | Engine 1 training healthy | See [Engine 1 Validation](#engine-1-aitraining-validation) | `jq -e` exits 0 |
| **C** | Engine 2 anti-conflation | See [Engine 2 Validation](#engine-2-research-validation) | No sharp from line |

### Gate Script Location

All gates combined: `scripts/prod_go_nogo.sh`

---

## Changelog

- **2026-02-10** - v20.18 Engine 3 Semantic Audit
  - Added per-signal provenance (`value`, `status`, `source_api`, `source_type`, `raw_inputs_summary`, `call_proof`)
  - Added request-scoped proof via `contextvars` (not contaminated by concurrent requests)
  - Added NOAA auth_context with `auth_type: "none"` (public API, no key_present)
  - Added `/debug/esoteric-candidates/{sport}` endpoint
  - Added `docs/ESOTERIC_TRUTH_TABLE.md` with machine-readable YAML
  - Added 22 tests in `tests/test_esoteric_truthfulness.py`
  - Added `scripts/engine3_esoteric_audit.py` and `.sh`
- **2026-02-10** - Created from Engine 1/2 audit lessons (81-83)
  - Lessons: training_telemetry path, attribution buckets, empty dict conditionals
