# Lessons Learned - AI Betting Backend

> Self-improvement loop: Document mistakes to prevent repetition

---

## Critical Incidents

### 1. Storage Path Blocker Crash (Jan 28-29, 2026)

**What happened:**
- Added code to block all `/app/*` paths in `data_dir.py`
- Assumed `/data` was ephemeral storage
- Did NOT verify storage health before making changes
- Did NOT read CLAUDE.md Storage Configuration section

**Impact:** Production crashed with 502 errors, 2 minutes downtime

**Root cause:** Misunderstanding that `/data` IS the Railway persistent volume (verified with `os.path.ismount() = True`)

**Fix:** Removed path blocker, unified to `RAILWAY_VOLUME_MOUNT_PATH`

**Lesson:**
- ALWAYS verify production health BEFORE assuming paths are wrong
- `/data` is NOT ephemeral on Railway - it's a mounted 5GB persistent volume
- NEVER add path validation that blocks legitimate storage paths

---

### 2. filter_date Bug (Jan 29, 2026)

**What happened:**
- `filter_date` showing "ERROR" in debug output
- Caused "cannot access local variable" error at line 2149

**Root cause:** Redundant `from core.time_et import et_day_bounds` at lines 3779 and 5029 made Python treat it as local variable

**Fix:** Removed redundant local imports, now uses top-level import consistently

**Lesson:**
- Avoid duplicate imports of the same function at different scopes
- Python's scoping rules can cause subtle bugs with local vs global references
- Check `/live/debug/time` to verify ET timezone consistency

---

## Architectural Rules (Learned the Hard Way)

### Storage Architecture
- ALL storage MUST use `RAILWAY_VOLUME_MOUNT_PATH` environment variable
- Both `storage_paths.py` AND `data_dir.py` must use this
- Picks: `/data/grader/predictions.jsonl` (high-frequency)
- Weights: `/data/grader_data/weights.json` (low-frequency)
- Audits: `/data/audit_logs/audit_{date}.json`

### ET Timezone Filtering
- ALWAYS filter Odds API events to TODAY only in ET timezone
- Single source of truth: `core/time_et.py`
- NEVER use `datetime.now()` or `utcnow()` for slate filtering
- NEVER use pytz - only `zoneinfo` allowed
- Apply filter BEFORE scoring, not after

### Titanium Rule
- `titanium_triggered=true` ONLY when >= 3 of 4 base engines >= 8.0
- 1/4 or 2/4 is ALWAYS false, even if scores are high
- Use `core/titanium.py` as single source of truth

### Response Contracts
- `/live/best-bets/{sport}` MUST always return `props`, `game_picks`, `meta` keys
- Empty arrays are valid, missing keys are not
- NHL often has 0 props - frontend must never get KeyError

---

## Pre-Deploy Checklist (From Past Failures)

Before ANY storage/autograder/scheduler change:

1. Read CLAUDE.md Storage Configuration section
2. Verify production health with `/internal/storage/health`
3. Verify grader status with `/live/grader/status`
4. Check that `RAILWAY_VOLUME_MOUNT_PATH` is used everywhere
5. Run `scripts/prod_sanity_check.sh`
6. Verify `filter_date` matches `et_date` in debug output
7. Run `scripts/verify_autograder_e2e.sh --mode pre`

---

## Code Review Red Flags

Watch for these patterns that have caused production issues:

- [ ] Path validation that blocks `/app/*` or `/data/*`
- [ ] Duplicate imports of `time_et` functions
- [ ] Direct use of `datetime.now()` for ET calculations
- [ ] Missing keys in API response structures
- [ ] Titanium logic duplicated instead of using `core/titanium.py`
- [ ] Storage paths hardcoded instead of using env vars
- [ ] Scoring adjustments applied to `final_score` but NOT surfaced as a pick field
- [ ] Env vars used in scripts but missing from `RUNTIME_ENV_VARS` in `integration_registry.py`
- [ ] `__file__` or `os.path.dirname(__file__)` used inside Python heredocs (`python3 - <<'PY'`)
- [ ] Go/no-go run locally without `ALLOW_EMPTY=1`

