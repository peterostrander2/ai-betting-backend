# CLAUDE CODE SESSION BEHAVIOR

**Context Management (READ FIRST):**
- Do NOT auto-summarize or compact conversation history unless explicitly requested
- Prefer retaining full context over aggressive summarization
- When approaching context limits, ASK the user before compacting
- Prioritize: (1) current task, (2) recent changes, (3) active file contents
- Do NOT re-read files already in context - reference what you have
- If you need to compact, preserve: invariants, current task state, recent code changes

**Session Efficiency:**
- Skip re-reading CLAUDE.md sections already loaded
- Use grep/search instead of reading entire files when looking for specific content
- Batch related changes together rather than one file at a time

---

## 📁 COMPANION FILES (Load When Needed)

| File | Contents | When to Load |
|------|----------|--------------|
| `docs/ML_REFERENCE.md` | LSTM models, GLITCH protocol, file index | When working on ML/scoring |
| `docs/LESSONS_LEARNED.md` | 50+ historical bugs & fixes | When debugging a similar issue |
| `docs/NEVER_DO.md` | 33 consolidated rule sets | Before modifying that subsystem |
| `docs/CHECKLISTS.md` | 17 verification checklists | Before deploying changes |
| `docs/SESSION_NOTES.md` | Codex DNS & troubleshooting | If hitting infra issues |

**How to use:** When working on ML models, run `cat docs/NEVER_DO.md | grep -A 20 "ML & GLITCH"` to load just that section.

---



## Sister Repositories

