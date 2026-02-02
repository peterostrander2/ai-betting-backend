# MASTER INDEX — START HERE

Quick entry points:
- `SESSION_START.md` (new session checklist)
- `docs/RECOVERY.md` (what to do if things break)

**This is the ONLY entry point for any code or documentation change.**

If you are Claude (or any contributor): before touching code or docs, use this file to route yourself to the single canonical source for the change. The goal is **zero drift**.

---

## Non-Negotiable Workflow

1) **Classify the change** using the Decision Tree below
2) **Edit the canonical source** (contract/registry/module) — not random call sites
3) **Run validators + CI sessions** (must pass)
4) **Update dependent docs** (only what the validators require)
5) **Commit code + docs together** (COMMIT_CHECKLIST.md)
6) **Verify production endpoints** (health/integrations/scheduler/storage)

---

## Decision Tree — Where to Look and What to Edit

### A) Scoring / Thresholds / Tier Rules / Confluence (v17.1 - 5 Engines)
**Examples:** engine weights, MIN_FINAL_SCORE, Gold Star gates, Titanium rule, confluence boost values.

**Current Architecture (v17.1):**
- 5 engines: AI (15%), Research (20%), Esoteric (15%), Jarvis (10%), Context (30%)
- Titanium: 3/5 engines >= 8.0
- GOLD_STAR gates: ai>=6.8, research>=5.5, jarvis>=6.5, esoteric>=4.0, context>=4.0
- Harmonic Convergence: +1.5 when Research >= 8.0 AND Esoteric >= 8.0

**Canonical source (edit here only):**
- `core/scoring_contract.py`

**Where implementation lives (should import from contract):**
- `live_data_router.py` (production pipeline)
- `tiering.py`
- `core/titanium.py`
- `core/scoring_pipeline.py`
- `context_layer.py` (DefensiveRankService, PaceVectorService, UsageVacuumService)

**Docs that must match the contract (via validator):**
- `SCORING_LOGIC.md`
- `CLAUDE.md` (if an invariant changes)
- `docs/JARVIS_SAVANT_MASTER_SPEC.md` (master spec + integration audit)

## Post-change gates (run after ANY backend change)

1) **Auth**
   - no header → `Missing`
   - wrong key → `Invalid`
   - correct key → success

2) **Shape contract**
   - required: `ai_score`, `research_score`, `esoteric_score`, `jarvis_score`, `context_score`
   - required: `total_score`, `final_score`
   - required: `bet_tier` object

3) **Hard gates**
   - no picks with `final_score < 6.5` ever returned
   - Titanium triggers only when ≥3/4 engines ≥8.0

4) **Fail-soft**
   - integration failures still return 200 with `errors` populated
   - `/live/debug/integrations` must loudly show missing/unhealthy items

5) **Freshness**
   - response includes `date_et` and `run_timestamp_et`
   - cache TTL matches expectations (best-bets shorter than others)

**Never do:**
- Add/modify scoring literals directly in `live_data_router.py` / `tiering.py` / `core/titanium.py`
- Duplicate thresholds anywhere outside the contract
- Pass hardcoded context values to LSTM (must use context layer services)

---

### B) Integrations / API Keys / Connectivity / "Are we using X?"
**Examples:** Odds API, Playbook, BallDontLie, Weather, NOAA, FRED, Finnhub, SerpAPI, Twitter, Whop, Astronomy keys, etc.

**Canonical source (edit here only):**
- `core/integration_contract.py` - All integration definitions, env vars, validation rules
- `integration_registry.py` - Runtime registry (imports from contract)

**Generated documentation (do not edit manually):**
- `docs/AUDIT_MAP.md` - Generated from contract via `./scripts/generate_audit_map.sh`

**Runtime verification:**
- `/live/debug/integrations` must report required integrations and validation state

**Validation:**
- `./scripts/validate_integration_contract.sh` - Ensures docs match contract

**Never do:**
- Add a new integration without adding it to `core/integration_contract.py`
- Edit `docs/AUDIT_MAP.md` manually (regenerate with `./scripts/generate_audit_map.sh`)
- Leave keys "present but unused" without explicit reason in `/live/debug/integrations`
- Add hidden feature flags to disable required integrations
- Allow weather to return `FEATURE_DISABLED` status (must be relevance-gated only)

---

### C) ET Window / Timezone / Day Filtering
**Examples:** "why is it UTC", missing games in the slate, cutoff bugs.

**Canonical source (edit here only):**
- `core/time_et.py`

**Hard invariant (must remain true everywhere):**
- **ET day bounds = [00:01:00 ET, 00:00:00 ET next day)** (start at 12:01 AM, end exclusive)
- ET window must be applied **before** fetch + scoring (games AND props)