---

### 3. v18.0 Option A: 4-Engine Base + Context Modifier (Feb 2026)

**What happened:**
- Kept 4 base engines (AI/Research/Esoteric/Jarvis)
- Converted Context into a bounded modifier (not a weighted engine)
- Preserved real context inputs to LSTM (no hardcoded defaults)
- Integrated Officials (Pillar 16) and Park Factors (Pillar 17)
- Implemented Harmonic Convergence boost (+1.5 when Research AND Esoteric both >= 8.0)

**Impact:** Context can no longer overpower paid data signals; scoring remains stable and explainable.

**Root cause:** Context was overweighted as a 30% engine, distorting outcomes vs paid feeds.

**Changes Made:**
1. `core/scoring_contract.py` - ENGINE_WEIGHTS = 4 base engines; added `CONTEXT_MODIFIER_CAP`
2. `live_data_router.py` - Context score -> bounded modifier; base score uses 4 engines only
3. Removed GOLD_STAR context gate
4. Titanium remains 3/4 engines (context never counts)
5. LSTM call still uses real `{def_rank, pace, vacuum}` inputs

**Fix Summary:**
- Context Layer Services (DefensiveRankService, PaceVectorService, UsageVacuumService) provide real data
- OfficialsAnalyzer adjusts research_score based on referee tendencies
- ParkFactorService adjusts esoteric_score for MLB venue effects

**Lesson:**
- When changing scoring architecture, update ALL canonical sources together:
  - `core/scoring_contract.py` (weights, caps)
  - `CLAUDE.md` (invariants)
  - `docs/MASTER_INDEX.md` + `docs/JARVIS_SAVANT_MASTER_SPEC.md`
- Always verify ML models receive real data, not hardcoded defaults

## Lesson: /health must be truthful (no greenwashing)
- `/health` is public for Railway but must report real internal status.
- Required probes: storage, db, redis, scheduler, integrations env map.
- Output must include: `status`, `ok`, `errors`, `degraded_reasons`.
- Fail-soft (200) but never return “healthy” when probes fail.

## Lesson: Post-change gates (run after ANY backend change)
1) Auth (missing/invalid/correct key)
2) Shape contract (engine scores, total/final, bet_tier)
3) Hard gates (final_score >= 6.5, Titanium 3-of-4)
4) Fail-soft (200 + errors, debug integrations loud)
5) Freshness (date_et/run_timestamp_et + cache TTL)
6) No UTC/telemetry leaks (startTime*, generated_at, *_utc, *_iso)
7) Cache headers present on /live (GET/HEAD)
8) Optional daily report (non-blocking): `scripts/daily_sanity_report.sh`
- Test context integration end-to-end before production

## Smoke Check Checklist (post-deploy, no secrets)
1) `/live/best-bets/NBA?debug=1` → `debug.used_integrations` present
2) `/live/best-bets/NBA` → `debug` absent
3) `/live/debug/integrations` → `last_used_at` fields present
4) Confirm no response body includes secrets

**Verification:**
```bash
# Check LSTM receives real context
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: KEY" | jq '.props.picks[0].lstm_metadata.features_used'

# Verify deploy version (Option A is documented in CLAUDE.md + SCORING_LOGIC.md)
curl -s "https://web-production-7b2a.up.railway.app/health" | jq '.deploy_version'
```

---

## Lesson: ET-only public payloads + deterministic responses (Feb 2026)

**What happened:**
- UTC/ISO timestamps leaked into member-facing `/live/*` responses.
- Cache headers were missing on some /live responses.
- Hashes changed every hit due to ordering + volatile fields.

**Fix:**
- Added `utils/public_payload_sanitizer.py` as the single choke point.
- Applied sanitizer in `LiveContractRoute` for member endpoints.
- Added /live no-store headers middleware.
- Stabilized ordering with deterministic sort key.
- Added stable error code for best-bets failures (`BEST_BETS_FAILED`).

**Lesson:**
- ET display strings only; never emit UTC/ISO in public payloads.
- Cache headers must be enforced at a single middleware.
- Stable ordering prevents hash churn when scores tie.

