# Learning Audit Report — auto_grader + trap_learning_loop + grader_store + persistence

Date: 2026-02-03

## Executive Summary (Pass/Fail)

1) **Storage + Persistence (Railway volume)**: **PARTIAL PASS**
- Predictions JSONL: **PASS** (grader_store uses `storage_paths.get_predictions_file()` under `RAILWAY_VOLUME_MOUNT_PATH`).
- Learned weights: **PASS** (auto_grader writes `weights.json` under `GRADER_DATA_DIR`, now aligned with `storage_paths.get_weights_file()` at `${RAILWAY_VOLUME_MOUNT_PATH}/grader_data/weights.json`).
- **Drift note**: trap_learning_loop writes additional JSONL files under `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning/`, which violates the “exactly two storage products” requirement if interpreted strictly.

2) **Data contract / training example**: **PARTIAL PASS**
- Training example = grader_store pick → `PredictionRecord` in auto_grader; labels from graded outcomes.
- No explicit filter in grader_store for `final_score >= 6.5`, but **AutoGrader now filters** below `MIN_FINAL_SCORE` on load.
- Dedup by `pick_id` now enforced on load.

3) **Isolation from runtime scoring**: **PASS**
- Runtime scoring only logs picks and persists; no weight updates during request path.

4) **Observability**: **PARTIAL PASS**
- `/grader/status` and `/debug/learning/latest` expose key stats.
- **Missing**: weight version hash and explicit “dropped samples + reasons” in learning endpoints.

5) **Trap Learning Loop reconciliation**: **PARTIAL PASS**
- Uses separate JSONL files with file locking.
- **Append-only guarantee** for grader_store is violated by `mark_graded()` rewriting the predictions file.

---

## Evidence — Storage & Persistence

### Canonical paths
- Predictions JSONL path from storage contract:
  - `storage_paths.get_predictions_file()` → `${RAILWAY_VOLUME_MOUNT_PATH}/grader/predictions.jsonl` (`storage_paths.py:135-137`).
- Weights JSON path from storage contract:
  - `storage_paths.get_weights_file()` → `${RAILWAY_VOLUME_MOUNT_PATH}/grader_data/weights.json` (`storage_paths.py:140-144`).
- AutoGrader uses `data_dir.GRADER_DATA` for weights:
  - `auto_grader.py:188-202` (load), `auto_grader.py:335-365` (save).
- Trap Learning Loop storage:
  - `trap_learning_loop.py:198-209` (uses `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning`).

### Predictions persistence
- Write path: `grader_store.persist_pick()` → `PREDICTIONS_FILE` (`grader_store.py:89-132`).
- Dedup: in-memory set + pick_id hash (`grader_store.py:101-123`).
- Read path: `grader_store.load_predictions()` (`grader_store.py:158-223`).

### Weights persistence (atomic)
- AutoGrader weights written via temp+rename + lock:
  - `auto_grader.py:352-363`.

### Storage health endpoint
- `/internal/storage/health` uses `storage_paths.get_storage_health()` with predictions + weights paths (`storage_paths.py:152-236`).

---

## Data Contract — Training Example & Labels

**Training example source**
- grader_store pick → `PredictionRecord` in AutoGrader
  - `auto_grader._convert_pick_to_record()` (`auto_grader.py:252-330`).
- Predicted value = `final_score` from pick (`auto_grader.py:270-272`).
- Labels from graded outcomes:
  - `grade_status == "GRADED"` → `result` → `hit` and `error` (`auto_grader.py:278-285`).

**Filtering + dedup**
- AutoGrader filters out picks with `final_score < MIN_FINAL_SCORE` when loading predictions (`auto_grader.py:219-240`).
- Dedup by `pick_id` enforced in the same load step (`auto_grader.py:237-240`).

**Leakage controls**
- `calculate_bias()` only uses records with `actual_value` set (graded) and within `days_back` window (`auto_grader.py:527-541`).
- Timestamp parsing uses persisted timestamps (`auto_grader.py:301-302`).

---