**Docs that describe the invariant:**
- `CLAUDE.md` (Invariant [1])

**Never do:**
- Re-implement day bounds in other modules
- Use naive datetimes for filtering

---

### D) Persistence / Storage / "Did we lose picks after restart?"
**Examples:** grader_store disappearing, volume mount issues, storage paths drifting.

**Canonical sources (edit here only):**
- `storage_paths.py`
- `data_dir.py`

**Hard invariant (must remain true everywhere):**
- All persisted data must be written **under `RAILWAY_VOLUME_MOUNT_PATH`** (derived paths only)

**Runtime verification:**
- `/internal/storage/health` must confirm mount + writeability
- Session 2 + Session 9 must pass in CI

**Never do:**
- Hardcode `/app/...` or other ephemeral filesystem paths for persistence
- Build new paths without going through the canonical storage helpers

---

### E) Scheduler / Auto-grading / Cache Warm / "6AM audit"
**Examples:** scheduler status import errors, missing jobs, ET schedule visibility.

**Canonical source (edit here only):**
- `daily_scheduler.py`

**Runtime verification:**
- `/live/scheduler/status` must return 200 and must not throw import errors
- Must report ET timezone (America/New_York) and the configured job times

**Docs:**
- `CLAUDE.md` (Invariant [10])

**Never do:**
- Add jobs without exposing them via the status endpoint
- Allow scheduler status to fail due to import/export drift

---

### F) Output Filtering / Dedup / Contradiction Gate / Top-N Caps
**Examples:** missing picks, duplicates, opposite sides, unexpectedly low volume.

**Canonical sources:**
- `live_data_router.py` (pipeline ordering)
- `tiering.py` (tier logic)

**Hard invariant:**
- Never output/store picks with `final_score < MIN_FINAL_SCORE` (contract)

**CI enforcement:**
- Session 7 must pass

---

### G) Auto-grader / Grading / Multi-sport grading rules
**Examples:** "grader shows 0", BDL grading, CLV logic.

**Canonical sources:**
- `auto_grader.py`
- `grader_store.py`

**CI enforcement:**
- Session 8 must pass

---

### H) Pick Output Format / PickContract v1 / "Frontend can't render this pick"
**Examples:** missing fields, wrong pick_type, selection_home_away missing, bet_string wrong format.

**Canonical sources (edit here only):**
- `utils/pick_normalizer.py` - Single source of truth for pick normalization
- `docs/PICK_CONTRACT_V1.md` - Full specification

**Related files:**
- `live_data_router.py` - Applies normalization via `_normalize_pick()`
- `jason_sim_confluence.py` - SHARP type mapping

**Hard invariants:**
- All picks MUST include ALL PickContract v1 fields (Core Identity, Bet Instruction, Reasoning)
- `selection_home_away` MUST be computed from selection vs home/away team
- `odds_american` MUST be actual value or null (NEVER fabricated)
- Empty arrays for no data (NEVER sample/fake picks)

**Tests:**
- `tests/test_pick_contract_v1.py` (12 tests must pass)

**Docs:**
- `CLAUDE.md` (Invariant 13)
- `docs/PICK_CONTRACT_V1.md`

**Never do:**
- Return picks without all required fields
- Fabricate odds (default to -110)
- Return sample/fallback data when real data unavailable
- Skip pick normalization before API response

---

## Canonical Sources of Truth — Quick Table

| Topic | Canonical File(s) | What It Defines |
|---|---|---|
| Scoring contract | `core/scoring_contract.py` | Weights, thresholds, gates, boost levels (v17.1: 5-engine) |
| Context layer | `context_layer.py` | DefensiveRank, Pace, Vacuum services (Pillars 13-15) |
| ML integration | `ml_integration.py` | LSTM, Ensemble models with real context data |
| Integrations mapping | `integration_registry.py` + `docs/AUDIT_MAP.md` | Env vars → modules/endpoints + validation |
| ET window | `core/time_et.py` | ET bounds + timezone correctness |
| Storage | `storage_paths.py` + `data_dir.py` | All persisted paths rooted at volume mount |
| Scheduler | `daily_scheduler.py` | Jobs + ET schedule + exported status |
| Tiering | `tiering.py` | Tier assignment + filters |
| **Pick output format** | `utils/pick_normalizer.py` + `docs/PICK_CONTRACT_V1.md` | PickContract v1 fields, normalization rules |
| **Public payload sanitizer** | `utils/public_payload_sanitizer.py` + `live_data_router.py` | ET-only public payloads, strip UTC/telemetry |
| CI sessions | `scripts/ci_sanity_check.sh` | Sessions 1–10 must pass |

---

## Validators & CI — What to Run

### Required (must pass before any push)
```bash
./scripts/ci_sanity_check.sh
```