---

### 4. Anti-Drift Architecture (Feb 2026)

**Problem:** Risk of duplicate work, forgotten canonical sources, frontend/backend drift.

**Solution:** Created complete anti-drift system mirroring scoring contract pattern:
- `core/integration_contract.py` - Canonical source for all 14 integrations
- `docs/AUDIT_MAP.md` - Auto-generated (never edit manually)
- `scripts/validate_integration_contract.sh` - Blocks drift before commit
- `docs/MASTER_INDEX.md` - Single routing entry point

**Lesson:** When you build one contract system that works (scoring), immediately apply the same pattern to other sources of truth (integrations). Don't wait for drift to happen.

**Rule:** Any time there's a "where should this live?" question, the answer should be in MASTER_INDEX.md routing. If it's not, add it.

---

### 5. Daily Learning Loop Must Produce a Lesson (Feb 2026)

**What happened:**
- Autograder was running daily, but there was no guaranteed “learning summary” persisted for the community UI.

**Impact:** The system learned internally, but the community couldn’t see daily progress.

**Fix:**
- Added a daily lesson writer triggered by the 6 AM ET audit job.
- Persisted lessons to `/data/grader_data/audit_logs/lesson_YYYY-MM-DD.json` and `lessons.jsonl`.
- Added API endpoint: `GET /live/grader/daily-lesson`.

**Lesson:**
- The learning loop is only complete if it **produces a human-facing artifact** every day.

**Rule:** Every automated learning step must write a daily summary to persistent storage and expose it via a member-safe endpoint.

---

---

### 6. Two Storage Systems Architecture (Feb 2026)

**What happened:**
- Confusion about why there are TWO storage paths: `grader_store.py` and `auto_grader.py`
- Questions about whether predictions.json should be removed from auto_grader

**Impact:** Risk of accidentally breaking the storage separation or duplicating pick writes.

**Root cause:** Intentional architectural decision that wasn't clearly documented.

**The Architecture (INTENTIONAL SEPARATION):**

| System | Module | Path | Purpose | Frequency |
|--------|--------|------|---------|-----------|
| **Picks Storage** | `grader_store.py` | `/data/grader/predictions.jsonl` | Store all picks | High-frequency (every best-bets call) |
| **Weights Storage** | `auto_grader.py` | `/data/grader_data/weights.json` | Learned weights only | Low-frequency (daily 6 AM) |

**Why Separate?**
1. **Access patterns differ**: Picks written constantly; weights updated daily
2. **File locking**: Separate files avoid contention
3. **Recovery**: Can restore weights without losing picks (and vice versa)
4. **Audit trail**: Picks are append-only JSONL; weights are overwritten

**Data Flow:**
```
Best-bets endpoint → grader_store.persist_pick() → /data/grader/predictions.jsonl
                                                          ↓ (read)
Daily 6 AM audit → auto_grader.grade_prediction() → /data/grader_data/weights.json
```

**What was removed (v20.x):**
- Legacy `_save_predictions()` method from auto_grader
- Predictions.json saving from `_save_state()`
- `_save_predictions()` calls from `grade_prediction()`

**What remains:**
- `auto_grader.py` READS from `grader_store` but only WRITES weights
- Predictions flow through `grader_store` exclusively

**Lesson:**
- Document intentional architectural decisions before they look like bugs
- Two storage systems is CORRECT - don't merge them
- Picks: `grader_store.py` (append-only JSONL)
- Weights: `auto_grader.py` (daily overwrite)

---

### 7. Props Sanity Check Gate (Feb 2026)

**What happened:**
- Props pipeline could silently fail without blocking deployment
- No automated verification that props were flowing correctly

**Impact:** Users might receive game picks but no props without anyone noticing.

**Fix:**
- Added `scripts/props_sanity_check.sh` for props pipeline verification
- Added to `COMMIT_CHECKLIST.md` as optional gate (set `REQUIRE_PROPS=1` to enforce)
- Documents expected behavior when props are unavailable vs broken

**Lesson:**
- Add sanity checks for each major data pipeline
- Make gates configurable (REQUIRE_PROPS=1 for strict mode)
- Document expected vs unexpected empty states