## Isolation from Runtime Scoring

- Runtime scoring only logs and persists picks; no weight updates or training calls in request path.
  - AutoGrader logging only: `live_data_router.py:6580-6645`.
  - Persistence only: `live_data_router.py:6650-6680`.
- Adjustments are exposed as explicit endpoints, not invoked during scoring:
  - `/grader/adjust-weights/{sport}` and audit endpoints (`live_data_router.py:8833-8842`, `live_data_router.py:8749-8777`).

---

## Observability & Debug Endpoints

**Learning status**
- `/debug/learning/latest` shows esoteric learning + auto_grader stats (`live_data_router.py:7917-7988`).
- `/grader/status` shows grader_store reconciliation + weight learning status (`live_data_router.py:8127-8241`).

**Persistence visibility**
- `grader_store.get_storage_stats()` provides counts + file sizes (`grader_store.py:338-396`).
- `grader_store.load_predictions_with_reconciliation()` provides reconciliation + skip reasons (`grader_store.py:226-335`).

**Missing**
- No weight version hash or file timestamp surfaced in learning endpoints (only file mtime on grader_store predictions). Weight file timestamp exists in `storage_paths.get_storage_health()` but not surfaced in `/grader/status`.

---

## Call-Chain Diagram (Text)

**Best-bets → persistence → learning**
1) `/live/best-bets/{sport}` computes picks → filters → persists
   - `live_data_router.py:6650-6680` → `grader_store.persist_pick()`.
2) `grader_store` appends JSONL (`grader_store.py:124-132`).
3) AutoGrader loads from grader_store on startup (`auto_grader.py:205-248`).
4) Scheduled job runs grading / weight updates via AutoGrader endpoints (see `/grader/run-audit`, `/grader/adjust-weights/{sport}` in `live_data_router.py:8749-8842`).
5) Weights saved atomically (`auto_grader.py:352-363`).

**Trap learning loop**
- `trap_router.py` endpoints access `TrapLearningLoop` (`trap_router.py:162-377`).
- TrapLearningLoop stores its own JSONL files (`trap_learning_loop.py:198-209`, `trap_learning_loop.py:789-817`).

---

## Table — Files Written, Paths, Atomicity

| File | Purpose | Writer | Path | Atomicity / Lock |
|---|---|---|---|---|
| `predictions.jsonl` | Picks stream | `grader_store.persist_pick()` | `${RAILWAY_VOLUME_MOUNT_PATH}/grader/predictions.jsonl` | Append with file lock (`grader_store.py:124-130`) |
| `weights.json` | Learned weights | `AutoGrader._save_state()` | `${RAILWAY_VOLUME_MOUNT_PATH}/grader_data/weights.json` | Temp + `os.replace` + lock (`auto_grader.py:352-363`) |
| `traps.jsonl` | Trap definitions | `TrapLearningLoop._save_traps()` | `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning/traps.jsonl` | Overwrite + lock (`trap_learning_loop.py:789-796`) |
| `evaluations.jsonl` | Trap eval history | `TrapLearningLoop._save_evaluations()` | `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning/evaluations.jsonl` | Append + lock (`trap_learning_loop.py:797-807`) |
| `adjustments.jsonl` | Trap adjustment log | `TrapLearningLoop._save_adjustments()` | `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning/adjustments.jsonl` | Append + lock (`trap_learning_loop.py:808-817`) |

**Non-append behavior (issue):** `grader_store.mark_graded()` rewrites the entire predictions file (not append-only) (`grader_store.py:399-447`).

---

## Prioritized Bug List

### 1) **Append-only requirement violated by `mark_graded()`** (Severity: HIGH)
- **Evidence:** `grader_store.mark_graded()` reads the entire JSONL and rewrites it (`grader_store.py:399-447`).
- **Impact:** Violates append-only invariant, risk of corruption on crash during rewrite.
- **Fix suggestion:** Append a grade record (immutable) or write to a separate graded log; reconcile on read.

