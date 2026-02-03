# CLAUDE.md - Project Instructions for AI Assistants

## Sister Repositories

| Repo | Purpose | URL |
|------|---------|-----|
| **This repo** | Backend API (Python/FastAPI) | [ai-betting-backend](https://github.com/peterostrander2/ai-betting-backend) |
| **Frontend** | Member dashboard (React/Vite) | [bookie-member-app](https://github.com/peterostrander2/bookie-member-app) |

**Production:** https://web-production-7b2a.up.railway.app

**Frontend Integration Guide:** See `docs/FRONTEND_INTEGRATION.md` for backend→frontend field mapping and pending frontend work.

---

## 🚨 MASTER SYSTEM INVARIANTS (NEVER VIOLATE) 🚨

**READ THIS FIRST BEFORE TOUCHING ANYTHING**

This section contains ALL critical invariants that must NEVER be violated. Breaking any of these will crash production.

---

### INVARIANT 1: Storage Persistence (MANDATORY)

**RULE:** ALL persistent data MUST live on Railway volume at `/data`

**Canonical Storage Locations (DO NOT CHANGE):**
```
/data/  (Railway 5GB persistent volume - NEVER use /data in production)
├── grader/
│   └── predictions.jsonl           ← Picks (grader_store.py) - WRITE PATH
├── grader_data/
│   ├── weights.json                ← Learned weights (data_dir.py)
│   └── predictions.json            ← Weight learning data
└── audit_logs/
    └── audit_{YYYY-MM-DD}.json     ← Daily audits (data_dir.py)
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

### INVARIANT 2: Titanium 3-of-5 Rule (STRICT) - v17.1

**RULE:** `titanium_triggered=true` ONLY when >= 3 of 5 engines >= 8.0

**Implementation:** `core/titanium.py` → `compute_titanium_flag(ai, research, esoteric, jarvis, context)`

**NEVER:**
- 1/5 engines ≥ 8.0 → `titanium=False` (ALWAYS)
- 2/5 engines ≥ 8.0 → `titanium=False` (ALWAYS)

**ALWAYS:**
- 3/5 engines ≥ 8.0 → `titanium=True` (MANDATORY)
- 4/5 engines ≥ 8.0 → `titanium=True` (MANDATORY)
- 5/5 engines ≥ 8.0 → `titanium=True` (MANDATORY)

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

### INVARIANT 3: EST Today-Only Gating (MANDATORY)

**RULE:** ALL picks MUST be for games in today's ET window ONLY

**CANONICAL ET SLATE WINDOW:**
- Start: 00:00:00 ET (midnight) - inclusive
- End: 00:00:00 ET next day (midnight) - exclusive
- Interval: [start, end)

**Single Source of Truth:** `core/time_et.py` (ONLY 2 functions allowed)
```python
from core.time_et import now_et, et_day_bounds

start_et, end_et, et_date = et_day_bounds()  # "2026-01-29"
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

### INVARIANT 4: 5-Engine Scoring (v17.1 - NO DOUBLE COUNTING)

**RULE:** Every pick MUST run through ALL 5 engines + Jason Sim 2.0

**Engine Weights (v17.1):**
```python
AI_WEIGHT = 0.15        # 15% - 8 AI models
RESEARCH_WEIGHT = 0.20  # 20% - Sharp/splits/variance/public fade
ESOTERIC_WEIGHT = 0.15  # 15% - Numerology/astro/fib/vortex/daily
JARVIS_WEIGHT = 0.10    # 10% - Gematria/triggers/mid-spread
CONTEXT_WEIGHT = 0.30   # 30% - Defensive Rank/Pace/Vacuum (Pillars 13-15)
# Total: 0.90 (remaining 0.10 from variable confluence_boost)
```

**Scoring Formula (EXACT):**
```python
BASE = (ai × 0.15) + (research × 0.20) + (esoteric × 0.15) + (jarvis × 0.10) + (context × 0.30)
FINAL = BASE + confluence_boost + jason_sim_boost
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
4. **Context Engine** (v17.1) - Pillars 13-15 aggregated
   - Defensive Rank (50%): Opponent's defensive strength vs position
   - Pace (30%): Game pace vector from team data
   - Vacuum (20%): Usage vacuum from injuries
   - LSTM model receives real context data (not hardcoded)
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
    "context_score": float,      # 0-10 (v17.1 - Pillars 13-15)
    "base_score": float,         # Weighted sum before boosts
    "confluence_boost": float,   # STRONG (+3), MODERATE (+1), DIVERGENT (+0), HARMONIC_CONVERGENCE (+4.5)
    "jason_sim_boost": float,    # Can be negative
    "final_score": float,        # BASE + confluence + jason_sim

    # Breakdown fields (MANDATORY)
    "ai_reasons": List[str],
    "research_reasons": List[str],
    "esoteric_reasons": List[str],
    "jarvis_reasons": List[str],
    "context_reasons": List[str],  # v17.1
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

**GOLD_STAR Hard Gates (v17.1):**
- If tier == "GOLD_STAR", MUST pass ALL gates:
  - `ai_score >= 6.8`
  - `research_score >= 5.5`
  - `jarvis_score >= 6.5`
  - `esoteric_score >= 4.0`
  - `context_score >= 4.0` (v17.1 - Pillars 13-15 must contribute)
- If ANY gate fails, downgrade to "EDGE_LEAN"

**Tier Hierarchy:**
1. TITANIUM_SMASH (3/5 engines ≥ 8.0) - Overrides all others
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

    # All 4 engine scores
    "ai_score",
    "research_score",
    "esoteric_score",
    "jarvis_score",

    # All 4 engine reasons
    "ai_reasons",
    "research_reasons",
    "esoteric_reasons",
    "jarvis_reasons",
]
```

**Storage Format:** JSONL (one pick per line) at `/data/grader/predictions.jsonl`

**Write Path:** `grader_store.persist_pick()` called from `/live/best-bets/{sport}`

**Read Path:** AutoGrader reads from same file via `grader_store.load_predictions()`

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
5. ✅ Ensure all 4 engines + Jason Sim run on every pick
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

**Last Verified:** January 29, 2026 - **ALL 17 CHECKS PASSING ✅**

### Usage

```bash
# Run sanity check
./scripts/prod_sanity_check.sh

# With custom base URL
BASE_URL=https://your-deployment.app ./scripts/prod_sanity_check.sh
```

### What It Checks (17 Total)

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

### Production Verification (Jan 29, 2026)

```bash
================================================
PRODUCTION SANITY CHECK - Master Prompt Invariants
================================================

[1/5] Validating storage persistence...
✓ Storage: resolved_base_dir is set
✓ Storage: is_mountpoint = true
✓ Storage: is_ephemeral = false
✓ Storage: predictions.jsonl exists

[2/5] Validating best-bets endpoint...
✓ Best-bets: filtered_below_6_5 > 0 OR no picks available
✓ Best-bets: minimum returned score >= 6.5
✓ Best-bets: ET filter applied to props (events_before == events_after)
✓ Best-bets: ET filter applied to games (events_before == events_after)

[3/5] Validating Titanium 3-of-4 rule...
✓ Titanium: 3-of-4 rule enforced (no picks with titanium=true and < 3 engines >= 8.0)

[4/5] Validating grader status...
✓ Grader: available = true
✓ Grader: predictions_logged > 0
✓ Grader: storage_path is inside Railway volume

[5/5] Validating ET timezone consistency...
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
        <div>{pick.titanium_count}/4 engines hit Titanium threshold</div>
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
    pick.research_score * 0.30 +
    pick.esoteric_score * 0.20 +
    pick.jarvis_rs * 0.15
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
    console.error(`Invalid Titanium: only ${enginesAbove8}/4 engines >= 8.0`);
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
3. SCORE: 4 engines + Jason Sim 2.0
   - AI (25%) + Research (30%) + Esoteric (20%) + Jarvis (15%)
   - Confluence boost + Jason Sim boost
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
    # Run through 4 engines + Jason Sim
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
   - Score through 4 engines (~2-3 seconds)
   - Filter to >= 6.5, apply contradiction gate
   - Persist to storage
   - Cache response
   - Return to frontend (~5-6 seconds total)

### Scoring Pipeline (4 Engines + Jason Sim)

**Formula:**
```
BASE = (AI × 0.25) + (Research × 0.30) + (Esoteric × 0.20) + (Jarvis × 0.15)
FINAL = BASE + confluence_boost + jason_sim_boost
```

**Engines:**
1. **AI (25%)** - 8 AI models with dynamic calibration
2. **Research (30%)** - Sharp money, line variance, public fade
3. **Esoteric (20%)** - Numerology, astro, fib, vortex, daily edge
4. **Jarvis (15%)** - Gematria triggers, mid-spread goldilocks

**Post-Pick:**
5. **Jason Sim 2.0** - Confluence boost (can be negative)

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

**RULE**: `titanium=true` ONLY when >= 3 of 4 engines >= 8.0

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

## Signal Architecture (5-Engine v17.1)

### Scoring Formula
```
FINAL = (AI × 0.15) + (Research × 0.20) + (Esoteric × 0.15) + (Jarvis × 0.10) + (Context × 0.30)
       + confluence_boost + jason_sim_boost (post-pick)
```

All engines score 0-10. Min output threshold: **6.5** (picks below this are filtered out).

### Engine 1: AI Score (15%)
- 8 AI Models (0-8 scaled to 0-10) - `advanced_ml_backend.py`
- Dynamic calibration: +0.5 sharp present, +0.25-1.0 signal strength, +0.5 favorable spread, +0.25 player data
- LSTM receives real context data (def_rank, pace, vacuum) via context layer

### Engine 2: Research Score (20%)
- Sharp Money (0-3 pts): STRONG/MODERATE/MILD signal from Playbook splits
- Line Variance (0-3 pts): Cross-book spread variance from Odds API
- Public Fade (0-2 pts): Contrarian signal at ≥65% public + ticket-money divergence ≥5%
- Base (2-3 pts): 2.0 default, 3.0 when real splits data present with money-ticket divergence
- Officials adjustment (Pillar 16): OfficialsAnalyzer adjusts based on referee tendencies

### Engine 3: Esoteric Score (15%)
- **See CRITICAL section below for rules**
- Park Factors (Pillar 17, MLB only): Venue-based adjustments

### Engine 4: Jarvis Score (10%)
- Gematria triggers: 2178, 201, 33, 93, 322
- Mid-spread Goldilocks, trap detection
- `jarvis_savant_engine.py`

### Engine 5: Context Score (30%) - v17.1
- Defensive Rank (50%): Opponent's defensive strength vs position type
- Pace (30%): Expected game pace from team velocity data
- Vacuum (20%): Usage vacuum from injury data
- Services: DefensiveRankService, PaceVectorService, UsageVacuumService

### Confluence (v17.1 — with STRONG eligibility gate + HARMONIC_CONVERGENCE)
- Alignment = `1 - abs(research - esoteric) / 10`
- **HARMONIC_CONVERGENCE (+4.5)**: Research ≥ 8.0 AND Esoteric ≥ 8.0 ("Golden Boost" when Math+Magic align)
- **STRONG (+3)**: alignment ≥ 80% **AND** at least one active signal (`jarvis_active`, `research_sharp_present`, or `jason_sim_boost != 0`). If alignment ≥70% but no active signal, downgrades to MODERATE.
- MODERATE (+1): alignment ≥ 60%
- DIVERGENT (+0): below 60%
- PERFECT/IMMORTAL: both ≥7.5 + jarvis ≥7.5 + alignment ≥80%

**Why the gate**: Without it, two engines that are both mediocre (e.g., R=4.0, E=4.0) get 100% alignment and STRONG +3 boost for free, inflating scores without real conviction.

**HARMONIC_CONVERGENCE**: When both Research (market signals) and Esoteric (cosmic signals) score ≥8.0, it represents exceptional alignment between analytical and intuitive sources. This adds +1.5 scaled boost (equivalent to +15 on 100-point).

### CRITICAL: GOLD_STAR Hard Gates (v17.1)

**GOLD_STAR tier requires ALL of these engine minimums. If any fails, downgrade to EDGE_LEAN.**

| Gate | Threshold | Why |
|------|-----------|-----|
| `ai_gte_6.8` | AI ≥ 6.8 | AI models must show conviction |
| `research_gte_5.5` | Research ≥ 5.5 | Must have real market signals (sharp/splits/variance) |
| `jarvis_gte_6.5` | Jarvis ≥ 6.5 | Jarvis triggers must fire |
| `esoteric_gte_4.0` | Esoteric ≥ 4.0 | Esoteric components must contribute |
| `context_gte_4.0` | Context ≥ 4.0 | Pillars 13-15 must contribute (v17.1) |

**Output includes**: `scoring_breakdown.gold_star_gates` (dict of gate→bool), `gold_star_eligible` (bool), `gold_star_failed` (list of failed gate names).

**Where it lives**: `live_data_router.py` `calculate_pick_score()`, after `tier_from_score()` call.

### Tier Hierarchy
| Tier | Score Threshold | Additional Requirements |
|------|----------------|------------------------|
| TITANIUM_SMASH | 3/5 engines ≥ 8.0 | Overrides all other tiers |
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

**Engine Weights (scoring_contract.py):**
```python
ENGINE_WEIGHTS = {
    "ai": 0.15,        # Pillars 1-8
    "research": 0.20,  # Pillars 9-12, 16
    "esoteric": 0.15,  # Pillar 17 + GLITCH
    "jarvis": 0.10,    # Gematria triggers
    "context": 0.30,   # Pillars 13-15
}
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
  context_score: .context_score
}]'
# SHOULD show varying def_rank (1-30), varying pace (94-104), context_score varies