---

### 8. Integration Tracking Pattern (Feb 2026)

**What happened:**
- NOAA integration was being used but `last_used_at` wasn't updating
- Made it hard to verify which integrations were actually called

**Fix:**
- Added `_mark_noaa_used()` helper in `alt_data_sources/noaa.py`
- Call `mark_integration_used()` on both cache hits AND live fetches
- Pattern: Every integration module should track its usage

**Lesson:**
- Integration tracking should happen at the source module level
- Track usage on BOTH cache hits and live API calls
- Use try/except to avoid breaking main flow if registry fails

---

### 9. Boost Field Contract (Feb 2026)

**What happened:**
- Frontend expected certain boost fields but they were inconsistently present
- No clear contract for which boost fields must appear in pick payloads

**Fix:**
- Documented Boost Field Contract in `SCORING_LOGIC.md`
- Required fields: `base_4_score`, `context_modifier`, `confluence_boost`, `msrf_boost`, `jason_sim_boost`, `serp_boost`
- Each boost includes `*_status` and `*_reasons` fields

**Lesson:**
- Document output contracts explicitly
- Every boost must have: value, status, and reasons
- Frontend should never have to guess field presence

---

## Template: Adding New Lessons

```markdown
### [Title] ([Date])

**What happened:**
- Describe the incident

**Impact:** User-facing impact

**Root cause:** Technical explanation

**Fix:** What was changed

**Lesson:**
- Key takeaway for future development
```

---

### 10. v20.5 Datetime/Timezone Bugs (Feb 4, 2026)

**What happened:**
- `/grader/queue` returned `name 'PYTZ_AVAILABLE' is not defined`
- `/grader/daily-report` returned `can't compare offset-naive and offset-aware datetimes`
- `/grader/performance/{sport}` returned `Internal Server Error` (same datetime bug)
- Daily report showed ~290 picks for "yesterday" instead of ~150 (2-day window bug)

**Impact:** All grader endpoints broken, performance analysis unavailable

**Root cause (4 bugs):**
1. `PYTZ_AVAILABLE` variable used but never defined
2. `datetime.now()` (naive) compared with `datetime.fromisoformat(timestamp)` (potentially aware)
3. Same naive vs aware bug copy-pasted to multiple endpoints
4. Date window math: `days_back + 1` and `days_back - 1` created 2-day window

**Fix:**
1. Replace `PYTZ_AVAILABLE` with `core.time_et.now_et()`
2. Use timezone-aware datetime and handle both naive/aware stored timestamps:
   ```python
   from core.time_et import now_et
   from zoneinfo import ZoneInfo
   et_tz = ZoneInfo("America/New_York")
   cutoff = now_et() - timedelta(days=days_back)
   
   ts = datetime.fromisoformat(p.timestamp)
   if ts.tzinfo is None:
       ts = ts.replace(tzinfo=et_tz)
   ```
3. Use exact day boundaries with `.replace(hour=0, minute=0, second=0, microsecond=0)`

**Lesson:**
- NEVER use `datetime.now()` in grader code - use `now_et()` from `core.time_et`
- NEVER use `pytz` - use `core.time_et` (single source of truth) or `zoneinfo`
- ALWAYS handle both naive and aware timestamps when parsing stored data
- NEVER use `days_back + 1` math - use exact day boundaries with `.replace()`
- When fixing a datetime bug, grep the entire codebase for the same pattern
- Run `grep -n "datetime.now()" *.py | grep fromisoformat` after datetime fixes

---

### 11. SHARP Picks 0% Hit Rate (Feb 4, 2026)

**What happened:**
- SHARP picks showing 0% hit rate across all sports (NBA 0/14, NHL 0/8, NCAAB 0/7)
- Made the sharp signal feature appear broken

**Impact:** SHARP picks incorrectly graded, learning loop getting bad data

**Root cause:**
- SHARP picks stored `line_variance` (movement amount like 1.5) in the `line` field
- Grading logic treated `line` as actual spread
- Example: line_variance=1.5 meant "Lakers +1.5 spread" instead of actual spread

