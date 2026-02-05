# CLAUDE.md - Project Instructions for AI Assistants

## Sister Repositories

| Repo | Purpose | URL |
|------|---------|-----|
| **This repo** | Backend API (Python/FastAPI) | [ai-betting-backend](https://github.com/peterostrander2/ai-betting-backend) |
| **Frontend** | Member dashboard (React/Vite) | [bookie-member-app](https://github.com/peterostrander2/bookie-member-app) |

**Production:** https://web-production-7b2a.up.railway.app

**Frontend Integration Guide:** See `docs/FRONTEND_INTEGRATION.md` for backend→frontend field mapping and pending frontend work.

---

## Session Management

**To prevent Claude Code context limit errors:**

1. Checkpoint commit every 30-60 minutes:
```bash
   ./scripts/checkpoint_commit.sh
```

2. Use `/compact` in Claude Code when you see:
   - "Conversation compacted" messages
   - Slower responses
   - Large repeated file reads

3. Split large refactors across multiple sessions

See `docs/SESSION_HYGIENE.md` for complete guide.

---

## 📚 MASTER INDEX (Quick Reference)

### Critical Invariants (26 Total)
| # | Name | Summary |
|---|------|---------|
| 1 | Storage Persistence | ALL data under `RAILWAY_VOLUME_MOUNT_PATH=/data` |
| 2 | Titanium 3-of-4 Rule | `titanium=true` ONLY when ≥3 of 4 engines ≥8.0 |
| 3 | ET Today-Only Gating | ALL picks for games in today's ET window ONLY |
| 4 | Option A Scoring | 4-engine base (AI 25%, Research 35%, Esoteric 20%, Jarvis 20%) + context modifier |
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
| 16 | 17-Pillar Scoring | All 17 pillars active (see detailed list) |
| 17 | Harmonic Convergence | +1.5 boost when Research AND Esoteric ≥7.5 |
| 18 | Secret Redaction | API keys never in logs |
| 19 | Demo Data Hard Gate | Block demo/test data in production |
| 20 | MSRF Boost | ±1.0 cap on MSRF adjustments |
| 21 | Dual-Use Functions | Must return dicts (not Response objects) |
| 22 | ESPN Integration | Injuries, officials, lineups from ESPN |
| 23 | SERP Intelligence | Web search boost capped at 4.3 |
| 24 | Trap Learning Loop | Daily trap evaluation and weight adjustment |
| 25 | Complete Learning | End-to-end grading → bias → weight updates |
| 26 | Total Boost Cap | Sum of confluence+msrf+jason+serp capped at 3.5 |

### Lessons Learned (54 Total) - Key Categories
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

### NEVER DO Sections (24 Categories)
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
```

### Key Files Reference
| File | Purpose |
|------|---------|
| `core/scoring_contract.py` | Scoring constants (Option A weights, thresholds, boost caps, calibration) |
| `core/scoring_pipeline.py` | Score calculation (single source of truth) |
| `live_data_router.py` | Main API endpoints, pick scoring |
| `utils/pick_normalizer.py` | Pick contract normalization (single source for all pick fields) |
| `auto_grader.py` | Learning loop, bias calculation, weight updates |
| `result_fetcher.py` | Game result fetching, pick grading |
| `grader_store.py` | Pick persistence (predictions.jsonl) |
| `utils/contradiction_gate.py` | Prevents opposite side picks |
| `integration_registry.py` | Env var registry, integration config |

### Current Version: v20.8 (Feb 5, 2026)
**Latest Fix (v20.8):**
- Lesson 54: CRITICAL — Props indentation bug made `props_picks.append()` unreachable dead code; ALL sports returned 0 props
- Root cause: `if _props_deadline_hit: break` placed BETWEEN `calculate_pick_score()` and prop processing code
- Fix: Moved deadline check AFTER `props_picks.append()` so each prop is fully processed before checking the deadline

**Previous Fix (v20.7):**
- Lesson 53: SERP sequential bottleneck — parallel pre-fetch reduces ~17s to ~2-3s, fixes props returning 0 picks
- Performance: `serp_prefetch` timing now in debug telemetry (`debug.serp.prefetch_cached`)

**Previous Fixes (v20.6):**
- Lesson 49: Props timeout — TIME_BUDGET_S configurable, increased 40→55s default
- Lesson 50: Empty description fields — auto-generated in `normalize_pick()`
- Lesson 51: Score inflation — TOTAL_BOOST_CAP = 3.5 prevents boost stacking to 10.0
- Lesson 52: Jarvis baseline misconception — 4.5 baseline is by design (sacred triggers are rare)
- Invariant 26: Total Boost Cap enforcement in `compute_final_score_option_a()`

**Previous Fixes (v20.5):**
- Lesson 41: SHARP pick grading fix (grade as moneyline, not line_variance)
- Lesson 42: PYTZ_AVAILABLE undefined in `/grader/queue`
- Lesson 43: Naive vs aware datetime in `/grader/daily-report`
- Lesson 44: Date window math error (2-day instead of 1-day)
- Lesson 45: Same datetime bug in `/grader/performance`

**All Grader Endpoints Verified Working:**
- `/grader/status` ✅
- `/grader/queue` ✅
- `/grader/daily-report` ✅
- `/grader/performance/{sport}` ✅
- `/grader/bias/{sport}` ✅
- `/grader/weights/{sport}` ✅

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
BASE_4 = (ai × 0.25) + (research × 0.35) + (esoteric × 0.20) + (jarvis × 0.20)
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment + live_adjustment + totals_calibration_adj
```

**Boosts are additive (NOT engines):**
- `msrf_boost` and `serp_boost` must remain separate (do NOT fold into confluence).
- Each boost must be present in payloads with status + reasons (even when 0.0 / unavailable).
- `ensemble_adjustment` is applied post-base for game picks when the ensemble model is available
  (+0.5 if hit_prob > 0.60, -0.5 if hit_prob < 0.40, else 0.0). Currently surfaced via `ai_reasons`.
- Live in-game adjustment: `live_adjustment` (bounded ±0.50) applied to **research_score** when game_status is LIVE.

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
FINAL = clamp(0, 10, BASE_4 + context_modifier + total_boosts + ensemble_adjustment + live_adjustment + totals_calibration_adj)
```
**TOTAL_BOOST_CAP = 3.5** — prevents score inflation from stacking multiple boosts (Invariant 26)

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
| **SUM of above 4** | `core/scoring_pipeline.py` | **`TOTAL_BOOST_CAP` (3.5)** | **Prevents score inflation (Inv. 26)** |
| ensemble_adjustment | `utils/ensemble_adjustment.py` | `ENSEMBLE_ADJUSTMENT_STEP` (0.5) | +0.5 / -0.5 step |
| live_adjustment | `live_data_router.py` | ±0.50 | In-game adjustment to research_score |
| totals_calibration_adj | `live_data_router.py` | ±0.75 | OVER penalty / UNDER boost from `TOTALS_SIDE_CALIBRATION` |

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

## Integration Registry Expectations

- **Validated**: env vars set + connectivity OK.
- **Configured**: env vars set but connectivity not verified.
- **Unreachable**: env vars set but API unreachable (fail‑loud).
- **Not configured**: missing required env vars (fail‑loud).
- `last_used_at` must update on **both cache hits and live fetches** for all paid integrations.

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

### INVARIANT 6: Output Filtering (6.5 MINIMUM)

**RULE:** NEVER return any pick with `final_score < 6.5` to frontend

**Filter Pipeline (in order):**
```python
# 1. Deduplicate by pick_id (same bet, different books)
deduplicated = _dedupe_picks(all_picks)

# 2. Filter to 6.5 minimum score
filtered = [p for p in deduplicated if p["final_score"] >= 6.5]

# 3. Apply contradiction gate (prevent opposite sides)
no_contradictions = apply_contradiction_gate(filtered)

# 4. Take top N picks
top_picks = no_contradictions[:max_picks]
```

**GOLD_STAR Hard Gates (Option A):**
- If tier == "GOLD_STAR", MUST pass ALL gates:
  - `ai_score >= 6.8`
  - `research_score >= 5.5`
  - `jarvis_score >= 6.5`
  - `esoteric_score >= 4.0`
  - context gate removed (context is a bounded modifier)
- If ANY gate fails, downgrade to "EDGE_LEAN"

**Tier Hierarchy:**
1. TITANIUM_SMASH (3/4 engines ≥ 8.0) - Overrides all others
2. GOLD_STAR (≥ 7.5 + passes all gates)
3. EDGE_LEAN (≥ 6.5)
4. MONITOR (≥ 5.5) - HIDDEN (not returned)
5. PASS (< 5.5) - HIDDEN (not returned)

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

### INVARIANT 9.1: Two Storage Systems (INTENTIONAL SEPARATION)

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
    pick.esoteric_score * 0.20 +
    pick.jarvis_rs * 0.20
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
6:30 AM  → Daily audit (all sports)
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
- Morning grading/audit happens BEFORE 10 AM props fetch
- Weights are updated daily based on yesterday's results
- Props fetches are scheduled to catch different game windows
- Weekend schedule includes noon/afternoon fetches for daytime games
- Live scores update every 2 minutes during games

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
   - AI (25%) + Research (35%) + Esoteric (20%) + Jarvis (20%)
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
3. **Esoteric (20%)** - Numerology, astro, fib, vortex, daily edge
4. **Jarvis (20%)** - Gematria triggers, mid-spread goldilocks

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

## CRITICAL INVARIANTS (NEVER BREAK THESE)

### FIX 1: Best-Bets Response Contract (NO KeyErrors)

**RULE**: `/live/best-bets/{sport}` MUST ALWAYS return JSON with these keys:
- `props: {count, total_analyzed, picks: []}` - ALWAYS present (empty array when no props)
- `games: {count, total_analyzed, picks: []}` - ALWAYS present (empty array when no games)
- `meta: {}` - ALWAYS present

**Why**: NHL often has no props. Frontend must never get KeyError.

**Implementation**: Use `models/best_bets_response.py` → `build_best_bets_response()`

**Example** (NHL with 0 props):
```json
{
  "sport": "NHL",
  "props": {"count": 0, "picks": []},
  "games": {"count": 2, "picks": [...]},
  "meta": {}
}
```

**Tests**: `tests/test_best_bets_contract.py` (5 tests)

---

### FIX 2: Titanium 3-of-4 Rule (MANDATORY)

**RULE**: `titanium=true` ONLY when >= 3 of 4 base engines >= 8.0

**Never**:
- 1/4 engines → titanium MUST be false
- 2/4 engines → titanium MUST be false

**Always**:
- 3/4 engines → titanium MUST be true
- 4/4 engines → titanium MUST be true

**Implementation**: Use `core/titanium.py` → `compute_titanium_flag(ai, research, esoteric, jarvis)`

**Returns**:
```python
(titanium_flag, diagnostics)

diagnostics = {
    "titanium": bool,
    "titanium_hits_count": int,
    "titanium_engines_hit": List[str],
    "titanium_reason": str,
    "titanium_threshold": 8.0,
    "engine_scores": {...}
}
```

**Example** (1/4 - MUST BE FALSE):
```python
titanium, diag = compute_titanium_flag(8.5, 6.0, 5.0, 4.0)
# titanium=False
# reason: "Only 1/4 engines >= 8.0 (need 3+)"
```

**Example** (3/4 - MUST BE TRUE):
```python
titanium, diag = compute_titanium_flag(8.5, 8.2, 8.1, 7.0)
# titanium=True
# engines: ['ai', 'research', 'esoteric']
# reason: "3/4 engines >= 8.0 (TITANIUM)"
```

**Tests**: `tests/test_titanium_fix.py` (7 tests)

**NO DUPLICATE LOGIC**: Use this ONE function everywhere (props + games). Remove any duplicated titanium logic.

---

### FIX 3: Grader Storage on Railway Volume (MANDATORY)

**RULE**: All grader data MUST live on Railway persistent volume

**Implementation**: `data_dir.py`
- Uses `RAILWAY_VOLUME_MOUNT_PATH` env var (set by Railway automatically)
- Production: `/data` (Railway 5GB persistent volume)
- Local dev fallback: `./grader_data`

**Startup Requirements**:
1. Create directories if missing
2. Test write to confirm writable
3. **Fail fast** if not writable (exit 1)
4. Log resolved storage path

**Startup Log** (MUST see this):
```
GRADER_DATA_DIR=/data
✓ Storage writable: /data
```

**Storage Paths**:
- Pick logs: `/data/pick_logs/picks_{YYYY-MM-DD}.jsonl`
- Graded picks: `/data/graded_picks/graded_{YYYY-MM-DD}.jsonl`
- Grader data: `/data/grader_data/predictions.json`
- Audit logs: `/data/audit_logs/audit_{YYYY-MM-DD}.json`

**Verification**: `scripts/verify_system.sh` checks storage path

---

### FIX 4: ET Today-Only Window (CANONICAL)

**RULE**: Daily slate window is [00:00:00 ET, 00:00:00 ET next day) - half-open interval

**CANONICAL ET SLATE WINDOW:**
- Start: 00:00:00 ET (midnight) - inclusive
- End: 00:00:00 ET next day (midnight) - exclusive
- Events at exactly 00:00:00 (midnight) belong to PREVIOUS day

**Implementation**: `core/time_et.py` → `et_day_bounds()`

**Returns**:
```python
(start_et, end_et, et_date)
# start = 2026-01-28 00:00:00 ET  (midnight)
# end = 2026-01-28 23:59:00 ET    (11:59 PM)
# et_date = "2026-01-28"
```

**Bounds**: Inclusive `[start, end]` - event at 11:59:00 PM is INCLUDED

**Single Source of Truth**:
- ONLY use `core/time_et.py` for ET timezone logic
- NO `datetime.now()` or `utcnow()` in slate filtering
- NO pytz allowed (uses zoneinfo only)
- Auto-grader uses "yesterday ET" (not UTC date)

**Required Functions**:
- `now_et()` - Get current time in ET
- `et_day_bounds(date_str=None)` - Get ET day bounds
- `is_in_et_day(event_time, date_str=None)` - Boolean check
- `filter_events_et(events, date_str=None)` - Filter events to ET day

**Verification**: `/debug/time` endpoint returns `et_date` - MUST match best-bets `filter_date`

**Example**:
```bash
curl /live/debug/time | jq '.et_date'
# "2026-01-28"

curl /live/best-bets/NHL?debug=1 | jq '.debug.date_window_et.filter_date'
# "2026-01-28"

# MUST MATCH ✅
```

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

## 🔌 INTEGRATION REGISTRY (Single Source of Truth)

**Module:** `integration_registry.py` - Declares ALL 14 external API integrations

**Canonical Mapping:** See `docs/ENV_VAR_MAPPING.md` for exact file→function→endpoint mapping

**Endpoint:** `GET /live/debug/integrations` - Returns status of all integrations
- `?quick=true` - Fast summary (configured/not_configured lists)
- Full mode - Detailed status with categories:
  - **(A) VALIDATED** - Configured AND reachable
  - **(B) CONFIGURED** - Env var set, connectivity not tested
  - **(C) UNREACHABLE** - Configured but failing (FAIL LOUD)
  - **(D) DISABLED** - Intentionally disabled via feature flag
  - **(E) NOT_CONFIGURED** - Missing required config (FAIL LOUD)

### All 14 Required Integrations

| # | Integration | Env Vars | Purpose | Status |
|---|-------------|----------|---------|--------|
| 1 | `odds_api` | `ODDS_API_KEY` | Live odds, props, lines | ✅ Configured |
| 2 | `playbook_api` | `PLAYBOOK_API_KEY` | Sharp money, splits, injuries | ✅ Configured |
| 3 | `balldontlie` | `BALLDONTLIE_API_KEY`, `BDL_API_KEY` | NBA grading (env var REQUIRED) | ✅ Required |
| 4 | `weather_api` | `WEATHER_API_KEY` | Outdoor sports (DISABLED) | ⚠️ Stubbed |
| 5 | `astronomy_api` | `ASTRONOMY_API_ID` | Moon phases for esoteric | ✅ Configured |
| 6 | `noaa_space_weather` | `NOAA_BASE_URL` | Solar activity for esoteric | ✅ Configured |
| 7 | `fred_api` | `FRED_API_KEY` | Economic sentiment | ✅ Configured |
| 8 | `finnhub_api` | `FINNHUB_KEY` | Sportsbook stocks | ✅ Configured |
| 9 | `serpapi` | `SERPAPI_KEY` | News aggregation | ✅ Configured |
| 10 | `twitter_api` | `TWITTER_BEARER` | Real-time news | ✅ Configured |
| 11 | `whop_api` | `WHOP_API_KEY` | Membership auth | ✅ Configured |
| 12 | `database` | `DATABASE_URL` | PostgreSQL | ✅ Configured |
| 13 | `redis` | `REDIS_URL` | Caching | ✅ Configured |
| 14 | `railway_storage` | `RAILWAY_VOLUME_MOUNT_PATH` | Picks persistence | ✅ Configured |

### Behavior: "No 500s"

- **Endpoints:** FAIL SOFT (graceful degradation, return partial data, never crash)
- **Health checks:** FAIL LOUD (clear error messages showing what's missing)

### Paid APIs Usage Map (Option A - canonical)

**BallDontLie (required)**
- **Calls from:** `alt_data_sources/balldontlie.py`
- **Used by:** `live_data_router.py` (live context + props/game normalization)
- **Signals:** live context, pace/usage context, identity resolution
- **Debug surfacing:** `/live/debug/integrations` → `balldontlie`

**Odds API (required)**
- **Calls from:** `odds_api.py` wrapper (used by best-bets paths)
- **Used by:** `live_data_router.py` via odds wrapper
- **Signals:** market lines, spreads/totals, line variance
- **Debug surfacing:** `/live/debug/integrations` → `odds_api`

**Playbook API (required)**
- **Calls from:** `playbook_api.py`
- **Used by:** `live_data_router.py` for sharp money, splits, public fade
- **Signals:** research engine inputs
- **Debug surfacing:** `/live/debug/integrations` → `playbook`

**SerpAPI (optional/paid)**
- **Calls from:** `alt_data_sources/serpapi.py`
- **Used by:** `live_data_router.py` (SERP boosts; shadow mode if enabled)
- **Signals:** search-trend / noosphere signals as boosts
- **Debug surfacing:** `/live/debug/integrations` → `serpapi`

### Key Functions

```python
from integration_registry import (
    get_all_integrations_status,  # Full status of all integrations
    get_integrations_summary,      # Quick configured/not_configured lists
    get_health_check_loud,         # Fail-loud health check for monitoring
    record_success,                # Track successful API call
    record_failure,                # Track failed API call
)
```

### Verification Commands

```bash
# Quick summary
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations?quick=true" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4"

# Full details with reachability
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4"
```

### BallDontLie API Key

The BallDontLie integration **requires** the API key to be set in environment variables:
- `BALLDONTLIE_API_KEY` (primary)
- `BDL_API_KEY` (fallback)

**No hardcoded fallback.** The API will not function without a valid key in the environment. Used for NBA prop grading.

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

## Architecture

### Core Files (Active)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI entry point, includes routers |
| `live_data_router.py` | All `/live/*` endpoints, JARVIS triggers, esoteric functions |
| `advanced_ml_backend.py` | 8 AI Models + 8 Pillars of Execution |

### Legacy Files (Reference Only - Do Not Modify)

| File | Status |
|------|--------|
| `new_endpoints.py` | DEPRECATED |
| `services/` | Legacy sync services |
| `prediction_api.py` | Old 8-model API |

---

## Signal Architecture (Option A: 4-Engine + Context Modifier)

### Scoring Formula
```
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment
       + msrf_boost + serp_boost (if enabled)
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

### Engine 3: Esoteric Score (20%)
- **See CRITICAL section below for rules**
- Park Factors (Pillar 17, MLB only): Venue-based adjustments

### Engine 4: Jarvis Score (20%)
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
| `research_gte_5.5` | Research ≥ 5.5 | Must have real market signals (sharp/splits/variance) |
| `jarvis_gte_6.5` | Jarvis ≥ 6.5 | Jarvis triggers must fire |
| `esoteric_gte_4.0` | Esoteric ≥ 4.0 | Esoteric components must contribute |
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

## 🧠 ML MODEL ACTIVATION & GLITCH PROTOCOL (v17.2)

**Implemented:** February 2026
**Status:** 100% Complete - All 19 features + 6 APIs active

This section documents the ML infrastructure and GLITCH Protocol esoteric signals that were dormant and have now been fully activated.

---

### INVARIANT 14: ML Model Activation (LSTM + Ensemble)

**RULE:** Props use LSTM models, Games use Ensemble model. Fallback to heuristic on failure.

**Architecture:**
```
PROPS:  LSTM (13 models) → ai_score adjustment ±3.0
GAMES:  XGBoost Ensemble → hit probability → confidence adjustment
```

**LSTM Models (13 weight files in `/models/`):**
| Sport | Stats | Files |
|-------|-------|-------|
| NBA | points, assists, rebounds | 3 |
| NFL | passing_yards, rushing_yards, receiving_yards | 3 |
| MLB | hits, total_bases, strikeouts | 3 |
| NHL | points, shots | 2 |
| NCAAB | points, rebounds | 2 |

**Key Files:**
```
ml_integration.py           # Core ML integration (725 LOC)
├── PropLSTMManager         # Lazy-loads LSTM models on demand
├── EnsembleModelManager    # XGBoost hit predictor for games
├── get_lstm_ai_score()     # Props: returns (ai_score, metadata)
└── get_ensemble_ai_score() # Games: returns (ai_score, metadata)

scripts/train_ensemble.py   # XGBoost training script (413 LOC)
daily_scheduler.py          # Retrain jobs (lines 458-476)
```

**Scheduler Jobs:**
| Job | Schedule | Threshold |
|-----|----------|-----------|
| LSTM Retrain | Sundays 4:00 AM ET | 500+ samples |
| Ensemble Retrain | Daily 6:45 AM ET | 100+ graded picks |

**Fallback Behavior:**
- If LSTM unavailable → Uses heuristic `base_ai = 5.0` with rule-based boosts
- If Ensemble unavailable → Uses heuristic game scoring
- All failures are SILENT to user (logged internally)

**Context Data Wiring (Pillars 13-15 → LSTM):**
```python
# live_data_router.py lines 3030-3054
game_data={
    "def_rank": DefensiveRankService.get_rank(...),   # Pillar 13
    "pace": PaceVectorService.get_game_pace(...),     # Pillar 14
    "vacuum": UsageVacuumService.calculate_vacuum(...) # Pillar 15
}
```

**Verification:**
```bash
# Check ML status
curl /live/ml/status -H "X-API-Key: KEY"
# Should show: lstm.loaded_count > 0, ensemble.available: true/false

# Check LSTM in pick metadata
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.props.picks[0].lstm_metadata'
```

---

### INVARIANT 15: GLITCH Protocol (6 Signals)

**RULE:** All 6 GLITCH signals must be wired into `get_glitch_aggregate()` and called from scoring.

**GLITCH Protocol Signals:**
| # | Signal | Weight | Source | Triggered When |
|---|--------|--------|--------|----------------|
| 1 | Chrome Resonance | 0.25 | Player birthday + game date | Chromatic interval is Perfect 5th/4th/Unison |
| 2 | Void Moon | 0.20 | Astronomical calculation | Moon is void-of-course |
| 3 | Noosphere Velocity | 0.15 | SerpAPI (Google Trends) | Search velocity > ±0.2 |
| 4 | Hurst Exponent | 0.25 | Line history analysis | H ≠ 0.5 (trending/mean-reverting) |
| 5 | Kp-Index | 0.25 | NOAA Space Weather API | Geomagnetic storm (Kp ≥ 5) |
| 6 | Benford Anomaly | 0.10 | Line value distribution | Chi-squared deviation ≥ 0.25 |

**v17.6 Benford Requirement:** Multi-book aggregation provides 10+ values (was dormant with only 3 values before).

**Key Files:**
```
esoteric_engine.py
├── calculate_chrome_resonance()    # Line 896
├── calculate_void_moon()           # Line 145
├── calculate_hurst_exponent()      # Line 313
├── get_schumann_frequency()        # Line 379 (Kp fallback)
└── get_glitch_aggregate()          # Line 1002 - COMBINES ALL 6

alt_data_sources/
├── noaa.py                         # NOAA Kp-Index client (FREE API)
│   ├── fetch_kp_index_live()       # 3-hour cache
│   └── get_kp_betting_signal()     # Betting interpretation
├── serpapi.py                      # SerpAPI client (already paid)
│   ├── get_search_trend()          # Google search volume
│   ├── get_team_buzz()             # Team comparison
│   └── get_noosphere_data()        # Hive mind velocity
└── __init__.py                     # Exports all signals

signals/math_glitch.py
└── check_benford_anomaly()         # First-digit distribution
```

**Integration Point (live_data_router.py lines 3321-3375):**
```python
# GLITCH signals adjust esoteric_score by ±0.75 max
glitch_result = get_glitch_aggregate(
    birth_date_str=player_birthday,
    game_date=game_date,
    game_time=game_datetime,
    line_history=line_history,
    value_for_benford=line_values,
    primary_value=prop_line
)
glitch_adjustment = (glitch_result["glitch_score_10"] - 5.0) * 0.15
esoteric_raw += glitch_adjustment
```

**API Configuration:**
| API | Env Var | Cost | Cache TTL |
|-----|---------|------|-----------|
| NOAA Space Weather | None (public) | FREE | 3 hours |
| SerpAPI | `SERPAPI_KEY` | Already paid | 30 minutes |

**Verification:**
```bash
# Check GLITCH in esoteric breakdown
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0].esoteric_reasons'
# Should include: "GLITCH: chrome_resonance", "GLITCH: void_moon_warning", etc.

# Check alt_data_sources status
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.noaa, .serpapi'
```

---

### INVARIANT 16: 17-Pillar Scoring System (v17.8 - ALL PILLARS ACTIVE)

**RULE:** All 17 pillars must contribute to scoring. No pillar may be orphaned.

**Pillar Map:**
| # | Pillar | Engine | Weight | Implementation | Status |
|---|--------|--------|--------|----------------|--------|
| 1-8 | 8 AI Models | AI (15%) | Direct | `advanced_ml_backend.py` | ✅ |
| 9 | Sharp Money (RLM) | Research (20%) | Direct | Playbook API splits | ✅ |
| 10 | Line Variance | Research | Direct | Cross-book comparison | ✅ |
| 11 | Public Fade | Research | Direct | Ticket-money divergence | ✅ |
| 12 | Splits Base | Research | Direct | Real data presence boost | ✅ |
| 13 | Defensive Rank | Context (30%) | 50% | `DefensiveRankService` | ✅ Real values |
| 14 | Pace Vector | Context | 30% | `PaceVectorService` | ✅ Real values |
| 15 | Usage Vacuum | Context | 20% | `UsageVacuumService` + injuries | ✅ Real values |
| 16 | Officials | Research | Adjustment | `OfficialsService` + `officials_data.py` | ✅ ACTIVE (v17.8) |
| 17 | Park Factors | Esoteric | MLB only | `ParkFactorService` | ✅ |

**v17.8 Completion Status (Feb 2026):**
- ✅ **Pillars 13-15 now use REAL DATA** (not hardcoded defaults)
- ✅ **Injuries fetched in parallel** with props and game odds
- ✅ **Context calculation runs for ALL pick types** (PROP, GAME, SHARP)
- ✅ **Pillar 16 (Officials)** - ACTIVE with referee tendency database (v17.8)
  - 25 NBA referees with over_tendency, foul_rate, home_bias
  - 17 NFL referee crews with flag_rate, over_tendency
  - 15 NHL referees with penalty_rate, over_tendency
  - Adjustment range: -0.5 to +0.5 on research score

**Data Flow (v17.8):**
```
_best_bets_inner()
  │
  ├── Parallel Fetch (asyncio.gather)
  │     ├── get_props(sport)
  │     ├── fetch_game_odds()
  │     └── get_injuries(sport)
  │
  ├── Build _injuries_by_team lookup (handles Playbook + ESPN formats)
  ├── Build _officials_by_game lookup (ESPN Hidden API)
  │
  └── calculate_pick_score() [for ALL pick types]
        ├── Pillar 13: DefensiveRankService.get_rank()
        ├── Pillar 14: PaceVectorService.get_game_pace()
        ├── Pillar 15: UsageVacuumService.calculate_vacuum(_injuries_by_team)
        ├── Pillar 16: OfficialsService.get_officials_adjustment() ← v17.8
        └── Pillar 17: ParkFactorService (MLB only)
```

**Base Engine Weights (scoring_contract.py):**
```python
ENGINE_WEIGHTS = {
    "ai": 0.25,        # Pillars 1-8
    "research": 0.35,  # Pillars 9-12, 16
    "esoteric": 0.20,  # Pillar 17 + GLITCH
    "jarvis": 0.20,    # Gematria triggers
}

CONTEXT_MODIFIER_CAP = 0.35  # Context is a bounded modifier, not a weighted engine
```

**Verification - Check REAL Values (Not Defaults):**
```bash
# 1. Check context layer has REAL values (not defaults)
# Default def_rank=16, pace=100.0, vacuum=0.0 - if ALL picks show these, it's broken
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '[.game_picks.picks[0:3][] | {
  matchup: .matchup,
  def_rank: .context_layer.def_rank,
  pace: .context_layer.pace,
  vacuum: .context_layer.vacuum,
  context_score: .context_score,
  context_modifier: .context_modifier
}]'
# SHOULD show varying def_rank (1-30), varying pace (94-104), context_score + modifier vary

# 2. Check injuries are loaded
curl /live/injuries/NBA -H "X-API-Key: KEY" | jq '{source: .source, count: .count, teams: [.data[].teamName]}'
# SHOULD show source: "playbook", count > 0, teams list

# 3. Check all engines in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  ai: .ai_score,
  research: .research_score,
  esoteric: .esoteric_score,
  jarvis: .jarvis_score,
  context_modifier: .context_modifier,
  officials: .context_layer.officials_adjustment,
  park: .context_layer.park_adjustment
}'
```

**Key Files (v17.8):**
| File | Lines | Purpose |
|------|-------|---------|
| `live_data_router.py` | 4172-4227 | Parallel fetch including injuries |
| `live_data_router.py` | 4201-4227 | Build _injuries_by_team (Playbook + ESPN format) |
| `live_data_router.py` | 4055-4106 | Pillar 16: Officials tendency integration (v17.8) |
| `live_data_router.py` | 3139-3183 | Context calculation for ALL pick types |
| `context_layer.py` | 413-472 | DefensiveRankService |
| `context_layer.py` | 543-635 | PaceVectorService |
| `context_layer.py` | 637-706 | UsageVacuumService |
| `context_layer.py` | 713-763 | ParkFactorService |
| `context_layer.py` | 2176-2248 | OfficialsService.get_officials_adjustment() (v17.8) |
| `officials_data.py` | All | Referee tendency database (25 NBA, 17 NFL, 15 NHL refs) |

---

### INVARIANT 17: Harmonic Convergence (+1.5 Boost)

**RULE:** When Research ≥ 8.0 AND Esoteric ≥ 8.0, add +1.5 "Golden Boost"

**Implementation (live_data_router.py lines 3424-3435):**
```python
HARMONIC_THRESHOLD = 8.0
HARMONIC_BOOST = 1.5

if research_score >= HARMONIC_THRESHOLD and esoteric_score >= HARMONIC_THRESHOLD:
    confluence = {
        "level": "HARMONIC_CONVERGENCE",
        "boost": confluence.get("boost", 0) + HARMONIC_BOOST,
        ...
    }
```

**Rationale:** When both analytical (Research/Math) and intuitive (Esoteric/Magic) signals strongly agree, this represents exceptional alignment worthy of extra confidence.

---

### INVARIANT 18: Secret Redaction (Log Sanitizer)

**RULE:** API keys, tokens, and auth headers MUST NEVER appear in logs.

**Implementation:** `core/log_sanitizer.py` (NEW - Feb 2026)

**Sensitive Data Classes:**
| Category | Examples | Redaction |
|----------|----------|-----------|
| Headers | `X-API-Key`, `Authorization`, `Cookie` | → `[REDACTED]` |
| Query Params | `apiKey`, `api_key`, `token`, `secret` | → `[REDACTED]` |
| Env Var Values | `ODDS_API_KEY`, `PLAYBOOK_API_KEY`, etc. | → `[REDACTED]` |
| Token Patterns | Bearer tokens, JWTs, long alphanumeric | → `[REDACTED]` |

**Key Functions:**
```python
from core.log_sanitizer import (
    sanitize_headers,    # Dict[str, Any] → Dict[str, str] with sensitive values redacted
    sanitize_dict,       # Recursively redacts api_key, token, etc.
    sanitize_url,        # Redacts ?apiKey=xxx query params
    sanitize,            # Text sanitization for Bearer/JWT/alphanumeric
    safe_log_request,    # Safe HTTP request logging
    safe_log_response,   # Safe HTTP response logging
)
```

**Files Updated:**
| File | Line | Change |
|------|------|--------|
| `playbook_api.py` | 211 | Uses `sanitize_dict(query_params)` |
| `live_data_router.py` | 6653 | Uses `params={}` not `?apiKey=` in URL |
| `legacy/services/odds_api_service.py` | 30 | Changed `key[:8]...` to `[REDACTED]` |

**NEVER:**
- Log `request.headers` without sanitizing
- Construct URLs with `?apiKey=VALUE` (use `params={}` dict)
- Log partial keys like `key[:8]...` (reconnaissance risk)
- Print exception messages that might contain secrets

**Tests:** `tests/test_log_sanitizer.py` (20 tests)

**Verification:**
```bash
# Run sanitizer tests
pytest tests/test_log_sanitizer.py -v

# Check no secrets in recent logs
railway logs | grep -i "apikey\|authorization\|bearer" | head -5
# Should return empty or only "[REDACTED]"
```

---

### INVARIANT 19: Demo Data Hard Gate

**RULE:** Sample/demo/fallback data ONLY returned when explicitly enabled.

**Implementation:** Gated behind `ENABLE_DEMO=true` env var OR `mode=demo` query param.

**What's Gated:**
| Location | Demo Data | Gate |
|----------|-----------|------|
| `legacy/services/odds_api_service.py` | Lakers/Warriors demo game | `ENABLE_DEMO=true` |
| `main.py:/debug/seed-pick` | Fake LeBron/LAL pick | `mode=demo` or `ENABLE_DEMO` |
| `main.py:/debug/seed-pick-and-grade` | Fake LeBron/LAL pick | `mode=demo` or `ENABLE_DEMO` |
| `main.py:/debug/e2e-proof` | Test pick with `e2e_` prefix | `mode=demo` or `ENABLE_DEMO` |
| `live_data_router.py:_DEPRECATED_*` | Sample matchups | `ENABLE_DEMO=true` |

**Behavior When Live Data Unavailable:**
| Scenario | Before | After |
|----------|--------|-------|
| No `ODDS_API_KEY` | Demo Lakers/Warriors game | Empty `[]` |
| API returns error | Demo fallback data | Empty `[]` + error logged |
| No games scheduled | Demo data | Empty `[]` |

**Endpoint Response When Gated:**
```json
{
  "error": "Demo data gated",
  "detail": "Set mode=demo query param or ENABLE_DEMO=true env var"
}
```
HTTP 403 Forbidden

**NEVER:**
- Return sample picks without explicit demo flag
- Use hardcoded player data (LeBron, Mahomes) in production responses
- Fall back to demo on API failure (return empty instead)

**Tests:** `tests/test_no_demo_data.py` (12 tests)

**Verification:**
```bash
# Debug endpoints should be blocked without flag
curl -X POST /debug/seed-pick -H "X-Admin-Key: KEY"
# Should return 403 "Demo data gated"

# With flag should work
curl -X POST "/debug/seed-pick?mode=demo" -H "X-Admin-Key: KEY"
# Should return seeded pick

# Best-bets should never have sample data
curl /live/best-bets/NHL -H "X-API-Key: KEY" | jq '.props.picks[].matchup'
# Should never show "Lakers @ Celtics" or other hardcoded matchups
```

---

### INVARIANT 20: MSRF Confluence Boost (v17.2)

**RULE:** MSRF (Mathematical Sequence Resonance Framework) calculates turn date resonance and adds confluence boost when mathematically significant.

**Implementation:** `signals/msrf_resonance.py` → `get_msrf_confluence_boost()`

**Mathematical Constants:**
| Constant | Value | Significance |
|----------|-------|--------------|
| `OPH_PI` | 3.14159... | Circle constant, cycles |
| `OPH_PHI` | 1.618... | Golden Ratio, natural growth |
| `OPH_CRV` | 2.618... | Phi² (curved growth) |
| `OPH_HEP` | 7.0 | Heptagon (7-fold symmetry) |

**MSRF Number Lists:**
| List | Count | Examples |
|------|-------|----------|
| `MSRF_NORMAL` | ~250 | 666, 777, 888, 2178 |
| `MSRF_IMPORTANT` | 36 | 144, 432, 720, 1080, 2520 |
| `MSRF_VORTEX` | 19 | 21.7, 144.3, 217.8 |

**16 Operations:** Transform time intervals (Y1, Y2, Y3) between last 3 significant dates using constants, then project forward to check if game date aligns.

**Boost Levels (added to confluence):**
| Level | Points Required | Boost | Triggered |
|-------|----------------|-------|-----------|
| EXTREME_RESONANCE | ≥ 8 | +1.0 | ✅ |
| HIGH_RESONANCE | ≥ 5 | +0.5 | ✅ |
| MODERATE_RESONANCE | ≥ 3 | +0.25 | ✅ |
| MILD_RESONANCE | ≥ 1 | +0.0 | ❌ |
| NO_RESONANCE | 0 | +0.0 | ❌ |

**Data Sources:**
1. **Stored Predictions:** High-confidence hits from `/data/grader/predictions.jsonl` (min_score ≥ 7.5)
2. **BallDontLie (NBA only):** Player standout games (points ≥ 150% of average)

**Integration Point:** `live_data_router.py:3567-3591` (after Harmonic Convergence, before confluence_boost extraction)

**Output Fields (debug mode):**
```python
{
    "msrf_boost": float,        # 0.0, 0.25, 0.5, or 1.0
    "msrf_metadata": {
        "source": "msrf_live",
        "level": "HIGH_RESONANCE",
        "points": 5.5,
        "matching_operations": [...],
        "significant_dates_used": ["2025-11-15", "2025-12-24", "2026-01-15"]
    }
}
```

**Feature Flag:** `MSRF_ENABLED` env var (default: `true`)

**Verification:**
```bash
# Check MSRF in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {msrf_boost, msrf_level: .msrf_metadata.level, msrf_points: .msrf_metadata.points}'

# Check MSRF in esoteric_reasons
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0].esoteric_reasons | map(select(startswith("MSRF")))'
```

**NEVER:**
- Add MSRF boost without sufficient significant dates (need 3+)
- Call MSRF for indoor sports without player/team context
- Modify MSRF number lists without understanding sacred number theory

---

### INVARIANT 21: Dual-Use Functions Must Return Dicts (v17.2)

**RULE:** Functions that are BOTH endpoint handlers AND called internally MUST return dicts, not JSONResponse.

**Why:** FastAPI auto-serializes dicts to JSON for endpoint responses. When a function returns `JSONResponse`, internal callers cannot use `.get()` or other dict methods on the return value.

**Affected Functions (live_data_router.py):**
| Function | Line | Endpoint | Internal Callers |
|----------|------|----------|------------------|
| `get_sharp_money()` | 1758 | `/live/sharp/{sport}` | `_best_bets_inner()` line 2580 |
| `get_splits()` | 1992 | `/live/splits/{sport}` | `_best_bets_inner()`, dashboard |
| `get_lines()` | 2100+ | `/live/lines/{sport}` | dashboard |
| `get_injuries()` | 2200+ | `/live/injuries/{sport}` | dashboard |

**Pattern to Avoid:**
```python
@router.get("/endpoint")
async def my_function():
    result = {"data": [...]}
    return JSONResponse(result)  # ❌ WRONG - breaks internal callers
```

**Correct Pattern:**
```python
@router.get("/endpoint")
async def my_function():
    result = {"data": [...]}
    return result  # ✅ FastAPI auto-serializes for endpoints, internal callers get dict
```

**When to Use JSONResponse:**
- Custom status codes: `return JSONResponse(content=data, status_code=201)`
- Custom headers: `return JSONResponse(content=data, headers={"X-Custom": "value"})`
- Custom media type: `return JSONResponse(content=data, media_type="application/xml")`

**Verification:**
```bash
# Find all JSONResponse returns in endpoint handlers
grep -n "return JSONResponse" live_data_router.py | head -20

# Check if those functions are called internally
# For each function, grep for calls outside the decorator
```

**Test All Sports After Changes:**
```bash
# After ANY change to dual-use functions, test ALL sports:
for sport in NBA NHL NFL MLB NCAAB; do
  echo "Testing $sport..."
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | jq '{sport: .sport, picks: (.game_picks.count + .props.count)}'
done
```

**Fixed in:** Commit `d7279e9` (Feb 2026)

---

### INVARIANT 22: ESPN Data Integration (v17.3)

**RULE:** ESPN data is a FREE secondary source for cross-validation and supplementation, NOT a replacement.

**Data Usage Hierarchy:**
| Data Type | Primary Source | ESPN Role | Integration |
|-----------|---------------|-----------|-------------|
| **Odds** | Odds API | Cross-validation | +0.25-0.5 research boost when confirmed |
| **Injuries** | Playbook API | Supplement | Merge into `_injuries_by_team` |
| **Officials** | ESPN (primary) | Primary for Pillar 16 | `_officials_by_game` lookup |
| **Weather** | Weather API | Fallback | Only for MLB/NFL when primary fails |
| **Venue** | ESPN | Supplementary | Indoor/outdoor, grass/turf info |

**Implementation Requirements:**
1. **Batch Parallel Fetching** - NEVER fetch ESPN data synchronously in scoring loop
2. **Graceful Fallback** - ESPN data unavailable → continue without it (no errors)
3. **Team Name Normalization** - Case-insensitive matching, handle accents
4. **Closure Access** - Scoring function accesses via closure from `_best_bets_inner()`

**Lookup Variables (defined in `_best_bets_inner()`):**
```python
_espn_events_by_teams = {}    # (home_lower, away_lower) → event_id
_officials_by_game = {}       # (home_lower, away_lower) → officials dict
_espn_odds_by_game = {}       # (home_lower, away_lower) → odds dict
_espn_injuries_supplement = {} # team_name → list of injuries
_espn_venue_by_game = {}      # (home_lower, away_lower) → venue dict (MLB/NFL only)
```

**ESPN Cache TTL:** 5 minutes (per-request cache, not global)

**Sport Support:**
| Sport | Officials | Odds | Injuries | Venue/Weather |
|-------|-----------|------|----------|---------------|
| NBA | ✅ | ✅ | ✅ | ❌ (indoor) |
| NFL | ✅ | ✅ | ✅ | ✅ |
| MLB | ✅ | ✅ | ✅ | ✅ |
| NHL | ✅ | ✅ | ✅ | ❌ (indoor) |
| NCAAB | ✅ | ✅ | ✅ | ❌ (indoor) |

**Verification:**
```bash
# Check ESPN integration active
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '{espn_events: .debug.espn_events_mapped, officials: .debug.officials_available, espn_odds: .debug.espn_odds_count}'

# Verify cross-validation in research_reasons
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].research_reasons | map(select(contains("ESPN")))'
```

**NEVER:**
- Replace Odds API with ESPN odds (ESPN is secondary validation only)
- Fetch ESPN data inside the scoring loop (batch before scoring)
- Skip team name normalization (causes lookup misses)
- Assume ESPN has all data (refs assigned late, not all games covered)

---

### INVARIANT 23: SERP Intelligence Integration (v17.4)

**RULE:** SERP betting intelligence provides search-trend signals that boost engine scores. Default is LIVE MODE (not shadow mode).

**Implementation:**
- `core/serp_guardrails.py` - Central config, quota tracking, boost caps, shadow mode control
- `alt_data_sources/serp_intelligence.py` - 5 signal detectors mapped to 4 base engines
- `alt_data_sources/serpapi.py` - SerpAPI client with cache and timeout from guardrails

**Configuration (serp_guardrails.py):**
```python
SERP_SHADOW_MODE = False      # LIVE MODE by default (boosts applied)
SERP_INTEL_ENABLED = True     # Feature flag
SERP_DAILY_QUOTA = 166        # 5000/30 days
SERP_MONTHLY_QUOTA = 5000     # Monthly API calls
SERP_TIMEOUT = 2.0            # Strict 2s timeout
SERP_CACHE_TTL = 5400         # 90 minutes cache
```

**Boost Caps (Code-Enforced):**
| Engine | Max Boost | Signal Type |
|--------|-----------|-------------|
| AI | 0.8 | Silent Spike (high search + low news) |
| Research | 1.3 | Sharp Chatter (RLM, sharp money mentions) |
| Esoteric | 0.6 | Noosphere (search velocity momentum) |
| Jarvis | 0.7 | Narrative (revenge, rivalry, playoff) |
| Context | 0.9 | Situational (B2B, rest, travel) |
| **TOTAL** | **4.3** | Combined max across all engines |

**Signal → Engine Mapping:**
```
detect_silent_spike()   → AI engine      (high search + low news = insider activity)
detect_sharp_chatter()  → Research engine (sharp money, RLM mentions)
detect_narrative()      → Jarvis engine   (revenge games, rivalries)
detect_situational()    → Context modifier (B2B, rest advantage, travel)
detect_noosphere()      → Esoteric engine (search trend velocity)
```

**Integration Point (live_data_router.py:3715-3750):**
```python
serp_intel = get_serp_betting_intelligence(sport, home_team, away_team, pick_side)
if serp_intel.get("available"):
    serp_boosts = serp_intel.get("boosts", {})
    serp_boost_total = sum(serp_boosts.values())
    confluence["boost"] += serp_boost_total  # Added to confluence
```

**Required Pick Output Fields:**
```python
{
    "serp_boost": float,           # Total SERP boost applied
    "serp_reasons": List[str],     # ["SERP[context]: Situational: b2b", ...]
    "serp_shadow_mode": bool,      # False when live
}
```

**Debug Output (debug.serp):**
```json
{
  "available": true,
  "shadow_mode": false,
  "mode": "live",
  "status": {
    "enabled": true,
    "quota": {"daily_remaining": 80, "monthly_remaining": 4800},
    "cache": {"hits": 1000, "misses": 150, "hit_rate_pct": 87.0}
  }
}
```

**Verification:**
```bash
# Check SERP status
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
# Expected: available=true, shadow_mode=false, mode="live"

# Check boosts on picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {serp_boost, serp_reasons}'
# Expected: serp_boost > 0 when signals fire

# Test all sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, serp_mode: .debug.serp.mode}'
done
```

**NEVER:**
- Set `SERP_SHADOW_MODE=True` in production (disables all boosts)
- Skip quota checks before API calls
- Exceed boost caps (enforced in `cap_boost()` and `cap_total_boost()`)
- Make SERP calls inside scoring loop without try/except
- Forget to add both `SERPAPI_KEY` and `SERP_API_KEY` to env var checks

---

### INVARIANT 24: Trap Learning Loop (v19.0)

**RULE:** Pre-game traps define conditional rules that automatically adjust engine weights based on post-game results.

**Implementation:**
- `trap_learning_loop.py` - Core module (~800 lines): TrapDefinition, TrapEvaluation, TrapLearningLoop
- `trap_router.py` - API endpoints (~400 lines): CRUD for traps, dry-run, history
- `daily_scheduler.py` - Evaluation job at 6:15 AM ET (after grading at 6:00 AM)

**Storage (JSONL on Railway volume):**
```
/data/trap_learning/
├── traps.jsonl              # Trap definitions
├── evaluations.jsonl        # Evaluation history (condition_met, action_taken)
└── adjustments.jsonl        # Weight change audit trail
```

**Supported Engines (5 total):**
| Engine | Parameters | Range |
|--------|------------|-------|
| **research** | `weight_public_fade`, `weight_sharp_money`, `weight_line_variance`, `splits_base` | 0.0-3.0 |
| **esoteric** | `weight_gematria`, `weight_astro`, `weight_fib`, `weight_vortex`, `weight_daily_edge`, `weight_glitch` | 0.0-1.0 |
| **jarvis** | `trigger_boost_2178`, `trigger_boost_201`, `trigger_boost_33`, `trigger_boost_93`, `trigger_boost_322`, `trigger_boost_666`, `trigger_boost_1656`, `trigger_boost_552`, `trigger_boost_138`, `baseline_score` | 0.0-20.0 |
| **context** | `weight_def_rank`, `weight_pace`, `weight_vacuum` | 0.1-0.7 |
| **ai** | `lstm_weight`, `ensemble_weight` | 0.1-0.4 |

**Safety Guards (Code-Enforced):**
| Guard | Value | Purpose |
|-------|-------|---------|
| `MAX_SINGLE_ADJUSTMENT` | 5% (0.05) | Prevent large swings |
| `MAX_CUMULATIVE_ADJUSTMENT` | 15% (0.15) | Lifetime cap per trap |
| `cooldown_hours` | 24 (default) | Min time between triggers |
| `max_triggers_per_week` | 3 (default) | Rate limiting |
| `DECAY_FACTOR` | 0.7 | Each trigger = 70% of previous |

**Condition Language:**
```json
{
    "operator": "AND",
    "conditions": [
        {"field": "result", "comparator": "==", "value": "win"},
        {"field": "margin", "comparator": ">=", "value": 20}
    ]
}
```

**Supported Condition Fields:**
| Category | Fields |
|----------|--------|
| **Outcome** | `result`, `margin`, `total_points`, `spread_result`, `over_under_result` |
| **Date** | `day_number`, `numerology_day`, `day_of_week`, `month` |
| **Gematria** | `name_sum_cipher`, `city_sum_cipher`, `combined_cipher` |
| **Scores** | `ai_score_was`, `research_score_was`, `jarvis_score_was`, `final_score_was` |

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/traps/` | POST | Create new trap |
| `/live/traps/` | GET | List traps (filter by sport, status) |
| `/live/traps/{trap_id}` | GET | Get trap details + evaluation history |
| `/live/traps/{trap_id}/status` | PUT | Update status (ACTIVE, PAUSED, RETIRED) |
| `/live/traps/evaluate/dry-run` | POST | Test trap without applying |
| `/live/traps/history/{engine}` | GET | Adjustment history by engine |
| `/live/traps/stats/summary` | GET | Aggregate statistics |

**Example Traps:**
```json
// Trap 1: Dallas Blowout → Reduce Public Fade weight
{
    "trap_id": "dallas-blowout-public-fade",
    "name": "Dallas Blowout Reduces Public Fade Weight",
    "sport": "NBA",
    "team": "Dallas Mavericks",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "result", "comparator": "==", "value": "win"},
            {"field": "margin", "comparator": ">=", "value": 20}
        ]
    },
    "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
    "target_engine": "research",
    "target_parameter": "weight_public_fade"
}

// Trap 2: Rangers Numerology → Trigger cipher audit
{
    "trap_id": "rangers-1day-cipher-audit",
    "name": "Rangers Day 1 Loss Triggers Cipher Audit",
    "sport": "MLB",
    "team": "Texas Rangers",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "result", "comparator": "==", "value": "loss"},
            {"field": "numerology_day", "comparator": "==", "value": 1}
        ]
    },
    "action": {"type": "AUDIT_TRIGGER", "audit_type": "cipher_comparison"},
    "target_engine": "jarvis",
    "target_parameter": "name_vs_city_cipher"
}

// Trap 3: Phoenix 1656 Cycle → Reduce trigger boost on loss
{
    "trap_id": "phoenix-1656-validation",
    "name": "1656 Trigger Loss Adjustment",
    "sport": "ALL",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "combined_cipher", "comparator": "==", "value": 1656},
            {"field": "jarvis_score_was", "comparator": ">=", "value": 7.0},
            {"field": "result", "comparator": "==", "value": "loss"}
        ]
    },
    "action": {"type": "WEIGHT_ADJUST", "delta": -0.5},
    "target_engine": "jarvis",
    "target_parameter": "trigger_boost_1656"
}
```

**Scheduler Integration (daily_scheduler.py):**
```python
# v19.0: Post-game trap evaluation (daily at 6:15 AM ET, after grading)
self.scheduler.add_job(
    self._run_trap_evaluation,
    CronTrigger(hour=6, minute=15, timezone="America/New_York"),
    id="trap_evaluation",
    name="Post-Game Trap Evaluation"
)
```

**Key Functions:**
```python
from trap_learning_loop import (
    get_trap_loop,           # Singleton access
    TrapLearningLoop,        # Main class
    TrapDefinition,          # Dataclass for trap config
    TrapEvaluation,          # Dataclass for evaluation result
    enrich_game_result,      # Add numerology/gematria fields
    calculate_numerology_day,# Reduce date to single digit
    calculate_team_gematria, # Team name cipher values
    SUPPORTED_ENGINES,       # Engine→parameter→range mapping
    CONDITION_FIELDS,        # Valid condition fields
)
```

**Verification:**
```bash
# 1. List active traps
curl /live/traps/ -H "X-API-Key: KEY"

# 2. Create a test trap
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Test Trap",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [
    {"field": "margin", "comparator": ">=", "value": 10}
  ]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "research",
  "target_parameter": "weight_public_fade"
}'

# 3. Dry-run evaluation
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap",
  "game_result": {"margin": 25, "result": "win"}
}'

# 4. Check adjustment history
curl /live/traps/history/research -H "X-API-Key: KEY"

# 5. Get summary stats
curl /live/traps/stats/summary -H "X-API-Key: KEY"

# 6. Check scheduler job registered
curl /live/scheduler/status -H "X-API-Key: KEY" | jq '.jobs[] | select(.id == "trap_evaluation")'
```

**NEVER:**
- Exceed `MAX_SINGLE_ADJUSTMENT` (5%) per trigger
- Bypass cooldown period (24h default)
- Create traps targeting invalid engine/parameter combinations
- Skip safety validation in `_validate_adjustment_safety()`
- Modify `SUPPORTED_ENGINES` without updating trap_router validation
- Apply adjustments without logging to `adjustments.jsonl`

---

### INVARIANT 25: Complete Learning System (v19.1)

**RULE:** Every signal contribution MUST be tracked for learning. AutoGrader and Trap Learning Loop MUST NOT conflict.

**Philosophy:** "Competition + variance. Learning loop baked in via fused upgrades."

**Implementation:**
- `auto_grader.py` - Statistical/reactive learning (daily 6:00 AM ET)
- `trap_learning_loop.py` - Hypothesis-driven/proactive learning (daily 6:15 AM ET)
- `live_data_router.py` - Pick persistence with full signal tracking

**Two Learning Systems (Complementary):**
| System | Type | Schedule | What It Learns |
|--------|------|----------|----------------|
| **AutoGrader** | Statistical/Reactive | 6:00 AM ET | Bias from prediction errors → adjusts context modifier calibration |
| **Trap Learning Loop** | Hypothesis/Proactive | 6:15 AM ET | Conditional rules → adjusts research/esoteric/jarvis weights |

**Signal Tracking Coverage (28 signals - 100% coverage):**
| Category | Count | Signals | Learning System |
|----------|-------|---------|-----------------|
| Context Layer | 5 | defense, pace, vacuum, lstm, officials | AutoGrader |
| Research Engine | 3 | sharp_money, public_fade, line_variance | AutoGrader + Traps |
| GLITCH Protocol | 6 | chrome_resonance, void_moon, noosphere, hurst, kp_index, benford | AutoGrader |
| Esoteric Engine | 14 | numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge, biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar | AutoGrader + Traps |
| **Total** | **28** | All signals tracked | Full coverage |

**PredictionRecord Fields (auto_grader.py lines 52-95):**
```python
@dataclass
class PredictionRecord:
    # Core
    prediction_id: str
    sport: str
    player_name: str
    stat_type: str
    predicted_value: float
    actual_value: Optional[float] = None
    line: Optional[float] = None
    timestamp: str = ""

    # Pick type (for differentiated learning)
    pick_type: str = ""  # PROP, SPREAD, TOTAL, MONEYLINE, SHARP

    # Context Layer (Pillars 13-15)
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0

    # Research Engine Signals (GAP 1 fix)
    sharp_money_adjustment: float = 0.0
    public_fade_adjustment: float = 0.0
    line_variance_adjustment: float = 0.0

    # GLITCH Protocol Signals (GAP 2 fix)
    glitch_signals: Optional[Dict[str, float]] = None  # chrome_resonance, void_moon, etc.

    # Esoteric Contributions (GAP 2 fix)
    esoteric_contributions: Optional[Dict[str, float]] = None  # numerology, astro, etc.

    # Outcome
    hit: Optional[bool] = None
    error: Optional[float] = None
```

**Bias Calculation (auto_grader.py calculate_bias()):**
- Calculates bias for ALL 28 signals (not just 5)
- Supports confidence decay (70% per day - older picks weighted less)
- Supports pick_type filtering (PROP vs GAME analysis separately)
- Returns `pick_type_breakdown` for differentiated learning

**Trap-AutoGrader Reconciliation:**
- Before AutoGrader adjusts a weight, it checks if Trap Learning Loop recently adjusted it
- 24-hour lookback window for reconciliation
- If trap adjusted in last 24h, AutoGrader SKIPS that parameter
- Prevents conflicting adjustments

**Key Functions:**
```python
from auto_grader import (
    get_grader,                          # Singleton access
    PredictionRecord,                    # Full signal tracking
    AutoGrader.calculate_bias,           # All 28 signals
    AutoGrader.adjust_weights_with_reconciliation,  # Trap-safe adjustment
    AutoGrader.check_trap_reconciliation,  # Check for recent trap adjustments
)

from trap_learning_loop import (
    get_trap_loop,                       # Singleton access
    has_recent_trap_adjustment,          # Check for recent adjustments
    get_recent_parameter_adjustments,    # Get adjustments for engine/parameter
)
```

**Verification:**
```bash
# 1. Check all signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  research_breakdown: .research_breakdown,
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions
}'

# 2. Verify bias calculation includes all signals
curl /live/grader/bias/NBA?days_back=1 -H "X-API-Key: KEY" | jq '.factor_bias | keys'
# Should include: defense, pace, vacuum, lstm, officials, sharp_money, public_fade, line_variance, glitch, esoteric

# 3. Check reconciliation in adjustment result
curl -X POST /live/grader/adjust/NBA -H "X-API-Key: KEY" | jq '.reconciliation'
# Shows which parameters were skipped due to recent trap adjustments

# 4. Check pick_type breakdown
curl /live/grader/bias/NBA?days_back=7 -H "X-API-Key: KEY" | jq '.pick_type_breakdown'
# Shows hit_rate and mean_error by pick type (PROP, SPREAD, TOTAL, etc.)
```

**NEVER:**
- Add a new signal without tracking it in PredictionRecord
- Skip signal persistence in live_data_router.py pick logging
- Let AutoGrader override recent trap adjustments (reconciliation mandatory)
- Calculate bias for only some signals (must be ALL 28)
- Assume pick_type is "GAME" for game picks (actual values: SPREAD, MONEYLINE, TOTAL, SHARP)

**Files Modified (v19.1):**
| File | Lines | Change |
|------|-------|--------|
| `auto_grader.py` | 52-95 | Expanded PredictionRecord with 28 signal fields |
| `auto_grader.py` | 237-290 | Updated log_prediction() to accept new fields |
| `auto_grader.py` | 395-555 | Expanded calculate_bias() for all signals + confidence decay |
| `auto_grader.py` | 556-630 | Updated _calculate_factor_bias() for weighted calculations |
| `auto_grader.py` | 716-825 | Added reconciliation methods |
| `trap_learning_loop.py` | 677-722 | Added has_recent_trap_adjustment(), get_recent_parameter_adjustments() |
| `live_data_router.py` | 4887-4899 | Added glitch_signals, esoteric_contributions to scoring result |
| `live_data_router.py` | 6390-6420 | Updated pick persistence with all signal fields |

### INVARIANT 26: Total Boost Cap (v20.6)

**RULE:** The sum of all additive boosts (confluence + msrf + jason_sim + serp) MUST be capped at `TOTAL_BOOST_CAP` (3.5) before being added to `base_score`. Context modifier is excluded from this cap.

**Why This Exists:**
Individual boost caps (confluence 10.0, msrf 1.0, jason_sim 1.5, serp 4.3) allowed a theoretical max of 16.8 additional points. In practice, picks with mediocre base scores (~6.5) were being inflated to 10.0 through boost stacking, eliminating score differentiation. TOTAL_BOOST_CAP ensures boosts improve good picks but can't rescue bad ones.

**Implementation:**
```python
# In core/scoring_pipeline.py:compute_final_score_option_a()
total_boosts = confluence_boost + msrf_boost + jason_sim_boost + serp_boost
if total_boosts > TOTAL_BOOST_CAP:
    total_boosts = TOTAL_BOOST_CAP
final_score = base_score + context_modifier + total_boosts
final_score = max(0.0, min(10.0, final_score))
```

**Constants (core/scoring_contract.py):**
- `TOTAL_BOOST_CAP = 3.5` — max sum of 4 boosts
- `SERP_BOOST_CAP_TOTAL = 4.3` — individual SERP cap (still applies first)
- `CONFLUENCE_BOOST_CAP = 10.0` — individual confluence cap
- `MSRF_BOOST_CAP = 1.0` — individual MSRF cap
- `JASON_SIM_BOOST_CAP = 1.5` — individual Jason cap

**Test Guard:** `tests/test_option_a_scoring_guard.py:test_compute_final_score_caps_serp_and_clamps_final`

**NEVER:**
- Remove or increase `TOTAL_BOOST_CAP` without analyzing production score distributions
- Include context_modifier in the total boost cap (it's a bounded modifier, not a boost)
- Add a new boost component without including it in the total cap sum

---

## 📚 MASTER FILE INDEX (ML & GLITCH)

### Core ML Files
| File | Purpose | Key Functions |
|------|---------|---------------|
| `ml_integration.py` | ML model management | `get_lstm_ai_score()`, `get_ensemble_ai_score()` |
| `lstm_brain.py` | LSTM model wrapper | `LSTMBrain.predict_from_context()` |
| `scripts/train_ensemble.py` | Ensemble training | Run with `--min-picks 100` |
| `models/*.weights.h5` | 13 LSTM weight files | Loaded on-demand |

### Phase 1 Dormant Signals (Activated v17.5 - Feb 2026)
| File | Function | Pick Type | Boost | Integration Line |
|------|----------|-----------|-------|------------------|
| `esoteric_engine.py` | `calculate_biorhythms()` | PROP | +0.3/+0.15/-0.2 | `live_data_router.py:3614-3642` |
| `esoteric_engine.py` | `analyze_spread_gann()` | GAME | +0.25/+0.15/+0.1 | `live_data_router.py:3647-3673` |
| `esoteric_engine.py` | `check_founders_echo()` | GAME | +0.2/+0.35 | `live_data_router.py:3678-3707` |

### Phase 2.2 - Void-of-Course Daily Edge (Activated v17.5 - Feb 2026)
| File | Function | Purpose | Integration Line |
|------|----------|---------|------------------|
| `astronomical_api.py` | `is_void_moon_now()` | VOC moon detection | `live_data_router.py:1431-1445` |
| `live_data_router.py` | `get_daily_energy()` | Daily Edge scoring | Lines 1397-1456 |

**VOC Penalty Logic:**
- When `is_void_moon_now()` returns `is_void=True` AND `confidence > 0.5`
- Apply `-20` penalty to `energy_score`
- This can push `daily_edge_score` from HIGH to MEDIUM or MEDIUM to LOW
- Traditional astrological wisdom: avoid initiating new bets during VOC periods

### Phase 3 - Vortex Math, Benford Activation & Line History (v17.6 - Feb 2026)
| File | Function | Purpose | Integration Line |
|------|----------|---------|------------------|
| `esoteric_engine.py` | `calculate_vortex_energy()` | Tesla 3-6-9 resonance | `live_data_router.py:3688-3710` |
| `live_data_router.py` | `_extract_benford_values_from_game()` | Multi-book line aggregation | Lines 3152-3205 |
| `database.py` | `LineSnapshot`, `SeasonExtreme` | Line history storage | Database models |
| `daily_scheduler.py` | `_run_line_snapshot_capture()` | 30-min line snapshots | Scheduler job |
| `daily_scheduler.py` | `_run_update_season_extremes()` | Daily 5 AM extremes | Scheduler job |

**Vortex Math Implementation:**
```python
# Tesla 3-6-9 sacred geometry analysis
calculate_vortex_energy(value, context="spread"|"total"|"prop"|"general")
# Returns:
{
    "vortex_score": 5.0-9.0,      # Baseline 5.0
    "digital_root": int,          # Single digit reduction
    "is_tesla_aligned": bool,     # Digital root is 3, 6, or 9
    "is_perfect_vortex": bool,    # Contains 369/396/639/693/936/963
    "is_golden_vortex": bool,     # Within 5% of phi multiples
    "triggered": bool,            # Score >= 7.0
    "signal": str,                # PERFECT_VORTEX|TESLA_ALIGNED|GOLDEN_RATIO|NEUTRAL
}
```

**Vortex Boost Logic:**
| Condition | Boost | Signal |
|-----------|-------|--------|
| Perfect vortex (369 sequence) | +0.3 | `PERFECT_VORTEX` |
| Tesla aligned (root=3,6,9) | +0.2 | `TESLA_ALIGNED` |
| Golden ratio (phi aligned) | +0.1 | `GOLDEN_RATIO` |
| Neutral | +0.0 | `NEUTRAL` |

**Benford Anomaly Fix (v17.6):**
- **Problem:** Only 3 values (prop_line, spread, total) - always < 10, Benford never ran
- **Solution:** `_extract_benford_values_from_game()` extracts from multi-book data:
  - Direct values: prop_line, spread, total (3 values)
  - Multi-book spreads: `game.bookmakers[].markets[spreads].outcomes[].point` (5-10 values)
  - Multi-book totals: `game.bookmakers[].markets[totals].outcomes[].point` (5-10 values)
  - **Result:** 10-25 unique values for Benford analysis
- **Pass `game_bookmakers` parameter** to `calculate_pick_score()` at all 3 call sites

**Line History Schema (v17.6):**
```sql
-- Table 1: Line snapshots for Hurst Exponent (needs 20+ sequential values)
CREATE TABLE line_snapshots (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL,
    sport VARCHAR(20) NOT NULL,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    book VARCHAR(50),
    spread DECIMAL(5,2),
    spread_odds INTEGER,
    total DECIMAL(6,2),
    total_odds INTEGER,
    public_pct DECIMAL(5,2),
    money_pct DECIMAL(5,2),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    game_start_time TIMESTAMP WITH TIME ZONE
);

-- Table 2: Season extremes for Fibonacci Retracement
CREATE TABLE season_extremes (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(20) NOT NULL,
    season VARCHAR(20) NOT NULL,
    stat_type VARCHAR(50) NOT NULL,
    subject_id VARCHAR(100),
    subject_name VARCHAR(100),
    season_high DECIMAL(8,2),
    season_low DECIMAL(8,2),
    current_value DECIMAL(8,2),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Line History Scheduler Jobs:**
| Job | Schedule | Purpose |
|-----|----------|---------|
| `_run_line_snapshot_capture()` | Every 30 minutes | Capture spread/total from Odds API |
| `_run_update_season_extremes()` | Daily 5 AM ET | Calculate season high/low |

**Line History Helper Functions (database.py):**
```python
save_line_snapshot(db, event_id, sport, ...)     # Save snapshot
get_line_history(db, event_id, limit=30)          # Get history dicts
get_line_history_values(db, event_id, "spread")   # Raw floats for Hurst
update_season_extreme(db, sport, season, ...)     # Update high/low
get_season_extreme(db, sport, season, stat_type)  # Get extremes for Fib
```

**Esoteric Engine Signal Status (17/17 active as of v18.2):**
| Signal | Status | Notes |
|--------|--------|-------|
| Numerology | ✅ ACTIVE | `calculate_generic_numerology()` |
| Astro | ✅ ACTIVE | Vedic astrology |
| Fibonacci Alignment | ✅ ACTIVE | `calculate_fibonacci_alignment()` - checks if line IS Fib number |
| Fibonacci Retracement | ✅ WIRED (v17.7) | `calculate_fibonacci_retracement()` - season range position |
| Vortex | ✅ ACTIVE (v17.6) | Tesla 3-6-9 via `calculate_vortex_energy()` |
| Daily Edge | ✅ ACTIVE + VOC (v17.5) | Daily energy score with VOC penalty |
| GLITCH (6 signals) | ✅ ACTIVE | `get_glitch_aggregate()` |
| Biorhythms | ✅ ACTIVE (v17.5) | Props only, player birth cycles |
| Gann Square | ✅ ACTIVE (v17.5) | Games only, sacred geometry |
| Founder's Echo | ✅ ACTIVE (v17.5) | Games only, team gematria |
| Hurst Exponent | ✅ WIRED (v17.7) | Line history passed to GLITCH (needs 10+ snapshots) |
| Benford Anomaly | ✅ ACTIVATED (v17.6) | Multi-book aggregation now provides 10+ values |
| **Lunar Phase** | ✅ ACTIVE (v18.2) | Full/New moon detection via `calculate_lunar_phase_intensity()` |
| **Mercury Retrograde** | ✅ ACTIVE (v18.2) | 2026 retrograde periods via `check_mercury_retrograde()` |
| **Rivalry Intensity** | ✅ ACTIVE (v18.2) | Major rivalry detection via `calculate_rivalry_intensity()` |
| **Streak Momentum** | ✅ ACTIVE (v18.2) | Win/loss streak analysis via `calculate_streak_momentum()` |
| **Solar Flare** | ✅ ACTIVE (v18.2) | NOAA X-ray flux via `get_solar_flare_status()` |

### Phase 8 - Advanced Esoteric Signals (v18.2 - Feb 2026)
| File | Function | Purpose | Trigger Condition |
|------|----------|---------|-------------------|
| `esoteric_engine.py` | `calculate_lunar_phase_intensity()` | Moon phase impact on scoring | Full moon (0.45-0.55) or New moon (0.0-0.05) |
| `esoteric_engine.py` | `check_mercury_retrograde()` | Retrograde caution signal | During 2026 retrograde periods |
| `esoteric_engine.py` | `calculate_rivalry_intensity()` | Major rivalry detection | Historic rivalry matchups |
| `esoteric_engine.py` | `calculate_streak_momentum()` | Team streak analysis | 2+ game win/loss streaks |
| `alt_data_sources/noaa.py` | `get_solar_flare_status()` | Solar activity chaos boost | X-class or M-class flare |
| `esoteric_engine.py` | `get_phase8_esoteric_signals()` | AGGREGATES ALL 5 | Entry point for Phase 8 |

**Phase 8 Signal Integration (live_data_router.py lines 4039-4106):**
```python
phase8_full_result = get_phase8_esoteric_signals(
    game_datetime=game_datetime,
    game_date=_game_date_obj,
    sport=sport,
    home_team=home_team,
    away_team=away_team,
    pick_type=pick_type,
    pick_side=pick_side,
    team_streak_data=_team_streak_data
)
phase8_boost = phase8_full_result.get("total_boost", 0.0)
esoteric_raw += phase8_boost
```

**Phase 8 Output Fields:**
```python
{
    "phase8_boost": float,
    "phase8_reasons": List[str],
    "phase8_breakdown": {
        "lunar": {"phase": "FULL/NEW/QUARTER", "boost_over": float, "boost_under": float},
        "mercury": {"is_retrograde": bool, "adjustment": float},
        "rivalry": {"is_rivalry": bool, "intensity": str, "under_boost": float},
        "streak": {"momentum": str, "for_boost": float},
        "solar": {"class": "X/M/QUIET", "chaos_boost": float}
    }
}
```

**v18.2 Bug Fixes Applied:**
1. Timezone-aware `ref_date` in `calculate_lunar_phase_intensity()` (line 1422-1426)
2. `weather_data = None` initialization at line 3345

### GLITCH Protocol Files
| File | Purpose | Key Functions |
|------|---------|---------------|
| `esoteric_engine.py` | GLITCH aggregator + Phase 1-3 signals | `get_glitch_aggregate()`, `calculate_chrome_resonance()`, `calculate_biorhythms()`, `analyze_spread_gann()`, `check_founders_echo()`, `calculate_vortex_energy()` |
| `alt_data_sources/noaa.py` | Kp-Index client | `fetch_kp_index_live()`, `get_kp_betting_signal()` |
| `alt_data_sources/serpapi.py` | Noosphere client | `get_noosphere_data()`, `get_team_buzz()` |
| `signals/math_glitch.py` | Benford analysis | `check_benford_anomaly()` |
| `signals/physics.py` | Hurst exponent | `calculate_hurst_exponent()` |
| `signals/hive_mind.py` | Void moon | `get_void_moon()` |
| `database.py` | Line history schema (v17.6) | `LineSnapshot`, `SeasonExtreme`, `save_line_snapshot()`, `get_line_history_values()` |
| `daily_scheduler.py` | Line history capture (v17.6) | `_run_line_snapshot_capture()`, `_run_update_season_extremes()` |

### Trap Learning Loop Files (v19.0)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `trap_learning_loop.py` | Core trap system (~800 LOC) | `TrapLearningLoop`, `TrapDefinition`, `TrapEvaluation`, `get_trap_loop()`, `enrich_game_result()`, `calculate_numerology_day()`, `calculate_team_gematria()` |
| `trap_router.py` | API endpoints (~400 LOC) | `create_trap()`, `list_traps()`, `get_trap()`, `update_trap_status()`, `dry_run_evaluation()`, `get_adjustment_history()` |
| `daily_scheduler.py` | Trap evaluation job | `_run_trap_evaluation()`, `_fetch_yesterday_results()` |

**Trap Data Flow:**
```
PRE-GAME                         POST-GAME (6:15 AM ET)
   │                                    │
Create Trap ───────────────────► Evaluate Traps
   │                                    │
   │  {condition, action,          Game Results
   │   target_engine,                   │
   │   target_parameter}           Check Conditions
   │                                    │
   └──────────────────────────► Apply Adjustments
                                        │
                                  Log & Audit
```

**Trap Definition Schema:**
```python
@dataclass
class TrapDefinition:
    trap_id: str                    # "dallas-blowout-public-fade"
    name: str                       # Human-readable name
    sport: str                      # NBA, NFL, MLB, NHL, NCAAB, ALL
    team: Optional[str]             # Specific team or None for all
    condition: Dict                 # JSON condition object
    action: Dict                    # What to do when triggered
    target_engine: str              # ai, research, esoteric, jarvis, context
    target_parameter: str           # Specific weight/parameter
    adjustment_cap: float = 0.05    # Max 5% per trigger
    cooldown_hours: int = 24        # Min time between triggers
    max_triggers_per_week: int = 3  # Rate limiting
    status: str = "ACTIVE"          # ACTIVE, PAUSED, RETIRED
```

### Complete Learning System Files (v20.2)
| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `auto_grader.py` | Statistical learning (6:00 AM ET) | `AutoGrader`, `PredictionRecord`, `calculate_bias()`, `adjust_weights_with_reconciliation()`, `check_trap_reconciliation()`, `_initialize_weights()`, `_convert_pick_to_record()` |
| `trap_learning_loop.py` | Hypothesis learning (6:15 AM ET) | `TrapLearningLoop`, `has_recent_trap_adjustment()`, `get_recent_parameter_adjustments()` |
| `grader_store.py` | Pick persistence | `persist_pick()`, `load_predictions()` |
| `live_data_router.py` | Signal extraction for learning | Lines 4887-4899 (glitch_signals), Lines 6390-6420 (pick persistence) |

**Critical auto_grader.py Lines (v20.2):**
| Line Range | Function | Purpose |
|------------|----------|---------|
| 173-210 | `_initialize_weights()` | **MUST include game_stat_types (spread, total, moneyline, sharp)** |
| 261-318 | `_convert_pick_to_record()` | Sets `stat_type = pick_type.lower()` for game picks |
| 534-634 | `calculate_bias()` | Filters by `record.stat_type == stat_type` (exact match) |
| 787-866 | `adjust_weights()` | Falls back to "points" if stat_type missing (line 802-803) |
| 1035-1078 | `run_daily_audit()` | Iterates over game_stat_types = ["spread", "total", "moneyline", "sharp"] |

**stat_type Mapping (v20.2):**
| Pick Type | stat_type Value | Source |
|-----------|-----------------|--------|
| PROP | "points", "rebounds", etc. | `pick.get("stat_type", ...)` |
| SPREAD | "spread" | `pick_type.lower()` |
| TOTAL | "total" | `pick_type.lower()` |
| MONEYLINE | "moneyline" | `pick_type.lower()` |
| SHARP | "sharp" | `pick_type.lower()` |

**PredictionRecord Signal Tracking (28 signals - 100% coverage):**
```python
@dataclass
class PredictionRecord:
    # Core fields
    prediction_id: str
    sport: str
    player_name: str
    stat_type: str
    predicted_value: float
    actual_value: Optional[float] = None
    pick_type: str = ""  # PROP, SPREAD, TOTAL, MONEYLINE, SHARP

    # Context Layer (Pillars 13-15)
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0

    # Research Engine Signals
    sharp_money_adjustment: float = 0.0
    public_fade_adjustment: float = 0.0
    line_variance_adjustment: float = 0.0

    # GLITCH Protocol Signals (6 signals)
    glitch_signals: Optional[Dict[str, float]] = None
    # chrome_resonance, void_moon, noosphere, hurst, kp_index, benford

    # Esoteric Contributions (14 signals)
    esoteric_contributions: Optional[Dict[str, float]] = None
    # numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge,
    # biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar
```

**Trap-AutoGrader Reconciliation Flow:**
```
AutoGrader (6:00 AM ET)
    │
    ├── Calculate bias for ALL 28 signals
    │   (with 70% confidence decay per day)
    │
    ├── Before adjusting any parameter:
    │   check_trap_reconciliation(engine, parameter)
    │       │
    │       └── has_recent_trap_adjustment(engine, parameter, lookback=24h)
    │           │
    │           └── If trap adjusted in last 24h → SKIP this parameter
    │
    └── Apply remaining adjustments
        (only parameters NOT recently adjusted by traps)

Trap Learning Loop (6:15 AM ET)
    │
    ├── Evaluate pre-game traps against results
    │
    └── Apply conditional adjustments
        (logged to adjustments.jsonl)
```

### Context Layer Files
| File | Purpose | Key Classes |
|------|---------|-------------|
| `context_layer.py` | Pillars 13-17 | `DefensiveRankService`, `PaceVectorService`, `UsageVacuumService`, `OfficialsService`, `ParkFactorService` |

### Scoring Contract
| File | Purpose |
|------|---------|
| `core/scoring_contract.py` | Single source of truth for weights, thresholds, gates |

### Master Specification
| File | Purpose |
|------|---------|
| `docs/JARVIS_SAVANT_MASTER_SPEC.md` | Full master spec + integration audit + missing API map |

### Security Files (Added Feb 2026)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `core/log_sanitizer.py` | Centralized secret redaction | `sanitize_headers()`, `sanitize_dict()`, `sanitize_url()` |
| `tests/test_log_sanitizer.py` | 20 tests for sanitizer | Tests headers, dicts, URLs, tokens |
| `tests/test_no_demo_data.py` | 12 tests for demo gate | Tests fallback behavior, endpoint gating |

### MSRF Files (Added Feb 2026)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `signals/msrf_resonance.py` | Turn date resonance (~565 LOC) | `calculate_msrf_resonance()`, `get_msrf_confluence_boost()` |
| `signals/__init__.py` | Exports MSRF functions | `MSRF_ENABLED`, `MSRF_NORMAL`, `MSRF_IMPORTANT`, `MSRF_VORTEX` |
| `docs/MSRF_INTEGRATION_PLAN.md` | Implementation plan | Reference for MSRF architecture decisions |

**MSRF Data Flow:**
```
get_significant_dates()
  ├── get_significant_dates_from_predictions() → /data/grader/predictions.jsonl
  └── get_significant_dates_from_player_history() → BallDontLie API (NBA only)
        ↓
calculate_msrf_resonance(dates, game_date)
  ├── 16 operations × 3 intervals → transformed values
  └── Match against MSRF_NORMAL/IMPORTANT/VORTEX → points
        ↓
get_msrf_confluence_boost() → (boost, metadata)
        ↓
live_data_router.py:3567 → adds to confluence["boost"]
```

### SERP Intelligence Files (Added Feb 2026 - v17.4)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `core/serp_guardrails.py` | Central config, quota, caps (~354 LOC) | `check_quota_available()`, `apply_shadow_mode()`, `cap_boost()`, `get_serp_status()` |
| `alt_data_sources/serp_intelligence.py` | Engine-aligned signal detection (~823 LOC) | `get_serp_betting_intelligence()`, `get_serp_prop_intelligence()`, `detect_*()` |
| `alt_data_sources/serpapi.py` | SerpAPI client with guardrails (~326 LOC) | `get_search_trend()`, `get_team_buzz()`, `get_player_buzz()`, `get_noosphere_data()` |

**SERP Signal Detectors:**
| Function | Engine | What It Detects |
|----------|--------|-----------------|
| `detect_silent_spike()` | AI | High search volume + low news (insider activity) |
| `detect_sharp_chatter()` | Research | Sharp money, RLM mentions in search |
| `detect_narrative()` | Jarvis | Revenge games, rivalries, playoff implications |
| `detect_situational()` | Context | B2B, rest advantage, travel fatigue |
| `detect_noosphere()` | Esoteric | Search trend velocity between teams |

**SERP Data Flow (v20.7 — Parallel Pre-Fetch):**
```
_best_bets_inner() — BEFORE scoring loop:
  │
  ├── Extract unique (home, away) pairs from raw_games + prop_games
  │
  ├── ThreadPoolExecutor(max_workers=16)
  │     └── _prefetch_serp_game(home, away, target) × 2 per game
  │           └── get_serp_betting_intelligence(sport, home, away, target)
  │                 ├── detect_silent_spike(team, sport) → AI boost
  │                 ├── detect_sharp_chatter(team, sport) → Research boost
  │                 ├── detect_narrative(home, away, sport) → Jarvis boost
  │                 ├── detect_situational(team, sport, b2b, rest) → Context boost
  │                 └── detect_noosphere(home, away) → Esoteric boost
  │
  └── _serp_game_cache[(home_lower, away_lower, target_lower)] = result

calculate_pick_score() — DURING scoring loop:
  │
  ├── Game bets: Check _serp_game_cache first (cache hit ~0ms)
  │     └── Fallback: get_serp_betting_intelligence() if cache miss
  │
  └── Prop bets: get_serp_prop_intelligence() inline (per-player, not pre-fetchable)
        ↓
  cap_total_boost(boosts) → enforce 4.3 total cap
        ↓
  apply_shadow_mode(boosts) → zero if shadow mode (currently OFF)
        ↓
  confluence["boost"] += serp_boost_total
```

**SERP Query Templates (SPORT_QUERIES):**
- NBA: `"{team} sharp money"`, `"{team} reverse line movement"`, `"{team1} vs {team2} rivalry"`
- NFL: `"{team} sharp action"`, `"{team} weather game"`, `"{team} short week"`
- MLB: `"{team} sharp money MLB"`, `"{team} bullpen tired"`, `"{team} pennant race"`
- NHL: `"{team} sharp money NHL"`, `"{team} back to back NHL"`
- NCAAB: `"{team} sharp money college basketball"`, `"{team} tournament"`

---

### ESPN Hidden API Files (Added Feb 2026 - v17.3)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `alt_data_sources/espn_lineups.py` | ESPN Hidden API client (~600 LOC) | See functions below |
| `alt_data_sources/__init__.py` | ESPN exports | `ESPN_AVAILABLE`, all ESPN functions |

**ESPN Functions:**
| Function | Purpose | Returns |
|----------|---------|---------|
| `get_espn_scoreboard()` | Today's games | Events list with IDs |
| `get_espn_event_id()` | Find event by teams | ESPN event ID |
| `get_officials_for_event()` | Referee assignments | Officials list (Pillar 16) |
| `get_officials_for_game()` | Officials by team names | Officials data |
| `get_espn_odds()` | Spread, ML, O/U | Odds dict (cross-validation) |
| `get_espn_injuries()` | Inline injury data | Injuries list |
| `get_espn_player_stats()` | Box scores | Player stats by team |
| `get_espn_venue_info()` | Venue, weather, attendance | Venue dict |
| `get_game_summary_enriched()` | All data in one call | Combined dict |
| `get_all_games_enriched()` | Batch for all games | List of enriched games |

**ESPN Endpoints (FREE - No Auth Required):**
```
Scoreboard:  https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
Summary:     https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
Officials:   https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials
Teams:       https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{abbrev}
```

**Sport/League Mapping:**
```python
SPORT_MAPPING = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
    "MLB": {"sport": "baseball", "league": "mlb"},
    "NHL": {"sport": "hockey", "league": "nhl"},
    "NCAAB": {"sport": "basketball", "league": "mens-college-basketball"},
}
```

**ESPN Data Flow (v17.3):**
```
_best_bets_inner() parallel fetch:
├── Props (Odds API)
├── Games (Odds API)
├── Injuries (Playbook)
├── ESPN Scoreboard
│   └── Build _espn_events_by_teams lookup
│
├── ESPN Officials (batch for all events)
│   └── Build _officials_by_game lookup
│
└── ESPN Enriched (batch for all events)
    ├── Odds → _espn_odds_by_game (cross-validation)
    ├── Injuries → _espn_injuries_supplement (merge with Playbook)
    └── Venue/Weather → _espn_venue_by_game (MLB/NFL outdoor)

Scoring Integration:
├── Research Engine: +0.25-0.5 boost when ESPN confirms spread/total
├── Injuries: ESPN injuries merged into _injuries_by_team
├── Weather: ESPN venue/weather as fallback for outdoor sports
└── Officials: Pillar 16 adjustment from referee tendencies
```

**Reference:** https://scrapecreators.com/blog/espn-api-free-sports-data

### Dual-Use Functions (Endpoint + Internal) - CRITICAL
| Function | Line | Endpoint | Internal Callers | Return Type |
|----------|------|----------|------------------|-------------|
| `get_sharp_money()` | 1758 | `/live/sharp/{sport}` | `_best_bets_inner:2580` | dict ✅ |
| `get_splits()` | 1992 | `/live/splits/{sport}` | dashboard | dict ✅ |
| `get_lines()` | 2100+ | `/live/lines/{sport}` | dashboard | dict ✅ |
| `get_injuries()` | 2200+ | `/live/injuries/{sport}` | dashboard | dict ✅ |

**Rule:** ALL functions in this table MUST return dicts, NOT JSONResponse. FastAPI auto-serializes.

### Go/No-Go Sanity Scripts (v20.4)
| Script | Purpose | Key Checks |
|--------|---------|------------|
| `scripts/prod_go_nogo.sh` | Master orchestrator | Runs all 12 checks, fails fast |
| `scripts/option_a_drift_scan.sh` | Scoring formula guard | No BASE_5, no context-as-engine |
| `scripts/audit_drift_scan.sh` | Unauthorized boost guard | No literal +/-0.5 outside ensemble |
| `scripts/endpoint_matrix_sanity.sh` | Endpoint contract | All sports, required fields, math check |
| `scripts/docs_contract_scan.sh` | Documentation sync | Required fields documented |
| `scripts/env_drift_scan.sh` | Environment config | Required env vars set |
| `scripts/learning_loop_sanity.sh` | Auto grader health | Grader available, weights loaded |
| `scripts/learning_sanity_check.sh` | Weights initialized | All stat types have weights |
| `scripts/live_sanity_check.sh` | Best-bets health | Returns valid JSON structure |
| `scripts/api_proof_check.sh` | Production API | API responding with 200 |

**Critical Line Number Filters (audit_drift_scan.sh):**
```bash
# Allowed ensemble adjustment lines in live_data_router.py:
# - 4753-4754: ensemble_reasons extend
# - 4756-4757: boost (+0.5) fallback
# - 4760-4762: penalty (-0.5) fallback
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" | \
rg -v "live_data_router.py:476[012]"
```

**Math Formula (endpoint_matrix_sanity.sh line 93-97):**
```jq
($p.base_4_score + $p.context_modifier + $p.confluence_boost +
 $p.msrf_boost + $p.jason_sim_boost + $p.serp_boost +
 ($p.ensemble_adjustment // 0) + ($p.live_adjustment // 0) +
 ($p.totals_calibration_adj // 0)) as $raw |
($raw | if . > 10 then 10 else . end) as $capped |
($p.final_score - $capped) | abs
# Must be < 0.02
```
**Every field that adjusts final_score MUST appear in this formula.** If you add a new adjustment to the scoring pipeline, you MUST: (1) surface it as its own field in the pick payload, (2) add it to this formula with `// 0` null handling.

### Key Debugging Locations
| Location | Line | Purpose |
|----------|------|---------|
| `get_best_bets()` exception handler | 2536-2547 | Catches all best-bets crashes, logs traceback |
| `_best_bets_inner()` | 2546+ | Main best-bets logic, 3000+ lines |
| `calculate_pick_score()` | 3084+ | Nested scoring function, ~900 lines |
| `calculate_jarvis_engine_score()` | 2622+ | Jarvis scoring, can return `jarvis_rs: None` |

### Debugging Commands
```bash
# Get detailed error info from best-bets
curl "/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY" | jq '.detail'

# Check if endpoint returns JSONResponse (should NOT for internal calls)
# If you see "JSONResponse object has no attribute 'get'" - function returns wrong type

# Test all 5 sports after ANY scoring change
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, games: .game_picks.count, props: .props.count, error: .detail.code}'
done
```

---

## 🔴 LESSONS LEARNED (NEVER REPEAT)

### Lesson 1: Dormant Code Detection
**Problem:** 8 AI models + 14 LSTM weights existed but were never called. Production used `base_ai = 5.0` hardcoded.

**Root Cause:** Code was written but integration points were never added to `live_data_router.py`.

**Prevention:**
- Every new feature MUST have an integration point in the scoring pipeline
- Use `grep -r "function_name" live_data_router.py` to verify integration
- Add to this MASTER FILE INDEX when creating new modules

### Lesson 2: Orphaned Signal Detection
**Problem:** GLITCH Protocol had 19 features designed, but only 10 were active. 9 were "orphaned" (code exists, never called).

**Root Cause:** `get_glitch_aggregate()` was created but individual signals weren't wired in.

**Prevention:**
- Every signal function MUST be called somewhere
- Use grep to verify: `grep -r "function_name" *.py | grep -v "^def\|^#"`
- Document signal weights and integration points

### Lesson 3: API Stubbing vs. Real Implementation
**Problem:** NOAA and SerpAPI were "stubbed" (returning default values) instead of making real API calls.

**Root Cause:** Stub code was written for development but never replaced with real implementation.

**Prevention:**
- Check for `return {"source": "fallback"}` patterns
- Verify env vars are set: `curl /live/debug/integrations`
- Real APIs should show `"source": "xxx_live"` in responses

### Lesson 4: Parameter Passing
**Problem:** `get_glitch_aggregate()` accepted `value_for_benford` parameter but ignored it internally.

**Root Cause:** Function signature was updated but body wasn't.

**Prevention:**
- Search for unused parameters: functions should USE what they accept
- Read function body after changing signature

### Lesson 5: Weight Normalization
**Problem:** GLITCH aggregate weights didn't sum properly, causing score drift.

**Prevention:**
- Always verify: `sum(weights) == 1.0` or use `weighted_score / total_weight`
- Document weights in function docstring

### Lesson 6: Secret Leakage in Logs (SECURITY)
**Problem:** API keys were logged in multiple places:
- `playbook_api.py:211` logged full query params including `api_key`
- `live_data_router.py:6653` constructed URL with bare `?apiKey=VALUE`
- `legacy/services/odds_api_service.py:30` logged `key[:8]...` (reconnaissance risk)

**Root Cause:** No centralized log sanitization. Each developer logged debug info without thinking about secrets.

**Prevention:**
- Use `core/log_sanitizer.py` for ALL logging that might contain sensitive data
- NEVER construct URLs with `?apiKey=` - use `params={}` dict instead
- NEVER log partial keys - even `key[:8]` is a security risk
- Run `grep -rn "apiKey\|api_key\|authorization" *.py` and verify all are sanitized

**Fixed in:** Commit `2e67adc` (Feb 2026)

### Lesson 7: Demo Data Leakage (SECURITY)
**Problem:** Sample/demo data (Lakers/Warriors, LeBron James picks) could leak to production when APIs failed.

**Root Cause:** Fallback code returned demo data without any gate. Any API failure would expose fake picks.

**Prevention:**
- ALL demo data MUST be gated behind `ENABLE_DEMO=true` or `mode=demo`
- When live data unavailable, return EMPTY response, not sample data
- Debug seed endpoints MUST check for demo flag before creating test picks
- Search for hardcoded player names in non-test files: `grep -rn "LeBron\|Lakers" --include="*.py" | grep -v test`

**Fixed in:** Commit `2e67adc` (Feb 2026)

### Lesson 8: New Signal Integration Pattern (MSRF)
**Problem:** How to integrate a new esoteric signal (MSRF) without disrupting existing scoring.

**Solution:** Use CONFLUENCE BOOST pattern instead of creating a 6th engine.

**Integration Pattern (RECOMMENDED for new signals):**
1. Create standalone module in `signals/` directory
2. Export main function as `get_XXX_confluence_boost(context) → (boost, metadata)`
3. Return boost value (0.0, 0.25, 0.5, 1.0) + full metadata dict
4. Integrate in `live_data_router.py` AFTER Harmonic Convergence, BEFORE `confluence_boost =`
5. Add to `confluence["boost"]` (not to engine scores directly)
6. Log boost in `esoteric_reasons` (for debug visibility)
7. Include `XXX_boost` and `XXX_metadata` in pick output

**Why Confluence Boost:**
- Avoids diluting BASE_4 weights (context is modifier-only)
- Easy to enable/disable via feature flag
- Provides additive boost only when signal fires
- Keeps engines clean and focused

**Files Changed for MSRF:**
```
signals/msrf_resonance.py     # NEW - Core module
signals/__init__.py           # MODIFIED - Export functions
live_data_router.py:3567-3591 # MODIFIED - Integration point
```

**Fixed in:** Commit `ce083ef` (Feb 2026)

### Lesson 9: Dual-Use Functions (Endpoint + Internal) - CRITICAL
**Problem:** `get_sharp_money()` was both an endpoint handler (`@router.get("/sharp/{sport}")`) AND called internally by `_best_bets_inner()`. The function returned `JSONResponse` objects, which worked for the endpoint but crashed internal callers expecting a dict.

**Error Message:**
```
AttributeError: 'JSONResponse' object has no attribute 'get'
```

**Root Cause:** Function returned `JSONResponse(_sanitize_public(result))` for all paths. When called internally at line 2580, the code did `sharp_data.get("data", [])` which failed because `JSONResponse` has no `.get()` method.

**The Pattern That Caused This:**
```python
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    # ... fetch data ...
    result = {"sport": sport, "data": [...]}
    return JSONResponse(_sanitize_public(result))  # ❌ WRONG for dual-use
```

**The Fix:**
```python
@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    # ... fetch data ...
    result = {"sport": sport, "data": [...]}
    return result  # ✅ FastAPI auto-serializes dicts for endpoints
```

**Prevention Rules:**
1. Functions used BOTH as endpoints AND internally MUST return dicts (not JSONResponse)
2. FastAPI automatically serializes dict returns to JSON for endpoint responses
3. Only use `JSONResponse()` when you need custom headers, status codes, or media types
4. Before calling any `async def` function internally, check if it's also an endpoint handler
5. Search for dual-use patterns: `grep -n "@router" *.py` then check if those functions are called elsewhere

**Verification:**
```bash
# Find endpoint handlers
grep -n "@router.get\|@router.post" live_data_router.py | head -20

# Check if any are called internally (not just as endpoints)
# Example: get_sharp_money is defined at line 1758
grep -n "get_sharp_money(" live_data_router.py
# If called anywhere other than the decorator line, it's dual-use
```

**Files Affected:**
- `live_data_router.py:1758-1989` - `get_sharp_money()` fixed to return dict

**Fixed in:** Commit `d7279e9` (Feb 2026)

### Lesson 10: Undefined Variables in Nested Functions
**Problem:** Multiple `NameError` and `TypeError` crashes in `calculate_pick_score()` due to undefined variables or None comparisons.

**Bugs Found (Feb 2026 Debugging Session):**
| Variable | Error | Line | Fix |
|----------|-------|------|-----|
| `_game_date_obj` | NameError | 3571 | Initialize to `None` before try block (line 3440) |
| `jarvis_rs >= 7.5` | TypeError | 3527 | Add `jarvis_rs is not None and` check |
| `esoteric_reasons` | NameError | various | Initialize as `[]` at function start |
| `odds`, `candidate` | NameError | GLITCH section | Removed undefined variable usage |

**Root Cause:** Nested function `calculate_pick_score()` inside `_best_bets_inner()` uses many variables. When code paths skip initialization (e.g., try block fails early), variables remain undefined.

**Prevention Rules:**
1. Initialize ALL variables at the START of the function, before any try blocks
2. Variables used in except/finally blocks MUST be initialized before the try
3. Before comparing numeric variables (e.g., `>= 7.5`), check for None
4. Use `variable is not None and variable >= threshold` pattern
5. When adding new variables to nested functions, grep for all usages and verify initialization

**Pattern:**
```python
# ✅ CORRECT - Initialize before try block
_game_date_obj = None  # Initialize here
glitch_adjustment = 0.0
try:
    _game_date_obj = parse_date(...)  # May fail
    # ... use _game_date_obj ...
except Exception:
    pass  # _game_date_obj is still None, not undefined

# Later code can safely check:
if _game_date_obj:  # Won't raise NameError
    do_something(_game_date_obj)
```

**Fixed in:** Commits `f1b9dae`, `fd4f105`, `559e173`, `4b0a35e`, `0d66095` (Feb 2026)

### Lesson 11: Production Debugging Without Logs Access
**Problem:** `BEST_BETS_FAILED` error gave no details about the actual exception. Had to iterate through multiple deploy cycles to find bugs.

**Solution Implemented:** Added detailed error info to response in debug mode:
```python
except Exception as e:
    import traceback as _tb
    _tb_str = _tb.format_exc()
    logger.error("best-bets CRASH: %s\n%s", e, _tb_str)
    detail = {"code": "BEST_BETS_FAILED", "message": "best-bets failed"}
    if debug_mode:
        detail["error_type"] = type(e).__name__
        detail["error_message"] = str(e)
        detail["traceback"] = _tb_str[-2000:]  # Last 2000 chars
    raise HTTPException(status_code=500, detail=detail)
```

**Usage:**
```bash
# Get detailed error info
curl "/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY"
# Returns: {"detail": {"code": "...", "error_type": "AttributeError", "error_message": "...", "traceback": "..."}}
```

**Prevention:**
- ALL major endpoints should include error details in debug mode
- Never swallow exceptions silently - always log with traceback
- Use `?debug=1` query param to get verbose error info in production

**Fixed in:** Commit `1cf5290` (Feb 2026)

### Lesson 12: API Data Format Mismatches (Playbook vs ESPN)
**Problem:** Injuries data wasn't being parsed correctly. Playbook and ESPN return injuries in different formats:
- **Playbook:** Team objects with nested `players` array (`{"teamName": "...", "players": [...]}`)
- **ESPN:** Flat list with `team` field per injury (`{"team": "...", "player": "..."}`)

**Root Cause:** Code assumed ESPN format (flat list), but production uses Playbook which nests players under team objects.

**Prevention:**
- When integrating API data, check BOTH format variations the API might return
- Add format detection: `if "players" in item and isinstance(item.get("players"), list)`
- Normalize to common format before use
- Test with actual production API responses, not assumptions

**Fixed in:** Commit `01b372c` (Feb 2026)

### Lesson 13: Scope Issues with Context Calculations
**Problem:** Context values (def_rank, pace, vacuum) were only calculated for PROP picks, not GAME picks. GAME picks got default values (def_rank=16, pace=100, vacuum=0).

**Root Cause:** The context lookup code was inside the `if pick_type == "PROP"` block instead of running for ALL pick types.

**Prevention:**
- Context calculations (Pillars 13-15) should run BEFORE the pick_type branch
- Move shared context setup OUTSIDE type-specific blocks
- Verify all pick types show real values in debug output, not just defaults
- Test: `curl /live/best-bets/NBA?debug=1 | jq '.game_picks.picks[0].context_layer'`

**Fixed in:** Commit `6780c93` (Feb 2026)

### Lesson 14: NCAAB Team Name Matching (Mascot Stripping)
**Problem:** NCAAB team names from Odds API include mascots ("North Carolina Tar Heels") but context layer data uses short names ("North Carolina"). This caused all NCAAB picks to get default context values.

**Additional Issue:** Aggressive fuzzy matching caused false positives where "Alabama St Hornets" matched "Alabama" (Crimson Tide) and "North Carolina Central Eagles" matched "North Carolina" (Tar Heels) - completely different schools.

**Root Cause:** The `standardize_team()` function only handled abbreviations, not NCAAB mascot suffixes.

**Solution Implemented:**
1. Added `NCAAB_TEAM_MAPPING` dict with 80+ major program mappings
2. Added `MASCOT_SUFFIXES` whitelist for conservative fuzzy matching
3. Only strip suffixes that are known mascots (not school identifiers like "St" or "Central")

**Key Code (context_layer.py):**
```python
NCAAB_TEAM_MAPPING = {
    "North Carolina Tar Heels": "North Carolina",
    "Duke Blue Devils": "Duke",
    "Syracuse Orange": "Syracuse",
    # ... 80+ mappings
}

MASCOT_SUFFIXES = {
    "Wildcats", "Tigers", "Bulldogs", "Eagles", "Tar Heels",
    "Blue Devils", "Orange", "Crimson Tide", ...
}
```

**Prevention:**
- Always check API team name format vs data format when adding new sports/data
- Use explicit mappings for common cases, conservative fuzzy matching for edge cases
- Test with both major programs AND small schools to catch false positives
- Verify: `curl /live/best-bets/NCAAB?debug=1 | jq '[.game_picks.picks[] | {matchup, pace}] | unique'`

**Known Limitation:** Small schools not in data (SE Louisiana, Gardner-Webb, etc.) will correctly get defaults.

**Fixed in:** Commits `98117dc`, `6518478` (Feb 2026)

### Lesson 15: ESPN Officials Integration (Pillar 16)
**Problem:** Pillar 16 (Officials) code was ready in `OfficialsService` but had no data source - the placeholder code had empty strings for `lead_official`, `official_2`, `official_3`.

**Solution Implemented (v17.2):**
1. Created `alt_data_sources/espn_lineups.py` - ESPN Hidden API integration (FREE, no auth)
2. Added ESPN scoreboard fetch to parallel gather in `_best_bets_inner()`
3. Prefetch officials for all games in batch operation
4. Store in `_officials_by_game[(home_lower, away_lower)]` lookup
5. Scoring function accesses via closure (like `_injuries_by_team`)

**ESPN Hidden API Endpoints:**
- Scoreboard: `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard`
- Officials: `https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials`

**Key Files:**
```
alt_data_sources/espn_lineups.py    # NEW - ESPN API client
live_data_router.py:266-277         # NEW - ESPN import
live_data_router.py:4207-4222       # MODIFIED - Parallel fetch includes ESPN
live_data_router.py:4267-4311       # NEW - Officials lookup building
live_data_router.py:3720-3770       # MODIFIED - Officials section uses prefetched data
```

**Verification:**
```bash
# Check if officials data appears in picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {officials_adjustment, research_reasons}'
# Should include "Officials: ..." in research_reasons when refs are assigned
```

**Note:** ESPN may not have officials data for all games (refs assigned closer to game time). The system gracefully falls back when data is unavailable.

**Fixed in:** Commit (Feb 2026)

### Lesson 16: NHL Team Name Accent Normalization
**Problem:** ESPN may return "Montréal Canadiens" (with accent) but context layer data uses "Montreal Canadiens" (without accent), causing lookup misses.

**Solution:** Added `NHL_ACCENT_MAP` to `standardize_team()` in `context_layer.py`:
```python
NHL_ACCENT_MAP = {
    "Montréal Canadiens": "Montreal Canadiens",
    "Montréal": "Montreal",
}
```

**Prevention:** When integrating external APIs, check for Unicode character variants (accents, special characters) that may differ from local data.

**Fixed in:** Commit (Feb 2026)

### Lesson 17: ESPN Data Expansion for Cross-Validation (v17.3)
**Problem:** We had ESPN officials working but weren't using the rich data available in ESPN's summary endpoint (odds, injuries, venue, weather).

**Solution Implemented (v17.3):**
1. Expanded `alt_data_sources/espn_lineups.py` with new extraction functions
2. Batch fetch ESPN enriched data (odds, injuries, venue) for ALL games in parallel
3. Use ESPN odds for cross-validation (+0.25-0.5 research boost when confirmed)
4. Merge ESPN injuries with Playbook injuries
5. Use ESPN venue/weather as fallback for outdoor sports (MLB, NFL)

**New Functions Added:**
```python
get_espn_odds(sport, event_id)        # Spread, ML, O/U extraction
get_espn_injuries(sport, event_id)    # Inline injury data
get_espn_player_stats(sport, event_id) # Box scores for props
get_espn_venue_info(sport, event_id)  # Venue, weather, attendance
get_game_summary_enriched(...)        # All data in one call
get_all_games_enriched(sport)         # Batch for all games
```

**Integration Points in live_data_router.py:**
```
Line 4333-4395: Batch fetch ESPN enriched data
Line 4397-4408: Merge ESPN injuries with Playbook
Line 3281-3312: ESPN odds cross-validation boost
Line 4700-4737: ESPN venue/weather for outdoor sports
```

**Research Boost Logic:**
```python
# ESPN confirms our spread (diff <= 0.5) → +0.5
# ESPN spread close (diff <= 1.0) → +0.25
# ESPN confirms total (diff <= 1.0) → +0.5
# ESPN total close (diff <= 2.0) → +0.25
```

**Prevention:**
- When a free API offers rich data, USE ALL OF IT
- Cross-validate primary data sources with secondary sources
- Batch parallel fetches to avoid N+1 query problems
- Always merge supplementary data, don't replace

**Fixed in:** Commit `f10de5b` (Feb 2026)

### Lesson 18: NCAAB Team Coverage Expansion (50 → 75 Teams)
**Problem:** NCAAB defensive data only covered Top 50 teams, causing mid-major tournament teams (VCU, Dayton, Murray State, etc.) to get default values.

**Solution Implemented:**
1. Expanded `NCAAB_DEFENSE_VS_GUARDS/WINGS/BIGS` from 50 to 75 teams
2. Added 25 mid-major tournament regulars (51-75)
3. Expanded `NCAAB_PACE` with pace values for these teams
4. Updated `DefensiveRankService.get_total_teams()` from 50 to 75

**Teams Added (51-75):**
```python
VCU, Dayton, Saint Mary's, Nevada, New Mexico, UNLV, Drake, Murray State,
Richmond, Davidson, Wichita State, FAU, UAB, Grand Canyon, Akron, Toledo,
Boise State, Utah State, Colorado State, George Mason, Saint Louis,
Loyola Chicago, Princeton, Yale, Liberty
```

**Prevention:**
- When adding team data, include tournament-relevant mid-majors
- Test with actual games to verify coverage
- Update team count constants when expanding data

**Fixed in:** Commit `46f81c6` (Feb 2026)

### Lesson 19: MLB SPORT_MAPPING Bug
**Problem:** MLB ESPN data wasn't being fetched - all MLB games showed empty ESPN enriched data.

**Root Cause:** Typo in `SPORT_MAPPING` - `"mlb": "mlb"` instead of `"league": "mlb"`:
```python
# BUG (wrong key name):
"MLB": {"sport": "baseball", "mlb": "mlb"}

# FIX (correct key name):
"MLB": {"sport": "baseball", "league": "mlb"}
```

**Prevention:**
- Verify all dictionary keys are consistent across the mapping
- Test ALL sports after adding/modifying sport mappings
- Use constants for repeated key names when possible

**Fixed in:** Commit `018d9ef` (Feb 2026)

### Lesson 20: Contradiction Gate Silent Failure
**Problem:** Both Over AND Under were returned for same totals. Contradiction gate wasn't blocking anything.

**Root Cause:** `filter_contradictions()` returned `[], {}` (empty dict) when props list was empty, but `apply_contradiction_gate()` expected dict with `contradictions_detected` key. This caused a silent `KeyError` that was caught by the try/except fallback.

**The Silent Failure Pattern:**
```python
try:
    filtered_props, filtered_games, debug = apply_contradiction_gate(...)
except Exception as e:
    # Fallback silently used - BUG HIDDEN
    filtered_props = filtered_props
    filtered_games = filtered_game_picks
```

**Fix:** Return proper dict structure when empty:
```python
if not picks:
    return [], {"contradictions_detected": 0, "picks_dropped": 0, "contradiction_groups": []}
```

**Prevention:**
- Always return consistent dict structure, not empty `{}`
- Log exceptions in fallback blocks (don't just swallow)
- Add assertions for expected dict keys in tests
- Test contradiction gate with empty props + non-empty games (the failure case)

**Fixed in:** Commit `b5ffc3c` (Feb 2026)

### Lesson 21: SERP Shadow Mode Default (Live Mode Required)
**Problem:** SERP intelligence was configured with `SERP_SHADOW_MODE=True` by default, which zeroed all boosts. User explicitly wanted LIVE MODE where boosts are actively applied to scoring.

**Root Cause:** The default was set to True (shadow/observation mode) as a safety measure during initial implementation, but it was never flipped to False for production use.

**The Shadow Mode Pattern:**
```python
# WRONG - All boosts zeroed, signals logged but never applied
SERP_SHADOW_MODE = _env_bool("SERP_SHADOW_MODE", True)  # ❌

# CORRECT - Boosts applied to scoring (LIVE MODE)
SERP_SHADOW_MODE = _env_bool("SERP_SHADOW_MODE", False)  # ✅
```

**What Shadow Mode Does:**
- When `True`: All SERP boosts are logged but set to 0.0 before applying
- When `False`: Boosts from Silent Spike, Sharp Chatter, Narrative, etc. actively modify scores

**Prevention:**
- Always verify `SERP_SHADOW_MODE` default in `core/serp_guardrails.py`
- Check debug output shows `shadow_mode: false` and `mode: "live"`
- Test that picks have non-zero `serp_boost` when signals fire
- User confirmed preference: "i dont want anything in shadowmode. I want everything active"

**Verification:**
```bash
# Must show shadow_mode: false, mode: "live"
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
```

**Fixed in:** Commit enabling SERP live mode by default (Feb 2026)

### Lesson 22: pick_type Value Mismatch (v17.5)
**Problem:** Phase 1 dormant signals (Gann Square, Founder's Echo) weren't triggering because the code checked `pick_type == "GAME"`, but game picks use `pick_type` values of "SPREAD", "MONEYLINE", or "TOTAL".

**Root Cause:** The `pick_type` parameter passed to `calculate_pick_score()` varies by market:
- Spread bets: `pick_type = "SPREAD"`
- Moneyline bets: `pick_type = "MONEYLINE"`
- Total (O/U) bets: `pick_type = "TOTAL"`
- Props: `pick_type = "PROP"`
- Sharp signals: `pick_type = "SHARP"`

The code assumed game picks would have `pick_type = "GAME"`, which is only used as a default/fallback.

**The Bug Pattern:**
```python
# WRONG - "GAME" never matches for actual game picks
if pick_type == "GAME" and spread and total:  # ❌ Never triggers

# CORRECT - Check for all game-related pick types
_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")
if _is_game_pick and spread and total:  # ✅ Works correctly
```

**Prevention:**
- Before using `pick_type` in conditions, trace where it's set (search for `pick_type=`)
- Game picks: "SPREAD", "MONEYLINE", "TOTAL", "SHARP"
- Prop picks: "PROP"
- Test with real production data, not assumptions
- Check actual API response `pick_type` values: `jq '[.game_picks.picks[].pick_type] | unique'`

**Verification:**
```bash
# Check actual pick_type values in production
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].pick_type] | unique'
# Returns: ["moneyline", "spread", "total"] - NOT "GAME"
```

**Fixed in:** Commit `9e01390` (Feb 2026)

### Lesson 23: Dormant Signal Activation Pattern (v17.5)
**Problem:** esoteric_engine.py contained fully implemented signals (Biorhythms, Gann Square, Founder's Echo) that were never called from the scoring pipeline.

**Root Cause:** Functions were written during initial development but integration points were never added to `calculate_pick_score()` in live_data_router.py.

**Solution Pattern (Phase 1 Activation):**
1. Identify dormant functions: `grep -r "def function_name" esoteric_engine.py`
2. Verify function is NOT called: `grep -r "function_name(" live_data_router.py`
3. Find correct integration point (after GLITCH, before esoteric_score clamp)
4. Add signal with proper pick_type guard (use `_is_game_pick` pattern)
5. Add to `esoteric_reasons` for debug visibility
6. Add boost to `esoteric_raw` (NOT to esoteric_score directly)
7. Test with production curl commands

**Phase 1 Signals Activated:**
| Signal | Pick Type | Boost Range | Function |
|--------|-----------|-------------|----------|
| Biorhythms | PROP only | +0.3 (PEAK), +0.15 (RISING), -0.2 (LOW) | `calculate_biorhythms()` |
| Gann Square | GAME only | +0.25 (STRONG), +0.15 (MODERATE), +0.1 (Combined) | `analyze_spread_gann()` |
| Founder's Echo | GAME only | +0.2 (single), +0.35 (both) | `check_founders_echo()` |

**Integration Point:** `live_data_router.py:3605-3710` (after GLITCH, before esoteric_score clamp)

**Esoteric Engine Status:** Was 8/10 signals active after Phase 1 (now 10/10 after v17.6)

**Verification:**
```bash
# Check esoteric_reasons for new signals
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | unique'
# Should show: "Gann: 45° (MODERATE)", "Biorhythm: PEAK (85)", etc.
```

**Fixed in:** Commits `2bfa25e`, `9e01390` (Feb 2026)

### Lesson 24: Benford Multi-Book Aggregation Fix (v17.6)
**Problem:** Benford's Law anomaly detection NEVER triggered because it requires 10+ values for statistical significance, but only 3 values were passed (prop_line, spread, total).

**Root Cause:** Original implementation only collected the primary line values:
```python
# BAD - Only 3 values, Benford always skips
_line_values = []
if prop_line: _line_values.append(prop_line)      # 1 value
if spread: _line_values.append(abs(spread))       # 2 values
if total: _line_values.append(total)              # 3 values
# len(_line_values) < 10, so Benford NEVER runs
```

**Solution:** Extract multi-book lines from `game.bookmakers[]` array (Odds API returns 5-10 sportsbooks):
```python
# GOOD - 10-25 values from multiple books
def _extract_benford_values_from_game(game: dict, prop_line, spread, total) -> list:
    values = []
    if prop_line: values.append(prop_line)
    if spread: values.append(abs(spread))
    if total: values.append(total)

    for bm in game.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") == "spreads":
                for outcome in market.get("outcomes", []):
                    point = outcome.get("point")
                    if point is not None:
                        values.append(abs(point))
            elif market.get("key") == "totals":
                for outcome in market.get("outcomes", []):
                    point = outcome.get("point")
                    if point is not None and point > 0:
                        values.append(point)
    return list(dict.fromkeys(values))  # Deduplicate
```

**Key Insight:** The Odds API data was already available but not being utilized. Multi-book data provides 10-25 unique line values across sportsbooks.

**Integration Pattern:**
1. Add `game_bookmakers=None` parameter to `calculate_pick_score()` function signature
2. Pass `game_bookmakers=candidate.get("bookmakers", [])` from all 3 call sites
3. Use helper to extract values: `_extract_benford_values_from_game({"bookmakers": game_bookmakers}, ...)`
4. Pass to GLITCH: `value_for_benford=_line_values if len(_line_values) >= 10 else None`

**Files Modified:**
- `live_data_router.py:3150-3165` - Added `_extract_benford_values_from_game()` helper
- `live_data_router.py:3210` - Updated function signature with `game_bookmakers` param
- `live_data_router.py:3590-3610` - Updated Benford value collection
- `live_data_router.py:5149, 5290, 5472` - Updated all 3 call sites

**Verification:**
```bash
# Check Benford now receives 10+ values
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.game_picks.picks[0].glitch_breakdown.benford | {values_count, triggered, distribution}'
# values_count should be 10-25
```

**Fixed in:** v17.6 (Feb 2026)

### Lesson 25: Function Parameter Threading Pattern (v17.6)
**Problem:** When adding new data to a scoring function called from multiple locations, ALL call sites must be updated or the data will be `None`.

**Root Cause:** `calculate_pick_score()` is called from 3 different places:
1. Game picks loop (~line 5149)
2. Props loop (~line 5290)
3. Sharp money loop (~line 5472)

Adding `game_bookmakers=None` to the function signature without updating all call sites means 2 out of 3 calls would pass `None`.

**Solution Pattern:**
1. **Grep for all call sites FIRST:** `grep -n "calculate_pick_score(" live_data_router.py`
2. **Count call sites:** Expect 3+ (definition + calls)
3. **Update ALL call sites** with the new parameter
4. **Verify no calls are missing:** Re-run grep after changes

**Example Fix:**
```python
# Call site 1 (game picks) - line 5149
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)

# Call site 2 (props) - line 5290
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)

# Call site 3 (sharp money) - line 5472
pick_score_result = calculate_pick_score(
    ...,
    game_bookmakers=candidate.get("bookmakers", [])  # NEW
)
```

**Invariant:** When adding parameters to multi-call-site functions, update ALL call sites in the same commit.

**Verification:**
```bash
# Verify all call sites pass the parameter
grep -n "calculate_pick_score(" live_data_router.py | wc -l
# Should be 4 (1 definition + 3 calls)

grep -n "game_bookmakers=" live_data_router.py | wc -l
# Should be 4 (matching all call sites)
```

**Fixed in:** v17.6 (Feb 2026)

### Lesson 26: Officials Tendency Integration Pattern (v17.8)
**Problem:** Pillar 16 (Officials) had ESPN data source wired but always returned 0.0 adjustment because there was no interpretation layer - no data about what referee names MEAN for betting.

**Root Cause:** ESPN provides referee names, but without tendency data, we couldn't calculate adjustments:
```python
# ESPN provided: {"lead_official": "Scott Foster", ...}
# But OfficialsService returned: (0.0, [])
# Because there was no tendency database
```

**Solution (v17.8):**
1. Create `officials_data.py` with referee tendency database
2. Add `get_officials_adjustment()` method to `OfficialsService`
3. Wire tendency-based adjustments in `live_data_router.py`

**Key Files:**
```
officials_data.py                   # Referee tendency database
├── NBA_REFEREES (25 refs)          # Scott Foster, Tony Brothers, etc.
├── NFL_REFEREES (17 crews)         # Carl Cheffers, Brad Allen, etc.
├── NHL_REFEREES (15 refs)          # Wes McCauley, Chris Rooney, etc.
├── get_referee_tendency()          # Lookup function
└── calculate_officials_adjustment()# Adjustment calculation

context_layer.py
└── OfficialsService.get_officials_adjustment()  # Uses officials_data module

live_data_router.py (lines 4055-4106)
└── Pillar 16 section                # Wires tendency-based adjustments
```

**Adjustment Logic:**
| Condition | Boost | Example |
|-----------|-------|---------|
| Over tendency > 52% + Over pick | +0.1 to +0.3 | Scott Foster (54%) |
| Over tendency < 48% + Under pick | +0.1 to +0.3 | Marc Davis (47%) |
| Home bias > 1.5% + Home pick | +0.1 to +0.2 | Kane Fitzgerald (+2%) |
| Home bias < -1.5% + Away pick | +0.1 to +0.2 | Bill Kennedy (-2%) |

**Invariant:** External data (names, IDs) is useless without an interpretation layer that converts it to betting-relevant signals. When adding a new data source, also add the lookup/tendency database.

**Verification:**
```bash
# Check officials adjustments in picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].research_reasons] | flatten | map(select(startswith("Officials")))'

# Test officials_data module
python3 -c "
from officials_data import get_referee_tendency, calculate_officials_adjustment
print('Scott Foster:', get_referee_tendency('NBA', 'Scott Foster'))
adj, reason = calculate_officials_adjustment('NBA', 'Scott Foster', 'TOTAL', 'Over')
print(f'Adjustment: {adj:+.2f} ({reason})')
"
```

**Fixed in:** v17.8 (Feb 2026)

### Lesson 27: Trap Learning Loop Architecture (v19.0)
**Problem:** Manual weight adjustments based on observed patterns (e.g., "Dallas always covers by 20+ when favored") required human intervention and weren't systematically tracked.

**Solution Implemented (v19.0):**
1. Create `trap_learning_loop.py` - Core hypothesis-driven learning system
2. Create `trap_router.py` - RESTful API for trap CRUD operations
3. Add scheduler job at 6:15 AM ET for post-game trap evaluation
4. JSONL storage for traps, evaluations, and adjustment audit trail

**Architecture Pattern - Hypothesis-Driven Learning:**
```
PRE-GAME: User creates trap with condition + action
          "If Dallas wins by 20+, reduce public_fade by 1%"
                    ↓
POST-GAME: System evaluates condition against results
          Yesterday's games → enrich_game_result() → check conditions
                    ↓
ADJUSTMENT: If condition met AND safety checks pass
          Apply delta to target_engine.target_parameter
                    ↓
AUDIT: Log to adjustments.jsonl with full context
```

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| JSONL storage (not DB) | Matches existing grader pattern, portable, human-readable |
| 5% single / 15% cumulative caps | Prevents runaway adjustments from bad traps |
| 24h cooldown default | Allows observation before next trigger |
| Decay factor (0.7x) | Reduces impact of repeatedly-firing traps |
| Separate evaluation time (6:15 AM) | Runs after grading (6:00 AM) has results |
| Dry-run endpoint | Test traps before committing to production |

**Condition Language Design:**
- JSON-based for API compatibility
- Operator support: AND, OR
- Comparators: ==, !=, >, <, >=, <=, IN, BETWEEN
- Extensible fields: outcome, date, gematria, prior scores

**Safety Guards (Defense in Depth):**
1. **Validation on create**: Engine/parameter must exist in SUPPORTED_ENGINES
2. **Cooldown check**: Skip if triggered within cooldown_hours
3. **Weekly limit**: Skip if max_triggers_per_week exceeded
4. **Single cap**: Clamp adjustment to MAX_SINGLE_ADJUSTMENT (5%)
5. **Cumulative cap**: Clamp total adjustments to MAX_CUMULATIVE_ADJUSTMENT (15%)
6. **Parameter bounds**: New value clamped to engine's valid range
7. **Audit trail**: Every adjustment logged with before/after values

**Integration Points:**
```python
# main.py - Register router
from trap_router import trap_router
app.include_router(trap_router)

# daily_scheduler.py - Add evaluation job
self.scheduler.add_job(
    self._run_trap_evaluation,
    CronTrigger(hour=6, minute=15, timezone="America/New_York"),
    id="trap_evaluation"
)
```

**Invariant:** Learning systems must have safety bounds. Unbounded automated adjustments can destabilize scoring. Always cap single and cumulative changes, enforce cooldowns, and maintain audit trails.

**Fixed in:** v19.0 (Feb 2026)

### Lesson 28: Complete Learning System Pattern (v19.1)
**Problem:** After implementing AutoGrader (statistical) and Trap Learning Loop (hypothesis-driven), we discovered 15 gaps where learning should happen but doesn't:
- GAP 1: Research Engine signals (sharp_money, public_fade, line_variance) not tracked for learning
- GAP 2: GLITCH/Esoteric signals not tracked for learning
- GAP 3: Props vs Games treated identically (no pick_type differentiation)
- GAP 4: AutoGrader and Trap Learning Loop could conflict on same parameter
- GAP 5: No confidence decay (old picks weighted same as recent)

**Solution Implemented (v19.1):**
1. Expanded `PredictionRecord` with ALL 28 signal tracking fields
2. Updated `calculate_bias()` to analyze ALL signals with 70% confidence decay
3. Added `pick_type_breakdown` for differentiated learning (PROP vs SPREAD vs TOTAL)
4. Added Trap-AutoGrader reconciliation (24h lookback prevents conflicts)
5. Updated `live_data_router.py` to extract and persist all signal contributions

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| Track ALL 28 signals | Complete learning coverage - no blind spots |
| 70% confidence decay | Recent picks more relevant than older picks |
| pick_type differentiation | Props behave differently than game picks |
| 24h reconciliation window | Prevents conflicting adjustments |
| Dict fields for GLITCH/Esoteric | Flexible signal structure, easy to extend |

**Signal Coverage (28 total):**
| Category | Count | Signals |
|----------|-------|---------|
| Context Layer | 5 | defense, pace, vacuum, lstm, officials |
| Research Engine | 3 | sharp_money, public_fade, line_variance |
| GLITCH Protocol | 6 | chrome_resonance, void_moon, noosphere, hurst, kp_index, benford |
| Esoteric Engine | 14 | numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge, biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar |

**Reconciliation Pattern:**
```python
# In AutoGrader.adjust_weights_with_reconciliation()
for param in parameters_to_adjust:
    if has_recent_trap_adjustment(engine, param, lookback_hours=24):
        logger.info("SKIP %s.%s - trap adjusted in last 24h", engine, param)
        continue
    # Apply statistical adjustment
```

**Verification Commands:**
```bash
# Check all signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions,
  research_breakdown: .research_breakdown
}'

# Check bias calculation includes all signals
curl /live/grader/bias/NBA?days_back=1 -H "X-API-Key: KEY" | jq '.factor_bias | keys'

# Check pick_type breakdown
curl /live/grader/bias/NBA?days_back=7 -H "X-API-Key: KEY" | jq '.pick_type_breakdown'
```

**Invariant:** Every signal contribution MUST be tracked for learning. Two learning systems MUST NOT conflict. Philosophy: "Competition + variance. Learning loop baked in via fused upgrades."

**Fixed in:** v19.1 (Feb 2026)

### Lesson 29: Timezone-Aware vs Naive Datetime Comparisons (v18.2)
**Problem:** Phase 8 lunar phase calculation crashed with `TypeError: can't subtract offset-naive and offset-aware datetimes` because the reference date was created without a timezone.

**Root Cause:**
```python
# WRONG - ref_date is naive (no timezone)
ref_date = datetime(2000, 1, 6, 18, 14, 0)  # Reference new moon
days_since = (game_datetime - ref_date).days  # CRASH! Can't mix aware/naive
```

**Solution:**
```python
# CORRECT - Both datetimes are timezone-aware
from zoneinfo import ZoneInfo

ref_date = datetime(2000, 1, 6, 18, 14, 0, tzinfo=ZoneInfo("UTC"))
game_datetime = datetime.now(ZoneInfo("America/New_York"))
days_since = (game_datetime - ref_date).days  # Works!
```

**Prevention:**
- When doing datetime arithmetic, BOTH datetimes must be timezone-aware
- Use `ZoneInfo("UTC")` for reference dates
- Use `ZoneInfo("America/New_York")` for game times
- The NEVER DO rule 88 enforces this

**Fixed in:** v18.2 (Feb 2026) - `calculate_lunar_phase_intensity()` line 1422-1426

### Lesson 30: Environment Variable OR Logic (v18.2)
**Problem:** SERP API integration failed because the env var check used AND logic when it should have used OR. Both `SERPAPI_KEY` and `SERP_API_KEY` are valid alternatives, but the code required BOTH to be set.

**Root Cause:**
```python
# WRONG - Requires BOTH keys to be set
if SERPAPI_KEY and SERP_API_KEY:
    # Only runs if both exist

# Also WRONG - all() requires ALL to be truthy
if all([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    # Only runs if both exist
```

**Solution:**
```python
# CORRECT - Either key works
if any([os.getenv("SERPAPI_KEY"), os.getenv("SERP_API_KEY")]):
    key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    # Runs if at least one exists
```

**Prevention:**
- Use `any()` for ALTERNATIVE env vars (either one works)
- Use `all()` for REQUIRED env vars (all must be set)
- Document which pattern is intended
- The NEVER DO rule 96 enforces this

**Fixed in:** v18.2 (Feb 2026)

### Lesson 31: Variable Initialization Before Conditional Use (v18.2)
**Problem:** Production crashed with `NameError: name 'weather_data' is not defined` because the variable was only assigned inside a conditional block but used outside it.

**Root Cause:**
```python
# WRONG - weather_data only defined if condition is True
if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # NameError if outdoor_sport was False!
    apply_weather_boost()
```

**Solution:**
```python
# CORRECT - weather_data always defined
weather_data = None  # Initialize first

if outdoor_sport:
    weather_data = fetch_weather()

# Later in code...
if weather_data:  # Safe - weather_data is always defined
    apply_weather_boost()
```

**Prevention:**
- Any variable used after a conditional block MUST be initialized before that block
- Initialize to `None`, `[]`, `{}`, or appropriate default
- The NEVER DO rule 90 enforces this

**Fixed in:** v18.2 (Feb 2026) - `weather_data = None` initialization at line 3345

### Lesson 32: Auto Grader Weights Must Include All Stat Types (v20.2)
**Problem:** Auto grader returned "No graded predictions found" for ALL game picks (spread, total, moneyline, sharp) even though 242 graded picks existed.

**Root Cause:** The `_initialize_weights()` method only created `WeightConfig` entries for PROP stat types (points, rebounds, assists, etc.) but NOT for GAME stat types (spread, total, moneyline, sharp).

```python
# BUG - Only PROP stat types initialized
stat_types = {
    "NBA": ["points", "rebounds", "assists", "threes", ...],  # PROP only
    ...
}
for stat in stat_types.get(sport, ["points"]):
    self.weights[sport][stat] = WeightConfig()
# Missing: spread, total, moneyline, sharp
```

**The Bug Flow:**
1. `run_daily_audit()` called `adjust_weights(sport, "spread")`
2. `adjust_weights()` checked if "spread" was in `weights[sport]` → **NO**
3. Line 802-803 defaulted to `stat_type = "points"` as fallback
4. `calculate_bias()` filtered for records where `record.stat_type == "points"`
5. Game picks have `stat_type` like "spread", "total" → **NO MATCH**
6. → "No graded predictions found" for ALL game picks

**Solution (v20.2):**
```python
# FIXED - Both PROP and GAME stat types initialized
prop_stat_types = {
    "NBA": ["points", "rebounds", "assists", ...],
    ...
}
game_stat_types = ["spread", "total", "moneyline", "sharp"]

for sport in self.SUPPORTED_SPORTS:
    self.weights[sport] = {}
    # Initialize PROP stat types
    for stat in prop_stat_types.get(sport, ["points"]):
        self.weights[sport][stat] = WeightConfig()
    # Initialize GAME stat types
    for stat in game_stat_types:
        self.weights[sport][stat] = WeightConfig()
```

**Prevention:**
- When adding new pick types (market types), ensure weights are initialized for them
- The `stat_type` field in `PredictionRecord` comes from `pick_type.lower()` for game picks
- Verify with: `curl /live/grader/bias/NBA?stat_type=spread` - should return sample_size > 0
- The NEVER DO rules 108-111 enforce this

**Verification Commands:**
```bash
# Check all game stat types have weights
for stat in spread total moneyline sharp; do
  echo "=== $stat ==="
  curl -s "/live/grader/bias/NBA?stat_type=$stat&days_back=1" -H "X-API-Key: KEY" | \
    jq '{stat_type: .stat_type, sample_size: .bias.sample_size, hit_rate: .bias.overall.hit_rate}'
done
# All should show sample_size > 0 (if graded picks exist)
```

**Fixed in:** v20.2 (Feb 2026) - Commit `ac25a59`

### Lesson 33: OVER Bet Performance Tracking (v20.2 Analysis)
**Problem:** Feb 3, 2026 analysis revealed severe OVER bias - 19.1% win rate on OVER bets vs 81.6% on UNDER bets.

**Performance Data (Feb 3, 2026):**
| Market | Record | Win Rate | Assessment |
|--------|--------|----------|------------|
| SPREAD | 96-21-40 | 82.1% | Excellent |
| UNDER | 31-7 | 81.6% | Excellent |
| OVER | 9-38 | 19.1% | **Critical Problem** |

**Root Cause:** The system was overvaluing OVER bets. 38 of 66 total losses (57.6%) came from OVER picks.

**Learning Loop Impact:**
- With v20.2 fix, the auto grader can now properly analyze this data
- `calculate_bias()` for "total" stat_type will detect the OVER bias
- Weights will be adjusted to reduce OVER confidence
- The esoteric/context signals that pushed OVER need recalibration

**Prevention:**
- Monitor OVER/UNDER split in daily grading reports
- Auto grader bias analysis now properly includes totals picks
- Consider market-type-specific confidence adjustments

**Action:** The v20.2 fix enables the learning loop to automatically adjust based on this performance data.

### Lesson 34: Verifying the Learning Loop is Working (v20.3)
**Problem:** After fixing the auto grader weights (v20.2), needed to verify the entire learning loop was functioning end-to-end.

**Verification Steps Performed (Feb 4, 2026):**
1. **Grader Status Check**: `available: true` ✅
2. **Grading Summary**: 242 graded picks, 136 wins, 66 losses (67.3% hit rate) ✅
3. **Bias Calculation for Game Types**: Working for all stat types ✅
4. **Weight Adjustments Applied**: `applied: true` with actual deltas ✅

**Key Verification Results:**

| Component | Endpoint | Expected | Actual |
|-----------|----------|----------|--------|
| Grader Status | `/live/grader/status` | `available: true` | ✅ Working |
| Weights Initialized | `/live/grader/weights/NBA` | All 11 stat types | ✅ spread, total, moneyline, sharp + props |
| Spread Bias | `/live/grader/bias/NBA?stat_type=spread` | sample_size > 0 | ✅ 53 samples, 84.9% hit rate |
| Total Bias | `/live/grader/bias/NBA?stat_type=total` | sample_size > 0 | ✅ 32 samples, 56.2% hit rate |
| Weight Adjustments | Run audit | `applied: true` | ✅ pace, vacuum, officials adjusted |
| Factor Correlations | Bias response | Non-null values | ✅ 28 signals tracked |

**What "Learning Loop Working" Means:**
1. Picks are being persisted to `/data/grader/predictions.jsonl`
2. Grading summary shows wins/losses/pushes
3. `calculate_bias()` returns sample_size > 0 for active stat types
4. `factor_bias` shows correlations for all tracked signals (pace, vacuum, officials, glitch, esoteric)
5. `weight_adjustments` shows `applied: true` with actual delta values
6. Confidence decay (70% per day) is being applied

**Factor Bias Signals Tracked (28 total):**
```python
factor_bias = {
    "pace": {"correlation": 0.088, "suggested_adjustment": -0.0088},
    "vacuum": {"correlation": 0.032, "suggested_adjustment": -0.0032},
    "officials": {"correlation": 0.313, "suggested_adjustment": -0.0313},
    "glitch": {
        "void_moon": {"correlation": 0.155},
        "kp_index": {"correlation": 0.0}
    },
    "esoteric": {
        "numerology": {"correlation": 0.114},
        "astro": {"correlation": 0.003},
        "fib_alignment": {"correlation": 0.146},
        "vortex": {"correlation": 0.058},
        "daily_edge": {"correlation": -0.313}
    }
}
```

**Prevention:**
- Run the full learning loop verification after any auto_grader.py changes
- Check both bias AND weight_adjustments sections of audit response
- Verify `applied: true` not just sample_size > 0
- Monitor factor correlations for outliers (e.g., officials at 0.313)

**Verification Command (Full Check):**
```bash
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{
    stat_type,
    sample_size: .bias.sample_size,
    hit_rate: .bias.overall.hit_rate,
    weight_adjustments_applied: (.weight_adjustments != null),
    factors_tracked: (.bias.factor_bias | keys)
  }'
```

### Lesson 35: Grading Pipeline Missing SHARP/MONEYLINE/PROP Handling (v20.3)
**Problem:** Investigation revealed:
- **SHARP**: 18 picks, 0% hit rate (all graded as PUSH)
- **MONEYLINE**: 1 sample in 7 days
- **PROPS**: 0 samples in learning loop

**Root Causes Found:**

1. **SHARP picks graded as PUSH** (`result_fetcher.py:842-884`)
   - `grade_game_pick()` checked for "total", "spread", "moneyline" in pick_type
   - SHARP picks have `pick_type="SHARP"` which matched NONE of these
   - Fell through to `return "PUSH", 0.0` - never WIN or LOSS

2. **`picked_team` not passed** (`result_fetcher.py:1067-1075`)
   - Call to `grade_game_pick()` didn't include `picked_team` parameter
   - For spreads/moneylines, couldn't determine which team was picked

3. **`run_daily_audit()` prop_stat_types incomplete** (`auto_grader.py:1071-1077`)
   - Only audited: points, rebounds, assists
   - Missing: threes, steals, blocks, pra (4 prop types not analyzed)

4. **Prop stat lookup failures** (`result_fetcher.py:770-798`)
   - STAT_TYPE_MAP didn't include direct formats like "threes"
   - Market keys like "player_points_over_under" not cleaned

**Fixes Applied (v20.3):**

| Bug | Fix | File:Lines |
|-----|-----|------------|
| SHARP grading | Added `elif "sharp" in pick_type_lower` handling | `result_fetcher.py:893-916` |
| picked_team | Extract from selection/picked_team/team/side fields | `result_fetcher.py:1066-1074` |
| prop_stat_types | Synced with `_initialize_weights()` (7 NBA, 5 NFL, etc.) | `auto_grader.py:1071-1077` |
| STAT_TYPE_MAP | Added direct formats + market suffix stripping | `result_fetcher.py:80-125` |

**Verification Commands:**
```bash
# After next grading cycle, verify SHARP picks have WIN/LOSS (not all PUSH)
curl -s "/live/picks/grading-summary?date=$(date +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '[.graded_picks[] | select(.pick_type == "SHARP")] | group_by(.result) | map({result: .[0].result, count: length})'

# Verify prop stat types being audited
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '.results.results.NBA | keys'
# Should include: points, rebounds, assists, threes, steals, blocks, pra, spread, total, moneyline, sharp
```

**Fixed in:** v20.3 (Feb 4, 2026)

### Lesson 36: Audit Drift Scan Line Number Filters (v20.4)
**Problem:** Go/no-go check failed with `audit_drift` error because the line number filter in `audit_drift_scan.sh` didn't match actual code locations.

**Root Cause:** The ensemble adjustment fallback code shifted from lines 4753-4757 to lines 4757-4763. The filter pattern `live_data_router.py:475[67]` allowed line 4757 but NOT line 4761 (the penalty code).

**The Failure:**
```
Found additive final_score +/-0.5 outside allowed ensemble adjustment:
live_data_router.py:4761:                            final_score = max(0.0, final_score - 0.5)
ERROR: Unexpected literal +/-0.5 applied to final_score
```

**The Fix:**
```bash
# OLD filter (incomplete)
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" || true

# NEW filter (includes lines 4760-4762)
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" | \
rg -v "live_data_router.py:476[012]" || true
```

**Prevention:**
- When code shifts (refactoring, additions), line-based filters in sanity scripts break
- After ANY change to `live_data_router.py`, re-run `audit_drift_scan.sh` locally
- Use broader patterns when possible, or document exact line purposes
- The filter comment now explains: "Lines 4757 (boost) and 4761 (penalty) are the fallback ensemble adjustments"

**Verification:**
```bash
# Check current ensemble adjustment line numbers
grep -n "final_score.*0\.5" live_data_router.py | grep -E "(min|max)"
# Should show lines ~4757 and ~4761

# Run audit_drift scan
bash scripts/audit_drift_scan.sh
# Should pass

# Full go/no-go
API_KEY="KEY" SKIP_NETWORK=0 SKIP_PYTEST=1 bash scripts/prod_go_nogo.sh
```

**Files Modified:**
- `scripts/audit_drift_scan.sh:43-48` - Updated filter pattern with comment

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 37: Endpoint Matrix Sanity Math Formula (v20.4)
**Problem:** `endpoint_matrix_sanity.sh` final_score math check failed because the formula was missing `ensemble_adjustment`.

**Root Cause:** The production API was returning `ensemble_adjustment: null` instead of `0.0` or an actual value, causing:
- Computed sum: 9.443
- Actual final_score: 9.94
- Difference: 0.497 (exceeds 0.02 tolerance)

**The Formula (must match scoring pipeline):**
```jq
($p.base_4_score + $p.context_modifier + $p.confluence_boost + $p.msrf_boost +
 $p.jason_sim_boost + $p.serp_boost + ($p.ensemble_adjustment // 0) +
 ($p.live_adjustment // 0) + ($p.totals_calibration_adj // 0)) as $raw |
($raw | if . > 10 then 10 else . end) as $capped |
($p.final_score - $capped) | abs
```

**Key Points:**
- `ensemble_adjustment` is exposed at `live_data_router.py:4939,4952`
- Default is `0.0` (line 4720), but can be `±0.5` based on ensemble model
- `totals_calibration_adj` is ±0.75 from `TOTALS_SIDE_CALIBRATION` (v20.4) - surfaced in v20.5
- `glitch_adjustment` is NOT added separately (already folded into `esoteric_score`)
- The `// 0` jq syntax handles null values
- **EVERY adjustment to final_score MUST be surfaced as a field** (Lesson 46)

**Prevention:**
- When adding new boosts/adjustments to scoring, update ALL THREE:
  1. `live_data_router.py` pick payload (surface as a named field)
  2. `scripts/endpoint_matrix_sanity.sh` math formula (add to jq sum)
  3. `CLAUDE.md` Boost Inventory + canonical formula
- Document formula in CLAUDE.md INVARIANT 4 (already done)

**Verification:**
```bash
# Check a pick's math manually
curl -s "/live/best-bets/NBA?debug=1&max_games=1" -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {
    base_4: .base_4_score,
    context: .context_modifier,
    confluence: .confluence_boost,
    msrf: .msrf_boost,
    jason_sim: .jason_sim_boost,
    serp: .serp_boost,
    ensemble: .ensemble_adjustment,
    live: .live_adjustment,
    totals_cal: .totals_calibration_adj,
    computed: (.base_4_score + .context_modifier + .confluence_boost +
               .msrf_boost + .jason_sim_boost + .serp_boost +
               (.ensemble_adjustment // 0) + (.live_adjustment // 0) +
               (.totals_calibration_adj // 0)),
    actual: .final_score,
    diff: ((.base_4_score + .context_modifier + .confluence_boost +
            .msrf_boost + .jason_sim_boost + .serp_boost +
            (.ensemble_adjustment // 0) + (.live_adjustment // 0) +
            (.totals_calibration_adj // 0)) - .final_score) | fabs
  }'
# diff should be < 0.02
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 38: OVER/UNDER Totals Bias Calibration (v20.4)
**Problem:** Learning loop revealed massive OVER vs UNDER imbalance:
- **OVER**: 9W / 38L = 19.1% hit rate (terrible)
- **UNDER**: 31W / 7L = 81.6% hit rate (excellent)

The contradiction gate was keeping whichever side scored higher. OVER picks consistently scored higher but lost more often.

**Root Cause:** No mechanism to apply learned bias corrections to totals scoring. Both Over and Under were scored identically with no calibration based on historical performance.

**The Fix (v20.4):**

1. Added `TOTALS_SIDE_CALIBRATION` to `core/scoring_contract.py`:
```python
TOTALS_SIDE_CALIBRATION = {
    "enabled": True,
    "over_penalty": -0.75,   # Penalty applied to OVER picks
    "under_boost": 0.75,     # Boost applied to UNDER picks
    "min_samples_required": 50,
    "last_updated": "2026-02-04",
}
```

2. Applied calibration in `live_data_router.py:4577-4592`:
   - When `pick_type == "TOTAL"`, check side
   - Apply over_penalty (-0.75) to Over picks
   - Apply under_boost (+0.75) to Under picks
   - Log adjustment for tracking

**Expected Outcome:**
- UNDER picks gain +0.75, more likely to win contradiction gate
- OVER picks penalized -0.75, less likely to be selected
- Learning loop should show improved total hit rates

**Verification:**
```bash
# Check OVER/UNDER split after next grading cycle
curl -s "/live/picks/grading-summary?date=$(date +%Y-%m-%d)" -H "X-API-Key: KEY" | jq '{
  over: {wins: [.graded_picks[] | select(.side == "Over" and .result == "WIN")] | length,
         losses: [.graded_picks[] | select(.side == "Over" and .result == "LOSS")] | length},
  under: {wins: [.graded_picks[] | select(.side == "Under" and .result == "WIN")] | length,
          losses: [.graded_picks[] | select(.side == "Under" and .result == "LOSS")] | length}
}'
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 39: Frontend Tooltip Alignment with Option A Weights (v20.4)

**Problem:** Frontend tooltips in `PropsSmashList.jsx` and `GameSmashList.jsx` showed incorrect engine weights that didn't match the backend `scoring_contract.py`:

| Engine | Frontend (Wrong) | Backend (Correct) |
|--------|------------------|-------------------|
| AI | 15% | **25%** |
| Research | 20% | **35%** |
| Esoteric | 15% | **20%** |
| Jarvis | 10% | **20%** |
| Context | 30% weighted | **±0.35 modifier** |

**Root Cause:** Frontend documentation and tooltips were written for an outdated scoring architecture. When Option A (4-engine base + context modifier) was implemented, the frontend wasn't updated to reflect that:
1. Context is NOT a weighted engine - it's a bounded modifier (±0.35 cap)
2. The 4 engine weights sum to 100% (25+35+20+20)
3. Context modifier is applied AFTER the weighted base score

**The Fix (v20.4):**

1. Updated `bookie-member-app/PropsSmashList.jsx` tooltips:
```jsx
// Option A: 4 weighted engines + context modifier
<ScoreBadge label="AI" tooltip="8 AI models (25% weight)" />
<ScoreBadge label="Research" tooltip="Sharp money, line variance (35% weight)" />
<ScoreBadge label="Esoteric" tooltip="Numerology, astro, fibonacci (20% weight)" />
<ScoreBadge label="Jarvis" tooltip="Gematria triggers (20% weight)" />
<ScoreBadge label="Context" tooltip="Defense rank, pace, vacuum (modifier ±0.35)" />
```

2. Updated `bookie-member-app/GameSmashList.jsx` with same corrections

3. Updated `bookie-member-app/CLAUDE.md` documentation in 3 sections

4. Updated `ai-betting-backend/docs/FRONTEND_INTEGRATION.md`:
   - Marked Priority 1-3 as COMPLETE
   - Fixed weight comments in API response structure

**Prevention:**
- ALWAYS check `core/scoring_contract.py` for authoritative weights
- When changing backend scoring, IMMEDIATELY update frontend tooltips
- Add drift scan for frontend/backend weight synchronization

**Files Modified:**
- `bookie-member-app/PropsSmashList.jsx`
- `bookie-member-app/GameSmashList.jsx`
- `bookie-member-app/CLAUDE.md`
- `ai-betting-backend/docs/FRONTEND_INTEGRATION.md`

**Verification:**
```bash
# Check frontend tooltips match backend weights
grep -n "25% weight\|35% weight\|20% weight\|modifier.*0.35" \
  /Users/apple/bookie-member-app/PropsSmashList.jsx \
  /Users/apple/bookie-member-app/GameSmashList.jsx

# Check backend scoring_contract.py for truth
grep -A5 "ENGINE_WEIGHTS" core/scoring_contract.py
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 40: Shell Variable Export for Python Subprocesses (v20.4)
**Problem:** `perf_audit_best_bets.sh` was trying to connect to `None` as a hostname:
```
curl: (6) Could not resolve host: None
```

**Root Cause:** Shell variables are NOT automatically inherited by Python subprocesses. The script set `BASE_URL` as a shell variable, but Python's `os.environ.get("BASE_URL")` returned `None`:

```bash
# BUG - Python subprocess doesn't see this variable
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"

# Inside Python heredoc:
base_url = os.environ.get("BASE_URL")  # Returns None!
```

**The Fix:**
```bash
# CORRECT - 'export' makes variable available to subprocesses
export BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
export API_KEY="${API_KEY:-}"
```

**Prevention:**
- When shell scripts call Python (via heredoc, subprocess, or exec), variables MUST be exported
- Use `export VAR=value` not just `VAR=value`
- Test scripts by checking what Python actually sees: `python3 -c "import os; print(os.environ.get('VAR'))"`

**Shell Variable Scope Rules:**
| Pattern | Scope | Python sees it? |
|---------|-------|-----------------|
| `VAR=value` | Current shell only | ❌ No |
| `export VAR=value` | Current shell + children | ✅ Yes |
| `VAR=value command` | Command only | ✅ Yes (for that command) |

**Files Modified:**
- `scripts/perf_audit_best_bets.sh` - Added `export` to BASE_URL and API_KEY

**Verification:**
```bash
# Test that Python inherits the variable
export TEST_VAR="hello"
python3 -c "import os; print(os.environ.get('TEST_VAR'))"
# Should print: hello
```

**Fixed in:** v20.4 (Feb 4, 2026)

### Lesson 41: SHARP Pick Grading - line_variance vs Actual Spread (v20.5)
**Problem:** SHARP picks showing 0% hit rate across all sports (NBA 0/14, NHL 0/8, NCAAB 0/7).

**Root Cause:** SHARP picks were being graded incorrectly because the `line` field contained `line_variance` (the movement amount) instead of the actual spread:

```python
# In live_data_router.py - SHARP pick creation
"line": signal.get("line_variance", 0),  # BUG: This is 0.5, 1.5, etc.

# In result_fetcher.py - Grading logic treated it as spread
if line and line != 0:
    adjusted = home_score + line  # WRONG: using line_variance as spread
```

**Example of the bug:**
- Sharp signal: "sharps on Lakers" for Lakers (-5.5) vs Celtics
- `line_variance` = 1.5 (line moved 1.5 points)
- Pick logged with `"line": 1.5`
- Grading treated as "Lakers +1.5 spread"
- Lakers win by 4 → graded as WIN (should be LOSS, didn't cover -5.5)

**The Fix:** Grade SHARP picks as moneyline only (who won), ignoring the `line` field:

```python
# v20.5 fix in result_fetcher.py
elif "sharp" in pick_type_lower:
    # ALWAYS grade as moneyline - line field is line_variance, not actual spread
    if home_score == away_score:
        return "PUSH", 0.0
    if picked_home:
        return ("WIN" if home_score > away_score else "LOSS"), 0.0
    else:
        return ("WIN" if away_score > home_score else "LOSS"), 0.0
```

**Why moneyline is correct:**
- Sharp signals indicate "sharps are betting HOME/AWAY"
- Without the actual spread line, we can only grade on straight-up winner
- This is semantically accurate: "sharp side won" = their team won

**Prevention:**
- Never assume a field contains what its name suggests - trace data flow
- `line_variance` ≠ `line` (spread)
- Always verify grading logic with actual data examples

**Files Modified:**
- `result_fetcher.py` - Fixed `grade_game_pick()` SHARP case (lines 930-943)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 42: Undefined PYTZ_AVAILABLE Variable (v20.5)
**Problem:** `/grader/queue` endpoint returning `{"detail":"name 'PYTZ_AVAILABLE' is not defined"}`

**Root Cause:** Code referenced `PYTZ_AVAILABLE` variable that was never defined:
```python
if PYTZ_AVAILABLE:  # NameError - never defined!
    ET_TZ = pytz.timezone("America/New_York")
```

**The Fix:** Use `core.time_et.now_et()` - the single source of truth for ET timezone:
```python
from core.time_et import now_et
date = now_et().strftime("%Y-%m-%d")
```

**Prevention:**
- NEVER use `pytz` in new code - use `core.time_et` or `zoneinfo`
- NEVER reference variables without importing/defining them
- All ET timezone logic MUST go through `core.time_et`

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 43: Naive vs Aware Datetime Comparison (v20.5)
**Problem:** `/grader/daily-report` returning `{"detail":"can't compare offset-naive and offset-aware datetimes"}`

**Root Cause:** Comparing `datetime.now()` (naive) with stored timestamps that may be timezone-aware:
```python
cutoff = datetime.now() - timedelta(days=1)  # Naive
ts = datetime.fromisoformat(p.timestamp)      # May be aware
if ts >= cutoff:  # TypeError!
```

**The Fix:** Use timezone-aware datetime and handle both naive/aware timestamps:
```python
from core.time_et import now_et
from zoneinfo import ZoneInfo
et_tz = ZoneInfo("America/New_York")

cutoff = now_et() - timedelta(days=1)  # Aware

ts = datetime.fromisoformat(p.timestamp)
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=et_tz)  # Make aware if naive
if ts >= cutoff:  # Safe comparison
```

**Prevention:**
- NEVER use `datetime.now()` in grader code - use `now_et()`
- ALWAYS handle both naive and aware timestamps when parsing stored data
- Test with both timezone-aware and naive timestamp data

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 44: Date Window Math Error (v20.5)
**Problem:** Daily report showing ~290 picks for "yesterday" when actual count was ~150

**Root Cause:** Wrong date window calculation created 2-day window instead of 1:
```python
# For days_back=1 (yesterday), this creates a 2-day window:
cutoff = now - timedelta(days=days_back + 1)      # 2 days ago (WRONG)
end_cutoff = now - timedelta(days=days_back - 1)  # today
```

**The Fix:** Use exact day boundaries:
```python
# Correct: exactly one day
day_start = (now - timedelta(days=days_back)).replace(
    hour=0, minute=0, second=0, microsecond=0
)
day_end = day_start + timedelta(days=1)

if day_start <= ts < day_end:  # Exclusive end bound
```

**Prevention:**
- NEVER use `days_back + 1` / `days_back - 1` math for date windows
- ALWAYS use `.replace(hour=0, ...)` for day boundaries
- Use exclusive end bounds (`<` not `<=`) to avoid overlap
- Test date window logic with specific date examples

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 45: Grader Performance Endpoint Same Bug (v20.5)
**Problem:** `/grader/performance/{sport}` returning `Internal Server Error`

**Root Cause:** Same naive vs aware datetime bug as Lesson 43 - copy-paste pattern:
```python
cutoff = datetime.now() - timedelta(days=days_back)
datetime.fromisoformat(p.timestamp) >= cutoff  # Same error
```

**The Fix:** Apply same fix as Lesson 43 - use `now_et()` and handle mixed timestamps.

**Prevention:**
- When fixing a bug, grep the entire codebase for the same pattern
- `/grader/daily-report` and `/grader/performance` had identical bugs
- Run `grep -n "datetime.now()" *.py | grep fromisoformat` after datetime fixes

**Files Modified (v20.5 datetime fixes):**
- `live_data_router.py` lines 8933-8944 (performance endpoint)
- `live_data_router.py` lines 9016-9058 (daily-report endpoint)
- `live_data_router.py` lines 9210-9215 (queue endpoint)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 46: Unsurfaced Scoring Adjustments Break Sanity Math (v20.5)
**Problem:** `endpoint_matrix_sanity.sh` math check showed diff=0.748 because `totals_calibration_adj` (±0.75) was applied to `final_score` but NOT surfaced as a field in the pick payload.

**Root Cause:** `TOTALS_SIDE_CALIBRATION` (v20.4) adjusted `final_score` directly via a local variable `totals_calibration_adj`, but this value was never included in the pick output dict. The sanity script recomputes `final_score` from surfaced fields, so the hidden adjustment caused a mismatch.

**The Fix:**
1. Added `"totals_calibration_adj": round(totals_calibration_adj, 3)` to pick output dict in `live_data_router.py`
2. Updated jq formula in `endpoint_matrix_sanity.sh` to include `+ ($p.totals_calibration_adj // 0)`

**Prevention:**
- **INVARIANT:** Every adjustment to `final_score` MUST be surfaced as its own field in the pick payload
- When adding a new scoring adjustment: (1) add to pick dict, (2) add to sanity formula, (3) add to CLAUDE.md Boost Inventory, (4) add to canonical formula
- The endpoint matrix math check exists precisely to catch this class of bug

**Files Modified:**
- `live_data_router.py` (pick output dict)
- `scripts/endpoint_matrix_sanity.sh` (jq formula)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 47: Script-Only Env Vars Must Be in RUNTIME_ENV_VARS (v20.5)
**Problem:** `env_drift_scan.sh` failed because `MAX_GAMES`, `MAX_PROPS`, and `RUNS` were used in scripts but not registered in `RUNTIME_ENV_VARS` in `integration_registry.py`.

**Root Cause:** The env drift scan greps all `.sh` and `.py` files for `os.environ` / `${}` references, then checks them against the `RUNTIME_ENV_VARS` list. Script-only variables were not registered because they seemed "not important enough."

**The Fix:** Added `MAX_GAMES`, `MAX_PROPS`, and `RUNS` to `RUNTIME_ENV_VARS` in `integration_registry.py` in alphabetical position.

**Prevention:**
- ANY env var referenced in ANY script or Python file must be in either `INTEGRATION_CONTRACTS` or `RUNTIME_ENV_VARS`
- Run `bash scripts/env_drift_scan.sh` after adding new env vars to scripts
- The scan is intentionally aggressive - false positives are better than missed drift

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 48: Python Heredoc `__file__` Path Resolution Bug (v20.5)
**Problem:** `prod_endpoint_matrix.sh` failed with `FileNotFoundError: [Errno 2] No such file or directory: '../docs/ENDPOINT_MATRIX_REPORT.md'`

**Root Cause:** The script uses `python3 - <<'PY'` (Python heredoc). Inside a heredoc, `__file__` resolves to `"<stdin>"`, so `os.path.dirname(__file__)` returns an empty string. The path `os.path.join("", "..", "docs", "ENDPOINT_MATRIX_REPORT.md")` resolved to `../docs/ENDPOINT_MATRIX_REPORT.md` which doesn't exist.

**The Fix:** Changed to project-relative path: `os.path.join("docs", "ENDPOINT_MATRIX_REPORT.md")` - works because the shell script runs from the project root.

**Prevention:**
- NEVER use `__file__`, `__dir__`, or `os.path.dirname(__file__)` inside Python heredocs
- In heredocs, use project-relative paths (scripts always run from project root)
- Test heredoc scripts directly: `bash scripts/script_name.sh`

**Files Modified:**
- `scripts/prod_endpoint_matrix.sh` (line 86)

**Fixed in:** v20.5 (Feb 4, 2026)

### Lesson 49: Props Timeout — Shared Time Budget Starvation (v20.6)
**Problem:** `/live/best-bets/NBA` returned 0 props despite game picks working. Props section showed `"picks": []`.

**Root Cause:** `TIME_BUDGET_S = 40.0` was hardcoded in `live_data_router.py:2741`. Game scoring consumed the full budget, leaving 0 seconds for props scoring. The timeout wasn't configurable.

**The Fix:**
1. Changed `TIME_BUDGET_S` from hardcoded `40.0` to `float(os.getenv("BEST_BETS_TIME_BUDGET_S", "55"))` — configurable with higher default
2. Registered `BEST_BETS_TIME_BUDGET_S` in `integration_registry.py` `RUNTIME_ENV_VARS`

**Prevention:**
- Any shared time budget must leave enough headroom for ALL consumers (games + props)
- All timeout/budget values should be env-configurable, not hardcoded
- Always register new env vars in `integration_registry.py` (see Lesson 47)

**Files Modified:**
- `live_data_router.py` (line 2741)
- `integration_registry.py` (RUNTIME_ENV_VARS)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 50: Empty Description Fields in Pick Payload (v20.6)
**Problem:** All picks returned `"description": ""` in the best-bets response. Frontend had no human-readable summary of each pick.

**Root Cause:** `compute_description()` existed in `models/pick_converter.py` but it used object attribute access (`.player_name`, `.matchup`) — only works for database model objects. The live scoring path uses plain dicts through `normalize_pick()`, so `compute_description()` was never called.

**The Fix:** Added dict-based description generation directly in `utils/pick_normalizer.py` `normalize_pick()`, covering:
- Player props: `"LeBron James Points Over 25.5"`
- Moneyline: `"LAL @ BOS — Lakers ML +150"`
- Spreads/totals: `"LAL @ BOS — Spread Away -3.5"`
- Fallback: matchup string

**Prevention:**
- When adding a new field to the pick contract, verify it's populated in ALL paths (normalize_pick is the single source)
- `normalize_pick()` is the ONLY place to set pick fields — never set them in individual scoring functions

**Files Modified:**
- `utils/pick_normalizer.py` (added ~15 lines in normalize_pick)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 51: Score Inflation from Unbounded Boost Stacking (v20.6)
**Problem:** Multiple picks had `final_score = 10.0` despite mediocre base scores (~6.5). Picks clustered at the max, eliminating score differentiation.

**Root Cause:** Individual boost caps existed (confluence 10.0, msrf 1.0, jason_sim 1.5, serp 4.3) but NO cap on their SUM. Theoretical max boost was 16.8 points. In practice, confluence 3.0 + msrf 1.0 + serp 2.0 + jason 0.5 = 6.5 boosts on a 6.5 base = 13.0 → clamped to 10.0.

**The Fix:**
1. Added `TOTAL_BOOST_CAP = 3.5` in `core/scoring_contract.py`
2. In `compute_final_score_option_a()`: sum of confluence+msrf+jason_sim+serp capped to `TOTAL_BOOST_CAP` before adding to base_score
3. Context modifier is excluded from the cap (it's a bounded modifier, not a boost)
4. Updated `test_option_a_scoring_guard.py` to test new cap behavior

**Prevention:**
- Every additive boost system needs BOTH individual caps AND a total cap
- Monitor production score distributions — clustering at boundaries is a red flag
- Added Invariant 26 to prevent regression

**Files Modified:**
- `core/scoring_contract.py` (TOTAL_BOOST_CAP constant)
- `core/scoring_pipeline.py` (cap enforcement in compute_final_score_option_a)
- `tests/test_option_a_scoring_guard.py` (updated tests for new cap)

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 52: Jarvis Baseline Is Not a Bug — Sacred Triggers Are Rare By Design (v20.6)
**Problem:** Report claimed `jarvis_score = 5.0` hardcoded at `core/scoring_pipeline.py:280` made Jarvis "dead code."

**Investigation Found:** The hardcoded 5.0 is in `score_candidate()` which is dormant demo code — NOT the production path. Production Jarvis scoring is in `live_data_router.py:calculate_jarvis_engine_score()` (lines 2819-3037), fully wired with real triggers.

**Why Jarvis Stays at 4.5 Baseline:**
- Sacred number triggers (2178, 201, 33, 93, 322, 666, 888, 369) fire on gematria sums of player+team names
- Simple gematria (a=1..z=26) produces sums typically in the 100-400 range
- Sacred numbers are statistically rare — most matchups don't trigger ANY
- This is intentional: Jarvis should ONLY boost when genuine sacred number alignment exists
- GOLD_STAR gate requires `jarvis_rs >= 6.5` — needs at minimum a +2.0 trigger (33, 93, or 322)

**Prevention:**
- Before reporting "dead code," trace the actual production call path (imports, function calls)
- `core/scoring_pipeline.py:score_candidate()` is NOT used in production — only `compute_final_score_option_a()` and `compute_harmonic_boost()` are imported
- A low/constant score from an engine is not necessarily a bug — check if triggers are designed to be rare

**Production Jarvis flow:**
```
get_jarvis_savant() → JarvisSavantEngine singleton
  → calculate_jarvis_engine_score()
    ├── check_jarvis_trigger() for sacred numbers
    ├── calculate_gematria_signal() for name sums
    └── mid-spread goldilocks for spreads 4.0-9.0
  → jarvis_rs = 4.5 + triggers + gematria + goldilocks
```

**Fixed in:** v20.6 (Feb 4, 2026)

### Lesson 53: SERP Sequential Bottleneck — Parallel Pre-Fetch Pattern (v20.7)
**Problem:** Props scoring returned 0 picks despite v20.6 timeout fix. Deep dive revealed 107 sequential SerpAPI calls at ~157ms each = ~17s, consuming half the game scoring budget and leaving no time for props.

**Root Cause:** `get_serp_betting_intelligence()` makes 9 API calls per game pick (silent_spike×1, sharp_chatter×2, narrative×2, situational×2, noosphere×2). For 8 games with both home and away targets, that's ~14 unique queries per game × 8 games = ~107 calls. Each call goes through `serpapi.py` with ~157ms average latency. All sequential.

**The Sequential Bottleneck Pattern:**
```python
# ❌ BAD - Sequential SERP calls inside scoring loop (~17s total)
for pick in game_picks:
    serp_intel = get_serp_betting_intelligence(sport, home, away, pick_side)
    # Each call: 9 sequential API requests × ~157ms = ~1.4s per pick
    # 12 picks × 1.4s = ~17s total
```

**Solution (v20.7 — Parallel Pre-Fetch Pattern):**
```python
# ✅ GOOD - Pre-fetch all SERP data in parallel before scoring loop (~2-3s)
# Step 1: Extract unique (home, away) pairs from all games
_unique_serp_games = {(g["home_team"], g["away_team"]) for g in raw_games + prop_games}

# Step 2: Pre-fetch both targets (home, away) per game in parallel
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(_prefetch_serp_game, h, a, target)
               for h, a in _unique_serp_games
               for target in [h, a]]  # Both home and away as target
    results = wait_for(gather(*futures), timeout=12.0)

# Step 3: Store in cache dict, accessed by scoring function via closure
_serp_game_cache[(home_lower, away_lower, target_lower)] = result

# Step 4: In calculate_pick_score(), check cache before live call
if _serp_cache_key in _serp_game_cache:
    serp_intel = _serp_game_cache[_serp_cache_key]  # Cache hit: ~0ms
else:
    serp_intel = get_serp_betting_intelligence(...)  # Fallback: ~1.4s
```

**Key Design Decisions:**
| Decision | Why |
|----------|-----|
| `ThreadPoolExecutor` + `run_in_executor` | SERP calls are synchronous (requests lib); threads avoid blocking async loop |
| 16 workers max | ~16 unique game-target pairs for 8 games; 1 thread per task |
| 12s timeout on entire batch | Hard ceiling prevents runaway parallel calls |
| Cache key = `(home_lower, away_lower, target_lower)` | Mirrors `serp_intelligence.py:602` target_team selection logic |
| Props NOT pre-fetched | Per-player data too many unique combinations; benefit from warm serpapi cache |
| Closure-scoped `_serp_game_cache` | Available to nested `calculate_pick_score()` without parameter threading |

**Performance Impact:**
| Metric | Before (v20.6) | After (v20.7) | Improvement |
|--------|----------------|---------------|-------------|
| SERP total time | ~17s sequential | ~2-3s parallel | **~6x faster** |
| Game scoring | ~35-46s | ~20-30s (expected) | Time freed for props |
| Props scoring | 0 picks (timeout) | Should complete | **Props restored** |

**Debug Telemetry Added:**
```json
{
  "debug": {
    "serp": {
      "prefetch_cached": 16,   // Results successfully pre-fetched
      "prefetch_games": 8      // Unique game pairs cached
    },
    "timings": {
      "serp_prefetch": 2.3     // Seconds for parallel pre-fetch
    }
  }
}
```

**Files Modified:**
- `live_data_router.py:5851-5927` — SERP pre-fetch block (after player resolution, before scoring loop)
- `live_data_router.py:4431-4442` — Cache lookup in `calculate_pick_score()` for game bets
- `live_data_router.py:7229-7230` — Debug telemetry (`prefetch_cached`, `prefetch_games`)

**Prevention:**
- When an external API is called N times sequentially in a loop, consider parallel pre-fetching
- Always measure actual API call counts and latencies before assuming "it's fast enough"
- The 90-minute `serpapi.py` cache helps for repeated queries but doesn't help when ALL queries are unique
- Pre-fetch tasks should have a hard timeout to prevent blocking the main budget
- Always add debug telemetry for pre-fetch results so performance can be monitored

**The General Pre-Fetch Pattern (for future similar bottlenecks):**
1. **Identify** the sequential bottleneck: grep for API calls inside scoring loops
2. **Extract** unique inputs from all candidates before the loop starts
3. **Parallelize** using `ThreadPoolExecutor` + `asyncio.run_in_executor()`
4. **Cache** results in a closure-scoped dict with deterministic keys
5. **Fallback** gracefully to live calls on cache miss or timeout
6. **Telemetry** via `_record()` and debug output fields

**Fixed in:** v20.7 (Feb 5, 2026)

### Lesson 54: Props Indentation Bug — Dead Code from Misplaced Break (v20.8)
**Problem:** ALL sports (NBA, NHL, NFL, MLB, NCAAB) returned 0 props despite game picks working correctly. Props were scored but never collected into the output.

**Root Cause:** `if _props_deadline_hit: break` was positioned at game-loop indentation level (12 spaces) BETWEEN `calculate_pick_score()` and all prop processing code (16 spaces). Due to Python's indentation-sensitive scoping:

```python
# BUG — Lines 6499-6506 (before fix):
                    game_status=_prop_game_status
                )
            if _props_deadline_hit:       # ← 12-space indent (game loop level)
                break

                # Lineup confirmation guard (props only)   # ← 16-space indent
                lineup_guard = _lineup_risk_guard(...)      #    INSIDE the if block
                ...
                props_picks.append({...})                   #    ALSO INSIDE — UNREACHABLE
```

**How Python interpreted this:**
- When `_props_deadline_hit = True`: `break` executes, everything after is unreachable
- When `_props_deadline_hit = False`: the entire `if` block is skipped — BUT all code at 16-space indent was INSIDE the `if` block, so it was ALSO skipped
- Result: `props_picks.append(...)` at line 6596 NEVER executes regardless of the flag's value

**The Fix:**
1. Removed `if _props_deadline_hit: break` from between `calculate_pick_score()` and prop processing (line 6502)
2. Added `if _props_deadline_hit: break` AFTER `props_picks.append({...})` completes (line 6662)

```python
# FIXED — Each prop is fully processed before deadline check:
                    game_status=_prop_game_status
                )

                # Lineup confirmation guard (props only)
                lineup_guard = _lineup_risk_guard(...)
                ...
                props_picks.append({...})
            if _props_deadline_hit:
                break
```

**Why This Was Hard to Find:**
- No errors, no crashes, no stack traces — the code simply never reached `append()`
- Props status showed "OK" (scoring succeeded), but count was always 0
- The bug was invisible in normal test output because Python's indentation scoping made the dead code syntactically valid
- A 4-character indentation difference (12 vs 16 spaces) determined whether 160+ lines of code executed

**Prevention:**
1. **NEVER place control flow (`if/break/continue/return`) between a function call and the code that uses its result** — especially in deeply nested loops
2. **When moving `break` statements, verify the indentation level matches the loop you intend to break from** — Python treats indentation as scope
3. **After any edit near loop control flow, read the surrounding 50+ lines** to verify the intended scope isn't broken
4. **If props return 0 picks but game picks work**, the first thing to check is the prop scoring loop's control flow — not timeouts, not data sources
5. **Add integration tests that verify `props.count > 0`** when test data is available — a structural invariant test would have caught this immediately

**Files Modified:**
- `live_data_router.py` — 2 edits: remove misplaced break (line 6502), add break after append (line 6662)

**Verification:**
```bash
# 1. Syntax check
python3 -m py_compile live_data_router.py

# 2. Scoring guard tests
python3 -m pytest tests/test_option_a_scoring_guard.py -q

# 3. Option A drift scan
bash scripts/option_a_drift_scan.sh

# 4. Verify props return picks in production
curl /live/best-bets/NBA -H "X-API-Key: KEY" | jq '.props.count'
# Should be > 0 when today's games exist

# 5. Check all sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, props: .props.count, games: .game_picks.count}'
done
```

**Impact:** This was the root cause of the "props not pulling across sports" issue. Every sport (NBA, NHL, NFL, MLB, NCAAB) was affected since the bug was in the shared props scoring loop in `_best_bets_inner()`.

**Fixed in:** v20.8 (Feb 5, 2026)

---

## ✅ VERIFICATION CHECKLIST (ESPN)

Run these after ANY change to ESPN integration:

```bash
# 1. Syntax check ESPN module
python -m py_compile alt_data_sources/espn_lineups.py

# 2. ESPN availability check
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.espn'
# Should show: available: true, configured: true

# 3. ESPN officials data
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug | {espn_events: .espn_events_mapped, officials: .officials_available}'
# Should show counts > 0 (varies by game day)

# 4. ESPN odds cross-validation
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].research_reasons | map(select(contains("ESPN")))'
# Should include "ESPN confirms spread" or "ESPN spread close" when available

# 5. ESPN injuries merged
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug | {injuries_teams: .injuries_lookup_count, espn_injuries_teams: .espn_injuries_count}'

# 6. ESPN venue/weather (MLB/NFL only)
curl /live/best-bets/MLB?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {venue: .espn_venue, weather_source: .weather_source}'

# 7. Test all sports ESPN integration
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  result=$(curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY")
  espn_events=$(echo "$result" | jq -r '.debug.espn_events_mapped // 0')
  echo "ESPN events: $espn_events"
done

# 8. Verify no ESPN errors in logs
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.errors | map(select(contains("ESPN") or contains("espn")))'
# Should be empty or null
```

---

## ✅ VERIFICATION CHECKLIST (ML & GLITCH)

Run these after ANY change to ML or GLITCH code:

```bash
# 1. Syntax check
python -m py_compile esoteric_engine.py ml_integration.py live_data_router.py

# 2. ML Status
curl /live/ml/status -H "X-API-Key: KEY" | jq '{
  lstm_loaded: .lstm.loaded_count,
  ensemble_available: .ensemble.available,
  tensorflow: .tensorflow_available
}'

# 3. GLITCH signals in output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    glitch_adj: .glitch_adjustment,
    esoteric_reasons: .esoteric_reasons | map(select(startswith("GLITCH")))
  }'

# 4. Context pillars
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    def_rank: .def_rank,
    pace: .pace,
    vacuum: .vacuum,
    context_score: .context_score
  }'

# 5. Alt data sources
curl /live/debug/integrations -H "X-API-Key: KEY" | \
  jq '{noaa: .noaa, serpapi: .serpapi}'

# 6. Harmonic Convergence (check high-scoring picks)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[] | select(.research_score >= 8 and .esoteric_score >= 8) | {
    research: .research_score,
    esoteric: .esoteric_score,
    confluence: .confluence_level
  }'

# 7. MSRF Resonance (check turn date detection)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    msrf_boost: .msrf_boost,
    msrf_level: .msrf_metadata.level,
    msrf_points: .msrf_metadata.points,
    msrf_dates: .msrf_metadata.significant_dates_used
  }'

# 8. MSRF in esoteric_reasons (verify integration)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[] | select(.msrf_boost > 0) | {
    player: .player_name,
    msrf: .msrf_boost,
    level: .msrf_metadata.level
  }'

# 9. Phase 1 Dormant Signals - Gann Square (GAME picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Gann")))'
# Should show: ["Gann: 45° (MODERATE)"] or similar when angles resonate

# 10. Phase 1 Dormant Signals - Founder's Echo (GAME picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Founder")))'
# Shows "Founder's Echo: TeamName (year)" when team gematria resonates with date

# 11. Phase 1 Dormant Signals - Biorhythms (PROP picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.props.picks[].esoteric_reasons] | flatten | map(select(startswith("Biorhythm")))'
# Shows "Biorhythm: PEAK (85)" when player is at peak cycle

# 12. Esoteric Score Variation (confirms signals are differentiating)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_score] | {min: min, max: max, avg: (add/length)}'
# Range should be > 1.0 point (e.g., min: 4.05, max: 5.7)

# 13. All unique esoteric_reasons (full signal inventory)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons, .props.picks[].esoteric_reasons] | flatten | unique'

# 14. Phase 2.2 - Void-of-Course Daily Edge (check VOC penalty)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.debug.daily_energy'
# Should include: void_of_course: {is_void, confidence, penalty}

# 15. Test VOC function directly
python3 -c "from astronomical_api import is_void_moon_now; is_void, conf = is_void_moon_now(); print(f'VOC: is_void={is_void}, confidence={conf}')"
# Returns current VOC status

# 16. Verify daily energy includes VOC data in response
curl -s '/live/daily-energy' -H 'X-API-Key: KEY' | jq '.void_of_course'
# When VOC active: {is_void: true, confidence: 0.87, penalty: -20}
```

---

## ✅ VERIFICATION CHECKLIST (SECURITY)

Run these after ANY change that touches logging, API clients, or debug endpoints:

```bash
# 1. Log sanitizer tests
pytest tests/test_log_sanitizer.py -v
# All 20 tests must pass

# 2. Demo data gate tests
pytest tests/test_no_demo_data.py -v
# All 12 tests must pass (some skip if deps missing)

# 3. Check for secret patterns in logs (should be empty or [REDACTED])
grep -rn "apiKey=\|api_key=\|Authorization:" *.py | grep -v "REDACTED\|sanitize\|test_"
# Should return few/no results

# 4. Verify demo endpoints are gated
curl -X POST /debug/seed-pick -H "X-Admin-Key: KEY" 2>/dev/null | jq '.error'
# Should return "Demo data gated"

# 5. Verify fallback returns empty (not demo data)
ENABLE_DEMO=false python3 -c "
from legacy.services.odds_api_service import OddsAPIService
import os
os.environ['ODDS_API_KEY'] = ''
os.environ['ENABLE_DEMO'] = 'false'
s = OddsAPIService()
result = s.get_odds('basketball_nba')
assert result == [], f'Expected empty, got {result}'
print('✓ Demo data properly gated')
"

# 6. Check sensitive env vars are in sanitizer
grep -c "ODDS_API_KEY\|PLAYBOOK_API_KEY" core/log_sanitizer.py
# Should return 2+ (vars are listed)
```

---

## ✅ VERIFICATION CHECKLIST (Best-Bets & Scoring)

**Run these after ANY change to best-bets, scoring, or dual-use functions:**

```bash
# 1. Syntax check
python -m py_compile live_data_router.py

# 2. Test ALL 5 sports (MANDATORY after scoring changes)
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== Testing $sport ==="
  result=$(curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/$sport" \
    -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4")

  # Check for error
  error=$(echo "$result" | jq -r '.detail.code // empty')
  if [ -n "$error" ]; then
    echo "❌ $sport FAILED: $error"
    echo "$result" | jq '.detail'
  else
    games=$(echo "$result" | jq '.game_picks.count')
    props=$(echo "$result" | jq '.props.count')
    echo "✅ $sport OK: $games game picks, $props props"
  fi
done

# 3. Check for JSONResponse returns in dual-use functions
grep -n "return JSONResponse" live_data_router.py | grep -E "get_sharp|get_splits|get_lines|get_injuries"
# Should return EMPTY (these functions must return dicts)

# 4. Verify debug mode error details work
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq 'has("detail") or has("sport")'
# Should return true (either error detail or valid response)

# 5. Check MSRF integration
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | \
  jq '.game_picks.picks[0] | {msrf_boost, msrf_source: .msrf_metadata.source}'
# Should show msrf_boost (0.0 or higher) and msrf_source

# 6. Verify no undefined variables in calculate_pick_score
grep -n "_game_date_obj\|jarvis_rs\|esoteric_reasons" live_data_router.py | head -20
# Verify these are initialized before use

# 7. Check sharp endpoint still works (after dual-use fix)
curl -s "https://web-production-7b2a.up.railway.app/live/sharp/NBA" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{source: .source, count: .count}'
# Should return source and count (not error)
```

**If ANY sport fails, DO NOT deploy other changes until fixed.**

---

## ✅ VERIFICATION CHECKLIST (SERP Intelligence)

Run these after ANY change to SERP integration (serp_guardrails.py, serp_intelligence.py, serpapi.py, or SERP pre-fetch in live_data_router.py):

```bash
# 1. Syntax check SERP modules
python -m py_compile core/serp_guardrails.py alt_data_sources/serp_intelligence.py alt_data_sources/serpapi.py

# 2. Verify SERP status (shadow mode OFF, live mode ON)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
# MUST show: available=true, shadow_mode=false, mode="live"

# 3. Check quota tracking
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp.status.quota | {daily_remaining, monthly_remaining}'
# Should show remaining counts (166/day, 5000/month starting values)

# 4. Check cache performance
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp.status.cache | {hits, misses, hit_rate_pct}'
# Hit rate should be >50% after initial warm-up

# 5. Check boosts on picks (signals should fire)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {serp_boost, serp_reasons}'
# serp_boost > 0 when signals fire, serp_reasons shows which signals

# 6. Test all 5 sports SERP integration
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, serp_available: .debug.serp.available, serp_mode: .debug.serp.mode}'
done
# All should show available=true, mode="live"

# 7. Verify boost caps enforced (no single engine > cap)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].serp_boost] | max'
# Max should be <= 4.3 (SERP_TOTAL_CAP)

# 8. Check env var aliases work
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.serpapi'
# Should show configured=true if either SERPAPI_KEY or SERP_API_KEY is set

# 9. Verify SERP pre-fetch is working (v20.7)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp | {prefetch_cached, prefetch_games}'
# prefetch_cached > 0 means pre-fetch is active and caching results
# prefetch_games > 0 means unique game pairs were identified

# 10. Check pre-fetch timing (should be < 12s)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.timings.serp_prefetch'
# Should be 1-5s (parallel). If > 12s, pre-fetch timed out

# 11. Verify pre-fetch not in timed_out_components
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug._timed_out_components'
# Should NOT include "serp_prefetch" — if it does, 12s timeout was hit

# 12. Verify props now return picks (v20.7 regression check)
curl /live/best-bets/NBA -H "X-API-Key: KEY" | \
  jq '{props_count: .props.count, game_count: .game_picks.count}'
# props_count should be > 0 when there are today's games
```

**Critical Invariants (ALWAYS verify these):**
- `SERP_SHADOW_MODE` must be `False` (live mode)
- Boosts must be capped per engine (ai=0.8, research=1.3, esoteric=0.6, jarvis=0.7, context=0.9)
- Total boost must not exceed 4.3
- Quota must be checked before API calls
- All SERP calls wrapped in try/except (fail-soft)
- `prefetch_cached > 0` in production (v20.7 — proves parallel pre-fetch is active)
- `serp_prefetch` timing < 12s (hard timeout)

---

## 🚫 NEVER DO THESE (ML & GLITCH)

1. **NEVER** add a new signal without wiring it into the scoring pipeline
2. **NEVER** add a function parameter without using it in the function body
3. **NEVER** leave API clients as stubs in production (verify `source != "fallback"`)
4. **NEVER** hardcode `base_ai = 5.0` when LSTM models are available
5. **NEVER** skip the ML fallback chain (LSTM → Ensemble → Heuristic)
6. **NEVER** change ENGINE_WEIGHTS without updating `core/scoring_contract.py`
7. **NEVER** add a new pillar without documenting it in the 17-pillar map
8. **NEVER** modify `get_glitch_aggregate()` without updating its docstring weights

## 🚫 NEVER DO THESE (MSRF)

16. **NEVER** call MSRF with fewer than 3 significant dates (will return no boost)
17. **NEVER** modify MSRF number lists without understanding sacred geometry theory
18. **NEVER** add MSRF as a 6th engine - use confluence boost pattern instead
19. **NEVER** skip feature flag check (`MSRF_ENABLED`) before MSRF calculations
20. **NEVER** hardcode significant dates - always pull from data sources

## 🚫 NEVER DO THESE (SECURITY)

9. **NEVER** log `request.headers` without using `sanitize_headers()`
10. **NEVER** construct URLs with `?apiKey=VALUE` - use `params={}` dict
11. **NEVER** log partial keys like `key[:8]...` (reconnaissance risk)
12. **NEVER** return demo/sample data without `ENABLE_DEMO=true` or `mode=demo`
13. **NEVER** fall back to demo data on API failure (return empty instead)
14. **NEVER** hardcode player names (LeBron, Mahomes) in production responses
15. **NEVER** add new env var secrets without adding to `SENSITIVE_ENV_VARS` in log_sanitizer.py

## 🚫 NEVER DO THESE (FastAPI & Function Patterns)

21. **NEVER** return `JSONResponse()` from functions that are called internally - return dicts instead
22. **NEVER** create dual-use functions (endpoint + internal) without verifying return type compatibility
23. **NEVER** use `.get()` on a function return value without verifying it returns a dict (not JSONResponse)
24. **NEVER** leave variables uninitialized before try blocks if they're used after the try block
25. **NEVER** compare numeric variables to thresholds without None checks (use `x is not None and x >= 8.0`)
26. **NEVER** swallow exceptions without logging the traceback
27. **NEVER** return generic error messages in production - include error details in debug mode

## 🚫 NEVER DO THESE (Nested Functions & Closures)

28. **NEVER** assume closure variables are defined - verify they're assigned before the nested function
29. **NEVER** use variables from outer scope without checking all code paths initialize them
30. **NEVER** add new variables to nested functions without grepping for all usages
31. **NEVER** modify scoring pipeline without testing all 5 sports (NBA, NHL, NFL, MLB, NCAAB)

## 🚫 NEVER DO THESE (API & Data Integration)

32. **NEVER** assume a single API format - check for format variations (Playbook vs ESPN, nested vs flat)
33. **NEVER** put shared context calculations inside pick_type-specific blocks - context runs for ALL types
34. **NEVER** assume injuries/data will match team names exactly - compare actual API responses to game data
35. **NEVER** skip parallel fetching for critical data (props, games, injuries should fetch concurrently)

## 🚫 NEVER DO THESE (ESPN Integration)

36. **NEVER** hardcode sport/league mappings inline - use the `SPORT_MAPPING` dict in espn_lineups.py
37. **NEVER** make ESPN calls synchronously in the scoring loop - use batch parallel fetches before scoring
38. **NEVER** assume ESPN has data for all games - officials are assigned closer to game time, gracefully fallback
39. **NEVER** replace primary data with ESPN data - ESPN is for SUPPLEMENT and CROSS-VALIDATION only
40. **NEVER** skip the `league` key in SPORT_MAPPING (the MLB bug: `"mlb": "mlb"` instead of `"league": "mlb"`)
41. **NEVER** forget to handle ESPN $ref links - officials endpoint returns URLs that need separate fetches
42. **NEVER** skip team name normalization when matching ESPN data to Odds API data (case-insensitive + accent handling)
43. **NEVER** assume ESPN venue data exists for indoor sports - only fetch venue/weather for MLB and NFL
44. **NEVER** add ESPN boosts without logging them in research_reasons for debug visibility
45. **NEVER** modify ESPN integration without testing ALL 5 sports (different endpoints, different data availability)

## 🚫 NEVER DO THESE (SERP Intelligence)

46. **NEVER** set `SERP_SHADOW_MODE=True` in production - user wants LIVE MODE with active boosts
47. **NEVER** skip quota checks before SerpAPI calls - use `check_quota_available()` first
48. **NEVER** exceed boost caps - enforced in `cap_boost()` (per-engine) and `cap_total_boost()` (4.3 total)
49. **NEVER** make SERP calls inside scoring loop without try/except - must fail-soft, never 500
50. **NEVER** add SERP env var aliases without updating BOTH `integration_contract.py` AND `serpapi.py`
51. **NEVER** change SERP_CACHE_TTL or SERP_TIMEOUT in `serpapi.py` - single source of truth is `serp_guardrails.py`
52. **NEVER** forget to call `record_cache_hit()` / `record_cache_miss()` / `record_cache_error()` for tracking
53. **NEVER** skip `apply_shadow_mode()` before returning boosts - even in live mode (it's a no-op but keeps code paths consistent)
54. **NEVER** forget to increment quota after successful API calls - use `increment_quota()` in serpapi.py
55. **NEVER** hardcode sport-specific search queries inline - use `SPORT_QUERIES` template dict in serp_intelligence.py
56. **NEVER** modify signal→engine mapping without updating INVARIANT 23 in CLAUDE.md

## 🚫 NEVER DO THESE (Esoteric/Phase 1 Signals)

57. **NEVER** assume `pick_type == "GAME"` for game picks - actual values are "SPREAD", "MONEYLINE", "TOTAL", "SHARP"
58. **NEVER** check `pick_type == "GAME"` directly - use pattern: `_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")`
59. **NEVER** add esoteric signals directly to `esoteric_score` - add to `esoteric_raw` before the clamp
60. **NEVER** wire signals without adding to `esoteric_reasons` for debug visibility
61. **NEVER** add GAME-only signals without the `_is_game_pick` guard
62. **NEVER** add PROP-only signals without checking `pick_type == "PROP"` AND `player_name`
63. **NEVER** assume all teams will trigger Founder's Echo - only ~7/119 teams resonate on any given day
64. **NEVER** activate dormant signals without testing on production data via curl verification commands
65. **NEVER** modify esoteric scoring without running the verification checklist (checks 9-13 in ML & GLITCH section)

## 🚫 NEVER DO THESE (v17.6 - Vortex & Benford)

66. **NEVER** add parameters to `calculate_pick_score()` without updating ALL 3 call sites (game_picks, props, sharp_money)
67. **NEVER** assume Benford will run with <10 values - it requires 10+ for statistical significance
68. **NEVER** pass only direct values (prop_line, spread, total) to Benford - use multi-book aggregation
69. **NEVER** forget to extract from `game.bookmakers[]` when multi-book data is needed
70. **NEVER** add Vortex/Tesla signals without checking for 0/None values first (division by zero risk)
71. **NEVER** modify line history tables without considering the scheduler job dependencies
72. **NEVER** run `_run_line_snapshot_capture()` without checking Odds API quota first
73. **NEVER** assume line history exists for new events - check for NULL/empty returns

## 🚫 NEVER DO THESE (v19.0 - Trap Learning Loop)

74. **NEVER** exceed `MAX_SINGLE_ADJUSTMENT` (5%) per trap trigger - safety guard is code-enforced
75. **NEVER** bypass the cooldown period (24h default) - prevents runaway adjustments
76. **NEVER** create traps targeting invalid engine/parameter combinations - validate against `SUPPORTED_ENGINES`
77. **NEVER** skip `_validate_adjustment_safety()` before applying adjustments
78. **NEVER** apply adjustments without logging to `adjustments.jsonl` - audit trail is mandatory
79. **NEVER** modify `SUPPORTED_ENGINES` dict without updating trap_router validation logic
80. **NEVER** create traps with `adjustment_cap > 0.05` - exceeds max single adjustment
81. **NEVER** run trap evaluation before grading completes (6:15 AM runs after 6:00 AM grading)
82. **NEVER** skip `enrich_game_result()` before evaluating conditions - numerology/gematria fields required
83. **NEVER** delete trap files manually - use `update_trap_status(trap_id, "RETIRED")` instead
84. **NEVER** allow cumulative adjustments to exceed 15% per trap - `MAX_CUMULATIVE_ADJUSTMENT` enforced
85. **NEVER** create traps without specifying `target_engine` AND `target_parameter` - both required
86. **NEVER** assume game results exist for all sports on all days - handle empty results gracefully
87. **NEVER** modify trap condition evaluation logic without updating dry-run endpoint to match

## 🚫 NEVER DO THESE (v18.2 - Phase 8 Esoteric Signals)

88. **NEVER** compare timezone-naive datetime to timezone-aware datetime - causes `TypeError: can't subtract offset-naive and offset-aware datetimes`
89. **NEVER** use `datetime(2000, 1, 1)` without timezone for astronomical calculations - add `tzinfo=ZoneInfo("UTC")`
90. **NEVER** forget to initialize `weather_data = None` before conditional blocks that may reference it
91. **NEVER** skip `get_phase8_esoteric_signals()` in the scoring pipeline - all 5 signals must run
92. **NEVER** hardcode Mercury retrograde dates without updating for the current year
93. **NEVER** assume Phase 8 signals will always trigger - some dates have no lunar/retrograde/rivalry activity
94. **NEVER** add Phase 8 boosts directly to `esoteric_score` - add to `esoteric_raw` before the clamp
95. **NEVER** skip adding Phase 8 reasons to `esoteric_reasons` for debug visibility
96. **NEVER** use AND logic for env var alternatives when OR is needed - check if ANY alternative is set, not ALL
97. **NEVER** forget that everything is in ET only - don't assume UTC for game times

## 🚫 NEVER DO THESE (v20.x - Two Storage Systems)

98. **NEVER** write picks from `auto_grader.py` - only `grader_store.py` writes picks
99. **NEVER** write weights from `grader_store.py` - only `auto_grader.py` writes weights
100. **NEVER** merge the two storage systems - they're separate by design for good reasons
101. **NEVER** add a new `_save_predictions()` method to auto_grader - it was removed intentionally
102. **NEVER** assume picks and weights should be in the same file - different access patterns require separation
103. **NEVER** bypass `grader_store.persist_pick()` when saving picks - it's the single source of truth
104. **NEVER** call `auto_grader._save_state()` expecting it to save picks - it only saves weights now

## 🚫 NEVER DO THESE (Boost Field Contract)

105. **NEVER** return a pick without all required boost fields (value + status + reasons)
106. **NEVER** omit `msrf_boost`, `jason_sim_boost`, or `serp_boost` from pick payloads - even if 0.0
107. **NEVER** skip tracking integration usage on cache hits - call `mark_integration_used()` for both cache and live

## 🚫 NEVER DO THESE (v20.2 - Auto Grader Weights)

108. **NEVER** add a new pick type (market type) without initializing weights for it in `_initialize_weights()`
109. **NEVER** assume `adjust_weights()` fallback to "points" is correct - it masks missing stat_type configurations
110. **NEVER** forget that game picks use `stat_type = pick_type.lower()` (spread, total, moneyline, sharp)
111. **NEVER** skip verifying `calculate_bias()` returns sample_size > 0 for new stat types
112. **NEVER** assume the auto grader "just works" - test with `/live/grader/bias/{sport}?stat_type=X` for all types
113. **NEVER** add new market types to `run_daily_audit()` without adding corresponding weights
114. **NEVER** assume weight adjustments are applied just because sample_size > 0 - check `applied: true` explicitly
115. **NEVER** skip checking `factor_bias` in bias response - it shows what signals are being tracked for learning
116. **NEVER** assume the daily lesson generated correctly - verify with `/live/grader/daily-lesson/latest`
117. **NEVER** forget to verify correlation tracking for all 28 signals (pace, vacuum, officials, glitch, esoteric)

## 🚫 NEVER DO THESE (v20.3 - Grading Pipeline)

118. **NEVER** add a new pick_type without adding handling in `grade_game_pick()` - it will grade as PUSH
119. **NEVER** forget to pass `picked_team` to `grade_game_pick()` for spread/moneyline grading accuracy
120. **NEVER** have mismatched stat type lists between `_initialize_weights()` and `run_daily_audit()` - both must match
121. **NEVER** assume STAT_TYPE_MAP covers all formats - check for direct formats ("points") AND Odds API formats ("player_points")
122. **NEVER** forget to strip market suffixes like "_over_under", "_alternate" from stat types before lookup
123. **NEVER** skip testing grading for ALL pick types after changes (SPREAD, TOTAL, MONEYLINE, SHARP, PROP)
124. **NEVER** assume 0% hit rate means bad predictions - it might mean grading is broken (all PUSH)

## 🚫 NEVER DO THESE (v20.4 - Go/No-Go & Sanity Scripts)

125. **NEVER** use hardcoded line numbers in sanity script filters without documenting what they filter
126. **NEVER** modify `live_data_router.py` without re-running `audit_drift_scan.sh` locally
127. **NEVER** add a new boost to the scoring formula without updating `endpoint_matrix_sanity.sh` math check
128. **NEVER** assume `ensemble_adjustment` is 0 - it can be `null`, `0.0`, `+0.5`, or `-0.5`
129. **NEVER** skip the go/no-go check after changes to scoring, boosts, or sanity scripts
130. **NEVER** commit code that fails `prod_go_nogo.sh` - all 12 checks must pass
131. **NEVER** forget that `glitch_adjustment` is ALREADY in `esoteric_score` (not a separate additive)

## 🚫 NEVER DO THESE (v20.4 - Frontend/Backend Synchronization)

132. **NEVER** change engine weights in `scoring_contract.py` without updating frontend tooltips
133. **NEVER** assume frontend documentation matches backend - verify against `scoring_contract.py`
134. **NEVER** describe context_score as a "weighted engine" - it's a bounded modifier (±0.35)
135. **NEVER** use old weight percentages (AI 15%, Research 20%, Esoteric 15%, Jarvis 10%, Context 30%)
136. **NEVER** skip updating `docs/FRONTEND_INTEGRATION.md` when backend scoring changes
137. **ALWAYS** verify frontend tooltips show: AI 25%, Research 35%, Esoteric 20%, Jarvis 20%, Context ±0.35

**Correct Option A Weights (authoritative source: `core/scoring_contract.py`):**
```python
ENGINE_WEIGHTS = {
    "ai": 0.25,        # 25% - 8 AI models
    "research": 0.35,  # 35% - Sharp money, splits, variance (LARGEST)
    "esoteric": 0.20,  # 20% - Numerology, astro, fib, vortex
    "jarvis": 0.20,    # 20% - Gematria, sacred triggers
}
CONTEXT_MODIFIER_CAP = 0.35  # ±0.35 (NOT a weighted engine!)
```

## 🚫 NEVER DO THESE (Shell Scripts with Python Subprocesses)

138. **NEVER** use `VAR=value` when Python subprocesses need the variable - use `export VAR=value`
139. **NEVER** assume shell variables are inherited by child processes - they must be explicitly exported
140. **NEVER** debug "Could not resolve host: None" without checking if env vars are exported
141. **NEVER** write shell scripts that call Python without verifying variable visibility with `os.environ.get()`

**Shell Variable Scope Quick Reference:**
```bash
# ❌ WRONG - Python subprocess can't see this
BASE_URL="https://example.com"
python3 -c "import os; print(os.environ.get('BASE_URL'))"  # None

# ✅ CORRECT - 'export' makes it visible to children
export BASE_URL="https://example.com"
python3 -c "import os; print(os.environ.get('BASE_URL'))"  # https://example.com
```

---

## 🚫 NEVER DO THESE (Datetime/Timezone - v20.5)

142. **NEVER** compare `datetime.now()` with `datetime.fromisoformat(timestamp)` - one may be naive, other aware
143. **NEVER** use undefined variables like `PYTZ_AVAILABLE` - use `core.time_et.now_et()` instead
144. **NEVER** use `pytz` for new code - use `core.time_et` (single source of truth) or `zoneinfo`
145. **NEVER** calculate date windows with wrong math like `days_back + 1` for start (creates 2-day window)
146. **NEVER** assume stored timestamps have the same timezone awareness as runtime datetime
147. **NEVER** store `line_variance` in a field named `line` - they have different meanings
148. **NEVER** grade SHARP picks using `line` field - it contains variance, not actual spread
149. **NEVER** add new datetime handling code without testing timezone-aware vs naive comparison
150. **NEVER** use `datetime.now()` in grader code - always use `now_et()` from `core.time_et`

## 🚫 NEVER DO THESE (v20.5 - Go/No-Go & Scoring Adjustments)

151. **NEVER** apply a scoring adjustment to `final_score` without surfacing it as its own field in the pick payload - unsurfaced adjustments break sanity math checks
152. **NEVER** use `os.path.dirname(__file__)` inside Python heredocs (`python3 - <<'PY'`) - `__file__` resolves to `<stdin>` and `dirname()` returns empty string; use project-relative paths instead
153. **NEVER** run `prod_go_nogo.sh` locally without `ALLOW_EMPTY=1` - local dev doesn't have production prediction/weight files
154. **NEVER** add script-only env vars (like `MAX_GAMES`, `MAX_PROPS`, `RUNS`) without registering them in `RUNTIME_ENV_VARS` in `integration_registry.py`
155. **NEVER** expect sanity scripts that test production API to pass pre-deploy when the change adds new fields - deploy first, then verify (chicken-and-egg pattern)

**Datetime Comparison Quick Reference:**
```python
# ❌ WRONG - Will crash if timestamp is timezone-aware
cutoff = datetime.now() - timedelta(days=7)
if datetime.fromisoformat(p.timestamp) >= cutoff:  # Error!

# ✅ CORRECT - Use timezone-aware datetime and handle both cases
from core.time_et import now_et
from zoneinfo import ZoneInfo
et_tz = ZoneInfo("America/New_York")
cutoff = now_et() - timedelta(days=7)

ts = datetime.fromisoformat(p.timestamp)
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=et_tz)  # Make aware if naive
if ts >= cutoff:  # Now safe to compare
```

**Date Window Calculation:**
```python
# ❌ WRONG - Creates 2-day window for days_back=1
cutoff = now - timedelta(days=days_back + 1)      # 2 days ago
end_cutoff = now - timedelta(days=days_back - 1)  # today

# ✅ CORRECT - Exact day boundaries
day_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
day_end = day_start + timedelta(days=1)
if day_start <= ts < day_end:  # Exclusive end
```

## 🚫 NEVER DO THESE (v20.6 - Boost Caps & Production)

156. **NEVER** allow the sum of confluence+msrf+jason_sim+serp boosts to exceed `TOTAL_BOOST_CAP` (3.5) — this causes score inflation and clustering at 10.0
157. **NEVER** add a new additive boost without updating `TOTAL_BOOST_CAP` logic in `compute_final_score_option_a()` — uncapped boosts compound silently
158. **NEVER** hardcode timeout values in API endpoints — always use `os.getenv()` with a sensible default and register in `integration_registry.py`
159. **NEVER** assume `TIME_BUDGET_S` only needs to cover game scoring — props scoring shares the same budget and needs time too
160. **NEVER** set pick contract fields (description, side_label, etc.) outside `normalize_pick()` — it is the single source of truth for the pick payload
161. **NEVER** use `models/pick_converter.py:compute_description()` for dict-based picks — it uses object attributes (`.player_name`) not dict keys (`["player_name"]`)
162. **NEVER** assume a consistently low engine score (like jarvis_rs=4.5) means the engine is dead code — check the production call path and whether triggers are designed to be rare
163. **NEVER** report a function as "dead code" without tracing which modules actually import it — `score_candidate()` in scoring_pipeline.py is dormant but `compute_final_score_option_a()` is active

## 🚫 NEVER DO THESE (v20.7 - Parallel Pre-Fetch & Performance)

164. **NEVER** make sequential external API calls inside a scoring loop when the same data can be pre-fetched in parallel — 107 sequential calls at ~157ms each = ~17s wasted; parallel = ~2-3s
165. **NEVER** assume "the cache handles it" for sequential API call performance — `serpapi.py` has a 90-min cache, but all ~107 queries were unique (different teams/targets); cache only helps on repeated calls within TTL
166. **NEVER** use `threading.Thread` directly for parallel API calls in an async context — use `concurrent.futures.ThreadPoolExecutor` + `asyncio.run_in_executor()` to avoid blocking the event loop
167. **NEVER** pre-fetch without a hard timeout — always wrap parallel batches in `asyncio.wait_for(gather(*futs), timeout=N)` to prevent runaway threads from consuming the entire time budget
168. **NEVER** change the SERP pre-fetch cache key format without updating BOTH the pre-fetch block (line ~5893) AND the cache lookup in `calculate_pick_score()` (line ~4434) — mismatched keys = cache misses = fallback to sequential calls
169. **NEVER** assume props can be pre-fetched like game SERP data — prop SERP calls are per-player with unique parameters that can't be batched ahead of time
170. **NEVER** add a new parallel pre-fetch phase without adding it to `_record()` timing AND checking `_past_deadline()` before starting — untracked phases break performance telemetry and can exceed the time budget
171. **NEVER** diagnose "0 props returned" without checking `_timed_out_components` in debug output — timeout starvation from upstream phases (SERP, game scoring) is the most common cause
172. **NEVER** assume a performance fix is working without verifying `debug.serp.prefetch_cached > 0` in production — a prefetch count of 0 means the pre-fetch failed silently and scoring is still sequential

**SERP Pre-Fetch Quick Reference:**
```python
# ❌ WRONG - Sequential API calls in scoring loop
for pick in candidates:
    result = external_api_call(pick.team)  # N calls × latency = slow

# ✅ CORRECT - Parallel pre-fetch before scoring loop
unique_inputs = extract_unique_from_candidates(candidates)
with ThreadPoolExecutor(max_workers=16) as pool:
    cache = dict(pool.map(fetch_one, unique_inputs))
for pick in candidates:
    result = cache.get(pick.key) or external_api_call(pick.team)  # Cache hit: ~0ms
```

## 🚫 NEVER DO THESE (v20.8 - Props Indentation & Code Placement)

173. **NEVER** place `if/break/continue/return` between a function call and the code that processes its result — in Python, indentation determines scope, and a misplaced break can make 160+ lines of code unreachable
174. **NEVER** insert loop control flow (`break`, `continue`) without verifying the indentation level matches the intended loop — a 4-space difference can silently change which loop you're breaking from
175. **NEVER** assume "0 props returned" is a timeout or data issue without checking the props scoring loop's control flow first — structural dead code is invisible (no errors, no crashes, no stack traces)
176. **NEVER** edit code near deeply nested loops without reading the surrounding 50+ lines to verify scope isn't broken — Python's indentation scoping means a single edit can silently disable entire code blocks
177. **NEVER** leave `props_picks.append()` unreachable after refactoring the props scoring loop — always verify the append executes by checking `props.count > 0` in production output

**Indentation Bug Quick Reference:**
```python
# ❌ CATASTROPHIC — break between calculate_pick_score() and processing code
                score = calculate_pick_score(...)
            if deadline:       # ← Wrong indent level (game loop, not prop loop)
                break          # Skips ALL processing below
                # Everything at 16-space indent is INSIDE the if block → DEAD CODE
                process_result(score)
                picks.append(result)  # NEVER EXECUTES

# ✅ CORRECT — break AFTER processing is complete
                score = calculate_pick_score(...)
                process_result(score)
                picks.append(result)  # Always executes
            if deadline:       # Check AFTER append
                break
```

---

## ✅ VERIFICATION CHECKLIST (Go/No-Go - REQUIRED BEFORE DEPLOY)

Run this after ANY change to scoring, boosts, sanity scripts, or live_data_router.py:

```bash
# Full go/no-go (MUST PASS all 12 checks)
API_KEY="YOUR_KEY" SKIP_NETWORK=0 SKIP_PYTEST=0 ALLOW_EMPTY=1 \
  bash scripts/prod_go_nogo.sh

# Expected output: "Prod go/no-go: PASS"
```

**IMPORTANT:** Always use `ALLOW_EMPTY=1` for local runs (dev doesn't have production prediction/weight files).

**The 12 Checks (+ optional pytest):**
| # | Check | Script | What It Validates |
|---|-------|--------|-------------------|
| 1 | option_a_drift | `option_a_drift_scan.sh` | No BASE_5 or context-as-engine |
| 2 | audit_drift | `audit_drift_scan.sh` | No unauthorized +/-0.5 to final_score |
| 3 | env_drift | `env_drift_scan.sh` | Required env vars configured |
| 4 | docs_contract | `docs_contract_scan.sh` | Required fields documented |
| 5 | learning_sanity | `learning_sanity_check.sh` | Weights initialized |
| 6 | learning_loop | `learning_loop_sanity.sh` | Auto grader operational |
| 7 | endpoint_matrix | `endpoint_matrix_sanity.sh` | All 5 sports, required fields, math check |
| 8 | prod_endpoint_matrix | `prod_endpoint_matrix.sh` | Production /health, /debug, /grader, best-bets |
| 9 | signal_coverage | `signal_coverage_report.py` | Signal coverage across sports |
| 10 | api_proof | `api_proof_check.sh` | Production API responding |
| 11 | live_sanity | `live_sanity_check.sh` | Best-bets returns valid data |
| 12 | perf_audit | `perf_audit_best_bets.sh` | Response times within benchmarks |

Checks 1-6 are offline (no network needed). Checks 7-12 require `SKIP_NETWORK=0` and a valid `API_KEY`.

**If ANY check fails:**
1. Read the artifact: `cat artifacts/{check_name}_YYYYMMDD_ET.json`
2. Fix the issue
3. Re-run go/no-go
4. Do NOT deploy until all 12 pass

**Common Failures:**
| Failure | Likely Cause | Fix |
|---------|--------------|-----|
| `audit_drift` | Line numbers shifted | Update filter in `audit_drift_scan.sh` |
| `endpoint_matrix` | Math mismatch (unsurfaced adjustment) | Surface the field + update jq formula in `endpoint_matrix_sanity.sh` |
| `env_drift` | New env var not registered | Add to `RUNTIME_ENV_VARS` in `integration_registry.py` |
| `option_a_drift` | BASE_5 introduced | Remove context-as-engine code |
| `learning_loop` | Weights missing | Check `_initialize_weights()` |
| `prod_endpoint_matrix` | Path bug or production down | Check `scripts/prod_endpoint_matrix.sh` paths, verify Railway deploy |
| `learning_sanity` | Missing ALLOW_EMPTY | Set `ALLOW_EMPTY=1` for local runs |

**Chicken-and-Egg Pattern:** When a code change adds new fields, `endpoint_matrix` (tests production) will fail pre-deploy because production doesn't have the field yet. In this case: deploy the code change first, then re-run go/no-go to verify.

**Artifacts Location:** `artifacts/{check_name}_YYYYMMDD_ET.json`

---

## 📊 PERFORMANCE BENCHMARKS (Feb 4, 2026)

**Perf Audit Results (perf_audit_best_bets.sh):**

| Sport | Game Scoring (p50) | Game Scoring (p95) | Parallel Fetch (p50) | Status |
|-------|-------------------|-------------------|---------------------|--------|
| NBA | 45.9s | 49.1s | 0.2s | ✅ Baseline |
| NFL | 0s | 0s | 0.1s | ✅ Off-season |
| NHL | 53.2s | 53.8s | 0.3s | ✅ Baseline |
| MLB | - | - | - | ✅ Off-season |
| NCAAB | - | - | - | ✅ No games |

**Component Timing Breakdown (NBA p50):**
| Component | Time (s) | Notes |
|-----------|----------|-------|
| init_engines | 0.002 | Fast after first run (cached) |
| game_context | 0.004 | Context layer setup |
| parallel_fetch | 0.206 | Odds API + Playbook + ESPN |
| et_filter | 0.002 | ET timezone filtering |
| player_resolution | 0.935 | BallDontLie player lookups |
| serp_prefetch | ~2-3 | v20.7: Parallel SERP pre-fetch (ThreadPoolExecutor, 16 workers) |
| game_picks_scoring | 45.944 | Full 4-engine + boosts pipeline (expected ~28-35s with pre-fetch) |
| props_scoring | 0.0 | No props today (should now complete with freed time budget) |
| pick_logging | 0.0 | Persistence to JSONL |

**Performance Notes:**
- Game scoring (45-53s) was the bottleneck — v20.7 SERP pre-fetch moves ~17s of sequential SERP calls to a ~2-3s parallel phase
- Expected game_picks_scoring after v20.7: ~28-35s (freed ~15s from SERP pre-fetch)
- Props should now complete within time budget (previously starved by sequential SERP calls)
- First run is slower (engine initialization ~0.6s), subsequent runs faster (~0.002s)
- Parallel fetch is efficient (~0.2s for 3 API sources)
- ET filtering is negligible (<0.02s)

**Acceptable Ranges:**
| Metric | Acceptable | Warning | Critical |
|--------|------------|---------|----------|
| game_picks_scoring | <60s | 60-90s | >90s |
| serp_prefetch | <5s | 5-10s | >12s (timeout) |
| parallel_fetch | <2s | 2-5s | >5s |
| player_resolution | <3s | 3-5s | >5s |
| Total endpoint response | <90s | 90-120s | >120s |

---

## ✅ VERIFICATION CHECKLIST (Perf Audit)

Run the perf audit after ANY change to scoring pipeline, API integrations, or parallel fetch:

```bash
# Run perf audit (requires API_KEY)
API_KEY="bookie-prod-2026-xK9mP2nQ7vR4" bash scripts/perf_audit_best_bets.sh

# Check specific sport
API_KEY="KEY" SPORTS="NBA" bash scripts/perf_audit_best_bets.sh

# More runs for better p50/p95 accuracy
API_KEY="KEY" RUNS=5 bash scripts/perf_audit_best_bets.sh
```

**What to Check:**
1. **game_picks_scoring p50 < 60s** - Main scoring pipeline
2. **parallel_fetch p50 < 2s** - API fetches
3. **No empty timings** for sports with active games
4. **init_engines fast after first run** (<0.1s on subsequent runs)

**Troubleshooting Slow Performance:**
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| parallel_fetch > 5s | API timeout or rate limit | Check Odds API quota |
| game_picks_scoring > 90s | Too many boosts enabled | Review SERP/MSRF/GLITCH |
| player_resolution > 5s | BallDontLie slow | Check BDL API health |
| init_engines > 1s every run | Engines not caching | Check singleton patterns |

**Shell Variable Export (Critical):**
The script uses Python heredocs. Variables MUST be exported:
```bash
# ❌ WRONG - Python can't see this
BASE_URL="https://example.com"

# ✅ CORRECT - Python inherits via os.environ
export BASE_URL="https://example.com"
```

---

## ✅ VERIFICATION CHECKLIST (v20.2 - Auto Grader)

Run these after ANY change to auto_grader.py or grading logic:

```bash
# 1. Syntax check auto_grader
python -m py_compile auto_grader.py

# 2. Verify weights exist for ALL stat types (PROP + GAME)
curl -s "/live/grader/weights/NBA" -H "X-API-Key: KEY" | jq 'keys'
# Should include: points, rebounds, assists, spread, total, moneyline, sharp

# 3. Test bias calculation for GAME stat types
for stat in spread total moneyline sharp; do
  echo "=== $stat ==="
  curl -s "/live/grader/bias/NBA?stat_type=$stat&days_back=1" -H "X-API-Key: KEY" | \
    jq '{stat_type: .stat_type, sample_size: .bias.sample_size, error: .bias.error}'
done
# All should show sample_size > 0 OR "No graded predictions found" (not a crash)

# 4. Run full audit and verify game picks processed
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '.results.results.NBA | {spread: .spread.bias_analysis.sample_size, total: .total.bias_analysis.sample_size}'
# Should show sample_size > 0 for spread and total

# 5. Verify grading summary has graded picks
curl -s "/live/picks/grading-summary?date=$(date -v-1d +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '{total: .total_picks, graded: (.graded_picks | length)}'
# graded should be > 0

# 6. Check OVER/UNDER performance split (for bias monitoring)
curl -s "/live/picks/grading-summary?date=$(date -v-1d +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '{
    over: {wins: [.graded_picks[] | select(.side == "Over" and .result == "WIN")] | length,
           losses: [.graded_picks[] | select(.side == "Over" and .result == "LOSS")] | length},
    under: {wins: [.graded_picks[] | select(.side == "Under" and .result == "WIN")] | length,
            losses: [.graded_picks[] | select(.side == "Under" and .result == "LOSS")] | length}
  }'
# Monitor for severe bias (e.g., OVER 19% vs UNDER 82%)

# 7. Test all 5 sports audit
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '[.results.results | to_entries[] | {sport: .key, spread_samples: .value.spread.bias_analysis.sample_size}]'

# 8. Verify weight adjustments are APPLIED (not just calculated)
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{applied: (.weight_adjustments != null), adjustments: .weight_adjustments}'
# Must show applied: true with pace, vacuum, officials deltas

# 9. Check factor correlations are tracked
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '.bias.factor_bias | keys'
# Should include: pace, vacuum, officials, glitch, esoteric

# 10. Full learning loop health check
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{
    stat_type,
    sample_size: .bias.sample_size,
    hit_rate: .bias.overall.hit_rate,
    bias_direction: .bias.overall.bias_direction,
    factors_tracked: (.bias.factor_bias | keys | length),
    adjustments_applied: (.weight_adjustments != null)
  }'
# Expected: sample_size > 0, factors_tracked >= 5, adjustments_applied: true

# 11. Verify daily lesson generation
curl -s "/live/grader/daily-lesson/latest" -H "X-API-Key: KEY" | \
  jq '{date_et, total_graded, weights_adjusted: (.weights_adjusted | length)}'
```

**Critical Invariants (ALWAYS verify these):**
- `_initialize_weights()` includes BOTH prop_stat_types AND game_stat_types
- Game picks use `stat_type = pick_type.lower()` (from `_convert_pick_to_record()`)
- `adjust_weights()` should NOT fall back to "points" for valid game stat types
- `calculate_bias()` filters by `record.stat_type == stat_type` (exact match)
- Weight adjustments must show `applied: true` (not just calculated)
- Factor correlations must include all 5 categories: pace, vacuum, officials, glitch, esoteric

**Learning Loop Health Indicators:**
| Indicator | Healthy | Unhealthy |
|-----------|---------|-----------|
| `sample_size` | > 0 | 0 or null |
| `hit_rate` | Non-null | null |
| `factor_bias` | 5+ categories | Empty or null |
| `weight_adjustments` | Non-null with deltas | null |
| `applied` | true | false or missing |

---

## ✅ VERIFICATION CHECKLIST (v19.0 - Trap Learning Loop)

Run these after ANY change to Trap Learning Loop:

```bash
# 1. Syntax check trap modules
python -m py_compile trap_learning_loop.py trap_router.py

# 2. Verify trap storage directory exists
curl /internal/storage/health -H "X-API-Key: KEY" | jq '.trap_learning_dir'
# Should show: /data/trap_learning

# 3. List active traps
curl /live/traps/ -H "X-API-Key: KEY" | jq 'length'
# Should return count of active traps

# 4. Test trap creation
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Test Trap Verification",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [
    {"field": "margin", "comparator": ">=", "value": 15}
  ]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "research",
  "target_parameter": "weight_public_fade"
}' | jq '{success, trap_id}'
# Should show success: true

# 5. Test dry-run evaluation (condition met)
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap-verification",
  "game_result": {"margin": 25, "result": "win", "home_team": "Lakers", "away_team": "Celtics"}
}' | jq '{condition_met, would_apply, proposed_adjustment}'
# Should show condition_met: true

# 6. Test dry-run evaluation (condition NOT met)
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap-verification",
  "game_result": {"margin": 5, "result": "win", "home_team": "Lakers", "away_team": "Celtics"}
}' | jq '{condition_met, would_apply}'
# Should show condition_met: false

# 7. Check adjustment history endpoint
curl /live/traps/history/research -H "X-API-Key: KEY" | jq '{engine, adjustments_count: (.adjustments | length)}'
# Should return engine: "research"

# 8. Get summary stats
curl /live/traps/stats/summary -H "X-API-Key: KEY" | jq '{total_traps, by_engine, by_sport}'
# Should show breakdown by engine and sport

# 9. Verify scheduler job is registered
curl /live/scheduler/status -H "X-API-Key: KEY" | jq '.jobs[] | select(.id == "trap_evaluation") | {id, next_run}'
# Should show trap_evaluation job with next_run time

# 10. Test SUPPORTED_ENGINES validation
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Invalid Engine Test",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [{"field": "margin", "comparator": ">=", "value": 10}]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "invalid_engine",
  "target_parameter": "some_param"
}' | jq '.detail'
# Should return error about invalid engine

# 11. Test safety cap enforcement
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Overcap Test",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [{"field": "margin", "comparator": ">=", "value": 10}]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.10},
  "target_engine": "research",
  "target_parameter": "weight_public_fade",
  "adjustment_cap": 0.10
}' | jq '.detail'
# Should return error about exceeding max adjustment cap

# 12. Verify base engines are supported
python3 -c "
from trap_learning_loop import SUPPORTED_ENGINES
print('Supported engines:', list(SUPPORTED_ENGINES.keys()))
for k in ['ai', 'research', 'esoteric', 'jarvis']:
    assert k in SUPPORTED_ENGINES, f'Missing base engine: {k}'
print('✓ Base engines configured')
"

# 13. Test condition field validation
python3 -c "
from trap_learning_loop import CONDITION_FIELDS
print('Condition fields:', list(CONDITION_FIELDS.keys())[:10], '...')
assert 'result' in CONDITION_FIELDS, 'Missing result field'
assert 'margin' in CONDITION_FIELDS, 'Missing margin field'
assert 'numerology_day' in CONDITION_FIELDS, 'Missing numerology_day field'
print('✓ Condition fields valid')
"

# 14. Cleanup test trap
curl -X PUT "/live/traps/test-trap-verification/status?status=RETIRED" -H "X-API-Key: KEY"
```

**Critical Invariants (ALWAYS verify these):**
- Trap evaluation runs AFTER grading (6:15 AM > 6:00 AM)
- All adjustments capped at 5% single / 15% cumulative
- Cooldown enforced (24h default between triggers)
- Audit trail in `/data/trap_learning/adjustments.jsonl`
- Base engines (research, esoteric, jarvis, ai) supported

---

## ✅ VERIFICATION CHECKLIST (v19.1 - Complete Learning System)

Run these after ANY change to AutoGrader, PredictionRecord, or signal tracking:

```bash
# 1. Syntax check learning system modules
python -m py_compile auto_grader.py trap_learning_loop.py grader_store.py

# 2. Verify PredictionRecord has all signal fields
python3 -c "
from auto_grader import PredictionRecord
import dataclasses
fields = [f.name for f in dataclasses.fields(PredictionRecord)]
required = ['pick_type', 'sharp_money_adjustment', 'public_fade_adjustment',
            'line_variance_adjustment', 'glitch_signals', 'esoteric_contributions']
for r in required:
    assert r in fields, f'Missing field: {r}'
print(f'✓ PredictionRecord has {len(fields)} fields including all signal tracking')
"

# 3. Check signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions,
  pick_type: .pick_type
}'
# Should show glitch_signals dict, esoteric_contributions dict, pick_type string

# 4. Verify reconciliation functions exist
python3 -c "
from trap_learning_loop import has_recent_trap_adjustment, get_recent_parameter_adjustments
from auto_grader import AutoGrader
grader = AutoGrader.__new__(AutoGrader)
assert hasattr(grader, 'check_trap_reconciliation') or hasattr(AutoGrader, 'check_trap_reconciliation'), 'Missing reconciliation'
print('✓ Reconciliation functions available')
"

# 5. Verify all 28 signals are tracked (spot check)
python3 -c "
from auto_grader import PredictionRecord
# Context Layer (5)
assert hasattr(PredictionRecord, '__dataclass_fields__')
# Check a sample
fields = PredictionRecord.__dataclass_fields__
context_fields = ['defense_adjustment', 'pace_adjustment', 'vacuum_adjustment', 'lstm_adjustment', 'officials_adjustment']
research_fields = ['sharp_money_adjustment', 'public_fade_adjustment', 'line_variance_adjustment']
glitch_field = 'glitch_signals'  # Dict for 6 signals
esoteric_field = 'esoteric_contributions'  # Dict for 14 signals

for f in context_fields + research_fields:
    assert f in fields, f'Missing: {f}'
assert glitch_field in fields, 'Missing glitch_signals'
assert esoteric_field in fields, 'Missing esoteric_contributions'
print('✓ All signal categories tracked (5 context + 3 research + 6 GLITCH + 14 esoteric = 28)')
"

# 6. Test grader status endpoint
curl /live/grader/status -H "X-API-Key: KEY" | jq '{
  available: .available,
  predictions_logged: .predictions_logged,
  storage_path: .storage_path
}'
# Should show available: true, predictions_logged > 0

# 7. Verify pick persistence includes new fields
# (This checks that live_data_router extracts signal data)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '[.game_picks.picks[0] | keys[]] | map(select(startswith("glitch") or startswith("esoteric")))'
# Should show glitch_signals, esoteric_contributions, etc.

# 8. Test all 5 sports signal extraction
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, picks: (.game_picks.count + .props.count), has_signals: (.game_picks.picks[0].glitch_signals != null)}'
done
```

**Critical Invariants (ALWAYS verify these):**
- ALL 28 signals tracked in PredictionRecord (5 context + 3 research + 6 GLITCH + 14 esoteric)
- pick_type field populated (PROP, SPREAD, TOTAL, MONEYLINE, SHARP)
- glitch_signals and esoteric_contributions are dicts (not null)
- Trap-AutoGrader reconciliation prevents conflicting adjustments
- 70% confidence decay applied in bias calculation

---

## ✅ VERIFICATION CHECKLIST (v17.6 - Vortex, Benford, Line History)

Run these after ANY change to Vortex, Benford, or Line History features:

```bash
# 1. Syntax check all modified files
python -m py_compile esoteric_engine.py live_data_router.py database.py daily_scheduler.py

# 2. Test Vortex function directly (Tesla 3-6-9 resonance)
python3 -c "
from esoteric_engine import calculate_vortex_energy
print('3.5 spread:', calculate_vortex_energy(3.5, 'spread'))
print('369 value:', calculate_vortex_energy(369, 'general'))
print('246.5 total:', calculate_vortex_energy(246.5, 'total'))
print('9.5 (Tesla):', calculate_vortex_energy(9.5, 'spread'))
"
# Should show: is_tesla_aligned=True for values with digital root 3, 6, or 9

# 3. Verify Benford now receives 10+ values
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.game_picks.picks[0].glitch_breakdown.benford | {values_count, triggered, distribution}'
# values_count should be 10-25 (not 3)

# 4. Check Vortex in esoteric_reasons
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Vortex")))'
# Should show: "Vortex: TESLA_ALIGNED (root=3)" or similar

# 5. Verify all 3 call sites pass game_bookmakers
grep -n "calculate_pick_score(" live_data_router.py | wc -l
# Should be 4 (1 definition + 3 calls)
grep -n "game_bookmakers=" live_data_router.py | wc -l
# Should be 4 (matching all call sites)

# 6. Test multi-book extraction function
python3 -c "
import sys
sys.path.insert(0, '.')
from live_data_router import _extract_benford_values_from_game
game = {
    'bookmakers': [
        {'markets': [{'key': 'spreads', 'outcomes': [{'point': 3.5}, {'point': -3.5}]},
                     {'key': 'totals', 'outcomes': [{'point': 220.5}, {'point': 220.5}]}]},
        {'markets': [{'key': 'spreads', 'outcomes': [{'point': 3}, {'point': -3}]},
                     {'key': 'totals', 'outcomes': [{'point': 221}, {'point': 221}]}]}
    ]
}
values = _extract_benford_values_from_game(game, 25.5, 3.5, 220.5)
print(f'Extracted {len(values)} values: {values}')
assert len(values) >= 5, f'Expected 5+ values, got {len(values)}'
print('✓ Multi-book extraction working')
"

# 7. Test all 5 sports for Vortex/Benford
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{
      picks: (.game_picks.count + .props.count),
      has_vortex: ([.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Vortex"))) | length > 0),
      benford_values: .game_picks.picks[0].glitch_breakdown.benford.values_count
    }'
done

# 8. Check database tables exist (for line history)
python3 -c "
from database import LineSnapshot, SeasonExtreme, engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('line_snapshots exists:', 'line_snapshots' in tables)
print('season_extremes exists:', 'season_extremes' in tables)
"

# 9. Esoteric Engine Signal Status (should be 10/10)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons, .props.picks[].esoteric_reasons] | flatten | unique | length'
# Should show 10+ unique signal types
```

---

## ✅ VERIFICATION CHECKLIST (v18.2 - Phase 8 Esoteric Signals)

Run these after ANY change to Phase 8 signals (lunar, mercury, rivalry, streak, solar):

```bash
# 1. Syntax check esoteric_engine.py
python -m py_compile esoteric_engine.py

# 2. Test Phase 8 aggregator directly
python3 -c "
from esoteric_engine import get_phase8_esoteric_signals
from datetime import datetime, date
from zoneinfo import ZoneInfo
dt = datetime.now(ZoneInfo('America/New_York'))
d = date.today()
result = get_phase8_esoteric_signals(
    game_datetime=dt,
    game_date=d,
    sport='NBA',
    home_team='Lakers',
    away_team='Celtics',
    pick_type='TOTAL',
    pick_side='Over'
)
print('Phase 8 result:', result)
print('Total boost:', result.get('total_boost'))
print('Reasons:', result.get('reasons'))
"

# 3. Check lunar phase calculation
python3 -c "
from esoteric_engine import calculate_lunar_phase_intensity
from datetime import datetime
from zoneinfo import ZoneInfo
dt = datetime.now(ZoneInfo('America/New_York'))
result = calculate_lunar_phase_intensity(dt)
print('Lunar:', result)
"

# 4. Check Mercury retrograde
python3 -c "
from esoteric_engine import check_mercury_retrograde
from datetime import date
print('Mercury:', check_mercury_retrograde(date.today()))
"

# 5. Check rivalry detection
python3 -c "
from esoteric_engine import calculate_rivalry_intensity
print('Lakers-Celtics:', calculate_rivalry_intensity('NBA', 'Lakers', 'Celtics'))
print('Packers-Bears:', calculate_rivalry_intensity('NFL', 'Packers', 'Bears'))
print('Non-rivalry:', calculate_rivalry_intensity('NBA', 'Kings', 'Wizards'))
"

# 6. Check Phase 8 in production picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {phase8_boost, phase8_reasons, phase8_breakdown}'

# 7. Test all 5 sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  result=$(curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY")
  picks=$(echo "$result" | jq '(.game_picks.count + .props.count)')
  phase8=$(echo "$result" | jq '.game_picks.picks[0].phase8_boost // "null"')
  echo "Picks: $picks, Phase8 boost: $phase8"
done

# 8. Check for timezone errors in logs
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].phase8_error // "none"'
# Should return "none" or null

# 9. Verify env-map OR logic
curl /ops/env-map -H "X-Admin-Key: ADMIN_KEY" | \
  jq '.missing_required'
# Should NOT include SERP_API_KEY if SERPAPI_KEY is set

# 10. Production sanity check (18 checks)
./scripts/prod_sanity_check.sh
# Should pass all 18 checks
```

**Critical Invariants (ALWAYS verify these):**
- `game_datetime` MUST be timezone-aware (use `ZoneInfo`)
- `ref_date` in lunar calculation MUST be timezone-aware (UTC)
- `weather_data` MUST be initialized to `None` before conditional use
- Phase 8 boost added to `esoteric_raw`, not directly to final score
- All 5 signals aggregated via `get_phase8_esoteric_signals()`

---

## Production Proof Checklist (Option A + Integrations)

Use this to prove (not assume) the backend is fully healthy end-to-end and Option A is enforced in production.

### 1) Prove Railway is running the intended commit
**Goal:** runtime build metadata matches the intended git commit.
- In Railway: Service -> Deployments -> confirm deployed commit SHA (expected: `87e70cc`).
- Hit a prod metadata endpoint (build_sha / deploy_version if exposed).
**Pass condition:** prod metadata matches the intended commit, and build_sha changes when you redeploy.

### 2) Integration truth test (not "it didn't crash")
**Goal:** each required integration is configured and exercised.
- Call `/live/debug/integrations`.
- Verify, per integration: `configured=true`, connectivity OK, and `last_success` moves after best-bets.
**Pass condition:** every required integration shows green and timestamps move with real calls.

### 3) Force an end-to-end best-bets run
**Goal:** prove full scoring pipeline executed (not partial/timeouts).
- Call best-bets for each sport supported.
- Verify: `stack_complete=true`, `_timed_out_components` empty, `errors` empty.
- Ensure breakdown fields exist: ai/research/esoteric/jarvis + `context_modifier` + boosts.
**Pass condition:** no critical timeouts on a normal run.

### 4) Prove Option A is enforced in production
**Goal:** confirm final score formula is Option A (context is modifier only).
Inspect 1 prod pick and verify:
- BASE_4 uses AI/Research/Esoteric/Jarvis only.
- Context appears as bounded modifier (cap) with explicit reasons.
- FINAL ~= BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost (within rounding).
**Pass condition:** hand-calc one pick and it matches response fields.

### 5) Hard guard against context-as-engine regression
**Goal:** CI fails if legacy weighted scoring returns.
- Add invariant test that fails if any of these appear in scoring paths:
  - `BASE_5`
  - `ENGINE_WEIGHTS["context"]`
  - `context * weight` logic inside final score calc
- Add CI drift scan (rg/grep) for forbidden tokens in scoring modules.
**Pass condition:** PR cannot merge if context is reintroduced as a weighted engine.

### 6) Diversity + concentration protection active in prod
**Goal:** ensure diversity filters engage and prevent repeats.
- Confirm telemetry counters exist and move when filter drops items:
  - `diversity_player_limited`
  - `diversity_game_limited`
  - `diversity_total_dropped`
**Pass condition:** filter engages when needed and never outputs duplicates beyond policy.

### 7) Caching + TTL behavior under load
**Goal:** avoid stale data and protect paid APIs.
- Call same endpoint twice quickly:
  - first call slower
  - second call faster with cache metadata where applicable
- Verify TTLs match intended policy (best-bets vs normal endpoints).
**Pass condition:** caching matches design.

### 8) Failure-mode smoke test
**Goal:** graceful degradation with deterministic error codes.
- In staging: disable one integration (revoke key or block network).
- Ensure best-bets returns fail-soft (no 500) and debug endpoint shows fail-loud.
**Pass condition:** no 500s, stable error codes, debug shows the exact failure.

### 9) Codex tasks (patch + review only)
1. Diff audit: confirm scoring formula is identical across:
   - scoring contract / pipeline
   - live router
   - any legacy helpers
2. Guardrails PR:
   - CI drift scan for forbidden patterns (BASE_5 / context weighting)
   - unit test that computes final_score and asserts Option A structure
3. Production sanity script:
   - calls best-bets for each sport
   - calls debug integrations
   - asserts: stack_complete true, no timeouts, no duplicates, no 500s

**Shortest path (do first):**
1) `/live/debug/integrations` all green + timestamps move
2) best-bets has `_timed_out_components = []` and `stack_complete = true`
3) manual recompute of one pick’s final_score matches formula

---

## 📊 FEATURE AUDIT TEMPLATE

Use this template when auditing for dormant/orphaned code:

```markdown
## Feature Audit: [FEATURE NAME]

### Status Matrix
| Feature | Implemented | Called | Active in Pipeline |
|---------|-------------|--------|-------------------|
| Feature1 | ✅/❌ | ✅/❌ | ✅/❌ |

### Verification Commands
```bash
# Check if function exists
grep -n "def function_name" *.py

# Check if function is called
grep -rn "function_name(" *.py | grep -v "^def "

# Check if result is used in scoring
grep -n "function_name" live_data_router.py
```

### Integration Point
- File: `live_data_router.py`
- Line: XXXX
- How it affects score: [describe]
```

---

## 🧠 DAILY LEARNING LOOP (AUTOGRADER → LESSON)

**Invariant:** The system must grade picks daily at **6:00 AM ET**, adjust weights/retrain when thresholds are hit, and write a **daily lesson** for the community dashboard.

### What runs automatically
- **Daily audit job (6 AM ET):** grades, audits bias, adjusts weights, triggers retrain.
- **Daily lesson writer:** generates a short lesson summary from audit results.

### v20.2 Stat Types Audited
The audit now processes BOTH prop picks AND game picks:

**PROP Stat Types (per sport):**
- NBA: points, rebounds, assists, threes, steals, blocks, pra
- NFL: passing_yards, rushing_yards, receiving_yards, receptions, touchdowns
- MLB: hits, runs, rbis, strikeouts, total_bases, walks
- NHL: goals, assists, points, shots, saves, blocks
- NCAAB: points, rebounds, assists, threes

**GAME Stat Types (all sports):**
- spread, total, moneyline, sharp

### Files + outputs (source of truth)
- Scheduler + audit flow: `daily_scheduler.py`
- Audit logs: `/data/grader_data/audit_logs/audit_YYYY-MM-DD.json`
- Daily lesson (single day): `/data/grader_data/audit_logs/lesson_YYYY-MM-DD.json`
- Daily lessons log (append-only): `/data/grader_data/audit_logs/lessons.jsonl`

### API endpoints
- `GET /live/grader/daily-lesson` - Get today's lesson
- `GET /live/grader/daily-lesson/latest` - Get most recent lesson
- `GET /live/grader/daily-lesson?days_back=1` - Get lesson from N days ago
- `GET /live/grader/bias/{sport}?stat_type=X` - Get bias for specific stat type
- `POST /live/grader/run-audit` - Manually trigger audit

### Performance Monitoring (v20.2)
Monitor OVER/UNDER bias in daily performance:
```bash
# Check OVER/UNDER split for yesterday
curl -s "/live/picks/grading-summary?date=$(date -v-1d +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '{
    over: {wins: [.graded_picks[] | select(.side == "Over" and .result == "WIN")] | length,
           losses: [.graded_picks[] | select(.side == "Over" and .result == "LOSS")] | length},
    under: {wins: [.graded_picks[] | select(.side == "Under" and .result == "WIN")] | length,
            losses: [.graded_picks[] | select(.side == "Under" and .result == "LOSS")] | length}
  }'
```

**Feb 3, 2026 Benchmark:**
| Market | Win Rate | Status |
|--------|----------|--------|
| SPREAD | 82.1% | ✅ Target |
| UNDER | 81.6% | ✅ Target |
| OVER | 19.1% | ⚠️ Needs recalibration |

### v20.3 Learning Loop Verification (Feb 4, 2026)

**Status: ✅ FULLY OPERATIONAL**

| Component | Status | Evidence |
|-----------|--------|----------|
| Grader Available | ✅ | `available: true` |
| Picks Graded | ✅ | 242 picks from Feb 3 (136W-66L-40P) |
| Weights Initialized | ✅ | All 11 stat types (spread, total, moneyline, sharp + props) |
| Spread Bias | ✅ | 53 samples, 84.9% hit rate |
| Total Bias | ✅ | 32 samples, 56.2% hit rate |
| Factor Correlations | ✅ | 5 categories: pace, vacuum, officials, glitch, esoteric |
| Weight Adjustments | ✅ | `applied: true` (pace -0.0004, vacuum -0.0002, officials -0.0016) |

**Signals Being Tracked for Learning (28 total):**
- **Context Layer**: pace (0.088), vacuum (0.032), officials (0.313)
- **GLITCH**: void_moon (0.155), kp_index (0.0)
- **Esoteric**: numerology (0.114), astro (0.003), fib_alignment (0.146), vortex (0.058), daily_edge (-0.313)

**What This Proves:**
1. v20.2 fix is working - game stat types (spread, total) are being processed
2. Factor correlations are calculated for all 28 signals
3. Weight adjustments are actually applied (not just calculated)
4. The learning loop will automatically recalibrate based on performance data

### Verification (post-deploy gate)
```bash
# Verify scheduler + audit readiness
API_BASE=https://web-production-7b2a.up.railway.app \
API_KEY=YOUR_KEY \
bash scripts/verify_autograder_e2e.sh --mode pre

# Check today's lesson (may 404 before 6AM ET)
curl -s "$API_BASE/live/grader/daily-lesson" -H "X-API-Key: $API_KEY"

# Verify game stat types are being audited (v20.2)
curl -s -X POST "$API_BASE/live/grader/run-audit" -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '.results.results.NBA | {spread: .spread.bias_analysis.sample_size, total: .total.bias_analysis.sample_size}'
# Both should show sample_size > 0
```

### Failure policy
- If lesson file missing before 6 AM ET: return **404** (expected).
- After 6 AM ET: lesson should exist for the day.
- If game stat types show "No graded predictions found" but picks exist: Check `_initialize_weights()` includes game_stat_types (see Lesson 32)

### Learning Loop Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `sample_size: 0` for spread/total | Weights not initialized for game stat types | Check `_initialize_weights()` (Lesson 32) |
| `hit_rate: null` | No graded picks in date range | Check grading-summary endpoint |
| `factor_bias: null` | Signal tracking not wired | Check PredictionRecord fields (v19.1) |
| `weight_adjustments: null` | Bias calculation failed | Check calculate_bias() logs |
| `applied: false` | Trap reconciliation blocked it | Check has_recent_trap_adjustment() |
| Daily lesson empty | No games completed for date | Expected if games still in progress |

### Quick Health Check Command
```bash
# Full learning loop health check (run after any auto_grader changes)
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{
    status: (if .bias.sample_size > 0 then "✅ HEALTHY" else "❌ NO DATA" end),
    sample_size: .bias.sample_size,
    hit_rate: .bias.overall.hit_rate,
    factors_tracked: (.bias.factor_bias | keys | length),
    adjustments_applied: (.weight_adjustments != null)
  }'
```

---

## Codex DNS / GitHub Push Caveat (Feb 3, 2026)

**Problem observed:**
- Codex runtime reported "No DNS configuration available" (from `scutil --dns`).
- Codex could not resolve `github.com` or `api.github.com`, so `git push`/`git fetch` failed inside Codex.
- Mac Wi-Fi was connected; the issue was isolated to Codex's runtime environment.

**What was true at the time:**
- A real commit existed locally: `d152a96` ("docs: lock Option A + add scoring guard").
- The commit was not pushed due to DNS failure inside Codex.
- Therefore, Option A only "lives in the system" after a successful push from a working terminal.

**Manual steps to finalize when Codex cannot push:**
```bash
cd /Users/apple/ai-betting-backend

# 1) Confirm the commit exists locally
git show -s --oneline d152a96

# 2) Push it
git push origin main

# 3) Verify remote has it
git ls-remote origin refs/heads/main | head -n 1
```

**Interpretation:**
- If `git ls-remote` returns a hash matching `d152a96` (or a newer commit that includes it), the change is pushed.
- If DNS still fails in Codex, use the local terminal to push; no Codex DNS fix is required for this workflow.

**Only meaningful DNS test inside Codex:**
```bash
python3 -c 'import socket; print(socket.gethostbyname("github.com"))'
```

**Next hardening steps (after push confirmed):**
1) Ensure guard tests run in CI (e.g., `tests/test_option_a_scoring_guard.py`).
2) Keep a one-line invariant in this file: Option A is canonical and context is modifier-only.
3) Add a drift-scan to `scripts/ci_sanity_check.sh` to block `BASE_5` / context-weighted strings.
# 1770205770