### Helpful production verification (read-only)
```bash
BASE_URL="https://web-production-7b2a.up.railway.app"
API_KEY="YOUR_KEY"

curl -s "$BASE_URL/health" | jq .
curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" | jq .
curl -s "$BASE_URL/live/scheduler/status" -H "X-API-Key: $API_KEY" | jq .
curl -s "$BASE_URL/internal/storage/health" -H "X-API-Key: $API_KEY" | jq .
```

---

## "If You Change X, You Must Also Change Y"

| Change | Must also update | Why |
|---|---|---|
| `core/scoring_contract.py` | `SCORING_LOGIC.md` (contract block), `CLAUDE.md` invariants | Prevent scoring drift |
| Context layer services | `live_data_router.py` (LSTM call), `ml_integration.py` | Ensure LSTM gets real context |
| Engine weights | `SCORING_LOGIC.md`, `CLAUDE.md`, frontend display | All must show same weights |
| Any invariant behavior | `CLAUDE.md` invariants section | Keep ops rules aligned |
| Any persisted path logic | `storage_paths.py` / `data_dir.py` only | Keep everything under volume mount |
| Any scheduler job / export | `/live/scheduler/status` output + Session 10 | Ensure observability |
| Any integration env var usage | `integration_registry.py` + `docs/AUDIT_MAP.md` | Maintain env var → code mapping |
| Any session spec changes | `scripts/ci_sanity_check.sh` + spot check scripts | CI must fail on regression |
| Pick output fields/format | `utils/pick_normalizer.py` + `docs/PICK_CONTRACT_V1.md` | Maintain frontend contract |
| Pillar additions (13-17) | `context_layer.py`, `live_data_router.py`, docs | All 17 pillars must be documented |
| Public payload ET-only rules | `utils/public_payload_sanitizer.py` + `CLAUDE.md` | No UTC/telemetry leaks; ET display only |
| Live caching headers | `main.py` middleware + `live_data_router.py` | Ensure no-store headers on GET/HEAD |

---

## What NOT to Do (Hard Bans)

- Add scoring literals to production code (contract exists for a reason)
- Re-implement ET bounds anywhere except `core/time_et.py`
- Write persisted data outside `RAILWAY_VOLUME_MOUNT_PATH`
- Add/rename integrations without updating the canonical mapping
- Let required endpoints return 500; fail-soft everywhere except debug/health which must fail-loud with explicit reasons
- Ship UTC/ISO timestamps or telemetry in public `/live/*` payloads (use sanitizer)

### /health must be truthful (no greenwashing)

`/health` is public for Railway but must report **real** internal status:
- probes: storage, db, redis, scheduler, integrations env map
- outputs: `status` + `ok` + `errors` + `degraded_reasons`
- fail-soft (200) but never “healthy” when probes fail
- "Fix" something by changing docs only (or code only). They must match.
- Lower log level globally or suppress INFO telemetry in production (see Observability below)

---

## Observability / Logs

**RULE:** Keep startup INFO telemetry. Do not suppress production visibility.

**Required startup logs (must remain visible):**
- Redis connection status
- Scheduler job registration (auto-grading, cache pre-warm, APScheduler)
- Prediction load count
- Health check requests

**Allowed suppression:**
- TensorFlow/CUDA noise (GPU probing) — already handled via env vars
- Third-party DEBUG/TRACE logs

**Never do:**
- Set global log level to WARNING/ERROR in production
- Suppress uvicorn startup/health INFO logs
- Remove scheduler/Redis connection confirmations

**Reference:** `CLAUDE.md` Invariant 12

---

## Documentation Map

- `docs/MASTER_INDEX.md` — this file (routing + policy)
- `CLAUDE.md` — invariants + operational rules
- `SCORING_LOGIC.md` — scoring details + contract representation
- `PROJECT_MAP.md` — file/module responsibilities
- `COMMIT_CHECKLIST.md` — code+docs commit discipline
- `BACKEND_OPTIMIZATION_CHECKLIST.md` — sessions checklist + commands
- `docs/AUDIT_MAP.md` — integration/env var mapping table (canonical)
- `docs/PICK_CONTRACT_V1.md` — pick output format specification (PickContract v1)

---

## Golden Command Sequence

Before any push:

```bash
./scripts/ci_sanity_check.sh
git status
git add -A
git commit -m "fix: ... + docs: ..."
git push origin main
```

---

## Post-deploy verification (always run)

```bash
./scripts/post_deploy_check.sh
```

This is the mirror gate to `ci_sanity_check.sh`:
- **Before deploy:** `./scripts/ci_sanity_check.sh`
- **After deploy:** `./scripts/post_deploy_check.sh`

Never skip. Catches runtime/env drift that CI cannot detect.