**Fix:**
- Grade SHARP picks as moneyline only (who won the game)
- Ignore the `line` field since it contains variance, not actual spread:
  ```python
  elif "sharp" in pick_type_lower:
      # ALWAYS grade as moneyline - line field is line_variance
      if picked_home:
          return ("WIN" if home_score > away_score else "LOSS"), 0.0
  ```

**Lesson:**
- NEVER store `line_variance` in a field named `line` - they have different meanings
- NEVER assume a field contains what its name suggests - trace data flow
- Always verify grading logic with actual data examples
- When pick types behave unexpectedly, check what data is actually stored

---

### 12. Unsurfaced Scoring Adjustments Break Sanity Math (Feb 4, 2026)

**What happened:**
- `endpoint_matrix_sanity.sh` math check showed diff=0.748 (threshold 0.02)
- `totals_calibration_adj` (±0.75 from v20.4) was applied to `final_score` but NOT surfaced as a pick payload field
- The sanity script recomputes final_score from surfaced fields, so the hidden adjustment caused a mismatch

**Impact:** Go/no-go gate blocked, math check appeared broken

**Root cause:** When `TOTALS_SIDE_CALIBRATION` was added (v20.4), the adjustment was applied to `final_score` via a local variable but never added to the pick output dict. The sanity formula couldn't account for it.

**Fix:**
1. Added `"totals_calibration_adj": round(totals_calibration_adj, 3)` to pick output dict in `live_data_router.py`
2. Updated jq formula in `endpoint_matrix_sanity.sh` to include `+ ($p.totals_calibration_adj // 0)`

**Lesson:**
- **INVARIANT:** Every adjustment to `final_score` MUST be surfaced as its own named field in pick payloads
- When adding a new scoring adjustment, update: (1) pick dict, (2) sanity formula, (3) CLAUDE.md Boost Inventory, (4) canonical formula
- The endpoint matrix math check exists to catch exactly this class of bug

---

### 13. Script-Only Env Vars Need RUNTIME_ENV_VARS Registration (Feb 4, 2026)

**What happened:**
- `env_drift_scan.sh` failed because `MAX_GAMES`, `MAX_PROPS`, and `RUNS` were used in scripts but not registered in `RUNTIME_ENV_VARS`
- These variables seemed "unimportant" because they were only used by test/sanity scripts

**Impact:** Go/no-go gate blocked on env_drift check

**Root cause:** The env drift scan intentionally scans ALL `.sh` and `.py` files for env var references. Any env var used anywhere must be registered.

**Fix:** Added all three to `RUNTIME_ENV_VARS` in `integration_registry.py` in alphabetical order.

**Lesson:**
- ANY env var referenced in ANY file must be in either `INTEGRATION_CONTRACTS` or `RUNTIME_ENV_VARS`
- Run `bash scripts/env_drift_scan.sh` after adding env vars to scripts
- The scan is intentionally aggressive - register everything

---

### 14. Python Heredoc `__file__` Path Resolution Bug (Feb 4, 2026)

**What happened:**
- `prod_endpoint_matrix.sh` failed with `FileNotFoundError: ../docs/ENDPOINT_MATRIX_REPORT.md`
- The script used `os.path.dirname(__file__)` inside a `python3 - <<'PY'` heredoc

**Impact:** Go/no-go gate blocked (prod_endpoint_matrix check failed)

**Root cause:** Inside Python heredocs, `__file__` resolves to `"<stdin>"`, so `os.path.dirname(__file__)` returns empty string `""`. The constructed path `os.path.join("", "..", "docs", ...)` resolved incorrectly.

**Fix:** Changed to project-relative path: `os.path.join("docs", "ENDPOINT_MATRIX_REPORT.md")` - works because shell scripts run from project root.

**Lesson:**
- NEVER use `__file__`, `os.path.dirname(__file__)`, or `Path(__file__)` inside Python heredocs
- In heredocs, always use project-relative paths
- Test heredoc scripts by running them directly: `bash scripts/script_name.sh`

---

### 16. Session 7 SHARP Fallback Detection Bug (Feb 8, 2026)