### 2) **Learning storage count exceeds “two products” requirement** (Severity: MEDIUM)
- **Evidence:** trap_learning_loop writes 3 JSONL files under `${RAILWAY_VOLUME_MOUNT_PATH}/trap_learning` (`trap_learning_loop.py:198-209`).
- **Impact:** Conflicts with “exactly two storage products” requirement. Clarify or update requirement.

### 3) **No explicit training drop telemetry** (Severity: LOW)
- **Evidence:** Filters/dedup occur on load (`auto_grader.py:219-240`) but counts are not exposed in `/grader/status` or `/debug/learning/latest`.
- **Impact:** Reduced observability of training data quality.

---

## Tests Added / Updated

- `tests/test_learning_system_audit.py`
  - weights file path under mount
  - predictions append-only
  - training ignores picks < 6.5
  - training dedup by `pick_id`
  - weights load safe if missing
  - scoring path does not adjust weights

---

## New Local Script

- `scripts/learning_sanity_check.sh`
  - Validates predictions/weights file paths under volume
  - Validates readable JSON
  - Supports `ALLOW_EMPTY=1` for local/dev

---

## Commands Run

- `python3 -m pytest -q`
- `ALLOW_EMPTY=1 bash scripts/learning_sanity_check.sh`
- `bash scripts/docs_contract_scan.sh`
- `bash scripts/env_drift_scan.sh`
- **Not run in this audit session:** `scripts/endpoint_matrix_sanity.sh`, `scripts/api_proof_check.sh`, `scripts/learning_loop_sanity.sh`

---

## Env/Registry Drift (New)

**Purpose:** Ensure every env var used in code is listed in `docs/AUDIT_MAP.md` and/or `integration_registry.py`, and that docs do not list unused env vars without a `deprecated` marker.

**Script:** `scripts/env_drift_scan.sh`

**Notes:**
- This scan is strict and will currently fail for env vars used outside the integration registry (e.g., `API_AUTH_KEY`, `ENABLE_DEMO`, `PORT`, etc.) unless they are added to the canonical documentation or explicitly marked deprecated.
- The audit script prints **missing** and **unused** env vars with a fail-fast exit code.

---

## Docs Contract Drift (New)

**Purpose:** Validate that key docs agree with the scoring contract (Option A), caps, and additive terms.

**Script:** `scripts/docs_contract_scan.sh`

**Checks:**
- Rejects **BASE_5** or any context-weighted wording.
- Verifies Option A weights and context cap match `core/scoring_contract.py`.
- Confirms additive terms are documented (`base_4`, `context_modifier`, `confluence_boost`, `msrf_boost`, `jason_sim_boost`, `serp_boost`, `ensemble_adjustment`).

---

## Endpoint Contract Manifest (New)

**Document:** `docs/ENDPOINT_CONTRACT.md`

**Scope:** best-bets, props, live betting endpoints + shared pick field contract.

**Fail-fast script:** `scripts/endpoint_matrix_sanity.sh`
- Hits prod endpoints across `NBA/NFL/NHL/MLB/NCAAB`
- Asserts 200 or structured error code
- Validates required pick fields when picks exist
- Checks context cap and final_score math (with cap)

---

## Learning Loop Persistence (New)

**Script:** `scripts/learning_loop_sanity.sh`

**Checks:**
- Predictions + weights under `RAILWAY_VOLUME_MOUNT_PATH`
- Predictions JSON readable
- No picks stored with `final_score < MIN_FINAL_SCORE`
- Prints file counts + mtime for quick operator visibility

---

## API Proof Checks (New)

**Script:** `scripts/api_proof_check.sh`

**Checks:**
- `/live/debug/integrations` shows **VALIDATED** for: `balldontlie`, `odds_api`, `playbook_api`, `serpapi`, `railway_storage`
- Debug pick payloads include status fields: `serp_status`, `msrf_status`, `jason_status`


---

## Live Betting Audit

### Endpoint inventory (paths → handler)
- `/live/in-play/{sport}` → `get_live_bets()` (`live_data_router.py:6999-7057`)
- `/in-game/{sport}` → `get_in_game_picks()` (`live_data_router.py:7064-7100`)

