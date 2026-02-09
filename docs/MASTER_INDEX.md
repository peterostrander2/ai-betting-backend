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

## Daily Sanity Report (Best Bets Health)

Use this after deploys or before sending daily picks:

```
API_KEY=your_key \
API_BASE=https://web-production-7b2a.up.railway.app \
SPORTS="NBA NFL NHL MLB" \
bash scripts/daily_sanity_report.sh
```

What it validates:
- `/health` status + build identifiers
- `/live/best-bets/{sport}` counts + top pick sample
- ET-only payload (no UTC/telemetry keys)
- Cache headers for best-bets endpoints

This is also wired into `scripts/ci_sanity_check.sh` as a **non-blocking** step.

---

## Decision Tree — Where to Look and What to Edit

### A) Scoring / Thresholds / Tier Rules / Confluence (v18.0 - Option A)
**Examples:** engine weights, MIN_FINAL_SCORE, Gold Star gates, Titanium rule, confluence boost values.

**Current Architecture (v18.0 Option A):**
- 4 base engines (weighted): AI (25%), Research (35%), Esoteric (20%), Jarvis (20%)
- Context is a bounded modifier (cap ±0.35), not a weighted engine
- Titanium: 3/4 engines >= 8.0 (AI/Research/Esoteric/Jarvis only)
- GOLD_STAR gates: ai>=6.8, research>=5.5, jarvis>=6.5, esoteric>=4.0 (context gate removed)
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
   - required: `ai_score`, `research_score`, `esoteric_score`, `jarvis_score`, `context_modifier`
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

## Post-deploy smoke checklist (debug telemetry)

```bash
BASE_URL="https://your-deployment.app" API_KEY="YOUR_KEY" \
  bash scripts/verify_live_endpoints.sh

BASE_URL="https://your-deployment.app" API_KEY="YOUR_KEY" \
  bash scripts/post_deploy_check.sh
```

Expected:
- `/live/best-bets/NBA?debug=1` includes `used_integrations`
- `/live/best-bets/NBA` omits `used_integrations`
- `/live/debug/integrations` shows `last_used_at` after a best-bets hit

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

**Telemetry rules:**
- `last_used_at` is global and updated on successful client calls.
- `used_integrations` is request-scoped and only returned in debug payloads (e.g., `?debug=1`).

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
- **ET day bounds = [00:00:00 ET, 00:00:00 ET next day)** (midnight start, end exclusive)
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

**Two Storage Systems (INTENTIONAL SEPARATION):**

| System | Module | Path | Purpose | Frequency |
|--------|--------|------|---------|-----------|
| **Picks** | `grader_store.py` | `/data/grader/predictions.jsonl` | All picks | High (every request) |
| **Weights** | `auto_grader.py` | `/data/grader_data/weights.json` | Learned weights | Low (daily 6 AM) |

**Why Separate?**
- Different access patterns (frequent writes vs daily batch)
- Avoids file locking contention
- Independent recovery (restore weights without losing picks)

**Data Flow:**
```
Best-bets → grader_store.persist_pick() → /data/grader/predictions.jsonl
                                                    ↓ (read)
Daily 6 AM → auto_grader.grade_prediction() → /data/grader_data/weights.json
```

**Runtime verification:**
- `/internal/storage/health` must confirm mount + writeability
- Session 2 + Session 9 must pass in CI