# 2. Check injuries are loaded
curl /live/injuries/NBA -H "X-API-Key: KEY" | jq '{source: .source, count: .count, teams: [.data[].teamName]}'
# SHOULD show source: "playbook", count > 0, teams list

# 3. Check all engines in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  ai: .ai_score,
  research: .research_score,
  esoteric: .esoteric_score,
  jarvis: .jarvis_score,
  context: .context_score,
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
- `alt_data_sources/serp_intelligence.py` - 5 signal detectors mapped to 5 engines
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
detect_situational()    → Context engine  (B2B, rest advantage, travel)
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

**Esoteric Engine Signal Status (10/10 active as of v17.6):**
| Signal | Status | Notes |
|--------|--------|-------|
| Numerology | ✅ ACTIVE | `calculate_generic_numerology()` |
| Astro | ✅ ACTIVE | Vedic astrology |
| Fibonacci | ✅ ACTIVE | `calculate_fibonacci_alignment()` |
| Vortex | ✅ ACTIVE (v17.6) | Tesla 3-6-9 via `calculate_vortex_energy()` |
| Daily Edge | ✅ ACTIVE + VOC (v17.5) | Daily energy score with VOC penalty |
| GLITCH (6 signals) | ✅ ACTIVE | `get_glitch_aggregate()` |
| Biorhythms | ✅ ACTIVE (v17.5) | Props only, player birth cycles |
| Gann Square | ✅ ACTIVE (v17.5) | Games only, sacred geometry |
| Founder's Echo | ✅ ACTIVE (v17.5) | Games only, team gematria |
| Hurst Exponent | ✅ SCHEMA READY (v17.6) | Line history tables created, scheduler jobs active |
| Benford Anomaly | ✅ ACTIVATED (v17.6) | Multi-book aggregation now provides 10+ values |

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
| `alt_data_sources/serp_intelligence.py` | 5-engine signal detection (~823 LOC) | `get_serp_betting_intelligence()`, `get_serp_prop_intelligence()`, `detect_*()` |
| `alt_data_sources/serpapi.py` | SerpAPI client with guardrails (~326 LOC) | `get_search_trend()`, `get_team_buzz()`, `get_player_buzz()`, `get_noosphere_data()` |