### Supported sports and detection
- Live endpoints accept any sport in `SPORT_MAPPINGS` (`live_data_router.py:7010-7012`, `live_data_router.py:7084-7087`).
- Live candidates are filtered by `game_status` from best-bets output:
  - `LIVE` or `MISSED_START` for in-game/live mode (`live_data_router.py:6690-6699`, `live_data_router.py:7091-7099`).
- In-game trigger windows for NBA are derived from BallDontLie live context:
  - `alt_data_sources/balldontlie.py:141-216` (`period`, `minutes_remaining`, `trigger_window`).

### LB-1 Scoring contract parity
**Evidence:**
- Live endpoints call `get_best_bets()` and then filter picks; no shadow scoring formula:
  - `/live/in-play/{sport}`: `best_bets_response = await get_best_bets(sport)` (`live_data_router.py:7015-7016`).
  - `/in-game/{sport}`: `best_bets_result = await get_best_bets(sport)` (`live_data_router.py:7088-7090`).
- Option A scoring is the only scoring path in best-bets (see main audit above).

**Live-only adjustment (explicit + bounded):**
- Live signals are applied as a bounded modifier to **research_score**:
  - `live_data_router.py:4189-4225` (applies `live_boost` to `research_score`, cap in `alt_data_sources/live_signals.py:28-31`).
- Live adjustment is surfaced as explicit fields:
  - `live_adjustment`, `live_reasons` in payload (`live_data_router.py:4928-4934`).
  - `scoring_breakdown.live_adjustment` (`live_data_router.py:4941-4946`).

### LB-2 Odds freshness + staleness handling
**Finding:** No explicit odds timestamp or staleness gate exists in live endpoints.
- Live endpoints reuse best-bets picks (same odds sources) with no odds_age/odds_timestamp fields exposed.
- No stale-odds fallback logic found in `live_data_router.py` or `odds_api.py`.

**Bug:** missing stale-odds guard and `odds_age_seconds` telemetry (see Bug List).

### LB-3 Market integrity rules
**Evidence:**
- Live filtering uses `game_status` only; no explicit market suspended status or live market validation fields exist in payload.
- `live_data_router.py:7091-7099` (filters by `game_status == "MISSED_START"`).

**Bug:** missing market suspended detection + explicit reasons (see Bug List).

### LB-4 Latency + fail-soft behavior
**Evidence:**
- Live endpoints are simple filters over best-bets output; failures in dependencies (Odds API, BallDontLie) fail-soft via best-bets error handling.
- `get_best_bets()` already fail-softs with `BEST_BETS_FAILED` error payloads (see prior audit).

### LB-5 Observability
**Present:**
- Live signals reasons are added to `research_reasons`, now also surfaced explicitly via `live_adjustment` / `live_reasons`.

**Missing:**
- `odds_source`, `odds_timestamp`, `odds_age_seconds`, `staleness_status`, and in-play state snapshot fields are **not** present.

### Live Betting Bug List (Prioritized)

1) **Missing odds staleness guard + telemetry** (Severity: HIGH)
- No `odds_timestamp` or `odds_age_seconds` in live responses; no stale-odds fail-soft behavior.
- Fix suggestion: include `fetched_at` from odds source, compute age, and skip live enhancements if stale.

2) **Missing market suspended/availability checks** (Severity: MEDIUM)
- No explicit `market_status` or `suspended` check for live markets in response shaping.
- Fix suggestion: add `market_status` from odds feed and skip picks when suspended.

3) **No live-specific in-play snapshot in payload** (Severity: LOW)
- No `period`, `clock`, `score_snapshot` fields exposed with live picks.
- Fix suggestion: surface in-play state for observability (from BallDontLie where available).

### Live Betting Tests + Script
- Unit tests for live signal caps: `tests/test_live_signals.py`.
- Local script: `scripts/live_sanity_check.sh` (supports `SKIP_NETWORK=1`).