**Never do:**
- Hardcode `/app/...` or other ephemeral filesystem paths for persistence
- Build new paths without going through the canonical storage helpers
- Merge the two storage systems (they're separate by design)
- Write picks from `auto_grader.py` (only `grader_store.py` writes picks)
- Write weights from `grader_store.py` (only `auto_grader.py` writes weights)

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

**Verification (required after any grader change):**
```bash
# Storage + grader health
curl -s https://web-production-7b2a.up.railway.app/internal/storage/health
curl -s https://web-production-7b2a.up.railway.app/live/grader/status -H "X-API-Key: KEY"

# Dry-run (does NOT modify state)
curl -s -X POST https://web-production-7b2a.up.railway.app/live/grader/dry-run -H "X-API-Key: KEY"
```

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

### I) Officials / Pillar 16 / Referee Tendency (v17.8)
**Examples:** "officials adjustment always 0", "referee not found", "wrong tendency data".

---

### J) Phase 8 Esoteric Signals / Lunar / Mercury / Rivalry (v18.2)
**Examples:** "lunar phase not calculating", "mercury retrograde not triggering", "rivalry boost missing", "timezone errors in esoteric".

**Canonical sources (edit here only):**
- `esoteric_engine.py` - All Phase 8 signal functions + `get_phase8_esoteric_signals()` aggregator
- `alt_data_sources/noaa.py` - Solar flare status from NOAA

**Related files:**
- `live_data_router.py` (lines 4039-4106) - Phase 8 integration into scoring
- `astronomical_api.py` - Lunar phase calculations

**Hard invariants:**
- All Phase 8 signals aggregated via `get_phase8_esoteric_signals()`
- `phase8_boost` added to `esoteric_raw`, NOT directly to final score
- Timezone-aware datetimes REQUIRED for lunar calculations (use `ZoneInfo`)
- 5 signals active: Lunar Phase, Mercury Retrograde, Rivalry Intensity, Streak Momentum, Solar Flare
- Signal count: 17/17 active in Esoteric Engine

**Verification:**
```bash
# Check Phase 8 in production picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {phase8_boost, phase8_reasons, phase8_breakdown}'

# Test Phase 8 signals directly
python3 -c "
from esoteric_engine import get_phase8_esoteric_signals
from datetime import datetime, date
from zoneinfo import ZoneInfo
result = get_phase8_esoteric_signals(
    game_datetime=datetime.now(ZoneInfo('America/New_York')),
    game_date=date.today(),
    sport='NBA', home_team='Lakers', away_team='Celtics',
    pick_type='TOTAL', pick_side='Over'
)
print('Phase 8 boost:', result.get('total_boost'))
"
```

**Tests:**
- `scripts/prod_sanity_check.sh` includes 4 Phase 8 checks (18 total)

**Docs:**
- `CLAUDE.md` (Phase 8 section, NEVER DO THESE rules 88-97)
- `docs/LESSONS.md` (Lessons 14-16: timezone, env vars, variable init)

**Never do:**
- Compare timezone-naive to timezone-aware datetimes (causes TypeError)
- Skip `get_phase8_esoteric_signals()` in the scoring pipeline
- Add Phase 8 boosts directly to `esoteric_score` instead of `esoteric_raw`
- Forget to initialize `weather_data = None` before conditional blocks
- Use AND logic for env var alternatives when OR is needed

**Canonical sources (edit here only):**
- `officials_data.py` - Referee tendency database (25 NBA, 17 NFL, 15 NHL refs)
- `context_layer.py:OfficialsService.get_officials_adjustment()` - Adjustment calculation

**Related files:**
- `live_data_router.py` (lines 4055-4106) - Pillar 16 integration
- `alt_data_sources/espn_lineups.py` - ESPN Hidden API for referee assignments

**Hard invariants:**
- Officials adjustments ONLY for NBA, NFL, NHL (not MLB, NCAAB)
- Adjustment range: -0.5 to +0.5 on research_score
- Over tendency > 52% boosts Over picks; < 48% boosts Under
- Home bias > 1.5% boosts home team picks
- ESPN assigns refs 1-3 hours before games (data may be unavailable earlier)

**Verification:**
```bash
# Check officials adjustments in picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].research_reasons] | flatten | map(select(startswith("Officials")))'

# Test officials_data module
python3 -c "from officials_data import get_database_stats; print(get_database_stats())"
```

**Tests:**
- Test with known refs (Scott Foster, Carl Cheffers, Wes McCauley)
- Test with unknown refs (should return 0.0, [])

**Docs:**
- `CLAUDE.md` (Invariant 16 - 17 Pillars)
- `docs/LESSONS.md` (Lesson 8 - External Data Without Interpretation Layer)

**Never do:**
- Add officials adjustments for MLB/NCAAB (insufficient data)
- Return adjustment without a reason string
- Assume ESPN always has referee data (fails gracefully)
- Hardcode referee names in live_data_router.py (use officials_data.py)

---

## Canonical Sources of Truth — Quick Table

| Topic | Canonical File(s) | What It Defines |
|---|---|---|
| Scoring contract | `core/scoring_contract.py` | Weights, thresholds, gates, boost levels (v18.0: 4-engine + context modifier) |
| Context layer | `context_layer.py` | DefensiveRank, Pace, Vacuum, Officials services (Pillars 13-16) |
| **Officials data (v17.8)** | `officials_data.py` | Referee tendency database (25 NBA, 17 NFL, 15 NHL refs) |
| **Phase 8 Esoteric (v18.2)** | `esoteric_engine.py` | Lunar, Mercury, Rivalry, Streak, Solar signals (17/17 active) |
| ML integration | `ml_integration.py` | LSTM, Ensemble models with real context data |
| Integrations mapping | `integration_registry.py` + `docs/AUDIT_MAP.md` | Env vars → modules/endpoints + validation |
| ET window | `core/time_et.py` | ET bounds + timezone correctness |
| **Picks storage** | `grader_store.py` | Pick persistence (`/data/grader/predictions.jsonl`) |
| **Weights storage** | `auto_grader.py` + `data_dir.py` | Learned weights (`/data/grader_data/weights.json`) |
| Storage paths | `storage_paths.py` + `data_dir.py` | All persisted paths rooted at volume mount |
| Scheduler | `daily_scheduler.py` | Jobs + ET schedule + exported status |
| Tiering | `tiering.py` | Tier assignment + filters |
| **Pick output format** | `utils/pick_normalizer.py` + `docs/PICK_CONTRACT_V1.md` | PickContract v1 fields, normalization rules |
| **Boost field contract** | `SCORING_LOGIC.md` | Required boost fields in pick payloads |
| **Public payload sanitizer** | `utils/public_payload_sanitizer.py` + `live_data_router.py` | ET-only public payloads, strip UTC/telemetry |
| **Props sanity check** | `scripts/props_sanity_check.sh` | Props pipeline verification (optional gate) |
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
| **Pick persistence** | `grader_store.py` only | Picks flow through grader_store exclusively |
| **Weights persistence** | `auto_grader.py` + `data_dir.py` only | Weights flow through auto_grader exclusively |
| Any scheduler job / export | `/live/scheduler/status` output + Session 10 | Ensure observability |
| Any integration env var usage | `integration_registry.py` + `docs/AUDIT_MAP.md` | Maintain env var → code mapping |
| Any session spec changes | `scripts/ci_sanity_check.sh` + spot check scripts | CI must fail on regression |
| Pick output fields/format | `utils/pick_normalizer.py` + `docs/PICK_CONTRACT_V1.md` | Maintain frontend contract |
| **Boost output fields** | `SCORING_LOGIC.md` (Boost Field Contract) | All boosts need value + status + reasons |
| **New scoring adjustment** | Pick payload field + `endpoint_matrix_sanity.sh` formula + `CLAUDE.md` Boost Inventory + canonical formula | Every adjustment to final_score must be surfaced as a field (Lesson 46) |
| **New script env var** | `RUNTIME_ENV_VARS` in `integration_registry.py` | env_drift_scan catches unregistered vars (Lesson 47) |
| Pillar additions (13-17) | `context_layer.py`, `live_data_router.py`, docs | All 17 pillars must be documented |
| Officials data (Pillar 16) | `officials_data.py`, `context_layer.py`, `live_data_router.py` | Referee tendency database + adjustment logic (v17.8) |
| **Phase 8 signals (v18.2)** | `esoteric_engine.py`, `live_data_router.py`, `CLAUDE.md` | Lunar/Mercury/Rivalry/Streak/Solar (17/17 signals) |
| Public payload ET-only rules | `utils/public_payload_sanitizer.py` + `CLAUDE.md` | No UTC/telemetry leaks; ET display only |
| Live caching headers | `main.py` middleware + `live_data_router.py` | Ensure no-store headers on GET/HEAD |
| **Integration tracking** | Source module + `integration_registry.py` | Track usage at source level |

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
- `docs/LESSONS.md` — mistakes made and how to avoid repeating them (61 lessons as of v20.11)
- `SCORING_LOGIC.md` — scoring details + contract representation
- `PROJECT_MAP.md` — file/module responsibilities
- `COMMIT_CHECKLIST.md` — code+docs commit discipline
- `BACKEND_OPTIMIZATION_CHECKLIST.md` — sessions checklist + commands
- `docs/AUDIT_MAP.md` — integration/env var mapping table (canonical)
- `docs/PICK_CONTRACT_V1.md` — pick output format specification (PickContract v1)
- `scripts/prod_go_nogo.sh` — 12-check go/no-go gate (must pass before deploy)
- `tasks/lessons.md` — incident log with root causes and prevention rules

---

## Daily Learning Loop

- **Autograder audit (6 AM ET)** writes:
  - `/data/grader_data/audit_logs/audit_YYYY-MM-DD.json`
  - `/data/grader_data/audit_logs/lesson_YYYY-MM-DD.json`
  - `/data/grader_data/audit_logs/lessons.jsonl`
- **Lesson endpoint** (member UI): `GET /live/grader/daily-lesson`

---

### K) Phase 9 Full Spectrum / Streaming / Live Signals / Weather / Travel (v20.0)
**Examples:** "streaming not working", "live signals not triggering", "weather adjustment missing", "travel fatigue not applied".

**Canonical sources (edit here only):**
- `streaming_router.py` - SSE endpoints for real-time data streaming
- `alt_data_sources/live_signals.py` - Score momentum and line movement detection
- `alt_data_sources/weather.py` - Weather integration for outdoor sports
- `alt_data_sources/travel.py` - Travel fatigue calculations

**Related files:**
- `live_data_router.py` (lines 4180-4220) - Live signals integration into scoring
- `main.py` - Streaming router registration

**Hard invariants:**
- Streaming requires `PHASE9_STREAMING_ENABLED=true` env var
- Live signals require `PHASE9_LIVE_SIGNALS_ENABLED=true` env var
- Weather applies ONLY to outdoor sports (NFL, MLB, NCAAF) - NOT NBA, NHL, NCAAB
- Weather adjustments capped at -0.35 (never positive)
- Live signals combined boost capped at ±0.50
- SSE refresh intervals: minimum 15s, maximum 120s, default 30s
- Polling fallback endpoints available for clients without SSE support

**Pillar 18: Live Context (v20.0):**
| Signal | Engine | Boost Range | Condition |
|--------|--------|-------------|-----------|
| Score momentum | Context | ±0.25 | game_status == LIVE |
| Live line movement | Research | ±0.30 | 1.5+ point move |
| Period pace trend | Esoteric | ±0.20 | Scoring variance |

**Streaming Endpoints:**
- `GET /live/stream/status` - Check if streaming is enabled/available
- `GET /live/stream/games/{sport}` - SSE stream of live game updates
- `GET /live/stream/lines/{sport}` - SSE stream of line movements
- `GET /live/stream/picks/{sport}` - SSE stream of high-confidence picks
- `GET /live/stream/poll/games/{sport}` - Polling fallback for live games
- `GET /live/stream/poll/lines/{sport}` - Polling fallback for line movements

**Verification:**
```bash
# Check streaming status
curl /live/stream/status -H "X-API-Key: KEY"
# Should show: status: "ACTIVE" when enabled

# Check live signals in debug output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | select(.game_status == "LIVE") | {live_boost, live_reasons}]'

# Check weather adjustments (NFL/MLB only)
curl /live/best-bets/NFL?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {weather_adj, research_reasons}'

# Check travel adjustments
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].context_reasons | map(select(contains("Travel")))'
```

**Feature Flags:**
- `PHASE9_STREAMING_ENABLED` - Enable real-time streaming (default: false)
- `PHASE9_LIVE_SIGNALS_ENABLED` - Enable live in-game signals (default: false)
- `TRAVEL_ENABLED` - Enable travel/fatigue adjustments (default: true)
- `PHASE9_WEATHER_ENABLED` - Weather integration (default: true)

**Never do:**
- Apply weather boost to indoor sports (NBA, NHL, NCAAB)
- Apply live signals to pre-game picks (game_status != "LIVE")
- Exceed weather modifier cap of -0.35
- Exceed live signals combined cap of ±0.50
- Use SSE polling intervals < 15 seconds (API quota)
- Stream full pick objects over SSE (bandwidth)
- Skip dome detection for NFL weather

**Docs:**
- `CLAUDE.md` (Pillar 18: Live Context, NEVER DO THESE rules 98-109)

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

---

### L) Automation / Cron Jobs / Scheduled Health Checks

**Examples:** "health check didn't run", "cron path wrong", "logs not generated".

**Canonical sources:**
- `crontab -l` (view current schedule)
- `scripts/*.sh` (individual scripts)

**33 Automated Jobs (Backend + Frontend):**

| Frequency | Backend Scripts | Frontend Scripts |
|-----------|-----------------|------------------|
| Every 30 min | `response_time_check.sh` | `response_time_check.sh` |
| Every 4 hours | `memory_profiler.sh` | `memory_leak_check.sh` |
| Hourly | `error_rate_monitor.sh` | - |
| Daily | `backup_data.sh`, `db_integrity_check.sh`, `access_log_audit.sh`, `daily_health_check.sh` | `console_log_scan.sh`, `daily_health_check.sh` |
| Weekly (Sun) | `prune_old_data.sh`, `dead_code_scan.sh`, `dependency_vuln_scan.sh`, `auto_cleanup.sh` | `prune_build_artifacts.sh`, `dead_code_scan.sh`, `accessibility_check.sh`, `dependency_vuln_scan.sh`, `auto_cleanup.sh` |
| Weekly (Mon) | `complexity_report.sh`, `test_coverage_report.sh`, `secret_rotation_check.sh`, `feature_flag_audit.sh` | `broken_import_check.sh`, `complexity_report.sh`, `test_coverage_report.sh`, `bundle_size_check.sh`, `secret_exposure_check.sh`, `feature_flag_audit.sh` |

**Log Locations:**
```bash
~/ai-betting-backend/logs/health_check.log  # Daily health
~/ai-betting-backend/logs/cron.log          # All cron output
~/bookie-member-app/logs/cron.log           # Frontend cron output
```

**Verification (after path changes or fresh setup):**
```bash
# Count jobs (should be 33+)
crontab -l | grep -c "^\*\|^[0-9]"

# Verify paths exist
ls -d ~/ai-betting-backend ~/bookie-member-app

# Check recent cron activity
tail -20 ~/ai-betting-backend/logs/cron.log
```

**Hard invariants:**
- Cron paths MUST match actual repo locations (Lesson 66)
- Logs go to `~/repo/logs/`, not Desktop or /tmp
- Mac must be awake for scheduled jobs to run

**Never do:**
- Use `~/Desktop/` paths in crontab (repos may be in home dir)
- Assume cron is working without checking logs
- Add manual health check steps when automation exists
- Skip path validation when setting up on new machine

---

## v20.11 Updates (Feb 8, 2026)

**Latest Enhancements — 4 Real Data Source Integrations + Rivalry Database:**

| Lesson | Enhancement | Description |
|--------|-------------|-------------|
| 57 | NOAA Space Weather | `signals/physics.py` calls real NOAA API for Kp-Index |
| 58 | Live ESPN Scores | `live_data_router.py` extracts live scores from scoreboard |
| 59 | Void Moon Improved | Meeus-based lunar calculation with perturbation |
| 60 | LSTM Real Data | Playbook API game logs before synthetic fallback |
| 61 | Rivalry Database | 204 rivalries covering ALL teams in 5 sports |

**Key Files Modified:**
- `signals/physics.py` — Real NOAA integration
- `signals/hive_mind.py` — Improved void moon
- `live_data_router.py` — ESPN live scores extraction
- `lstm_training_pipeline.py` — Real data training
- `esoteric_engine.py` — Comprehensive MAJOR_RIVALRIES

**Invariant Updates:**
- TOTAL_BOOST_CAP = 1.5 (fixed from incorrect 3.5 in sanity scripts and docs)
- 61 total lessons documented
- 27 NEVER DO categories

**Prevention Checklist Added to CLAUDE.md:**
A new "🛡️ Prevention Checklist" section consolidates key prevention rules from all lessons for quick reference before writing code.
