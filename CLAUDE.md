# CLAUDE.md - Project Instructions for AI Assistants

## Sister Repositories

| Repo | Purpose | URL |
|------|---------|-----|
| **This repo** | Backend API (Python/FastAPI) | [ai-betting-backend](https://github.com/peterostrander2/ai-betting-backend) |
| **Frontend** | Member dashboard (React/Vite) | [bookie-member-app](https://github.com/peterostrander2/bookie-member-app) |

**Production:** https://web-production-7b2a.up.railway.app

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
- Start: 00:01:00 ET (12:01 AM) - inclusive
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
    "start_time_et": str,      # ISO timestamp in ET
    "game_status": str,        # "SCHEDULED", "LIVE", "FINAL"
}
```

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

# 6. Run tests
pytest tests/test_titanium_fix.py tests/test_best_bets_contract.py
# MUST pass: 12/12 tests

# 7. Scheduler status (no import errors)
curl /live/scheduler/status -H "X-API-Key: KEY"
# MUST show: available: true (no import errors)
```

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
- `et_day_bounds(date_str)` - Get ET day bounds [00:01:00 ET, 00:00:00 next day ET)
- `is_in_et_day(event_time, date_str)` - Boolean check
- `filter_events_et(events, date_str)` - Filter to ET day, returns (kept, dropped_window, dropped_missing)

**CANONICAL WINDOW:** [00:01:00 ET, 00:00:00 ET next day) - half-open interval

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

**RULE**: Daily slate window is [00:01:00 ET, 00:00:00 ET next day) - half-open interval

**CANONICAL ET SLATE WINDOW:**
- Start: 00:01:00 ET (12:01 AM) - inclusive
- End: 00:00:00 ET next day (midnight) - exclusive
- Events at exactly 00:00:00 (midnight) belong to PREVIOUS day

**Implementation**: `core/time_et.py` → `et_day_bounds()`

**Returns**:
```python
(start_et, end_et, et_date)
# start = 2026-01-28 00:01:00 ET  (12:01 AM)
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
2. The day boundary is **[00:01:00 ET, 00:00:00 ET next day)** — start at 12:01 AM, end exclusive
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

