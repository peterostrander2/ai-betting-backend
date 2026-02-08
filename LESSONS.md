# Lessons Learned

> Mistakes we've made and how to avoid repeating them.
> Update this file whenever a bug or issue teaches us something.

---

## Table of Contents

### Code Quality & Foundations (1-12)
1. [Database Session Handling](#1-database-session-handling)
2. [Hardcoded None Parameters](#2-hardcoded-none-parameters)
3. [Data Accumulation Delays](#3-data-accumulation-delays)
4. [Function Name Confusion](#4-function-name-confusion)
5. [Import Management](#5-import-management)
6. [Error Handling Patterns](#6-error-handling-patterns)
7. [Testing with No Data](#7-testing-with-no-data)
8. [External Data Without Interpretation Layer](#8-external-data-without-interpretation-layer)
9. [Alt Data Modules Implemented But Not Wired](#9-alt-data-modules-implemented-but-not-wired)
10. [Timezone-Aware vs Naive Datetime Comparisons](#10-timezone-aware-vs-naive-datetime-comparisons)
11. [Environment Variable OR Logic for Alternatives](#11-environment-variable-or-logic-for-alternatives)
12. [Variable Initialization Before Conditional Use](#12-variable-initialization-before-conditional-use)

### Integration & Data (13-19) — v17.x
13. [Scope Issues with Context Calculations](#13-scope-issues-with-context-calculations)
14. [NCAAB Team Name Matching](#14-ncaab-team-name-matching)
15. [ESPN Officials Integration](#15-espn-officials-integration)
16. [NHL Team Name Accent Normalization](#16-nhl-team-name-accent-normalization)
17. [ESPN Data Expansion for Cross-Validation](#17-espn-data-expansion-for-cross-validation)
18. [NCAAB Team Coverage Expansion](#18-ncaab-team-coverage-expansion)
19. [MLB SPORT_MAPPING Bug](#19-mlb-sport_mapping-bug)

### Signals & Gates (20-28) — v17.x-v19.x
20. [Contradiction Gate Silent Failure](#20-contradiction-gate-silent-failure)
21. [SERP Shadow Mode Default](#21-serp-shadow-mode-default)
22. [pick_type Value Mismatch](#22-pick_type-value-mismatch)
23. [Dormant Signal Activation Pattern](#23-dormant-signal-activation-pattern)
24. [Benford Multi-Book Aggregation Fix](#24-benford-multi-book-aggregation-fix)
25. [Function Parameter Threading Pattern](#25-function-parameter-threading-pattern)
26. [Officials Tendency Integration Pattern](#26-officials-tendency-integration-pattern)
27. [Trap Learning Loop Architecture](#27-trap-learning-loop-architecture)
28. [Complete Learning System Pattern](#28-complete-learning-system-pattern)

### Datetime & Variables (29-31) — v18.x
29. [Timezone-Aware vs Naive Datetime](#29-timezone-aware-vs-naive-datetime)
30. [Environment Variable OR Logic](#30-environment-variable-or-logic)
31. [Variable Initialization Before Conditional](#31-variable-initialization-before-conditional)

### Learning Loop (32-38) — v20.x
32. [Auto Grader Weights Must Include All Types](#32-auto-grader-weights-must-include-all-types)
33. [OVER Bet Performance Tracking](#33-over-bet-performance-tracking)
34. [Verifying the Learning Loop is Working](#34-verifying-the-learning-loop-is-working)
35. [Grading Pipeline Missing SHARP/ML/PROP](#35-grading-pipeline-missing-sharpmlprop)
36. [Audit Drift Scan Line Number Filters](#36-audit-drift-scan-line-number-filters)
37. [Endpoint Matrix Sanity Math Formula](#37-endpoint-matrix-sanity-math-formula)
38. [OVER/UNDER Totals Bias Calibration](#38-overunder-totals-bias-calibration)

### Frontend & Shell (39-40) — v20.4
39. [Frontend Tooltip Alignment](#39-frontend-tooltip-alignment)
40. [Shell Variable Export for Python](#40-shell-variable-export-for-python)

### Grading & Datetime Fixes (41-48) — v20.5
41. [SHARP Pick Grading Bug](#41-sharp-pick-grading-bug)
42. [Undefined PYTZ_AVAILABLE Variable](#42-undefined-pytz_available-variable)
43. [Naive vs Aware Datetime Comparison](#43-naive-vs-aware-datetime-comparison)
44. [Date Window Math Error](#44-date-window-math-error)
45. [Grader Performance Same Bug](#45-grader-performance-same-bug)
46. [Unsurfaced Scoring Adjustments](#46-unsurfaced-scoring-adjustments)
47. [Script-Only Env Vars Registration](#47-script-only-env-vars-registration)
48. [Python Heredoc __file__ Path Bug](#48-python-heredoc-__file__-path-bug)

### Production Fixes (49-54) — v20.6-v20.8
49. [Props Timeout — Shared Budget Starvation](#49-props-timeout--shared-budget-starvation)
50. [Empty Description Fields in Payload](#50-empty-description-fields-in-payload)
51. [Score Inflation from Unbounded Boosts](#51-score-inflation-from-unbounded-boosts)
52. [Jarvis Baseline Not a Bug](#52-jarvis-baseline-not-a-bug)
53. [SERP Sequential Bottleneck](#53-serp-sequential-bottleneck)
54. [Props Indentation Bug — Dead Code](#54-props-indentation-bug--dead-code)

### Dormant Features (55) — v20.12
55. [Officials Fallback to Tendency Database](#55-officials-fallback-to-tendency-database-pillar-16)

---

## 1. Database Session Handling

### The Mistake
Leaving database connections open, causing connection pool exhaustion.

### The Fix
**ALWAYS** use the context manager pattern:

```python
# CORRECT
from database import get_db, DB_ENABLED

if DB_ENABLED:
    with get_db() as db:
        if db:
            result = get_line_history_values(db, event_id, "spread", 30)

# WRONG - connection never closed
db = get_db()
result = get_line_history_values(db, event_id, "spread", 30)
```

### Rule
> **INVARIANT**: Every `get_db()` call MUST use `with` context manager.

---

## 2. Hardcoded None Parameters

### The Mistake
In v17.6, we added `line_history` parameter to `get_glitch_aggregate()` but hardcoded `line_history=None` in the caller at `live_data_router.py:3347`. The function existed but was never actually used.

### The Evidence
```python
# This was the problem - parameter existed but was always None
glitch_result = get_glitch_aggregate(
    ...
    line_history=None,  # <- HARDCODED! Never wired to actual data
    ...
)
```

### The Fix
Always wire new parameters to actual data sources when adding them:

```python
# Fetch the data BEFORE the call
_line_history = None
if DB_ENABLED:
    with get_db() as db:
        if db:
            _line_history = get_line_history_values(db, event_id, "spread", 30)

# Pass the actual data
glitch_result = get_glitch_aggregate(
    ...
    line_history=_line_history,  # <- Now wired to real data
    ...
)
```

### Rule
> **INVARIANT**: When adding a parameter to a function, grep for all callers and update them. Never leave `parameter=None` hardcoded.

### Checklist for New Parameters
- [ ] Added parameter to function signature
- [ ] Added data fetch logic before function call
- [ ] Updated all callers (grep for function name)
- [ ] Verified data flows end-to-end

---

## 3. Data Accumulation Delays

### The Mistake
Expecting new signals to work immediately after deployment. They won't.

### The Reality
| Signal | Data Source | Time to Activate |
|--------|-------------|------------------|
| Hurst Exponent | line_snapshots | ~5 hours (needs 10+ snapshots) |
| Fibonacci Retracement | season_extremes | ~24 hours (daily 5 AM job) |
| Benford Anomaly | line values | Immediate (uses current lines) |

### The Fix
1. Document expected delays in deployment notes
2. Add "no data" handling that fails gracefully
3. Don't panic when new signals show empty results

### Rule
> **INVARIANT**: New database-dependent signals will show "no data" for 24-48 hours. This is expected, not a bug.

---

## 4. Function Name Confusion

### The Mistake
Confusing `calculate_fibonacci_alignment()` (Jarvis) with `calculate_fibonacci_retracement()` (Esoteric).

### The Difference
| Function | What It Does | Example |
|----------|--------------|---------|
| `calculate_fibonacci_alignment()` | Checks if line IS a Fibonacci number | Line 13 -> "Fib number!" |
| `calculate_fibonacci_retracement()` | Checks if line is at Fib % of range | Line at 61.8% of season range |

### The Fix
Use descriptive comments when calling these functions:

```python
# Jarvis: Is the line itself a Fibonacci number?
fib_align = jarvis.calculate_fibonacci_alignment(line)

# Esoteric: Is the line at a Fibonacci retracement level?
fib_retrace = calculate_fibonacci_retracement(line, season_high, season_low)
```

### Rule
> **INVARIANT**: When two functions have similar names, add a comment explaining which one you're using and why.

---

## 5. Import Management

### The Mistake
Adding imports in random places, making them hard to find and causing circular import issues.

### The Fix
Group imports by source and add new ones to existing groups:

```python
# Standard library
import os
from datetime import datetime

# Third-party
from fastapi import FastAPI

# Local - Database
from database import get_db, get_line_history_values, get_season_extreme, DB_ENABLED

# Local - Esoteric
from esoteric_engine import get_glitch_aggregate, calculate_fibonacci_retracement
```

### Rule
> **INVARIANT**: When adding imports, first check if there's an existing import from that module and extend it.

---

## 6. Error Handling Patterns

### The Mistake
Letting database errors crash the entire request.

### The Fix
**ALWAYS** wrap optional signal calculations in try/except:

```python
# CORRECT
try:
    if DB_ENABLED:
        with get_db() as db:
            if db:
                result = some_db_operation(db)
except Exception as e:
    logger.debug("Operation skipped: %s", e)  # Debug, not error
    result = None  # Graceful fallback

# WRONG - crashes entire request if DB fails
result = some_db_operation(db)
```

### Rule
> **INVARIANT**: Esoteric signals are OPTIONAL. A failure in one signal must never crash the request. Use try/except with debug logging.

---

## 7. Testing with No Data

### The Mistake
Writing tests that expect signals to return data when the database is empty.

### The Fix
Tests should verify:
1. Function returns valid structure (even if empty)
2. No exceptions thrown with None inputs
3. Graceful handling of missing data

```python
def test_hurst_no_data():
    """Hurst should return None when no line history exists."""
    result = calculate_hurst_exponent(None)
    assert result is None  # Not an error, just no data

def test_hurst_insufficient_data():
    """Hurst needs 10+ data points."""
    result = calculate_hurst_exponent([1, 2, 3])  # Only 3 points
    assert result is None  # Not enough data
```

### Rule
> **INVARIANT**: All signal functions must handle None and insufficient data gracefully. Never assume data exists.

---

## 8. External Data Without Interpretation Layer

### The Mistake
Pillar 16 (Officials) had ESPN data source wired (referee names) but returned 0.0 adjustment because there was no interpretation layer - no data about what those referee names MEAN for betting.

### The Evidence
```python
# ESPN provided: {"lead_official": "Scott Foster", ...}
# But OfficialsService just returned: (0.0, [])
# Because it had no data about Scott Foster's tendencies
```

### The Fix
Create an interpretation/tendency database that maps referee names to betting-relevant metrics:

```python
# officials_data.py
REFEREE_TENDENCIES = {
    "NBA": {
        "Scott Foster": {
            "over_tendency": 0.54,  # 54% of games go over
            "foul_rate": "HIGH",
            "home_bias": 0.02,
        },
        # ... more refs
    }
}

# Now the adjustment can be calculated
def calculate_officials_adjustment(sport, ref_name, pick_type, pick_side):
    tendency = get_referee_tendency(sport, ref_name)
    if tendency["over_tendency"] > 0.52 and pick_side == "Over":
        return +0.2, f"Officials: {ref_name} over tendency (54%)"
```

### Rule
> **INVARIANT**: External data (names, IDs) is useless without an interpretation layer that converts it to betting-relevant signals. When adding a new data source, also add the lookup/tendency database.

### Checklist for New Data Sources
- [ ] Data source provides raw identifiers (names, IDs)
- [ ] Interpretation database maps identifiers → betting metrics
- [ ] Adjustment function converts metrics → score changes
- [ ] Output includes human-readable reasons

---

## 9. Alt Data Modules Implemented But Not Wired

### The Mistake
In v17.8 and earlier, three alt_data modules were fully implemented but their results weren't flowing into the scoring pipeline:
- **Weather**: Fetched but bypassed engines, going directly to final_score
- **Altitude**: 62-venue registry existed but was never called
- **Travel/B2B**: ESPN `rest_days_by_team` computed but never passed to travel module

### The Evidence
```python
# Weather was applied to final_score, bypassing engine weights
if _game_weather and _game_weather.get("available"):
    final_score = final_score + _wmod  # Wrong! Bypasses research weight

# Altitude service existed but was never called
class StadiumAltitudeService:  # Dead code!
    ...

# ESPN computed rest_days but never passed it anywhere
_rest_days_by_team = {...}  # Orphaned data
```

### The Fix (v17.9)
Wire each module to the appropriate engine score:

| Signal | Target Score | Why |
|--------|--------------|-----|
| Weather | research_score | Market doesn't fully price weather |
| Altitude | esoteric_score | Non-traditional factor |
| Travel/B2B | context_score | Game context factor |

```python
# Weather → research_score (scaled and capped)
if _game_weather:
    weather_adj = max(-0.5, _wmod * 0.5)
    research_raw += weather_adj

# Altitude → esoteric_score
altitude_adj, reasons = StadiumAltitudeService.get_altitude_adjustment(...)
esoteric_raw += altitude_adj

# Travel/B2B → context_score (via compute_context_modifiers)
if _ctx_mods.get("travel_fatigue"):
    context_raw += travel_adj
```

### Rule
> **INVARIANT**: When implementing alt_data modules, follow the full data flow: (1) Fetch/compute data, (2) Pass to context/compute function, (3) Apply adjustment to appropriate engine score, (4) Add reason to engine's reasons list. Dead code is worse than no code.

### Checklist for Alt Data Wiring
- [ ] Data is fetched or computed
- [ ] Data is passed to the appropriate service/function
- [ ] Adjustment is applied to correct engine (context/esoteric/research)
- [ ] Reasons are added to the engine's reasons list
- [ ] Old/duplicate applications are removed

---

## 10. Timezone-Aware vs Naive Datetime Comparisons

### The Mistake
In Phase 8 (v18.2), the lunar phase calculation failed with:
```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

The reference date `datetime(2000, 1, 1, 18, 14)` was timezone-naive, but `game_datetime` from API parsing was timezone-aware.

### The Evidence
```python
# BUG - ref_date is naive, game_datetime is aware
ref_date = datetime(2000, 1, 1, 18, 14)  # No timezone!
days_since = (game_datetime - ref_date).total_seconds() / 86400  # CRASH!
```

### The Fix
Always make reference dates timezone-aware when comparing to aware datetimes:

```python
from zoneinfo import ZoneInfo

# CORRECT - ref_date is now timezone-aware (UTC)
ref_date = datetime(2000, 1, 1, 18, 14, tzinfo=ZoneInfo("UTC"))

# Also ensure game_datetime has timezone
if game_datetime.tzinfo is None:
    game_datetime = game_datetime.replace(tzinfo=ZoneInfo("UTC"))

days_since = (game_datetime - ref_date).total_seconds() / 86400  # Works!
```

### Rule
> **INVARIANT**: When comparing datetimes, BOTH must be timezone-aware OR both must be naive. In this system (ET-only), always use timezone-aware with `ZoneInfo("America/New_York")` or `ZoneInfo("UTC")`.

### Quick Check
```python
# Test if datetime is aware
is_aware = dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
```

---

## 11. Environment Variable OR Logic for Alternatives

### The Mistake
The `/ops/env-map` endpoint showed `missing_required: ["SERP_API_KEY"]` even though `SERPAPI_KEY` was set. The integration contract defined both as alternatives (either one satisfies the requirement), but the code used AND logic.

### The Evidence
```python
# BUG - AND logic (ALL must be set)
is_configured = all(os.getenv(ev) for ev in env_vars_list)

# With env_vars_list = ["SERPAPI_KEY", "SERP_API_KEY"]
# If SERPAPI_KEY is set but SERP_API_KEY is not, is_configured = False (WRONG!)
```

### The Fix
Use OR logic for alternative env vars:

```python
# CORRECT - OR logic (ANY can satisfy)
any_set = any(bool(os.getenv(ev)) for ev in env_vars_list)

# With env_vars_list = ["SERPAPI_KEY", "SERP_API_KEY"]
# If either is set, any_set = True (CORRECT!)
```

### The Pattern
```python
# Track which integrations have at least one env var set
integration_satisfied = {}
for name, meta in CONTRACT_INTEGRATIONS.items():
    env_vars_list = meta.get("env_vars", [])
    any_set = any(bool(os.getenv(ev)) for ev in env_vars_list)
    integration_satisfied[name] = any_set

# For missing_required: only flag if integration has NO env vars set
missing_required = sorted([
    k for k, v in env_map.items()
    if v["required"] and not v["is_set"]
    and not all(integration_satisfied.get(i, False) for i in v["integrations"])
])
```

### Rule
> **INVARIANT**: When an integration lists multiple env vars as alternatives (e.g., `["SERPAPI_KEY", "SERP_API_KEY"]`), use OR logic. The integration is satisfied if ANY of its env vars is set.

---

## 12. Variable Initialization Before Conditional Use

### The Mistake
NFL best-bets crashed with `NameError: name 'weather_data' is not defined` because `weather_data` was only set inside a conditional block, but used later unconditionally.

### The Evidence
```python
# BUG - weather_data only set inside condition
if is_outdoor_sport and venue_id:
    weather_data = fetch_weather(venue_id)  # Only set here!

# ... later in code ...
if weather_data and weather_data.get("available"):  # CRASH! weather_data undefined
    apply_weather_boost()
```

### The Fix
Initialize variables to `None` BEFORE conditional blocks:

```python
# CORRECT - Initialize before condition
weather_data = None  # Initialize first!

if is_outdoor_sport and venue_id:
    weather_data = fetch_weather(venue_id)

# ... later in code ...
if weather_data and weather_data.get("available"):  # Safe! weather_data is None if not fetched
    apply_weather_boost()
```

### Rule
> **INVARIANT**: Any variable used after a conditional block MUST be initialized before the block. This applies especially in nested functions where variables may be used across multiple code paths.

### Checklist for New Variables
- [ ] Is this variable used outside the block where it's first assigned?
- [ ] If yes, initialize it (usually to `None`) before the block
- [ ] Check all code paths that might skip the assignment

---

---

## 13. Scope Issues with Context Calculations

### The Mistake
Context values (def_rank, pace, vacuum) were only calculated for PROP picks, not GAME picks. GAME picks got default values because the context lookup was inside the `if pick_type == "PROP"` block.

### The Fix
Move context calculations (Pillars 13-15) BEFORE the pick_type branch so they run for ALL pick types. Verify all pick types show real values in debug output.

### Rule
> **INVARIANT**: Shared calculations must run OUTSIDE type-specific blocks. Move shared context setup before the pick_type branch.

---

## 14. NCAAB Team Name Matching

### The Mistake
NCAAB team names from Odds API include mascots ("North Carolina Tar Heels") but context layer uses short names ("North Carolina"). Aggressive fuzzy matching caused false positives ("Alabama St Hornets" matched "Alabama").

### The Fix
Added `NCAAB_TEAM_MAPPING` dict with 80+ mappings and `MASCOT_SUFFIXES` whitelist for conservative fuzzy matching. Only strip suffixes that are known mascots.

### Rule
> **INVARIANT**: Always check API team name format vs data format when adding new sports/data. Use explicit mappings for common cases, conservative fuzzy matching for edge cases.

---

## 15. ESPN Officials Integration

### The Mistake
Pillar 16 (Officials) code was ready but had no data source. Placeholder code had empty strings for official names.

### The Fix
Created `alt_data_sources/espn_lineups.py` using ESPN Hidden API (free, no auth). Prefetch officials for all games in batch, store in `_officials_by_game` lookup. Scoring function accesses via closure.

### Rule
> **INVARIANT**: When adding a new pillar/signal, ensure the data source is wired end-to-end. Placeholder code with empty strings is dead code.

---

## 16. NHL Team Name Accent Normalization

### The Mistake
ESPN returns "Montréal Canadiens" (with accent) but context data uses "Montreal Canadiens" (without), causing lookup misses.

### The Fix
Added `NHL_ACCENT_MAP` to `standardize_team()` in `context_layer.py`.

### Rule
> **INVARIANT**: When integrating external APIs, check for Unicode character variants (accents, special characters) that may differ from local data.

---

## 17. ESPN Data Expansion for Cross-Validation

### The Mistake
ESPN officials working but not using rich data available in ESPN's summary endpoint (odds, injuries, venue, weather).

### The Fix
Expanded ESPN integration: batch fetch enriched data, cross-validate odds (+0.25-0.5 research boost when confirmed), merge injuries, use venue/weather as fallback.

### Rule
> **INVARIANT**: When a free API offers rich data, USE ALL OF IT. Cross-validate primary data sources with secondary sources. Batch parallel fetches to avoid N+1 problems.

---

## 18. NCAAB Team Coverage Expansion

### The Mistake
NCAAB defensive data only covered Top 50 teams. Mid-major tournament teams (VCU, Dayton, Murray State) got default values.

### The Fix
Expanded from 50 to 75 teams. Added 25 mid-major tournament regulars. Updated `DefensiveRankService.get_total_teams()`.

### Rule
> **INVARIANT**: When adding team data, include tournament-relevant mid-majors. Update team count constants when expanding data.

---

## 19. MLB SPORT_MAPPING Bug

### The Mistake
MLB ESPN data wasn't fetched. Typo in `SPORT_MAPPING`: `"mlb": "mlb"` instead of `"league": "mlb"`.

### The Fix
Fixed the key name to `"league": "mlb"`. Verified all sports after modifying sport mappings.

### Rule
> **INVARIANT**: Verify all dictionary keys are consistent across mappings. Test ALL sports after adding/modifying sport mappings.

---

## 20. Contradiction Gate Silent Failure

### The Mistake
Both Over AND Under returned for same totals. `filter_contradictions()` returned empty `{}` instead of proper dict with `contradictions_detected` key, causing silent `KeyError` caught by try/except fallback.

### The Fix
Return proper dict structure when empty: `{"contradictions_detected": 0, "picks_dropped": 0, "contradiction_groups": []}`.

### Rule
> **INVARIANT**: Always return consistent dict structure, not empty `{}`. Log exceptions in fallback blocks — don't swallow silently.

---

## 21. SERP Shadow Mode Default

### The Mistake
SERP intelligence was configured with `SERP_SHADOW_MODE=True` by default, which zeroed all boosts. User wanted LIVE MODE.

### The Fix
Changed default to `SERP_SHADOW_MODE = False` in `core/serp_guardrails.py`.

### Rule
> **INVARIANT**: Always verify `SERP_SHADOW_MODE` default is `False` (live mode). Check debug output shows `shadow_mode: false`.

---

## 22. pick_type Value Mismatch

### The Mistake
Phase 1 dormant signals checked `pick_type == "GAME"`, but game picks use "SPREAD", "MONEYLINE", or "TOTAL". The value "GAME" is only a fallback.

### The Fix
Use `_is_game_pick = pick_type in ("GAME", "SPREAD", "MONEYLINE", "TOTAL", "SHARP")` pattern.

### Rule
> **INVARIANT**: Before using `pick_type` in conditions, trace where it's set. Game picks: "SPREAD", "MONEYLINE", "TOTAL", "SHARP". Prop picks: "PROP".

---

## 23. Dormant Signal Activation Pattern

### The Mistake
`esoteric_engine.py` contained fully implemented signals (Biorhythms, Gann Square, Founder's Echo) that were never called from `calculate_pick_score()`.

### The Fix
Added integration points after GLITCH, before esoteric_score clamp. Added with proper `_is_game_pick` guard, boosted `esoteric_raw` (not esoteric_score directly), and added to `esoteric_reasons`.

### Rule
> **INVARIANT**: When implementing signals, verify they're called from the scoring pipeline. Use `grep -r "function_name(" live_data_router.py` to confirm wiring.

---

## 24. Benford Multi-Book Aggregation Fix

### The Mistake
Benford's Law anomaly detection NEVER triggered because only 3 values were passed (prop_line, spread, total) but it requires 10+ for statistical significance.

### The Fix
Extract multi-book lines from `game.bookmakers[]` array (Odds API returns 5-10 sportsbooks, giving 10-25 unique values).

### Rule
> **INVARIANT**: Statistical tests have minimum sample size requirements. Verify the data volume before assuming a signal is "working." Benford needs 10+ values.

---

## 25. Function Parameter Threading Pattern

### The Mistake
Added `game_bookmakers=None` to `calculate_pick_score()` but only updated 1 of 3 call sites. The other 2 passed `None`.

### The Fix
Grep for all call sites FIRST: `grep -n "calculate_pick_score(" live_data_router.py`. Update ALL call sites in the same commit.

### Rule
> **INVARIANT**: When adding parameters to multi-call-site functions, update ALL call sites in the same commit. Grep before and after changes to verify count.

---

## 26. Officials Tendency Integration Pattern

### The Mistake
Pillar 16 had ESPN data wired but always returned 0.0 adjustment because there was no interpretation layer mapping referee names to betting-relevant metrics.

### The Fix
Created `officials_data.py` with referee tendency database (NBA 25 refs, NFL 17 crews, NHL 15 refs). Added `get_officials_adjustment()` to compute tendency-based adjustments.

### Rule
> **INVARIANT**: External data (names, IDs) is useless without an interpretation layer. When adding a data source, also add the lookup/tendency database.

---

## 27. Trap Learning Loop Architecture

### The Mistake
Manual weight adjustments based on observed patterns required human intervention and weren't systematically tracked.

### The Fix
Created hypothesis-driven learning system: `trap_learning_loop.py` + `trap_router.py`. Scheduler job at 6:15 AM ET. Safety guards: 5% single / 15% cumulative caps, 24h cooldown, 0.7x decay factor.

### Rule
> **INVARIANT**: Learning systems must have safety bounds. Always cap single and cumulative changes, enforce cooldowns, and maintain audit trails.

---

## 28. Complete Learning System Pattern

### The Mistake
After implementing AutoGrader and Trap Learning Loop, discovered 15 gaps where learning should happen but doesn't — signals not tracked, no pick_type differentiation, possible conflicts.

### The Fix
Expanded `PredictionRecord` with ALL 28 signal tracking fields. Added 70% confidence decay, pick_type breakdown, and 24h Trap-AutoGrader reconciliation.

### Rule
> **INVARIANT**: Every signal contribution MUST be tracked for learning. Two learning systems MUST NOT conflict. Use reconciliation windows to prevent conflicting adjustments.

---

## 29. Timezone-Aware vs Naive Datetime

### The Mistake
Phase 8 lunar phase calculation crashed: `TypeError: can't subtract offset-naive and offset-aware datetimes`. Reference date had no timezone.

### The Fix
Use `ZoneInfo("UTC")` for reference dates, `ZoneInfo("America/New_York")` for game times. Both sides of datetime arithmetic must match.

### Rule
> **INVARIANT**: When doing datetime arithmetic, BOTH datetimes must be timezone-aware. Use `core.time_et.now_et()` as single source of truth.

---

## 30. Environment Variable OR Logic

### The Mistake
SERP API integration failed because env var check used AND logic when alternatives (`SERPAPI_KEY` and `SERP_API_KEY`) should use OR logic.

### The Fix
Use `any()` for ALTERNATIVE env vars, `all()` for REQUIRED env vars.

### Rule
> **INVARIANT**: When an integration lists multiple env vars as alternatives, use OR logic (`any()`). The integration is satisfied if ANY env var is set.

---

## 31. Variable Initialization Before Conditional

### The Mistake
Production crashed with `NameError: name 'weather_data' is not defined` because it was only assigned inside a conditional block.

### The Fix
Initialize to `None` before conditional blocks: `weather_data = None`.

### Rule
> **INVARIANT**: Any variable used after a conditional block MUST be initialized before the block.

---

## 32. Auto Grader Weights Must Include All Types

### The Mistake
Auto grader returned "No graded predictions found" for ALL game picks because `_initialize_weights()` only created entries for PROP stat types, not GAME stat types (spread, total, moneyline, sharp).

### The Fix
Initialize BOTH prop stat types AND game stat types: `game_stat_types = ["spread", "total", "moneyline", "sharp"]`.

### Rule
> **INVARIANT**: When adding new pick types, ensure weights are initialized for them in `_initialize_weights()`. Verify with `/live/grader/bias/{sport}?stat_type=X`.

---

## 33. OVER Bet Performance Tracking

### The Mistake
Analysis revealed OVER 19.1% win rate vs UNDER 81.6%. The system was overvaluing OVER bets — 38 of 66 total losses (57.6%) came from OVER picks.

### The Fix
With v20.2 fix, auto grader can properly analyze totals bias. Learning loop adjusts weights to reduce OVER confidence.

### Rule
> **INVARIANT**: Monitor OVER/UNDER split in daily grading reports. Market-type-specific bias must be tracked and corrected.

---

## 34. Verifying the Learning Loop is Working

### The Mistake
After fixing auto grader weights, needed to verify the entire learning loop was functioning end-to-end — not just that data existed, but that adjustments were being applied.

### The Fix
Verified: grader status, grading summary, bias calculation for ALL stat types, weight adjustments with `applied: true`, and factor correlations for all 28 signals.

### Rule
> **INVARIANT**: After any `auto_grader.py` change, verify: (1) sample_size > 0, (2) `applied: true` in weight_adjustments, (3) factor_bias shows all 28 signals tracked.

---

## 35. Grading Pipeline Missing SHARP/MONEYLINE/PROP

### The Mistake
SHARP picks had 0% hit rate (all graded as PUSH), MONEYLINE barely sampled, PROPS absent from learning loop.

### The Fix
Added `elif "sharp" in pick_type_lower` handling. Extracted `picked_team` from selection fields. Synced `run_daily_audit()` prop_stat_types with `_initialize_weights()`. Added direct format + market suffix stripping to STAT_TYPE_MAP.

### Rule
> **INVARIANT**: Test grading for ALL pick types after changes (SPREAD, TOTAL, MONEYLINE, SHARP, PROP). A 0% hit rate may mean grading is broken, not predictions.

---

## 36. Audit Drift Scan Line Number Filters

### The Mistake
Go/no-go failed because line number filter in `audit_drift_scan.sh` didn't match actual code locations after code shifted.

### The Fix
Updated filter patterns to include new line ranges. Added comments documenting what each filter allows.

### Rule
> **INVARIANT**: After ANY change to `live_data_router.py`, re-run `audit_drift_scan.sh` locally. Line-based filters break when code shifts.

---

## 37. Endpoint Matrix Sanity Math Formula

### The Mistake
`endpoint_matrix_sanity.sh` math check failed because formula was missing `ensemble_adjustment`, `live_adjustment`, and `totals_calibration_adj`.

### The Fix
Updated jq formula to include all adjustments with `// 0` for null handling. Added 10.0 cap.

### Rule
> **INVARIANT**: When adding new boosts/adjustments, update ALL THREE: (1) pick payload, (2) sanity script formula, (3) CLAUDE.md canonical formula.

---

## 38. OVER/UNDER Totals Bias Calibration

### The Mistake
OVER 19.1% vs UNDER 81.6% hit rate. No mechanism to apply learned bias corrections to totals scoring.

### The Fix
Added `TOTALS_SIDE_CALIBRATION` to `scoring_contract.py`: `over_penalty: -0.75`, `under_boost: +0.75`. Applied when `pick_type == "TOTAL"`.

### Rule
> **INVARIANT**: When learning loop reveals systematic bias, add calibration adjustments to `scoring_contract.py` with clear documentation and surfaced fields.

---

## 39. Frontend Tooltip Alignment

### The Mistake
Frontend tooltips showed wrong engine weights (AI 15%, Research 20%, Esoteric 15%, Jarvis 10%, Context 30%) that didn't match backend (AI 25%, Research 35%, Esoteric 20%, Jarvis 20%, Context modifier).

### The Fix
Updated `PropsSmashList.jsx` and `GameSmashList.jsx` tooltips to match `scoring_contract.py`.

### Rule
> **INVARIANT**: When changing backend scoring, IMMEDIATELY update frontend tooltips. Always check `scoring_contract.py` for authoritative weights.

---

## 40. Shell Variable Export for Python

### The Mistake
`perf_audit_best_bets.sh` tried to connect to `None` as hostname because shell variables aren't inherited by Python subprocesses without `export`.

### The Fix
Use `export VAR=value` not just `VAR=value` when Python subprocesses need the variable.

### Rule
> **INVARIANT**: When shell scripts call Python, variables MUST be exported. `VAR=value` = current shell only. `export VAR=value` = children see it too.

---

## 41. SHARP Pick Grading Bug

### The Mistake
SHARP picks showing 0% hit rate because `line` field contained `line_variance` (movement amount), not the actual spread. Grading treated variance as spread.

### The Fix
Grade SHARP picks as moneyline only (who won), ignoring the `line` field. Semantically correct: "sharp side won" = their team won.

### Rule
> **INVARIANT**: Never assume a field contains what its name suggests — trace data flow. `line_variance` is not `line` (spread).

---

## 42. Undefined PYTZ_AVAILABLE Variable

### The Mistake
`/grader/queue` returned `NameError: name 'PYTZ_AVAILABLE' is not defined`. Variable was never defined.

### The Fix
Use `core.time_et.now_et()` — the single source of truth for ET timezone. Never use `pytz` in new code.

### Rule
> **INVARIANT**: NEVER reference variables without importing/defining them. All ET timezone logic MUST go through `core.time_et`.

---

## 43. Naive vs Aware Datetime Comparison

### The Mistake
`/grader/daily-report` returned `TypeError: can't compare offset-naive and offset-aware datetimes`. Comparing `datetime.now()` (naive) with stored timestamps (may be aware).

### The Fix
Use `now_et()` for timezone-aware datetime. Handle both naive/aware stored timestamps by checking `ts.tzinfo is None` and adding timezone if needed.

### Rule
> **INVARIANT**: NEVER use `datetime.now()` in grader code — use `now_et()`. ALWAYS handle both naive and aware timestamps when parsing stored data.

---

## 44. Date Window Math Error

### The Mistake
Daily report showing ~290 picks for "yesterday" when actual count was ~150. Wrong date window calculation created 2-day window: `cutoff = now - timedelta(days=days_back + 1)`.

### The Fix
Use exact day boundaries with `.replace(hour=0, minute=0, ...)` and exclusive end bounds (`<` not `<=`).

### Rule
> **INVARIANT**: NEVER use `days_back + 1` / `days_back - 1` for date windows. Use `.replace(hour=0, ...)` for day boundaries with exclusive end bounds.

---

## 45. Grader Performance Same Bug

### The Mistake
`/grader/performance/{sport}` returning `Internal Server Error` — same naive vs aware datetime bug as Lesson 43.

### The Fix
Applied same fix as Lesson 43. Then grepped entire codebase for `datetime.now()` pattern to find all instances.

### Rule
> **INVARIANT**: When fixing a bug, grep the entire codebase for the same pattern. Fix ALL instances in one pass.

---

## 46. Unsurfaced Scoring Adjustments

### The Mistake
`endpoint_matrix_sanity.sh` showed diff=0.748 because `totals_calibration_adj` was applied to `final_score` but NOT surfaced as a field in the pick payload.

### The Fix
Added `"totals_calibration_adj": round(totals_calibration_adj, 3)` to pick output dict. Updated sanity formula to include it.

### Rule
> **INVARIANT**: Every adjustment to `final_score` MUST be surfaced as its own field in the pick payload. Hidden adjustments break sanity math checks.

---

## 47. Script-Only Env Vars Registration

### The Mistake
`env_drift_scan.sh` failed because `MAX_GAMES`, `MAX_PROPS`, `RUNS` were used in scripts but not registered in `RUNTIME_ENV_VARS`.

### The Fix
Added all three to `RUNTIME_ENV_VARS` in `integration_registry.py`.

### Rule
> **INVARIANT**: ANY env var referenced in ANY script or Python file must be in `INTEGRATION_CONTRACTS` or `RUNTIME_ENV_VARS`. Run `env_drift_scan.sh` after adding new env vars.

---

## 48. Python Heredoc __file__ Path Bug

### The Mistake
`prod_endpoint_matrix.sh` failed with `FileNotFoundError`. Inside `python3 - <<'PY'` heredoc, `__file__` resolves to `"<stdin>"`, so `os.path.dirname(__file__)` returns empty string.

### The Fix
Use project-relative paths in heredocs (scripts run from project root). Never use `__file__` or `os.path.dirname(__file__)` in heredocs.

### Rule
> **INVARIANT**: NEVER use `__file__` inside Python heredocs. Use project-relative paths instead.

---

## 49. Props Timeout — Shared Budget Starvation

### The Mistake
`/live/best-bets/NBA` returned 0 props. Game scoring consumed the full `TIME_BUDGET_S = 40.0` hardcoded budget, leaving 0 seconds for props.

### The Fix
Changed to env-configurable: `float(os.getenv("BEST_BETS_TIME_BUDGET_S", "55"))`. Registered in `RUNTIME_ENV_VARS`.

### Rule
> **INVARIANT**: Shared time budgets must leave headroom for ALL consumers. All timeout values should be env-configurable, not hardcoded.

---

## 50. Empty Description Fields in Payload

### The Mistake
All picks returned `"description": ""`. `compute_description()` used object attribute access (`.player_name`) but the live path uses plain dicts through `normalize_pick()`.

### The Fix
Added dict-based description generation directly in `normalize_pick()`: "LeBron James Points Over 25.5", "LAL @ BOS — Lakers ML +150", etc.

### Rule
> **INVARIANT**: When adding a field to the pick contract, verify it's populated in ALL paths. `normalize_pick()` is the single source for pick fields.

---

## 51. Score Inflation from Unbounded Boosts

### The Mistake
Multiple picks had `final_score = 10.0` despite mediocre base scores (~6.5). Individual boost caps existed but no cap on their SUM. Theoretical max boost was 16.8.

### The Fix
Added `TOTAL_BOOST_CAP = 3.5` in `scoring_contract.py`. Sum of confluence+msrf+jason_sim+serp capped before adding to base_score. Context modifier excluded from cap.

### Rule
> **INVARIANT**: Every additive boost system needs BOTH individual caps AND a total cap. Score clustering at boundaries is a red flag.

---

## 52. Jarvis Baseline Not a Bug

### The Mistake
Report claimed `jarvis_score = 5.0` hardcoded at `scoring_pipeline.py:280` made Jarvis "dead code." Investigation found: the hardcoded 5.0 is in dormant `score_candidate()`, NOT the production path.

### The Fix
No fix needed. Production Jarvis is in `live_data_router.py:calculate_jarvis_engine_score()`, fully wired. Sacred number triggers are statistically rare by design — baseline 4.5 is intentional.

### Rule
> **INVARIANT**: Before reporting "dead code," trace the actual production call path. A low/constant score is not a bug if triggers are designed to be rare.

---

## 53. SERP Sequential Bottleneck

### The Mistake
Props scoring returned 0 picks. 107 sequential SerpAPI calls at ~157ms each = ~17s consumed half the game scoring budget, leaving no time for props.

### The Fix
Parallel pre-fetch pattern: extract unique game pairs, pre-fetch both targets per game using `ThreadPoolExecutor(max_workers=16)`, cache results in closure-scoped dict, scoring function checks cache before live call. ~6x faster (17s -> 2-3s).

### Rule
> **INVARIANT**: When an external API is called N times sequentially in a loop, consider parallel pre-fetching. Always measure actual API call counts and latencies.

---

## 54. Props Indentation Bug — Dead Code

### The Mistake
ALL sports returned 0 props. `if _props_deadline_hit: break` was at 12-space indent (game loop level) between `calculate_pick_score()` and all prop processing code (16-space indent). Python interpreted the 16-space code as INSIDE the if block, making `props_picks.append()` unreachable regardless of the flag's value.

### The Fix
Removed misplaced break. Added `if _props_deadline_hit: break` AFTER `props_picks.append()` completes. Each prop is now fully processed before deadline check.

### Rule
> **INVARIANT**: NEVER place control flow (if/break/continue/return) between a function call and the code that uses its result. When moving break statements, verify indentation matches the loop you intend to break from.

---

## 55. Officials Fallback to Tendency Database (Pillar 16)

### The Mistake
ESPN assigns officials 1-2 hours before game time, but best-bets fetches run earlier (10 AM, 12 PM, 6 PM). Pillar 16 officials integration returned empty `[]` for pre-game picks because `_officials_by_game` only stored results where `available=True`. With no officials data available, the entire Pillar 16 adjustment was skipped.

### The Fix
Added `get_likely_officials_for_game()` function to `officials_data.py` that returns a randomly selected official from the tendency database as fallback. Added fallback logic in Pillar 16 section of `live_data_router.py` (around line 5040) that calls this function when ESPN data is unavailable. Fallback results are marked with `confidence: "LOW"` and `source: "tendency_database_fallback"`.

```python
# officials_data.py - New fallback function
def get_likely_officials_for_game(sport: str, home_team: str, game_time: datetime = None) -> Dict[str, Any]:
    officials_map = {"NBA": NBA_REFEREES, "NFL": NFL_REFEREES, "NHL": NHL_REFEREES}.get(sport.upper(), {})
    if not officials_map:
        return {"available": False, "reason": "NO_TENDENCY_DATA"}
    officials_list = list(officials_map.keys())
    if officials_list:
        lead = random.choice(officials_list)
        return {"available": True, "lead_official": lead, "source": "tendency_database_fallback", "confidence": "LOW"}
    return {"available": False, "reason": "EMPTY_DATABASE"}
```

### Rule
> **INVARIANT**: When external data sources have timing gaps (ESPN officials assigned late), always provide a fallback using existing data (tendency database) with appropriate confidence markers.

---

## Quick Reference: The Golden Rules

1. **Database**: Always use `with get_db() as db:` context manager
2. **Parameters**: When adding params, wire them to real data (never hardcode None)
3. **Timing**: New signals need 24-48 hours to accumulate data
4. **Naming**: Comment which similarly-named function you're using
5. **Imports**: Extend existing import lines, don't scatter new ones
6. **Errors**: Wrap all optional signals in try/except
7. **Testing**: Test with None/empty data, not just happy path
8. **Data Sources**: Always pair raw data with interpretation/tendency database
9. **Alt Data Wiring**: Follow full data flow: fetch -> pass -> apply -> add reasons
10. **Timezones**: Both datetimes in a comparison MUST be timezone-aware (or both naive)
11. **Env Var Alternatives**: Use OR logic for alternative env vars (any satisfies)
12. **Variable Init**: Initialize variables BEFORE conditional blocks that may skip assignment
13. **Scope**: Shared calculations go OUTSIDE type-specific blocks
14. **Team Names**: Check API name format vs data format for each sport
15. **Parameter Threading**: Update ALL call sites when adding function parameters
16. **pick_type Values**: Game picks are "SPREAD"/"MONEYLINE"/"TOTAL"/"SHARP", NOT "GAME"
17. **Grader Weights**: Initialize weights for ALL pick types (prop + game stat types)
18. **Sanity Formula**: Every adjustment to final_score MUST appear in sanity math AND pick payload
19. **Shell Export**: Use `export VAR=value` when Python subprocesses need variables
20. **Heredoc Paths**: Never use `__file__` in Python heredocs — use project-relative paths
21. **Boost Caps**: Both individual AND total boost caps required
22. **Control Flow**: Never place break/return between a call and the code using its result
23. **Grep After Fix**: When fixing a bug, grep the codebase for the same pattern and fix ALL instances
24. **API Timing Fallbacks**: When external APIs have timing gaps (data assigned late), provide fallbacks using existing tendency/lookup databases with confidence markers

---

## Adding New Lessons

When you encounter a bug or issue, add it here:

```markdown
## N. [Short Title]

### The Mistake
What went wrong.

### The Fix
How to do it correctly (with code examples).

### Rule
> **INVARIANT**: The rule to follow going forward.
```