**SERP Signal Detectors:**
| Function | Engine | What It Detects |
|----------|--------|-----------------|
| `detect_silent_spike()` | AI | High search volume + low news (insider activity) |
| `detect_sharp_chatter()` | Research | Sharp money, RLM mentions in search |
| `detect_narrative()` | Jarvis | Revenge games, rivalries, playoff implications |
| `detect_situational()` | Context | B2B, rest advantage, travel fatigue |
| `detect_noosphere()` | Esoteric | Search trend velocity between teams |

**SERP Data Flow:**
```
get_serp_betting_intelligence(sport, home, away, pick_side)
  ├── detect_silent_spike(team, sport) → AI boost
  ├── detect_sharp_chatter(team, sport) → Research boost
  ├── detect_narrative(home, away, sport) → Jarvis boost
  ├── detect_situational(team, sport, b2b, rest) → Context boost
  └── detect_noosphere(home, away) → Esoteric boost
        ↓
  cap_total_boost(boosts) → enforce 4.3 total cap
        ↓
  apply_shadow_mode(boosts) → zero if shadow mode (currently OFF)
        ↓
  live_data_router.py:3727 → confluence["boost"] += serp_boost_total
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
- Avoids diluting existing 5-engine weights
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

Run these after ANY change to SERP integration (serp_guardrails.py, serp_intelligence.py, serpapi.py):

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
```

**Critical Invariants (ALWAYS verify these):**
- `SERP_SHADOW_MODE` must be `False` (live mode)
- Boosts must be capped per engine (ai=0.8, research=1.3, esoteric=0.6, jarvis=0.7, context=0.9)
- Total boost must not exceed 4.3
- Quota must be checked before API calls
- All SERP calls wrapped in try/except (fail-soft)

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