| Repo | Purpose | URL |
|------|---------|-----|
| **This repo** | Backend API (Python/FastAPI) | [ai-betting-backend](https://github.com/peterostrander2/ai-betting-backend) |
| **Frontend** | Member dashboard (React/Vite) | [bookie-member-app](https://github.com/peterostrander2/bookie-member-app) |

**Production:** https://web-production-7b2a.up.railway.app

**Frontend Integration Guide:** See `docs/FRONTEND_INTEGRATION.md` for backend→frontend field mapping and pending frontend work.

---


## 📚 MASTER INDEX (Quick Reference)

### Critical Invariants (26 Total)
| # | Name | Summary |
|---|------|---------|
| 1 | Storage Persistence | ALL data under `RAILWAY_VOLUME_MOUNT_PATH=/data` |
| 2 | Titanium 3-of-4 Rule | `titanium=true` ONLY when ≥3 of 4 engines ≥8.0 |
| 3 | ET Today-Only Gating | ALL picks for games in today's ET window ONLY |
| 4 | Option A Scoring | 4-engine base (AI 25%, Research 35%, Esoteric 15%, Jarvis 25%) + context modifier |
| 5 | Jarvis Additive | Jarvis is weighted engine, NOT separate boost |
| 6 | Output Filtering | `final_score >= 6.5` required for output |
| 7 | Contradiction Gate | Never output both Over AND Under on same line |
| 8 | Best-Bets Contract | Response MUST have `props.picks[]` and `game_picks.picks[]` |
| 9 | Pick Persistence | Picks logged to grader_store for learning loop |
| 9.1 | Two Storage Systems | grader_store (picks) + weights.json (learning) |
| 10 | Frontend-Ready | Human-readable times, no internal IDs |
| 11 | Integration Contract | ESPN/Playbook field mapping |
| 12 | Logging Visibility | Keep INFO telemetry for debugging |
| 13 | PickContract v1 | Frontend-proof picks with all required fields |
| 14 | ML Model Activation | LSTM + Ensemble models active |
| 15 | GLITCH Protocol | 6 signals: chrome_resonance, void_moon, noosphere, hurst, kp_index, benford |
| 16 | 18-Pillar Scoring | All 18 pillars active (see detailed list) |
| 17 | Harmonic Convergence | +1.5 boost when Research AND Esoteric ≥7.5 |
| 18 | Secret Redaction | API keys never in logs |
| 19 | Demo Data Hard Gate | Block demo/test data in production |
| 20 | MSRF Boost | ±1.0 cap on MSRF adjustments |
| 21 | Dual-Use Functions | Must return dicts (not Response objects) |
| 22 | ESPN Integration | Injuries, officials, lineups from ESPN |
| 23 | SERP Intelligence | Web search boost capped at 4.3 |
| 24 | Trap Learning Loop | Daily trap evaluation and weight adjustment |
| 25 | Complete Learning | End-to-end grading → bias → weight updates |
| 26 | Total Boost Cap | Sum of confluence+msrf+jason+serp capped at 1.5 |

### Lessons Learned (87 Total) - Key Categories
| Range | Category | Examples |
|-------|----------|----------|
| 1-5 | Code Quality | Dormant code, orphaned signals, weight normalization |
| 6-7 | Security | Secret leakage, demo data |
| 8-15 | Integration | MSRF, ESPN, API mismatches |
| 16-22 | Team/Data | NHL accents, NCAAB expansion, pick_type values |
| 23-28 | Signals | Benford, officials, trap learning |
| 29-31 | Datetime | Timezone awareness, variable initialization |
| 32-38 | **v20.x Learning Loop** | Grader weights, SHARP/MONEYLINE grading, OVER/UNDER calibration |
| 39 | **Frontend Sync** | Option A tooltip alignment (weights must match scoring_contract.py) |
| 40 | **Shell/Python** | Export variables for Python subprocesses (`export VAR=value`) |
| 41 | **Grading Bug** | SHARP picks: line_variance ≠ actual spread (grade as moneyline) |
| 42-45 | **v20.5 Datetime/Grader** | Naive vs aware datetime, PYTZ undefined, date window math |
| 46-48 | **v20.5 Scoring/Scripts** | Unsurfaced adjustments, env var registry, heredoc __file__ |
| 49-52 | **v20.6 Production Fixes** | Props timeout, empty descriptions, score inflation (total boost cap), Jarvis baseline |
| 53 | **v20.7 Performance** | SERP sequential bottleneck: parallel pre-fetch pattern for external API calls |
| 54 | **v20.8 Props Dead Code** | Indentation bug made props_picks.append() unreachable — ALL sports returned 0 props |
| 55 | **v20.9 Missing Endpoint** | Frontend called GET /picks/graded but endpoint didn't exist; MOCK_PICKS masked the 404 |
| 56 | **v20.10 SHARP Field** | `signal.get("side")` should be `signal.get("sharp_side")` — wrong team graded |
| 57-60 | **v20.11 Real Data Sources** | NOAA Kp-index, ESPN live scores, Improved void moon, LSTM Playbook API training |
| 61 | **v20.11 Rivalry Database** | Comprehensive MAJOR_RIVALRIES expansion: 204 rivalries covering all teams in 5 sports |
| 62 | **v20.11 Post-Base Signals** | Hook/Expert/Prop signals mutated research_score AFTER base_score — NO EFFECT on final_score |
| 63 | **v20.12 Dormant Features** | Stadium altitude, travel fatigue fix, gematria twitter, officials tendency fallback |
| 64 | **v20.12 CI Partial-Success** | Spot checks must distinguish fatal errors from partial-success (timeouts with valid picks) |
| 65 | **v20.12 SERP Quota** | SERP burned 5000 searches/month — disabled by default, per-call APIs need explicit opt-in |
| 66-67 | **v20.13 Learning Loop Coverage** | SPORT_STATS only had 3 props per sport — expanded to all 7 for complete learning coverage |
| 68 | **v20.13 Robust Shell Script Error Handling** | Daily sanity report failed silently on non-JSON responses — added HTTP status capture and JSON validation |
| 69 | **v20.13 Auto-Grader Field Mismatch** | `_convert_pick_to_record()` read `sharp_money` but picks store `sharp_boost` — learning loop got 0.0 for all research signals |
| 70 | **v20.13 GOLD_STAR Gate Labels** | Gate labels said `research_gte_5.5`/`esoteric_gte_4.0` but actual thresholds are 6.5/5.5 — misleading downgrade messages |
| 71 | **v20.14 Grader Routes & Authentication** | Grader endpoints need `/live` prefix + API key — routes mounted at `/live/*`, public URLs require auth |
| 72 | **v20.15 Prop Detection Bug** | Props stored as `market="player_points"` without `pick_type`, auto-grader check `in ("PROP", "PLAYER_PROP")` missed them — learning loop got 0 prop samples |
| 73 | **v20.15 Incomplete Prop Markets** | Only 4 NBA props fetched (points/rebounds/assists/threes), missing steals/blocks/turnovers — "if we bet on it, we track it" |
| 74 | **v20.16 "Trained But Isn't"** | `is_trained=True` based on file existence, not actual training samples — sklearn models never fitted, predict() crashes |
| 75 | **v20.16.3 Training Visibility** | No way to prove training executed — added `/debug/training-status` with artifact_proof, training_health, telemetry |
| 76 | **v20.16.5 Engine 2 Anti-Conflation** | sharp_strength and lv_strength were conflated — now separate with source_api attribution |
| 77 | **v20.16.6 Odds Fallback Conflation** | When Playbook unavailable, signal_strength from variance polluted sharp_strength — explicit NONE now |
| 78 | **v20.16.7 XGBoost Feature Mismatch** | Model trained on 12 scoring features but runtime passed 6 context features — validate count before predict |
| 79 | **v20.16.8 Daily Report Missing NCAAB** | Sports loop hardcoded [NBA,NFL,MLB,NHL] without NCAAB — 64 graded picks not showing in report |
| 80 | **v20.16.9 Training Filter Telemetry** | Training showed 41 samples but no proof they were legitimate — added filter_counts with drop reasons + sample_pick_ids |
| 81 | **v20.17.3 Training Telemetry Path** | `training_telemetry` is at TOP level of `get_model_status()`, NOT inside `"ensemble"` dict — endpoint read wrong path, showed NEVER_RAN when healthy |
| 82 | **v20.17.3 Attribution Buckets** | 950 picks had "unknown" missing model_preds — added `heuristic_fallback` and `empty_raw_inputs` buckets for proper diagnosis |
| 83 | **v20.17.3 Empty Dict Conditionals** | `if filter_telemetry:` is False for empty dict `{}` — training signatures not stored if passed as empty; check explicitly |
| 84 | **v20.18 Engine 3 Behavior Creep** | Activated dormant signals during audit task — audit = observe, not modify; use hard weight assertions |
| 85 | **ENGINE 4 v2.2.1 Scale Factor Calibration** | SF=4.0 showed 96% -bias; calibrate SF based on `mean(msrf)/mean(jarvis)` ratio; check side-balance not just saturation rate |
| 86 | **v20.19 Engine Weight Rebalancing** | Weight changes required 16+ file updates due to duplicates — use single source of truth (scoring_contract.py), import don't duplicate |
| 87 | **v20.19 Test Field Name Drift** | Test expected `ophis_normalized` but impl uses `ophis_score_norm` — copy field names from implementation output, don't invent them |
| 88 | **v20.20 Never Loosen Regression Gates** | Gate failed on MONITOR tier — fix production (add HIDDEN_TIERS filter), don't add MONITOR to valid_tiers |
| 89 | **v20.20 Golden Run Gate Design** | Validate contracts not volatile data; separate thresholds (props 6.5, games 7.0); unit + live tests |
| 90 | **v20.20 Two Threshold Systems** | Internal tier assignment (EDGE_LEAN ≥6.5) vs API output (games 7.0, props 6.5); use canonical field name `final_score` |

### NEVER DO Sections (39 Categories)
- ML & GLITCH (rules 1-10)
- MSRF (rules 11-14)
- Security (rules 15-19)
- FastAPI & Functions (rules 20-25)
- Nested Functions (rules 26-30)
- API & Data (rules 31-40)
- ESPN Integration (rules 41-55)
- SERP Intelligence (rules 56-65)
- Esoteric/Phase 1 (rules 66-80)
- v17.6 Vortex & Benford (rules 81-90)
- v19.0 Trap Learning (rules 91-100)
- v18.2 Phase 8 Esoteric (rules 101-110)
- Boost Field Contract (rules 105-107)
- v20.2 Auto Grader Weights (rules 108-117)
- v20.x Two Storage Systems (rules 111-117)
- v20.3 Grading Pipeline (rules 118-124)
- v20.4 Go/No-Go Scripts (rules 125-131)
- v20.4 Frontend/Backend Sync (rules 132-137)
- Shell/Python Subprocesses (rules 138-141)
- v20.5 Datetime/Timezone (rules 142-150)
- v20.5 Go/No-Go & Scoring Adjustments (rules 151-155)
- v20.6 Boost Caps & Production (rules 156-163)
- v20.7 Parallel Pre-Fetch & Performance (rules 164-172)
- v20.8 Props Indentation & Code Placement (rules 173-177)
- v20.9 Frontend/Backend Endpoint Contract (rules 178-181)
- v20.11 Real Data Sources (rules 182-191)
- v20.11 Rivalry Database (rules 192-197)
- v20.11 Post-Base Signals Architecture (rules 198-202)
- v20.12 Dormant Features & API Timing Fallbacks (rules 203-207)
- v20.12 CI Spot Checks & Error Handling (rules 208-212)
- v20.13 Learning Loop Coverage (rules 213-215)
- v20.13 Shell Script Error Handling (rules 216-219)
- v20.13 Field Name Mapping & Gate Label Drift (rules 220-226)
- v20.14 Grader Routes & Authentication (rules 227-229)
- v20.15 Learning Loop & Prop Detection (rules 230-236)
- v20.16.5+ Engine 2 Research Anti-Conflation (rules 237-244)
- v20.16.7 XGBoost Feature Consistency (rules 245-248)
- v20.16.8 Hardcoded Sports Lists (rules 249-251)
- v20.18.1 ENGINE 4 Calibration (rules 250-252)
- v20.19 Engine Weight Management (rules 253-258)
- v20.19 Test Field Name Contracts (rules 259-263)
- v20.20 Golden Run Regression Gates (rules 264-272)

### Deployment Gates (REQUIRED BEFORE DEPLOY)
```bash
# 1. Option A drift scan (blocks BASE_5, context-weighted patterns)
./scripts/option_a_drift_scan.sh

# 2. Audit drift scan (verifies scoring formula)
./scripts/audit_drift_scan.sh

# 3. Full CI sanity check
./scripts/ci_sanity_check.sh

# 4. Production Go/No-Go
./scripts/prod_go_nogo.sh

# 5. Golden Run regression gate (unit tests)
pytest tests/test_golden_run.py -v

# 6. Post-deploy: Golden Run live validation
API_KEY=your_key python3 scripts/golden_run.py check

# 7. Post-deploy: Verify grader routes (run from Railway shell)
./scripts/verify_grader_routes.sh
```

### 🛡️ Prevention Checklist (BEFORE WRITING CODE)

**Scan this checklist before ANY code change to avoid repeating past mistakes:**

#### Data & API
- [ ] **Field names match source** — Trace back to where data is created (e.g., `sharp_side` not `side`)
- [ ] **Working APIs are wired** — If an API implementation exists, call it (don't leave simulations)
- [ ] **Real data before synthetic** — Try real data sources with graceful fallback
- [ ] **Surface all adjustments** — Every `final_score` adjustment needs a payload field

#### Code Structure
- [ ] **Initialize before conditionals** — Variables used after `if` blocks must be initialized before
- [ ] **Update ALL call sites** — When adding function parameters, grep for all callers
- [ ] **Code placement matters** — `break` and `return` positioning affects reachability
- [ ] **Copy-paste variable names** — Never type dict keys from memory

#### Datetimes & Timezones
- [ ] **Both sides timezone-aware** — Can't subtract naive from aware datetime
- [ ] **ET for user-facing, UTC for storage** — Use `core/time_et.py` only
- [ ] **Date math is correct** — yesterday = today - 1 day (not 2)

#### Environment & Config
- [ ] **Env var logic correct** — `any()` for alternatives, `all()` for required
- [ ] **Script vars in registry** — Add script-only env vars to `RUNTIME_ENV_VARS`
- [ ] **Heredocs use explicit paths** — `__file__` doesn't work in heredocs

#### Scoring & Boosts
- [ ] **TOTAL_BOOST_CAP = 1.5** — Sum of confluence+msrf+jason+serp is capped
- [ ] **Jarvis baseline is 4.5** — Sacred triggers are rare by design
- [ ] **pick_type values** — Game picks use "SPREAD"/"MONEYLINE"/"TOTAL", not "GAME"

#### Frontend/Backend Contract
- [ ] **Endpoint exists before calling** — Verify backend route exists before frontend API method
- [ ] **No silent fallbacks** — Don't use mock data that looks real (masks bugs)
- [ ] **Weights match** — Frontend tooltips must match `scoring_contract.py`

#### Grading & Learning
- [ ] **SHARP graded as moneyline** — Did the team win? (not line_variance)
- [ ] **All stat types in weights** — Auto grader needs complete structure
- [ ] **Comprehensive data coverage** — Cover ALL teams/types, not just popular ones
- [ ] **Field names match write↔read** — `_convert_pick_to_record()` must use same keys as `persist_pick()` (e.g., `sharp_boost` not `sharp_money`)
- [ ] **Gate labels match contract** — Threshold labels in `live_data_router.py` must match `scoring_contract.py` values (grep after any threshold change)
- [ ] **Prop detection is robust** — Check `pick_type`, `market` prefix (PLAYER_), AND `player_name` presence (not just one field)
- [ ] **Prop configs in sync** — `prop_markets`, `prop_stat_types` (2x), `SPORT_STATS`, `STAT_TYPE_MAP` must ALL match
- [ ] **Verify learning sees data** — `/grader/bias/{sport}?stat_type={stat}` must show `sample_size > 0`

#### CI & Testing Scripts
- [ ] **Distinguish fatal vs partial errors** — Timeout with picks = partial success, not failure
- [ ] **Check actual data presence** — Count picks before deciding on error severity
- [ ] **Handle off-season gracefully** — 0 picks is valid when no games scheduled
- [ ] **Allow transient failures** — HTTP 502 during deploy is temporary; retry helps

#### Tests & Schema (v20.19)
- [ ] **Test field names match implementation** — Copy from actual output dict, never invent field names
- [ ] **Check edge case behavior** — Test what `func(empty_inputs)` ACTUALLY returns, not assumed behavior
- [ ] **Update tests with schema changes** — When output dict changes, update test assertions IMMEDIATELY
- [ ] **Internal vars ≠ output fields** — Local variables like `jarvis_boost` are NOT in output dict

#### Regression Gates (v20.20)
- [ ] **Never loosen gate to match bug** — Gate fails → fix production, don't add failing value to valid set
- [ ] **HIDDEN_TIERS filter at output** — MONITOR/PASS are internal, never returned to API
- [ ] **Separate thresholds by type** — Props use 6.5, games use 7.0 (don't collapse)
- [ ] **Valid output tiers only** — `{TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN}`, nothing else
- [ ] **Run golden run after changes** — `pytest tests/test_golden_run.py -v` before deploy

### Key Files Reference
| File | Purpose |
|------|---------|
| `core/scoring_contract.py` | Scoring constants (Option A weights, thresholds, boost caps, calibration) |
| `core/scoring_pipeline.py` | Score calculation (single source of truth) |
| `live_data_router.py` | Main API endpoints, pick scoring, `/debug/training-status` (v20.16.3) |
| `utils/pick_normalizer.py` | Pick contract normalization (single source for all pick fields) |
| `auto_grader.py` | Learning loop, bias calculation, weight updates. **prop_stat_types** at lines 176 & 1109 |
| `daily_scheduler.py` | Cron jobs, **SPORT_STATS** config at line 174, team_model_train job at 7 AM ET |
| `team_ml_models.py` | TeamLSTM, TeamMatchup, GameEnsemble — training telemetry, `training_status` property |
| `scripts/train_team_models.py` | Training script for team ML models (called at 7 AM ET) |
| `result_fetcher.py` | Game result fetching, pick grading. **STAT_TYPE_MAP** at line 80 |
| `grader_store.py` | Pick persistence (predictions.jsonl) |
| `utils/contradiction_gate.py` | Prevents opposite side picks |
| `integration_registry.py` | Env var registry, integration config |
| `signals/physics.py` | Kp-index via NOAA API (v20.11) — was simulation, now real data |
| `signals/hive_mind.py` | Void moon with Meeus calculation (v20.11) — improved accuracy |
| `lstm_training_pipeline.py` | LSTM training with Playbook API data (v20.11) — real data fallback |
| `alt_data_sources/noaa.py` | NOAA Space Weather API client (Kp-index, X-ray flux) |
| `scripts/spot_check_session8.sh` | Grading & persistence + multi-sport smoke tests (partial-success handling v20.12) |
| `scripts/ci_sanity_check.sh` | Full CI sanity check — runs all 10 session spot checks |
| `scripts/prod_go_nogo.sh` | Production go/no-go validation before deploy |
| `scripts/verify_grader_routes.sh` | Grader routes verification — tests all `/live/grader/*` endpoints (v20.14) |
| `tests/test_training_status.py` | Training pipeline visibility tests (13 tests) — v20.16.3 |
| `tests/test_ai_model_usage.py` | AI model safety tests including `TestEnsembleStackingModelSafety` — v20.16.1 |
| `core/research_types.py` | ComponentStatus enum (SUCCESS/NO_DATA/ERROR/DISABLED), source constants — v20.16.5 |
| `docs/RESEARCH_TRUTH_TABLE.md` | Engine 2 Research contract: 6 components, sources, anti-conflation rules — v20.16.5 |
| `tests/test_research_truthfulness.py` | 21 anti-conflation tests: sharp/line separation, source attribution — v20.16.5 |
| `scripts/engine2_research_audit.py` | Runtime verification: research_breakdown, usage counters, source APIs — v20.16.5 |
| `scripts/engine2_research_audit.sh` | Static + runtime checks: conflation patterns, object separation — v20.16.5 |
| `core/jarvis_ophis_hybrid.py` | ENGINE 4 Jarvis-Ophis hybrid blend — v2.2.1 with OPHIS_SCALE_FACTOR calibration |
| `core/jarvis_score_api.py` | Shared Jarvis scoring module (single source of truth for savant + hybrid) — v2.1 |
| `docs/JARVIS_TRUTH_TABLE.md` | ENGINE 4 contract: blend formula, calibration table, invariants — v2.2.1 |
| `tests/test_engine4_jarvis_guards.py` | 34 guard tests: blend math, saturation flag, delta bounds — v2.2.1 |
| `tests/test_golden_run.py` | Golden run contract tests: weights, tiers, thresholds, hidden tier filter — v20.20 |
| `scripts/golden_run.py` | Golden run live validation script: capture, validate, check commands — v20.20 |
| `core/integration_contract.py` | Integration definitions with criticality tiers — v2.0.0 (v20.19) |
| `scripts/integration_gate.sh` | Production wire-level verification for integrations — v20.19 |
| `tests/test_pick_data_contract.py` | Pick schema validation tests (boundary contract tests) — v20.19 |

### Current Version: v20.20 (Feb 13, 2026)
**Latest Change (v20.20) — Golden Run Regression Gate + Hidden Tier Filter:**
- **Golden Run Gate:** New deployment gate validates contracts haven't drifted (tiers, thresholds, weights, Jarvis blend)
- **HIDDEN_TIERS Filter:** Added output filter `{"MONITOR", "PASS"}` in `live_data_router.py` — internal tiers never returned to API
- **Separate Thresholds:** Props use 6.5 (MIN_PROPS_SCORE), games use 7.0 (MIN_FINAL_SCORE)
- **Valid Output Tiers:** `{TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN}` only — MONITOR/PASS are internal workflow states
- **Key Lesson (88):** Never loosen regression gates to match production bugs — fix production instead
- **Files:** `live_data_router.py`, `scripts/golden_run.py`, `tests/test_golden_run.py`
- **Commits:** `8be10e7`, `ca6309a`

**Previous Change (v20.19) — Engine Weight Rebalancing:**
- **Jarvis (Engine 4):** 20% → 25% (increased to reflect calibrated hybrid blend value)
- **Esoteric (Engine 3):** 20% → 15% (reduced to compensate)
- **Total remains 100%:** AI 25% + Research 35% + Esoteric 15% + Jarvis 25% = 100%
- **Rationale:** Jarvis hybrid blend (v2.2.1) has proven reliable with calibrated scale factor; increased weight rewards system confidence in Engine 4
- **Files updated:** `core/scoring_contract.py`, `core/compute_final_score.py`, tests, CLAUDE.md

**Previous Fixes (v20.18.1) — ENGINE 4 Scale Factor Calibration (Lesson 85):**
- **Fix: OPHIS_SCALE_FACTOR calibrated to 5.0** — SF=4.0 showed 96% -bias (96% of saturations were -0.75 clamps). Root cause: `msrf_mean ≈ 0.97` vs `jarvis_mean ≈ 5.38` created systematic negative bias.
- **Calibration Table:**
  - SF=4.0: 37% sat, mean=-1.21, 4%/96% balance (strong -bias)
  - SF=5.0: 42% sat, mean=-0.31, 42%/58% balance (**SELECTED**)
  - SF=5.5: 57% sat, mean=+0.18, 61%/39% balance (high saturation)
- **Key Insight:** Saturation rate alone is misleading; must check side-balance. Low saturation with one-sided clamps indicates miscalibration.
- **Formula:** Target SF ≈ `jarvis_mean / msrf_mean` for centering
- **Key Files:** `core/jarvis_ophis_hybrid.py:73`, `docs/JARVIS_TRUTH_TABLE.md`
- **Commit:** `0cd8592 fix(engine4): calibrate OPHIS_SCALE_FACTOR to 5.0 for balanced saturation`

**Previous Fixes (v20.18) — Engine 3 Semantic Audit (Audit-Only Posture):**
- **Fix 1: Behavior Creep Revert (Lesson 84)** — Reverted activation of 4 dormant signals (golden_ratio, prime_resonance, phoenix_resonance, planetary_hour) that violated audit-only constraint. Audit = observe, not modify.
- **Fix 2: Weight Guard Hardening (Lesson 84)** — Changed weak assertion `assert total > 0.9` to hard assertion `assert abs(total - 1.05) < 0.001`. Prevents weight drift.
- **Fix 3: GLITCH Weight Restoration** — Restored original weights: chrome 0.25, void 0.20, noosphere 0.15, hurst 0.25, kp 0.25, benford 0.10.
- **Key Files:** `esoteric_engine.py`, `tests/test_engine3_esoteric_guards.py`, `docs/ESOTERIC_TRUTH_TABLE.md`
- **Invariant:** 23 wired signals, 6 dormant (code exists but NOT called in scoring path)
- **Commit:** `dfec72b fix(engine3): revert behavior creep; harden glitch weight guards`

**Previous Fixes (v20.17.3) — Engine 1 Training Telemetry Audit:**
- **Fix 1: Training Telemetry Path (Lesson 81)** — `/live/debug/training-status` was reading `status["ensemble"]["training_telemetry"]` but it should be `status["training_telemetry"]` (top level). Caused `training_health: "NEVER_RAN"` when training was healthy.
- **Fix 2: Attribution Buckets (Lesson 82)** — 950 picks had "unknown" missing model_preds. Added `heuristic_fallback` (ai_mode == HEURISTIC_FALLBACK) and `empty_raw_inputs` (game market with empty raw_inputs) buckets. Now `unknown: 0`.
- **Fix 3: Top-Level build_sha** — Added `build_sha` to training-status response for single-call validation.
- **Validation Command:** See "Training Status Validation" section below.
- **Key Files:** `scripts/audit_training_store.py`, `live_data_router.py:11370`, `docs/TRAINING_TRUTH_TABLE.md`

**Previous Fixes (v20.16.5/v20.16.6/v20.16.7) — Engine 2 Research Semantic Audit:**
- **Fix 1: Anti-Conflation (Lesson 76)** — `sharp_boost` and `line_boost` were both reading from same `sharp_signal` dict. Line variance was UPGRADING `signal_strength` to STRONG. Split into `playbook_sharp` (Playbook API only) and `odds_line` (Odds API only) objects that are NEVER merged.
- **Fix 2: Odds API Fallback (Lesson 77)** — When Playbook unavailable, fallback path set `sharp_strength` from line variance. Fixed: `sharp_strength: "NONE"` explicitly set in Odds API fallback since no Playbook data exists.
- **Fix 3: XGBoost Feature Mismatch (Lesson 78)** — Training used 12 features, runtime passed 6. Added feature count validation before predict; mismatches fall through to weighted average. Eliminated 48+ warnings per request.
- **New Files:** `core/research_types.py` (ComponentStatus enum), `tests/test_research_truthfulness.py` (21 tests), `scripts/engine2_research_audit.py|.sh` (verification)
- **Key Invariants:** `sharp_boost` ONLY from `playbook_sharp`, `line_boost` ONLY from `odds_line`. Source attribution: `sharp_source_api: "playbook_api"`, `line_source_api: "odds_api"`.

**Previous Enhancement (v20.16.4) — Automatic Training Verification:**
- **Enhancement: Training Verification Job** — Runs at 7:30 AM ET (30 min after training) to verify training executed. Checks `last_train_run_at`, `training_status`, and artifact mtimes. On failure: logs ERROR, writes alert to `/data/audit_logs/training_alert_{date}.json`.

**Previous Enhancement (v20.16.3) — Training Pipeline Visibility:**
- **Enhancement 1: Enhanced `/live/scheduler/status`** — Now shows all jobs with next_run_time_et, trigger_type, trigger, misfire_grace_time. Includes `training_job_registered` bool.
- **Enhancement 2: New `/live/debug/training-status`** — Returns model_status, training_telemetry, artifact_proof (file exists/size/mtime), scheduler_proof, training_health (HEALTHY/STALE/NEVER_RAN).
- **Tests:** 13 new tests in `tests/test_training_status.py`

**Previous Fixes (v20.16.1/v20.16.2) — Model Safety:**
- **Fix 1: Ensemble Hard Safety Rule (Lesson 74)** — Added `_ensemble_pipeline_trained` flag that ONLY becomes True after `train()` completes. Never call `.predict()` on unfitted sklearn models.
- **Fix 2: Truthful Training Status (Lesson 74)** — `is_trained` now requires actual training samples (`_trained_samples > 0`), not just file existence. Added `training_status` property: TRAINED | LOADED_PLACEHOLDER | INITIALIZING.
- **Fix 3: Training Telemetry** — `record_training_run()` writes `_last_train_run_at`, `_graded_samples_seen`, `_samples_used_for_training` to prove pipeline executed.

**Previous Fixes (v20.15) — 2 Updates:**
- **Fix 1: Auto-Grader Prop Detection (Lesson 72)** — Props stored with `market="player_points"` but no `pick_type` field. The check `in ("PROP", "PLAYER_PROP")` missed them. Fixed with expanded detection: `pick_type.startswith("PLAYER_")` or `player_name` presence. Learning loop now sees 63+ prop samples.
- **Fix 2: Expanded Prop Market Coverage (Lesson 73)** — Only 4 NBA props were fetched. Added: steals, blocks, turnovers. Also expanded NFL (anytime_td), MLB (runs, home_runs, outs), NHL (goals, saves). Updated all 4 config locations: `prop_markets`, `prop_stat_types` (2x), `SPORT_STATS`, `STAT_TYPE_MAP`.

**Previous Fixes (v20.14) — 1 Update:**
- **Fix: Grader Routes Documentation (Lesson 71)** — All grader endpoints require `/live` prefix (routes are mounted at `/live/*` in main.py). Public URLs also require `X-API-Key` header. Added comprehensive verification script `scripts/verify_grader_routes.sh` with 6 test suites.

**Previous Fixes (v20.13) — 4 Updates:**
- **Fix 1: Learning Loop Coverage (Lessons 66-67)** — `SchedulerConfig.SPORT_STATS` expanded NBA from 3 to 7 prop types (added threes, steals, blocks, pra). Auto grader now tracks and adjusts weights for ALL prop types, not just the "big 3" (points, rebounds, assists).
- **Fix 2: Robust Shell Script Error Handling (Lesson 68)** — Daily sanity report script improved with HTTP status capture, JSON validation, and proper error handling for non-JSON responses.
- **Fix 3: Auto-Grader Field Name Mismatch (Lesson 69)** — `auto_grader.py:_convert_pick_to_record()` read `sharp_money`/`public_fade`/`line_variance` from `research_breakdown`, but picks store as `sharp_boost`/`public_boost`/`line_boost`. Daily learning loop always saw 0.0 for research signals. Fixed with fallback pattern.
- **Fix 4: GOLD_STAR Gate Labels (Lesson 70)** — Gate labels said `research_gte_5.5`/`esoteric_gte_4.0` but actual thresholds in `scoring_contract.py` are 6.5/5.5. Labels in `live_data_router.py` and docs now match contract.

**Previous Enhancements (v20.12) — 5 Updates:**
- **Enhancement 1: Stadium Altitude Impact (Lesson 63)** — `live_data_router.py` now calls `alt_data_sources/stadium.py` for NFL/MLB high-altitude venues (Denver 5280ft, Utah 4226ft). Adds esoteric scoring boost when altitude >1000ft.
- **Enhancement 2: Travel Fatigue Fix (Lesson 63)** — Fixed bug where `rest_days` variable was undefined. Now uses `_rest_days_for_team(away_team)` closure.
- **Enhancement 3: Gematria Twitter Intel** — Already wired at `live_data_router.py:4800-4842`, just needed `SERPAPI_KEY` env var. No code changes required.
- **Fix 4: CI Partial-Success (Lesson 64)** — Session 8 spot check now distinguishes fatal errors from partial-success (timeout with valid picks). Scripts must check both error codes AND pick counts.
- **Fix 5: SERP Quota (Lesson 65)** — SERP disabled by default (`SERP_INTEL_ENABLED=false`). Per-call APIs need explicit opt-in to prevent quota exhaustion.

**Previous Enhancements (v20.11) — 5 Key Updates:**
- **Enhancement 1: NOAA Space Weather (Lesson 57)** — `signals/physics.py` now calls `alt_data_sources/noaa.py:get_kp_betting_signal()` for real Kp-Index data instead of time-based simulation
- **Enhancement 2: Live Game Signals (Lesson 58)** — `live_data_router.py` extracts live scores from ESPN scoreboard and passes to `calculate_pick_score()` for in-game adjustments
- **Enhancement 3: Void Moon Improved (Lesson 59)** — `signals/hive_mind.py:get_void_moon()` now uses Meeus-based lunar ephemeris with synodic month and perturbation correction
- **Enhancement 4: LSTM Real Data (Lesson 60)** — `lstm_training_pipeline.py` now tries Playbook API game logs via `build_training_data_real()` before falling back to synthetic data
- **Fix 5: Post-Base Signals (Lesson 62)** — Hook/Expert/Prop signals were mutating `research_score` AFTER base_score (no effect). Fixed by wiring as explicit parameters to `compute_final_score_option_a()`

**Previous Fix (v20.10):**
- Lesson 56: SHARP signal field name mismatch — `signal.get("side")` should be `signal.get("sharp_side")`
- Root cause: Signal dictionary uses `sharp_side` but pick creation used `side`, causing all SHARP picks to be treated as HOME team
- Fix: Changed all `signal.get("side")` to `signal.get("sharp_side")` with lowercase comparison

**Previous Fix (v20.9):**
- Lesson 55: Frontend Grading page called `GET /live/picks/graded` but endpoint didn't exist — frontend fell back to MOCK_PICKS silently
- Root cause: `api.js` had `getGradedPicks()` calling a non-existent endpoint; backend only had `POST /picks/grade` and `GET /picks/grading-summary`
- Fix: Added `GET /picks/graded` endpoint using `grader_store.load_predictions()`, updated `Grading.jsx` to remove mock fallback, fixed `pick_id` usage

**Previous Fix (v20.8):**
- Lesson 54: CRITICAL — Props indentation bug made `props_picks.append()` unreachable dead code; ALL sports returned 0 props
- Root cause: `if _props_deadline_hit: break` placed BETWEEN `calculate_pick_score()` and prop processing code
- Fix: Moved deadline check AFTER `props_picks.append()` so each prop is fully processed before checking the deadline

**Previous Fix (v20.7):**
- Lesson 53: SERP sequential bottleneck — parallel pre-fetch reduces ~17s to ~2-3s, fixes props returning 0 picks
- Performance: `serp_prefetch` timing now in debug telemetry (`debug.serp.prefetch_cached`)

**Previous Fixes (v20.6):**
- Lesson 49: Props timeout — TIME_BUDGET_S configurable, increased 40→55s default
- Lesson 50: Empty description fields — auto-generated in `normalize_pick()`
- Lesson 51: Score inflation — TOTAL_BOOST_CAP = 1.5 prevents boost stacking to 10.0
- Lesson 52: Jarvis baseline misconception — 4.5 baseline is by design (sacred triggers are rare)
- Invariant 26: Total Boost Cap enforcement in `compute_final_score_option_a()`

**Previous Fixes (v20.5):**
- Lesson 41: SHARP pick grading fix (grade as moneyline, not line_variance)
- Lesson 42: PYTZ_AVAILABLE undefined in `/grader/queue`
- Lesson 43: Naive vs aware datetime in `/grader/daily-report`
- Lesson 44: Date window math error (2-day instead of 1-day)
- Lesson 45: Same datetime bug in `/grader/performance`

**All Grader Endpoints Verified Working (Feb 10, 2026):**

**IMPORTANT:** All grader endpoints require the `/live` prefix and `X-API-Key` header for authentication.

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/live/grader/status` | GET | Grader availability, storage health, predictions count | ✅ |
| `/live/grader/weights/{sport}` | GET | Learned weights per stat type | ✅ |
| `/live/grader/bias/{sport}` | GET | Bias analysis with factor correlations | ✅ |
| `/live/grader/run-audit` | POST | Trigger manual audit | ✅ |
| `/live/grader/performance/{sport}` | GET | Performance metrics by stat type | ✅ |
| `/live/grader/queue` | GET | Pending picks for grading | ✅ |
| `/live/grader/daily-report` | GET | Daily grading summary | ✅ |
| `/live/grader/train-team-models` | POST | Manual trigger for team model training | ✅ (v20.16) |
| `/live/picks/graded` | GET | Graded picks for frontend | ✅ (v20.9) |
| `/live/picks/grade` | POST | Grade a single pick | ✅ |
| `/live/picks/grading-summary` | GET | Stats by tier | ✅ |
| `/live/scheduler/status` | GET | Scheduler jobs with next_run_time_et | ✅ (v20.16.3) |
| `/live/debug/training-status` | GET | Training status with artifact proof | ✅ (v20.16.3) |

**Verification Script:** `scripts/verify_grader_routes.sh` — Tests all grader endpoints in Railway shell.

**Training Health States (v20.16.3):**

| State | Condition | Action |
|-------|-----------|--------|
| `HEALTHY` | Training ran within 24h OR no graded picks | Normal operation |
| `STALE` | Training older than 24h AND graded picks > 0 | Check scheduler, may need manual trigger |
| `NEVER_RAN` | last_train_run_at null AND graded picks > 0 | Training pipeline never executed, trigger manually |

**Production Test Results (Feb 8, 2026):**
- `/live/grader/status` — available: true, 1310+ predictions logged
- `/live/grader/weights/NBA` — All stat types with weights (defense, pace, vacuum, lstm)
- `/live/grader/bias/NBA` — 566 samples, 58% hit rate
- `/live/grader/performance/NBA` — 137 graded, 53.3% hit rate
- `/live/grader/run-audit` — audit_complete with NBA/NHL results

**Frontend Integration (Priority 1-5 COMPLETE):**
- Context score displayed with correct tooltip (modifier ±0.35)
- Harmonic Convergence badge (purple) when Research + Esoteric ≥7.5
- MSRF Turn Date badge when msrf_boost > 0
- Context Layer expandable details (def_rank, pace, vacuum, officials)

**Active Calibration:**
```python
TOTALS_SIDE_CALIBRATION = {
    "enabled": True,
    "over_penalty": -0.75,
    "under_boost": 0.75,
}
```

---


## Code Style & Simplification Rules

**Apply these automatically when writing or modifying code:**

### Preserve Functionality
- Never change what code does - only how it does it
- All original features, outputs, and behaviors must remain intact

### Clarity Over Brevity
- **AVOID** nested ternary operators - use if/else or switch statements
- **AVOID** dense one-liners that sacrifice readability
- **PREFER** explicit, readable code over clever compact solutions
- **PREFER** clear variable/function names over comments explaining bad names

### Simplification Guidelines
- Reduce unnecessary complexity and nesting
- Eliminate redundant code and abstractions
- Consolidate related logic
- Remove comments that describe obvious code
- Don't combine too many concerns into single functions

### Python-Specific (This Project)
- Use type hints for function signatures
- Use f-strings for string formatting
- Use `logging` module, not print statements
- Handle errors gracefully with proper logging
- Follow existing patterns in the codebase

### What NOT to Do
- Don't over-simplify to the point of reducing clarity
- Don't create "clever" solutions that are hard to understand
- Don't remove helpful abstractions that improve organization
- Don't prioritize "fewer lines" over maintainability

---


## 🚨 MASTER SYSTEM INVARIANTS (NEVER VIOLATE) 🚨

**READ THIS FIRST BEFORE TOUCHING ANYTHING**

This section contains ALL critical invariants that must NEVER be violated. Breaking any of these will crash production.

---

### INVARIANT 1: Storage Persistence (MANDATORY)

**RULE:** ALL persistent data MUST live under `RAILWAY_VOLUME_MOUNT_PATH` (e.g., `/data` or `/app/grader_data` depending on Railway mount)

**Canonical Storage Locations (DO NOT CHANGE):**
```
${RAILWAY_VOLUME_MOUNT_PATH}/  (Railway 5GB persistent volume)
├── grader/
│   └── predictions.jsonl           ← Picks (grader_store.py) - WRITE PATH
├── grader_data/
│   ├── weights.json                ← Learned weights (data_dir.py)
│   └── predictions.json            ← Weight learning data
├── audit_logs/
│   └── audit_{YYYY-MM-DD}.json     ← Daily audits (data_dir.py)
└── trap_learning/                  ← v19.0 Trap Learning Loop
    ├── traps.jsonl                 ← Trap definitions
    ├── evaluations.jsonl           ← Evaluation history
    └── adjustments.jsonl           ← Weight adjustment audit trail
```

**CRITICAL FACTS:**
1. `RAILWAY_VOLUME_MOUNT_PATH=/data` (set by Railway automatically)
2. `/data` IS THE PERSISTENT VOLUME (verified `os.path.ismount() = True`)
3. **NEVER** add code to block `/app/*` paths - this crashes production
4. Both `storage_paths.py` AND `data_dir.py` MUST use `RAILWAY_VOLUME_MOUNT_PATH`
5. Picks MUST persist across container restarts (verified: 14+ picks survived Jan 28-29 crash)

**Startup Requirements:**
```python
# data_dir.py and storage_paths.py MUST log on startup:
GRADER_DATA_DIR=/data
✓ Storage writable: /data
✓ Is mountpoint: True
```

**VERIFICATION:**
```bash
curl https://web-production-7b2a.up.railway.app/internal/storage/health
# MUST show: is_mountpoint: true, is_ephemeral: false, predictions_line_count > 0
```

---

### INVARIANT 2: Titanium 3-of-4 Rule (STRICT)

**RULE:** `titanium_triggered=true` ONLY when >= 3 of 4 base engines >= 8.0

**Implementation:** `core/titanium.py` → `compute_titanium_flag(ai, research, esoteric, jarvis)` / `evaluate_titanium(...)`

**NEVER:**
- 1/4 engines ≥ 8.0 → `titanium=False` (ALWAYS)
- 2/4 engines ≥ 8.0 → `titanium=False` (ALWAYS)

**ALWAYS:**
- 3/4 engines ≥ 8.0 → `titanium=True` (MANDATORY)
- 4/4 engines ≥ 8.0 → `titanium=True` (MANDATORY)

**Boundary:** Score of exactly 8.0 DOES qualify. Score of 7.99 does NOT.

**Output Fields (MANDATORY in every pick):**
```python
{
    "titanium_triggered": bool,
    "titanium_count": int,  # 0-4
    "titanium_qualified_engines": List[str],  # ["ai", "research", ...]
    "titanium_threshold": 8.0
}
```

**Tests:** `tests/test_titanium_fix.py` (7 tests enforce this rule)

---

### INVARIANT 3: ET Today-Only Gating (MANDATORY)

**RULE:** ALL picks MUST be for games in today's ET window ONLY

**CANONICAL ET SLATE WINDOW:**
- Start: 00:00:00 ET (midnight) - inclusive
- End: 00:00:00 ET next day (midnight) - exclusive
- Interval: [start, end)

**Single Source of Truth:** `core/time_et.py` (ONLY 2 functions allowed)
```python
from core.time_et import now_et, et_day_bounds

start_et, end_et, start_utc, end_utc = et_day_bounds()  # ET window + UTC bounds
et_date = start_et.date().isoformat()  # "2026-01-29"
```

**MANDATORY Application Points:**
1. Props fetch → `filter_events_et(props_events, date_str=et_date)`
2. Games fetch → `filter_events_et(game_events, date_str=et_date)`
3. Autograder → Uses "yesterday ET" not UTC for grading

**NEVER:**
- Use `datetime.now()` or `utcnow()` for slate filtering
- Use pytz (ONLY zoneinfo allowed)
- Create new date helper functions
- Skip ET filtering on ANY data path touching Odds API

**Verification:**
```bash
curl /live/debug/time | jq '.et_date'  # "2026-01-29"
curl /live/best-bets/NBA?debug=1 | jq '.debug.date_window_et.filter_date'  # MUST MATCH
```

---

### INVARIANT 4: 4-Engine + Context Modifier Scoring (Option A - NO DOUBLE COUNTING)

**RULE:** Every pick MUST run through ALL 4 base engines + Jason Sim 2.0

**Engine Weights (Option A):**
```python
AI_WEIGHT = 0.25        # 25% - 8 AI models
RESEARCH_WEIGHT = 0.35  # 35% - Sharp/splits/variance/public fade
ESOTERIC_WEIGHT = 0.20  # 20% - Numerology/astro/fib/vortex/daily
JARVIS_WEIGHT = 0.20    # 20% - Gematria/triggers/mid-spread
CONTEXT_MODIFIER_CAP = 0.35  # Context is a bounded modifier, NOT an engine
# Total base weight: 1.00 (context is additive modifier, not weighted engine)
```

**Scoring Formula (EXACT):**
```python
BASE_4 = (ai × 0.25) + (research × 0.35) + (esoteric × 0.15) + (jarvis × 0.25)
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment + live_adjustment + totals_calibration_adj + hook_penalty + expert_consensus_boost + prop_correlation_adjustment
```

**Boosts are additive (NOT engines):**
- `msrf_boost` and `serp_boost` must remain separate (do NOT fold into confluence).
- Each boost must be present in payloads with status + reasons (even when 0.0 / unavailable).
- `ensemble_adjustment` is applied post-base for game picks when the ensemble model is available
  (+0.5 if hit_prob > 0.60, -0.5 if hit_prob < 0.40, else 0.0). Currently surfaced via `ai_reasons`.
- Live in-game adjustment: `live_adjustment` (bounded ±0.50) applied to **research_score** when game_status is LIVE.

**v20.3 Post-Base Signals (8 Pillars of Execution):**

| Signal | Cap | Notes |
|--------|-----|-------|
| `hook_penalty` | `HOOK_PENALTY_CAP` (0.25) | Always ≤0, penalizes bad hooks (key numbers) |
| `expert_consensus_boost` | `EXPERT_CONSENSUS_CAP` (0.35) | Always ≥0, boosts expert alignment (SHADOW MODE until validated) |
| `prop_correlation_adjustment` | `PROP_CORRELATION_CAP` (0.20) | Signed ±, prop correlation signals |

**CRITICAL: v20.3 No-Mutation Rule:**
- These signals are **post-base additive** — they MUST NOT mutate `research_score` or any engine score
- They are computed separately and passed as explicit parameters to `compute_final_score_option_a()`
- Caps are enforced inside `compute_final_score_option_a()`, not at call sites
- Each signal has explicit output fields for auditability: `{signal}_penalty/boost`, `{signal}_status`, `{signal}_reasons`

**Non-negotiable rule for any NEW final_score adjustment:**
- Must be **bounded**
- Must be **surfaced as its own field** in payloads
- Must be **included in docs contract scan**
- Must be **included in endpoint sanity math checks**

---


## Canonical Scoring Contract (Option A)

**Base (4 engines only):**
```
BASE_4 = (AI * 0.25) + (Research * 0.35) + (Esoteric * 0.20) + (Jarvis * 0.20)
```

**Context (modifier only):**
```
CONTEXT_MODIFIER_CAP = 0.35
context_modifier ∈ [-0.35, +0.35]
```

**Final score (clamped):**
```
total_boosts = min(TOTAL_BOOST_CAP, confluence_boost + msrf_boost + jason_sim_boost + serp_boost)
FINAL = clamp(0, 10, BASE_4 + context_modifier + total_boosts + ensemble_adjustment + live_adjustment + totals_calibration_adj + hook_penalty + expert_consensus_boost + prop_correlation_adjustment)
```
**TOTAL_BOOST_CAP = 1.5** — prevents score inflation from stacking multiple boosts (Invariant 26)

**v20.3 Post-Base Signal Caps (enforced in compute_final_score_option_a):**
- `hook_penalty` ∈ [-0.25, 0] (HOOK_PENALTY_CAP)
- `expert_consensus_boost` ∈ [0, 0.35] (EXPERT_CONSENSUS_CAP) — currently SHADOW MODE (forced to 0)
- `prop_correlation_adjustment` ∈ [-0.20, 0.20] (PROP_CORRELATION_CAP)

**Ensemble adjustment:**
- Uses `ENSEMBLE_ADJUSTMENT_STEP` (no magic ±0.5 literals).

---

## Boost Inventory (Source + Cap)

| Boost | Source | Cap | Notes |
|---|---|---|---|
| confluence_boost | `live_data_router.py` | `CONFLUENCE_BOOST_CAP` (10.0) | Derived from confluence levels |
| msrf_boost | `signals/msrf_resonance.py` | `MSRF_BOOST_CAP` (1.0) | 0.0 / 0.25 / 0.5 / 1.0 |
| jason_sim_boost | `jason_sim_confluence.py` | `JASON_SIM_BOOST_CAP` (1.5) | Can be negative (block rules) |
| serp_boost | `alt_data_sources/serp_intelligence.py` | `SERP_BOOST_CAP_TOTAL` (4.3) | Total SERP capped |
| **SUM of above 4** | `core/scoring_pipeline.py` | **`TOTAL_BOOST_CAP` (1.5)** | **Prevents score inflation (Inv. 26)** |
| ensemble_adjustment | `utils/ensemble_adjustment.py` | `ENSEMBLE_ADJUSTMENT_STEP` (0.5) | +0.5 / -0.5 step |
| live_adjustment | `live_data_router.py` | ±0.50 | In-game adjustment to research_score |
| totals_calibration_adj | `live_data_router.py` | ±0.75 | OVER penalty / UNDER boost from `TOTALS_SIDE_CALIBRATION` |
| **v20.3 Post-Base Signals** | | | **8 Pillars of Execution** |
| hook_penalty | `live_data_router.py` | `HOOK_PENALTY_CAP` (0.25) | Always ≤0, bad hook detection |
| expert_consensus_boost | `live_data_router.py` | `EXPERT_CONSENSUS_CAP` (0.35) | Always ≥0, SHADOW MODE (boost forced to 0) |
| prop_correlation_adjustment | `live_data_router.py` | `PROP_CORRELATION_CAP` (0.20) | Signed ±, prop correlation signals |

---

## Go/No-Go Checklist (Run Exactly)

```bash
# Full go/no-go (all 12 checks + optional pytest must pass)
API_KEY="YOUR_KEY" SKIP_NETWORK=0 SKIP_PYTEST=0 ALLOW_EMPTY=1 \
  bash scripts/prod_go_nogo.sh

# Or run individual checks:
bash scripts/option_a_drift_scan.sh
bash scripts/audit_drift_scan.sh
bash scripts/env_drift_scan.sh
bash scripts/docs_contract_scan.sh
ALLOW_EMPTY=1 bash scripts/learning_sanity_check.sh
ALLOW_EMPTY=1 bash scripts/learning_loop_sanity.sh
API_KEY=YOUR_KEY bash scripts/endpoint_matrix_sanity.sh
API_KEY=YOUR_KEY bash scripts/prod_endpoint_matrix.sh
API_KEY=YOUR_KEY python3 scripts/signal_coverage_report.py
API_KEY=YOUR_KEY bash scripts/api_proof_check.sh
API_KEY=YOUR_KEY bash scripts/live_sanity_check.sh
API_KEY=YOUR_KEY bash scripts/perf_audit_best_bets.sh
```

**IMPORTANT:** Always use `ALLOW_EMPTY=1` for local runs (dev doesn't have production prediction/weight files).

---


## Integration Registry Expectations (v2.0.0)

### Status Categories
- **Validated**: env vars set + connectivity OK.
- **Configured**: env vars set but connectivity not verified.
- **Unreachable**: env vars set but API unreachable (fail‑loud).
- **Not configured**: missing required env vars (fail‑loud).
- `last_used_at` must update on **both cache hits and live fetches** for all paid integrations.

### Criticality Tiers (v20.19)

| Tier | Health Impact | Integrations |
|------|---------------|--------------|
| **CRITICAL** | `/health.ok = false` | odds_api, playbook_api, balldontlie, railway_storage, database |
| **DEGRADED_OK** | `status = degraded`, `ok = true` | redis, whop_api |
| **OPTIONAL** | Log warning only | serpapi, twitter_api, astronomy_api, noaa_space_weather, fred_api, finnhub_api |
| **RELEVANCE_GATED** | Context-dependent | weather_api (outdoor sports only) |

### Integration Gate Script
```bash
# Run before deployment to validate all integrations
API_KEY=your_key ./scripts/integration_gate.sh

# Exit codes:
# 0 = All checks passed
# 1 = Critical integration missing/unreachable (BLOCK DEPLOY)
# 2 = Optional integrations failing (system degraded)
```

### Data Contract Tests
```bash
# Run schema validation tests
pytest tests/test_pick_data_contract.py -v

# Run against live endpoint
RUN_LIVE_TESTS=1 API_KEY=your_key pytest tests/test_pick_data_contract.py -v
```

**Engine Separation Rules:**
1. **Research Engine** - ALL market signals ONLY (sharp, splits, variance, public fade)
   - Public Fade lives ONLY here, NOT in Jarvis or Esoteric
   - Officials adjustments (Pillar 16) applied here
2. **Esoteric Engine** - NON-JARVIS ritual environment (astro, fib, vortex, daily edge)
   - For PROPS: Use `prop_line` for fib/vortex magnitude (NOT spread=0)
   - Expected range: 2.0-5.5 (median ~3.5), average MUST NOT exceed 7.0
   - Park Factors (Pillar 17) applied here for MLB
3. **Jarvis Engine** - Standalone gematria + sacred triggers + Jarvis-specific logic
   - MUST always return meaningful output with 7 required fields (see below)
4. **Context Modifier Layer** (Option A) - Pillars 13-15 aggregated
   - Defensive Rank (50%): Opponent's defensive strength vs position
   - Pace (30%): Game pace vector from team data
   - Vacuum (20%): Usage vacuum from injuries
   - Output is a bounded modifier: `context_modifier ∈ [-0.35, +0.35]`
5. **Jason Sim 2.0** - Post-pick confluence layer (NO ODDS)
   - Spread/ML: Boost if pick-side win% ≥61%, block if ≤52% and base < 7.2
   - Totals: Reduce confidence if variance HIGH
   - Props: Boost ONLY if base_prop_score ≥6.8 AND environment supports prop

**Required Output Fields (ALL picks):**
```python
{
    "ai_score": float,           # 0-10
    "research_score": float,     # 0-10
    "esoteric_score": float,     # 0-10
    "jarvis_score": float,       # 0-10
    "context_modifier": float,   # bounded modifier (authoritative)
    "context_score": float,      # backward-compat only (do not use for weighting)
    "base_score": float,         # Weighted sum before boosts
    "confluence_boost": float,   # STRONG (+3), MODERATE (+1), DIVERGENT (+0), HARMONIC_CONVERGENCE (+4.5)
    "jason_sim_boost": float,    # Can be negative
    "final_score": float,        # BASE + confluence + jason_sim

    # Breakdown fields (MANDATORY)
    "ai_reasons": List[str],
    "research_reasons": List[str],
    "esoteric_reasons": List[str],
    "jarvis_reasons": List[str],
    "context_reasons": List[str],
    "jason_sim_reasons": List[str],

    # Jarvis 7-field contract (see Invariant 5)
    "jarvis_rs": float | None,
    "jarvis_active": bool,
    "jarvis_hits_count": int,
    "jarvis_triggers_hit": List[str],
    "jarvis_fail_reasons": List[str],
    "jarvis_inputs_used": Dict[str, Any],
}
```

---

### INVARIANT 5: Jarvis Additive Scoring Contract (v16.0)

**RULE:** Jarvis ALWAYS runs when inputs are present. Uses ADDITIVE trigger scoring.

**Scoring Model:**
- **Baseline:** 4.5 when inputs present but no triggers fire
- **Triggers ADD to baseline** (not replace it)
- **GOLD_STAR requires jarvis_rs >= 6.5** (at least 1 strong trigger or 2+ triggers)

**Trigger Contributions (ADD to baseline 4.5):**
| Trigger | Contribution | Total |
|---------|-------------|-------|
| IMMORTAL (2178) | +3.5 | 8.0 |
| ORDER (201) | +2.5 | 7.0 |
| MASTER/WILL/SOCIETY (33/93/322) | +2.0 | 6.5 |
| BEAST/JESUS/TESLA (666/888/369) | +1.5 | 6.0 |
| Gematria strong/moderate | +1.5/+0.8 | varies |
| Goldilocks zone | +0.5 | varies |

**Stacking:** Each additional trigger adds 70% of previous (decay factor)

**Required Fields:**
```python
{
    "jarvis_rs": float | None,           # 0-10 when active, None when inputs missing
    "jarvis_baseline": 4.5,              # Always 4.5 when inputs present
    "jarvis_trigger_contribs": Dict,     # {"THE MASTER": 2.0, "gematria_strong": 1.5}
    "jarvis_active": bool,               # True if inputs present (Jarvis ran)
    "jarvis_hits_count": int,            # Count of triggers hit
    "jarvis_triggers_hit": List[Dict],   # Trigger details with contributions
    "jarvis_reasons": List[str],         # Why it triggered (or didn't)
    "jarvis_fail_reasons": List[str],    # Explain no triggers
    "jarvis_no_trigger_reason": str|None,# "NO_TRIGGER_BASELINE" if no triggers
    "jarvis_inputs_used": Dict,          # Tracks all inputs (spread, total, etc.)
}
```

**Validation:** `tests/test_jarvis_transparency.py`

---

### INVARIANT 6: Output Filtering (Score + Tier Gates)

**RULE:** NEVER return picks below thresholds OR with internal-only tiers

**⚠️ IMPORTANT: Two Different Threshold Systems**

| Type | Internal Tier Assignment | API Output Threshold |
|------|--------------------------|---------------------|
| Games | EDGE_LEAN at ≥6.5 | **7.0** (MIN_FINAL_SCORE) |
| Props | EDGE_LEAN at ≥6.5 | **6.5** (MIN_PROPS_SCORE) |

A game pick scored 6.7 is internally tiered as EDGE_LEAN but **never returned** because 6.7 < 7.0.

**API Output Thresholds (v20.20):**
- **Games:** `final_score >= 7.0` (MIN_FINAL_SCORE)
- **Props:** `final_score >= 6.5` (MIN_PROPS_SCORE - lower because SERP disabled)

**Hidden Tier Filter (v20.20 - CRITICAL):**
```python
# MONITOR/PASS are internal workflow states, NOT output tiers
HIDDEN_TIERS = {"MONITOR", "PASS"}
```

**Filter Pipeline (in order):**
```python
# 1. Deduplicate by pick_id (same bet, different books)
deduplicated = _dedupe_picks(all_picks)

# 2. Filter to API output thresholds (props=6.5, games=7.0)
# Note: total_score == final_score (aliases), contract uses final_score
filtered_props = [p for p in props if p["final_score"] >= MIN_PROPS_SCORE]  # 6.5
filtered_games = [p for p in games if p["final_score"] >= MIN_FINAL_SCORE]  # 7.0

# 3. Filter out HIDDEN_TIERS (MONITOR/PASS are internal only)
HIDDEN_TIERS = {"MONITOR", "PASS"}
filtered_props = [p for p in filtered_props if p.get("tier") not in HIDDEN_TIERS]
filtered_games = [p for p in filtered_games if p.get("tier") not in HIDDEN_TIERS]

# 4. Apply contradiction gate (prevent opposite sides)
no_contradictions = apply_contradiction_gate(filtered_props, filtered_games)

# 5. Take top N picks
top_picks = no_contradictions[:max_picks]
```

**GOLD_STAR Hard Gates (Option A):**
- If tier == "GOLD_STAR", MUST pass ALL gates:
  - `ai_score >= 6.8`
  - `research_score >= 6.5`
  - `jarvis_score >= 6.5`
  - `esoteric_score >= 5.5`
  - context gate removed (context is a bounded modifier)
- If ANY gate fails, downgrade to "EDGE_LEAN" → may further downgrade to "MONITOR"

**Internal Tier Assignment (NOT the same as output):**
1. TITANIUM_SMASH (3/4 engines ≥ 8.0) - Overrides all others
2. GOLD_STAR (≥ 7.5 + passes all gates)
3. EDGE_LEAN (≥ 6.5) - **Note: Games need 7.0 to be returned, props need 6.5**
4. MONITOR (≥ 5.5) - **HIDDEN (never returned to API)**
5. PASS (< 5.5) - **HIDDEN (never returned to API)**

**Valid Output Tiers:** `{TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN}` only

---

### INVARIANT 7: Contradiction Gate (MANDATORY)

**RULE:** NEVER return both sides of same bet (Over AND Under, Team A AND Team B)

**Unique Key Format:**
```
{sport}|{date_et}|{event_id}|{market}|{prop_type}|{player_id/team_id}|{line}
```

**Detection Rules:**
1. **Totals/Props:** Detect Over vs Under on same line
2. **Spreads:** Use `abs(line)` so +1.5 and -1.5 match
3. **Moneylines:** Use "Game" as subject for both teams
4. **Player Props:** Check markets with "PLAYER_" prefix (player_points, player_assists, etc.)

**Priority When Duplicates Found:**
- Keep pick with higher `final_score`
- Tiebreaker: Preferred book (draftkings > fanduel > betmgm > caesars > pinnacle)

**Implementation:** `utils/contradiction_gate.py` → `apply_contradiction_gate(props, games)`

**Tests:** 8 tests verify all cases (totals, props, spreads, player props)

---

### INVARIANT 8: Best-Bets Response Contract (NO KeyErrors)

**RULE:** `/live/best-bets/{sport}` MUST ALWAYS return JSON with these keys

**Required Structure:**
```json
{
  "sport": "NBA",
  "props": {
    "count": 0,
    "picks": []
  },
  "game_picks": {
    "count": 0,
    "picks": []
  },
  "meta": {}
}
```

**NEVER:**
- Missing `props` key (even when 0 props available)
- Missing `game_picks` key (even when 0 game picks)
- Missing `meta` key

**Why:** NHL often has 0 props. Frontend MUST NOT get KeyError.

**Implementation:** `models/best_bets_response.py` → `build_best_bets_response()`

**Tests:** `tests/test_best_bets_contract.py` (5 tests enforce this)

---

### INVARIANT 9: Pick Persistence Contract (AutoGrader)

**RULE:** Every pick MUST include ALL required fields for AutoGrader to grade it

**Required Fields:**
```python
[
    "prediction_id",        # Stable 12-char deterministic ID
    "sport",                # NBA, NHL, NFL, MLB, NCAAB
    "market_type",          # SPREAD, TOTAL, MONEYLINE, PROP
    "line_at_bet",          # Line when bet placed
    "odds_at_bet",          # Odds when bet placed (American format)
    "book",                 # Sportsbook name
    "event_start_time_et",  # Game start time in ET
    "created_at",           # Pick creation timestamp
    "final_score",          # Pick score (≥ 6.5)
    "tier",                 # TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN

    # All 4 base engine scores
    "ai_score",
    "research_score",
    "esoteric_score",
    "jarvis_score",
    "context_modifier",

    # All 4 base engine reasons
    "ai_reasons",
    "research_reasons",
    "esoteric_reasons",
    "jarvis_reasons",
    "context_breakdown",
]
```

**Storage Format:** JSONL (one pick per line) at `/data/grader/predictions.jsonl`

**Write Path:** `grader_store.persist_pick()` called from `/live/best-bets/{sport}`

**Read Path:** AutoGrader reads from same file via `grader_store.load_predictions()`

---

#### INVARIANT 9.1: Two Storage Systems (INTENTIONAL SEPARATION)

**RULE:** Picks and Weights use SEPARATE storage systems by design. Never merge them.

**Architecture:**

| System | Module | Path | Purpose | Frequency |
|--------|--------|------|---------|-----------|
| **Picks** | `grader_store.py` | `/data/grader/predictions.jsonl` | All picks | High (every best-bets call) |
| **Weights** | `auto_grader.py` | `/data/grader_data/weights.json` | Learned weights | Low (daily 6 AM audit) |

**Why Separate?**
1. **Access patterns differ**: Picks written on every request; weights updated once daily
2. **File locking**: Separate files prevent contention between frequent writes and batch processing
3. **Recovery**: Can restore weights without losing picks (and vice versa)
4. **Format**: Picks use append-only JSONL; weights use overwrite JSON

**Data Flow:**
```
Best-bets endpoint
        ↓
grader_store.persist_pick(pick_data)
        ↓
/data/grader/predictions.jsonl  ←── [PICKS WRITE PATH]
        ↓ (read by auto_grader)
Daily 6 AM audit
        ↓
auto_grader → grade_prediction() → adjust_weights()
        ↓
/data/grader_data/weights.json  ←── [WEIGHTS WRITE PATH]
```

**What Was Removed (v20.x cleanup):**
- Legacy `_save_predictions()` method from auto_grader.py
- `predictions.json` saving from `_save_state()`
- `_save_predictions()` calls from `grade_prediction()`

**What Remains:**
- `auto_grader.py` READS picks from `grader_store` but only WRITES `weights.json`
- All pick persistence flows through `grader_store.py` exclusively

**NEVER:**
- Write picks from `auto_grader.py` (only `grader_store.py` writes picks)
- Write weights from `grader_store.py` (only `auto_grader.py` writes weights)
- Merge the two storage systems (they're separate by design)
- Add a new `_save_predictions()` method to auto_grader

**Verification:**
```bash
# Check both storage systems are healthy
curl /internal/storage/health | jq '{
  picks_count: .predictions_line_count,
  picks_path: .predictions_path,
  weights_dir: .grader_data_dir
}'

# Verify grader reads picks and manages weights correctly
curl /live/grader/status -H "X-API-Key: KEY" | jq '{
  predictions_logged: .predictions_logged,
  weights_loaded: .weights_loaded,
  storage_path: .storage_path
}'
```

---

### Autograder Verification (REQUIRED)

Run after any change to storage, grading, or best-bets output:

```bash
# 1) Storage + grader status
curl /internal/storage/health
curl /live/grader/status -H "X-API-Key: KEY"

# 2) Dry-run (no state changes)
curl -X POST /live/grader/dry-run -H "X-API-Key: KEY" \
  -d '{"date":"YYYY-MM-DD","mode":"pre"}'

# 3) End-to-end check (pre/post)
./scripts/verify_autograder_e2e.sh --mode pre
./scripts/verify_autograder_e2e.sh --mode post
```

**Expected:**
- `available=true`
- `predictions_logged > 0`
- `storage_path` inside `/data`
- Dry-run shows `pre_mode_pass=true` and `failed=0`
- E2E script reports PASS

---

### INVARIANT 10: Frontend-Ready Output (Human Readable)

**RULE:** Every pick MUST include clear human-readable fields

**Required Human-Readable Fields:**
```python
{
    "description": str,        # "Jamal Murray Assists Over 3.5"
    "pick_detail": str,        # "Assists Over 3.5"
    "matchup": str,            # "Away @ Home"
    "sport": str,              # "NBA"
    "market": str,             # "PROP", "TOTAL", "SPREAD", "MONEYLINE"
    "side": str,               # "Over", "Under", "Lakers", etc.
    "line": float,             # 3.5, 246.5, +6.5, etc.
    "odds_american": int,      # -110, +135, etc.
    "book": str,               # "draftkings"
    "start_time_et": str,      # Display string in ET (e.g., "9:10 PM ET")
    "start_time_timezone": str,# Always "ET"
    "start_time_status": str,  # "OK" | "UNAVAILABLE"
    "game_status": str,        # "SCHEDULED", "LIVE", "FINAL"
}
```

**Public Payload ET-Only Rule (MANDATORY):**
- Member-facing `/live/*` responses MUST NOT include UTC/ISO/telemetry keys.
- Drop keys: `generated_at`, `persisted_at`, `timestamp`, `_cached_at`, `_elapsed_s`, `_timed_out_components`,
  any `*_utc`, `*_iso`, `*_epoch`, and vendor time keys like `startTime`, `startTimeEst`.
- ET display strings are allowed: `start_time_et`, `run_timestamp_et`, `date_et`.
- Sanitizer is the single choke point: `utils/public_payload_sanitizer.py` + `LiveContractRoute`.

**NEVER:**
- Generic labels like "Game" without context
- Missing Over/Under for totals
- Missing team name for spreads/ML
- Missing player name for props

**Backfill:** If old picks missing fields, compute from primitives (see `models/pick_converter.py`)

---

### MASTER VERIFICATION CHECKLIST

**Before ANY storage/autograder/scheduler change, verify ALL of these:**

```bash
# 1. Storage health
curl /internal/storage/health
# MUST show: is_mountpoint: true, predictions_line_count > 0

# 2. Grader status
curl /live/grader/status -H "X-API-Key: KEY"
# MUST show: predictions_logged > 0, weights_loaded: true

# 3. Best-bets has all keys
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY"
# MUST have: props, game_picks, meta keys
# MUST have: filtered_below_6_5_total, contradiction_blocked_total

# 4. ET date consistency
diff <(curl -s /live/debug/time | jq -r '.et_date') \
     <(curl -s /live/best-bets/NBA?debug=1 | jq -r '.debug.date_window_et.filter_date')
# MUST be empty (dates match)

# 5. Autograder dry-run
curl -X POST /live/grader/dry-run -H "X-API-Key: KEY" \
  -d '{"date":"2026-01-29","mode":"pre"}'
# MUST show: pre_mode_pass: true, failed: 0

# 6. Cache headers on /live (GET/HEAD)
curl -sD - /live/best-bets/NBA -H "X-API-Key: KEY" -o /dev/null \
 | egrep -i 'cache-control|pragma|expires|vary'
# MUST include no-store + vary headers

# 7. Public payload has no UTC/telemetry keys
curl -s /live/best-bets/NBA -H "X-API-Key: KEY" \
 | jq -r '.. | objects | keys[]' \
 | egrep -i 'generated_at|persisted_at|timestamp|_cached_at|_elapsed_s|_timed_out_components|_utc$|_iso$|starttime' \
 | head
# MUST be empty

# 8. Run tests
pytest tests/test_titanium_fix.py tests/test_best_bets_contract.py
# MUST pass: 12/12 tests

# 9. Scheduler status (no import errors)
curl /live/scheduler/status -H "X-API-Key: KEY"
# MUST show: available: true (no import errors)
```

### POST-CHANGE GATES (RUN AFTER ANY BACKEND CHANGE)

These checks catch the exact regressions that previously slipped through.

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

6) **No UTC/Telemetry Leaks**
   - no `*_utc`, `*_iso`, `startTime*`, `generated_at`, `persisted_at`, `_cached_at`
   - ET display strings only

### /health TRUTH FIX (REQUIRED)

`/health` is public for Railway, but it must be **truthful**:
- It now runs internal probes (storage, db, redis, scheduler, integrations env map)
- It returns `status: healthy|degraded|critical`, plus `errors` + `degraded_reasons`
- No external API calls; fail-soft only
- If any critical probe fails, `/health` must show **degraded/critical**, not “healthy”

---

### NEVER BREAK THESE RULES

1. ✅ Read CLAUDE.md BEFORE touching storage/autograder/scheduler
2. ✅ Verify production health BEFORE making assumptions
3. ✅ Run verification checklist BEFORE committing
4. ✅ Check that RAILWAY_VOLUME_MOUNT_PATH is used everywhere
5. ✅ Ensure all 4 base engines + Jason Sim run on every pick
6. ✅ Filter to >= 6.5 BEFORE returning to frontend
7. ✅ Apply contradiction gate to prevent opposite sides
8. ✅ Include ALL required fields for autograder
9. ✅ Use `core/time_et.py` ONLY for ET timezone logic
10. ✅ Test with `pytest` BEFORE deploying
11. ✅ Scheduler status endpoint MUST work (no import errors, reports ET timezone)

**If you violate ANY of these invariants, production WILL crash.**

---


## 📋 FRONTEND CONTRACT (UI Integration)

**CRITICAL:** Frontend must render directly from API fields. **NO recomputation** on the frontend.

### Pick Object Fields (Guaranteed Present)

Every pick returned from `/live/best-bets/{sport}` includes these fields:

#### Core Pick Data
```javascript
{
  // Identity
  "pick_id": "a1b2c3d4e5f6",           // 12-char stable ID
  "sport": "NBA",                       // NBA, NHL, NFL, MLB, NCAAB
  "market": "PROP",                     // PROP, TOTAL, SPREAD, MONEYLINE

  // Human-Readable Display
  "description": "LeBron James Points Over 25.5",  // Full sentence
  "pick_detail": "Points Over 25.5",               // Compact bet string
  "matchup": "Lakers @ Celtics",                   // Always "Away @ Home"
  "side": "Over",                                  // Over/Under/Team name
  "line": 25.5,                                    // Bet line

  // Tier & Score (NEVER RECOMPUTE)
  "final_score": 8.2,                   // >= 6.5 guaranteed
  "tier": "GOLD_STAR",                  // TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN
  "units": 2.0,                         // Bet sizing

  // Engine Scores (For Transparency Display)
  "ai_score": 8.5,                      // 0-10 scale
  "research_score": 7.8,                // 0-10 scale
  "esoteric_score": 7.2,                // 0-10 scale
  "jarvis_rs": 6.0,                     // 0-10 scale

  // Titanium Status
  "titanium_triggered": false,          // true iff >= 3 engines >= 8.0
  "titanium_count": 2,                  // Count of engines >= 8.0
  "titanium_qualified_engines": ["ai", "research"],  // Which engines qualified

  // Game Status
  "start_time_et": "2026-01-29T19:00:00-05:00",  // ISO timestamp in ET
  "game_status": "SCHEDULED",                     // SCHEDULED, LIVE, FINAL
  "is_live_bet_candidate": false,                 // true if game hasn't started

  // Sportsbook
  "book": "draftkings",                 // Book name
  "odds_american": -110,                // American odds format
  "sportsbook_url": "https://...",      // Click-to-bet deep link
}
```

### Debug Data (Available with `?debug=1`)

```javascript
{
  "debug": {
    // ET Filtering Telemetry
    "date_window_et": {
      "filter_date": "2026-01-29",           // ET date used for filtering
      "start_et": "00:00:00",                // Window start
      "end_et": "23:59:59",                  // Window end
      "events_before_props": 60,             // Events before ET filter
      "events_after_props": 12,              // Events after ET filter
      "events_before_games": 25,
      "events_after_games": 8
    },

    // Score Filtering Telemetry
    "filtered_below_6_5_total": 1012,        // Picks filtered < 6.5
    "filtered_below_6_5_props": 850,
    "filtered_below_6_5_games": 162,

    // Contradiction Gate Telemetry
    "contradiction_blocked_total": 323,      // Opposite sides blocked
    "contradiction_blocked_props": 310,
    "contradiction_blocked_games": 13,

    // Pick Logger Status
    "picks_logged": 12,                      // New picks persisted
    "picks_skipped_dupes": 8,                // Duplicate picks skipped
    "pick_log_errors": [],                   // Any logging errors

    // Performance
    "total_elapsed_s": 5.57                  // Endpoint response time
  }
}
```

### Frontend Rules (MANDATORY)

**DO:**
- ✅ Render `final_score`, `tier`, `titanium_triggered` directly from API
- ✅ Display all 4 engine scores (`ai_score`, `research_score`, `esoteric_score`, `jarvis_rs`)
- ✅ Use `description` for pick cards ("LeBron James Points Over 25.5")
- ✅ Use `pick_detail` for compact display ("Points Over 25.5")
- ✅ Use `start_time_et` for game time display (already in ET timezone)
- ✅ Check `is_live_bet_candidate` before showing "Bet Now" button
- ✅ Use `titanium_qualified_engines` to show which engines hit Titanium threshold

**NEVER:**
- ❌ Recalculate `final_score` from engine scores (backend formula is complex)
- ❌ Recompute `tier` from `final_score` (GOLD_STAR has hard gates beyond score)
- ❌ Determine `titanium_triggered` from engine scores (uses 3/4 >= 8.0 rule + final_score >= 8.0)
- ❌ Convert `start_time_et` to another timezone (already in ET, display as-is)
- ❌ Compute `game_status` from timestamps (backend knows actual game state)
- ❌ Show picks with `final_score < 6.5` (API will never return them, but validate anyway)

### Example UI Code (TypeScript)

```typescript
interface Pick {
  pick_id: string;
  description: string;
  pick_detail: string;
  matchup: string;
  final_score: number;
  tier: "TITANIUM_SMASH" | "GOLD_STAR" | "EDGE_LEAN";
  titanium_triggered: boolean;
  titanium_count: number;
  ai_score: number;
  research_score: number;
  esoteric_score: number;
  jarvis_rs: number;
  start_time_et: string;
  game_status: "SCHEDULED" | "LIVE" | "FINAL";
  is_live_bet_candidate: boolean;
}

// ✅ CORRECT: Render directly from API
function PickCard({ pick }: { pick: Pick }) {
  return (
    <div>
      <h3>{pick.description}</h3>
      <div>Score: {pick.final_score.toFixed(1)}</div>
      <div>Tier: {pick.tier}</div>
      {pick.titanium_triggered && <span>⚡ TITANIUM</span>}

      {/* Engine breakdown */}
      <div>
        AI: {pick.ai_score.toFixed(1)} |
        Research: {pick.research_score.toFixed(1)} |
        Esoteric: {pick.esoteric_score.toFixed(1)} |
        Jarvis: {pick.jarvis_rs.toFixed(1)}
      </div>

      {/* Titanium transparency */}
      {pick.titanium_triggered && (
        <div>{pick.titanium_count}/4 base engines hit Titanium threshold</div>
      )}

      {pick.is_live_bet_candidate && (
        <button>Bet Now</button>
      )}
    </div>
  );
}

// ❌ WRONG: Recomputing values from API
function BadPickCard({ pick }: { pick: Pick }) {
  // ❌ NEVER do this
  const finalScore = (
    pick.ai_score * 0.25 +
    pick.research_score * 0.35 +
    pick.esoteric_score * 0.15 +
    pick.jarvis_rs * 0.25
  );

  // ❌ NEVER do this
  const tier = finalScore >= 7.5 ? "GOLD_STAR" : "EDGE_LEAN";

  // Use API values instead!
  return <div>Score: {pick.final_score}</div>;
}
```

### Validation on Frontend

Even though API guarantees these invariants, validate to catch bugs early:

```typescript
function validatePick(pick: Pick): boolean {
  // Score threshold
  if (pick.final_score < 6.5) {
    console.error(`Invalid pick: score ${pick.final_score} < 6.5`);
    return false;
  }

  // Titanium rule
  const enginesAbove8 = [
    pick.ai_score,
    pick.research_score,
    pick.esoteric_score,
    pick.jarvis_rs
  ].filter(s => s >= 8.0).length;

  if (pick.titanium_triggered && enginesAbove8 < 3) {
    console.error(`Invalid Titanium: only ${enginesAbove8}/4 base engines >= 8.0`);
    return false;
  }

  return true;
}
```

### Debug Mode Integration

```typescript
// Fetch with debug mode
const response = await fetch('/live/best-bets/NBA?debug=1', {
  headers: { 'X-API-Key': API_KEY }
});

const data = await response.json();

// Show filtering stats in dev tools
if (data.debug) {
  console.log('ET filtering:', data.debug.date_window_et);
  console.log('Score filtering:', data.debug.filtered_below_6_5_total);
  console.log('Contradiction gate:', data.debug.contradiction_blocked_total);
  console.log('Performance:', data.debug.total_elapsed_s + 's');
}
```

### Integration Status Display (Admin Dashboard)

For `/live/debug/integrations` response, use this color mapping:

| Status | Color | Meaning |
|--------|-------|---------|
| `VALIDATED` | 🟢 Green | Key configured AND connectivity verified |
| `CONFIGURED` | 🟡 Yellow | Key present, no ping test (acceptable) |
| `NOT_RELEVANT` | ⚪ Gray | Integration not applicable (e.g., weather for indoor sports) |
| `UNREACHABLE` | 🔴 Red | Key configured but API unreachable (investigate) |
| `ERROR` | 🔴 Red | Integration error (investigate) |
| `NOT_CONFIGURED` | ⚫ Black/Disabled | Required key missing (critical) |

**Current production status (14 integrations):**
- **5 VALIDATED** (critical path): odds_api, playbook_api, balldontlie, weather_api, railway_storage
- **9 CONFIGURED** (keys present): astronomy, noaa, fred, finnhub, serpapi, twitter, whop, database, redis

**Frontend display:**
```typescript
const statusColor = {
  VALIDATED: 'green',
  CONFIGURED: 'yellow',
  NOT_RELEVANT: 'gray',
  UNREACHABLE: 'red',
  ERROR: 'red',
  NOT_CONFIGURED: 'black'
};

// Usage
<StatusBadge color={statusColor[integration.status_category]} />
```

**Yellow is acceptable** for CONFIGURED integrations - it means the key is set but we don't ping on every request (to avoid rate limits on esoteric APIs).

---


## ⚠️ BACKEND FROZEN - DO NOT MODIFY

**As of January 29, 2026, the backend is production-ready and FROZEN.**

**DO NOT:**
- Add new features to backend
- Modify existing endpoints
- Change storage paths
- Refactor working code
- "Improve" or "optimize" anything

**ONLY MODIFY IF:**
- Critical production bug (storage fails, grading breaks, API crashes)
- Security vulnerability discovered
- User explicitly requests a specific fix

**ALL OTHER CHANGES:** Suggest to user first, get explicit approval.

---

## User Environment
- **OS:** Mac
- **Terminal:** Use Mac Terminal commands (no Windows-specific instructions)

---

## CRITICAL: Deployment Workflow

**ALWAYS push changes automatically. NEVER ask the user to check deployment status.**

### When You Make Code Changes:
1. **Commit immediately:**
   ```bash
   git add .
   git commit -m "descriptive message"
   ```
2. **Push immediately:**
   ```bash
   git push origin main
   ```
3. **Railway auto-deploys** - Takes 2-3 minutes, happens automatically
4. **DO NOT ask user to check** - Railway handles it, user knows the workflow

---


## 📅 SCHEDULED DATA FETCHES & CACHE TTLs

**IMPORTANT:** This is the system's automated schedule. DO NOT ask when to run best-bets - check this section first.

### Scheduled Tasks (All Times ET)

| Time | Task | Description |
|------|------|-------------|
| **5:00 AM** | Grading + Tuning | Grade yesterday's picks, adjust weights based on results |
| **5:30 AM** | Smoke Test | Verify system health before picks go out |
| **6:00 AM** | JSONL Grading | Grade predictions from logs (auto-grader) |
| **6:15 AM** | Trap Evaluation | v19.0: Evaluate pre-game traps against yesterday's results |
| **6:30 AM** | Daily Audit | Full audit for all sports, update weights |
| **7:00 AM** | Team Model Training | v20.16: Train LSTM, Matchup, Ensemble from graded picks |
| **7:30 AM** | Training Verification | v20.16.4: Verify 7 AM training ran, log alert if failed |
| **10:00 AM** | Props Fetch | Fresh morning props data for all sports |
| **12:00 PM** | Props Fetch (Weekends Only) | Noon games (NBA/NCAAB) |
| **2:00 PM** | Props Fetch (Weekends Only) | Afternoon games (NBA/NCAAB) |
| **6:00 PM** | Props Fetch | Evening refresh for all sports |

### Cache TTLs

| Data Type | TTL | Reason |
|-----------|-----|--------|
| **Props** | 8 hours | Props don't change frequently, conserve API quota |
| **Best-bets** | 5-10 minutes | Balance freshness with API usage |
| **Live scores** | 2 minutes | Near real-time game updates |
| **Splits/Lines** | 5 minutes | Market moves frequently |

### On-Demand Fetching

Best-bets are **generated on-demand** when `/live/best-bets/{sport}` is called:
- First call: Fresh fetch from APIs (slow, ~5-6 seconds)
- Subsequent calls: Served from cache (fast, ~100ms)
- Cache expires after 5-10 minutes, then next call triggers fresh fetch

### Daily Workflow

```
5:00 AM  → Grade yesterday's picks, adjust weights
5:30 AM  → Smoke test (health check)
6:00 AM  → JSONL grading
6:15 AM  → Trap evaluation
6:30 AM  → Daily audit (all sports)
         ↓
7:00 AM  → Team model training (LSTM, Matchup, Ensemble)
7:30 AM  → Training verification (alerts if training failed)
         ↓
10:00 AM → Props fetch (morning)
         ↓
12:00 PM → Props fetch (weekends only)
2:00 PM  → Props fetch (weekends only)
         ↓
6:00 PM  → Props fetch (evening)
         ↓
Throughout day → Best-bets served on-demand (cached 5-10 min)
```

**Key Points:**
- Morning grading/audit happens BEFORE training
- Team model training at 7 AM uses graded picks from 6 AM audit
- Training verification at 7:30 AM confirms training succeeded (logs ERROR if not)
- Weights are updated daily based on yesterday's results
- Props fetches are scheduled to catch different game windows
- Weekend schedule includes noon/afternoon fetches for daytime games
- Live scores update every 2 minutes during games

### Morning Spot Check (Run After 7:30 AM ET)

Two quick commands to verify training ran:

**1. Training Health:**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.training_health'
# Expected: "HEALTHY"
```

**2. Artifact Timestamps (Proof Training Ran at 7 AM):**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.artifact_proof | to_entries[] | {file: .key, updated: .value.mtime_iso}'
# Expected: All 3 files show today's date at 07:00:00-05:00
```

**3. Daily Report (Verify All Sports):**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/grader/daily-report" \
  -H "X-API-Key: YOUR_KEY" | jq '.by_sport | keys'
# Expected: ["NBA", "NCAAB"] (active sports with picks)
```

**4. Training Filter Telemetry (Verify Training Data Quality) — v20.16.9:**
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/debug/training-status" \
  -H "X-API-Key: YOUR_KEY" | jq '.training_telemetry.filter_counts'
# Shows: candidates_loaded, dropped_*, used_for_training, sample_pick_ids
```

| Result | Meaning |
|--------|---------|
| `HEALTHY` + today's 7 AM timestamps | Both jobs worked ✅ |
| `STALE` | Training older than 24h — check scheduler |
| `NEVER_RAN` | Training pipeline never executed — trigger manually |
| Yesterday's timestamps | 7 AM job didn't run — check Railway logs |

### Training Status Validation (v20.17.3)

**Complete validation script with hard assertions:**
```bash
#!/usr/bin/env bash
set -euo pipefail
API_KEY='YOUR_KEY'
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

echo "✅ HARD CHECKS PASS"
```

**Note:** The `ensemble_signature == null` allowance handles runs before telemetry fixes deployed. Remove once all runs have signatures.

**Attribution Buckets (missing model_preds):**
| Bucket | Meaning | Expected? |
|--------|---------|-----------|
| `old_schema` | Before 2026-02-01 (model_preds not added yet) | Yes |
| `non_game_market` | Prop pick (no ensemble scoring) | Yes |
| `error_path` | Explicit error/timeout/fallback indicator | Investigate |
| `heuristic_fallback` | ai_mode == HEURISTIC_FALLBACK (MPS unavailable) | Investigate if high |
| `empty_raw_inputs` | Game market but raw_inputs empty (MPS partial result) | Investigate if high |
| `unknown` | Cannot determine reason | MUST be 0 |

---

## Deployment Gates (Required Before Deploy)

**Three gates must pass before any production deployment:**

### Gate A: Build SHA Verification
```bash
# Verify deployed commit matches expected
curl -s "$BASE_URL/health" | jq -e '.build_sha == "EXPECTED_SHA"'
```

### Gate B: Engine 1 Training Health (jq Hard Assertions)
```bash
json="$(curl -fsS -H 'X-API-Key: YOUR_KEY' \
  'https://web-production-7b2a.up.railway.app/live/debug/training-status')"

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

echo "✅ GATE B PASS"
```

### Gate C: Engine 2 Research Anti-Conflation
```bash
json="$(curl -fsS -H 'X-API-Key: YOUR_KEY' \
  'https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1')"

echo "$json" | jq '.game_picks.picks[0] | {
  final_score,
  research_breakdown,
  research_reasons: (.research_reasons[0:3] // [])
}'

# Hard semantic checks - ALL must pass
echo "$json" | jq -e '
  (.game_picks.picks // []) | all(
    # SHARP: if boost > 0, must be Playbook + SUCCESS + real inputs
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
    # LINE: if boost > 0, must be Odds API + SUCCESS + real inputs
    (
      (.research_breakdown.line_boost // 0) <= 0
      or (
        .research_breakdown.line_source_api == "odds_api"
        and .research_breakdown.line_status == "SUCCESS"
        and (.research_breakdown.line_raw_inputs.line_variance != null)
      )
    )
    and
    # Anti-conflation: sharp_status != SUCCESS → sharp_strength == NONE
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

echo "✅ GATE C PASS"
```

### Important: jq Assertion Failures

**When `jq -e` returns non-zero exit:**

1. **Do NOT blame phantom shell quoting** unless you can reproduce the exact quoting issue
2. **Check actual response** with `echo "$json" | jq .` to see raw data
3. **Verify field paths** match current API response shape
4. **Common causes:**
   - Response shape changed (add optional chaining `?` or `// null`)
   - Field genuinely missing (actual bug, not assertion bug)
   - Network error (curl returned empty/error response)

**The jq command is correct if it worked before.** Investigate response content first.

**Shell quoting rules:**
- Always single-quote jq filters (avoid double quotes)
- Use `==` instead of `!=` (inequality can cause shell quoting issues)
- Use `<= 0` instead of `!= 0` or negated `> 0`
- Use `test("pattern") | not` instead of `!~`

---


## 📊 COMPLETE BEST-BETS DATA FLOW (END-TO-END)

**CRITICAL:** This section documents the COMPLETE flow from API fetch → filtering → scoring → persistence. **CHECK THIS FIRST** before asking any questions about best-bets.

### Overview: How Best-Bets Are Generated

```
User Request: GET /live/best-bets/NBA
         ↓
Check Cache (5-10 min TTL)
         ↓ CACHE MISS
1. FETCH: Get raw data from Odds API
   - raw_prop_games = get_props(sport)    // ALL upcoming events (60+ games)
   - raw_games = get_games(sport)         // ALL upcoming events
         ↓
2. FILTER: ET timezone gate (TODAY ONLY)
   - Props: filter_events_et(raw_prop_games, date_str)   [line 3027]
   - Games: filter_events_et(raw_games, date_str)        [line 3051]
   - Drops: Events for tomorrow/yesterday
         ↓
3. SCORE: 4 base engines + Jason Sim 2.0
   - AI (25%) + Research (35%) + Esoteric (15%) + Jarvis (25%)
   - Confluence boost + MSRF/SERP (if enabled) + Jason Sim boost
   - Tier assignment (TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN)
         ↓
4. FILTER: Score threshold (>= 6.5)
   - Drops: All picks with final_score < 6.5
         ↓
5. FILTER: Contradiction gate
   - Drops: Opposite sides of same bet (Over AND Under)
         ↓
6. PERSIST: Write to storage
   - File: /data/grader/predictions.jsonl
   - Function: grader_store.persist_pick(pick_data)  [line 3794]
         ↓
7. CACHE: Store response (5-10 min)
         ↓
8. RETURN: Top picks to frontend
```

### Data Sources (External APIs)

**Odds API** (`ODDS_API_KEY`)
- **Endpoint:** Custom props/games endpoints
- **Returns:** ALL upcoming events across multiple days (60+ events possible)
- **Cache:** 8 hours (props don't change frequently)
- **Used for:** Props, games, odds, lines

**Playbook API** (`PLAYBOOK_API_KEY`)
- **Endpoint:** `/splits`, `/injuries`, `/lines`
- **Cache:** 5 minutes
- **Used for:** Sharp money, public splits, injury data

**BallDontLie GOAT** (`BALLDONTLIE_API_KEY`)
- **Endpoint:** Player stats, box scores
- **Used for:** NBA grading, player resolution

### Implementation Details (live_data_router.py)

**Line 97-102: Import ET filtering**
```python
from core.time_et import (
    now_et,
    et_day_bounds,
    is_in_et_day,
    filter_events_et,  # Single source of truth
)
TIME_ET_AVAILABLE = True
```

**Line ~3000: Fetch props from Odds API**
```python
raw_prop_games = get_props(sport)
# Returns: ALL upcoming prop events (could be 60+ games across multiple days)
```

**Line 3027: Filter props to TODAY ONLY (ET timezone)**
```python
if TIME_ET_AVAILABLE and raw_prop_games:
    prop_games, _dropped_props_window, _dropped_props_missing = filter_events_et(
        raw_prop_games,
        date_str  # "2026-01-29" in ET
    )
    logger.info("PROPS TODAY GATE: kept=%d, dropped_window=%d, dropped_missing=%d",
                len(prop_games), len(_dropped_props_window), len(_dropped_props_missing))
```

**Line ~3040: Fetch games from Odds API**
```python
raw_games = get_games(sport)
# Returns: ALL upcoming game events (could be 25+ games across multiple days)
```

**Line 3051: Filter games to TODAY ONLY (ET timezone)**
```python
if TIME_ET_AVAILABLE:
    raw_games, _dropped_games_window, _dropped_games_missing = filter_events_et(
        raw_games,
        date_str
    )
    logger.info("GAMES TODAY GATE: kept=%d, dropped_window=%d, dropped_missing=%d",
                len(raw_games), len(_dropped_games_window), len(_dropped_games_missing))
```

**Lines 3075-3410: Score each filtered event**
```python
for prop in prop_games:  # ONLY today's events (filtered)
    # Run through 4 base engines + Jason Sim
    score_result = calculate_pick_score(
        candidate=prop,
        ai_score=...,
        research_score=...,
        esoteric_score=...,
        jarvis_score=...,
    )
    # Filter: final_score >= 6.5
    if score_result["final_score"] < 6.5:
        continue
```

**Line 3794: Persist picks to storage**
```python
from grader_store import persist_pick

pick_result = persist_pick(pick_data)
# Writes to: /data/grader/predictions.jsonl
```

### ET Timezone Filtering (MANDATORY)

**Module:** `core/time_et.py` (SINGLE SOURCE OF TRUTH)

**Functions:**
- `now_et()` - Get current time in ET
- `et_day_bounds(date_str)` - Get ET day bounds [00:00:00 ET, 00:00:00 next day ET)
- `is_in_et_day(event_time, date_str)` - Boolean check
- `filter_events_et(events, date_str)` - Filter to ET day, returns (kept, dropped_window, dropped_missing)

**CANONICAL WINDOW:** [00:00:00 ET, 00:00:00 ET next day) - half-open interval

**Timezone:** America/New_York (explicit via zoneinfo)

**Why This Is Critical:**
- Without ET gating: `get_props()` returns 60+ games across multiple days
- Causes: Inflated counts, ghost picks, score distribution skew
- **EVERY data path touching Odds API MUST filter to ET day**

**Verification:**
```bash
# Check ET date
curl /live/debug/time | jq '.et_date'
# Returns: "2026-01-29"

# Check best-bets filter_date matches
curl /live/best-bets/NBA?debug=1 | jq '.debug.date_window_et.filter_date'
# Returns: "2026-01-29" (MUST MATCH)

# Check filtering telemetry
curl /live/best-bets/NBA?debug=1 | jq '.debug.date_window_et'
# Shows: events_before_props, events_after_props, dropped counts
```

### Cache Strategy

| Data Type | Cache TTL | Where Cached | Invalidation |
|-----------|-----------|--------------|--------------|
| **Props from Odds API** | 8 hours | In-memory | Time-based |
| **Best-bets response** | 5-10 minutes | In-memory | Time-based |
| **Live scores** | 2 minutes | In-memory | Time-based |
| **Splits/Lines** | 5 minutes | In-memory | Time-based |

### On-Demand vs Scheduled

**Scheduled (Background - Warms Cache):**
| Time | What | Purpose |
|------|------|---------|
| 10:00 AM | Props fetch (all sports) | Morning games |
| 12:00 PM | Props fetch (NBA/NCAAB, weekends only) | Noon games |
| 2:00 PM | Props fetch (NBA/NCAAB, weekends only) | Afternoon games |
| 6:00 PM | Props fetch (all sports) | Evening games |

**On-Demand (User Request):**
1. Frontend calls `/live/best-bets/NBA`
2. Backend checks cache (5-10 min TTL)
3. **If cache hit:** Return cached response (~100ms) ✅
4. **If cache miss:**
   - Fetch from Odds API (~2-3 seconds)
   - Filter to TODAY only (ET timezone)
   - Score through 4 base engines (~2-3 seconds)
   - Filter to >= 6.5, apply contradiction gate
   - Persist to storage
   - Cache response
   - Return to frontend (~5-6 seconds total)

### Scoring Pipeline (4 Engines + Jason Sim)

**Formula:**
```
BASE_4 = (AI × 0.25) + (Research × 0.35) + (Esoteric × 0.20) + (Jarvis × 0.20)
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment
```

**Engines:**
1. **AI (25%)** - 8 AI models with dynamic calibration
2. **Research (35%)** - Sharp money, line variance, public fade
3. **Esoteric (15%)** - Numerology, astro, fib, vortex, daily edge (v20.19: reduced from 20%)
4. **Jarvis (25%)** - Gematria triggers, mid-spread goldilocks (v20.19: increased from 20%)

**Post-Pick:**
5. **Jason Sim 2.0** - Confluence boost (can be negative)
6. **MSRF / SERP** - Optional additive boosts (must never be weighted engines)

**Output Filters:**
1. Score >= 6.5 (MANDATORY)
2. Contradiction gate (no opposite sides)
3. Titanium 3/4 rule (>= 3 engines >= 8.0)

### Persistence (AutoGrader Integration)

**Write Path:**
- Endpoint: `/live/best-bets/{sport}` (line 3794)
- Function: `grader_store.persist_pick(pick_data)`
- File: `/data/grader/predictions.jsonl`
- Format: JSONL (one pick per line, append-only)

**Read Path:**
- AutoGrader: `grader_store.load_predictions(date_et)`
- Daily audit: Grades picks from this file
- Weight learning: Updates weights based on results

**Storage Survives:**
- Container restarts ✅
- Railway deployments ✅
- App crashes ✅

### Debug Telemetry (Available with ?debug=1)

```json
{
  "debug": {
    "date_window_et": {
      "filter_date": "2026-01-29",           // ET date used
      "start_et": "00:00:00",                // Window start
      "end_et": "23:59:59",                  // Window end
      "events_before_props": 60,             // Before ET filter
      "events_after_props": 12,              // After ET filter
      "dropped_out_of_window_props": 48,     // Tomorrow/yesterday
      "events_before_games": 25,
      "events_after_games": 8,
      "dropped_out_of_window_games": 17
    },
    "filtered_below_6_5_total": 1012,        // Picks < 6.5 dropped
    "filtered_below_6_5_props": 850,
    "filtered_below_6_5_games": 162,
    "contradiction_blocked_total": 323,      // Opposite sides blocked
    "contradiction_blocked_props": 310,
    "contradiction_blocked_games": 13,
    "picks_logged": 12,                      // New picks persisted
    "picks_skipped_dupes": 8,                // Already logged today
    "pick_log_errors": [],                   // Any errors
    "total_elapsed_s": 5.57                  // Response time
  }
}
```

### Key Files & Line Numbers

| File | Lines | Purpose |
|------|-------|---------|
| `live_data_router.py` | 97-102 | Import ET filtering functions |
| `live_data_router.py` | ~3000 | Fetch props from Odds API |
| `live_data_router.py` | 3027 | **Props ET filtering (BEFORE scoring)** |
| `live_data_router.py` | ~3040 | Fetch games from Odds API |
| `live_data_router.py` | 3051 | **Games ET filtering (BEFORE scoring)** |
| `live_data_router.py` | 3075-3410 | Scoring loop (filtered events only) |
| `live_data_router.py` | 3794 | **Persist picks to grader_store** |
| `core/time_et.py` | All | Single source of truth for ET timezone |
| `core/titanium.py` | All | Single source of truth for Titanium rule |
| `grader_store.py` | All | Pick persistence (JSONL storage) |
| `tiering.py` | All | Tier assignment (uses core/titanium.py) |

### NEVER Forget These Rules

1. ✅ **ALWAYS filter to ET day BEFORE scoring** (lines 3027, 3051)
2. ✅ **ALWAYS use `core/time_et.py`** - NO other date helpers
3. ✅ **ALWAYS persist picks** after scoring (line 3794)
4. ✅ **ALWAYS filter to >= 6.5** before returning
5. ✅ **ALWAYS apply contradiction gate** (no opposite sides)
6. ✅ **ALWAYS verify filter_date matches et_date** in debug output
7. ✅ **NEVER skip ET filtering** on any Odds API data path
8. ✅ **NEVER use pytz** - only zoneinfo allowed
9. ✅ **NEVER create duplicate date helper functions**
10. ✅ **NEVER modify this flow without reading this section first**

### Common Questions (Answer From This Section)

**Q: When do we fetch best-bets throughout the day?**
A: On-demand when `/live/best-bets/{sport}` is called. Scheduled props fetches at 10 AM, 12 PM (weekends), 2 PM (weekends), 6 PM warm the cache.

**Q: How long are best-bets cached?**
A: 5-10 minutes. Props from Odds API are cached 8 hours.

**Q: Where are picks persisted?**
A: `/data/grader/predictions.jsonl` via `grader_store.persist_pick()` at line 3794.

**Q: How do we filter to today's games only?**
A: `filter_events_et(events, date_str)` from `core/time_et.py` at lines 3027 (props) and 3051 (games).

**Q: What happens if Odds API returns tomorrow's games?**
A: They are DROPPED by ET filtering. Only events in 00:00:00-23:59:59 ET are kept.

**Q: How do we prevent both Over and Under for same bet?**
A: Contradiction gate after scoring, before returning to frontend.

---

### Storage Configuration (Railway Volume) - UNIFIED JANUARY 29, 2026

**🚨 CRITICAL: READ THIS BEFORE TOUCHING STORAGE/AUTOGRADER CODE 🚨**

**ALL STORAGE IS NOW ON THE RAILWAY PERSISTENT VOLUME AT `/data`**

#### Storage Architecture (UNIFIED)

```
/data/  (Railway 5GB persistent volume)
├── grader/
│   └── predictions.jsonl           ← Picks (grader_store.py)
├── grader_data/
│   ├── weights.json                ← Learned weights (data_dir.py)
│   └── predictions.json            ← Weight learning data
├── audit_logs/
│   └── audit_{date}.json           ← Daily audits (data_dir.py)
└── pick_logs/                      ← Legacy (unused)
```

#### Three Storage Subdirectories (ALL ON SAME VOLUME)

**1. Picks Storage** (`/data/grader/`)
- **File**: `predictions.jsonl`
- **Module**: `storage_paths.py` → `grader_store.py`
- **Used by**: Best-bets endpoint (write), Autograder (read/write)
- **Format**: JSONL (one pick per line)
- **Purpose**: High-frequency pick logging

**2. Weight Learning Storage** (`/data/grader_data/`)
- **Files**: `weights.json`, `predictions.json`
- **Module**: `data_dir.py` → `auto_grader.py`
- **Used by**: Auto-grader weight learning
- **Format**: JSON
- **Purpose**: Low-frequency weight updates after daily audit

**3. Audit Storage** (`/data/audit_logs/`)
- **Files**: `audit_{YYYY-MM-DD}.json`
- **Module**: `data_dir.py` → `daily_scheduler.py`
- **Used by**: Daily 6 AM audits
- **Format**: JSON
- **Purpose**: Audit history

#### Environment Variables (UNIFIED)
- `RAILWAY_VOLUME_MOUNT_PATH=/data` (Railway sets this automatically)
- **BOTH** `storage_paths.py` AND `data_dir.py` now use this env var
- **ALL** storage paths derived from this single root
- This path **IS PERSISTENT** - it's a mounted 5GB Railway volume

#### Critical Facts (NEVER FORGET)

1. **`/data` IS THE RAILWAY PERSISTENT VOLUME**
   - Verified with `os.path.ismount() = True`
   - NOT ephemeral, NOT wiped on redeploy
   - Survives container restarts

2. **ALL STORAGE MUST USE RAILWAY_VOLUME_MOUNT_PATH**
   - `storage_paths.py`: ✅ Uses RAILWAY_VOLUME_MOUNT_PATH
   - `data_dir.py`: ✅ Uses RAILWAY_VOLUME_MOUNT_PATH (unified Jan 29)
   - Both resolve to `/data`

3. **NEVER add code to block `/app/*` paths**
   - `/data` is the CORRECT persistent storage
   - Blocking `/app/*` will crash production (Jan 28-29 incident)

4. **Dual storage structure is INTENTIONAL**
   - Picks: Separate from weights (different access patterns)
   - Weights: Separate from picks (avoid lock contention)
   - Both on SAME volume, different subdirs

5. **Learned weights now persist across deployments**
   - Before: `/data/grader_data/` (ephemeral, wiped on restart)
   - After: `/data/grader_data/` (persistent, survives restarts)

#### Verification Commands
```bash
# Check picks storage health
curl https://web-production-7b2a.up.railway.app/internal/storage/health

# Check grader status (shows all three storage paths)
curl https://web-production-7b2a.up.railway.app/live/grader/status \
  -H "X-API-Key: YOUR_KEY"

# Verify autograder can see picks
curl -X POST https://web-production-7b2a.up.railway.app/live/grader/dry-run \
  -H "X-API-Key: YOUR_KEY" -d '{"date":"2026-01-29","mode":"pre"}'

# Check if both modules use same volume
grep -n "RAILWAY_VOLUME_MOUNT_PATH" storage_paths.py data_dir.py
```

#### The Rule (MANDATORY)

**BEFORE touching storage/autograder/scheduler code:**

1. ✅ Read this Storage Configuration section
2. ✅ Verify production health with endpoints above
3. ✅ Check that RAILWAY_VOLUME_MOUNT_PATH is used
4. ✅ NEVER assume paths are wrong without verification

**NEVER:**
- ❌ Add path validation that blocks `/app/*` - crashes production
- ❌ Modify storage paths without reading this section
- ❌ Assume `/data` is ephemeral - it's the persistent volume
- ❌ Change RAILWAY_VOLUME_MOUNT_PATH usage in storage_paths.py or data_dir.py
- ❌ Create new storage paths outside `/data`

#### Past Mistakes (NEVER REPEAT)

**January 28-29, 2026 - Storage Path Blocker Incident:**
- ❌ Added code to block all `/app/*` paths in data_dir.py
- ❌ Assumed `/data` was ephemeral
- ❌ Did NOT read this documentation before making changes
- ❌ Did NOT verify storage health before assuming paths wrong
- 💥 **Result**: Production crashed (502 errors), 2 minutes downtime
- ✅ **Fix**: Removed path blocker, unified to RAILWAY_VOLUME_MOUNT_PATH
- 📚 **Lesson**: `/data` IS the Railway volume (NOT ephemeral)

**January 29, 2026 - Storage Unification (FINAL):**
- ✅ Unified data_dir.py to use RAILWAY_VOLUME_MOUNT_PATH
- ✅ Removed `/app/*` path blocker
- ✅ Changed fallback from `/data` to `./grader_data` for local dev
- ✅ Now ALL storage on same Railway persistent volume
- ✅ Learned weights now persist across deployments

### SSH Configuration
- GitHub SSH uses port 443 (not 22) - configured in `~/.ssh/config`
- This is already set up and working

---


## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v14.2 PRODUCTION HARDENED
**Stack:** Python 3.11+, FastAPI, Railway deployment
**Frontend:** bookie-member-app (separate repo)
**Production URL:** https://web-production-7b2a.up.railway.app

---

## IMPORTANT: Paid APIs - Always Use These

**We pay for Odds API and Playbook API. Always use these for any data needs:**

| API | Purpose | Key |
|-----|---------|-----|
| **Odds API** | Live odds, lines, betting data, historical props | `ODDS_API_KEY` |
| **Playbook API** | Player stats, game logs, sharp money, splits (all 5 sports) | `PLAYBOOK_API_KEY` |

**Default to our paid APIs first.** These cover all 5 sports: **NBA, NFL, MLB, NHL, NCAAB**

**Exception:** You may suggest alternative APIs if:
1. You explain WHY it's better than our paid APIs (data not available, better quality, etc.)
2. You get approval before implementing
3. There's a clear benefit over what we're already paying for

### Playbook API v1 Endpoints

**Base URL:** `https://api.playbook-api.com/v1`
**Auth:** `api_key` query parameter (NOT Bearer header)
**Leagues:** NBA | NFL | CFB | MLB | NHL (uppercase)

| Endpoint | Purpose | Required Params |
|----------|---------|-----------------|
| `/health` | Health check | none |
| `/me` | Plan + usage info | `api_key` |
| `/teams` | Team metadata + injuries | `league`, `api_key` |
| `/injuries` | Injury report by team | `league`, `api_key` |
| `/splits` | Public betting splits | `league`, `api_key` |
| `/splits-history` | Historical splits | `league`, `date`, `api_key` |
| `/odds-games` | Schedule + gameId list | `league`, `api_key` |
| `/lines` | Current spread/total/ML | `league`, `api_key` |
| `/games` | Game objects from splits | `league`, `date`, `api_key` |

### API Usage Monitoring

**IMPORTANT:** Monitor API usage to avoid hitting limits, especially if community usage grows.

| Endpoint | Purpose |
|----------|---------|
| `GET /live/api-health` | Quick status check (for dashboards) |
| `GET /live/api-usage` | Combined usage with threshold warnings |
| `GET /live/playbook/usage` | Playbook plan + quota info |
| `GET /live/odds-api/usage` | Odds API requests remaining |

**Threshold Warning Levels:**
| Level | % Used | Emoji | Action |
|-------|--------|-------|--------|
| `HEALTHY` | < 25% | ✅ | None needed |
| `CAUTION_25` | 25-49% | 🟢 | Monitor |
| `CAUTION_50` | 50-74% | 🟡 | Watch closely |
| `CAUTION_75` | 75-89% | 🟠 | Consider upgrading |
| `CRITICAL` | 90%+ | 🚨 | UPGRADE NOW |

**Response includes:**
- `overall_status`: Worst status across all APIs
- `action_needed`: true if CRITICAL or CAUTION_75
- `alerts`: List of warning messages
- `summary`: Human-readable status message

**Odds API Info:**
- Resets monthly
- Free tier = 500 requests/month
- Headers: `x-requests-remaining`, `x-requests-used`

**Quick check command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-health" -H "X-API-Key: YOUR_KEY"
```

**Full details:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-usage" -H "X-API-Key: YOUR_KEY"
```

---


## CRITICAL: Today-Only ET Gate (NEVER skip this)

**Every data path that touches Odds API events MUST filter to today-only in ET before processing.**

### Single Source of Truth: `core/time_et.py`

**ONLY use these functions - NO other date helpers allowed:**
- `now_et()` - UTC to ET conversion
- `et_day_bounds(date_str=None)` - Returns (start_et, end_et, et_date)
- `is_in_et_day(event_time, date_str=None)` - Boolean check
- `filter_events_et(events, date_str=None)` - Filter to ET day

**Server clock is UTC. All app logic enforces ET (America/New_York).**

### Rules
1. **Props AND game picks** must both pass through `filter_events_et()` before iteration
2. The day boundary is **[00:00:00 ET, 00:00:00 ET next day)** — start at midnight, end exclusive
3. `filter_events_et(events, date_str)` returns `(kept, dropped_window, dropped_missing)` — always log the drop counts
4. `date_str` (YYYY-MM-DD) must be threaded through the full call chain: endpoint → `get_best_bets(date=)` → `_best_bets_inner(date_str=)` → `filter_events_et(events, date_str)`
5. Debug output must include `dropped_out_of_window_props`, `dropped_out_of_window_games`, `dropped_missing_time_props`, `dropped_missing_time_games`
6. **All `filter_date` fields MUST match `/debug/time` endpoint's `et_date`**

### Why
Without the gate, `get_props()` returns ALL upcoming events from Odds API (could be 60+ games across multiple days). This causes:
- Inflated candidate counts
- Ghost picks for games not happening today
- Score distribution skewed by tomorrow's games

### Where it lives
- **`core/time_et.py`**: SINGLE SOURCE OF TRUTH - `now_et()`, `et_day_bounds()`, `is_in_et_day()`, `filter_events_et()`
- `live_data_router.py` `_best_bets_inner()`: applied to both props loop (~line 3018) and game picks (~line 3042)
- `main.py` `/ops/score-distribution`: passes `date=date` to `get_best_bets()`

### Debug Endpoint
**`GET /live/debug/time`** - Returns current ET time info:
```json
{
  "now_utc_iso": "2026-01-29T02:48:33.886614+00:00",
  "now_et_iso": "2026-01-28T21:48:33.886625-05:00",
  "et_date": "2026-01-28",
  "et_day_start_iso": "2026-01-28T00:00:00-05:00",
  "et_day_end_iso": "2026-01-29T00:00:00-05:00",
  "build_sha": "5c0f104",
  "deploy_version": "15.1"
}
```

### Verification
```bash
# Check ET date
curl /live/debug/time | jq '.et_date'

# Verify filter_date matches
curl /live/best-bets/NHL?debug=1 | jq '.debug.date_window_et.filter_date'

# Should match /debug/time.et_date
```

### If adding a new data path
If you add ANY new endpoint or function that processes Odds API events, you MUST:
1. Import from `core.time_et` ONLY
2. Apply `filter_events_et()` before iteration
3. Use `et_day_bounds()` for date calculations
4. NO other date helpers allowed - NO pytz, NO time_filters.py

---


## Signal Architecture (Option A: 4-Engine + Context Modifier)

### Scoring Formula
```
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment
```

All engines score 0-10. Min output threshold: **6.5** (picks below this are filtered out).

### Engine 1: AI Score (25%)
- 8 AI Models (0-8 scaled to 0-10) - `advanced_ml_backend.py`
- Dynamic calibration: +0.5 sharp present, +0.25-1.0 signal strength, +0.5 favorable spread, +0.25 player data
- LSTM receives real context data (def_rank, pace, vacuum) via context layer

### Engine 2: Research Score (35%)
- Sharp Money (0-3 pts): STRONG/MODERATE/MILD signal from Playbook splits
- Line Variance (0-3 pts): Cross-book spread variance from Odds API
- Public Fade (0-2 pts): Contrarian signal at ≥65% public + ticket-money divergence ≥5%
- Base (2-3 pts): 2.0 default, 3.0 when real splits data present with money-ticket divergence
- Officials adjustment (Pillar 16): OfficialsAnalyzer adjusts based on referee tendencies

### Engine 3: Esoteric Score (15%)
- 29 signals across GLITCH Protocol, Phase 8, Physics, Math Glitch, Phase 1, and Context
- **Active signals: 23** | Dormant: 4 | Disabled: 1 (noosphere - SERP cancelled)
- **GLITCH Protocol (5 active)**: chrome_resonance, void_moon, hurst, kp_index, benford
- **Phase 8 (5 active)**: lunar_phase, mercury_retrograde, rivalry_intensity, streak_momentum, solar_flare
- External dependency: NOAA Space Weather API (3-hour cache, fail-soft)
- Output: `esoteric_score` [0.0-10.0], `esoteric_reasons[]`, `esoteric_contributions{}`
- Park Factors (Pillar 17, MLB only): Venue-based adjustments
- **Audit doc**: `docs/AUDIT_ENGINE3_ESOTERIC.md` — canonical boundary map with all 29 signals

### Engine 4: Jarvis Score (25%)
- Gematria triggers: 2178, 201, 33, 93, 322
- Mid-spread Goldilocks, trap detection
- `jarvis_savant_engine.py`

### Context Modifier (bounded, NOT an engine)
- Derived from Defensive Rank (50%), Pace (30%), Vacuum (20%)
- Bounded modifier cap: ±0.35 (see `CONTEXT_MODIFIER_CAP`)
- Services: DefensiveRankService, PaceVectorService, UsageVacuumService

### Confluence (Option A — STRONG gate + HARMONIC_CONVERGENCE)
- Alignment = `1 - abs(research - esoteric) / 10`
- **HARMONIC_CONVERGENCE (+4.5)**: Research ≥ 8.0 AND Esoteric ≥ 8.0 ("Golden Boost" when Math+Magic align)
- **STRONG (+3)**: alignment ≥ 80% **AND** at least one active signal (`jarvis_active`, `research_sharp_present`, or `jason_sim_boost != 0`). If alignment ≥70% but no active signal, downgrades to MODERATE.
- MODERATE (+1): alignment ≥ 60%
- DIVERGENT (+0): below 60%
- PERFECT/IMMORTAL: both ≥7.5 + jarvis ≥7.5 + alignment ≥80%

**Why the gate**: Without it, two engines that are both mediocre (e.g., R=4.0, E=4.0) get 100% alignment and STRONG +3 boost for free, inflating scores without real conviction.

**HARMONIC_CONVERGENCE**: When both Research (market signals) and Esoteric (cosmic signals) score ≥8.0, it represents exceptional alignment between analytical and intuitive sources. This adds +1.5 scaled boost (equivalent to +15 on 100-point).

### CRITICAL: GOLD_STAR Hard Gates (Option A)

**GOLD_STAR tier requires ALL of these engine minimums. If any fails, downgrade to EDGE_LEAN.**

| Gate | Threshold | Why |
|------|-----------|-----|
| `ai_gte_6.8` | AI ≥ 6.8 | AI models must show conviction |
| `research_gte_6.5` | Research ≥ 6.5 | Must have real market signals (sharp/splits/variance) |
| `jarvis_gte_6.5` | Jarvis ≥ 6.5 | Jarvis triggers must fire |
| `esoteric_gte_5.5` | Esoteric ≥ 5.5 | Esoteric components must contribute |
| `context_gte_4.0` | **REMOVED** | Context is a modifier, not a hard gate |

**Output includes**: `scoring_breakdown.gold_star_gates` (dict of gate→bool), `gold_star_eligible` (bool), `gold_star_failed` (list of failed gate names).

**Where it lives**: `live_data_router.py` `calculate_pick_score()`, after `tier_from_score()` call.

### Tier Hierarchy
| Tier | Score Threshold | Additional Requirements |
|------|----------------|------------------------|
| TITANIUM_SMASH | 3/4 engines ≥ 8.0 | Overrides all other tiers |
| GOLD_STAR | ≥ 7.5 | Must pass ALL hard gates |
| EDGE_LEAN | ≥ 6.5 | Default for picks above output filter |
| MONITOR | ≥ 5.5 | Below output filter (hidden) |
| PASS | < 5.5 | Below output filter (hidden) |

### If modifying confluence or tiers
1. Do NOT remove STRONG eligibility gate — it prevents inflation from aligned-but-weak engines
2. Do NOT remove GOLD_STAR hard gates — they ensure only picks with real multi-engine conviction get top tier
3. Run debug mode and verify gates show in `scoring_breakdown`
4. Check that STRONG only fires with alignment ≥80% + active signal

---

---

### INVARIANT 11: Integration Contract (Part B)

**RULE:** All API integrations must be defined in `core/integration_contract.py`

**Canonical Source:**
- `core/integration_contract.py` - All integration definitions
- `integration_registry.py` - Runtime registry (imports from contract)
- `docs/AUDIT_MAP.md` - **GENERATED** (do not edit manually)

**Generation:**
```bash
./scripts/generate_audit_map.sh
```

**Validation:**
```bash
./scripts/validate_integration_contract.sh
```

**Weather Integration Rules:**
- Required but **relevance-gated** (not feature-disabled)
- Allowed statuses: `VALIDATED`, `CONFIGURED`, `NOT_RELEVANT`, `UNAVAILABLE`, `ERROR`, `MISSING`
- **BANNED statuses:** `FEATURE_DISABLED`, `DISABLED` (hard ban)
- Returns `NOT_RELEVANT` for indoor sports (NBA, NHL)

**Never do:**
- Add integration without adding to `core/integration_contract.py`
- Edit `docs/AUDIT_MAP.md` manually
- Allow weather to return `FEATURE_DISABLED` status
- Add hidden feature flags to disable required integrations

---

### INVARIANT 12: Logging Visibility (KEEP INFO TELEMETRY)

**RULE:** Keep startup INFO telemetry in production. Do not lower log level globally or suppress INFO logs.

**Required startup logs (must remain visible):**
- Redis connection status (`Redis caching enabled`, `Redis cache connected`)
- Scheduler job registration (`Auto-grading enabled`, `Cache pre-warm enabled`, `APScheduler started`)
- Prediction load count (`Loaded N predictions from...`)
- Health check requests (`GET /health`)

**Why:** These logs are operational telemetry for debugging and monitoring. They confirm the system initialized correctly and help diagnose issues.

**Allowed suppression:**
- TensorFlow/CUDA noise (GPU probing errors) - already suppressed via env vars
- Third-party library DEBUG/TRACE logs
- Repetitive per-request logs (if needed for performance)

**Never do:**
- Set global log level to WARNING/ERROR in production
- Suppress uvicorn INFO logs for startup/health
- Remove scheduler/Redis connection confirmations
- Hide prediction load counts

---

### INVARIANT 13: PickContract v1 (Frontend-Proof Picks)

**RULE:** Every pick from `/live/best-bets/{sport}` MUST include ALL PickContract v1 fields

**Documentation:** `docs/PICK_CONTRACT_V1.md` (full specification)

**Required Field Groups:**

1. **Core Identity** (12 fields):
   - `id`, `sport`, `league`, `event_id`, `matchup`, `home_team`, `away_team`
   - `start_time_et`, `start_time_iso`, `status`, `has_started`, `is_live`

2. **Bet Instruction** (12 fields):
   - `pick_type`: `"spread"` | `"moneyline"` | `"total"` | `"player_prop"`
   - `market_label`, `selection`, `selection_home_away`, `side_label`
   - `line`, `line_signed`, `odds_american`, `units`, `bet_string`, `book`, `book_link`

3. **Reasoning** (6 fields):
   - `tier`, `score`, `confidence_label`, `signals_fired`, `confluence_reasons`, `engine_breakdown`

**selection_home_away Logic:**
```python
if selection matches home_team → "HOME"
if selection matches away_team → "AWAY"
else → null  # totals, props
```

**SHARP Pick Normalization:**
- SHARP with line → `pick_type: "spread"`
- SHARP without line → `pick_type: "moneyline"`
- Always sets `signal_label: "Sharp Signal"`

**odds_american Policy:**
- NEVER fabricate odds (no default -110)
- If unavailable: `odds_american: null`, bet_string shows `"(N/A)"`

**No Sample Data:**
- Return empty arrays `[]` when no picks available
- NEVER return fake/sample picks

**Anti-Cache Headers (ALL /live/best-bets/* responses):**
```
Cache-Control: no-store, no-cache, must-revalidate, max-age=0, private
Pragma: no-cache
Expires: 0
Vary: Origin, X-API-Key, Authorization
```

**Implementation Files:**
- `utils/pick_normalizer.py` - Single source of truth
- `live_data_router.py` - Applies normalization
- `jason_sim_confluence.py` - SHARP type mapping

**Tests:** `tests/test_pick_contract_v1.py` (12 tests)

**Verification:**
```bash
pytest tests/test_pick_contract_v1.py -v
# All 12 tests must pass
```

---

---



---

## 🤖 Automation & Cron Jobs

### Overview
33 automated jobs run via cron across both repositories. No manual intervention needed as long as Mac is awake.

### Cron Schedule (Backend - ai-betting-backend)

| Schedule | Script | Purpose |
|----------|--------|---------|
| Every 30 min | `response_time_check.sh` | Monitor API latency |
| Every 4 hours | `memory_profiler.sh` | Track memory, detect leaks |
| Hourly | `error_rate_monitor.sh` | Track 4xx/5xx rates |
| Daily 3 AM | `backup_data.sh` | Backup /data persistent storage |
| Daily 4 AM | `db_integrity_check.sh` | Verify JSON/SQLite/pickle integrity |
| Daily 6 AM | `access_log_audit.sh` | Detect unusual API access |
| Daily 9 AM | `daily_health_check.sh` | Full system health check |
| Sunday 5 AM | `prune_old_data.sh` | Clean old logs/cache |
| Sunday 7 AM | `dead_code_scan.sh` | Find unused functions |
| Sunday 10 AM | `dependency_vuln_scan.sh` | pip-audit + npm audit |
| Monday 7 AM | `complexity_report.sh` | Flag complex code |
| Monday 8 AM | `test_coverage_report.sh` | Coverage % report |
| Monday 9:15 AM | `secret_rotation_check.sh` | Check for old secrets |
| Monday 9:30 AM | `feature_flag_audit.sh` | Audit feature flags |

### Log Locations
```bash
# Backend
~/ai-betting-backend/logs/health_check.log  # Daily health
~/ai-betting-backend/logs/cron.log          # All cron output

# Frontend
~/bookie-member-app/logs/cron.log           # All cron output
```

### Verify Cron is Running
```bash
crontab -l | wc -l        # Should show 33+ lines
tail -20 ~/ai-betting-backend/logs/cron.log  # Recent activity
```

### Manual Script Runs
```bash
# Morning check-in
./scripts/session_start.sh

# Before deploys
./scripts/contract_sync_check.sh
./scripts/prod_go_nogo.sh

# Anytime health check
./scripts/daily_health_check.sh
```

### CRITICAL: Path Validation
Cron jobs silently fail if paths are wrong. After any path changes:
```bash
# Verify paths in crontab match reality
crontab -l | grep "cd ~/"
ls -d ~/ai-betting-backend ~/bookie-member-app  # Both must exist
```

### Keep Mac Awake (Optional)
For overnight jobs to run:
- **System Settings → Energy → Prevent automatic sleeping**
- Or run `caffeinate -s` in Terminal

---

---

## 🔒 PRODUCTION SANITY CHECK (REQUIRED BEFORE DEPLOY)

**Script:** `scripts/prod_sanity_check.sh`

This script validates ALL master prompt invariants in production. Run before every deployment.

**Last Verified:** February 3, 2026 - **ALL 18 CHECKS PASSING ✅**

### Usage

```bash
# Run sanity check
./scripts/prod_sanity_check.sh

# With custom base URL
BASE_URL=https://your-deployment.app ./scripts/prod_sanity_check.sh
```

### Daily Sanity Report (Best Bets Health)

Use this for quick daily verification (non-blocking, informational):

```bash
API_KEY=your_key \
API_BASE=https://web-production-7b2a.up.railway.app \
SPORTS="NBA NFL NHL MLB" \
bash scripts/daily_sanity_report.sh
```

Checks:
- `/health` status + build identifiers
- `/live/best-bets/{sport}` counts + top pick sample
- ET-only payload (no UTC/telemetry keys)
- Cache headers on best-bets endpoints

### Option A Handoff Summary (scoring + telemetry)

**Scoring (Option A):**
- Base engines: AI (0.25), Research (0.35), Esoteric (0.20), Jarvis (0.20)
- Context is **NOT** an engine: bounded modifier `context_modifier ∈ [-0.35, +0.35]`
- Final: `BASE_4 + context_modifier + confluence + jason + msrf + serp (if enabled)`

**Titanium / Gold Star:**
- Titanium strict **3-of-4** (AI/Research/Esoteric/Jarvis). Context excluded.
- Gold Star gates evaluate **only** 4 engines. Context excluded.

**Telemetry rules:**
- `last_used_at` is global and updated **only on successful client calls**
- `used_integrations` is **request-scoped** and **debug-only** (`?debug=1`)
- No request_id in non-debug payloads

**Post-deploy smoke checklist (no secrets):**
```bash
BASE_URL="https://your-deployment.app" API_KEY="YOUR_KEY" \
  bash scripts/verify_live_endpoints.sh

BASE_URL="https://your-deployment.app" API_KEY="YOUR_KEY" \
  bash scripts/post_deploy_check.sh
```

### What It Checks (18 Total)

**1. Storage Persistence (4 checks)**
- ✅ `resolved_base_dir` is set to `/data`
- ✅ `is_mountpoint = true` (Railway volume)
- ✅ `is_ephemeral = false` (survives restarts)
- ✅ `predictions.jsonl` exists with picks

**2. Best-Bets Endpoint (4 checks)**
- ✅ `filtered_below_6_5 > 0` (proves filter is active)
- ✅ Minimum returned score >= 6.5 (no picks below threshold)
- ✅ ET filter applied to props (events_before == events_after)
- ✅ ET filter applied to games (events_before == events_after)

**3. Titanium 3-of-4 Rule (1 check)**
- ✅ No picks with `titanium_triggered=true` and < 3 engines >= 8.0
- Validates every pick in response

**4. Grader Status (3 checks)**
- ✅ `available = true` (grader operational)
- ✅ `predictions_logged > 0` (picks being persisted)
- ✅ `storage_path` inside Railway volume (not ephemeral)

**5. ET Timezone Consistency (2 checks)**
- ✅ `et_date` is set (America/New_York)
- ✅ `filter_date` matches `et_date` (single source of truth)

**6. Phase 8 Esoteric Signals (4 checks)**
- ✅ `phase8_boost` field present in picks
- ✅ Lunar phase calculation works (no timezone errors)
- ✅ All 5 signals aggregated via `get_phase8_esoteric_signals()`
- ✅ Phase 8 reasons appear in `esoteric_reasons` or `phase8_reasons`

### Production Verification (Feb 3, 2026)

```bash
================================================
PRODUCTION SANITY CHECK - Master Prompt Invariants
================================================

[1/4] Validating storage persistence...
✓ Storage: resolved_base_dir is set
✓ Storage: is_mountpoint = true
✓ Storage: is_ephemeral = false
✓ Storage: predictions.jsonl exists

[2/4] Validating best-bets endpoint...
✓ Best-bets: filtered_below_6_5 > 0 OR no picks available
✓ Best-bets: minimum returned score >= 6.5
✓ Best-bets: ET filter applied to props (events_before == events_after)
✓ Best-bets: ET filter applied to games (events_before == events_after)

[3/4] Validating Titanium 3-of-4 rule...
✓ Titanium: 3-of-4 rule enforced (no picks with titanium=true and < 3 engines >= 8.0)

[4/4] Validating grader status...
✓ Grader: available = true
✓ Grader: predictions_logged > 0
✓ Grader: storage_path is inside Railway volume

[4/4] Validating ET timezone consistency...
✓ ET Timezone: et_date is set
✓ ET Timezone: filter_date matches et_date (single source of truth)

================================================
✓ ALL SANITY CHECKS PASSED
Production invariants are enforced and working correctly.
================================================
```

### Recent Fixes

**January 29, 2026 - Fixed filter_date Bug (Commit 03a7117)**
- **Issue:** `filter_date` showing "ERROR" due to local imports
- **Root Cause:** Redundant `from core.time_et import et_day_bounds` at lines 3779 and 5029 made Python treat it as local variable
- **Impact:** Caused "cannot access local variable" error at line 2149
- **Fix:** Removed redundant local imports, now uses top-level import consistently
- **Result:** ✅ filter_date now shows correct date ("2026-01-29")

### Exit Codes

- **0** = All checks passed → Safe to deploy ✅
- **1** = One or more failed → **BLOCK DEPLOY** 🚫

### Integration with CI/CD

Add to Railway build command or GitHub Actions:

```yaml
# .github/workflows/deploy.yml
- name: Production Sanity Check
  run: |
    ./scripts/prod_sanity_check.sh
  env:
    BASE_URL: ${{ secrets.PRODUCTION_URL }}
    API_KEY: ${{ secrets.API_KEY }}
```

**NEVER skip this check.** If it fails, production invariants are broken.

---

---

## Authentication

**API Authentication is ENABLED.** Key stored in Railway environment variables (`API_AUTH_KEY`).
- All `/live/*` endpoints require `X-API-Key` header
- `/health` endpoint is public (for Railway health checks)
- `/status` endpoint is public (browser-friendly HTML status page)

### Public Endpoints (No Auth Required)

| Endpoint | Purpose | Format |
|----------|---------|--------|
| `GET /health` | Health check for monitoring | JSON |
| `GET /status` | Browser-friendly status page | HTML |
| `GET /` | API info and endpoint list | JSON |

### Protected Endpoints (Require X-API-Key Header)

All `/live/*` endpoints require the `X-API-Key` header:
```bash
curl -H "X-API-Key: YOUR_API_KEY" https://web-production-7b2a.up.railway.app/live/best-bets/nba
```

### Browser Limitations

**Browsers cannot set custom headers** like `X-API-Key`. This means:
- You CANNOT access `/live/*` endpoints directly in a browser
- Use curl, Postman, or the frontend app for protected endpoints
- The `/status` page is designed for browser access and shows system health

### /status Page Features

The `/status` endpoint provides a browser-friendly HTML page showing:
- **Build Info**: SHA, deploy version, engine version
- **Current Time**: ET date and time
- **Internal Health**: Storage, database, Redis, scheduler (✅/❌)
- **Curl Examples**: How to access protected endpoints

**Rate Limited**: 10 requests per minute per IP

**Example**:
```bash
# Open in browser or curl
curl https://web-production-7b2a.up.railway.app/status
```

### Smoke Test Script

Use `scripts/smoke_test.sh` to verify basic functionality:
```bash
# Test production
./scripts/smoke_test.sh

# Test local
BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh
```

---

---

## 📚 CONTENT MOVED TO COMPANION FILES

The following sections have been moved to reduce context load:

1. **ML REFERENCE (1,597 lines)** → `docs/ML_REFERENCE.md`
   - LSTM models, GLITCH protocol, Phase 1-2 signals, file index
   - Load when: working on ML models, scoring, or esoteric signals

2. **LESSONS LEARNED (2,293 lines)** → `docs/LESSONS_LEARNED.md`
   - 50+ historical bugs, root causes, and prevention rules
   - Load when: debugging issues that seem familiar

3. **NEVER DO THESE (33 sections, 651 lines)** → `docs/NEVER_DO.md`
   - Consolidated rules for: ML, Security, API, Esoteric, Deployment, etc.
   - Load when: modifying code in that subsystem

4. **VERIFICATION CHECKLISTS (17 sections, 1,440 lines)** → `docs/CHECKLISTS.md`
   - Pre-deploy checklists for every subsystem
   - Load when: preparing to deploy changes

5. **SESSION NOTES (419 lines)** → `docs/SESSION_NOTES.md`
   - Codex DNS issues, GitHub push troubleshooting
   - Load when: hitting infrastructure problems

**To load a companion file in Claude Code:**
```bash
cat docs/LESSONS_LEARNED.md  # Full file
grep -A 30 "Lesson 5" docs/LESSONS_LEARNED.md  # Specific lesson
```

---