**What happened:**
- CI spot check Session 7 (`scripts/spot_check_session7.sh`) failed with: `❌ FAIL: games returned but no game events analyzed (and not all SHARP)`
- Debug output showed: `events_after_games=0, games_returned=1, sharp_picks=0`
- Script was checking `pick_type == "SHARP"` to detect SHARP fallback picks
- But SHARP fallback picks have `pick_type` set to the bet type ("spread", "moneyline"), not "SHARP"

**Impact:** Session 7 CI check falsely failed when SHARP fallback picks were returned (valid scenario when Odds API has no events but Playbook API has sharp signals)

**Root cause:**
- SHARP fallback picks are created when `raw_games` is empty after ET filtering but Playbook API has sharp money signals
- These picks have `market: "sharp_money"` as the identifier
- The `pick_type` field is set to the bet type (e.g., "spread" for spread bets)
- Script incorrectly looked for `pick_type == "SHARP"` which never exists

**Fix:**
Changed detection from `pick_type` to `market` field:
```bash
# Before (WRONG):
SHARP_PICKS="$(echo "$RAW" | jq -r '[.game_picks.picks[] | select(.pick_type == "SHARP")] | length')"

# After (CORRECT):
SHARP_MARKET_PICKS="$(echo "$RAW" | jq -r '[.game_picks.picks[] | select(.market == "sharp_money")] | length')"
```

**Lesson:**
- SHARP fallback picks are identified by `market == "sharp_money"`, NOT by `pick_type`
- `pick_type` always contains the bet type (spread/moneyline/total), not the signal source
- When validating pick types, always trace back to where the field is set in `live_data_router.py`

**Commit:** `f2dc80b`

---

### 15. Technical Debt Cleanup: 5-Item Audit Resolution (Feb 4, 2026)

**What happened:**
- Learning Audit Report identified 5 technical debt items across storage, observability, and live betting
- All 5 items resolved in a single coordinated cleanup

**Items resolved:**

1. **mark_graded() append-only violation (HIGH)** — `grader_store.py` was rewriting entire `predictions.jsonl` on every grade. Now grades are appended to a separate `graded_picks.jsonl` file; `predictions.jsonl` is never modified. `load_predictions()` merges grade records at read time. Corrupted partial writes are skipped gracefully.

2. **Odds staleness guard (MEDIUM)** — Added `ODDS_STALENESS_THRESHOLD_SECONDS = 120` to `scoring_contract.py`. Live endpoints now track `odds_fetched_at` and compute `odds_age_seconds`. Stale odds are flagged and `live_adjustment` is suppressed.

3. **Market suspended detection (MEDIUM)** — Live endpoints now detect suspended markets using the heuristic: if `odds_american` is None AND `book` is falsy, the market is suspended. Each live pick includes a `market_status` field.

4. **Training drop telemetry (LOW)** — `auto_grader.py` now tracks drop reasons in `last_drop_stats` dict (unsupported_sport, below_score_threshold, duplicate_id, missing_pick_id, conversion_failed). Exposed via `/grader/status`.

5. **Weight version hash (LOW)** — `/grader/status` now includes `weights_version_hash` (SHA256[:12] of weights.json content), `weights_file_exists`, and `weights_last_modified_et`.

**Files modified:**
- `storage_paths.py` — Added `get_graded_picks_file()`
- `grader_store.py` — Rewrote `mark_graded()`, updated `load_predictions()` to merge grades
- `core/scoring_contract.py` — Added `ODDS_STALENESS_THRESHOLD_SECONDS`
- `auto_grader.py` — Added `last_drop_stats` tracking
- `main.py` — Added weight hash + drop stats to `/grader/status`
- `live_data_router.py` — Added odds staleness + market status to live endpoints
- `tests/test_tech_debt_cleanup.py` — 19 tests covering all 5 items

**Lesson:**
- Append-only storage patterns are safer than read-modify-write for crash resilience
- Always separate mutable data (grades) from immutable data (predictions)
- Telemetry for dropped training data helps diagnose learning loop issues
- When fixing multiple related items, coordinate in a single pass to avoid drift

---
